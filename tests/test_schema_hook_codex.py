"""Offline Codex apply_patch feedback; no host trust or discovery claims."""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "hooks" / "validate-schema.py"
LAUNCHER = ROOT / "hooks" / "run-python-hook.js"
SPEC = importlib.util.spec_from_file_location("schema_hook_codex_test", HOOK)
hook = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(hook)


def _page(path, schema=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    schema = schema if schema is not None else {"@context": "https://schema.org", "@type": "Thing"}
    path.write_text('<script type="application/ld+json">' + json.dumps(schema) + '</script>', encoding="utf-8")


def _patch(*operations):
    return "*** Begin Patch\n" + "\n".join(operations) + "\n*** End Patch\n"


def _update(path):
    return f"*** Update File: {path}\n@@\n-old\n+new"


def _event(tmp_path, command):
    return {"hook_event_name": "PostToolUse", "tool_name": "apply_patch", "cwd": str(tmp_path),
            "tool_input": {"command": command}, "tool_response": {"success": True}}


def _run(tmp_path, event, args=(), launcher=False):
    command = [sys.executable, str(HOOK), *args]
    if launcher:
        node = shutil.which("node")
        if not node:
            pytest.skip("Node not available")
        command = [node, str(LAUNCHER), str(HOOK), *args]
    return subprocess.run(command, cwd=tmp_path, input=json.dumps(event),
                          capture_output=True, encoding="utf-8", timeout=10,
                          env={**os.environ, "CLAUDE_SEO_PYTHON": sys.executable})


def _context(result):
    assert result.returncode == 0
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert set(payload) == {"hookSpecificOutput"}
    assert set(payload["hookSpecificOutput"]) == {"hookEventName", "additionalContext"}
    assert payload["hookSpecificOutput"]["hookEventName"] == "PostToolUse"
    return payload["hookSpecificOutput"]["additionalContext"]


def test_add_update_multi_file_and_mixed_severity(tmp_path):
    _page(tmp_path / "clean.html")
    _page(tmp_path / "warning.html", {"@type": "Thing"})
    _page(tmp_path / "critical.html", {"@context": "https://schema.org", "@type": "ClaimReview"})
    result = _run(tmp_path, _event(tmp_path, _patch(
        "*** Add File: clean.html\n+anything", _update("warning.html"), _update("critical.html"))))
    assert result.returncode == 2
    assert result.stdout == ""
    assert "critical.html" in result.stderr and "ClaimReview" in result.stderr
    assert "warning.html" in result.stderr and "Missing @context" in result.stderr
    assert "clean.html" not in result.stderr


def test_clean_patch_is_silent(tmp_path):
    _page(tmp_path / "clean.html")
    result = _run(tmp_path, _event(tmp_path, _patch(_update("clean.html"))))
    assert (result.returncode, result.stdout, result.stderr) == (0, "", "")


def test_warning_only_uses_json_context_and_escaped_filename(tmp_path):
    _page(tmp_path / "folder with spaces" / "crème.html", {"@type": "Thing"})
    result = _run(tmp_path, _event(tmp_path, _patch(_update("folder with spaces/crème.html"))))
    context = _context(result)
    assert "folder with spaces" in context and "Missing @context" in context
    assert "\\u00e8" in context


def test_header_like_source_lines_do_not_add_targets(tmp_path):
    _page(tmp_path / "clean.html")
    command = _patch("*** Add File: clean.html\n+*** Update File: /secret\n+*** Move to: /secret",
                     "*** Update File: clean.html\n@@\n *** Delete File: /secret\n-*** Update File: /secret\n+new")
    result = _run(tmp_path, _event(tmp_path, command))
    assert (result.returncode, result.stdout, result.stderr) == (0, "", "")


def test_move_reads_final_destination_and_delete_never_reads(tmp_path):
    _page(tmp_path / "new.html", {"@type": "Thing"})
    _page(tmp_path / "deleted.html", {"@type": "ClaimReview"})
    command = _patch("*** Update File: old.html\n*** Move to: new.html\n@@\n-old\n+new",
                     "*** Delete File: deleted.html")
    context = _context(_run(tmp_path, _event(tmp_path, command)))
    assert "new.html" in context and "Missing @context" in context
    assert "old.html" not in context and "deleted.html" not in context and "ClaimReview" not in context


def test_pure_move_uses_existing_destination_without_hunks(tmp_path):
    _page(tmp_path / "new.html", {"@type": "Thing"})
    command = _patch("*** Update File: old.html\n*** Move to: new.html")
    assert "Missing @context" in _context(_run(tmp_path, _event(tmp_path, command)))


def test_duplicate_and_delete_then_add_validate_final_file_once(tmp_path):
    _page(tmp_path / "final.html", {"@type": "Thing"})
    command = _patch(_update("final.html"), "*** Delete File: final.html",
                     "*** Add File: final.html\n+new", _update("final.html"))
    context = _context(_run(tmp_path, _event(tmp_path, command)))
    assert context.count("Missing @context") == 1


@pytest.mark.parametrize("event", [[], None, "event", {"tool_name": "apply_patch", "tool_input": []},
                                   {"tool_name": "apply_patch", "tool_input": {"command": 1}}])
def test_invalid_event_shapes_are_bounded_feedback(tmp_path, event):
    assert "validation not completed" in _context(_run(tmp_path, event))


@pytest.mark.parametrize("command", ["touch /secret", "*** Begin Patch\n*** End Patch",
    "*** Begin Patch\n*** Add File: x.html\nnot prefixed\n*** End Patch",
    "*** Begin Patch\n*** Move to: x.html\n*** End Patch",
    "*** Begin Patch\n*** Update File: x.html\n@@\n+new\n*** Move to: other.html\n*** End Patch",
    "*** Begin Patch\n*** Update File: x.html\n*** End Patch"])
def test_invalid_envelopes_do_not_fall_back_to_shell(tmp_path, command):
    result = _run(tmp_path, _event(tmp_path, command))
    assert "validation not completed" in _context(result)
    assert "/secret" not in result.stdout


def test_missing_cwd_uses_process_working_directory(tmp_path):
    _page(tmp_path / "page.html", {"@type": "Thing"})
    event = _event(tmp_path, _patch(_update("page.html")))
    del event["cwd"]
    assert "Missing @context" in _context(_run(tmp_path, event))


@pytest.mark.parametrize("cwd", [None, 42, "relative", "\x00secret"])
def test_invalid_cwd_never_reads_files(tmp_path, cwd):
    event = _event(tmp_path, _patch(_update("page.html")))
    event["cwd"] = cwd
    assert "validation not completed" in _context(_run(tmp_path, event))


def test_path_escapes_are_redacted_while_safe_files_continue(tmp_path):
    _page(tmp_path / "safe.html", {"@type": "Thing"})
    command = _patch(_update("../CREDENTIAL_SECRET.html"),
                     _update(str(tmp_path.parent / "OUTSIDE_SECRET.html")),
                     _update("C:\\SECRET.html"), _update("safe.html"))
    context = _context(_run(tmp_path, _event(tmp_path, command)))
    assert context.count("unsafe path skipped") == 3
    assert "SECRET" not in context
    assert "Missing @context" in context


def test_apply_patch_ignores_injected_legacy_file_path(tmp_path):
    _page(tmp_path / "safe.html")
    outside = tmp_path.parent / (tmp_path.name + "-OUTSIDE_SECRET.html")
    _page(outside, {"@type": "ClaimReview"})
    event = _event(tmp_path, _patch(_update("safe.html")))
    event["tool_input"]["file_path"] = str(outside)
    result = _run(tmp_path, event)
    assert (result.returncode, result.stdout, result.stderr) == (0, "", "")


def test_symlink_file_parent_and_move_source_are_rejected(tmp_path):
    actual = tmp_path / "actual"
    _page(actual / "bad.html", {"@type": "ClaimReview"})
    try:
        (tmp_path / "link").symlink_to(actual, target_is_directory=True)
        (tmp_path / "link.html").symlink_to(actual / "bad.html")
    except OSError as exc:
        pytest.skip(f"Symlinks unavailable: {exc}")
    command = _patch(_update("link.html"), _update("link/bad.html"),
        "*** Update File: link.html\n*** Move to: actual/bad.html\n@@\n-old\n+new")
    context = _context(_run(tmp_path, _event(tmp_path, command)))
    assert context.count("unsafe path skipped") == 3
    assert "ClaimReview" not in context


def test_missing_nonregular_unsupported_and_template_targets_are_explicit(tmp_path):
    (tmp_path / "directory.html").mkdir()
    (tmp_path / "source.astro").write_text("not parsed")
    (tmp_path / "template.tsx").write_text('<script type="application/ld+json">{schema}</script>')
    command = _patch(*(_update(name) for name in ("missing.html", "directory.html", "source.astro", "template.tsx")))
    context = _context(_run(tmp_path, _event(tmp_path, command)))
    for expected in ("unreadable", "nonregular", "unsupported file type", "template-only"):
        assert expected in context


def test_mixed_template_and_literal_blocks_preserve_skip_and_errors(tmp_path):
    (tmp_path / "page.tsx").write_text('<script type="application/ld+json">{schema}</script>'
                                      '<script type="application/ld+json">{"@type":"Thing"}</script>')
    context = _context(_run(tmp_path, _event(tmp_path, _patch(_update("page.tsx")))))
    assert "template-only" in context and "Missing @context" in context


def test_event_and_operation_quotas(tmp_path, monkeypatch):
    monkeypatch.setattr(hook, "MAX_PATCH_OPERATIONS", 1)
    event = _event(tmp_path, _patch(_update("one.html"), _update("two.html")))
    assert "validation not completed" in hook._codex_feedback(event)[1][0]
    oversized = _event(tmp_path, "x" * hook.MAX_EVENT_BYTES)
    assert "size limit" in _context(_run(tmp_path, oversized))


def test_file_and_aggregate_quotas_do_not_read_over_limit(tmp_path, monkeypatch):
    _page(tmp_path / "one.html")
    _page(tmp_path / "two.html")
    size = (tmp_path / "one.html").stat().st_size
    monkeypatch.setattr(hook, "MAX_FILE_BYTES", size - 1)
    event = _event(tmp_path, _patch(_update("one.html")))
    assert "file exceeds size limit" in hook._codex_feedback(event)[1][0]
    monkeypatch.setattr(hook, "MAX_FILE_BYTES", size + 1)
    monkeypatch.setattr(hook, "MAX_TOTAL_BYTES", size)
    event = _event(tmp_path, _patch(_update("one.html"), _update("two.html")))
    assert "aggregate file limit" in hook._codex_feedback(event)[1][0]


def test_changed_file_identity_is_refused_before_read(tmp_path):
    path = tmp_path / "page.html"
    _page(path)
    expected = path.stat()
    replacement = tmp_path / "replacement.html"
    _page(replacement)
    os.replace(replacement, path)
    with pytest.raises(OSError, match="File changed"):
        hook._read_regular_file(path, expected, 100)


def test_posix_parent_replacement_with_symlink_is_refused(tmp_path):
    if os.open not in os.supports_dir_fd or not hasattr(os, "O_NOFOLLOW"):
        pytest.skip("POSIX no-follow directory traversal unavailable")
    folder = tmp_path / "folder"
    path = folder / "page.html"
    _page(path)
    expected = path.stat()
    moved = tmp_path / "moved"
    folder.rename(moved)
    folder.symlink_to(moved, target_is_directory=True)
    with pytest.raises(OSError):
        hook._read_regular_file(path, expected, 100)


@pytest.mark.parametrize("kind", ["objects", "values", "depth", "placeholders", "blocks"])
def test_schema_expansion_limits_are_explicit_and_skip_validator(tmp_path, monkeypatch, kind):
    path = tmp_path / "page.html"
    if kind == "objects":
        _page(path, {"@context": "https://schema.org", "@graph": [{}] * 130})
    elif kind == "values":
        _page(path, {"@type": "Thing", "values": [0] * 5000})
    elif kind == "depth":
        nested = {}
        for _ in range(66):
            nested = {"nested": nested}
        _page(path, nested)
    elif kind == "placeholders":
        _page(path, {"@type": "Thing", "name": "REPLACE " * 130})
    else:
        _page(path)
        path.write_text(path.read_text() * 129)
    monkeypatch.setattr(hook, "validate_jsonld", lambda *_: pytest.fail("Oversized analysis entered validator"))
    critical, warnings = hook._codex_feedback(_event(tmp_path, _patch(_update("page.html"))))
    assert critical == []
    assert len(warnings) == 1 and "schema analysis limit exceeded; not validated" in warnings[0]


def test_feedback_is_bounded_without_suppressing_critical_status(capsys):
    result = hook._emit_feedback(["critical"] * 200, ["warning"] * 200, "prefix")
    captured = capsys.readouterr()
    assert result == 2 and captured.out == ""
    assert captured.err.count("  - critical") == hook.MAX_FEEDBACK_ITEMS
    assert "Further findings omitted" in captured.err


def test_escaped_placeholder_expansion_is_also_bounded(tmp_path, monkeypatch):
    path = tmp_path / "page.html"
    path.write_text('<script type="application/ld+json">{"name":"'
                    + "REPL\\u0041CE " * 130 + '"}</script>')
    monkeypatch.setattr(hook, "validate_jsonld", lambda *_: pytest.fail("Decoded token limit bypassed"))
    critical, warnings = hook._codex_feedback(_event(tmp_path, _patch(_update("page.html"))))
    assert critical == []
    assert "schema analysis limit exceeded" in warnings[0]


def test_legacy_argv_and_file_path_still_work(tmp_path):
    file = tmp_path / "legacy.html"
    _page(file, {"@type": "Thing"})
    for args, event in [([str(file)], {"bad": "event"}),
                        ([], {"tool_name": "Write", "tool_input": {"file_path": str(file)}})]:
        assert "Missing @context" in _context(_run(tmp_path, event, args=args))
    _page(file, {"@type": "ClaimReview"})
    result = _run(tmp_path, {}, args=[str(file)])
    assert result.returncode == 2 and result.stdout == "" and "ClaimReview" in result.stderr


def test_launcher_forwards_stdin_and_critical_feedback(tmp_path):
    _page(tmp_path / "page.html", {"@type": "ClaimReview"})
    result = _run(tmp_path, _event(tmp_path, _patch(_update("page.html"))),
                  args=["${tool_input.file_path}"], launcher=True)
    assert result.returncode == 2 and result.stdout == ""
    assert "page.html" in result.stderr and "ClaimReview" in result.stderr
