"""Offline contracts for bounded full crawls and specialist reservations."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('codex_full_audit_tests', ROOT / 'scripts/codex_full_audit.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)
SITE = 'https://audit.example/'


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    """Any accidental live provider/fetch use must fail this fixture suite."""
    monkeypatch.delenv('CLAUDE_SEO_LOCAL_TARGETS', raising=False)
    import fetch_page
    import render_page
    import requests
    def blocked(*args, **kwargs):
        pytest.fail('Offline full-audit test attempted a network fetch')
    monkeypatch.setattr(fetch_page, 'fetch_page', blocked)
    monkeypatch.setattr(render_page, 'render_page', blocked)
    monkeypatch.setattr(requests.sessions.Session, 'request', blocked)


@pytest.fixture
def planned(tmp_path):
    def make(pages=None, robots='', robots_status=200, max_pages=100, roles=None, max_workers=2):
        index = len(list(tmp_path.glob('fixtures-*.json')))
        fixture = tmp_path / f'fixtures-{index}.json'
        fixture.write_text(json.dumps({'pages': pages or {SITE: '<html><title>Home</title></html>'},
                                       'robots': robots, 'robots_status': robots_status}))
        root = tmp_path / f'audit-{index}'
        audit.plan(root, SITE, max_pages=max_pages, roles=roles or ['technical', 'content', 'schema'],
                   max_workers=max_workers, fixtures=fixture)
        return root
    return make


def findings(root, role, status='complete', notes=None, limitations=None):
    state = audit.load(root)
    value = {'role': role, 'site_sha256': state['site_sha256'], 'status': status,
             'findings': notes or ['Reviewed the frozen capture.'],
             'limitations': limitations or ([] if status == 'complete' else ['Work remains.'])}
    (root / 'findings' / f'{role}.json').write_bytes(audit.encode(value))


def finish(root, role, status='complete', **kwargs):
    audit.dispatch(root, 'start', role)
    findings(root, role, status, **kwargs)
    audit.dispatch(root, 'release', role)


def test_crawl_follows_only_same_origin_links_obeys_robots_and_deduplicates(planned):
    html = '''<html><a href="/about#one">about</a><a href="/about#two">duplicate</a>
    <a href="/blocked">blocked</a><a href="https://other.example/page">external</a>
    <a href="http://audit.example/http">different scheme</a><a href="mailto:x@example.com">mail</a>
    <a href="http://127.0.0.1/private">private</a></html>'''
    root = planned({SITE: html, SITE + 'about': '<title>About</title>'},
                   robots='User-agent: *\nDisallow: /blocked\n')
    result = audit.crawl(root)
    state = audit.load(root)
    assert result['status'] == 'complete'
    assert [page['url'] for page in state['pages']] == [SITE, SITE + 'about']
    assert state['excluded'] == [{'url': SITE + 'blocked', 'reason': 'robots.txt'}]
    assert state['queue'] == []
    assert state['site_sha256'] == audit.identity(state)
    for page in state['pages']:
        assert page['representation'] == 'fixture'
        assert f"{page['path']}/raw.html" in state['files']
        assert f"{page['path']}/parsed.json" in state['files']


def test_page_cap_freezes_remaining_queue_and_is_idempotent(planned):
    root = planned({SITE: '<a href="/next">Next</a>', SITE + 'next': 'next'}, max_pages=1)
    result = audit.crawl(root)
    assert result['status'] == 'page-limit' and result['remaining'] == 1
    before = (root / audit.MANIFEST).read_bytes()
    assert audit.crawl(root)['site_sha256'] == result['site_sha256']
    assert (root / audit.MANIFEST).read_bytes() == before


@pytest.mark.parametrize('status', [429, 500, 503])
def test_unavailable_robots_pauses_without_fetching_pages(planned, status):
    root = planned(robots_status=status)
    with pytest.raises(audit.AuditError, match='robots'):
        audit.crawl(root)
    state = audit.load(root)
    assert state['crawl_status'] == 'paused' and state['pages'] == []
    assert state['site_sha256'] is None
    assert not list((root / 'crawl/pages').iterdir())


def test_disallowed_site_is_frozen_without_page_capture(planned):
    root = planned(robots_status=403)
    result = audit.crawl(root)
    assert result['pages'] == 0 and result['excluded'] == 1
    assert audit.report(root)['status'] == 'partial'


def test_transient_robots_failure_can_resume_and_preserves_failed_evidence(tmp_path, monkeypatch):
    import fetch_page
    import render_page
    root = tmp_path / 'retry'
    audit.plan(root, SITE, roles=['technical'])
    replies = iter([{'status_code': 503, 'content': '', 'error': None},
                    {'status_code': 200, 'content': 'User-agent: *\nAllow: /', 'error': None}])
    monkeypatch.setattr(fetch_page, 'fetch_page', lambda *a, **kw: next(replies))
    monkeypatch.setattr(render_page, 'render_page', lambda *a, **kw: {
        'url': SITE, 'status_code': 200, 'content': '<title>Okay</title>', 'error': None})
    with pytest.raises(audit.AuditError, match='robots'):
        audit.crawl(root)
    assert audit.crawl(root)['status'] == 'complete'
    state = audit.load(root)
    assert 'resources/robots-attempt-001.json' in state['files']
    assert json.loads((root / 'resources/robots-attempt-001.json').read_text(encoding="utf-8"))['status_code'] == 503


def test_cannot_finalize_invented_capture_citation(planned):
    root = planned(roles=['technical'])
    audit.crawl(root)
    audit.dispatch(root, 'start', 'technical')
    findings(root, 'technical', notes=['Claim from crawl/pages/p999-invented/raw.html.'])
    with pytest.raises(audit.AuditError, match='cited missing'):
        audit.dispatch(root, 'release', 'technical')


@pytest.mark.parametrize('target', ['http://127.0.0.1/', 'http://169.254.169.254/',
                                    'https://user:password@public.example/', 'file:///etc/passwd'])
def test_plan_rejects_private_credentialed_and_non_http_urls(tmp_path, target):
    with pytest.raises((audit.AuditError, ValueError)):
        audit.plan(tmp_path / 'audit', target)
    assert not (tmp_path / 'audit').exists()


def test_local_target_override_is_not_accepted(tmp_path, monkeypatch):
    monkeypatch.setenv('CLAUDE_SEO_LOCAL_TARGETS', 'localhost:8000')
    with pytest.raises(audit.AuditError, match='overrides'):
        audit.plan(tmp_path / 'audit', SITE)


def test_capture_artifact_tamper_is_rejected_before_dispatch(planned):
    root = planned()
    audit.crawl(root)
    state = audit.load(root)
    raw = root / state['pages'][0]['path'] / 'raw.html'
    raw.write_text('tampered')
    with pytest.raises(audit.AuditError, match='evidence changed'):
        audit.dispatch(root, 'next', available_slots=2)


def test_config_and_frozen_page_manifest_tamper_are_rejected(planned):
    root = planned()
    audit.crawl(root)
    original = (root / audit.MANIFEST).read_bytes()
    state = json.loads(original)
    state['config']['max_pages'] = 500
    (root / audit.MANIFEST).write_bytes(audit.encode(state))
    with pytest.raises(audit.AuditError, match='configuration changed'):
        audit.load(root)
    state = json.loads(original)
    state['pages'][0]['status'] = 'invented'
    (root / audit.MANIFEST).write_bytes(audit.encode(state))
    with pytest.raises(audit.AuditError, match='Frozen crawl changed'):
        audit.load(root)


def test_manifest_json_duplicate_keys_and_nonfinite_values_are_rejected():
    for raw in (b'{"a": 1, "a": 2}', b'{"value": NaN}', b'{"value": Infinity}'):
        with pytest.raises(audit.AuditError):
            audit.decode(raw)


def test_specialists_require_frozen_crawl_and_at_most_two_reservations(planned):
    root = planned()
    with pytest.raises(audit.AuditError, match='freeze'):
        audit.dispatch(root, 'start', 'technical')
    audit.crawl(root)
    jobs = audit.dispatch(root, 'next', available_slots=20)
    assert len(jobs['tasks']) == 2
    audit.dispatch(root, 'start', 'technical')
    audit.dispatch(root, 'start', 'content')
    assert audit.dispatch(root, 'next', available_slots=20)['tasks'] == []
    with pytest.raises(audit.AuditError, match='capacity'):
        audit.dispatch(root, 'start', 'schema')
    assert set(audit.load(root)['tasks']) == {'technical', 'content', 'schema'}


def test_partial_result_retains_slot_until_release_and_retry_is_explicit(planned):
    root = planned()
    audit.crawl(root)
    audit.dispatch(root, 'start', 'technical')
    findings(root, 'technical', 'partial')
    partial = audit.dispatch(root, 'reconcile')
    assert partial['active'] == ['technical']
    assert partial['statuses']['technical'] == 'partial'
    audit.dispatch(root, 'release', 'technical')
    assert 'technical' not in [job['task'] for job in audit.dispatch(root, 'next', available_slots=2)['tasks']]
    with pytest.raises(audit.AuditError, match='resume-incomplete'):
        audit.dispatch(root, 'start', 'technical')
    audit.dispatch(root, 'start', 'technical', resume_incomplete=True)
    assert audit.load(root)['tasks']['technical']['starts'] == 2
    findings(root, 'technical', 'complete')
    audit.dispatch(root, 'release', 'technical')
    assert audit.load(root)['tasks']['technical']['final_sha256']
    with pytest.raises(audit.AuditError, match='finalized'):
        audit.dispatch(root, 'start', 'technical', resume_incomplete=True)


def test_complete_findings_do_not_free_slot_until_release(planned):
    root = planned()
    audit.crawl(root)
    audit.dispatch(root, 'start', 'technical')
    findings(root, 'technical')
    state = audit.dispatch(root, 'reconcile')
    assert state['active'] == ['technical']
    assert audit.report(root)['status'] == 'partial'
    audit.dispatch(root, 'release', 'technical')
    assert not audit.load(root)['tasks']['technical']['active']


def test_unavailable_specialist_is_terminal_and_report_stays_unmeasured(planned):
    root = planned(roles=['technical', 'performance'])
    audit.crawl(root)
    finish(root, 'technical')
    finish(root, 'performance', 'unavailable', limitations=['No field metrics are configured.'])
    report = audit.report(root)
    assert report['status'] == 'partial'
    data = json.loads((root / 'audit-data.json').read_text(encoding="utf-8"))
    assert data['summary']['health_score'] is None
    assert {c['name']: c['status'] for c in data['categories']} == {'technical': 'complete', 'performance': 'unavailable'}
    assert all(c['score'] is None for c in data['categories'])
    assert audit.dispatch(root, 'next', available_slots=2, resume_incomplete=True)['tasks'] == []


def test_finalized_findings_and_cited_evidence_cannot_be_changed(planned):
    root = planned(roles=['technical'])
    audit.crawl(root)
    evidence = root / 'evidence/technical.txt'
    evidence.write_text('checked')
    finish(root, 'technical', notes=['Observed evidence/technical.txt'])
    evidence.write_text('changed')
    with pytest.raises(audit.AuditError, match='evidence changed'):
        audit.report(root)
    evidence.write_text('checked')
    findings(root, 'technical', notes=['Changed conclusion'])
    with pytest.raises(audit.AuditError, match='Finalized findings changed'):
        audit.report(root)


def test_complete_audit_requires_all_specialists_finished_and_all_pages_available(planned):
    root = planned(roles=['technical'])
    audit.crawl(root)
    finish(root, 'technical')
    assert audit.report(root)['status'] == 'complete'
    data = json.loads((root / 'audit-data.json').read_text(encoding="utf-8"))
    assert data['summary']['fixture_mode'] is True
    assert data['summary']['health_score'] is None


def test_truncated_crawl_cannot_be_reported_as_complete(planned):
    root = planned({SITE: '<a href="/next">Next</a>', SITE + 'next': 'Next'}, max_pages=1, roles=['technical'])
    audit.crawl(root)
    finish(root, 'technical')
    assert audit.report(root)['status'] == 'partial'


def test_deleted_finalized_findings_are_tamper_not_missing_work(planned):
    root = planned(roles=['technical'])
    audit.crawl(root)
    finish(root, 'technical')
    (root / 'findings/technical.json').unlink()
    with pytest.raises((audit.AuditError, audit.pilot.PilotError, OSError)):
        audit.report(root)


def test_injected_task_key_is_rejected_even_with_unchanged_frozen_crawl(planned):
    root = planned(roles=['technical'])
    audit.crawl(root)
    state = json.loads((root / audit.MANIFEST).read_bytes())
    state['tasks']['unexpected-role'] = {'active': False, 'starts': 0, 'status': 'pending',
                                          'final_sha256': None, 'evidence': {}}
    (root / audit.MANIFEST).write_bytes(audit.encode(state))
    with pytest.raises((audit.AuditError, audit.pilot.PilotError, ValueError)):
        audit.dispatch(root, 'next', available_slots=2)


def test_cross_origin_redirect_is_unavailable_and_does_not_expand_scope(planned):
    root = planned({SITE: {'url': 'https://other.example/', 'content': '<a href="/foreign">foreign</a>'}},
                   roles=['technical'])
    result = audit.crawl(root)
    state = audit.load(root)
    assert result['pages'] == 1
    assert state['pages'][0]['status'] == 'unavailable'
    assert state['queue'] == []
    finish(root, 'technical')
    assert audit.report(root)['status'] == 'partial'


def test_non_html_response_is_unavailable_case_insensitively(planned):
    root = planned({SITE: {'content': 'fake PDF bytes', 'headers': {'Content-Type': 'application/pdf'}}})
    audit.crawl(root)
    assert audit.load(root)['pages'][0]['status'] == 'unavailable'


def test_raw_and_rendered_representations_are_frozen_separately(planned):
    root = planned({SITE: {'content': '<h1>Rendered content</h1>', 'raw_content': '<div id="root"></div>',
                          'mode_used': 'rendered'}})
    audit.crawl(root)
    state = audit.load(root)
    prefix = state['pages'][0]['path']
    assert (root / prefix / 'raw.html').read_text(encoding="utf-8") == '<div id="root"></div>'
    assert (root / prefix / 'rendered.html').read_text(encoding="utf-8") == '<h1>Rendered content</h1>'
    assert f'{prefix}/raw.html' in state['files']
    assert f'{prefix}/rendered.html' in state['files']


def test_page_representation_limit_pauses_before_artifact_creation(planned, monkeypatch):
    root = planned({SITE: 'x' * 100})
    monkeypatch.setattr(audit, 'MAX_PAGE', 20)
    with pytest.raises(audit.AuditError, match='size limit'):
        audit.crawl(root)
    state = audit.load(root)
    assert state['crawl_status'] == 'paused' and state['pages'] == []
    assert not list((root / 'crawl/pages').iterdir())


def test_captured_artifact_symlink_is_rejected(planned, tmp_path):
    root = planned()
    audit.crawl(root)
    state = audit.load(root)
    raw = root / state['pages'][0]['path'] / 'raw.html'
    external = tmp_path / 'external.txt'
    external.write_bytes(raw.read_bytes())
    raw.unlink()
    try:
        raw.symlink_to(external)
    except OSError:
        pytest.skip('Symlinks are unavailable for this account')
    with pytest.raises(audit.pilot.PilotError, match='Symlink'):
        audit.load(root)


@pytest.mark.parametrize("suffix", [".md", ".json"])
def test_historical_report_snapshot_tamper_is_rejected(planned, suffix):
    root = planned(roles=['technical'])
    audit.crawl(root)
    finish(root, 'technical')
    written = audit.report(root)
    (root / written['snapshot']).with_suffix(suffix).write_text('changed historical report')
    with pytest.raises((audit.AuditError, audit.pilot.PilotError, ValueError)):
        audit.report(root)


def test_empty_raw_response_is_not_replaced_by_rendered_dom(planned):
    root = planned({SITE: {"raw_content": "", "content": "<html><title>Rendered</title></html>", "mode_used": "rendered"}})
    audit.crawl(root)
    page = audit.load(root)["pages"][0]
    assert (root / page["path"] / "raw.html").read_text(encoding="utf-8") == ""
    assert "Rendered" in (root / page["path"] / "rendered.html").read_text(encoding="utf-8")
