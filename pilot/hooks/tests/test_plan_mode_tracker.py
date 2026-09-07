"""Tests for plan_mode_tracker hook."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from plan_mode_tracker import is_plan_file, main


def _run_main(stdin_data: dict, session_dir: Path, awaiting_approval: bool = False) -> tuple[int, str]:
    """Run main() with patched session dir and stdin, return (exit_code, stdout)."""
    with (
        patch("plan_mode_tracker._sessions_base", return_value=session_dir),
        patch("_lib.util._sessions_base", return_value=session_dir),
        patch("native_plan_capture._sessions_base", return_value=session_dir),
        patch("plan_mode_tracker.resolve_session_id", return_value="test-session"),
        patch("plan_mode_tracker.read_hook_stdin", return_value=stdin_data),
        patch("plan_mode_tracker.spec_plan_awaiting_approval", return_value=awaiting_approval),
    ):
        import io
        from contextlib import redirect_stdout

        buf = io.StringIO()
        with redirect_stdout(buf):
            code = main()
        return code, buf.getvalue()


class TestIsPlanFile:
    def test_plan_md_is_plan_file(self):
        assert is_plan_file("docs/plans/2026-06-03-my-plan.md") is True

    def test_nested_plans_dir(self):
        assert is_plan_file("/home/user/repo/docs/plans/foo.md") is True

    def test_buildout_md_is_plan_file(self):
        """`/build` Buildouts live in docs/builds/ and are plan docs too."""
        assert is_plan_file("docs/builds/2026-08-10-running-brand.md") is True

    def test_implementation_ts_is_not_plan(self):
        assert is_plan_file("src/components/hero.tsx") is False

    def test_json_in_plans_dir_is_not_plan(self):
        assert is_plan_file("docs/plans/data.json") is False

    def test_md_outside_plans_is_not_plan(self):
        assert is_plan_file("README.md") is False


class TestSentinelTracking:
    def test_enter_plan_mode_writes_sentinel(self, tmp_path):
        stdin = {
            "tool_name": "EnterPlanMode",
            "tool_input": {},
            "tool_response": {"result": "ok"},
        }
        code, _ = _run_main(stdin, tmp_path)
        assert code == 0
        assert (tmp_path / "test-session" / "plan-mode-active").exists()

    def test_enter_plan_mode_skips_sentinel_on_error(self, tmp_path):
        stdin = {
            "tool_name": "EnterPlanMode",
            "tool_input": {},
            "tool_response": {"is_error": True},
        }
        _run_main(stdin, tmp_path)
        assert not (tmp_path / "test-session" / "plan-mode-active").exists()

    def test_unconfirmed_enter_does_not_create_an_active_leg(self, tmp_path):
        for response in (None, "unknown response"):
            _run_main({"tool_name": "EnterPlanMode", "tool_input": {}, "tool_response": response}, tmp_path)
            assert not (tmp_path / "test-session" / "plan-mode-active").exists()

    def test_enter_clears_a_stale_bypass_restore_marker(self, tmp_path):
        marker = tmp_path / "test-session" / "bypass-restore-pending"
        marker.parent.mkdir(parents=True)
        marker.write_text("")

        _run_main({"tool_name": "EnterPlanMode", "tool_input": {}, "permission_mode": "default"}, tmp_path)

        assert not marker.exists()

    def test_pre_enter_plan_mode_records_permission_mode(self, tmp_path):
        """PreToolUse(EnterPlanMode) fires before the mode flips to plan, so
        the observed permission_mode is the pre-plan mode - the bypass
        evidence auto_approve_plan needs to arm the post-exit restore."""
        stdin = {
            "tool_name": "EnterPlanMode",
            "tool_input": {},
            "permission_mode": "bypassPermissions",
        }
        code, out = _run_main(stdin, tmp_path)
        assert code == 0
        assert out == ""
        record = tmp_path / "test-session" / "pre-plan-permission-mode"
        assert record.read_text() == "bypassPermissions"

    def test_pre_enter_plan_mode_records_who_owns_the_leg(self, tmp_path):
        """The leg's owner is decided at ENTRY, because exit cannot tell.

        At Step 12.3 a /spec plan is PENDING + `Approved: Yes` - identical to an
        approved plan the model opened native plan mode on top of during
        implementation, and to a locked Buildout. Reading the run state at exit
        answered "a run exists" for all three and handed native plan mode to the
        /spec code path. Entry separates them cleanly.
        """
        session_dir = tmp_path / "sessions" / "test-session"
        session_dir.mkdir(parents=True)
        plans_dir = tmp_path / "project" / "docs" / "plans"
        plans_dir.mkdir(parents=True)
        stdin = {"tool_name": "EnterPlanMode", "tool_input": {}, "permission_mode": "bypassPermissions"}
        record = session_dir / "plan-leg-owner"

        def register(status: str, approved: str, plan_type: str) -> None:
            plan = plans_dir / f"2026-09-02-{plan_type.lower()}.md"
            plan.write_text(f"# P\n\nStatus: {status}\nApproved: {approved}\nType: {plan_type}\n")
            (session_dir / "active_plan.json").write_text(json.dumps({"plan_path": str(plan), "status": status}))

        with patch.dict(os.environ, {"CLAUDE_PROJECT_ROOT": str(tmp_path / "project")}):
            # Nothing registered yet: spec-plan Step 0.1a runs before Step 2's
            # register-plan, so this is a fresh /spec planning leg.
            _run_main(stdin, tmp_path / "sessions")
            assert record.read_text() == "pilot-planning"

            # A plan still in its planning phase: /spec resuming it, which
            # registers at the dispatcher before entering plan mode.
            register("PENDING", "No", "Feature")
            _run_main(stdin, tmp_path / "sessions")
            assert record.read_text() == "pilot-planning"

            # Approved and being implemented: this plan mode is somebody else's.
            register("PENDING", "Yes", "Feature")
            _run_main(stdin, tmp_path / "sessions")
            assert record.read_text() == "native"

            # A Buildout locks `Approved: Yes` with no user sign-off and never
            # enters plan mode at all - the case that let a native plan be
            # auto-approved inside a running /build.
            register("PENDING", "Yes", "Build")
            _run_main(stdin, tmp_path / "sessions")
            assert record.read_text() == "native"

    def test_pre_enter_plan_mode_without_mode_clears_stale_record(self, tmp_path):
        """No permission_mode field (older Claude Code) -> clear any stale
        record so a previous leg's evidence cannot arm a later restore."""
        record = tmp_path / "test-session" / "pre-plan-permission-mode"
        record.parent.mkdir(parents=True)
        record.write_text("bypassPermissions")
        stdin = {"tool_name": "EnterPlanMode", "tool_input": {}}
        code, out = _run_main(stdin, tmp_path)
        assert code == 0
        assert out == ""
        assert not record.exists()

    def test_exit_plan_mode_deletes_sentinel(self, tmp_path):
        sentinel = tmp_path / "test-session" / "plan-mode-active"
        sentinel.parent.mkdir(parents=True)
        sentinel.write_text("")

        stdin = {
            "tool_name": "ExitPlanMode",
            "tool_input": {},
            "tool_response": {"result": "ok"},
        }
        code, _ = _run_main(stdin, tmp_path)
        assert code == 0
        assert not sentinel.exists()

    def test_exit_plan_mode_no_error_if_sentinel_missing(self, tmp_path):
        stdin = {
            "tool_name": "ExitPlanMode",
            "tool_input": {},
            "tool_response": {"result": "ok"},
        }
        code, _ = _run_main(stdin, tmp_path)
        assert code == 0

    def test_exit_plan_mode_keeps_sentinel_on_unconfirmed_error(self, tmp_path):
        sentinel = tmp_path / "test-session" / "plan-mode-active"
        sentinel.parent.mkdir(parents=True)
        sentinel.write_text("")

        stdin = {
            "tool_name": "ExitPlanMode",
            "tool_input": {},
            "tool_response": {"is_error": True},
        }
        code, _ = _run_main(stdin, tmp_path)
        assert code == 0
        assert sentinel.exists(), "a failed ExitPlanMode does not prove plan mode ended"

    def test_exit_plan_mode_clears_sentinel_when_runtime_confirms_mode_already_closed(self, tmp_path):
        sentinel = tmp_path / "test-session" / "plan-mode-active"
        sentinel.parent.mkdir(parents=True)
        sentinel.write_text("")
        code, _ = _run_main(
            {
                "tool_name": "ExitPlanMode",
                "tool_input": {},
                "tool_response": {"is_error": True, "message": "Not in plan mode"},
            },
            tmp_path,
        )
        assert code == 0
        assert not sentinel.exists()


class TestPreToolUseWarning:
    def test_warns_for_impl_file_when_sentinel_active(self, tmp_path):
        sentinel = tmp_path / "test-session" / "plan-mode-active"
        sentinel.parent.mkdir(parents=True)
        sentinel.write_text("")

        stdin = {"tool_name": "Edit", "tool_input": {"file_path": "src/auth.ts"}}
        code, stdout = _run_main(stdin, tmp_path)
        assert code == 0
        data = json.loads(stdout)
        context = data["hookSpecificOutput"]["additionalContext"]
        assert "ExitPlanMode" in context
        assert "PLAN MODE" in context

    def test_no_warn_for_plan_file_when_sentinel_active(self, tmp_path):
        sentinel = tmp_path / "test-session" / "plan-mode-active"
        sentinel.parent.mkdir(parents=True)
        sentinel.write_text("")

        stdin = {"tool_name": "Write", "tool_input": {"file_path": "docs/plans/2026-06-03-my-plan.md"}}
        code, stdout = _run_main(stdin, tmp_path)
        assert code == 0
        assert stdout.strip() == ""

    def test_no_warn_when_sentinel_absent(self, tmp_path):
        stdin = {"tool_name": "Edit", "tool_input": {"file_path": "src/auth.ts"}}
        code, stdout = _run_main(stdin, tmp_path)
        assert code == 0
        assert stdout.strip() == ""

    def test_no_warn_when_no_file_path(self, tmp_path):
        sentinel = tmp_path / "test-session" / "plan-mode-active"
        sentinel.parent.mkdir(parents=True)
        sentinel.write_text("")

        stdin = {"tool_name": "Edit", "tool_input": {}}
        _, stdout = _run_main(stdin, tmp_path)
        assert stdout.strip() == ""

    def test_sibling_sentinel_in_default_bucket_does_not_warn_identified_session(self, tmp_path):
        """Same-repo sibling bleed: a plan-mode sentinel another (env-less) session
        left in the shared 'default' bucket must not fire "PLAN MODE STILL ACTIVE"
        warnings on every edit of a session whose hook payload carries its own
        session_id and never entered plan mode."""
        import io
        from contextlib import redirect_stdout

        import _lib.util as util

        sessions = tmp_path / "sessions"
        (sessions / "default").mkdir(parents=True)
        (sessions / "default" / "plan-mode-active").write_text("")

        stdin_data = {
            "tool_name": "Edit",
            "tool_input": {"file_path": "src/auth.ts"},
            "session_id": "session-b-uuid",
        }
        with (
            patch("plan_mode_tracker._sessions_base", return_value=sessions),
            patch.object(util, "_sessions_base", return_value=sessions),
            patch("plan_mode_tracker.read_hook_stdin", return_value=stdin_data),
            patch.dict(os.environ, {}, clear=True),
        ):
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = main()

        assert code == 0
        assert buf.getvalue().strip() == "", (
            "a sibling session's plan-mode sentinel in the shared 'default' bucket "
            "must not warn a session that carries its own session_id"
        )

    def test_pre_approval_warning_while_plan_awaits_approval(self, tmp_path):
        """While the spec plan is unapproved, the warning must NOT instruct
        calling ExitPlanMode (auto_approve_plan denies it in that window) but
        must still fire as an edit-time tripwire pointing at the approval gate.
        """
        sentinel = tmp_path / "test-session" / "plan-mode-active"
        sentinel.parent.mkdir(parents=True)
        sentinel.write_text("")

        stdin = {"tool_name": "Edit", "tool_input": {"file_path": "src/auth.ts"}}
        code, stdout = _run_main(stdin, tmp_path, awaiting_approval=True)
        assert code == 0
        data = json.loads(stdout)
        context = data["hookSpecificOutput"]["additionalContext"]
        assert "NOT APPROVED" in context
        assert "Call ExitPlanMode NOW" not in context


class TestPlanningLegModelCheck:
    """Observed-model verification for the /spec planning leg.

    Automated mode only: plan mode under opusplan must run on Opus. Claude
    Code can silently serve the Sonnet leg instead (usage-limit fallback, a
    conversation grown past Opus's effective window, or the session was never
    on opusplan). The hook verifies the observed model from the statusline
    cache at the first plan-file write after EnterPlanMode and warns once per
    planning leg.
    """

    PLAN_WRITE = {"tool_name": "Write", "tool_input": {"file_path": "docs/plans/2026-07-06-fix.md"}}

    def _setup_leg(self, tmp_path, model_id, cache_fresh=True):
        """Create sentinel + statusline cache; cache render post-dates the sentinel unless stale."""
        session = tmp_path / "test-session"
        session.mkdir(parents=True, exist_ok=True)
        sentinel = session / "plan-mode-active"
        sentinel.write_text("")
        os.utime(sentinel, (1_000_000, 1_000_000))
        cache = session / "context-pct.json"
        cache.write_text(json.dumps({"model_id": model_id}))
        stamp = 1_000_100 if cache_fresh else 999_900
        os.utime(cache, (stamp, stamp))
        return session

    def _run(self, tmp_path, mode="automated"):
        with patch("plan_mode_tracker.read_model_switch_mode", return_value=mode):
            return _run_main(self.PLAN_WRITE, tmp_path)

    def test_warns_when_planning_leg_not_on_opus(self, tmp_path):
        session = self._setup_leg(tmp_path, "claude-sonnet-5")
        code, stdout = self._run(tmp_path)
        assert code == 0
        context = json.loads(stdout)["hookSpecificOutput"]["additionalContext"]
        assert "NOT running on Opus" in context
        assert "claude-sonnet-5" in context
        assert "/model opusplan" in context
        assert "usage limit" in context.lower()
        assert "Manual" in context
        assert "200K" not in context
        assert "cause is not established" in context
        assert (session / "plan-model-warned").exists()

    def test_confirms_when_planning_leg_on_opus(self, tmp_path):
        """A successful switch must be reported, not silent.

        Claude Code prints nothing of its own when opusplan upgrades the plan
        leg, so silence here is indistinguishable from a failed switch - which
        is exactly how a working switch gets reported as broken.
        """
        session = self._setup_leg(tmp_path, "claude-opus-5[1m]")
        code, stdout = self._run(tmp_path)
        assert code == 0
        context = json.loads(stdout)["hookSpecificOutput"]["additionalContext"]
        assert "claude-opus-5[1m]" in context
        assert "NOT running on Opus" not in context
        assert (session / "plan-model-confirmed").exists()

    def test_confirms_only_once_per_planning_leg(self, tmp_path):
        self._setup_leg(tmp_path, "claude-opus-4-8")
        _, first = self._run(tmp_path)
        assert first.strip() != ""
        _, second = self._run(tmp_path)
        assert second.strip() == ""

    def test_marker_is_claimed_atomically_not_check_then_write(self, tmp_path):
        """Overlapping hook processes must not both emit the same notice.

        Claude Code runs tools in parallel and fires PostToolUse per tool, so
        several hook processes reach the marker claim at once. A real thread
        race would be flaky in both directions, so the contract is asserted
        directly: with the marker already on disk but `exists()` lying about
        it - the exact state a check-then-write loses to - only an exclusive
        create still suppresses the second emission.
        """
        import plan_mode_tracker as pmt

        session = self._setup_leg(tmp_path, "claude-opus-4-8")
        (session / "plan-model-confirmed").write_text("")  # already claimed by a peer process
        with (
            patch("plan_mode_tracker.read_model_switch_mode", return_value="automated"),
            patch("plan_mode_tracker._sessions_base", return_value=tmp_path),
            patch("plan_mode_tracker.resolve_session_id", return_value="test-session"),
            patch.object(Path, "exists", return_value=False),
        ):
            assert pmt.planning_leg_model_context() is None

    def test_mismatch_still_warns_after_a_confirmation(self, tmp_path):
        """The mid-planning downgrade must survive an earlier Opus confirmation.

        Planning starts on Opus, the conversation crosses 200K, and Claude Code
        silently falls back to Sonnet. Sharing one marker between the confirm
        and warn paths would swallow that warning.
        """
        session = self._setup_leg(tmp_path, "claude-opus-4-8")
        _, first = self._run(tmp_path)
        assert "claude-opus-4-8" in first
        cache = session / "context-pct.json"
        cache.write_text(json.dumps({"model_id": "claude-sonnet-5"}))
        os.utime(cache, (1_000_200, 1_000_200))
        _, second = self._run(tmp_path)
        assert "NOT running on Opus" in second

    def test_silent_in_manual_and_off_modes(self, tmp_path):
        for mode in ("manual", "off"):
            self._setup_leg(tmp_path, "claude-sonnet-5")
            _, stdout = self._run(tmp_path, mode=mode)
            assert stdout.strip() == "", mode

    def test_warns_on_fable_family_model(self, tmp_path):
        # The Automated pair is fixed Opus/Sonnet -- a Fable render during the
        # planning leg is a mismatch now (no configurable Fable plan model).
        self._setup_leg(tmp_path, "claude-fable-5[1m]")
        _, stdout = self._run(tmp_path)
        assert "NOT running on Opus" in stdout

    def test_silent_when_cache_render_predates_sentinel(self, tmp_path):
        """A render from before EnterPlanMode proves nothing - no warning."""
        self._setup_leg(tmp_path, "claude-sonnet-5", cache_fresh=False)
        _, stdout = self._run(tmp_path)
        assert stdout.strip() == ""

    def test_silent_when_cache_missing(self, tmp_path):
        session = tmp_path / "test-session"
        session.mkdir(parents=True)
        (session / "plan-mode-active").write_text("")
        _, stdout = self._run(tmp_path)
        assert stdout.strip() == ""

    def test_warns_only_once_per_planning_leg(self, tmp_path):
        self._setup_leg(tmp_path, "claude-sonnet-5")
        _, first = self._run(tmp_path)
        assert first.strip() != ""
        _, second = self._run(tmp_path)
        assert second.strip() == ""

    def test_enter_plan_mode_resets_report_markers(self, tmp_path):
        """A new planning leg gets a fresh chance to report (uneven switching)."""
        session = tmp_path / "test-session"
        session.mkdir(parents=True)
        (session / "plan-model-warned").write_text("")
        (session / "plan-model-confirmed").write_text("")
        stdin = {"tool_name": "EnterPlanMode", "tool_input": {}, "tool_response": {"result": "ok"}}
        _run_main(stdin, tmp_path)
        assert not (session / "plan-model-warned").exists()
        assert not (session / "plan-model-confirmed").exists()
