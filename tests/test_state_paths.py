"""No credentials or actual user state are read by path-policy tests."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("state_paths_test", ROOT / "scripts/state_paths.py")
assert SPEC and SPEC.loader
paths = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(paths)


def test_explicit_fixed_paths_do_not_create_or_read_files(tmp_path):
    state = tmp_path / "state"
    source = tmp_path / "source"
    with patch.object(Path, "read_text", side_effect=AssertionError("file read")), \
            patch.object(Path, "mkdir", side_effect=AssertionError("file write")):
        result = paths.resolve_codex_paths(str(state), source)
    assert result == {"state_root": state, "runtime": state / "runtime", "config": state / "config", "cache": state / "cache"}
    assert not state.exists()


@pytest.mark.parametrize("value", [None, "", "relative/state", "~/state"])
def test_missing_or_relative_root_is_rejected(tmp_path, value):
    with pytest.raises(ValueError, match="absolute"):
        paths.resolve_codex_paths(value, tmp_path / "source")


def test_root_home_and_source_overlap_rejected(tmp_path, monkeypatch):
    home = tmp_path / "home"
    source = home / "source"
    monkeypatch.setattr(paths.Path, "home", classmethod(lambda cls: home))
    for value in (Path(tmp_path.anchor), home, source, source / "inside", source.parent):
        with pytest.raises(ValueError):
            paths.resolve_codex_paths(str(value), source)


def test_symlinks_and_non_directory_state_are_rejected(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "linked"
    link.symlink_to(target, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        paths.resolve_codex_paths(str(link / "state"), tmp_path / "source")
    state = tmp_path / "state"
    state.mkdir()
    (state / "config").symlink_to(target, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        paths.resolve_codex_paths(str(state), tmp_path / "source")
    (state / "config").unlink()
    (state / "config").write_text("not a directory")
    with pytest.raises(ValueError, match="directories"):
        paths.resolve_codex_paths(str(state), tmp_path / "source")
    file_parent = tmp_path / "not-directory"
    file_parent.write_text("file")
    with pytest.raises(ValueError, match="ancestors"):
        paths.resolve_codex_paths(str(file_parent / "child"), tmp_path / "source")


def test_ambient_aliases_cannot_choose_paths(tmp_path, monkeypatch):
    for key in ("CLAUDE_SEO_DATA_DIR", "CLAUDE_PLUGIN_DATA", "PLUGIN_DATA", "CODEX_SEO_STATE_ROOT"):
        monkeypatch.setenv(key, str(tmp_path / "unrelated"))
    result = paths.resolve_codex_paths(str(tmp_path / "selected"), tmp_path / "source")
    assert result["state_root"] == tmp_path / "selected"
    with pytest.raises(ValueError):
        paths.resolve_codex_paths(None, tmp_path / "source")
