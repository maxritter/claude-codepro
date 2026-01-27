#!/usr/bin/env python3
"""TDD enforcer - reminds to use TDD when modifying implementation code.

This is a NON-BLOCKING reminder (PostToolUse hook) - edits always complete,
then a reminder is shown to encourage TDD practices when appropriate.
Returns exit code 2 to show TDD reminders to Claude.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

YELLOW = "\033[0;33m"
NC = "\033[0m"

EXCLUDED_EXTENSIONS = [
    ".md",
    ".rst",
    ".txt",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".lock",
    ".sum",
    ".env",
    ".env.example",
    ".sql",
    ".tsx",
]

EXCLUDED_DIRS = [
    "/cdk/",
    "/infra/",
    "/infrastructure/",
    "/terraform/",
    "/pulumi/",
    "/stacks/",
    "/cloudformation/",
    "/aws/",
    "/deploy/",
    "/migrations/",
    "/alembic/",
    "/generated/",
    "/proto/",
    "/__generated__/",
    "/dist/",
    "/build/",
    "/node_modules/",
    "/.venv/",
    "/venv/",
    "/__pycache__/",
]


def should_skip(file_path: str) -> bool:
    """Check if file should be skipped based on extension or directory."""
    path = Path(file_path)

    if path.suffix in EXCLUDED_EXTENSIONS:
        return True

    if path.name in EXCLUDED_EXTENSIONS:
        return True

    for excluded_dir in EXCLUDED_DIRS:
        if excluded_dir in file_path:
            return True

    return False


def is_test_file(file_path: str) -> bool:
    """Check if file is a test file."""
    path = Path(file_path)
    name = path.name

    if name.endswith(".py"):
        stem = path.stem
        if stem.startswith("test_") or stem.endswith("_test"):
            return True

    if name.endswith((".test.ts", ".spec.ts", ".test.tsx", ".spec.tsx")):
        return True

    return False


def has_related_failing_test(project_dir: str, impl_file: str) -> bool:
    """Check if there's a failing test specifically for this module.

    Looks for test files matching the implementation file name in the
    pytest lastfailed cache. Only returns True if there's a failing test
    that appears to be for the module being edited.
    """
    cache_file = Path(project_dir) / ".pytest_cache" / "v" / "cache" / "lastfailed"

    if not cache_file.exists():
        return False

    impl_path = Path(impl_file)
    module_name = impl_path.stem

    try:
        with cache_file.open() as f:
            lastfailed = json.load(f)

        if not lastfailed:
            return False

        for test_path in lastfailed:
            test_file = test_path.split("::")[0]
            test_name = Path(test_file).stem

            if test_name == f"test_{module_name}" or test_name == f"{module_name}_test":
                return True

        return False
    except (json.JSONDecodeError, OSError):
        return False


def has_typescript_test_file(impl_path: str) -> bool:
    """Check if corresponding TypeScript test file exists."""
    path = Path(impl_path)
    directory = path.parent

    if path.name.endswith(".tsx"):
        base_name = path.name[:-4]
        extensions = [".test.tsx", ".spec.tsx", ".test.ts", ".spec.ts"]
    elif path.name.endswith(".ts"):
        base_name = path.name[:-3]
        extensions = [".test.ts", ".spec.ts"]
    else:
        return False

    for ext in extensions:
        test_file = directory / f"{base_name}{ext}"
        if test_file.exists():
            return True

    return False


def warn(message: str, suggestion: str) -> int:
    """Show warning and return exit code 2 (blocking)."""
    print("", file=sys.stderr)
    print(f"{YELLOW}TDD Reminder: {message}{NC}", file=sys.stderr)
    print(f"{YELLOW}    {suggestion}{NC}", file=sys.stderr)
    return 2


def run_tdd_enforcer() -> int:
    """Run TDD enforcement and return exit code."""
    try:
        hook_data = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        return 0

    tool_name = hook_data.get("tool_name", "")
    if tool_name not in ("Write", "Edit"):
        return 0

    tool_input = hook_data.get("tool_input", {})
    file_path = tool_input.get("file_path", "")
    if not file_path:
        return 0

    if should_skip(file_path):
        return 0

    if is_test_file(file_path):
        return 0

    if file_path.endswith(".py"):
        path = Path(file_path).parent
        found_failing = False

        for _ in range(10):
            if has_related_failing_test(str(path), file_path):
                found_failing = True
                break
            if path.parent == path:
                break
            path = path.parent

        if found_failing:
            return 0

        module_name = Path(file_path).stem
        return warn(
            f"No failing test for '{module_name}' module",
            f"Write a failing test in test_{module_name}.py first.",
        )

    if file_path.endswith((".ts", ".tsx")):
        if has_typescript_test_file(file_path):
            return 0

        base_name = Path(file_path).stem
        return warn(
            "No test file found for this module",
            f"Consider creating {base_name}.test.ts first.",
        )

    return 0


if __name__ == "__main__":
    sys.exit(run_tdd_enforcer())
