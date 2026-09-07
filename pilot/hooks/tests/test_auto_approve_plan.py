"""Tests for auto_approve_plan hook - approval-state-aware ExitPlanMode gate."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HOOK_PATH = Path(__file__).resolve().parent.parent / "auto_approve_plan.py"
SESSION = "test-session"
RESTORE_MARKER = "bypass-restore-pending"


def _marker(tmp_path: Path) -> Path:
    return tmp_path / "home" / ".pilot" / "sessions" / SESSION / RESTORE_MARKER


def _arm_marker(tmp_path: Path) -> Path:
    marker = _marker(tmp_path)
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("")
    return marker


def _record_pre_plan_mode(tmp_path: Path, mode: str) -> Path:
    record = tmp_path / "home" / ".pilot" / "sessions" / SESSION / "pre-plan-permission-mode"
    record.parent.mkdir(parents=True, exist_ok=True)
    record.write_text(mode)
    return record


def _setup_spec_state(  # noqa: PLR0913 - a fixture builder; each flag isolates one guard condition
    tmp_path: Path,
    *,
    approved: str = "No",
    status: str = "PENDING",
    sentinel: bool = True,
    plan_file: bool = True,
    plan_in_project: bool = True,
    plan_type: str = "Feature",
    leg_owner: str | None = "pilot-planning",
) -> Path:
    """Create the session + plan state the hook inspects. Returns the plan path.

    ``leg_owner`` is the record plan_mode_tracker writes at
    PreToolUse(EnterPlanMode); `None` omits it, which is what a shift-tab plan
    entry leaves behind. Only "pilot-planning" makes this a /spec leg.
    """
    session_dir = tmp_path / "home" / ".pilot" / "sessions" / SESSION
    session_dir.mkdir(parents=True, exist_ok=True)
    if leg_owner is not None:
        (session_dir / "plan-leg-owner").write_text(leg_owner)
    plan_parent = tmp_path / "project" if plan_in_project else tmp_path / "elsewhere"
    plans_dir = plan_parent / "docs" / "plans"
    plans_dir.mkdir(parents=True, exist_ok=True)
    plan_path = plans_dir / "2026-07-02-test-feature.md"
    if plan_file:
        plan_path.write_text(f"# Test Feature\n\nStatus: {status}\nApproved: {approved}\nType: {plan_type}\n")
    (session_dir / "active_plan.json").write_text(json.dumps({"plan_path": str(plan_path), "status": status}))
    if sentinel:
        (session_dir / "plan-mode-active").write_text("")
    return plan_path


def _run(
    tmp_path: Path,
    hook_path: Path = HOOK_PATH,
    project_root_env: bool = True,
    payload: dict | None = None,
    session_env: bool = True,
) -> tuple[int, dict | None]:
    """Run the hook hermetically (isolated HOME/session/project) and parse its output.

    payload is the PermissionRequest stdin JSON; the default simulates the
    classic ExitPlanMode request. Returns None for data when the hook printed
    nothing (passthrough to the normal permission dialog). session_env=False
    strips the whole session-id env chain, simulating a launch where neither
    the shell wrapper nor the agent exported a session id.
    """
    home = tmp_path / "home"
    project = tmp_path / "project"
    home.mkdir(exist_ok=True)
    project.mkdir(exist_ok=True)
    env = os.environ.copy()
    env["HOME"] = str(home)
    if session_env:
        env["PILOT_SESSION_ID"] = SESSION
    else:
        env.pop("PILOT_SESSION_ID", None)
    if project_root_env:
        env["CLAUDE_PROJECT_ROOT"] = str(project)
    else:
        env.pop("CLAUDE_PROJECT_ROOT", None)
    env.pop("CLAUDE_CODE_SESSION_ID", None)
    env.pop("CODEX_THREAD_ID", None)
    env.pop("PYTHONPATH", None)  # a leaked path to pilot/hooks would defeat the orphan-_lib isolation
    if payload is None:
        payload = {"tool_name": "ExitPlanMode", "permission_mode": "plan"}
    result = subprocess.run(
        [sys.executable, str(hook_path)],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(project),
        input=json.dumps(payload),
    )
    stdout = result.stdout.strip()
    return result.returncode, json.loads(stdout) if stdout else None


def _decision(data: dict | None) -> dict:
    assert data is not None, "hook printed no decision"
    return data["hookSpecificOutput"]["decision"]


def _prepared_native_state(tmp_path: Path, *, enter: bool = True) -> tuple[Path, Path, dict]:
    plan = _setup_spec_state(tmp_path, approved="No", sentinel=False)
    plan.write_text(
        "# Test Feature\n\nCreated: 2026-09-07\nAgent: Claude Code\nStatus: PENDING\nApproved: No\n"
        "Worktree: No\nType: Feature\nIterations: 0\n\n## Summary\n\nA concrete feature.\n"
    )
    marker = tmp_path / "home" / ".pilot" / "sessions" / SESSION / "native-spec-planning.json"
    marker.write_text(
        json.dumps(
            {
                "project_root": str((tmp_path / "project").resolve()),
                "plan_path": str(plan.resolve()),
                "sha256": hashlib.sha256(plan.read_bytes()).hexdigest(),
                "approval_required": False,
                "state": "prepared",
            }
        )
    )
    scratch = tmp_path / "home" / ".claude" / "plans" / "prepared.md"
    scratch.parent.mkdir(parents=True, exist_ok=True)
    tracker = HOOK_PATH.with_name("plan_mode_tracker.py")
    if enter:
        _run(
            tmp_path,
            hook_path=tracker,
            payload={
                "tool_name": "EnterPlanMode",
                "tool_use_id": "first-enter",
                "tool_input": {},
                "permission_mode": "bypassPermissions",
            },
        )
        _run(
            tmp_path,
            hook_path=tracker,
            payload={
                "tool_name": "EnterPlanMode",
                "tool_use_id": "first-enter",
                "tool_input": {},
                "tool_response": {"is_error": False, "planFilePath": str(scratch)},
            },
        )
    scratch.write_text(plan.read_text())
    payload = {"tool_name": "ExitPlanMode", "permission_mode": "plan", "tool_input": {"planFilePath": str(scratch)}}
    return plan, marker, payload


class TestAutoApprovePlan:
    def test_approval_disabled_only_allows_current_entered_matching_draft(self, tmp_path: Path) -> None:
        _, _, payload = _prepared_native_state(tmp_path)

        code, result = _run(tmp_path, payload=payload)

        assert code == 0
        decision = _decision(result)
        assert decision["behavior"] == "allow"
        assert decision["updatedInput"] == payload["tool_input"]
        assert "updatedPermissions" not in decision

    @pytest.mark.parametrize(
        "case", ["no-enter", "unrelated", "changed-target", "already-approved", "later-enter", "failed-enter"]
    )
    def test_prepared_marker_does_not_approve_an_unbound_exit(self, tmp_path: Path, case: str) -> None:
        plan, marker, payload = _prepared_native_state(tmp_path, enter=case not in {"no-enter", "failed-enter"})
        tracker = HOOK_PATH.with_name("plan_mode_tracker.py")
        if case == "unrelated":
            payload["tool_input"] = {"plan": "# Unrelated native idea\n\n## Summary\n\nDifferent work.\n"}
        elif case == "changed-target":
            plan.write_text(plan.read_text() + "\nConcurrent user change.\n")
        elif case == "already-approved":
            plan.write_text(plan.read_text().replace("Approved: No", "Approved: Yes"))
        elif case in {"later-enter", "failed-enter"}:
            _run(
                tmp_path,
                hook_path=tracker,
                payload={
                    "tool_name": "EnterPlanMode",
                    "tool_use_id": "another-enter",
                    "tool_input": {},
                    "permission_mode": "default",
                },
            )
            _run(
                tmp_path,
                hook_path=tracker,
                payload={
                    "tool_name": "EnterPlanMode",
                    "tool_use_id": "another-enter",
                    "tool_input": {},
                    "tool_response": {"is_error": case == "failed-enter"},
                },
            )

        code, result = _run(tmp_path, payload=payload)

        assert code == 0
        assert result is None
        assert not _marker(tmp_path).exists()
        assert marker.exists() or case in {"later-enter", "failed-enter"}

    def test_native_bridge_discards_legacy_bypass_restore_before_user_choice(self, tmp_path: Path) -> None:
        _, marker, payload = _prepared_native_state(tmp_path)
        data = json.loads(marker.read_text())
        data["approval_required"] = True
        marker.write_text(json.dumps(data))
        _arm_marker(tmp_path)

        _, result = _run(tmp_path, payload=payload)
        _, next_result = _run(
            tmp_path,
            payload={
                "tool_name": "Bash",
                "permission_mode": "default",
                "tool_input": {"command": "true"},
            },
        )

        assert result is None
        assert next_result is None
        assert not _marker(tmp_path).exists()

    def test_ordinary_native_exit_clears_an_old_restore_before_the_next_prompt(self, tmp_path: Path) -> None:
        _arm_marker(tmp_path)

        _, result = _run(tmp_path)
        _, next_result = _run(
            tmp_path,
            payload={
                "tool_name": "Bash",
                "permission_mode": "manual",
                "tool_input": {"command": "true"},
            },
        )

        assert result is None
        assert next_result is None
        assert not _marker(tmp_path).exists()

    @pytest.mark.parametrize("write_completed", [False, True])
    def test_draft_path_fallback_requires_a_changed_native_file(self, tmp_path: Path, write_completed: bool) -> None:
        _, _, payload = _prepared_native_state(tmp_path, enter=False)
        tracker = HOOK_PATH.with_name("plan_mode_tracker.py")
        _run(tmp_path, hook_path=tracker, payload={"tool_name": "EnterPlanMode", "tool_input": {}})
        _run(
            tmp_path,
            hook_path=tracker,
            payload={
                "tool_name": "EnterPlanMode",
                "tool_input": {},
                "tool_response": {"result": "ok"},
            },
        )
        scratch = Path(payload["tool_input"]["planFilePath"])
        _run(
            tmp_path,
            hook_path=tracker,
            payload={
                "tool_name": "Write",
                "permission_mode": "plan",
                "tool_input": {"file_path": str(scratch)},
            },
        )
        if write_completed:
            scratch.write_text(scratch.read_text() + "\nThe completed implementation approach.\n")

        _, result = _run(tmp_path, payload=payload)

        assert (result is not None) is write_completed

    def test_approval_disabled_rejects_another_scratch_file_with_matching_metadata(self, tmp_path: Path) -> None:
        _, _, payload = _prepared_native_state(tmp_path)
        actual = Path(payload["tool_input"]["planFilePath"])
        unrelated = actual.with_name("unrelated.md")
        unrelated.write_bytes(actual.read_bytes())
        payload["tool_input"]["planFilePath"] = str(unrelated)

        _, result = _run(tmp_path, payload=payload)

        assert result is None

    def test_native_spec_bridge_keeps_native_approval_and_permission_choice(self, tmp_path: Path) -> None:
        plan = _setup_spec_state(tmp_path, approved="No")
        marker = tmp_path / "home" / ".pilot" / "sessions" / SESSION / "native-spec-planning.json"
        marker.write_text(
            json.dumps(
                {
                    "project_root": str((tmp_path / "project").resolve()),
                    "plan_path": str(plan.resolve()),
                    "sha256": hashlib.sha256(plan.read_bytes()).hexdigest(),
                    "approval_required": True,
                }
            )
        )
        _record_pre_plan_mode(tmp_path, "bypassPermissions")

        code, decision = _run(tmp_path)

        assert code == 0
        assert decision is None
        assert not _marker(tmp_path).exists()
        assert "Approved: No" in plan.read_text()

    def test_native_plan_mode_exit_is_left_to_claude_code(self, tmp_path):
        """No registered Pilot run -> NO output, so the native plan dialog runs.

        Regression guard for the field report that this hook "auto-approves
        normal plan mode": an unconditional allow (with `updatedInput` echoed,
        which tells Claude Code the required interaction was already collected)
        accepted every plan the user entered plan mode to review, without ever
        showing it to them. Outside a `/spec` leg the hook must stay silent -
        ExitPlanMode IS the approval there, and only the user can give it.
        """
        code, data = _run(tmp_path)
        assert code == 0
        assert data is None, f"native ExitPlanMode must not be decided by the hook: {data!r}"

    def test_native_plan_mode_never_touches_the_permission_mode(self, tmp_path):
        """The native exit dialog's mode choice is the USER's - never override it.

        "Yes, and manually approve edits" selects a permission mode deliberately;
        it is not Claude Code dropping one the way a /spec exit does. Arming the
        bypass restore here would auto-allow their very next permission request
        and force bypassPermissions over the choice they just made - a worse
        outcome than the plan approval this hook exists to stop.
        """
        record = _record_pre_plan_mode(tmp_path, "bypassPermissions")
        code, data = _run(tmp_path)
        assert code == 0
        assert data is None
        assert not _marker(tmp_path).exists(), "a native plan exit must not arm the bypass restore"
        assert record.exists(), "the evidence record belongs to the next planning leg"

    def test_native_plan_mode_during_a_live_buildout_is_still_native(self, tmp_path):
        """Regression guard: a running /build must not make native plans auto-approve.

        `/build` sets `Approved: Yes` the moment its contract locks, with no user
        sign-off, and never enters plan mode itself. Gating on "a PENDING run is
        registered" therefore read a Buildout's approval as this plan's approval
        and suppressed the dialog - the original bug, inside every /build run.
        """
        _setup_spec_state(tmp_path, approved="Yes", plan_type="Build", leg_owner="native")
        code, data = _run(tmp_path)
        assert code == 0
        assert data is None

    def test_native_plan_mode_during_implementation_is_still_native(self, tmp_path):
        """Same hole via /spec: an approved plan mid-implementation is PENDING+Yes.

        Indistinguishable from a Step 12.3 exit by run state alone, which is why
        ownership is recorded at EnterPlanMode instead of inferred at exit.
        """
        _setup_spec_state(tmp_path, approved="Yes", leg_owner="native")
        code, data = _run(tmp_path)
        assert code == 0
        assert data is None

    def test_shift_tab_plan_entry_is_native(self, tmp_path):
        """No tool call, so no owner record - the safe default must be native."""
        _setup_spec_state(tmp_path, approved="Yes", leg_owner=None)
        code, data = _run(tmp_path)
        assert code == 0
        assert data is None

    def test_native_plan_mode_is_never_denied_by_an_unapproved_spec_plan(self, tmp_path):
        """A stale unapproved /spec plan must not deny an unrelated native exit.

        The deny message talks about the /spec approval gate; firing it at a plan
        mode the user opened for something else is a dead end for them.
        """
        _setup_spec_state(tmp_path, approved="No", leg_owner="native")
        code, data = _run(tmp_path)
        assert code == 0
        assert data is None

    def test_spec_leg_exit_suppresses_the_redundant_dialog(self, tmp_path):
        """Approved /spec plan -> allow + echoed updatedInput (dialog skipped).

        `updatedInput` is what signals the required interaction was collected.
        It is safe ONLY here: the user already approved at the AskUserQuestion
        gate, and this ExitPlanMode is just the opusplan model switch.
        """
        _setup_spec_state(tmp_path, approved="Yes")
        payload = {
            "tool_name": "ExitPlanMode",
            "permission_mode": "plan",
            "tool_input": {"plan": "# Plan\n", "planFilePath": "/tmp/p.md"},
        }
        code, data = _run(tmp_path, payload=payload)
        assert code == 0
        decision = _decision(data)
        assert decision["behavior"] == "allow"
        assert decision["updatedInput"] == payload["tool_input"]

    def test_native_exit_never_echoes_updated_input(self, tmp_path):
        """The dialog-suppressing field must never be emitted outside a Pilot leg."""
        payload = {
            "tool_name": "ExitPlanMode",
            "permission_mode": "plan",
            "tool_input": {"plan": "# Plan\n", "planFilePath": "/tmp/p.md"},
        }
        code, data = _run(tmp_path, payload=payload)
        assert code == 0
        assert data is None

    def test_allow_message_does_not_claim_plan_approval(self, tmp_path):
        """The allow message must NOT signal that the plan is approved.

        Regression guard: emitting "Plan auto-approved" made agents misread the
        auto-allowed ExitPlanMode (a model-switch/permission action) as the user
        approving the plan, so they skipped the real /spec approval gate
        (spec-plan/steps/12-approval.md). The message must perform the permission
        action while explicitly disclaiming plan approval.
        """
        _setup_spec_state(tmp_path, approved="Yes")
        _, data = _run(tmp_path)
        message = _decision(data)["message"].lower()
        assert "approved" not in message, f"misleading approval wording: {message!r}"
        assert "not plan approval" in message, f"missing disclaimer: {message!r}"

    def test_unapproved_legacy_spec_keeps_the_native_approval_dialog(self, tmp_path):
        """A native approval boundary must not be blocked by a second Pilot gate."""
        plan = _setup_spec_state(tmp_path, approved="No")
        code, data = _run(tmp_path)
        assert code == 0
        assert data is None
        assert "Approved: No" in plan.read_text()
        assert not _marker(tmp_path).exists()

    def test_allows_after_plan_approved(self, tmp_path):
        _setup_spec_state(tmp_path, approved="Yes")
        _record_pre_plan_mode(tmp_path, "bypassPermissions")
        _, data = _run(tmp_path)
        decision = _decision(data)
        assert decision["behavior"] == "allow"
        assert any(p.get("mode") == "bypassPermissions" for p in decision["updatedPermissions"])

    def test_allows_without_plan_mode_sentinel(self, tmp_path):
        """No EnterPlanMode sentinel = no plan-mode leg in flight -> never deny.

        A stale PENDING plan must not trap a user who entered plan mode manually
        (Shift+Tab does not call the EnterPlanMode tool, so no sentinel exists).
        """
        _setup_spec_state(tmp_path, approved="No", sentinel=False)
        _, data = _run(tmp_path)
        assert data is None

    def test_allows_when_plan_file_missing(self, tmp_path):
        """Registered plan path that no longer exists -> fail open (no deny)."""
        _setup_spec_state(tmp_path, approved="No", plan_file=False)
        _, data = _run(tmp_path)
        assert data is None

    def test_allows_when_plan_file_undecodable(self, tmp_path):
        """Unreadable/undecodable plan file -> fail open (allow), never a deny trap.

        A deny here would be unrecoverable: 'set Approved: Yes' can never clear a
        decode error, so the session would be stuck in plan mode.
        """
        plan_path = _setup_spec_state(tmp_path, approved="No")
        plan_path.write_bytes(b"Status: PENDING\nApproved: No\n\xe9\xff")
        _, data = _run(tmp_path)
        assert data is None  # unreadable state cannot authorize automatic approval

    def test_allows_when_plan_outside_project(self, tmp_path):
        """Cross-session bleed guard: a plan from another repo never denies here."""
        _setup_spec_state(tmp_path, approved="No", plan_in_project=False)
        _, data = _run(tmp_path)
        assert data is None

    def test_allows_when_project_root_undetermined(self, tmp_path):
        """No CLAUDE_PROJECT_ROOT and a non-git cwd -> fail open (allow).

        plan_in_current_project returns True when the root cannot be
        determined; for the deny consumer that would be fail-closed, letting a
        stale plan deny ExitPlanMode in an unrelated non-git directory.
        """
        _setup_spec_state(tmp_path, approved="No")
        _, data = _run(tmp_path, project_root_env=False)
        assert data is None

    def test_sibling_default_bucket_state_does_not_deny_identified_session(self, tmp_path):
        """Same-repo sibling bleed: deny state another (env-less) session left in the
        shared 'default' bucket must not deny ExitPlanMode in a session whose hook
        payload carries its own session_id. The project guard passes here (same
        repo), so only session-scoped resolution prevents the cross-fire."""
        default_dir = tmp_path / "home" / ".pilot" / "sessions" / "default"
        default_dir.mkdir(parents=True)
        plans_dir = tmp_path / "project" / "docs" / "plans"
        plans_dir.mkdir(parents=True)
        plan_path = plans_dir / "2026-08-13-sibling-feature.md"
        plan_path.write_text("# Sibling\n\nStatus: PENDING\nApproved: No\nType: Feature\n")
        (default_dir / "active_plan.json").write_text(json.dumps({"plan_path": str(plan_path), "status": "PENDING"}))
        (default_dir / "plan-mode-active").write_text("")

        code, data = _run(
            tmp_path,
            payload={"tool_name": "ExitPlanMode", "permission_mode": "plan", "session_id": "session-b-uuid"},
            session_env=False,
        )
        assert code == 0
        assert data is None, (
            "a sibling session's unapproved plan in the shared 'default' bucket must "
            "not deny this session's ExitPlanMode"
        )

    def test_sibling_default_bucket_restore_marker_not_consumed_by_identified_session(self, tmp_path):
        """Same-repo sibling bleed, restore branch: a bypass-restore marker another
        (env-less) session armed in the shared 'default' bucket must neither
        auto-allow this session's permission prompt nor be consumed by it -
        otherwise one session silently escalates another's permissions AND steals
        the owning session's pending restore."""
        default_dir = tmp_path / "home" / ".pilot" / "sessions" / "default"
        default_dir.mkdir(parents=True)
        marker = default_dir / RESTORE_MARKER
        marker.write_text("")

        code, data = _run(
            tmp_path,
            payload={"tool_name": "Bash", "permission_mode": "acceptEdits", "session_id": "session-b-uuid"},
            session_env=False,
        )
        assert code == 0
        assert data is None, "a sibling session's restore marker must not auto-allow this session's prompt"
        assert marker.exists(), "the owning session's pending restore marker must survive"

    def test_degrades_to_the_native_dialog_when_lib_util_unavailable(self, tmp_path):
        """A version-skewed install (hook without _lib) degrades to the dialog.

        The hook must exit 0 without crashing. It can no longer tell a /spec leg
        from native plan mode, so it must decide nothing: Claude Code's own
        prompt is the only safe fallback in both directions - it neither traps a
        /spec run behind a deny nor approves a native plan unseen.
        """
        orphan_hook = tmp_path / "orphan" / "auto_approve_plan.py"
        orphan_hook.parent.mkdir(parents=True)
        shutil.copy(HOOK_PATH, orphan_hook)
        _setup_spec_state(tmp_path, approved="No")  # deny state, but guard can't load
        code, data = _run(tmp_path, hook_path=orphan_hook)
        assert code == 0
        assert data is None
        # Restore branch under the same skew: never crash, never auto-allow -
        # a non-ExitPlanMode request degrades to the normal permission dialog.
        code, data = _run(
            tmp_path,
            hook_path=orphan_hook,
            payload={"tool_name": "Bash", "permission_mode": "acceptEdits"},
        )
        assert code == 0
        assert data is None

    def test_missing_bridge_module_cannot_fall_back_to_legacy_autoapproval(self, tmp_path: Path) -> None:
        plan, _, payload = _prepared_native_state(tmp_path)
        plan.write_text(plan.read_text().replace("Approved: No", "Approved: Yes"))
        orphan_hook = tmp_path / "partial-install" / "auto_approve_plan.py"
        orphan_hook.parent.mkdir()
        shutil.copy(HOOK_PATH, orphan_hook)
        shutil.copytree(HOOK_PATH.parent / "_lib", orphan_hook.parent / "_lib")

        code, result = _run(tmp_path, hook_path=orphan_hook, payload=payload)

        assert code == 0
        assert result is None
        assert not _marker(tmp_path).exists()

    def test_exit_allow_arms_restore_marker(self, tmp_path):
        """An allowed ExitPlanMode must arm the bypass-restore marker.

        Claude Code resets the session to acceptEdits on plan exit (upstream
        #39973) and silently drops the setMode sent on the exit request itself
        (#49525), so the restore must be replayed on the NEXT permission
        request. The marker is what arms that replay. Arming requires positive
        pre-plan bypass evidence (recorded by plan_mode_tracker at
        PreToolUse(EnterPlanMode)); the record is consumed per planning leg.
        """
        _setup_spec_state(tmp_path, approved="Yes")
        record = _record_pre_plan_mode(tmp_path, "bypassPermissions")
        code, data = _run(tmp_path, payload={"tool_name": "ExitPlanMode", "permission_mode": "plan"})
        assert code == 0
        assert _decision(data)["behavior"] == "allow"
        assert _marker(tmp_path).exists()
        assert not record.exists()  # evidence is per-leg, consumed on use

    def test_exit_allow_requires_bypass_evidence_to_arm(self, tmp_path):
        """No recorded pre-plan bypass mode -> allow, but NEVER arm the marker.

        Guards the permissions regression a reviewer flagged: without this
        gate, a session that was never in bypassPermissions (user deliberately
        in manual/acceptEdits, or a shift-tab plan entry that records nothing)
        would get its next permission prompt silently auto-allowed.
        """
        _setup_spec_state(tmp_path, approved="Yes")
        payload = {"tool_name": "ExitPlanMode", "permission_mode": "plan"}
        # (a) no evidence record at all
        code, data = _run(tmp_path, payload=payload)
        assert code == 0
        decision = _decision(data)
        assert decision["behavior"] == "allow"
        assert "updatedPermissions" not in decision
        assert "restoring bypassPermissions" not in decision["message"]
        assert not _marker(tmp_path).exists()
        # (b) evidence of a NON-bypass pre-plan mode
        _record_pre_plan_mode(tmp_path, "default")
        code, data = _run(tmp_path, payload=payload)
        assert code == 0
        decision = _decision(data)
        assert decision["behavior"] == "allow"
        assert "updatedPermissions" not in decision
        assert "restoring bypassPermissions" not in decision["message"]
        assert not _marker(tmp_path).exists()

    def test_enter_plan_mode_request_leaves_marker_untouched(self, tmp_path):
        """A PermissionRequest for EnterPlanMode is pure passthrough: no
        output, and an armed marker survives to fire on the next
        non-EnterPlanMode request."""
        marker = _arm_marker(tmp_path)
        code, data = _run(tmp_path, payload={"tool_name": "EnterPlanMode", "permission_mode": "acceptEdits"})
        assert code == 0
        assert data is None
        assert marker.exists()

    def test_restore_fires_on_first_prompt_after_plan_exit(self, tmp_path):
        """First permission request after a plan exit -> allow + setMode
        bypassPermissions, marker consumed (single-shot).

        The exit drops the session to acceptEdits (#39973) OR to manual
        (Claude Code >= 2.1.204's exit dialog, field report from the /spec
        smoke test) - the replay must cover every involuntary drop state,
        both 'default' and its 2.1.200+ alias 'manual'.
        """
        for dropped_mode in ("acceptEdits", "default", "manual"):
            marker = _arm_marker(tmp_path)
            code, data = _run(
                tmp_path,
                payload={
                    "tool_name": "Bash",
                    "permission_mode": dropped_mode,
                    "tool_input": {"command": "echo hi"},
                },
            )
            assert code == 0, dropped_mode
            decision = _decision(data)
            assert decision["behavior"] == "allow", dropped_mode
            assert any(
                p.get("type") == "setMode"
                and p.get("mode") == "bypassPermissions"
                and p.get("destination") == "session"
                for p in decision["updatedPermissions"]
            ), dropped_mode
            assert not marker.exists(), dropped_mode
            message = decision["message"].lower()
            assert "approved" not in message, f"misleading approval wording: {message!r}"
            assert "not plan approval" in message, f"missing disclaimer: {message!r}"

    def test_passthrough_for_other_tools_without_marker(self, tmp_path):
        """No armed marker -> a non-ExitPlanMode request produces NO output.

        Safety-critical with the '*' matcher: any output here would auto-allow
        arbitrary permission requests. Silence hands the request back to the
        normal Claude Code permission dialog.
        """
        code, data = _run(tmp_path, payload={"tool_name": "Bash", "permission_mode": "acceptEdits"})
        assert code == 0
        assert data is None

    def test_no_restore_in_plan_or_unknown_mode(self, tmp_path):
        """Marker armed but the session is back in plan mode (or the mode is
        missing/unrecognized) -> stand down: consume the marker, no output.

        Only the involuntary drop states (acceptEdits/default/manual) replay;
        anything else must never be auto-allowed.
        """
        for mode_payload in (
            {"permission_mode": "plan"},
            {"permission_mode": "bypassPermissions"},  # unreachable in practice; pinned defensively
            {},
        ):
            marker = _arm_marker(tmp_path)
            code, data = _run(tmp_path, payload={"tool_name": "Bash", **mode_payload})
            assert code == 0, mode_payload
            assert data is None, mode_payload
            assert not marker.exists(), mode_payload
