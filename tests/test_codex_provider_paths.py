"""Codex providers never discover or migrate legacy home credentials."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import codex_paths  # noqa: E402


def load(script):
    spec = importlib.util.spec_from_file_location('provider_test_' + Path(script).stem, ROOT / script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def state(tmp_path, monkeypatch):
    root = tmp_path.resolve() / 'state'
    monkeypatch.setenv('CODEX_SEO_STATE_ROOT', str(root))
    for kind in ('CONFIG', 'CACHE', 'RUNTIME'):
        monkeypatch.delenv('CODEX_SEO_' + kind + '_DIR', raising=False)
    (root / 'config').mkdir(parents=True)
    return root


def test_paths_preserve_legacy_defaults_when_inactive(monkeypatch):
    for key in ('CODEX_SEO_STATE_ROOT', 'CODEX_SEO_CONFIG_DIR', 'CODEX_SEO_CACHE_DIR', 'CODEX_SEO_RUNTIME_DIR'):
        monkeypatch.delenv(key, raising=False)
    assert codex_paths.config_path('ignored', '/legacy/config') == Path('/legacy/config')


def test_explicit_paths_reject_external_credentials_and_symlinks(state, tmp_path):
    assert codex_paths.credential_path('service.json') == str(state / 'config/service.json')
    with pytest.raises(ValueError):
        codex_paths.credential_path('../outside.json')
    with pytest.raises(ValueError):
        codex_paths.credential_path(str(tmp_path / 'outside.json'))
    try:
        (state / 'config' / 'link').symlink_to(tmp_path, target_is_directory=True)
    except OSError:
        pytest.skip('Symlinks are unavailable for this account')
    with pytest.raises(ValueError):
        codex_paths.config_path('link/key.json')


def test_google_uses_only_explicit_config_and_adc(state, monkeypatch):
    monkeypatch.setenv('CLOUDSDK_CONFIG', '/legacy-gcloud')
    monkeypatch.delenv('GOOGLE_APPLICATION_CREDENTIALS', raising=False)
    module = load('scripts/google_auth.py')
    assert module.CONFIG_PATH == str(state / 'config/google-api.json')
    assert module.TOKEN_PATH == str(state / 'config/oauth-token.json')
    assert module._gcloud_adc_path() == str(state / 'config/application_default_credentials.json')
    (state / 'config/google-api.json').write_text(json.dumps({'service_account_path': 'service.json'}))
    assert module.load_config()['service_account_path'] == str(state / 'config/service.json')


@pytest.mark.parametrize('script,attribute,suffix', [
    ('scripts/backlinks_auth.py', 'CONFIG_PATH', 'config/backlinks-api.json'),
    ('scripts/backlinks_auth.py', 'CACHE_DIR', 'cache/commoncrawl'),
    ('scripts/matomo_auth.py', 'CONFIG_PATH', 'config/matomo.json'),
    ('scripts/moz_api.py', 'RATE_LIMIT_FILE', 'cache/moz_last_request.lock'),
    ('scripts/drift_baseline.py', 'DB_DIR', 'cache/drift'),
    ('scripts/dataforseo_costs.py', 'CONFIG_DIR', 'config'),
    ('extensions/banana/scripts/generate.py', 'OUTPUT_DIR', 'cache/banana/generated'),
    ('extensions/banana/scripts/presets.py', 'PRESETS_DIR', 'config/banana/presets'),
    ('extensions/banana/scripts/cost_tracker.py', 'BANANA_DIR', 'cache/banana'),
    ('extensions/banana/scripts/setup_mcp.py', 'SETTINGS_PATH', 'config/banana-mcp.json'),
])
def test_provider_state_uses_explicit_root(state, script, attribute, suffix):
    pytest.importorskip('requests')
    module = load(script)
    assert Path(getattr(module, attribute)) == state / suffix


def test_backlink_cache_override_cannot_escape_state(state):
    pytest.importorskip('requests')
    module = load('scripts/backlinks_auth.py')
    (state / 'config/backlinks-api.json').write_text('{"commoncrawl_cache_dir":"/legacy/cache"}')
    assert module.load_config()['commoncrawl_cache_dir'] == str(state / 'cache/commoncrawl')


def test_extension_generation_guard_precedes_network(state, monkeypatch):
    module = load('extensions/banana/scripts/generate.py')
    monkeypatch.delenv('CODEX_SEO_ALLOW_WRITE', raising=False)
    monkeypatch.setattr(module.urllib.request, 'urlopen', lambda *a, **kw: pytest.fail('network called'))
    with pytest.raises(ValueError, match='allow-write'):
        module.generate_image('prompt', 'model', '1:1', '1K', 'secret')


def test_oauth_client_relative_path_resolves_under_config_before_open(state, tmp_path, monkeypatch):
    module = load('scripts/google_auth.py')
    client = {'installed': {'client_id': 'correct-config-client', 'client_secret': 'secret'}}
    (state / 'config/client.json').write_text(json.dumps(client))
    (tmp_path / 'client.json').write_text(json.dumps({'installed': {'client_id': 'wrong-cwd-client'}}))
    monkeypatch.chdir(tmp_path)
    assert module._load_oauth_client('client.json') == client['installed']


@pytest.mark.parametrize('entrypoint', ['--auth', '--exchange'])
def test_oauth_entrypoints_reject_external_client_before_open(state, tmp_path, monkeypatch, entrypoint):
    module = load('scripts/google_auth.py')
    client = tmp_path / 'external-client.json'
    client.write_text('{"installed":{"client_id":"outside","client_secret":"secret"}}')
    argv = ['google_auth.py', entrypoint, '--creds', str(client)]
    if entrypoint == '--exchange':
        argv.extend(['--code', 'dummy-code'])
    monkeypatch.setattr(sys, 'argv', argv)
    monkeypatch.setattr('builtins.open', lambda *a, **kw: pytest.fail('external OAuth credential was opened'))
    with pytest.raises(ValueError, match='explicit config directory'):
        module.main()


def test_oauth_client_preserves_legacy_cwd_resolution(tmp_path, monkeypatch):
    for key in ('CODEX_SEO_STATE_ROOT', 'CODEX_SEO_CONFIG_DIR', 'CODEX_SEO_CACHE_DIR', 'CODEX_SEO_RUNTIME_DIR'):
        monkeypatch.delenv(key, raising=False)
    module = load('scripts/google_auth.py')
    client = {'installed': {'client_id': 'legacy-cwd-client', 'client_secret': 'secret'}}
    (tmp_path / 'client.json').write_text(json.dumps(client))
    monkeypatch.chdir(tmp_path)
    assert module._load_oauth_client('client.json') == client['installed']
