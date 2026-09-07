"""Python file checker — ruff."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from _lib.util import check_file_length


def _has_ruff_config(file_path: Path) -> bool:
    """Check if the project has ruff configured by walking up from the file."""
    current = file_path.parent
    for _ in range(20):
        if (current / "ruff.toml").exists() or (current / ".ruff.toml").exists():
            return True
        pyproject = current / "pyproject.toml"
        if pyproject.exists():
            try:
                content = pyproject.read_text()
                if "[tool.ruff]" in content:
                    return True
            except OSError:
                pass
        if current.parent == current:
            break
        current = current.parent
    return False


def check_python(file_path: Path) -> tuple[int, str]:
    """Check Python file with ruff. Returns (0, reason)."""
    if file_path.stem.startswith("test_") or file_path.stem.endswith(("_test", "_spec")):
        return 0, ""

    length_warning = check_file_length(file_path)

    if not _has_ruff_config(file_path):
        return 0, length_warning

    ruff_bin = shutil.which("ruff")
    if not ruff_bin:
        return 0, length_warning

    results: dict[str, tuple] = {}
    has_issues = False

    try:
        result = subprocess.run(
            [ruff_bin, "check", "--output-format=concise", str(file_path)],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        output = result.stdout + result.stderr
        error_pattern = re.compile(r":\d+:\d+: [A-Z]{1,3}\d+")
        error_lines = [line for line in output.splitlines() if error_pattern.search(line)]
        if error_lines:
            has_issues = True
            results["ruff"] = (len(error_lines), error_lines)
    except (OSError, subprocess.SubprocessError):
        pass

    if has_issues:
        parts = []
        for tool_name, (count, _) in results.items():
            parts.append(f"{count} {tool_name}")
        reason = f"Python: {', '.join(parts)} in {file_path.name}"
        details = _format_python_issues(file_path, results)
        if details:
            reason = f"{reason}\n{details}"
        if length_warning:
            reason = f"{reason}\n{length_warning}"
        return 0, reason

    return 0, length_warning


def _format_python_issues(file_path: Path, results: dict[str, tuple]) -> str:
    """Format Python diagnostic issues as plain text."""
    lines: list[str] = []
    try:
        display_path = file_path.relative_to(Path.cwd())
    except ValueError:
        display_path = file_path
    lines.append(f"Python Issues found in: {display_path}")

    if "ruff" in results:
        count, error_lines = results["ruff"]
        plural = "issue" if count == 1 else "issues"
        lines.append(f"Ruff: {count} {plural}")
        for line in error_lines:
            parts = line.split(None, 1)
            if parts:
                code = parts[0]
                msg = parts[1] if len(parts) > 1 else ""
                msg = msg.replace("[*] ", "")
                lines.append(f"  {code}: {msg}")

    lines.append("Review these diagnostics with the current change; fix confirmed issues before final verification.")
    return "\n".join(lines)
