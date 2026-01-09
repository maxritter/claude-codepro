"""Unit tests for Claude wrapper with pipe-based control."""

from __future__ import annotations

import stat
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock


class TestClaudeWrapper:
    """Tests for ClaudeWrapper class."""

    def test_wrapper_creates_pipe_directory(self, tmp_path: Path) -> None:
        """Wrapper creates pipe directory if it doesn't exist."""
        from scripts.wrapper import ClaudeWrapper

        pipe_dir = tmp_path / "pipes"
        wrapper = ClaudeWrapper(claude_args=[], pipe_dir=pipe_dir)

        assert pipe_dir.exists()

    def test_wrapper_creates_named_pipe(self, tmp_path: Path) -> None:
        """Wrapper creates a named pipe file."""
        from scripts.wrapper import ClaudeWrapper

        pipe_dir = tmp_path / "pipes"
        wrapper = ClaudeWrapper(claude_args=[], pipe_dir=pipe_dir)
        wrapper._create_pipe()

        assert wrapper.pipe_path.exists()
        assert stat.S_ISFIFO(wrapper.pipe_path.stat().st_mode)

    def test_wrapper_exports_pipe_env_var(self, tmp_path: Path) -> None:
        """Wrapper sets WRAPPER_PIPE environment variable."""
        from scripts.wrapper import ClaudeWrapper

        pipe_dir = tmp_path / "pipes"
        wrapper = ClaudeWrapper(claude_args=[], pipe_dir=pipe_dir)
        wrapper._create_pipe()
        env = wrapper._get_claude_env()

        assert "WRAPPER_PIPE" in env
        assert env["WRAPPER_PIPE"] == str(wrapper.pipe_path)

    def test_wrapper_cleanup_removes_pipe(self, tmp_path: Path) -> None:
        """Wrapper cleans up pipe on exit."""
        from scripts.wrapper import ClaudeWrapper

        pipe_dir = tmp_path / "pipes"
        wrapper = ClaudeWrapper(claude_args=[], pipe_dir=pipe_dir)
        wrapper._create_pipe()
        pipe_path = wrapper.pipe_path

        assert pipe_path.exists()
        wrapper._cleanup()
        assert not pipe_path.exists()

    def test_handle_clear_command(self, tmp_path: Path) -> None:
        """Wrapper handles 'clear' command by setting restart flags."""
        from scripts.wrapper import ClaudeWrapper

        pipe_dir = tmp_path / "pipes"
        wrapper = ClaudeWrapper(claude_args=[], pipe_dir=pipe_dir)
        wrapper._create_pipe()

        # Mock _kill_claude to prevent it from doing anything
        wrapper._kill_claude = MagicMock()

        wrapper._handle_command("clear")

        # Supervisor pattern: flags are set, kill is called
        assert wrapper._restart_pending is True
        assert wrapper._restart_prompt is None
        wrapper._kill_claude.assert_called_once()

    def test_handle_clear_continue_command(self, tmp_path: Path) -> None:
        """Wrapper handles 'clear-continue <plan>' command by setting restart flags."""
        from scripts.wrapper import ClaudeWrapper

        pipe_dir = tmp_path / "pipes"
        wrapper = ClaudeWrapper(claude_args=[], pipe_dir=pipe_dir)
        wrapper._create_pipe()

        wrapper._kill_claude = MagicMock()

        wrapper._handle_command("clear-continue docs/plans/test.md")

        # Supervisor pattern: flags are set with prompt, kill is called
        assert wrapper._restart_pending is True
        assert wrapper._restart_prompt == "/spec --continue docs/plans/test.md"
        wrapper._kill_claude.assert_called_once()

    def test_handle_exit_command(self, tmp_path: Path) -> None:
        """Wrapper handles 'exit' command by setting shutdown flag."""
        from scripts.wrapper import ClaudeWrapper

        pipe_dir = tmp_path / "pipes"
        wrapper = ClaudeWrapper(claude_args=[], pipe_dir=pipe_dir)
        wrapper._create_pipe()
        wrapper._kill_claude = MagicMock()

        wrapper._handle_command("exit")

        # Supervisor pattern: shutdown flag is set, kill is called
        assert wrapper._shutdown_requested is True
        wrapper._kill_claude.assert_called_once()

    def test_wrapper_passes_args_to_claude(self, tmp_path: Path) -> None:
        """Wrapper passes arguments to claude command."""
        from scripts.wrapper import ClaudeWrapper

        pipe_dir = tmp_path / "pipes"
        wrapper = ClaudeWrapper(
            claude_args=["--model", "opus", "--verbose"], pipe_dir=pipe_dir
        )

        assert wrapper.claude_args == ["--model", "opus", "--verbose"]


class TestWrapperIntegration:
    """Integration tests for wrapper functionality."""

    def test_pipe_receives_commands(self, tmp_path: Path) -> None:
        """Test that pipe can receive and process commands."""
        from scripts.wrapper import ClaudeWrapper

        pipe_dir = tmp_path / "pipes"
        wrapper = ClaudeWrapper(claude_args=[], pipe_dir=pipe_dir)
        wrapper._create_pipe()
        wrapper._kill_claude = MagicMock()

        # Write command to pipe in a separate thread
        def write_to_pipe() -> None:
            time.sleep(0.1)
            with open(wrapper.pipe_path, "w") as f:
                f.write("clear\n")

        write_thread = threading.Thread(target=write_to_pipe)
        write_thread.start()

        # Read one command from pipe
        wrapper._read_pipe_command()

        write_thread.join()
        # Command was processed: restart flag set, kill called
        assert wrapper._restart_pending is True
        wrapper._kill_claude.assert_called_once()
