"""UI abstraction layer - Rich wrapper with simple input prompts."""

from __future__ import annotations

import getpass
import os
import sys
from contextlib import contextmanager
from typing import Any, Iterator, TextIO

from rich.console import Console as RichConsole
from rich.panel import Panel
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

CCP_THEME = Theme(
    {
        "info": "cyan",
        "success": "green",
        "warning": "yellow",
        "error": "red bold",
        "step": "bold magenta",
        "highlight": "bold cyan",
        "dim": "dim white",
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


class Console:
    """Console wrapper for Rich with simple input prompts."""

    def __init__(self, non_interactive: bool = False):
        self._console = RichConsole(theme=CCP_THEME)
        self._non_interactive = non_interactive
        self._current_step = 0
        self._total_steps = 0
        self._tty: TextIO | None = None

    def _get_input_stream(self) -> TextIO:
        """Get the input stream for interactive prompts."""
        if self._tty is None:
            self._tty = _get_tty_input()
        return self._tty

    def close(self) -> None:
        """Close TTY handle if opened."""
        if self._tty is not None and self._tty is not sys.stdin:
            self._tty.close()
            self._tty = None

    @property
    def non_interactive(self) -> bool:
        """Check if running in non-interactive mode."""
        return self._non_interactive

    def banner(self) -> None:
        """Print the Claude CodePro banner with feature highlights."""
        logo = """
[bold cyan]   _____ _                 _          _____          _      _____
  / ____| |               | |        / ____|        | |    |  __ \\
 | |    | | __ _ _   _  __| | ___   | |     ___   __| | ___| |__) | __ ___
 | |    | |/ _` | | | |/ _` |/ _ \\  | |    / _ \\ / _` |/ _ \\  ___/ '__/ _ \\
 | |____| | (_| | |_| | (_| |  __/  | |___| (_) | (_| |  __/ |   | | | (_) |
  \\_____|_|\\__,_|\\__,_|\\__,_|\\___|   \\_____\\___/ \\__,_|\\___|_|   |_|  \\___/[/bold cyan]
"""
        self._console.print(logo)

        tagline = Text()
        tagline.append("  ✨ ", style="yellow")
        tagline.append("Professional Development Environment for Claude Code", style="bold white")
        tagline.append(" ✨", style="yellow")
        self._console.print(tagline)
        self._console.print()

        features = Text()
        features.append("  ♾️  ", style="yellow")
        features.append("Endless Mode", style="bold green")
        features.append(" — Unlimited context across sessions, zero manual intervention\n", style="white")
        features.append("  📋 ", style="yellow")
        features.append("Two Development Modes", style="bold green")
        features.append(" — /spec for planning, Quick Mode for fast fixes\n", style="white")
        features.append("  💡 ", style="yellow")
        features.append("Modular Rules System", style="bold green")
        features.append(" — Standards + custom rules loaded as project memory\n", style="white")
        features.append("  🛠️ ", style="yellow")
        features.append("Quality Hooks", style="bold green")
        features.append(" — TDD enforcer, linting, type checking, context monitor\n", style="white")
        features.append("  🔌 ", style="yellow")
        features.append("Enhanced Capabilities", style="bold green")
        features.append(" — Vexor, Context7, Firecrawl, LSP servers", style="white")

        panel = Panel(
            features,
            border_style="cyan",
            padding=(1, 2),
            title="[bold white]What You're Getting[/bold white]",
            title_align="left",
        )
        self._console.print(panel)
        self._console.print()

    def set_total_steps(self, total: int) -> None:
        """Set total number of installation steps."""
        self._total_steps = total
        self._current_step = 0

    def step(self, name: str) -> None:
        """Print a step indicator with progress."""
        self._current_step += 1
        step_text = Text()
        step_text.append(f"[{self._current_step}/{self._total_steps}] ", style="bold magenta")
        step_text.append(name, style="bold white")
        self._console.print()
        self._console.print(Rule(step_text, style="magenta"))

    def status(self, message: str) -> None:
        """Print a status message in cyan with arrow."""
        self._console.print(f"  [cyan]→[/cyan] {message}")

    def success(self, message: str) -> None:
        """Print a success message in green with checkmark."""
        self._console.print(f"  [green]✓[/green] [green]{message}[/green]")

    def warning(self, message: str) -> None:
        """Print a warning message in yellow with warning symbol."""
        self._console.print(f"  [yellow]⚠[/yellow] [yellow]{message}[/yellow]")

    def error(self, message: str) -> None:
        """Print an error message in red with X symbol."""
        self._console.print(f"  [red bold]✗[/red bold] [red]{message}[/red]")

    def info(self, message: str) -> None:
        """Print an info message with info icon."""
        self._console.print(f"  [dim]ℹ[/dim] [dim]{message}[/dim]")

    def section(self, title: str) -> None:
        """Print a section header with styled panel."""
        self._console.print()
        panel = Panel(
            Text(title, style="bold white", justify="center"),
            border_style="blue",
            padding=(0, 2),
            expand=False,
        )
        self._console.print(panel)
        self._console.print()

    def box(self, content: str, title: str | None = None, style: str = "cyan") -> None:
        """Print content in a styled box."""
        panel = Panel(
            content,
            title=title,
            title_align="left",
            border_style=style,
            padding=(1, 2),
        )
        self._console.print(panel)

    def success_box(self, title: str, items: list[str]) -> None:
        """Print a success summary box with checkmarks."""
        content = "\n".join(f"[green]✓[/green] {item}" for item in items)
        panel = Panel(
            content,
            title=f"[bold green]✨ {title}[/bold green]",
            title_align="left",
            border_style="green",
            padding=(1, 2),
        )
        self._console.print()
        self._console.print(panel)

    def error_box(self, title: str, items: list[str]) -> None:
        """Print an error summary box."""
        content = "\n".join(f"[red]✗[/red] {item}" for item in items)
        panel = Panel(
            content,
            title=f"[bold red]❌ {title}[/bold red]",
            title_align="left",
            border_style="red",
            padding=(1, 2),
        )
        self._console.print()
        self._console.print(panel)

    def next_steps(self, steps: list[tuple[str, str]]) -> None:
        """Print a styled next steps guide."""
        self._console.print()
        self._console.print(Rule("[bold cyan]📋 Next Steps[/bold cyan]", style="cyan"))
        self._console.print()

        for i, (title, description) in enumerate(steps, 1):
            self._console.print(f"  [bold magenta]{i}.[/bold magenta] [bold]{title}[/bold]")
            self._console.print(f"     [dim]{description}[/dim]")
            self._console.print()

    @contextmanager
    def progress(self, total: int, description: str = "Processing") -> Iterator[ProgressTask]:
        """Context manager for progress bar display with time tracking."""
        with Progress(
            SpinnerColumn("dots"),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(bar_width=40, style="cyan", complete_style="green"),
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

    def table(self, data: list[dict[str, Any]], title: str | None = None) -> None:
        """Print a styled table with the given data."""
        if not data:
            return

        table = Table(
            title=title,
            title_style="bold cyan",
            border_style="dim",
            header_style="bold magenta",
            row_styles=["", "dim"],
        )

        for key in data[0].keys():
            table.add_column(key.replace("_", " ").title())

        for row in data:
            table.add_row(*[str(v) for v in row.values()])

        self._console.print()
        self._console.print(table)
        self._console.print()

    def checklist(self, title: str, items: list[tuple[str, bool]]) -> None:
        """Print a checklist with pass/fail indicators."""
        self._console.print()
        self._console.print(f"[bold]{title}[/bold]")
        self._console.print()

        for item, passed in items:
            icon = "[green]✓[/green]" if passed else "[red]✗[/red]"
            status = "[green]PASS[/green]" if passed else "[red]FAIL[/red]"
            self._console.print(f"  {icon} {item} [{status}]")

    def confirm(self, message: str, default: bool = True) -> bool:
        """Prompt for yes/no confirmation."""
        if self._non_interactive:
            return default

        default_str = "Y/n" if default else "y/N"
        self._console.print()
        self._console.print(f"  [bold cyan]?[/bold cyan] {message} \\[{default_str}]: ", end="")

        try:
            tty = self._get_input_stream()
            response = tty.readline().strip().lower()
        except (EOFError, KeyboardInterrupt, OSError):
            self._console.print()
            return default

        if not response:
            return default
        return response in ("y", "yes", "true", "1")

    def select(self, message: str, choices: list[str]) -> str:
        """Prompt for single selection from choices."""
        if self._non_interactive:
            return choices[0] if choices else ""

        self._console.print()
        self._console.print(f"  [bold cyan]?[/bold cyan] {message}")
        for i, choice in enumerate(choices, 1):
            self._console.print(f"    [bold magenta]{i}.[/bold magenta] {choice}")
        self._console.print(f"  Enter choice [1-{len(choices)}]: ", end="")

        try:
            tty = self._get_input_stream()
            response = tty.readline().strip()
        except (EOFError, KeyboardInterrupt, OSError):
            self._console.print()
            return choices[0] if choices else ""

        try:
            idx = int(response) - 1
            if 0 <= idx < len(choices):
                return choices[idx]
        except ValueError:
            pass

        return choices[0] if choices else ""

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
            tty = self._get_input_stream()
            response = tty.readline().strip()
        except (EOFError, KeyboardInterrupt, OSError):
            self._console.print()
            return default

        return response if response else default

    def password(self, message: str) -> str:
        """Prompt for hidden password input."""
        if self._non_interactive:
            return ""

        self._console.print()
        self._console.print(f"  [bold cyan]?[/bold cyan] {message}: ", end="")

        try:
            tty = self._get_input_stream()
            return getpass.getpass(prompt="", stream=tty)
        except (EOFError, KeyboardInterrupt, OSError):
            self._console.print()
            return ""

    def print(self, message: str = "") -> None:
        """Print a plain message."""
        self._console.print(message)

    def rule(self, title: str = "", style: str = "dim") -> None:
        """Print a horizontal rule."""
        self._console.print(Rule(title, style=style))

    def newline(self, count: int = 1) -> None:
        """Print one or more newlines."""
        for _ in range(count):
            self._console.print()
