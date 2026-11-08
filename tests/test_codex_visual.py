"""Offline visual lifecycle tests: no network, credentials or browser install."""
import json
import os
import signal
import struct
import subprocess
import sys
import time
import zlib
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import codex_pilot as pilot  # noqa: E402
import codex_visual as visual  # noqa: E402


def png(width, height):
    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xffffffff)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)) +
            chunk(b"IDAT", zlib.compress((b"\0" + b"\xff\xff\xff" * width) * height)) + chunk(b"IEND", b""))


def entry(name, complete=True):
    value = {"status": "complete" if complete else "partial", "diagnostics": [], "blocked_requests": 0}
    if complete:
        viewport = visual.VIEWPORTS[name]
        value["geometry"] = {**viewport, "scroll_width": viewport["width"], "scroll_height": viewport["height"],
                             "inspected_elements": 4, "elements_truncated": False, "overflow": []}
    return value


@pytest.fixture
def source(tmp_path, monkeypatch):
    monkeypatch.delenv("CLAUDE_SEO_LOCAL_TARGETS", raising=False)
    fixture = tmp_path / "fixture.html"
    fixture.write_text("<!doctype html><html><head><title>Saved</title></head><body>Saved fixture</body></html>")
    root = tmp_path / "source"
    pilot.capture("https://example.com/", root, fixture)
    return root


def fake_worker(source, output, browser, timeout, *, missing=None):
    results = {}
    for name, viewport in visual.VIEWPORTS.items():
        if name == missing:
            continue
        for suffix, data in (("html", b"<html><body>Saved fixture</body></html>"), ("png", png(**viewport))):
            pilot.write_new(output / f"{name}.{suffix}", data)
        results[name] = entry(name)
    visual._write_render(output, results, browser_version="test-browser-1")
    return None


def capture(source, tmp_path, worker=fake_worker):
    output = tmp_path / "visual"
    with patch.object(visual, "doctor", return_value={"ready": True}), patch.object(visual, "_run_worker", side_effect=worker):
        manifest = visual.capture(source, output, "/explicit/browser")
    return output, manifest


def role(output, manifest, status="complete"):
    value = {"role": "visual", "capture_sha256": manifest["evidence"]["source"]["capture_sha256"],
             "render_sha256": manifest["evidence_sha256"], "status": status,
             "findings": ["Viewport reviewed."], "limitations": list(visual.LIMITATIONS)}
    (output / "findings/visual.json").write_bytes(pilot.encode(value))
    return value


def test_success_requires_role_and_finalization_preserves_evidence(source, tmp_path):
    before = {path.name: path.read_bytes() for path in (source / "capture").iterdir()}
    source_manifest = (source / pilot.MANIFEST).read_bytes()
    output, manifest = capture(source, tmp_path)
    assert visual.validate(output)["complete"] is False
    role(output, manifest)
    assert visual.validate(output)["complete"] is True
    result = visual.finalize(output)
    assert result["phase"] == "complete"
    after = json.loads((output / visual.MANIFEST).read_bytes())
    assert after["evidence"] == manifest["evidence"]
    assert after["evidence_sha256"] == manifest["evidence_sha256"]
    assert (source / pilot.MANIFEST).read_bytes() == source_manifest
    assert {path.name: path.read_bytes() for path in (source / "capture").iterdir()} == before
    with pytest.raises(visual.VisualError, match="already finalized"):
        visual.finalize(output)


def test_missing_browser_is_saved_as_partial(source, tmp_path):
    output = tmp_path / "visual"
    manifest = visual.capture(source, output, "/does/not/exist")
    assert manifest["evidence"]["worker_status"] == "partial"
    assert visual.validate(output)["viewports"] == {"desktop": "partial", "mobile": "partial"}
    assert visual.finalize(output)["phase"] == "partial"
    assert not visual.doctor("relative-browser")["browser_executable"]


def test_failed_viewport_stays_partial_with_complete_role(source, tmp_path):
    def partial(*args):
        return fake_worker(*args, missing="mobile")
    output, manifest = capture(source, tmp_path, partial)
    role(output, manifest)
    assert visual.validate(output)["complete"] is False
    assert visual.finalize(output)["phase"] == "partial"


def test_worker_timeout_even_after_both_viewports_stays_partial(source, tmp_path):
    def timeout(*args):
        fake_worker(*args)
        return "Renderer exceeded the whole-run timeout."
    output, manifest = capture(source, tmp_path, timeout)
    role(output, manifest)
    assert visual.finalize(output)["phase"] == "partial"


@pytest.mark.parametrize("name", ["desktop.html", "desktop.png", "render.json", "source_html", "source_manifest", "role", "manifest"])
def test_tampered_artifacts_or_identities_rejected(source, tmp_path, name):
    output, manifest = capture(source, tmp_path)
    role(output, manifest)
    if name == "source_html":
        path = source / "capture/page.html"
        path.write_bytes(path.read_bytes() + b"!")
    elif name == "source_manifest":
        path = source / pilot.MANIFEST
        path.write_bytes(path.read_bytes() + b" ")
    elif name == "role":
        value = role(output, manifest)
        value["render_sha256"] = "0" * 64
        (output / "findings/visual.json").write_bytes(pilot.encode(value))
    elif name == "manifest":
        manifest["evidence"]["device_scale_factor"] = 2
        (output / visual.MANIFEST).write_bytes(pilot.encode(manifest))
    else:
        path = output / name
        path.write_bytes(path.read_bytes() + b"!")
    with pytest.raises(visual.VisualError):
        visual.validate(output)


def test_finalized_report_and_role_are_immutable(source, tmp_path):
    output, manifest = capture(source, tmp_path)
    role(output, manifest)
    visual.finalize(output)
    report = output / "REPORT.md"
    report.write_text("changed")
    with pytest.raises(visual.VisualError, match="Finalized visual artifact"):
        visual.validate(output)


def test_symlink_and_existing_output_rejected(source, tmp_path):
    linked = tmp_path / "linked"
    linked.symlink_to(source, target_is_directory=True)
    with pytest.raises(visual.VisualError, match="Symlink"):
        visual.capture(linked, tmp_path / "out", "/missing")
    with pytest.raises(visual.VisualError, match="fresh directory"):
        visual.capture(source, source, "/missing")
    output, _ = capture(source, tmp_path)
    original = output / "desktop.png"
    original.unlink()
    original.symlink_to(output / "mobile.png")
    with pytest.raises(visual.VisualError, match="Symlink"):
        visual.validate(output)


def test_reject_failed_source_before_creating_output(source, tmp_path):
    manifest_path = source / pilot.MANIFEST
    manifest = json.loads(manifest_path.read_bytes())
    manifest["capture"]["complete"] = False
    manifest_path.write_bytes(pilot.encode(manifest))
    output = tmp_path / "out"
    with pytest.raises(visual.VisualError):
        visual.capture(source, output, "/missing")
    assert not output.exists()


def test_png_dimensions_crc_and_decoded_size_are_verified():
    viewport = visual.VIEWPORTS["desktop"]
    data = png(**viewport)
    visual._png(data, viewport)
    with pytest.raises(visual.VisualError, match="dimensions"):
        visual._png(data, visual.VIEWPORTS["mobile"])
    with pytest.raises(visual.VisualError):
        visual._png(data[:-13], viewport)
    with pytest.raises(visual.VisualError, match="checksum"):
        visual._png(data[:50] + bytes([data[50] ^ 1]) + data[51:], viewport)


def test_diagnostics_and_geometry_bounded(source, tmp_path):
    output, manifest = capture(source, tmp_path)
    metadata = json.loads((output / "render.json").read_bytes())
    metadata["viewports"]["desktop"]["diagnostics"] = ["x" * 501]
    (output / "render.json").write_bytes(pilot.encode(metadata))
    with pytest.raises(visual.VisualError, match="diagnostics"):
        visual.render_data(output)
    assert not visual._geometry({**entry("desktop")["geometry"], "overflow": [{}] * 21}, visual.VIEWPORTS["desktop"])
    assert not visual.bounded_strings(["x"] * 257)
    assert not visual.bounded_strings(["x" * 10001])


def test_missing_or_unhashed_artifact_never_complete(source, tmp_path):
    output, manifest = capture(source, tmp_path)
    role(output, manifest)
    (output / "desktop.png").unlink()
    with pytest.raises((visual.VisualError, OSError)):
        visual.validate(output)


def test_source_change_during_worker_rejected(source, tmp_path):
    def change(*args):
        fake_worker(*args)
        path = source / pilot.MANIFEST
        path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(visual.VisualError, match="changed while rendering"):
        capture(source, tmp_path, change)


def test_worker_group_cleanup_success_and_timeout(monkeypatch, tmp_path):
    class FakeProcess:
        pid = 4321
        calls = 0
        def wait(self, timeout=None):
            self.calls += 1
            if timeout is not None and timeout == 1:
                raise subprocess.TimeoutExpired("worker", 1)
            return 0
    fake = FakeProcess()
    killed = []
    monkeypatch.setattr(visual.subprocess, "Popen", lambda *a, **kw: fake)
    monkeypatch.setattr(visual.os, "killpg", lambda pid, sig: killed.append((pid, sig)))
    assert "timeout" in visual._run_worker(tmp_path, tmp_path, "/browser", 1)
    assert killed == [(fake.pid, signal.SIGKILL)]
    killed.clear()
    assert visual._run_worker(tmp_path, tmp_path, "/browser", 2) is None
    assert killed == [(fake.pid, signal.SIGKILL)]


@pytest.mark.skipif(os.name != "posix", reason="POSIX process groups required")
def test_timeout_kills_actual_worker_descendant(monkeypatch, tmp_path):
    marker = tmp_path / "child.pid"
    actual_popen = subprocess.Popen
    program = ("import pathlib,subprocess,sys,time; "
               "p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); "
               f"pathlib.Path({str(marker)!r}).write_text(str(p.pid)); time.sleep(60)")
    def launch(command, **kwargs):
        return actual_popen([sys.executable, "-c", program], **kwargs)
    monkeypatch.setattr(visual.subprocess, "Popen", launch)
    try:
        assert "timeout" in visual._run_worker(tmp_path, tmp_path, "/browser", 1)
        child_pid = int(marker.read_text())
        for _ in range(50):
            try:
                os.kill(child_pid, 0)
            except ProcessLookupError:
                break
            # An already dead orphan can remain as a zombie until init reaps it.
            state = subprocess.run(["ps", "-o", "stat=", "-p", str(child_pid)], capture_output=True, text=True).stdout.strip()
            if not state or state.startswith("Z"):
                break
            time.sleep(.02)
        else:
            pytest.fail("Worker descendant survived process-group cleanup")
    finally:
        if marker.exists():
            try:
                os.kill(int(marker.read_text()), signal.SIGKILL)
            except ProcessLookupError:
                pass


def test_isolated_cli_doctor_and_missing_browser_capture(source, tmp_path):
    script = Path(visual.__file__).absolute()
    doctor = subprocess.run([sys.executable, "-I", "-B", str(script), "doctor", "--browser", "/missing"],
                            capture_output=True, text=True, timeout=10)
    assert doctor.returncode == 1, doctor.stderr
    assert json.loads(doctor.stdout)["ready"] is False
    output = tmp_path / "isolated-visual"
    captured = subprocess.run([sys.executable, "-I", "-B", str(script), "capture", "--source", str(source),
                               "--output", str(output), "--browser", "/missing", "--timeout", "2"],
                              capture_output=True, text=True, timeout=10)
    assert captured.returncode == 1, captured.stderr
    result = json.loads(captured.stdout)
    assert result["evidence"]["worker_status"] == "partial"
    checked = subprocess.run([sys.executable, "-I", "-B", str(script), "validate", "--output", str(output)],
                             capture_output=True, text=True, timeout=10)
    assert checked.returncode == 0, checked.stderr
    assert json.loads(checked.stdout)["complete"] is False


def test_failed_cli_finalization_has_nonzero_exit_and_retains_report(source, tmp_path):
    output, _ = capture(source, tmp_path)
    result = subprocess.run([sys.executable, "-I", "-B", visual.__file__, "finalize", "--output", str(output)],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 1
    assert json.loads(result.stdout)["phase"] == "partial"
    assert (output / "REPORT.md").is_file()
    assert visual.validate(output)["valid"] is True


def test_original_charset_recorded_from_verified_transport(source, tmp_path):
    path = source / "capture/transport.json"
    transport = json.loads(path.read_bytes())
    transport["headers"]["Content-Type"] = 'text/html; charset="windows-1252"'
    path.write_bytes(pilot.encode(transport))
    manifest_path = source / pilot.MANIFEST
    manifest = json.loads(manifest_path.read_bytes())
    manifest["artifacts"]["capture/transport.json"] = visual.file_record(path, pilot.MAX_BYTES)
    manifest_path.write_bytes(pilot.encode(manifest))
    assert visual.content_type(source) == "text/html; charset=windows-1252"
    output, manifest = capture(source, tmp_path)
    assert manifest["evidence"]["content_type"] == "text/html; charset=windows-1252"
    assert manifest["evidence"]["browser_version"] == "test-browser-1"
    assert visual.validate(output)["valid"]


def _dead(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    state = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True).stdout.strip()
    return not state or state.startswith("Z")


@pytest.mark.skipif(os.name != "posix", reason="POSIX process groups required")
def test_sigterm_supervisor_cleans_worker_and_descendant(tmp_path):
    marker = tmp_path / "pids.json"
    child_program = ("import json,os,pathlib,subprocess,sys,time; "
                     "p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); "
                     f"pathlib.Path({str(marker)!r}).write_text(json.dumps([os.getpid(),p.pid])); time.sleep(60)")
    program = (f"import sys; sys.path.insert(0,{str(Path(visual.__file__).parent)!r})\n"
               "import codex_visual as v\nfrom pathlib import Path\n"
               "original=v.subprocess.Popen\n"
               f"def launch(command,**kwargs): return original([sys.executable,'-c',{child_program!r}],**kwargs)\n"
               "v.subprocess.Popen=launch\nv._run_worker(Path('.'),Path('.'),'/browser',60)\n")
    supervisor = subprocess.Popen([sys.executable, "-I", "-B", "-c", program],
                                  stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    pids = []
    try:
        for _ in range(100):
            if marker.exists():
                pids = json.loads(marker.read_text())
                break
            if supervisor.poll() is not None:
                pytest.fail("Supervisor failed before launching the worker")
            time.sleep(.02)
        assert len(pids) == 2
        supervisor.terminate()
        assert supervisor.wait(timeout=5) == 128 + signal.SIGTERM
        for _ in range(100):
            if all(_dead(pid) for pid in pids):
                break
            time.sleep(.02)
        assert all(_dead(pid) for pid in pids)
    finally:
        if supervisor.poll() is None:
            supervisor.kill()
            supervisor.wait()
        if pids:
            try:
                os.killpg(pids[0], signal.SIGKILL)
            except ProcessLookupError:
                pass
