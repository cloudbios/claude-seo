"""Offline saved report validation, fraction semantics and immutable evidence."""
import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import codex_agentic as agentic  # noqa: E402
import codex_pilot as pilot  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures/lighthouse_agentic_13_5_psi.json"


def report():
    return json.loads(FIXTURE.read_bytes())


def analyze(value):
    return agentic.analyze(pilot.encode(value))


def capture(tmp_path, value=None):
    source = tmp_path / "input.json"
    source.write_bytes(pilot.encode(report() if value is None else value))
    output = tmp_path / "output"
    return source, output, agentic.capture(source, output)


def role(output, manifest, status="complete"):
    value = {"role": "agentic", "capture_sha256": manifest["evidence"]["source"]["sha256"],
             "evidence_sha256": manifest["evidence_sha256"], "status": status,
             "findings": ["Saved report reviewed."], "limitations": ["Offline evidence only."]}
    (output / "findings/agentic.json").write_bytes(pilot.encode(value))
    return value


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setattr("socket.getaddrinfo", lambda *a, **kw: pytest.fail("Unexpected DNS request"))
    monkeypatch.setattr("requests.sessions.Session.request", lambda *a, **kw: pytest.fail("Unexpected HTTP request"))


@pytest.mark.parametrize("wrapped", [False, True])
def test_fixture_fraction_raw_and_psi(wrapped):
    value = report()
    result = analyze({"lighthouseResult": value} if wrapped else value)
    assert result["status"] == "complete"
    assert result["fraction"]["display"] == "4/4"
    assert result["fraction"]["informative"] == 2
    assert result["metadata"]["formFactor"] == "mobile"
    assert result["metadata"]["fetchTime"] == value["fetchTime"]
    assert result["audits"][0]["audit_pointer"].startswith("/lighthouseResult/" if wrapped else "/audits/")
    assert "details" not in result["audits"][1]


@pytest.mark.parametrize("version", ["13.4.0", "13.5.1", "99.0.0", ""])
def test_unverified_version_has_no_fraction(version):
    value = report()
    value["lighthouseVersion"] = version
    result = analyze(value)
    assert result["status"] == "partial"
    assert result["fraction"]["available"] is False
    assert len(result["audits"]) == 7
    assert all(row["status"] == "unverified" for row in result["audits"])


@pytest.mark.parametrize("field", ["categories", "audits", "lighthouseVersion", "fetchTime", "requestedUrl", "configSettings"])
def test_missing_coverage_truthful_partial(field):
    value = report()
    del value[field]
    assert analyze(value)["status"] == "partial"


@pytest.mark.parametrize("change", ["missing_category", "missing_refs", "empty_refs", "missing_audit", "empty_audit", "missing_mode", "missing_score", "unknown_mode", "wrong_display"])
def test_incomplete_fraction_unavailable(change):
    value = report()
    category = value["categories"][agentic.CATEGORY]
    audit = value["audits"]["agent-accessibility-tree"]
    if change == "missing_category":
        value["categories"] = {}
    elif change == "missing_refs":
        del category["auditRefs"]
    elif change == "empty_refs":
        category["auditRefs"] = []
    elif change == "missing_audit":
        del value["audits"]["agent-accessibility-tree"]
    elif change == "empty_audit":
        value["audits"]["agent-accessibility-tree"] = {}
    elif change == "missing_mode":
        del audit["scoreDisplayMode"]
    elif change == "missing_score":
        del audit["score"]
    elif change == "unknown_mode":
        audit["scoreDisplayMode"] = "future-mode"
    else:
        category["categoryScoreDisplayMode"] = "numeric"
    result = analyze(value)
    assert result["status"] == "partial"
    assert result["fraction"]["available"] is False


def test_runtime_error_and_warnings_preserved():
    value = report()
    value["runtimeError"] = {"code": "NO_FCP", "message": "Something failed"}
    value["runWarnings"] = ["Reported warning"]
    result = analyze(value)
    assert result["status"] == "partial" and not result["fraction"]["available"]
    assert result["runtimeError"] == value["runtimeError"]
    assert result["runWarnings"] == value["runWarnings"]


def test_scores_weight_zero_threshold_and_exclusions():
    value = report()
    refs = value["categories"][agentic.CATEGORY]["auditRefs"]
    refs[0]["weight"] = 0
    value["audits"]["agent-accessibility-tree"]["score"] = .8999
    value["audits"]["webmcp-schema-validity"]["score"] = .9
    result = analyze(value)
    assert result["fraction"]["display"] == "3/4"
    assert result["audits"][0]["status"] == "fail"
    for index, ref in enumerate(refs):
        audit = value["audits"][ref["id"]]
        audit["scoreDisplayMode"] = ["manual", "notApplicable", "informative"][index % 3]
        audit["score"] = None
    result = analyze(value)
    assert result["fraction"]["display"] == "0/0"
    assert result["fraction"]["counted"] == 0
    refs[0]["group"] = "hidden"
    value["audits"][refs[0]["id"]].update(scoreDisplayMode="binary", score=None)
    assert analyze(value)["audits"][0]["status"] == "hidden"
    assert analyze(value)["fraction"]["display"] == "0/0"


def test_error_audit_is_counted_failure_with_partial_coverage():
    value = report()
    audit = value["audits"]["agent-accessibility-tree"]
    audit.update(score=None, scoreDisplayMode="error", errorMessage="Failed check")
    result = analyze(value)
    assert result["status"] == "partial"
    assert result["fraction"]["display"] == "3/4"
    assert result["audits"][0]["errorMessage"] == "Failed check"


@pytest.mark.parametrize("raw", [b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":Infinity}', b'{"x":1e999}', b'null', b'[]', b'{', b'\xff', b'{"lighthouseResult":null}'])
def test_invalid_json_rejected(raw):
    with pytest.raises(agentic.AgenticError):
        agentic.analyze(raw)


@pytest.mark.parametrize("score", [-1, 1.01, True, False, "1", [], {}])
def test_invalid_score_types_rejected(score):
    value = report()
    value["audits"]["agent-accessibility-tree"]["score"] = score
    with pytest.raises(agentic.AgenticError):
        analyze(value)
    value = report()
    value["categories"][agentic.CATEGORY]["score"] = score
    with pytest.raises(agentic.AgenticError):
        analyze(value)


@pytest.mark.parametrize("field,bad", [("categories", []), ("audits", []), ("configSettings", None),
    ("runWarnings", "x"), ("runtimeError", True), ("requestedUrl", 3), ("fetchTime", "yesterday")])
def test_malformed_report_fields_rejected(field, bad):
    value = report()
    value[field] = bad
    with pytest.raises(agentic.AgenticError):
        analyze(value)


@pytest.mark.parametrize("field,bad", [("auditRefs", {}), ("auditRefs", [None]), ("auditRefs", [{"id":True}]), ("score", True)])
def test_malformed_category_rejected(field, bad):
    value = report()
    value["categories"][agentic.CATEGORY][field] = bad
    with pytest.raises(agentic.AgenticError):
        analyze(value)


@pytest.mark.parametrize("field,bad", [("id", "other-id"), ("title", []), ("warnings", [True]), ("scoreDisplayMode", None)])
def test_malformed_audit_rejected(field, bad):
    value = report()
    value["audits"]["agent-accessibility-tree"][field] = bad
    with pytest.raises(agentic.AgenticError):
        analyze(value)


def test_duplicate_references_rejected():
    value = report()
    refs = value["categories"][agentic.CATEGORY]["auditRefs"]
    refs.append(copy.deepcopy(refs[0]))
    with pytest.raises(agentic.AgenticError, match="Duplicate"):
        analyze(value)


@pytest.mark.parametrize("weight", [True, -1, "1", 1e100])
def test_invalid_weight_rejected(weight):
    value = report()
    value["categories"][agentic.CATEGORY]["auditRefs"][0]["weight"] = weight
    with pytest.raises(agentic.AgenticError):
        analyze(value)


def test_input_depth_node_size_and_reference_bounds(monkeypatch):
    with pytest.raises(agentic.AgenticError, match="nesting"):
        agentic.decode(b'[' * 65 + b'0' + b']' * 65)
    monkeypatch.setattr(agentic, "MAX_NODES", 5)
    with pytest.raises(agentic.AgenticError, match="node"):
        agentic.decode(b'[1,2,3,4,5]')
    monkeypatch.setattr(agentic, "MAX_NODES", 200000)
    monkeypatch.setattr(agentic, "MAX_JSON", 20)
    with pytest.raises(agentic.AgenticError, match="10 MiB"):
        agentic.decode(b' ' * 21)
    monkeypatch.setattr(agentic, "MAX_JSON", 10 * 1024 * 1024)
    monkeypatch.setattr(agentic, "MAX_REFS", 2)
    with pytest.raises(agentic.AgenticError, match="bounded list"):
        analyze(report())


def test_source_bytes_and_complete_lifecycle(tmp_path):
    source, output, manifest = capture(tmp_path)
    original = source.read_bytes()
    assert (output / "source.json").read_bytes() == original
    assert not agentic.validate(output)["complete"]
    role(output, manifest)
    assert agentic.finalize(output)["complete"]
    assert agentic.validate(output)["phase"] == "complete"
    assert source.read_bytes() == original
    with pytest.raises(agentic.AgenticError, match="already finalized"):
        agentic.finalize(output)


@pytest.mark.parametrize("with_role", [True, False])
def test_partial_finalization(tmp_path, with_role):
    value = report()
    value["lighthouseVersion"] = "99"
    _, output, manifest = capture(tmp_path, value)
    if with_role:
        role(output, manifest)
    assert agentic.finalize(output)["phase"] == "partial"


@pytest.mark.parametrize("field,bad", [("role", "technical"), ("status", "done"), ("capture_sha256", "wrong"),
    ("evidence_sha256", "wrong"), ("findings", "not-list"), ("limitations", [False]), ("findings", ["x" * 10001])])
def test_role_contract_rejects_bad_identity_and_shape(tmp_path, field, bad):
    _, output, manifest = capture(tmp_path)
    value = role(output, manifest)
    value[field] = bad
    (output / "findings/agentic.json").write_bytes(pilot.encode(value))
    with pytest.raises(agentic.AgenticError):
        agentic.validate(output)


@pytest.mark.parametrize("target", ["source", "source.json", "analysis.json", "manifest", "role", "report"])
def test_tamper_rejected(tmp_path, target):
    source, output, manifest = capture(tmp_path)
    value = role(output, manifest)
    if target in {"role", "report"}:
        agentic.finalize(output)
    if target == "source":
        source.write_bytes(b'{}')
    elif target in {"source.json", "analysis.json", "report"}:
        (output / ("REPORT.md" if target == "report" else target)).write_bytes(b'{}')
    elif target == "manifest":
        manifest["evidence"]["network"] = "fetch"
        (output / agentic.MANIFEST).write_bytes(pilot.encode(manifest))
    else:
        value["findings"] = ["Changed."]
        (output / "findings/agentic.json").write_bytes(pilot.encode(value))
    with pytest.raises(agentic.AgenticError):
        agentic.validate(output)


def test_rehashed_false_analysis_rejected(tmp_path):
    _, output, manifest = capture(tmp_path)
    analysis = json.loads((output / "analysis.json").read_bytes())
    analysis["fraction"]["display"] = "7/7"
    (output / "analysis.json").write_bytes(pilot.encode(analysis))
    manifest["evidence"]["artifacts"]["analysis.json"] = agentic.file_record(output / "analysis.json")
    manifest["evidence_sha256"] = pilot.digest(pilot.encode(manifest["evidence"], compact=True))
    (output / agentic.MANIFEST).write_bytes(pilot.encode(manifest))
    with pytest.raises(agentic.AgenticError, match="disagrees"):
        agentic.validate(output)


def test_implementation_provenance_checked(tmp_path, monkeypatch):
    _, output, _ = capture(tmp_path)
    original = agentic.file_record
    def changed(path):
        result = original(path)
        if str(path).endswith("scripts/lighthouse_agentic.py"):
            result["sha256"] = "0" * 64
        return result
    monkeypatch.setattr(agentic, "file_record", changed)
    with pytest.raises(agentic.AgenticError, match="implementation provenance"):
        agentic.validate(output)


def test_existing_output_and_symlink_paths_rejected(tmp_path):
    source, output, _ = capture(tmp_path)
    with pytest.raises(agentic.AgenticError, match="fresh"):
        agentic.capture(source, output)
    link = tmp_path / "link.json"
    link.symlink_to(source)
    with pytest.raises(agentic.AgenticError, match="Symlink"):
        agentic.capture(link, tmp_path / "new")
    with pytest.raises(agentic.AgenticError, match="absolute"):
        agentic.capture(Path("input.json"), tmp_path / "new")


def test_untrusted_text_display_does_not_create_markup(tmp_path):
    value = report()
    value["requestedUrl"] = '<script>alert(1)</script> [click](https://bad.test)\n# injected'
    _, output, manifest = capture(tmp_path, value)
    finding = role(output, manifest)
    finding["findings"] = ["<img src=x>\n# pretend heading [click](https://bad.test)"]
    (output / "findings/agentic.json").write_bytes(pilot.encode(finding))
    agentic.finalize(output)
    report_text = (output / "REPORT.md").read_text()
    assert "<script>" not in report_text and "<img" not in report_text
    assert "\n# pretend heading" not in report_text and "[click]" not in report_text


def test_import_has_no_provider_or_http_imports():
    program = ("import sys; sys.path.insert(0, 'scripts'); import codex_agentic; "
               "assert 'requests' not in sys.modules; assert 'google_auth' not in sys.modules")
    result = subprocess.run([sys.executable, "-I", "-B", "-c", program], cwd=FIXTURE.parents[2], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("mode", ["binary", "numeric"])
def test_null_ordinary_score_is_incomplete(mode):
    value = report()
    value["audits"]["agent-accessibility-tree"].update(score=None, scoreDisplayMode=mode)
    result = analyze(value)
    assert result["status"] == "partial"
    assert result["audits"][0]["status"] == "unverified"
    assert not result["fraction"]["available"]


def test_rehashed_analysis_cannot_change_boolean_types(tmp_path):
    _, output, manifest = capture(tmp_path)
    analysis = json.loads((output / "analysis.json").read_bytes())
    analysis["fraction"]["available"] = 1
    (output / "analysis.json").write_bytes(pilot.encode(analysis))
    manifest["evidence"]["artifacts"]["analysis.json"] = agentic.file_record(output / "analysis.json")
    manifest["evidence_sha256"] = pilot.digest(pilot.encode(manifest["evidence"], compact=True))
    (output / agentic.MANIFEST).write_bytes(pilot.encode(manifest))
    with pytest.raises(agentic.AgenticError, match="disagrees"):
        agentic.validate(output)


def test_audit_and_category_bounds(monkeypatch):
    monkeypatch.setattr(agentic, "MAX_AUDITS", 2)
    with pytest.raises(agentic.AgenticError, match="Too many audits"):
        analyze(report())
    monkeypatch.setattr(agentic, "MAX_AUDITS", 5000)
    value = report()
    value["categories"] = {str(index): {} for index in range(101)}
    with pytest.raises(agentic.AgenticError, match="Too many categories"):
        analyze(value)


def test_bounded_row_text_retains_exact_source(tmp_path):
    value = report()
    value["audits"]["agent-accessibility-tree"]["explanation"] = "x" * 5000
    source, output, _ = capture(tmp_path, value)
    analysis = json.loads((output / "analysis.json").read_bytes())
    assert len(analysis["audits"][0]["explanation"]) == agentic.MAX_TEXT
    assert analysis["audits"][0]["summary_text_truncated"] is True
    assert (output / "source.json").read_bytes() == source.read_bytes()
    assert len(json.loads(source.read_bytes())["audits"]["agent-accessibility-tree"]["explanation"]) == 5000


@pytest.mark.parametrize("missing", ["score", "scoreDisplayMode"])
def test_hidden_audit_excluded_despite_omitted_scoring_field(missing):
    value = report()
    value["categories"][agentic.CATEGORY]["auditRefs"][0]["group"] = "hidden"
    del value["audits"]["agent-accessibility-tree"][missing]
    result = analyze(value)
    assert result["status"] == "complete"
    assert result["fraction"]["display"] == "3/3"
    assert result["audits"][0]["status"] == "hidden"


@pytest.mark.parametrize("mode", ["manual", "notApplicable", "informative"])
def test_excluded_display_modes_do_not_require_a_score(mode):
    value = report()
    audit = value["audits"]["agent-accessibility-tree"]
    audit["scoreDisplayMode"] = mode
    del audit["score"]
    result = analyze(value)
    assert result["status"] == "complete"
    assert result["fraction"]["display"] == "3/3"
