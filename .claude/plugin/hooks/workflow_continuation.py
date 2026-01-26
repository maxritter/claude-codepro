#!/usr/bin/env python3
"""PostToolUse hook for Skill tool - ensures /spec workflow continues.

When /implement or /verify finishes, this hook checks if the plan needs
continuation and outputs a loud reminder to Claude to invoke the next step.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def find_active_plan() -> tuple[Path, str] | None:
    """Find a plan file that needs workflow continuation."""
    plans_dir = Path("docs/plans")
    if not plans_dir.exists():
        return None

    for plan_file in sorted(plans_dir.glob("*.md"), reverse=True):
        try:
            content = plan_file.read_text()
        except Exception:
            continue

        if "Status: VERIFIED" in content:
            continue

        if "Status: COMPLETE" in content:
            return plan_file, "COMPLETE"

        if "Status: PENDING" in content and "Approved: Yes" in content:
            return plan_file, "PENDING"

    return None


def main() -> None:
    """Check if workflow continuation is needed after Skill tool use."""
    try:
        data = json.loads(sys.stdin.read())
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = data.get("tool_name", "")

    if tool_name != "Skill":
        sys.exit(0)

    result = find_active_plan()
    if not result:
        sys.exit(0)

    plan_file, status = result

    border = "=" * 65
    print(f"\n{border}", file=sys.stderr)
    print("🚨 WORKFLOW CONTINUATION REQUIRED - DO NOT END RESPONSE 🚨", file=sys.stderr)
    print(border, file=sys.stderr)
    print(f"Plan: {plan_file}", file=sys.stderr)

    if status == "COMPLETE":
        print("Status: COMPLETE → MUST invoke /verify NOW", file=sys.stderr)
        print("", file=sys.stderr)
        print("IN THIS SAME RESPONSE, invoke:", file=sys.stderr)
        print(f'   Skill(skill="verify", args="{plan_file}")', file=sys.stderr)

    elif status == "PENDING":
        print("Status: PENDING (approved) → MUST invoke /implement NOW", file=sys.stderr)
        print("", file=sys.stderr)
        print("IN THIS SAME RESPONSE, invoke:", file=sys.stderr)
        print(f'   Skill(skill="implement", args="{plan_file}")', file=sys.stderr)

    print(border, file=sys.stderr)
    print("⛔ STOPPING WITHOUT CONTINUING IS A WORKFLOW VIOLATION", file=sys.stderr)
    print(border, file=sys.stderr)

    sys.exit(0)


if __name__ == "__main__":
    main()
