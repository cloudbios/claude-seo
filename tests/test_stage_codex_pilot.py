"""Offline staging safety and provenance; no real installs or credentials."""

import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "stage_codex_pilot.py"
SPEC = importlib.util.spec_from_file_location("stage_codex_pilot", SCRIPT)
stage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stage)


class StagePilotTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name).resolve()
        self.source = self.base / "source tree"
        self.source.mkdir()
        for source, _ in stage.COPY_FILES:
            path = self.source / source
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"fixture for {source}\n", encoding="utf-8")
        (self.source / "AGENTS.md").write_text("UNBOUNDED UPSTREAM GUIDANCE")
        (self.source / "secret-config.json").write_text("never copied")
        self.output = self.base / "staged pilot with spaces"

    def test_exact_subset_spaces_manifest_and_no_global_writes(self):
        fake_home = self.base / "untouched home"
        fake_home.mkdir()
        (fake_home / "keep").write_text("original")
        with mock.patch.dict("os.environ", {"HOME": str(fake_home), "USERPROFILE": str(fake_home)}):
            manifest = stage.stage_pilot(self.output, source_root=self.source, source_ref="test-ref")
        # Independent contract: an added auth/config helper must fail this test
        # even if COPY_FILES and the emitted manifest agree with one another.
        expected = {
            ".agents/skills/seo-codex-pilot/SKILL.md",
            ".codex/agents/seo-codex-technical.toml",
            ".codex/agents/seo-codex-schema.toml",
            "scripts/codex_pilot.py",
            "scripts/url_safety.py",
            "scripts/parse_html.py",
            "hooks/validate-schema.py",
            "LICENSE",
            "AGENTS.md",
            "stage-manifest.json",
        }
        actual = {p.relative_to(self.output).as_posix() for p in self.output.rglob("*") if p.is_file()}
        self.assertEqual(actual, expected)
        self.assertEqual([p.name for p in fake_home.iterdir()], ["keep"])
        self.assertEqual((fake_home / "keep").read_text(), "original")
        self.assertEqual(json.loads((self.output / "stage-manifest.json").read_text()), manifest)
        self.assertEqual(manifest["source_ref"], "test-ref")
        self.assertEqual(manifest["compatibility_status"], "not_verified_by_staging")
        for record in manifest["files"] + manifest["generated_files"]:
            data = (self.output / record["destination"]).read_bytes()
            self.assertEqual(record["sha256"], hashlib.sha256(data).hexdigest())
            self.assertEqual(record["bytes"], len(data))
            if "source" in record:
                self.assertEqual(data, (self.source / record["source"]).read_bytes())
        instructions = (self.output / "AGENTS.md").read_text()
        self.assertNotIn("UNBOUNDED", instructions)
        self.assertIn("Do not invoke", instructions)
        self.assertFalse((self.output / ".git").exists())
        self.assertFalse(any(p.is_symlink() for p in self.output.rglob("*")))

    def test_existing_empty_directory_is_supported(self):
        self.output.mkdir()
        stage.stage_pilot(self.output, source_root=self.source)
        self.assertTrue((self.output / "LICENSE").is_file())

    def test_refuses_nonempty_directory_without_changes(self):
        self.output.mkdir()
        sentinel = self.output / "keep"
        sentinel.write_text("original")
        with self.assertRaisesRegex(stage.StageError, "new or empty"):
            stage.stage_pilot(self.output, source_root=self.source)
        self.assertEqual(list(self.output.iterdir()), [sentinel])
        self.assertEqual(sentinel.read_text(), "original")

    def test_missing_source_leaves_no_output(self):
        (self.source / stage.COPY_FILES[-1][0]).unlink()
        with self.assertRaisesRegex(stage.StageError, "Required pilot source is missing: LICENSE"):
            stage.stage_pilot(self.output, source_root=self.source)
        self.assertFalse(self.output.exists())

    def test_refuses_symlink_output_and_parent(self):
        real = self.base / "real directory"
        real.mkdir()
        alias = self.base / "alias"
        try:
            alias.symlink_to(real, target_is_directory=True)
        except OSError as exc:
            self.skipTest(f"Symlink unavailable: {exc}")
        for destination in (alias, alias / "child"):
            with self.subTest(destination=destination), self.assertRaisesRegex(stage.StageError, "Symlink"):
                stage.stage_pilot(destination, source_root=self.source)
        self.assertEqual(list(real.iterdir()), [])

    def test_refuses_symlink_source_outside_root(self):
        target = self.source / stage.COPY_FILES[0][0]
        target.unlink()
        outside = self.base / "outside"
        outside.write_text("external content")
        try:
            target.symlink_to(outside)
        except OSError as exc:
            self.skipTest(f"Symlink unavailable: {exc}")
        with self.assertRaisesRegex(stage.StageError, "Symlink"):
            stage.stage_pilot(self.output, source_root=self.source)
        self.assertFalse(self.output.exists())

    def test_refuses_regular_file_and_missing_parent(self):
        self.output.write_text("original")
        with self.assertRaises(stage.StageError):
            stage.stage_pilot(self.output, source_root=self.source)
        self.assertEqual(self.output.read_text(), "original")
        with self.assertRaisesRegex(stage.StageError, "parent must already exist"):
            stage.stage_pilot(self.base / "missing" / "child", source_root=self.source)


if __name__ == "__main__":
    unittest.main()
