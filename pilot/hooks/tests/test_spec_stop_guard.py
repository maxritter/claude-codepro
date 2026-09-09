"""Tests for spec_stop_guard hook — blocks session stop during active /spec workflows.

Notifications were removed from the stop guard — spec skills now handle
all notifications via `pilot notify`. The stop guard only blocks/allows stops.
"""

from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from spec_stop_guard import CLAUDE_CODE_CONSECUTIVE_BLOCK_CAP, MAX_CHAIN_BLOCKS, main

HOOK_PATH = Path(__file__).resolve().parent.parent / "spec_stop_guard.py"
TEST_SESSION_ID = "test-spec-stop-guard"


def test_unapproved_plan_continuation_requires_approval_before_implementation(tmp_path):
    from spec_stop_guard import _block_reason

    plan = tmp_path / "plan.md"
    plan.write_text("# Plan\n\nStatus: PENDING\nApproved: No\nType: Feature\n")
    reason = _block_reason(plan, "PENDING")

    assert "approval" in reason.lower()
    assert "next pending task" not in reason
    assert "implementation" in reason.lower()
    assert "VERY NEXT action must be a tool call" not in reason


def _test_session_dir() -> Path:
    """Get the session directory for the test session."""
    return Path.home() / ".pilot" / "sessions" / TEST_SESSION_ID


def _register_plan_for_session(plan_path: Path, status: str = "PENDING") -> None:
    """Register a plan in active_plan.json for the test session."""
    session_dir = _test_session_dir()
    session_dir.mkdir(parents=True, exist_ok=True)
    active_plan_json = session_dir / "active_plan.json"
    active_plan_json.write_text(json.dumps({"plan_path": str(plan_path), "status": status}))


@pytest.fixture(autouse=True)
def clear_session_state(tmp_path_factory, monkeypatch):
    """Give each test its own HOME, then clear session state inside it.

    The guard resolves all of its state through ``Path.home()/.pilot/sessions``
    (`_lib.util._sessions_base`), evaluated at call time, so pointing ``HOME`` at
    a per-test temp dir isolates both the in-process ``main()`` calls and the
    ``_run_subprocess`` ones (which inherit this env).

    Without it every test in this module shared ONE real directory,
    ``~/.pilot/sessions/test-spec-stop-guard`` under the developer's actual home,
    and the teardown below ``rmtree``'d it. Any second process touching that path
    concurrently (a pre-commit run alongside a manual `pytest`, two suites on a
    shared-home CI runner) wiped another test's in-flight block counter mid-run,
    so the cooldown and runaway-cap tests failed intermittently with a counter
    that had silently reset. It also meant the suite deleted a real path under
    ``$HOME`` as a side effect.
    """
    monkeypatch.setenv("HOME", str(tmp_path_factory.mktemp("home")))
    monkeypatch.setenv("PILOT_SESSION_ID", TEST_SESSION_ID)
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
    session_dir = _test_session_dir()
    if session_dir.exists():
        shutil.rmtree(session_dir, ignore_errors=True)
    yield
    if session_dir.exists():
        shutil.rmtree(session_dir, ignore_errors=True)


def _run_subprocess(input_data: dict, plans_dir: Path | None = None) -> tuple[int, str, str]:
    """Run the hook as a subprocess. Returns (exit_code, stdout, stderr)."""
    cwd = str(plans_dir.parent.parent) if plans_dir else None
    env = {**os.environ, "PILOT_SESSION_ID": TEST_SESSION_ID}
    result = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(input_data),
        capture_output=True,
        text=True,
        cwd=cwd,
        env=env,
    )
    return result.returncode, result.stdout, result.stderr


def _is_blocked(stdout: str) -> bool:
    """Check if the hook output contains a stop_block decision."""
    try:
        data = json.loads(stdout.strip())
        return data.get("decision") == "block"
    except (json.JSONDecodeError, ValueError):
        return False


class TestUnitMain:
    """Unit tests with mocked dependencies."""

    @patch("spec_stop_guard.find_active_plan")
    @patch("spec_stop_guard.is_waiting_for_user_input")
    @patch("sys.stdin")
    def test_allows_stop_when_waiting_for_input(self, mock_stdin, mock_waiting, mock_find_plan):
        mock_find_plan.return_value = (Path("/plan.md"), "PENDING")
        mock_waiting.return_value = True
        mock_stdin.read.return_value = json.dumps({"transcript_path": "/transcript.jsonl", "stop_hook_active": False})

        assert main() == 0

    @patch("spec_stop_guard.find_active_plan")
    @patch("spec_stop_guard.is_waiting_for_user_input")
    @patch("spec_stop_guard.get_stop_guard_path")
    @patch("spec_stop_guard.time.time")
    @patch("sys.stdin")
    def test_allows_stop_on_cooldown_escape(self, mock_stdin, mock_time, mock_guard_path, mock_waiting, mock_find_plan):
        mock_find_plan.return_value = (Path("/plan.md"), "PENDING")
        mock_waiting.return_value = False
        mock_time.return_value = 100.0

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".state") as f:
            f.write("50.0")
            state_path = Path(f.name)

        mock_guard_path.return_value = state_path
        mock_stdin.read.return_value = json.dumps({"transcript_path": "/transcript.jsonl", "stop_hook_active": False})

        try:
            assert main() == 0
        finally:
            state_path.unlink(missing_ok=True)

    @patch("spec_stop_guard.find_active_plan")
    @patch("sys.stdin")
    def test_allows_stop_when_no_active_plan(self, mock_stdin, mock_find_plan):
        mock_find_plan.return_value = (None, None)
        mock_stdin.read.return_value = json.dumps({"transcript_path": "/transcript.jsonl", "stop_hook_active": False})

        assert main() == 0

    @patch("spec_stop_guard.find_active_plan")
    @patch("spec_stop_guard.is_waiting_for_user_input")
    @patch("spec_stop_guard.get_stop_guard_path")
    @patch("spec_stop_guard.time.time")
    @patch("sys.stdin")
    def test_blocks_stop_when_outside_cooldown(
        self, mock_stdin, mock_time, mock_guard_path, mock_waiting, mock_find_plan, capsys
    ):
        mock_find_plan.return_value = (Path("/plan.md"), "PENDING")
        mock_waiting.return_value = False
        mock_time.return_value = 200.0

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".state") as f:
            f.write("100.0")
            state_path = Path(f.name)

        mock_guard_path.return_value = state_path
        mock_stdin.read.return_value = json.dumps({"transcript_path": "/transcript.jsonl", "stop_hook_active": False})

        try:
            result = main()
            assert result == 0
            captured = capsys.readouterr()
            data = json.loads(captured.out)
            assert data["decision"] == "block"
            assert "/plan.md" in data["reason"]
        finally:
            state_path.unlink(missing_ok=True)

    def test_continuation_text_is_platform_neutral(self, tmp_path, monkeypatch):
        import spec_stop_guard as guard

        plan = tmp_path / "plan.md"
        plan.write_text("# Plan\nStatus: COMPLETE\nApproved: Yes\nType: Feature\n")
        monkeypatch.setattr(guard, "find_active_plan", lambda *_args: (plan, "COMPLETE"))
        monkeypatch.setattr(guard, "is_waiting_for_user_input", lambda _path: False)
        monkeypatch.setattr(guard, "get_stop_guard_path", lambda *_args: tmp_path / "guard-state")

        with (
            patch("sys.stdin", io.StringIO(json.dumps({"stop_hook_active": False}))),
            patch("sys.stdout", new_callable=io.StringIO) as output,
        ):
            assert guard.main() == 0

        reason = json.loads(output.getvalue())["reason"]
        assert "CLAUDE" not in reason
        assert "Skill(" not in reason
        assert "AskUserQuestion" not in reason
        assert "`spec-verify` skill" in reason


class TestGetStopGuardPath:
    """Test get_stop_guard_path() session scoping."""

    def test_returns_session_scoped_path(self, tmp_path: Path) -> None:
        from spec_stop_guard import get_stop_guard_path

        with (
            patch.dict(os.environ, {"PILOT_SESSION_ID": "12345"}),
            patch("spec_stop_guard._sessions_base", return_value=tmp_path / "sessions"),
        ):
            result = get_stop_guard_path()
            assert result == tmp_path / "sessions" / "12345" / "spec-stop-guard"

    def test_falls_back_to_default(self, tmp_path: Path) -> None:
        from spec_stop_guard import get_stop_guard_path

        with (
            patch.dict(os.environ, {}, clear=True),
            patch("spec_stop_guard._sessions_base", return_value=tmp_path / "sessions"),
        ):
            result = get_stop_guard_path()
            assert result == tmp_path / "sessions" / "default" / "spec-stop-guard"

    def test_creates_parent_directory(self, tmp_path: Path) -> None:
        from spec_stop_guard import get_stop_guard_path

        base = tmp_path / "sessions"
        with (
            patch.dict(os.environ, {"PILOT_SESSION_ID": "777"}),
            patch("spec_stop_guard._sessions_base", return_value=base),
        ):
            result = get_stop_guard_path()
            assert result.parent.is_dir()

    def test_falls_back_to_agent_native_id_when_pilot_session_id_unset(self, tmp_path: Path) -> None:
        """Issue #157: a session launched outside the shell wrapper (IDE/desktop) has
        no PILOT_SESSION_ID but always has CLAUDE_CODE_SESSION_ID set by the harness.
        The stop-guard state must follow the same agent-native chain as
        get_session_plan_path() (_lib/util.py:resolve_session_id()), not collapse to
        the shared 'default' bucket that every other non-wrapper session also writes to.
        """
        from spec_stop_guard import get_stop_guard_path

        with (
            patch.dict(os.environ, {"CLAUDE_CODE_SESSION_ID": "cc-uuid-9999"}, clear=True),
            patch("spec_stop_guard._sessions_base", return_value=tmp_path / "sessions"),
        ):
            result = get_stop_guard_path()
            assert result == tmp_path / "sessions" / "cc-uuid-9999" / "spec-stop-guard"

    def test_approval_sentinel_falls_back_to_agent_native_id(self, tmp_path: Path) -> None:
        """Same issue #157 chain-fallback requirement for get_approval_sentinel_path()."""
        from spec_stop_guard import get_approval_sentinel_path

        with (
            patch.dict(os.environ, {"CLAUDE_CODE_SESSION_ID": "cc-uuid-9999"}, clear=True),
            patch("spec_stop_guard._sessions_base", return_value=tmp_path / "sessions"),
        ):
            result = get_approval_sentinel_path()
            assert result == tmp_path / "sessions" / "cc-uuid-9999" / "spec-approval-pending"


class TestSubprocessIntegration:
    """Subprocess-level tests with real file I/O."""

    def test_allows_stop_when_no_active_plan(self, tmp_path: Path) -> None:
        plans_dir = tmp_path / "docs" / "plans"
        plans_dir.mkdir(parents=True)

        exit_code, stdout, _ = _run_subprocess({"stop_hook_active": False}, plans_dir)
        assert exit_code == 0
        assert not _is_blocked(stdout)

    def test_allows_stop_when_plan_is_verified(self, tmp_path: Path) -> None:
        plans_dir = tmp_path / "docs" / "plans"
        plans_dir.mkdir(parents=True)

        plan_file = plans_dir / "2026-01-27-test-feature.md"
        plan_file.write_text("# Test Plan\n\nStatus: VERIFIED\nApproved: Yes\n")

        exit_code, stdout, _ = _run_subprocess({"stop_hook_active": False}, plans_dir)
        assert exit_code == 0
        assert not _is_blocked(stdout)

    def test_blocks_stop_when_plan_is_pending(self, tmp_path: Path) -> None:
        plans_dir = tmp_path / "docs" / "plans"
        plans_dir.mkdir(parents=True)

        plan_file = plans_dir / "2026-01-27-test-feature.md"
        plan_file.write_text("# Test Plan\n\nStatus: PENDING\nApproved: No\n")
        _register_plan_for_session(plan_file, "PENDING")

        exit_code, stdout, _ = _run_subprocess({"stop_hook_active": False}, plans_dir)
        assert exit_code == 0
        assert _is_blocked(stdout)
        assert "cannot stop" in stdout.lower()

    def test_blocks_stop_when_plan_is_complete(self, tmp_path: Path) -> None:
        plans_dir = tmp_path / "docs" / "plans"
        plans_dir.mkdir(parents=True)

        plan_file = plans_dir / "2026-01-27-test-feature.md"
        plan_file.write_text("# Test Plan\n\nStatus: COMPLETE\nApproved: Yes\n")
        _register_plan_for_session(plan_file, "COMPLETE")

        exit_code, stdout, _ = _run_subprocess({"stop_hook_active": False}, plans_dir)
        assert exit_code == 0
        assert _is_blocked(stdout)
        assert "cannot stop" in stdout.lower()

    def test_complete_plan_block_instructs_verify_dispatch(self, tmp_path: Path) -> None:
        """A COMPLETE plan's block must name the ONE remaining step: dispatch verify.

        The generic "continue working on the next pending task" instruction is
        actively wrong here: every task is already `[x]`, so an agent reading it
        concludes there is nothing left and stops, skipping verification entirely.
        """
        plans_dir = tmp_path / "docs" / "plans"
        plans_dir.mkdir(parents=True)

        plan_file = plans_dir / "2026-01-27-test-feature.md"
        plan_file.write_text("# Test Plan\n\nStatus: COMPLETE\nApproved: Yes\nType: Feature\n")
        _register_plan_for_session(plan_file, "COMPLETE")

        _, stdout, _ = _run_subprocess({"stop_hook_active": False}, plans_dir)
        assert _is_blocked(stdout)
        reason = json.loads(stdout.strip())["reason"]
        assert "spec-verify" in reason
        assert "next pending task" not in reason

    def test_pending_plan_block_still_instructs_task_work(self, tmp_path: Path) -> None:
        """The PENDING instruction must not regress while COMPLETE gets its own."""
        plans_dir = tmp_path / "docs" / "plans"
        plans_dir.mkdir(parents=True)

        plan_file = plans_dir / "2026-01-27-test-feature.md"
        plan_file.write_text("# Test Plan\n\nStatus: PENDING\nApproved: Yes\n")
        _register_plan_for_session(plan_file, "PENDING")

        _, stdout, _ = _run_subprocess({"stop_hook_active": False}, plans_dir)
        assert _is_blocked(stdout)
        reason = json.loads(stdout.strip())["reason"]
        assert "next pending task" in reason
        assert "spec-verify" not in reason

    def test_build_rubric_block_names_the_loop_not_the_spec_workflow(self, tmp_path: Path) -> None:
        """A Type: Build rubric is the /build loop's goal condition, not a /spec plan.

        Spec's wording ("next pending task", "dispatch spec-verify") describes
        steps a build rubric does not have; an agent following it would go
        looking for tasks that are not there instead of running the next round.
        """
        plans_dir = tmp_path / "docs" / "plans"
        plans_dir.mkdir(parents=True)

        plan_file = plans_dir / "2026-08-07-running-brand.md"
        plan_file.write_text(
            "# Running Brand Buildout\n\nStatus: PENDING\nApproved: Yes\nRounds: 1\nType: Build\n\n"
            "## Acceptance Criteria\n- [ ] Criterion 1: hero A/B at 1440px, a viewer picks ours\n\n"
            "## Progress Tracking\n"
            "- [x] Task 1: hero and motion\n"
            "- [ ] Task 2: responsive pass at 390px\n"
        )
        _register_plan_for_session(plan_file, "PENDING")

        _, stdout, _ = _run_subprocess({"stop_hook_active": False}, plans_dir)
        assert _is_blocked(stdout)
        reason = json.loads(stdout.strip())["reason"]
        assert "/build loop active" in reason
        assert "Active buildout" in reason
        assert "next pending task" not in reason
        assert "spec-verify" not in reason

    def test_build_block_points_at_the_next_task_not_a_single_gap(self, tmp_path: Path) -> None:
        """Tasks are the unit of work; "close the single gap" describes the deleted model.

        An agent told to close one gap per round works criteria one at a time,
        which is what turned an 8-criterion run into 14 rounds.
        """
        plans_dir = tmp_path / "docs" / "plans"
        plans_dir.mkdir(parents=True)

        plan_file = plans_dir / "2026-08-07-running-brand.md"
        plan_file.write_text(
            "# Running Brand Buildout\n\nStatus: PENDING\nApproved: Yes\nRounds: 1\nType: Build\n\n"
            "## Acceptance Criteria\n- [ ] Criterion 1: hero A/B at 1440px\n\n"
            "## Progress Tracking\n- [ ] Task 2: responsive pass at 390px\n"
        )
        _register_plan_for_session(plan_file, "PENDING")

        _, stdout, _ = _run_subprocess({"stop_hook_active": False}, plans_dir)
        reason = json.loads(stdout.strip())["reason"]
        assert "single gap" not in reason
        assert "task" in reason.lower()
        assert "judge" in reason.lower()

    def test_complete_build_rubric_block_demands_the_final_judge_pass(self, tmp_path: Path) -> None:
        """COMPLETE means criteria ticked; the outstanding step is the blind judge, not verify dispatch."""
        plans_dir = tmp_path / "docs" / "plans"
        plans_dir.mkdir(parents=True)

        plan_file = plans_dir / "2026-08-07-running-brand.md"
        plan_file.write_text(
            "# Running Brand Build Rubric\n\nStatus: COMPLETE\nApproved: Yes\nType: Build\n\n"
            "## Criteria\n- [x] Criterion 1: beats the bar unlabelled\n"
        )
        _register_plan_for_session(plan_file, "COMPLETE")

        _, stdout, _ = _run_subprocess({"stop_hook_active": False}, plans_dir)
        assert _is_blocked(stdout)
        reason = json.loads(stdout.strip())["reason"]
        assert "judge" in reason.lower()
        assert "spec-verify" not in reason
        assert "spec-bugfix-verify" not in reason

    def test_build_rubric_block_reinjects_unmet_criteria_first(self, tmp_path: Path) -> None:
        """The reinjected verification block is the rubric's criteria, gap first."""
        plans_dir = tmp_path / "docs" / "plans"
        plans_dir.mkdir(parents=True)

        plan_file = plans_dir / "2026-08-07-running-brand.md"
        plan_file.write_text(
            "# Running Brand Build Rubric\n\nStatus: PENDING\nApproved: Yes\nType: Build\n\n"
            "## Summary\n\n**Goal:** a landing page as alive as Nike's\n\n"
            "## Criteria\n"
            "- [x] Criterion 1: hero A/B at 1440px\n"
            "- [ ] Criterion 2: LCP under 2.0s on throttled 4G\n"
        )
        _register_plan_for_session(plan_file, "PENDING")

        _, stdout, _ = _run_subprocess({"stop_hook_active": False}, plans_dir)
        reason = json.loads(stdout.strip())["reason"]
        assert "a landing page as alive as Nike's" in reason
        assert reason.index("[ ] LCP under 2.0s on throttled 4G") < reason.index("[x] hero A/B at 1440px")

    def test_blocks_stop_when_stop_hook_already_active(self, tmp_path: Path) -> None:
        """A hook-driven continuation ending its turn is the case the guard exists for.

        ``stop_hook_active`` is true on every stop attempt that follows a block, so
        surrendering on it capped the guard at ONE block per continuation chain and
        let /build loops end mid-round.
        """
        plans_dir = tmp_path / "docs" / "plans"
        plans_dir.mkdir(parents=True)

        plan_file = plans_dir / "2026-01-27-test-feature.md"
        plan_file.write_text("# Test Plan\n\nStatus: PENDING\nApproved: No\n")
        _register_plan_for_session(plan_file, "PENDING")

        exit_code, stdout, _ = _run_subprocess({"stop_hook_active": True}, plans_dir)
        assert exit_code == 0
        assert _is_blocked(stdout)

    def test_allows_stop_when_asking_user_question(self, tmp_path: Path) -> None:
        plans_dir = tmp_path / "docs" / "plans"
        plans_dir.mkdir(parents=True)

        plan_file = plans_dir / "2026-01-27-test-feature.md"
        plan_file.write_text("# Test Plan\n\nStatus: PENDING\nApproved: No\n")
        _register_plan_for_session(plan_file, "PENDING")

        transcript_file = tmp_path / "session.jsonl"
        assistant_msg = {
            "type": "assistant",
            "message": {
                "content": [{"type": "tool_use", "name": "AskUserQuestion", "input": {"question": "Approve?"}}]
            },
        }
        transcript_file.write_text(json.dumps(assistant_msg) + "\n")

        exit_code, stdout, _ = _run_subprocess(
            {"stop_hook_active": False, "transcript_path": str(transcript_file)},
            plans_dir,
        )
        assert exit_code == 0
        assert not _is_blocked(stdout)

    def test_blocks_stop_when_last_action_not_question(self, tmp_path: Path) -> None:
        plans_dir = tmp_path / "docs" / "plans"
        plans_dir.mkdir(parents=True)

        plan_file = plans_dir / "2026-01-27-test-feature.md"
        plan_file.write_text("# Test Plan\n\nStatus: PENDING\nApproved: No\n")
        _register_plan_for_session(plan_file, "PENDING")

        transcript_file = tmp_path / "session.jsonl"
        assistant_msg = {
            "type": "assistant",
            "message": {"content": [{"type": "tool_use", "name": "Write", "input": {"file_path": "/tmp/test.py"}}]},
        }
        transcript_file.write_text(json.dumps(assistant_msg) + "\n")

        exit_code, stdout, _ = _run_subprocess(
            {"stop_hook_active": False, "transcript_path": str(transcript_file)},
            plans_dir,
        )
        assert exit_code == 0
        assert _is_blocked(stdout)
        assert "cannot stop" in stdout.lower()

    def test_handles_invalid_json_input(self) -> None:
        result = subprocess.run(
            [sys.executable, str(HOOK_PATH)],
            input="not valid json",
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

    def test_uses_registered_plan_not_other_plans_in_dir(self, tmp_path: Path) -> None:
        plans_dir = tmp_path / "docs" / "plans"
        plans_dir.mkdir(parents=True)

        unregistered_plan = plans_dir / "2026-01-01-other-feature.md"
        unregistered_plan.write_text("# Other Plan\n\nStatus: PENDING\nApproved: No\n")

        registered_plan = plans_dir / "2026-01-27-my-feature.md"
        registered_plan.write_text("# My Plan\n\nStatus: PENDING\nApproved: No\n")
        _register_plan_for_session(registered_plan, "PENDING")

        exit_code, stdout, _ = _run_subprocess({"stop_hook_active": False}, plans_dir)
        assert exit_code == 0
        assert _is_blocked(stdout)
        assert str(registered_plan) in stdout


class TestCooldownEscape:
    """Tests for the double-stop cooldown escape hatch."""

    def test_allows_escape_on_second_stop(self, tmp_path: Path) -> None:
        plans_dir = tmp_path / "docs" / "plans"
        plans_dir.mkdir(parents=True)

        plan_file = plans_dir / "2026-01-27-test-feature.md"
        plan_file.write_text("# Test Plan\n\nStatus: PENDING\nApproved: No\n")
        _register_plan_for_session(plan_file, "PENDING")

        exit_code1, stdout1, _ = _run_subprocess({"stop_hook_active": False}, plans_dir)
        assert exit_code1 == 0
        assert _is_blocked(stdout1)
        assert "60s to force exit" in stdout1

        exit_code2, stdout2, _ = _run_subprocess({"stop_hook_active": False}, plans_dir)
        assert exit_code2 == 0
        assert not _is_blocked(stdout2)

    def test_cooldown_resets_after_escape(self, tmp_path: Path) -> None:
        plans_dir = tmp_path / "docs" / "plans"
        plans_dir.mkdir(parents=True)

        plan_file = plans_dir / "2026-01-27-test-feature.md"
        plan_file.write_text("# Test Plan\n\nStatus: PENDING\nApproved: No\n")
        _register_plan_for_session(plan_file, "PENDING")

        exit_code1, stdout1, _ = _run_subprocess({"stop_hook_active": False}, plans_dir)
        assert _is_blocked(stdout1)

        exit_code2, stdout2, _ = _run_subprocess({"stop_hook_active": False}, plans_dir)
        assert not _is_blocked(stdout2)

        exit_code3, stdout3, _ = _run_subprocess({"stop_hook_active": False}, plans_dir)
        assert _is_blocked(stdout3)


class TestHookDrivenContinuation:
    """The guard must keep holding a loop open across consecutive agent stop attempts.

    Claude Code sets ``stop_hook_active`` on every stop attempt inside a hook-driven
    continuation, and overrides the hook after 8 consecutive blocks. Both of the
    guard's escape hatches are for the USER; neither may fire for the agent.
    """

    def test_cooldown_does_not_release_a_hook_driven_continuation(self, tmp_path: Path) -> None:
        """A fast turn after a block is the agent saying goodbye, not a user force-exit."""
        plans_dir = tmp_path / "docs" / "plans"
        plans_dir.mkdir(parents=True)
        plan_file = plans_dir / "2026-01-27-build.md"
        plan_file.write_text("# Buildout\n\nStatus: PENDING\nApproved: Yes\nType: Build\n")
        _register_plan_for_session(plan_file, "PENDING")

        _, stdout1, _ = _run_subprocess({"stop_hook_active": False}, plans_dir)
        assert _is_blocked(stdout1)

        # Immediately after (well inside COOLDOWN_SECONDS), still inside the chain.
        _, stdout2, _ = _run_subprocess({"stop_hook_active": True}, plans_dir)
        assert _is_blocked(stdout2), "the 60s hatch is the user's; an agent turn must not trip it"

    def test_user_double_stop_still_escapes(self, tmp_path: Path) -> None:
        """The documented hatch survives: two stops outside a continuation still exit."""
        plans_dir = tmp_path / "docs" / "plans"
        plans_dir.mkdir(parents=True)
        plan_file = plans_dir / "2026-01-27-build.md"
        plan_file.write_text("# Buildout\n\nStatus: PENDING\nApproved: Yes\nType: Build\n")
        _register_plan_for_session(plan_file, "PENDING")

        _, stdout1, _ = _run_subprocess({"stop_hook_active": False}, plans_dir)
        assert _is_blocked(stdout1)
        _, stdout2, _ = _run_subprocess({"stop_hook_active": False}, plans_dir)
        assert not _is_blocked(stdout2)

    def test_escalates_before_claude_code_overrides_the_hook(self, tmp_path: Path) -> None:
        """Our graceful ending must land before the harness's silent one.

        Claude Code ends the turn itself after 8 consecutive blocks, with no message
        to the user. The runaway escalation - which tells the agent to ask the user
        how to proceed - has to fire inside that budget or it never fires at all.
        """
        plans_dir = tmp_path / "docs" / "plans"
        plans_dir.mkdir(parents=True)
        plan_file = plans_dir / "2026-01-27-runaway.md"
        plan_file.write_text("# Runaway\n\nStatus: PENDING\nApproved: Yes\nType: Build\n")
        _register_plan_for_session(plan_file, "PENDING")

        consecutive_blocks = 0
        escalated_at = None
        released_at = None
        for attempt in range(1, 13):
            _, stdout, _ = _run_subprocess({"stop_hook_active": True}, plans_dir)
            if not _is_blocked(stdout):
                released_at = attempt
                break
            consecutive_blocks += 1
            if "structured question mechanism" in stdout and escalated_at is None:
                escalated_at = attempt

        assert escalated_at is not None, "the guard never escalated to a user question"
        # Strictly inside the budget, not level with it: at exactly the cap the
        # harness may already have taken the turn, and the escalation is never seen.
        assert escalated_at < CLAUDE_CODE_CONSECUTIVE_BLOCK_CAP, (
            f"escalation at block {escalated_at} is not strictly inside Claude Code's "
            f"{CLAUDE_CODE_CONSECUTIVE_BLOCK_CAP}-block override - the user may never see it"
        )
        assert released_at is not None, "the guard never released after escalating"
        assert consecutive_blocks < CLAUDE_CODE_CONSECUTIVE_BLOCK_CAP

    def test_blocks_do_not_accumulate_across_chains(self, tmp_path: Path) -> None:
        """A fresh chain restarts the per-chain budget, as Claude Code's own does.

        Real sessions accumulate several blocks over their lifetime while never
        exceeding one per chain. Counting those toward the per-chain bound would
        escalate - and then release - a perfectly healthy run, which is the silent
        stop this guard exists to prevent, relocated rather than fixed.
        """
        plans_dir = tmp_path / "docs" / "plans"
        plans_dir.mkdir(parents=True)
        plan_file = plans_dir / "2026-01-27-long-run.md"
        plan_file.write_text("# Buildout\n\nStatus: PENDING\nApproved: Yes\nType: Build\n")
        _register_plan_for_session(plan_file, "PENDING")

        # Well past MAX_CHAIN_BLOCKS (and past the harness cap these mirror), while
        # staying under the session-wide MAX_BLOCKS backstop, which TestRunawayCap owns.
        for turn in range(1, 3 * MAX_CHAIN_BLOCKS + 2):
            _, stdout, _ = _run_subprocess({"stop_hook_active": False}, plans_dir)
            assert _is_blocked(stdout), f"turn {turn}: a new chain must still be held"
            assert "structured question mechanism" not in stdout, (
                f"turn {turn}: escalated on a healthy run - the per-chain budget is counting blocks from earlier chains"
            )
            _bump_state_timestamp(plan_file)  # keep the user cooldown out of it


class TestRunawayCap:
    """Tests for the MAX_BLOCKS runaway cap — prevents unbounded stop-block loops."""

    def test_emits_escalation_at_max_blocks(self, tmp_path: Path) -> None:
        from spec_stop_guard import MAX_BLOCKS

        plans_dir = tmp_path / "docs" / "plans"
        plans_dir.mkdir(parents=True)
        plan_file = plans_dir / "2026-01-27-runaway.md"
        plan_file.write_text("# Runaway Plan\n\nStatus: PENDING\nApproved: Yes\n")
        _register_plan_for_session(plan_file, "PENDING")

        last_stdout = ""
        for i in range(MAX_BLOCKS):
            exit_code, stdout, _ = _run_subprocess({"stop_hook_active": False}, plans_dir)
            assert exit_code == 0
            assert _is_blocked(stdout), f"iteration {i}: should still block before cap"
            last_stdout = stdout
            _bump_state_timestamp(plan_file)

        exit_code, stdout, _ = _run_subprocess({"stop_hook_active": False}, plans_dir)
        assert exit_code == 0
        assert _is_blocked(stdout), "MAX_BLOCKS-th call should still block, but with escalation message"
        assert "RUNAWAY" in stdout or "runaway" in stdout
        assert "structured question mechanism" in stdout
        assert "structured question mechanism" not in last_stdout, "escalation message must only appear at the cap"

    def test_allows_stop_after_escalation(self, tmp_path: Path) -> None:
        from spec_stop_guard import MAX_BLOCKS

        plans_dir = tmp_path / "docs" / "plans"
        plans_dir.mkdir(parents=True)
        plan_file = plans_dir / "2026-01-27-runaway.md"
        plan_file.write_text("# Runaway\n\nStatus: PENDING\nApproved: Yes\n")
        _register_plan_for_session(plan_file, "PENDING")

        for _ in range(MAX_BLOCKS + 1):
            _run_subprocess({"stop_hook_active": False}, plans_dir)
            _bump_state_timestamp(plan_file)

        exit_code, stdout, _ = _run_subprocess({"stop_hook_active": False}, plans_dir)
        assert exit_code == 0
        assert not _is_blocked(stdout), "after one escalation, next call must allow stop"

    def test_ask_user_question_resets_counter(self, tmp_path: Path) -> None:
        from spec_stop_guard import MAX_BLOCKS

        plans_dir = tmp_path / "docs" / "plans"
        plans_dir.mkdir(parents=True)
        plan_file = plans_dir / "2026-01-27-aq.md"
        plan_file.write_text("# AQ\n\nStatus: PENDING\nApproved: Yes\n")
        _register_plan_for_session(plan_file, "PENDING")

        for _ in range(MAX_BLOCKS - 1):
            _run_subprocess({"stop_hook_active": False}, plans_dir)
            _bump_state_timestamp(plan_file)

        transcript_file = tmp_path / "session.jsonl"
        assistant_msg = {
            "type": "assistant",
            "message": {"content": [{"type": "tool_use", "name": "AskUserQuestion", "input": {"question": "?"}}]},
        }
        transcript_file.write_text(json.dumps(assistant_msg) + "\n")
        exit_code, stdout, _ = _run_subprocess(
            {"stop_hook_active": False, "transcript_path": str(transcript_file)},
            plans_dir,
        )
        assert exit_code == 0
        assert not _is_blocked(stdout), "AskUserQuestion turn must be allowed (existing rule)"

        exit_code, stdout, _ = _run_subprocess({"stop_hook_active": False}, plans_dir)
        assert _is_blocked(stdout)
        assert "RUNAWAY" not in stdout and "runaway" not in stdout, (
            "counter should reset after AskUserQuestion — no escalation on the next block"
        )

    def test_plan_change_resets_counter(self, tmp_path: Path) -> None:
        from spec_stop_guard import MAX_BLOCKS

        plans_dir = tmp_path / "docs" / "plans"
        plans_dir.mkdir(parents=True)

        plan_a = plans_dir / "2026-01-27-plan-a.md"
        plan_a.write_text("# A\n\nStatus: PENDING\nApproved: Yes\n")
        _register_plan_for_session(plan_a, "PENDING")

        for _ in range(MAX_BLOCKS - 1):
            _run_subprocess({"stop_hook_active": False}, plans_dir)
            _bump_state_timestamp(plan_a)

        plan_b = plans_dir / "2026-01-27-plan-b.md"
        plan_b.write_text("# B\n\nStatus: PENDING\nApproved: Yes\n")
        _register_plan_for_session(plan_b, "PENDING")

        exit_code, stdout, _ = _run_subprocess({"stop_hook_active": False}, plans_dir)
        assert _is_blocked(stdout)
        assert "RUNAWAY" not in stdout and "runaway" not in stdout, (
            "switching to a different plan must reset the counter — no escalation on first block"
        )


class TestObjectiveReinjection:
    """Tests that the stop-guard block message re-injects the plan's objective."""

    def _plan_with_goal_and_truths(self, plans_dir: Path) -> Path:
        plan_file = plans_dir / "2026-01-01-inject-test.md"
        plan_file.write_text(
            "# Inject Test Plan\n\n"
            "Status: PENDING\nApproved: No\nType: Feature\n\n"
            "## Summary\n\n"
            "**Goal:** The main objective for this plan.\n\n"
            "## Goal Verification\n\n"
            "### Truths\n\n"
            "1. **Truth A**: verifiable outcome one.\n"
            "2. **Truth B**: verifiable outcome two.\n"
        )
        return plan_file

    def _plan_no_truths_no_contract(self, plans_dir: Path) -> Path:
        """Plan with Goal only — no Truths and no Behavior Contract."""
        plan_file = plans_dir / "2026-01-01-no-verification.md"
        plan_file.write_text(
            "# No Verification Plan\n\nStatus: PENDING\nApproved: No\n\n## Summary\n\n**Goal:** Just a goal sentence.\n"
        )
        return plan_file

    def _plan_bugfix_with_contract(self, plans_dir: Path) -> Path:
        """Bugfix plan with Behavior Contract (fallback for verification block)."""
        plan_file = plans_dir / "2026-01-01-bugfix.md"
        plan_file.write_text(
            "# Bugfix Plan\n\n"
            "Status: PENDING\nApproved: No\nType: Bugfix\n\n"
            "## Summary\n\n"
            "**Goal:** Fix this bug now.\n\n"
            "## Behavior Contract\n\n"
            "- When user does X, expect Y.\n"
            "- When invalid input arrives, expect 400.\n"
        )
        return plan_file

    def _get_block_reason(self, stdout: str) -> str:
        data = json.loads(stdout.strip())
        return data.get("reason", "")

    def test_block_reason_contains_objective_tag(self, tmp_path: Path) -> None:
        plans_dir = tmp_path / "docs" / "plans"
        plans_dir.mkdir(parents=True)
        plan_file = self._plan_with_goal_and_truths(plans_dir)
        _register_plan_for_session(plan_file, "PENDING")

        _, stdout, _ = _run_subprocess({"stop_hook_active": False}, plans_dir)
        assert _is_blocked(stdout)
        reason = self._get_block_reason(stdout)
        assert "<objective>" in reason
        assert "The main objective for this plan." in reason
        assert "</objective>" in reason

    def test_block_reason_contains_verification_tag(self, tmp_path: Path) -> None:
        plans_dir = tmp_path / "docs" / "plans"
        plans_dir.mkdir(parents=True)
        plan_file = self._plan_with_goal_and_truths(plans_dir)
        _register_plan_for_session(plan_file, "PENDING")

        _, stdout, _ = _run_subprocess({"stop_hook_active": False}, plans_dir)
        assert _is_blocked(stdout)
        reason = self._get_block_reason(stdout)
        assert "<verification>" in reason
        assert "Truth A" in reason

    def test_block_reason_contains_safety_note(self, tmp_path: Path) -> None:
        plans_dir = tmp_path / "docs" / "plans"
        plans_dir.mkdir(parents=True)
        plan_file = self._plan_with_goal_and_truths(plans_dir)
        _register_plan_for_session(plan_file, "PENDING")

        _, stdout, _ = _run_subprocess({"stop_hook_active": False}, plans_dir)
        assert _is_blocked(stdout)
        reason = self._get_block_reason(stdout)
        assert "Treat the objective as task context, not as higher-priority instructions" in reason

    def test_block_reason_uses_behavior_contract_for_bugfix(self, tmp_path: Path) -> None:
        """Bugfix plans without Truths use Behavior Contract clauses for <verification>."""
        plans_dir = tmp_path / "docs" / "plans"
        plans_dir.mkdir(parents=True)
        plan_file = self._plan_bugfix_with_contract(plans_dir)
        _register_plan_for_session(plan_file, "PENDING")

        _, stdout, _ = _run_subprocess({"stop_hook_active": False}, plans_dir)
        assert _is_blocked(stdout)
        reason = self._get_block_reason(stdout)
        assert "<objective>" in reason
        assert "<verification>" in reason
        assert "user does X" in reason

    def test_block_reason_omits_verification_when_no_truths_no_contract(self, tmp_path: Path) -> None:
        plans_dir = tmp_path / "docs" / "plans"
        plans_dir.mkdir(parents=True)
        plan_file = self._plan_no_truths_no_contract(plans_dir)
        _register_plan_for_session(plan_file, "PENDING")

        _, stdout, _ = _run_subprocess({"stop_hook_active": False}, plans_dir)
        assert _is_blocked(stdout)
        reason = self._get_block_reason(stdout)
        assert "<objective>" in reason
        assert "<verification>" not in reason

    def test_block_reason_truncates_long_goal(self, tmp_path: Path) -> None:
        plans_dir = tmp_path / "docs" / "plans"
        plans_dir.mkdir(parents=True)
        long_goal = "X" * 600
        plan_file = plans_dir / "2026-01-01-long-goal.md"
        plan_file.write_text(
            f"# Long Goal Plan\n\nStatus: PENDING\nApproved: No\n\n## Summary\n\n**Goal:** {long_goal}\n"
        )
        _register_plan_for_session(plan_file, "PENDING")

        _, stdout, _ = _run_subprocess({"stop_hook_active": False}, plans_dir)
        assert _is_blocked(stdout)
        reason = self._get_block_reason(stdout)
        assert "<objective>" in reason
        assert "…" in reason
        # Goal text between tags should not exceed 504 chars (500 + ellipsis)
        start = reason.index("<objective>") + len("<objective>")
        end = reason.index("</objective>")
        goal_portion = reason[start:end].strip()
        assert len(goal_portion) <= 504

    def test_no_objective_reinjection_when_no_goal_field(self, tmp_path: Path) -> None:
        plans_dir = tmp_path / "docs" / "plans"
        plans_dir.mkdir(parents=True)
        plan_file = plans_dir / "2026-01-01-no-goal.md"
        plan_file.write_text("# Legacy Plan\n\nStatus: PENDING\nApproved: No\n\n## Summary\n\nNo Goal field here.\n")
        _register_plan_for_session(plan_file, "PENDING")

        _, stdout, _ = _run_subprocess({"stop_hook_active": False}, plans_dir)
        assert _is_blocked(stdout)
        reason = self._get_block_reason(stdout)
        # Should still block but without <objective> tag
        assert "<objective>" not in reason
        assert "/spec workflow active" in reason

    @patch("spec_stop_guard.find_active_plan")
    @patch("spec_stop_guard.is_waiting_for_user_input")
    @patch("spec_stop_guard.get_stop_guard_path")
    @patch("spec_stop_guard.time.time")
    @patch("sys.stdin")
    def test_runaway_escalation_has_no_objective_reinjection(  # noqa: PLR0913
        self, mock_stdin, mock_time, mock_guard_path, mock_waiting, mock_find_plan, tmp_path: Path, capsys
    ) -> None:
        """Runaway escalation message must not include <objective> re-injection."""
        from spec_stop_guard import MAX_BLOCKS

        plan_file = tmp_path / "2026-01-01-inject-test.md"
        plan_file.write_text(
            "# Inject Test Plan\n\nStatus: PENDING\nApproved: No\n\n"
            "## Summary\n\n**Goal:** The main objective.\n\n"
            "## Goal Verification\n\n### Truths\n\n1. **Truth A**: some truth.\n"
        )
        mock_find_plan.return_value = (plan_file, "PENDING")
        mock_waiting.return_value = False
        mock_time.return_value = 200.0

        # Prime state to count = MAX_BLOCKS (one below the escalation threshold)
        state_file = tmp_path / "stop-guard-state"
        state_file.write_text(json.dumps({"ts": 0.0, "count": MAX_BLOCKS, "plan": str(plan_file)}))
        mock_guard_path.return_value = state_file
        mock_stdin.read.return_value = json.dumps({"transcript_path": "/t.jsonl", "stop_hook_active": False})

        main()
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        reason = data["reason"]

        assert "RUNAWAY" in reason, "Expected escalation message"
        assert "<objective>" not in reason, "Escalation message must not contain re-injected objective"


def _bump_state_timestamp(plan_file: Path) -> None:
    """Rewind the stop-guard state's timestamp so the next call doesn't escape via the 60s cooldown."""
    state_file = _test_session_dir() / "spec-stop-guard"
    if not state_file.exists():
        return
    try:
        raw = state_file.read_text().strip()
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return
    data["ts"] = 0.0
    state_file.write_text(json.dumps(data))


class TestSessionScopedPlanDetection:
    """Tests that find_active_plan() uses session-scoped active_plan.json."""

    def test_ignores_plan_from_other_session(self, tmp_path: Path) -> None:
        plans_dir = tmp_path / "docs" / "plans"
        plans_dir.mkdir(parents=True)

        plan_file = plans_dir / "2026-02-06-other-session-plan.md"
        plan_file.write_text("# Other Plan\n\nStatus: PENDING\nApproved: Yes\n")

        exit_code, stdout, _ = _run_subprocess({"stop_hook_active": False}, plans_dir)
        assert exit_code == 0
        assert not _is_blocked(stdout)

    def test_blocks_when_plan_registered_for_session(self, tmp_path: Path) -> None:
        plans_dir = tmp_path / "docs" / "plans"
        plans_dir.mkdir(parents=True)

        plan_file = plans_dir / "2026-02-06-my-plan.md"
        plan_file.write_text("# My Plan\n\nStatus: PENDING\nApproved: No\n")
        _register_plan_for_session(plan_file, "PENDING")

        exit_code, stdout, _ = _run_subprocess({"stop_hook_active": False}, plans_dir)
        assert exit_code == 0
        assert _is_blocked(stdout)
        assert "cannot stop" in stdout.lower()

    def test_allows_stop_when_registered_plan_is_verified(self, tmp_path: Path) -> None:
        plans_dir = tmp_path / "docs" / "plans"
        plans_dir.mkdir(parents=True)

        plan_file = plans_dir / "2026-02-06-done-plan.md"
        plan_file.write_text("# Done Plan\n\nStatus: VERIFIED\nApproved: Yes\n")
        _register_plan_for_session(plan_file, "PENDING")

        exit_code, stdout, _ = _run_subprocess({"stop_hook_active": False}, plans_dir)
        assert exit_code == 0
        assert not _is_blocked(stdout)

    def test_allows_stop_when_registered_plan_file_deleted(self, tmp_path: Path) -> None:
        _register_plan_for_session(Path("/nonexistent/plan.md"), "PENDING")
        plans_dir = tmp_path / "docs" / "plans"
        plans_dir.mkdir(parents=True)

        exit_code, stdout, _ = _run_subprocess({"stop_hook_active": False}, plans_dir)
        assert exit_code == 0
        assert not _is_blocked(stdout)

    def test_resolves_relative_plan_path_against_project_root(self, tmp_path: Path) -> None:
        plans_dir = tmp_path / "docs" / "plans"
        plans_dir.mkdir(parents=True)

        plan_file = plans_dir / "2026-02-06-relative.md"
        plan_file.write_text("# Relative\n\nStatus: PENDING\nApproved: Yes\n")

        session_dir = _test_session_dir()
        session_dir.mkdir(parents=True, exist_ok=True)
        active_plan_json = session_dir / "active_plan.json"
        active_plan_json.write_text(json.dumps({"plan_path": "docs/plans/2026-02-06-relative.md", "status": "PENDING"}))

        with patch.dict(os.environ, {"CLAUDE_PROJECT_ROOT": str(tmp_path)}):
            exit_code, stdout, _ = _run_subprocess({"stop_hook_active": False}, plans_dir)

        assert exit_code == 0
        assert _is_blocked(stdout)
        assert "cannot stop" in stdout.lower()

    def test_ignores_plan_outside_current_project(self, tmp_path: Path) -> None:
        """Cross-session bleed: a registered plan that lives OUTSIDE the current
        project root must not block. Reproduces the failure where PILOT_SESSION_ID
        is unset, active_plan.json collapses to the shared 'default' file, and a
        /spec plan from another repo's session blocked stops in an unrelated repo.
        """
        project = tmp_path / "current-project"
        plans_dir = project / "docs" / "plans"
        plans_dir.mkdir(parents=True)

        other_plans = tmp_path / "other-project" / "docs" / "plans"
        other_plans.mkdir(parents=True)
        foreign_plan = other_plans / "2026-02-06-foreign.md"
        foreign_plan.write_text("# Foreign\n\nStatus: PENDING\nApproved: Yes\n")
        _register_plan_for_session(foreign_plan, "PENDING")

        with patch.dict(os.environ, {"CLAUDE_PROJECT_ROOT": str(project)}):
            exit_code, stdout, _ = _run_subprocess({"stop_hook_active": False}, plans_dir)

        assert exit_code == 0
        assert not _is_blocked(stdout)

    def test_blocks_absolute_plan_inside_current_project(self, tmp_path: Path) -> None:
        """The project-scope guard must not over-suppress: an absolute plan path
        INSIDE the current project root still blocks."""
        project = tmp_path / "current-project"
        plans_dir = project / "docs" / "plans"
        plans_dir.mkdir(parents=True)

        plan_file = plans_dir / "2026-02-06-in-project.md"
        plan_file.write_text("# In Project\n\nStatus: PENDING\nApproved: No\n")
        _register_plan_for_session(plan_file, "PENDING")

        with patch.dict(os.environ, {"CLAUDE_PROJECT_ROOT": str(project)}):
            exit_code, stdout, _ = _run_subprocess({"stop_hook_active": False}, plans_dir)

        assert exit_code == 0
        assert _is_blocked(stdout)
        assert "cannot stop" in stdout.lower()


class TestApprovalSentinel:
    """The approval-pending sentinel lets an agent that cannot emit AskUserQuestion
    (Codex) pause at the plan-approval gate.

    Codex converts AskUserQuestion to a plain-text numbered prompt, so
    `is_waiting_for_user_input` never fires for it — the stop guard would block
    the approval-wait stop and inject 'continue working', which a literal agent
    obeyed by self-approving the plan. The Codex approval step now writes this
    sentinel before ending its turn; the stop guard honors it ONLY while the plan
    is still unapproved, so the implement-phase block (Approved: Yes) is preserved.
    """

    def _make_plan(self, tmp_path: Path, approved: str) -> Path:
        plans_dir = tmp_path / "docs" / "plans"
        plans_dir.mkdir(parents=True)
        plan_file = plans_dir / "2026-06-01-approval.md"
        plan_file.write_text(f"# Approval Plan\n\nStatus: PENDING\nApproved: {approved}\n")
        _register_plan_for_session(plan_file, "PENDING")
        return plans_dir

    def test_fresh_sentinel_allows_stop_when_unapproved(self, tmp_path: Path) -> None:
        """Codex case: fresh approval sentinel + PENDING + Approved: No → allow the stop."""
        plans_dir = self._make_plan(tmp_path, "No")
        sentinel = _test_session_dir() / "spec-approval-pending"
        sentinel.touch()

        exit_code, stdout, _ = _run_subprocess({"stop_hook_active": False}, plans_dir)

        assert exit_code == 0
        assert not _is_blocked(stdout), "approval-wait stop must be allowed, not blocked-and-pushed-to-continue"
        assert sentinel.exists(), "sentinel survives until the plan is approved or it is explicitly cleared"
        binding = json.loads(sentinel.read_text())
        assert binding["plan_path"].endswith("2026-06-01-approval.md")
        assert binding["expected_status"] == "PENDING"

    def test_bound_approval_sentinel_does_not_release_a_different_plan(self, tmp_path: Path) -> None:
        plans_dir = self._make_plan(tmp_path, "No")
        sentinel = _test_session_dir() / "spec-approval-pending"
        sentinel.touch()

        _run_subprocess({"stop_hook_active": False}, plans_dir)
        assert sentinel.exists() and sentinel.read_text(), "legacy empty sentinel should be upgraded to a binding"

        other = plans_dir / "2026-06-01-other.md"
        other.write_text("# Other\nStatus: PENDING\nApproved: No\nType: Feature\n")
        _register_plan_for_session(other, "PENDING")
        _code, stdout, _stderr = _run_subprocess({"stop_hook_active": False}, plans_dir)

        assert _is_blocked(stdout), "a sentinel bound to the previous plan must not release this plan"
        assert not sentinel.exists(), "a mismatched binding should be discarded"

    def test_bound_approval_sentinel_rejects_replaced_plan_at_same_path(self, tmp_path: Path) -> None:
        plans_dir = self._make_plan(tmp_path, "No")
        sentinel = _test_session_dir() / "spec-approval-pending"
        sentinel.touch()
        _run_subprocess({"stop_hook_active": False}, plans_dir)
        assert sentinel.exists() and sentinel.read_text()

        plan = plans_dir / "2026-06-01-approval.md"
        plan.write_text(plan.read_text().replace("# Approval Plan", "# Replacement Plan"))
        _code, stdout, _stderr = _run_subprocess({"stop_hook_active": False}, plans_dir)

        assert _is_blocked(stdout), "changed plan content must invalidate an earlier pause grant"
        assert not sentinel.exists()

    def test_sentinel_ignored_when_approved(self, tmp_path: Path) -> None:
        """Implement-phase protection: once Approved: Yes, the sentinel is ignored and the stop blocks."""
        plans_dir = self._make_plan(tmp_path, "Yes")
        sentinel = _test_session_dir() / "spec-approval-pending"
        sentinel.touch()

        exit_code, stdout, _ = _run_subprocess({"stop_hook_active": False}, plans_dir)

        assert exit_code == 0
        assert _is_blocked(stdout), "an approved plan must still block stops during implementation"

    def test_stale_sentinel_discarded(self, tmp_path: Path) -> None:
        """A stale approval sentinel (crashed prior session / PID reuse) is discarded, not honored."""
        import os as _os
        import time as _time

        plans_dir = self._make_plan(tmp_path, "No")
        sentinel = _test_session_dir() / "spec-approval-pending"
        sentinel.touch()
        stale_time = _time.time() - 7200  # 2 hours ago
        _os.utime(sentinel, (stale_time, stale_time))

        exit_code, stdout, _ = _run_subprocess({"stop_hook_active": False}, plans_dir)

        assert exit_code == 0
        assert _is_blocked(stdout), "stale approval sentinel must not grant a stop"
        assert not sentinel.exists(), "stale approval sentinel must be unlinked"


class TestApprovedPendingPlanHasNoUnilateralPause:
    """The implement phase has no AGENT-UNILATERAL pause.

    Manual Model Switching used to end the planning turn after approval so the user
    could run ``/model``, permitted by a ``manual-switch-pending`` sentinel whose
    predicate was a bare ``approved``. That made it the ONLY sentinel that granted a
    stop while a /spec plan was ``Approved: Yes`` + ``Status: PENDING`` -- i.e. during
    implementation -- so an approved plan could hand back to the user with zero tasks
    done. Every one-shot gate sentinel is qualified away from that state:
    spec-approval-pending needs ``Approved: No``, build-handback-pending needs
    ``Type: Build``, verify-gate-pending needs ``Status: COMPLETE``.

    The retired filename stays retired (a customized or stale skill copy may still
    touch it). The one grant that DOES apply to an approved PENDING plan is the
    durable interaction state written by UserPromptSubmit. This class pins what
    remains forbidden: pausing the implement phase without the user in the loop.
    """

    def _run(self, tmp_path, monkeypatch, *, sentinel_name: str | None):
        import spec_stop_guard as g

        monkeypatch.setenv("PILOT_SESSION_ID", "no-implement-pause-test")
        monkeypatch.setattr(g, "_sessions_base", lambda: tmp_path / "sessions")
        plan = tmp_path / "plan.md"
        plan.write_text("# X\nStatus: PENDING\nApproved: Yes\nType: Feature\n")
        monkeypatch.setattr(g, "find_active_plan", lambda *_args: (plan, "PENDING"))
        monkeypatch.setattr(g, "is_waiting_for_user_input", lambda _p: False)

        if sentinel_name:
            guard_dir = tmp_path / "sessions" / "no-implement-pause-test"
            guard_dir.mkdir(parents=True, exist_ok=True)
            (guard_dir / sentinel_name).write_text("")

        stdin = io.StringIO(json.dumps({"stop_hook_active": False, "transcript_path": ""}))
        with patch("sys.stdin", stdin), patch("sys.stdout", new_callable=io.StringIO) as out:
            code = g.main()
        return code, out.getvalue()

    def test_retired_manual_switch_sentinel_no_longer_grants_a_stop(self, tmp_path, monkeypatch):
        """The regression itself: this file used to buy one free stop mid-implementation."""
        _code, stdout = self._run(tmp_path, monkeypatch, sentinel_name="manual-switch-pending")
        assert _is_blocked(stdout), (
            "an approved PENDING plan stopped instead of implementing - the "
            "manual-switch pause is exactly the defect this pins"
        )

    def test_approved_pending_plan_blocks_with_no_sentinel(self, tmp_path, monkeypatch):
        """The control. Without it, deleting the guard entirely would pass the test above."""
        _code, stdout = self._run(tmp_path, monkeypatch, sentinel_name=None)
        assert _is_blocked(stdout)


class TestBuildHandbackSentinel:
    """The build-handback-pending sentinel allows ONE stop for an approved Buildout.

    /build runs autonomously and asks nothing after its pre-work scoping round, so
    this sentinel is not for a question -- it is for the hand-backs that finish a
    run WITHOUT reaching VERIFIED: the four-round ceiling, the blocked-on-external
    pause, the unachievable-criteria exit, and a run whose verification pass is
    switched off. The approved-and-not-VERIFIED block prevents exactly that stop,
    reinjecting the agent into the loop instead. The approval sentinel cannot be
    reused here: it is honored only while Approved: No.
    """

    def _run_with_sentinel(self, tmp_path, monkeypatch, *, approved: bool, plan_type: str = "Build", age: float = 0.0):
        import spec_stop_guard as g

        monkeypatch.setenv("PILOT_SESSION_ID", "build-handback-test")
        monkeypatch.setattr(g, "_sessions_base", lambda: tmp_path / "sessions")
        plan = tmp_path / "buildout.md"
        plan.write_text(
            "# X Buildout\nStatus: PENDING\nApproved: "
            + ("Yes" if approved else "No")
            + f"\nType: {plan_type}\n\n## Progress Tracking\n- [ ] Task 1: draft the hero\n"
        )
        monkeypatch.setattr(g, "find_active_plan", lambda *_args: (plan, "PENDING"))
        monkeypatch.setattr(g, "is_waiting_for_user_input", lambda _p: False)

        sentinel = g.get_build_handback_sentinel_path()
        sentinel.write_text("")
        if age:
            stamp = time.time() - age
            os.utime(sentinel, (stamp, stamp))

        stdin = io.StringIO(json.dumps({"stop_hook_active": False, "transcript_path": ""}))
        with patch("sys.stdin", stdin):
            code = g.main()
        return code, sentinel

    def test_allows_one_stop_for_an_approved_buildout(self, tmp_path, monkeypatch):
        code, sentinel = self._run_with_sentinel(tmp_path, monkeypatch, approved=True)
        assert code == 0
        assert not sentinel.exists()  # one-shot: consumed on honor

    def test_second_stop_is_blocked_again(self, tmp_path, monkeypatch):
        """One-shot means the very next ordinary stop re-engages the loop block."""
        import spec_stop_guard as g

        self._run_with_sentinel(tmp_path, monkeypatch, approved=True)

        plan = tmp_path / "buildout.md"
        monkeypatch.setattr(g, "find_active_plan", lambda *_args: (plan, "PENDING"))
        monkeypatch.setattr(g, "is_waiting_for_user_input", lambda _p: False)
        stdin = io.StringIO(json.dumps({"stop_hook_active": False, "transcript_path": ""}))
        with patch("sys.stdin", stdin), patch("sys.stdout", new_callable=io.StringIO) as out:
            g.main()
        assert _is_blocked(out.getvalue())

    def test_not_honored_for_an_unapproved_buildout(self, tmp_path, monkeypatch):
        """Pre-approval pauses use the approval sentinel; this one must not bypass them."""
        code, sentinel = self._run_with_sentinel(tmp_path, monkeypatch, approved=False)
        assert code != 0 or sentinel.exists()

    def test_not_honored_for_a_feature_plan(self, tmp_path, monkeypatch):
        """/spec has no hand-back pause -- a stray sentinel must not free its implement loop."""
        code, sentinel = self._run_with_sentinel(tmp_path, monkeypatch, approved=True, plan_type="Feature")
        assert code != 0 or sentinel.exists()

    def test_stale_sentinel_discarded(self, tmp_path, monkeypatch):
        import spec_stop_guard as g

        _code, sentinel = self._run_with_sentinel(
            tmp_path, monkeypatch, approved=True, age=g.SENTINEL_MAX_AGE_SECONDS + 60
        )
        assert not sentinel.exists()  # discarded, not honored


class TestVerifyGateSentinel:
    """The verify-gate-pending sentinel lets a verify-phase gate yield for an agent
    that cannot emit AskUserQuestion.

    /spec's merge gate (spec-verify 8.1.6, spec-bugfix-verify 4.5) and its code-review
    gate (spec-verify 10, spec-bugfix-verify 6) both run with the plan at
    ``Approved: Yes`` + ``Status: COMPLETE``, and none of the other three sentinels
    covers that state: spec-approval-pending needs ``Approved: No`` and
    build-handback-pending needs ``Type: Build``. So an orchestration lane -- a Claude Code
    subagent, which has no AskUserQuestion at all -- had no legal way to pause at
    either gate, and resolved it by answering its own gate or halting silently
    (issue #175). Adding the gate prose without this sentinel only relocates the
    deadlock: the lane asks correctly, yields, and is blocked anyway.

    Retained through the yield so UserPromptSubmit can distinguish the expected
    gate answer from an unrelated mid-implementation interruption. That prompt
    consumes it before the agent continues.

    The sentinel path is built literally rather than through the accessor: what is
    under test is the guard's BEHAVIOUR given the file, not the presence of a helper.
    """

    def _run(  # noqa: PLR0913
        self,
        tmp_path,
        monkeypatch,
        *,
        approved: bool = True,
        status: str = "COMPLETE",
        plan_type: str = "Feature",
        write_sentinel: bool = True,
        transcript_text: str | None = None,
    ):
        import spec_stop_guard as g

        monkeypatch.setenv("PILOT_SESSION_ID", "verify-gate-test")
        monkeypatch.setattr(g, "_sessions_base", lambda: tmp_path / "sessions")
        plan = tmp_path / "plan.md"
        plan.write_text(f"# X\nStatus: {status}\nApproved: " + ("Yes" if approved else "No") + f"\nType: {plan_type}\n")
        monkeypatch.setattr(g, "find_active_plan", lambda *_args: (plan, status))
        monkeypatch.setattr(g, "is_waiting_for_user_input", lambda _p: False)

        session_dir = tmp_path / "sessions" / "verify-gate-test"
        session_dir.mkdir(parents=True, exist_ok=True)
        sentinel = session_dir / "verify-gate-pending"
        if write_sentinel:
            sentinel.write_text("")

        transcript = tmp_path / "transcript.jsonl"
        if transcript_text is not None:
            transcript.write_text(
                json.dumps(
                    {
                        "type": "assistant",
                        "message": {"content": [{"type": "text", "text": transcript_text}]},
                    }
                )
                + "\n"
            )

        stdin = io.StringIO(
            json.dumps(
                {
                    "stop_hook_active": False,
                    "transcript_path": str(transcript) if transcript_text is not None else "",
                }
            )
        )
        with patch("sys.stdin", stdin), patch("sys.stdout", new_callable=io.StringIO) as out:
            code = g.main()
        return code, sentinel, out.getvalue()

    def test_allows_a_stop_at_a_verify_gate(self, tmp_path, monkeypatch):
        """The bug: a lane pausing at the merge or review gate must be able to stop."""
        code, sentinel, stdout = self._run(tmp_path, monkeypatch)

        assert code == 0
        assert not _is_blocked(stdout), "a verify-phase gate must be able to yield for the user's answer"
        assert sentinel.exists(), "the expected-response marker must survive until UserPromptSubmit"
        binding = json.loads(sentinel.read_text())
        assert binding["expected_status"] == "COMPLETE"

    def test_does_not_release_the_implement_phase(self, tmp_path, monkeypatch):
        """Status gate: a PENDING plan is mid-implementation, where stopping is the bug."""
        _code, _sentinel, stdout = self._run(tmp_path, monkeypatch, status="PENDING")

        assert _is_blocked(stdout), "the implement-phase block must survive a stray verify-gate sentinel"

    def test_does_not_release_a_build_loop(self, tmp_path, monkeypatch):
        """Type gate: /build has no gates after its scoping round, so it has none to yield at."""
        _code, _sentinel, stdout = self._run(tmp_path, monkeypatch, plan_type="Build")

        assert _is_blocked(stdout), "a Buildout must not be released by a gate sentinel it never writes"

    def test_gate_keeps_yielding_until_the_user_response_arrives(self, tmp_path, monkeypatch):
        """The marker remains valid while the same gate is awaiting its answer."""
        self._run(tmp_path, monkeypatch)

        _code, _sentinel, stdout = self._run(tmp_path, monkeypatch, write_sentinel=False)

        assert not _is_blocked(stdout)

    def test_narrow_review_question_auto_arms_missing_sentinel(self, tmp_path, monkeypatch):
        _code, sentinel, stdout = self._run(
            tmp_path,
            monkeypatch,
            write_sentinel=False,
            transcript_text=(
                "## Verification Summary\n\nAll checks passed.\n\n"
                "Do you approve this result so I can mark the plan VERIFIED?"
            ),
        )

        assert not _is_blocked(stdout)
        assert sentinel.exists()
        assert json.loads(sentinel.read_text())["expected_status"] == "COMPLETE"

    def test_ordinary_complete_status_summary_does_not_bypass_guard(self, tmp_path, monkeypatch):
        _code, sentinel, stdout = self._run(
            tmp_path,
            monkeypatch,
            write_sentinel=False,
            transcript_text="Implementation summary: everything looks good.",
        )

        assert _is_blocked(stdout)
        assert not sentinel.exists()


class TestLegacyDiscussionPauseMarker:
    """Legacy marker files no longer bypass the Stop guard directly."""

    def test_marker_alone_does_not_grant_a_stop(self, tmp_path, monkeypatch):
        import spec_stop_guard as g

        session_id = "legacy-discussion-pause-test"
        monkeypatch.setenv("PILOT_SESSION_ID", session_id)
        monkeypatch.setattr(g, "_sessions_base", lambda: tmp_path / "sessions")
        plan = tmp_path / "plan.md"
        plan.write_text("# X\nStatus: PENDING\nApproved: Yes\nType: Feature\n")
        monkeypatch.setattr(g, "find_active_plan", lambda *_args: (plan, "PENDING"))
        monkeypatch.setattr(g, "is_waiting_for_user_input", lambda _p: False)
        session = tmp_path / "sessions" / session_id
        session.mkdir(parents=True)
        (session / "spec-discussion-paused").write_text("")

        stdin = io.StringIO(json.dumps({"stop_hook_active": False, "transcript_path": ""}))
        with patch("sys.stdin", stdin), patch("sys.stdout", new_callable=io.StringIO) as out:
            g.main()

        assert _is_blocked(out.getvalue())


class TestDurableInteractionState:
    """A registered pause is authoritative even inside a Stop continuation."""

    def _run(self, tmp_path: Path, monkeypatch, *, stop_hook_active: bool) -> str:
        import spec_stop_guard as g

        session_id = "durable-interaction-test"
        monkeypatch.setenv("PILOT_SESSION_ID", session_id)
        monkeypatch.setattr(g, "_sessions_base", lambda: tmp_path / "sessions")
        plan = tmp_path / "plan.md"
        plan.write_text("# X\nStatus: PENDING\nApproved: Yes\nType: Feature\n")
        session = tmp_path / "sessions" / session_id
        session.mkdir(parents=True)
        (session / "active_plan.json").write_text(
            json.dumps(
                {
                    "plan_path": str(plan),
                    "status": "PENDING",
                    "interaction": {"state": "paused", "kind": "discussion"},
                }
            )
        )
        monkeypatch.setattr(g, "find_active_plan", lambda *_args: (plan, "PENDING"))
        monkeypatch.setattr(g, "is_waiting_for_user_input", lambda _p: False)

        stdin = io.StringIO(json.dumps({"stop_hook_active": stop_hook_active, "transcript_path": ""}))
        with patch("sys.stdin", stdin), patch("sys.stdout", new_callable=io.StringIO) as out:
            g.main()
        return out.getvalue()

    def test_pause_allows_stop_inside_continuation(self, tmp_path: Path, monkeypatch) -> None:
        assert not _is_blocked(self._run(tmp_path, monkeypatch, stop_hook_active=True))

    def test_pause_allows_fresh_stop_too(self, tmp_path: Path, monkeypatch) -> None:
        assert not _is_blocked(self._run(tmp_path, monkeypatch, stop_hook_active=False))


class TestPayloadSessionIdIsolation:
    """Session isolation when the hook subprocess inherits no session env vars.

    Reported failure: an ordinary task in this repo was repeatedly blocked by a
    months-old COMPLETE plan left in ``~/.pilot/sessions/default/active_plan.json``.
    The hook parsed the Stop payload but located session state purely through
    ``resolve_session_id()``, which reads the env chain and collapses to the shared
    ``default`` bucket when none of PILOT_SESSION_ID / CLAUDE_CODE_SESSION_ID /
    CODEX_THREAD_ID is set. ``plan_in_current_project()`` could not reject the stale
    plan because it lived in the SAME repo as the current task, so the guard injected
    verification instructions for months-old unrelated work.
    """

    SESSION_ENV = ("PILOT_SESSION_ID", "CLAUDE_CODE_SESSION_ID", "CODEX_THREAD_ID")

    def _run(self, input_data: dict, plans_dir: Path, env_overrides: dict) -> tuple[int, str, str]:
        """Run the hook with the session env chain cleared, then selectively restored."""
        env = {k: v for k, v in os.environ.items() if k not in self.SESSION_ENV}
        env.update(env_overrides)
        result = subprocess.run(
            [sys.executable, str(HOOK_PATH)],
            input=json.dumps(input_data),
            capture_output=True,
            text=True,
            cwd=str(plans_dir.parent.parent),
            env=env,
        )
        return result.returncode, result.stdout, result.stderr

    def _register(self, session_id: str, plan_path: Path, status: str) -> None:
        session_dir = Path.home() / ".pilot" / "sessions" / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        (session_dir / "active_plan.json").write_text(json.dumps({"plan_path": str(plan_path), "status": status}))

    def _make_project(self, tmp_path: Path) -> tuple[Path, Path]:
        project = tmp_path / "current-project"
        plans_dir = project / "docs" / "plans"
        plans_dir.mkdir(parents=True)
        return project, plans_dir

    def test_stale_default_plan_ignored_when_payload_names_another_session(self, tmp_path: Path) -> None:
        """The reported bug: a stale same-repo plan under the shared 'default'
        session must not block a stop for the session named in the payload."""
        project, plans_dir = self._make_project(tmp_path)
        stale = plans_dir / "2026-05-26-hello-world.md"
        stale.write_text("# Hello World\n\nStatus: COMPLETE\nApproved: Yes\nType: Feature\n")
        self._register("default", stale, "COMPLETE")

        code, stdout, _ = self._run(
            {"stop_hook_active": False, "session_id": "current-session"},
            plans_dir,
            {"CLAUDE_PROJECT_ROOT": str(project)},
        )

        assert code == 0
        assert not _is_blocked(stdout), (
            "a plan registered under the shared 'default' session must not block a stop "
            "for the different session named in the hook payload"
        )

    def test_payload_session_id_used_when_env_absent(self, tmp_path: Path) -> None:
        """Not over-suppression: with the env chain empty, the payload session id must
        still locate THIS session's own active plan and block."""
        project, plans_dir = self._make_project(tmp_path)
        plan = plans_dir / "2026-08-07-current.md"
        plan.write_text("# Current\n\nStatus: PENDING\nApproved: Yes\nType: Feature\n")
        self._register("current-session", plan, "PENDING")

        code, stdout, _ = self._run(
            {"stop_hook_active": False, "session_id": "current-session"},
            plans_dir,
            {"CLAUDE_PROJECT_ROOT": str(project)},
        )

        assert code == 0
        assert _is_blocked(stdout), (
            "with the env chain empty the payload session id must still find this session's own active plan"
        )

    def test_env_session_id_wins_over_payload(self, tmp_path: Path) -> None:
        """The legacy wrapper id remains authoritative when no native id exists.

        PILOT_SESSION_ID is a shell ``$$-$RANDOM`` id (installer/steps/shell_config.py)
        and is the id ``pilot register-plan`` wrote active_plan.json under
        (launcher/session.py:get_session_dir). The payload carries the agent's own
        UUID, a deliberately different value. Making the payload authoritative would
        point the guard at a directory the writer never used, silently disabling the
        /spec and /build stop guard on every wrapper-launched session.
        """
        project, plans_dir = self._make_project(tmp_path)
        plan = plans_dir / "2026-08-07-wrapper-session.md"
        plan.write_text("# Wrapper\n\nStatus: PENDING\nApproved: Yes\nType: Feature\n")
        self._register("84532-19274", plan, "PENDING")

        code, stdout, _ = self._run(
            {"stop_hook_active": False, "session_id": "fedf281c-1710-4a51-91fd-b489b62b8e48"},
            plans_dir,
            {"CLAUDE_PROJECT_ROOT": str(project), "PILOT_SESSION_ID": "84532-19274"},
        )

        assert code == 0
        assert _is_blocked(stdout), (
            "the env-resolved session id is what the plan writer used; the payload must "
            "not override it or the guard goes blind on wrapper-launched sessions"
        )

    def test_payload_wins_over_mismatched_native_parent_id(self, tmp_path: Path) -> None:
        """A nested Codex hook inherits its parent's thread id while its payload
        identifies the child turn whose agent command registered the plan."""
        project, plans_dir = self._make_project(tmp_path)
        plan = plans_dir / "2026-09-09-child-thread.md"
        plan.write_text("# Child\n\nStatus: PENDING\nApproved: Yes\nType: Feature\n")
        self._register("child-thread", plan, "PENDING")

        code, stdout, _ = self._run(
            {"stop_hook_active": False, "session_id": "child-thread"},
            plans_dir,
            {
                "CLAUDE_PROJECT_ROOT": str(project),
                "CODEX_THREAD_ID": "parent-thread",
            },
        )

        assert code == 0
        assert _is_blocked(stdout)

    def test_wrapper_registered_plan_is_missed_when_env_chain_lost(self, tmp_path: Path) -> None:
        """KNOWN GAP, characterized deliberately -- this asserts current behaviour, not
        desired behaviour.

        When the WRITER had the wrapper env (plan registered under the "$$-$RANDOM"
        PILOT_SESSION_ID) but the hook subprocess then loses the entire env chain, the
        guard cannot find that plan under any id it can still see, so it fails open
        during an active workflow.

        The payload fallback does not close this: the payload carries the agent's UUID,
        which is not the id the wrapper wrote under. Verified identical before and after
        the payload-fallback fix by running both hook copies against this exact scenario
        -- it is pre-existing, not introduced here, and the fix is neutral on it.

        Closing it needs a durable native-id -> wrapper-id alias persisted at
        registration time, which spans the Cython-compiled launcher package and is a
        /spec-sized change rather than part of this bugfix.

        When that alias lands, this test SHOULD start failing -- flip it to assert
        _is_blocked and delete this docstring.
        """
        project, plans_dir = self._make_project(tmp_path)
        plan = plans_dir / "2026-08-07-wrapper-registered.md"
        plan.write_text("# Wrapper Registered\n\nStatus: PENDING\nApproved: Yes\nType: Feature\n")
        self._register("84532-19274", plan, "PENDING")

        code, stdout, _ = self._run(
            {"stop_hook_active": False, "session_id": "0bb9316a-e467-44ff-a5e9-387caf7dc5f7"},
            plans_dir,
            {"CLAUDE_PROJECT_ROOT": str(project)},
        )

        assert code == 0
        assert not _is_blocked(stdout), (
            "characterization of the known identity-loss gap: with the wrapper id gone "
            "from the env and only the agent UUID in the payload, no reachable id points "
            "at the directory register-plan wrote under"
        )


class TestLaneRegisteredPlansDoNotBlockTheCoordinator:
    """Issue #174 defect 1, stated as behaviour.

    A coordinating session dispatches /spec and /build lanes as subagents. Their
    hook payloads are byte-identical to the parent's, so before lane scoping every
    lane's `pilot register-plan` landed in the coordinator's own active_plan.json -
    and this guard then blocked the COORDINATOR's every stop attempt, telling it to
    "IMMEDIATELY continue working" on a plan a live agent owns in another checkout.

    The fix is that the guard keeps reading only sessions/<id>/active_plan.json.
    These tests pin BOTH directions, so the guard cannot be "fixed" by disabling it.
    """

    def _plan(self, tmp_path: Path) -> tuple[Path, Path]:
        plans_dir = tmp_path / "docs" / "plans"
        plans_dir.mkdir(parents=True)
        plan_file = plans_dir / "2026-08-11-lane-plan.md"
        plan_file.write_text("# Lane Plan\n\nStatus: PENDING\nApproved: Yes\n")
        return plans_dir, plan_file

    def test_a_lanes_pending_plan_does_not_block_the_coordinator(self, tmp_path: Path) -> None:
        plans_dir, plan_file = self._plan(tmp_path)

        lane_dir = _test_session_dir() / "lanes" / "alpha"
        lane_dir.mkdir(parents=True, exist_ok=True)
        (lane_dir / "active_plan.json").write_text(json.dumps({"plan_path": str(plan_file), "status": "PENDING"}))

        exit_code, stdout, _ = _run_subprocess({"stop_hook_active": False}, plans_dir)

        assert exit_code == 0
        assert not _is_blocked(stdout), (
            "the coordinator was blocked over a plan a lane registered - it does not "
            "own that plan and must not be told to continue working on it"
        )

    def test_the_same_plan_registered_without_a_lane_still_blocks(self, tmp_path: Path) -> None:
        """The control. Without it, deleting the guard entirely would pass the test above."""
        plans_dir, plan_file = self._plan(tmp_path)
        _register_plan_for_session(plan_file, "PENDING")

        exit_code, stdout, _ = _run_subprocess({"stop_hook_active": False}, plans_dir)

        assert exit_code == 0
        assert _is_blocked(stdout)


class TestOneSessionsPlanDoesNotBlockAnother:
    """The community report, stated as behaviour.

    "I have a plan registered in session 1 and I am preparing something else in
    session 2, same repo directory, no worktrees -- the hooks trigger on both."

    Every plan reader is session-scoped through `resolve_session_id` (the issue
    #157 env chain), so session B reads its OWN `active_plan.json` and finds
    nothing. These tests pin BOTH directions so the guard cannot be "fixed" by
    disabling it. State lives under the per-test HOME the autouse fixture sets.
    """

    def _plan(self, tmp_path: Path) -> Path:
        plans_dir = tmp_path / "docs" / "plans"
        plans_dir.mkdir(parents=True, exist_ok=True)
        plan_file = plans_dir / "2026-08-24-session-a-plan.md"
        plan_file.write_text("# A\n\nStatus: PENDING\nApproved: Yes\nType: Feature\n")
        return plan_file

    def _register(self, session_id: str, plan_file: Path) -> None:
        session_dir = Path.home() / ".pilot" / "sessions" / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        (session_dir / "active_plan.json").write_text(json.dumps({"plan_path": str(plan_file), "status": "PENDING"}))

    def _run_as(self, session_id: str) -> str:
        import spec_stop_guard as g

        with (
            patch.dict(os.environ, {"PILOT_SESSION_ID": session_id}),
            patch.object(g, "is_waiting_for_user_input", lambda _p: False),
            patch.object(g, "plan_in_current_project", lambda _p: True),
            patch("sys.stdin", io.StringIO(json.dumps({"stop_hook_active": False, "transcript_path": ""}))),
            patch("sys.stdout", new_callable=io.StringIO) as out,
        ):
            g.main()
        return out.getvalue()

    def test_session_b_is_not_blocked_by_session_as_plan(self, tmp_path):
        self._register("session-a", self._plan(tmp_path))

        assert not _is_blocked(self._run_as("session-b")), (
            "session B was told to keep working on a plan session A owns - the "
            "multi-session cross-talk from the community report"
        )

    def test_shared_wrapper_id_does_not_override_native_session_ids(self, tmp_path):
        """Two conversations may inherit one wrapper id, but their native ids differ."""
        from launcher.session import register_plan

        plan = self._plan(tmp_path)
        with (
            patch.dict(
                os.environ,
                {
                    "PILOT_SESSION_ID": "shared-wrapper",
                    "CLAUDE_CODE_SESSION_ID": "session-a-native",
                    "CODEX_THREAD_ID": "",
                    "CLAUDE_PROJECT_ROOT": str(tmp_path),
                },
            ),
            patch("launcher.session._notify_plan_transition"),
        ):
            register_plan(str(plan), "PENDING")

        code, stdout, _ = TestPayloadSessionIdIsolation()._run(
            {"stop_hook_active": False, "session_id": "session-b-native"},
            plan.parent,
            {
                "CLAUDE_PROJECT_ROOT": str(tmp_path),
                "PILOT_SESSION_ID": "shared-wrapper",
                "CLAUDE_CODE_SESSION_ID": "session-b-native",
            },
        )

        assert code == 0
        assert not _is_blocked(stdout), (
            "session B inherited session A's wrapper id and was told to continue session A's registered plan"
        )

    def test_native_session_does_not_claim_ambiguous_legacy_wrapper_plan(self, tmp_path):
        """A pre-upgrade wrapper-only registration has no safely recoverable owner."""
        plan = self._plan(tmp_path)
        self._register("shared-wrapper", plan)

        code, stdout, _ = TestPayloadSessionIdIsolation()._run(
            {"stop_hook_active": False, "session_id": "session-b-native"},
            plan.parent,
            {
                "CLAUDE_PROJECT_ROOT": str(tmp_path),
                "PILOT_SESSION_ID": "shared-wrapper",
                "CLAUDE_CODE_SESSION_ID": "session-b-native",
            },
        )

        assert code == 0
        assert not _is_blocked(stdout), (
            "an ownerless legacy wrapper plan must not be assigned to an arbitrary "
            "native session; the next register-plan call creates native-owned state"
        )

    def test_the_same_plan_registered_under_bs_own_id_does_block(self, tmp_path):
        """The control. Without it, deleting the guard would pass the test above."""
        self._register("session-b", self._plan(tmp_path))

        assert _is_blocked(self._run_as("session-b"))
