#!/usr/bin/env python3
"""Prepare a bounded SEO strategy from requirements and verified saved pages.

Native planning is separate from deterministic evidence validation. This helper
does not fetch pages, look up metrics, install providers or publish changes.
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
from urllib.parse import unquote

sys.dont_write_bytecode = True
_SCRIPTS = str(Path(__file__).resolve().parent)
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)
import codex_pilot as pilot  # noqa: E402
import codex_planning as planning  # noqa: E402

PlanError = planning.PlanningError
MAX_INPUT = 64 * 1024
MAX_JSON = planning.MAX_JSON
MANIFEST = "plan-manifest.json"
COLLECTIONS = ("notes", "roadmap", "content_calendar", "site_structure", "measurement")
REPORTS = ("SEO-STRATEGY.md", "IMPLEMENTATION-ROADMAP.md", "CONTENT-CALENDAR.md",
           "SITE-STRUCTURE.md", "MEASUREMENT-PLAN.md")
IMPLEMENTATION = ("scripts/codex_pilot.py", "scripts/url_safety.py", "scripts/parse_html.py",
                  "hooks/validate-schema.py", "scripts/codex_planning.py", "scripts/codex_plan.py")
INDUSTRIES = {"generic", "saas", "local-service", "ecommerce", "publisher", "agency"}
LIMITATIONS = [
    "Planning uses supplied requirements and at most five saved source HTML captures; no live research or audit import.",
    "User claims, source labels and page text do not establish ownership, accuracy, current availability or search demand.",
    "Schedules, priorities, owners and proposed URLs are planning proposals, not approved commitments or verified capacity.",
    "Metric baselines are unavailable; proposed targets are not forecasts or guaranteed outcomes.",
    "Complete means the bounded strategy is finished, not that the site, claims or recommendations are independently verified.",
]


def path_at(root: Path, name: str) -> Path:
    if name not in {MANIFEST, "input.json", "findings/plan.json", *REPORTS}:
        raise PlanError("Unrecognized strategy artifact")
    return pilot.no_symlinks(root / name)


def identifier(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[a-z][a-z0-9-]{0,39}", value) is not None


def fields(value: object, keys: set[str], label: str) -> dict:
    if not isinstance(value, dict) or set(value) != keys:
        raise PlanError("Invalid " + label + " fields")
    return value


def texts(value: dict, names: tuple[str, ...], label: str, maximum: int = 2000) -> None:
    if any(not planning.text(value[name], maximum) for name in names):
        raise PlanError("Invalid " + label + " text")


def normalize(value: object) -> dict:
    required = {"mode", "business_context", "audience", "goals", "resources", "horizon_weeks", "sources"}
    if not isinstance(value, dict) or not required <= set(value) or set(value) - required - {"industry", "constraints"}:
        raise PlanError("Requirements have missing or unknown fields")
    if not isinstance(value["mode"], str) or value["mode"] not in {"new", "existing"}:
        raise PlanError("Mode must be new or existing")
    texts(value, ("business_context", "audience"), "requirements", 4000)
    if not planning.strings(value["goals"], 10, 1000) or not value["goals"]:
        raise PlanError("Supply one to ten goals")
    resources = fields(value["resources"], {"team", "capacity", "budget"}, "resources")
    texts(resources, ("team", "capacity", "budget"), "resource")
    horizon = value["horizon_weeks"]
    if type(horizon) is not int or not 1 <= horizon <= 52:
        raise PlanError("Horizon must be an integer from 1 to 52 weeks")
    industry = value.get("industry", "generic")
    if not isinstance(industry, str) or industry not in INDUSTRIES:
        raise PlanError("Unsupported industry")
    constraints = value.get("constraints", [])
    if not planning.strings(constraints, 30, 2000):
        raise PlanError("Invalid constraints")
    supplied = value["sources"]
    if not isinstance(supplied, list) or len(supplied) > 5:
        raise PlanError("At most five saved sources may be supplied")
    sources = []
    ids, directories = set(), set()
    for source in supplied:
        fields(source, {"id", "kind", "capture"}, "source")
        if not identifier(source["id"]) or source["id"] in ids:
            raise PlanError("Source IDs must be unique bounded identifiers")
        if not isinstance(source["kind"], str) or source["kind"] not in {"site", "reference"}:
            raise PlanError("Source kind must be site or reference")
        if not planning.text(source["capture"], 4096):
            raise PlanError("Invalid source capture path")
        capture = str(planning.absolute(Path(source["capture"])))
        if capture in directories:
            raise PlanError("Source capture directories must be distinct")
        ids.add(source["id"])
        directories.add(capture)
        sources.append({"id": source["id"], "kind": source["kind"], "capture": capture})
    if value["mode"] == "existing" and not any(source["kind"] == "site" for source in sources):
        raise PlanError("Existing-site planning requires at least one site capture")
    return {"mode": value["mode"], "business_context": value["business_context"], "audience": value["audience"],
            "goals": value["goals"], "resources": dict(resources), "horizon_weeks": horizon,
            "industry": industry, "constraints": constraints, "sources": sources}


def limitations(requirements: dict) -> list[str]:
    scope = ("Input-only planning: no page observations or source comparisons are available."
             if not requirements["sources"] else
             "Source assessment covers the supplied saved pages only, not the full site or competitive landscape.")
    return [*LIMITATIONS, scope]


def provenance() -> dict:
    return planning.provenance(IMPLEMENTATION, "plan_files")


def prepare(input_path: Path, output: Path) -> dict:
    input_path, output = planning.absolute(input_path), planning.absolute(output)
    original = pilot.read_bytes(input_path, MAX_INPUT)
    requirements = normalize(planning.decode(original, MAX_INPUT))
    sources = planning.source_registry(requirements["sources"])
    raw = pilot.encode(requirements)
    if len(raw) > MAX_INPUT * 2:
        raise PlanError("Normalized requirements exceed size bound")
    evidence = {"input_source": {"file": str(input_path), "sha256": pilot.digest(original), "bytes": len(original)},
                "requirements_sha256": pilot.digest(raw), "sources": sources, "network": "none",
                "representation": "saved-source-html" if sources else "input-only", "provenance": provenance(),
                "limitations": limitations(requirements), "artifacts": {"input.json": {"sha256": pilot.digest(raw), "bytes": len(raw)}}}
    manifest = {"schema_version": 1, "created_at": pilot.now(), "status": "prepared", "evidence": evidence,
                "evidence_sha256": pilot.digest(pilot.encode(evidence, compact=True)), "finalized_artifacts": {}}
    if output.exists() or not output.parent.is_dir():
        raise PlanError("Output must be a fresh directory under an existing parent")
    output.mkdir(mode=0o700)
    (output / "findings").mkdir()
    pilot.write_new(path_at(output, "input.json"), raw)
    pilot.write_new(path_at(output, MANIFEST), pilot.encode(manifest))
    return manifest


def load_prepared(output: Path) -> tuple[Path, dict, dict]:
    root = planning.absolute(output)
    if not root.is_dir():
        raise PlanError("Strategy directory is missing")
    for path in root.rglob("*"):
        pilot.no_symlinks(path)
    manifest = planning.decode(pilot.read_bytes(path_at(root, MANIFEST)))
    keys = {"schema_version", "created_at", "status", "evidence", "evidence_sha256", "finalized_artifacts"}
    if not isinstance(manifest, dict) or set(manifest) not in (keys, keys | {"finalized_at"}):
        raise PlanError("Invalid plan manifest fields")
    if type(manifest["schema_version"]) is not int or manifest["schema_version"] != 1 or not isinstance(manifest["status"], str) or manifest["status"] not in {"prepared", "complete", "partial"}:
        raise PlanError("Invalid plan manifest version or status")
    for name in ("created_at", *(("finalized_at",) if "finalized_at" in manifest else ())):
        try:
            valid_timestamp = isinstance(manifest[name], str) and datetime.fromisoformat(manifest[name]).tzinfo is not None
        except ValueError:
            valid_timestamp = False
        if not valid_timestamp:
            raise PlanError("Invalid manifest timestamp")
    evidence = manifest["evidence"]
    if not isinstance(evidence, dict) or manifest["evidence_sha256"] != pilot.digest(pilot.encode(evidence, compact=True)):
        raise PlanError("Plan evidence identity mismatch")
    raw = pilot.read_bytes(path_at(root, "input.json"), MAX_INPUT * 2)
    requirements = normalize(planning.decode(raw))
    if raw != pilot.encode(requirements):
        raise PlanError("Requirements must be canonical normalized JSON")
    planning.validate_provenance(evidence.get("provenance"), IMPLEMENTATION, "plan_files")
    source = evidence.get("input_source")
    if not isinstance(source, dict) or not isinstance(source.get("file"), str):
        raise PlanError("Invalid original input reference")
    source_path = planning.absolute(Path(source["file"]))
    original = pilot.read_bytes(source_path, MAX_INPUT)
    expected_source = {"file": str(source_path), "sha256": pilot.digest(original), "bytes": len(original)}
    if source != expected_source or pilot.encode(normalize(planning.decode(original, MAX_INPUT))) != raw:
        raise PlanError("Original requirements changed")
    expected = {"input_source": expected_source, "requirements_sha256": pilot.digest(raw),
                "sources": planning.source_registry(requirements["sources"]), "network": "none",
                "representation": "saved-source-html" if requirements["sources"] else "input-only",
                "provenance": evidence["provenance"], "limitations": limitations(requirements),
                "artifacts": {"input.json": {"sha256": pilot.digest(raw), "bytes": len(raw)}}}
    if pilot.encode(evidence, compact=True) != pilot.encode(expected, compact=True):
        raise PlanError("Requirements, sources or contract changed")
    finalized = manifest["finalized_artifacts"]
    if not isinstance(finalized, dict) or set(finalized) - {*REPORTS, "findings/plan.json"}:
        raise PlanError("Invalid finalized artifacts")
    for name, record in finalized.items():
        if planning.record(path_at(root, name)) != record:
            raise PlanError("Finalized artifact changed")
    return root, manifest, requirements


def collection(value: object, maximum: int, label: str) -> dict[str, dict]:
    if not isinstance(value, list) or len(value) > maximum:
        raise PlanError("Invalid " + label + " collection")
    result = {}
    for row in value:
        if not isinstance(row, dict) or not identifier(row.get("id")) or row["id"] in result:
            raise PlanError("Invalid or duplicate " + label + " ID")
        result[row["id"]] = row
    return result


def references(value: object, known: set[str], maximum: int, label: str, *, required: bool = False) -> None:
    if (not planning.strings(value, maximum, 40) or len(set(value)) != len(value) or
            not set(value) <= known or (required and not value)):
        raise PlanError("Invalid " + label + " references")


def window(row: dict, horizon: int) -> None:
    first, last = row["start_week"], row["end_week"]
    if type(first) is not int or type(last) is not int or not 1 <= first <= last <= horizon:
        raise PlanError("Invalid planning week window")


def acyclic(graph: dict[str, list[str]], label: str) -> None:
    visiting, visited = set(), set()

    def visit(node):
        if node in visiting:
            raise PlanError("Cyclic " + label + " references")
        if node in visited:
            return
        visiting.add(node)
        for target in graph[node]:
            visit(target)
        visiting.remove(node)
        visited.add(node)

    for node in graph:
        visit(node)


def proposed_path(value: object) -> bool:
    if not planning.text(value, 2048):
        return False
    decoded = value
    for _ in range(5):
        if re.search(r"%(?![0-9A-Fa-f]{2})", decoded):
            return False
        updated = unquote(decoded)
        if updated == decoded:
            break
        decoded = updated
    return (decoded.startswith("/") and not decoded.startswith("//") and
            not any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in decoded) and
            not any(char in decoded for char in "?#\\:<>%") and
            all(part not in {".", ".."} for part in decoded.split("/")))


def role_result(root: Path, manifest: dict, requirements: dict) -> dict | None:
    path = path_at(root, "findings/plan.json")
    if not path.exists():
        return None
    value = planning.decode(pilot.read_bytes(path))
    keys = {"role", "requirements_sha256", "evidence_sha256", "status", *COLLECTIONS, "limitations"}
    fields(value, keys, "plan role")
    if (value["role"] != "plan" or value["requirements_sha256"] != manifest["evidence"]["requirements_sha256"] or
            value["evidence_sha256"] != manifest["evidence_sha256"] or not isinstance(value["status"], str) or
            value["status"] not in {"partial", "complete"}):
        raise PlanError("Plan role identity or status mismatch")
    if not planning.strings(value["limitations"], 100, 4000):
        raise PlanError("Invalid role limitations")
    rows = {name: collection(value[name], 60 if name == "notes" else 20 if name == "measurement" else 40, name)
            for name in COLLECTIONS}
    if value["status"] == "complete" and any(not rows[name] for name in COLLECTIONS):
        raise PlanError("Complete strategy requires all five collections")
    sources = {source["id"]: source for source in manifest["evidence"]["sources"]}
    source_ids = set(sources)
    site_ids = {name for name, source in sources.items() if source["kind"] == "site"}
    note_ids = set(rows["notes"])
    for row in rows["notes"].values():
        fields(row, {"id", "basis", "text", "sources"}, "note")
        if not isinstance(row["basis"], str) or row["basis"] not in {"user", "source", "inference", "proposal"} or not planning.text(row["text"]):
            raise PlanError("Invalid note basis or text")
        references(row["sources"], source_ids, 5, "note source", required=row["basis"] == "source")
    if requirements["mode"] == "existing" and value["status"] == "complete" and not any(
            row["basis"] == "source" and set(row["sources"]) & site_ids for row in rows["notes"].values()):
        raise PlanError("Complete existing-site strategy must assess a site source")
    horizon = requirements["horizon_weeks"]
    task_ids = set(rows["roadmap"])
    for row in rows["roadmap"].values():
        fields(row, {"id", "action", "rationale", "priority", "owner", "start_week", "end_week", "depends_on", "done_when"}, "roadmap")
        texts(row, ("action", "owner", "done_when"), "roadmap")
        references(row["rationale"], note_ids, 60, "rationale", required=True)
        if not isinstance(row["priority"], str) or row["priority"] not in {"P0", "P1", "P2", "P3"}:
            raise PlanError("Invalid roadmap priority")
        window(row, horizon)
        references(row["depends_on"], task_ids, 40, "roadmap dependency")
    for row in rows["roadmap"].values():
        if row["id"] in row["depends_on"] or any(rows["roadmap"][dep]["end_week"] > row["start_week"] for dep in row["depends_on"]):
            raise PlanError("Invalid roadmap dependency timing")
    acyclic({key: row["depends_on"] for key, row in rows["roadmap"].items()}, "roadmap")
    for row in rows["content_calendar"].values():
        fields(row, {"id", "topic", "purpose", "format", "owner", "start_week", "end_week", "roadmap_id", "evidence_needed", "rationale"}, "calendar")
        texts(row, ("topic", "purpose", "format", "owner"), "calendar")
        window(row, horizon)
        if not isinstance(row["roadmap_id"], str) or row["roadmap_id"] not in task_ids:
            raise PlanError("Unknown calendar roadmap reference")
        task = rows["roadmap"][row["roadmap_id"]]
        if not task["start_week"] <= row["start_week"] <= row["end_week"] <= task["end_week"]:
            raise PlanError("Calendar window exceeds related roadmap window")
        if not planning.strings(row["evidence_needed"], 20, 2000):
            raise PlanError("Invalid calendar evidence needs")
        references(row["rationale"], note_ids, 60, "rationale", required=True)
    page_ids = set(rows["site_structure"])
    for row in rows["site_structure"].values():
        fields(row, {"id", "url", "basis", "purpose", "parent_id", "links_to", "rationale", "sources"}, "site structure")
        texts(row, ("purpose",), "site structure")
        if not isinstance(row["basis"], str) or row["basis"] not in {"source", "proposal"}:
            raise PlanError("Invalid site structure basis")
        references(row["sources"], source_ids, 5, "page source", required=row["basis"] == "source")
        if row["basis"] == "source":
            if (not planning.text(row["url"], 4096) or not set(row["sources"]) <= site_ids or
                    not any(row["url"] in {sources[key]["requested_url"], sources[key]["final_url"]} for key in row["sources"])):
                raise PlanError("Observed page URL must match its supplied site capture")
        elif not proposed_path(row["url"]):
            raise PlanError("Proposed URL must be a safe relative path")
        if row["parent_id"] is not None and (not isinstance(row["parent_id"], str) or row["parent_id"] not in page_ids):
            raise PlanError("Unknown parent page")
        references(row["links_to"], page_ids, 40, "page link")
        if row["parent_id"] == row["id"] or row["id"] in row["links_to"]:
            raise PlanError("Self-referencing page")
        references(row["rationale"], note_ids, 60, "rationale", required=True)
    acyclic({key: [row["parent_id"]] if row["parent_id"] else [] for key, row in rows["site_structure"].items()}, "parent page")
    for row in rows["measurement"].values():
        fields(row, {"id", "question", "metric", "scope", "collection_source", "owner", "cadence", "baseline", "target", "rationale"}, "measurement")
        texts(row, ("question", "metric", "scope", "collection_source", "owner", "cadence"), "measurement")
        if row["baseline"] != "unavailable":
            raise PlanError("Measured baselines are unavailable in this workflow")
        target = fields(row["target"], {"status", "value"}, "target")
        if not isinstance(target["status"], str) or target["status"] not in {"not-set", "proposal"} or (
                target["status"] == "not-set" and target["value"] is not None) or (
                target["status"] == "proposal" and not planning.text(target["value"], 2000)):
            raise PlanError("Invalid proposed target")
        references(row["rationale"], note_ids, 60, "rationale", required=True)
    return value


def validate(output: Path) -> dict:
    root, manifest, requirements = load_prepared(output)
    role = role_result(root, manifest, requirements)
    complete = role is not None and role["status"] == "complete"
    if manifest["status"] == "prepared":
        if manifest["finalized_artifacts"] or "finalized_at" in manifest:
            raise PlanError("Prepared manifest has finalized metadata")
    elif (manifest["status"] != ("complete" if complete else "partial") or "finalized_at" not in manifest or
          set(manifest["finalized_artifacts"]) != set(REPORTS) | ({"findings/plan.json"} if role else set())):
        raise PlanError("Finalized completion or role changed")
    return {"valid": True, "phase": manifest["status"], "complete": complete, "role": role["status"] if role else "missing",
            "requirements_sha256": manifest["evidence"]["requirements_sha256"], "evidence_sha256": manifest["evidence_sha256"]}


def render(manifest: dict, requirements: dict, role: dict | None) -> dict[str, bytes]:
    esc = planning.escaped
    status = "complete" if role and role["status"] == "complete" else "partial"
    footer = ["", "## Limitations", ""] + ["- " + esc(item) for item in [*manifest["evidence"]["limitations"], *(role["limitations"] if role else [])]]
    footer += ["", "Requirements SHA-256: " + manifest["evidence"]["requirements_sha256"], "Evidence SHA-256: " + manifest["evidence_sha256"]]

    def document(title, lines):
        data = ("\n".join(["# " + title, "", "Status: " + status + ".", "",
                            "This is a proposed plan, not an approved commitment or verified performance forecast.", "", *lines, *footer]) + "\n").encode()
        if len(data) > MAX_JSON:
            raise PlanError("Rendered strategy exceeds size bound")
        return data

    def refs(row):
        return "; rationale notes: " + ", ".join(row["rationale"])

    collections = {name: role[name] if role else [] for name in COLLECTIONS}
    strategy = ["## Requirements supplied by the user", ""]
    for name in ("mode", "business_context", "audience", "industry"):
        strategy.append("- " + name.replace("_", " ").capitalize() + ": " + esc(requirements[name]))
    strategy.append("- Proposed horizon: " + str(requirements["horizon_weeks"]) + " relative weeks; no calendar start date is assigned.")
    strategy.extend("- Goal: " + esc(item) for item in requirements["goals"])
    strategy.extend("- " + key.capitalize() + " (user supplied): " + esc(value) for key, value in requirements["resources"].items())
    strategy.extend("- Constraint: " + esc(item) for item in requirements["constraints"])
    strategy += ["", "## Saved sources", ""]
    strategy.extend("- " + item["id"] + " (" + item["kind"] + "): " + esc(item["final_url"]) +
                    "; capture SHA-256: " + item["capture_sha256"] for item in manifest["evidence"]["sources"])
    if not requirements["sources"]:
        strategy.append("Input-only planning; no page observations or source comparisons are available.")
    strategy += ["", "## Assessment and reasoning", ""]
    strategy.extend("- " + row["id"] + " [" + row["basis"] + ("; sources: " + ", ".join(row["sources"]) if row["sources"] else "") + "]: " + esc(row["text"]) for row in collections["notes"])
    road = ["All actions, owner roles and week windows below are proposals.", ""]
    road.extend("- " + row["id"] + " — " + esc(row["action"]) + "; " + row["priority"] + "; weeks " +
                str(row["start_week"]) + "–" + str(row["end_week"]) + "; owner: " + esc(row["owner"]) +
                "; depends on: " + (", ".join(row["depends_on"]) or "none") + "; complete when: " + esc(row["done_when"]) + refs(row)
                for row in collections["roadmap"])
    calendar = ["Proposed production windows require confirmation against actual capacity.", ""]
    calendar.extend("- " + row["id"] + " — " + esc(row["topic"]) + "; purpose: " + esc(row["purpose"]) +
                    "; format: " + esc(row["format"]) + "; weeks " + str(row["start_week"]) + "–" + str(row["end_week"]) +
                    "; owner: " + esc(row["owner"]) + "; roadmap: " + row["roadmap_id"] +
                    "; evidence needed: " + ("; ".join(esc(item) for item in row["evidence_needed"]) or "none specified") + refs(row)
                    for row in collections["content_calendar"])
    structure = ["Source URLs identify supplied saved pages; proposed paths have unverified availability. Neither status establishes live URL health.", ""]
    structure.extend("- " + row["id"] + " [" + row["basis"] + "] " + esc(row["url"]) + "; purpose: " + esc(row["purpose"]) +
                     "; proposed parent: " + (row["parent_id"] or "none") + "; proposed links to: " + (", ".join(row["links_to"]) or "none") +
                     "; sources: " + (", ".join(row["sources"]) or "none") + refs(row) for row in collections["site_structure"])
    measurement = ["No measured baselines were supplied through this workflow. Collection and targets below are proposals, not enabled integrations or forecasts.", ""]
    measurement.extend("- " + row["id"] + " — " + esc(row["question"]) + "; metric: " + esc(row["metric"]) +
                       "; scope: " + esc(row["scope"]) + "; proposed collection: " + esc(row["collection_source"]) +
                       "; owner: " + esc(row["owner"]) + "; cadence: " + esc(row["cadence"]) +
                       "; baseline: unavailable; target [" + row["target"]["status"] + "]: " +
                       (esc(row["target"]["value"]) if row["target"]["value"] is not None else "not set") + refs(row)
                       for row in collections["measurement"])
    if not role:
        for lines in (strategy, road, calendar, structure, measurement):
            lines.append("Native planner findings are missing; coverage is partial.")
    return dict(zip(REPORTS, [document(title, lines) for title, lines in (
        ("SEO strategy", strategy), ("Implementation roadmap", road), ("Content calendar", calendar),
        ("Site structure", structure), ("Measurement plan", measurement))]))


def finalize(output: Path) -> dict:
    check = validate(output)
    root, manifest, requirements = load_prepared(output)
    if manifest["status"] != "prepared" or any(path_at(root, name).exists() for name in REPORTS):
        raise PlanError("Strategy already finalized; refusing overwrite")
    role = role_result(root, manifest, requirements)
    reports = render(manifest, requirements, role)
    # All five reports are rendered and bounded before the first write.
    for name, raw in reports.items():
        pilot.write_new(path_at(root, name), raw)
        manifest["finalized_artifacts"][name] = planning.record(path_at(root, name))
    if role:
        manifest["finalized_artifacts"]["findings/plan.json"] = planning.record(path_at(root, "findings/plan.json"))
    manifest.update(status="complete" if check["complete"] else "partial", finalized_at=pilot.now())
    fd, temporary = tempfile.mkstemp(prefix=".plan-manifest-", dir=root)
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
    except (PlanError, OSError, ValueError, TypeError, KeyError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
