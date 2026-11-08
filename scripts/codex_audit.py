#!/usr/bin/env python3
"""Coordinate a fixed public-page sample; native processes remain caller-owned.

Only the coordinator writes the audit ledger. Roles write their assigned page
result. Reservations persist until explicit release after process termination.
No command discovers links, starts agents, installs packages, or loads providers.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import codex_pilot as pilot  # noqa: E402

MAX_PAGES = 5
MAX_MANIFEST_BYTES = 1024 * 1024
MAX_INPUT_BYTES = 64 * 1024
MANIFEST = "audit-manifest.json"
ROLES = ("technical", "schema")
CORE_ROLES = (*ROLES, "content", "images", "local", "hreflang")
SUPPORTED_ROLES = (*CORE_ROLES, "geo")
GEO_RESOURCES = (
    ".codex/agents/seo-codex-geo.toml",
    ".agents/skills/seo-codex-geo/SKILL.md",
    ".agents/skills/seo-codex-geo/references/review.md",
    ".agents/skills/seo-codex-geo/LICENSE.txt",
)


class AuditError(ValueError):
    pass


def _geo_available() -> bool:
    if not (pilot.ROOT / "stage-manifest.json").is_file():
        return False
    if not all((pilot.ROOT / name).is_file() for name in GEO_RESOURCES):
        return False
    try:
        source = pilot.provenance()
        destinations = {entry["destination"] for entry in source["files"]}
        return source["kind"] == "staged-copy" and set(GEO_RESOURCES).issubset(destinations)
    except (pilot.PilotError, OSError, ValueError, KeyError, TypeError, RecursionError):
        return False


def route(workflow: str) -> dict:
    if workflow in ("page", "technical", "schema"):
        return {"status": "available", "workflow": workflow, "skill": "seo-codex-pilot", "focus": workflow}
    if workflow == "audit":
        return {"status": "available", "workflow": workflow, "skill": "seo-codex-audit", "focus": "explicit-page-sample"}
    if workflow in ("content", "images", "local", "hreflang"):
        return {"status": "available", "workflow": workflow, "skill": "seo-codex-" + workflow, "focus": workflow}
    if workflow == "geo":
        if _geo_available():
            return {"status": "available", "workflow": workflow, "skill": "seo-codex-geo",
                    "focus": "source-passages-and-preview-controls"}
        return {"status": "unavailable", "workflow": workflow,
                "reason": "The optional GEO source-review payload is missing or fails staged provenance validation."}
    if workflow == "visual":
        required = ("scripts/codex_visual.py", ".codex/agents/seo-codex-visual.toml",
                    ".agents/skills/seo-codex-visual/SKILL.md",
                    ".agents/skills/seo-codex-visual/references/review.md")
        if all((pilot.ROOT / path).is_file() for path in required):
            return {"status": "available", "workflow": workflow, "skill": "seo-codex-visual",
                    "focus": "offline-saved-html"}
        return {"status": "unavailable", "workflow": workflow,
                "reason": "The optional offline visual adapter is not staged; no browser or provider was started."}
    if workflow == "sitemap":
        required = ("scripts/codex_sitemap.py", "scripts/sitemap_discovery.py",
                    ".codex/agents/seo-codex-sitemap.toml",
                    ".agents/skills/seo-codex-sitemap/SKILL.md",
                    ".agents/skills/seo-codex-sitemap/references/review.md")
        if all((pilot.ROOT / path).is_file() for path in required):
            return {"status": "available", "workflow": workflow, "skill": "seo-codex-sitemap",
                    "focus": "saved-xml-analysis"}
        return {"status": "unavailable", "workflow": workflow,
                "reason": "The optional saved sitemap adapter is not staged; no discovery or URL fetch was started."}
    if workflow == "agentic":
        required = ("scripts/codex_agentic.py", "scripts/lighthouse_agentic.py",
                    ".codex/agents/seo-codex-agentic.toml",
                    ".agents/skills/seo-codex-agentic/SKILL.md",
                    ".agents/skills/seo-codex-agentic/references/review.md")
        if all((pilot.ROOT / path).is_file() for path in required):
            return {"status": "available", "workflow": workflow, "skill": "seo-codex-agentic",
                    "focus": "saved-lighthouse-report"}
        return {"status": "unavailable", "workflow": workflow,
                "reason": "The optional saved Lighthouse adapter is not staged; no browser, PSI request or provider was started."}
    if workflow == "content-brief":
        required = ("scripts/codex_brief.py", "scripts/codex_planning.py", ".codex/agents/seo-codex-content-brief.toml",
                    ".agents/skills/seo-codex-content-brief/SKILL.md",
                    ".agents/skills/seo-codex-content-brief/references/review.md",
                    ".agents/skills/seo-codex-content-brief/LICENSE.txt")
        if all((pilot.ROOT / path).is_file() for path in required):
            return {"status": "available", "workflow": workflow, "skill": "seo-codex-content-brief",
                    "focus": "supplied-evidence-planning"}
        return {"status": "unavailable", "workflow": workflow,
                "reason": "The optional content-brief adapter is not staged; no research or authoring was started."}
    if workflow == "plan":
        required = ("scripts/codex_plan.py", "scripts/codex_planning.py", ".codex/agents/seo-codex-plan.toml",
                    ".agents/skills/seo-codex-plan/SKILL.md",
                    ".agents/skills/seo-codex-plan/references/review.md",
                    ".agents/skills/seo-codex-plan/references/industries.md")
        if all((pilot.ROOT / path).is_file() for path in required):
            return {"status": "available", "workflow": workflow, "skill": "seo-codex-plan",
                    "focus": "supplied-evidence-strategy"}
        return {"status": "unavailable", "workflow": workflow,
                "reason": "The optional strategy planner is not staged; no research or planning was started."}
    if workflow == "drift":
        required = ("scripts/codex_drift.py", "scripts/codex_planning.py", ".codex/agents/seo-codex-drift.toml",
                    ".agents/skills/seo-codex-drift/SKILL.md",
                    ".agents/skills/seo-codex-drift/references/review.md",
                    ".agents/skills/seo-codex-drift/references/fields.md")
        if all((pilot.ROOT / path).is_file() for path in required):
            return {"status": "available", "workflow": workflow, "skill": "seo-codex-drift",
                    "focus": "saved-capture-comparison"}
        return {"status": "unavailable", "workflow": workflow,
                "reason": "The optional saved-capture drift adapter is not staged; no fetch or monitoring was started."}
    if workflow == "programmatic":
        required = ("scripts/codex_programmatic.py", "scripts/codex_planning.py",
                    ".codex/agents/seo-codex-programmatic.toml",
                    ".agents/skills/seo-codex-programmatic/SKILL.md",
                    ".agents/skills/seo-codex-programmatic/references/review.md",
                    ".agents/skills/seo-codex-programmatic/LICENSE.txt")
        if all((pilot.ROOT / path).is_file() for path in required):
            return {"status": "available", "workflow": workflow, "skill": "seo-codex-programmatic",
                    "focus": "saved-page-family-sample"}
        return {"status": "unavailable", "workflow": workflow,
                "reason": "The optional programmatic sample reviewer is not staged."}
    if workflow == "competitor-pages":
        required = ("scripts/codex_comparison.py", "scripts/codex_planning.py",
                    ".codex/agents/seo-codex-competitor-pages.toml",
                    ".agents/skills/seo-codex-competitor-pages/SKILL.md",
                    ".agents/skills/seo-codex-competitor-pages/references/review.md",
                    ".agents/skills/seo-codex-competitor-pages/LICENSE.txt")
        if all((pilot.ROOT / path).is_file() for path in required):
            return {"status": "available", "workflow": workflow, "skill": "seo-codex-competitor-pages",
                    "focus": "two-subject-comparison-brief"}
        return {"status": "unavailable", "workflow": workflow,
                "reason": "The optional comparison-brief adapter is not staged."}
    if workflow == "doctor":
        return {"status": "available", "workflow": workflow, "target": "runtime",
                "command": "scripts/runtime.py --host codex --state-root <absolute-root> doctor --json"}
    return {"status": "unavailable", "workflow": workflow, "reason": "Workflow is outside this bounded adapter; no provider or global fallback was attempted."}


def _json(path: Path, limit: int = MAX_MANIFEST_BYTES):
    try:
        return json.loads(pilot.read_bytes(path, limit))
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise AuditError("Invalid or oversized JSON input") from exc


def _url(value: str) -> str:
    if not isinstance(value, str) or len(value) > 8192:
        raise AuditError("Each page requires a bounded URL string")
    if os.environ.get("CLAUDE_SEO_LOCAL_TARGETS", "").strip():
        raise AuditError("Unset local-target overrides for this public-page audit")
    safety, _ = pilot.modules()
    if not safety.validate_url(value):
        raise AuditError("Page URL is not a permitted public HTTP(S) target")
    try:
        parts = urlsplit(value)
        port = parts.port
    except ValueError as exc:
        raise AuditError("Invalid page URL") from exc
    host = parts.hostname.lower()
    host = f"[{host}]" if ":" in host else host
    if port is not None and not ((parts.scheme.lower() == "https" and port == 443) or (parts.scheme.lower() == "http" and port == 80)):
        host += f":{port}"
    return urlunsplit((parts.scheme.lower(), host, parts.path or "/", parts.query, ""))


def _selected_roles(value: object) -> list[str]:
    if (not isinstance(value, list) or not value or
            any(not isinstance(role, str) or role not in SUPPORTED_ROLES for role in value) or
            len(set(value)) != len(value)):
        raise AuditError("Roles must be a nonempty list of unique supported roles")
    return [role for role in SUPPORTED_ROLES if role in value]


def _plan_roles(specification: dict) -> list[str]:
    # Plans created before role selection retain the original two specialists.
    roles = specification.get("roles", list(ROLES))
    selected = _selected_roles(roles)
    if selected != roles:
        raise AuditError("Planned roles must use canonical supported order")
    return selected


def _new_plan(entries: object, source_file: Path, max_workers: int, roles: list[str]) -> dict:
    if max_workers not in (1, 2):
        raise AuditError("max-workers must be 1 or 2")
    if not isinstance(entries, list) or not 1 <= len(entries) <= MAX_PAGES:
        raise AuditError("Supply an explicit list of 1 to 5 pages")
    pages = []
    seen = set()
    for index, entry in enumerate(entries, 1):
        if isinstance(entry, str):
            entry = {"url": entry}
        if not isinstance(entry, dict) or set(entry) - {"url", "html"} or "url" not in entry:
            raise AuditError("Pages must be URL strings or objects with url and optional html")
        url = _url(entry["url"])
        if url in seen:
            raise AuditError("Duplicate page URLs are not accepted")
        seen.add(url)
        fixture = None
        if "html" in entry:
            if not isinstance(entry["html"], str) or not entry["html"]:
                raise AuditError("Fixture path must be a nonempty string")
            path = Path(entry["html"])
            path = pilot.no_symlinks(path if path.is_absolute() else source_file.parent / path)
            data = pilot.read_bytes(path)
            fixture = {"path": str(path), "sha256": pilot.digest(data), "bytes": len(data)}
        pages.append({"id": f"p{index:03d}-{pilot.digest(url.encode())[:12]}", "url": url, "fixture": fixture})
    return {"max_workers": max_workers, "roles": roles, "pages": pages, "provenance": pilot.provenance()}


def plan(urls: Path, output: Path, max_workers: int = 2, roles: list[str] | None = None) -> dict:
    selected = _selected_roles(list(ROLES) if roles is None else roles)
    if "geo" in selected and not _geo_available():
        raise AuditError("GEO review requires the complete verified --geo-review stage")
    source = pilot.no_symlinks(urls)
    specification = _new_plan(_json(source, MAX_INPUT_BYTES), source, max_workers, selected)
    root = pilot.no_symlinks(output)
    if root.exists() or not root.parent.is_dir():
        raise AuditError("Output must be a new directory under an existing parent")
    tasks = {f"{page['id']}:{role}": {"page_id": page["id"], "role": role, "active": False,
             "starts": 0, "status": "pending", "completed_sha256": None}
             for page in specification["pages"] for role in selected}
    ledger = {"schema_version": 1, "created_at": pilot.now(), "plan": specification,
              "plan_sha256": pilot.digest(pilot.encode(specification, compact=True)),
              "captures": {}, "tasks": tasks, "reports": []}
    root.mkdir(mode=0o700)
    (root / "pages").mkdir()
    (root / "reports").mkdir()
    pilot.write_new(root / MANIFEST, pilot.encode(ledger))
    return {"status": "planned", "pages": len(specification["pages"]), "tasks": len(tasks),
            "max_workers": max_workers, "plan_sha256": ledger["plan_sha256"]}


def _load(output: Path) -> tuple[Path, dict]:
    root = pilot.no_symlinks(output)
    ledger = _json(root / MANIFEST)
    if not isinstance(ledger, dict) or ledger.get("schema_version") != 1:
        raise AuditError("Unsupported audit ledger")
    specification = ledger.get("plan")
    if not isinstance(specification, dict) or pilot.digest(pilot.encode(specification, compact=True)) != ledger.get("plan_sha256"):
        raise AuditError("Audit plan identity mismatch")
    roles = _plan_roles(specification)
    pages = specification.get("pages")
    if not isinstance(pages, list) or not 1 <= len(pages) <= MAX_PAGES or specification.get("max_workers") not in (1, 2):
        raise AuditError("Invalid audit plan bounds")
    expected_tasks = set()
    seen = set()
    for index, page in enumerate(pages, 1):
        if not isinstance(page, dict) or not isinstance(page.get("url"), str):
            raise AuditError("Invalid page plan")
        expected = f"p{index:03d}-{pilot.digest(page['url'].encode())[:12]}"
        if page.get("id") != expected or page["url"] in seen:
            raise AuditError("Page identity mismatch")
        seen.add(page["url"])
        expected_tasks.update(f"{expected}:{role}" for role in roles)
        pilot.no_symlinks(root / "pages" / expected)
    tasks = ledger.get("tasks")
    if not isinstance(tasks, dict) or set(tasks) != expected_tasks:
        raise AuditError("Audit task identity mismatch")
    for task_id, task in tasks.items():
        if not isinstance(task, dict) or task_id != f"{task.get('page_id')}:{task.get('role')}" or type(task.get("active")) is not bool:
            raise AuditError("Invalid task ledger")
        if task.get("status") not in ("pending", "partial", "complete", "unavailable") or type(task.get("starts")) is not int or task["starts"] < 0:
            raise AuditError("Invalid task state")
        bound = task.get("completed_sha256")
        if bound is not None and (not isinstance(bound, str) or not re.fullmatch(r"[a-f0-9]{64}", bound)):
            raise AuditError("Invalid completed result identity")
    if sum(task["active"] for task in tasks.values()) > specification["max_workers"]:
        raise AuditError("Active reservations exceed the audit cap")
    captures = ledger.get("captures")
    if not isinstance(captures, dict) or set(captures) - {page["id"] for page in pages}:
        raise AuditError("Invalid capture ledger")
    for record in captures.values():
        if not isinstance(record, dict) or record.get("status") not in ("complete", "failed"):
            raise AuditError("Invalid capture state")
        hashes = (record.get("capture_sha256"), record.get("manifest_sha256"))
        if not (all(value is None for value in hashes) or
                all(isinstance(value, str) and re.fullmatch(r"[a-f0-9]{64}", value) for value in hashes)):
            raise AuditError("Invalid capture identity")
        if record["status"] == "complete" and (hashes[0] is None or record.get("error") is not None):
            raise AuditError("Complete capture lacks accepted evidence")
        if record["status"] == "failed" and not isinstance(record.get("error"), str):
            raise AuditError("Failed capture lacks a reason")
    reports = ledger.get("reports")
    if not isinstance(reports, list) or len(reports) > 100:
        raise AuditError("Invalid report ledger")
    for index, record in enumerate(reports, 1):
        name = f"reports/{index:04d}.md"
        if not isinstance(record, dict) or record.get("path") != name:
            raise AuditError("Invalid report identity")
        data = pilot.read_bytes(pilot.no_symlinks(root / name), MAX_MANIFEST_BYTES)
        if pilot.digest(data) != record.get("sha256") or len(data) != record.get("bytes"):
            raise AuditError("Report snapshot changed")
    return root, ledger


@contextlib.contextmanager
def _locked(output: Path):
    root = pilot.no_symlinks(output)
    lock = pilot.no_symlinks(root / ".audit.lock")
    try:
        handle = lock.open("x")
    except FileExistsError as exc:
        raise AuditError("Another coordinator command is active; verify it stopped before recovering its lock") from exc
    try:
        handle.close()
        yield _load(root)
    finally:
        lock.unlink()


def _save(root: Path, ledger: dict) -> None:
    data = pilot.encode(ledger)
    if len(data) > MAX_MANIFEST_BYTES:
        raise AuditError("Audit ledger exceeds its size limit")
    fd, temp = tempfile.mkstemp(prefix=".audit-manifest-", dir=root)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        pilot.no_symlinks(root / MANIFEST)
        os.replace(temp, root / MANIFEST)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def _accept_capture(root: Path, page: dict, provenance: dict) -> dict:
    directory = root / "pages" / page["id"]
    _, manifest = pilot.load_capture(directory)
    if manifest["capture"]["requested_url"] != page["url"] or manifest["capture"]["representation"] != ("fixture" if page["fixture"] else "raw-http"):
        raise AuditError("Capture does not match the planned page")
    if manifest["status"] != "captured":
        raise AuditError("Audit pages must remain unsealed and resumable")
    if manifest.get("provenance") != provenance:
        raise AuditError("Capture source differs from the audit plan")
    fixture = page["fixture"]
    if fixture and (manifest["capture"]["sha256"] != fixture["sha256"] or
                    manifest["artifacts"]["capture/page.html"]["bytes"] != fixture["bytes"]):
        raise AuditError("Capture bytes differ from the planned fixture")
    return {"status": "complete" if manifest["capture"]["complete"] else "failed",
            "capture_sha256": manifest["capture"]["sha256"],
            "manifest_sha256": pilot.digest(pilot.read_bytes(directory / pilot.MANIFEST)),
            "error": None if manifest["capture"]["complete"] else "Page capture failed or is incomplete"}


def _observe(root: Path, ledger: dict) -> dict:
    observations = {}
    for page in ledger["plan"]["pages"]:
        page_id = page["id"]
        record = ledger["captures"].get(page_id)
        if record and record.get("capture_sha256") is not None:
            actual = _accept_capture(root, page, ledger["plan"]["provenance"])
            if actual != record:
                raise AuditError("Captured page identity changed")
        for role in _plan_roles(ledger["plan"]):
            task_id = f"{page_id}:{role}"
            task = ledger["tasks"][task_id]
            result = None
            result_hash = None
            if record and record["status"] == "complete":
                directory = root / "pages" / page_id
                result = pilot.role_result(directory, role, record["capture_sha256"])
                if result is not None:
                    result_hash = pilot.digest(pilot.read_bytes(directory / "findings" / f"{role}.json"))
            if task["completed_sha256"] is not None and (result_hash != task["completed_sha256"] or not result or result["status"] != "complete"):
                raise AuditError("Previously completed role result changed or disappeared")
            status = result["status"] if result else ("unavailable" if record and record["status"] == "failed" else "pending")
            observations[task_id] = {"status": status, "result": result, "sha256": result_hash}
    return observations


def _record(ledger: dict, observations: dict) -> None:
    for task_id, observed in observations.items():
        task = ledger["tasks"][task_id]
        task["status"] = observed["status"]
        if observed["status"] == "complete":
            task["completed_sha256"] = observed["sha256"]


def capture(output: Path) -> dict:
    with _locked(output) as (root, ledger):
        _observe(root, ledger)
        for page in ledger["plan"]["pages"]:
            if page["id"] in ledger["captures"]:
                continue
            directory = root / "pages" / page["id"]
            try:
                if not directory.exists():
                    fixture = page["fixture"]
                    if fixture:
                        data = pilot.read_bytes(pilot.no_symlinks(Path(fixture["path"])))
                        if len(data) != fixture["bytes"] or pilot.digest(data) != fixture["sha256"]:
                            raise AuditError("Planned fixture changed")
                    pilot.capture(page["url"], directory, Path(fixture["path"]) if fixture else None)
                ledger["captures"][page["id"]] = _accept_capture(root, page, ledger["plan"]["provenance"])
            except (OSError, ValueError, ImportError):
                ledger["captures"][page["id"]] = {"status": "failed", "capture_sha256": None,
                                                  "manifest_sha256": None, "error": "Capture unavailable or failed validation; create a new audit to retry"}
            _save(root, ledger)
        observations = _observe(root, ledger)
        _record(ledger, observations)
        _save(root, ledger)
        return _summary(ledger, observations)


def _job(root: Path, ledger: dict, task_id: str) -> dict:
    task = ledger["tasks"][task_id]
    directory = root / "pages" / task["page_id"]
    return {"task_id": task_id, "page_id": task["page_id"], "role": task["role"],
            "agent_type": "seo-codex-" + task["role"], "output_dir": str(directory),
            "capture_sha256": ledger["captures"][task["page_id"]]["capture_sha256"],
            "result_file": str(directory / "findings" / f"{task['role']}.json"),
            "reservation": task["starts"]}


def _summary(ledger: dict, observations: dict) -> dict:
    active = sum(task["active"] for task in ledger["tasks"].values())
    results_complete = all(item["status"] == "complete" for item in observations.values())
    captures_complete = len(ledger["captures"]) == len(ledger["plan"]["pages"]) and all(item["status"] == "complete" for item in ledger["captures"].values())
    return {"status": "complete" if results_complete and captures_complete and not active else "partial",
            "captures": {page["id"]: ledger["captures"].get(page["id"], {"status": "missing"})["status"] for page in ledger["plan"]["pages"]},
            "tasks": {task: item["status"] for task, item in observations.items()},
            "all_result_files_complete": results_complete, "active_reservations": active}


def next_jobs(output: Path, available_slots: int, resume_incomplete: bool = False) -> dict:
    if type(available_slots) is not int or not 0 <= available_slots <= 64:
        raise AuditError("available-slots must be between 0 and 64")
    root, ledger = _load(output)
    observations = _observe(root, ledger)
    active = sum(task["active"] for task in ledger["tasks"].values())
    capacity = min(available_slots, ledger["plan"]["max_workers"] - active)
    jobs = []
    for page in ledger["plan"]["pages"]:
        for role in _plan_roles(ledger["plan"]):
            task_id = f"{page['id']}:{role}"
            task = ledger["tasks"][task_id]
            record = ledger["captures"].get(task["page_id"])
            if (record and record["status"] == "complete" and not task["active"]
                    and observations[task_id]["status"] != "complete" and (task["starts"] == 0 or resume_incomplete)):
                jobs.append(_job(root, ledger, task_id))
    return {**_summary(ledger, observations), "jobs": jobs[:capacity], "resume_incomplete": resume_incomplete}


def start(output: Path, task_id: str) -> dict:
    with _locked(output) as (root, ledger):
        observations = _observe(root, ledger)
        if task_id not in ledger["tasks"]:
            raise AuditError("Unknown task")
        task = ledger["tasks"][task_id]
        record = ledger["captures"].get(task["page_id"])
        if not record or record["status"] != "complete" or task["active"] or observations[task_id]["status"] == "complete":
            raise AuditError("Task is not eligible to start")
        if sum(item["active"] for item in ledger["tasks"].values()) >= ledger["plan"]["max_workers"]:
            raise AuditError("Audit concurrency cap is already reserved")
        _record(ledger, observations)
        task["active"] = True
        task["starts"] += 1
        _save(root, ledger)
        return _job(root, ledger, task_id)


def reconcile(output: Path, release_task: str | None = None) -> dict:
    with _locked(output) as (root, ledger):
        observations = _observe(root, ledger)
        if release_task is not None:
            if release_task not in ledger["tasks"] or not ledger["tasks"][release_task]["active"]:
                raise AuditError("Task has no active reservation to release")
            ledger["tasks"][release_task]["active"] = False
        _record(ledger, observations)
        _save(root, ledger)
        return _summary(ledger, observations)


def report(output: Path) -> dict:
    with _locked(output) as (root, ledger):
        observations = _observe(root, ledger)
        _record(ledger, observations)
        summary = _summary(ledger, observations)
        if len(ledger["reports"]) >= 100:
            raise AuditError("Report snapshot limit reached")
        roles = _plan_roles(ledger["plan"])
        # Preserve the original two-role excerpt budget as role coverage grows.
        items_per_field = max(1, 40 // len(roles))
        lines = ["# Explicit page-sample SEO audit", "", f"Review status: {summary['status']}.",
                 f"Active native-process reservations: {summary['active_reservations']}.", "",
                 "This report covers only the listed pages. It is not a full-site audit or a site score.",
                 "Source HTML cannot establish indexing, field Core Web Vitals, traffic or rendered behavior.", ""]
        for page in ledger["plan"]["pages"]:
            record = ledger["captures"].get(page["id"])
            state = record["status"] if record else "missing"
            lines.extend([f"## {page['id']}", "", f"URL: {page['url']}", f"Capture: {state}.", ""])
            if record and record.get("error"):
                lines.append(record["error"])
            if record and record.get("capture_sha256"):
                _, manifest = pilot.load_capture(root / "pages" / page["id"])
                lines.append(f"Representation: {manifest['capture']['representation']}. Automated schema check: {manifest['checks']['schema']}.")
            for role in roles:
                item = observations[f"{page['id']}:{role}"]
                lines.extend(["", f"### {role.title()}: {item['status']}", ""])
                result = item["result"]
                if result is None:
                    lines.append("No validated role result is available; coverage remains incomplete.")
                    continue
                for field in ("findings", "limitations"):
                    for text in result[field][:items_per_field]:
                        safe = text.replace("\n", " ").replace("<", "&lt;").replace(">", "&gt;")
                        encoded = safe.encode()
                        excerpt = encoded[:2000].decode("utf-8", errors="ignore")
                        lines.append(f"- {field}: {excerpt}" + (" [truncated; read role artifact]" if len(encoded) > 2000 else ""))
                    if len(result[field]) > items_per_field:
                        lines.append(f"- {len(result[field]) - items_per_field} additional {field} retained; read role artifact.")
        data = ("\n".join(lines) + "\n").encode()
        if len(data) > MAX_MANIFEST_BYTES:
            raise AuditError("Aggregate report exceeds size limit")
        name = f"reports/{len(ledger['reports']) + 1:04d}.md"
        path = pilot.no_symlinks(root / name)
        if path.exists():
            # A crash after writing the immutable snapshot but before the
            # atomic ledger replacement is recoverable only if regeneration
            # from current verified evidence produces the exact same bytes.
            if pilot.read_bytes(path, MAX_MANIFEST_BYTES) != data:
                raise AuditError("Unrecorded report differs from current evidence; preserve it for explicit recovery")
        else:
            pilot.write_new(path, data)
        ledger["reports"].append({"path": name, "sha256": pilot.digest(data), "bytes": len(data)})
        _save(root, ledger)
        return {**summary, "report": str(root / name)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("route").add_argument("workflow")
    p = commands.add_parser("plan")
    p.add_argument("--urls", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--max-workers", type=int, choices=(1, 2), default=2)
    p.add_argument("--roles", nargs="+", choices=SUPPORTED_ROLES, default=list(ROLES))
    for name in ("capture", "next", "start", "reconcile", "release", "report"):
        command = commands.add_parser(name)
        command.add_argument("--output", type=Path, required=True)
        if name == "next":
            command.add_argument("--available-slots", type=int, required=True)
            command.add_argument("--resume-incomplete", action="store_true",
                                 help="Explicitly include previously started incomplete tasks; do not loop retries automatically")
        if name in ("start", "release"):
            command.add_argument("--task", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "route":
            result = route(args.workflow)
        elif args.command == "plan":
            result = plan(args.urls, args.output, args.max_workers, args.roles)
        elif args.command == "capture":
            result = capture(args.output)
        elif args.command == "next":
            result = next_jobs(args.output, args.available_slots, args.resume_incomplete)
        elif args.command == "start":
            result = start(args.output, args.task)
        elif args.command == "reconcile":
            result = reconcile(args.output)
        elif args.command == "release":
            result = reconcile(args.output, args.task)
        else:
            result = report(args.output)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if args.command == "capture":
            return 0 if all(value == "complete" for value in result["captures"].values()) else 1
        return 1 if result.get("status") in ("unavailable", "partial") and args.command in ("route", "report") else 0
    except (OSError, ValueError, ImportError, KeyError, TypeError) as exc:
        # Do not emit raw filesystem/network exception strings or URLs.
        message = str(exc) if type(exc) is AuditError else "Audit command refused: invalid, unavailable or changed evidence"
        print(json.dumps({"status": "error", "error": message}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
