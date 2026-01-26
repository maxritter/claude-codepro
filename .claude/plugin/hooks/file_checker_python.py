"""Python file checker hook - runs ruff and basedpyright on most recent Python file."""

from __future__ import annotations

import io
import json
import os
import re
import shutil
import subprocess
import sys
import tokenize
from pathlib import Path

RED = "\033[0;31m"
GREEN = "\033[0;32m"
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


def strip_inline_comments(file_path: Path) -> bool:
    """Remove inline comments from Python file.

    Removes:
    - End-of-line comments: `code  # comment` → `code`
    - Full-line comments: `# comment` → (line removed)

    Preserves:
    - Shebang lines: #!/usr/bin/env python
    - Type comments: # type: ignore, # type:
    - Noqa comments: # noqa
    - Pragma comments: # pragma:
    - Docstrings (triple-quoted strings)

    Returns True if file was modified.
    """
    try:
        content = file_path.read_text()
        lines = content.splitlines(keepends=True)
    except Exception:
        return False

    preserve_patterns = [
        r"#!",
        r"#\s*type:",
        r"#\s*noqa",
        r"#\s*pragma:",
        r"#\s*pylint:",
        r"#\s*pyright:",
        r"#\s*ruff:",
        r"#\s*fmt:",
        r"#\s*TODO",
        r"#\s*FIXME",
        r"#\s*XXX",
        r"#\s*NOTE",
    ]
    preserve_re = re.compile("|".join(preserve_patterns), re.IGNORECASE)

    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(content).readline))
    except tokenize.TokenError:
        return False

    comments_to_remove: list[tuple[int, int, int]] = []
    for tok in tokens:
        if tok.type == tokenize.COMMENT:
            comment_text = tok.string
            if preserve_re.search(comment_text):
                continue
            start_row, start_col = tok.start
            _, end_col = tok.end
            comments_to_remove.append((start_row, start_col, end_col))

    if not comments_to_remove:
        return False

    new_lines = list(lines)
    lines_to_delete: set[int] = set()

    for line_num, start_col, _ in reversed(comments_to_remove):
        idx = line_num - 1
        if idx >= len(new_lines):
            continue

        line = new_lines[idx]
        before_comment = line[:start_col].rstrip()

        if before_comment:
            new_lines[idx] = before_comment + "\n"
        else:
            lines_to_delete.add(idx)

    for idx in sorted(lines_to_delete, reverse=True):
        del new_lines[idx]

    new_content = "".join(new_lines)
    if new_content != content:
        file_path.write_text(new_content)
        return True

    return False


def auto_format(file_path: Path) -> None:
    """Auto-format file with ruff before checks."""
    strip_inline_comments(file_path)

    ruff_bin = shutil.which("ruff")
    if not ruff_bin:
        return

    try:
        subprocess.run(
            [ruff_bin, "check", "--select", "I,RUF022", "--fix", str(file_path)],
            capture_output=True,
            check=False,
        )

        subprocess.run([ruff_bin, "format", str(file_path)], capture_output=True, check=False)
    except Exception:
        pass


def run_ruff_check(file_path: Path) -> tuple[bool, str]:
    """Run ruff check."""
    ruff_bin = shutil.which("ruff")
    if not ruff_bin:
        return False, ""

    try:
        result = subprocess.run(
            [ruff_bin, "check", "--output-format=concise", str(file_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        output = result.stdout + result.stderr
        lines = output.splitlines()
        error_pattern = re.compile(r":\d+:\d+: [A-Z]{1,3}\d+")
        error_lines = [line for line in lines if error_pattern.search(line)]
        has_issues = len(error_lines) > 0
        return has_issues, output
    except Exception:
        return False, ""


def run_basedpyright_check(file_path: Path) -> tuple[bool, str]:
    """Run basedpyright check."""
    basedpyright_bin = shutil.which("basedpyright")
    if not basedpyright_bin:
        return False, ""

    try:
        result = subprocess.run(
            [basedpyright_bin, "--outputjson", str(file_path.resolve())],
            capture_output=True,
            text=True,
            check=False,
        )
        output = result.stdout + result.stderr
        try:
            data = json.loads(output)
            error_count = data.get("summary", {}).get("errorCount", 0)
            has_issues = error_count > 0
            return has_issues, output
        except json.JSONDecodeError:
            has_issues = bool('error"' in output or " error" in output)
            return has_issues, output
    except Exception:
        return False, ""


def display_ruff_result(output: str) -> None:
    """Display ruff results."""
    lines = output.splitlines()
    error_pattern = re.compile(r":\d+:\d+: [A-Z]{1,3}\d+")
    error_lines = [line for line in lines if error_pattern.search(line)]
    error_count = len(error_lines)
    plural = "issue" if error_count == 1 else "issues"

    print("", file=sys.stderr)
    print(f"🔧 Ruff: {error_count} {plural}", file=sys.stderr)
    print("───────────────────────────────────────", file=sys.stderr)

    for line in error_lines:
        parts = line.split(None, 1)
        if parts:
            code = parts[0]
            msg = parts[1] if len(parts) > 1 else ""

            msg = msg.replace("[*] ", "")
            print(f"  {code}: {msg}", file=sys.stderr)

    print("", file=sys.stderr)


def display_basedpyright_result(output: str) -> None:
    """Display basedpyright results."""
    try:
        data = json.loads(output)
        error_count = data.get("summary", {}).get("errorCount", 0)
        plural = "issue" if error_count == 1 else "issues"

        print("", file=sys.stderr)
        print(f"🐍 BasedPyright: {error_count} {plural}", file=sys.stderr)
        print("───────────────────────────────────────", file=sys.stderr)

        for diag in data.get("generalDiagnostics", []):
            file_name = Path(diag.get("file", "")).name
            line = diag.get("range", {}).get("start", {}).get("line", 0)
            msg = diag.get("message", "").split("\n")[0]
            print(f"  {file_name}:{line} - {msg}", file=sys.stderr)

    except json.JSONDecodeError:
        print("", file=sys.stderr)
        print("🐍 BasedPyright: issues found", file=sys.stderr)
        print("───────────────────────────────────────", file=sys.stderr)
        print(output, file=sys.stderr)

    print("", file=sys.stderr)


def get_edited_file_from_stdin() -> Path | None:
    """Get the edited file path from PostToolUse hook stdin or command line."""
    if len(sys.argv) > 1:
        return Path(sys.argv[1])

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


def main() -> int:
    """Main entry point."""

    git_root = find_git_root()
    if git_root:
        os.chdir(git_root)

    target_file = get_edited_file_from_stdin()
    if not target_file or not target_file.exists():
        return 0

    if target_file.suffix != ".py":
        return 0

    if "test" in target_file.name or "spec" in target_file.name:
        return 0

    has_ruff = shutil.which("ruff") is not None
    has_basedpyright = shutil.which("basedpyright") is not None

    if not (has_ruff or has_basedpyright):
        return 0

    auto_format(target_file)

    results = {}
    has_issues = False

    if has_ruff:
        ruff_issues, ruff_output = run_ruff_check(target_file)
        if ruff_issues:
            has_issues = True
            results["ruff"] = ruff_output

    if has_basedpyright:
        pyright_issues, pyright_output = run_basedpyright_check(target_file)
        if pyright_issues:
            has_issues = True
            results["basedpyright"] = pyright_output

    if has_issues:
        print("", file=sys.stderr)
        try:
            display_path = target_file.relative_to(Path.cwd())
        except ValueError:
            display_path = target_file
        print(
            f"{RED}🛑 Python Issues found in: {display_path}{NC}",
            file=sys.stderr,
        )

        if "ruff" in results:
            display_ruff_result(results["ruff"])

        if "basedpyright" in results:
            display_basedpyright_result(results["basedpyright"])

        print(f"{RED}Fix Python issues above before continuing{NC}", file=sys.stderr)
        return 2
    else:
        print("", file=sys.stderr)
        print(f"{GREEN}✅ Python: All checks passed{NC}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
