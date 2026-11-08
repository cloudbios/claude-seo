#!/usr/bin/env python3
"""Shared bounded evidence helpers for offline Codex planning workflows.

These helpers do not define a workflow schema or perform network, provider,
installation or publication operations. Callers own policy and lifecycle.
"""
from __future__ import annotations

import html
import json
import math
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True
_SCRIPTS = str(Path(__file__).resolve().parent)
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)
import codex_pilot as pilot  # noqa: E402

PlanningError = pilot.PilotError
MAX_JSON = 2 * 1024 * 1024


def absolute(path: Path) -> Path:
    if not path.is_absolute():
        raise PlanningError("Paths must be absolute")
    return pilot.no_symlinks(path)


def record(path: Path, limit: int = MAX_JSON) -> dict:
    raw = pilot.read_bytes(path, limit)
    return {"sha256": pilot.digest(raw), "bytes": len(raw)}


def decode(raw: bytes, limit: int = MAX_JSON) -> object:
    if len(raw) > limit:
        raise PlanningError("JSON exceeds size bound")

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise PlanningError("Duplicate JSON object key")
            result[key] = value
        return result

    def nonfinite(_):
        raise PlanningError("Nonfinite JSON number")

    try:
        value = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=pairs, parse_constant=nonfinite)
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise PlanningError("Invalid bounded JSON") from exc
    stack = [(value, 0)]
    nodes = 0
    while stack:
        item, depth = stack.pop()
        nodes += 1
        if depth > 32 or nodes > 10000:
            raise PlanningError("JSON depth or node bound exceeded")
        if isinstance(item, dict):
            stack.extend((child, depth + 1) for child in item.values())
        elif isinstance(item, list):
            stack.extend((child, depth + 1) for child in item)
        elif isinstance(item, float) and not math.isfinite(item):
            raise PlanningError("Nonfinite JSON number")
    return value


def text(value: object, maximum: int = 4000) -> bool:
    return isinstance(value, str) and bool(value.strip()) and len(value) <= maximum


def strings(value: object, count: int, maximum: int) -> bool:
    return isinstance(value, list) and len(value) <= count and all(text(item, maximum) for item in value)


def source_reference(source: dict) -> dict:
    root, manifest = pilot.load_capture(absolute(Path(source["capture"])))
    capture = manifest["capture"]
    if capture.get("complete") is not True or manifest["checks"].get("transport") != "passed":
        raise PlanningError("Sources require successful complete captures")
    transport = decode(pilot.read_bytes(root / "capture/transport.json"))
    if not isinstance(transport, dict) or any(capture.get(key) != transport.get(key) for key in ("requested_url", "final_url", "representation")):
        raise PlanningError("Capture identity disagrees with transport")
    for key in ("requested_url", "final_url"):
        if not text(capture.get(key), 4096):
            raise PlanningError("Missing capture URL")
    if capture["representation"] == "raw-http" and not (
            type(transport.get("status_code")) is int and 200 <= transport["status_code"] < 400):
        raise PlanningError("Raw HTTP capture requires a successful response")
    return {**source, "pilot_manifest_sha256": record(root / pilot.MANIFEST)["sha256"],
            "capture_sha256": capture["sha256"], "requested_url": capture["requested_url"],
            "final_url": capture["final_url"], "representation": capture["representation"]}


def source_registry(sources: list[dict]) -> list[dict]:
    """Bind an already schema-validated list to distinct saved captures."""
    result = [source_reference(source) for source in sources]
    if len({source["final_url"] for source in result}) != len(result):
        raise PlanningError("Source final URLs must be distinct")
    return result


def provenance(implementation: tuple[str, ...], key: str) -> dict:
    """Record caller-selected implementation files alongside pilot provenance."""
    value = pilot.provenance()
    value[key] = [{"destination": name, **record(pilot.ROOT / name)} for name in implementation]
    return value


def validate_provenance(value: object, implementation: tuple[str, ...], key: str) -> None:
    """Keep saved Git identity while checking current implementation bytes."""
    if not isinstance(value, dict):
        raise PlanningError("Invalid provenance")
    expected = [{"destination": name, **record(pilot.ROOT / name)} for name in implementation]
    if value.get(key) != expected:
        raise PlanningError("Planning implementation changed")
    # Compare current file identities, never rebind a saved run to a later HEAD.
    current = pilot.provenance()
    recorded = {name: item for name, item in value.items() if name != key}
    if current.get("kind") == "git-checkout":
        commit = recorded.get("source_commit")
        if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40,64}", commit):
            raise PlanningError("Invalid source commit")
        current["source_commit"] = commit
    if recorded != current:
        raise PlanningError("Source provenance changed")


def escaped(value: str) -> str:
    """HTML entities neutralize Markdown punctuation, URLs and raw HTML alike."""
    value = " ".join(value.split())
    return "".join(html.escape(char, quote=True) if char in "&<>\"'" else
                   char if char.isalnum() or char == " " else f"&#{ord(char)};" for char in value)
