"""Finalize step - runs final cleanup tasks and displays success."""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from pathlib import Path

from installer import __version__
from installer.claude_paths import get_claude_app_config_path, get_claude_config_dir
from installer.console_settings import get_console_display, get_worker_port
from installer.context import InstallContext
from installer.steps.base import BaseStep
from installer.ui import Console


def _get_pilot_version() -> str:
    """Get version from Pilot binary, fallback to installer version."""
    pilot_path = Path.home() / ".pilot" / "bin" / "pilot"
    if pilot_path.exists():
        try:
            result = subprocess.run(
                [str(pilot_path), "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                match = re.search(r" v(\S+)$", result.stdout.strip())
                if match:
                    return match.group(1)
        except Exception:
            pass
    return __version__


def _get_active_trial_days() -> int | None:
    """Return remaining trial days when on an active trial, else None.

    Lets the success panel reinforce that an in-product trial is running and how
    long is left. Returns None for paid/expired/no-license states or any error.
    """
    pilot_path = Path.home() / ".pilot" / "bin" / "pilot"
    if not pilot_path.exists():
        return None
    try:
        result = subprocess.run(
            [str(pilot_path), "trial", "--check", "--json"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return None
        data = json.loads(result.stdout.strip())
        if data.get("license_state") == "active" and data.get("tier") == "trial":
            days = data.get("days_remaining")
            return int(days) if days is not None else None
    except (subprocess.SubprocessError, json.JSONDecodeError, OSError, ValueError):
        pass
    return None


class FinalizeStep(BaseStep):
    """Step that runs final cleanup tasks and displays success panel."""

    name = "finalize"

    def check(self, ctx: InstallContext) -> bool:
        """Always returns False - finalize always runs."""
        return False

    def run(self, ctx: InstallContext) -> None:
        """Run final cleanup tasks and display success."""
        self._kill_stale_worker()
        self._record_claude_profile()
        self._report_claude_profile(ctx.ui)
        self._display_success(ctx)

    @staticmethod
    def _record_claude_profile() -> None:
        """Record the Claude config dir this install targeted, for the drift guard.

        Read only by pilot/hooks/config_dir_guard.py to detect a later session
        served by a different profile. NEVER consulted to resolve a path -
        resolution stays ambient-env-only.
        """
        try:
            claude_dir = get_claude_config_dir()
        except ValueError:
            # Invalid CLAUDE_CONFIG_DIR: the install itself will have failed
            # earlier. Nothing meaningful to record.
            return
        try:
            record = Path.home() / ".pilot" / "state" / "last-claude-config-dir"
            record.parent.mkdir(parents=True, exist_ok=True)
            record.write_text(str(claude_dir), encoding="utf-8")
        except OSError:
            pass

    @staticmethod
    def _report_claude_profile(ui: Console | None) -> None:
        """State which Claude profile was written when it is not the default.

        The session-start drift guard cannot fire in a directory that has no Pilot
        install, so this report is the primary protection against installing into
        a profile the user did not intend. Silent on the default profile - that is
        the documented behaviour and needs no narration.
        """
        if not ui or ui.quiet or not os.environ.get("CLAUDE_CONFIG_DIR"):
            return
        try:
            claude_dir = get_claude_config_dir()
            app_config = get_claude_app_config_path()
        except ValueError:
            return

        ui.print()
        ui.print("  [bold]Claude config directory[/bold] (from CLAUDE_CONFIG_DIR):")
        ui.print(f"    Config dir: {claude_dir}")
        ui.print(f"    App config: {app_config}")
        ui.print(f"    Your default {Path.home() / '.claude'} was not modified.")
        ui.print("    Launch with the same variable set:")
        ui.print(f"      CLAUDE_CONFIG_DIR={claude_dir} claude")

    @staticmethod
    def _kill_stale_worker() -> None:
        """Kill the process listening on the Console port so the worker restarts."""
        try:
            result = subprocess.run(
                ["lsof", "-ti", f":{get_worker_port()}", "-sTCP:LISTEN"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            pids = result.stdout.strip()
            if pids:
                for pid in pids.splitlines():
                    p = pid.strip()
                    if not re.fullmatch(r"\d+", p):
                        continue
                    # SIGTERM first for graceful shutdown
                    subprocess.run(["kill", p], capture_output=True, timeout=5)
                    time.sleep(1)
                    # SIGKILL only if still alive
                    alive = subprocess.run(["kill", "-0", p], capture_output=True, timeout=2)
                    if alive.returncode == 0:
                        subprocess.run(["kill", "-9", p], capture_output=True, timeout=5)
        except Exception:
            pass

    def _display_success(self, ctx: InstallContext) -> None:
        """Display success panel with next steps."""
        ui = ctx.ui

        if not ui:
            return

        if ui.quiet:
            ui.print(f"  [green]✓[/green] Update complete (v{_get_pilot_version()})")
            return

        getting_started: list[tuple[str, str]] = []

        if ctx.config.get("shell_needs_reload"):
            modified = ctx.config.get("modified_shell_configs", [])
            reload_cmds = []
            for f in modified:
                if ".zshrc" in f:
                    reload_cmds.append("source ~/.zshrc")
                elif ".bashrc" in f:
                    reload_cmds.append("source ~/.bashrc")
                elif "fish" in f:
                    reload_cmds.append("source ~/.config/fish/config.fish")

            if reload_cmds:
                cmd_str = " or ".join(reload_cmds)
                getting_started.append(("Reload shell", f"{cmd_str} (or restart terminal)"))

        getting_started.extend(
            [
                ("Start", "claude or codex"),
                (
                    "Setup (optional)",
                    "/setup-rules (Claude) · $setup-rules (Codex)",
                ),
                ("Console", f"http://{get_console_display()}"),
                ("Docs", "https://pilot-shell.com/docs"),
                ("Update", "pilot update"),
            ]
        )

        ui.next_steps([("Next steps", getting_started)])

        if not ui.quiet:
            ui.rule()
            ui.print()
            trial_days = _get_active_trial_days()
            if trial_days is not None:
                ui.print(
                    f"  [bold cyan]✦ Free trial active:[/bold cyan] {trial_days} days remaining "
                    "[muted](shown in the statusline & Console)[/muted]"
                )
                ui.print("  [muted]Subscribe anytime: [/muted][cyan]https://pilot-shell.com/pricing[/cyan]")
                ui.print()
            ui.print("  [bold yellow]⭐ Star this repo:[/bold yellow] https://github.com/maxritter/pilot-shell")
            ui.print()
            ui.print(f"  [muted]Installed version: {_get_pilot_version()}[/muted]")
            ui.print()
