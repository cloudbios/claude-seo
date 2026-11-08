"""Offline content-brief contracts: bounded inputs and immutable source evidence."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import codex_brief as brief  # noqa: E402
import codex_pilot as pilot  # noqa: E402


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setattr("socket.getaddrinfo", lambda *a, **kw: pytest.fail("Unexpected DNS"))
    monkeypatch.setattr("requests.sessions.Session.request", lambda *a, **kw: pytest.fail("Unexpected HTTP"))


def requirements(**updates):
    return {"mode": "new", "topic": "Repair questions", "audience": "Homeowners",
            "business_context": "A repair business", "business_goal": "Explain repair options", "sources": [], **updates}


def prepare(tmp_path, value=None):
    path = tmp_path / "requirements.json"
    path.write_bytes(pilot.encode(requirements() if value is None else value))
    output = tmp_path / "brief"
    return path, output, brief.prepare(path, output)


def capture(tmp_path, name="target"):
    fixture = tmp_path / (name + ".html")
    fixture.write_text('<html><title>Repairs</title><body><h1>Repair service</h1></body></html>')
    root = tmp_path / name
    pilot.capture("https://example.com/" + name, root, fixture)
    return {"id": name, "kind": "target", "capture": str(root)}


def role(output, manifest, status="complete", target=None):
    sections = {name: [{"basis": "proposal", "text": "Editorial proposal to verify.", "sources": []}]
                if status == "complete" else [] for name in brief.SECTIONS}
    if target:
        sections["source_assessment"] = [{"basis": "source", "text": "capture/parsed.json title: Repairs",
                                          "sources": [target]}]
    value = {"role": "content-brief", "requirements_sha256": manifest["evidence"]["requirements_sha256"],
             "evidence_sha256": manifest["evidence_sha256"], "status": status,
             "sections": sections, "limitations": ["Author facts require verification."]}
    write_role(output, value)
    return value


def write_role(output, value):
    (output / "findings/content-brief.json").write_bytes(pilot.encode(value))


def test_input_only_complete_brief(tmp_path):
    _, output, manifest = prepare(tmp_path)
    assert manifest["evidence"]["representation"] == "input-only"
    assert brief.validate(output)["role"] == "missing"
    assert not brief.validate(output)["complete"]
    role(output, manifest)
    assert brief.finalize(output)["complete"]
    report = (output / "BRIEF.md").read_text()
    assert "Input-only planning" in report
    assert "not independently verified" in report
    for name in brief.SECTIONS:
        assert "## " + name.replace("_", " ").capitalize() in report
    with pytest.raises(brief.BriefError, match="already finalized"):
        brief.finalize(output)


def test_improve_records_target_hashes(tmp_path):
    source = capture(tmp_path)
    _, output, manifest = prepare(tmp_path, requirements(mode="improve", sources=[source]))
    saved = manifest["evidence"]["sources"][0]
    assert saved["capture_sha256"] == pilot.json_read(Path(source["capture"]) / pilot.MANIFEST)["capture"]["sha256"]
    assert saved["pilot_manifest_sha256"] == brief.record(Path(source["capture"]) / pilot.MANIFEST)["sha256"]
    assert saved["requested_url"] == saved["final_url"] == "https://example.com/target"
    assert saved["representation"] == "fixture"
    role(output, manifest, target="target")
    assert brief.finalize(output)["complete"]


def test_new_with_reference(tmp_path):
    source = {**capture(tmp_path), "kind": "reference"}
    _, output, manifest = prepare(tmp_path, requirements(sources=[source]))
    assert manifest["evidence"]["representation"] == "saved-source-html"
    assert brief.validate(output)["valid"]


@pytest.mark.parametrize("updates", [
    {"mode": "bad"}, {"mode": []}, {"topic": " "}, {"topic": "a" * 4001},
    {"audience": None}, {"business_context": False}, {"business_goal": 1},
    {"page_type": "a" * 101}, {"page_type": ""}, {"constraints": ["a"] * 31},
    {"constraints": [""]}, {"constraints": ["a" * 2001]}, {"constraints": {}},
    {"extra": True}, {"sources": {}}, {"sources": [{}] * 6},
    {"sources": [{"id": "x", "kind": "reference", "capture": "relative"}]},
    {"sources": [{"id": "Bad", "kind": "reference", "capture": "/tmp/x"}]},
    {"sources": [{"id": "x", "kind": "unknown", "capture": "/tmp/x"}]},
    {"sources": [{"id": "x", "kind": "reference", "capture": "/tmp/x", "extra": 1}]},
    {"mode": "improve"},
])
def test_invalid_requirements(updates):
    with pytest.raises(brief.BriefError):
        brief.normalize(requirements(**updates))


@pytest.mark.parametrize("field", ["mode", "topic", "audience", "business_context", "business_goal", "sources"])
def test_required_fields(field):
    value = requirements()
    del value[field]
    with pytest.raises(brief.BriefError):
        brief.normalize(value)


@pytest.mark.parametrize("raw", [b'{"mode": "new", "mode": "improve"}', b'{"a":NaN}', b'{"a":Infinity}',
                                  b'{"a":1e9999}', b'\xff', b'[' * 34 + b'0' + b']' * 34,
                                  b'[' * 2000 + b'0' + b']' * 2000])
def test_strict_json(raw):
    with pytest.raises(brief.BriefError):
        brief.decode(raw)


def test_input_size_bound(tmp_path):
    path = tmp_path / "huge.json"
    path.write_bytes(b" " * (brief.MAX_INPUT + 1))
    with pytest.raises(brief.BriefError):
        brief.prepare(path, tmp_path / "brief")
    assert not (tmp_path / "brief").exists()


def test_target_and_duplicates(tmp_path):
    one = capture(tmp_path, "one")
    two = capture(tmp_path, "two")
    with pytest.raises(brief.BriefError):
        brief.normalize(requirements(sources=[one]))
    with pytest.raises(brief.BriefError):
        brief.normalize(requirements(mode="improve", sources=[one, two]))
    with pytest.raises(brief.BriefError):
        brief.normalize(requirements(sources=[{**one, "kind": "reference"}, {**two, "id": "one", "kind": "reference"}]))
    with pytest.raises(brief.BriefError):
        brief.normalize(requirements(sources=[{**one, "kind": "reference"}, {**one, "id": "other", "kind": "reference"}]))
    # Distinct captures of the same URL still count as one evidence identity.
    fixture = tmp_path / "one.html"
    root = tmp_path / "same-url"
    pilot.capture("https://example.com/one", root, fixture)
    with pytest.raises(brief.BriefError, match="final URLs"):
        prepare(tmp_path, requirements(mode="improve", sources=[one, {"id": "copy", "kind": "reference", "capture": str(root)}]))


def test_failed_transport_not_accepted(tmp_path, monkeypatch):
    source = capture(tmp_path)
    original = pilot.load_capture
    def failed(path):
        root, manifest = original(path)
        manifest["capture"]["complete"] = False
        return root, manifest
    monkeypatch.setattr(pilot, "load_capture", failed)
    with pytest.raises(brief.BriefError, match="successful complete"):
        prepare(tmp_path, requirements(mode="improve", sources=[source]))


@pytest.mark.parametrize("target", ["capture/page.html", "capture/parsed.json", "capture/transport.json", "pilot-manifest.json"])
def test_source_tamper(tmp_path, target):
    source = capture(tmp_path)
    _, output, _ = prepare(tmp_path, requirements(mode="improve", sources=[source]))
    with (Path(source["capture"]) / target).open("ab") as handle:
        handle.write(b" ")
    with pytest.raises(brief.BriefError):
        brief.validate(output)


def test_partial_and_missing_finalize(tmp_path):
    _, output, manifest = prepare(tmp_path)
    role(output, manifest, "partial")
    assert brief.finalize(output)["phase"] == "partial"
    assert "Pending native review" in (output / "BRIEF.md").read_text()


def test_missing_role_finalize(tmp_path):
    _, output, _ = prepare(tmp_path)
    assert brief.finalize(output)["role"] == "missing"
    assert not brief.validate(output)["complete"]


@pytest.mark.parametrize("change", ["missing", "extra", "empty", "bad_basis", "unknown_source", "empty_source",
                                    "duplicate_source", "bad_text", "extra_entry", "many", "bad_status", "wrong_hash"])
def test_role_contract(tmp_path, change):
    source = {**capture(tmp_path), "kind": "reference"}
    _, output, manifest = prepare(tmp_path, requirements(sources=[source]))
    value = role(output, manifest)
    entries = value["sections"]["intent"]
    if change == "missing":
        del value["sections"]["intent"]
    elif change == "extra":
        value["sections"]["bonus"] = []
    elif change == "empty":
        value["sections"]["intent"] = []
    elif change == "bad_basis":
        entries[0]["basis"] = "fact"
    elif change == "unknown_source":
        entries[0]["sources"] = ["unknown"]
    elif change == "empty_source":
        entries[0]["basis"] = "source"
    elif change == "duplicate_source":
        entries[0]["sources"] = ["target", "target"]
    elif change == "bad_text":
        entries[0]["text"] = "x" * 4001
    elif change == "extra_entry":
        entries[0]["extra"] = "x"
    elif change == "many":
        value["sections"]["intent"] *= 41
    elif change == "bad_status":
        value["status"] = []
    else:
        value["requirements_sha256"] = "0" * 64
    write_role(output, value)
    with pytest.raises(brief.BriefError):
        brief.validate(output)


def test_improve_requires_target_assessment(tmp_path):
    source = capture(tmp_path)
    _, output, manifest = prepare(tmp_path, requirements(mode="improve", sources=[source]))
    role(output, manifest)
    with pytest.raises(brief.BriefError, match="target source"):
        brief.validate(output)


@pytest.mark.parametrize("target", ["BRIEF.md", "findings/content-brief.json"])
def test_finalized_tamper(tmp_path, target):
    _, output, manifest = prepare(tmp_path)
    role(output, manifest)
    brief.finalize(output)
    with (output / target).open("ab") as handle:
        handle.write(b" ")
    with pytest.raises(brief.BriefError, match="Finalized artifact"):
        brief.validate(output)


def test_rehashed_input_cannot_replace_original(tmp_path):
    _, output, manifest = prepare(tmp_path)
    value = json.loads((output / "input.json").read_text())
    value["topic"] = "Replacement"
    raw = pilot.encode(value)
    (output / "input.json").write_bytes(raw)
    manifest["evidence"]["requirements_sha256"] = pilot.digest(raw)
    manifest["evidence"]["artifacts"]["input.json"] = {"sha256": pilot.digest(raw), "bytes": len(raw)}
    manifest["evidence_sha256"] = pilot.digest(pilot.encode(manifest["evidence"], compact=True))
    (output / brief.MANIFEST).write_bytes(pilot.encode(manifest))
    with pytest.raises(brief.BriefError, match="Original requirements changed"):
        brief.validate(output)


def test_original_input_change_rejected(tmp_path):
    source, output, _ = prepare(tmp_path)
    source.write_text(source.read_text() + " ")
    with pytest.raises(brief.BriefError):
        brief.validate(output)


def test_noncanonical_requirements_rejected(tmp_path):
    _, output, _ = prepare(tmp_path)
    with (output / "input.json").open("ab") as handle:
        handle.write(b" ")
    with pytest.raises(brief.BriefError, match="canonical"):
        brief.validate(output)


def test_provenance_change_rejected(tmp_path, monkeypatch):
    _, output, _ = prepare(tmp_path)
    original = brief.record
    def changed(path, limit=brief.MAX_JSON):
        result = original(path, limit)
        if path.name == "codex_brief.py":
            result["sha256"] = "0" * 64
        return result
    monkeypatch.setattr(brief, "record", changed)
    with pytest.raises(brief.BriefError, match="implementation changed"):
        brief.validate(output)


def test_later_head_does_not_change_frozen_provenance(tmp_path, monkeypatch):
    _, output, manifest = prepare(tmp_path)
    assert manifest["evidence"]["provenance"]["kind"] == "git-checkout"
    monkeypatch.setattr(pilot, "source_commit", lambda: "f" * 40)
    assert brief.validate(output)["valid"]


def test_render_untrusted_html_markdown_urls(tmp_path):
    attack = '<img src="https://evil.test/x"> ![x](https://evil.test/a) <script>alert(1)</script>\n# heading'
    _, output, manifest = prepare(tmp_path, requirements(topic=attack))
    value = role(output, manifest)
    value["sections"]["intent"][0]["text"] = attack
    write_role(output, value)
    brief.finalize(output)
    rendered = (output / "BRIEF.md").read_text()
    assert '<img' not in rendered and '<script' not in rendered
    assert "![x]" not in rendered and "https://evil" not in rendered
    assert "&lt;img" in rendered
    assert "[proposal]" in rendered


def test_symlink_and_relative_paths_rejected(tmp_path):
    source, output, _ = prepare(tmp_path)
    alias = tmp_path / "alias"
    alias.symlink_to(source)
    with pytest.raises(brief.BriefError):
        brief.prepare(alias, tmp_path / "other")
    with pytest.raises(brief.BriefError):
        brief.validate(Path("relative"))
    (output / "evil").symlink_to(source)
    with pytest.raises(brief.BriefError):
        brief.validate(output)


def test_cli_help_and_partial_exit(tmp_path):
    _, output, _ = prepare(tmp_path)
    process = subprocess.run([sys.executable, str(Path(brief.__file__)), "finalize", "--output", str(output)],
                             capture_output=True, text=True)
    assert process.returncode == 1
    assert json.loads(process.stdout)["phase"] == "partial"
