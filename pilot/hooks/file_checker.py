"""Unified quality gate — file length + TDD enforcement in a single hook.

Runs both checks and produces one combined warning via additionalContext
to avoid duplicate system-reminders from multiple hooks in the same group.
Warnings are non-blocking — they inform but never prevent edits.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _checkers.charset import check_charset
from _checkers.dotnet import DOTNET_EXTENSIONS, check_dotnet
from _checkers.go import check_go
from _checkers.python import check_python
from _checkers.tdd import (
    has_dotnet_test_file,
    has_go_test_file,
    has_python_test_file,
    has_related_failing_test,
    has_test_importing_module,
    has_test_importing_module_dotnet,
    has_test_importing_module_ts,
    has_typescript_test_file,
    is_dotnet_logic_free,
    is_inside_dotnet_test_project,
    is_test_file,
    is_trivial_edit,
    should_skip,
)
from _checkers.typescript import TS_EXTENSIONS, check_typescript
from _lib.util import find_git_root, post_tool_use_context

# Codex apply_patch section header, e.g. "*** Update File: path/to/x.py".
_APPLY_PATCH_FILE_MARKER = re.compile(r"\*\*\* (?:Update|Add) File:\s*(.+)")

_TEST_COVERAGE_REMINDER = (
    "TDD Reminder: No nearby test was identified for {name}. "
    "Check whether existing behavioral tests cover the change. Add or extend a test "
    "when behavior changes and coverage is missing; naming alone does not establish coverage. "
    "A cosmetic or declarative edit may need only a focused check."
)


def _tdd_check(tool_name: str, tool_input: dict, file_path: str) -> str:
    """Run TDD enforcement, return warning message or empty string."""
    if should_skip(file_path) or is_test_file(file_path):
        return ""
    if is_trivial_edit(tool_name, tool_input):
        return ""

    if file_path.endswith(".py"):
        path = Path(file_path).parent
        for _ in range(10):
            if has_related_failing_test(str(path), file_path):
                return ""
            if path.parent == path:
                break
            path = path.parent
        if has_python_test_file(file_path) or has_test_importing_module(file_path):
            return ""
        return _TEST_COVERAGE_REMINDER.format(name=Path(file_path).name)

    if file_path.endswith((".ts", ".tsx")):
        if has_typescript_test_file(file_path) or has_test_importing_module_ts(file_path):
            return ""
        return _TEST_COVERAGE_REMINDER.format(name=Path(file_path).name)

    if file_path.endswith(".go"):
        if has_go_test_file(file_path):
            return ""
        return _TEST_COVERAGE_REMINDER.format(name=Path(file_path).name)

    if file_path.endswith((".cs", ".razor")):
        # A file inside a .NET test project (MyApp.Tests, IntegrationTests, ...) is
        # itself test code - skip, matching check_dotnet's format-path behaviour.
        if is_inside_dotnet_test_project(file_path):
            return ""
        if has_dotnet_test_file(file_path):
            return ""
        if has_test_importing_module_dotnet(file_path):
            return ""
        if is_dotnet_logic_free(file_path):
            return ""
        return _TEST_COVERAGE_REMINDER.format(name=Path(file_path).name)

    return ""


def _extract_file_paths(tool_input: dict) -> list[str]:
    """Extract file paths from tool_input for both CC and Codex formats.

    Claude Code Edit/Write: tool_input.file_path
    Codex apply_patch: tool_input.command with '*** Update File:' / '*** Add File:' markers
    """
    file_path = tool_input.get("file_path", "")
    if file_path:
        return [file_path]

    command = tool_input.get("command", "")
    if command:
        return [p.strip() for p in _APPLY_PATCH_FILE_MARKER.findall(command)]

    return []


def _diff_added_text(added: list[str], removed: set[str]) -> str:
    """Join added lines, dropping ones also present in the replaced text.

    Unchanged context lines (present in both old and new) are removed, so a
    decorative char merely preserved by an edit is never flagged -- only chars
    on genuinely new or changed lines are.
    """
    return "\n".join(line for line in added if line not in removed)


def _extract_changed_text(tool_input: dict) -> dict[str, str]:
    """Map each edited file path to the text this edit introduced into it.

    Scopes the charset check to what the edit actually added so pre-existing
    decorative chars in untouched code -- including untouched *files* in a
    multi-file Codex patch -- are never surfaced. An empty dict means the tool
    shape was unrecognised, so the caller falls back to a whole-file scan.

    Claude Code Write: tool_input.content (whole file is authored now)
    Claude Code Edit: tool_input.old_string / new_string
    Claude Code MultiEdit: tool_input.edits[].old_string / new_string
    Codex apply_patch: tool_input.command unified diff, scoped per file
    """
    file_path = tool_input.get("file_path", "")
    if file_path:
        content = tool_input.get("content")
        if isinstance(content, str):  # Write
            return {file_path: content}

        removed: set[str] = set()
        added: list[str] = []
        edits = tool_input.get("edits")
        if isinstance(edits, list):  # MultiEdit
            for edit in edits:
                removed.update((edit.get("old_string") or "").splitlines())
            for edit in edits:
                added.extend((edit.get("new_string") or "").splitlines())
        elif "new_string" in tool_input:  # Edit
            removed.update((tool_input.get("old_string") or "").splitlines())
            added.extend((tool_input.get("new_string") or "").splitlines())
        else:
            return {}
        return {file_path: _diff_added_text(added, removed)}

    command = tool_input.get("command", "")
    if command:  # Codex apply_patch -- scope added text to each file's own hunks
        return _extract_apply_patch_text(command)

    return {}


def _extract_apply_patch_text(command: str) -> dict[str, str]:
    """Parse a Codex apply_patch command into {file_path: introduced_text}.

    Each file's added/removed lines are tracked separately so a decorative char
    added to one file is never reported against another file in the same patch.
    """
    added: dict[str, list[str]] = {}
    removed: dict[str, set[str]] = {}
    current = ""  # path of the file section currently being parsed ("" = none yet)
    for line in command.splitlines():
        marker = _APPLY_PATCH_FILE_MARKER.match(line)
        if marker:
            current = (marker.group(1) or "").strip()
            added.setdefault(current, [])
            removed.setdefault(current, set())
            continue
        if not current or line.startswith(("+++", "---")):
            continue
        if line.startswith("+"):
            added[current].append(line[1:])
        elif line.startswith("-"):
            removed[current].add(line[1:])

    return {path: _diff_added_text(lines, removed[path]) for path, lines in added.items()}


def main() -> int:
    """Single entry point — file quality + TDD in one pass."""
    try:
        hook_data = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        return 0

    tool_name = hook_data.get("tool_name", "")
    tool_input = hook_data.get("tool_input", {})

    file_paths = _extract_file_paths(tool_input)
    if not file_paths:
        return 0

    changed_text = _extract_changed_text(tool_input)

    git_root = find_git_root()
    if git_root:
        os.chdir(git_root)

    all_reasons: list[str] = []
    for file_path_str in file_paths:
        target_file = Path(file_path_str)
        if not target_file.exists():
            continue

        file_reason = ""
        if target_file.suffix == ".py":
            _, file_reason = check_python(target_file)
        elif target_file.suffix in TS_EXTENSIONS:
            _, file_reason = check_typescript(target_file)
        elif target_file.suffix == ".go":
            _, file_reason = check_go(target_file)
        elif target_file.suffix in DOTNET_EXTENSIONS:
            _, file_reason = check_dotnet(target_file)

        tdd_reason = _tdd_check(tool_name, tool_input, file_path_str)
        charset_reason = check_charset(target_file, changed_text.get(file_path_str))
        all_reasons.extend(r for r in (file_reason, tdd_reason, charset_reason) if r)

    if all_reasons:
        print(post_tool_use_context("\n".join(all_reasons)))

    return 0


if __name__ == "__main__":
    sys.exit(main())
