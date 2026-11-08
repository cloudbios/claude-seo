#!/usr/bin/env python3
"""Offline visual evidence from an immutable, successful codex_pilot capture.

No browser discovery, installation, credentials, or live-page requests. The
browser runs in a bounded POSIX process group; findings are a separate handoff.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import signal
import struct
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path
from urllib.parse import urldefrag

sys.dont_write_bytecode = True
_SCRIPTS = str(Path(__file__).resolve().parent)
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)
import codex_pilot as pilot  # noqa: E402

MANIFEST = "visual-manifest.json"
VIEWPORTS = {"desktop": {"width": 1280, "height": 800}, "mobile": {"width": 390, "height": 844}}
MAX_HTML = 2 * 1024 * 1024
MAX_PNG = 8 * 1024 * 1024
MAX_JSON = 128 * 1024
ARTIFACTS = {**{f"{name}.html": MAX_HTML for name in VIEWPORTS},
             **{f"{name}.png": MAX_PNG for name in VIEWPORTS}, "render.json": MAX_JSON}
LIMITATIONS = [
    "Offline saved HTML only (offline-saved-html); this is not a rendered live-page capture.",
    "External assets, fonts, frames, workers, API data and network requests are blocked; appearance may differ from the live page.",
    "Inline HTML, CSS and JavaScript may execute; fixed viewport screenshots cover only the initial viewport.",
    "No field Core Web Vitals, full accessibility audit, live layout or interaction verification.",
]
VisualError = pilot.PilotError


def path_at(root: Path, name: str) -> Path:
    if name not in {*ARTIFACTS, MANIFEST, "REPORT.md", "findings/visual.json"}:
        raise VisualError("Unrecognized visual artifact")
    return pilot.no_symlinks(root / name)


def bounded_strings(value: object, limit: int = 256, width: int = 10000) -> bool:
    return (isinstance(value, list) and len(value) <= limit and
            all(isinstance(item, str) and len(item) <= width for item in value))


def file_record(path: Path, limit: int) -> dict:
    data = pilot.read_bytes(path, limit)
    return {"sha256": pilot.digest(data), "bytes": len(data)}


def source_capture(source: Path) -> tuple[Path, dict, str]:
    root, manifest = pilot.load_capture(source)
    if manifest["capture"].get("complete") is not True or manifest["checks"].get("transport") != "passed":
        raise VisualError("Visual rendering requires a successful complete source capture")
    if os.environ.get("CLAUDE_SEO_LOCAL_TARGETS", "").strip():
        raise VisualError("Unset CLAUDE_SEO_LOCAL_TARGETS for offline visual evidence")
    from url_safety import validate_url
    if not validate_url(manifest["capture"]["final_url"]):
        raise VisualError("Source is not a public HTTP(S) capture")
    return root, manifest, pilot.digest(pilot.read_bytes(root / pilot.MANIFEST))


def doctor(browser: str) -> dict:
    path = Path(browser)
    executable = (path.is_absolute() and path.is_file() and os.access(path, os.X_OK))
    try:
        playwright = importlib.util.find_spec("playwright.sync_api") is not None
    except (ImportError, ModuleNotFoundError):
        playwright = False
    posix = os.name == "posix"
    return {"ready": executable and playwright and posix, "browser": str(path),
            "browser_executable": executable, "playwright": playwright, "posix_process_groups": posix,
            "representation": "offline-saved-html", "network": "blocked",
            "limitations": list(LIMITATIONS)}


def _kill_group(process: subprocess.Popen) -> None:
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait()


def _run_worker(source: Path, output: Path, browser: str, timeout: int) -> str | None:
    """Never pipe untrusted browser output; always reap its entire process group."""
    command = [sys.executable, "-I", "-B", str(Path(__file__).absolute()), "_worker", "--source", str(source),
               "--output", str(output), "--browser", browser, "--timeout", str(timeout)]
    process = None
    previous = signal.getsignal(signal.SIGTERM)

    def terminate(signum, _frame):
        if process is not None:
            _kill_group(process)
        raise SystemExit(128 + signum)

    signal.signal(signal.SIGTERM, terminate)
    try:
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL, start_new_session=True)
        code = process.wait(timeout=timeout)
        return None if code == 0 else "Renderer worker failed; incomplete viewports were not accepted."
    except subprocess.TimeoutExpired:
        return "Renderer exceeded the whole-run timeout; its process group was terminated."
    finally:
        if process is not None:
            _kill_group(process)
        signal.signal(signal.SIGTERM, previous)


def _write_render(output: Path, results: dict, *, content_type: str = "text/html; charset=utf-8",
                  browser_version: str | None = None) -> None:
    """Worker-only atomic checkpoint; completed viewport artifacts are immutable."""
    value = {"representation": "offline-saved-html", "network": "blocked", "viewports": results,
             "content_type": content_type, "browser_version": browser_version}
    data = pilot.encode(value)
    if len(data) > MAX_JSON:
        raise VisualError("Render diagnostics exceed byte budget")
    target = path_at(output, "render.json")
    fd, temporary = tempfile.mkstemp(prefix=".visual-checkpoint-", dir=output)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        pilot.no_symlinks(target)
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def content_type(source: Path) -> str:
    transport = pilot.json_read(source / "capture/transport.json")
    headers = transport.get("headers", {})
    if not isinstance(headers, dict):
        raise VisualError("Invalid source headers")
    value = next((value for key, value in headers.items() if key.lower() == "content-type"), "")
    if not isinstance(value, str) or len(value) > 200 or "\n" in value or "\r" in value:
        raise VisualError("Invalid source content type")
    charset = re.search(r"(?:^|;)\s*charset\s*=\s*[\"']?([A-Za-z0-9._-]{1,40})(?:[\"']|\s|;|$)", value, re.I)
    return "text/html; charset=" + (charset.group(1) if charset else "utf-8")


def _worker(source: Path, output: Path, browser: str, timeout: int) -> None:
    root, manifest, _ = source_capture(source)
    from render_page import render_saved_html
    results = {}
    render_content_type = content_type(root)
    raw = pilot.read_bytes(root / "capture/page.html", MAX_HTML)
    if pilot.digest(raw) != manifest["capture"]["sha256"]:
        raise VisualError("Source bytes changed before rendering")

    def save(name: str, result: dict) -> None:
        metadata = {key: value for key, value in result.items() if key not in ("html", "png", "browser_version")}
        if result["status"] == "complete":
            # Validate before persisting; no truncated/invalid PNG becomes evidence.
            _png(result["png"], VIEWPORTS[name])
            for suffix, key in (("html", "html"), ("png", "png")):
                pilot.write_new(path_at(output, f"{name}.{suffix}"), result[key])
        results[name] = metadata
        _write_render(output, results, content_type=render_content_type, browser_version=result["browser_version"])

    render_saved_html(raw,
                      urldefrag(manifest["capture"]["final_url"])[0], browser_path=browser,
                      timeout_ms=min(5000, timeout * 1000), content_type=render_content_type, on_viewport=save)


def _png(data: bytes, viewport: dict) -> None:
    """Check PNG framing, CRCs, IHDR dimensions and bounded decoded scanlines."""
    if len(data) > MAX_PNG or not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise VisualError("Invalid or oversized viewport PNG")
    offset, chunks, compressed, header = 8, 0, bytearray(), None
    ended = False
    while offset + 12 <= len(data):
        size = struct.unpack(">I", data[offset:offset + 4])[0]
        end = offset + 12 + size
        if end > len(data):
            raise VisualError("Truncated viewport PNG")
        kind = data[offset + 4:offset + 8]
        body = data[offset + 8:offset + 8 + size]
        crc = struct.unpack(">I", data[offset + 8 + size:end])[0]
        if zlib.crc32(kind + body) & 0xffffffff != crc:
            raise VisualError("Viewport PNG checksum mismatch")
        if chunks == 0:
            if kind != b"IHDR" or size != 13:
                raise VisualError("PNG header missing")
            width, height, depth, color, compression, filtering, interlace = struct.unpack(">IIBBBBB", body)
            if (width != viewport["width"] or height != viewport["height"] or depth != 8 or
                    color not in (2, 6) or compression or filtering or interlace):
                raise VisualError("PNG dimensions or format disagree with viewport")
            header = (width, height, 3 if color == 2 else 4)
        elif kind == b"IHDR":
            raise VisualError("Duplicate PNG header")
        if kind == b"IDAT":
            compressed.extend(body)
        if kind == b"IEND":
            if size != 0 or end != len(data):
                raise VisualError("Invalid PNG end")
            ended = True
            break
        offset = end
        chunks += 1
    if not ended or not compressed or header is None:
        raise VisualError("Incomplete viewport PNG")
    width, height, channels = header
    expected = height * (1 + width * channels)
    try:
        decoder = zlib.decompressobj()
        raw = decoder.decompress(bytes(compressed), expected + 1)
        if len(raw) != expected or not decoder.eof or decoder.unused_data:
            raise VisualError("Invalid PNG scanline size")
        stride = 1 + width * channels
        if any(raw[index] > 4 for index in range(0, expected, stride)):
            raise VisualError("Invalid PNG scanline filter")
    except zlib.error as exc:
        raise VisualError("Invalid PNG compressed data") from exc


def _geometry(value: object, viewport: dict) -> bool:
    if not isinstance(value, dict) or set(value) != {"width", "height", "scroll_width", "scroll_height", "inspected_elements", "elements_truncated", "overflow"}:
        return False
    if any(type(value.get(key)) is not int for key in ("width", "height", "scroll_width", "scroll_height", "inspected_elements")):
        return False
    if any(value[key] != viewport[key] for key in ("width", "height")):
        return False
    if not (0 <= value["scroll_width"] <= 1000000 and 0 <= value["scroll_height"] <= 1000000 and
            0 <= value["inspected_elements"] <= 5000 and type(value["elements_truncated"]) is bool):
        return False
    overflow = value["overflow"]
    return (isinstance(overflow, list) and len(overflow) <= 20 and all(
        isinstance(item, dict) and set(item) == {"tag", "left", "right"} and
        isinstance(item["tag"], str) and len(item["tag"]) <= 32 and
        all(type(item[key]) is int and -1000000 <= item[key] <= 1000000 for key in ("left", "right"))
        for item in overflow))


def render_data(root: Path, records: dict | None = None) -> tuple[dict, dict]:
    value = pilot.json_read(path_at(root, "render.json"), MAX_JSON)
    if not isinstance(value, dict) or set(value) != {"representation", "network", "viewports", "content_type", "browser_version"} or value["representation"] != "offline-saved-html" or value["network"] != "blocked":
        raise VisualError("Invalid offline render metadata")
    if (not isinstance(value["content_type"], str) or not re.fullmatch(r"text/html; charset=[A-Za-z0-9._-]{1,40}", value["content_type"]) or
            (value["browser_version"] is not None and (not isinstance(value["browser_version"], str) or not 1 <= len(value["browser_version"]) <= 200))):
        raise VisualError("Invalid render browser version or content type")
    viewports = value["viewports"]
    if not isinstance(viewports, dict) or set(viewports) != set(VIEWPORTS):
        raise VisualError("Missing viewport status")
    actual = {"render.json": file_record(path_at(root, "render.json"), MAX_JSON)}
    for name, expected in VIEWPORTS.items():
        entry = viewports[name]
        if (not isinstance(entry, dict) or entry.get("status") not in ("complete", "partial") or
                not bounded_strings(entry.get("diagnostics"), 32, 500) or
                type(entry.get("blocked_requests")) is not int or not 0 <= entry["blocked_requests"] <= 1000000):
            raise VisualError("Invalid viewport diagnostics")
        if set(entry) != ({"status", "diagnostics", "blocked_requests", "geometry"} if entry["status"] == "complete" else {"status", "diagnostics", "blocked_requests"}):
            raise VisualError("Invalid viewport metadata fields")
        if entry["status"] == "complete":
            if value["browser_version"] is None:
                raise VisualError("Completed viewport lacks browser version")
            if not _geometry(entry.get("geometry"), expected):
                raise VisualError("Invalid viewport geometry")
            _png(pilot.read_bytes(path_at(root, f"{name}.png"), MAX_PNG), expected)
            for extension in ("html", "png"):
                filename = f"{name}.{extension}"
                actual[filename] = file_record(path_at(root, filename), ARTIFACTS[filename])
        elif any(path_at(root, f"{name}.{ext}").exists() for ext in ("html", "png")):
            raise VisualError("Incomplete viewport has unaccepted artifacts")
    if records is not None and records != actual:
        raise VisualError("Render artifact hashes or sizes changed")
    return value, actual


def capture(source: Path, output: Path, browser: str, timeout: int = 20) -> dict:
    if os.name != "posix":
        raise VisualError("Offline renderer requires POSIX process-group cleanup; Windows is unavailable")
    if type(timeout) is not int or not 1 <= timeout <= 60:
        raise VisualError("Whole-run timeout must be 1..60 seconds")
    source_root, source_manifest, source_sha = source_capture(source)
    render_content_type = content_type(source_root)
    output = pilot.no_symlinks(output)
    if output.exists() or not output.parent.is_dir():
        raise VisualError("Output must be a fresh directory under an existing parent")
    output.mkdir(mode=0o700)
    (output / "findings").mkdir()
    diagnostics = []
    prerequisites = doctor(browser)
    failure = None
    if not prerequisites["ready"]:
        failure = "Renderer prerequisites unavailable: explicit executable browser, Playwright and POSIX are required."
    else:
        try:
            failure = _run_worker(source_root, output, browser, timeout)
        except OSError:
            failure = "Renderer worker could not start."
    if failure:
        diagnostics.append(failure)
    checkpoint = path_at(output, "render.json")
    results = {}
    version = None
    if checkpoint.exists():
        pending = pilot.json_read(checkpoint, MAX_JSON)
        if isinstance(pending, dict) and isinstance(pending.get("viewports"), dict):
            results = pending["viewports"]
            version = pending.get("browser_version")
    for name in VIEWPORTS:
        if name not in results:
            # A timeout between file writes and checkpoint never promotes an
            # unverified artifact. Remove only our fixed worker artifact paths.
            for extension in ("html", "png"):
                path_at(output, f"{name}.{extension}").unlink(missing_ok=True)
            results[name] = {"status": "partial", "blocked_requests": 0,
                             "diagnostics": [failure or "Viewport was not returned by renderer."]}
    _write_render(output, results, content_type=render_content_type, browser_version=version)
    _, artifacts = render_data(output)
    _, source_again, sha_again = source_capture(source_root)
    if sha_again != source_sha or source_again["capture"]["sha256"] != source_manifest["capture"]["sha256"]:
        raise VisualError("Source capture changed while rendering")
    provenance = pilot.provenance()
    provenance["visual_files"] = [
        {"destination": name, **file_record(pilot.ROOT / name, pilot.MAX_ARTIFACT_BYTES)}
        for name in ("scripts/codex_visual.py", "scripts/render_page.py")]
    evidence = {"source": {"directory": str(source_root), "capture_sha256": source_manifest["capture"]["sha256"],
                           "pilot_manifest_sha256": source_sha, "final_url": source_manifest["capture"]["final_url"]},
                "provenance": provenance, "representation": "offline-saved-html", "network": "blocked",
                "viewports": VIEWPORTS, "device_scale_factor": 1, "full_page": False,
                "browser": prerequisites, "timeout_seconds": timeout, "artifacts": artifacts,
                "browser_version": version, "content_type": render_content_type,
                "worker_status": "partial" if failure else "complete",
                "diagnostics": diagnostics, "limitations": list(LIMITATIONS)}
    manifest = {"schema_version": 1, "created_at": pilot.now(), "status": "captured",
                "evidence": evidence, "evidence_sha256": pilot.digest(pilot.encode(evidence, compact=True)),
                "finalized_artifacts": {}}
    pilot.write_new(path_at(output, MANIFEST), pilot.encode(manifest))
    return manifest


def load_capture(output: Path) -> tuple[Path, dict, dict]:
    root = pilot.no_symlinks(output)
    if not root.is_dir():
        raise VisualError("Visual output directory missing")
    for path in root.rglob("*"):
        pilot.no_symlinks(path)
    manifest = pilot.json_read(path_at(root, MANIFEST), MAX_JSON)
    if (not isinstance(manifest, dict) or manifest.get("schema_version") != 1 or
            manifest.get("status") not in ("captured", "complete", "partial")):
        raise VisualError("Invalid visual manifest")
    evidence = manifest.get("evidence")
    if not isinstance(evidence, dict) or manifest.get("evidence_sha256") != pilot.digest(pilot.encode(evidence, compact=True)):
        raise VisualError("Visual evidence identity mismatch")
    source = evidence.get("source")
    if not isinstance(source, dict) or not isinstance(source.get("directory"), str) or not Path(source["directory"]).is_absolute():
        raise VisualError("Invalid visual source reference")
    _, original, sha = source_capture(Path(source["directory"]))
    if source != {"directory": source["directory"], "capture_sha256": original["capture"]["sha256"],
                  "pilot_manifest_sha256": sha, "final_url": original["capture"]["final_url"]}:
        raise VisualError("Source capture or source manifest changed")
    if (evidence.get("representation") != "offline-saved-html" or evidence.get("network") != "blocked" or
            evidence.get("viewports") != VIEWPORTS or evidence.get("device_scale_factor") != 1 or evidence.get("full_page") is not False or
            not bounded_strings(evidence.get("diagnostics"), 32, 500) or evidence.get("limitations") != LIMITATIONS):
        raise VisualError("Invalid rendering contract")
    if (not isinstance(evidence.get("artifacts"), dict) or evidence.get("worker_status") not in ("complete", "partial") or
            type(evidence.get("timeout_seconds")) is not int or not 1 <= evidence["timeout_seconds"] <= 60):
        raise VisualError("Invalid render artifacts or worker completion")
    rendered, _ = render_data(root, evidence["artifacts"])
    if (evidence.get("browser_version") != rendered["browser_version"] or
            evidence.get("content_type") != rendered["content_type"] or
            rendered["content_type"] != content_type(Path(source["directory"]))):
        raise VisualError("Rendering provenance disagrees with source or artifacts")
    finalized = manifest.get("finalized_artifacts")
    if not isinstance(finalized, dict) or not set(finalized).issubset({"REPORT.md", "findings/visual.json"}):
        raise VisualError("Invalid finalized artifacts")
    for name, record in finalized.items():
        if file_record(path_at(root, name), pilot.MAX_BYTES) != record:
            raise VisualError("Finalized visual artifact changed")
    return root, manifest, rendered


def role_result(root: Path, manifest: dict) -> dict | None:
    path = path_at(root, "findings/visual.json")
    if not path.exists():
        return None
    value = pilot.json_read(path)
    if (not isinstance(value, dict) or value.get("role") != "visual" or
            value.get("capture_sha256") != manifest["evidence"]["source"]["capture_sha256"] or
            value.get("render_sha256") != manifest["evidence_sha256"] or value.get("status") not in ("complete", "partial") or
            not bounded_strings(value.get("findings")) or not bounded_strings(value.get("limitations"))):
        raise VisualError("Visual role identity, status or findings are invalid")
    return value


def validate(output: Path) -> dict:
    root, manifest, rendered = load_capture(output)
    role = role_result(root, manifest)
    complete = (manifest["evidence"]["worker_status"] == "complete" and
                all(item["status"] == "complete" for item in rendered["viewports"].values()) and
                role is not None and role["status"] == "complete")
    if manifest["status"] != "captured":
        expected_files = {"REPORT.md"} | ({"findings/visual.json"} if role else set())
        if (manifest["status"] != ("complete" if complete else "partial") or
                set(manifest["finalized_artifacts"]) != expected_files):
            raise VisualError("Finalized visual completion or role changed")
    elif manifest["finalized_artifacts"]:
        raise VisualError("Unfinalized output contains finalized hashes")
    return {"valid": True, "phase": manifest["status"], "complete": complete,
            "capture_sha256": manifest["evidence"]["source"]["capture_sha256"],
            "render_sha256": manifest["evidence_sha256"], "role": role["status"] if role else "missing",
            "viewports": {name: item["status"] for name, item in rendered["viewports"].items()}}


def finalize(output: Path) -> dict:
    check = validate(output)
    root, manifest, rendered = load_capture(output)
    if manifest["status"] != "captured" or path_at(root, "REPORT.md").exists():
        raise VisualError("Visual output already finalized; refusing to overwrite")
    role = role_result(root, manifest)
    status = "complete" if check["complete"] else "partial"
    lines = ["# Offline visual evidence", "", f"Status: {status}.", "",
             "Representation: offline-saved-html. Network: blocked.",
             f"Source capture SHA-256: `{check['capture_sha256']}`",
             f"Render evidence SHA-256: `{check['render_sha256']}`", ""]
    lines.extend("- " + item for item in LIMITATIONS)
    for name, item in rendered["viewports"].items():
        lines.extend(["", f"{name.title()}: {item['status']}."])
        lines.extend("- " + message.replace("\n", " ") for message in item["diagnostics"])
    lines.extend(["", "## Visual findings", ""])
    if role:
        lines.extend("- " + item.replace("\n", " ") for item in role["findings"])
        lines.extend("- Limitation: " + item.replace("\n", " ") for item in role["limitations"])
        manifest["finalized_artifacts"]["findings/visual.json"] = file_record(path_at(root, "findings/visual.json"), pilot.MAX_BYTES)
    else:
        lines.append("Visual role missing; coverage is partial.")
    report = ("\n".join(lines) + "\n").encode()
    if len(report) > pilot.MAX_BYTES:
        raise VisualError("Visual report exceeds byte budget")
    pilot.write_new(path_at(root, "REPORT.md"), report)
    manifest["finalized_artifacts"]["REPORT.md"] = file_record(path_at(root, "REPORT.md"), pilot.MAX_BYTES)
    manifest.update(status=status, finalized_at=pilot.now())
    target = path_at(root, MANIFEST)
    fd, temporary = tempfile.mkstemp(prefix=".visual-manifest-", dir=root)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(pilot.encode(manifest))
        pilot.no_symlinks(target)
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return validate(root)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prerequisites = commands.add_parser("doctor")
    prerequisites.add_argument("--browser", required=True)
    for name in ("capture", "_worker"):
        command = commands.add_parser(name)
        command.add_argument("--source", type=Path, required=True)
        command.add_argument("--output", type=Path, required=True)
        command.add_argument("--browser", required=True)
        command.add_argument("--timeout", type=int, default=20)
    for name in ("validate", "finalize"):
        command = commands.add_parser(name)
        command.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "doctor":
            result = doctor(args.browser)
        elif args.command == "capture":
            result = capture(args.source, args.output, args.browser, args.timeout)
        elif args.command == "_worker":
            _worker(args.source, args.output, args.browser, args.timeout)
            return 0
        elif args.command == "validate":
            result = validate(args.output)
        else:
            result = finalize(args.output)
        print(json.dumps(result, indent=2))
        if args.command == "doctor":
            return 0 if result["ready"] else 1
        if args.command == "capture":
            rendered, _ = render_data(args.output)
            return 0 if result["evidence"]["worker_status"] == "complete" and all(
                item["status"] == "complete" for item in rendered["viewports"].values()) else 1
        if args.command == "finalize":
            return 0 if result["complete"] else 1
        return 0
    except (VisualError, OSError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
