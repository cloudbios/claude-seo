#!/usr/bin/env python3
"""Analyze one explicitly supplied saved XML sitemap, without network access.

Capture creates immutable evidence; a native sitemap specialist supplies findings
before finalization. Completeness describes analysis coverage, not sitemap validity.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

sys.dont_write_bytecode = True
_SCRIPTS = str(Path(__file__).resolve().parent)
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)
import codex_pilot as pilot  # noqa: E402
from sitemap_discovery import parse_sitemap_xml  # noqa: E402
from url_safety import validate_url  # noqa: E402

NS = "http://www.sitemaps.org/schemas/sitemap/0.9"
MANIFEST = "sitemap-manifest.json"
MAX_XML = 5 * 1024 * 1024
MAX_JSON = 2 * 1024 * 1024
MAX_ENTRIES = 200
MAX_ISSUES = 100
MAX_CAPTURES = 5
SitemapError = pilot.PilotError
LIMITATIONS = [
    "Offline analysis of one saved XML file; no discovery, fetch, submission or generation.",
    "The adapter accepts at most 5 MiB; the sitemap protocol permits 50 MiB uncompressed and 50,000 entries.",
    "Bounded examples accompany totals from the whole accepted input; this is not full sitemap schema validation.",
    "URL checks are syntax and public-looking host checks only; DNS and HTTP health are unverified.",
    "Lastmod syntax and future dates are checked; modification-date accuracy is unverified.",
    "Cross-host or out-of-directory locations require verification; cross-site submission can be valid.",
    "Extension namespaces are recognized but their contents are outside validation scope.",
    "Sitemap index children are never followed; child contents and page membership are unavailable.",
    "Membership does not establish indexation, canonical status, noindex status or HTTP health.",
]


def absolute(path: Path) -> Path:
    if not path.is_absolute():
        raise SitemapError("Paths must be absolute")
    return pilot.no_symlinks(path)


def path_at(root: Path, name: str) -> Path:
    if name not in {MANIFEST, "source.xml", "analysis.json", "findings/sitemap.json", "REPORT.md"}:
        raise SitemapError("Unrecognized sitemap artifact")
    return pilot.no_symlinks(root / name)


def file_record(path: Path, limit: int = MAX_JSON) -> dict:
    raw = pilot.read_bytes(path, limit)
    return {"sha256": pilot.digest(raw), "bytes": len(raw)}


def public_url(value: str) -> bool:
    """No resolution, requests or local-target override is permitted here."""
    if not isinstance(value, str) or not value or len(value) >= 2048:
        return False
    if any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in value) or "\\" in value or "#" in value:
        return False
    if re.search(r"%(?![0-9a-fA-F]{2})", value):
        return False
    try:
        parsed = urlparse(value)
        _ = parsed.port
        return (parsed.scheme in {"http", "https"} and bool(parsed.hostname) and
                parsed.username is None and parsed.password is None and validate_url(value))
    except ValueError:
        return False


def lastmod(value: str, at: datetime) -> str:
    """W3C date profiles, including reduced precision and timezone HH:MM."""
    match = re.fullmatch(r"(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?", value)
    try:
        if match:
            year, month, day = match.groups()
            parsed = datetime(int(year), int(month or 1), int(day or 1), tzinfo=timezone.utc)
        elif re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2})", value):
            offset = re.search(r"[+-](\d{2}):(\d{2})$", value)
            if offset and (int(offset[1]) > 23 or int(offset[2]) > 59):
                return "invalid"
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        else:
            return "invalid"
    except ValueError:
        return "invalid"
    return "future" if parsed > at else "valid"


def page_reference(path: Path) -> dict:
    root, manifest = pilot.load_capture(absolute(path))
    capture = manifest["capture"]
    if capture.get("complete") is not True or manifest["checks"].get("transport") != "passed":
        raise SitemapError("Page membership requires a successful complete pilot capture")
    if not all(public_url(capture.get(key)) for key in ("requested_url", "final_url")):
        raise SitemapError("Page capture URLs must be public-looking absolute HTTP(S) URLs")
    transport = pilot.json_read(root / "capture/transport.json")
    if any(capture.get(key) != transport.get(key) for key in ("requested_url", "final_url", "representation")):
        raise SitemapError("Page capture identity disagrees with transport")
    if capture["representation"] == "raw-http" and not (
            type(transport.get("status_code")) is int and 200 <= transport["status_code"] < 400):
        raise SitemapError("Raw HTTP page capture has no successful response status")
    return {"directory": str(root), "capture_sha256": capture["sha256"],
            "pilot_manifest_sha256": file_record(root / pilot.MANIFEST)["sha256"],
            "requested_url": capture["requested_url"], "final_url": capture["final_url"],
            "representation": capture["representation"]}


def analyze(raw: bytes, sitemap_url: str, analyzed_at: str, references: list[dict]) -> dict:
    at = datetime.fromisoformat(analyzed_at)
    if at.tzinfo is None:
        raise SitemapError("Analysis time must include a timezone")
    result = {"schema_version": 1, "status": "partial", "kind": None, "sitemap_url": sitemap_url,
              "analyzed_at": analyzed_at, "checks": {}, "totals": {"entries": 0, "valid_locations": 0,
              "unique_locations": 0, "duplicate_locations": 0, "issues": 0}, "entries": [], "issues": [],
              "issue_counts": {}, "extensions": [], "page_captures": [
                  {**reference, "requested_url_membership": "unavailable", "final_url_membership": "unavailable"}
                  for reference in references], "limitations": list(LIMITATIONS)}
    counts = Counter()

    def issue(code, message, entry=None, severity="error"):
        counts[code] += 1
        if len(result["issues"]) < MAX_ISSUES:
            result["issues"].append({"code": code, "severity": severity, "entry": entry, "message": message})

    def finish():
        result["issue_counts"] = dict(sorted(counts.items()))
        result["totals"]["issues"] = sum(counts.values())
        result["entries_truncated"] = result["totals"]["entries"] > len(result["entries"])
        result["issues_truncated"] = result["totals"]["issues"] > len(result["issues"])
        return result

    try:
        root = parse_sitemap_xml(raw)
    except ValueError as exc:
        issue("xml_parse", str(exc))
        result["checks"]["xml"] = "invalid"
        return finish()
    result["checks"]["xml"] = "valid"
    encoding = root.getroottree().docinfo.encoding.upper().replace("-", "")
    try:
        utf8_bytes = b"\0" not in raw and bool(raw.decode("utf-8-sig"))
    except UnicodeError:
        utf8_bytes = False
    encoding_valid = encoding == "UTF8" and utf8_bytes
    result["checks"]["encoding"] = "valid" if encoding_valid else "invalid"
    if not encoding_valid:
        issue("encoding", "Sitemap protocol requires UTF-8 encoding; source XML uses a different encoding.")
    if root.tag not in {f"{{{NS}}}urlset", f"{{{NS}}}sitemapindex"}:
        issue("root_namespace", "Expected urlset or sitemapindex in the exact sitemap 0.9 namespace.")
        result["checks"]["root"] = "unsupported"
        return finish()
    kind = root.tag.split("}")[1]
    result.update(status="complete", kind=kind)
    result["checks"]["root"] = "valid"
    expected = "url" if kind == "urlset" else "sitemap"
    seen = set()
    all_seen = set()
    extensions = set()
    ignored = Counter()
    lastmods = Counter()
    base = urlparse(sitemap_url)
    base_directory = base.path.rsplit("/", 1)[0] + "/"
    if root.text and root.text.strip():
        issue("root_text", "Unexpected text directly in sitemap root.")
    # Record unused declarations at the root once; descendant declarations are
    # recognized when their namespace is actually used in an element tag.
    extensions.update(namespace for namespace in root.nsmap.values() if namespace and namespace != NS)
    for node in root.iter():
        if isinstance(node.tag, str) and node.tag.startswith("{"):
            namespace = node.tag[1:].split("}", 1)[0]
            if namespace != NS:
                extensions.add(namespace)
    for node in root:
        if node.tail and node.tail.strip():
            issue("root_text", "Unexpected text after a root child.")
        if not isinstance(node.tag, str):
            continue
        if node.tag != f"{{{NS}}}{expected}":
            issue("root_child", f"Expected a direct {expected} child in the sitemap namespace.")
            continue
        result["totals"]["entries"] += 1
        index = result["totals"]["entries"]
        entry = {"index": index, "loc": None, "loc_status": "invalid", "lastmod": []}
        if node.text and node.text.strip():
            issue("entry_text", "Unexpected text directly in entry.", index)
        allowed = {"loc", "lastmod", "priority", "changefreq"} if kind == "urlset" else {"loc", "lastmod"}
        for child in node:
            if child.tail and child.tail.strip():
                issue("entry_text", "Unexpected text after an entry field.", index)
            if not isinstance(child.tag, str):
                continue
            if child.tag.startswith(f"{{{NS}}}"):
                name = child.tag.split("}")[1]
                if name not in allowed:
                    issue("entry_child", "Unexpected sitemap namespace field in entry.", index)
            elif not child.tag.startswith("{"):
                issue("entry_child", "Entry field has no sitemap namespace.", index)
        locations = node.findall(f"{{{NS}}}loc")
        if len(locations) != 1:
            issue("loc_count", "Entry must contain exactly one direct loc.", index)
        elif len(locations[0]):
            issue("loc_text", "Location must contain only URL text.", index)
        else:
            value = locations[0].text or ""
            entry["loc"] = value[:2048]
            if value in all_seen:
                result["totals"]["duplicate_locations"] += 1
                issue("duplicate_loc", "Exact duplicate location.", index, "warning")
            all_seen.add(value)
            if not public_url(value):
                issue("loc_url", "Location is not a public-looking absolute HTTP(S) URL shorter than 2,048 characters without whitespace, credentials, backslashes or fragments.", index)
            else:
                entry["loc_status"] = "valid"
                result["totals"]["valid_locations"] += 1
                seen.add(value)
                parsed = urlparse(value)
                if parsed.netloc.lower() != base.netloc.lower():
                    issue("cross_host", "Location uses a different authority; verify cross-site submission ownership and configuration.", index, "verification")
                elif not parsed.path.startswith(base_directory):
                    issue("outside_directory", "Location is outside the sitemap URL directory; verify hosting or submission scope.", index, "verification")
        dates = node.findall(f"{{{NS}}}lastmod")
        if len(dates) > 1:
            issue("lastmod_count", "Entry contains multiple lastmod fields.", index)
        for date in dates:
            value = date.text or ""
            state = "invalid" if len(date) else lastmod(value, at)
            lastmods[state] += 1
            if len(entry["lastmod"]) < 4:
                entry["lastmod"].append({"value": value[:128], "status": state})
            if state != "valid":
                issue("lastmod_" + state, "Lastmod is in the future." if state == "future" else "Lastmod is not a valid W3C date or calendar value.", index)
        for field in ("priority", "changefreq"):
            ignored[field] += len(node.findall(f"{{{NS}}}{field}"))
        if len(result["entries"]) < MAX_ENTRIES:
            result["entries"].append(entry)
    total = result["totals"]["entries"]
    if total > 50000:
        issue("entry_limit", "Entry count exceeds the 50,000-entry protocol limit.")
    if total == 0:
        issue("empty_sitemap", "Sitemap contains no entries of the required type.")
    result["totals"]["unique_locations"] = len(seen)
    result["checks"].update(entry_limit="invalid" if total > 50000 else "valid",
                            structure="invalid" if any(counts[k] for k in ("root_text", "root_child", "entry_text", "entry_child", "loc_count", "loc_text", "lastmod_count", "empty_sitemap")) else "valid",
                            locations="invalid" if counts["loc_count"] or counts["loc_text"] or counts["loc_url"] else "valid",
                            lastmod={"syntax_and_calendar": dict(lastmods), "accuracy": "unverified"},
                            google_ignored={"priority": ignored["priority"], "changefreq": ignored["changefreq"]})
    result["extensions"] = [namespace[:512] for namespace in sorted(extensions)[:MAX_ENTRIES]]
    result["totals"]["extension_namespaces"] = len(extensions)
    result["page_captures"] = []
    for reference in references:
        result["page_captures"].append({**reference,
            "requested_url_membership": reference["requested_url"] in seen if kind == "urlset" else "unavailable",
            "final_url_membership": reference["final_url"] in seen if kind == "urlset" else "unavailable"})
    return finish()


def capture(xml: Path, sitemap_url: str, output: Path, page_captures: list[Path] | None = None) -> dict:
    if os.environ.get("CLAUDE_SEO_LOCAL_TARGETS", "").strip():
        raise SitemapError("Unset CLAUDE_SEO_LOCAL_TARGETS for offline public sitemap analysis")
    xml, output = absolute(xml), absolute(output)
    if not public_url(sitemap_url):
        raise SitemapError("Sitemap URL must be a public-looking absolute HTTP(S) URL")
    if xml.name.lower() == "robots.txt" or xml.suffix.lower() in {".gz", ".zip", ".bz2", ".xz", ".tgz"}:
        raise SitemapError("Only uncompressed saved XML is accepted; robots and compressed inputs are unsupported")
    if not xml.is_file() or xml.stat().st_size > MAX_XML:
        raise SitemapError("Saved XML must be a file within the 5 MiB adapter bound (protocol limit: 50 MiB uncompressed)")
    raw = pilot.read_bytes(xml, MAX_XML)
    if raw.startswith((b"\x1f\x8b", b"PK\x03\x04", b"BZh", b"\xfd7zXZ")):
        raise SitemapError("Compressed input is unsupported; supply uncompressed saved XML")
    paths = page_captures or []
    if len(paths) > MAX_CAPTURES:
        raise SitemapError("At most five page captures may be supplied")
    references = [page_reference(path) for path in paths]
    if len({ref["directory"] for ref in references}) != len(references):
        raise SitemapError("Page capture directories must be distinct")
    if output.exists() or not output.parent.is_dir():
        raise SitemapError("Output must be a fresh directory under an existing parent")
    analyzed_at = pilot.now()
    analysis = analyze(raw, sitemap_url, analyzed_at, references)
    analysis_bytes = pilot.encode(analysis)
    if len(analysis_bytes) > MAX_JSON:
        raise SitemapError("Analysis exceeds bounded artifact size")
    provenance = pilot.provenance()
    provenance["sitemap_files"] = [{"destination": name, **file_record(pilot.ROOT / name)}
                                   for name in ("scripts/codex_sitemap.py", "scripts/sitemap_discovery.py")]
    evidence = {"source": {"file": str(xml), "sha256": pilot.digest(raw), "bytes": len(raw)},
                "sitemap_url": sitemap_url, "analyzed_at": analyzed_at, "representation": "saved-xml",
                "network": "none", "analysis_status": analysis["status"], "page_captures": references,
                "provenance": provenance, "limitations": list(LIMITATIONS),
                "artifacts": {"source.xml": {"sha256": pilot.digest(raw), "bytes": len(raw)},
                              "analysis.json": {"sha256": pilot.digest(analysis_bytes), "bytes": len(analysis_bytes)}}}
    manifest = {"schema_version": 1, "created_at": analyzed_at, "status": "captured", "evidence": evidence,
                "evidence_sha256": pilot.digest(pilot.encode(evidence, compact=True)), "finalized_artifacts": {}}
    output.mkdir(mode=0o700)
    (output / "findings").mkdir()
    pilot.write_new(path_at(output, "source.xml"), raw)
    pilot.write_new(path_at(output, "analysis.json"), analysis_bytes)
    pilot.write_new(path_at(output, MANIFEST), pilot.encode(manifest))
    return manifest


def validate_provenance(value: dict) -> None:
    """Verify source records without tying evidence to the checkout's later HEAD."""
    required = {"scripts/codex_pilot.py", "scripts/url_safety.py", "scripts/parse_html.py", "hooks/validate-schema.py"}
    if value.get("kind") == "git-checkout":
        if not isinstance(value.get("source_commit"), str) or not re.fullmatch(r"[0-9a-f]{40,64}", value["source_commit"]):
            raise SitemapError("Invalid source commit provenance")
    elif value.get("kind") == "staged-copy":
        if value.get("source_commit") is not None or not isinstance(value.get("generated_files"), list):
            raise SitemapError("Invalid staged source provenance")
        if file_record(pilot.ROOT / "stage-manifest.json")["sha256"] != value.get("stage_manifest_sha256"):
            raise SitemapError("Staged provenance manifest changed")
    else:
        raise SitemapError("Invalid sitemap provenance kind")
    if not isinstance(value.get("source_ref_note"), str) or not isinstance(value.get("files"), list):
        raise SitemapError("Invalid source provenance records")
    records = value["files"]
    found = set()
    for record in records:
        if not isinstance(record, dict) or not isinstance(record.get("destination"), str):
            raise SitemapError("Invalid source provenance record")
        path = Path(record["destination"])
        sha = record.get("sha256")
        if path.is_absolute() or ".." in path.parts or not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{64}", sha):
            raise SitemapError("Invalid source provenance path or hash")
        if record["destination"] in required:
            if file_record(pilot.ROOT / path)["sha256"] != sha:
                raise SitemapError("Source implementation changed")
            found.add(record["destination"])
    if found != required:
        raise SitemapError("Missing required source provenance")
    expected = [{"destination": name, **file_record(pilot.ROOT / name)}
                for name in ("scripts/codex_sitemap.py", "scripts/sitemap_discovery.py")]
    if pilot.encode(value.get("sitemap_files"), compact=True) != pilot.encode(expected, compact=True):
        raise SitemapError("Sitemap implementation provenance changed")


def load_capture(output: Path) -> tuple[Path, dict, dict]:
    if os.environ.get("CLAUDE_SEO_LOCAL_TARGETS", "").strip():
        raise SitemapError("Unset CLAUDE_SEO_LOCAL_TARGETS for offline public sitemap analysis")
    root = absolute(output)
    if not root.is_dir():
        raise SitemapError("Sitemap output directory missing")
    for path in root.rglob("*"):
        pilot.no_symlinks(path)
    manifest = pilot.json_read(path_at(root, MANIFEST), MAX_JSON)
    if (not isinstance(manifest, dict) or type(manifest.get("schema_version")) is not int or manifest.get("schema_version") != 1 or
            manifest.get("status") not in {"captured", "complete", "partial"}):
        raise SitemapError("Invalid sitemap manifest")
    evidence = manifest.get("evidence")
    if not isinstance(evidence, dict) or manifest.get("evidence_sha256") != pilot.digest(pilot.encode(evidence, compact=True)):
        raise SitemapError("Sitemap evidence identity mismatch")
    source = evidence.get("source")
    if not isinstance(source, dict) or not isinstance(source.get("file"), str):
        raise SitemapError("Invalid XML source reference")
    source_file = absolute(Path(source["file"]))
    raw = pilot.read_bytes(path_at(root, "source.xml"), MAX_XML)
    expected = {"sha256": pilot.digest(raw), "bytes": len(raw)}
    if source != {"file": str(source_file), **expected} or file_record(source_file, MAX_XML) != expected:
        raise SitemapError("Original XML source changed")
    if (evidence.get("representation") != "saved-xml" or evidence.get("network") != "none" or
            not public_url(evidence.get("sitemap_url")) or evidence.get("limitations") != LIMITATIONS or
            not isinstance(evidence.get("provenance"), dict)):
        raise SitemapError("Invalid offline sitemap contract")
    validate_provenance(evidence["provenance"])
    refs = evidence.get("page_captures")
    if not isinstance(refs, list) or len(refs) > MAX_CAPTURES:
        raise SitemapError("Invalid page capture references")
    for ref in refs:
        if not isinstance(ref, dict) or not isinstance(ref.get("directory"), str) or page_reference(Path(ref["directory"])) != ref:
            raise SitemapError("Page capture or pilot manifest changed")
    artifacts = {"source.xml": expected, "analysis.json": file_record(path_at(root, "analysis.json"))}
    if evidence.get("artifacts") != artifacts:
        raise SitemapError("Sitemap artifact hash or size changed")
    analysis = pilot.json_read(path_at(root, "analysis.json"), MAX_JSON)
    expected_analysis = analyze(raw, evidence["sitemap_url"], evidence["analyzed_at"], refs)
    if pilot.encode(analysis, compact=True) != pilot.encode(expected_analysis, compact=True) or evidence.get("analysis_status") != analysis["status"]:
        raise SitemapError("Analysis disagrees with saved XML evidence")
    finalized = manifest.get("finalized_artifacts")
    if not isinstance(finalized, dict) or not set(finalized).issubset({"REPORT.md", "findings/sitemap.json"}):
        raise SitemapError("Invalid finalized artifacts")
    for name, record in finalized.items():
        if file_record(path_at(root, name)) != record:
            raise SitemapError("Finalized sitemap artifact changed")
    return root, manifest, analysis


def bounded_strings(value: object) -> bool:
    return isinstance(value, list) and len(value) <= 200 and all(isinstance(item, str) and len(item) <= 10000 for item in value)


def role_result(root: Path, manifest: dict) -> dict | None:
    path = path_at(root, "findings/sitemap.json")
    if not path.exists():
        return None
    value = pilot.json_read(path, MAX_JSON)
    if (not isinstance(value, dict) or value.get("role") != "sitemap" or
            value.get("capture_sha256") != manifest["evidence"]["source"]["sha256"] or
            value.get("evidence_sha256") != manifest["evidence_sha256"] or
            value.get("status") not in {"complete", "partial"} or
            not bounded_strings(value.get("findings")) or not bounded_strings(value.get("limitations"))):
        raise SitemapError("Sitemap role identity, status or findings are invalid")
    return value


def validate(output: Path) -> dict:
    root, manifest, analysis = load_capture(output)
    role = role_result(root, manifest)
    complete = analysis["status"] == "complete" and role is not None and role["status"] == "complete"
    if manifest["status"] == "captured":
        if manifest["finalized_artifacts"]:
            raise SitemapError("Unfinalized output contains finalized hashes")
    elif (manifest["status"] != ("complete" if complete else "partial") or
          set(manifest["finalized_artifacts"]) != {"REPORT.md"} | ({"findings/sitemap.json"} if role else set())):
        raise SitemapError("Finalized sitemap completion or role changed")
    return {"valid": True, "phase": manifest["status"], "complete": complete,
            "analysis": analysis["status"], "role": role["status"] if role else "missing",
            "capture_sha256": manifest["evidence"]["source"]["sha256"],
            "evidence_sha256": manifest["evidence_sha256"]}


def finalize(output: Path) -> dict:
    check = validate(output)
    root, manifest, analysis = load_capture(output)
    if manifest["status"] != "captured" or path_at(root, "REPORT.md").exists():
        raise SitemapError("Sitemap output already finalized; refusing to overwrite")
    role = role_result(root, manifest)
    status = "complete" if check["complete"] else "partial"
    lines = ["# Offline sitemap evidence", "", f"Status: {status}.", "",
             "Completeness describes analysis coverage, not sitemap validity.",
             f"Sitemap URL: {analysis['sitemap_url']}",
             f"XML capture SHA-256: `{check['capture_sha256']}`",
             f"Evidence SHA-256: `{check['evidence_sha256']}`", "",
             f"Analysis: {analysis['status']}; kind: {analysis['kind'] or 'unsupported'}; entries: {analysis['totals']['entries']}; issues: {analysis['totals']['issues']}.", ""]
    lines.extend("- " + item for item in LIMITATIONS)
    lines.extend(["", "## Findings", ""])
    if role:
        lines.extend("- " + item.replace("\n", " ") for item in role["findings"])
        lines.extend("- Limitation: " + item.replace("\n", " ") for item in role["limitations"])
        manifest["finalized_artifacts"]["findings/sitemap.json"] = file_record(path_at(root, "findings/sitemap.json"))
    else:
        lines.append("Sitemap specialist findings are missing; coverage is partial.")
    report = ("\n".join(lines) + "\n").encode()
    if len(report) > MAX_JSON:
        raise SitemapError("Report exceeds artifact bound")
    pilot.write_new(path_at(root, "REPORT.md"), report)
    manifest["finalized_artifacts"]["REPORT.md"] = file_record(path_at(root, "REPORT.md"))
    manifest.update(status=status, finalized_at=pilot.now())
    fd, temporary = tempfile.mkstemp(prefix=".sitemap-manifest-", dir=root)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(pilot.encode(manifest))
        pilot.no_symlinks(path_at(root, MANIFEST))
        os.replace(temporary, path_at(root, MANIFEST))
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return validate(root)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser("capture")
    command.add_argument("--xml", type=Path, required=True)
    command.add_argument("--sitemap-url", required=True)
    command.add_argument("--output", type=Path, required=True)
    command.add_argument("--page-capture", type=Path, action="append", default=[])
    for name in ("validate", "finalize"):
        command = commands.add_parser(name)
        command.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "capture":
            result = capture(args.xml, args.sitemap_url, args.output, args.page_capture)
            success = result["evidence"]["analysis_status"] == "complete"
        elif args.command == "validate":
            result, success = validate(args.output), True
        else:
            result = finalize(args.output)
            success = result["complete"]
        print(json.dumps(result, indent=2))
        return 0 if success else 1
    except (SitemapError, OSError, ValueError, TypeError, KeyError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
