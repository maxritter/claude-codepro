#!/usr/bin/env python3
"""Context monitor - warns when context usage is high."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

THRESHOLD_WARN = 80
THRESHOLD_STOP = 90

CACHE_FILE = Path("/tmp/.claude_context_cache.json")
CACHE_TTL = 30

RED = "\033[0;31m"
YELLOW = "\033[0;33m"
NC = "\033[0m"


def get_current_session_id() -> str:
    """Get current session ID from history."""
    history = Path.home() / ".claude" / "history.jsonl"
    if not history.exists():
        return ""
    try:
        with history.open() as f:
            lines = f.readlines()
            if lines:
                return json.loads(lines[-1]).get("sessionId", "")
    except (json.JSONDecodeError, OSError):
        pass
    return ""


def find_session_file(session_id: str) -> Path | None:
    """Find session file for given session ID."""
    projects_dir = Path.home() / ".claude" / "projects"
    if not projects_dir.exists():
        return None
    for project_dir in projects_dir.iterdir():
        if project_dir.is_dir():
            session_file = project_dir / f"{session_id}.jsonl"
            if session_file.exists():
                return session_file
    return None


def get_actual_token_count(session_file: Path) -> int | None:
    """Get actual token count from the most recent API usage data."""
    last_usage = None

    try:
        with session_file.open() as f:
            for line in f:
                try:
                    msg = json.loads(line)
                    if msg.get("type") != "assistant":
                        continue

                    message = msg.get("message", {})
                    if not isinstance(message, dict):
                        continue

                    usage = message.get("usage")
                    if usage:
                        last_usage = usage
                except (json.JSONDecodeError, KeyError):
                    continue
    except OSError:
        return None

    if not last_usage:
        return None

    input_tokens = last_usage.get("input_tokens", 0)
    cache_creation = last_usage.get("cache_creation_input_tokens", 0)
    cache_read = last_usage.get("cache_read_input_tokens", 0)

    return input_tokens + cache_creation + cache_read


def get_cached_context(session_id: str) -> tuple[int, bool]:
    """Get cached context value if fresh enough and for current session."""
    if CACHE_FILE.exists():
        try:
            with CACHE_FILE.open() as f:
                cache = json.load(f)
                if cache.get("session_id") == session_id and time.time() - cache.get("timestamp", 0) < CACHE_TTL:
                    return cache.get("tokens", 0), True
        except (json.JSONDecodeError, OSError):
            pass
    return 0, False


def save_cache(tokens: int, session_id: str) -> None:
    """Save context calculation to cache with session ID."""
    try:
        with CACHE_FILE.open("w") as f:
            json.dump({"tokens": tokens, "timestamp": time.time(), "session_id": session_id}, f)
    except OSError:
        pass


def run_context_monitor() -> int:
    """Run context monitoring and return exit code."""
    session_id = get_current_session_id()
    if not session_id:
        return 0

    cached_tokens, is_cached = get_cached_context(session_id)
    if is_cached:
        total_tokens = cached_tokens
    else:
        session_file = find_session_file(session_id)
        if not session_file:
            return 0

        actual_tokens = get_actual_token_count(session_file)
        if actual_tokens is None:
            return 0

        total_tokens = actual_tokens
        save_cache(total_tokens, session_id)

    percentage = (total_tokens / 200000) * 100

    if percentage >= THRESHOLD_STOP:
        print("", file=sys.stderr)
        print(f"{RED}⚠️  CONTEXT {percentage:.0f}% - HANDOFF NOW (not optional){NC}", file=sys.stderr)
        print(f"{RED}STOP current work. Your NEXT actions must be:{NC}", file=sys.stderr)
        print(
            f"{RED}1. Check for active plan: grep -l '^Status: PENDING\\|^Status: COMPLETE' docs/plans/*.md 2>/dev/null | head -1{NC}",
            file=sys.stderr,
        )
        print(f"{RED}2. Write /tmp/claude-continuation.md (include Active Plan path if found){NC}", file=sys.stderr)
        print(
            f"{RED}3. Run: $CLAUDE_PROJECT_ROOT/.claude/bin/ccp send-clear <plan-path>  (or --general if no active plan){NC}",
            file=sys.stderr,
        )
        return 2

    if percentage >= THRESHOLD_WARN:
        print("", file=sys.stderr)
        print(
            f"{YELLOW}Context: {percentage:.0f}% - Finish current task with full quality or find a good place to wrap up, then hand off{NC}",
            file=sys.stderr,
        )
        print(
            f"{YELLOW}IMPORTANT: NEVER rush to finish a task when context is high. Always finish with full quality - next session can also do it!{NC}",
            file=sys.stderr,
        )
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(run_context_monitor())
