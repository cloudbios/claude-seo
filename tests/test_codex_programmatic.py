"""Offline programmatic sample review and immutable evidence contracts."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import codex_pilot as pilot  # noqa: E402
import codex_programmatic as programmatic  # noqa: E402


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setattr("socket.getaddrinfo", lambda *a, **kw: pytest.fail("Unexpected DNS"))
    monkeypatch.setattr("requests.sessions.Session.request", lambda *a, **kw: pytest.fail("Unexpected HTTP"))


def capture(tmp_path, name, html=None, url=None):
    fixture = tmp_path / (name + ".html")
    fixture.write_text(html or '<html><title>Repairs</title><meta name="description" content="Help"><h1>Repairs</h1></html>')
    root = tmp_path / name
    pilot.capture(url or "https://example.com/" + name, root, fixture)
    return {"id": name, "capture": str(root)}


def requirements(source_list, **updates):
    return {"family": "Repair locations", "business_context": "A repair company", "audience": "Homeowners",
            "page_purpose": "Explain local repairs", "expected_differences": ["Local contact details"],
            "sources": source_list, **updates}


def prepare(tmp_path, sources=None, **updates):
    if sources is None:
        sources = [capture(tmp_path, "one"), capture(tmp_path, "two")]
    path = tmp_path / "requirements.json"
    path.write_bytes(pilot.encode(requirements(sources, **updates)))
    output = tmp_path / "review"
    return path, output, programmatic.prepare(path, output)


def write_role(output, value):
    (output / "findings/programmatic.json").write_bytes(pilot.encode(value))


def role(output, manifest, status="complete"):
    value = {"role": "programmatic", "requirements_sha256": manifest["evidence"]["requirements_sha256"],
             "evidence_sha256": manifest["evidence_sha256"], "status": status,
             "findings": [{"kind": "observation", "scope": "sample",
                           "sources": [source["id"] for source in manifest["evidence"]["sources"]],
                           "text": "The saved titles are Repairs in both source documents."}] if status == "complete" else [],
             "limitations": ["Only the saved sample was reviewed."]}
    write_role(output, value)
    return value


def replace_parsed(source, **updates):
    root = Path(source["capture"])
    parsed = pilot.json_read(root / "capture/parsed.json", pilot.MAX_ARTIFACT_BYTES)
    parsed.update(updates)
    raw = pilot.encode(parsed)
    (root / "capture/parsed.json").write_bytes(raw)
    manifest = pilot.json_read(root / pilot.MANIFEST)
    manifest["artifacts"]["capture/parsed.json"] = {"sha256": pilot.digest(raw), "bytes": len(raw)}
    (root / pilot.MANIFEST).write_bytes(pilot.encode(manifest))


def test_complete_and_exact_groups(tmp_path):
    _, output, manifest = prepare(tmp_path)
    analyzed = pilot.json_read(output / "analysis.json")
    assert analyzed["repeated_values"] == [
        {"field": "title", "sources": ["one", "two"]},
        {"field": "meta_description", "sources": ["one", "two"]},
        {"field": "html_sha256", "sources": ["one", "two"]}]
    page = analyzed["pages"][0]
    assert set(page) == {"id", "requested_url", "final_url", "representation", "html_sha256", "title",
                         "meta_description", "canonical", "h1", "sample_links"}
    assert page["h1"] == programmatic.value_record(["Repairs"])
    assert page["canonical"] == programmatic.value_record(None)
    assert programmatic.validate(output)["role"] == "missing"
    role(output, manifest)
    assert programmatic.finalize(output)["complete"]
    assert programmatic.validate(output)["phase"] == "complete"
    with pytest.raises(programmatic.ProgrammaticError, match="already finalized"):
        programmatic.finalize(output)


@pytest.mark.parametrize("count", [2, 5])
def test_sample_bounds_accepted(tmp_path, count):
    sources = [capture(tmp_path, "source-" + str(i)) for i in range(count)]
    _, output, manifest = prepare(tmp_path, sources)
    role(output, manifest)
    assert programmatic.validate(output)["complete"]


@pytest.mark.parametrize("updates", [
    {"family": ""}, {"family": "x" * 201}, {"audience": []}, {"audience": "x" * 4001},
    {"business_context": None}, {"page_purpose": False}, {"expected_differences": [""]},
    {"expected_differences": ["x"] * 21}, {"expected_differences": ["x" * 2001]},
    {"extra": 1}, {"sources": []}, {"sources": [{}]}, {"sources": [{}] * 6},
    {"sources": [{"id": "x", "capture": "relative"}] * 2},
    {"sources": [{"id": "UPPER", "capture": "/tmp/one"}, {"id": "two", "capture": "/tmp/two"}]},
])
def test_invalid_requirements(updates):
    with pytest.raises(programmatic.ProgrammaticError):
        programmatic.normalize(requirements([{"id": "one", "capture": "/tmp/one"},
                                             {"id": "two", "capture": "/tmp/two"}], **updates))


@pytest.mark.parametrize("field", ["family", "business_context", "audience", "page_purpose", "expected_differences", "sources"])
def test_required_input_fields(field):
    value = requirements([])
    del value[field]
    with pytest.raises(programmatic.ProgrammaticError):
        programmatic.normalize(value)


def test_duplicate_ids_paths_final_urls_and_unknown_keys(tmp_path):
    one, two = capture(tmp_path, "one"), capture(tmp_path, "two")
    duplicate_url = capture(tmp_path, "copy", url="https://example.com/one")
    for sources in ([one, {**two, "id": "one"}], [one, {**one, "id": "copy"}],
                    [one, duplicate_url], [one, {**two, "kind": "reference"}]):
        with pytest.raises(programmatic.ProgrammaticError):
            prepare(tmp_path, sources)
        assert not (tmp_path / "review").exists()


def test_failed_capture_preflight_does_not_read_parsed(tmp_path, monkeypatch):
    one, two = capture(tmp_path, "one"), capture(tmp_path, "two")
    original = pilot.load_capture
    def failed(path):
        root, manifest = original(path)
        manifest["capture"]["complete"] = False
        return root, manifest
    monkeypatch.setattr(pilot, "load_capture", failed)
    monkeypatch.setattr(programmatic, "parsed_fields", lambda *a: pytest.fail("Inspected error-page content"))
    with pytest.raises(programmatic.ProgrammaticError, match="successful complete"):
        prepare(tmp_path, [one, two])
    assert not (tmp_path / "review").exists()


def test_literal_canonical_empty_values_and_stable_groups(tmp_path):
    sources = [capture(tmp_path, name, html='<title>' + name + '</title>') for name in ("one", "two", "three", "four")]
    replace_parsed(sources[0], title="", meta_description=None, canonical="/literal")
    replace_parsed(sources[1], title="", meta_description="", canonical="https://example.com/literal")
    replace_parsed(sources[2], title=None, meta_description=None, canonical="/literal")
    replace_parsed(sources[3], title=None, meta_description="", canonical="https://example.com/literal")
    _, output, _ = prepare(tmp_path, sources)
    assert pilot.json_read(output / "analysis.json")["repeated_values"] == [
        {"field": "canonical", "sources": ["one", "three"]},
        {"field": "canonical", "sources": ["two", "four"]}]


def test_sample_links_strip_only_fragments_and_preserve_input_order(tmp_path):
    urls = ["https://example.com/one", "https://other.test/path?b=2&a=1", "https://other.test/path?a=1&b=2",
            "https://other.test/path/", "https://other.test/Path"]
    sources = [capture(tmp_path, name, url=url) for name, url in zip(("one", "two", "three", "four", "five"), urls)]
    hrefs = [urls[4] + "#x", urls[1] + "#first", urls[1] + "#repeat", "https://OTHER.test/path/",
             "https://other.test/path", "mailto:someone@example.com", "ftp://other.test/path/"]
    replace_parsed(sources[0], links={"internal": [{"href": href} for href in hrefs[:3]],
                                    "external": [{"href": href} for href in hrefs[3:]]})
    _, output, _ = prepare(tmp_path, sources)
    assert pilot.json_read(output / "analysis.json")["pages"][0]["sample_links"] == ["two", "five"]


def test_large_field_omission_and_large_parsed_artifact(tmp_path):
    one, two = capture(tmp_path, "one"), capture(tmp_path, "two")
    giant = "雪" * 2000
    replace_parsed(one, title=giant, h1=[giant], images=[{"src": str(i)} for i in range(12000)])
    replace_parsed(two, title=giant)
    _, output, _ = prepare(tmp_path, [one, two])
    analyzed = pilot.json_read(output / "analysis.json")
    for name, original in (("title", giant), ("h1", [giant])):
        item = analyzed["pages"][0][name]
        assert item == {"value": None, "sha256": pilot.digest(pilot.encode(original, compact=True)),
                        "bytes": len(pilot.encode(original, compact=True)), "omitted": True}
    assert giant not in (output / "analysis.json").read_text()
    assert {"field": "title", "sources": ["one", "two"]} in analyzed["repeated_values"]
    assert programmatic.validate(output)["valid"]


@pytest.mark.parametrize("updates", [{"title": []}, {"meta_description": 1}, {"canonical": {}},
                                     {"h1": [False]}, {"links": {}}, {"links": {"internal": ["bad"], "external": []}}])
def test_parsed_shape_preflight(tmp_path, updates):
    one, two = capture(tmp_path, "one"), capture(tmp_path, "two")
    replace_parsed(one, **updates)
    with pytest.raises(programmatic.ProgrammaticError):
        prepare(tmp_path, [one, two])
    assert not (tmp_path / "review").exists()


@pytest.mark.parametrize("target", ["capture/page.html", "capture/parsed.json", "capture/transport.json", "pilot-manifest.json"])
def test_capture_tampering(tmp_path, target):
    _, output, manifest = prepare(tmp_path)
    with (Path(manifest["evidence"]["sources"][0]["capture"]) / target).open("ab") as handle:
        handle.write(b" ")
    with pytest.raises(programmatic.ProgrammaticError):
        programmatic.validate(output)


@pytest.mark.parametrize("target", ["requirements.json", "review/input.json", "review/analysis.json"])
def test_input_and_analysis_tampering(tmp_path, target):
    _, output, _ = prepare(tmp_path)
    with (tmp_path / target).open("ab") as handle:
        handle.write(b" ")
    with pytest.raises(programmatic.ProgrammaticError):
        programmatic.validate(output)


def test_rehashed_analysis_still_recomputed(tmp_path):
    _, output, manifest = prepare(tmp_path)
    analyzed = pilot.json_read(output / "analysis.json")
    analyzed["pages"][0]["sample_links"] = ["two"]
    raw = pilot.encode(analyzed)
    (output / "analysis.json").write_bytes(raw)
    manifest["evidence"]["artifacts"]["analysis.json"] = {"sha256": pilot.digest(raw), "bytes": len(raw)}
    manifest["evidence_sha256"] = pilot.digest(pilot.encode(manifest["evidence"], compact=True))
    (output / programmatic.MANIFEST).write_bytes(pilot.encode(manifest))
    with pytest.raises(programmatic.ProgrammaticError, match="recomputed"):
        programmatic.validate(output)


def test_rehashed_input_cannot_replace_original(tmp_path):
    _, output, manifest = prepare(tmp_path)
    value = pilot.json_read(output / "input.json")
    value["family"] = "Replacement"
    raw = pilot.encode(value)
    (output / "input.json").write_bytes(raw)
    manifest["evidence"]["requirements_sha256"] = pilot.digest(raw)
    manifest["evidence"]["artifacts"]["input.json"] = {"sha256": pilot.digest(raw), "bytes": len(raw)}
    manifest["evidence_sha256"] = pilot.digest(pilot.encode(manifest["evidence"], compact=True))
    (output / programmatic.MANIFEST).write_bytes(pilot.encode(manifest))
    with pytest.raises(programmatic.ProgrammaticError, match="Original requirements changed"):
        programmatic.validate(output)


@pytest.mark.parametrize("changed_file", ["codex_programmatic.py", "codex_planning.py"])
def test_code_identity_tamper(tmp_path, monkeypatch, changed_file):
    _, output, _ = prepare(tmp_path)
    original = programmatic.planning.record
    def changed(path, limit=programmatic.MAX_JSON):
        result = original(path, limit)
        if path.name == changed_file:
            result["sha256"] = "0" * 64
        return result
    monkeypatch.setattr(programmatic.planning, "record", changed)
    with pytest.raises(programmatic.ProgrammaticError, match="implementation changed"):
        programmatic.validate(output)


def test_later_head_preserves_saved_provenance(tmp_path, monkeypatch):
    _, output, _ = prepare(tmp_path)
    monkeypatch.setattr(pilot, "source_commit", lambda: "f" * 40)
    assert programmatic.validate(output)["valid"]


@pytest.mark.parametrize("change", ["extra", "identity", "status", "kind", "scope", "refs", "duplicate",
                                   "emptyrefs", "page-many", "sample-one", "text", "many", "limitations",
                                   "limit-text", "finding-extra", "no-observation", "page-only", "incomplete"])
def test_native_contract(tmp_path, change):
    _, output, manifest = prepare(tmp_path)
    value = role(output, manifest)
    finding = value["findings"][0]
    if change == "extra":
        value["extra"] = True
    elif change == "identity":
        value["evidence_sha256"] = "0" * 64
    elif change == "status":
        value["status"] = []
    elif change == "kind":
        finding["kind"] = []
    elif change == "scope":
        finding["scope"] = False
    elif change == "refs":
        finding["sources"] = ["one", "unknown"]
    elif change == "duplicate":
        finding["sources"] = ["one", "one"]
    elif change == "emptyrefs":
        finding["sources"] = []
    elif change == "page-many":
        finding["scope"] = "page"
    elif change == "sample-one":
        finding["sources"] = ["one"]
    elif change == "text":
        finding["text"] = "x" * 4001
    elif change == "many":
        value["findings"] *= 101
    elif change == "limitations":
        value["limitations"] *= 101
    elif change == "limit-text":
        value["limitations"] = ["x" * 4001]
    elif change == "finding-extra":
        finding["score"] = 90
    elif change == "no-observation":
        finding["kind"] = "recommendation"
    elif change == "page-only":
        value["findings"] = [{**finding, "scope": "page", "sources": [name]} for name in ("one", "two")]
    else:
        third = capture(tmp_path, "three")
        # Source coverage is independently enforced when a sample has more than two sources.
        sources = manifest["evidence"]["sources"]
        req = requirements([{key: source[key] for key in ("id", "capture")} for source in sources] + [third])
        other_input = tmp_path / "other-input.json"
        other_input.write_bytes(pilot.encode(req))
        output = tmp_path / "other-review"
        manifest = programmatic.prepare(other_input, output)
        value = role(output, manifest)
        value["findings"][0]["sources"] = ["one", "two"]
    write_role(output, value)
    with pytest.raises(programmatic.ProgrammaticError):
        programmatic.validate(output)


def test_observation_coverage_can_mix_page_and_sample(tmp_path):
    sources = [capture(tmp_path, name) for name in ("one", "two", "three")]
    _, output, manifest = prepare(tmp_path, sources)
    value = role(output, manifest)
    value["findings"][0]["sources"] = ["one", "two"]
    value["findings"].append({"kind": "observation", "scope": "page", "sources": ["three"], "text": "Saved title is Repairs."})
    write_role(output, value)
    assert programmatic.validate(output)["complete"]


@pytest.mark.parametrize("native", [False, True])
def test_partial_finalize_and_freeze(tmp_path, native):
    _, output, manifest = prepare(tmp_path)
    if native:
        role(output, manifest, "partial")
    assert programmatic.validate(output)["valid"]
    assert not programmatic.finalize(output)["complete"]
    assert programmatic.validate(output)["phase"] == "partial"
    if native:
        role(output, manifest)
    else:
        role(output, manifest, "partial")
    with pytest.raises(programmatic.ProgrammaticError):
        programmatic.validate(output)


@pytest.mark.parametrize("target", ["REPORT.md", "findings/programmatic.json"])
def test_finalized_tampering(tmp_path, target):
    _, output, manifest = prepare(tmp_path)
    role(output, manifest)
    programmatic.finalize(output)
    with (output / target).open("ab") as handle:
        handle.write(b" ")
    with pytest.raises(programmatic.ProgrammaticError, match="Finalized artifact"):
        programmatic.validate(output)


def test_report_preserves_findings_and_escapes_untrusted_text(tmp_path):
    attack = '<script>alert(1)</script> ![x](https://evil.test/a)\n# heading'
    _, output, manifest = prepare(tmp_path, family=attack)
    value = role(output, manifest)
    for kind in ("inference", "recommendation"):
        value["findings"].append({"kind": kind, "scope": "page", "sources": ["one"], "text": attack})
    write_role(output, value)
    programmatic.finalize(output)
    rendered = (output / "REPORT.md").read_text()
    assert '<script' not in rendered and '![x]' not in rendered and 'https://evil' not in rendered
    assert '&lt;script&gt;' in rendered
    assert '[observation, sample, one, two]' in rendered
    assert '[inference, page, one]' in rendered and '[recommendation, page, one]' in rendered


def test_symlink_paths_and_fresh_output(tmp_path):
    source, output, _ = prepare(tmp_path)
    alias = tmp_path / "alias"
    alias.symlink_to(source)
    with pytest.raises(programmatic.ProgrammaticError):
        programmatic.prepare(alias, tmp_path / "other")
    with pytest.raises(programmatic.ProgrammaticError):
        programmatic.prepare(source, output)
    with pytest.raises(programmatic.ProgrammaticError):
        programmatic.validate(Path("relative"))
    (output / "unrelated").symlink_to(source)
    with pytest.raises(programmatic.ProgrammaticError):
        programmatic.validate(output)


@pytest.mark.parametrize("raw", [b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":1e9999}', b'\xff', b'[' * 34 + b'0' + b']' * 34])
def test_strict_json(raw):
    with pytest.raises(programmatic.ProgrammaticError):
        programmatic.decode(raw)


def test_input_bound(tmp_path):
    source = tmp_path / "huge.json"
    source.write_bytes(b" " * (programmatic.MAX_INPUT + 1))
    with pytest.raises(programmatic.ProgrammaticError):
        programmatic.prepare(source, tmp_path / "review")
    assert not (tmp_path / "review").exists()


def test_cli_partial_exit_and_help(tmp_path):
    _, output, _ = prepare(tmp_path)
    script = str(Path(programmatic.__file__))
    result = subprocess.run([sys.executable, script, "validate", "--output", str(output)], capture_output=True, text=True)
    assert result.returncode == 0
    assert json.loads(result.stdout)["valid"]
    result = subprocess.run([sys.executable, script, "finalize", "--output", str(output)], capture_output=True, text=True)
    assert result.returncode == 1
    assert json.loads(result.stdout)["phase"] == "partial"
    result = subprocess.run([sys.executable, script, "--help"], capture_output=True, text=True)
    assert result.returncode == 0 and "prepare" in result.stdout


def test_real_failed_http_capture_preflight(tmp_path, monkeypatch):
    one, two = capture(tmp_path, "one"), capture(tmp_path, "two")
    root = Path(one["capture"])
    transport = pilot.json_read(root / "capture/transport.json")
    transport.update(representation="raw-http", status_code=404, error="HTTP 404")
    raw = pilot.encode(transport)
    (root / "capture/transport.json").write_bytes(raw)
    manifest = pilot.json_read(root / pilot.MANIFEST)
    manifest["capture"].update(representation="raw-http", complete=False)
    manifest["checks"]["transport"] = "failed"
    manifest["artifacts"]["capture/transport.json"] = {"sha256": pilot.digest(raw), "bytes": len(raw)}
    (root / pilot.MANIFEST).write_bytes(pilot.encode(manifest))
    monkeypatch.setattr(programmatic, "parsed_fields", lambda *a: pytest.fail("Inspected error-page content"))
    with pytest.raises(programmatic.ProgrammaticError, match="successful complete"):
        prepare(tmp_path, [one, two])
    assert not (tmp_path / "review").exists()


def test_value_record_exact_byte_boundary():
    # JSON quotes and the encoder's final newline count toward the bound.
    assert programmatic.value_record("a" * 4093)["omitted"] is False
    assert programmatic.value_record("a" * 4094)["omitted"] is True


def test_cli_prepare_and_complete(tmp_path):
    sources = [capture(tmp_path, "one"), capture(tmp_path, "two")]
    source = tmp_path / "input.json"
    source.write_bytes(pilot.encode(requirements(sources)))
    output = tmp_path / "review"
    script = str(Path(programmatic.__file__))
    result = subprocess.run([sys.executable, script, "prepare", "--input", str(source), "--output", str(output)],
                            capture_output=True, text=True)
    assert result.returncode == 0
    role(output, json.loads(result.stdout))
    result = subprocess.run([sys.executable, script, "finalize", "--output", str(output)], capture_output=True, text=True)
    assert result.returncode == 0
    assert json.loads(result.stdout)["complete"]
