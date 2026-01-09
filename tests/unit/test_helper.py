"""Unit tests for helper context monitoring and wrapper communication."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


class TestContextPercentage:
    """Tests for context percentage calculation."""

    def test_get_context_percentage_returns_float(self, tmp_path: Path) -> None:
        """get_context_percentage returns a float percentage."""
        from scripts.helper import get_context_percentage

        # Create mock session file with usage data
        session_id = "test-session-123"
        history_file = tmp_path / ".claude" / "history.jsonl"
        history_file.parent.mkdir(parents=True)
        history_file.write_text(json.dumps({"sessionId": session_id}) + "\n")

        projects_dir = tmp_path / ".claude" / "projects" / "test-project"
        projects_dir.mkdir(parents=True)
        session_file = projects_dir / f"{session_id}.jsonl"

        # Write assistant message with usage data (100k tokens = 50%)
        usage_data = {
            "type": "assistant",
            "message": {
                "usage": {
                    "input_tokens": 50000,
                    "cache_creation_input_tokens": 25000,
                    "cache_read_input_tokens": 25000,
                }
            },
        }
        session_file.write_text(json.dumps(usage_data) + "\n")

        with patch.object(Path, "home", return_value=tmp_path):
            percentage = get_context_percentage()

        assert isinstance(percentage, float)
        assert 49.0 <= percentage <= 51.0  # ~50%

    def test_get_context_percentage_returns_zero_on_missing_session(
        self, tmp_path: Path
    ) -> None:
        """get_context_percentage returns 0 when session file missing."""
        from scripts.helper import get_context_percentage

        with patch.object(Path, "home", return_value=tmp_path):
            percentage = get_context_percentage()

        assert percentage == 0.0


class TestCheckContext:
    """Tests for check_context function."""

    def test_check_context_returns_ok_below_threshold(self, tmp_path: Path) -> None:
        """check_context returns 'OK' when below threshold."""
        from scripts.helper import check_context

        # Mock 50% usage
        with patch("scripts.helper.get_context_percentage", return_value=50.0):
            result = check_context(threshold=95)

        assert result == "OK"

    def test_check_context_returns_clear_needed_above_threshold(
        self, tmp_path: Path
    ) -> None:
        """check_context returns 'CLEAR_NEEDED' when above threshold."""
        from scripts.helper import check_context

        # Mock 96% usage
        with patch("scripts.helper.get_context_percentage", return_value=96.0):
            result = check_context(threshold=95)

        assert result == "CLEAR_NEEDED"

    def test_check_context_uses_default_threshold(self) -> None:
        """check_context uses 90% as default threshold."""
        from scripts.helper import check_context

        with patch("scripts.helper.get_context_percentage", return_value=89.0):
            result = check_context()

        assert result == "OK"

        with patch("scripts.helper.get_context_percentage", return_value=90.0):
            result = check_context()

        assert result == "CLEAR_NEEDED"


class TestSendClear:
    """Tests for send_clear function."""

    def test_send_clear_writes_to_pipe(self, tmp_path: Path) -> None:
        """send_clear writes command to WRAPPER_PIPE."""
        from scripts.helper import send_clear

        pipe_path = tmp_path / "test.pipe"
        os.mkfifo(pipe_path)

        # Read from pipe in separate process to avoid blocking
        import threading

        received = []

        def read_pipe() -> None:
            with open(pipe_path) as f:
                received.append(f.read())

        reader = threading.Thread(target=read_pipe)
        reader.start()

        # Give reader time to start
        import time

        time.sleep(0.1)

        with patch.dict(os.environ, {"WRAPPER_PIPE": str(pipe_path)}):
            result = send_clear()

        reader.join(timeout=1)

        assert result is True
        assert "clear\n" in received[0]

    def test_send_clear_with_plan_path(self, tmp_path: Path) -> None:
        """send_clear sends clear-continue with plan path."""
        from scripts.helper import send_clear

        pipe_path = tmp_path / "test.pipe"
        os.mkfifo(pipe_path)

        import threading

        received = []

        def read_pipe() -> None:
            with open(pipe_path) as f:
                received.append(f.read())

        reader = threading.Thread(target=read_pipe)
        reader.start()

        import time

        time.sleep(0.1)

        with patch.dict(os.environ, {"WRAPPER_PIPE": str(pipe_path)}):
            result = send_clear(plan_path="docs/plans/test.md")

        reader.join(timeout=1)

        assert result is True
        assert "clear-continue docs/plans/test.md\n" in received[0]

    def test_send_clear_returns_false_without_pipe(self) -> None:
        """send_clear returns False when WRAPPER_PIPE not set."""
        from scripts.helper import send_clear

        with patch.dict(os.environ, {}, clear=True):
            # Remove WRAPPER_PIPE if it exists
            os.environ.pop("WRAPPER_PIPE", None)
            result = send_clear()

        assert result is False

    def test_send_clear_returns_false_when_pipe_missing(self, tmp_path: Path) -> None:
        """send_clear returns False when pipe file doesn't exist."""
        from scripts.helper import send_clear

        with patch.dict(os.environ, {"WRAPPER_PIPE": str(tmp_path / "nonexistent.pipe")}):
            result = send_clear()

        assert result is False


class TestCLI:
    """Tests for CLI interface."""

    def test_cli_check_context_output(self) -> None:
        """CLI check-context prints OK or CLEAR_NEEDED."""
        from scripts.helper import cli_check_context

        with patch("scripts.helper.get_context_percentage", return_value=50.0):
            result = cli_check_context(json_output=False)

        assert result == "OK"

    def test_cli_check_context_json_output(self) -> None:
        """CLI check-context --json prints JSON."""
        from scripts.helper import cli_check_context

        with patch("scripts.helper.get_context_percentage", return_value=50.0):
            result = cli_check_context(json_output=True)

        data = json.loads(result)
        assert data["status"] == "OK"
        assert data["percentage"] == 50.0
