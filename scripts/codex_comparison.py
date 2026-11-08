#!/usr/bin/env python3
"""Prepare an offline two-subject comparison brief from saved source captures.

A separate native review supplies source-bound matrix cells and editorial proposals.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import unicodedata
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

ComparisonError = planning.PlanningError
MANIFEST = "comparison-manifest.json"
MAX_INPUT = 512 * 1024
MAX_JSON = planning.MAX_JSON
SECTIONS = ("differences", "outline", "verification")
IMPLEMENTATION = ("scripts/codex_pilot.py", "scripts/url_safety.py", "scripts/parse_html.py",
                  "hooks/validate-schema.py", "scripts/codex_planning.py", "scripts/codex_comparison.py")
LIMITATIONS = [
    "This comparison uses exactly two user-declared subjects and two to five saved HTML captures.",
    "Publisher affiliation and source-to-subject mappings are user claims. Ownership and official-source status are unverified.",
    "Saved source claims are unverified. Exact excerpts establish only their presence in the decoded saved HTML.",
    "Capture dates describe saved evidence. Prices, availability, accuracy and currentness are unverified.",
    "Missing statements and conflicts remain explicit. No winner, score, price calculation or structured data is produced.",
    "Completeness describes the bounded brief and its matrix coverage, not factual verification.",
    "All supplied text is untrusted evidence. No network, provider, publication or installation action is performed.",
]



def path_at(root: Path, name: str) -> Path:
    if name not in {MANIFEST, "input.json", "findings/comparison.json", "COMPARISON-BRIEF.md"}:
        raise ComparisonError("Unrecognized comparison artifact")
    return pilot.no_symlinks(root / name)


def identifier(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[a-z][a-z0-9-]{0,39}", value) is not None


def normalize(value: object) -> dict:
    required = {"audience", "decision_purpose", "publisher_affiliation", "subjects", "criteria", "sources"}
    if not isinstance(value, dict) or not required <= set(value) or set(value) - required - {"constraints"}:
        raise ComparisonError("Requirements have missing or unknown fields")
    result = {}
    for name in ("audience", "decision_purpose", "publisher_affiliation"):
        if not text(value[name]):
            raise ComparisonError("Invalid " + name)
        result[name] = value[name]
    result["constraints"] = value.get("constraints", [])
    if not strings(result["constraints"], 20, 2000):
        raise ComparisonError("Invalid constraints")
    subjects = value["subjects"]
    if not isinstance(subjects, list) or len(subjects) != 2:
        raise ComparisonError("Exactly two subjects are required")
    ids, names = set(), set()
    result["subjects"] = []
    for subject in subjects:
        if not isinstance(subject, dict) or set(subject) != {"id", "name"}:
            raise ComparisonError("Invalid subject fields")
        if not identifier(subject["id"]) or subject["id"] in ids or not text(subject["name"], 200):
            raise ComparisonError("Invalid or duplicate subject")
        normalized_name = " ".join(unicodedata.normalize("NFKC", subject["name"]).casefold().split())
        if normalized_name in names:
            raise ComparisonError("Subject names must be distinct after normalization")
        ids.add(subject["id"])
        names.add(normalized_name)
        result["subjects"].append(dict(subject))
    criteria = value["criteria"]
    if not isinstance(criteria, list) or not 1 <= len(criteria) <= 10:
        raise ComparisonError("One to ten criteria are required")
    criterion_ids = set()
    result["criteria"] = []
    for criterion in criteria:
        if not isinstance(criterion, dict) or set(criterion) != {"id", "label", "question"}:
            raise ComparisonError("Invalid criterion fields")
        if (not identifier(criterion["id"]) or criterion["id"] in criterion_ids or
                not text(criterion["label"], 200) or not text(criterion["question"], 2000)):
            raise ComparisonError("Invalid or duplicate criterion")
        criterion_ids.add(criterion["id"])
        result["criteria"].append(dict(criterion))
    sources = value["sources"]
    if not isinstance(sources, list) or not 2 <= len(sources) <= 5:
        raise ComparisonError("Two to five sources are required")
    source_ids, directories, represented = set(), set(), set()
    result["sources"] = []
    for source in sources:
        if not isinstance(source, dict) or set(source) != {"id", "subject_id", "capture"}:
            raise ComparisonError("Invalid source fields")
        if (not identifier(source["id"]) or source["id"] in source_ids or
                not isinstance(source["subject_id"], str) or source["subject_id"] not in ids or
                not text(source["capture"], 4096)):
            raise ComparisonError("Invalid source identity or subject mapping")
        directory = str(absolute(Path(source["capture"])))
        if directory in directories:
            raise ComparisonError("Source capture directories must be distinct")
        source_ids.add(source["id"])
        directories.add(directory)
        represented.add(source["subject_id"])
        result["sources"].append({**source, "capture": directory})
    if represented != ids:
        raise ComparisonError("Each subject requires at least one source")
    return result


def source_registry(requirements: dict) -> list[dict]:
    return planning.source_registry(requirements["sources"])


def provenance() -> dict:
    return planning.provenance(IMPLEMENTATION, "comparison_files")


def validate_provenance(value: object) -> None:
    planning.validate_provenance(value, IMPLEMENTATION, "comparison_files")




def prepare(input_path: Path, output: Path) -> dict:
    input_path, output = absolute(input_path), absolute(output)
    source_bytes = pilot.read_bytes(input_path, MAX_INPUT)
    requirements = normalize(decode(source_bytes, MAX_INPUT))
    sources = source_registry(requirements)
    raw = pilot.encode(requirements)
    evidence = {"input_source": {"file": str(input_path), "sha256": pilot.digest(source_bytes), "bytes": len(source_bytes)},
                "requirements_sha256": pilot.digest(raw), "sources": sources,
                "network": "none", "representation": "saved-source-html",
                "provenance": provenance(), "limitations": list(LIMITATIONS),
                "artifacts": {"input.json": {"sha256": pilot.digest(raw), "bytes": len(raw)}}}
    manifest = {"schema_version": 1, "created_at": pilot.now(), "status": "prepared", "evidence": evidence,
                "evidence_sha256": pilot.digest(pilot.encode(evidence, compact=True)), "finalized_artifacts": {}}
    if output.exists() or not output.parent.is_dir():
        raise ComparisonError("Output must be a fresh directory under an existing parent")
    output.mkdir(mode=0o700)
    (output / "findings").mkdir()
    pilot.write_new(path_at(output, "input.json"), raw)
    pilot.write_new(path_at(output, MANIFEST), pilot.encode(manifest))
    return manifest


def load_prepared(output: Path) -> tuple[Path, dict, dict]:
    root = absolute(output)
    if not root.is_dir():
        raise ComparisonError("Comparison directory is missing")
    for path in root.rglob("*"):
        pilot.no_symlinks(path)
    manifest = decode(pilot.read_bytes(path_at(root, MANIFEST)))
    keys = {"schema_version", "created_at", "status", "evidence", "evidence_sha256", "finalized_artifacts"}
    if not isinstance(manifest, dict) or set(manifest) not in (keys, keys | {"finalized_at"}):
        raise ComparisonError("Invalid comparison manifest fields")
    if type(manifest["schema_version"]) is not int or manifest["schema_version"] != 1 or not isinstance(manifest["status"], str) or manifest["status"] not in {"prepared", "complete", "partial"}:
        raise ComparisonError("Invalid comparison manifest version or status")
    for name in ("created_at", *( ("finalized_at",) if "finalized_at" in manifest else ())):
        if not isinstance(manifest[name], str) or datetime.fromisoformat(manifest[name]).tzinfo is None:
            raise ComparisonError("Invalid manifest timestamp")
    evidence = manifest["evidence"]
    if not isinstance(evidence, dict) or manifest["evidence_sha256"] != pilot.digest(pilot.encode(evidence, compact=True)):
        raise ComparisonError("Comparison evidence identity mismatch")
    raw = pilot.read_bytes(path_at(root, "input.json"), MAX_INPUT)
    requirements = normalize(decode(raw, MAX_INPUT))
    if raw != pilot.encode(requirements):
        raise ComparisonError("Requirements must be canonical normalized JSON")
    validate_provenance(evidence.get("provenance"))
    source = evidence.get("input_source")
    if not isinstance(source, dict) or not isinstance(source.get("file"), str):
        raise ComparisonError("Invalid original input reference")
    original_path = absolute(Path(source["file"]))
    original = pilot.read_bytes(original_path, MAX_INPUT)
    expected_source = {"file": str(original_path), "sha256": pilot.digest(original), "bytes": len(original)}
    if source != expected_source or pilot.encode(normalize(decode(original, MAX_INPUT))) != raw:
        raise ComparisonError("Original requirements changed")
    expected = {"input_source": expected_source, "requirements_sha256": pilot.digest(raw), "sources": source_registry(requirements),
                "network": "none", "representation": "saved-source-html",
                "provenance": evidence["provenance"], "limitations": list(LIMITATIONS),
                "artifacts": {"input.json": {"sha256": pilot.digest(raw), "bytes": len(raw)}}}
    if evidence != expected:
        raise ComparisonError("Requirements, source registry or contract changed")
    finalized = manifest["finalized_artifacts"]
    if not isinstance(finalized, dict) or set(finalized) - {"COMPARISON-BRIEF.md", "findings/comparison.json"}:
        raise ComparisonError("Invalid finalized artifacts")
    for name, value in finalized.items():
        if record(path_at(root, name)) != value:
            raise ComparisonError("Finalized artifact changed")
    return root, manifest, requirements


def decoded_sources(requirements: dict) -> dict[str, str]:
    safety, _ = pilot.modules()
    result = {}
    for source in requirements["sources"]:
        root = Path(source["capture"])
        transport = decode(pilot.read_bytes(root / "capture/transport.json"))
        headers = transport.get("headers", {})
        if not isinstance(headers, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in headers.items()):
            raise ComparisonError("Invalid saved transport headers")
        content_type = next((v for k, v in headers.items() if k.lower() == "content-type"), "")
        result[source["id"]] = safety.decode_body(pilot.read_bytes(root / "capture/page.html"), content_type)
    return result


def role_result(root: Path, manifest: dict, requirements: dict) -> dict | None:
    path = path_at(root, "findings/comparison.json")
    if not path.exists():
        return None
    value = decode(pilot.read_bytes(path, MAX_JSON))
    keys = {"role", "requirements_sha256", "evidence_sha256", "status", "matrix", "sections", "limitations"}
    if not isinstance(value, dict) or set(value) != keys or value["role"] != "comparison":
        raise ComparisonError("Invalid comparison role fields")
    if (value["requirements_sha256"] != manifest["evidence"]["requirements_sha256"] or
            value["evidence_sha256"] != manifest["evidence_sha256"] or
            not isinstance(value["status"], str) or value["status"] not in {"complete", "partial"}):
        raise ComparisonError("Role identity or status mismatch")
    if not strings(value["limitations"], 100, 4000):
        raise ComparisonError("Invalid role limitations")
    sources = {source["id"]: source for source in requirements["sources"]}
    grid = {(subject["id"], criterion["id"]) for subject in requirements["subjects"] for criterion in requirements["criteria"]}
    matrix = value["matrix"]
    if not isinstance(matrix, list) or len(matrix) > 20:
        raise ComparisonError("Invalid comparison matrix")
    html = decoded_sources(requirements)
    seen = set()
    for cell in matrix:
        if not isinstance(cell, dict) or set(cell) != {"subject_id", "criterion_id", "status", "text", "evidence"}:
            raise ComparisonError("Invalid matrix cell fields")
        if not isinstance(cell["subject_id"], str) or not isinstance(cell["criterion_id"], str):
            raise ComparisonError("Invalid matrix identifiers")
        key = (cell["subject_id"], cell["criterion_id"])
        if key not in grid or key in seen:
            raise ComparisonError("Unknown or duplicate matrix cell")
        seen.add(key)
        if (not isinstance(cell["status"], str) or cell["status"] not in
                {"source_claim", "not_stated", "conflicting", "not_comparable"} or not text(cell["text"])):
            raise ComparisonError("Invalid cell status or text")
        evidence = cell["evidence"]
        if not isinstance(evidence, list) or len(evidence) > 10:
            raise ComparisonError("Invalid cell evidence")
        quotes = set()
        for item in evidence:
            if not isinstance(item, dict) or set(item) != {"source_id", "locator", "excerpt"}:
                raise ComparisonError("Invalid evidence fields")
            source_id = item["source_id"]
            if (not isinstance(source_id, str) or source_id not in sources or
                    sources[source_id]["subject_id"] != cell["subject_id"]):
                raise ComparisonError("Evidence source must belong to the cell subject")
            if (not text(item["locator"], 500) or not item["locator"].startswith("capture/page.html") or
                    not isinstance(item["excerpt"], str) or not 1 <= len(item["excerpt"]) <= 1000 or
                    item["excerpt"] not in html[source_id]):
                raise ComparisonError("Evidence requires a saved HTML locator and exact decoded excerpt")
            identity = (source_id, item["excerpt"])
            if identity in quotes:
                raise ComparisonError("Duplicate evidence source and excerpt")
            quotes.add(identity)
        if ((cell["status"] == "not_stated" and evidence) or
                (cell["status"] in {"source_claim", "not_comparable"} and not evidence) or
                (cell["status"] == "conflicting" and len(quotes) < 2)):
            raise ComparisonError("Cell status and evidence disagree")
    if value["status"] == "complete" and seen != grid:
        raise ComparisonError("Complete comparison requires every subject and criterion cell")
    sections = value["sections"]
    if not isinstance(sections, dict) or set(sections) != {*SECTIONS, "metadata"}:
        raise ComparisonError("Invalid comparison sections")
    for name in SECTIONS:
        entries = sections[name]
        if not isinstance(entries, list) or len(entries) > 30 or (value["status"] == "complete" and not entries):
            raise ComparisonError("Invalid or empty complete section")
        for entry in entries:
            if not isinstance(entry, dict) or set(entry) != {"basis", "text", "sources"}:
                raise ComparisonError("Invalid section entry fields")
            if (not isinstance(entry["basis"], str) or entry["basis"] not in {"source", "inference", "proposal"} or
                    not text(entry["text"])):
                raise ComparisonError("Invalid entry basis or text")
            refs = entry["sources"]
            if (not strings(refs, 5, 40) or len(set(refs)) != len(refs) or not set(refs) <= sources.keys() or
                    (entry["basis"] in {"source", "inference"} and not refs)):
                raise ComparisonError("Invalid section source citations")
    metadata = sections["metadata"]
    if (not isinstance(metadata, dict) or set(metadata) != {"title", "description"} or
            not all(isinstance(item, str) and len(item) <= 4000 for item in metadata.values()) or
            (value["status"] == "complete" and not all(text(item) for item in metadata.values()))):
        raise ComparisonError("Invalid comparison metadata")
    return value


def validate(output: Path) -> dict:
    root, manifest, requirements = load_prepared(output)
    role = role_result(root, manifest, requirements)
    complete = role is not None and role["status"] == "complete"
    if manifest["status"] == "prepared":
        if manifest["finalized_artifacts"] or "finalized_at" in manifest:
            raise ComparisonError("Prepared manifest has finalized metadata")
    elif (manifest["status"] != ("complete" if complete else "partial") or "finalized_at" not in manifest or
          set(manifest["finalized_artifacts"]) != {"COMPARISON-BRIEF.md"} | ({"findings/comparison.json"} if role else set())):
        raise ComparisonError("Finalized completion or role changed")
    return {"valid": True, "phase": manifest["status"], "complete": complete,
            "role": role["status"] if role else "missing", "requirements_sha256": manifest["evidence"]["requirements_sha256"],
            "evidence_sha256": manifest["evidence_sha256"]}


def report(manifest: dict, requirements: dict, role: dict | None, complete: bool) -> bytes:
    lines = ["# Comparison brief", "", "Review status is " + ("complete." if complete else "partial."), "",
             "## User-supplied requirements", ""]
    for name in ("audience", "decision_purpose", "publisher_affiliation"):
        lines.extend(["### " + name.replace("_", " ").capitalize(), "", escaped(requirements[name]), ""])
    lines.extend("- " + escaped(item) for item in requirements["constraints"])
    lines.extend(["", "## Subjects and criteria", ""])
    for subject in requirements["subjects"]:
        lines.append("- " + escaped(subject["id"]) + " — " + escaped(subject["name"]))
    for criterion in requirements["criteria"]:
        lines.append("- " + escaped(criterion["id"]) + " — " + escaped(criterion["label"]) + ". " + escaped(criterion["question"]))
    lines.extend(["", "## Saved source registry", ""])
    for source in manifest["evidence"]["sources"]:
        transport = decode(pilot.read_bytes(Path(source["capture"]) / "capture/transport.json"))
        lines.extend(["### " + escaped(source["id"]), "",
                      "User-mapped subject is " + escaped(source["subject_id"]) + ".",
                      "Requested URL is " + escaped(source["requested_url"]) + ".",
                      "Final URL is " + escaped(source["final_url"]) + ".",
                      "Representation is " + escaped(source["representation"]) + ".",
                      "HTML SHA-256 is " + source["capture_sha256"] + "."])
        for name in ("captured_at", "retrieved_at"):
            stamp = transport.get(name)
            lines.append(name.replace("_", " ").capitalize() + " is " +
                         (escaped(stamp) if isinstance(stamp, str) and stamp else "unavailable") + ".")
        lines.append("")
    subjects = requirements["subjects"]
    lines.extend(["## Comparison matrix", "",
                  "| Criterion | " + " | ".join(escaped(subject["name"]) for subject in subjects) + " |",
                  "| --- | --- | --- |"])
    cells = {(cell["subject_id"], cell["criterion_id"]): cell for cell in role["matrix"]} if role else {}
    for criterion in requirements["criteria"]:
        row = [escaped(criterion["label"])]
        for subject in subjects:
            cell = cells.get((subject["id"], criterion["id"]))
            state, content = (cell["status"], cell["text"]) if cell else ("pending", "Native review is pending.")
            row.append(escaped(state) + ". " + escaped(content))
        lines.append("| " + " | ".join(row) + " |")
    lines.extend(["", "## Evidence ledger", ""])
    for cell in role["matrix"] if role else []:
        lines.extend(["### " + escaped(cell["subject_id"]) + " / " + escaped(cell["criterion_id"]), "",
                      "State is " + escaped(cell["status"]) + ".", ""])
        for item in cell["evidence"]:
            lines.extend(["- Source " + escaped(item["source_id"]) + ". Locator " + escaped(item["locator"]) + ".",
                          "  Excerpt “" + escaped(item["excerpt"]) + "”"])
        if not cell["evidence"]:
            lines.append("No supporting excerpts are supplied for this not-stated assessment.")
        lines.append("")
    if not cells:
        lines.extend(["Native evidence is pending.", ""])
    for name in SECTIONS:
        lines.extend(["## " + name.capitalize(), ""])
        entries = role["sections"][name] if role else []
        for entry in entries:
            lines.append("- [" + entry["basis"] + "] " + escaped(entry["text"]) +
                         (" Sources " + ", ".join(escaped(item) for item in entry["sources"]) + "." if entry["sources"] else ""))
        if not entries:
            lines.append("Native review is pending.")
        lines.append("")
    lines.extend(["## Proposed metadata", ""])
    for name in ("title", "description"):
        content = role["sections"]["metadata"][name] if role else ""
        lines.extend(["### " + name.capitalize(), "", escaped(content) if content.strip() else "Native review is pending.", ""])
    lines.extend(["## Limitations", ""])
    lines.extend("- " + escaped(item) for item in [*LIMITATIONS, *(role["limitations"] if role else [])])
    lines.extend(["", "Requirements SHA-256 is " + manifest["evidence"]["requirements_sha256"] + ".",
                  "Evidence SHA-256 is " + manifest["evidence_sha256"] + "."])
    raw = ("\n".join(lines) + "\n").encode()
    if len(raw) > MAX_JSON:
        raise ComparisonError("Rendered comparison exceeds size bound")
    return raw


def finalize(output: Path) -> dict:
    check = validate(output)
    root, manifest, requirements = load_prepared(output)
    if manifest["status"] != "prepared" or path_at(root, "COMPARISON-BRIEF.md").exists():
        raise ComparisonError("Comparison already finalized; refusing overwrite")
    role = role_result(root, manifest, requirements)
    raw = report(manifest, requirements, role, check["complete"])
    pilot.write_new(path_at(root, "COMPARISON-BRIEF.md"), raw)
    manifest["finalized_artifacts"]["COMPARISON-BRIEF.md"] = record(path_at(root, "COMPARISON-BRIEF.md"))
    if role:
        manifest["finalized_artifacts"]["findings/comparison.json"] = record(path_at(root, "findings/comparison.json"))
    manifest.update(status="complete" if check["complete"] else "partial", finalized_at=pilot.now())
    fd, temporary = tempfile.mkstemp(prefix=".comparison-manifest-", dir=root)
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
    except (ComparisonError, OSError, ValueError, TypeError, KeyError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
