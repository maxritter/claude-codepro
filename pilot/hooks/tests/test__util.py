"""Tests for _util.py — model config, JSON helpers, session paths, and shared utilities."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from _lib.util import (
    BLUE,
    CYAN,
    FILE_LENGTH_CRITICAL,
    FILE_LENGTH_WARN,
    GREEN,
    MAGENTA,
    NC,
    RED,
    YELLOW,
    _sessions_base,
    current_project_root,
    find_git_root,
    get_edited_file_from_stdin,
    get_session_cache_path,
    get_session_plan_path,
    is_waiting_for_user_input,
    read_hook_stdin,
)


class TestClaudeConfigDir:
    """Tests for claude_config_dir().

    Hooks may not import launcher/ or installer/, so this resolver is a third
    copy of the same rule. Unlike those two it must NEVER raise - a hook that
    throws breaks the user's session - so a set-but-invalid value returns None
    and callers skip their config-dir work entirely.
    """

    def test_unset_returns_home_claude(self, monkeypatch, tmp_path: Path) -> None:
        from _lib.util import claude_config_dir

        monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))

        assert claude_config_dir() == tmp_path / ".claude"

    def test_absolute_value_is_used(self, monkeypatch, tmp_path: Path) -> None:
        from _lib.util import claude_config_dir

        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / ".claude_work"))

        assert claude_config_dir() == tmp_path / ".claude_work"

    def test_relative_returns_none_not_default(self, monkeypatch, tmp_path: Path) -> None:
        """Must NOT fall back to ~/.claude - that is the profile being protected."""
        from _lib.util import claude_config_dir

        monkeypatch.setenv("CLAUDE_CONFIG_DIR", "relative/path")
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))

        assert claude_config_dir() is None

    def test_empty_returns_none(self, monkeypatch, tmp_path: Path) -> None:
        from _lib.util import claude_config_dir

        monkeypatch.setenv("CLAUDE_CONFIG_DIR", "   ")
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))

        assert claude_config_dir() is None


class TestPilotOwnedSkillNamesDefault:
    """The default argument must follow CLAUDE_CONFIG_DIR, not hardcode ~/.claude."""

    def test_default_uses_custom_config_dir(self, monkeypatch, tmp_path: Path) -> None:
        from _lib.util import pilot_owned_skill_names

        custom = tmp_path / ".claude_work"
        custom.mkdir()
        (custom / ".pilot-manifest.json").write_text(
            json.dumps({"files": ["skills/spec/manifest.json"]}), encoding="utf-8"
        )
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(custom))
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))

        assert pilot_owned_skill_names() == {"spec"}

    def test_default_returns_empty_on_invalid_dir(self, monkeypatch, tmp_path: Path) -> None:
        """Invalid value means "touch nothing", never "read the personal profile"."""
        from _lib.util import pilot_owned_skill_names

        claude = tmp_path / ".claude"
        claude.mkdir()
        (claude / ".pilot-manifest.json").write_text(
            json.dumps({"files": ["skills/spec/manifest.json"]}), encoding="utf-8"
        )
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", "relative/path")
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))

        assert pilot_owned_skill_names() == set()


class TestGetMaxContextTokens:
    """Tests for _get_max_context_tokens()."""

    @patch.dict("os.environ", {}, clear=True)
    def test_returns_200k_without_cache(self) -> None:
        from _lib.util import _get_max_context_tokens

        result = _get_max_context_tokens()

        assert result == 200_000

    def test_returns_1m_with_cache(self, tmp_path: Path) -> None:
        from _lib.util import _get_max_context_tokens

        session_id = "test-session-ctx"
        cache_dir = tmp_path / ".pilot" / "sessions" / session_id
        cache_dir.mkdir(parents=True)
        cache_file = cache_dir / "context-pct.json"
        cache_file.write_text(json.dumps({"context_window_size": 1_000_000}))

        with (
            patch("pathlib.Path.home", return_value=tmp_path),
            patch.dict("os.environ", {"PILOT_SESSION_ID": session_id}),
        ):
            result = _get_max_context_tokens()

        assert result == 1_000_000

    @patch.dict("os.environ", {}, clear=True)
    def test_returns_200k_when_no_session_id(self) -> None:
        from _lib.util import _get_max_context_tokens

        result = _get_max_context_tokens()

        assert result == 200_000


class TestGetCompactionThresholdPct:
    """Tests for _get_compaction_threshold_pct()."""

    @patch.dict("os.environ", {}, clear=True)
    def test_returns_83_5_for_200k_default(self) -> None:
        from _lib.util import _get_compaction_threshold_pct

        result = _get_compaction_threshold_pct()

        assert abs(result - 83.5) < 0.1

    def test_returns_96_7_for_1m_cache(self, tmp_path: Path) -> None:
        from _lib.util import _get_compaction_threshold_pct

        session_id = "test-session-compact"
        cache_dir = tmp_path / ".pilot" / "sessions" / session_id
        cache_dir.mkdir(parents=True)
        cache_file = cache_dir / "context-pct.json"
        cache_file.write_text(json.dumps({"context_window_size": 1_000_000}))

        with (
            patch("pathlib.Path.home", return_value=tmp_path),
            patch.dict("os.environ", {"PILOT_SESSION_ID": session_id}),
        ):
            result = _get_compaction_threshold_pct()

        assert abs(result - 96.7) < 0.1


class TestJsonHelpers:
    """Tests for JSON response helper functions."""

    def test_post_tool_use_context(self) -> None:
        from _lib.util import post_tool_use_context

        result = json.loads(post_tool_use_context("Context at 80%"))
        assert result == {
            "continue": True,
            "suppressOutput": True,
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": "Context at 80%",
            },
        }

    def test_pre_tool_use_context(self) -> None:
        from _lib.util import pre_tool_use_context

        result = json.loads(pre_tool_use_context("Try Semble first"))
        assert result == {
            "continue": True,
            "suppressOutput": True,
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": "Try Semble first",
            },
        }

    def test_stop_block(self) -> None:
        from _lib.util import stop_block

        result = json.loads(stop_block("Spec workflow in progress"))
        assert result == {"decision": "block", "reason": "Spec workflow in progress"}

    def test_helpers_handle_special_chars(self) -> None:
        from _lib.util import post_tool_use_context

        msg = 'File "test.py" has\nnewlines & "quotes"'
        result = json.loads(post_tool_use_context(msg))
        assert result["hookSpecificOutput"]["additionalContext"] == msg


class TestCheckFileLength:
    """Tests for check_file_length returning string."""

    def test_returns_empty_for_normal_file(self, tmp_path: Path) -> None:
        from _lib.util import check_file_length

        f = tmp_path / "small.py"
        f.write_text("\n".join(f"line {i}" for i in range(100)))
        assert check_file_length(f) == ""

    def test_returns_warning_for_long_file(self, tmp_path: Path) -> None:
        from _lib.util import check_file_length

        f = tmp_path / "growing.py"
        f.write_text("\n".join(f"line {i}" for i in range(850)))
        result = check_file_length(f)
        assert "growing.py" in result
        assert "850" in result
        assert "800" in result

    def test_returns_critical_for_very_long_file(self, tmp_path: Path) -> None:
        from _lib.util import check_file_length

        f = tmp_path / "huge.py"
        f.write_text("\n".join(f"line {i}" for i in range(1050)))
        result = check_file_length(f)
        assert "huge.py" in result
        assert "1050" in result
        assert "1000" in result

    def test_returns_empty_for_nonexistent_file(self, tmp_path: Path) -> None:
        from _lib.util import check_file_length

        result = check_file_length(tmp_path / "nope.py")
        assert result == ""

    def test_no_ansi_codes_in_output(self, tmp_path: Path) -> None:
        from _lib.util import check_file_length

        f = tmp_path / "big.py"
        f.write_text("\n".join(f"line {i}" for i in range(1050)))
        result = check_file_length(f)
        assert "\033[" not in result


class TestColorConstants:
    """Color constants are defined and non-empty."""

    def test_all_colors_defined(self):
        assert RED
        assert YELLOW
        assert GREEN
        assert CYAN
        assert BLUE
        assert MAGENTA
        assert NC


class TestFileLengthConstants:
    """File length constants have expected values."""

    def test_warn_threshold(self):
        assert FILE_LENGTH_WARN == 800

    def test_critical_threshold(self):
        assert FILE_LENGTH_CRITICAL == 1000


class TestSessionsBase:
    """Tests for _sessions_base()."""

    def test_returns_path_under_home(self):
        base = _sessions_base()
        assert isinstance(base, Path)
        assert base == Path.home() / ".pilot" / "sessions"


class TestResolveSessionId:
    """Tests for resolve_session_id() — agent-native fallback chain (the #157 root)."""

    def test_prefers_agent_native_id_over_wrapper(self):
        from _lib.util import resolve_session_id

        with patch.dict(
            "os.environ",
            {"PILOT_SESSION_ID": "wrap-1", "CLAUDE_CODE_SESSION_ID": "claude-2", "CODEX_THREAD_ID": "codex-3"},
            clear=True,
        ):
            assert resolve_session_id() == "claude-2"

    def test_falls_back_to_claude_code_session_id(self):
        from _lib.util import resolve_session_id

        with patch.dict("os.environ", {"CLAUDE_CODE_SESSION_ID": "claude-2", "CODEX_THREAD_ID": "codex-3"}, clear=True):
            assert resolve_session_id() == "claude-2"

    def test_falls_back_to_codex_thread_id(self):
        from _lib.util import resolve_session_id

        with patch.dict("os.environ", {"CODEX_THREAD_ID": "codex-3"}, clear=True):
            assert resolve_session_id() == "codex-3"

    def test_defaults_when_all_unset(self):
        from _lib.util import resolve_session_id

        with patch.dict("os.environ", {}, clear=True):
            assert resolve_session_id() == "default"

    def test_payload_fallback_used_when_env_chain_empty(self):
        from _lib.util import resolve_session_id

        with patch.dict("os.environ", {}, clear=True):
            assert resolve_session_id("payload-uuid-1") == "payload-uuid-1"

    def test_unsafe_payload_fallback_rejected(self):
        """The payload session_id feeds directly into ~/.pilot/sessions/<id> path
        construction, and session_clear DELETES under that path - a traversal
        value must never become a path component (Codex review finding)."""
        from _lib.util import resolve_session_id

        with patch.dict("os.environ", {}, clear=True):
            assert resolve_session_id("../other-session") == "default"
            assert resolve_session_id("/etc") == "default"
            assert resolve_session_id("a/b") == "default"
            assert resolve_session_id("..") == "default"
            assert resolve_session_id(".") == "default"

    def test_non_string_payload_fallback_rejected(self):
        from _lib.util import resolve_session_id

        with patch.dict("os.environ", {}, clear=True):
            assert resolve_session_id(123) == "default"
            assert resolve_session_id(["session"]) == "default"

    def test_payload_first_resolver_sanitizes_before_overriding_environment(self):
        from _lib.util import resolve_payload_session_id

        with patch.dict("os.environ", {"PILOT_SESSION_ID": "env-session"}, clear=True):
            assert resolve_payload_session_id("payload-session") == "payload-session"
            assert resolve_payload_session_id("../victim") == "env-session"
            assert resolve_payload_session_id("/tmp/victim") == "env-session"
            assert resolve_payload_session_id(123) == "env-session"

    def test_hook_resolver_uses_payload_over_stale_native_parent_id(self):
        from _lib.util import resolve_hook_session_id

        with patch.dict("os.environ", {"CODEX_THREAD_ID": "parent-thread"}, clear=True):
            assert resolve_hook_session_id("active-hook-thread") == "active-hook-thread"

        with patch.dict("os.environ", {"CLAUDE_CODE_SESSION_ID": "active-hook-thread"}, clear=True):
            assert resolve_hook_session_id("active-hook-thread") == "active-hook-thread"

    def test_hook_resolver_preserves_legacy_wrapper_identity(self):
        from _lib.util import resolve_hook_session_id

        with patch.dict("os.environ", {"PILOT_SESSION_ID": "wrapper-session"}, clear=True):
            assert resolve_hook_session_id("native-payload") == "wrapper-session"
            assert resolve_hook_session_id("../unsafe") == "wrapper-session"


class TestGetSessionCachePath:
    """Tests for get_session_cache_path()."""

    @patch.dict("os.environ", {"PILOT_SESSION_ID": "test-session-123"})
    def test_with_session_id(self):
        path = get_session_cache_path()
        assert isinstance(path, Path)
        assert "test-session-123" in str(path)
        assert path.name == "context-cache.json"

    @patch.dict("os.environ", {"CLAUDE_CODE_SESSION_ID": "claude-cache-1"}, clear=True)
    def test_falls_back_to_claude_session_id(self):
        """Reader path must key on the same agent-native id the writer uses, so an
        IDE/desktop session (no PILOT_SESSION_ID) is isolated rather than sharing 'default'."""
        path = get_session_cache_path()
        assert "claude-cache-1" in str(path)
        assert "default" not in str(path)

    @patch.dict("os.environ", {}, clear=True)
    def test_defaults_to_default(self):
        path = get_session_cache_path()
        assert isinstance(path, Path)
        assert "default" in str(path)


class TestGetSessionPlanPath:
    """Tests for get_session_plan_path()."""

    @patch.dict("os.environ", {"PILOT_SESSION_ID": "test-session-456"})
    def test_returns_session_scoped_plan_path(self):
        path = get_session_plan_path()
        assert isinstance(path, Path)
        assert "test-session-456" in str(path)
        assert path.name == "active_plan.json"

    @patch.dict("os.environ", {"CLAUDE_CODE_SESSION_ID": "claude-plan-1"}, clear=True)
    def test_falls_back_to_claude_session_id(self):
        """active_plan.json must key on the agent-native id (matching the launcher
        register_plan writer) so a foreign session's plan never lands in 'default'."""
        path = get_session_plan_path()
        assert "claude-plan-1" in str(path)
        assert "default" not in str(path)


class TestFindGitRoot:
    """Tests for find_git_root()."""

    @patch("subprocess.run")
    def test_returns_root_when_in_repo(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="/home/user/repo\n")
        result = find_git_root()
        assert result == Path("/home/user/repo")

    @patch("subprocess.run")
    def test_returns_none_when_not_in_repo(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        result = find_git_root()
        assert result is None

    @patch("subprocess.run", side_effect=Exception("Git not found"))
    def test_handles_exception(self, mock_run):
        result = find_git_root()
        assert result is None


class TestCurrentProjectRoot:
    """Tests for current_project_root() authoritative-source resolution."""

    @patch("subprocess.run")
    def test_returns_claude_project_root_env(self, mock_run):
        with patch.dict("os.environ", {"CLAUDE_PROJECT_ROOT": "/work/proj"}, clear=True):
            assert current_project_root() == Path("/work/proj")
        mock_run.assert_not_called()

    @patch("_lib.util.find_git_root", return_value=Path("/work/repo"))
    def test_returns_git_toplevel_when_env_unset(self, _mock_git):
        with patch.dict("os.environ", {}, clear=True):
            assert current_project_root() == Path("/work/repo")

    @patch("_lib.util.find_git_root", return_value=None)
    def test_returns_none_when_no_authoritative_source(self, _mock_git):
        """Degraded env (no CLAUDE_PROJECT_ROOT, git unavailable): must NOT fall back
        to cwd. cwd is not an authoritative containment boundary — a hook run from a
        subdirectory would wrongly reject a legitimate same-project plan. Returning
        None makes plan_in_current_project fail open instead."""
        with patch.dict("os.environ", {}, clear=True):
            assert current_project_root() is None

    @patch("_lib.util.find_git_root", return_value=None)
    def test_guard_fails_open_under_degraded_root(self, _mock_git):
        """The reported regression: with no authoritative root, an absolute plan under
        the real project root (but outside the hook's cwd subdirectory) must NOT be
        suppressed — plan_in_current_project fails open."""
        from _lib.util import plan_in_current_project

        plan_under_real_root = Path("/work/proj/docs/plans/2026-05-31-own.md")
        with patch.dict("os.environ", {}, clear=True):
            assert plan_in_current_project(plan_under_real_root) is True


class TestReadHookStdin:
    """Tests for read_hook_stdin()."""

    def test_parses_valid_json(self, monkeypatch):
        test_data = {"tool_name": "Write", "tool_input": {"file_path": "test.py"}}
        monkeypatch.setattr("sys.stdin", MagicMock(read=lambda: json.dumps(test_data)))
        result = read_hook_stdin()
        assert result == test_data

    def test_returns_empty_dict_on_invalid_json(self, monkeypatch):
        monkeypatch.setattr("sys.stdin", MagicMock(read=lambda: "not json"))
        result = read_hook_stdin()
        assert result == {}

    def test_returns_empty_dict_on_empty_input(self, monkeypatch):
        monkeypatch.setattr("sys.stdin", MagicMock(read=lambda: ""))
        result = read_hook_stdin()
        assert result == {}


class TestGetEditedFileFromStdin:
    """Tests for get_edited_file_from_stdin()."""

    def test_extracts_file_path(self, monkeypatch):
        test_data = {"tool_input": {"file_path": "/path/to/file.py"}}
        with patch("select.select") as mock_select:
            mock_select.return_value = ([sys.stdin], [], [])
            monkeypatch.setattr("sys.stdin", MagicMock(read=lambda: json.dumps(test_data)))
            with patch("json.load", return_value=test_data):
                result = get_edited_file_from_stdin()
                assert result == Path("/path/to/file.py")

    def test_returns_none_without_file_path(self, monkeypatch):
        test_data = {"tool_input": {}}
        with patch("select.select") as mock_select:
            mock_select.return_value = ([sys.stdin], [], [])
            with patch("json.load", return_value=test_data):
                result = get_edited_file_from_stdin()
                assert result is None

    def test_returns_none_when_stdin_empty(self, monkeypatch):
        with patch("select.select") as mock_select:
            mock_select.return_value = ([], [], [])
            result = get_edited_file_from_stdin()
            assert result is None


class TestIsWaitingForUserInput:
    """Tests for is_waiting_for_user_input()."""

    def test_returns_true_when_last_tool_is_ask_user_question(self, tmp_path):
        transcript = tmp_path / "transcript.jsonl"
        msg = {
            "type": "assistant",
            "message": {"content": [{"type": "tool_use", "name": "AskUserQuestion", "input": {}}]},
        }
        transcript.write_text(json.dumps(msg) + "\n")
        assert is_waiting_for_user_input(str(transcript)) is True

    def test_returns_false_when_last_tool_is_not_ask(self, tmp_path):
        transcript = tmp_path / "transcript.jsonl"
        msg = {
            "type": "assistant",
            "message": {"content": [{"type": "tool_use", "name": "Write", "input": {}}]},
        }
        transcript.write_text(json.dumps(msg) + "\n")
        assert is_waiting_for_user_input(str(transcript)) is False

    def test_returns_false_for_missing_file(self):
        assert is_waiting_for_user_input("/nonexistent/transcript.jsonl") is False

    def test_returns_false_for_empty_transcript(self, tmp_path):
        transcript = tmp_path / "transcript.jsonl"
        transcript.write_text("")
        assert is_waiting_for_user_input(str(transcript)) is False

    def test_uses_last_assistant_message(self, tmp_path):
        transcript = tmp_path / "transcript.jsonl"
        ask_msg = {
            "type": "assistant",
            "message": {"content": [{"type": "tool_use", "name": "AskUserQuestion", "input": {}}]},
        }
        write_msg = {
            "type": "assistant",
            "message": {"content": [{"type": "tool_use", "name": "Write", "input": {}}]},
        }
        lines = [json.dumps(ask_msg), json.dumps(write_msg)]
        transcript.write_text("\n".join(lines) + "\n")
        assert is_waiting_for_user_input(str(transcript)) is False


class TestActivePlanHelpers:
    """Unit tests for active-plan helpers that remain after the v12 model rework.

    The orchestrator-aware window resolution (and its supporting model
    resolver) was deleted with config schema v12 — per-skill model selection
    is no longer stored in ~/.pilot/config.json. The remaining `_infer_active_skill`
    helper is still consumed by spec_stop_guard and notify, so it is tested here.
    """

    def test_infer_active_skill_maps_phases(self) -> None:
        from _lib.util import _infer_active_skill

        assert _infer_active_skill("PENDING", False, "Feature") == "spec-plan"
        assert _infer_active_skill("PENDING", False, "Bugfix") == "spec-bugfix-plan"
        assert _infer_active_skill("PENDING", True, "Feature") == "spec-implement"
        assert _infer_active_skill("PENDING", True, "Bugfix") == "spec-implement"
        assert _infer_active_skill("COMPLETE", True, "Feature") == "spec-verify"
        assert _infer_active_skill("COMPLETE", True, "Bugfix") == "spec-bugfix-verify"
        assert _infer_active_skill("VERIFIED", True, "Feature") is None
        assert _infer_active_skill("", False, "Feature") is None

    # `_resolve_orchestrator_window` was deleted with the v12 model-rework —
    # per-skill orchestrator-window scaling no longer exists, and
    # `context_monitor.py` now relies on the live statusline `context_window_size`
    # alone. Nothing to test here anymore.


class TestPlanRegisteredByOtherSession:
    """Ownership lookup for the planning guard's fallback.

    Fails CLOSED on ambiguity: an unparseable sibling registration returns True,
    because treating it as "nobody owns this" would let the fallback accept a file
    a sibling probably owned -- the exact cross-session cross-talk being fixed.
    """

    def _sessions(self, tmp_path, monkeypatch):
        import _lib.util as util

        base = tmp_path / "sessions"
        base.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(util, "_sessions_base", lambda: base)
        return base

    def _register(self, base, session_id, plan, *, raw=None):
        session_dir = base / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        target = session_dir / "active_plan.json"
        target.write_text(raw if raw is not None else json.dumps({"plan_path": str(plan), "status": "PENDING"}))

    def test_true_for_a_plan_another_session_owns(self, tmp_path, monkeypatch):
        from _lib.util import plan_registered_by_other_session

        base = self._sessions(tmp_path, monkeypatch)
        plan = tmp_path / "plan.md"
        plan.write_text("x")
        self._register(base, "session-a", plan)

        assert plan_registered_by_other_session(plan, "session-b") is True

    def test_false_for_the_callers_own_registration(self, tmp_path, monkeypatch):
        from _lib.util import plan_registered_by_other_session

        base = self._sessions(tmp_path, monkeypatch)
        plan = tmp_path / "plan.md"
        plan.write_text("x")
        self._register(base, "session-b", plan)

        assert plan_registered_by_other_session(plan, "session-b") is False

    def test_false_when_no_session_registered_it(self, tmp_path, monkeypatch):
        from _lib.util import plan_registered_by_other_session

        base = self._sessions(tmp_path, monkeypatch)
        other = tmp_path / "other.md"
        other.write_text("x")
        self._register(base, "session-a", other)

        plan = tmp_path / "plan.md"
        plan.write_text("x")
        assert plan_registered_by_other_session(plan, "session-b") is False

    def test_finds_a_lane_registration(self, tmp_path, monkeypatch):
        from _lib.util import plan_registered_by_other_session

        base = self._sessions(tmp_path, monkeypatch)
        plan = tmp_path / "plan.md"
        plan.write_text("x")
        lane_dir = base / "session-a" / "lanes" / "alpha"
        lane_dir.mkdir(parents=True)
        (lane_dir / "active_plan.json").write_text(json.dumps({"plan_path": str(plan), "status": "PENDING"}))

        assert plan_registered_by_other_session(plan, "session-b") is True

    def test_truncated_sibling_state_fails_closed(self, tmp_path, monkeypatch):
        """A torn write must block, not be skipped."""
        from _lib.util import plan_registered_by_other_session

        base = self._sessions(tmp_path, monkeypatch)
        plan = tmp_path / "plan.md"
        plan.write_text("x")
        self._register(base, "session-a", plan, raw='{"plan_path": "/half')

        assert plan_registered_by_other_session(plan, "session-b") is True

    def test_does_not_raise_on_unreadable_sibling_state(self, tmp_path, monkeypatch):
        from _lib.util import plan_registered_by_other_session

        base = self._sessions(tmp_path, monkeypatch)
        plan = tmp_path / "plan.md"
        plan.write_text("x")
        self._register(base, "session-a", plan, raw="not json at all")

        assert plan_registered_by_other_session(plan, "session-b") is True
