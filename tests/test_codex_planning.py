"""Cross-workflow contracts for shared, offline planning evidence helpers."""
from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import codex_planning as planning  # noqa: E402


@pytest.fixture
def implementation(tmp_path, monkeypatch):
    (tmp_path / "workflow.py").write_text("# original workflow\n")
    monkeypatch.setattr(planning.pilot, "ROOT", tmp_path)
    base = {"kind": "git-checkout", "source_commit": "a" * 40,
            "files": [], "source_ref_note": "test current file hashes"}
    monkeypatch.setattr(planning.pilot, "provenance", lambda: copy.deepcopy(base))
    return tmp_path, base


def test_provenance_is_scoped_to_the_calling_workflow(implementation):
    _, base = implementation
    files = ("workflow.py",)
    plan = planning.provenance(files, "plan_files")
    brief = planning.provenance(files, "brief_files")
    planning.validate_provenance(plan, files, "plan_files")
    planning.validate_provenance(brief, files, "brief_files")
    with pytest.raises(planning.PlanningError, match="implementation changed"):
        planning.validate_provenance(plan, files, "brief_files")
    with pytest.raises(planning.PlanningError, match="implementation changed"):
        planning.validate_provenance(brief, files, "plan_files")
    assert "plan_files" not in base and "brief_files" not in base


def test_shared_provenance_preserves_head_but_rejects_changed_code(implementation):
    root, base = implementation
    files = ("workflow.py",)
    saved = planning.provenance(files, "plan_files")
    base["source_commit"] = "b" * 40
    planning.validate_provenance(saved, files, "plan_files")
    (root / "workflow.py").write_text("# changed workflow\n")
    with pytest.raises(planning.PlanningError, match="implementation changed"):
        planning.validate_provenance(saved, files, "plan_files")


def test_shared_decoder_rejects_wide_json_before_workflow_use():
    raw = b"[" + b",".join([b"0"] * 10000) + b"]"
    with pytest.raises(planning.PlanningError, match="node bound"):
        planning.decode(raw)
