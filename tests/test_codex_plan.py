"""Offline strategy evidence, planning graph and immutable-output contracts."""
import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import codex_pilot as pilot  # noqa: E402
import codex_plan as plan  # noqa: E402


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setattr("socket.getaddrinfo", lambda *a, **kw: pytest.fail("Unexpected DNS"))
    monkeypatch.setattr("requests.sessions.Session.request", lambda *a, **kw: pytest.fail("Unexpected network"))


def requirements(**updates):
    return {"mode": "new", "business_context": "Residential drafting, not construction",
            "audience": "Homeowners", "goals": ["Explain the drawing service"],
            "resources": {"team": "Owner", "capacity": "unknown", "budget": "unknown"},
            "horizon_weeks": 8, "sources": [], **updates}


def capture(tmp_path, name="home", kind="site", url=None):
    fixture = tmp_path / (name + ".html")
    fixture.write_text('<html><title>Drafting</title><body><h1>Drawing services</h1></body></html>')
    output = tmp_path / name
    pilot.capture(url or "https://example.com/" + name, output, fixture)
    return {"id": name, "kind": kind, "capture": str(output)}


def prepare(tmp_path, value=None):
    source = tmp_path / "requirements.json"
    source.write_bytes(pilot.encode(requirements() if value is None else value))
    output = tmp_path / "plan"
    return source, output, plan.prepare(source, output)


def result(manifest, status="complete", source=None):
    value = {"role": "plan", "requirements_sha256": manifest["evidence"]["requirements_sha256"],
             "evidence_sha256": manifest["evidence_sha256"], "status": status,
             **{name: [] for name in plan.COLLECTIONS}, "limitations": ["Capacity needs confirmation."]}
    if status == "partial":
        return value
    value["notes"] = [{"id": "need", "basis": "user", "text": "Goal supplied in input.json goals[0].", "sources": []}]
    if source:
        value["notes"].append({"id": "observed", "basis": "source", "text": "Saved capture/parsed.json title: Drafting", "sources": [source]})
    value["roadmap"] = [{"id": "clarify", "action": "Confirm audience questions", "rationale": ["need"],
        "priority": "P1", "owner": "Owner", "start_week": 1, "end_week": 4, "depends_on": [],
        "done_when": "Owner accepts the brief"}]
    value["content_calendar"] = [{"id": "guide", "topic": "Preparing a drafting brief", "purpose": "Help readers prepare",
        "format": "Guide", "owner": "Owner", "start_week": 2, "end_week": 3, "roadmap_id": "clarify",
        "evidence_needed": ["Approved service scope"], "rationale": ["need"]}]
    value["site_structure"] = [{"id": "guide", "url": "/drafting-guide/", "basis": "proposal", "purpose": "Guide page",
        "parent_id": None, "links_to": [], "rationale": ["need"], "sources": []}]
    value["measurement"] = [{"id": "requests", "question": "Do suitable readers contact the business?",
        "metric": "Qualified service enquiries", "scope": "Proposed guide, monthly",
        "collection_source": "Owner-reviewed enquiry log", "owner": "Owner", "cadence": "Monthly",
        "baseline": "unavailable", "target": {"status": "not-set", "value": None}, "rationale": ["need"]}]
    return value


def write_result(output, value):
    (output / "findings/plan.json").write_bytes(pilot.encode(value))


def test_new_input_only_complete_strategy(tmp_path):
    source, output, manifest = prepare(tmp_path)
    assert manifest["evidence"]["representation"] == "input-only"
    assert plan.validate(output)["role"] == "missing"
    write_result(output, result(manifest))
    assert plan.finalize(output)["complete"]
    assert plan.validate(output)["phase"] == "complete"
    assert source.read_bytes() == pilot.encode(requirements())
    assert set(p.name for p in output.glob("*.md")) == set(plan.REPORTS)
    assert "Input-only planning" in (output / "SEO-STRATEGY.md").read_text()
    assert "baseline: unavailable" in (output / "MEASUREMENT-PLAN.md").read_text()
    with pytest.raises(plan.PlanError, match="already finalized"):
        plan.finalize(output)


def test_existing_plan_uses_verified_site_capture(tmp_path):
    site = capture(tmp_path)
    _, output, manifest = prepare(tmp_path, requirements(mode="existing", sources=[site]))
    value = result(manifest, source="home")
    value["site_structure"][0].update(url="https://example.com/home", basis="source", sources=["home"])
    write_result(output, value)
    assert plan.finalize(output)["complete"]
    assert manifest["evidence"]["sources"][0]["capture_sha256"] == pilot.json_read(Path(site["capture"]) / pilot.MANIFEST)["capture"]["sha256"]


@pytest.mark.parametrize("update", [
    {"mode": "other"}, {"mode": []}, {"business_context": ""}, {"audience": False},
    {"goals": []}, {"goals": [""]}, {"goals": ["x"] * 11}, {"goals": {}},
    {"resources": {}}, {"resources": {"team": "a", "capacity": "b", "budget": 10}},
    {"resources": {"team": "a", "capacity": "b", "budget": "c", "extra": True}},
    {"horizon_weeks": True}, {"horizon_weeks": 0}, {"horizon_weeks": 53}, {"horizon_weeks": "8"},
    {"industry": "other"}, {"industry": []}, {"constraints": [""]}, {"constraints": ["x"] * 31},
    {"sources": {}}, {"sources": [{}] * 6}, {"mode": "existing"}, {"extra": True},
    {"sources": [{"id": "Home", "kind": "site", "capture": "/tmp/site"}]},
    {"sources": [{"id": "home", "kind": "target", "capture": "/tmp/site"}]},
    {"sources": [{"id": "home", "kind": "site", "capture": "relative"}]},
])
def test_invalid_requirements(update):
    with pytest.raises(plan.PlanError):
        plan.normalize(requirements(**update))


@pytest.mark.parametrize("field", ["mode", "business_context", "audience", "goals", "resources", "horizon_weeks", "sources"])
def test_required_fields(field):
    value = requirements()
    del value[field]
    with pytest.raises(plan.PlanError):
        plan.normalize(value)


@pytest.mark.parametrize("raw", [b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":1e999}', b'\xff', b'[' * 40 + b'0' + b']' * 40])
def test_invalid_json_rejected_before_output(tmp_path, raw):
    source = tmp_path / "input.json"
    source.write_bytes(raw)
    output = tmp_path / "plan"
    with pytest.raises(plan.PlanError):
        plan.prepare(source, output)
    assert not output.exists()


def test_input_size_bound(tmp_path):
    source = tmp_path / "input.json"
    source.write_bytes(b" " * (plan.MAX_INPUT + 1))
    with pytest.raises(plan.PlanError):
        plan.prepare(source, tmp_path / "plan")


def test_source_count_duplicates_and_failed_capture(tmp_path, monkeypatch):
    site = capture(tmp_path)
    with pytest.raises(plan.PlanError):
        plan.normalize(requirements(sources=[site, dict(site, id="copy")]))
    second = capture(tmp_path, "second", url="https://example.com/home")
    with pytest.raises(plan.PlanError, match="final URLs"):
        prepare(tmp_path, requirements(sources=[site, second]))
    original = pilot.load_capture
    def failed(path):
        root, manifest = original(path)
        manifest["capture"]["complete"] = False
        return root, manifest
    monkeypatch.setattr(pilot, "load_capture", failed)
    with pytest.raises(plan.PlanError, match="successful complete"):
        prepare(tmp_path, requirements(sources=[site]))


def test_five_captures_accepted(tmp_path):
    sources = [capture(tmp_path, "site" + str(n)) for n in range(5)]
    _, output, manifest = prepare(tmp_path, requirements(mode="existing", sources=sources))
    assert len(manifest["evidence"]["sources"]) == 5
    assert plan.validate(output)["valid"]


def test_partial_and_missing_finalization(tmp_path):
    _, output, manifest = prepare(tmp_path)
    write_result(output, result(manifest, "partial"))
    assert plan.finalize(output)["phase"] == "partial"
    other = tmp_path / "other"
    other.mkdir()
    _, output, _ = prepare(other)
    assert plan.finalize(output)["role"] == "missing"
    assert "Native planner findings are missing" in (output / plan.REPORTS[0]).read_text()


@pytest.mark.parametrize("change", ["role", "hash", "status", "extra", "missing_collection", "empty_collection", "bad_collection", "duplicate_id"])
def test_role_envelope_and_collections(tmp_path, change):
    _, output, manifest = prepare(tmp_path)
    value = result(manifest)
    if change == "role":
        value["role"] = "content-brief"
    elif change == "hash":
        value["requirements_sha256"] = "0" * 64
    elif change == "status":
        value["status"] = []
    elif change == "extra":
        value["extra"] = True
    elif change == "missing_collection":
        del value["measurement"]
    elif change == "empty_collection":
        value["measurement"] = []
    elif change == "bad_collection":
        value["measurement"] = {}
    else:
        value["roadmap"].append(copy.deepcopy(value["roadmap"][0]))
    write_result(output, value)
    with pytest.raises(plan.PlanError):
        plan.validate(output)


@pytest.mark.parametrize("change", ["basis", "text", "source", "empty_source", "rationale", "id", "extra"])
def test_note_contract(tmp_path, change):
    _, output, manifest = prepare(tmp_path)
    value = result(manifest)
    row = value["notes"][0]
    if change == "basis":
        row["basis"] = "fact"
    elif change == "text":
        row["text"] = "x" * 4001
    elif change == "source":
        row["sources"] = ["missing"]
    elif change == "empty_source":
        row["basis"] = "source"
    elif change == "rationale":
        value["roadmap"][0]["rationale"] = ["missing"]
    elif change == "id":
        row["id"] = False
    else:
        row["extra"] = True
    write_result(output, value)
    with pytest.raises(plan.PlanError):
        plan.validate(output)


@pytest.mark.parametrize("change", ["priority", "week_bool", "week_zero", "week_end", "week_order", "dependency", "self", "timing", "cycle"])
def test_roadmap_graph_and_windows(tmp_path, change):
    _, output, manifest = prepare(tmp_path)
    value = result(manifest)
    row = value["roadmap"][0]
    if change == "priority":
        row["priority"] = "urgent"
    elif change == "week_bool":
        row["start_week"] = True
    elif change == "week_zero":
        row["start_week"] = 0
    elif change == "week_end":
        row["end_week"] = 9
    elif change == "week_order":
        row["start_week"] = 5
    elif change == "dependency":
        row["depends_on"] = ["missing"]
    elif change == "self":
        row["depends_on"] = ["clarify"]
    else:
        other = dict(row, id="second", start_week=1, end_week=1, depends_on=["clarify"])
        value["roadmap"].append(other)
        if change == "timing":
            pass
        else:
            row.update(start_week=1, end_week=1, depends_on=["second"])
            value["content_calendar"][0].update(start_week=1, end_week=1)
    write_result(output, value)
    with pytest.raises(plan.PlanError):
        plan.validate(output)


@pytest.mark.parametrize("change", ["unknown_task", "outside_task", "week_bool", "unknown_note", "bad_evidence"])
def test_calendar_contract(tmp_path, change):
    _, output, manifest = prepare(tmp_path)
    value = result(manifest)
    row = value["content_calendar"][0]
    if change == "unknown_task":
        row["roadmap_id"] = "missing"
    elif change == "outside_task":
        row["end_week"] = 5
    elif change == "week_bool":
        row["end_week"] = False
    elif change == "unknown_note":
        row["rationale"] = []
    else:
        row["evidence_needed"] = [False]
    write_result(output, value)
    with pytest.raises(plan.PlanError):
        plan.validate(output)


@pytest.mark.parametrize("url", ["https://example.com/page", "//example.com/page", "/a/../b", "/a/./b", "/x?y", "/x#y", "/a\\b", "/a b", "/%2e%2e/x", "/%252e%252e/x", "/%2f%2fevil", "/%00"])
def test_proposed_paths_reject_unsafe_or_absolute_urls(tmp_path, url):
    _, output, manifest = prepare(tmp_path)
    value = result(manifest)
    value["site_structure"][0]["url"] = url
    write_result(output, value)
    with pytest.raises(plan.PlanError):
        plan.validate(output)


@pytest.mark.parametrize("change", ["missing_parent", "self_parent", "self_link", "missing_link", "cycle", "observed_without_source", "wrong_observed_url", "reference_is_not_site", "bad_url_type"])
def test_site_structure_graph_and_source_identity(tmp_path, change):
    site = capture(tmp_path)
    reference = capture(tmp_path, "ref", "reference")
    _, output, manifest = prepare(tmp_path, requirements(sources=[site, reference]))
    value = result(manifest)
    row = value["site_structure"][0]
    if change == "missing_parent":
        row["parent_id"] = "missing"
    elif change == "self_parent":
        row["parent_id"] = "guide"
    elif change == "self_link":
        row["links_to"] = ["guide"]
    elif change == "missing_link":
        row["links_to"] = ["missing"]
    elif change == "cycle":
        row["parent_id"] = "second"
        value["site_structure"].append(dict(row, id="second", parent_id="guide", url="/second/"))
    else:
        row.update(basis="source", url="https://example.com/home", sources=["home"])
        if change == "observed_without_source":
            row["sources"] = []
        elif change == "wrong_observed_url":
            row["url"] = "https://example.com/unknown"
        elif change == "reference_is_not_site":
            row.update(url="https://example.com/ref", sources=["ref"])
        else:
            row["url"] = []
    write_result(output, value)
    with pytest.raises(plan.PlanError):
        plan.validate(output)


@pytest.mark.parametrize("change", ["baseline_number", "baseline_claim", "target_status", "target_missing_value", "not_set_value", "unknown_note"])
def test_measurement_has_no_invented_baseline(tmp_path, change):
    _, output, manifest = prepare(tmp_path)
    value = result(manifest)
    row = value["measurement"][0]
    if change == "baseline_number":
        row["baseline"] = 100
    elif change == "baseline_claim":
        row["baseline"] = "zero"
    elif change == "target_status":
        row["target"]["status"] = "forecast"
    elif change == "target_missing_value":
        row["target"]["status"] = "proposal"
    elif change == "not_set_value":
        row["target"]["value"] = "100"
    else:
        row["rationale"] = ["missing"]
    write_result(output, value)
    with pytest.raises(plan.PlanError):
        plan.validate(output)


def test_proposed_target_is_labelled_and_existing_requires_observation(tmp_path):
    site = capture(tmp_path)
    _, output, manifest = prepare(tmp_path, requirements(mode="existing", sources=[site]))
    value = result(manifest)
    write_result(output, value)
    with pytest.raises(plan.PlanError, match="assess a site"):
        plan.validate(output)
    value["notes"].append({"id": "page", "basis": "source", "text": "Saved title", "sources": ["home"]})
    value["measurement"][0]["target"] = {"status": "proposal", "value": "Define baseline before setting a target"}
    write_result(output, value)
    assert plan.finalize(output)["complete"]
    assert "target [proposal]" in (output / "MEASUREMENT-PLAN.md").read_text()


@pytest.mark.parametrize("target", ["input.json", "original", "capture", "manifest", "result", *plan.REPORTS])
def test_tamper_rejected(tmp_path, target):
    site = capture(tmp_path)
    source, output, manifest = prepare(tmp_path, requirements(sources=[site]))
    write_result(output, result(manifest))
    if target in {"result", *plan.REPORTS}:
        plan.finalize(output)
    if target == "original":
        changed = source
    elif target == "capture":
        changed = Path(site["capture"]) / "capture/page.html"
    elif target == "manifest":
        manifest["evidence"]["network"] = "live"
        (output / plan.MANIFEST).write_bytes(pilot.encode(manifest))
        with pytest.raises(plan.PlanError):
            plan.validate(output)
        return
    elif target == "result":
        changed = output / "findings/plan.json"
    else:
        changed = output / target
    with changed.open("ab") as handle:
        handle.write(b" ")
    with pytest.raises(plan.PlanError):
        plan.validate(output)


def test_rehashed_normalized_input_cannot_replace_original(tmp_path):
    _, output, manifest = prepare(tmp_path)
    value = json.loads((output / "input.json").read_bytes())
    value["audience"] = "Changed audience"
    raw = pilot.encode(value)
    (output / "input.json").write_bytes(raw)
    manifest["evidence"]["requirements_sha256"] = pilot.digest(raw)
    manifest["evidence"]["artifacts"]["input.json"] = {"sha256": pilot.digest(raw), "bytes": len(raw)}
    manifest["evidence_sha256"] = pilot.digest(pilot.encode(manifest["evidence"], compact=True))
    (output / plan.MANIFEST).write_bytes(pilot.encode(manifest))
    with pytest.raises(plan.PlanError, match="Original requirements changed"):
        plan.validate(output)


def test_later_head_does_not_rebind_provenance(tmp_path, monkeypatch):
    _, output, _ = prepare(tmp_path)
    monkeypatch.setattr(pilot, "source_commit", lambda: "f" * 40)
    assert plan.validate(output)["valid"]


def test_implementation_change_rejected(tmp_path, monkeypatch):
    _, output, _ = prepare(tmp_path)
    original = plan.planning.record
    def changed(path, limit=plan.MAX_JSON):
        value = original(path, limit)
        if path.name == "codex_plan.py":
            value["sha256"] = "0" * 64
        return value
    monkeypatch.setattr(plan.planning, "record", changed)
    with pytest.raises(plan.PlanError, match="implementation changed"):
        plan.validate(output)


@pytest.mark.parametrize("timestamp", ["not-a-date", "2026-11-08T12:00:00", None])
def test_invalid_manifest_timestamp(tmp_path, timestamp):
    _, output, manifest = prepare(tmp_path)
    manifest["created_at"] = timestamp
    (output / plan.MANIFEST).write_bytes(pilot.encode(manifest))
    with pytest.raises(plan.PlanError, match="timestamp"):
        plan.validate(output)


def test_all_report_sizes_checked_before_any_write(tmp_path, monkeypatch):
    _, output, manifest = prepare(tmp_path)
    write_result(output, result(manifest))
    monkeypatch.setattr(plan, "MAX_JSON", 100)
    with pytest.raises(plan.PlanError, match="Rendered strategy"):
        plan.finalize(output)
    assert not list(output.glob("*.md"))
    assert plan.validate(output)["phase"] == "prepared"


def test_escaping_and_cli_partial_exit(tmp_path):
    attack = '<img src="https://evil.test/x"> ![x](https://evil.test/y)\n# injected'
    _, output, manifest = prepare(tmp_path, requirements(business_context=attack))
    value = result(manifest)
    for name in ("action", "owner", "done_when"):
        value["roadmap"][0][name] = attack
    write_result(output, value)
    plan.finalize(output)
    for name in plan.REPORTS:
        rendered = (output / name).read_text()
        assert "<img" not in rendered and "![x]" not in rendered and "https://evil" not in rendered
    assert "&lt;img" in (output / plan.REPORTS[0]).read_text()
    other = tmp_path / "other"
    other.mkdir()
    _, output, _ = prepare(other)
    run = subprocess.run([sys.executable, str(Path(plan.__file__)), "finalize", "--output", str(output)], capture_output=True, text=True)
    assert run.returncode == 1 and json.loads(run.stdout)["phase"] == "partial"


def test_symlink_and_relative_output_rejected(tmp_path):
    source, output, _ = prepare(tmp_path)
    with pytest.raises(plan.PlanError):
        plan.validate(Path("relative"))
    alias = tmp_path / "alias"
    alias.symlink_to(source)
    with pytest.raises(plan.PlanError):
        plan.prepare(alias, tmp_path / "other")
    (output / "extra").symlink_to(source)
    with pytest.raises(plan.PlanError):
        plan.validate(output)
