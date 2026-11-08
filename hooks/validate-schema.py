#!/usr/bin/env python3
"""Post-edit schema feedback for Claude file edits and Codex apply_patch events.

Validates JSON-LD schema after file edits. The file is already written when
a PostToolUse hook runs, so nothing here can undo the edit; the hook makes
sure Claude reads what is wrong:

- critical errors (placeholders, deprecated or retired types): exit 2, with
  the errors on stderr, which Claude Code feeds back to Claude;
- warnings only: exit 0, with the warnings as hookSpecificOutput
  additionalContext JSON on stdout, which Claude reads without an error
  notice (exit 1 would show them to the user only).

Hook configuration in ~/.claude/settings.json:
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "node",
            "args": [
              "${CLAUDE_PLUGIN_ROOT}/hooks/run-python-hook.js",
              "${CLAUDE_PLUGIN_ROOT}/hooks/validate-schema.py",
              "${tool_input.file_path}"
            ]
          }
        ]
      }
    ]
  }
}

Note: matcher filters by tool name only (Edit, Write). The script itself
checks if the file contains schema markup before validating.
"""

import json
import os
import re
import stat
import sys
from pathlib import Path, PureWindowsPath
from typing import Any, List

BRACKET_PLACEHOLDERS = (
    "[Business Name]",
    "[City]",
    "[State]",
    "[Phone]",
    "[Address]",
    "[Your",
    "[INSERT",
    "[URL]",
    "[Email]",
)
BARE_PLACEHOLDER_RE = re.compile(r"\bREPLACE(?:_[A-Z]+)*\b")

# Match every <script ...>...</script> pair, then filter on the type attribute.
# The previous pattern required ``type`` to be the first and only attribute, so
# blocks carrying a CSP ``nonce``, an ``id`` or ``data-*`` attributes, or an
# unquoted type value were skipped without validation.
#
# The attribute group is a small tokenizer, not a plain ``[^>]*``: it consumes a
# double-quoted value, a single-quoted value, or a run of characters that is
# neither a quote nor ``>``. A ``[^>]*`` scan ends the tag at the first ``>`` it
# sees, quoted or not, so an attribute value containing ``>`` (``data-cond="a>b"``,
# a templated nonce) truncated the tag early and fed the remainder of the
# attributes plus the real body to the JSON parser as garbage. Treating a quoted
# span as atomic keeps an embedded ``>`` from ending the tag prematurely.
# The fallback class excludes both quote characters: if it matched an
# apostrophe, the alternation would be ambiguous and a tag with many
# apostrophes and no closing tag would backtrack exponentially, hanging the
# blocking hook.
_ATTRS_RE = r'(?:"[^"]*"|\'[^\']*\'|[^"\'>])*'
SCRIPT_TAG_RE = re.compile(
    r"<script\b(" + _ATTRS_RE + r")>(.*?)</script\s*>", re.DOTALL | re.IGNORECASE
)
LD_JSON_TYPE_RE = re.compile(
    r"""(?:^|\s)type\s*=\s*"""
    r"""(?:"application/ld\+json"|'application/ld\+json'|application/ld\+json(?=\s|$))""",
    re.IGNORECASE,
)

# Server- or client-side template expressions that render JSON-LD at runtime.
# The hook runs on .jsx/.tsx/.vue/.svelte/.php/.ejs sources, where the script
# body is frequently an expression rather than literal JSON. Those blocks cannot
# be validated statically and must not be reported as invalid JSON.
SERVER_TEMPLATE_RE = re.compile(
    r"""^(?:
        <\?(?:php\b|=)            # <?php ... ?> / <?= ... ?>
      | <%                        # EJS / ERB
    )""",
    re.VERBOSE,
)
COMPONENT_EXPRESSION_RE = re.compile(
    r"""^(?:
        \{\{                      # Vue / Handlebars / Twig
      | \{@html\b                 # Svelte
      | \$\{                      # JS template literal
      | \{\s*[A-Za-z_$][\w$.]*    # JSX expression: {schema} / {JSON.stringify(...)}
    )""",
    re.VERBOSE,
)
COMPONENT_EXTENSIONS = (".jsx", ".tsx", ".vue", ".svelte")

SCHEMA_ORG_CONTEXTS = frozenset(
    {"https://schema.org", "http://schema.org", "https://schema.org/", "http://schema.org/"}
)
MAX_EVENT_BYTES = 1024 * 1024
MAX_PATCH_OPERATIONS = 256
MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_TOTAL_BYTES = 20 * 1024 * 1024
MAX_FEEDBACK_ITEMS = 128
MAX_SCHEMA_BLOCKS = 128
MAX_SCHEMA_VALUES = 4096
MAX_SCHEMA_OBJECTS = 128
MAX_SCHEMA_DEPTH = 64
MAX_PLACEHOLDER_OCCURRENCES = 128
VALID_EXTENSIONS = (".html", ".htm", ".jsx", ".tsx", ".vue", ".svelte", ".php", ".ejs")


def _configure_utf8() -> None:
    """Keep hook diagnostics printable on legacy Windows console encodings."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            reconfigure(encoding="utf-8", errors="replace")


def _extract_ld_json_blocks(content: str) -> List[str]:
    """Return the bodies of every ``<script type="application/ld+json">`` block.

    Attribute order, extra attributes (``nonce``, ``id``, ``data-*``), tag case
    and unquoted type values are all accepted; only the type value is decisive.
    """
    blocks = []
    for attributes, body in SCRIPT_TAG_RE.findall(content):
        if LD_JSON_TYPE_RE.search(attributes):
            blocks.append(body)
    return blocks


def _is_template_expression(block: str, filepath: str = "") -> bool:
    """True when the script body is rendered at runtime rather than literal JSON.

    Server-side markers (PHP, EJS) are never valid JSON and are skipped for
    every file type. Component expressions (JSX, Vue, Svelte, template
    literals) are only skipped in component sources, so a malformed object
    literal in a plain ``.html`` file is still reported.
    """
    if SERVER_TEMPLATE_RE.match(block):
        return True
    if filepath.lower().endswith(COMPONENT_EXTENSIONS):
        return bool(COMPONENT_EXPRESSION_RE.match(block))
    return False


def _is_schema_org_context(value: Any) -> bool:
    """Accept the schema.org context in its string, list and object forms."""
    if isinstance(value, str):
        return value in SCHEMA_ORG_CONTEXTS
    if isinstance(value, list):
        return any(_is_schema_org_context(item) for item in value)
    if isinstance(value, dict):
        return _is_schema_org_context(value.get("@vocab"))
    return False


def validate_jsonld(content: str, filepath: str = "") -> List[str]:
    """Validate JSON-LD blocks in HTML content."""
    errors = []
    blocks = _extract_ld_json_blocks(content)

    if not blocks:
        return []  # No schema found; not an error

    for i, block in enumerate(blocks, 1):
        block = block.strip()
        if _is_template_expression(block, filepath):
            continue  # Rendered at runtime; nothing to validate statically
        try:
            data = json.loads(block)
        except json.JSONDecodeError as e:
            errors.append(f"Block {i}: Invalid JSON; {e}")
            continue

        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    errors.extend(_validate_schema_object(item, i))
                else:
                    errors.append(f"Block {i}: JSON-LD list members must be objects")
        elif isinstance(data, dict):
            errors.extend(_validate_schema_object(data, i))
        else:
            errors.append(f"Block {i}: JSON-LD root must be an object or list")

    return errors


def _validate_schema_object(
    obj: dict[str, Any], block_num: int, *, inherited_context: bool = False
) -> List[str]:
    """Validate one schema node, including members of a top-level ``@graph``."""
    errors = []
    prefix = f"Block {block_num}"

    # Check @context
    if "@context" not in obj and not inherited_context:
        errors.append(f"{prefix}: Missing @context")
    elif "@context" in obj and not _is_schema_org_context(obj["@context"]):
        errors.append(f"{prefix}: @context should be 'https://schema.org'")

    graph = obj.get("@graph")
    has_graph = isinstance(graph, list)

    # A graph container does not need its own @type. Its object members do.
    if "@type" not in obj and not has_graph:
        errors.append(f"{prefix}: Missing @type")

    # Check for placeholder text
    placeholder_scope = {key: value for key, value in obj.items() if key != "@graph"}
    text = json.dumps(placeholder_scope, ensure_ascii=False)
    for p in BRACKET_PLACEHOLDERS:
        if p.lower() in text.lower():
            errors.append(f"{prefix}: Contains placeholder text: {p}")
    for placeholder in BARE_PLACEHOLDER_RE.findall(text):
        errors.append(f"{prefix}: Contains placeholder text: {placeholder}")

    # Check for deprecated types
    schema_type = obj.get("@type", "")
    deprecated = {
        "HowTo": "deprecated September 2023",
        "SpecialAnnouncement": "deprecated July 31, 2025",
        "CourseInfo": "retired June 2025",
        "EstimatedSalary": "retired June 2025",
        "LearningVideo": "retired June 2025",
        "ClaimReview": "retired June 2025; fact-check rich results discontinued",
        "VehicleListing": "retired June 2025; vehicle listing structured data discontinued",
    }
    schema_types = schema_type if isinstance(schema_type, list) else [schema_type]
    for item_type in schema_types:
        if isinstance(item_type, str) and item_type in deprecated:
            errors.append(f"{prefix}: @type '{item_type}' is {deprecated[item_type]}")

    # Check for restricted types used incorrectly.
    # FAQPage is intentionally NOT flagged: Google retired FAQ rich results for
    # all sites (May 7, 2026), but FAQPage remains a valid Schema.org type.
    # This project makes no claim of a confirmed AI or ranking benefit.
    restricted: dict = {}
    for item_type in schema_types:
        if isinstance(item_type, str) and item_type in restricted:
            errors.append(f"{prefix}: @type '{item_type}' is {restricted[item_type]}; verify site qualifies")

    if "@graph" in obj:
        if not isinstance(graph, list):
            errors.append(f"{prefix}: @graph must be a list")
        else:
            context_is_inherited = inherited_context or "@context" in obj
            for index, item in enumerate(graph, 1):
                if not isinstance(item, dict):
                    errors.append(
                        f"{prefix}: @graph member {index} must be an object"
                    )
                    continue
                errors.extend(
                    _validate_schema_object(
                        item,
                        block_num,
                        inherited_context=context_is_inherited,
                    )
                )

    return errors


def _read_input():
    """Preserve legacy path precedence; otherwise read one bounded hook event.

    Claude Code's documented hook contract delivers the event as JSON on stdin;
    the argv template is kept for harnesses that substitute it. Whichever yields
    an existing file wins.
    """
    if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]):
        return sys.argv[1], None, []
    try:
        if not sys.stdin.isatty():
            raw = sys.stdin.read(MAX_EVENT_BYTES + 1)
            if len(raw.encode("utf-8")) > MAX_EVENT_BYTES:
                return None, None, ["Hook event exceeds the size limit; validation not completed."]
            if raw.strip():
                event = json.loads(raw)
                if not isinstance(event, dict):
                    return None, None, ["Invalid hook event object; validation not completed."]
                # Codex input must use the contained patch-target path, even if
                # an unexpected legacy field is also present in the event.
                if event.get("tool_name") == "apply_patch":
                    return None, event, []
                tool_input = event.get("tool_input")
                if isinstance(tool_input, dict):
                    fp = tool_input.get("file_path")
                    if isinstance(fp, str) and os.path.isfile(fp):
                        return fp, None, []
    except (OSError, ValueError, RecursionError):
        return None, None, ["Unreadable or invalid hook event; validation not completed."]
    return None, None, []


class PatchInputError(ValueError):
    """A patch envelope cannot safely identify its final on-disk targets."""


def _patch_targets(command):
    """Parse operation boundaries, never source contents or executable commands.

    Paths in added/context lines carry a leading +/space and cannot become
    operation headers. A move is only legal immediately after an update header.
    Returned deletions cancel an earlier target; subsequent adds can restore it.
    """
    if not isinstance(command, str):
        raise PatchInputError("Patch command must be a string.")
    lines = command.splitlines()
    if len(lines) < 3 or lines[0] != "*** Begin Patch" or lines[-1] != "*** End Patch":
        raise PatchInputError("Patch envelope is missing or malformed.")
    operations = []
    index = 1
    while index < len(lines) - 1:
        line = lines[index]
        kind = next((kind for kind in ("Add", "Update", "Delete")
                     if line.startswith(f"*** {kind} File: ")), None)
        if kind is None:
            raise PatchInputError("Invalid patch operation header.")
        path = line[len(f"*** {kind} File: "):]
        if not path or "\x00" in path:
            raise PatchInputError("Invalid patch path.")
        index += 1
        source = path
        if kind == "Update" and index < len(lines) - 1 and lines[index].startswith("*** Move to: "):
            path = lines[index][len("*** Move to: "):]
            if not path or "\x00" in path:
                raise PatchInputError("Invalid move path.")
            index += 1
        body_lines = 0
        at_end = False
        while index < len(lines) - 1:
            body = lines[index]
            if any(body.startswith(f"*** {operation} File: ") for operation in ("Add", "Update", "Delete")):
                break
            if kind == "Delete" or at_end:
                raise PatchInputError("Unexpected patch operation body.")
            if kind == "Add":
                valid = body.startswith("+")
            else:
                valid = body.startswith((" ", "+", "-")) or body == "@@" or body.startswith("@@ ")
                if body == "*** End of File":
                    valid, at_end = True, True
            if not valid:
                raise PatchInputError("Invalid patch body or misplaced move header.")
            body_lines += 1
            index += 1
        if kind == "Update" and not body_lines and source == path:
            raise PatchInputError("Update operation has no body.")
        operations.append((kind, source, path))
        if len(operations) > MAX_PATCH_OPERATIONS:
            raise PatchInputError("Patch operation limit exceeded.")
    return operations


def _no_symlinks(path):
    return not any(part.is_symlink() for part in (path, *path.parents))


def _safe_patch_path(root, value):
    """Contain paths before opening; rejected values never enter diagnostics."""
    path = Path(value)
    if ".." in path.parts or (os.name != "nt" and PureWindowsPath(value).drive):
        raise PatchInputError("Path outside the patch working directory was skipped.")
    path = path if path.is_absolute() else root / path
    if not _no_symlinks(path):
        raise PatchInputError("Symlink path was skipped.")
    path = path.resolve()
    if path == root or not path.is_relative_to(root):
        raise PatchInputError("Path outside the patch working directory was skipped.")
    return path


def _read_regular_file(path, expected, limit):
    """Bound reads and refuse changed files; anchor POSIX traversal without links.

    Windows uses the same before/after file-identity check but lacks this POSIX
    directory-descriptor traversal. Neither path reads a replacement FIFO.
    """
    directory_fd = file_fd = None
    try:
        flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0)
        if os.open in os.supports_dir_fd and hasattr(os, "O_NOFOLLOW"):
            directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
            directory_fd = os.open(path.anchor, directory_flags)
            for part in path.parts[1:-1]:
                next_fd = os.open(part, directory_flags, dir_fd=directory_fd)
                os.close(directory_fd)
                directory_fd = next_fd
            file_fd = os.open(path.name, flags | os.O_NOFOLLOW, dir_fd=directory_fd)
        else:
            file_fd = os.open(path, flags)
        actual = os.fstat(file_fd)
        if not stat.S_ISREG(actual.st_mode) or (actual.st_dev, actual.st_ino) != (expected.st_dev, expected.st_ino):
            raise OSError("File changed during validation")
        with os.fdopen(file_fd, "rb") as handle:
            file_fd = None
            return handle.read(limit + 1)
    finally:
        if file_fd is not None:
            os.close(file_fd)
        if directory_fd is not None:
            os.close(directory_fd)


def _schema_within_limits(blocks, filepath):
    """Bound Codex-only analysis expansion before the legacy recursive validator.

    JSON decoding is bounded by the file cap. Invalid JSON is left for the
    validator's existing diagnostic; excessive recursion is an incomplete check.
    The iterative walk bounds graph width/depth, and repeated placeholder tokens
    are bounded before findall in the legacy validator can allocate its results.
    """
    if len(blocks) > MAX_SCHEMA_BLOCKS:
        return False
    values = objects = placeholders = 0
    for block in blocks:
        block = block.strip()
        if _is_template_expression(block, filepath):
            continue
        try:
            data = json.loads(block)
        except json.JSONDecodeError:
            continue
        except RecursionError:
            return False
        pending = [(data, 0)]
        while pending:
            item, depth = pending.pop()
            values += 1
            if values > MAX_SCHEMA_VALUES or depth > MAX_SCHEMA_DEPTH:
                return False
            texts = (item,) if isinstance(item, str) else item.keys() if isinstance(item, dict) else ()
            for text in texts:
                for _ in BARE_PLACEHOLDER_RE.finditer(text):
                    placeholders += 1
                    if placeholders > MAX_PLACEHOLDER_OCCURRENCES:
                        return False
            if isinstance(item, dict):
                objects += 1
                if objects > MAX_SCHEMA_OBJECTS:
                    return False
                if len(item) > MAX_SCHEMA_VALUES - values - len(pending):
                    return False
                pending.extend((value, depth + 1) for value in item.values())
            elif isinstance(item, list):
                if len(item) > MAX_SCHEMA_VALUES - values - len(pending):
                    return False
                pending.extend((value, depth + 1) for value in item)
    return True


def _codex_feedback(event):
    """Return separate critical/warning lists for safe final files in a patch."""
    critical, warnings = [], []
    tool_input = event.get("tool_input")
    if not isinstance(tool_input, dict):
        return [], ["Invalid apply_patch input; validation not completed."]
    try:
        operations = _patch_targets(tool_input.get("command"))
        cwd = event.get("cwd", os.getcwd())
        if not isinstance(cwd, str) or not cwd or "\x00" in cwd:
            raise PatchInputError("Invalid patch working directory.")
        root = Path(cwd)
        if not root.is_absolute() or not _no_symlinks(root) or not root.is_dir():
            raise PatchInputError("Invalid or symlinked patch working directory.")
        root = root.resolve()
    except (PatchInputError, OSError, ValueError):
        return [], ["Invalid or oversized apply_patch envelope or working directory; validation not completed."]

    targets = {}
    for number, (kind, source, destination) in enumerate(operations, 1):
        try:
            # Check both ends of a move, even though only its final file is read.
            old_path = _safe_patch_path(root, source)
            path = _safe_patch_path(root, destination)
        except (PatchInputError, OSError, ValueError, RuntimeError):
            warnings.append(f"Operation {number}: unsafe path skipped; validation not completed.")
            continue
        if kind == "Delete":
            targets.pop(path, None)
        else:
            if old_path != path:
                targets.pop(old_path, None)
            targets[path] = number

    total = 0
    for path, number in targets.items():
        # The relative label is escaped and bounded; rejected paths are never printed.
        label = json.dumps(str(path.relative_to(root)), ensure_ascii=True)[:200]
        prefix = f"Operation {number} ({label})"
        if path.suffix.lower() not in VALID_EXTENSIONS:
            warnings.append(f"{prefix}: unsupported file type; not validated.")
            continue
        try:
            info = path.lstat()
            if not stat.S_ISREG(info.st_mode) or not _no_symlinks(path):
                warnings.append(f"{prefix}: nonregular or symlink file; not validated.")
                continue
            if info.st_size > MAX_FILE_BYTES:
                warnings.append(f"{prefix}: file exceeds size limit; not validated.")
                continue
            remaining = MAX_TOTAL_BYTES - total
            if info.st_size > remaining:
                warnings.append(f"{prefix}: aggregate file limit exceeded; not validated.")
                continue
            data = _read_regular_file(path, info, min(MAX_FILE_BYTES, remaining))
            total += len(data)
            if len(data) > min(MAX_FILE_BYTES, remaining):
                warnings.append(f"{prefix}: file grew beyond size limit; not validated.")
                continue
            content = data.decode("utf-8", errors="replace")
            blocks = _extract_ld_json_blocks(content)
            if not _schema_within_limits(blocks, str(path)):
                warnings.append(f"{prefix}: schema analysis limit exceeded; not validated.")
                continue
            skipped = sum(_is_template_expression(block.strip(), str(path)) for block in blocks)
            if skipped:
                warnings.append(f"{prefix}: {skipped} template-only schema block(s); not statically validated.")
                if skipped == len(blocks):
                    continue
            errors = validate_jsonld(content, str(path))
            for error in errors:
                target = critical if any(word in error.lower() for word in ("placeholder", "deprecated", "retired")) else warnings
                # Parser exception text can include source content: keep only its location.
                if ": Invalid JSON;" in error:
                    error = error.split(": Invalid JSON;", 1)[0] + ": Invalid JSON."
                target.append(f"{prefix}: {error[:1000]}")
        except (OSError, ValueError, RecursionError, RuntimeError):
            warnings.append(f"{prefix}: unreadable or unsupported content; validation not completed.")
    return critical, warnings


def _emit_feedback(critical, warnings, context_prefix):
    """One aggregate response, keeping critical feedback on stderr for both hosts."""
    if len(critical) + len(warnings) > MAX_FEEDBACK_ITEMS:
        critical = critical[:MAX_FEEDBACK_ITEMS]
        warnings = warnings[:max(0, MAX_FEEDBACK_ITEMS - len(critical))]
        warnings.append("Further findings omitted from bounded feedback; validation needs review.")
    if critical:
        print("🛑 Schema validation ERRORS (flagged for Claude, fix before shipping):", file=sys.stderr)
        for error in critical:
            print(f"  - {error}", file=sys.stderr)
        if warnings:
            print("⚠️  Also warnings:", file=sys.stderr)
            for warning in warnings:
                print(f"  - {warning}", file=sys.stderr)
        return 2
    if warnings:
        context = context_prefix + "\n" + "\n".join(f"- {warning}" for warning in warnings)
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": context}}))
    return 0


def main():
    _configure_utf8()
    filepath, event, diagnostics = _read_input()
    if event is not None:
        critical, warnings = _codex_feedback(event)
        sys.exit(_emit_feedback(critical, diagnostics + warnings, "Schema validation feedback for apply_patch:"))
    if diagnostics:
        sys.exit(_emit_feedback([], diagnostics, "Schema validation feedback:"))
    if not filepath:
        sys.exit(0)

    # Only validate HTML-like files
    if not filepath.lower().endswith(VALID_EXTENSIONS):
        sys.exit(0)

    # File-size guard: skip files >10MB to bound memory + hook latency.
    # Real source files almost never exceed this; bigger inputs are typically
    # generated, minified bundles or accidental binary writes.
    try:
        if os.path.getsize(filepath) > MAX_FILE_BYTES:
            sys.exit(0)
    except OSError:
        sys.exit(0)

    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except (OSError, IOError):
        sys.exit(0)

    errors = validate_jsonld(content, filepath)

    if not errors:
        sys.exit(0)

    # Categorize errors
    critical_keywords = ["placeholder", "deprecated", "retired"]
    critical = [e for e in errors if any(kw in e.lower() for kw in critical_keywords)]
    warnings = [e for e in errors if e not in critical]

    sys.exit(_emit_feedback(critical, warnings, "Schema validation warnings for " + filepath + ":"))


if __name__ == "__main__":
    main()
