#!/usr/bin/env python3
"""Helper for context monitoring and wrapper communication."""

from __future__ import annotations

import argparse
import json
import os
import stat
import sys
from pathlib import Path

MAX_CONTEXT_TOKENS = 200_000
DEFAULT_THRESHOLD = 90
PRE_CLEAR_DELAY_SECONDS = 10.0


def get_current_session_id() -> str:
    """Get current session ID from Claude history."""
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


def get_context_percentage() -> float:
    """Calculate current context usage as a percentage."""
    session_id = get_current_session_id()
    if not session_id:
        return 0.0

    session_file = find_session_file(session_id)
    if not session_file:
        return 0.0

    actual_tokens = get_actual_token_count(session_file)
    if actual_tokens is None:
        return 0.0

    return (actual_tokens / MAX_CONTEXT_TOKENS) * 100


def check_context(threshold: int = DEFAULT_THRESHOLD) -> str:
    """Check context usage and return status."""
    percentage = get_context_percentage()
    if percentage >= threshold:
        return "CLEAR_NEEDED"
    return "OK"


def send_clear(plan_path: str | None = None, general: bool = False) -> bool:
    """Send clear command to wrapper via pipe.

    For continuation modes (general or plan_path), waits before sending
    to give Claude Mem time to capture the session summary.
    """
    import time

    pipe_path = os.environ.get("WRAPPER_PIPE")
    if not pipe_path:
        return False

    pipe = Path(pipe_path)
    if not pipe.exists():
        return False

    try:
        if not stat.S_ISFIFO(pipe.stat().st_mode):
            return False
    except OSError:
        return False

    if general:
        cmd = "clear-continue-general\n"
    elif plan_path:
        cmd = f"clear-continue {plan_path}\n"
    else:
        cmd = "clear\n"

    if general or plan_path:
        print(f"Waiting {PRE_CLEAR_DELAY_SECONDS}s for Claude Mem to capture session summary...")
        time.sleep(PRE_CLEAR_DELAY_SECONDS)

    try:
        with open(pipe, "w") as f:
            f.write(cmd)
        return True
    except OSError:
        return False


def cli_check_context(json_output: bool = False) -> str:
    """CLI handler for check-context command."""
    percentage = get_context_percentage()
    status = "CLEAR_NEEDED" if percentage >= DEFAULT_THRESHOLD else "OK"

    if json_output:
        return json.dumps({"status": status, "percentage": percentage})
    return status


def main() -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="Helper for context monitoring and wrapper communication")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    check_parser = subparsers.add_parser("check-context", help="Check current context usage")
    check_parser.add_argument("--json", action="store_true", help="Output as JSON")
    check_parser.add_argument(
        "--threshold",
        type=int,
        default=DEFAULT_THRESHOLD,
        help=f"Threshold percentage (default: {DEFAULT_THRESHOLD})",
    )

    clear_parser = subparsers.add_parser("send-clear", help="Send clear command to wrapper")
    clear_parser.add_argument("plan_path", nargs="?", help="Plan path for clear-continue")
    clear_parser.add_argument("--general", action="store_true", help="General continuation (no plan file)")

    args = parser.parse_args()

    if args.command == "check-context":
        result = cli_check_context(json_output=args.json)
        print(result)
        return 0 if "OK" in result else 1

    elif args.command == "send-clear":
        success = send_clear(plan_path=args.plan_path, general=args.general)
        if success:
            print("Clear command sent")
            return 0
        else:
            print("Failed to send clear command (wrapper not running?)", file=sys.stderr)
            return 1

    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
