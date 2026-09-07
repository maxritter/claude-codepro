#!/usr/bin/env python3
"""Generate Claude and Codex hook manifests from the lifecycle matrix."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MATRIX_PATH = ROOT / "pilot" / "hooks" / "hook-lifecycle.json"
DOCS_PATH = ROOT / "docs" / "docusaurus" / "docs" / "features" / "hooks.md"
OUTPUTS = {
    "claude": ROOT / "pilot" / "hooks" / "hooks.json",
    "codex": ROOT / "pilot" / "hooks" / "codex_hooks.json",
}
REQUIRED_ENTRY_FIELDS = {
    "id",
    "platform",
    "event",
    "matcher",
    "handlers",
    "async",
    "timeout",
    "contract_test",
}
PLATFORMS = frozenset(OUTPUTS)
EVENTS = frozenset(
    {
        "SessionStart",
        "UserPromptSubmit",
        "UserPromptExpansion",
        "PermissionRequest",
        "PreToolUse",
        "PostToolUse",
        "PostToolUseFailure",
        "Stop",
        "SessionEnd",
        "PreCompact",
    }
)
ID_PATTERN = re.compile(r"^[a-z][a-z0-9-]+$")
LOCAL_TARGET_PATTERN = re.compile(r'\$HOME/\.pilot/(?P<area>hooks|scripts)/(?P<target>[^" ]+)')
PUBLIC_DOCUMENTED_EVENTS = EVENTS - {"UserPromptExpansion"}


def load_matrix(path: Path = MATRIX_PATH) -> dict[str, Any]:
    """Load the lifecycle matrix."""
    return json.loads(path.read_text())


def _entry_errors(entry: object, index: int) -> list[str]:
    """Validate one lifecycle entry."""
    label = f"entries[{index}]"
    if not isinstance(entry, dict):
        return [f"{label} must be an object"]
    errors: list[str] = []
    missing = REQUIRED_ENTRY_FIELDS - set(entry)
    extra = set(entry) - REQUIRED_ENTRY_FIELDS
    if missing:
        errors.append(f"{label} is missing fields: {', '.join(sorted(missing))}")
    if extra:
        errors.append(f"{label} has unknown fields: {', '.join(sorted(extra))}")

    entry_id = entry.get("id")
    if not isinstance(entry_id, str) or not ID_PATTERN.fullmatch(entry_id):
        errors.append(f"{label}.id must be a lowercase kebab-case identifier")
    if entry.get("platform") not in PLATFORMS:
        errors.append(f"{label}.platform must be one of: {', '.join(sorted(PLATFORMS))}")
    if entry.get("event") not in EVENTS:
        errors.append(f"{label}.event is not a supported lifecycle event")
    if entry.get("matcher") is not None and not isinstance(entry.get("matcher"), str):
        errors.append(f"{label}.matcher must be a string or null")

    handlers = entry.get("handlers")
    async_values = entry.get("async")
    timeouts = entry.get("timeout")
    if (
        not isinstance(handlers, list)
        or not handlers
        or not all(isinstance(value, str) and value for value in handlers)
    ):
        errors.append(f"{label}.handlers must be a non-empty list of commands")
        handlers = []
    if not isinstance(async_values, list) or not all(isinstance(value, bool) for value in async_values):
        errors.append(f"{label}.async must be a list of booleans")
        async_values = []
    if not isinstance(timeouts, list) or not all(
        value is None or (isinstance(value, int) and not isinstance(value, bool) and value > 0) for value in timeouts
    ):
        errors.append(f"{label}.timeout must be a list of positive integers or null")
        timeouts = []
    if len(handlers) != len(async_values) or len(handlers) != len(timeouts):
        errors.append(f"{label}.handlers, .async, and .timeout must have equal lengths")

    contract_test = entry.get("contract_test")
    if not isinstance(contract_test, str) or "::" not in contract_test:
        errors.append(f"{label}.contract_test must be an explicit pytest node identifier")
    else:
        test_path, test_name = contract_test.split("::", 1)
        if not test_name or not (ROOT / test_path).is_file():
            errors.append(f"{label}.contract_test does not reference an existing test file and node")
    return errors


def validate_matrix(matrix: object) -> list[str]:
    """Return lifecycle matrix schema and consistency errors."""
    if not isinstance(matrix, dict):
        return ["matrix must be an object"]
    errors: list[str] = []
    if matrix.get("version") != 1:
        errors.append("matrix.version must be 1")
    entries = matrix.get("entries")
    if not isinstance(entries, list) or not entries:
        return [*errors, "matrix.entries must be a non-empty list"]
    for index, entry in enumerate(entries):
        errors.extend(_entry_errors(entry, index))
    ids = [entry.get("id") for entry in entries if isinstance(entry, dict) and isinstance(entry.get("id"), str)]
    duplicates = sorted({entry_id for entry_id in ids if ids.count(entry_id) > 1})
    if duplicates:
        errors.append(f"entry ids must be unique; duplicates: {', '.join(duplicates)}")
    return errors


def referenced_local_targets(matrix: dict[str, Any]) -> list[Path]:
    """Resolve installed command paths back to repository source targets."""
    targets: list[Path] = []
    for entry in matrix["entries"]:
        for command in entry["handlers"]:
            for match in LOCAL_TARGET_PATTERN.finditer(command):
                targets.append(ROOT / "pilot" / match.group("area") / match.group("target"))
    return targets


def render_manifest(matrix: dict[str, Any], platform: str) -> str:
    """Render one platform manifest while preserving matrix order and grouping."""
    hooks: dict[str, list[dict[str, Any]]] = {}
    for entry in matrix["entries"]:
        if entry["platform"] != platform:
            continue
        group: dict[str, Any] = {}
        if entry["matcher"] is not None:
            group["matcher"] = entry["matcher"]
        handlers = []
        for command, is_async, timeout in zip(entry["handlers"], entry["async"], entry["timeout"], strict=True):
            handler: dict[str, Any] = {"type": "command", "command": command}
            if is_async:
                handler["async"] = True
            if timeout is not None:
                handler["timeout"] = timeout
            handlers.append(handler)
        group["hooks"] = handlers
        hooks.setdefault(entry["event"], []).append(group)

    payload: dict[str, Any] = {"hooks": hooks}
    if platform == "claude":
        payload = {
            "description": "Pilot Shell hooks - memory system and quality checks",
            "hooks": hooks,
        }
    return json.dumps(payload, indent=2) + "\n"


def documentation_errors(matrix: dict[str, Any], path: Path = DOCS_PATH) -> list[str]:
    """Ensure the narrative hook docs declare and cover the canonical matrix."""
    try:
        content = path.read_text()
    except OSError as exc:
        return [f"cannot read {path}: {exc}"]
    errors = []
    for event in sorted({entry["event"] for entry in matrix["entries"]} & PUBLIC_DOCUMENTED_EVENTS):
        if f"## {event}" not in content:
            errors.append(f"{path} is missing lifecycle section `## {event}`")
    return errors


def _check(matrix: dict[str, Any]) -> int:
    drift = [
        str(path.relative_to(ROOT))
        for platform, path in OUTPUTS.items()
        if path.read_text() != render_manifest(matrix, platform)
    ]
    missing_targets = [str(path.relative_to(ROOT)) for path in referenced_local_targets(matrix) if not path.is_file()]
    doc_errors = documentation_errors(matrix)
    if drift or missing_targets or doc_errors:
        for path in drift:
            print(f"drift: {path}", file=sys.stderr)
        for path in missing_targets:
            print(f"missing command target: {path}", file=sys.stderr)
        for error in doc_errors:
            print(error, file=sys.stderr)
        return 1
    print("Hook manifest drift check passed: zero drift.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Report drift without writing files")
    args = parser.parse_args(argv)

    try:
        matrix = load_matrix()
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Cannot load {MATRIX_PATH}: {exc}", file=sys.stderr)
        return 2
    errors = validate_matrix(matrix)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 2
    if args.check:
        return _check(matrix)
    for platform, path in OUTPUTS.items():
        path.write_text(render_manifest(matrix, platform))
    print("Generated Claude and Codex hook manifests.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
