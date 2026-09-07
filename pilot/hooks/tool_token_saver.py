#!/usr/bin/env python3
"""Hook to rewrite Bash commands via rtk for token savings.

Delegates all rewrite logic to `rtk rewrite` (Rust binary).
To add or change rewrite rules, edit the Rust registry — not this file.
Requires: rtk >= 0.23.0
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
MIN_RTK_VERSION = (0, 23, 0)


def _parse_version(version_str: str) -> tuple[int, ...] | None:
    """Parse version string like '0.23.1' into tuple."""
    try:
        parts = version_str.strip().split(".")
        return tuple(int(p) for p in parts[:3])
    except (ValueError, IndexError):
        return None


def _get_rtk_version() -> tuple[int, ...] | None:
    """Get rtk version, or None if not available."""
    try:
        result = subprocess.run(
            ["rtk", "--version"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        if result.returncode != 0:
            return None
        for word in result.stdout.split():
            version = _parse_version(word)
            if version:
                return version
    except (OSError, subprocess.TimeoutExpired):
        pass
    return None


def _rewrite_command(cmd: str) -> str | None:
    """Call rtk rewrite and return rewritten command, or None if no rewrite."""
    try:
        result = subprocess.run(
            ["rtk", "rewrite", cmd],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        rewritten = result.stdout.strip()
        if not rewritten or rewritten == cmd:
            return None
        return rewritten
    except (OSError, subprocess.TimeoutExpired):
        return None


def _hook_platform(hook_data: dict) -> str | None:
    """Use the registration marker, with native Codex evidence for older registrations."""
    platform = os.environ.get("CLAUDE_PROJECT_PLATFORM") or hook_data.get("platform")
    if platform in ("claude", "codex"):
        return platform
    # turn_id is a Codex-specific hook field. Older sessions may instead expose
    # their native id through the environment; match it, don't trust inheritance.
    if isinstance(hook_data.get("turn_id"), str) and hook_data["turn_id"]:
        return "codex"
    session_id = hook_data.get("session_id")
    if isinstance(session_id, str) and session_id:
        if any(session_id == os.environ.get(name) for name in ("CODEX_THREAD_ID", "CODEX_SESSION_ID")):
            return "codex"
    return None


def run_tool_token_saver() -> int:
    """Rewrite Bash commands via rtk for token savings."""
    try:
        hook_data = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        return 0

    cmd = hook_data.get("tool_input", {}).get("command")
    if not cmd:
        return 0

    platform = _hook_platform(hook_data)
    if platform is None:
        # An ambiguous host must keep the original command and its permission
        # flow, not receive a guessed response that fails or auto-approves it.
        return 0

    if not shutil.which("rtk"):
        return 0

    version = _get_rtk_version()
    if version and version < MIN_RTK_VERSION:
        return 0

    rewritten = _rewrite_command(cmd)
    if not rewritten:
        return 0

    updated_input = dict(hook_data.get("tool_input", {}))
    updated_input["command"] = rewritten

    hook_output = {
        "hookEventName": "PreToolUse",
        "updatedInput": updated_input,
    }
    if platform == "codex":
        # Codex requires allow to apply updatedInput; this does not bypass its
        # native sandbox/approval policy. Claude applies updatedInput independently,
        # and allow there would skip the user's normal permission prompt.
        hook_output["permissionDecision"] = "allow"
    print(json.dumps({"hookSpecificOutput": hook_output}))
    return 0


if __name__ == "__main__":
    sys.exit(run_tool_token_saver())
