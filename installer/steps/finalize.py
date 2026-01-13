"""Finalize step - runs final cleanup tasks and displays success."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from installer import __version__
from installer.steps.base import BaseStep

if TYPE_CHECKING:
    from installer.context import InstallContext


class FinalizeStep(BaseStep):
    """Step that runs final cleanup tasks and displays success panel."""

    name = "finalize"

    def check(self, ctx: InstallContext) -> bool:
        """Always returns False - finalize always runs."""
        return False

    def run(self, ctx: InstallContext) -> None:
        """Run final cleanup tasks and display success."""

        self._install_statusline_config(ctx)
        self._display_success(ctx)

    def _install_statusline_config(self, ctx: InstallContext) -> None:
        """Install statusline configuration to user config directory."""
        ui = ctx.ui
        source_config = ctx.project_dir / ".claude" / "statusline.json"

        if not source_config.exists():
            if ui:
                ui.warning("statusline.json not found, skipping")
            return

        if ui:
            ui.status("Installing statusline configuration...")

        target_dir = Path.home() / ".config" / "ccstatusline"
        target_config = target_dir / "settings.json"

        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_config, target_config)
            if ui:
                ui.success("Installed statusline configuration")
        except (OSError, IOError) as e:
            if ui:
                ui.warning(f"Failed to install statusline config: {e}")

    def _display_success(self, ctx: InstallContext) -> None:
        """Display success panel with next steps."""
        ui = ctx.ui

        if not ui:
            return

        installed_items = []
        if ctx.config.get("installed_dependencies"):
            for dep in ctx.config["installed_dependencies"]:
                installed_items.append(dep.replace("_", " ").title())

        installed_items.extend(
            [
                "Claude CodePro rules",
                "Shell alias (ccp)",
                "Endless Mode (unlimited context)",
            ]
        )

        if ctx.install_python:
            installed_items.append("Python development tools")

        if ctx.install_typescript:
            installed_items.append("TypeScript quality hooks")

        ui.success_box("Installation Complete!", installed_items)

        project_slug = ctx.project_dir.name.lower().replace(" ", "-").replace("_", "-")

        ui.next_steps(
            [
                (
                    "Connect to dev container",
                    f"Open your favorite terminal (iTerm, Terminal, etc.) and run:\n"
                    f'     docker exec -it $(docker ps --filter "name={project_slug}" -q) zsh',
                ),
                ("Start Claude CodePro", "Run: ccp"),
                ("Connect IDE", "Run: /ide → Enables real-time diagnostics"),
                (
                    "Install IDE Extensions",
                    "Open Extensions sidebar → Filter by '@recommended' → Install all\n"
                    "     (Extensions may not auto-install in fresh containers)",
                ),
                (
                    "Custom MCP Servers (Optional)",
                    "Add your MCP servers to mcp_servers.json, then run /setup\n"
                    "     to generate documentation. Use mcp-cli to interact with them.",
                ),
                (
                    "Spec-Driven Mode",
                    '/spec "your task" → For new features with planning and verification',
                ),
                (
                    "Quick Mode",
                    "Just chat → For bug fixes and small changes without a spec",
                ),
            ]
        )

        ui.rule()
        ui.print()
        ui.print("  [bold yellow]⭐ Star this repo:[/bold yellow] https://github.com/maxritter/claude-codepro")
        ui.print()

        ui.print("  [bold white]📜 License:[/bold white] Free for individuals, freelancers & open source (AGPL-3.0)")
        ui.print(
            "             Companies with proprietary software require a [bold yellow]commercial license[/bold yellow]."
        )
        ui.print("             Contact: [cyan]mail@maxritter.net[/cyan]")
        ui.print()
        ui.print("  [dim]💝 Enjoying Claude CodePro? Consider sponsoring: https://github.com/sponsors/maxritter[/dim]")
        ui.print()
        ui.print(f"  [dim]Installed version: {__version__}[/dim]")
        ui.print()

    def rollback(self, ctx: InstallContext) -> None:
        """Finalize has no rollback (informational only)."""
        pass
