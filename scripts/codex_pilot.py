#!/usr/bin/env python3
"""Bounded, credential-free single-page capture and evidence handoff.

This is a local CLI, not an installer or a complete SEO/schema validator.
Network requests use the existing DNS-pinned transport with trust_env=False.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent.parent
MAX_BYTES = 2 * 1024 * 1024
MAX_ARTIFACT_BYTES = MAX_BYTES * 8
MAX_BLOCKS = 128
MAX_NODES = 4096
MANIFEST = "pilot-manifest.json"
CAPTURE_FILES = ("capture/page.html", "capture/parsed.json", "capture/schema.json", "capture/transport.json")
ROLES = ("technical", "schema")
# Additional audit specialists may write results without changing the pilot's
# original two-role validation and finalization contract.
RESULT_ROLES = (*ROLES, "content", "images")
LIMITS = [
    "Source HTML only; rendered DOM and browser checks are unavailable.",
    "No field Core Web Vitals, indexing, traffic, site-wide or provider verification.",
    "Schema checks cover bounded syntax, shape and local references, not full vocabulary or rich-result eligibility.",
]


class PilotError(ValueError):
    pass


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def source_commit() -> str:
    """Read local Git identity without invoking Git, configuration or credentials."""
    git = ROOT / ".git"
    if git.is_file():
        line = git.read_text().strip()
        if not line.startswith("gitdir: "):
            raise PilotError("Cannot identify source Git directory")
        git = (ROOT / line[8:]).resolve()
    head = (git / "HEAD").read_text().strip()
    if head.startswith("ref: "):
        ref = head[5:]
        if not re.fullmatch(r"refs/[A-Za-z0-9_./-]+", ref) or ".." in ref:
            raise PilotError("Invalid source Git ref")
        common = git
        if (git / "commondir").is_file():
            common = (git / (git / "commondir").read_text().strip()).resolve()
        ref_file = common / ref
        if ref_file.is_file():
            head = ref_file.read_text().strip()
        else:
            packed = common / "packed-refs"
            head = next((line.split()[0] for line in packed.read_text().splitlines()
                         if line.endswith(" " + ref)), "") if packed.is_file() else ""
    if not re.fullmatch(r"[0-9a-f]{40,64}", head):
        raise PilotError("Source commit is unavailable")
    return head


def provenance() -> dict:
    stage_path = ROOT / "stage-manifest.json"
    if stage_path.is_file():
        stage = json_read(stage_path)
        if not isinstance(stage, dict) or stage.get("format_version") != 1 or not isinstance(stage.get("files"), list):
            raise PilotError("Invalid stage provenance")
        generated = stage.get("generated_files", [])
        if not isinstance(generated, list):
            raise PilotError("Invalid generated stage entries")
        for entry in stage["files"] + generated:
            if not isinstance(entry, dict) or not isinstance(entry.get("destination"), str):
                raise PilotError("Invalid stage source entry")
            relative = Path(entry["destination"])
            if relative.is_absolute() or ".." in relative.parts:
                raise PilotError("Stage source escapes package")
            data = read_bytes(no_symlinks(ROOT / relative), MAX_BYTES * 8)
            if entry.get("sha256") != digest(data) or entry.get("bytes") != len(data):
                raise PilotError("Staged source changed: " + str(relative))
        return {"kind": "staged-copy", "source_commit": None,
                "source_baseline_ref": stage.get("source_baseline_ref"), "source_ref": stage.get("source_ref"),
                "source_ref_note": "Caller-supplied, not independently verified; hashes identify copied source bytes.",
                "stage_manifest_sha256": digest(read_bytes(stage_path)), "files": stage["files"],
                "generated_files": generated}
    files = ("scripts/codex_pilot.py", "scripts/url_safety.py", "scripts/parse_html.py", "hooks/validate-schema.py")
    return {"kind": "git-checkout", "source_commit": source_commit(),
            "files": [{"destination": name, "sha256": digest(read_bytes(ROOT / name))} for name in files],
            "source_ref_note": "Git HEAD plus current file hashes; uncommitted file changes may exist."}


def no_symlinks(path: Path) -> Path:
    path = Path(os.path.abspath(path))
    for part in (path, *path.parents):
        if part.is_symlink():
            raise PilotError("Symlink paths are not accepted")
    return path


def child(root: Path, name: str) -> Path:
    if name not in (*CAPTURE_FILES, MANIFEST, "REPORT.md", *(f"findings/{role}.json" for role in RESULT_ROLES)):
        raise PilotError("Unrecognized artifact path")
    path = no_symlinks(root / name)
    if root not in path.parents:
        raise PilotError("Artifact escapes output directory")
    return path


def read_bytes(path: Path, limit: int = MAX_BYTES) -> bytes:
    no_symlinks(path)
    with path.open("rb") as handle:
        data = handle.read(limit + 1)
    if len(data) > limit:
        raise PilotError("Artifact exceeds the size limit")
    return data


def encode(value: object, *, compact: bool = False) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=None if compact else 2,
                       separators=(",", ":") if compact else None, allow_nan=False) + "\n").encode()


def write_new(path: Path, data: bytes) -> None:
    no_symlinks(path)
    with path.open("xb") as handle:
        handle.write(data)


def replace_manifest(root: Path, value: dict) -> None:
    path = child(root, MANIFEST)
    fd, temp = tempfile.mkstemp(prefix=".pilot-manifest-", dir=root)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(encode(value))
        no_symlinks(path)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def json_read(path: Path, limit: int = MAX_BYTES) -> object:
    try:
        return json.loads(read_bytes(path, limit))
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise PilotError("Artifact is not bounded valid JSON") from exc


def modules():
    # These modules do not discover provider credentials or import auth helpers.
    scripts = str(ROOT / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    import url_safety
    from parse_html import parse_html
    return url_safety, parse_html


def schema_check(html: str, base_url: str) -> dict:
    safety, _ = modules()
    spec = importlib.util.spec_from_file_location("_pilot_schema_hook", ROOT / "hooks" / "validate-schema.py")
    hook = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hook)
    blocks = hook._extract_ld_json_blocks(html)
    result = {"status": "passed", "block_count": len(blocks), "blocks": [], "limitations": [LIMITS[2]]}
    if not blocks:
        return {**result, "status": "skipped", "reason": "No JSON-LD found in the inspected source representation"}
    if len(blocks) > MAX_BLOCKS:
        return {**result, "status": "failed", "error": "Too many JSON-LD blocks", "blocks": []}
    ids: dict[str, int] = {}
    refs: set[str] = set()
    count = 0
    for index, raw in enumerate(blocks, 1):
        entry = {"index": index, "sha256": digest(raw.encode()), "status": "passed", "errors": [], "warnings": []}
        result["blocks"].append(entry)
        try:
            if len(raw.encode()) > MAX_BYTES // 2 or safety.json_depth_exceeds(raw, max_depth=64):
                raise ValueError("JSON-LD exceeds block size or depth limit")
            data = json.loads(raw, parse_constant=lambda value: (_ for _ in ()).throw(ValueError("Non-finite JSON number")))
            entry["data"] = data
            # Reuse the existing hook's context, graph and policy checks.
            entry["warnings"] = hook.validate_jsonld('<script type="application/ld+json">' + raw + '</script>')
            roots = data if isinstance(data, list) else [data]
            if not roots or not all(isinstance(node, dict) for node in roots):
                raise ValueError("JSON-LD root must be an object or nonempty list of objects")
            pending = [(node, False, True) for node in roots]
            while pending:
                node, inherited, root_node = pending.pop()
                count += 1
                if count > MAX_NODES:
                    raise ValueError("JSON-LD exceeds node limit")
                context = inherited
                if "@context" in node:
                    context = hook._is_schema_org_context(node["@context"])
                    if not context:
                        entry["errors"].append("Unsupported or non-Schema.org context; not resolved remotely")
                if root_node and not context:
                    entry["errors"].append("Missing supported Schema.org context")
                types = node.get("@type")
                if types is not None and not (isinstance(types, str) and types or
                                             isinstance(types, list) and types and all(isinstance(t, str) and t for t in types)):
                    entry["errors"].append("@type must be a nonempty string or list of nonempty strings")
                if root_node and types is None and "@graph" not in node:
                    entry["errors"].append("Top-level node has no @type or @graph")
                ident = node.get("@id")
                if ident is not None:
                    if not isinstance(ident, str) or not ident:
                        entry["errors"].append("@id must be a nonempty string")
                    else:
                        normalized = urljoin(base_url, ident)
                        if len(node) == 1:
                            refs.add(normalized)
                        else:
                            ids[normalized] = ids.get(normalized, 0) + 1
                if "@graph" in node and not isinstance(node["@graph"], list):
                    entry["errors"].append("@graph must be a list")
                for key, value in node.items():
                    if key == "@context":
                        continue
                    values = value if isinstance(value, list) else [value]
                    for nested in values:
                        if isinstance(nested, dict):
                            pending.append((nested, context, key == "@graph"))
                        elif key == "@graph":
                            entry["errors"].append("@graph members must be objects")
        except (ValueError, TypeError, RecursionError) as exc:
            entry["errors"].append(str(exc))
        if entry["errors"]:
            entry["status"] = "failed"
            result["status"] = "failed"
        elif entry["warnings"]:
            entry["status"] = "warning"
            if result["status"] != "failed":
                result["status"] = "warning"
    result["duplicate_ids"] = sorted(key for key, n in ids.items() if n > 1)
    # Only local fragment references can be checked for absence in this capture.
    page = urlparse(base_url)._replace(fragment="").geturl()
    result["unresolved_local_refs"] = sorted(ref for ref in refs if "#" in ref and ref.split("#", 1)[0] == page and ref not in ids)
    if result["duplicate_ids"] or result["unresolved_local_refs"]:
        if result["status"] != "failed":
            result["status"] = "warning"
    return result


def parsed_capture(html: str, base_url: str) -> dict:
    """Keep schema parsing out of the generic parser: it drops bad blocks and
    has no depth bound. The explicit schema artifact owns that work instead.
    """
    from bs4 import BeautifulSoup
    _, parse = modules()
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all("script"):
        if str(tag.get("type", "")).lower() == "application/ld+json":
            tag.decompose()
    parsed = parse(str(soup), base_url)
    parsed["schema"] = []
    parsed["schema_evidence"] = "capture/schema.json"
    return parsed


def doctor() -> dict:
    dependencies = {}
    for package, module in (("requests", "requests"), ("beautifulsoup4", "bs4"), ("lxml", "lxml")):
        try:
            dependencies[package] = {"available": importlib.util.find_spec(module) is not None,
                                     "version": importlib.metadata.version(package)}
        except importlib.metadata.PackageNotFoundError:
            dependencies[package] = {"available": False, "version": None}
    return {"python": sys.version.split()[0], "dependencies": dependencies,
            "ready": sys.version_info >= (3, 11) and all(dependencies[p]["available"] for p in ("requests", "beautifulsoup4")),
            "parser": "lxml" if dependencies["lxml"]["available"] else "html.parser",
            "rendered_capture": "unavailable", "credentials": "not inspected"}


def capture(url: str, output: Path, fixture: Path | None = None) -> dict:
    safety, _ = modules()
    if os.environ.get("CLAUDE_SEO_LOCAL_TARGETS", "").strip():
        raise PilotError("Unset CLAUDE_SEO_LOCAL_TARGETS for the public-page pilot")
    if not safety.validate_url(url):
        raise PilotError("URL is not a permitted public HTTP(S) target")
    output = no_symlinks(output)
    if not output.parent.is_dir() or output.exists():
        raise PilotError("Output must be a new directory under an existing parent")
    source = provenance()
    if fixture is not None:
        raw = read_bytes(no_symlinks(fixture))
    else:
        raw = b""
    output.mkdir(mode=0o700)
    (output / "capture").mkdir()
    (output / "findings").mkdir()
    transport = {"requested_url": url, "final_url": url, "captured_at": now(),
                 "retrieved_at": None if fixture else now(),
                 "representation": "fixture" if fixture else "raw-http", "status_code": None,
                 "headers": {}, "redirect_chain": [], "too_large": False, "error": None,
                 "trust_env": False, "rendered_capture": "unavailable"}
    if fixture is None:
        try:
            with safety.safe_requests_session(url, trust_env=False) as session:
                session.max_redirects = 5
                response = session.get(url, headers=safety.DEFAULT_REQUEST_HEADERS, timeout=(10, 30), stream=True)
                try:
                    raw, transport["too_large"] = safety.read_bounded(response, MAX_BYTES)
                    transport["final_url"] = response.url
                    transport["status_code"] = response.status_code
                    selected = {"content-type", "content-length", "location", "link", "x-robots-tag", "cache-control", "etag", "last-modified"}
                    transport["headers"] = {k: v for k, v in response.headers.items() if k.lower() in selected}
                    transport["redirect_chain"] = [{"url": item.url, "status_code": item.status_code} for item in response.history]
                    if response.status_code >= 400:
                        transport["error"] = f"HTTP {response.status_code}"
                finally:
                    response.close()
        except (safety.URLSafetyError, safety.requests.RequestException) as exc:
            # Avoid copying third-party exception strings containing URLs/secrets.
            transport["error"] = type(exc).__name__
    if transport["too_large"]:
        transport["error"] = "Body exceeded capture byte limit; saved prefix is incomplete"
    content_type = next((v for k, v in transport["headers"].items() if k.lower() == "content-type"), "")
    html = safety.decode_body(raw, content_type)
    parsed = parsed_capture(html, transport["final_url"])
    schema = schema_check(html, transport["final_url"])
    parsed_bytes = encode(parsed, compact=True)
    schema_bytes = encode(schema, compact=True)
    if len(parsed_bytes) > MAX_ARTIFACT_BYTES:
        transport["error"] = transport["error"] or "Parsed artifact exceeds byte budget; original HTML preserved"
        parsed_bytes = encode({"error": "Parsed artifact exceeds byte budget", "source": "capture/page.html"})
    if len(schema_bytes) > MAX_ARTIFACT_BYTES:
        transport["error"] = transport["error"] or "Schema artifact exceeds byte budget; original blocks preserved in HTML"
        schema["status"] = "failed"
        schema["error"] = "Structured block data omitted due to artifact byte budget; original blocks preserved in capture/page.html"
        for block in schema["blocks"]:
            block.pop("data", None)
            block["status"] = "failed"
            block["errors"].append("Serialized data exceeds artifact byte budget; use original block in capture/page.html")
        schema_bytes = encode(schema, compact=True)
    artifacts = {"capture/page.html": raw, "capture/parsed.json": parsed_bytes,
                 "capture/schema.json": schema_bytes, "capture/transport.json": encode(transport, compact=True)}
    if any(len(data) > MAX_ARTIFACT_BYTES for data in artifacts.values()):
        raise PilotError("Capture artifacts exceed byte budget; capture was not accepted")
    for name, data in artifacts.items():
        write_new(child(output, name), data)
    manifest = {"schema_version": 1, "source_commit": source["source_commit"], "provenance": source,
                "runtime": doctor(), "created_at": now(), "status": "captured",
                "capture": {"sha256": digest(raw), "requested_url": url, "final_url": transport["final_url"],
                            "representation": transport["representation"], "complete": transport["error"] is None},
                "artifacts": {name: {"sha256": digest(data), "bytes": len(data)} for name, data in artifacts.items()},
                "checks": {"transport": "failed" if transport["error"] else "passed", "schema": schema["status"],
                           "technical": "unavailable", "schema_role": "unavailable", "rendered_capture": "unavailable"},
                "limitations": list(LIMITS), "roles": {role: f"findings/{role}.json" for role in ROLES}}
    write_new(child(output, MANIFEST), encode(manifest))
    return manifest


def load_capture(output: Path) -> tuple[Path, dict]:
    root = no_symlinks(output)
    if not root.is_dir():
        raise PilotError("Output directory is missing")
    for path in root.rglob("*"):
        no_symlinks(path)
    manifest = json_read(child(root, MANIFEST))
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        raise PilotError("Unsupported manifest")
    if manifest.get("status") not in ("captured", "complete", "partial"):
        raise PilotError("Invalid manifest status")
    if not isinstance(manifest.get("capture"), dict) or not isinstance(manifest.get("checks"), dict):
        raise PilotError("Invalid manifest capture or checks")
    if not isinstance(manifest.get("limitations"), list) or not all(isinstance(item, str) for item in manifest["limitations"]):
        raise PilotError("Invalid manifest limitations")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict) or not set(CAPTURE_FILES).issubset(artifacts):
        raise PilotError("Capture artifacts are missing")
    for name, expected in artifacts.items():
        data = read_bytes(child(root, name), MAX_ARTIFACT_BYTES)
        if not isinstance(expected, dict) or expected != {"sha256": digest(data), "bytes": len(data)}:
            raise PilotError("Artifact hash or size mismatch: " + name)
    if manifest.get("capture", {}).get("sha256") != artifacts["capture/page.html"]["sha256"]:
        raise PilotError("Capture identity mismatch")
    transport = json_read(child(root, "capture/transport.json"))
    if not isinstance(transport, dict):
        raise PilotError("Invalid transport artifact")
    if (not isinstance(transport.get("error"), (str, type(None))) or
            not isinstance(transport.get("too_large"), bool) or transport.get("trust_env") is not False or
            transport.get("representation") not in ("fixture", "raw-http")):
        raise PilotError("Invalid transport status or shape")
    if transport["too_large"] and not transport["error"]:
        raise PilotError("Oversized transport cannot be successful")
    status_code = transport.get("status_code")
    if status_code is not None and (type(status_code) is not int or not 100 <= status_code <= 599):
        raise PilotError("Invalid HTTP status")
    if status_code is not None and status_code >= 400 and not transport["error"]:
        raise PilotError("HTTP failure cannot be successful")
    expected_transport = "failed" if transport["error"] else "passed"
    if manifest["checks"].get("transport") != expected_transport:
        raise PilotError("Transport check disagrees with transport evidence")
    schema = json_read(child(root, "capture/schema.json"), MAX_ARTIFACT_BYTES)
    if (not isinstance(schema, dict) or schema.get("status") not in ("passed", "failed", "warning", "skipped") or
            type(schema.get("block_count")) is not int or schema["block_count"] < 0 or
            not isinstance(schema.get("blocks"), list)):
        raise PilotError("Invalid schema status or shape")
    if schema["status"] == "skipped" and (schema["block_count"] != 0 or not schema.get("reason")):
        raise PilotError("Invalid skipped schema evidence")
    if schema["block_count"] != len(schema["blocks"]) and not (schema["status"] == "failed" and schema.get("error")):
        raise PilotError("Schema block count mismatch")
    for block in schema["blocks"]:
        if (not isinstance(block, dict) or block.get("status") not in ("passed", "failed", "warning") or
                not isinstance(block.get("errors"), list) or not isinstance(block.get("warnings"), list)):
            raise PilotError("Invalid schema block evidence")
    if schema["status"] == "passed" and any(block["status"] != "passed" for block in schema["blocks"]):
        raise PilotError("Schema pass disagrees with block evidence")
    if manifest["checks"].get("schema") != schema["status"]:
        raise PilotError("Schema check disagrees with schema evidence")
    if manifest["capture"].get("complete") != (transport.get("error") is None):
        raise PilotError("Capture completion disagrees with transport evidence")
    for field in ("requested_url", "final_url", "representation"):
        if manifest["capture"].get(field) != transport.get(field):
            raise PilotError("Capture identity disagrees with transport evidence")
    return root, manifest


def role_result(root: Path, role: str, sha: str) -> dict | None:
    path = child(root, f"findings/{role}.json")
    if not path.exists():
        return None
    data = json_read(path)
    if not isinstance(data, dict) or data.get("role") != role or data.get("capture_sha256") != sha:
        raise PilotError("Role or capture identity mismatch: " + role)
    if data.get("status") not in ("complete", "partial"):
        raise PilotError("Invalid role completion status: " + role)
    for field in ("findings", "limitations"):
        values = data.get(field)
        if not isinstance(values, list) or len(values) > 256 or not all(isinstance(item, str) and len(item) <= 10000 for item in values):
            raise PilotError("Invalid role " + field + ": " + role)
    return data


def validate(output: Path) -> dict:
    root, manifest = load_capture(output)
    statuses = {role: (result["status"] if (result := role_result(root, role, manifest["capture"]["sha256"])) else "missing") for role in ROLES}
    complete = manifest["capture"]["complete"] and all(value == "complete" for value in statuses.values())
    if manifest.get("status") == "complete" and not complete:
        raise PilotError("Finalized manifest overstates completion")
    if manifest.get("status") == "partial" and complete:
        raise PilotError("Finalized partial output changed after finalization")
    if manifest.get("status") in ("complete", "partial"):
        for role, status in statuses.items():
            check = role if role == "technical" else "schema_role"
            if manifest["checks"].get(check) != ("unavailable" if status == "missing" else status):
                raise PilotError("Finalized role status changed: " + role)
    if manifest.get("status") in ("complete", "partial") and "REPORT.md" not in manifest["artifacts"]:
        raise PilotError("Finalized report is missing")
    return {"valid": True, "phase": manifest["status"], "complete": complete,
            "capture_sha256": manifest["capture"]["sha256"], "roles": statuses}


def finalize(output: Path) -> dict:
    root, manifest = load_capture(output)
    if manifest.get("status") != "captured" or child(root, "REPORT.md").exists():
        raise PilotError("Output is already finalized; refusing to overwrite")
    results = {role: role_result(root, role, manifest["capture"]["sha256"]) for role in ROLES}
    complete = manifest["capture"]["complete"] and all(result and result["status"] == "complete" for result in results.values())
    status = "complete" if complete else "partial"
    lines = ["# Single-page SEO pilot", "", f"Status: {status}.", "", f"Page: {manifest['capture']['final_url']}",
             f"Capture SHA-256: `{manifest['capture']['sha256']}`", "", "## Evidence and limitations", ""]
    lines.append("Automated schema check: " + manifest["checks"]["schema"] + ". This is not full Schema.org validation.")
    lines.extend("- " + limitation for limitation in manifest["limitations"])
    if not manifest["capture"]["complete"]:
        lines.append("- Capture failed or is incomplete; findings cannot establish complete page coverage.")
    for role, result in results.items():
        lines.extend(["", "## " + role.title(), ""])
        manifest["checks"][role if role == "technical" else "schema_role"] = result["status"] if result else "unavailable"
        if result is None:
            lines.append("Result unavailable; coverage incomplete.")
            continue
        lines.append("Role status: " + result["status"] + ".")
        lines.extend("- " + value.replace("\n", " ") for value in result["findings"])
        lines.extend("- Limitation: " + value.replace("\n", " ") for value in result["limitations"])
        name = f"findings/{role}.json"
        data = read_bytes(child(root, name))
        manifest["artifacts"][name] = {"sha256": digest(data), "bytes": len(data)}
    report = ("\n".join(lines) + "\n").encode()
    write_new(child(root, "REPORT.md"), report)
    manifest["artifacts"]["REPORT.md"] = {"sha256": digest(report), "bytes": len(report)}
    manifest.update(status=status, finalized_at=now())
    replace_manifest(root, manifest)
    return validate(root)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor")
    c = commands.add_parser("capture")
    c.add_argument("--url", required=True)
    c.add_argument("--output", type=Path, required=True)
    c.add_argument("--html", type=Path, help="Local public-safe HTML fixture; makes no network request")
    for name in ("validate", "finalize"):
        commands.add_parser(name).add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "doctor":
            result = doctor()
        elif args.command == "capture":
            result = capture(args.url, args.output, args.html)
        elif args.command == "validate":
            result = validate(args.output)
        else:
            result = finalize(args.output)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if args.command == "doctor":
            return 0 if result["ready"] else 2
        if args.command == "capture":
            return 0 if result["capture"]["complete"] else 1
        if args.command == "finalize":
            return 0 if result["complete"] else 1
        return 0
    except (PilotError, OSError, ImportError, ValueError) as exc:
        print(json.dumps({"valid": False, "error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
