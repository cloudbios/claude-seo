"""Structural invariants of the generated full Codex skill distribution."""
from __future__ import annotations

import importlib.util
import json
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("build_codex_skills", ROOT / "scripts/build_codex_skills.py")
BUILDER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILDER)

REQUIRED_ROUTES = {
    "audit", "page", "technical", "content", "content-brief", "schema",
    "sitemap", "images", "geo", "agentic", "plan", "cluster", "sxo", "drift",
    "ecommerce", "programmatic", "competitor-pages", "flow", "local", "maps",
    "hreflang", "google", "backlinks", "dataforseo", "image-gen", "firecrawl",
    "ahrefs", "bing", "profound", "seranking", "matomo", "unlighthouse",
}


def test_full_distribution_preserves_sources_and_native_profiles():
    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory)
        manifest = BUILDER.build(output)
        assert REQUIRED_ROUTES <= manifest["routes"].keys()
        assert len(manifest["extensions"]) == 9
        assert manifest == json.loads((output / "source-manifest.json").read_text())
        for entry in manifest["files"]:
            assert BUILDER.digest((output / entry["destination"]).read_bytes()) == entry["sha256"]
            if "source" in entry:
                assert BUILDER.digest((ROOT / entry["source"]).read_bytes()) == entry["source_sha256"]
        for agent in manifest["agents"]:
            data = tomllib.loads((output / "agents" / (agent["name"] + ".toml")).read_text())
            assert set(data) == {"name", "description", "developer_instructions"}
            assert data["name"] == agent["name"]
            assert agent["skill"] in data["developer_instructions"]
        upstream_roles = {path.stem.removeprefix("seo-") for path in (ROOT / "agents").glob("*.md")}
        generated_roles = {entry["name"].removeprefix("seo-full-") for entry in manifest["agents"]}
        assert upstream_roles <= generated_roles


def test_full_distribution_retains_flow_prompts_and_adapts_runtime():
    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory)
        BUILDER.build(output)
        source = ROOT / "skills/seo-flow/references/prompts"
        target = output / "skills/seo-codex-flow/references/prompts"
        assert {p.relative_to(source) for p in source.rglob("*") if p.is_file()} == {
            p.relative_to(target) for p in target.rglob("*") if p.is_file()
        }
        for path in source.rglob("*.md"):
            original = path.read_text()
            adapted = (target / path.relative_to(source)).read_text()
            if "CC BY 4.0" in original:
                assert "CC BY 4.0" in adapted
                assert "github.com/AgriciDaniel/flow" in adapted
        for path in (output / "skills").rglob("*.md"):
            text = path.read_text()
            assert "${CLAUDE_PLUGIN_ROOT}" not in text
            assert '"$HOME/.claude/' not in text
            assert "seo-codex-codex" not in text
            assert "../$seo-codex" not in text


def test_command_translation_preserves_paths_and_native_agent_names():
    assert "../seo-codex-plan/assets/" == BUILDER.adapt("../seo-plan/assets/")
    assert "$seo-codex-audit URL" == BUILDER.adapt("/seo audit URL")
    assert "$seo-codex setup" == BUILDER.adapt("/seo setup")
    assert "Spawn seo-full-content agent" == BUILDER.adapt("Spawn seo-content agent")
