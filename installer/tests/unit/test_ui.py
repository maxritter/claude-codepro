"""Tests for installer UI abstraction layer."""

from __future__ import annotations

import re

# Rich honours FORCE_COLOR/CLICOLOR_FORCE, so captured output carries SGR escapes on
# any developer machine that sets them (Claude Code, most modern terminals) and is bare
# in CI. These assertions are about layout, not colour, so compare what the user reads.
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")


def _visible(text: str) -> str:
    """Return `text` with ANSI escape sequences removed."""
    return _ANSI_RE.sub("", text)


class TestConsole:
    """Test Console wrapper class."""

    def test_console_status_outputs_blue_text(self):
        """Console.status should output styled message."""
        from installer.ui import Console

        console = Console()
        # Should not raise
        console.status("Installing...")

    def test_console_success_outputs_green_checkmark(self):
        """Console.success should output green checkmark message."""
        from installer.ui import Console

        console = Console()
        console.success("Installed successfully")

    def test_console_warning_outputs_yellow_warning(self):
        """Console.warning should output yellow warning message."""
        from installer.ui import Console

        console = Console()
        console.warning("This might cause issues")

    def test_console_error_outputs_red_error(self):
        """Console.error should output red error message."""
        from installer.ui import Console

        console = Console()
        console.error("Installation failed")

    def test_console_progress_context_manager(self):
        """Console.progress should return a context manager."""
        from installer.ui import Console

        console = Console()
        with console.progress(total=10, description="Downloading") as progress:
            progress.advance(5)
            progress.advance(5)


class TestConsoleQuietMode:
    """Quiet mode (used only by `pilot update`) must still surface progress.

    Regression: quiet mode early-returned from status/success/warning/info, so the
    long Dependencies step emitted only its `[N/M]` header for minutes and failed
    installs were silently swallowed - the update looked frozen. Quiet means
    "suppress decorative chrome", not "hide line-level progress and problems".
    """

    def test_quiet_mode_surfaces_progress_status_and_failures(self):
        """In quiet mode, success/status/warning/info still emit their message."""
        from installer.ui import Console

        console = Console(non_interactive=True, quiet=True)

        def capture(fn, message):
            with console._console.capture() as out:
                fn(message)
            return _visible(out.get())

        assert "Semble installed" in capture(console.success, "Semble installed")
        assert "Initializing CodeGraph" in capture(console.status, "Initializing CodeGraph...")
        assert "Could not install playwright-cli" in capture(console.warning, "Could not install playwright-cli")
        assert "network timeout" in capture(console.info, "  Error: network timeout")

    def test_quiet_mode_still_suppresses_decorative_chrome(self):
        """Quiet keeps the compact step format and drops the next-steps panel."""
        from installer.ui import Console

        console = Console(non_interactive=True, quiet=True)
        console.set_total_steps(8)

        with console._console.capture() as out:
            console.step("Dependencies")
        step_output = _visible(out.get())
        assert "[1/8] Dependencies" in step_output  # compact, not a Rule banner
        assert "─" not in step_output

        with console._console.capture() as out:
            console.next_steps([("Getting Started", [("Start", "run claude")])])
        assert out.get() == ""  # decorative panel stays suppressed


class TestConsoleNonInteractive:
    """Test Console in non-interactive mode."""

    def test_input_returns_default_in_non_interactive(self):
        """In non-interactive mode, input returns default."""
        from installer.ui import Console

        console = Console(non_interactive=True)
        result = console.input("Enter value:", default="default_value")
        assert result == "default_value"

    def test_next_steps_keeps_each_action_on_one_line_at_80_columns(self):
        from installer.ui import Console

        console = Console(non_interactive=True)
        console._console.width = 80
        items = [
            ("Start", "claude or codex"),
            ("Setup (optional)", "/setup-rules (Claude) · $setup-rules (Codex)"),
            ("Console", "http://localhost:41777"),
            ("Docs", "https://pilot-shell.com/docs"),
            ("Update", "pilot update"),
        ]
        with console._console.capture() as out:
            console.next_steps([("Next steps", items)])
        lines = [line for line in _visible(out.get()).splitlines() if line.strip()]
        assert len(lines) == 6
        assert lines[0].strip() == "Next steps"
        for line, (title, description) in zip(lines[1:], items, strict=True):
            assert title in line and description in line


class TestConsoleInteractiveInput:
    """Console.input() reading from the controlling terminal (non-TTY stdin)."""

    def test_input_submits_when_enter_is_bare_carriage_return(self, monkeypatch):
        """Enter delivered as a lone CR (no LF) must submit the line.

        Regression (6283848b): the readline()-based prompt held a trailing CR
        pending (universal-newline CR/CRLF disambiguation), so under the VSCode/
        debugpy launcher Enter ('\\r') never returned -- the user saw '^M' and
        input hung. Keeping the write end open simulates a real terminal that
        does not send EOF; the read must still complete on the bare CR.
        """
        import os
        import sys
        import threading

        from installer.ui import Console

        class _FakeStdin:
            def isatty(self) -> bool:
                return False

        monkeypatch.setattr(sys, "stdin", _FakeStdin())

        read_fd, write_fd = os.pipe()
        os.write(write_fd, b"LICENSE-KEY-XYZ\r")

        console = Console()
        monkeypatch.setattr(console, "_get_input_stream", lambda: os.fdopen(read_fd, "r"))

        result: dict[str, str] = {}

        def _read() -> None:
            result["value"] = console.input("Enter your license key")

        worker = threading.Thread(target=_read, daemon=True)
        worker.start()
        worker.join(timeout=5.0)

        try:
            assert not worker.is_alive(), "input() hung waiting for a newline after a bare CR"
            assert result["value"] == "LICENSE-KEY-XYZ"
        finally:
            os.close(write_fd)  # unblock any hung reader so the daemon thread can exit
