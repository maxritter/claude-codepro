"""VS Code Extensions step - installs recommended IDE extensions."""

from __future__ import annotations

import subprocess

from installer.context import InstallContext
from installer.steps.base import BaseStep

IDE_CLI_COMMANDS = [
    "antigravity",
    "cursor",
    "windsurf",
    "code",
]

CONTAINER_EXTENSIONS = [
    "anthropic.claude-code",
    "charliermarsh.ruff",
    "dbaeumer.vscode-eslint",
    "dotenv.dotenv-vscode",
    "esbenp.prettier-vscode",
    "github.github-vscode-theme",
    "lumirelle.shell-format-rev",
    "ms-python.debugpy",
    "ms-python.python",
    "detachhead.basedpyright",
    "pkief.material-icon-theme",
    "redhat.vscode-xml",
    "redhat.vscode-yaml",
    "tamasfe.even-better-toml",
]

LOCAL_EXTENSIONS = [
    "dkodr.claudeboard",
]


def _get_ide_cli() -> str | None:
    """Find a working IDE CLI command."""
    for cmd in IDE_CLI_COMMANDS:
        try:
            result = subprocess.run(
                [cmd, "--list-extensions"],
                capture_output=True,
                timeout=10,
            )
            if result.returncode == 0:
                return cmd
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    return None


def _get_installed_extensions(cli: str) -> set[str]:
    """Get set of currently installed extension IDs."""
    try:
        result = subprocess.run(
            [cli, "--list-extensions"],
            capture_output=True,
            text=True,
            check=True,
        )
        return {ext.strip().lower() for ext in result.stdout.splitlines() if ext.strip()}
    except subprocess.CalledProcessError:
        return set()


def _install_extension(cli: str, extension_id: str) -> bool:
    """Install a single extension and verify it was installed."""
    try:
        result = subprocess.run(
            [cli, "--install-extension", extension_id, "--force"],
            capture_output=True,
            text=True,
        )
        output = result.stdout + result.stderr
        if "Cannot install" in output or "not found" in output.lower():
            return False
        installed = _get_installed_extensions(cli)
        return extension_id.lower() in installed
    except subprocess.CalledProcessError:
        return False


class VSCodeExtensionsStep(BaseStep):
    """Step that installs recommended VS Code/Cursor/Windsurf extensions."""

    name = "vscode_extensions"

    def check(self, ctx: InstallContext) -> bool:
        """Always run this step to show proper status messages."""
        return False

    def run(self, ctx: InstallContext) -> None:
        """Install missing IDE extensions."""
        ui = ctx.ui

        cli = _get_ide_cli()
        if not cli:
            if ui:
                ui.warning("No IDE CLI found - extensions will install when IDE connects")
                ui.print("  [dim]Supported: VS Code, Cursor, Windsurf[/dim]")
            return

        if ui:
            ui.status(f"Using {cli} CLI for extension management")

        installed = _get_installed_extensions(cli)
        missing = [ext for ext in CONTAINER_EXTENSIONS if ext.lower() not in installed]
        already_installed = [ext for ext in CONTAINER_EXTENSIONS if ext.lower() in installed]

        if not missing:
            if ui:
                ui.success(f"All {len(already_installed)} recommended extensions already installed:")
                for ext in already_installed:
                    ui.print(f"    [dim]✓ {ext}[/dim]")
            ctx.config["installed_extensions"] = 0
            ctx.config["failed_extensions"] = []
            ctx.config["local_extensions"] = LOCAL_EXTENSIONS
            return

        if ui:
            ui.status(f"Installing {len(missing)} extensions...")

        installed_count = 0
        failed: list[str] = []

        for ext in missing:
            if _install_extension(cli, ext):
                installed_count += 1
                if ui:
                    ui.print(f"  [green]✓[/green] {ext}")
            else:
                failed.append(ext)
                if ui:
                    ui.print(f"  [yellow]✗[/yellow] {ext}")

        if ui:
            if installed_count > 0:
                ui.success(f"Installed {installed_count} extensions")
            if failed:
                ui.warning(f"Failed to install: {', '.join(failed)}")

        ctx.config["installed_extensions"] = installed_count
        ctx.config["failed_extensions"] = failed
        ctx.config["local_extensions"] = LOCAL_EXTENSIONS
