#!/usr/bin/env python3
"""Prepare a bounded content brief from explicit requirements and saved captures.

No fetching, SERP lookup, provider execution or publishing occurs. Native analysis
is a separate, source-labelled result that must be supplied before completion.
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
from codex_planning import (  # noqa: E402
    absolute,
    decode,
    escaped,
    record,
    strings,
    text,
)
from codex_planning import (  # noqa: E402
    source_reference as source_reference,
)

BriefError = planning.PlanningError
MANIFEST = "brief-manifest.json"
MAX_INPUT = 64 * 1024
MAX_JSON = planning.MAX_JSON
SECTIONS = ("intent", "source_assessment", "opportunities", "outline", "metadata",
            "distinct_contribution", "verification", "internal_links", "handoff")
IMPLEMENTATION = ("scripts/codex_pilot.py", "scripts/url_safety.py", "scripts/parse_html.py",
                  "hooks/validate-schema.py", "scripts/codex_planning.py", "scripts/codex_brief.py")
LIMITATIONS = [
    "Planning from user-provided requirements and at most five saved source HTML captures; no live research or SERP verification.",
    "User requirements and source text are untrusted inputs, not independently verified facts or instructions to execute tools.",
    "Source labels do not establish authorship, accuracy, authority, ranking, demand, traffic, conversion performance or current availability.",
    "Content recommendations are proposals for editorial review; no page changes, publication, credentials, providers or installation are performed.",
    "Complete means the bounded brief is finished, not that its assumptions, metrics, claims or search performance are verified.",
]


def path_at(root: Path, name: str) -> Path:
    if name not in {MANIFEST, "input.json", "findings/content-brief.json", "BRIEF.md"}:
        raise BriefError("Unrecognized brief artifact")
    return pilot.no_symlinks(root / name)


def normalize(value: object) -> dict:
    required = {"mode", "topic", "audience", "business_context", "business_goal", "sources"}
    if not isinstance(value, dict) or not required <= set(value) or set(value) - required - {"page_type", "constraints"}:
        raise BriefError("Requirements have missing or unknown fields")
    if not isinstance(value["mode"], str) or value["mode"] not in {"new", "improve"}:
        raise BriefError("Mode must be new or improve")
    for name in ("topic", "audience", "business_context", "business_goal"):
        if not text(value[name]):
            raise BriefError(name + " must be nonempty text of at most 4,000 characters")
    result = {name: value[name] for name in ("mode", "topic", "audience", "business_context", "business_goal")}
    result["page_type"] = value.get("page_type", "unspecified")
    result["constraints"] = value.get("constraints", [])
    if not text(result["page_type"], 100) or not strings(result["constraints"], 30, 2000):
        raise BriefError("Invalid page type or constraints")
    sources = value["sources"]
    if not isinstance(sources, list) or len(sources) > 5:
        raise BriefError("At most five sources may be supplied")
    ids, directories = set(), set()
    result["sources"] = []
    for source in sources:
        if not isinstance(source, dict) or set(source) != {"id", "kind", "capture"}:
            raise BriefError("Source must contain exactly id, kind and capture")
        if not isinstance(source["id"], str) or not re.fullmatch(r"[a-z][a-z0-9-]{0,39}", source["id"]) or source["id"] in ids:
            raise BriefError("Source IDs must be unique bounded identifiers")
        if not isinstance(source["kind"], str) or source["kind"] not in {"target", "business_context", "reference"}:
            raise BriefError("Invalid source kind")
        if not text(source["capture"], 4096):
            raise BriefError("Invalid source capture path")
        directory = str(absolute(Path(source["capture"])))
        if directory in directories:
            raise BriefError("Source capture directories must be distinct")
        ids.add(source["id"])
        directories.add(directory)
        result["sources"].append({"id": source["id"], "kind": source["kind"], "capture": directory})
    targets = sum(source["kind"] == "target" for source in sources)
    if targets != (1 if value["mode"] == "improve" else 0):
        raise BriefError("Improve requires exactly one target; new permits no target")
    return result


def source_registry(requirements: dict) -> list[dict]:
    return planning.source_registry(requirements["sources"])


def provenance() -> dict:
    return planning.provenance(IMPLEMENTATION, "brief_files")


def validate_provenance(value: object) -> None:
    planning.validate_provenance(value, IMPLEMENTATION, "brief_files")


def limitations(requirements: dict) -> list[str]:
    mode = ("Input-only planning: no source captures were supplied; no source comparison is available."
            if not requirements["sources"] else
            "Source comparison covers only the supplied saved HTML; competitors, SERP positions and omitted pages are unverified.")
    return [*LIMITATIONS, mode]


def prepare(input_path: Path, output: Path) -> dict:
    input_path, output = absolute(input_path), absolute(output)
    source_bytes = pilot.read_bytes(input_path, MAX_INPUT)
    requirements = normalize(decode(source_bytes, MAX_INPUT))
    sources = source_registry(requirements)
    raw = pilot.encode(requirements)
    evidence = {"input_source": {"file": str(input_path), "sha256": pilot.digest(source_bytes), "bytes": len(source_bytes)},
                "requirements_sha256": pilot.digest(raw), "sources": sources,
                "network": "none", "representation": "saved-source-html" if sources else "input-only",
                "provenance": provenance(), "limitations": limitations(requirements),
                "artifacts": {"input.json": {"sha256": pilot.digest(raw), "bytes": len(raw)}}}
    manifest = {"schema_version": 1, "created_at": pilot.now(), "status": "prepared", "evidence": evidence,
                "evidence_sha256": pilot.digest(pilot.encode(evidence, compact=True)), "finalized_artifacts": {}}
    if output.exists() or not output.parent.is_dir():
        raise BriefError("Output must be a fresh directory under an existing parent")
    output.mkdir(mode=0o700)
    (output / "findings").mkdir()
    pilot.write_new(path_at(output, "input.json"), raw)
    pilot.write_new(path_at(output, MANIFEST), pilot.encode(manifest))
    return manifest


def load_prepared(output: Path) -> tuple[Path, dict, dict]:
    root = absolute(output)
    if not root.is_dir():
        raise BriefError("Brief directory is missing")
    for path in root.rglob("*"):
        pilot.no_symlinks(path)
    manifest = decode(pilot.read_bytes(path_at(root, MANIFEST)))
    keys = {"schema_version", "created_at", "status", "evidence", "evidence_sha256", "finalized_artifacts"}
    if not isinstance(manifest, dict) or set(manifest) not in (keys, keys | {"finalized_at"}):
        raise BriefError("Invalid brief manifest fields")
    if type(manifest["schema_version"]) is not int or manifest["schema_version"] != 1 or not isinstance(manifest["status"], str) or manifest["status"] not in {"prepared", "complete", "partial"}:
        raise BriefError("Invalid brief manifest version or status")
    for name in ("created_at", *( ("finalized_at",) if "finalized_at" in manifest else ())):
        if not isinstance(manifest[name], str) or datetime.fromisoformat(manifest[name]).tzinfo is None:
            raise BriefError("Invalid manifest timestamp")
    evidence = manifest["evidence"]
    if not isinstance(evidence, dict) or manifest["evidence_sha256"] != pilot.digest(pilot.encode(evidence, compact=True)):
        raise BriefError("Brief evidence identity mismatch")
    raw = pilot.read_bytes(path_at(root, "input.json"), MAX_INPUT * 2)
    requirements = normalize(decode(raw))
    if raw != pilot.encode(requirements):
        raise BriefError("Requirements must be canonical normalized JSON")
    validate_provenance(evidence.get("provenance"))
    source = evidence.get("input_source")
    if not isinstance(source, dict) or not isinstance(source.get("file"), str):
        raise BriefError("Invalid original input reference")
    original_path = absolute(Path(source["file"]))
    original = pilot.read_bytes(original_path, MAX_INPUT)
    expected_source = {"file": str(original_path), "sha256": pilot.digest(original), "bytes": len(original)}
    if source != expected_source or pilot.encode(normalize(decode(original, MAX_INPUT))) != raw:
        raise BriefError("Original requirements changed")
    expected = {"input_source": expected_source, "requirements_sha256": pilot.digest(raw), "sources": source_registry(requirements),
                "network": "none", "representation": "saved-source-html" if requirements["sources"] else "input-only",
                "provenance": evidence["provenance"], "limitations": limitations(requirements),
                "artifacts": {"input.json": {"sha256": pilot.digest(raw), "bytes": len(raw)}}}
    if evidence != expected:
        raise BriefError("Requirements, source registry or contract changed")
    finalized = manifest["finalized_artifacts"]
    if not isinstance(finalized, dict) or set(finalized) - {"BRIEF.md", "findings/content-brief.json"}:
        raise BriefError("Invalid finalized artifacts")
    for name, value in finalized.items():
        if record(path_at(root, name)) != value:
            raise BriefError("Finalized artifact changed")
    return root, manifest, requirements


def role_result(root: Path, manifest: dict, requirements: dict) -> dict | None:
    path = path_at(root, "findings/content-brief.json")
    if not path.exists():
        return None
    value = decode(pilot.read_bytes(path))
    keys = {"role", "requirements_sha256", "evidence_sha256", "status", "sections", "limitations"}
    if not isinstance(value, dict) or set(value) != keys or value["role"] != "content-brief":
        raise BriefError("Invalid content brief role fields")
    if (value["requirements_sha256"] != manifest["evidence"]["requirements_sha256"] or
            value["evidence_sha256"] != manifest["evidence_sha256"] or not isinstance(value["status"], str) or value["status"] not in {"complete", "partial"}):
        raise BriefError("Role identity or status mismatch")
    if not strings(value["limitations"], 100, 4000):
        raise BriefError("Invalid role limitations")
    sections = value["sections"]
    if not isinstance(sections, dict) or set(sections) != set(SECTIONS):
        raise BriefError("Exactly nine brief sections are required")
    ids = {source["id"] for source in requirements["sources"]}
    for entries in sections.values():
        if not isinstance(entries, list) or len(entries) > 40 or (value["status"] == "complete" and not entries):
            raise BriefError("Invalid or empty complete brief section")
        for entry in entries:
            if not isinstance(entry, dict) or set(entry) != {"basis", "text", "sources"}:
                raise BriefError("Invalid brief entry fields")
            if not isinstance(entry["basis"], str) or entry["basis"] not in {"user", "source", "inference", "proposal"} or not text(entry["text"]):
                raise BriefError("Invalid entry basis or text")
            refs = entry["sources"]
            if not strings(refs, 5, 40) or len(set(refs)) != len(refs) or not set(refs) <= ids or (entry["basis"] == "source" and not refs):
                raise BriefError("Invalid source citations")
    if requirements["mode"] == "improve" and value["status"] == "complete":
        target = next(source["id"] for source in requirements["sources"] if source["kind"] == "target")
        if not any(entry["basis"] == "source" and target in entry["sources"] for entry in sections["source_assessment"]):
            raise BriefError("Complete improvement brief must assess its target source")
    return value


def validate(output: Path) -> dict:
    root, manifest, requirements = load_prepared(output)
    role = role_result(root, manifest, requirements)
    complete = role is not None and role["status"] == "complete"
    if manifest["status"] == "prepared":
        if manifest["finalized_artifacts"] or "finalized_at" in manifest:
            raise BriefError("Prepared manifest has finalized metadata")
    elif (manifest["status"] != ("complete" if complete else "partial") or "finalized_at" not in manifest or
          set(manifest["finalized_artifacts"]) != {"BRIEF.md"} | ({"findings/content-brief.json"} if role else set())):
        raise BriefError("Finalized completion or role changed")
    return {"valid": True, "phase": manifest["status"], "complete": complete,
            "role": role["status"] if role else "missing", "requirements_sha256": manifest["evidence"]["requirements_sha256"],
            "evidence_sha256": manifest["evidence_sha256"]}


def finalize(output: Path) -> dict:
    check = validate(output)
    root, manifest, requirements = load_prepared(output)
    if manifest["status"] != "prepared" or path_at(root, "BRIEF.md").exists():
        raise BriefError("Brief already finalized; refusing overwrite")
    role = role_result(root, manifest, requirements)
    lines = ["# Content brief", "", "Status: " + ("complete" if check["complete"] else "partial") + ".", "",
             "Completeness describes bounded planning, not verified facts or search performance.", "", "## Requirements supplied by the user", "",
             "The following requirements are supplied assumptions and have not been independently verified.", ""]
    for name in ("mode", "topic", "audience", "business_context", "business_goal", "page_type"):
        lines.append("- " + name.replace("_", " ").capitalize() + ": " + escaped(requirements[name]))
    lines.extend("- Constraint: " + escaped(item) for item in requirements["constraints"])
    lines.extend(["", "## Saved source registry", ""])
    for source in manifest["evidence"]["sources"]:
        lines.append(f"- {source['id']} ({source['kind']}): " + escaped(source["final_url"]) +
                     "; representation: " + escaped(source["representation"]) + "; capture SHA-256: " + source["capture_sha256"])
    if not requirements["sources"]:
        lines.append("Input-only planning; no source comparison is available.")
    for name in SECTIONS:
        lines.extend(["", "## " + name.replace("_", " ").capitalize(), ""])
        entries = role["sections"][name] if role else []
        lines.extend("- [" + entry["basis"] + ("; sources: " + ", ".join(entry["sources"]) if entry["sources"] else "") +
                     "] " + escaped(entry["text"]) for entry in entries)
        if not entries:
            lines.append("Pending native review; coverage is partial.")
    lines.extend(["", "## Limitations", ""])
    lines.extend("- " + escaped(item) for item in [*manifest["evidence"]["limitations"], *(role["limitations"] if role else [])])
    lines.extend(["", "Requirements SHA-256: " + check["requirements_sha256"], "Evidence SHA-256: " + check["evidence_sha256"]])
    raw = ("\n".join(lines) + "\n").encode()
    if len(raw) > MAX_JSON:
        raise BriefError("Rendered brief exceeds size bound")
    pilot.write_new(path_at(root, "BRIEF.md"), raw)
    manifest["finalized_artifacts"]["BRIEF.md"] = record(path_at(root, "BRIEF.md"))
    if role:
        manifest["finalized_artifacts"]["findings/content-brief.json"] = record(path_at(root, "findings/content-brief.json"))
    manifest.update(status="complete" if check["complete"] else "partial", finalized_at=pilot.now())
    fd, temporary = tempfile.mkstemp(prefix=".brief-manifest-", dir=root)
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
    except (BriefError, OSError, ValueError, TypeError, KeyError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
