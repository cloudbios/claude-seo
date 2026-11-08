"""Offline bounded coordinator tests; no provider, agent or network calls."""
from __future__ import annotations

import importlib.util
import json
import socket
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
SPEC = importlib.util.spec_from_file_location("codex_audit_test", ROOT / "scripts/codex_audit.py")
assert SPEC and SPEC.loader
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)

HTML = '<html><head><title>Example</title></head><body><h1>Example</h1></body></html>'


@pytest.fixture
def sample(tmp_path, monkeypatch):
    monkeypatch.delenv("CLAUDE_SEO_LOCAL_TARGETS", raising=False)
    file = tmp_path / "page.html"
    file.write_text(HTML)
    urls = tmp_path / "urls.json"
    urls.write_text(json.dumps([{"url": "https://example.com/first", "html": str(file)},
                                {"url": "https://example.com/second", "html": str(file)}]))
    output = tmp_path / "audit"
    audit.plan(urls, output)
    return output


def result(output, task_id, status="complete", *, digest=None, role=None):
    root, ledger = audit._load(output)
    task = ledger["tasks"][task_id]
    page = root / "pages" / task["page_id"]
    value = {"role": role or task["role"], "capture_sha256": digest or ledger["captures"][task["page_id"]]["capture_sha256"],
             "status": status, "findings": ["Observed title in capture/parsed.json:title."],
             "limitations": ["No rendered or field-data verification."]}
    path = page / "findings" / (task["role"] + ".json")
    path.write_text(json.dumps(value))
    return path


def test_route_never_looks_up_auth_or_runs_network():
    with patch.object(audit.pilot, "modules", side_effect=AssertionError("dependencies")), \
            patch.object(socket, "getaddrinfo", side_effect=AssertionError("network")):
        for workflow in ("page", "technical", "schema"):
            assert audit.route(workflow)["skill"] == "seo-codex-pilot"
        assert audit.route("audit")["skill"] == "seo-codex-audit"
        assert audit.route("doctor")["target"] == "runtime"
        for workflow in ("backlinks", "setup", "image-gen", "anything"):
            assert audit.route(workflow)["status"] == "unavailable"


@pytest.mark.parametrize("entries", [[], ["https://example.com/" + str(i) for i in range(6)],
                                      ["http://127.0.0.1/"], ["https://user:secret@example.com/"],
                                      ["https://example.com", "https://EXAMPLE.com:443/#fragment"],
                                      [{"url": "https://example.com/", "extra": True}]])
def test_plan_rejects_unbounded_duplicate_or_unsafe_input(tmp_path, monkeypatch, entries):
    monkeypatch.delenv("CLAUDE_SEO_LOCAL_TARGETS", raising=False)
    urls = tmp_path / "urls.json"
    urls.write_text(json.dumps(entries))
    with pytest.raises(ValueError):
        audit.plan(urls, tmp_path / "audit")
    assert not (tmp_path / "audit").exists()


def test_plan_is_deterministic_and_has_no_capture_or_dns(sample, tmp_path):
    _, ledger = audit._load(sample)
    urls = tmp_path / "urls.json"
    with patch.object(audit.pilot, "capture", side_effect=AssertionError("capture")), \
            patch.object(socket, "getaddrinfo", side_effect=AssertionError("DNS")):
        audit.plan(urls, tmp_path / "other")
    _, second = audit._load(tmp_path / "other")
    assert ledger["plan"] == second["plan"]
    assert ledger["plan_sha256"] == second["plan_sha256"]
    assert list((sample / "pages").iterdir()) == []
    before = (sample / audit.MANIFEST).read_bytes()
    assert audit.next_jobs(sample, 2)["jobs"] == []
    assert (sample / audit.MANIFEST).read_bytes() == before


def test_sequential_capture_reuses_existing_pages(sample):
    actual = audit.pilot.capture
    calls = []

    def wrapped(url, path, fixture):
        calls.append(url)
        return actual(url, path, fixture)

    with patch.object(audit.pilot, "capture", side_effect=wrapped):
        value = audit.capture(sample)
        audit.capture(sample)
    assert calls == ["https://example.com/first", "https://example.com/second"]
    assert set(value["captures"].values()) == {"complete"}
    assert audit.next_jobs(sample, 0)["jobs"] == []
    jobs = audit.next_jobs(sample, 64)["jobs"]
    assert len(jobs) == 2
    assert [job["role"] for job in jobs] == ["technical", "schema"]
    assert jobs[0]["page_id"] == jobs[1]["page_id"]


def test_global_cap_duplicate_start_and_explicit_release(sample):
    audit.capture(sample)
    jobs = audit.next_jobs(sample, 2)["jobs"]
    audit.start(sample, jobs[0]["task_id"])
    with pytest.raises(audit.AuditError, match="eligible"):
        audit.start(sample, jobs[0]["task_id"])
    assert len(audit.next_jobs(sample, 2)["jobs"]) == 1
    audit.start(sample, jobs[1]["task_id"])
    assert audit.next_jobs(sample, 2)["jobs"] == []
    _, ledger = audit._load(sample)
    other = list(ledger["tasks"])[2]
    with pytest.raises(audit.AuditError, match="cap"):
        audit.start(sample, other)
    result(sample, jobs[0]["task_id"])
    state = audit.reconcile(sample)
    assert state["active_reservations"] == 2
    assert audit.next_jobs(sample, 2)["jobs"] == []
    audit.reconcile(sample, jobs[0]["task_id"])
    assert len(audit.next_jobs(sample, 2)["jobs"]) == 1
    with pytest.raises(audit.AuditError, match="active"):
        audit.reconcile(sample, jobs[0]["task_id"])


def test_partial_missing_claims_survive_reconcile_and_resume(sample):
    audit.capture(sample)
    jobs = audit.next_jobs(sample, 2)["jobs"]
    for job in jobs:
        audit.start(sample, job["task_id"])
    result(sample, jobs[0]["task_id"], "partial")
    status = audit.reconcile(sample)
    assert status["active_reservations"] == 2
    assert status["tasks"][jobs[0]["task_id"]] == "partial"
    assert status["tasks"][jobs[1]["task_id"]] == "pending"
    audit.reconcile(sample, jobs[0]["task_id"])
    resumed = audit.start(sample, jobs[0]["task_id"])
    assert resumed["reservation"] == 2
    assert resumed["capture_sha256"] == jobs[0]["capture_sha256"]


def test_completed_result_is_bound_and_never_rescheduled(sample):
    audit.capture(sample)
    job = audit.next_jobs(sample, 1)["jobs"][0]
    path = result(sample, job["task_id"])
    audit.reconcile(sample)
    assert all(item["task_id"] != job["task_id"] for item in audit.next_jobs(sample, 2)["jobs"])
    with pytest.raises(audit.AuditError, match="eligible"):
        audit.start(sample, job["task_id"])
    path.write_text(path.read_text() + " ")
    with pytest.raises(audit.AuditError, match="changed"):
        audit.report(sample)


def test_wrong_capture_or_role_is_refused(sample):
    audit.capture(sample)
    job = audit.next_jobs(sample, 1)["jobs"][0]
    result(sample, job["task_id"], digest="0" * 64)
    with pytest.raises(ValueError):
        audit.reconcile(sample)
    result(sample, job["task_id"], role="other")
    with pytest.raises(ValueError):
        audit.reconcile(sample)


def test_failed_or_invalid_capture_never_silently_retries(sample):
    with patch.object(audit.pilot, "capture", side_effect=OSError("private detail")) as capture:
        status = audit.capture(sample)
        audit.capture(sample)
    assert capture.call_count == 2  # One attempt per explicit page, no retry.
    assert set(status["captures"].values()) == {"failed"}
    assert audit.next_jobs(sample, 2)["jobs"] == []
    report = audit.report(sample)
    text = Path(report["report"]).read_text()
    assert "failed" in text and "private detail" not in text


def test_changed_capture_or_fixture_is_refused(sample, tmp_path):
    audit.capture(sample)
    job = audit.next_jobs(sample, 1)["jobs"][0]
    (Path(job["output_dir"]) / "capture/page.html").write_text("tampered")
    with pytest.raises(ValueError):
        audit.next_jobs(sample, 1)
    # An altered planned fixture is failed once without invoking capture.
    other = tmp_path / "other"
    audit.plan(tmp_path / "urls.json", other)
    (tmp_path / "page.html").write_text("changed fixture")
    with patch.object(audit.pilot, "capture", side_effect=AssertionError("capture")):
        assert set(audit.capture(other)["captures"].values()) == {"failed"}


def test_existing_unsealed_capture_can_be_adopted_after_interruption(sample):
    root, ledger = audit._load(sample)
    page = ledger["plan"]["pages"][0]
    audit.pilot.capture(page["url"], root / "pages" / page["id"], Path(page["fixture"]["path"]))
    actual = audit.pilot.capture
    with patch.object(audit.pilot, "capture", wraps=actual) as capture:
        audit.capture(sample)
    assert capture.call_count == 1


def test_reports_are_numbered_truthful_and_do_not_seal_pages(sample):
    audit.capture(sample)
    first = audit.report(sample)
    assert first["status"] == "partial"
    root, ledger = audit._load(sample)
    jobs = [audit._job(root, ledger, key) for key in ledger["tasks"]]
    for job in jobs:
        result(sample, job["task_id"])
    second = audit.report(sample)
    assert second["status"] == "complete"
    assert Path(first["report"]).name == "0001.md"
    assert Path(second["report"]).name == "0002.md"
    text = Path(second["report"]).read_text()
    assert "not a full-site audit or a site score" in text
    assert "Automated schema check: skipped" in text
    for page in ledger["plan"]["pages"]:
        _, capture = audit.pilot.load_capture(root / "pages" / page["id"])
        assert capture["status"] == "captured"
    Path(first["report"]).write_text("modified report")
    with pytest.raises(audit.AuditError, match="snapshot"):
        audit.report(sample)


def test_all_complete_files_with_active_process_remain_partial(sample):
    audit.capture(sample)
    root, ledger = audit._load(sample)
    task_id = next(iter(ledger["tasks"]))
    audit.start(sample, task_id)
    for key in ledger["tasks"]:
        result(sample, key)
    report = audit.report(sample)
    assert report["all_result_files_complete"] is True
    assert report["status"] == "partial"
    assert report["active_reservations"] == 1
    audit.reconcile(sample, task_id)
    assert audit.report(sample)["status"] == "complete"


def test_symlinks_overwrites_plan_tamper_and_lock_refused(sample, tmp_path):
    with pytest.raises(ValueError):
        audit.plan(tmp_path / "urls.json", sample)
    alias = tmp_path / "alias"
    alias.symlink_to(sample, target_is_directory=True)
    with pytest.raises(ValueError):
        audit.next_jobs(alias, 1)
    (sample / ".audit.lock").write_text("")
    with pytest.raises(audit.AuditError, match="coordinator"):
        audit.reconcile(sample)
    (sample / ".audit.lock").unlink()
    path = sample / audit.MANIFEST
    ledger = json.loads(path.read_text())
    ledger["plan"]["max_workers"] = 1
    path.write_text(json.dumps(ledger))
    with pytest.raises(audit.AuditError, match="identity"):
        audit.next_jobs(sample, 1)


def test_capacity_one_and_cli_failure_codes(sample, tmp_path, capsys):
    output = tmp_path / "one"
    audit.plan(tmp_path / "urls.json", output, max_workers=1)
    assert audit.main(["capture", "--output", str(output)]) == 0
    assert len(audit.next_jobs(output, 2)["jobs"]) == 1
    assert audit.main(["report", "--output", str(output)]) == 1
    assert audit.main(["route", "backlinks"]) == 1
    assert audit.main(["next", "--output", str(output), "--available-slots", "-1"]) == 2
    assert "error" in capsys.readouterr().err


def test_released_partial_is_not_automatically_retried(sample):
    audit.capture(sample)
    job = audit.next_jobs(sample, 1)["jobs"][0]
    audit.start(sample, job["task_id"])
    result(sample, job["task_id"], "partial")
    audit.reconcile(sample, job["task_id"])
    assert job["task_id"] not in [item["task_id"] for item in audit.next_jobs(sample, 2)["jobs"]]
    resumed = audit.next_jobs(sample, 2, resume_incomplete=True)
    assert resumed["resume_incomplete"] is True
    assert job["task_id"] in [item["task_id"] for item in resumed["jobs"]]


def test_preexisting_capture_must_match_planned_fixture_bytes(sample, tmp_path):
    root, ledger = audit._load(sample)
    page = ledger["plan"]["pages"][0]
    other = tmp_path / "other.html"
    other.write_text("<h1>Wrong fixture</h1>")
    directory = root / "pages" / page["id"]
    audit.pilot.capture(page["url"], directory, other)
    status = audit.capture(sample)
    assert status["captures"][page["id"]] == "failed"
    assert (directory / "capture/page.html").read_text() == "<h1>Wrong fixture</h1>"
    assert all(item["page_id"] != page["id"] for item in audit.next_jobs(sample, 2)["jobs"])


def test_report_recovers_matching_orphan_after_ledger_save_failure(sample):
    audit.capture(sample)
    with patch.object(audit, "_save", side_effect=OSError("interrupted ledger write")):
        with pytest.raises(OSError):
            audit.report(sample)
    orphan = sample / "reports/0001.md"
    original = orphan.read_bytes()
    _, ledger = audit._load(sample)
    assert ledger["reports"] == []
    recovered = audit.report(sample)
    assert recovered["report"] == str(orphan)
    assert orphan.read_bytes() == original
    _, ledger = audit._load(sample)
    assert len(ledger["reports"]) == 1


def test_unmatched_orphan_is_preserved_and_not_accepted(sample):
    audit.capture(sample)
    orphan = sample / "reports/0001.md"
    orphan.write_text("unverified content")
    with pytest.raises(audit.AuditError, match="differs"):
        audit.report(sample)
    assert orphan.read_text() == "unverified content"


def test_forged_complete_capture_without_hashes_is_rejected(sample):
    path = sample / audit.MANIFEST
    ledger = json.loads(path.read_text())
    page_id = ledger["plan"]["pages"][0]["id"]
    ledger["captures"][page_id] = {"status": "complete", "capture_sha256": None, "manifest_sha256": None, "error": None}
    path.write_text(json.dumps(ledger))
    with pytest.raises(audit.AuditError, match="lacks accepted evidence"):
        audit.next_jobs(sample, 2)
