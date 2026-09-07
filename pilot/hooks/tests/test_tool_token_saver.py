"""Tests for tool_token_saver hook."""

from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from tool_token_saver import _rewrite_command, run_tool_token_saver


class TestRewriteCommand:
    @patch("tool_token_saver.subprocess.run")
    def test_accepts_rewrite_when_rtk_exits_nonzero_with_output(self, mock_run):
        """rtk rewrite exits 3 on success — hook must accept non-empty stdout regardless of exit code."""
        mock_run.return_value = MagicMock(
            returncode=3,
            stdout="rtk git status\n",
            stderr="",
        )
        result = _rewrite_command("git status")
        assert result == "rtk git status"

    @patch("tool_token_saver.subprocess.run")
    def test_returns_none_when_rtk_produces_no_output(self, mock_run):
        """No stdout means no rewrite available, regardless of exit code."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="",
        )
        assert _rewrite_command("echo hi") is None

    @patch("tool_token_saver.subprocess.run")
    def test_returns_none_when_rewrite_equals_original(self, mock_run):
        """If rtk echoes back the same command, there's no savings."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="echo hi\n",
            stderr="",
        )
        assert _rewrite_command("echo hi") is None

    @patch("tool_token_saver.subprocess.run")
    def test_accepts_rewrite_on_exit_zero(self, mock_run):
        """Normal exit 0 with output still works."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="rtk ls\n",
            stderr="",
        )
        assert _rewrite_command("ls") == "rtk ls"

    @patch("tool_token_saver.subprocess.run")
    def test_returns_none_on_timeout(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="rtk", timeout=5)
        assert _rewrite_command("git status") is None

    @patch("tool_token_saver.subprocess.run")
    def test_returns_none_on_os_error(self, mock_run):
        mock_run.side_effect = OSError("not found")
        assert _rewrite_command("git status") is None


@pytest.mark.parametrize("platform", ["claude", "codex"])
def test_rewrite_preserves_agent_permission_contract(platform, capsys, monkeypatch):
    monkeypatch.setenv("CLAUDE_PROJECT_PLATFORM", platform)
    payload = {"tool_input": {"command": "git push origin dev", "timeout": 10}}

    with (
        patch("tool_token_saver.sys.stdin", io.StringIO(json.dumps(payload))),
        patch("tool_token_saver.shutil.which", return_value="/usr/local/bin/rtk"),
        patch("tool_token_saver._get_rtk_version", return_value=(0, 23, 0)),
        patch("tool_token_saver._rewrite_command", return_value="rtk git push origin dev"),
    ):
        assert run_tool_token_saver() == 0

    output = json.loads(capsys.readouterr().out)
    hook_output = output["hookSpecificOutput"]
    assert hook_output["updatedInput"] == {"command": "rtk git push origin dev", "timeout": 10}
    if platform == "codex":
        assert hook_output["permissionDecision"] == "allow"
    else:
        assert "permissionDecision" not in hook_output
    assert "permissionDecisionReason" not in hook_output


def test_missing_rtk_is_silent(capsys):
    payload = {"tool_input": {"command": "git status"}}
    with (
        patch("tool_token_saver.sys.stdin", io.StringIO(json.dumps(payload))),
        patch("tool_token_saver.shutil.which", return_value=None),
    ):
        assert run_tool_token_saver() == 0

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


@pytest.mark.parametrize(
    ("payload_fields", "environment", "expected"),
    [
        ({"turn_id": "turn-1", "session_id": "codex-1"}, {}, "allow"),
        ({"session_id": "codex-1"}, {"CODEX_THREAD_ID": "codex-1"}, "allow"),
        ({"session_id": "codex-1"}, {"CODEX_SESSION_ID": "codex-1"}, "allow"),
        (
            {"session_id": "claude-1"},
            {"CODEX_THREAD_ID": "parent-codex", "CLAUDE_PROJECT_PLATFORM": "claude"},
            "claude",
        ),
        ({"session_id": "claude-1"}, {"CODEX_THREAD_ID": "parent-codex"}, "silent"),
        ({}, {}, "silent"),
    ],
)
def test_native_payload_without_platform_marker(payload_fields, environment, expected, capsys, monkeypatch):
    for name in ("CLAUDE_PROJECT_PLATFORM", "CODEX_THREAD_ID", "CODEX_SESSION_ID"):
        monkeypatch.delenv(name, raising=False)
    for name, value in environment.items():
        monkeypatch.setenv(name, value)
    payload = {"tool_name": "Bash", "tool_input": {"command": "git status", "timeout": 1000}, **payload_fields}
    with (
        patch("tool_token_saver.sys.stdin", io.StringIO(json.dumps(payload))),
        patch("tool_token_saver.shutil.which", return_value="/usr/local/bin/rtk"),
        patch("tool_token_saver._get_rtk_version", return_value=(0, 23, 0)),
        patch("tool_token_saver._rewrite_command", return_value="rtk git status"),
    ):
        assert run_tool_token_saver() == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    if expected == "silent":
        assert captured.out == ""
        return
    output = json.loads(captured.out)["hookSpecificOutput"]
    assert output["updatedInput"] == {"command": "rtk git status", "timeout": 1000}
    if expected == "allow":
        assert output["permissionDecision"] == "allow"
    else:
        assert "permissionDecision" not in output
