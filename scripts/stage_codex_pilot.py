#!/usr/bin/env python3
"""Stage the bounded Codex pilot without installation or global configuration.

Run with the caller's preconfigured Python. Dependencies are neither installed
nor copied. A non-Git stage can be opened using Codex's skip-Git-check option.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import sys
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parents[1]
SOURCE_BASELINE_REF = "6be93f45064ffbadced572b5d5c95f55fd263af0"
COPY_FILES = (
    ("adapters/codex/skills/seo-codex-pilot/SKILL.md", ".agents/skills/seo-codex-pilot/SKILL.md"),
    ("adapters/codex/agents/seo-codex-technical.toml", ".codex/agents/seo-codex-technical.toml"),
    ("adapters/codex/agents/seo-codex-schema.toml", ".codex/agents/seo-codex-schema.toml"),
    ("scripts/codex_pilot.py", "scripts/codex_pilot.py"),
    ("scripts/url_safety.py", "scripts/url_safety.py"),
    ("scripts/parse_html.py", "scripts/parse_html.py"),
    ("hooks/validate-schema.py", "hooks/validate-schema.py"),
    ("LICENSE", "LICENSE"),
)
FOUNDATION_FILES = (
    ("scripts/runtime.py", "scripts/runtime.py"),
    ("scripts/state_paths.py", "scripts/state_paths.py"),
)
CORE_FILES = (
    ("scripts/codex_audit.py", "scripts/codex_audit.py"),
    ("adapters/codex/skills/seo-codex/SKILL.md", ".agents/skills/seo-codex/SKILL.md"),
    ("adapters/codex/skills/seo-codex-audit/SKILL.md", ".agents/skills/seo-codex-audit/SKILL.md"),
    ("adapters/codex/skills/seo-codex-audit/references/synthesis.md",
     ".agents/skills/seo-codex-audit/references/synthesis.md"),
    ("adapters/codex/agents/seo-codex-content.toml", ".codex/agents/seo-codex-content.toml"),
    ("adapters/codex/agents/seo-codex-images.toml", ".codex/agents/seo-codex-images.toml"),
    ("adapters/codex/skills/seo-codex-content/SKILL.md", ".agents/skills/seo-codex-content/SKILL.md"),
    ("adapters/codex/skills/seo-codex-content/references/review.md",
     ".agents/skills/seo-codex-content/references/review.md"),
    ("skills/seo-content/LICENSE.txt", ".agents/skills/seo-codex-content/LICENSE.txt"),
    ("adapters/codex/skills/seo-codex-images/SKILL.md", ".agents/skills/seo-codex-images/SKILL.md"),
    ("adapters/codex/skills/seo-codex-images/references/review.md",
     ".agents/skills/seo-codex-images/references/review.md"),
    ("skills/seo-images/LICENSE.txt", ".agents/skills/seo-codex-images/LICENSE.txt"),
    ("adapters/codex/agents/seo-codex-local.toml", ".codex/agents/seo-codex-local.toml"),
    ("adapters/codex/skills/seo-codex-local/SKILL.md", ".agents/skills/seo-codex-local/SKILL.md"),
    ("adapters/codex/skills/seo-codex-local/references/review.md",
     ".agents/skills/seo-codex-local/references/review.md"),
    ("adapters/codex/agents/seo-codex-hreflang.toml", ".codex/agents/seo-codex-hreflang.toml"),
    ("adapters/codex/skills/seo-codex-hreflang/SKILL.md", ".agents/skills/seo-codex-hreflang/SKILL.md"),
    ("adapters/codex/skills/seo-codex-hreflang/references/review.md",
     ".agents/skills/seo-codex-hreflang/references/review.md"),
)
VISUAL_FILES = (
    ("scripts/render_page.py", "scripts/render_page.py"),
    ("scripts/codex_visual.py", "scripts/codex_visual.py"),
    ("adapters/codex/agents/seo-codex-visual.toml", ".codex/agents/seo-codex-visual.toml"),
    ("adapters/codex/skills/seo-codex-visual/SKILL.md", ".agents/skills/seo-codex-visual/SKILL.md"),
    ("adapters/codex/skills/seo-codex-visual/references/review.md",
     ".agents/skills/seo-codex-visual/references/review.md"),
)
SITEMAP_FILES = (
    ("scripts/sitemap_discovery.py", "scripts/sitemap_discovery.py"),
    ("scripts/codex_sitemap.py", "scripts/codex_sitemap.py"),
    ("adapters/codex/agents/seo-codex-sitemap.toml", ".codex/agents/seo-codex-sitemap.toml"),
    ("adapters/codex/skills/seo-codex-sitemap/SKILL.md", ".agents/skills/seo-codex-sitemap/SKILL.md"),
    ("adapters/codex/skills/seo-codex-sitemap/references/review.md",
     ".agents/skills/seo-codex-sitemap/references/review.md"),
)
AGENTIC_FILES = (
    ("scripts/lighthouse_agentic.py", "scripts/lighthouse_agentic.py"),
    ("scripts/codex_agentic.py", "scripts/codex_agentic.py"),
    ("adapters/codex/agents/seo-codex-agentic.toml", ".codex/agents/seo-codex-agentic.toml"),
    ("adapters/codex/skills/seo-codex-agentic/SKILL.md", ".agents/skills/seo-codex-agentic/SKILL.md"),
    ("adapters/codex/skills/seo-codex-agentic/references/review.md",
     ".agents/skills/seo-codex-agentic/references/review.md"),
)
BRIEF_FILES = (
    ("scripts/codex_brief.py", "scripts/codex_brief.py"),
    ("adapters/codex/agents/seo-codex-content-brief.toml", ".codex/agents/seo-codex-content-brief.toml"),
    ("adapters/codex/skills/seo-codex-content-brief/SKILL.md", ".agents/skills/seo-codex-content-brief/SKILL.md"),
    ("adapters/codex/skills/seo-codex-content-brief/references/review.md",
     ".agents/skills/seo-codex-content-brief/references/review.md"),
    ("skills/seo-content-brief/LICENSE.txt", ".agents/skills/seo-codex-content-brief/LICENSE.txt"),
)
PLANNING_FILES = (("scripts/codex_planning.py", "scripts/codex_planning.py"),)
PLAN_FILES = (
    ("scripts/codex_plan.py", "scripts/codex_plan.py"),
    ("adapters/codex/agents/seo-codex-plan.toml", ".codex/agents/seo-codex-plan.toml"),
    ("adapters/codex/skills/seo-codex-plan/SKILL.md", ".agents/skills/seo-codex-plan/SKILL.md"),
    ("adapters/codex/skills/seo-codex-plan/references/review.md", ".agents/skills/seo-codex-plan/references/review.md"),
    ("adapters/codex/skills/seo-codex-plan/references/industries.md", ".agents/skills/seo-codex-plan/references/industries.md"),
)
DRIFT_FILES = (
    ("scripts/codex_drift.py", "scripts/codex_drift.py"),
    ("adapters/codex/agents/seo-codex-drift.toml", ".codex/agents/seo-codex-drift.toml"),
    ("adapters/codex/skills/seo-codex-drift/SKILL.md", ".agents/skills/seo-codex-drift/SKILL.md"),
    ("adapters/codex/skills/seo-codex-drift/references/review.md", ".agents/skills/seo-codex-drift/references/review.md"),
    ("adapters/codex/skills/seo-codex-drift/references/fields.md", ".agents/skills/seo-codex-drift/references/fields.md"),
)
AGENT_REGISTRATION = '''[agents.seo-codex-technical]
description = "Review the staged one-page pilot's shared capture for technical SEO signals and save evidence-linked findings."
config_file = "agents/seo-codex-technical.toml"

[agents.seo-codex-schema]
description = "Review the staged one-page pilot's captured structured data and save grounded schema findings."
config_file = "agents/seo-codex-schema.toml"
'''
CORE_AGENT_REGISTRATION = '''
[agents.seo-codex-content]
description = "Review captured source HTML for observable content quality, attribution and structure signals."
config_file = "agents/seo-codex-content.toml"

[agents.seo-codex-images]
description = "Review captured source HTML for image markup, text alternatives and delivery declarations."
config_file = "agents/seo-codex-images.toml"

[agents.seo-codex-local]
description = "Review captured source HTML for local business identity and declared location signals."
config_file = "agents/seo-codex-local.toml"

[agents.seo-codex-hreflang]
description = "Review one captured page's language and alternate-URL declarations."
config_file = "agents/seo-codex-hreflang.toml"
'''
VISUAL_AGENT_REGISTRATION = '''
[agents.seo-codex-visual]
description = "Review verified offline desktop/mobile render evidence and save bounded visual findings."
config_file = "agents/seo-codex-visual.toml"
'''
SITEMAP_AGENT_REGISTRATION = '''
[agents.seo-codex-sitemap]
description = "Review supplied sitemap XML and bounded captured-page membership evidence."
config_file = "agents/seo-codex-sitemap.toml"
'''
AGENTIC_AGENT_REGISTRATION = '''
[agents.seo-codex-agentic]
description = "Interpret one saved Lighthouse Agentic Browsing report with version-bound evidence."
config_file = "agents/seo-codex-agentic.toml"
'''
BRIEF_AGENT_REGISTRATION = '''
[agents.seo-codex-content-brief]
description = "Draft a content brief from supplied requirements and verified source captures."
config_file = "agents/seo-codex-content-brief.toml"
'''
PLAN_AGENT_REGISTRATION = '''
[agents.seo-codex-plan]
description = "Build a source-labelled SEO strategy, roadmap, calendar, site structure and measurement plan."
config_file = "agents/seo-codex-plan.toml"
'''
DRIFT_AGENT_REGISTRATION = '''
[agents.seo-codex-drift]
description = "Interpret changes between two verified saved page captures without assuming every change is a regression."
config_file = "agents/seo-codex-drift.toml"
'''
STAGE_INSTRUCTIONS = """# Bounded Codex SEO pilot

Use only `.agents/skills/seo-codex-pilot/SKILL.md` for this pilot. Do not invoke
unrelated globally installed SEO skills or upstream workflows. Follow the
caller's authorization and tool restrictions; this directory grants no new
network, installation, authentication, spending, or publication authority.

Run `scripts/codex_pilot.py` from this project root using the caller's
preconfigured Python. Do not install dependencies or change global settings.
The technical and schema agent definitions are in `.codex/agents/`; model and
reasoning settings inherit from the caller. Do not assume agent discovery or
hook compatibility has passed. Use explicit schema validation through the
pilot, not an implicit edit hook, and report unavailable capabilities honestly.

This stage is intentionally not initialized as a Git repository. A caller may
use Codex's skip-Git-check option where required. `stage-manifest.json` records
the copied source hashes; it is provenance, not a compatibility test receipt.
"""
FOUNDATION_INSTRUCTIONS = """
## Explicit prepared runtime

This stage includes the opt-in Codex runtime foundation. Invoke the prepared
Python directly with `scripts/runtime.py --host codex --state-root <absolute
dedicated directory> run codex_pilot.py ...`. The state root must be supplied
by the caller and must not overlap this source project. If it is missing,
request it; do not borrow a global or Claude state/configuration directory.
The Codex runner allows only `codex_pilot.py`, `codex_audit.py`,
`codex_visual.py`, `codex_sitemap.py`, `codex_agentic.py`, `codex_brief.py`, `codex_plan.py` and `codex_drift.py`;
each must be present in this stage to run. It refuses
installation and providers.
Run its `doctor --json` before the audit. Its clean environment is process
hygiene, not a replacement for the host sandbox or permissions.
"""
VISUAL_INSTRUCTIONS = """
## Optional offline visual evidence

This stage also includes `.agents/skills/seo-codex-visual/SKILL.md`. It renders
an existing verified raw capture with external requests blocked, using an
explicit prepared Chromium executable. It does not browse the live site.
Use the visual helper through the same prepared runtime; run its own doctor
before capture. Do not install browsers or infer an executable from global
configuration. Preserve the source capture and create a separate evidence
directory. The native visual role requires actual screenshot inspection;
missing image-view capability means partial review.
"""
SITEMAP_INSTRUCTIONS = """
## Optional saved sitemap analysis

This stage includes `.agents/skills/seo-codex-sitemap/SKILL.md`. Analyze supplied
XML using the prepared runtime and `codex_sitemap.py`; its supporting discovery
module supplies a secure parser only. Do not run discovery or fetch URLs.
Use a separate output directory and preserve the XML and any supplied verified
page captures. Index children are not followed. A native sitemap review owns
only its findings file; the coordinator validates and finalizes after the
reviewer stops. This adapter does not generate or submit sitemaps.
"""
AGENTIC_INSTRUCTIONS = """
## Optional saved Agentic Browsing report

This stage includes `.agents/skills/seo-codex-agentic/SKILL.md`. Import an
explicit saved Lighthouse or PSI JSON file through `codex_agentic.py` using
the prepared runtime. The supporting Lighthouse module supplies pure scoring
helpers only; never invoke its CLI or live PSI path. No browser, credentials
or network requests are needed. Preserve the source and use separate output.
The fraction is version-bound evidence from that recorded run, not a live
site certification or prediction of search rankings or AI citations.
"""
BRIEF_INSTRUCTIONS = """
## Optional content briefs

This stage includes `.agents/skills/seo-codex-content-brief/SKILL.md`. Use
`codex_brief.py` through the prepared runtime to freeze supplied requirements
and up to five existing verified page captures. New-page and improve-page
briefs are standalone planning outputs. The native author distinguishes user
claims, source observations, inferences and proposals; it does not establish
search rankings or demand. Preserve source captures. The author writes only
its findings JSON, and the coordinator finalizes BRIEF.md after observing the
author stop. This adapter performs no discovery, fetch, publication or edits
to the target site.
"""
PLAN_INSTRUCTIONS = """
## Optional SEO strategy planning

This stage includes `.agents/skills/seo-codex-plan/SKILL.md`. Use
`codex_plan.py` through the prepared runtime to freeze business requirements,
resources, a relative planning horizon and up to five verified captures.
The native planner writes only findings/plan.json. The coordinator observes
termination, validates references and dependencies, and finalizes five planning
documents. Schedules and targets are proposals, and baselines remain unavailable.
There is no live research, audit import, provider execution or site change.
The shared codex_planning.py module is a library, not an executable workflow.
"""
DRIFT_INSTRUCTIONS = """
## Optional saved-capture change review

This stage includes `.agents/skills/seo-codex-drift/SKILL.md`. Compare two
explicit captures with the same recorded requested URL using `codex_drift.py`
through the prepared runtime. Preserve both captures. A failed after-capture
allows only partial transport comparison; it never proves document elements
were removed. The native reviewer interprets changes, while the coordinator
finalizes REPORT.md after observing the reviewer stop. This workflow does not
fetch, store history in a database, schedule monitoring or change a site.
"""
CORE_INSTRUCTIONS = """# Bounded Codex SEO core

Use `.agents/skills/seo-codex/SKILL.md` to route requests. Its supported workflows
are the one-page pilot, content, image-markup, local and hreflang source reviews, and a sampled audit
of one to five explicit pages using `.agents/skills/seo-codex-audit/SKILL.md`.
Other routes require an explicitly staged adapter.
Do not invoke unrelated globally installed SEO skills or upstream workflows.
Follow the caller's authorization and tool restrictions; this directory grants
no new network, installation, authentication, spending, or publication authority.

The caller supplies a prepared Python and an absolute dedicated state root.
Do not install dependencies or change global settings. Technical, schema,
content, images, local and hreflang profiles are in `.codex/agents/`; model, reasoning,
and permissions inherit from the caller. Do not assume agent discovery or
hook compatibility has passed.
Use explicit schema validation through the capture workflow.

One coordinator owns the audit manifest. Serialize commands that mutate the
same audit directory. Reserve each task before spawning; respect both the
two-worker limit and the host's available capacity. Keep its
reservation until native completion or confirmed stop, then reconcile and
release. A result file alone never proves the agent stopped. Report missing or
partial results and retain captured evidence when resuming. Never claim that a
sampled audit covers the full site.

This stage is intentionally not initialized as a Git repository. A caller may
use Codex's skip-Git-check option where required. `stage-manifest.json` records
the copied source hashes; it is provenance, not a compatibility test receipt.
"""


class StageError(ValueError):
    """An unsafe or incomplete staging request."""


def _reject_symlinks(path: Path) -> None:
    """Reject symlinks in an absolute path, including existing ancestors."""
    for candidate in (path, *path.parents):
        if candidate.is_symlink():
            raise StageError(f"Symlink paths are not allowed: {candidate}")


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stage_pilot(
    output: Path,
    *,
    source_root: Path = SOURCE_ROOT,
    source_ref: str | None = None,
    register_agents: bool = False,
    runtime_foundation: bool = False,
    core_orchestration: bool = False,
    visual_evidence: bool = False,
    sitemap_analysis: bool = False,
    agentic_report: bool = False,
    content_brief: bool = False,
    strategy_plan: bool = False,
    source_drift: bool = False,
    schema_hook_python: Path | None = None,
) -> dict:
    """Copy the explicit allowlist into a new or existing empty directory.

    All inputs and the destination are validated before any write. The caller
    must control the destination parent while staging; this is not a sandbox
    against concurrent filesystem replacement by another local process.
    """
    root = Path(source_root).absolute()
    output = Path(output).absolute()
    _reject_symlinks(root)
    _reject_symlinks(output)
    root = root.resolve()
    output = output.resolve()
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise StageError(f"Output must be a new or empty directory: {output}")
    if not output.parent.is_dir():
        raise StageError(f"Output parent must already exist: {output.parent}")

    hook_python = None
    if schema_hook_python is not None:
        if sys.platform == "win32":
            raise StageError("Schema-hook staging currently supports POSIX shells only")
        if not schema_hook_python.is_absolute():
            raise StageError("Hook interpreter must be an explicit absolute executable path")
        hook_python = schema_hook_python.resolve()
        if not hook_python.is_file() or not os.access(hook_python, os.X_OK):
            raise StageError("Hook interpreter must be an existing executable file")

    core_orchestration = core_orchestration or visual_evidence or sitemap_analysis or agentic_report or content_brief or strategy_plan or source_drift
    runtime_foundation = runtime_foundation or core_orchestration
    payloads: list[tuple[str, str, bytes]] = []
    sources = (COPY_FILES + (FOUNDATION_FILES if runtime_foundation else ())
               + (CORE_FILES if core_orchestration else ())
               + (VISUAL_FILES if visual_evidence else ())
               + (SITEMAP_FILES if sitemap_analysis else ())
               + (AGENTIC_FILES if agentic_report else ())
               + (PLANNING_FILES if content_brief or strategy_plan or source_drift else ())
               + (BRIEF_FILES if content_brief else ())
               + (PLAN_FILES if strategy_plan else ())
               + (DRIFT_FILES if source_drift else ()))
    for source, destination in sources:
        path = root / source
        _reject_symlinks(path)
        if not path.resolve().is_relative_to(root):
            raise StageError(f"Source is outside the source root: {source}")
        if not path.is_file():
            raise StageError(f"Required pilot source is missing: {source}")
        payloads.append((source, destination, path.read_bytes()))

    instructions = ((CORE_INSTRUCTIONS if core_orchestration else STAGE_INSTRUCTIONS)
                    + (FOUNDATION_INSTRUCTIONS if runtime_foundation else "")
                    + (VISUAL_INSTRUCTIONS if visual_evidence else "")
                    + (SITEMAP_INSTRUCTIONS if sitemap_analysis else "")
                    + (AGENTIC_INSTRUCTIONS if agentic_report else "")
                    + (BRIEF_INSTRUCTIONS if content_brief else "")
                    + (PLAN_INSTRUCTIONS if strategy_plan else "")
                    + (DRIFT_INSTRUCTIONS if source_drift else ""))
    generated = {"AGENTS.md": instructions.encode("utf-8")}
    if register_agents:
        generated[".codex/config.toml"] = (
            AGENT_REGISTRATION + (CORE_AGENT_REGISTRATION if core_orchestration else "")
            + (VISUAL_AGENT_REGISTRATION if visual_evidence else "")
            + (SITEMAP_AGENT_REGISTRATION if sitemap_analysis else "")
            + (AGENTIC_AGENT_REGISTRATION if agentic_report else "")
            + (BRIEF_AGENT_REGISTRATION if content_brief else "")
            + (PLAN_AGENT_REGISTRATION if strategy_plan else "")
            + (DRIFT_AGENT_REGISTRATION if source_drift else "")
        ).encode("utf-8")
    if hook_python is not None:
        argv = [str(hook_python), "-I", "-B", str(output / "hooks" / "validate-schema.py")]
        hook_config = {
            "description": "Project-local schema feedback. Review and trust this exact hook in Codex before use.",
            "hooks": {"PostToolUse": [{"matcher": "^apply_patch$", "hooks": [{
                "type": "command", "command": shlex.join(argv),
                "timeout": 30, "statusMessage": "Checking edited schema",
            }]}]},
        }
        generated[".codex/hooks.json"] = (json.dumps(hook_config, indent=2) + "\n").encode("utf-8")
    manifest = {
        "format_version": 1,
        "source_baseline_ref": SOURCE_BASELINE_REF,
        "source_ref": source_ref,
        "source_ref_note": "Caller supplied; null when not supplied. File hashes describe the actual copied bytes.",
        "compatibility_status": "not_verified_by_staging",
        "files": [
            {"source": source, "destination": destination, "sha256": _digest(data), "bytes": len(data)}
            for source, destination, data in payloads
        ],
        "generated_files": [
            {"destination": destination, "sha256": _digest(data), "bytes": len(data)}
            for destination, data in generated.items()
        ],
    }
    output.mkdir(exist_ok=True)
    for _, destination, data in payloads:
        target = output / destination
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as handle:
            handle.write(data)
    for destination, data in generated.items():
        target = output / destination
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as handle:
            handle.write(data)
    with (output / "stage-manifest.json").open("x", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path, help="New or empty directory; parent must exist")
    parser.add_argument("--source-ref", help="Optional caller-supplied source revision (not verified by staging)")
    parser.add_argument("--register-agents", action="store_true",
                        help="Generate scoped project agent registrations in .codex/config.toml")
    parser.add_argument("--runtime-foundation", action="store_true",
                        help="Include the explicit Codex runtime and state-path policy")
    parser.add_argument("--core-orchestration", action="store_true",
                        help="Include the bounded router/audit coordinator and runtime foundation")
    parser.add_argument("--visual-evidence", action="store_true",
                        help="Include opt-in offline visual capture and its native role; implies core orchestration")
    parser.add_argument("--sitemap-analysis", action="store_true",
                        help="Include saved XML sitemap analysis and its native role; implies core orchestration")
    parser.add_argument("--agentic-report", action="store_true",
                        help="Include saved Lighthouse JSON analysis and its native role; implies core orchestration")
    parser.add_argument("--content-brief", action="store_true",
                        help="Include content-brief planning and its native author; implies core orchestration")
    parser.add_argument("--strategy-plan", action="store_true",
                        help="Include SEO strategy planning and its native planner; implies core orchestration")
    parser.add_argument("--source-drift", action="store_true",
                        help="Include saved-capture change comparison and its native reviewer; implies core orchestration")
    parser.add_argument("--schema-hook-python", type=Path,
                        help="Generate an untrusted local schema hook using this absolute prepared interpreter")
    args = parser.parse_args(argv)
    try:
        manifest = stage_pilot(args.output, source_ref=args.source_ref,
                               register_agents=args.register_agents,
                               runtime_foundation=args.runtime_foundation,
                               core_orchestration=args.core_orchestration,
                               visual_evidence=args.visual_evidence,
                               sitemap_analysis=args.sitemap_analysis,
                               agentic_report=args.agentic_report,
                               content_brief=args.content_brief,
                               strategy_plan=args.strategy_plan,
                               source_drift=args.source_drift,
                               schema_hook_python=args.schema_hook_python)
    except (OSError, StageError) as exc:
        print(f"Pilot staging refused: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"output": str(args.output.absolute()), "copied_files": len(manifest["files"]),
                      "compatibility_status": manifest["compatibility_status"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
