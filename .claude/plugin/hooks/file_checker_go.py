"""Go file checker hook - runs gofmt, go vet, and golangci-lint on most recent Go file."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[0;33m"
NC = "\033[0m"


def find_git_root() -> Path | None:
    """Find git repository root."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return Path(result.stdout.strip())
    except Exception:
        pass
    return None


def get_edited_file_from_stdin() -> Path | None:
    """Get the edited file path from PostToolUse hook stdin."""
    try:
        import select

        if select.select([sys.stdin], [], [], 0)[0]:
            data = json.load(sys.stdin)
            tool_input = data.get("tool_input", {})
            file_path = tool_input.get("file_path")
            if file_path:
                return Path(file_path)
    except Exception:
        pass
    return None


def auto_format(file_path: Path) -> bool:
    """Auto-format file with gofmt."""
    gofmt_bin = shutil.which("gofmt")
    if not gofmt_bin:
        return False

    try:
        result = subprocess.run(
            [gofmt_bin, "-w", str(file_path)],
            capture_output=True,
            check=False,
        )
        return result.returncode == 0
    except Exception:
        return False


def run_go_vet(file_path: Path) -> tuple[bool, str]:
    """Run go vet on the file."""
    go_bin = shutil.which("go")
    if not go_bin:
        return False, ""

    try:
        result = subprocess.run(
            [go_bin, "vet", str(file_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        output = result.stdout + result.stderr
        has_issues = result.returncode != 0 or bool(output.strip())
        return has_issues, output
    except Exception:
        return False, ""


def run_golangci_lint(file_path: Path) -> tuple[bool, str, bool]:
    """Run golangci-lint on the file.

    Returns:
        Tuple of (has_issues, output, tool_available)
    """
    lint_bin = shutil.which("golangci-lint")
    if not lint_bin:
        return False, "", False

    try:
        result = subprocess.run(
            [lint_bin, "run", "--fast", str(file_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        output = result.stdout + result.stderr
        has_issues = result.returncode != 0
        return has_issues, output, True
    except Exception:
        return False, "", True


def display_vet_result(output: str) -> None:
    """Display go vet results."""
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    issue_count = len(lines)
    plural = "issue" if issue_count == 1 else "issues"

    print("", file=sys.stderr)
    print(f"🔍 go vet: {issue_count} {plural}", file=sys.stderr)
    print("───────────────────────────────────────", file=sys.stderr)

    for line in lines[:10]:
        print(f"  {line}", file=sys.stderr)

    if issue_count > 10:
        print(f"  ... and {issue_count - 10} more issues", file=sys.stderr)

    print("", file=sys.stderr)


def display_lint_result(output: str) -> None:
    """Display golangci-lint results."""
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    issue_count = len([line for line in lines if ": " in line])
    plural = "issue" if issue_count == 1 else "issues"

    print("", file=sys.stderr)
    print(f"🔧 golangci-lint: {issue_count} {plural}", file=sys.stderr)
    print("───────────────────────────────────────", file=sys.stderr)

    for line in lines[:10]:
        print(f"  {line}", file=sys.stderr)

    if len(lines) > 10:
        print(f"  ... and {len(lines) - 10} more lines", file=sys.stderr)

    print("", file=sys.stderr)


def main() -> int:
    """Main entry point."""
    git_root = find_git_root()
    if git_root:
        os.chdir(git_root)

    target_file = get_edited_file_from_stdin()
    if not target_file or not target_file.exists():
        return 0

    if target_file.suffix != ".go":
        return 0

    if target_file.name.endswith("_test.go"):
        return 0

    has_go = shutil.which("go") is not None
    has_gofmt = shutil.which("gofmt") is not None
    has_golangci_lint = shutil.which("golangci-lint") is not None

    if not has_go:
        return 0

    if has_gofmt:
        auto_format(target_file)

    results = {}
    has_issues = False
    missing_tools = []

    vet_issues, vet_output = run_go_vet(target_file)
    if vet_issues:
        has_issues = True
        results["vet"] = vet_output

    if has_golangci_lint:
        lint_issues, lint_output, _ = run_golangci_lint(target_file)
        if lint_issues:
            has_issues = True
            results["lint"] = lint_output
    else:
        missing_tools.append("golangci-lint")

    if has_issues:
        print("", file=sys.stderr)
        try:
            display_path = target_file.relative_to(Path.cwd())
        except ValueError:
            display_path = target_file
        print(
            f"{RED}🛑 Go Issues found in: {display_path}{NC}",
            file=sys.stderr,
        )

        if "vet" in results:
            display_vet_result(results["vet"])

        if "lint" in results:
            display_lint_result(results["lint"])

        if missing_tools:
            print(f"{YELLOW}⚠️  Missing tools: {', '.join(missing_tools)}{NC}", file=sys.stderr)
            print("   Install golangci-lint: https://golangci-lint.run/usage/install/", file=sys.stderr)
            print("", file=sys.stderr)

        print(f"{RED}Fix Go issues above before continuing{NC}", file=sys.stderr)
        return 2
    else:
        print("", file=sys.stderr)
        if missing_tools:
            print(f"{YELLOW}⚠️  Missing: {', '.join(missing_tools)} (install for full linting){NC}", file=sys.stderr)
        print(f"{GREEN}✅ Go: All checks passed{NC}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
