"""Prepared Codex dispatch is additive and never enables legacy providers."""
from __future__ import annotations

import importlib.util
import json
import os
import signal
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("runtime_codex_test", ROOT / "scripts/runtime.py")
assert SPEC and SPEC.loader
runtime = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runtime)


def args(tmp_path, **kwargs):
    return SimpleNamespace(host="codex", state_root=str(tmp_path / "state"), script="codex_pilot.py",
                           extension=None, script_args=["doctor"], json=True, **kwargs)


def fixture_source(tmp_path, monkeypatch):
    root = tmp_path / "source"
    (root / "scripts").mkdir(parents=True)
    (root / "scripts/codex_pilot.py").write_text("pass\n")
    (root / "scripts/codex_audit.py").write_text("pass\n")
    (root / "scripts/codex_visual.py").write_text("pass\n")
    (root / "scripts/codex_sitemap.py").write_text("pass\n")
    monkeypatch.setattr(runtime, "_root", lambda: root)
    return root


def test_codex_dispatch_safe_argv_clean_env_and_exit(tmp_path, monkeypatch):
    root = fixture_source(tmp_path, monkeypatch)
    for key in ("HOME", "CODEX_HOME", "PYTHONPATH", "PYTHONHOME", "HTTPS_PROXY", "NETRC", "GOOGLE_APPLICATION_CREDENTIALS",
                "GOOGLE_API_KEY", "CLAUDE_SEO_DATA_DIR", "CLAUDE_PLUGIN_DATA", "PLUGIN_DATA", "CLAUDE_SEO_PYTHON"):
        monkeypatch.setenv(key, "ambient-secret")
    call = args(tmp_path)
    call.script_args = ["capture", "--url", "https://example.com/?x=$()", "--output", "path with spaces"]
    with patch.object(runtime.subprocess, "run", return_value=SimpleNamespace(returncode=7)) as run:
        assert runtime.command_run(call) == 7
    argv = run.call_args.args[0]
    assert argv == [sys.executable, "-I", "-B", str(root / "scripts/codex_pilot.py"), *call.script_args]
    env = run.call_args.kwargs["env"]
    assert "ambient-secret" not in env.values()
    assert env["CODEX_SEO_CONFIG_DIR"] == str(tmp_path / "state/config")
    assert env["CODEX_SEO_CACHE_DIR"] == str(tmp_path / "state/cache")
    assert env["CODEX_SEO_RUNTIME_DIR"] == str(tmp_path / "state/runtime")
    assert env["PYTHONNOUSERSITE"] == env["PYTHONDONTWRITEBYTECODE"] == "1"
    assert env["PATH"] == os.defpath


@pytest.mark.parametrize("script,extension", [("google_auth.py", None), ("parse_html.py", None),
                                              ("../codex_pilot.py", None), ("codex_pilot.py", "banana"),
                                              ("../codex_audit.py", None), ("codex_audit.py", "banana")])
def test_blocked_dispatch_never_starts_subprocess(tmp_path, monkeypatch, script, extension):
    fixture_source(tmp_path, monkeypatch)
    call = args(tmp_path)
    call.script, call.extension = script, extension
    with patch.object(runtime.subprocess, "run", side_effect=AssertionError("dispatch")):
        with pytest.raises(ValueError, match="only codex_pilot"):
            runtime.command_run(call)


def test_codex_audit_dispatch_is_explicit_and_uses_same_boundary(tmp_path, monkeypatch):
    root = fixture_source(tmp_path, monkeypatch)
    call = args(tmp_path)
    call.script = "codex_audit.py"
    call.script_args = ["route", "audit"]
    with patch.object(runtime.subprocess, "run", return_value=SimpleNamespace(returncode=0)) as run:
        assert runtime.command_run(call) == 0
    assert run.call_args.args[0] == [sys.executable, "-I", "-B", str(root / "scripts/codex_audit.py"),
                                    "route", "audit"]
    assert run.call_args.kwargs["env"]["CODEX_SEO_STATE_ROOT"] == str(tmp_path / "state")
    assert runtime.CODEX_ALLOWED_SCRIPTS == {"codex_pilot.py", "codex_audit.py", "codex_visual.py", "codex_sitemap.py"}


def test_visual_dispatch_requires_explicit_staged_script(tmp_path, monkeypatch):
    root = fixture_source(tmp_path, monkeypatch)
    call = args(tmp_path)
    call.script, call.script_args = "codex_visual.py", ["doctor", "--browser", "/prepared/chromium"]
    with patch.object(runtime.subprocess, "run", return_value=SimpleNamespace(returncode=0)) as run:
        assert runtime.command_run(call) == 0
    assert run.call_args.args[0][3] == str(root / "scripts/codex_visual.py")
    (root / "scripts/codex_visual.py").unlink()
    with patch.object(runtime.subprocess, "run", side_effect=AssertionError("dispatch")):
        with pytest.raises(ValueError, match="missing or outside"):
            runtime.command_run(call)


def test_sitemap_dispatch_requires_explicit_staged_script(tmp_path, monkeypatch):
    root = fixture_source(tmp_path, monkeypatch)
    call = args(tmp_path)
    call.script, call.script_args = "codex_sitemap.py", ["validate", "--output", "/saved/evidence"]
    with patch.object(runtime.subprocess, "run", return_value=SimpleNamespace(returncode=0)) as run:
        assert runtime.command_run(call) == 0
    assert run.call_args.args[0] == [sys.executable, "-I", "-B", str(root / "scripts/codex_sitemap.py"), *call.script_args]
    (root / "scripts/codex_sitemap.py").unlink()
    with patch.object(runtime.subprocess, "run", side_effect=AssertionError("dispatch")):
        with pytest.raises(ValueError, match="missing or outside"):
            runtime.command_run(call)


def test_missing_audit_in_pilot_only_stage_does_not_fall_back(tmp_path, monkeypatch):
    root = fixture_source(tmp_path, monkeypatch)
    (root / "scripts/codex_audit.py").unlink()
    call = args(tmp_path)
    call.script = "codex_audit.py"
    with patch.object(runtime.subprocess, "run", side_effect=AssertionError("dispatch")):
        with pytest.raises(ValueError, match="missing or outside"):
            runtime.command_run(call)


def test_symlinked_script_is_rejected(tmp_path, monkeypatch):
    root = fixture_source(tmp_path, monkeypatch)
    script = root / "scripts/codex_pilot.py"
    script.unlink()
    script.symlink_to(tmp_path / "outside")
    with patch.object(runtime.subprocess, "run", side_effect=AssertionError("dispatch")):
        with pytest.raises(ValueError):
            runtime.command_run(args(tmp_path))


def test_setup_refuses_without_creating_state(tmp_path, monkeypatch, capsys):
    fixture_source(tmp_path, monkeypatch)
    with patch.object(runtime.subprocess, "run", side_effect=AssertionError("installation")), \
            patch.object(runtime, "_status", side_effect=AssertionError("legacy state")):
        assert runtime.command_setup(args(tmp_path)) == 2
    assert "prepared runtime only; installation not supported" in capsys.readouterr().err
    assert not (tmp_path / "state").exists()


def test_doctor_uses_prepared_probe_no_legacy_reads_or_writes(tmp_path, monkeypatch, capsys):
    fixture_source(tmp_path, monkeypatch)
    probe = {"ready": True, "credentials": "not inspected", "dependencies": {"requests": {"available": True}}, "parser": "lxml"}
    with patch.object(runtime, "_status", side_effect=AssertionError("legacy state")), \
            patch.object(runtime, "_load_state", side_effect=AssertionError("legacy marker")), \
            patch.object(Path, "mkdir", side_effect=AssertionError("write")), \
            patch.object(runtime.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout=json.dumps(probe))) as run:
        assert runtime.command_doctor(args(tmp_path)) == 0
    public = json.loads(capsys.readouterr().out)
    assert public["host"] == "codex"
    assert public["mode"] == "prepared"
    assert public["ready"] is True
    assert "state" not in public
    assert run.call_args.args[0][-1] == "doctor"
    assert not (tmp_path / "state").exists()


def test_doctor_failing_probe_and_unsupported_python_not_ready(tmp_path, monkeypatch, capsys):
    fixture_source(tmp_path, monkeypatch)
    with patch.object(runtime.subprocess, "run", return_value=SimpleNamespace(returncode=2, stdout="not JSON")):
        assert runtime.command_doctor(args(tmp_path)) == 3
    assert json.loads(capsys.readouterr().out)["ready"] is False
    with patch.object(runtime.subprocess, "run", side_effect=subprocess.TimeoutExpired("private-command", 30)):
        assert runtime.command_doctor(args(tmp_path)) == 3
    assert "private-command" not in capsys.readouterr().out
    with patch.object(runtime, "_python_supported", return_value=False), \
            patch.object(runtime.subprocess, "run", side_effect=AssertionError("unsupported probe")):
        assert runtime.command_doctor(args(tmp_path)) == 3


def test_missing_root_and_state_root_without_host_fail(tmp_path, monkeypatch):
    fixture_source(tmp_path, monkeypatch)
    with patch.object(runtime.subprocess, "run", side_effect=AssertionError("dispatch")):
        assert runtime.main(["--host", "codex", "doctor", "--json"]) == 2
        assert runtime.main(["--state-root", str(tmp_path / "state"), "doctor"]) == 2


def test_empty_explicit_state_root_cannot_fall_back_to_legacy():
    with patch.object(runtime, "_status", side_effect=AssertionError("legacy state access")), \
            patch.object(runtime.subprocess, "run", side_effect=AssertionError("dispatch")):
        assert runtime.main(["--state-root", "", "doctor", "--json"]) == 2


def test_codex_signal_propagation(tmp_path, monkeypatch):
    fixture_source(tmp_path, monkeypatch)
    with patch.object(runtime.subprocess, "run", return_value=SimpleNamespace(returncode=-signal.SIGTERM)), \
            patch.object(runtime.os, "kill") as kill:
        assert runtime.command_run(args(tmp_path)) == 128 + signal.SIGTERM
    kill.assert_called_once_with(os.getpid(), signal.SIGTERM)


def test_absent_host_keeps_legacy_dispatch(tmp_path, monkeypatch):
    root = fixture_source(tmp_path, monkeypatch)
    call = SimpleNamespace(script="fetch_page.py", extension=None, script_args=["https://example.com"])
    with patch.object(runtime, "_resolve_script", return_value=root / "scripts/fetch_page.py"), \
            patch.object(runtime, "_status", return_value={"ready": True, "python_path": Path("legacy-python"), "data_dir": tmp_path}), \
            patch.object(runtime.subprocess, "run", return_value=SimpleNamespace(returncode=0)) as run:
        assert runtime.command_run(call) == 0
    assert run.call_args.args[0][0] == "legacy-python"
    assert "-I" not in run.call_args.args[0]


def test_real_prepared_doctor(tmp_path):
    state = tmp_path / "state"
    result = subprocess.run([sys.executable, "-I", "-B", str(ROOT / "scripts/runtime.py"),
                             "--host", "codex", "--state-root", str(state), "doctor", "--json"],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["ready"] is True
    assert not state.exists()
