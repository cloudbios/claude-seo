"""Explicit Codex provider state paths; legacy callers keep their original paths.

No credentials are migrated or discovered in home directories. Relative credential
references resolve under the explicit config directory; absolute references must
also remain there. This is path hygiene, not an operating-system sandbox.
"""
from __future__ import annotations

import os
from pathlib import Path


def codex_active() -> bool:
    return any(os.environ.get(k) for k in ("CODEX_SEO_STATE_ROOT", "CODEX_SEO_CONFIG_DIR", "CODEX_SEO_CACHE_DIR", "CODEX_SEO_RUNTIME_DIR"))


def _checked(path: Path) -> Path:
    if not path.is_absolute():
        raise ValueError("Codex state paths must be absolute")
    for part in (path, *path.parents):
        if part.is_symlink():
            raise ValueError("Codex state paths must not contain symlinks")
    return path.resolve()


def state_dir(kind: str) -> Path:
    raw = os.environ.get(f"CODEX_SEO_{kind.upper()}_DIR")
    root = os.environ.get("CODEX_SEO_STATE_ROOT")
    if not raw and not root:
        raise ValueError("Codex requires explicit state configuration")
    path = _checked(Path(raw) if raw else Path(root) / kind)
    if root and path != _checked(Path(root)) / kind:
        raise ValueError("Codex state directories must belong to the explicit state root")
    return path


def _path(kind: str, name: str, legacy: str | Path | None) -> Path:
    if not codex_active():
        if legacy is None:
            raise ValueError("No legacy path supplied")
        return Path(legacy).expanduser()
    base = state_dir(kind)
    path = _checked(base / name)
    if path != base and base not in path.parents:
        raise ValueError("Codex path escapes its state directory")
    return path


def config_path(name: str, legacy: str | Path | None = None) -> Path:
    return _path("config", name, legacy)


def cache_path(name: str, legacy: str | Path | None = None) -> Path:
    return _path("cache", name, legacy)


def runtime_path(name: str, legacy: str | Path | None = None) -> Path:
    return _path("runtime", name, legacy)


def credential_path(value: str | Path) -> str:
    if not codex_active():
        return os.path.expanduser(str(value))
    base = state_dir("config")
    path = _checked(base / value)
    if base not in path.parents:
        raise ValueError("Codex credential files must be inside the explicit config directory")
    return str(path)


def write_allowed() -> bool:
    return not codex_active() or os.environ.get("CODEX_SEO_ALLOW_WRITE") == "1"


def require_write() -> None:
    if not write_allowed():
        raise ValueError("This operation requires explicit run --allow-write authorization")
