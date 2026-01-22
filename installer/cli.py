"""CLI entry point and step orchestration using Typer."""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer

from installer import __build__
from installer.config import load_config, save_config
from installer.context import InstallContext
from installer.errors import FatalInstallError
from installer.steps.base import BaseStep
from installer.steps.bootstrap import BootstrapStep
from installer.steps.claude_files import ClaudeFilesStep
from installer.steps.config_files import ConfigFilesStep
from installer.steps.dependencies import DependenciesStep
from installer.steps.environment import EnvironmentStep
from installer.steps.finalize import FinalizeStep
from installer.steps.git_setup import GitSetupStep
from installer.steps.github_auth import GitHubAuthStep
from installer.steps.prerequisites import PrerequisitesStep
from installer.steps.shell_config import ShellConfigStep
from installer.steps.vscode_extensions import VSCodeExtensionsStep
from installer.ui import Console

app = typer.Typer(
    name="installer",
    help="Claude CodePro Installer",
    add_completion=False,
)


def get_all_steps() -> list[BaseStep]:
    """Get all installation steps in order."""
    return [
        BootstrapStep(),
        PrerequisitesStep(),
        GitSetupStep(),
        GitHubAuthStep(),
        ClaudeFilesStep(),
        ConfigFilesStep(),
        DependenciesStep(),
        EnvironmentStep(),
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


def rollback_completed_steps(ctx: InstallContext, steps: list[BaseStep]) -> None:
    """Rollback all completed steps in reverse order."""
    ui = ctx.ui
    if ui:
        ui.warning("Rolling back installation...")

    completed_names = set(ctx.completed_steps)

    for step in reversed(steps):
        if step.name in completed_names:
            try:
                if ui:
                    ui.status(f"Rolling back {step.name}...")
                step.rollback(ctx)
            except Exception as e:
                if ui:
                    ui.error(f"Rollback failed for {step.name}: {e}")


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
            ctx.mark_completed(step.name)
        except FatalInstallError:
            rollback_completed_steps(ctx, steps)
            raise


@app.command()
def install(
    non_interactive: bool = typer.Option(False, "--non-interactive", "-n", help="Run without interactive prompts"),
    skip_env: bool = typer.Option(False, "--skip-env", help="Skip environment setup (API keys)"),
    local: bool = typer.Option(False, "--local", help="Use local files instead of downloading"),
    local_repo_dir: Optional[Path] = typer.Option(None, "--local-repo-dir", help="Local repository directory"),
    skip_python: bool = typer.Option(False, "--skip-python", help="Skip Python support installation"),
    skip_typescript: bool = typer.Option(False, "--skip-typescript", help="Skip TypeScript support installation"),
    skip_golang: bool = typer.Option(False, "--skip-golang", help="Skip Go support installation"),
    local_system: bool = typer.Option(False, "--local-system", help="Local installation (not in container)"),
) -> None:
    """Install Claude CodePro."""
    console = Console(non_interactive=non_interactive)

    effective_local_repo_dir = local_repo_dir if local_repo_dir else (Path.cwd() if local else None)
    skip_prompts = non_interactive
    project_dir = Path.cwd()
    saved_config = load_config(project_dir)

    from installer.steps.ccp_binary import CcpBinaryStep

    ccp_step = CcpBinaryStep()
    ccp_ctx = InstallContext(project_dir=project_dir, ui=console)
    if not ccp_step.check(ccp_ctx):
        ccp_step.run(ccp_ctx)

    license_info = _get_license_info(project_dir, local, effective_local_repo_dir, console)
    license_acknowledged = license_info is not None and license_info.get("tier") in ("trial", "standard", "enterprise")

    console.banner(license_info=license_info)

    if not skip_prompts and license_acknowledged and license_info:
        tier = license_info.get("tier", "unknown")
        is_expired = license_info.get("is_expired", False)

        if tier == "trial" and is_expired:
            console.print()
            console.print("  [bold]Enter your license key to continue:[/bold]")
            console.print()

            for attempt in range(3):
                license_key = console.input("License key").strip()
                if not license_key:
                    console.error("License key is required")
                    continue

                validated = _validate_license_key(console, project_dir, license_key, local, effective_local_repo_dir)
                if validated:
                    license_info = _get_license_info(project_dir, local, effective_local_repo_dir)
                    break
                if attempt < 2:
                    console.print("  [dim]Please check your license key and try again.[/dim]")
            else:
                console.error("License validation failed after 3 attempts.")
                console.print("  [bold]Subscribe at:[/bold] [cyan]https://license.claude-code.pro[/cyan]")
                raise typer.Exit(1)

            console.print()

    elif not skip_prompts and not license_acknowledged:
        console.print()
        console.print("  [bold cyan]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold cyan]")
        console.print("  [bold]📜 License Agreement[/bold]")
        console.print("  [bold cyan]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold cyan]")
        console.print()
        console.print("  [bold green]7-day free trial[/bold green] to explore all features")
        console.print()
        console.print("  [bold]After trial, choose a plan:[/bold]")
        console.print("    • [bold]Standard[/bold]")
        console.print("    • [bold]Enterprise[/bold] (priority support + training)")
        console.print()
        console.print("  [bold cyan]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold cyan]")
        console.print()
        console.print("  [dim]Subscribe: https://license.claude-code.pro[/dim]")
        console.print()
        console.print("  [bold cyan]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold cyan]")
        console.print()

        with console.spinner("Checking trial eligibility..."):
            trial_used, can_reactivate = _check_trial_used(project_dir, local, effective_local_repo_dir)
        if trial_used is None:
            trial_used = False

        if trial_used and not can_reactivate:
            console.print("  [bold yellow]Trial has expired on this machine.[/bold yellow]")
            console.print("  Please enter a license key to continue.")
            console.print()
            console.print("  [bold green]Use code TRIAL50OFF for 50% off your first month![/bold green]")
            console.print("  [dim](Regular pricing applies after first month)[/dim]")
            console.print()

            for attempt in range(3):
                license_key = console.input("Enter your license key").strip()
                if not license_key:
                    console.error("License key is required")
                    if attempt < 2:
                        console.print("  [dim]Please try again.[/dim]")
                    continue

                validated = _validate_license_key(console, project_dir, license_key, local, effective_local_repo_dir)
                if validated:
                    break
                else:
                    if attempt < 2:
                        console.print()
                        console.print("  [dim]Please check your license key and try again.[/dim]")
                        console.print("  [dim]Subscribe: https://license.claude-code.pro[/dim]")
                        console.print()
            else:
                console.print()
                console.error("License validation failed after 3 attempts.")
                console.print("  [bold]Subscribe at:[/bold] [cyan]https://license.claude-code.pro[/cyan]")
                console.print()
                raise typer.Exit(1)
        else:
            started = _start_trial(console, project_dir, local, effective_local_repo_dir)
            if started:
                console.print()
                console.success("Your 7-day trial has started!")
                console.print("  All features are unlocked for 7 days.")
                console.print()
                console.print("  [bold]Subscribe after trial:[/bold] [cyan]https://license.claude-code.pro[/cyan]")
                console.print()

    claude_dir = Path.cwd() / ".claude"
    if claude_dir.exists() and not skip_prompts:
        console.print()
        console.print("  [bold yellow]⚠️  Existing .claude folder detected[/bold yellow]")
        console.print()
        console.print("  The following will be [bold red]overwritten[/bold red] during installation:")
        console.print("    • .claude/commands/")
        console.print("    • .claude/hooks/")
        console.print("    • .claude/skills/")
        console.print("    • .claude/bin/")
        console.print("    • .claude/rules/standard/")
        console.print("    • .claude/settings.json")
        console.print()
        console.print("  [dim]Your custom rules in .claude/rules/custom/ will NOT be touched.[/dim]")
        console.print()
        create_backup = console.confirm("Create backup before proceeding?", default=False)

        if create_backup:
            timestamp = datetime.now().strftime("%Y%m%d.%H%M%S")
            backup_dir = Path.cwd() / f".claude.backup.{timestamp}"
            console.status(f"Creating backup at {backup_dir}...")

            def ignore_special_files(directory: str, files: list[str]) -> list[str]:
                """Ignore pipes, sockets, and other special files."""
                ignored = []
                for f in files:
                    path = Path(directory) / f
                    if path.is_fifo() or path.is_socket() or path.is_block_device() or path.is_char_device():
                        ignored.append(f)
                    if f == "tmp":
                        ignored.append(f)
                return ignored

            shutil.copytree(claude_dir, backup_dir, ignore=ignore_special_files)
            console.success(f"Backup created: {backup_dir}")

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

    from installer.steps.environment import add_env_key, key_is_set

    env_file = project_dir / ".env"

    enable_openai_embeddings = True
    if not skip_prompts:
        if "enable_openai_embeddings" in saved_config:
            enable_openai_embeddings = saved_config["enable_openai_embeddings"]
            console.print(f"  [dim]Using saved preference: OpenAI embeddings = {enable_openai_embeddings}[/dim]")
        else:
            console.print()
            console.print("  [bold]Do you want to enable OpenAI embeddings for Vexor?[/bold]")
            console.print("  This includes: Fast, high-quality semantic code search")
            console.print("  [dim]Requires API key from platform.openai.com[/dim]")
            enable_openai_embeddings = console.confirm("Enable OpenAI embeddings?", default=True)
            if not enable_openai_embeddings:
                console.info("Will use local embeddings (model downloaded during setup)")

        if enable_openai_embeddings and not key_is_set("OPENAI_API_KEY", env_file):
            console.print()
            console.print("  [bold]Create at:[/bold] [cyan]https://platform.openai.com/api-keys[/cyan]")
            openai_key = console.input("OPENAI_API_KEY", default="")
            if openai_key:
                add_env_key("OPENAI_API_KEY", openai_key, env_file)
                console.success("OpenAI API key saved")

    enable_firecrawl = True
    if not skip_prompts:
        if "enable_firecrawl" in saved_config:
            enable_firecrawl = saved_config["enable_firecrawl"]
            console.print(f"  [dim]Using saved preference: Firecrawl = {enable_firecrawl}[/dim]")
        else:
            console.print()
            console.print("  [bold]Do you want to enable Firecrawl web scraping?[/bold]")
            console.print("  This includes: Web scraping, search, and content extraction")
            console.print("  [dim]Requires API key from firecrawl.dev (free tier available)[/dim]")
            enable_firecrawl = console.confirm("Enable Firecrawl?", default=True)
            if not enable_firecrawl:
                console.info("Firecrawl disabled - web scraping features will not be available")

        if enable_firecrawl and not key_is_set("FIRECRAWL_API_KEY", env_file):
            console.print()
            console.print("  [bold]Create at:[/bold] [cyan]https://www.firecrawl.dev/app/api-keys[/cyan] (free tier)")
            firecrawl_key = console.input("FIRECRAWL_API_KEY", default="")
            if firecrawl_key:
                add_env_key("FIRECRAWL_API_KEY", firecrawl_key, env_file)
                console.success("Firecrawl API key saved")

    if not skip_prompts:
        saved_config["enable_python"] = enable_python
        saved_config["enable_typescript"] = enable_typescript
        saved_config["enable_golang"] = enable_golang
        saved_config["enable_agent_browser"] = enable_agent_browser
        saved_config["enable_openai_embeddings"] = enable_openai_embeddings
        saved_config["enable_firecrawl"] = enable_firecrawl
        save_config(project_dir, saved_config)

    ctx = InstallContext(
        project_dir=project_dir,
        enable_python=enable_python,
        enable_typescript=enable_typescript,
        enable_golang=enable_golang,
        enable_agent_browser=enable_agent_browser,
        non_interactive=non_interactive,
        skip_env=skip_env,
        local_mode=local,
        local_repo_dir=effective_local_repo_dir,
        is_local_install=local_system,
        enable_openai_embeddings=enable_openai_embeddings,
        enable_firecrawl=enable_firecrawl,
        ui=console,
    )

    try:
        run_installation(ctx)
    except FatalInstallError as e:
        console.error(f"Installation failed: {e}")
        raise typer.Exit(1) from e
    except KeyboardInterrupt:
        console.warning("Installation cancelled")
        raise typer.Exit(130) from None


@app.command()
def version() -> None:
    """Show version information."""
    typer.echo(f"ccp-installer (build: {__build__})")


def find_ccp_binary() -> Path | None:
    """Find the ccp binary in .claude/bin/."""
    binary_path = Path.cwd() / ".claude" / "bin" / "ccp"
    if binary_path.exists():
        return binary_path
    return None


@app.command()
def launch(
    args: Optional[list[str]] = typer.Argument(None, help="Arguments to pass to claude"),
) -> None:
    """Launch Claude Code via ccp binary."""
    claude_args = args or []

    ccp_path = find_ccp_binary()
    if ccp_path:
        cmd = [str(ccp_path)] + claude_args
    else:
        cmd = ["claude"] + claude_args

    exit_code = subprocess.call(cmd)
    raise typer.Exit(exit_code)


def main() -> None:
    """Main entry point."""
    app()


if __name__ == "__main__":
    main()
