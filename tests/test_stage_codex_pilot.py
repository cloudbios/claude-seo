"""Offline staging safety and provenance; no real installs or credentials."""

import hashlib
import importlib.util
import json
import shlex
import subprocess
import sys
import tempfile
import tomllib
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
        for source, _ in stage.COPY_FILES + stage.FOUNDATION_FILES + stage.CORE_FILES + stage.VISUAL_FILES + stage.SITEMAP_FILES + stage.AGENTIC_FILES + stage.BRIEF_FILES + stage.PLANNING_FILES + stage.PLAN_FILES + stage.DRIFT_FILES:
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

    def test_optional_registration_is_scoped_and_manifested(self):
        default_output = self.base / "default stage"
        stage.stage_pilot(default_output, source_root=self.source)
        manifest = stage.stage_pilot(self.output, source_root=self.source, register_agents=True)
        default_files = {p.relative_to(default_output).as_posix()
                         for p in default_output.rglob("*") if p.is_file()}
        registered_files = {p.relative_to(self.output).as_posix()
                            for p in self.output.rglob("*") if p.is_file()}
        self.assertEqual(registered_files - default_files, {".codex/config.toml"})
        self.assertEqual(default_files - registered_files, set())
        config_path = self.output / ".codex/config.toml"
        config = tomllib.loads(config_path.read_text())
        self.assertEqual(set(config), {"agents"})
        self.assertEqual(set(config["agents"]), {"seo-codex-technical", "seo-codex-schema"})
        for name, agent in config["agents"].items():
            self.assertEqual(set(agent), {"description", "config_file"})
            self.assertTrue(agent["description"])
            self.assertEqual(agent["config_file"], f"agents/{name}.toml")
            self.assertTrue((config_path.parent / agent["config_file"]).is_file())
        generated = {record["destination"]: record for record in manifest["generated_files"]}
        self.assertEqual(set(generated), {"AGENTS.md", ".codex/config.toml"})
        data = config_path.read_bytes()
        self.assertEqual(generated[".codex/config.toml"]["sha256"], hashlib.sha256(data).hexdigest())
        self.assertEqual(generated[".codex/config.toml"]["bytes"], len(data))
        self.assertEqual(manifest["compatibility_status"], "not_verified_by_staging")

    def test_foundation_adds_only_the_bounded_runtime_payload(self):
        manifest = stage.stage_pilot(self.output, source_root=self.source, runtime_foundation=True)
        additions = {entry["destination"] for entry in manifest["files"]} - {
            destination for _, destination in stage.COPY_FILES
        }
        self.assertEqual(additions, {"scripts/runtime.py", "scripts/state_paths.py"})
        self.assertEqual(len(manifest["files"]), 10)
        for entry in manifest["files"]:
            data = (self.output / entry["destination"]).read_bytes()
            self.assertEqual(entry["sha256"], hashlib.sha256(data).hexdigest())
        self.assertFalse((self.output / "scripts/google_auth.py").exists())
        self.assertFalse((self.output / ".codex/hooks.json").exists())

    def test_core_payload_is_fixed_scoped_and_hashes_supporting_reference(self):
        manifest = stage.stage_pilot(self.output, source_root=self.source, core_orchestration=True)
        additions = {entry["destination"] for entry in manifest["files"]} - {
            destination for _, destination in stage.COPY_FILES
        }
        self.assertEqual(additions, {
            "scripts/runtime.py", "scripts/state_paths.py", "scripts/codex_audit.py",
            ".agents/skills/seo-codex/SKILL.md", ".agents/skills/seo-codex-audit/SKILL.md",
            ".agents/skills/seo-codex-audit/references/synthesis.md",
            ".codex/agents/seo-codex-content.toml", ".codex/agents/seo-codex-images.toml",
            ".agents/skills/seo-codex-content/SKILL.md",
            ".agents/skills/seo-codex-content/references/review.md",
            ".agents/skills/seo-codex-content/LICENSE.txt",
            ".agents/skills/seo-codex-images/SKILL.md",
            ".agents/skills/seo-codex-images/references/review.md",
            ".agents/skills/seo-codex-images/LICENSE.txt",
            ".codex/agents/seo-codex-local.toml",
            ".agents/skills/seo-codex-local/SKILL.md",
            ".agents/skills/seo-codex-local/references/review.md",
            ".codex/agents/seo-codex-hreflang.toml",
            ".agents/skills/seo-codex-hreflang/SKILL.md",
            ".agents/skills/seo-codex-hreflang/references/review.md",
        })
        self.assertEqual(len(manifest["files"]), 28)
        for entry in manifest["files"] + manifest["generated_files"]:
            data = (self.output / entry["destination"]).read_bytes()
            self.assertEqual(entry["sha256"], hashlib.sha256(data).hexdigest())
        instructions = (self.output / "AGENTS.md").read_text()
        self.assertIn("seo-codex/SKILL.md", instructions)
        self.assertIn("one to five explicit pages", instructions)
        self.assertIn("result file alone never proves", instructions)
        self.assertIn("codex_audit.py", instructions)
        self.assertFalse((self.output / ".codex/config.toml").exists())
        self.assertFalse((self.output / ".codex/hooks.json").exists())
        self.assertFalse((self.output / "scripts/google_auth.py").exists())
        self.assertFalse((self.output / "secret-config.json").exists())

    def test_core_and_foundation_flags_do_not_duplicate_files(self):
        manifest = stage.stage_pilot(self.output, source_root=self.source, core_orchestration=True,
                                    runtime_foundation=True, register_agents=True)
        destinations = [row["destination"] for row in manifest["files"]]
        self.assertEqual(len(destinations), len(set(destinations)))
        self.assertEqual(len(destinations), 28)
        self.assertTrue((self.output / ".codex/config.toml").is_file())
        config = tomllib.loads((self.output / ".codex/config.toml").read_text())
        self.assertEqual(set(config["agents"]), {
            "seo-codex-technical", "seo-codex-schema", "seo-codex-content", "seo-codex-images",
            "seo-codex-local", "seo-codex-hreflang"
        })
        for name, agent in config["agents"].items():
            self.assertEqual(set(agent), {"description", "config_file"})
            self.assertEqual(agent["config_file"], f"agents/{name}.toml")
            self.assertTrue((self.output / ".codex" / agent["config_file"]).is_file())

    def test_missing_specialist_license_leaves_no_output(self):
        (self.source / "skills/seo-images/LICENSE.txt").unlink()
        with self.assertRaisesRegex(stage.StageError, "Required pilot source is missing"):
            stage.stage_pilot(self.output, source_root=self.source, core_orchestration=True)
        self.assertFalse(self.output.exists())

    def test_visual_option_is_scoped_includes_core_and_has_provenance(self):
        manifest = stage.stage_pilot(self.output, source_root=self.source,
                                    visual_evidence=True, register_agents=True)
        self.assertEqual(len(manifest["files"]), 33)
        self.assertEqual(len({r["destination"] for r in manifest["files"]}), 33)
        visual = {r["destination"] for r in manifest["files"]} - {
            dest for _, dest in stage.COPY_FILES + stage.FOUNDATION_FILES + stage.CORE_FILES
        }
        self.assertEqual(visual, {"scripts/codex_visual.py", "scripts/render_page.py",
                                 ".codex/agents/seo-codex-visual.toml",
                                 ".agents/skills/seo-codex-visual/SKILL.md",
                                 ".agents/skills/seo-codex-visual/references/review.md"})
        config = tomllib.loads((self.output / ".codex/config.toml").read_text())
        self.assertEqual(set(config["agents"]), {
            "seo-codex-technical", "seo-codex-schema", "seo-codex-content",
            "seo-codex-images", "seo-codex-local", "seo-codex-hreflang", "seo-codex-visual"
        })
        for row in manifest["files"] + manifest["generated_files"]:
            self.assertEqual(row["sha256"], hashlib.sha256(
                (self.output / row["destination"]).read_bytes()).hexdigest())
        self.assertIn("external requests blocked", (self.output / "AGENTS.md").read_text())
        self.assertFalse((self.output / "scripts/pagespeed_check.py").exists())

    def test_core_without_visual_preserves_existing_registration(self):
        stage.stage_pilot(self.output, source_root=self.source,
                          core_orchestration=True, register_agents=True)
        self.assertFalse((self.output / "scripts/codex_visual.py").exists())
        self.assertFalse((self.output / ".codex/agents/seo-codex-visual.toml").exists())
        config = tomllib.loads((self.output / ".codex/config.toml").read_text())
        self.assertNotIn("seo-codex-visual", config["agents"])
        self.assertNotIn("seo-codex-sitemap", config["agents"])
        self.assertFalse((self.output / "scripts/codex_sitemap.py").exists())
        self.assertNotIn("seo-codex-agentic", config["agents"])
        self.assertFalse((self.output / "scripts/codex_agentic.py").exists())
        self.assertNotIn("seo-codex-content-brief", config["agents"])
        self.assertFalse((self.output / "scripts/codex_brief.py").exists())

    def test_sitemap_option_is_scoped_and_independent_of_visual(self):
        manifest = stage.stage_pilot(self.output, source_root=self.source,
                                    sitemap_analysis=True, register_agents=True)
        self.assertEqual(len(manifest["files"]), 33)
        added = {r["destination"] for r in manifest["files"]} - {
            dest for _, dest in stage.COPY_FILES + stage.FOUNDATION_FILES + stage.CORE_FILES
        }
        self.assertEqual(added, {"scripts/codex_sitemap.py", "scripts/sitemap_discovery.py",
                                ".codex/agents/seo-codex-sitemap.toml",
                                ".agents/skills/seo-codex-sitemap/SKILL.md",
                                ".agents/skills/seo-codex-sitemap/references/review.md"})
        config = tomllib.loads((self.output / ".codex/config.toml").read_text())
        self.assertEqual(set(config["agents"]), {
            "seo-codex-technical", "seo-codex-schema", "seo-codex-content",
            "seo-codex-images", "seo-codex-local", "seo-codex-hreflang", "seo-codex-sitemap"
        })
        self.assertFalse((self.output / "scripts/codex_visual.py").exists())
        self.assertFalse((self.output / "scripts/google_auth.py").exists())
        for row in manifest["files"] + manifest["generated_files"]:
            self.assertEqual(row["sha256"], hashlib.sha256(
                (self.output / row["destination"]).read_bytes()).hexdigest())
        self.assertIn("Do not run discovery", (self.output / "AGENTS.md").read_text())

    def test_optional_adapters_can_be_staged_together_without_duplicates(self):
        manifest = stage.stage_pilot(self.output, source_root=self.source,
                                    sitemap_analysis=True, visual_evidence=True, register_agents=True)
        destinations = [row["destination"] for row in manifest["files"]]
        self.assertEqual(len(destinations), 38)
        self.assertEqual(len(destinations), len(set(destinations)))
        config = tomllib.loads((self.output / ".codex/config.toml").read_text())
        self.assertEqual(len(config["agents"]), 8)

    def test_agentic_option_is_scoped_and_only_imports_pure_helpers(self):
        manifest = stage.stage_pilot(self.output, source_root=self.source,
                                    agentic_report=True, register_agents=True)
        self.assertEqual(len(manifest["files"]), 33)
        added = {r["destination"] for r in manifest["files"]} - {
            dest for _, dest in stage.COPY_FILES + stage.FOUNDATION_FILES + stage.CORE_FILES
        }
        self.assertEqual(added, {"scripts/codex_agentic.py", "scripts/lighthouse_agentic.py",
                                ".codex/agents/seo-codex-agentic.toml",
                                ".agents/skills/seo-codex-agentic/SKILL.md",
                                ".agents/skills/seo-codex-agentic/references/review.md"})
        config = tomllib.loads((self.output / ".codex/config.toml").read_text())
        self.assertEqual(set(config["agents"]), {
            "seo-codex-technical", "seo-codex-schema", "seo-codex-content",
            "seo-codex-images", "seo-codex-local", "seo-codex-hreflang", "seo-codex-agentic"
        })
        for name in ("google_auth.py", "agentic_check.py", "agentic_fix.py", "pagespeed_check.py", "codex_visual.py"):
            self.assertFalse((self.output / "scripts" / name).exists())
        self.assertIn("never invoke its CLI", (self.output / "AGENTS.md").read_text())
        for row in manifest["files"] + manifest["generated_files"]:
            self.assertEqual(row["sha256"], hashlib.sha256(
                (self.output / row["destination"]).read_bytes()).hexdigest())

    def test_all_three_optional_adapters_remain_additive(self):
        manifest = stage.stage_pilot(self.output, source_root=self.source, sitemap_analysis=True,
                                    visual_evidence=True, agentic_report=True, register_agents=True)
        destinations = [row["destination"] for row in manifest["files"]]
        self.assertEqual(len(destinations), 43)
        self.assertEqual(len(destinations), len(set(destinations)))
        config = tomllib.loads((self.output / ".codex/config.toml").read_text())
        self.assertEqual(len(config["agents"]), 9)

    def test_missing_agentic_helper_leaves_no_output(self):
        (self.source / "scripts/lighthouse_agentic.py").unlink()
        with self.assertRaisesRegex(stage.StageError, "Required pilot source is missing"):
            stage.stage_pilot(self.output, source_root=self.source, agentic_report=True)
        self.assertFalse(self.output.exists())

    def test_brief_option_is_scoped_and_preserves_author_notice(self):
        manifest = stage.stage_pilot(self.output, source_root=self.source,
                                    content_brief=True, register_agents=True)
        self.assertEqual(len(manifest["files"]), 34)
        added = {r["destination"] for r in manifest["files"]} - {
            dest for _, dest in stage.COPY_FILES + stage.FOUNDATION_FILES + stage.CORE_FILES
        }
        self.assertEqual(added, {"scripts/codex_brief.py", "scripts/codex_planning.py", ".codex/agents/seo-codex-content-brief.toml",
                                ".agents/skills/seo-codex-content-brief/SKILL.md",
                                ".agents/skills/seo-codex-content-brief/references/review.md",
                                ".agents/skills/seo-codex-content-brief/LICENSE.txt"})
        self.assertEqual((self.output / ".agents/skills/seo-codex-content-brief/LICENSE.txt").read_bytes(),
                         (self.source / "skills/seo-content-brief/LICENSE.txt").read_bytes())
        config = tomllib.loads((self.output / ".codex/config.toml").read_text())
        self.assertEqual(set(config["agents"]), {
            "seo-codex-technical", "seo-codex-schema", "seo-codex-content",
            "seo-codex-images", "seo-codex-local", "seo-codex-hreflang", "seo-codex-content-brief"
        })
        for name in ("google_auth.py", "pagespeed_check.py", "codex_agentic.py", "codex_visual.py"):
            self.assertFalse((self.output / "scripts" / name).exists())
        for row in manifest["files"] + manifest["generated_files"]:
            self.assertEqual(row["sha256"], hashlib.sha256(
                (self.output / row["destination"]).read_bytes()).hexdigest())

    def test_all_four_optional_adapters_remain_additive(self):
        manifest = stage.stage_pilot(self.output, source_root=self.source, sitemap_analysis=True,
                                    visual_evidence=True, agentic_report=True, content_brief=True, register_agents=True)
        destinations = [row["destination"] for row in manifest["files"]]
        self.assertEqual(len(destinations), 49)
        self.assertEqual(len(destinations), len(set(destinations)))
        self.assertEqual(len(tomllib.loads((self.output / ".codex/config.toml").read_text())["agents"]), 10)

    def test_missing_brief_license_leaves_no_output(self):
        (self.source / "skills/seo-content-brief/LICENSE.txt").unlink()
        with self.assertRaisesRegex(stage.StageError, "Required pilot source is missing"):
            stage.stage_pilot(self.output, source_root=self.source, content_brief=True)
        self.assertFalse(self.output.exists())

    def test_strategy_is_scoped_and_shares_only_the_planning_helper(self):
        manifest = stage.stage_pilot(self.output, source_root=self.source,
                                    strategy_plan=True, register_agents=True)
        self.assertEqual(len(manifest["files"]), 34)
        added = {r["destination"] for r in manifest["files"]} - {
            dest for _, dest in stage.COPY_FILES + stage.FOUNDATION_FILES + stage.CORE_FILES
        }
        self.assertEqual(added, {"scripts/codex_plan.py", "scripts/codex_planning.py",
                                ".codex/agents/seo-codex-plan.toml", ".agents/skills/seo-codex-plan/SKILL.md",
                                ".agents/skills/seo-codex-plan/references/review.md",
                                ".agents/skills/seo-codex-plan/references/industries.md"})
        self.assertFalse((self.output / "scripts/codex_brief.py").exists())
        self.assertEqual(len(tomllib.loads((self.output / ".codex/config.toml").read_text())["agents"]), 7)

    def test_brief_and_strategy_copy_shared_helper_once(self):
        manifest = stage.stage_pilot(self.output, source_root=self.source,
                                    content_brief=True, strategy_plan=True, register_agents=True)
        destinations = [row["destination"] for row in manifest["files"]]
        self.assertEqual(len(destinations), 39)
        self.assertEqual(destinations.count("scripts/codex_planning.py"), 1)
        self.assertEqual(len(destinations), len(set(destinations)))
        self.assertEqual(len(tomllib.loads((self.output / ".codex/config.toml").read_text())["agents"]), 8)

    def test_all_optional_workflows_share_one_planning_helper(self):
        manifest = stage.stage_pilot(self.output, source_root=self.source, sitemap_analysis=True,
                                    visual_evidence=True, agentic_report=True, content_brief=True,
                                    strategy_plan=True, register_agents=True)
        destinations = [row["destination"] for row in manifest["files"]]
        self.assertEqual(len(destinations), 54)
        self.assertEqual(len(destinations), len(set(destinations)))
        self.assertEqual(len(tomllib.loads((self.output / ".codex/config.toml").read_text())["agents"]), 11)

    def test_missing_shared_planning_helper_leaves_no_output(self):
        (self.source / "scripts/codex_planning.py").unlink()
        for option in ("content_brief", "strategy_plan", "source_drift"):
            with self.assertRaisesRegex(stage.StageError, "Required pilot source is missing"):
                stage.stage_pilot(self.output, source_root=self.source, **{option: True})
            self.assertFalse(self.output.exists())

    def test_source_drift_is_a_scoped_saved_capture_adapter(self):
        manifest = stage.stage_pilot(self.output, source_root=self.source,
                                    source_drift=True, register_agents=True)
        self.assertEqual(len(manifest["files"]), 34)
        added = {r["destination"] for r in manifest["files"]} - {
            dest for _, dest in stage.COPY_FILES + stage.FOUNDATION_FILES + stage.CORE_FILES
        }
        self.assertEqual(added, {"scripts/codex_drift.py", "scripts/codex_planning.py",
                                ".codex/agents/seo-codex-drift.toml", ".agents/skills/seo-codex-drift/SKILL.md",
                                ".agents/skills/seo-codex-drift/references/review.md",
                                ".agents/skills/seo-codex-drift/references/fields.md"})
        self.assertFalse((self.output / "scripts/drift_baseline.py").exists())
        self.assertFalse((self.output / "scripts/drift_compare.py").exists())
        self.assertFalse((self.output / "scripts/google_auth.py").exists())
        self.assertEqual(len(tomllib.loads((self.output / ".codex/config.toml").read_text())["agents"]), 7)

    def test_all_six_optional_workflows_share_one_helper(self):
        manifest = stage.stage_pilot(self.output, source_root=self.source, sitemap_analysis=True,
                                    visual_evidence=True, agentic_report=True, content_brief=True,
                                    strategy_plan=True, source_drift=True, register_agents=True)
        destinations = [row["destination"] for row in manifest["files"]]
        self.assertEqual(len(destinations), 59)
        self.assertEqual(destinations.count("scripts/codex_planning.py"), 1)
        self.assertEqual(len(destinations), len(set(destinations)))
        self.assertEqual(len(tomllib.loads((self.output / ".codex/config.toml").read_text())["agents"]), 12)

    def test_missing_sitemap_parser_leaves_no_output(self):
        (self.source / "scripts/sitemap_discovery.py").unlink()
        with self.assertRaisesRegex(stage.StageError, "Required pilot source is missing"):
            stage.stage_pilot(self.output, source_root=self.source, sitemap_analysis=True)
        self.assertFalse(self.output.exists())

    def test_missing_core_reference_leaves_no_output(self):
        (self.source / "adapters/codex/skills/seo-codex-audit/references/synthesis.md").unlink()
        with self.assertRaisesRegex(stage.StageError, "Required pilot source is missing"):
            stage.stage_pilot(self.output, source_root=self.source, core_orchestration=True)
        self.assertFalse(self.output.exists())

    @unittest.skipIf(sys.platform == "win32", "POSIX hook staging contract")
    def test_opt_in_hook_is_scoped_quoted_and_manifested_without_trust(self):
        python = Path(sys.executable).resolve()
        manifest = stage.stage_pilot(self.output, source_root=self.source,
                                    schema_hook_python=Path(sys.executable))
        config_path = self.output / ".codex/hooks.json"
        config = json.loads(config_path.read_text())
        self.assertEqual(set(config["hooks"]), {"PostToolUse"})
        group, = config["hooks"]["PostToolUse"]
        self.assertEqual(group["matcher"], "^apply_patch$")
        handler, = group["hooks"]
        expected = [str(python), "-I", "-B", str(self.output / "hooks/validate-schema.py")]
        self.assertEqual(shlex.split(handler["command"]), expected)
        self.assertNotIn("commandWindows", handler)
        self.assertEqual(handler["type"], "command")
        self.assertEqual(handler["timeout"], 30)
        entry, = [row for row in manifest["generated_files"]
                  if row["destination"] == ".codex/hooks.json"]
        self.assertEqual(entry["sha256"], hashlib.sha256(config_path.read_bytes()).hexdigest())
        self.assertEqual(manifest["compatibility_status"], "not_verified_by_staging")
        self.assertNotIn("trust", handler)
        self.assertFalse((self.output / ".codex/config.toml").exists())

    def test_hook_requires_explicit_executable_before_writing_output(self):
        for python in (Path("python3"), self.base / "does-not-exist"):
            with self.subTest(python=python), self.assertRaises(stage.StageError):
                stage.stage_pilot(self.output, source_root=self.source, schema_hook_python=python)
            self.assertFalse(self.output.exists())

    def test_hook_staging_refuses_unverified_windows_shell(self):
        with mock.patch.object(stage.sys, "platform", "win32"), self.assertRaisesRegex(stage.StageError, "POSIX"):
            stage.stage_pilot(self.output, source_root=self.source, schema_hook_python=Path(sys.executable))
        self.assertFalse(self.output.exists())

    @unittest.skipIf(sys.platform == "win32", "POSIX hook command contract")
    def test_hook_command_keeps_shell_metacharacters_literal(self):
        self.output = self.base / "stage; touch injected; #"
        (self.source / "hooks/validate-schema.py").write_text("print('hook-ok')\n")
        stage.stage_pilot(self.output, source_root=self.source, schema_hook_python=Path(sys.executable))
        config = json.loads((self.output / ".codex/hooks.json").read_text())
        command = config["hooks"]["PostToolUse"][0]["hooks"][0]["command"]
        result = subprocess.run(command, shell=True, cwd=self.base, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "hook-ok")
        self.assertFalse((self.base / "injected").exists())

    def test_missing_foundation_source_leaves_no_output(self):
        (self.source / "scripts/state_paths.py").unlink()
        with self.assertRaisesRegex(stage.StageError, "Required pilot source is missing"):
            stage.stage_pilot(self.output, source_root=self.source, runtime_foundation=True)
        self.assertFalse(self.output.exists())

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
