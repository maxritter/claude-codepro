"""TypeScript/JavaScript file checker — eslint."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from _lib.util import BLUE, NC, check_file_length

TS_EXTENSIONS = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".mts"}
DEBUG = os.environ.get("HOOK_DEBUG", "").lower() == "true"


def debug_log(message: str) -> None:
    """Print debug message if enabled."""
    if DEBUG:
        print(f"{BLUE}[DEBUG]{NC} {message}", file=sys.stderr)


def find_project_root(file_path: Path) -> Path | None:
    """Find nearest directory with package.json."""
    current = file_path.parent
    depth = 0
    while current != current.parent:
        if (current / "package.json").exists():
            return current
        current = current.parent
        depth += 1
        if depth > 20:
            break
    return None


_ESLINT_CONFIGS = (
    ".eslintrc",
    ".eslintrc.js",
    ".eslintrc.cjs",
    ".eslintrc.json",
    ".eslintrc.yml",
    ".eslintrc.yaml",
    "eslint.config.js",
    "eslint.config.mjs",
    "eslint.config.cjs",
    "eslint.config.ts",
    "eslint.config.mts",
    "eslint.config.cts",
)


def _has_eslint_config(project_root: Path | None) -> bool:
    """Check if the project has eslint configured."""
    if not project_root:
        return False
    if any((project_root / cfg).exists() for cfg in _ESLINT_CONFIGS):
        return True
    pkg_json = project_root / "package.json"
    if pkg_json.exists():
        try:
            data = json.loads(pkg_json.read_text())
            if "eslintConfig" in data:
                return True
        except (json.JSONDecodeError, OSError):
            pass
    return False


def find_tool(tool_name: str, project_root: Path | None) -> str | None:
    """Find tool binary, preferring local node_modules."""
    if project_root:
        local_bin = project_root / "node_modules" / ".bin" / tool_name
        if local_bin.exists():
            return str(local_bin)
    return shutil.which(tool_name)


def check_typescript(file_path: Path) -> tuple[int, str]:
    """Check TypeScript file with eslint. Returns (0, reason)."""
    if ".test." in file_path.name or ".spec." in file_path.name:
        return 0, ""

    length_warning = check_file_length(file_path)

    project_root = find_project_root(file_path)

    eslint_bin = find_tool("eslint", project_root)

    if not eslint_bin or not _has_eslint_config(project_root):
        return 0, length_warning

    results: dict[str, tuple] = {}
    has_issues = False

    if eslint_bin:
        has_issues, results = _run_eslint(eslint_bin, file_path, project_root, has_issues, results)

    if has_issues:
        parts = []
        if "eslint" in results:
            errs, warns, _ = results["eslint"]
            parts.append(f"{errs + warns} eslint")
        reason = f"TypeScript: {', '.join(parts)} in {file_path.name}"
        details = _format_typescript_issues(file_path, results)
        if details:
            reason = f"{reason}\n{details}"
        if length_warning:
            reason = f"{reason}\n{length_warning}"
        return 0, reason

    return 0, length_warning


def _run_eslint(
    eslint_bin: str,
    file_path: Path,
    project_root: Path | None,
    has_issues: bool,
    results: dict[str, tuple],
) -> tuple[bool, dict[str, tuple]]:
    """Run eslint and collect results."""
    try:
        result = subprocess.run(
            [eslint_bin, "--format", "json", str(file_path)],
            capture_output=True,
            text=True,
            check=False,
            cwd=project_root,
            timeout=10,
        )
        try:
            data = json.loads(result.stdout)
            total_errors = sum(f.get("errorCount", 0) for f in data)
            total_warnings = sum(f.get("warningCount", 0) for f in data)
            if total_errors > 0 or total_warnings > 0:
                has_issues = True
                results["eslint"] = (total_errors, total_warnings, data)
        except json.JSONDecodeError:
            pass
    except (OSError, subprocess.SubprocessError, TypeError, AttributeError):
        pass
    return has_issues, results


def _format_typescript_issues(file_path: Path, results: dict[str, tuple]) -> str:
    """Format TypeScript diagnostic issues as plain text."""
    lines: list[str] = []
    try:
        display_path = file_path.relative_to(Path.cwd())
    except ValueError:
        display_path = file_path
    lines.append(f"TypeScript Issues found in: {display_path}")

    if "eslint" in results:
        total_errors, total_warnings, data = results["eslint"]
        total = total_errors + total_warnings
        plural = "issue" if total == 1 else "issues"
        lines.append(f"ESLint: {total} {plural} ({total_errors} errors, {total_warnings} warnings)")
        for file_result in data:
            file_name = Path(file_result.get("filePath", "")).name
            for msg in file_result.get("messages", [])[:10]:
                line_num = msg.get("line", 0)
                rule_id = msg.get("ruleId", "unknown")
                message = msg.get("message", "")
                severity = "error" if msg.get("severity", 0) == 2 else "warn"
                lines.append(f"  {file_name}:{line_num} [{severity}] {rule_id}: {message}")
            if len(file_result.get("messages", [])) > 10:
                remaining = len(file_result["messages"]) - 10
                lines.append(f"  ... and {remaining} more issues")

    lines.append("Review these diagnostics with the current change; fix confirmed issues before final verification.")
    return "\n".join(lines)
