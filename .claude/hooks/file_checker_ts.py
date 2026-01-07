"""TypeScript file checker hook - runs eslint and tsc on most recent TypeScript file."""

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
BLUE = "\033[0;34m"
NC = "\033[0m"

TS_EXTENSIONS = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".mts"}

# Enable debug mode with: HOOK_DEBUG=true
DEBUG = os.environ.get("HOOK_DEBUG", "").lower() == "true"


def debug_log(message: str) -> None:
    """Print debug message if debug mode is enabled."""
    if DEBUG:
        print(f"{BLUE}[DEBUG]{NC} {message}", file=sys.stderr)


def find_git_root() -> Path | None:
    """Find git repository root."""
    debug_log("Looking for git root...")
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            git_root = Path(result.stdout.strip())
            debug_log(f"Found git root: {git_root}")
            return git_root
        else:
            debug_log("Not in a git repository")
    except Exception as e:
        debug_log(f"Error finding git root: {e}")
    return None


def find_most_recent_file(root: Path) -> Path | None:
    """Find most recently modified file (excluding cache/build dirs)."""
    debug_log(f"Searching for most recent file in: {root}")
    
    exclude_patterns = [
        "node_modules",
        ".next",
        "dist",
        "build",
        ".git",
        ".cache",
        "coverage",
        ".turbo",
        ".vercel",
        "__pycache__",
        ".venv",
    ]
    debug_log(f"Excluding patterns: {', '.join(exclude_patterns)}")

    most_recent_file = None
    most_recent_time = 0.0
    files_checked = 0

    try:
        for file_path in root.rglob("*"):
            if not file_path.is_file():
                continue

            if any(pattern in file_path.parts for pattern in exclude_patterns):
                continue

            files_checked += 1
            try:
                mtime = file_path.stat().st_mtime
                if mtime > most_recent_time:
                    most_recent_time = mtime
                    most_recent_file = file_path
                    debug_log(f"New most recent: {file_path.relative_to(root)} (mtime: {mtime})")
            except (OSError, PermissionError) as e:
                debug_log(f"Error accessing {file_path}: {e}")
                continue

    except Exception as e:
        debug_log(f"Error during file search: {e}")

    debug_log(f"Checked {files_checked} files")
    if most_recent_file:
        debug_log(f"Most recent file: {most_recent_file}")
    else:
        debug_log("No files found")
    
    return most_recent_file


def find_project_root(file_path: Path) -> Path | None:
    """Find the nearest directory with package.json."""
    debug_log(f"Looking for package.json starting from: {file_path.parent}")
    
    current = file_path.parent
    depth = 0
    while current != current.parent:
        debug_log(f"Checking: {current} (depth: {depth})")
        if (current / "package.json").exists():
            debug_log(f"Found package.json at: {current}")
            return current
        current = current.parent
        depth += 1
        if depth > 20:  # Safety limit
            debug_log("Reached max depth searching for package.json")
            break
    
    debug_log("No package.json found")
    return None


def find_tool(tool_name: str, project_root: Path | None) -> str | None:
    """Find tool binary, preferring local node_modules."""
    debug_log(f"Looking for tool: {tool_name}")
    
    if project_root:
        local_bin = project_root / "node_modules" / ".bin" / tool_name
        debug_log(f"Checking local: {local_bin}")
        if local_bin.exists():
            debug_log(f"Found local {tool_name}: {local_bin}")
            return str(local_bin)
        else:
            debug_log(f"Local {tool_name} not found")

    global_bin = shutil.which(tool_name)
    if global_bin:
        debug_log(f"Found global {tool_name}: {global_bin}")
    else:
        debug_log(f"Global {tool_name} not found")
    
    return global_bin


def auto_format(file_path: Path, project_root: Path | None) -> None:
    """Auto-format file with prettier before checks."""
    debug_log("Attempting auto-format with prettier...")
    
    prettier_bin = find_tool("prettier", project_root)
    if not prettier_bin:
        debug_log("Prettier not available, skipping auto-format")
        return

    try:
        debug_log(f"Running: {prettier_bin} --write {file_path}")
        result = subprocess.run(
            [prettier_bin, "--write", str(file_path)],
            capture_output=True,
            check=False,
            cwd=project_root,
        )
        if result.returncode == 0:
            debug_log("Auto-format successful")
        else:
            debug_log(f"Auto-format failed with code {result.returncode}")
            if result.stderr:
                debug_log(f"Prettier stderr: {result.stderr.decode()}")
    except Exception as e:
        debug_log(f"Error during auto-format: {e}")


def run_eslint_check(file_path: Path, project_root: Path | None) -> tuple[bool, str]:
    """Run eslint check."""
    debug_log("Running ESLint check...")
    
    eslint_bin = find_tool("eslint", project_root)
    if not eslint_bin:
        debug_log("ESLint not available")
        return False, ""

    try:
        cmd = [eslint_bin, "--format", "json", str(file_path)]
        debug_log(f"Running: {' '.join(cmd)}")
        debug_log(f"Working directory: {project_root}")
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            cwd=project_root,
        )
        
        debug_log(f"ESLint exit code: {result.returncode}")
        
        output = result.stdout
        try:
            data = json.loads(output)
            total_errors = sum(f.get("errorCount", 0) for f in data)
            total_warnings = sum(f.get("warningCount", 0) for f in data)
            debug_log(f"ESLint found: {total_errors} errors, {total_warnings} warnings")
            has_issues = total_errors > 0 or total_warnings > 0
            return has_issues, output
        except json.JSONDecodeError as e:
            debug_log(f"Failed to parse ESLint JSON output: {e}")
            has_issues = result.returncode != 0
            return has_issues, result.stdout + result.stderr
    except Exception as e:
        debug_log(f"Error running ESLint: {e}")
        return False, ""


def run_tsc_check(file_path: Path, project_root: Path | None) -> tuple[bool, str]:
    """Run TypeScript compiler check."""
    debug_log("Running TypeScript compiler check...")
    
    if file_path.suffix not in {".ts", ".tsx", ".mts"}:
        debug_log(f"File extension {file_path.suffix} not suitable for tsc, skipping")
        return False, ""

    tsc_bin = find_tool("tsc", project_root)
    if not tsc_bin:
        debug_log("TypeScript compiler not available")
        return False, ""

    tsconfig_path = None
    if project_root:
        for tsconfig_name in ["tsconfig.json", "tsconfig.app.json"]:
            potential_tsconfig = project_root / tsconfig_name
            debug_log(f"Checking for: {potential_tsconfig}")
            if potential_tsconfig.exists():
                tsconfig_path = potential_tsconfig
                debug_log(f"Found tsconfig: {tsconfig_path}")
                break

    try:
        cmd = [tsc_bin, "--noEmit"]
        if tsconfig_path:
            cmd.extend(["--project", str(tsconfig_path)])
            debug_log(f"Using tsconfig: {tsconfig_path}")
        else:
            cmd.append(str(file_path))
            debug_log("No tsconfig found, checking single file")

        debug_log(f"Running: {' '.join(cmd)}")
        debug_log(f"Working directory: {project_root}")
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            cwd=project_root,
        )
        
        debug_log(f"TSC exit code: {result.returncode}")
        
        output = result.stdout + result.stderr
        has_issues = result.returncode != 0
        
        if has_issues:
            error_count = len([line for line in output.splitlines() if "error TS" in line])
            debug_log(f"TSC found {error_count} type errors")
        else:
            debug_log("TSC check passed")
        
        return has_issues, output
    except Exception as e:
        debug_log(f"Error running TSC: {e}")
        return False, ""


def display_eslint_result(output: str) -> None:
    """Display eslint results."""
    try:
        data = json.loads(output)
        total_errors = sum(f.get("errorCount", 0) for f in data)
        total_warnings = sum(f.get("warningCount", 0) for f in data)
        total = total_errors + total_warnings
        plural = "issue" if total == 1 else "issues"

        print("", file=sys.stderr)
        print(f"📝 ESLint: {total} {plural} ({total_errors} errors, {total_warnings} warnings)", file=sys.stderr)
        print("───────────────────────────────────────", file=sys.stderr)

        for file_result in data:
            file_name = Path(file_result.get("filePath", "")).name
            for msg in file_result.get("messages", [])[:10]:
                line = msg.get("line", 0)
                rule_id = msg.get("ruleId", "unknown")
                message = msg.get("message", "")
                severity = "error" if msg.get("severity", 0) == 2 else "warn"
                print(f"  {file_name}:{line} [{severity}] {rule_id}: {message}", file=sys.stderr)

            if len(file_result.get("messages", [])) > 10:
                remaining = len(file_result["messages"]) - 10
                print(f"  ... and {remaining} more issues", file=sys.stderr)

    except json.JSONDecodeError:
        print("", file=sys.stderr)
        print("📝 ESLint: issues found", file=sys.stderr)
        print("───────────────────────────────────────", file=sys.stderr)
        print(output, file=sys.stderr)

    print("", file=sys.stderr)


def display_tsc_result(output: str) -> None:
    """Display TypeScript compiler results."""
    lines = [line for line in output.splitlines() if line.strip()]
    error_lines = [line for line in lines if "error TS" in line]
    error_count = len(error_lines)
    plural = "issue" if error_count == 1 else "issues"

    print("", file=sys.stderr)
    print(f"🔷 TypeScript: {error_count} {plural}", file=sys.stderr)
    print("───────────────────────────────────────", file=sys.stderr)

    for line in error_lines[:10]:
        if "): error TS" in line:
            parts = line.split("): error TS", 1)
            location = parts[0].split("/")[-1] if "/" in parts[0] else parts[0]
            error_msg = parts[1] if len(parts) > 1 else ""
            code_end = error_msg.find(":")
            if code_end > 0:
                code = "TS" + error_msg[:code_end]
                msg = error_msg[code_end + 1:].strip()
                print(f"  {location}) [{code}]: {msg}", file=sys.stderr)
            else:
                print(f"  {line}", file=sys.stderr)
        else:
            print(f"  {line}", file=sys.stderr)

    if len(error_lines) > 10:
        remaining = len(error_lines) - 10
        print(f"  ... and {remaining} more issues", file=sys.stderr)

    print("", file=sys.stderr)


def main() -> int:
    """Main entry point."""
    debug_log("=" * 60)
    debug_log("TypeScript Hook Starting")
    debug_log("=" * 60)
    debug_log(f"Current working directory: {Path.cwd()}")
    debug_log(f"Script arguments: {sys.argv}")

    git_root = find_git_root()
    if git_root:
        debug_log(f"Changing to git root: {git_root}")
        os.chdir(git_root)
    else:
        debug_log("No git root found, staying in current directory")

    most_recent = find_most_recent_file(Path.cwd())
    if not most_recent:
        debug_log("No files found, exiting")
        return 0

    debug_log(f"Most recent file: {most_recent}")
    debug_log(f"File extension: {most_recent.suffix}")

    if most_recent.suffix not in TS_EXTENSIONS:
        debug_log(f"File extension {most_recent.suffix} not in {TS_EXTENSIONS}, skipping")
        return 0

    # Check for test files
    # if any(pattern in most_recent.name for pattern in ["test.", "spec.", ".test.", ".spec."]):
    #     debug_log(f"File {most_recent.name} appears to be a test file, skipping")
    #     return 0

    # if any(pattern in str(most_recent) for pattern in ["/test/", "/tests/", "/__tests__/"]):
    #     debug_log(f"File {most_recent} is in a test directory, skipping")
    #     return 0

    project_root = find_project_root(most_recent)
    debug_log(f"Project root: {project_root}")

    has_eslint = find_tool("eslint", project_root) is not None
    has_tsc = find_tool("tsc", project_root) is not None and most_recent.suffix in {".ts", ".tsx", ".mts"}

    debug_log(f"Tools available - ESLint: {has_eslint}, TSC: {has_tsc}")

    if not (has_eslint or has_tsc):
        debug_log("No linting tools available, exiting")
        return 0

    auto_format(most_recent, project_root)

    results = {}
    has_issues = False

    if has_eslint:
        debug_log("Starting ESLint check...")
        eslint_issues, eslint_output = run_eslint_check(most_recent, project_root)
        if eslint_issues:
            debug_log("ESLint found issues")
            has_issues = True
            results["eslint"] = eslint_output
        else:
            debug_log("ESLint check passed")

    if has_tsc:
        debug_log("Starting TypeScript check...")
        tsc_issues, tsc_output = run_tsc_check(most_recent, project_root)
        if tsc_issues:
            debug_log("TypeScript found issues")
            has_issues = True
            results["tsc"] = tsc_output
        else:
            debug_log("TypeScript check passed")

    if has_issues:
        debug_log("Issues found, displaying results")
        print("", file=sys.stderr)
        print(
            f"{RED}🛑 TypeScript Issues found in: {most_recent.relative_to(Path.cwd())}{NC}",
            file=sys.stderr,
        )

        if "eslint" in results:
            display_eslint_result(results["eslint"])

        if "tsc" in results:
            display_tsc_result(results["tsc"])

        print(f"{RED}Fix TypeScript issues above before continuing{NC}", file=sys.stderr)
        debug_log("Exiting with code 2 (issues found)")
        return 2
    else:
        debug_log("All checks passed")
        print("", file=sys.stderr)
        print(f"{GREEN}✅ TypeScript: All checks passed{NC}", file=sys.stderr)
        debug_log("Exiting with code 0 (success)")
        return 0  # Fixed: was 2, should be 0


if __name__ == "__main__":
    sys.exit(main())