"""CLI entry point and step orchestration using Typer."""

from __future__ import annotations

import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer

from installer import __build__
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
from installer.steps.shell_config import ShellConfigStep
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
        GitSetupStep(),
        ClaudeFilesStep(),
        ConfigFilesStep(),
        DependenciesStep(),
        EnvironmentStep(),
        ShellConfigStep(),
        FinalizeStep(),
    ]


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
) -> None:
    """Install Claude CodePro."""
    console = Console(non_interactive=non_interactive)

    console.banner()
    console.info(f"Build: {__build__}")

    effective_local_repo_dir = local_repo_dir if local_repo_dir else (Path.cwd() if local else None)

    # In local mode, skip all interactive prompts and use defaults
    skip_prompts = non_interactive or local

    claude_dir = Path.cwd() / ".claude"
    if claude_dir.exists() and not skip_prompts:
        console.print()
        console.print("  [bold yellow]⚠️  Existing .claude folder detected[/bold yellow]")
        console.print()
        console.print("  The following will be [bold red]overwritten[/bold red] during installation:")
        console.print("    • .claude/commands/")
        console.print("    • .claude/hooks/")
        console.print("    • .claude/skills/")
        console.print("    • .claude/scripts/")
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
            shutil.copytree(claude_dir, backup_dir)
            console.success(f"Backup created: {backup_dir}")

    install_python = not skip_python
    if not skip_python and not skip_prompts:
        console.print()
        console.print("  [bold]Do you want to install advanced Python features?[/bold]")
        console.print("  This includes: uv, ruff, mypy, basedpyright, and Python quality hooks")
        install_python = console.confirm("Install Python support?", default=True)

    install_typescript = not skip_typescript
    if not skip_typescript and not skip_prompts:
        console.print()
        console.print("  [bold]Do you want to install TypeScript features?[/bold]")
        console.print("  This includes: TypeScript quality hooks (eslint, tsc, prettier)")
        install_typescript = console.confirm("Install TypeScript support?", default=True)

    ctx = InstallContext(
        project_dir=Path.cwd(),
        install_python=install_python,
        install_typescript=install_typescript,
        non_interactive=non_interactive,
        skip_env=skip_env,
        local_mode=local,
        local_repo_dir=effective_local_repo_dir,
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


def find_wrapper_script() -> Path | None:
    """Find the wrapper.py script in .claude/scripts/."""
    wrapper_path = Path.cwd() / ".claude" / "scripts" / "wrapper.py"
    if wrapper_path.exists():
        return wrapper_path

    module_path = Path(__file__).parent.parent / ".claude" / "scripts" / "wrapper.py"
    if module_path.exists():
        return module_path

    return None


def run_with_wrapper(args: list[str]) -> int:
    """Run Claude via the wrapper script."""
    wrapper_path = find_wrapper_script()
    if wrapper_path is None:
        typer.echo("Error: wrapper.py not found in .claude/scripts/", err=True)
        return 1

    cmd = [sys.executable, str(wrapper_path)] + args
    return subprocess.call(cmd)


@app.command()
def launch(
    no_wrapper: bool = typer.Option(False, "--no-wrapper", help="Bypass wrapper, run claude directly"),
    args: Optional[list[str]] = typer.Argument(None, help="Arguments to pass to claude"),
) -> None:
    """Launch Claude Code (via wrapper by default)."""
    claude_args = args or []

    if no_wrapper:
        cmd = ["claude"] + claude_args
        exit_code = subprocess.call(cmd)
    else:
        exit_code = run_with_wrapper(claude_args)

    raise typer.Exit(exit_code)


def main() -> None:
    """Main entry point."""
    app()


if __name__ == "__main__":
    main()
