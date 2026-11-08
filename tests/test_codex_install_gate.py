"""Explicit dependency installation policy without registry or website access."""
from __future__ import annotations

import importlib.util
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location('install_gate_' + name, ROOT / 'scripts' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runtime = load('codex_runtime')
unlighthouse = load('unlighthouse_run')


@pytest.fixture
def state(tmp_path, monkeypatch):
    for key in ('CODEX_SEO_STATE_ROOT', 'CODEX_SEO_CONFIG_DIR', 'CODEX_SEO_CACHE_DIR', 'CODEX_SEO_RUNTIME_DIR', 'CODEX_SEO_ALLOW_INSTALL'):
        monkeypatch.delenv(key, raising=False)
    return runtime.paths_module.resolve_codex_paths(str(tmp_path.resolve() / 'state'), ROOT)


def command(tmp_path):
    return unlighthouse.build_cmd('https://example.com', device='mobile', out_dir=tmp_path,
                                  config_path=tmp_path / 'config.mjs')


def test_legacy_npx_arguments_are_preserved(state, tmp_path):
    argv = command(tmp_path)
    assert argv[:5] == ['npx', '--yes', '--package', unlighthouse.UNLIGHTHOUSE_PIN, 'unlighthouse-ci']
    assert '--offline' not in argv


def test_codex_npx_is_offline_unless_invocation_allows_installs(state, tmp_path, monkeypatch):
    monkeypatch.setenv('CODEX_SEO_STATE_ROOT', str(state['state_root']))
    argv = command(tmp_path)
    assert '--offline' in argv
    assert '--ignore-scripts' in argv
    assert argv.index('--offline') < argv.index('unlighthouse-ci')
    monkeypatch.setenv('CODEX_SEO_ALLOW_INSTALL', '1')
    allowed = command(tmp_path)
    assert '--offline' not in allowed
    assert '--ignore-scripts' not in allowed


def test_runtime_does_not_inherit_install_permission(state, monkeypatch):
    monkeypatch.setenv('CODEX_SEO_ALLOW_INSTALL', '1')
    assert 'CODEX_SEO_ALLOW_INSTALL' not in runtime.environment(state, 'unlighthouse_run.py')
    assert runtime.environment(state, 'unlighthouse_run.py', allow_install=True)['CODEX_SEO_ALLOW_INSTALL'] == '1'


def test_install_flag_is_parsed_before_script_and_forwarded_explicitly(state, monkeypatch):
    args = runtime.build_parser().parse_args(['--state-root', str(state['state_root']), 'run',
                                              '--allow-install', 'unlighthouse_run.py', 'https://example.com'])
    monkeypatch.setattr(runtime, 'status', lambda _: {'ready': True, 'python_path': Path('/python')})
    captured = {}
    def launch(argv, **kwargs):
        captured.update(kwargs)
        return subprocess.CompletedProcess(argv, 0, '', '')
    monkeypatch.setattr(runtime.subprocess, 'run', launch)
    assert runtime.run(state, args) == 0
    assert captured['env']['CODEX_SEO_ALLOW_INSTALL'] == '1'
    assert 'CODEX_SEO_ALLOW_WRITE' not in captured['env']
    assert Path(captured['env']['NPM_CONFIG_CACHE']) == state['cache'] / 'npm'
    assert captured['env']['NPM_CONFIG_USERCONFIG'] == os.devnull


def test_offline_package_failure_is_actionable(state, tmp_path, monkeypatch):
    monkeypatch.setenv('CODEX_SEO_STATE_ROOT', str(state['state_root']))
    monkeypatch.setattr(unlighthouse, 'validate_url_strict', lambda url: (url, '93.184.216.34'))
    monkeypatch.setattr(unlighthouse, '_check_node', lambda: None)
    def launch(argv, **kwargs):
        assert '--offline' in argv
        return subprocess.CompletedProcess(argv, 1, '', 'npm cache miss')
    monkeypatch.setattr(unlighthouse.subprocess, 'run', launch)
    result = unlighthouse.run('https://example.com', output_dir=str(tmp_path / 'report'))
    assert not result['ok']
    assert 'run --allow-install unlighthouse_run.py' in result['error']
