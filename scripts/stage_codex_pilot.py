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
AGENT_REGISTRATION = '''[agents.seo-codex-technical]
description = "Review the staged one-page pilot's shared capture for technical SEO signals and save evidence-linked findings."
config_file = "agents/seo-codex-technical.toml"

[agents.seo-codex-schema]
description = "Review the staged one-page pilot's captured structured data and save grounded schema findings."
config_file = "agents/seo-codex-schema.toml"
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
The Codex runner accepts only the pilot and refuses installation and providers.
Run its `doctor --json` before the audit. Its clean environment is process
hygiene, not a replacement for the host sandbox or permissions.
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

    payloads: list[tuple[str, str, bytes]] = []
    for source, destination in COPY_FILES + (FOUNDATION_FILES if runtime_foundation else ()):
        path = root / source
        _reject_symlinks(path)
        if not path.resolve().is_relative_to(root):
            raise StageError(f"Source is outside the source root: {source}")
        if not path.is_file():
            raise StageError(f"Required pilot source is missing: {source}")
        payloads.append((source, destination, path.read_bytes()))

    instructions = STAGE_INSTRUCTIONS + (FOUNDATION_INSTRUCTIONS if runtime_foundation else "")
    generated = {"AGENTS.md": instructions.encode("utf-8")}
    if register_agents:
        generated[".codex/config.toml"] = AGENT_REGISTRATION.encode("utf-8")
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
    parser.add_argument("--schema-hook-python", type=Path,
                        help="Generate an untrusted local schema hook using this absolute prepared interpreter")
    args = parser.parse_args(argv)
    try:
        manifest = stage_pilot(args.output, source_ref=args.source_ref,
                               register_agents=args.register_agents,
                               runtime_foundation=args.runtime_foundation,
                               schema_hook_python=args.schema_hook_python)
    except (OSError, StageError) as exc:
        print(f"Pilot staging refused: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"output": str(args.output.absolute()), "copied_files": len(manifest["files"]),
                      "compatibility_status": manifest["compatibility_status"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
