"""Offline source-bound comparison validation and immutable lifecycle tests."""
import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import codex_comparison as comparison  # noqa: E402
import codex_pilot as pilot  # noqa: E402


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setattr("socket.getaddrinfo", lambda *a, **kw: pytest.fail("Unexpected DNS"))
    monkeypatch.setattr("requests.sessions.Session.request", lambda *a, **kw: pytest.fail("Unexpected HTTP"))


def capture(tmp_path, name, subject=None, raw=None, url=None, content_type=None):
    fixture = tmp_path / (name + ".html")
    fixture.write_bytes(raw if raw is not None else b"<html><title>Offer</title><p>First claim. Second claim.</p></html>")
    root = tmp_path / name
    pilot.capture(url or "https://example.com/" + name, root, fixture)
    if content_type:
        transport = pilot.json_read(root / "capture/transport.json")
        transport["headers"] = {"Content-Type": content_type}
        replace_capture_artifact(root, "capture/transport.json", pilot.encode(transport))
    return {"id": name, "subject_id": subject or name, "capture": str(root)}


def replace_capture_artifact(root, name, raw):
    (root / name).write_bytes(raw)
    manifest = pilot.json_read(root / pilot.MANIFEST)
    manifest["artifacts"][name] = {"sha256": pilot.digest(raw), "bytes": len(raw)}
    if name == "capture/page.html":
        manifest["capture"]["sha256"] = pilot.digest(raw)
    (root / pilot.MANIFEST).write_bytes(pilot.encode(manifest))


def requirements(sources=None, **updates):
    return {"audience": "Buyers", "decision_purpose": "Compare supported claims", "publisher_affiliation": "Independent",
            "subjects": [{"id": "one", "name": "One"}, {"id": "two", "name": "Two"}],
            "criteria": [{"id": "offer", "label": "Offer", "question": "What is offered?"}],
            "sources": sources if sources is not None else [{"id": "a", "subject_id": "one", "capture": "/private/tmp/a"},
                                   {"id": "b", "subject_id": "two", "capture": "/private/tmp/b"}], **updates}


def prepare(tmp_path, sources=None, **updates):
    if sources is None:
        sources = [capture(tmp_path, "one"), capture(tmp_path, "two")]
    path, output = tmp_path / "requirements.json", tmp_path / "comparison"
    path.write_bytes(pilot.encode(requirements(sources, **updates)))
    return path, output, comparison.prepare(path, output)


def evidence(source="one", excerpt="First claim.", locator="capture/page.html#p"):
    return {"source_id": source, "locator": locator, "excerpt": excerpt}


def write_role(output, value):
    (output / "findings/comparison.json").write_bytes(pilot.encode(value))


def role(output, manifest, status="complete"):
    value = {"role": "comparison", "requirements_sha256": manifest["evidence"]["requirements_sha256"],
             "evidence_sha256": manifest["evidence_sha256"], "status": status,
             "matrix": [{"subject_id": name, "criterion_id": "offer", "status": "source_claim",
                         "text": "The source claims an offer.", "evidence": [evidence(name)]} for name in ("one", "two")],
             "sections": {"differences": [{"basis": "source", "text": "Saved claims overlap.", "sources": ["one", "two"]}],
                          "outline": [{"basis": "proposal", "text": "Present both offers", "sources": []}],
                          "verification": [{"basis": "inference", "text": "Confirm current offers", "sources": ["one"]}],
                          "metadata": {"title": "One and Two compared", "description": "A source-bound comparison."}},
             "limitations": ["Saved HTML only."]}
    if status == "partial":
        value["matrix"] = []
        value["sections"] = {**{name: [] for name in comparison.SECTIONS}, "metadata": {"title": "", "description": ""}}
    write_role(output, value)
    return value


def test_complete_lifecycle_and_no_overwrite(tmp_path):
    source, output, manifest = prepare(tmp_path)
    assert comparison.validate(output)["role"] == "missing"
    value = role(output, manifest)
    assert comparison.validate(output)["complete"]
    assert comparison.finalize(output)["phase"] == "complete"
    assert comparison.validate(output)["valid"]
    assert set(manifest["evidence"]["artifacts"]) == {"input.json"}
    for operation in (lambda: comparison.prepare(source, output), lambda: comparison.finalize(output)):
        with pytest.raises(comparison.ComparisonError):
            operation()
    assert value["matrix"][0]["status"] == "source_claim"


@pytest.mark.parametrize("native", [False, True])
def test_partial_completion_and_sealing(tmp_path, native):
    _, output, manifest = prepare(tmp_path)
    if native:
        role(output, manifest, "partial")
    assert not comparison.finalize(output)["complete"]
    assert comparison.validate(output)["phase"] == "partial"
    role(output, manifest)
    with pytest.raises(comparison.ComparisonError):
        comparison.validate(output)


@pytest.mark.parametrize("updates", [
    {"audience": ""}, {"audience": "x" * 4001}, {"decision_purpose": []}, {"publisher_affiliation": None},
    {"constraints": ["x"] * 21}, {"constraints": ["x" * 2001]}, {"constraints": "x"}, {"extra": True},
    {"subjects": []}, {"subjects": [{"id": "one", "name": "One"}] * 3},
    {"criteria": []}, {"criteria": [{}] * 11}, {"sources": []}, {"sources": [{}] * 6},
])
def test_input_bounds_and_mapping(updates):
    with pytest.raises(comparison.ComparisonError):
        comparison.normalize(requirements(**updates))


@pytest.mark.parametrize("field", ["audience", "decision_purpose", "publisher_affiliation", "subjects", "criteria", "sources"])
def test_required_input_fields(field):
    value = requirements()
    del value[field]
    with pytest.raises(comparison.ComparisonError):
        comparison.normalize(value)


@pytest.mark.parametrize("change", ["sameid", "upperid", "samename", "normalized", "longname", "extra", "unknown", "unrepresented", "duplicate-source", "relative", "duplicate-path", "criterion-id", "criterion-label", "criterion-question", "criterion-extra"])
def test_nested_input_validation(change):
    value = requirements()
    if change == "sameid":
        value["subjects"][1]["id"] = "one"
    elif change == "upperid":
        value["subjects"][0]["id"] = "ONE"
    elif change == "samename":
        value["subjects"][1]["name"] = "oNE"
    elif change == "normalized":
        value["subjects"][1]["name"] = "  ＯＮＥ  "
    elif change == "longname":
        value["subjects"][0]["name"] = "x" * 201
    elif change == "extra":
        value["subjects"][0]["official"] = True
    elif change == "unknown":
        value["sources"][0]["subject_id"] = "unknown"
    elif change == "unrepresented":
        value["sources"][1]["subject_id"] = "one"
    elif change == "duplicate-source":
        value["sources"][1]["id"] = "a"
    elif change == "relative":
        value["sources"][0]["capture"] = "relative"
    elif change == "duplicate-path":
        value["sources"][1]["capture"] = "/private/tmp/a"
    elif change == "criterion-id":
        value["criteria"] *= 2
    elif change == "criterion-label":
        value["criteria"][0]["label"] = "x" * 201
    elif change == "criterion-question":
        value["criteria"][0]["question"] = "x" * 2001
    else:
        value["criteria"][0]["extra"] = True
    with pytest.raises(comparison.ComparisonError):
        comparison.normalize(value)


def test_max_unicode_input_and_default_constraints(tmp_path):
    sources = [capture(tmp_path, "one"), capture(tmp_path, "two")]
    _, output, _ = prepare(tmp_path, sources, audience="雪" * 4000, decision_purpose="雪" * 4000,
                           publisher_affiliation="雪" * 4000, constraints=["雪" * 2000] * 20,
                           criteria=[{"id": "criterion-" + str(i), "label": "雪" * 200, "question": "雪" * 2000} for i in range(10)])
    assert comparison.validate(output)["valid"]
    assert len((output / "input.json").read_bytes()) < comparison.MAX_INPUT
    assert comparison.normalize(requirements(sources))["constraints"] == []


def test_source_bounds_and_duplicate_urls(tmp_path):
    sources = [capture(tmp_path, "one"), capture(tmp_path, "two")]
    sources.extend(capture(tmp_path, name, "one") for name in ("three", "four", "five"))
    _, output, _ = prepare(tmp_path, sources)
    assert comparison.validate(output)["valid"]
    other = tmp_path / "other"
    other.mkdir()
    sources = [capture(other, "one"), capture(other, "two", url="https://example.com/one")]
    with pytest.raises(comparison.ComparisonError, match="final URLs"):
        prepare(other, sources)
    assert not (other / "comparison").exists()


@pytest.mark.parametrize("target", ["capture/page.html", "capture/transport.json", "capture/parsed.json", "pilot-manifest.json"])
def test_source_tampering(target, tmp_path):
    _, output, manifest = prepare(tmp_path)
    path = Path(manifest["evidence"]["sources"][0]["capture"]) / target
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(comparison.ComparisonError):
        comparison.validate(output)


def test_failed_capture_rejected_before_output(tmp_path):
    sources = [capture(tmp_path, "one"), capture(tmp_path, "two")]
    root = Path(sources[0]["capture"])
    transport = pilot.json_read(root / "capture/transport.json")
    transport.update(representation="raw-http", status_code=404, error="HTTP 404")
    replace_capture_artifact(root, "capture/transport.json", pilot.encode(transport))
    manifest = pilot.json_read(root / pilot.MANIFEST)
    manifest["capture"].update(representation="raw-http", complete=False)
    manifest["checks"]["transport"] = "failed"
    (root / pilot.MANIFEST).write_bytes(pilot.encode(manifest))
    with pytest.raises(comparison.ComparisonError, match="successful complete"):
        prepare(tmp_path, sources)
    assert not (tmp_path / "comparison").exists()


@pytest.mark.parametrize("state", ["source_claim", "not_stated", "not_comparable", "conflicting"])
def test_valid_states_preserved(tmp_path, state):
    _, output, manifest = prepare(tmp_path)
    value = role(output, manifest)
    for cell in value["matrix"]:
        cell["status"] = state
        if state == "not_stated":
            cell["evidence"] = []
        elif state == "conflicting":
            cell["evidence"].append(evidence(cell["subject_id"], "Second claim."))
    write_role(output, value)
    assert comparison.finalize(output)["complete"]
    rendered = (output / "COMPARISON-BRIEF.md").read_text(encoding="utf-8")
    assert comparison.escaped(state) in rendered


@pytest.mark.parametrize("change", ["extra", "identity", "status", "matrix-type", "too-many", "duplicate", "unknown-cell", "missing-cell", "cell-extra", "cell-status", "cell-text", "cell-evidence", "evidence-extra", "cross-subject", "unknown-source", "locator", "locator-long", "excerpt", "excerpt-long", "excerpt-empty", "evidence-duplicate", "claim-empty", "incomparable-empty", "not-stated-evidence", "conflicting-one", "conflicting-samequote", "sections-extra", "sections-missing", "section-empty", "section-long", "entry-extra", "entry-basis", "entry-text", "source-empty", "inference-empty", "refs-unknown", "refs-duplicate", "metadata-extra", "metadata-empty", "metadata-long", "metadata-type", "limitations"])
def test_invalid_native_contract(tmp_path, change):
    _, output, manifest = prepare(tmp_path)
    value = role(output, manifest)
    cell = value["matrix"][0]
    entry = value["sections"]["differences"][0]
    if change == "extra":
        value["winner"] = "one"
    elif change == "identity":
        value["evidence_sha256"] = "0" * 64
    elif change == "status":
        value["status"] = []
    elif change == "matrix-type":
        value["matrix"] = {}
    elif change == "too-many":
        value["matrix"] *= 11
    elif change == "duplicate":
        value["matrix"].append(copy.deepcopy(cell))
    elif change == "unknown-cell":
        cell["criterion_id"] = "unknown"
    elif change == "missing-cell":
        value["matrix"].pop()
    elif change == "cell-extra":
        cell["score"] = 10
    elif change == "cell-status":
        cell["status"] = "winner"
    elif change == "cell-text":
        cell["text"] = "x" * 4001
    elif change == "cell-evidence":
        cell["evidence"] *= 11
    elif change == "evidence-extra":
        cell["evidence"][0]["extra"] = True
    elif change == "cross-subject":
        cell["evidence"][0]["source_id"] = "two"
    elif change == "unknown-source":
        cell["evidence"][0]["source_id"] = "unknown"
    elif change == "locator":
        cell["evidence"][0]["locator"] = "https://example.com"
    elif change == "locator-long":
        cell["evidence"][0]["locator"] += "x" * 500
    elif change == "excerpt":
        cell["evidence"][0]["excerpt"] = "Not in saved HTML"
    elif change == "excerpt-long":
        cell["evidence"][0]["excerpt"] = "x" * 1001
    elif change == "excerpt-empty":
        cell["evidence"][0]["excerpt"] = ""
    elif change == "evidence-duplicate":
        cell["evidence"] *= 2
    elif change in {"claim-empty", "incomparable-empty"}:
        cell["evidence"] = []
        cell["status"] = "source_claim" if change == "claim-empty" else "not_comparable"
    elif change == "not-stated-evidence":
        cell["status"] = "not_stated"
    elif change in {"conflicting-one", "conflicting-samequote"}:
        cell["status"] = "conflicting"
        if change == "conflicting-samequote":
            cell["evidence"].append(evidence(locator="capture/page.html#other"))
    elif change == "sections-extra":
        value["sections"]["schema"] = []
    elif change == "sections-missing":
        del value["sections"]["outline"]
    elif change == "section-empty":
        value["sections"]["outline"] = []
    elif change == "section-long":
        value["sections"]["outline"] *= 31
    elif change == "entry-extra":
        entry["extra"] = True
    elif change == "entry-basis":
        entry["basis"] = "user"
    elif change == "entry-text":
        entry["text"] = "x" * 4001
    elif change in {"source-empty", "inference-empty"}:
        entry["sources"] = []
        entry["basis"] = "source" if change == "source-empty" else "inference"
    elif change == "refs-unknown":
        entry["sources"] = ["unknown"]
    elif change == "refs-duplicate":
        entry["sources"] = ["one", "one"]
    elif change == "metadata-extra":
        value["sections"]["metadata"]["winner"] = "one"
    elif change == "metadata-empty":
        value["sections"]["metadata"]["title"] = " "
    elif change == "metadata-long":
        value["sections"]["metadata"]["title"] = "x" * 4001
    elif change == "metadata-type":
        value["sections"]["metadata"]["title"] = []
    elif change == "limitations":
        value["limitations"] = ["x"] * 101
    write_role(output, value)
    with pytest.raises(comparison.ComparisonError):
        comparison.validate(output)


def test_partial_subset_and_exact_excerpts_still_required(tmp_path):
    _, output, manifest = prepare(tmp_path)
    value = role(output, manifest)
    value["status"] = "partial"
    value["matrix"].pop()
    write_role(output, value)
    assert comparison.validate(output)["valid"]
    value["matrix"][0]["evidence"][0]["excerpt"] = "Fabrication"
    write_role(output, value)
    with pytest.raises(comparison.ComparisonError, match="exact decoded excerpt"):
        comparison.validate(output)


@pytest.mark.parametrize("encoding,content_type,html", [
    ("utf-8-sig", "text/html; charset=ascii", "<p>雪と海</p>"),
    ("utf-16", "text/html; charset=ascii", "<p>雪と海</p>"),
    ("windows-1252", "text/html; charset=windows-1252", "<p>Café £50</p>"),
    ("windows-1252", None, '<meta charset="windows-1252"><p>Café £50</p>'),
])
def test_encoding_matches_saved_capture(tmp_path, encoding, content_type, html):
    sources = [capture(tmp_path, "one", raw=html.encode(encoding), content_type=content_type), capture(tmp_path, "two")]
    _, output, manifest = prepare(tmp_path, sources)
    value = role(output, manifest)
    value["matrix"][0]["evidence"][0]["excerpt"] = "雪と海" if "雪" in html else "Café £50"
    write_role(output, value)
    assert comparison.validate(output)["complete"]


def test_reuse_across_criteria_and_multiple_sources_per_subject(tmp_path):
    sources = [capture(tmp_path, "one"), capture(tmp_path, "two"), capture(tmp_path, "three", "one")]
    _, output, manifest = prepare(tmp_path, sources, criteria=[{"id": name, "label": name, "question": name} for name in ("offer", "support")])
    value = role(output, manifest)
    value["matrix"].extend({**copy.deepcopy(cell), "criterion_id": "support"} for cell in list(value["matrix"]))
    value["matrix"][0]["status"] = "conflicting"
    value["matrix"][0]["evidence"].append(evidence("three"))
    write_role(output, value)
    assert comparison.validate(output)["complete"]


@pytest.mark.parametrize("target", ["requirements.json", "comparison/input.json", "comparison/COMPARISON-BRIEF.md", "comparison/findings/comparison.json"])
def test_input_and_finalized_artifact_tampering(tmp_path, target):
    _, output, manifest = prepare(tmp_path)
    role(output, manifest)
    comparison.finalize(output)
    path = tmp_path / target
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(comparison.ComparisonError):
        comparison.validate(output)


@pytest.mark.parametrize("filename", ["codex_comparison.py", "codex_planning.py"])
def test_implementation_provenance(tmp_path, monkeypatch, filename):
    _, output, _ = prepare(tmp_path)
    original = comparison.planning.record
    def changed(path, limit=comparison.MAX_JSON):
        result = original(path, limit)
        if path.name == filename:
            result["sha256"] = "0" * 64
        return result
    monkeypatch.setattr(comparison.planning, "record", changed)
    with pytest.raises(comparison.ComparisonError, match="implementation changed"):
        comparison.validate(output)


def test_later_head_keeps_saved_identity(tmp_path, monkeypatch):
    _, output, _ = prepare(tmp_path)
    monkeypatch.setattr(pilot, "source_commit", lambda: "f" * 40)
    assert comparison.validate(output)["valid"]


def test_escaping_and_source_dates(tmp_path):
    attack = '<script>x</script> | ![x](https://evil.test)\n# heading'
    sources = [capture(tmp_path, "one", raw=("<p>" + attack + "</p>").encode()), capture(tmp_path, "two")]
    subjects = [{"id": "one", "name": attack}, {"id": "two", "name": "Two"}]
    _, output, manifest = prepare(tmp_path, sources, subjects=subjects, publisher_affiliation=attack)
    value = role(output, manifest)
    value["matrix"][0]["text"] = attack
    value["matrix"][0]["evidence"] = [evidence(excerpt=attack, locator="capture/page.html#" + attack)]
    value["sections"]["outline"][0]["text"] = attack
    value["sections"]["metadata"]["title"] = attack
    write_role(output, value)
    comparison.finalize(output)
    rendered = (output / "COMPARISON-BRIEF.md").read_text(encoding="utf-8")
    assert '<script>' not in rendered and '![x]' not in rendered and 'https://evil.test' not in rendered
    assert comparison.escaped(attack) in rendered
    assert 'Captured at is ' in rendered and 'Retrieved at is unavailable.' in rendered
    assert '## Evidence ledger' in rendered


def test_symlinks_strict_json_and_input_bound(tmp_path):
    source, output, _ = prepare(tmp_path)
    alias = tmp_path / "alias"
    alias.symlink_to(source)
    with pytest.raises(comparison.ComparisonError):
        comparison.prepare(alias, tmp_path / "other")
    (output / "unexpected").symlink_to(source)
    with pytest.raises(comparison.ComparisonError):
        comparison.validate(output)
    for raw in (b'{"x":1,"x":2}', b'{"x":NaN}', b'\xff', b'[' * 34 + b'0' + b']' * 34):
        with pytest.raises(comparison.ComparisonError):
            comparison.decode(raw)
    large = tmp_path / "large.json"
    large.write_bytes(b" " * (comparison.MAX_INPUT + 1))
    with pytest.raises(comparison.ComparisonError):
        comparison.prepare(large, tmp_path / "other")


def test_cli_prepare_validate_and_finalize(tmp_path):
    sources = [capture(tmp_path, "one"), capture(tmp_path, "two")]
    source, output = tmp_path / "input.json", tmp_path / "comparison"
    source.write_bytes(pilot.encode(requirements(sources)))
    def run(*args):
        return subprocess.run([sys.executable, comparison.__file__, *args], capture_output=True, text=True)
    result = run("prepare", "--input", str(source), "--output", str(output))
    assert result.returncode == 0
    manifest = json.loads(result.stdout)
    assert run("validate", "--output", str(output)).returncode == 0
    role(output, manifest)
    assert run("finalize", "--output", str(output)).returncode == 0
    assert run("finalize", "--output", str(output)).returncode == 1
    assert run("--help").returncode == 0


def test_rehashed_normalized_input_cannot_replace_original(tmp_path):
    _, output, manifest = prepare(tmp_path)
    value = pilot.json_read(output / "input.json")
    value["audience"] = "Replacement audience"
    raw = pilot.encode(value)
    (output / "input.json").write_bytes(raw)
    manifest["evidence"]["requirements_sha256"] = pilot.digest(raw)
    manifest["evidence"]["artifacts"]["input.json"] = {"sha256": pilot.digest(raw), "bytes": len(raw)}
    manifest["evidence_sha256"] = pilot.digest(pilot.encode(manifest["evidence"], compact=True))
    (output / comparison.MANIFEST).write_bytes(pilot.encode(manifest))
    with pytest.raises(comparison.ComparisonError, match="Original requirements changed"):
        comparison.validate(output)


def test_rehashed_source_cannot_replace_bound_capture(tmp_path):
    _, output, manifest = prepare(tmp_path)
    source = Path(manifest["evidence"]["sources"][0]["capture"])
    replace_capture_artifact(source, "capture/page.html", b"<p>Replaced source</p>")
    with pytest.raises(comparison.ComparisonError, match="source registry"):
        comparison.validate(output)


def test_full_grid_boundary_and_same_page_conflicts(tmp_path):
    criteria = [{"id": "criterion-" + str(i), "label": "Offer", "question": "What is claimed?"} for i in range(10)]
    _, output, manifest = prepare(tmp_path, criteria=criteria)
    value = role(output, manifest)
    value["matrix"] = [{**copy.deepcopy(cell), "criterion_id": criterion["id"]}
                       for criterion in criteria for cell in value["matrix"]]
    assert len(value["matrix"]) == 20
    for cell in value["matrix"]:
        cell["status"] = "conflicting"
        cell["evidence"].append(evidence(cell["subject_id"], "Second claim."))
    write_role(output, value)
    assert comparison.finalize(output)["complete"]


def test_partial_cli_exit_and_preexisting_report(tmp_path):
    _, output, _ = prepare(tmp_path)
    (output / "COMPARISON-BRIEF.md").write_text("Preserve this report", encoding="utf-8")
    with pytest.raises(comparison.ComparisonError, match="refusing overwrite"):
        comparison.finalize(output)
    assert (output / "COMPARISON-BRIEF.md").read_text(encoding="utf-8") == "Preserve this report"
    (output / "COMPARISON-BRIEF.md").unlink()
    result = subprocess.run([sys.executable, comparison.__file__, "finalize", "--output", str(output)],
                            capture_output=True, text=True)
    assert result.returncode == 1
    assert json.loads(result.stdout)["phase"] == "partial"


def test_evidence_byte_exactness_and_whitespace_substring(tmp_path):
    sources = [capture(tmp_path, "one", raw="<p>Café \n claim.</p>".encode()), capture(tmp_path, "two")]
    _, output, manifest = prepare(tmp_path, sources)
    value = role(output, manifest)
    value["matrix"][0]["evidence"][0]["excerpt"] = " \n "
    write_role(output, value)
    assert comparison.validate(output)["complete"]
    value["matrix"][0]["evidence"][0]["excerpt"] = "Cafe\u0301"
    write_role(output, value)
    with pytest.raises(comparison.ComparisonError, match="exact decoded excerpt"):
        comparison.validate(output)


def test_repeated_quote_with_different_locator_rejected(tmp_path):
    _, output, manifest = prepare(tmp_path)
    value = role(output, manifest)
    value["matrix"][0]["evidence"].append(evidence(locator="capture/page.html#other"))
    write_role(output, value)
    with pytest.raises(comparison.ComparisonError, match="Duplicate evidence source and excerpt"):
        comparison.validate(output)


def test_side_by_side_matrix_preserves_pending_cells(tmp_path):
    _, output, manifest = prepare(tmp_path)
    value = role(output, manifest)
    value["status"] = "partial"
    value["matrix"].pop()
    write_role(output, value)
    comparison.finalize(output)
    rendered = (output / "COMPARISON-BRIEF.md").read_text(encoding="utf-8")
    assert "| Criterion | One | Two |" in rendered
    assert "| Offer | source&#95;claim. The source claims an offer&#46; | pending. Native review is pending&#46; |" in rendered
