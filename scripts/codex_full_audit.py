#!/usr/bin/env python3
"""Crawl a bounded public site and coordinate native Codex specialist evidence.

The CLI never starts agents. Reservations are released only by the caller after
observing process termination. A frozen crawl is shared by all specialists.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import codex_pilot as pilot  # noqa: E402

MANIFEST = "site-manifest.json"
MAX_JSON = 32 * 1024 * 1024
MAX_PAGE = 8 * 1024 * 1024
MAX_QUEUE = 10000
USER_AGENT = "CodexSEO/1.0"
ROLES = ("technical", "content", "schema", "sitemap", "performance", "visual", "geo", "sxo",
         "page", "images", "agentic", "content-brief", "plan", "cluster", "drift", "ecommerce",
         "programmatic", "competitor-pages", "flow", "local", "maps", "hreflang", "google",
         "backlinks", "dataforseo", "image-gen", "firecrawl", "ahrefs", "bing", "profound",
         "seranking", "matomo", "unlighthouse")
DEFAULT_ROLES = ROLES[:8]


class AuditError(ValueError):
    pass


def encode(value: object) -> bytes:
    return pilot.encode(value)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def absolute(path: Path) -> Path:
    if not path.is_absolute():
        raise AuditError("Paths must be absolute")
    return pilot.no_symlinks(path)


def decode(data: bytes) -> object:
    if len(data) > MAX_JSON:
        raise AuditError("JSON exceeds size limit")

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise AuditError("Duplicate JSON key")
            result[key] = value
        return result

    def nonfinite(_):
        raise AuditError("Nonfinite JSON number")

    try:
        value = json.loads(data, object_pairs_hook=pairs, parse_constant=nonfinite)
    except (ValueError, RecursionError) as exc:
        raise AuditError("Invalid JSON") from exc
    stack = [(value, 0)]
    nodes = 0
    while stack:
        item, depth = stack.pop()
        nodes += 1
        if depth > 40 or nodes > 500000:
            raise AuditError("JSON structure exceeds limit")
        if isinstance(item, dict):
            stack.extend((child, depth + 1) for child in item.values())
        elif isinstance(item, list):
            stack.extend((child, depth + 1) for child in item)
    return value


def read(path: Path, limit: int = MAX_JSON) -> bytes:
    return pilot.read_bytes(path, limit)


def record(path: Path) -> dict:
    data = read(path)
    return {"sha256": sha(data), "bytes": len(data)}


def replace(path: Path, data: bytes) -> None:
    absolute(path)
    fd, name = tempfile.mkstemp(prefix=".audit-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def url(value: str) -> str:
    if os.environ.get("CLAUDE_SEO_LOCAL_TARGETS", "").strip():
        raise AuditError("Unset local-target overrides for a public audit")
    from url_safety import validate_url
    if not isinstance(value, str) or len(value) > 8192 or not validate_url(value):
        raise AuditError("Expected a public HTTP(S) URL without credentials")
    parts = urlsplit(value)
    host = parts.hostname.lower()
    host = f"[{host}]" if ":" in host else host
    if parts.port and (parts.scheme.lower(), parts.port) not in (("http", 80), ("https", 443)):
        host += f":{parts.port}"
    return urlunsplit((parts.scheme.lower(), host, parts.path or "/", parts.query, ""))


def origin(value: str) -> str:
    parts = urlsplit(value)
    return urlunsplit((parts.scheme, parts.netloc, "", "", ""))


def identity(state: dict) -> str:
    frozen = {key: state[key] for key in ("config", "files", "pages", "excluded", "crawl_status", "queue")}
    return sha(encode(frozen))


def load(root: Path) -> dict:
    absolute(root)
    state = decode(read(root / MANIFEST))
    if not isinstance(state, dict) or state.get("version") != 1:
        raise AuditError("Unsupported site manifest")
    if state.get("config_sha256") != sha(encode(state["config"])):
        raise AuditError("Audit configuration changed")
    roles = state["config"].get("roles")
    if not isinstance(roles, list) or not roles or len(set(roles)) != len(roles) or any(role not in ROLES for role in roles):
        raise AuditError("Invalid specialist roles")
    if not isinstance(state.get("tasks"), dict) or set(state["tasks"]) != set(roles):
        raise AuditError("Specialist ledger disagrees with planned roles")
    for task in state["tasks"].values():
        if (not isinstance(task, dict) or set(task) != {"active", "starts", "status", "final_sha256", "evidence"}
                or type(task["active"]) is not bool or type(task["starts"]) is not int or task["starts"] < 0
                or task["status"] not in ("pending", "incomplete", "partial", "complete", "unavailable")
                or not isinstance(task["evidence"], dict)
                or (task["final_sha256"] is not None and not re.fullmatch(r"[a-f0-9]{64}", str(task["final_sha256"])))):
            raise AuditError("Invalid specialist ledger")
    for name, expected in state["files"].items():
        if Path(name).is_absolute() or ".." in Path(name).parts or record(root / name) != expected:
            raise AuditError(f"Saved evidence changed: {name}")
    for snapshot in state["reports"]:
        name = snapshot["path"]
        if not re.fullmatch(r"reports/[0-9]{4,}\.md", name) or record(root / name) != {key: snapshot[key] for key in ("sha256", "bytes")}:
            raise AuditError("Historical report snapshot changed")
        if record(root / name.replace(".md", ".json")) != snapshot["data"]:
            raise AuditError("Historical report data changed")
    if state.get("site_sha256") and state["site_sha256"] != identity(state):
        raise AuditError("Frozen crawl changed")
    return state


@contextlib.contextmanager
def locked(root: Path):
    absolute(root)
    # Atomic mkdir is portable and deliberately fail-closed after a crashed writer.
    lock = root / ".audit-lock"
    absolute(lock)
    try:
        lock.mkdir()
    except FileExistsError as exc:
        raise AuditError("Audit writer active; recover a stale .audit-lock only after verifying termination") from exc
    try:
        yield
    finally:
        lock.rmdir()


def save(root: Path, state: dict) -> None:
    replace(root / MANIFEST, encode(state))


def artifact(root: Path, state: dict, name: str, data: bytes) -> None:
    path = absolute(root / name)
    if root not in path.parents:
        raise AuditError("Artifact escapes output")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if read(path) != data:
            raise AuditError(f"Existing artifact differs: {name}")
    else:
        pilot.write_new(path, data)
    state["files"][name] = record(path)


def plan(output: Path, target: str, max_pages: int = 100, render: str = "auto",
         roles: list[str] | None = None, max_workers: int = 2, fixtures: Path | None = None) -> dict:
    root = absolute(output)
    selected = list(DEFAULT_ROLES) if roles is None else roles
    if not selected or len(set(selected)) != len(selected) or any(role not in ROLES for role in selected):
        raise AuditError("Select distinct supported specialist roles")
    if type(max_pages) is not int or not 1 <= max_pages <= 500 or max_workers not in (1, 2):
        raise AuditError("max-pages must be 1..500 and max-workers 1 or 2")
    if render not in ("auto", "always", "never"):
        raise AuditError("Invalid rendering mode")
    target = url(target)
    config = {"url": target, "origin": origin(target), "max_pages": max_pages, "render": render,
              "roles": selected, "max_workers": max_workers, "fixtures": fixtures is not None}
    fixture_data = None
    if fixtures is not None:
        fixture_data = read(absolute(fixtures))
        data = decode(fixture_data)
        if not isinstance(data, dict) or not isinstance(data.get("pages"), dict) or not isinstance(data.get("robots", ""), str):
            raise AuditError("Fixtures require pages object and optional robots text")
        config["fixtures_sha256"] = sha(fixture_data)
    if root.exists() or not root.parent.is_dir():
        raise AuditError("Output must be a new directory under an existing parent")
    root.mkdir(mode=0o700)
    for name in ("findings", "reports", "evidence", "resources", "crawl/pages"):
        (root / name).mkdir(parents=True)
    state = {"version": 1, "config": config, "config_sha256": sha(encode(config)), "files": {},
             "pages": [], "excluded": [], "queue": [target], "crawl_status": "pending", "site_sha256": None,
             "tasks": {role: {"active": False, "starts": 0, "status": "pending", "final_sha256": None,
                              "evidence": {}} for role in selected}, "reports": []}
    if fixture_data is not None:
        artifact(root, state, "resources/fixtures.json", fixture_data)
    pilot.write_new(root / MANIFEST, encode(state))
    return {"status": "planned", "roles": selected, "max_pages": max_pages, "fixture_mode": fixtures is not None}


def robots(root: Path, state: dict) -> RobotFileParser:
    target = state["config"]["origin"] + "/robots.txt"
    robots_name = "resources/robots.json"
    response = decode(read(root / robots_name)) if robots_name in state["files"] else None
    retry = response and (response.get("error") or response.get("too_large") or
                          response.get("status_code") is None or response["status_code"] >= 500 or response["status_code"] == 429)
    if response is None or retry:
        if state["config"]["fixtures"]:
            fixture = decode(read(root / "resources/fixtures.json"))
            response = {"url": target, "status_code": fixture.get("robots_status", 200), "content": fixture.get("robots", ""), "error": None}
        else:
            from fetch_page import fetch_page
            response = fetch_page(target, max_bytes=1024 * 1024, user_agent=USER_AGENT)
        if retry:
            attempt = 1 + sum(name.startswith("resources/robots-attempt-") for name in state["files"])
            artifact(root, state, f"resources/robots-attempt-{attempt:03d}.json", read(root / robots_name))
            replace(root / robots_name, encode(response))
            state["files"][robots_name] = record(root / robots_name)
        else:
            artifact(root, state, robots_name, encode(response))
    status = response.get("status_code")
    parser = RobotFileParser(target)
    if response.get("error") or response.get("too_large") or status is None or status >= 500 or status == 429:
        raise AuditError("robots.txt unavailable; crawl paused without fetching pages")
    if status in (401, 403):
        parser.disallow_all = True
    elif 200 <= status < 300:
        parser.parse((response.get("content") or "").splitlines())
    elif 400 <= status < 500:
        parser.allow_all = True
    else:
        raise AuditError("Unresolved robots.txt response; crawl paused")
    return parser


def enqueue(state: dict, candidates: list[str]) -> None:
    seen = {entry["url"] for entry in state["pages"]} | {entry["url"] for entry in state["excluded"]} | set(state["queue"])
    for candidate in candidates:
        try:
            candidate = url(candidate)
        except (AuditError, ValueError):
            continue
        if origin(candidate) != state["config"]["origin"] or candidate in seen:
            continue
        if len(state["queue"]) + len(seen) >= MAX_QUEUE:
            state["queue_truncated"] = True
            break
        state["queue"].append(candidate)
        seen.add(candidate)


def capture(root: Path, state: dict, target: str) -> dict:
    from parse_html import parse_html
    if state["config"]["fixtures"]:
        fixture = decode(read(root / "resources/fixtures.json"))["pages"].get(target)
        if isinstance(fixture, str):
            fixture = {"content": fixture}
        if not isinstance(fixture, dict):
            response = {"url": target, "status_code": 404, "content": "", "error": "No fixture for URL"}
        else:
            response = {"url": target, "status_code": 200, "error": None, **fixture}
    else:
        from render_page import render_page
        response = render_page(target, mode=state["config"]["render"], user_agent=USER_AGENT)
    page_id = f"p{len(state['pages']) + 1:03d}-{sha(target.encode())[:12]}"
    prefix = f"crawl/pages/{page_id}"
    raw = response["raw_content"] if response.get("raw_content") is not None else (response.get("content") or "")
    rendered = response.get("content") or ""
    if not isinstance(raw, str) or not isinstance(rendered, str) or max(len(raw.encode()), len(rendered.encode())) > MAX_PAGE:
        raise AuditError("Page representation exceeds size limit")
    artifact(root, state, prefix + "/raw.html", raw.encode())
    if response.get("raw_content") is not None and response.get("mode_used") != "raw":
        artifact(root, state, prefix + "/rendered.html", rendered.encode())
    transport = {key: value for key, value in response.items() if key not in ("content", "raw_content")}
    artifact(root, state, prefix + "/transport.json", encode(transport))
    final_url = url(response.get("url") or target)
    headers = {str(key).lower(): value for key, value in response.get("headers", {}).items()}
    content_type = str(headers.get("content-type", "text/html")).lower()
    okay = not response.get("error") and not response.get("too_large") and 200 <= (response.get("status_code") or 0) < 300
    okay = okay and origin(final_url) == state["config"]["origin"] and ("html" in content_type or not content_type)
    parsed = parse_html(rendered, final_url) if okay else {}
    artifact(root, state, prefix + "/parsed.json", encode(parsed))
    if okay:
        artifact(root, state, prefix + "/schema.json", encode(pilot.schema_check(rendered, final_url)))
        enqueue(state, [urljoin(final_url, link["href"]) for group in parsed.get("links", {}).values()
                        for link in group if isinstance(link, dict) and isinstance(link.get("href"), str)])
    return {"id": page_id, "url": target, "final_url": final_url, "status": "captured" if okay else "unavailable",
            "status_code": response.get("status_code"), "path": prefix, "representation": "fixture" if state["config"]["fixtures"] else response.get("mode_used", "raw")}


def crawl(output: Path) -> dict:
    root = absolute(output)
    with locked(root):
        state = load(root)
        if state["site_sha256"]:
            return {"status": state["crawl_status"], "pages": len(state["pages"]), "site_sha256": state["site_sha256"]}
        state["crawl_status"] = "running"
        try:
            policy = robots(root, state)
            if "resources/sitemap-discovery.json" not in state["files"]:
                # Only same-origin sitemaps are fetched; do not multiply cross-host crawl scope.
                artifact(root, state, "resources/sitemap-discovery.json", encode({
                    "declared": policy.site_maps() or [],
                    "limitation": "Declarations recorded; this bounded crawler discovers pages from same-origin HTML links. Use the sitemap specialist to validate XML separately."}))
            delay = policy.crawl_delay(USER_AGENT) or 0
            rate = policy.request_rate(USER_AGENT)
            if rate and rate.requests:
                delay = max(delay, rate.seconds / rate.requests)
            if delay > 60:
                raise AuditError("robots.txt requests a crawl delay above 60 seconds; use a scheduled crawl")
            while state["queue"] and len(state["pages"]) < state["config"]["max_pages"]:
                target = state["queue"][0]
                if not policy.can_fetch(USER_AGENT, target):
                    state["queue"].pop(0)
                    state["excluded"].append({"url": target, "reason": "robots.txt"})
                else:
                    if state["pages"] and delay and not state["config"]["fixtures"]:
                        time.sleep(delay)
                    page = capture(root, state, target)
                    state["queue"].pop(0)
                    state["pages"].append(page)
                save(root, state)
            state["crawl_status"] = "page-limit" if state["queue"] else "complete"
            if state.get("queue_truncated"):
                state["crawl_status"] = "queue-limit"
            state["site_sha256"] = identity(state)
            save(root, state)
            return {"status": state["crawl_status"], "pages": len(state["pages"]), "excluded": len(state["excluded"]),
                    "remaining": len(state["queue"]), "site_sha256": state["site_sha256"]}
        except BaseException:
            state["crawl_status"] = "paused"
            save(root, state)
            raise


def result(root: Path, state: dict, role: str) -> tuple[dict | None, str | None]:
    path = root / f"findings/{role}.json"
    if not path.exists():
        if state["tasks"][role]["final_sha256"]:
            raise AuditError(f"Finalized findings missing for {role}")
        return None, None
    data = read(path, 2 * 1024 * 1024)
    value = decode(data)
    if not isinstance(value, dict) or set(value) != {"role", "site_sha256", "status", "findings", "limitations"}:
        raise AuditError(f"Invalid findings contract for {role}")
    if value["role"] != role or value["site_sha256"] != state["site_sha256"] or value["status"] not in ("partial", "complete", "unavailable"):
        raise AuditError(f"Findings identity/status mismatch for {role}")
    for field in ("findings", "limitations"):
        if not isinstance(value[field], list) or len(value[field]) > 300 or any(not isinstance(item, str) or not item.strip() or len(item) > 8000 for item in value[field]):
            raise AuditError(f"Invalid findings text for {role}")
    if value["status"] != "complete" and not value["limitations"]:
        raise AuditError("Partial or unavailable results must explain limitations")
    if not value["findings"] and not value["limitations"]:
        raise AuditError("Results must record findings or inspected-scope limitations")
    locked_hash = state["tasks"][role]["final_sha256"]
    if locked_hash and sha(data) != locked_hash:
        raise AuditError(f"Finalized findings changed for {role}")
    for name, expected in state["tasks"][role]["evidence"].items():
        if record(root / name) != expected:
            raise AuditError(f"Specialist evidence changed for {role}")
    return value, sha(data)


def reconcile_state(root: Path, state: dict) -> None:
    for role, task in state["tasks"].items():
        value, _ = result(root, state, role)
        task["status"] = value["status"] if value else ("incomplete" if task["starts"] else "pending")


def dispatch(output: Path, action: str, role: str | None = None, available_slots: int = 0,
             resume_incomplete: bool = False) -> dict:
    root = absolute(output)
    with locked(root):
        state = load(root)
        if not state["site_sha256"]:
            raise AuditError("Finish and freeze the crawl before specialist dispatch")
        reconcile_state(root, state)
        if action in ("start", "release"):
            if role not in state["tasks"]:
                raise AuditError("Unknown specialist task")
            task = state["tasks"][role]
            if action == "start":
                if task["active"] or task["final_sha256"] or sum(item["active"] for item in state["tasks"].values()) >= state["config"]["max_workers"]:
                    raise AuditError("Task finalized, already active, or worker capacity exhausted")
                if task["starts"] and not resume_incomplete:
                    raise AuditError("Retry requires --resume-incomplete after observing prior termination")
                task["active"] = True
                task["starts"] += 1
            else:
                if not task["active"]:
                    raise AuditError("Task has no active reservation")
                value, digest = result(root, state, role)
                if value and value["status"] in ("complete", "unavailable"):
                    task["final_sha256"] = digest
                    cited_names = {name.rstrip('.') for name in re.findall(r"(?:crawl|resources|evidence)/[A-Za-z0-9_./-]+", "\n".join(value["findings"] + value["limitations"]))}
                    for name in cited_names:
                        if ".." in Path(name).parts:
                            raise AuditError("Specialist cited missing or unsafe evidence")
                        path = absolute(root / name)
                        if not path.is_file() or (not name.startswith("evidence/") and name not in state["files"]):
                            raise AuditError("Specialist cited missing or unsafe evidence")
                        if name.startswith("evidence/"):
                            task["evidence"][name] = record(path)
                task["active"] = False
        elif action == "next":
            if type(available_slots) is not int or available_slots < 0:
                raise AuditError("available-slots must be nonnegative")
        elif action != "reconcile":
            raise AuditError("Unknown dispatch action")
        save(root, state)
        capacity = max(0, state["config"]["max_workers"] - sum(item["active"] for item in state["tasks"].values()))
        candidates = [name for name, task in state["tasks"].items()
                      if not task["active"] and not task["final_sha256"] and (not task["starts"] or resume_incomplete)]
        return {"site_sha256": state["site_sha256"], "active": [name for name, task in state["tasks"].items() if task["active"]],
                "tasks": [{"task": name, "agent_type": "seo-full-" + name, "manifest": str(root / MANIFEST),
                           "output": str(root / f"findings/{name}.json")} for name in candidates[:min(capacity, available_slots)]],
                "statuses": {name: task["status"] for name, task in state["tasks"].items()}}


def report(output: Path) -> dict:
    from codex_planning import escaped
    root = absolute(output)
    with locked(root):
        state = load(root)
        if not state["site_sha256"]:
            raise AuditError("Crawl must be frozen before reporting")
        reconcile_state(root, state)
        categories = []
        for role, task in state["tasks"].items():
            value, _ = result(root, state, role)
            status = task["status"] if task["final_sha256"] and not task["active"] else "partial"
            categories.append({"name": role, "status": status, "score": None,
                               "findings": value["findings"] if value else [],
                               "limitations": value["limitations"] if value else ["No validated specialist result."]})
        complete = state["crawl_status"] == "complete" and bool(state["pages"]) and all(page["status"] == "captured" for page in state["pages"])
        complete = complete and all(category["status"] == "complete" for category in categories)
        payload = {"site": state["config"]["url"], "site_sha256": state["site_sha256"],
                   "summary": {"status": "complete" if complete else "partial", "health_score": None,
                               "pages_crawled": len(state["pages"]), "crawl_status": state["crawl_status"],
                               "pages_remaining": len(state["queue"]), "fixture_mode": state["config"]["fixtures"]},
                   "categories": categories}
        lines = ["# Full Codex SEO audit", "", f"Site: {escaped(payload['site'])}", "",
                 f"Status: {payload['summary']['status']}; captured {len(state['pages'])} pages; crawl {state['crawl_status']}.",
                 "", "Scores and unavailable provider metrics are unmeasured. Specialist conclusions cover only the pages and evidence they cite.",
                 "The page cap and same-origin HTML-link discovery can leave URLs outside this crawl. robots.txt exclusions are recorded in the manifest.",
                 f"Fixture mode: {state['config']['fixtures']}. Crawl identity: {state['site_sha256']}.", ""]
        for category in categories:
            lines += [f"## {category['name']} ({category['status']})", ""]
            lines += ["- " + escaped(item) for item in category["findings"]]
            lines += ["- Limitation: " + escaped(item) for item in category["limitations"]]
            lines.append("")
        data = ("\n".join(lines) + "\n").encode()
        number = len(state["reports"]) + 1
        snapshot = f"reports/{number:04d}.md"
        pilot.write_new(root / snapshot, data)
        pilot.write_new(root / f"reports/{number:04d}.json", encode(payload))
        replace(root / "FULL-AUDIT-REPORT.md", data)
        replace(root / "audit-data.json", encode(payload))
        state["reports"].append({"path": snapshot, **record(root / snapshot),
                                 "data": record(root / f"reports/{number:04d}.json"),
                                 "status": payload["summary"]["status"]})
        save(root, state)
        return {"status": payload["summary"]["status"], "report": str(root / "FULL-AUDIT-REPORT.md"), "snapshot": snapshot}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("plan")
    p.add_argument("--url", required=True)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--max-pages", type=int, default=100)
    p.add_argument("--render", choices=("auto", "always", "never"), default="auto")
    p.add_argument("--roles", nargs="+", choices=ROLES)
    p.add_argument("--max-workers", type=int, default=2)
    p.add_argument("--fixtures", type=Path)
    for name in ("crawl", "next", "start", "release", "reconcile", "report"):
        p = commands.add_parser(name)
        p.add_argument("--output", required=True, type=Path)
        if name in ("start", "release"):
            p.add_argument("--task", required=True)
        if name == "next":
            p.add_argument("--available-slots", type=int, required=True)
        if name in ("start", "next"):
            p.add_argument("--resume-incomplete", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "plan":
            value = plan(args.output, args.url, args.max_pages, args.render, args.roles, args.max_workers, args.fixtures)
        elif args.command == "crawl":
            value = crawl(args.output)
        elif args.command == "report":
            value = report(args.output)
        else:
            value = dispatch(args.output, args.command, getattr(args, "task", None),
                             getattr(args, "available_slots", 0), getattr(args, "resume_incomplete", False))
    except (AuditError, pilot.PilotError, OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(2, f"{exc}\n")
    print(json.dumps(value, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
