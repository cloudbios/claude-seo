"""Offline source drift contracts and evidence integrity."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import codex_drift as drift  # noqa: E402
import codex_pilot as pilot  # noqa: E402

HTML = '<html><head><title>Example</title><meta name="description" content="Description"></head><body><h1>Heading</h1></body></html>'
URL = "https://example.com/path?utm_source=a&x=1"


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setattr("socket.getaddrinfo", lambda *a, **kw: pytest.fail("Unexpected DNS"))
    monkeypatch.setattr("requests.sessions.Session.request", lambda *a, **kw: pytest.fail("Unexpected HTTP"))


def capture(tmp_path, name, html=HTML, url=URL):
    fixture = tmp_path / (name + ".html")
    fixture.write_text(html)
    root = tmp_path / name
    pilot.capture(url, root, fixture)
    return root


def edit(root, name, **updates):
    path = root / name
    data = json.loads(path.read_bytes())
    data.update(updates)
    path.write_bytes(pilot.encode(data))
    manifest_path = root / pilot.MANIFEST
    manifest = json.loads(manifest_path.read_bytes())
    manifest["artifacts"][name] = drift.record(path, pilot.MAX_ARTIFACT_BYTES)
    if name == "capture/transport.json":
        for key in ("requested_url", "final_url", "representation"):
            manifest["capture"][key] = data[key]
        manifest["capture"]["complete"] = data["error"] is None
        manifest["checks"]["transport"] = "failed" if data["error"] else "passed"
    if name == "capture/schema.json":
        manifest["checks"]["schema"] = data["status"]
    manifest_path.write_bytes(pilot.encode(manifest))


def prepare(tmp_path, before_html=HTML, after_html=HTML):
    before = capture(tmp_path, "before", before_html)
    after = capture(tmp_path, "after", after_html)
    output = tmp_path / "drift"
    return before, after, output


def compare(tmp_path, before_html=HTML, after_html=HTML):
    before, after, output = prepare(tmp_path, before_html, after_html)
    manifest = drift.compare(before, after, output)
    return before, after, output, manifest


def rows(output):
    return {row["id"]: row for row in json.loads((output / "analysis.json").read_bytes())["comparisons"]}


def native(output, manifest, **updates):
    value = {"role": "drift", "before_capture_sha256": manifest["evidence"]["before"]["capture_sha256"],
             "after_capture_sha256": manifest["evidence"]["after"]["capture_sha256"],
             "evidence_sha256": manifest["evidence_sha256"], "status": "complete",
             "findings": [{"kind": "observation", "text": "Saved titles agree.", "comparisons": ["document.title"]}],
             "limitations": ["Saved evidence only."], **updates}
    (output / "findings/drift.json").write_bytes(pilot.encode(value))
    return value


def test_identical_complete_fixture_and_final_report(tmp_path):
    before, after, output, manifest = compare(tmp_path)
    analysis = json.loads((output / "analysis.json").read_bytes())
    assert analysis["status"] == "complete"
    assert analysis["scope"] == "source"
    assert tuple(rows(output)) == drift.COMPARISON_IDS
    assert analysis["totals"] == {"changed": 0, "unchanged": 20, "unavailable": 1}
    assert manifest["evidence"]["before"]["capture"] == str(before)
    assert manifest["evidence"]["after"]["pilot_manifest"] == drift.record(after / pilot.MANIFEST)
    assert not drift.validate(output)["complete"]
    native(output, manifest)
    assert drift.finalize(output)["complete"]
    report = (output / "REPORT.md").read_text()
    assert all(identifier in report for identifier in drift.COMPARISON_IDS)
    assert "Saved titles agree" in report
    with pytest.raises(drift.DriftError, match="already finalized"):
        drift.finalize(output)


def test_changes_are_exact_and_preview_is_escaped(tmp_path):
    _, _, output, manifest = compare(tmp_path, HTML, HTML.replace("Example", "Other").replace("Heading", "New"))
    result = rows(output)
    assert result["document.title"]["status"] == "changed"
    assert result["document.h1"]["status"] == "changed"
    assert result["source.html_sha256"]["status"] == "changed"
    native(output, manifest, findings=[{"kind": "interpretation", "text": '<script>x</script> [click](https://bad.test)',
                                       "comparisons": ["document.title"]}])
    drift.finalize(output)
    report = (output / "REPORT.md").read_text()
    assert "<script>" not in report and "[click]" not in report and "https://bad.test" not in report


@pytest.mark.parametrize("url", ["https://example.com/path/?utm_source=a&x=1", "https://example.com/path?x=1&utm_source=a",
                                  "https://example.com/path?utm_source=b&x=1", "https://example.com/path?x=1",
                                  "https://EXAMPLE.com/path?utm_source=a&x=1"])
def test_requested_urls_must_match_exactly(tmp_path, url):
    before = capture(tmp_path, "before")
    after = capture(tmp_path, "after", url=url)
    with pytest.raises(drift.DriftError, match="exactly"):
        drift.compare(before, after, tmp_path / "output")


def test_distinct_paths_and_matching_representation_required(tmp_path):
    before, after, output = prepare(tmp_path)
    with pytest.raises(drift.DriftError, match="distinct"):
        drift.compare(before, before, output)
    edit(after, "capture/transport.json", representation="raw-http", status_code=200)
    with pytest.raises(drift.DriftError, match="mix"):
        drift.compare(before, after, output)


@pytest.mark.parametrize("too_large", [False, True])
def test_failed_after_suppresses_all_source_comparisons(tmp_path, too_large):
    before, after, output = prepare(tmp_path, HTML, "<html>Error</html>")
    edit(after, "capture/transport.json", error="Body too large" if too_large else "HTTP 503", too_large=too_large,
         status_code=503 if not too_large else 200, headers={"X-Robots-Tag": "noindex"})
    manifest = drift.compare(before, after, output)
    result = rows(output)
    assert drift.validate(output)["analysis"] == "partial"
    assert drift.validate(output)["scope"] == "transport-only"
    assert result["transport.headers.x_robots_tag"]["after"]["value"] == ["noindex"]
    for key, row in result.items():
        if not key.startswith("transport."):
            assert row["status"] == "unavailable"
            assert row["before"] is None and row["after"] is None
    native(output, manifest)
    with pytest.raises(drift.DriftError, match="overstate"):
        drift.validate(output)
    native(output, manifest, status="partial", findings=[])
    assert not drift.finalize(output)["complete"]


def test_failed_before_rejected(tmp_path):
    before, after, output = prepare(tmp_path)
    edit(before, "capture/transport.json", error="HTTP 500", status_code=500)
    with pytest.raises(drift.DriftError, match="Before"):
        drift.compare(before, after, output)


def test_raw_headers_case_insensitive_preserve_values_and_redirects(tmp_path):
    before, after, output = prepare(tmp_path)
    headers = {"X-Robots-Tag": "noindex, follow", "x-robots-tag": "googlebot: index", "Link": '<a>; rel="canonical"'}
    for root in (before, after):
        edit(root, "capture/transport.json", headers=headers, representation="raw-http", status_code=200,
             redirect_chain=[{"url": "https://example.com/old", "status_code": 301}])
    edit(after, "capture/transport.json", headers={"x-robots-tag": "googlebot: index", "X-Robots-Tag": "noindex, follow", "link": '<a>; rel="canonical"'},
         final_url="https://example.com/final")
    drift.compare(before, after, output)
    result = rows(output)
    assert result["transport.headers.x_robots_tag"]["before"]["value"] == ["googlebot: index", "noindex, follow"]
    assert result["transport.headers.x_robots_tag"]["status"] == "unchanged"
    assert result["transport.headers.link"]["status"] == "unchanged"
    assert result["transport.final_url"]["status"] == "changed"
    assert result["transport.status_code"]["status"] == "unchanged"


def test_incomplete_json_ld_is_not_absence(tmp_path):
    before, after, output = prepare(tmp_path)
    edit(after, "capture/schema.json", status="failed", block_count=200, blocks=[], error="Too many JSON-LD blocks")
    drift.compare(before, after, output)
    result = rows(output)
    assert result["json_ld.block_count"]["after"]["value"] == 200
    assert result["json_ld.raw_hashes"]["status"] == "unavailable"
    assert result["json_ld.validation_statuses"]["status"] == "unavailable"
    assert drift.validate(output)["analysis"] == "partial"


def test_invalid_json_still_has_comparable_raw_hash(tmp_path):
    html = HTML + '<script type="application/ld+json">{ invalid }</script>'
    _, _, output, _ = compare(tmp_path, html, html.replace("{ invalid }", "{ invalid changed }"))
    result = rows(output)
    assert result["json_ld.raw_hashes"]["status"] == "changed"
    assert result["json_ld.validation_statuses"]["before"]["value"] == ["failed"]
    assert drift.validate(output)["analysis"] == "complete"


def test_deep_schema_data_is_ignored_without_rejecting_saved_capture(tmp_path):
    before, after, output = prepare(tmp_path)
    data = "leaf"
    for _ in range(48):
        data = {"nested": data}
    for root in (before, after):
        edit(root, "capture/schema.json", status="failed", block_count=1,
             blocks=[{"index": 1, "sha256": "a" * 64, "status": "failed", "errors": ["Invalid schema"], "warnings": [], "data": data}])
    drift.compare(before, after, output)
    assert rows(output)["json_ld.raw_hashes"]["status"] == "unchanged"


def test_large_value_hash_not_preview_determines_change(tmp_path):
    before, after, output = prepare(tmp_path)
    a = "é" * 18000
    edit(before, "capture/parsed.json", title=a)
    edit(after, "capture/parsed.json", title=a + "b")
    drift.compare(before, after, output)
    row = rows(output)["document.title"]
    assert row["status"] == "changed"
    assert row["before"]["value"] is None and row["before"]["truncated"]
    assert row["before"]["preview"] == row["after"]["preview"]
    assert len(row["before"]["preview"].encode()) <= drift.PREVIEW_LIMIT
    assert row["before"]["sha256"] == pilot.digest(drift.canonical(a))
    assert (output / "analysis.json").stat().st_size <= drift.MAX_JSON


@pytest.mark.parametrize("field,bad", [("title", 1), ("meta_description", []), ("canonical", {}), ("meta_robots", False),
                                       ("h1", [1]), ("h2", None), ("h3", {}), ("open_graph", {"og:x": []}), ("twitter_card", [])])
def test_malformed_selected_document_fields_rejected(tmp_path, field, bad):
    before, after, output = prepare(tmp_path)
    edit(after, "capture/parsed.json", **{field: bad})
    with pytest.raises(drift.DriftError):
        drift.compare(before, after, output)


@pytest.mark.parametrize("updates", [{"headers": {"Link": 1}}, {"redirect_chain": ["a"]},
                                     {"redirect_chain": [{"url": "x", "status_code": True}]}, {"captured_at": None}])
def test_malformed_transport_fields_rejected(tmp_path, updates):
    before, after, output = prepare(tmp_path)
    edit(after, "capture/transport.json", **updates)
    with pytest.raises(drift.DriftError):
        drift.compare(before, after, output)


@pytest.mark.parametrize("artifact", ["capture/page.html", "capture/parsed.json", pilot.MANIFEST])
def test_external_capture_tampering_rejected(tmp_path, artifact):
    before, _, output, _ = compare(tmp_path)
    path = before / artifact
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(drift.DriftError):
        drift.validate(output)


def test_rehashed_analysis_cannot_change_derived_values(tmp_path):
    _, _, output, _ = compare(tmp_path)
    path = output / "analysis.json"
    analysis = json.loads(path.read_bytes())
    analysis["comparisons"][1]["status"] = "changed"
    path.write_bytes(pilot.encode(analysis))
    manifest_path = output / drift.MANIFEST
    manifest = json.loads(manifest_path.read_bytes())
    manifest["evidence"]["artifacts"]["analysis.json"] = drift.record(path)
    manifest["evidence_sha256"] = pilot.digest(drift.canonical(manifest["evidence"]))
    manifest_path.write_bytes(pilot.encode(manifest))
    with pytest.raises(drift.DriftError, match="disagrees"):
        drift.validate(output)


@pytest.mark.parametrize("updates", [{"role": "technical"}, {"before_capture_sha256": "0" * 64}, {"after_capture_sha256": "0" * 64},
                                     {"evidence_sha256": "0" * 64}, {"extra": 1}, {"status": []}, {"findings": ["x"]},
                                     {"findings": [{"kind": "fact", "text": "x", "comparisons": ["document.title"]}]},
                                     {"findings": [{"kind": "observation", "text": "x", "comparisons": ["bad"]}]},
                                     {"findings": [{"kind": "observation", "text": "x", "comparisons": ["document.title", "document.title"]}]},
                                     {"findings": [{"kind": "observation", "text": "x", "comparisons": []}]},
                                     {"limitations": ["x"] * 101}])
def test_invalid_native_findings_rejected(tmp_path, updates):
    _, _, output, manifest = compare(tmp_path)
    native(output, manifest, **updates)
    with pytest.raises(drift.DriftError):
        drift.validate(output)


@pytest.mark.parametrize("raw", [b'{"role":"drift","role":"drift"}', b'{"n":NaN}', b'{"n":1e999}'])
def test_strict_json_native_findings(tmp_path, raw):
    _, _, output, _ = compare(tmp_path)
    (output / "findings/drift.json").write_bytes(raw)
    with pytest.raises(drift.DriftError):
        drift.validate(output)


@pytest.mark.parametrize("native_present", [False, True])
def test_partial_finalization_and_later_edits_are_rejected(tmp_path, native_present):
    _, _, output, manifest = compare(tmp_path)
    if native_present:
        native(output, manifest, status="partial", findings=[])
    assert not drift.finalize(output)["complete"]
    native(output, manifest)
    with pytest.raises(drift.DriftError):
        drift.validate(output)


def test_finalized_report_and_implementation_hashes_bound(tmp_path, monkeypatch):
    _, _, output, manifest = compare(tmp_path)
    native(output, manifest)
    drift.finalize(output)
    path = output / "REPORT.md"
    saved = path.read_bytes()
    path.write_bytes(saved + b"tamper")
    with pytest.raises(drift.DriftError, match="Finalized"):
        drift.validate(output)
    path.write_bytes(saved)
    monkeypatch.setattr(drift, "IMPLEMENTATION", ("scripts/codex_pilot.py",))
    with pytest.raises(drift.DriftError, match="implementation"):
        drift.validate(output)


def test_relative_and_symlink_paths_rejected(tmp_path):
    before, after, output = prepare(tmp_path)
    with pytest.raises(drift.DriftError, match="absolute"):
        drift.compare(Path("before"), after, output)
    link = tmp_path / "linked"
    link.symlink_to(before, target_is_directory=True)
    with pytest.raises(drift.DriftError, match="Symlink"):
        drift.compare(link, after, output)


def test_cli_validate_and_partial_finalize(tmp_path):
    _, _, output, _ = compare(tmp_path)
    command = [sys.executable, str(Path(drift.__file__)), "validate", "--output", str(output)]
    assert subprocess.run(command, capture_output=True).returncode == 0
    command[2] = "finalize"
    result = subprocess.run(command, capture_output=True)
    assert result.returncode == 1 and json.loads(result.stdout)["phase"] == "partial"


def test_semantically_valid_rehashed_source_edit_still_rejected(tmp_path):
    before, _, output, _ = compare(tmp_path)
    edit(before, "capture/parsed.json", title="Changed after comparison")
    with pytest.raises(drift.DriftError, match="Original capture evidence changed"):
        drift.validate(output)


def test_parser_schema_is_not_used_and_heading_order_is_significant(tmp_path):
    before, after, output = prepare(tmp_path)
    edit(before, "capture/parsed.json", schema=[{"fabricated": "schema"}], h2=["One", "Two"])
    edit(after, "capture/parsed.json", schema=[], h2=["Two", "One"])
    drift.compare(before, after, output)
    assert rows(output)["json_ld.block_count"]["status"] == "unchanged"
    assert rows(output)["document.h2"]["status"] == "changed"


def test_header_casing_and_order_do_not_make_false_change(tmp_path):
    before, after, output = prepare(tmp_path)
    edit(before, "capture/transport.json", headers={"X-Robots-Tag": "a", "x-robots-tag": "b"})
    edit(after, "capture/transport.json", headers={"X-ROBOTS-TAG": "b", "x-robots-tag": "a"})
    drift.compare(before, after, output)
    assert rows(output)["transport.headers.x_robots_tag"]["status"] == "unchanged"


def test_capture_artifact_duplicate_json_is_rejected_even_with_matching_hash(tmp_path):
    before, after, output = prepare(tmp_path)
    path = after / "capture/parsed.json"
    original = path.read_bytes()
    path.write_bytes(original.rstrip()[:-1] + b',"title":"duplicate"}')
    manifest_path = after / pilot.MANIFEST
    manifest = json.loads(manifest_path.read_bytes())
    manifest["artifacts"]["capture/parsed.json"] = drift.record(path)
    manifest_path.write_bytes(pilot.encode(manifest))
    with pytest.raises(drift.DriftError, match="Duplicate"):
        drift.compare(before, after, output)


def test_invalid_block_hash_rejected(tmp_path):
    html = HTML + '<script type="application/ld+json">{ invalid }</script>'
    before, after, output = prepare(tmp_path, html, html)
    schema = json.loads((after / "capture/schema.json").read_bytes())
    schema["blocks"][0]["sha256"] = "not-a-hash"
    edit(after, "capture/schema.json", **schema)
    with pytest.raises(drift.DriftError, match="block identity"):
        drift.compare(before, after, output)


def test_recorded_times_do_not_require_chronology(tmp_path):
    before, after, output = prepare(tmp_path)
    edit(before, "capture/transport.json", captured_at="2030-01-01T00:00:00+00:00")
    edit(after, "capture/transport.json", captured_at="2000-01-01T00:00:00+00:00")
    manifest = drift.compare(before, after, output)
    assert manifest["evidence"]["before"]["captured_at"].startswith("2030")
    assert drift.validate(output)["analysis"] == "complete"


def test_largest_allowed_native_text_can_be_escaped_and_finalized(tmp_path):
    _, _, output, manifest = compare(tmp_path)
    native(output, manifest, findings=[{"kind": "observation", "text": "!" * 4000,
                                       "comparisons": ["document.title"]}] * 100)
    assert drift.finalize(output)["complete"]
    assert drift.validate(output)["complete"]


@pytest.mark.parametrize("size,omitted", [(3000, False), (18000, True)])
def test_report_labels_preview_truncation_separately_from_value_omission(tmp_path, size, omitted):
    before, after, output = prepare(tmp_path)
    for root in (before, after):
        edit(root, "capture/parsed.json", title="x" * size)
    manifest = drift.compare(before, after, output)
    value = rows(output)["document.title"]["before"]
    assert value["preview_truncated"] is True
    assert value["truncated"] is omitted
    assert (value["value"] is None) is omitted
    native(output, manifest)
    drift.finalize(output)
    report = (output / "REPORT.md").read_text()
    assert "Before preview:" in report
    assert f"preview truncated: True; value omitted: {omitted}" in report
