"""CLI entry point and step orchestration using argparse."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from installer import __build__
from installer.config import load_config, save_config
from installer.context import InstallContext
from installer.errors import FatalInstallError, InstallationCancelled
from installer.steps.base import BaseStep
from installer.steps.bootstrap import BootstrapStep
from installer.steps.claude_files import ClaudeFilesStep
from installer.steps.config_files import ConfigFilesStep
from installer.steps.dependencies import DependenciesStep
from installer.steps.finalize import FinalizeStep
from installer.steps.git_setup import GitSetupStep
from installer.steps.prerequisites import PrerequisitesStep
from installer.steps.shell_config import ShellConfigStep
from installer.steps.vscode_extensions import VSCodeExtensionsStep
from installer.ui import Console


def get_all_steps() -> list[BaseStep]:
    """Get all installation steps in order."""
    return [
        BootstrapStep(),
        PrerequisitesStep(),
        GitSetupStep(),
        ClaudeFilesStep(),
        ConfigFilesStep(),
        DependenciesStep(),
        ShellConfigStep(),
        VSCodeExtensionsStep(),
        FinalizeStep(),
    ]


def _validate_license_key(
    console: Console,
    project_dir: Path,
    license_key: str,
    local_mode: bool,
    local_repo_dir: Path | None,
) -> bool:
    """Validate license key using ccp binary."""
    bin_path = project_dir / ".claude" / "bin" / "ccp"

    if local_mode and local_repo_dir:
        local_bin = local_repo_dir / ".claude" / "bin" / "ccp"
        if local_bin.exists():
            bin_path = local_bin

    if not bin_path.exists():
        console.warning("CCP binary not found - skipping license validation")
        console.info("License will be validated on first run")
        return True

    with console.spinner("Validating license key..."):
        result = subprocess.run(
            [str(bin_path), "activate", license_key, "--json"],
            capture_output=True,
            text=True,
            timeout=30,
        )

    if result.returncode == 0:
        console.print()
        console.success("License activated successfully!")
        console.print()
        return True
    else:
        console.print()
        console.error("License validation failed")
        if result.stderr:
            console.print(f"  [dim]{result.stderr.strip()}[/dim]")
        console.print()
        return False


def _start_trial(
    console: Console,
    project_dir: Path,
    local_mode: bool,
    local_repo_dir: Path | None,
) -> bool:
    """Start a 7-day trial using ccp binary."""
    bin_path = project_dir / ".claude" / "bin" / "ccp"
    if not bin_path.exists() and local_mode and local_repo_dir:
        local_bin = local_repo_dir / ".claude" / "bin" / "ccp"
        if local_bin.exists():
            bin_path = local_bin

    if not bin_path.exists():
        console.error("CCP binary not found")
        return False

    def _run_trial_start() -> bool:
        result = subprocess.run(
            [str(bin_path), "trial", "--start", "--json"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return True
        output = result.stdout.strip() or result.stderr.strip()
        if output:
            try:
                data = json.loads(output)
                if data.get("error") == "trial_already_used":
                    console.error("Trial has already been used on this machine")
                    console.print("  [cyan]Subscribe at: https://license.claude-code.pro[/cyan]")
                    console.print("  [bold green]Use code TRIAL50OFF for 50% off your first month![/bold green]")
                else:
                    console.error(f"Failed to start trial: {data.get('error', 'Unknown error')}")
            except json.JSONDecodeError:
                console.error(f"Failed to start trial: {output}")
        else:
            console.error("Failed to start trial")
        return False

    try:
        with console.spinner("Starting trial..."):
            return _run_trial_start()
    except subprocess.TimeoutExpired:
        console.error("Trial start timed out")
        return False
    except Exception as e:
        console.error(f"Failed to start trial: {e}")
        return False


def _check_trial_used(
    project_dir: Path,
    local_mode: bool,
    local_repo_dir: Path | None,
) -> tuple[bool | None, bool]:
    """Check if trial has been used via ccp binary.

    Returns (trial_used, can_reactivate):
    - trial_used: True if trial was used, False if not, None if check failed
    - can_reactivate: True if within 7-day window and can reactivate
    """
    bin_path = project_dir / ".claude" / "bin" / "ccp"
    if not bin_path.exists() and local_mode and local_repo_dir:
        local_bin = local_repo_dir / ".claude" / "bin" / "ccp"
        if local_bin.exists():
            bin_path = local_bin

    if not bin_path.exists():
        return None, False

    try:
        result = subprocess.run(
            [str(bin_path), "trial", "--check", "--json"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        output = result.stdout.strip() or result.stderr.strip()
        if output:
            data = json.loads(output)
            trial_used = data.get("trial_used", False)
            can_reactivate = data.get("can_reactivate", False)
            return trial_used, can_reactivate
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        pass
    return None, False


def _get_license_info(
    project_dir: Path,
    local: bool = False,
    local_repo_dir: Path | None = None,
    console: Console | None = None,
) -> dict | None:
    """Get current license information using ccp binary.

    Returns dict with: tier, email, created_at, expires_at, days_remaining, is_expired
    or None if no license exists or ccp binary not found.
    """
    bin_path = project_dir / ".claude" / "bin" / "ccp"
    if not bin_path.exists() and local and local_repo_dir:
        local_bin = local_repo_dir / ".claude" / "bin" / "ccp"
        if local_bin.exists():
            bin_path = local_bin

    if not bin_path.exists():
        return None

    def _run_status() -> dict | None:
        try:
            result = subprocess.run(
                [str(bin_path), "status", "--json"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            output = result.stdout.strip() or result.stderr.strip()
            if output:
                data = json.loads(output)
                if not data.get("success", True) and "expired" in data.get("error", "").lower():
                    data["is_expired"] = True
                return data
        except (subprocess.SubprocessError, json.JSONDecodeError):
            pass
        return None

    if console:
        with console.spinner("Checking license status..."):
            return _run_status()
    else:
        return _run_status()


def run_installation(ctx: InstallContext) -> None:
    """Execute all installation steps."""
    ui = ctx.ui
    steps = get_all_steps()

    if ui:
        ui.set_total_steps(len(steps))

    for step in steps:
        if ui:
            ui.step(step.name.replace("_", " ").title())

        if step.check(ctx):
            if ui:
                ui.info(f"Already complete, skipping")
            continue

        try:
            step.run(ctx)
        except KeyboardInterrupt:
            raise InstallationCancelled(step.name) from None
        ctx.mark_completed(step.name)


def _prompt_license_key(
    console: Console,
    project_dir: Path,
    local_mode: bool,
    local_repo_dir: Path | None,
    max_attempts: int = 3,
) -> bool:
    """Prompt user for license key with retry logic."""
    for attempt in range(max_attempts):
        license_key = console.input("Enter your license key").strip()
        if not license_key:
            console.error("License key is required")
            if attempt < max_attempts - 1:
                console.print("  [dim]Please try again.[/dim]")
            continue

        validated = _validate_license_key(console, project_dir, license_key, local_mode, local_repo_dir)
        if validated:
            return True
        if attempt < max_attempts - 1:
            console.print()
            console.print("  [dim]Please check your license key and try again.[/dim]")
            console.print("  [dim]Subscribe: https://license.claude-code.pro[/dim]")
            console.print()

    console.print()
    console.error(f"License validation failed after {max_attempts} attempts.")
    console.print("  [bold]Subscribe at:[/bold] [cyan]https://license.claude-code.pro[/cyan]")
    console.print()
    return False


def _handle_license_flow(
    console: Console,
    project_dir: Path,
    local_mode: bool,
    local_repo_dir: Path | None,
    license_info: dict | None,
    license_acknowledged: bool,
) -> int | None:
    """Handle license verification flow. Returns exit code if should exit, None to continue."""
    if license_acknowledged and license_info:
        tier = license_info.get("tier", "unknown")
        is_expired = license_info.get("is_expired", False)

        if tier == "trial" and is_expired:
            console.print()
            console.print("  [bold]Enter your license key to continue:[/bold]")
            console.print()
            if not _prompt_license_key(console, project_dir, local_mode, local_repo_dir):
                return 1
            console.print()
        return None

    console.print()
    console.print("  [bold cyan]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold cyan]")
    console.print("  [bold]📜 License Agreement[/bold]")
    console.print("  [bold cyan]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold cyan]")
    console.print()
    console.print("  [bold green]7-day free trial[/bold green] to explore all features")
    console.print()
    console.print("  [bold]After trial, choose a plan:[/bold]")
    console.print("    • [bold]Standard[/bold]")
    console.print("    • [bold]Enterprise[/bold] (priority support + feature requests)")
    console.print()
    console.print("  [bold cyan]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold cyan]")
    console.print()
    console.print("  [dim]Subscribe: https://license.claude-code.pro[/dim]")
    console.print()
    console.print("  [bold cyan]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold cyan]")
    console.print()

    with console.spinner("Checking trial eligibility..."):
        trial_used, can_reactivate = _check_trial_used(project_dir, local_mode, local_repo_dir)
    if trial_used is None:
        trial_used = False

    if trial_used and not can_reactivate:
        console.print("  [bold yellow]Trial has expired on this machine.[/bold yellow]")
        console.print("  Please enter a license key to continue.")
        console.print()
        console.print("  [bold green]Use code TRIAL50OFF for 50% off your first month![/bold green]")
        console.print("  [dim](Regular pricing applies after first month)[/dim]")
        console.print()
        if not _prompt_license_key(console, project_dir, local_mode, local_repo_dir):
            return 1
    else:
        started = _start_trial(console, project_dir, local_mode, local_repo_dir)
        if started:
            console.print()
            console.success("Your 7-day trial has started!")
            console.print("  All features are unlocked for 7 days.")
            console.print()
            console.print("  [bold]Subscribe after trial:[/bold] [cyan]https://license.claude-code.pro[/cyan]")
            console.print()
        else:
            console.print()
            console.error("Could not start trial. Please enter a license key.")
            console.print("  [bold]Subscribe at:[/bold] [cyan]https://license.claude-code.pro[/cyan]")
            console.print()
            return 1

    return None


def _prompt_for_features(
    console: Console,
    saved_config: dict,
    skip_python: bool,
    skip_typescript: bool,
    skip_golang: bool,
    skip_prompts: bool,
) -> tuple[bool, bool, bool, bool]:
    """Prompt for feature installation preferences. Returns (python, typescript, golang, browser)."""
    enable_python = not skip_python
    if not skip_python and not skip_prompts:
        if "enable_python" in saved_config:
            enable_python = saved_config["enable_python"]
            console.print()
            console.print(f"  [dim]Using saved preference: Python support = {enable_python}[/dim]")
        else:
            console.print()
            console.print("  [bold]Do you want to install advanced Python features?[/bold]")
            console.print("  This includes: uv, ruff, basedpyright, and Python quality hooks")
            enable_python = console.confirm("Install Python support?", default=True)

    enable_typescript = not skip_typescript
    if not skip_typescript and not skip_prompts:
        if "enable_typescript" in saved_config:
            enable_typescript = saved_config["enable_typescript"]
            console.print(f"  [dim]Using saved preference: TypeScript support = {enable_typescript}[/dim]")
        else:
            console.print()
            console.print("  [bold]Do you want to install TypeScript features?[/bold]")
            console.print("  This includes: TypeScript quality hooks (eslint, tsc, prettier)")
            enable_typescript = console.confirm("Install TypeScript support?", default=True)

    enable_golang = not skip_golang
    if not skip_golang and not skip_prompts:
        if "enable_golang" in saved_config:
            enable_golang = saved_config["enable_golang"]
            console.print(f"  [dim]Using saved preference: Go support = {enable_golang}[/dim]")
        else:
            console.print()
            console.print("  [bold]Do you want to install Go features?[/bold]")
            console.print("  This includes: Go quality hooks (gofmt, go vet, golangci-lint)")
            enable_golang = console.confirm("Install Go support?", default=True)

    enable_agent_browser = True
    if not skip_prompts:
        if "enable_agent_browser" in saved_config:
            enable_agent_browser = saved_config["enable_agent_browser"]
            console.print(f"  [dim]Using saved preference: Agent browser = {enable_agent_browser}[/dim]")
        else:
            console.print()
            console.print("  [bold]Do you want to install agent-browser?[/bold]")
            console.print("  This includes: Headless Chromium browser for web automation and testing")
            enable_agent_browser = console.confirm("Install agent-browser?", default=True)

    return enable_python, enable_typescript, enable_golang, enable_agent_browser


def cmd_install(args: argparse.Namespace) -> int:
    """Install Claude CodePro."""
    console = Console(non_interactive=args.non_interactive, quiet=args.quiet)

    effective_local_repo_dir = args.local_repo_dir if args.local_repo_dir else (Path.cwd() if args.local else None)
    skip_prompts = args.non_interactive
    project_dir = Path.cwd()
    saved_config = load_config(project_dir)

    license_info = _get_license_info(project_dir, args.local, effective_local_repo_dir, console)
    license_acknowledged = license_info is not None and license_info.get("tier") in ("trial", "standard", "enterprise")

    console.banner(license_info=license_info)

    if not skip_prompts:
        exit_code = _handle_license_flow(
            console, project_dir, args.local, effective_local_repo_dir, license_info, license_acknowledged
        )
        if exit_code is not None:
            return exit_code

    enable_python, enable_typescript, enable_golang, enable_agent_browser = _prompt_for_features(
        console, saved_config, args.skip_python, args.skip_typescript, args.skip_golang, skip_prompts
    )

    if not skip_prompts:
        saved_config["enable_python"] = enable_python
        saved_config["enable_typescript"] = enable_typescript
        saved_config["enable_golang"] = enable_golang
        saved_config["enable_agent_browser"] = enable_agent_browser
        save_config(project_dir, saved_config)

    ctx = InstallContext(
        project_dir=project_dir,
        enable_python=enable_python,
        enable_typescript=enable_typescript,
        enable_golang=enable_golang,
        enable_agent_browser=enable_agent_browser,
        non_interactive=args.non_interactive,
        skip_env=args.skip_env,
        local_mode=args.local,
        local_repo_dir=effective_local_repo_dir,
        is_local_install=args.local_system,
        target_version=args.target_version,
        ui=console,
    )

    try:
        run_installation(ctx)
    except FatalInstallError as e:
        console.error(f"Installation failed: {e}")
        return 1
    except InstallationCancelled as e:
        console.warning(f"Installation cancelled during: {e.step_name}")
        console.info("Run the installer again to resume from where you left off")
        return 130
    except KeyboardInterrupt:
        console.warning("Installation cancelled")
        return 130

    return 0


def cmd_version(_args: argparse.Namespace) -> int:
    """Show version information."""
    print(f"ccp-installer (build: {__build__})")
    return 0


def find_ccp_binary() -> Path | None:
    """Find the ccp binary in .claude/bin/."""
    binary_path = Path.cwd() / ".claude" / "bin" / "ccp"
    if binary_path.exists():
        return binary_path
    return None


def cmd_launch(args: argparse.Namespace) -> int:
    """Launch Claude Code via ccp binary."""
    claude_args = args.args or []

    ccp_path = find_ccp_binary()
    if ccp_path:
        cmd = [str(ccp_path)] + claude_args
    else:
        cmd = ["claude"] + claude_args

    return subprocess.call(cmd)


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        prog="installer",
        description="Claude CodePro Installer",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    install_parser = subparsers.add_parser("install", help="Install Claude CodePro")
    install_parser.add_argument(
        "-n",
        "--non-interactive",
        action="store_true",
        help="Run without interactive prompts",
    )
    install_parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Minimal output (for updates)",
    )
    install_parser.add_argument(
        "--skip-env",
        action="store_true",
        help="Skip environment setup (API keys)",
    )
    install_parser.add_argument(
        "--local",
        action="store_true",
        help="Use local files instead of downloading",
    )
    install_parser.add_argument(
        "--local-repo-dir",
        type=Path,
        default=None,
        help="Local repository directory",
    )
    install_parser.add_argument(
        "--skip-python",
        action="store_true",
        help="Skip Python support installation",
    )
    install_parser.add_argument(
        "--skip-typescript",
        action="store_true",
        help="Skip TypeScript support installation",
    )
    install_parser.add_argument(
        "--skip-golang",
        action="store_true",
        help="Skip Go support installation",
    )
    install_parser.add_argument(
        "--local-system",
        action="store_true",
        help="Local installation (not in container)",
    )
    install_parser.add_argument(
        "--target-version",
        type=str,
        default=None,
        help="Target version/tag for downloads (e.g., dev-abc1234-20260124)",
    )

    subparsers.add_parser("version", help="Show version information")

    launch_parser = subparsers.add_parser("launch", help="Launch Claude Code via ccp binary")
    launch_parser.add_argument(
        "args",
        nargs="*",
        help="Arguments to pass to claude",
    )

    return parser


def main() -> None:
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()

    if args.command == "install":
        sys.exit(cmd_install(args))
    elif args.command == "version":
        sys.exit(cmd_version(args))
    elif args.command == "launch":
        sys.exit(cmd_launch(args))
    else:
        parser.print_help()
        sys.exit(0)


if __name__ == "__main__":
    main()
