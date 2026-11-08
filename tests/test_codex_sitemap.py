"""Saved XML analysis and evidence lifecycle; all fixtures stay offline."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import codex_pilot as pilot  # noqa: E402
import codex_sitemap as sitemap  # noqa: E402

AT = "2026-11-08T12:00:00+00:00"
URL = "https://example.com/sitemap.xml"


def xml(body, kind="urlset"):
    return f'<{kind} xmlns="{sitemap.NS}">{body}</{kind}>'.encode()


def analyze(body, kind="urlset", url=URL):
    return sitemap.analyze(xml(body, kind), url, AT, [])


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.delenv("CLAUDE_SEO_LOCAL_TARGETS", raising=False)
    monkeypatch.setattr("socket.getaddrinfo", lambda *a, **kw: pytest.fail("Unexpected DNS request"))
    monkeypatch.setattr("requests.sessions.Session.request", lambda *a, **kw: pytest.fail("Unexpected HTTP request"))


def capture(tmp_path, raw=None, refs=None):
    source = tmp_path / "input.xml"
    source.write_bytes(raw if raw is not None else xml("<url><loc>https://example.com/</loc></url>"))
    output = tmp_path / "output"
    manifest = sitemap.capture(source, URL, output, refs)
    return source, output, manifest


def role(output, manifest, status="complete"):
    value = {"role": "sitemap", "capture_sha256": manifest["evidence"]["source"]["sha256"],
             "evidence_sha256": manifest["evidence_sha256"], "status": status,
             "findings": ["Saved sitemap reviewed."], "limitations": list(sitemap.LIMITATIONS)}
    (output / "findings/sitemap.json").write_bytes(pilot.encode(value))
    return value


def test_urlset_totals_and_google_ignored_fields():
    result = analyze("<url><loc>https://example.com/one</loc><lastmod>2024</lastmod>"
                     "<priority>anything</priority><changefreq>daily</changefreq></url>"
                     "<url><loc>https://example.com/one</loc></url>")
    assert result["status"] == "complete"
    assert result["totals"]["entries"] == 2
    assert result["totals"]["unique_locations"] == 1
    assert result["totals"]["duplicate_locations"] == 1
    assert result["checks"]["google_ignored"] == {"priority": 1, "changefreq": 1}
    assert result["checks"]["lastmod"] == {"syntax_and_calendar": {"valid": 1}, "accuracy": "unverified"}
    assert result["checks"]["structure"] == "valid"


@pytest.mark.parametrize("value", ["2024", "2024-02", "2024-02-29", "2024-02-29T12:30Z",
    "2024-02-29T12:30+05:30", "2024-02-29T12:30:59Z", "2024-02-29T12:30:59.123456789-04:00"])
def test_w3c_date_profiles(value):
    result = analyze(f"<url><loc>https://example.com/</loc><lastmod>{value}</lastmod></url>")
    assert result["entries"][0]["lastmod"][0]["status"] == "valid"


@pytest.mark.parametrize("value", ["2023-02-29", "2024-13", "0000", "2024-01-01T12:00",
    "2024-01-01 12:00Z", "2024-01-01T24:00Z", "2024-01-01T12:60Z", "2024-01-01T12:00:60Z",
    "2024-01-01T12:00:01+25:00", "2024-01-01T12:00+01:99", " 2024-01-01", "2024-01-01T12:00.1Z"])
def test_invalid_date_profiles(value):
    result = analyze(f"<url><loc>https://example.com/</loc><lastmod>{value}</lastmod></url>")
    assert result["entries"][0]["lastmod"][0]["status"] == "invalid"


@pytest.mark.parametrize("value", ["2027", "2026-12", "2026-11-09", "2026-11-08T12:01Z"])
def test_future_dates(value):
    assert analyze(f"<url><loc>https://example.com/</loc><lastmod>{value}</lastmod></url>")["issue_counts"]["lastmod_future"] == 1


@pytest.mark.parametrize("value", ["/relative", "http://localhost/", "http://127.0.0.1/", "http://2130706433/",
    "http://169.254.169.254/", "http://[::1]/", "http://user:pass@example.com/", "https://example.com/#fragment",
    "https://example.com:bad/", "https://example.com:99999/", "https://example.com/%XZ", " https://example.com/", "https://example.com/a b", "https://example.com/a\\b",
    "ftp://example.com/file", "https://example.com/" + "x" * 2048])
def test_invalid_locations_are_flagged_without_lookup(value):
    result = analyze(f"<url><loc>{value}</loc></url>")
    assert result["status"] == "complete"
    assert result["checks"]["locations"] == "invalid"
    assert result["issue_counts"]["loc_url"] == 1


def test_loc_structure_namespace_and_extensions():
    result = analyze('<url><loc>https://example.com/<part/></loc></url>'
                     '<url><loc>https://example.com/</loc><loc>https://example.com/two</loc></url>'
                     '<url><loc xmlns="">https://example.com/three</loc></url>'
                     '<bogus/><url><loc>https://example.com/four</loc>'
                     '<image:image xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">'
                     '<image:loc>https://cdn.example.com/a.jpg</image:loc></image:image></url>')
    assert result["status"] == "complete"
    assert result["totals"]["entries"] == 4
    assert result["totals"]["valid_locations"] == 1
    assert result["issue_counts"]["loc_text"] == 1
    assert result["issue_counts"]["loc_count"] == 2
    assert result["issue_counts"]["root_child"] == 1
    assert result["extensions"] == ["http://www.google.com/schemas/sitemap-image/1.1"]
    assert result["checks"]["structure"] == "invalid"


def test_comments_and_processing_instructions_do_not_hide_text():
    result = analyze('<!-- note -->hidden<?test instruction?>more'
                     '<url><!-- note -->hidden<loc>https://example.com/</loc><?test instruction?>more</url>')
    assert result["issue_counts"]["root_text"] == 2
    assert result["issue_counts"]["entry_text"] == 2
    assert result["checks"]["structure"] == "invalid"


def test_declared_extension_namespaces_are_reported_even_when_unused():
    raw = (f'<urlset xmlns="{sitemap.NS}" xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">'
           '<url><loc>https://example.com/</loc></url></urlset>').encode()
    result = sitemap.analyze(raw, URL, AT, [])
    assert result["extensions"] == ["http://www.google.com/schemas/sitemap-image/1.1"]


@pytest.mark.parametrize("raw", [b"<urlset/>", b'<urlset xmlns="wrong"/>',
    b'<rss/>', b'<sitemapindex xmlns="wrong"/>', b"<urlset>",
    b'<!DOCTYPE urlset><urlset/>', b'<html/>'])
def test_unsupported_or_invalid_xml_stays_truthful_partial(tmp_path, raw):
    _, output, manifest = capture(tmp_path, raw)
    assert manifest["evidence"]["analysis_status"] == "partial"
    assert sitemap.validate(output)["valid"] is True
    role(output, manifest)
    assert sitemap.finalize(output)["phase"] == "partial"
    assert (output / "source.xml").read_bytes() == raw
    assert (output / "REPORT.md").exists()


@pytest.mark.parametrize("encoding", ["utf-8", "utf-16", "utf-16-be", "utf-32"])
def test_doctype_entity_and_xinclude_are_inert_and_partial(encoding):
    raw = ('<?xml version="1.0"?><!DOCTYPE urlset [<!ENTITY stolen SYSTEM "file:///etc/passwd">]>'
           f'<urlset xmlns="{sitemap.NS}"><url><loc>&stolen;</loc></url></urlset>').encode(encoding)
    result = sitemap.analyze(raw, URL, AT, [])
    assert result["status"] == "partial"
    assert result["checks"]["xml"] == "invalid"
    assert result["totals"]["entries"] == 0
    included = f'<urlset xmlns="{sitemap.NS}" xmlns:xi="http://www.w3.org/2001/XInclude"><xi:include href="https://example.com/"/></urlset>'.encode()
    assert sitemap.analyze(included, URL, AT, [])["checks"]["xml"] == "invalid"


def test_utf16_sitemap_and_empty_sitemap():
    raw = xml("<url><loc>https://example.com/</loc></url>").decode().encode("utf-16")
    parsed = sitemap.analyze(raw, URL, AT, [])
    assert parsed["totals"]["entries"] == 1
    assert parsed["checks"]["encoding"] == "invalid"
    assert parsed["status"] == "complete"
    result = analyze("")
    assert result["status"] == "complete"
    assert result["issue_counts"]["empty_sitemap"] == 1


def test_cross_host_and_directory_are_verification_findings():
    result = analyze("<url><loc>https://cdn.example.com/a</loc></url>"
                     "<url><loc>https://example.com/a</loc></url>", url="https://example.com/maps/sitemap.xml")
    assert result["checks"]["locations"] == "valid"
    assert result["checks"]["structure"] == "valid"
    assert {item["severity"] for item in result["issues"]} == {"verification"}
    assert result["issue_counts"]["cross_host"] == 1
    assert result["issue_counts"]["outside_directory"] == 1


def test_full_scan_counts_with_bounded_examples_and_protocol_limit():
    result = analyze("<url><loc>https://example.com/</loc></url>" * 50001)
    assert result["totals"]["entries"] == 50001
    assert result["totals"]["duplicate_locations"] == 50000
    assert result["issue_counts"]["entry_limit"] == 1
    assert result["checks"]["entry_limit"] == "invalid"
    assert len(result["entries"]) == 200
    assert len(result["issues"]) == 100
    assert result["entries_truncated"] and result["issues_truncated"]


def test_complete_lifecycle_requires_matching_native_result(tmp_path):
    source, output, manifest = capture(tmp_path)
    raw = source.read_bytes()
    assert not sitemap.validate(output)["complete"]
    role(output, manifest)
    assert sitemap.validate(output)["complete"]
    check = sitemap.finalize(output)
    assert check["phase"] == "complete"
    saved = json.loads((output / sitemap.MANIFEST).read_bytes())
    assert saved["evidence"] == manifest["evidence"]
    assert saved["evidence_sha256"] == manifest["evidence_sha256"]
    assert source.read_bytes() == raw
    with pytest.raises(sitemap.SitemapError, match="already finalized"):
        sitemap.finalize(output)


def test_invalid_structure_can_have_complete_analysis_and_review(tmp_path):
    _, output, manifest = capture(tmp_path, xml("<url><loc>/relative</loc></url>"))
    analysis = json.loads((output / "analysis.json").read_bytes())
    assert analysis["status"] == "complete" and analysis["checks"]["locations"] == "invalid"
    role(output, manifest)
    assert sitemap.finalize(output)["complete"]


def test_finalized_findings_are_immutable(tmp_path):
    _, output, manifest = capture(tmp_path)
    result = role(output, manifest)
    sitemap.finalize(output)
    result["findings"] = ["Changed after finalization."]
    (output / "findings/sitemap.json").write_bytes(pilot.encode(result))
    with pytest.raises(sitemap.SitemapError, match="Finalized sitemap artifact"):
        sitemap.validate(output)


@pytest.mark.parametrize("target", ["source", "source.xml", "analysis.json", "manifest", "role", "report"])
def test_tamper_rejected(tmp_path, target):
    source, output, manifest = capture(tmp_path)
    result = role(output, manifest)
    if target == "report":
        sitemap.finalize(output)
        (output / "REPORT.md").write_text("changed")
    elif target == "manifest":
        manifest["evidence"]["sitemap_url"] = "https://changed.example.com/"
        (output / sitemap.MANIFEST).write_bytes(pilot.encode(manifest))
    elif target == "role":
        result["evidence_sha256"] = "0" * 64
        (output / "findings/sitemap.json").write_bytes(pilot.encode(result))
    else:
        path = source if target == "source" else output / target
        path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(sitemap.SitemapError):
        sitemap.validate(output)


@pytest.mark.parametrize("target", ["provenance", "total_type", "entry_type", "manifest_version"])
def test_rehashed_metadata_cannot_change_analysis_or_provenance(tmp_path, target):
    _, output, manifest = capture(tmp_path)
    if target == "provenance":
        manifest["evidence"]["provenance"] = {}
    elif target == "manifest_version":
        manifest["schema_version"] = True
    else:
        path = output / "analysis.json"
        analysis = json.loads(path.read_bytes())
        if target == "total_type":
            analysis["totals"]["entries"] = True
        else:
            analysis["entries"][0]["index"] = 1.0
        path.write_bytes(pilot.encode(analysis))
        manifest["evidence"]["artifacts"]["analysis.json"] = sitemap.file_record(path)
    manifest["evidence_sha256"] = pilot.digest(pilot.encode(manifest["evidence"], compact=True))
    (output / sitemap.MANIFEST).write_bytes(pilot.encode(manifest))
    with pytest.raises(sitemap.SitemapError):
        sitemap.validate(output)


def test_finalized_role_addition_and_edits_are_rejected(tmp_path):
    _, output, manifest = capture(tmp_path)
    sitemap.finalize(output)
    role(output, manifest)
    with pytest.raises(sitemap.SitemapError, match="completion or role changed"):
        sitemap.validate(output)


def test_reject_symlinks_reused_output_relative_paths_and_large_input(tmp_path):
    source, output, _ = capture(tmp_path)
    with pytest.raises(sitemap.SitemapError, match="fresh directory"):
        sitemap.capture(source, URL, output)
    link = tmp_path / "link.xml"
    link.symlink_to(source)
    with pytest.raises(sitemap.SitemapError, match="Symlink"):
        sitemap.capture(link, URL, tmp_path / "linked-output")
    with pytest.raises(sitemap.SitemapError, match="absolute"):
        sitemap.capture(Path("input.xml"), URL, tmp_path / "relative-output")
    oversized = tmp_path / "oversized.xml"
    oversized.write_bytes(b" " * (sitemap.MAX_XML + 1))
    with pytest.raises(sitemap.SitemapError, match="5 MiB adapter bound.*50 MiB"):
        sitemap.capture(oversized, URL, tmp_path / "large-output")
    assert not (tmp_path / "large-output").exists()
    (output / "analysis.json").unlink()
    (output / "analysis.json").symlink_to(source)
    with pytest.raises(sitemap.SitemapError, match="Symlink"):
        sitemap.validate(output)


@pytest.mark.parametrize("name,raw", [("robots.txt", b"User-agent: *\n"), ("map.xml.gz", b"fake"),
    ("map.xml", b"\x1f\x8btest")])
def test_compressed_and_robots_inputs_refused(tmp_path, name, raw):
    source = tmp_path / name
    source.write_bytes(raw)
    with pytest.raises(sitemap.SitemapError, match="compressed|robots"):
        sitemap.capture(source, URL, tmp_path / "output")
    assert not (tmp_path / "output").exists()


def make_page(tmp_path):
    fixture = tmp_path / "fixture.html"
    fixture.write_text("<html><head><title>Saved</title></head><body>Saved page</body></html>")
    root = tmp_path / "page"
    pilot.capture("https://example.com/requested", root, fixture)
    return root


def test_optional_page_membership_preserves_fixture_provenance(tmp_path):
    page = make_page(tmp_path)
    _, output, manifest = capture(tmp_path, xml("<url><loc>https://example.com/requested</loc></url>"), [page])
    analysis = json.loads((output / "analysis.json").read_bytes())
    ref = analysis["page_captures"][0]
    assert ref["requested_url_membership"] is True and ref["final_url_membership"] is True
    assert ref["representation"] == "fixture"
    assert ref["capture_sha256"] == manifest["evidence"]["page_captures"][0]["capture_sha256"]
    assert sitemap.validate(output)["valid"]
    path = page / pilot.MANIFEST
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(sitemap.SitemapError, match="Page capture"):
        sitemap.validate(output)


def test_index_does_not_claim_page_membership_or_follow_children(tmp_path):
    page = make_page(tmp_path)
    _, output, _ = capture(tmp_path, xml("<sitemap><loc>https://example.com/requested</loc></sitemap>", "sitemapindex"), [page])
    analysis = json.loads((output / "analysis.json").read_bytes())
    assert analysis["status"] == "complete" and analysis["kind"] == "sitemapindex"
    assert analysis["page_captures"][0]["final_url_membership"] == "unavailable"
    assert analysis["totals"]["entries"] == 1


def test_page_requested_and_final_urls_use_exact_membership(tmp_path):
    page = make_page(tmp_path)
    ref = sitemap.page_reference(page)
    ref["final_url"] = "https://example.com/requested/"
    analysis = sitemap.analyze(xml("<url><loc>https://example.com/requested</loc></url>"), URL, AT, [ref])
    assert analysis["page_captures"][0]["requested_url_membership"] is True
    assert analysis["page_captures"][0]["final_url_membership"] is False


def test_page_capture_limits_and_failure_refused_before_output(tmp_path):
    page = make_page(tmp_path)
    source = tmp_path / "input.xml"
    source.write_bytes(xml(""))
    with pytest.raises(sitemap.SitemapError, match="five"):
        sitemap.capture(source, URL, tmp_path / "output", [page] * 6)
    with pytest.raises(sitemap.SitemapError, match="distinct"):
        sitemap.capture(source, URL, tmp_path / "output", [page] * 2)
    path = page / pilot.MANIFEST
    manifest = json.loads(path.read_bytes())
    manifest["capture"]["complete"] = False
    path.write_bytes(pilot.encode(manifest))
    with pytest.raises(sitemap.SitemapError):
        sitemap.capture(source, URL, tmp_path / "output", [page])
    assert not (tmp_path / "output").exists()


def test_isolated_cli_partial_capture_validate_and_finalize(tmp_path):
    source = tmp_path / "input.xml"
    source.write_bytes(b"<html/>")
    output = tmp_path / "output"
    command = [sys.executable, "-I", "-B", sitemap.__file__]
    result = subprocess.run(command + ["capture", "--xml", str(source), "--sitemap-url", URL, "--output", str(output)],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 1, result.stderr
    assert json.loads(result.stdout)["evidence"]["analysis_status"] == "partial"
    result = subprocess.run(command + ["validate", "--output", str(output)], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    result = subprocess.run(command + ["finalize", "--output", str(output)], capture_output=True, text=True, timeout=10)
    assert result.returncode == 1, result.stderr
    assert json.loads(result.stdout)["phase"] == "partial"
    assert (output / "REPORT.md").is_file()


def test_oversized_role_array_is_rejected(tmp_path):
    _, output, manifest = capture(tmp_path)
    result = role(output, manifest)
    result["findings"] = ["x"] * 201
    (output / "findings/sitemap.json").write_bytes(pilot.encode(result))
    with pytest.raises(sitemap.SitemapError, match="findings"):
        sitemap.validate(output)


def test_local_target_override_is_refused(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_SEO_LOCAL_TARGETS", "localhost:3000")
    with pytest.raises(sitemap.SitemapError, match="Unset"):
        sitemap.capture(tmp_path / "anything.xml", "http://localhost:3000/", tmp_path / "output")
