"""Offline unit tests; no credentials, live requests or dependency installation."""
import contextlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import codex_pilot as pilot  # noqa: E402
import requests  # noqa: E402
import url_safety  # noqa: E402

HTML = b'''<!doctype html><html><head><title>Example</title>
<script type="application/ld+json">{"@context":"https://schema.org","@graph":[
{"@type":["WebPage","Thing"],"@id":"https://example.com/#page","publisher":{"@id":"https://example.com/#org"}},
{"@type":"Organization","@id":"https://example.com/#org"}]}</script>
</head><body><h1>Example</h1><a href="/about/">About</a></body></html>'''


class Response:
    def __init__(self, raw=HTML, status=200):
        self.raw = raw
        self.status_code = status
        self.headers = {"Content-Type": "text/html; charset=utf-8", "Set-Cookie": "never-record"}
        self.url = "https://example.com/"
        self.history = []
        self.closed = False

    def iter_content(self, chunk_size):
        for index in range(0, len(self.raw), chunk_size):
            yield self.raw[index:index + chunk_size]

    def close(self):
        self.closed = True


class PilotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir="/private/tmp" if Path("/private/tmp").is_dir() else None)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.fixture = self.root / "input.html"
        self.fixture.write_bytes(HTML)
        self.output = self.root / "out"
        self.env = patch.dict(os.environ, {"CLAUDE_SEO_LOCAL_TARGETS": ""})
        self.env.start()
        self.addCleanup(self.env.stop)

    def capture(self, fixture=None):
        return pilot.capture("https://example.com/", self.output, fixture or self.fixture)

    def role(self, role, status="complete", sha=None):
        if sha is None:
            sha = json.loads((self.output / pilot.MANIFEST).read_text())["capture"]["sha256"]
        value = {"role": role, "capture_sha256": sha, "status": status,
                 "findings": ["Observed title in capture/page.html."], "limitations": []}
        (self.output / "findings" / (role + ".json")).write_text(json.dumps(value))

    def test_fixture_preserves_bytes_and_shared_parse(self):
        with patch.object(url_safety, "safe_requests_session", side_effect=AssertionError("network")):
            manifest = self.capture()
        self.assertEqual((self.output / "capture/page.html").read_bytes(), HTML)
        self.assertEqual(manifest["capture"]["sha256"], pilot.digest(HTML))
        self.assertEqual(manifest["capture"]["representation"], "fixture")
        self.assertIn("python", manifest["runtime"])
        self.assertIsNone(json.loads((self.output / "capture/transport.json").read_text())["retrieved_at"])
        parsed = json.loads((self.output / "capture/parsed.json").read_text())
        self.assertEqual(parsed["title"], "Example")
        self.assertEqual(parsed["links"]["internal"][0]["href"], "https://example.com/about/")
        self.assertEqual(pilot.validate(self.output)["roles"], {"technical": "missing", "schema": "missing"})

    def test_schema_graph_arrays_and_refs(self):
        result = pilot.schema_check(HTML.decode(), "https://example.com/")
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["blocks"][0]["data"]["@graph"][0]["@type"], ["WebPage", "Thing"])
        self.assertEqual(result["unresolved_local_refs"], [])

    def test_bad_schema_block_is_retained_and_later_valid_block_runs(self):
        html = '<script type="application/ld+json">{broken</script>' + HTML.decode()
        result = pilot.schema_check(html, "https://example.com/")
        self.assertEqual(result["block_count"], 2)
        self.assertEqual(result["blocks"][0]["status"], "failed")
        self.assertEqual(result["blocks"][1]["status"], "passed")
        self.assertEqual(result["status"], "failed")

    def test_absent_source_schema_is_not_validation_pass(self):
        result = pilot.schema_check("<html><h1>No schema</h1></html>", "https://example.com/")
        self.assertEqual(result["status"], "skipped")
        self.assertEqual(result["block_count"], 0)

    def test_unresolved_reference_and_duplicate_id_are_warnings(self):
        html = HTML.decode().replace('"https://example.com/#org"}', '"https://example.com/#missing"}', 1)
        result = pilot.schema_check(html, "https://example.com/")
        self.assertEqual(result["status"], "warning")
        self.assertEqual(result["unresolved_local_refs"], ["https://example.com/#missing"])
        result = pilot.schema_check(HTML.decode() * 2, "https://example.com/")
        self.assertIn("https://example.com/#org", result["duplicate_ids"])

    def test_hostile_depth_is_bounded_before_generic_parser(self):
        raw = ('<script type="application/ld+json">' + '[' * 2000 + '0' + ']' * 2000 + '</script>').encode()
        self.fixture.write_bytes(raw)
        self.capture()
        result = json.loads((self.output / "capture/schema.json").read_text())
        self.assertEqual(result["status"], "failed")
        self.assertIn("depth", result["blocks"][0]["errors"][0])

    def test_hook_type_array_regression(self):
        spec = importlib.util.spec_from_file_location("hook_test", ROOT / "hooks/validate-schema.py")
        hook = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(hook)
        self.assertEqual(hook.validate_jsonld(HTML.decode()), [])
        self.assertTrue(any("HowTo" in item for item in hook.validate_jsonld(
            '<script type="application/ld+json">{"@context":"https://schema.org","@type":["Thing","HowTo"]}</script>')))

    def test_unsafe_url_and_local_allowlist_refused_before_output(self):
        for url in ("http://127.0.0.1/", "http://user:secret@example.com/", "file:///etc/passwd"):
            with self.assertRaises(pilot.PilotError):
                pilot.capture(url, self.output, self.fixture)
        with patch.dict(os.environ, {"CLAUDE_SEO_LOCAL_TARGETS": "example.com"}):
            with self.assertRaises(pilot.PilotError):
                self.capture()
        self.assertFalse(self.output.exists())

    def test_no_overwrite_or_symlink(self):
        self.capture()
        with self.assertRaises(pilot.PilotError):
            self.capture()
        link = self.root / "link"
        link.symlink_to(self.output, target_is_directory=True)
        with self.assertRaises(pilot.PilotError):
            pilot.validate(link)
        (self.output / "findings/technical.json").symlink_to(self.fixture)
        with self.assertRaises(pilot.PilotError):
            pilot.validate(self.output)

    def test_snapshot_tamper_and_path_escape_rejected(self):
        self.capture()
        (self.output / "capture/page.html").write_bytes(b"modified")
        with self.assertRaisesRegex(pilot.PilotError, "mismatch"):
            pilot.validate(self.output)
        with self.assertRaises(pilot.PilotError):
            pilot.child(self.output, "../escape")

    def test_missing_and_partial_roles_finalize_partial(self):
        self.capture()
        self.role("technical", "partial")
        result = pilot.finalize(self.output)
        self.assertFalse(result["complete"])
        self.assertEqual(result["phase"], "partial")
        self.assertIn("Result unavailable", (self.output / "REPORT.md").read_text())
        with self.assertRaises(pilot.PilotError):
            pilot.finalize(self.output)

    def test_complete_roles_finalize_and_hashes_include_report(self):
        self.capture()
        for role in pilot.ROLES:
            self.role(role)
        result = pilot.finalize(self.output)
        self.assertTrue(result["complete"])
        self.assertEqual(result["phase"], "complete")
        (self.output / "REPORT.md").write_text("tampered")
        with self.assertRaises(pilot.PilotError):
            pilot.validate(self.output)

    def test_extra_result_paths_do_not_expand_pilot_completion(self):
        self.capture()
        for role in ("content", "images", "local", "hreflang"):
            self.role(role)
            path = pilot.child(self.output, "findings/" + role + ".json")
            self.assertEqual(path.parent.name, "findings")
            self.assertEqual(pilot.role_result(self.output, role, pilot.digest(HTML))["role"], role)
        with self.assertRaises(pilot.PilotError):
            pilot.child(self.output, "findings/unknown.json")
        self.assertEqual(pilot.validate(self.output)["roles"], {"technical": "missing", "schema": "missing"})
        self.assertFalse(pilot.finalize(self.output)["complete"])

    def test_pilot_finalizes_original_pair_without_extra_results(self):
        self.capture()
        for role in pilot.ROLES:
            self.role(role)
        state = pilot.validate(self.output)
        self.assertEqual(set(state["roles"]), {"technical", "schema"})
        self.assertTrue(pilot.finalize(self.output)["complete"])
        report = (self.output / "REPORT.md").read_text()
        self.assertNotIn("Content", report)
        self.assertNotIn("Images", report)

    def test_role_capture_mismatch_and_shapes_refused(self):
        self.capture()
        self.role("technical", sha="0" * 64)
        with self.assertRaises(pilot.PilotError):
            pilot.finalize(self.output)
        self.role("technical")
        path = self.output / "findings/technical.json"
        data = json.loads(path.read_text())
        data["findings"] = [123]
        path.write_text(json.dumps(data))
        with self.assertRaises(pilot.PilotError):
            pilot.finalize(self.output)

    def test_http_failure_and_body_limit_are_partial_evidence(self):
        for status, raw in ((429, HTML), (200, b"a" * (pilot.MAX_BYTES + 1))):
            response = Response(raw, status)

            @contextlib.contextmanager
            def session(url, **kwargs):
                self.assertEqual(kwargs, {"trust_env": False})
                class Session:
                    def get(self, *args, **kwargs):
                        return response
                yield Session()

            with patch.object(url_safety, "safe_requests_session", session):
                out = self.root / str(status)
                manifest = pilot.capture("https://example.com/", out)
            self.assertFalse(manifest["capture"]["complete"])
            transport = json.loads((out / "capture/transport.json").read_text())
            self.assertNotIn("Set-Cookie", transport["headers"])
            self.assertTrue(response.closed)
            self.assertTrue(pilot.validate(out)["valid"])

    def test_network_failure_is_not_claimed_success(self):
        with patch.object(url_safety, "safe_requests_session", side_effect=requests.exceptions.SSLError("sensitive")):
            manifest = pilot.capture("https://example.com/", self.output)
        self.assertFalse(manifest["capture"]["complete"])
        transport = (self.output / "capture/transport.json").read_text()
        self.assertIn("SSLError", transport)
        self.assertNotIn("sensitive", transport)

    def test_session_disables_netrc_proxies_and_ca_discovery(self):
        with patch.object(url_safety, "validate_url_strict", return_value=("https://example.com/", "93.184.216.34")), \
             patch.object(url_safety, "_pin_dns", return_value=contextlib.nullcontext()), \
             patch.object(url_safety, "_validated_proxy_hosts", side_effect=AssertionError("proxy discovery")), \
             patch("requests.sessions.get_netrc_auth", side_effect=AssertionError("netrc discovery")), \
             patch.dict(os.environ, {"HTTPS_PROXY": "https://user:password@127.0.0.1", "REQUESTS_CA_BUNDLE": "/no/ca"}):
            with url_safety.safe_requests_session("https://example.com/", trust_env=False) as session:
                self.assertFalse(session.trust_env)
                prepared = session.prepare_request(requests.Request("GET", "https://example.com/"))
                self.assertNotIn("Authorization", prepared.headers)
                settings = session.merge_environment_settings(prepared.url, {}, None, None, None)
                self.assertEqual(settings["proxies"], {})
                self.assertTrue(settings["verify"])

    def test_doctor_does_not_load_network_or_auth(self):
        with patch.object(pilot, "modules", side_effect=AssertionError("runtime import")):
            self.assertTrue(pilot.doctor()["ready"])

    def test_staged_provenance_verifies_actual_copied_bytes(self):
        stage = self.root / "stage"
        stage.mkdir()
        (stage / "scripts").mkdir()
        data = b"staged source"
        (stage / "scripts/source.py").write_bytes(data)
        instructions = b"stage instructions"
        (stage / "AGENTS.md").write_bytes(instructions)
        manifest = {"format_version": 1, "source_baseline_ref": "baseline", "source_ref": None,
                    "files": [{"destination": "scripts/source.py", "sha256": pilot.digest(data), "bytes": len(data)}],
                    "generated_files": [{"destination": "AGENTS.md", "sha256": pilot.digest(instructions), "bytes": len(instructions)}]}
        (stage / "stage-manifest.json").write_text(json.dumps(manifest))
        with patch.object(pilot, "ROOT", stage):
            result = pilot.provenance()
            self.assertEqual(result["kind"], "staged-copy")
            self.assertIsNone(result["source_commit"])
            self.assertEqual(result["generated_files"], manifest["generated_files"])
            (stage / "AGENTS.md").write_bytes(b"changed")
            with self.assertRaises(pilot.PilotError):
                pilot.provenance()
            (stage / "AGENTS.md").write_bytes(instructions)
            (stage / "scripts/source.py").write_bytes(b"changed")
            with self.assertRaises(pilot.PilotError):
                pilot.provenance()

    def test_detached_and_worktree_git_identity(self):
        git = self.root / "gitdir"
        git.mkdir()
        sha = "a" * 40
        (git / "HEAD").write_text(sha + "\n")
        (self.root / ".git").write_text("gitdir: gitdir\n")
        with patch.object(pilot, "ROOT", self.root):
            self.assertEqual(pilot.source_commit(), sha)
            common = self.root / "common"
            (common / "refs/heads").mkdir(parents=True)
            (common / "refs/heads/pilot").write_text(sha + "\n")
            (git / "commondir").write_text("../common\n")
            (git / "HEAD").write_text("ref: refs/heads/pilot\n")
            self.assertEqual(pilot.source_commit(), sha)

    def test_finalized_partial_cannot_silently_accept_later_role(self):
        self.capture()
        self.role("technical")
        pilot.finalize(self.output)
        self.role("schema")
        with self.assertRaises(pilot.PilotError):
            pilot.validate(self.output)

    def test_actual_staged_cli_fixture_capture_and_validation(self):
        spec = importlib.util.spec_from_file_location("pilot_stager", ROOT / "scripts/stage_codex_pilot.py")
        stager = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(stager)
        staged = self.root / "staged"
        stager.stage_pilot(staged)
        env = {"PATH": os.defpath, "PYTHONNOUSERSITE": "1", "PYTHONDONTWRITEBYTECODE": "1"}
        command = [sys.executable, "-I", "-B", str(staged / "scripts/codex_pilot.py")]
        capture = subprocess.run(command + ["capture", "--url", "https://example.com/", "--html", str(self.fixture),
                                           "--output", str(self.output)], cwd=self.root, env=env,
                                 text=True, capture_output=True, timeout=30)
        self.assertEqual(capture.returncode, 0, capture.stderr)
        self.assertEqual(json.loads(capture.stdout)["provenance"]["kind"], "staged-copy")
        checked = subprocess.run(command + ["validate", "--output", str(self.output)], cwd=self.root, env=env,
                                 text=True, capture_output=True, timeout=30)
        self.assertEqual(checked.returncode, 0, checked.stderr)
        self.assertFalse(json.loads(checked.stdout)["complete"])

    def test_dense_deep_schema_remains_within_artifact_budget(self):
        nested = [0] * 180000
        for _ in range(50):
            nested = {"a": nested}
        data = {"@context": "https://schema.org", "@type": "Thing", "data": nested}
        raw = ('<script type="application/ld+json">' + json.dumps(data, separators=(",", ":")) + '</script>').encode()
        self.fixture.write_bytes(raw)
        manifest = self.capture()
        self.assertTrue(manifest["capture"]["complete"])
        self.assertLess((self.output / "capture/schema.json").stat().st_size, pilot.MAX_ARTIFACT_BYTES)
        self.assertTrue(pilot.validate(self.output)["valid"])
        schema = json.loads((self.output / "capture/schema.json").read_text())
        self.assertEqual(schema["blocks"][0]["data"], data)

    def test_serialized_schema_overflow_keeps_original_and_is_partial(self):
        data = {"@context": "https://schema.org", "@type": "Thing", "data": "0" * 1800}
        self.fixture.write_text('<script type="application/ld+json">' + json.dumps(data) + '</script>')
        with patch.object(pilot, "MAX_ARTIFACT_BYTES", 2200):
            manifest = self.capture()
            self.assertFalse(manifest["capture"]["complete"])
            self.assertEqual(manifest["checks"]["schema"], "failed")
            self.assertEqual((self.output / "capture/page.html").read_bytes(), self.fixture.read_bytes())
            self.assertTrue(pilot.validate(self.output)["valid"])

    def test_manifest_check_tamper_cannot_overstate_hashed_evidence(self):
        self.fixture.write_text('<script type="application/ld+json">broken</script>')
        self.capture()
        path = self.output / pilot.MANIFEST
        manifest = json.loads(path.read_text())
        manifest["checks"]["schema"] = "passed"
        path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(pilot.PilotError, "Schema check disagrees"):
            pilot.finalize(self.output)
        manifest["checks"]["schema"] = "failed"
        manifest["checks"]["transport"] = "failed"
        path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(pilot.PilotError, "Transport check disagrees"):
            pilot.validate(self.output)


if __name__ == "__main__":
    unittest.main()
