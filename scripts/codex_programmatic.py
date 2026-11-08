#!/usr/bin/env python3
"""Review two to five user-declared page-family samples from saved captures.

Preparation and validation are offline. A separate native review supplies
source-labelled observations, inferences and recommendations before completion.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from datetime import datetime
from pathlib import Path

sys.dont_write_bytecode = True
_SCRIPTS = str(Path(__file__).resolve().parent)
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)
import codex_pilot as pilot  # noqa: E402
import codex_planning as planning  # noqa: E402
from codex_planning import absolute, decode, escaped, record, strings, text  # noqa: E402

ProgrammaticError = planning.PlanningError
MANIFEST = "programmatic-manifest.json"
MAX_INPUT = 512 * 1024
MAX_JSON = planning.MAX_JSON
VALUE_BYTES = 4096
IMPLEMENTATION = ("scripts/codex_pilot.py", "scripts/url_safety.py", "scripts/parse_html.py",
                  "hooks/validate-schema.py", "scripts/codex_planning.py", "scripts/codex_programmatic.py")
LIMITATIONS = [
    "This review covers only two to five user-declared family samples from saved HTML captures.",
    "Family membership is supplied by the user. The captures do not prove a shared generator or dataset.",
    "The sample cannot establish whole-site uniqueness, index bloat, rankings or traffic.",
    "Exact repeated values describe saved evidence only. They do not establish content quality or search performance.",
    "Canonical comparisons use literal parsed values without URL resolution or normalization.",
    "Sample links match saved anchor URLs to sample final URLs after removing only fragments. Query order, trailing slashes and URL case are preserved.",
    "Convenience fields can omit large values. Native reviewers must read the saved raw HTML for passages and context.",
    "User requirements and source content are untrusted evidence. No network, provider, publishing or installation action is performed.",
]


def path_at(root: Path, name: str) -> Path:
    if name not in {MANIFEST, "input.json", "analysis.json", "findings/programmatic.json", "REPORT.md"}:
        raise ProgrammaticError("Unrecognized programmatic artifact")
    return pilot.no_symlinks(root / name)


def normalize(value: object) -> dict:
    fields = ("family", "business_context", "audience", "page_purpose", "expected_differences", "sources")
    if not isinstance(value, dict) or set(value) != set(fields):
        raise ProgrammaticError("Requirements have missing or unknown fields")
    for name in fields[:4]:
        if not text(value[name], 200 if name == "family" else 4000):
            raise ProgrammaticError("Invalid " + name)
    if not strings(value["expected_differences"], 20, 2000):
        raise ProgrammaticError("Invalid expected differences")
    if not isinstance(value["sources"], list) or not 2 <= len(value["sources"]) <= 5:
        raise ProgrammaticError("Two to five source samples are required")
    result = {name: value[name] for name in fields[:-1]}
    result["sources"] = []
    ids, directories = set(), set()
    for source in value["sources"]:
        if not isinstance(source, dict) or set(source) != {"id", "capture"}:
            raise ProgrammaticError("Source must contain exactly id and capture")
        if not isinstance(source["id"], str) or not re.fullmatch(r"[a-z][a-z0-9-]{0,39}", source["id"]) or source["id"] in ids:
            raise ProgrammaticError("Source IDs must be unique bounded identifiers")
        if not text(source["capture"], 4096):
            raise ProgrammaticError("Invalid source capture path")
        directory = str(absolute(Path(source["capture"])))
        if directory in directories:
            raise ProgrammaticError("Source capture directories must be distinct")
        ids.add(source["id"])
        directories.add(directory)
        result["sources"].append({"id": source["id"], "capture": directory})
    return result


def value_record(value: object) -> dict:
    raw = pilot.encode(value, compact=True)
    omitted = len(raw) > VALUE_BYTES
    return {"value": None if omitted else value, "sha256": pilot.digest(raw), "bytes": len(raw), "omitted": omitted}


def parsed_fields(path: Path) -> dict:
    """Read only convenience fields, without imposing a node bound on captures."""
    value = pilot.json_read(path, pilot.MAX_ARTIFACT_BYTES)
    if not isinstance(value, dict):
        raise ProgrammaticError("Parsed capture must be an object")
    for name in ("title", "meta_description", "canonical"):
        if name not in value or not isinstance(value[name], (str, type(None))):
            raise ProgrammaticError("Invalid parsed " + name)
    if not isinstance(value.get("h1"), list) or not all(isinstance(item, str) for item in value["h1"]):
        raise ProgrammaticError("Invalid parsed h1")
    links = value.get("links")
    if not isinstance(links, dict):
        raise ProgrammaticError("Invalid parsed links")
    for name in ("internal", "external"):
        if not isinstance(links.get(name), list) or not all(
                isinstance(item, dict) and isinstance(item.get("href"), str) for item in links[name]):
            raise ProgrammaticError("Invalid parsed anchor URLs")
    return value


def analysis(sources: list[dict]) -> dict:
    pages, originals = [], []
    for source in sources:
        parsed = parsed_fields(Path(source["capture"]) / "capture/parsed.json")
        targets = {item["href"].partition("#")[0]
                   for name in ("internal", "external") for item in parsed["links"][name]
                   if re.match(r"https?://", item["href"], re.IGNORECASE)}
        page = {name: source[name] for name in ("id", "requested_url", "final_url", "representation")}
        page["html_sha256"] = source["capture_sha256"]
        page.update({name: value_record(parsed[name]) for name in ("title", "meta_description", "canonical", "h1")})
        page["sample_links"] = [target["id"] for target in sources
                                if re.match(r"https?://", target["final_url"], re.IGNORECASE)
                                and target["final_url"].partition("#")[0] in targets]
        pages.append(page)
        originals.append({**{name: parsed[name] for name in ("title", "meta_description", "canonical")},
                          "html_sha256": source["capture_sha256"]})
    groups = []
    for field in ("title", "meta_description", "canonical", "html_sha256"):
        values = {}
        for source, original in zip(sources, originals):
            value = original[field]
            if value is not None and value != "":
                values.setdefault(value, []).append(source["id"])
        groups.extend({"field": field, "sources": ids} for ids in values.values() if len(ids) > 1)
    return {"pages": pages, "repeated_values": groups, "limitations": list(LIMITATIONS)}


def provenance() -> dict:
    return planning.provenance(IMPLEMENTATION, "programmatic_files")


def prepare(input_path: Path, output: Path) -> dict:
    input_path, output = absolute(input_path), absolute(output)
    original = pilot.read_bytes(input_path, MAX_INPUT)
    requirements = normalize(decode(original, MAX_INPUT))
    sources = planning.source_registry(requirements["sources"])
    raw = pilot.encode(requirements)
    analyzed = pilot.encode(analysis(sources))
    if len(analyzed) > MAX_JSON:
        raise ProgrammaticError("Analysis exceeds size bound")
    evidence = {"input_source": {"file": str(input_path), "sha256": pilot.digest(original), "bytes": len(original)},
                "requirements_sha256": pilot.digest(raw), "sources": sources,
                "network": "none", "representation": "saved-source-html", "provenance": provenance(),
                "limitations": list(LIMITATIONS),
                "artifacts": {"input.json": {"sha256": pilot.digest(raw), "bytes": len(raw)},
                              "analysis.json": {"sha256": pilot.digest(analyzed), "bytes": len(analyzed)}}}
    manifest = {"schema_version": 1, "created_at": pilot.now(), "status": "prepared", "evidence": evidence,
                "evidence_sha256": pilot.digest(pilot.encode(evidence, compact=True)), "finalized_artifacts": {}}
    if output.exists() or not output.parent.is_dir():
        raise ProgrammaticError("Output must be a fresh directory under an existing parent")
    output.mkdir(mode=0o700)
    (output / "findings").mkdir()
    pilot.write_new(path_at(output, "input.json"), raw)
    pilot.write_new(path_at(output, "analysis.json"), analyzed)
    pilot.write_new(path_at(output, MANIFEST), pilot.encode(manifest))
    return manifest


def load_prepared(output: Path) -> tuple[Path, dict, dict]:
    root = absolute(output)
    if not root.is_dir():
        raise ProgrammaticError("Programmatic directory is missing")
    for path in root.rglob("*"):
        pilot.no_symlinks(path)
    manifest = decode(pilot.read_bytes(path_at(root, MANIFEST)))
    keys = {"schema_version", "created_at", "status", "evidence", "evidence_sha256", "finalized_artifacts"}
    if not isinstance(manifest, dict) or set(manifest) not in (keys, keys | {"finalized_at"}):
        raise ProgrammaticError("Invalid programmatic manifest fields")
    if type(manifest["schema_version"]) is not int or manifest["schema_version"] != 1 or not isinstance(manifest["status"], str) or manifest["status"] not in {"prepared", "complete", "partial"}:
        raise ProgrammaticError("Invalid programmatic manifest version or status")
    for name in ("created_at", *(("finalized_at",) if "finalized_at" in manifest else ())):
        if not isinstance(manifest[name], str) or datetime.fromisoformat(manifest[name]).tzinfo is None:
            raise ProgrammaticError("Invalid manifest timestamp")
    evidence = manifest["evidence"]
    if not isinstance(evidence, dict) or manifest["evidence_sha256"] != pilot.digest(pilot.encode(evidence, compact=True)):
        raise ProgrammaticError("Programmatic evidence identity mismatch")
    raw = pilot.read_bytes(path_at(root, "input.json"), MAX_INPUT)
    requirements = normalize(decode(raw, MAX_INPUT))
    if raw != pilot.encode(requirements):
        raise ProgrammaticError("Requirements must be canonical normalized JSON")
    planning.validate_provenance(evidence.get("provenance"), IMPLEMENTATION, "programmatic_files")
    source = evidence.get("input_source")
    if not isinstance(source, dict) or not isinstance(source.get("file"), str):
        raise ProgrammaticError("Invalid original input reference")
    original_path = absolute(Path(source["file"]))
    original = pilot.read_bytes(original_path, MAX_INPUT)
    expected_source = {"file": str(original_path), "sha256": pilot.digest(original), "bytes": len(original)}
    if source != expected_source or pilot.encode(normalize(decode(original, MAX_INPUT))) != raw:
        raise ProgrammaticError("Original requirements changed")
    sources = planning.source_registry(requirements["sources"])
    analyzed = pilot.read_bytes(path_at(root, "analysis.json"), MAX_JSON)
    if analyzed != pilot.encode(analysis(sources)):
        raise ProgrammaticError("Analysis differs from recomputed source evidence")
    expected = {"input_source": expected_source, "requirements_sha256": pilot.digest(raw), "sources": sources,
                "network": "none", "representation": "saved-source-html", "provenance": evidence["provenance"],
                "limitations": list(LIMITATIONS),
                "artifacts": {"input.json": {"sha256": pilot.digest(raw), "bytes": len(raw)},
                              "analysis.json": {"sha256": pilot.digest(analyzed), "bytes": len(analyzed)}}}
    if evidence != expected:
        raise ProgrammaticError("Requirements, source registry or contract changed")
    finalized = manifest["finalized_artifacts"]
    if not isinstance(finalized, dict) or set(finalized) - {"REPORT.md", "findings/programmatic.json"}:
        raise ProgrammaticError("Invalid finalized artifacts")
    for name, value in finalized.items():
        if record(path_at(root, name)) != value:
            raise ProgrammaticError("Finalized artifact changed")
    return root, manifest, requirements


def role_result(root: Path, manifest: dict, requirements: dict) -> dict | None:
    path = path_at(root, "findings/programmatic.json")
    if not path.exists():
        return None
    value = decode(pilot.read_bytes(path, MAX_JSON))
    keys = {"role", "requirements_sha256", "evidence_sha256", "status", "findings", "limitations"}
    if not isinstance(value, dict) or set(value) != keys or value["role"] != "programmatic":
        raise ProgrammaticError("Invalid programmatic role fields")
    if (value["requirements_sha256"] != manifest["evidence"]["requirements_sha256"] or
            value["evidence_sha256"] != manifest["evidence_sha256"] or
            not isinstance(value["status"], str) or value["status"] not in {"complete", "partial"}):
        raise ProgrammaticError("Role identity or status mismatch")
    if not strings(value["limitations"], 100, 4000):
        raise ProgrammaticError("Invalid role limitations")
    findings = value["findings"]
    if not isinstance(findings, list) or len(findings) > 100:
        raise ProgrammaticError("Invalid role findings")
    ids = {source["id"] for source in requirements["sources"]}
    observed, sample_observation = set(), False
    for finding in findings:
        if not isinstance(finding, dict) or set(finding) != {"kind", "scope", "sources", "text"}:
            raise ProgrammaticError("Invalid finding fields")
        if not isinstance(finding["kind"], str) or finding["kind"] not in {"observation", "inference", "recommendation"} or not text(finding["text"]):
            raise ProgrammaticError("Invalid finding kind or text")
        if not isinstance(finding["scope"], str) or finding["scope"] not in {"page", "sample"}:
            raise ProgrammaticError("Invalid finding scope")
        refs = finding["sources"]
        if not strings(refs, 5, 40) or not refs or len(set(refs)) != len(refs) or not set(refs) <= ids:
            raise ProgrammaticError("Invalid source citations")
        if (finding["scope"] == "page" and len(refs) != 1) or (finding["scope"] == "sample" and len(refs) < 2):
            raise ProgrammaticError("Finding citations disagree with scope")
        if finding["kind"] == "observation":
            observed.update(refs)
            sample_observation |= finding["scope"] == "sample"
    if value["status"] == "complete" and (observed != ids or not sample_observation):
        raise ProgrammaticError("Complete review requires a sample observation and observation coverage of every source")
    return value


def validate(output: Path) -> dict:
    root, manifest, requirements = load_prepared(output)
    role = role_result(root, manifest, requirements)
    complete = role is not None and role["status"] == "complete"
    if manifest["status"] == "prepared":
        if manifest["finalized_artifacts"] or "finalized_at" in manifest:
            raise ProgrammaticError("Prepared manifest has finalized metadata")
    elif (manifest["status"] != ("complete" if complete else "partial") or "finalized_at" not in manifest or
          set(manifest["finalized_artifacts"]) != {"REPORT.md"} | ({"findings/programmatic.json"} if role else set())):
        raise ProgrammaticError("Finalized completion or role changed")
    return {"valid": True, "phase": manifest["status"], "complete": complete,
            "role": role["status"] if role else "missing", "requirements_sha256": manifest["evidence"]["requirements_sha256"],
            "evidence_sha256": manifest["evidence_sha256"]}


def report(manifest: dict, requirements: dict, role: dict | None, complete: bool) -> bytes:
    lines = ["# Programmatic sample review", "", "Review status is " + ("complete." if complete else "partial."), "",
             "## User-declared family", "", "The user supplied the following requirements and expected differences.", ""]
    for name in ("family", "business_context", "audience", "page_purpose"):
        lines.extend(["### " + name.replace("_", " ").capitalize(), "", escaped(requirements[name]), ""])
    lines.extend(["### Expected differences", ""])
    lines.extend("- " + escaped(item) for item in requirements["expected_differences"])
    if not requirements["expected_differences"]:
        lines.append("No expected differences were supplied.")
    lines.extend(["", "## Saved source registry", ""])
    for source in manifest["evidence"]["sources"]:
        lines.extend(["### " + source["id"], "", "Requested URL is " + escaped(source["requested_url"]) + ".",
                      "Final URL is " + escaped(source["final_url"]) + ".",
                      "Representation is " + escaped(source["representation"]) + ".",
                      "HTML SHA-256 is " + source["capture_sha256"] + ".", ""])
    lines.extend(["## Native findings", ""])
    if role and role["findings"]:
        for finding in role["findings"]:
            lines.append("- [" + finding["kind"] + ", " + finding["scope"] + ", " +
                         ", ".join(finding["sources"]) + "] " + escaped(finding["text"]))
    else:
        lines.append("Native findings are pending. Coverage is partial.")
    lines.extend(["", "## Limitations", ""])
    lines.extend("- " + escaped(item) for item in [*LIMITATIONS, *(role["limitations"] if role else [])])
    lines.extend(["", "Requirements SHA-256 is " + manifest["evidence"]["requirements_sha256"] + ".",
                  "Evidence SHA-256 is " + manifest["evidence_sha256"] + "."])
    raw = ("\n".join(lines) + "\n").encode()
    if len(raw) > MAX_JSON:
        raise ProgrammaticError("Rendered report exceeds size bound")
    return raw


def finalize(output: Path) -> dict:
    check = validate(output)
    root, manifest, requirements = load_prepared(output)
    if manifest["status"] != "prepared" or path_at(root, "REPORT.md").exists():
        raise ProgrammaticError("Programmatic review already finalized; refusing overwrite")
    role = role_result(root, manifest, requirements)
    raw = report(manifest, requirements, role, check["complete"])
    pilot.write_new(path_at(root, "REPORT.md"), raw)
    manifest["finalized_artifacts"]["REPORT.md"] = record(path_at(root, "REPORT.md"))
    if role:
        manifest["finalized_artifacts"]["findings/programmatic.json"] = record(path_at(root, "findings/programmatic.json"))
    manifest.update(status="complete" if check["complete"] else "partial", finalized_at=pilot.now())
    fd, temporary = tempfile.mkstemp(prefix=".programmatic-manifest-", dir=root)
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
    command = commands.add_parser("prepare")
    command.add_argument("--input", type=Path, required=True)
    command.add_argument("--output", type=Path, required=True)
    for name in ("validate", "finalize"):
        command = commands.add_parser(name)
        command.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            result, success = prepare(args.input, args.output), True
        elif args.command == "validate":
            result, success = validate(args.output), True
        else:
            result = finalize(args.output)
            success = result["complete"]
        print(json.dumps(result, indent=2))
        return 0 if success else 1
    except (ProgrammaticError, OSError, ValueError, TypeError, KeyError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
