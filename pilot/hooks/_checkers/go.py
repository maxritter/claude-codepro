"""Go file checker — go vet, golangci-lint."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from _lib.util import check_file_length

_GOLANGCI_CONFIGS = (
    ".golangci.yml",
    ".golangci.yaml",
    ".golangci.toml",
    ".golangci.json",
)


def _has_go_project(file_path: Path) -> bool:
    """Check if the file is inside a Go module (has go.mod)."""
    current = file_path.parent
    for _ in range(20):
        if (current / "go.mod").exists():
            return True
        if current.parent == current:
            break
        current = current.parent
    return False


def _has_golangci_config(file_path: Path) -> bool:
    """Check if the project has golangci-lint configured."""
    current = file_path.parent
    for _ in range(20):
        if any((current / cfg).exists() for cfg in _GOLANGCI_CONFIGS):
            return True
        if current.parent == current:
            break
        current = current.parent
    return False


def check_go(file_path: Path) -> tuple[int, str]:
    """Check Go file with go vet and golangci-lint. Returns (0, reason)."""
    if file_path.name.endswith("_test.go"):
        return 0, ""

    length_warning = check_file_length(file_path)

    if not _has_go_project(file_path):
        return 0, length_warning

    go_bin = shutil.which("go")
    golangci_lint_bin = shutil.which("golangci-lint")

    if not go_bin:
        return 0, length_warning

    results: dict[str, tuple] = {}
    has_issues = False

    try:
        # A Go file is compiled with its package: vetting only the edited file
        # invents undefined-symbol errors for declarations in sibling files.
        result = subprocess.run(
            [go_bin, "vet", "."], capture_output=True, text=True, check=False, cwd=file_path.parent, timeout=10
        )
        output = result.stdout + result.stderr
        if result.returncode != 0 or output.strip():
            lines = [line.strip() for line in output.splitlines() if line.strip() and not line.strip().startswith("#")]
            if lines:
                has_issues = True
                results["vet"] = (len(lines), lines)
    except (OSError, subprocess.SubprocessError):
        pass

    if golangci_lint_bin and _has_golangci_config(file_path):
        try:
            result = subprocess.run(
                [golangci_lint_bin, "run", "."],
                capture_output=True,
                text=True,
                check=False,
                cwd=file_path.parent,
                timeout=10,
            )
            output = result.stdout + result.stderr
            if result.returncode != 0:
                lines = [line.strip() for line in output.splitlines() if line.strip()]
                issue_count = len([line for line in lines if ": " in line])
                if issue_count > 0:
                    has_issues = True
                    results["lint"] = (issue_count, lines)
        except (OSError, subprocess.SubprocessError):
            pass

    if has_issues:
        parts = []
        for tool_name, (count, _) in results.items():
            parts.append(f"{count} {tool_name}")
        reason = f"Go: {', '.join(parts)} in {file_path.name}"
        details = _format_go_issues(file_path, results)
        if details:
            reason = f"{reason}\n{details}"
        if length_warning:
            reason = f"{reason}\n{length_warning}"
        return 0, reason

    return 0, length_warning


def _format_go_issues(file_path: Path, results: dict[str, tuple]) -> str:
    """Format Go diagnostic issues as plain text."""
    out: list[str] = []
    try:
        display_path = file_path.relative_to(Path.cwd())
    except ValueError:
        display_path = file_path
    out.append(f"Go Issues found in: {display_path}")

    if "vet" in results:
        count, lines = results["vet"]
        plural = "issue" if count == 1 else "issues"
        out.append(f"go vet: {count} {plural}")
        for line in lines[:10]:
            out.append(f"  {line}")
        if count > 10:
            out.append(f"  ... and {count - 10} more issues")

    if "lint" in results:
        count, lines = results["lint"]
        plural = "issue" if count == 1 else "issues"
        out.append(f"golangci-lint: {count} {plural}")
        for line in lines[:10]:
            out.append(f"  {line}")
        if len(lines) > 10:
            out.append(f"  ... and {len(lines) - 10} more lines")

    out.append("Review these diagnostics with the current change; fix confirmed issues before final verification.")
    return "\n".join(out)
