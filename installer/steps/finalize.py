"""Finalize step - runs final cleanup tasks and displays success."""

from __future__ import annotations

import shutil
import subprocess
import sys
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
        self._build_rules(ctx)

        self._install_statusline_config(ctx)

        self._display_success(ctx)

    def _build_rules(self, ctx: InstallContext) -> None:
        """Build rules using build.py script."""
        build_script = ctx.project_dir / ".claude" / "rules" / "build.py"
        ui = ctx.ui

        if not build_script.exists():
            if ui:
                ui.warning("build.py not found, skipping rules build")
            return

        if ui:
            ui.section("Building Rules")
            ui.status("Running rules build script...")

        python_commands = [
            ["uv", "run", "python", str(build_script)],
            [sys.executable, str(build_script)],
            ["python3", str(build_script)],
        ]

        for cmd in python_commands:
            try:
                if cmd[0] == "uv" and shutil.which("uv") is None:
                    continue

                subprocess.run(
                    cmd,
                    check=True,
                    capture_output=True,
                    cwd=ctx.project_dir,
                )
                if ui:
                    ui.success("Rules built successfully")
                return
            except subprocess.CalledProcessError:
                continue
            except FileNotFoundError:
                continue

        if ui:
            ui.error("Failed to build rules")
            ui.warning("You may need to run 'uv run python .claude/rules/build.py' manually")

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
                "MCP configuration",
            ]
        )

        if ctx.install_python:
            installed_items.append("Python development tools")

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
                (
                    "Configure settings",
                    "Run: /config and set:\n"
                    "     • Auto-compact = false\n"
                    "     • Verbose output = true\n"
                    "     • Respect .gitignore in file picker = false\n"
                    "     • Auto-connect to IDE (external terminal) = true",
                ),
                ("Verify MCP servers", "Run: /mcp → If any fail, click on the server and select 'Reconnect'"),
                ("Connect IDE", "Run: /ide → Enables real-time diagnostics"),
                ("Initialize project", "Run: /setup → Scans and indexes codebase"),
                ("Start building!", "/plan → /implement → /verify"),
            ]
        )

        ui.rule()
        ui.print()
        ui.print("  [bold yellow]⭐ Star this repo:[/bold yellow] https://github.com/maxritter/claude-codepro")
        ui.print("  [bold magenta]💎 Premium Features:[/bold magenta] https://www.claude-code.pro")
        ui.print("  [bold cyan]🐛 Bugs, Features, PRs:[/bold cyan] https://github.com/maxritter/claude-codepro/issues")
        ui.print()
        ui.print(f"  [dim]Installed version: {__version__}[/dim]")
        ui.print()

    def rollback(self, ctx: InstallContext) -> None:
        """Finalize has no rollback (informational only)."""
        pass
