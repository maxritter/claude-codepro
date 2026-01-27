#!/usr/bin/env python3
"""Stop guard for /spec workflow - prevents early finishing when plan is active.

Only allows stopping when:
1. Asking user for plan approval (AskUserQuestion tool)
2. Asking user for an important decision (AskUserQuestion tool)
3. No active plan exists (not in /spec mode)
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

RED = "\033[0;31m"
YELLOW = "\033[0;33m"
NC = "\033[0m"


def find_active_plan() -> tuple[Path | None, str | None]:
    """Find an active plan file (PENDING or COMPLETE status)."""
    plans_dir = Path("docs/plans")
    if not plans_dir.exists():
        return None, None

    plan_files = sorted(plans_dir.glob("*.md"), reverse=True)

    for plan_file in plan_files:
        try:
            content = plan_file.read_text()
            status_match = re.search(r"^Status:\s*(\w+)", content, re.MULTILINE)
            if status_match:
                status = status_match.group(1).upper()
                if status in ("PENDING", "COMPLETE"):
                    return plan_file, status
        except OSError:
            continue

    return None, None


def is_waiting_for_user_input(transcript_path: str) -> bool:
    """Check if Claude's last action was asking the user a question."""
    try:
        transcript = Path(transcript_path)
        if not transcript.exists():
            return False

        # Read transcript and find last assistant message
        last_assistant_msg = None
        with transcript.open() as f:
            for line in f:
                try:
                    msg = json.loads(line)
                    if msg.get("type") == "assistant":
                        last_assistant_msg = msg
                except json.JSONDecodeError:
                    continue

        if not last_assistant_msg:
            return False

        # Check if assistant used AskUserQuestion tool
        message = last_assistant_msg.get("message", {})
        if not isinstance(message, dict):
            return False

        content = message.get("content", [])
        if not isinstance(content, list):
            return False

        # Look for tool_use blocks with AskUserQuestion
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                if block.get("name") == "AskUserQuestion":
                    return True

        return False

    except OSError:
        return False


def main() -> int:
    """Check if stopping is allowed based on /spec workflow state."""
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0

    # Prevent infinite loops
    if input_data.get("stop_hook_active", False):
        return 0

    # Check for active plan
    plan_path, status = find_active_plan()
    if plan_path is None:
        return 0

    # Allow stopping if waiting for user input (AskUserQuestion)
    transcript_path = input_data.get("transcript_path", "")
    if transcript_path and is_waiting_for_user_input(transcript_path):
        return 0

    # Block stopping - active plan and not waiting for user
    print(f"{RED}⛔ /spec workflow active - cannot stop without user interaction{NC}", file=sys.stderr)
    print(f"{YELLOW}Active plan: {plan_path} (Status: {status}){NC}", file=sys.stderr)
    print("", file=sys.stderr)
    print("You may only stop when:", file=sys.stderr)
    print("  • Asking user for plan approval (use AskUserQuestion)", file=sys.stderr)
    print("  • Asking user for an important decision (use AskUserQuestion)", file=sys.stderr)
    print("", file=sys.stderr)

    if status == "PENDING":
        print("Status is PENDING. Either:", file=sys.stderr)
        print("  1. Ask user for plan approval with AskUserQuestion", file=sys.stderr)
        print("  2. Continue implementing tasks", file=sys.stderr)
        print("  3. If blocked, ask user for decision with AskUserQuestion", file=sys.stderr)
    elif status == "COMPLETE":
        print("Status is COMPLETE. You must:", file=sys.stderr)
        print("  1. Run PHASE 3: VERIFICATION", file=sys.stderr)
        print("  2. Update status to VERIFIED when done", file=sys.stderr)
        print("  3. If issues found, fix them or ask user with AskUserQuestion", file=sys.stderr)

    print("", file=sys.stderr)
    print(f"Continue the workflow or use AskUserQuestion if user input is needed.", file=sys.stderr)

    return 2


if __name__ == "__main__":
    sys.exit(main())
