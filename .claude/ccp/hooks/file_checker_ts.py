"""TypeScript file checker hook - runs eslint and tsc on edited TypeScript file."""

from __future__ import annotations

import json
import os
import re
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

PRESERVE_COMMENT_PATTERNS = re.compile(
    r"//\s*@ts-|"
    r"//\s*eslint-|"
    r"//\s*prettier-|"
    r"//\s*TODO|"
    r"//\s*FIXME|"
    r"//\s*XXX|"
    r"//\s*NOTE|"
    r"//\s*@type|"
    r"//\s*@param|"
    r"//\s*@returns",
    re.IGNORECASE,
)

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


def get_edited_file_from_stdin() -> Path | None:
    """Get the edited file path from PostToolUse hook stdin."""
    try:
        import select

        if select.select([sys.stdin], [], [], 0)[0]:
            data = json.load(sys.stdin)
            tool_input = data.get("tool_input", {})
            file_path = tool_input.get("file_path")
            if file_path:
                debug_log(f"Got file from stdin: {file_path}")
                return Path(file_path)
    except Exception as e:
        debug_log(f"Error reading stdin: {e}")
    return None


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
        if depth > 20:
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


def strip_inline_comments(file_path: Path) -> bool:
    """Remove inline // comments from TypeScript/JavaScript file.

    Removes:
    - End-of-line comments: `code  // comment` → `code`
    - Full-line comments: `// comment` → (line removed)

    Preserves:
    - @ts- directives, eslint/prettier directives
    - TODO, FIXME, XXX, NOTE markers
    - JSDoc-style @type, @param, @returns
    - URLs containing //

    Returns True if file was modified.
    """
    try:
        content = file_path.read_text()
        lines = content.splitlines(keepends=True)
    except Exception:
        return False

    new_lines = []
    modified = False

    for line in lines:
        if "//" not in line:
            new_lines.append(line)
            continue

        if '"//' in line or "'//" in line or "`//" in line:
            new_lines.append(line)
            continue

        if "://" in line:
            new_lines.append(line)
            continue

        match = re.search(r"//.*$", line)
        if not match:
            new_lines.append(line)
            continue

        comment = match.group(0)

        if PRESERVE_COMMENT_PATTERNS.search(comment):
            new_lines.append(line)
            continue

        before_comment = line[: match.start()].rstrip()

        if before_comment:
            new_lines.append(before_comment + "\n")
            modified = True
        else:
            modified = True

    if modified:
        new_content = "".join(new_lines)
        file_path.write_text(new_content)
        return True

    return False


def auto_format(file_path: Path, project_root: Path | None) -> None:
    """Auto-format file with prettier before checks."""
    strip_inline_comments(file_path)
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
                msg = error_msg[code_end + 1 :].strip()
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

    target_file = get_edited_file_from_stdin()
    if not target_file or not target_file.exists():
        debug_log("No file from stdin, exiting")
        return 0

    if git_root:
        try:
            target_file.resolve().relative_to(git_root)
        except ValueError:
            debug_log("File outside git root, skipping")
            return 0

    debug_log(f"Target file: {target_file}")
    debug_log(f"File extension: {target_file.suffix}")

    if target_file.suffix not in TS_EXTENSIONS:
        debug_log(f"File extension {target_file.suffix} not in {TS_EXTENSIONS}, skipping")
        return 0

    if "test" in target_file.name or "spec" in target_file.name:
        debug_log("Test/spec file, skipping")
        return 0

    project_root = find_project_root(target_file)
    debug_log(f"Project root: {project_root}")

    has_eslint = find_tool("eslint", project_root) is not None
    has_tsc = find_tool("tsc", project_root) is not None and target_file.suffix in {".ts", ".tsx", ".mts"}

    debug_log(f"Tools available - ESLint: {has_eslint}, TSC: {has_tsc}")

    if not (has_eslint or has_tsc):
        debug_log("No linting tools available, exiting")
        return 0

    auto_format(target_file, project_root)

    results = {}
    has_issues = False

    if has_eslint:
        debug_log("Starting ESLint check...")
        eslint_issues, eslint_output = run_eslint_check(target_file, project_root)
        if eslint_issues:
            debug_log("ESLint found issues")
            has_issues = True
            results["eslint"] = eslint_output
        else:
            debug_log("ESLint check passed")

    if has_tsc:
        debug_log("Starting TypeScript check...")
        tsc_issues, tsc_output = run_tsc_check(target_file, project_root)
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
            f"{RED}🛑 TypeScript Issues found in: {target_file.relative_to(Path.cwd())}{NC}",
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
        return 0


if __name__ == "__main__":
    sys.exit(main())
