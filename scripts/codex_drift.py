#!/usr/bin/env python3
"""Compare two existing pilot captures offline, then validate native findings."""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
_SCRIPTS = str(Path(__file__).resolve().parent)
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)
import codex_pilot as pilot  # noqa: E402
from codex_planning import (  # noqa: E402
    MAX_JSON,
    absolute,
    decode,
    escaped,
    provenance,
    record,
    strings,
    text,
    validate_provenance,
)

DriftError = pilot.PilotError
MANIFEST = "drift-manifest.json"
IMPLEMENTATION = ("scripts/codex_drift.py", "scripts/codex_planning.py")
VALUE_LIMIT = 16 * 1024
PREVIEW_LIMIT = 2048
DOCUMENT_FIELDS = ("title", "meta_description", "canonical", "meta_robots", "h1", "h2", "h3", "open_graph", "twitter_card")
TRANSPORT_FIELDS = ("status_code", "error", "too_large", "final_url", "redirect_chain")
HEADERS = {"x_robots_tag": "x-robots-tag", "link": "link", "content_type": "content-type"}
COMPARISON_IDS = tuple(
    ["transport." + key for key in TRANSPORT_FIELDS]
    + ["transport.headers." + key for key in HEADERS]
    + ["document." + key for key in DOCUMENT_FIELDS]
    + ["json_ld." + key for key in ("block_count", "raw_hashes", "validation_statuses")]
    + ["source.html_sha256"]
)
LIMITATIONS = [
    "Offline comparison of saved evidence only; no DNS, HTTP requests, credential access or live-site checks.",
    "The before capture is a comparison baseline, not known-good SEO. Recorded times do not prove deployment chronology.",
    "Requested URL strings must match exactly; redirects and final URLs are compared without URL normalization.",
    "Source HTML is not browser-rendered DOM. Changes are observations, not ranking, traffic or causation claims.",
    "Document values are selected pilot parser output: first title/canonical, selected description/robots, nonempty heading text, and maps that can overwrite duplicate metadata. No source reparse is performed.",
    "JSON-LD comparisons use saved ordered raw-block hashes and validation statuses only, not parsed.schema or semantic equivalence. Invalid JSON can still have a comparable raw hash.",
    "Header values are raw response strings grouped case-insensitively. No effective robots/noindex policy or robots.txt evaluation is performed; failure-response headers describe only that response.",
    "Unavailable comparisons do not establish absence or removal. Fixture captures have no HTTP status code.",
    "Large values retain full canonical-value hashes and byte counts, with bounded previews; full values remain in the original capture artifacts.",
]


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")


def artifact_json(path: Path) -> object:
    """Read full pilot artifacts; nested schema data is validated but never compared."""
    raw = pilot.read_bytes(path, pilot.MAX_ARTIFACT_BYTES)

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise DriftError("Duplicate JSON object key")
            result[key] = value
        return result

    def nonfinite(_):
        raise DriftError("Nonfinite JSON number")

    try:
        value = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=pairs, parse_constant=nonfinite)
    except DriftError:
        raise
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise DriftError("Invalid capture JSON") from exc
    stack, nodes = [(value, 0)], 0
    while stack:
        item, depth = stack.pop()
        nodes += 1
        if depth > 128 or nodes > 2000000:
            raise DriftError("Capture JSON structural bound exceeded")
        if isinstance(item, dict):
            stack.extend((child, depth + 1) for child in item.values())
        elif isinstance(item, list):
            stack.extend((child, depth + 1) for child in item)
        elif isinstance(item, float) and not math.isfinite(item):
            raise DriftError("Nonfinite JSON number")
    return value


def source(path: Path) -> tuple[dict, dict, dict, dict]:
    root = absolute(path)
    artifact_json(root / pilot.MANIFEST)
    root, manifest = pilot.load_capture(root)
    parsed, schema, transport = [artifact_json(root / name) for name in
                                 ("capture/parsed.json", "capture/schema.json", "capture/transport.json")]
    if not all(isinstance(item, dict) for item in (parsed, schema, transport)):
        raise DriftError("Capture artifacts must be objects")
    for key in DOCUMENT_FIELDS[:4]:
        if key not in parsed or (parsed[key] is not None and not isinstance(parsed[key], str)):
            raise DriftError("Invalid captured document field: " + key)
    for key in ("h1", "h2", "h3"):
        if not isinstance(parsed.get(key), list) or not all(isinstance(item, str) for item in parsed[key]):
            raise DriftError("Invalid captured headings: " + key)
    for key in ("open_graph", "twitter_card"):
        if not isinstance(parsed.get(key), dict) or not all(isinstance(v, str) for v in parsed[key].values()):
            raise DriftError("Invalid captured metadata map: " + key)
    for key in ("requested_url", "final_url", "captured_at"):
        if not text(transport.get(key), 4096):
            raise DriftError("Missing captured URL or timestamp: " + key)
    if transport.get("retrieved_at") is not None and not text(transport["retrieved_at"], 4096):
        raise DriftError("Invalid retrieval timestamp")
    if not text(manifest.get("created_at"), 4096) or type(manifest["capture"].get("complete")) is not bool:
        raise DriftError("Invalid capture metadata")
    headers = transport.get("headers")
    if not isinstance(headers, dict) or len(headers) > 1024 or not all(isinstance(v, str) for v in headers.values()):
        raise DriftError("Invalid captured headers")
    redirects = transport.get("redirect_chain")
    if not isinstance(redirects, list) or len(redirects) > 100:
        raise DriftError("Invalid captured redirects")
    for redirect in redirects:
        if (not isinstance(redirect, dict) or set(redirect) != {"url", "status_code"}
                or not text(redirect["url"], 4096) or type(redirect["status_code"]) is not int
                or not 100 <= redirect["status_code"] <= 599):
            raise DriftError("Invalid captured redirect entry")
    for index, block in enumerate(schema["blocks"], 1):
        if (type(block.get("index")) is not int or block["index"] != index
                or not isinstance(block.get("sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", block["sha256"])):
            raise DriftError("Invalid captured JSON-LD block identity")
    reference = {"capture": str(root), "pilot_manifest": record(root / pilot.MANIFEST, pilot.MAX_ARTIFACT_BYTES),
                 "artifacts": {name: record(root / name, pilot.MAX_ARTIFACT_BYTES) for name in sorted(manifest["artifacts"])},
                 "capture_sha256": manifest["capture"]["sha256"],
                 "requested_url": transport["requested_url"], "final_url": transport["final_url"],
                 "representation": transport["representation"], "created_at": manifest["created_at"],
                 "captured_at": transport["captured_at"], "retrieved_at": transport.get("retrieved_at"),
                 "complete": manifest["capture"]["complete"], "transport_check": manifest["checks"]["transport"]}
    return reference, parsed, schema, transport


def value_record(value: object) -> dict:
    raw = canonical(value)
    return {"sha256": pilot.digest(raw), "bytes": len(raw), "value": value if len(raw) <= VALUE_LIMIT else None,
            "preview": raw[:PREVIEW_LIMIT].decode("utf-8", errors="ignore"),
            "preview_truncated": len(raw) > PREVIEW_LIMIT, "truncated": len(raw) > VALUE_LIMIT}


def analyze(before: tuple, after: tuple) -> dict:
    b_ref, b_doc, b_schema, b_transport = before
    a_ref, a_doc, a_schema, a_transport = after
    if b_ref["capture"] == a_ref["capture"]:
        raise DriftError("Before and after must be distinct capture paths")
    if not b_ref["complete"] or b_ref["transport_check"] != "passed":
        raise DriftError("Before must be a successful complete capture")
    if b_ref["requested_url"] != a_ref["requested_url"]:
        raise DriftError("Recorded requested URL strings must match exactly")
    if b_ref["representation"] != a_ref["representation"]:
        raise DriftError("Cannot mix fixture and raw-http captures")
    source_available = a_ref["complete"] and a_ref["transport_check"] == "passed"
    issues = [] if source_available else ["After transport failed or was truncated; document, JSON-LD and source comparisons are unavailable."]
    rows = []

    def add(identifier, left, right, artifact, pointer, reason=None):
        rows.append({"id": identifier, "group": identifier.split(".")[0],
                     "status": "unavailable" if reason else "unchanged" if canonical(left) == canonical(right) else "changed",
                     "before": None if reason else value_record(left), "after": None if reason else value_record(right),
                     "reason": reason, "before_evidence": "before:" + artifact + "#" + pointer,
                     "after_evidence": "after:" + artifact + "#" + pointer})

    for key in TRANSPORT_FIELDS:
        reason = None
        if key == "status_code" and (b_transport[key] is None or a_transport[key] is None):
            reason = "HTTP status unavailable in fixture capture." if b_ref["representation"] == "fixture" else "Recorded HTTP status unavailable."
            if b_ref["representation"] != "fixture":
                issues.append(reason)
        add("transport." + key, b_transport[key], a_transport[key], "capture/transport.json", "/" + key, reason)
    for key, header in HEADERS.items():
        def values(transport):
            return sorted(v for k, v in transport["headers"].items() if k.lower() == header)
        add("transport.headers." + key, values(b_transport), values(a_transport), "capture/transport.json", "/headers")
    unavailable = None if source_available else "After transport is incomplete; no source removal or document change can be inferred."
    for key in DOCUMENT_FIELDS:
        add("document." + key, b_doc[key], a_doc[key], "capture/parsed.json", "/" + key, unavailable)
    incomplete_schema = any(item["block_count"] != len(item["blocks"]) for item in (b_schema, a_schema))
    if source_available and incomplete_schema:
        issues.append("Saved JSON-LD block lists are incomplete; raw hashes and validation statuses are unavailable.")
    add("json_ld.block_count", b_schema["block_count"], a_schema["block_count"], "capture/schema.json", "/block_count", unavailable)
    for key, field in (("raw_hashes", "sha256"), ("validation_statuses", "status")):
        reason = unavailable or ("Saved JSON-LD block list does not cover its positive recorded block count." if incomplete_schema else None)
        add("json_ld." + key, [b[field] for b in b_schema["blocks"]], [b[field] for b in a_schema["blocks"]],
            "capture/schema.json", "/blocks", reason)
    add("source.html_sha256", b_ref["capture_sha256"], a_ref["capture_sha256"], "capture/page.html", "", unavailable)
    return {"schema_version": 1, "status": "partial" if issues else "complete", "scope": "source" if source_available else "transport-only",
            "comparisons": rows, "totals": {status: sum(row["status"] == status for row in rows)
                                              for status in ("changed", "unchanged", "unavailable")},
            "coverage_issues": issues, "limitations": list(LIMITATIONS),
            "limits": {"value_bytes": VALUE_LIMIT, "preview_bytes": PREVIEW_LIMIT, "analysis_bytes": MAX_JSON}}


def path_at(root: Path, name: str) -> Path:
    if name not in {MANIFEST, "analysis.json", "findings/drift.json", "REPORT.md"}:
        raise DriftError("Unrecognized drift artifact")
    return pilot.no_symlinks(root / name)


def compare(before: Path, after: Path, output: Path) -> dict:
    output = absolute(output)
    before_data, after_data = source(before), source(after)
    analysis = analyze(before_data, after_data)
    raw = pilot.encode(analysis)
    if len(raw) > MAX_JSON:
        raise DriftError("Analysis exceeds artifact bound")
    if output.exists() or not output.parent.is_dir():
        raise DriftError("Output must be a fresh directory under an existing parent")
    at = pilot.now()
    evidence = {"before": before_data[0], "after": after_data[0], "compared_at": at,
                "network": "none", "provenance": provenance(IMPLEMENTATION, "drift_files"),
                "artifacts": {"analysis.json": {"sha256": pilot.digest(raw), "bytes": len(raw)}}}
    manifest = {"schema_version": 1, "created_at": at, "status": "captured", "evidence": evidence,
                "evidence_sha256": pilot.digest(canonical(evidence)), "finalized_artifacts": {}}
    output.mkdir(mode=0o700)
    (output / "findings").mkdir()
    pilot.write_new(path_at(output, "analysis.json"), raw)
    pilot.write_new(path_at(output, MANIFEST), pilot.encode(manifest))
    return manifest


def read_json(path: Path) -> object:
    return decode(pilot.read_bytes(path, MAX_JSON))


def load_capture(output: Path) -> tuple[Path, dict, dict]:
    root = absolute(output)
    if not root.is_dir():
        raise DriftError("Drift output directory missing")
    for path in root.rglob("*"):
        pilot.no_symlinks(path)
    manifest = read_json(path_at(root, MANIFEST))
    base_keys = {"schema_version", "created_at", "status", "evidence", "evidence_sha256", "finalized_artifacts"}
    if (not isinstance(manifest, dict) or set(manifest) not in (base_keys, base_keys | {"finalized_at"})
            or type(manifest.get("schema_version")) is not int or manifest["schema_version"] != 1
            or manifest.get("status") not in ("captured", "complete", "partial")):
        raise DriftError("Invalid drift manifest")
    evidence = manifest["evidence"]
    if (not isinstance(evidence, dict) or set(evidence) != {"before", "after", "compared_at", "network", "provenance", "artifacts"}
            or manifest["evidence_sha256"] != pilot.digest(canonical(evidence))
            or evidence["network"] != "none" or evidence["compared_at"] != manifest["created_at"]
            or not text(manifest["created_at"], 4096)):
        raise DriftError("Invalid drift evidence identity")
    validate_provenance(evidence["provenance"], IMPLEMENTATION, "drift_files")
    dependencies = []
    for side in ("before", "after"):
        saved = evidence[side]
        if not isinstance(saved, dict) or not isinstance(saved.get("capture"), str):
            raise DriftError("Invalid capture reference")
        current = source(Path(saved["capture"]))
        if current[0] != saved:
            raise DriftError("Original capture evidence changed: " + side)
        dependencies.append(current)
    analysis = read_json(path_at(root, "analysis.json"))
    if evidence["artifacts"] != {"analysis.json": record(path_at(root, "analysis.json"))}:
        raise DriftError("Analysis artifact changed")
    if canonical(analysis) != canonical(analyze(*dependencies)):
        raise DriftError("Analysis disagrees with saved captures")
    finalized = manifest["finalized_artifacts"]
    if not isinstance(finalized, dict) or not set(finalized).issubset({"REPORT.md", "findings/drift.json"}):
        raise DriftError("Invalid finalized artifacts")
    for name, expected in finalized.items():
        if record(path_at(root, name), pilot.MAX_ARTIFACT_BYTES) != expected:
            raise DriftError("Finalized drift artifact changed")
    return root, manifest, analysis


def role_result(root: Path, manifest: dict, analysis: dict) -> dict | None:
    path = path_at(root, "findings/drift.json")
    if not path.exists():
        return None
    value = read_json(path)
    keys = {"role", "before_capture_sha256", "after_capture_sha256", "evidence_sha256", "status", "findings", "limitations"}
    if (not isinstance(value, dict) or set(value) != keys or value["role"] != "drift"
            or value["before_capture_sha256"] != manifest["evidence"]["before"]["capture_sha256"]
            or value["after_capture_sha256"] != manifest["evidence"]["after"]["capture_sha256"]
            or value["evidence_sha256"] != manifest["evidence_sha256"] or value["status"] not in ("complete", "partial")):
        raise DriftError("Invalid drift role identity or status")
    if value["status"] == "complete" and analysis["status"] != "complete":
        raise DriftError("Native findings cannot overstate partial analysis")
    if not isinstance(value["findings"], list) or len(value["findings"]) > 100 or not strings(value["limitations"], 100, 4000):
        raise DriftError("Invalid native findings or limitations")
    for finding in value["findings"]:
        if (not isinstance(finding, dict) or set(finding) != {"kind", "text", "comparisons"}
                or finding["kind"] not in ("observation", "interpretation", "recommendation") or not text(finding["text"])
                or not strings(finding["comparisons"], len(COMPARISON_IDS), 100) or not finding["comparisons"]
                or len(set(finding["comparisons"])) != len(finding["comparisons"])
                or not set(finding["comparisons"]).issubset(COMPARISON_IDS)):
            raise DriftError("Invalid native comparison finding")
    return value


def validate(output: Path) -> dict:
    root, manifest, analysis = load_capture(output)
    role = role_result(root, manifest, analysis)
    complete = analysis["status"] == "complete" and role is not None and role["status"] == "complete"
    if manifest["status"] == "captured":
        if manifest["finalized_artifacts"] or "finalized_at" in manifest:
            raise DriftError("Unfinalized output contains finalized metadata")
    elif (manifest["status"] != ("complete" if complete else "partial") or not text(manifest.get("finalized_at"), 4096)
          or set(manifest["finalized_artifacts"]) != {"REPORT.md"} | ({"findings/drift.json"} if role else set())):
        raise DriftError("Finalized completion or findings changed")
    return {"valid": True, "phase": manifest["status"], "complete": complete, "analysis": analysis["status"],
            "scope": analysis["scope"], "role": role["status"] if role else "missing", "evidence_sha256": manifest["evidence_sha256"]}


def finalize(output: Path) -> dict:
    check = validate(output)
    root, manifest, analysis = load_capture(output)
    if manifest["status"] != "captured" or path_at(root, "REPORT.md").exists():
        raise DriftError("Drift output already finalized; refusing to overwrite")
    role = role_result(root, manifest, analysis)
    lines = ["# Saved capture drift comparison", "", "Status: " + ("complete" if check["complete"] else "partial"),
             "Scope: " + analysis["scope"], "Evidence SHA-256: " + manifest["evidence_sha256"], "",
             "Completeness describes comparison coverage, not site quality or regression severity.", "", "## Comparisons", ""]
    for row in analysis["comparisons"]:
        lines.extend(["### " + row["id"], "Status: " + row["status"]])
        if row["reason"]:
            lines.append(escaped(row["reason"]))
        else:
            for side in ("before", "after"):
                value = row[side]
                lines.append(side.capitalize() + " preview: " + escaped(value["preview"]))
                lines.append(f"SHA-256: {value['sha256']}; bytes: {value['bytes']}; preview truncated: {value['preview_truncated']}; value omitted: {value['truncated']}")
        lines.extend(["Evidence: " + escaped(row["before_evidence"] + " ; " + row["after_evidence"]), ""])
    lines.extend(["## Native findings", ""])
    if role:
        for finding in role["findings"]:
            lines.append("- " + escaped(finding["kind"] + ": " + finding["text"] + " [" + ", ".join(finding["comparisons"]) + "]"))
        manifest["finalized_artifacts"]["findings/drift.json"] = record(path_at(root, "findings/drift.json"))
    else:
        lines.append("Native drift findings are missing; review is partial.")
    lines.extend(["", "## Limitations", ""])
    lines.extend("- " + escaped(item) for item in analysis["coverage_issues"] + LIMITATIONS + (role["limitations"] if role else []))
    report = ("\n".join(lines) + "\n").encode()
    if len(report) > pilot.MAX_ARTIFACT_BYTES:
        raise DriftError("Report exceeds artifact bound")
    pilot.write_new(path_at(root, "REPORT.md"), report)
    manifest["finalized_artifacts"]["REPORT.md"] = record(path_at(root, "REPORT.md"), pilot.MAX_ARTIFACT_BYTES)
    manifest.update(status="complete" if check["complete"] else "partial", finalized_at=pilot.now())
    fd, temporary = tempfile.mkstemp(prefix=".drift-manifest-", dir=root)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(pilot.encode(manifest))
        os.replace(temporary, path_at(root, MANIFEST))
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return validate(root)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser("compare")
    command.add_argument("--before", type=Path, required=True)
    command.add_argument("--after", type=Path, required=True)
    command.add_argument("--output", type=Path, required=True)
    for name in ("validate", "finalize"):
        commands.add_parser(name).add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "compare":
            result = compare(args.before, args.after, args.output)
            success = True
        elif args.command == "validate":
            result, success = validate(args.output), True
        else:
            result = finalize(args.output)
            success = result["complete"]
        print(json.dumps(result, indent=2))
        return 0 if success else 1
    except (DriftError, OSError, ValueError, TypeError, KeyError, RecursionError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
