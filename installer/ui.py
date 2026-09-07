"""UI abstraction layer - Rich wrapper with simple input prompts."""

from __future__ import annotations

import os
import sys
from contextlib import contextmanager
from typing import Any, Iterator, TextIO

from rich.console import Console as RichConsole
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.rule import Rule
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

PILOT_THEME = Theme(
    {
        "info": "cyan",
        "success": "green",
        "warning": "yellow",
        "error": "red bold",
        "step": "bold magenta",
        "highlight": "bold cyan",
        "muted": "bright_black",
    }
)


class ProgressTask:
    """Wrapper for Rich progress task."""

    def __init__(self, progress: Progress, task_id: TaskID):
        self._progress = progress
        self._task_id = task_id

    def advance(self, amount: int = 1) -> None:
        """Advance the progress bar."""
        self._progress.advance(self._task_id, advance=amount)

    def update(self, completed: int) -> None:
        """Update the progress to a specific value."""
        self._progress.update(self._task_id, completed=completed)


def _get_tty_input() -> TextIO:
    """Get a file handle for TTY input, even when stdin is piped.

    When running via 'curl | bash', stdin is consumed by the pipe.
    This function opens /dev/tty directly to get interactive input.
    Falls back to sys.stdin if /dev/tty is not available.
    """
    if sys.stdin.isatty():
        return sys.stdin

    try:
        return open("/dev/tty", "r")
    except OSError:
        return sys.stdin


def _get_trial_time_str(days: int | None, expires_at: str | None) -> str:
    """Get human-readable time remaining for trial."""
    if days is not None and days > 0:
        return f"{days}d"
    if days == 0 and expires_at:
        from datetime import datetime, timezone

        try:
            expires_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            remaining = expires_dt - datetime.now(timezone.utc)
            hours = int(remaining.total_seconds() // 3600)
            return f"{hours}h" if hours > 0 else "<1h"
        except (ValueError, AttributeError):
            pass
    return "<1d" if days == 0 else "trial"


class Console:
    """Console wrapper for Rich with simple input prompts."""

    def __init__(self, non_interactive: bool = False, quiet: bool = False):
        self._console = RichConsole(theme=PILOT_THEME)
        self._non_interactive = non_interactive
        self._quiet = quiet
        self._current_step = 0
        self._total_steps = 0
        self._tty: TextIO | None = None

    def _get_input_stream(self) -> TextIO:
        """Get the input stream for interactive prompts."""
        if self._tty is None:
            self._tty = _get_tty_input()
        return self._tty

    @property
    def non_interactive(self) -> bool:
        """Check if running in non-interactive mode."""
        return self._non_interactive

    @property
    def quiet(self) -> bool:
        """Check if running in quiet mode (minimal output)."""
        return self._quiet

    def banner(self, license_info: dict[str, Any] | None = None) -> None:
        """Print the Pilot Shell banner with feature highlights.

        Args:
            license_info: Current license info dict (tier, email, etc.) or None if not yet checked.
        """
        if self._quiet:
            return

        if self._console.width >= 90:
            logo = """
[bold blue]  ██████╗ ██╗██╗      ██████╗ ████████╗    ███████╗██╗  ██╗███████╗██╗     ██╗     [/bold blue]
[bold blue]  ██╔══██╗██║██║     ██╔═══██╗╚══██╔══╝    ██╔════╝██║  ██║██╔════╝██║     ██║     [/bold blue]
[bold blue]  ██████╔╝██║██║     ██║   ██║   ██║       ███████╗███████║█████╗  ██║     ██║     [/bold blue]
[bold blue]  ██╔═══╝ ██║██║     ██║   ██║   ██║       ╚════██║██╔══██║██╔══╝  ██║     ██║     [/bold blue]
[bold blue]  ██║     ██║███████╗╚██████╔╝   ██║       ███████║██║  ██║███████╗███████╗███████╗[/bold blue]
[bold blue]  ╚═╝     ╚═╝╚══════╝ ╚═════╝    ╚═╝       ╚══════╝╚═╝  ╚═╝╚══════╝╚══════╝╚══════╝[/bold blue]
"""
            self._console.print(logo)
        else:
            self._console.print()
            self._console.print("  [bold blue]✦ PILOT SHELL[/bold blue]")
            self._console.print()

        tagline = Text()
        tagline.append("  ✈ ", style="cyan")
        tagline.append("How real engineers run Claude Code and Codex", style="bold")
        self._console.print(tagline)
        self._console.print(
            "    Professional context and harness engineering around the coding agents you already use.",
            style="muted",
        )
        self._console.print("    Persistent knowledge. Enforced quality. Runtime proof.", style="muted")
        self._console.print()

        tier = license_info.get("tier") if license_info else None

        if tier in ("solo", "team"):
            tier_map = {"solo": "Solo", "team": "Team"}
            tier_display = tier_map.get(tier, tier.title())
            email = license_info.get("email", "") if license_info else ""
            license_text = Text()
            license_text.append("  ✓ ", style="green")
            license_text.append(f"{tier_display} License", style="bold green")
            if email:
                license_text.append(f" — {email}", style="muted")
            self._console.print(license_text)
        elif tier == "trial":
            days = license_info.get("days_remaining") if license_info else None
            is_expired = license_info.get("is_expired", False) if license_info else False
            if is_expired:
                license_text = Text()
                license_text.append("  ⚠ ", style="red")
                license_text.append("Trial Expired", style="bold red")
                license_text.append(" — Get a license: ", style="muted")
                license_text.append("https://pilot-shell.com/pricing", style="cyan")
                self._console.print(license_text)
                self._console.print()
            elif days is not None and days <= 3:
                expires_at = license_info.get("expires_at") if license_info else None
                time_str = _get_trial_time_str(days, expires_at)
                license_text = Text()
                license_text.append("  ⏳ ", style="yellow")
                license_text.append(f"Trial ({time_str} remaining)", style="bold yellow")
                self._console.print(license_text)
                self._console.print()

    def set_total_steps(self, total: int) -> None:
        """Set total number of installation steps."""
        self._total_steps = total
        self._current_step = 0

    def step(self, name: str) -> None:
        """Print a step indicator with progress."""
        self._current_step += 1
        if self._quiet:
            self._console.print(f"  [{self._current_step}/{self._total_steps}] {name}...")
            return
        step_text = Text()
        step_text.append(f"[{self._current_step}/{self._total_steps}] ", style="bold magenta")
        step_text.append(name, style="bold")
        self._console.print()
        self._console.print(Rule(step_text, style="magenta"))

    def status(self, message: str) -> None:
        """Print a status message in cyan with arrow.

        Emitted even in quiet mode: quiet suppresses decorative chrome (banner,
        step rules, next-steps panel), not line-level progress and problems.
        """
        self._console.print(f"  [cyan]→[/cyan] {message}")

    def success(self, message: str) -> None:
        """Print a success message in green with checkmark.

        Emitted even in quiet mode (see status() for the quiet-mode contract).
        """
        self._console.print(f"  [green]✓[/green] [green]{message}[/green]")

    def warning(self, message: str) -> None:
        """Print a warning message in yellow with warning symbol.

        Emitted even in quiet mode so recoverable problems during `pilot update`
        (e.g. a "could not install X" package skip) are never silently swallowed.
        Fatal failures use error(), which is never suppressed. See status() for
        the quiet-mode contract.
        """
        self._console.print(f"  [yellow]⚠[/yellow] [yellow]{message}[/yellow]")

    def error(self, message: str) -> None:
        """Print an error message in red with X symbol."""
        self._console.print(f"  [red bold]✗[/red bold] [red]{message}[/red]")

    def info(self, message: str) -> None:
        """Print an info message with info icon.

        Emitted even in quiet mode (see status() for the quiet-mode contract).
        """
        self._console.print(f"  [muted]ℹ[/muted] [muted]{message}[/muted]")

    def next_steps(self, sections: list[tuple[str, list[tuple[str, str]]]]) -> None:
        """Print a styled next steps guide with named sections.

        Args:
            sections: List of (section_title, items) where items are (title, description) tuples.
        """
        if self._quiet:
            return

        step_num = 1
        for section_title, items in sections:
            self._console.print()
            self._console.print(f"  [bold]{section_title}[/bold]")
            self._console.print()
            table = Table.grid(padding=(0, 2))
            table.add_column(no_wrap=True)
            table.add_column(style="muted")
            for title, description in items:
                table.add_row(
                    f"  [bold magenta]{step_num}.[/bold magenta] [bold]{title}[/bold]",
                    description,
                )
                step_num += 1
            self._console.print(table)
            self._console.print()

    @contextmanager
    def progress(self, total: int, description: str = "Processing") -> Iterator[ProgressTask]:
        """Context manager for progress bar display with time tracking."""
        with Progress(
            SpinnerColumn("dots"),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(bar_width=None, style="cyan", complete_style="green"),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("•"),
            TimeElapsedColumn(),
            TextColumn("•"),
            TimeRemainingColumn(),
            console=self._console,
            transient=True,
        ) as progress:
            task_id = progress.add_task(description, total=total)
            yield ProgressTask(progress, task_id)

    @contextmanager
    def spinner(self, message: str) -> Iterator[None]:
        """Context manager for a simple spinner."""
        with self._console.status(f"[cyan]{message}[/cyan]", spinner="dots"):
            yield

    def input(self, message: str, default: str = "") -> str:
        """Prompt for text input."""
        if self._non_interactive:
            return default

        self._console.print()
        prompt = f"  [bold cyan]?[/bold cyan] {message}"
        if default:
            prompt += f" [{default}]"
        prompt += ": "
        self._console.print(prompt, end="")

        try:
            if sys.stdin.isatty():
                # Normal terminals (and debugpy/IDE integrated terminals that keep
                # stdin a TTY): the builtin handles line editing and CR/LF for us.
                response = input().strip()
            else:
                # stdin is not a TTY -- either 'curl | bash' (stdin is the script
                # pipe) or a proxied stdin (e.g. the VSCode/debugpy launcher). Read
                # the controlling terminal directly, accepting CR, LF or CRLF as the
                # line terminator so Enter submits even without ICRNL translation.
                response = self._read_interactive_line().strip()
        except (EOFError, KeyboardInterrupt, OSError):
            self._console.print()
            return default

        return response if response else default

    def _read_interactive_line(self) -> str:
        """Read one line from the controlling terminal, byte by byte.

        A plain readline() in text mode holds a trailing CR pending (universal-
        newline CR/CRLF disambiguation), so a lone '\\r' -- which is what Enter
        produces under the VSCode/debugpy launcher's terminal (no ICRNL CR->NL
        translation) -- never returns and the raw CR echoes as '^M'. Reading raw
        bytes and stopping on the first CR or LF avoids that.
        """
        stream = self._get_input_stream()
        fd = stream.fileno()
        buf = bytearray()
        while True:
            chunk = os.read(fd, 1)
            if not chunk or chunk in (b"\n", b"\r"):  # EOF or end of line
                break
            buf += chunk
        return buf.decode("utf-8", "replace")

    def print(self, message: str = "") -> None:
        """Print a plain message."""
        self._console.print(message)

    def rule(self, title: str = "", style: str = "muted") -> None:
        """Print a horizontal rule."""
        self._console.print(Rule(title, style=style))
