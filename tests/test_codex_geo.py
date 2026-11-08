"""Offline GEO capability gates and saved-source audit lifecycle coverage."""
from __future__ import annotations

import importlib.util
import json
import socket
import sys
import tomllib
from pathlib import Path
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True


def load_script(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


audit = load_script("codex_geo_audit_test", "codex_audit.py")
stage = load_script("codex_geo_stage_test", "stage_codex_pilot.py")
GEO_RESOURCES = (
    ".codex/agents/seo-codex-geo.toml",
    ".agents/skills/seo-codex-geo/SKILL.md",
    ".agents/skills/seo-codex-geo/references/review.md",
    ".agents/skills/seo-codex-geo/LICENSE.txt",
)
CORE_ROLES = ("technical", "schema", "content", "images", "local", "hreflang")
HTML = """<html><head><title>Source evidence</title>
<meta name="robots" content="max-snippet:120"></head><body>
<h1>Source evidence</h1><p>A clearly attributed source passage.</p></body></html>"""


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.delenv("CLAUDE_SEO_LOCAL_TARGETS", raising=False)
    monkeypatch.setattr(socket, "getaddrinfo", Mock(side_effect=AssertionError("DNS is forbidden")))
    safety, _ = audit.pilot.modules()
    monkeypatch.setattr(safety, "safe_requests_session",
                        Mock(side_effect=AssertionError("HTTP is forbidden")))


@pytest.fixture
def staged(tmp_path, monkeypatch):
    root = tmp_path / "geo-stage"
    stage.stage_pilot(root, source_root=ROOT, geo_review=True, register_agents=True)
    monkeypatch.setattr(audit.pilot, "ROOT", root)
    return root


@pytest.fixture
def urls(tmp_path):
    fixture = tmp_path / "page.html"
    fixture.write_text(HTML)
    path = tmp_path / "urls.json"
    path.write_text(json.dumps([
        {"url": "https://example.com/first", "html": str(fixture)},
        {"url": "https://example.com/second", "html": str(fixture)},
    ]))
    return path


def write_result(output, task_id, status="complete", *, role=None, digest=None):
    root, ledger = audit._load(output)
    task = ledger["tasks"][task_id]
    path = root / "pages" / task["page_id"] / "findings" / f"{task['role']}.json"
    path.write_text(json.dumps({
        "role": task["role"] if role is None else role,
        "capture_sha256": ledger["captures"][task["page_id"]]["capture_sha256"] if digest is None else digest,
        "status": status,
        "findings": ["Observed preview control in capture/page.html and title in capture/parsed.json."],
        "limitations": ["Saved-source review does not measure AI visibility or citations."],
    }))
    return path


def assert_gate_closed(urls, output):
    assert audit.route("geo")["status"] == "unavailable"
    with pytest.raises(audit.AuditError, match="GEO"):
        audit.plan(urls, output, roles=["geo"])
    assert not output.exists()


def test_registered_geo_stage_is_complete_and_routes_without_dependencies(staged, monkeypatch):
    manifest = json.loads((staged / "stage-manifest.json").read_text())
    assert set(GEO_RESOURCES).issubset({entry["destination"] for entry in manifest["files"]})
    assert len(manifest["files"]) == 32
    assert len([path for path in staged.rglob("*") if path.is_file()]) == 35
    registration = tomllib.loads((staged / ".codex/config.toml").read_text())
    assert set(registration["agents"]) == {"seo-codex-" + role for role in (*CORE_ROLES, "geo")}
    assert audit.pilot.provenance()["kind"] == "staged-copy"
    monkeypatch.setattr(audit.pilot, "modules", Mock(side_effect=AssertionError("dependency inspection")))
    assert audit.route("geo") == {
        "status": "available", "workflow": "geo", "skill": "seo-codex-geo",
        "focus": "source-passages-and-preview-controls",
    }


def test_unstaged_checkout_cannot_plan_geo(urls, tmp_path):
    assert_gate_closed(urls, tmp_path / "unavailable")


def test_core_stage_does_not_expose_geo(urls, tmp_path, monkeypatch):
    root = tmp_path / "core-stage"
    stage.stage_pilot(root, source_root=ROOT, core_orchestration=True, register_agents=True)
    monkeypatch.setattr(audit.pilot, "ROOT", root)
    assert_gate_closed(urls, tmp_path / "unavailable")


@pytest.mark.parametrize("resource", GEO_RESOURCES)
@pytest.mark.parametrize("damage", ["missing", "corrupt", "symlink", "unlisted"])
def test_each_geo_resource_must_be_present_hashed_and_listed(staged, urls, tmp_path, resource, damage):
    path = staged / resource
    if damage == "missing":
        path.unlink()
    elif damage == "corrupt":
        path.write_bytes(path.read_bytes() + b"\nmodified")
    elif damage == "symlink":
        replacement = tmp_path / "replacement"
        replacement.write_bytes(path.read_bytes())
        path.unlink()
        path.symlink_to(replacement)
    else:
        manifest_path = staged / "stage-manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["files"] = [entry for entry in manifest["files"] if entry["destination"] != resource]
        manifest_path.write_text(json.dumps(manifest))
        # Existing unlisted bytes must not confer the optional capability.
        assert path.is_file()
        assert audit.pilot.provenance()["kind"] == "staged-copy"
    assert_gate_closed(urls, tmp_path / "unavailable")


@pytest.mark.parametrize("damage", ["missing", "invalid-json", "wrong-version", "symlink"])
def test_geo_requires_valid_stage_manifest(staged, urls, tmp_path, damage):
    path = staged / "stage-manifest.json"
    if damage == "missing":
        path.unlink()
    elif damage == "invalid-json":
        path.write_text("{")
    elif damage == "wrong-version":
        manifest = json.loads(path.read_text())
        manifest["format_version"] = 99
        path.write_text(json.dumps(manifest))
    else:
        replacement = tmp_path / "manifest.json"
        replacement.write_bytes(path.read_bytes())
        path.unlink()
        path.symlink_to(replacement)
    assert_gate_closed(urls, tmp_path / "unavailable")


@pytest.mark.parametrize("resource", ["scripts/codex_pilot.py", "AGENTS.md", ".codex/config.toml"])
def test_geo_verifies_other_staged_and_generated_files(staged, urls, tmp_path, resource):
    path = staged / resource
    path.write_bytes(path.read_bytes() + b"\nmodified")
    assert_gate_closed(urls, tmp_path / "unavailable")


def test_geo_only_lifecycle_explicit_retry_and_saved_capture(staged, urls, tmp_path):
    output = tmp_path / "geo-audit"
    audit.plan(urls, output, roles=["geo"])
    assert audit.next_jobs(output, 64)["jobs"] == []
    assert set(audit.capture(output)["captures"].values()) == {"complete"}
    jobs = audit.next_jobs(output, 64)["jobs"]
    assert len(jobs) == 2
    assert all(job["agent_type"] == "seo-codex-geo" for job in jobs)
    assert all(Path(job["result_file"]).name == "geo.json" for job in jobs)
    first = jobs[0]["task_id"]
    started = audit.start(output, first)
    assert started["reservation"] == 1
    write_result(output, first, "partial")
    assert audit.reconcile(output)["active_reservations"] == 1
    audit.reconcile(output, first)
    assert first not in [job["task_id"] for job in audit.next_jobs(output, 64)["jobs"]]
    assert first in [job["task_id"] for job in audit.next_jobs(output, 64, True)["jobs"]]
    retry = audit.start(output, first)
    assert retry["reservation"] == 2
    assert retry["capture_sha256"] == started["capture_sha256"]
    for job in jobs:
        write_result(output, job["task_id"])
    assert audit.report(output)["status"] == "partial"
    audit.reconcile(output, first)
    report = audit.report(output)
    assert report["status"] == "complete"
    rendered = Path(report["report"]).read_text()
    assert "### Geo: complete" in rendered
    assert "### Technical" not in rendered
    assert audit.next_jobs(output, 64, True)["jobs"] == []


def test_mixed_roles_have_canonical_order_and_global_two_worker_cap(staged, urls, tmp_path):
    output = tmp_path / "mixed"
    audit.plan(urls, output, roles=list(reversed((*CORE_ROLES, "geo"))))
    _, ledger = audit._load(output)
    assert ledger["plan"]["roles"] == [*CORE_ROLES, "geo"]
    assert len(ledger["tasks"]) == 14
    audit.capture(output)
    initial = audit.next_jobs(output, 64)["jobs"]
    assert [job["role"] for job in initial] == ["technical", "schema"]
    for job in initial:
        audit.start(output, job["task_id"])
    geo_id = f"{initial[0]['page_id']}:geo"
    with pytest.raises(audit.AuditError, match="cap"):
        audit.start(output, geo_id)
    assert audit.next_jobs(output, 64)["jobs"] == []
    write_result(output, initial[0]["task_id"])
    assert audit.reconcile(output)["active_reservations"] == 2
    audit.reconcile(output, initial[0]["task_id"])
    assert len(audit.next_jobs(output, 64)["jobs"]) == 1
    geo = audit.start(output, geo_id)
    assert geo["agent_type"] == "seo-codex-geo"
    for task_id in ledger["tasks"]:
        write_result(output, task_id)
    assert audit.report(output)["status"] == "partial"
    audit.reconcile(output, initial[1]["task_id"])
    audit.reconcile(output, geo_id)
    report = audit.report(output)
    assert report["status"] == "complete"
    text = Path(report["report"]).read_text()
    for role in (*CORE_ROLES, "geo"):
        assert f"### {role.title()}: complete" in text


@pytest.mark.parametrize("damage", ["wrong-role", "wrong-capture", "changed", "removed"])
def test_geo_results_are_bound_to_role_capture_and_accepted_bytes(staged, urls, tmp_path, damage):
    output = tmp_path / "bound"
    audit.plan(urls, output, roles=["geo"])
    audit.capture(output)
    task_id = audit.next_jobs(output, 1)["jobs"][0]["task_id"]
    if damage == "wrong-role":
        write_result(output, task_id, role="technical")
    elif damage == "wrong-capture":
        write_result(output, task_id, digest="0" * 64)
    else:
        path = write_result(output, task_id)
        audit.reconcile(output)
        if damage == "changed":
            path.write_text(path.read_text() + " ")
        else:
            path.unlink()
    with pytest.raises(ValueError):
        audit.report(output)


def test_failed_request_preserves_capture_and_marks_geo_unavailable(staged, tmp_path, monkeypatch):
    urls = tmp_path / "live-urls.json"
    urls.write_text(json.dumps(["https://example.com/failed"]))
    output = tmp_path / "failed"
    audit.plan(urls, output, roles=["geo"])
    safety, _ = audit.pilot.modules()
    request = Mock(side_effect=safety.requests.exceptions.SSLError("private credential detail"))
    monkeypatch.setattr(safety, "safe_requests_session", request)
    summary = audit.capture(output)
    assert request.call_count == 1
    assert set(summary["captures"].values()) == {"failed"}
    assert set(summary["tasks"].values()) == {"unavailable"}
    root, ledger = audit._load(output)
    page = root / "pages" / ledger["plan"]["pages"][0]["id"]
    _, capture = audit.pilot.load_capture(page)
    assert capture["capture"]["complete"] is False
    assert capture["capture"]["representation"] == "raw-http"
    assert capture["checks"]["transport"] == "failed"
    assert ledger["captures"][page.name]["capture_sha256"] == capture["capture"]["sha256"]
    assert (page / "capture/page.html").read_bytes() == b""
    assert json.loads((page / "capture/transport.json").read_text())["error"] == "SSLError"
    assert audit.next_jobs(output, 64, True)["jobs"] == []
    audit.capture(output)
    assert request.call_count == 1
    report = audit.report(output)
    assert report["status"] == "partial"
    rendered = Path(report["report"]).read_text()
    assert "### Geo: unavailable" in rendered
    assert "private credential detail" not in rendered


@pytest.mark.parametrize("roles", [None, list(CORE_ROLES)])
def test_old_two_and_six_role_graphs_do_not_gain_geo(staged, urls, tmp_path, roles):
    assert audit.ROLES == audit.pilot.ROLES == ("technical", "schema")
    assert audit.CORE_ROLES == CORE_ROLES
    output = tmp_path / "old-graph"
    audit.plan(urls, output, roles=roles)
    path = output / audit.MANIFEST
    ledger = json.loads(path.read_text())
    expected = list(audit.ROLES) if roles is None else roles
    assert ledger["plan"]["roles"] == expected
    if roles is None:
        del ledger["plan"]["roles"]
        ledger["plan_sha256"] = audit.pilot.digest(audit.pilot.encode(ledger["plan"], compact=True))
        path.write_text(json.dumps(ledger))
    for resource in GEO_RESOURCES:
        (staged / resource).unlink()
    assert audit.route("geo")["status"] == "unavailable"
    _, loaded = audit._load(output)
    assert len(loaded["tasks"]) == 2 * len(expected)
    assert {task["role"] for task in loaded["tasks"].values()} == set(expected)
    assert audit.report(output)["status"] == "partial"


def test_saved_geo_results_remain_readable_after_optional_stage_removed(staged, urls, tmp_path):
    output = tmp_path / "saved"
    audit.plan(urls, output, roles=["geo"])
    audit.capture(output)
    _, ledger = audit._load(output)
    for task_id in ledger["tasks"]:
        write_result(output, task_id)
    first = audit.report(output)
    assert first["status"] == "complete"
    evidence = {path: path.read_bytes() for path in output.rglob("*")
                if path.is_file() and ("capture" in path.parts or "findings" in path.parts)}
    snapshot = Path(first["report"]).read_bytes()
    for resource in GEO_RESOURCES:
        (staged / resource).unlink()
    assert audit.route("geo")["status"] == "unavailable"
    assert audit.next_jobs(output, 64)["jobs"] == []
    assert audit.reconcile(output)["status"] == "complete"
    assert audit.report(output)["status"] == "complete"
    assert Path(first["report"]).read_bytes() == snapshot
    assert all(path.read_bytes() == data for path, data in evidence.items())
