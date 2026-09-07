#!/usr/bin/env python3
"""SessionStart hook (Claude Code only): deliver one-time announcements.

Each announcement is injected into the session via `additionalContext` exactly
once. The hook touches the ack sentinel itself before injecting, so the message
shows once regardless of session outcome -- no AskUserQuestion round-trip needed.

Extensible: add entries to ANNOUNCEMENTS. Stdlib only (package boundary);
never raises.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

# Ordered list of one-time announcements. Add new entries here; each shows once
# (per machine) until acknowledged. Keep messages ASCII (no-emojis-in-source).
# Retire release-specific messages once their defaults or model-limit claims
# age out. New sessions should start with the user's task, not old release notes.
ANNOUNCEMENTS: list[dict[str, str]] = []


def _pilot_dir() -> Path:
    return Path.home() / ".pilot"


def _ack_path(announce_id: str, base: Path) -> Path:
    """Ack sentinel path: ``<base>/.announce-<id>-ack``."""
    return base / f".announce-{announce_id}-ack"


def pending(base: Path, announcements: list[dict[str, str]]) -> list[dict[str, str]]:
    """Return announcements whose ack sentinel does not yet exist."""
    result: list[dict[str, str]] = []
    for a in announcements:
        try:
            if not _ack_path(a["id"], base).exists():
                result.append(a)
        except OSError:
            result.append(a)
    return result


def render_context(pending_list: list[dict[str, str]]) -> str:
    """Build the SessionStart additionalContext for the pending announcements.

    Empty string when nothing is pending.
    Ack sentinels are touched by the hook before this context is injected.
    """
    if not pending_list:
        return ""
    blocks: list[str] = [
        "[Pilot one-time announcement] Display the following announcement(s) to "
        "the user as clearly formatted text output. "
        "Do NOT use AskUserQuestion. "
        "Just show the announcement text, then continue with the user's request."
    ]
    for a in pending_list:
        blocks.append(f"\n--- Announcement ---\n{a['message']}")
    return "\n".join(blocks)


def main() -> None:
    # Claude Code only -- Codex has no SessionStart announcement channel here.
    if not os.environ.get("CLAUDE_CODE_ENTRYPOINT"):
        return
    try:
        base = _pilot_dir()
        pending_list = pending(base, ANNOUNCEMENTS)
        ctx = render_context(pending_list)
        if not ctx:
            return
        # Touch ack sentinels now so each announcement shows exactly once.
        for a in pending_list:
            try:
                _ack_path(a["id"], base).touch()
            except OSError:
                pass
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "SessionStart",
                        "additionalContext": ctx,
                    }
                }
            )
        )
    except Exception:
        # SessionStart hook: never raise / never block the session.
        return


if __name__ == "__main__":
    main()
