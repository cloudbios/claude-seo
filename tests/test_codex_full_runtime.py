"""Full Codex dispatch and setup policy, without installs or provider calls."""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('full_runtime', ROOT / 'scripts/codex_runtime.py')
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)


def paths(tmp_path):
    root = tmp_path.resolve() / 'state'
    return runtime.paths_module.resolve_codex_paths(str(root), ROOT)


def test_explicit_allowlist_and_extension_traversal():
    assert runtime.resolve_script('google_auth.py').name == 'google_auth.py'
    assert runtime.resolve_script('generate.py', 'banana').name == 'generate.py'
    for name, extension in [('runtime.py', None), ('../google_auth.py', None), ('generate.py', '../banana'), ('setup.py', 'banana')]:
        with pytest.raises(ValueError):
            runtime.resolve_script(name, extension)


def test_minimal_environment_is_scoped_to_provider(tmp_path, monkeypatch):
    for key in ('HOME', 'PYTHONPATH', 'HTTPS_PROXY', 'CLAUDE_PLUGIN_DATA', 'GOOGLE_APPLICATION_CREDENTIALS', 'GOOGLE_API_KEY', 'MOZ_API_KEY', 'DATAFORSEO_PASSWORD'):
        monkeypatch.setenv(key, 'sentinel-' + key)
    result = runtime.environment(paths(tmp_path), 'google_auth.py')
    assert result['GOOGLE_API_KEY'] == 'sentinel-GOOGLE_API_KEY'
    assert all(k not in result for k in ('HOME', 'PYTHONPATH', 'HTTPS_PROXY', 'CLAUDE_PLUGIN_DATA', 'GOOGLE_APPLICATION_CREDENTIALS', 'MOZ_API_KEY', 'DATAFORSEO_PASSWORD'))
    assert result['NETRC'] == os.devnull
    assert Path(result['NPM_CONFIG_CACHE']) == paths(tmp_path)['cache'] / 'npm'
    assert 'CODEX_SEO_ALLOW_WRITE' not in result


@pytest.mark.parametrize('script,args,extension', [
    ('indexnow_submit.py', ['https://example.com'], None),
    ('indexing_notify.py', ['https://example.com'], None),
    ('content_humanize.py', ['article.md'], None),
    ('google_auth.py', ['--au', '--creds', 'client.json'], None),
    ('google_auth.py', ['--exch', '--code', 'secret'], None),
    ('generate.py', ['--prompt', 'image'], 'banana'),
    ('setup_mcp.py', ['--remove'], 'banana'),
    ('presets.py', ['delete', 'brand', '--confirm'], 'banana'),
])
def test_mutation_entrypoints_require_invocation_permission(script, args, extension):
    assert runtime.requires_write(script, args, extension)


def test_readonly_variants_and_option_forwarding():
    assert not runtime.requires_write('indexing_notify.py', ['--status', 'https://example.com'])
    assert runtime.requires_write('indexing_notify.py', ['--status', '', '--batch', 'urls.txt'])
    assert not runtime.requires_write('presets.py', ['list'], 'banana')
    assert not runtime.requires_write('batch.py', ['--csv', 'input.csv'], 'banana')
    args = runtime.build_parser().parse_args(['--state-root', '/state', 'run', '--extension', 'banana', '--allow-write', 'generate.py', '--prompt', 'hello', '--model', 'm'])
    assert args.allow_write and args.extension == 'banana'
    assert args.script_args == ['--prompt', 'hello', '--model', 'm']


def test_doctor_does_not_install_or_inspect_credentials(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(runtime.subprocess, 'run', lambda *a, **kw: pytest.fail('doctor launched subprocess'))
    assert runtime.doctor(paths(tmp_path), SimpleNamespace(json=True)) == 3
    result = json.loads(capsys.readouterr().out)
    assert result['credentials'] == 'not inspected'
    assert not result['ready']
    assert not paths(tmp_path)['state_root'].exists()


def test_run_checks_permission_before_subprocess(tmp_path, monkeypatch):
    monkeypatch.setattr(runtime.subprocess, 'run', lambda *a, **kw: pytest.fail('unapproved mutation launched'))
    args = SimpleNamespace(script='indexnow_submit.py', extension=None, script_args=['https://example.com'], allow_write=False)
    with pytest.raises(ValueError, match='allow-write'):
        runtime.run(paths(tmp_path), args)


def test_dispatch_uses_isolation_and_masks_explicit_secrets(tmp_path, monkeypatch, capsys):
    state = paths(tmp_path)
    state['config'].mkdir(parents=True)
    (state['config'] / 'google-api.json').write_text('{"api_key":"test-secret-value"}')
    monkeypatch.setattr(runtime, 'status', lambda _: {'ready': True, 'python_path': Path('/python')})
    captured = {}
    def launch(argv, **kw):
        captured.update(argv=argv, **kw)
        return subprocess.CompletedProcess(argv, 0, 'failed test-secret-value', '')
    monkeypatch.setattr(runtime.subprocess, 'run', launch)
    args = SimpleNamespace(script='google_auth.py', extension=None, script_args=['--check'], allow_write=False)
    assert runtime.run(state, args) == 0
    assert captured['argv'][1:3] == ['-I', '-B']
    assert 'test-secret-value' not in capsys.readouterr().out


def test_setup_rolls_back_previous_runtime_on_manifest_failure(tmp_path, monkeypatch):
    state = paths(tmp_path)
    final = state['runtime'] / '.venv'
    final.mkdir(parents=True)
    (final / 'preserved').write_text('old')
    (state['runtime'] / 'runtime-state.json').write_text(json.dumps({'codex_runtime_schema': runtime.SCHEMA}))
    monkeypatch.setattr(runtime.legacy, '_python_supported', lambda: True)
    def fake_checked(argv, **kwargs):
        if 'venv' in argv:
            Path(argv[-1]).mkdir()
    monkeypatch.setattr(runtime.legacy, '_run_checked', fake_checked)
    monkeypatch.setattr(runtime, 'status', lambda _: (_ for _ in ()).throw(OSError('manifest failure')))
    with pytest.raises(OSError):
        runtime.setup(state, SimpleNamespace(skip_browser=True))
    assert (final / 'preserved').read_text(encoding="utf-8") == 'old'
    assert not (state['runtime'] / '.setup.lock').exists()


def test_setup_refuses_unowned_existing_venv(tmp_path, monkeypatch):
    state = paths(tmp_path)
    (state['runtime'] / '.venv').mkdir(parents=True)
    monkeypatch.setattr(runtime.legacy, '_python_supported', lambda: True)
    with pytest.raises(ValueError, match='unmanaged'):
        runtime.setup(state, SimpleNamespace(skip_browser=True))


def test_platform_tool_path_uses_static_install_locations(tmp_path, monkeypatch):
    monkeypatch.setenv('PATH', '/untrusted/caller/bin')
    monkeypatch.setattr(runtime.sys, 'platform', 'darwin')
    result = runtime.environment(paths(tmp_path), 'unlighthouse_run.py')
    directories = result['PATH'].split(os.pathsep)
    assert '/opt/homebrew/bin' in directories
    assert '/usr/local/bin' in directories
    assert '/untrusted/caller/bin' not in directories
    assert '' not in directories


def test_linux_tool_path_includes_system_local_bin(monkeypatch):
    monkeypatch.setattr(runtime.sys, 'platform', 'linux')
    assert '/usr/local/bin' in runtime.executable_path().split(os.pathsep)


def test_setup_path_resolution_error_has_safe_diagnostic(tmp_path, monkeypatch, capsys):
    def fail_path_resolution(*args):
        raise OSError('sensitive detail')
    monkeypatch.setattr(runtime.paths_module, 'resolve_codex_paths', fail_path_resolution)
    assert runtime.main(['--state-root', str(tmp_path), 'setup']) == 2
    diagnostic = capsys.readouterr().err
    assert 'could not complete' in diagnostic
    assert 'sensitive detail' not in diagnostic
