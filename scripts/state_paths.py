"""Pure path policy for the prepared Codex runtime; no migration or I/O writes.

These paths do not retrofit isolation onto unported provider/auth modules.
The runtime must keep those modules outside its Codex dispatch allowlist.
"""
from __future__ import annotations

import os
from pathlib import Path


def _reject_symlinks(path: Path) -> None:
    for candidate in (path, *path.parents):
        if candidate.is_symlink():
            raise ValueError("Codex state paths must not contain symlinks")


def resolve_codex_paths(state_root: str | None, source_root: Path) -> dict[str, Path]:
    """Return fixed paths without creating or reading configuration files.

    The caller owns the parent directory. This path policy is not an OS sandbox
    and cannot prevent concurrent filesystem replacement by another process.
    """
    if not state_root or not Path(state_root).is_absolute():
        raise ValueError("Codex requires an explicit absolute --state-root")
    path = Path(os.path.abspath(state_root))
    _reject_symlinks(path)
    if any(parent.exists() and not parent.is_dir() for parent in path.parents):
        raise ValueError("Codex state ancestors must be directories")
    path = path.resolve()
    source = source_root.resolve()
    if path == Path(path.anchor) or path == Path.home().resolve():
        raise ValueError("Codex state root must be a dedicated directory, not home or filesystem root")
    if path == source or path in source.parents or source in path.parents:
        raise ValueError("Codex state root must not overlap the source directory")
    paths = {"state_root": path, "runtime": path / "runtime", "config": path / "config", "cache": path / "cache"}
    for value in paths.values():
        _reject_symlinks(value)
        if value.exists() and not value.is_dir():
            raise ValueError("Codex state paths must be directories")
    return paths
