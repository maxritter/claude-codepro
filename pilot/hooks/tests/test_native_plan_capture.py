"""Tests for native_plan_capture - filing an approved native plan under docs/plans/."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

HOOK_PATH = Path(__file__).resolve().parent.parent / "native_plan_capture.py"
SESSION = "test-session"

PLAN = """# Rate-limit the webhook receiver

## Context

Bursty senders currently melt the queue.

## Steps

- [ ] Task 1: add a token bucket per sender
- [ ] Task 2: shed load past the bucket
"""


def _run(
    tmp_path: Path,
    payload: dict | None = None,
    *,
    project_root_env: bool = True,
    arguments: list[str] | None = None,
    hook_path: Path = HOOK_PATH,
) -> tuple[int, str]:
    """Run the hook hermetically and return (exit code, stdout)."""
    home = tmp_path / "home"
    project = tmp_path / "project"
    home.mkdir(exist_ok=True)
    project.mkdir(exist_ok=True)
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PILOT_SESSION_ID"] = SESSION
    if project_root_env:
        env["CLAUDE_PROJECT_ROOT"] = str(project)
    else:
        env.pop("CLAUDE_PROJECT_ROOT", None)
    env.pop("CLAUDE_CODE_SESSION_ID", None)
    env.pop("CODEX_THREAD_ID", None)
    env.pop("PYTHONPATH", None)
    if payload is None:
        payload = {
            "tool_name": "ExitPlanMode",
            "tool_input": {"plan": PLAN, "planFilePath": "/tmp/scratch.md"},
            "tool_response": {"is_error": False},
        }
    result = subprocess.run(
        [sys.executable, str(hook_path), *(arguments or [])],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(project),
        input=json.dumps(payload),
    )
    return result.returncode, result.stdout.strip()


def _register_run(tmp_path: Path, *, status: str = "PENDING", in_project: bool = True) -> Path:
    """Write the active_plan.json a live /spec or /build run leaves behind."""
    session_dir = tmp_path / "home" / ".pilot" / "sessions" / SESSION
    session_dir.mkdir(parents=True, exist_ok=True)
    parent = tmp_path / "project" if in_project else tmp_path / "elsewhere"
    plans_dir = parent / "docs" / "plans"
    plans_dir.mkdir(parents=True, exist_ok=True)
    plan_path = plans_dir / "2026-09-02-registered-run.md"
    plan_path.write_text(f"# Registered\n\nStatus: {status}\nApproved: Yes\nType: Feature\n")
    (session_dir / "active_plan.json").write_text(json.dumps({"plan_path": str(plan_path), "status": status}))
    return plan_path


def _captured(tmp_path: Path) -> list[Path]:
    plans = tmp_path / "project" / "docs" / "plans"
    if not plans.is_dir():
        return []
    return sorted(p for p in plans.iterdir() if p.suffix == ".md")


def _prepare_native_spec(tmp_path: Path) -> tuple[Path, Path]:
    plan = _register_run(tmp_path)
    plan.write_text(
        "# Native spec\n\nCreated: 2026-09-07\nAgent: Claude Code\n"
        "Status: PENDING\nApproved: No\nWorktree: No\nType: Feature\nIterations: 0\n\n"
        "## Summary\n\nDraft reserved before entering native plan mode.\n"
    )
    marker = tmp_path / "home" / ".pilot" / "sessions" / SESSION / "native-spec-planning.json"
    marker.write_text(
        json.dumps(
            {
                "project_root": str((tmp_path / "project").resolve()),
                "plan_path": str(plan.resolve()),
                "sha256": hashlib.sha256(plan.read_bytes()).hexdigest(),
                "approval_required": True,
                "state": "prepared",
            }
        )
    )
    return plan, marker


def _enter_native_spec(tmp_path: Path, plan: Path) -> Path:
    scratch = tmp_path / "home" / ".claude" / "plans" / "native-spec.md"
    scratch.parent.mkdir(parents=True, exist_ok=True)
    tracker = HOOK_PATH.with_name("plan_mode_tracker.py")
    _run(
        tmp_path,
        {
            "tool_name": "EnterPlanMode",
            "tool_use_id": "enter-native-spec",
            "tool_input": {},
            "permission_mode": "bypassPermissions",
        },
        hook_path=tracker,
    )
    _run(
        tmp_path,
        {
            "tool_name": "EnterPlanMode",
            "tool_use_id": "enter-native-spec",
            "tool_input": {},
            "tool_response": {"is_error": False, "planFilePath": str(scratch)},
        },
        hook_path=tracker,
    )
    scratch.write_text(plan.read_text())
    return scratch


class TestNativeSpecCapture:
    @pytest.mark.parametrize(
        "failure",
        [
            {"hook_event_name": "PostToolUse", "tool_response": {"is_error": True}},
            {"hook_event_name": "PostToolUse", "tool_response": None},
            {"hook_event_name": "PostToolUseFailure", "error": "Could not enter plan mode", "is_interrupt": False},
        ],
    )
    def test_failed_entry_does_not_poison_later_ordinary_capture(self, tmp_path: Path, failure: dict) -> None:
        plan, marker = _prepare_native_spec(tmp_path)
        tracker = HOOK_PATH.with_name("plan_mode_tracker.py")
        entry = {"tool_name": "EnterPlanMode", "tool_use_id": "failed-entry", "tool_input": {}}
        _run(tmp_path, {**entry, "permission_mode": "default"}, hook_path=tracker)

        code, _ = _run(tmp_path, {**entry, **failure}, hook_path=tracker)

        assert code == 0
        assert not marker.exists()
        for name in ("plan-mode-active", "pre-plan-permission-mode", "plan-leg-owner"):
            assert not (marker.parent / name).exists()
        assert "Approved: No" in plan.read_text()

        # The abandoned workflow is no longer registered; a later ordinary
        # native plan must still get its normal SAVED capture.
        (marker.parent / "active_plan.json").unlink()
        _run(tmp_path)
        assert len([path for path in _captured(tmp_path) if "Status: SAVED" in path.read_text()]) == 1

    def test_old_invalid_entry_marker_is_retired_on_new_native_entry(self, tmp_path: Path) -> None:
        _, marker = _prepare_native_spec(tmp_path)
        stale = json.loads(marker.read_text())
        stale["state"] = "invalid"
        marker.write_text(json.dumps(stale))
        (marker.parent / "active_plan.json").unlink()
        tracker = HOOK_PATH.with_name("plan_mode_tracker.py")

        _run(tmp_path, {"tool_name": "EnterPlanMode", "tool_input": {}}, hook_path=tracker)
        _run(tmp_path, {"tool_name": "EnterPlanMode", "tool_input": {}, "tool_response": {}}, hook_path=tracker)
        _run(tmp_path)

        assert not marker.exists()
        assert len([path for path in _captured(tmp_path) if "Status: SAVED" in path.read_text()]) == 1

    @pytest.mark.parametrize("plan_type", ["Feature", "Bugfix"])
    @pytest.mark.parametrize("defect", ["numbering", "missing-label"])
    def test_invalid_accepted_task_contract_preserves_unapproved_target(
        self, tmp_path: Path, plan_type: str, defect: str
    ) -> None:
        plan, marker = _prepare_native_spec(tmp_path)
        original = plan.read_text().replace("Type: Feature", f"Type: {plan_type}")
        plan.write_text(original)
        state = json.loads(marker.read_text())
        state["sha256"] = hashlib.sha256(plan.read_bytes()).hexdigest()
        marker.write_text(json.dumps(state))
        scratch = _enter_native_spec(tmp_path, plan)
        number = 2 if defect == "numbering" else 1
        progress = "Tasks" if plan_type == "Bugfix" else "Progress Tracking"
        tasks = "" if plan_type == "Bugfix" else "\n## Implementation Tasks\n"
        accepted = original + (
            f"\n## {progress}\n\n- [ ] Task {number}: Repair behavior\n{tasks}\n"
            f"### Task {number}: Repair behavior\n\n"
            "**Objective:** Fix the reproduced behavior.\n\n"
            "**Files:** src/example.py\n\n"
            "**Key Decisions / Notes:** Preserve other behavior.\n\n"
        )
        if defect != "missing-label":
            accepted += "**Definition of Done:** The regression and existing checks pass.\n"
        scratch.write_text(accepted)

        _, output = _run(
            tmp_path,
            {
                "tool_name": "ExitPlanMode",
                "tool_input": {},
                "tool_response": {"plan": accepted, "filePath": str(scratch)},
            },
        )

        assert plan.read_text() == original
        assert marker.exists()
        assert "validat" in output.lower() or "task" in output.lower()

    def test_late_target_edit_is_preserved_before_replacement(self, tmp_path: Path) -> None:
        import native_plan_capture as capture

        plan, marker_file = _prepare_native_spec(tmp_path)
        marker = json.loads(marker_file.read_text())
        original = plan.read_text()
        accepted = original.replace("Draft reserved before entering native plan mode.", "Accepted native plan.")
        concurrent = original + "\nConcurrent user annotation.\n"
        real_header = capture._spec_header

        def edit_after_initial_hash(content: str) -> dict[str, str]:
            parsed = real_header(content)
            if content == accepted:
                plan.write_text(concurrent)
            return parsed

        with (
            patch.object(capture, "_spec_header", side_effect=edit_after_initial_hash),
            patch.object(capture, "native_spec_marker", return_value=marker_file),
        ):
            notice = capture._capture_native_spec(marker, accepted, SESSION)

        assert plan.read_text() == concurrent
        assert marker_file.exists()
        assert "changed" in notice.lower()

    def test_current_claude_post_exit_binds_returned_file_path_with_empty_input(self, tmp_path: Path) -> None:
        """Claude 2.1.263 returns plan/filePath after approval, with empty tool_input."""
        plan, marker = _prepare_native_spec(tmp_path)
        scratch = _enter_native_spec(tmp_path, plan)
        accepted = scratch.read_text().replace("Draft reserved before entering native plan mode.", "Accepted result.")
        scratch.write_text(accepted)

        code, output = _run(
            tmp_path,
            {
                "hook_event_name": "PostToolUse",
                "tool_name": "ExitPlanMode",
                "tool_input": {},
                "permission_mode": "default",
                "tool_response": {"plan": accepted, "isAgent": False, "filePath": str(scratch)},
            },
        )

        assert code == 0
        assert "Approved: Yes" in plan.read_text()
        assert "Accepted result." in plan.read_text()
        assert not marker.exists()
        assert "could not bind" not in output

    def test_prepare_command_binds_the_registered_unapproved_draft(self, tmp_path: Path) -> None:
        plan, marker = _prepare_native_spec(tmp_path)
        marker.unlink()

        code, output = _run(tmp_path, arguments=["prepare-spec", str(plan)])

        assert code == 0
        bound = json.loads(marker.read_text())
        assert bound["plan_path"] == str(plan.resolve())
        assert bound["sha256"] == hashlib.sha256(plan.read_bytes()).hexdigest()
        assert bound["approval_required"] is True
        assert "permitted draft file" in output
        assert "Approved: No" in plan.read_text()

    def test_prepare_command_does_not_adopt_an_unregistered_plan(self, tmp_path: Path) -> None:
        plan, marker = _prepare_native_spec(tmp_path)
        marker.unlink()
        (marker.parent / "active_plan.json").unlink()

        code, _ = _run(tmp_path, arguments=["prepare-spec", str(plan)])

        assert code == 1
        assert not marker.exists()
        assert "Approved: No" in plan.read_text()

    def test_captures_actual_native_approval_into_registered_spec(self, tmp_path: Path) -> None:
        plan, marker = _prepare_native_spec(tmp_path)
        _enter_native_spec(tmp_path, plan)
        accepted = plan.read_text().replace(
            "Draft reserved before entering native plan mode.", "User-edited native plan."
        )

        code, output = _run(
            tmp_path,
            {
                "tool_name": "ExitPlanMode",
                "tool_input": {"plan": plan.read_text()},
                "tool_response": {"is_error": False, "plan": accepted},
            },
        )

        assert code == 0
        assert _captured(tmp_path) == [plan]
        assert "User-edited native plan." in plan.read_text()
        assert "Approved: Yes" in plan.read_text()
        assert "Status: PENDING" in plan.read_text()
        assert "Type: Feature" in plan.read_text()
        assert "Status: SAVED" not in plan.read_text()
        assert not marker.exists()
        assert "spec-implement" in output

    def test_does_not_overwrite_changes_made_during_native_review(self, tmp_path: Path) -> None:
        plan, marker = _prepare_native_spec(tmp_path)
        _enter_native_spec(tmp_path, plan)
        draft = plan.read_text()
        plan.write_text(draft + "\nConcurrent Console annotation.\n")

        _, output = _run(
            tmp_path,
            {
                "tool_name": "ExitPlanMode",
                "tool_input": {"plan": draft},
                "tool_response": {"is_error": False},
            },
        )

        assert "Concurrent Console annotation." in plan.read_text()
        assert "Approved: No" in plan.read_text()
        assert marker.exists()
        assert "changed during native planning" in output
        assert _captured(tmp_path) == [plan]

    def test_requires_successful_native_exit_before_marking_approved(self, tmp_path: Path) -> None:
        plan, marker = _prepare_native_spec(tmp_path)
        _enter_native_spec(tmp_path, plan)
        for response in (None, {"is_error": True}):
            payload = {"tool_name": "ExitPlanMode", "tool_input": {"plan": plan.read_text()}}
            if response is not None:
                payload["tool_response"] = response
            _run(tmp_path, payload)
            assert "Approved: No" in plan.read_text()
            assert marker.exists()
            assert _captured(tmp_path) == [plan]

    def test_prepare_rejects_registered_plan_outside_current_project(self, tmp_path: Path) -> None:
        plan, marker = _prepare_native_spec(tmp_path)
        outside = tmp_path / "unrelated" / "docs" / "plans" / plan.name
        outside.parent.mkdir(parents=True)
        outside.write_bytes(plan.read_bytes())
        (marker.parent / "active_plan.json").write_text(json.dumps({"plan_path": str(outside), "status": "PENDING"}))
        marker.unlink()

        code, _ = _run(tmp_path, arguments=["prepare-spec", str(outside)])

        assert code == 1
        assert not marker.exists()
        assert outside.read_bytes() == plan.read_bytes()

    def test_session_worktree_record_cannot_authorize_another_repository(self, tmp_path: Path) -> None:
        plan, marker = _prepare_native_spec(tmp_path)
        outside = tmp_path / "different-repo" / "docs" / "plans" / plan.name
        outside.parent.mkdir(parents=True)
        outside.write_text(plan.read_text().replace("Worktree: No", "Worktree: Yes"))
        for directory in (tmp_path / "project", tmp_path / "different-repo"):
            subprocess.run(["git", "init", "--quiet", str(directory)], check=True, capture_output=True)
        (marker.parent / "active_plan.json").write_text(json.dumps({"plan_path": str(outside), "status": "PENDING"}))
        (marker.parent / "worktree.json").write_text(
            json.dumps(
                {
                    "project_root": str(tmp_path / "project"),
                    "worktree_path": str(tmp_path / "different-repo"),
                }
            )
        )
        marker.unlink()

        code, _ = _run(tmp_path, arguments=["prepare-spec", str(outside)])

        assert code == 1
        assert not marker.exists()

    @pytest.mark.parametrize("registered", [False, True])
    def test_external_git_worktree_requires_session_registration(
        self, tmp_path: Path, registered: bool, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # A commit hook exports Git location variables; the fixture and its
        # native-plan probe must resolve their own temporary repositories.
        for name in (
            "GIT_DIR",
            "GIT_INDEX_FILE",
            "GIT_WORK_TREE",
            "GIT_PREFIX",
            "GIT_COMMON_DIR",
            "GIT_OBJECT_DIRECTORY",
        ):
            monkeypatch.delenv(name, raising=False)
        plan, marker = _prepare_native_spec(tmp_path)
        project = tmp_path / "project"
        worktree = tmp_path / "external-worktree"
        subprocess.run(["git", "init", "--quiet", str(project)], check=True, capture_output=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(project),
                "-c",
                "user.name=Test",
                "-c",
                "user.email=test@example.invalid",
                "commit",
                "--quiet",
                "--allow-empty",
                "-m",
                "initial",
            ],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(project), "worktree", "add", "--detach", str(worktree)], check=True, capture_output=True
        )
        external = worktree / "docs" / "plans" / plan.name
        external.parent.mkdir(parents=True)
        external.write_text(plan.read_text().replace("Worktree: No", "Worktree: Yes"))
        (marker.parent / "active_plan.json").write_text(json.dumps({"plan_path": str(external), "status": "PENDING"}))
        if registered:
            (marker.parent / "worktree.json").write_text(
                json.dumps(
                    {
                        "project_root": str(project),
                        "worktree_path": str(worktree),
                        "plan_slug": "registered-run",
                        "lane": None,
                    }
                )
            )
        marker.unlink()

        code, _ = _run(tmp_path, arguments=["prepare-spec", str(external)])

        assert code == (0 if registered else 1)
        assert marker.exists() is registered

    @pytest.mark.parametrize("field", ["Created", "Agent", "Worktree", "Iterations"])
    def test_capture_preserves_target_when_approved_draft_loses_header(self, tmp_path: Path, field: str) -> None:
        plan, marker = _prepare_native_spec(tmp_path)
        scratch = _enter_native_spec(tmp_path, plan)
        original = plan.read_text()
        accepted = "\n".join(line for line in original.splitlines() if not line.startswith(f"{field}:")) + "\n"

        _, output = _run(
            tmp_path,
            {
                "tool_name": "ExitPlanMode",
                "tool_input": {"planFilePath": str(scratch)},
                "tool_response": {"is_error": False, "plan": accepted},
            },
        )

        assert plan.read_text() == original
        assert marker.exists()
        assert "header" in output.lower() or "metadata" in output.lower()

    @pytest.mark.parametrize(
        "before,after",
        [
            ("Worktree: No", "Worktree: Yes"),
            ("Iterations: 0", "Iterations: 2"),
            ("Agent: Claude Code", "Agent: Codex"),
            ("Created: 2026-09-07", "Created: 2026-09-08"),
        ],
    )
    def test_capture_preserves_registered_execution_identity(self, tmp_path: Path, before: str, after: str) -> None:
        plan, marker = _prepare_native_spec(tmp_path)
        scratch = _enter_native_spec(tmp_path, plan)
        original = plan.read_text()

        _run(
            tmp_path,
            {
                "tool_name": "ExitPlanMode",
                "tool_input": {"planFilePath": str(scratch)},
                "tool_response": {"is_error": False, "plan": original.replace(before, after)},
            },
        )

        assert plan.read_text() == original
        assert marker.exists()

    def test_capture_does_not_race_exit_trackers_sentinel_cleanup(self, tmp_path: Path) -> None:
        plan, marker = _prepare_native_spec(tmp_path)
        scratch = _enter_native_spec(tmp_path, plan)
        payload = {
            "tool_name": "ExitPlanMode",
            "tool_input": {"planFilePath": str(scratch)},
            "tool_response": {"is_error": False, "plan": scratch.read_text()},
        }
        _run(tmp_path, payload, hook_path=HOOK_PATH.with_name("plan_mode_tracker.py"))

        _, output = _run(tmp_path, payload)

        assert "Approved: Yes" in plan.read_text()
        assert not marker.exists()
        assert "spec-implement" in output


class TestNativePlanCapture:
    def test_captures_an_approved_native_plan(self, tmp_path):
        code, out = _run(tmp_path)
        assert code == 0
        files = _captured(tmp_path)
        assert len(files) == 1
        assert files[0].name.endswith("-rate-limit-the-webhook-receiver.md")
        content = files[0].read_text()
        assert content.startswith("# Rate-limit the webhook receiver\n")
        # The body survives verbatim below the header, headings and tasks intact.
        assert "## Context" in content
        assert "- [ ] Task 1: add a token bucket per sender" in content
        # Exactly one H1: the lifted title, never a duplicate from the body.
        assert content.count("\n# ") == 0
        # A plan that already opens with a section keeps it: no empty Summary
        # card wrapped above the real first heading.
        assert "## Summary" not in content
        assert out, "the agent must be told where the plan was filed"
        assert "docs/plans" in out

    def test_prose_only_plan_is_wrapped_in_a_summary_section(self, tmp_path):
        """Body text outside any `## ` section renders nowhere - give it one."""
        _run(
            tmp_path,
            payload={
                "tool_name": "ExitPlanMode",
                "tool_input": {"plan": "# Small change\n\nSwap the constant and move on.\n"},
            },
        )
        content = _captured(tmp_path)[0].read_text()
        assert "## Summary\n\nSwap the constant and move on." in content

    def test_captured_plan_is_never_an_in_flight_run(self, tmp_path):
        """The staleness contract: a captured plan carries a terminal status.

        Nothing advances a native plan - there is no implement or verify phase
        to hook - so writing it PENDING would put a spec in the Console's active
        surfaces that no workflow can ever close. Every active-run surface keys
        on PENDING/COMPLETE, so the status must be neither.
        """
        _run(tmp_path)
        content = _captured(tmp_path)[0].read_text()
        assert "Status: SAVED" in content
        assert "Status: PENDING" not in content
        assert "Status: COMPLETE" not in content
        # Type keeps it off the Feature/Bugfix/Build workflow surfaces.
        assert "Type: Plan" in content
        # Header fields the plan format declares required, so every reader agrees.
        for field in ("Created:", "Agent:", "Approved:", "Worktree:", "Iterations:"):
            assert field in content, field

    def test_skips_while_a_pilot_run_owns_the_plan_mode_leg(self, tmp_path):
        """`/spec` and `/build` maintain their own plan file - never duplicate it.

        Regression guard: capturing here would drop a second file into
        docs/plans/ that competes with the registered run in the Console list.
        """
        registered = _register_run(tmp_path)
        code, out = _run(tmp_path)
        assert code == 0
        assert out == ""
        assert _captured(tmp_path) == [registered]

    def test_captures_when_the_registered_run_is_finished(self, tmp_path):
        """A VERIFIED plan from an earlier /spec in the same session is not a live run."""
        registered = _register_run(tmp_path, status="VERIFIED")
        _run(tmp_path)
        assert len(_captured(tmp_path)) == 2
        assert registered.read_text().startswith("# Registered")

    def test_captures_when_the_registered_run_belongs_to_another_project(self, tmp_path):
        """Cross-project bleed: a PENDING plan from another repo must not mute capture."""
        _register_run(tmp_path, in_project=False)
        _run(tmp_path)
        assert len(_captured(tmp_path)) == 1

    def test_skips_a_failed_or_rejected_exit(self, tmp_path):
        code, out = _run(
            tmp_path,
            payload={
                "tool_name": "ExitPlanMode",
                "tool_input": {"plan": PLAN},
                "tool_response": {"is_error": True},
            },
        )
        assert code == 0
        assert out == ""
        assert _captured(tmp_path) == []

    def test_skips_other_tools_and_empty_plans(self, tmp_path):
        for payload in (
            {"tool_name": "EnterPlanMode", "tool_input": {"plan": PLAN}},
            {"tool_name": "ExitPlanMode", "tool_input": {"plan": "   "}},
            {"tool_name": "ExitPlanMode", "tool_input": {}},
            {"tool_name": "ExitPlanMode"},
        ):
            code, out = _run(tmp_path, payload=payload)
            assert code == 0, payload
            assert out == "", payload
            assert _captured(tmp_path) == [], payload

    def test_falls_back_to_the_scratch_file_claude_code_wrote(self, tmp_path):
        scratch = tmp_path / "home" / ".claude" / "plans" / "scratch.md"
        scratch.parent.mkdir(parents=True)
        scratch.write_text(PLAN)
        code, _ = _run(
            tmp_path,
            payload={
                "tool_name": "ExitPlanMode",
                "tool_input": {"planFilePath": str(scratch)},
            },
        )
        assert code == 0
        assert len(_captured(tmp_path)) == 1

    def test_never_reads_a_scratch_file_outside_claudes_plan_directory(self, tmp_path):
        """A tool payload must not turn plan capture into an arbitrary-file copy."""
        outside = tmp_path / "private.md"
        outside.write_text("# Private\n\nA secret that is not a Claude plan.\n")

        code, out = _run(
            tmp_path,
            payload={
                "tool_name": "ExitPlanMode",
                "tool_input": {"planFilePath": str(outside)},
            },
        )

        assert code == 0
        assert out == ""
        assert _captured(tmp_path) == []

    def test_honors_a_project_relative_custom_plans_directory(self, tmp_path):
        config_dir = tmp_path / "home" / ".claude"
        config_dir.mkdir(parents=True)
        (config_dir / "settings.json").write_text(json.dumps({"plansDirectory": ".plans"}))
        scratch = tmp_path / "project" / ".plans" / "scratch.md"
        scratch.parent.mkdir(parents=True)
        scratch.write_text(PLAN)

        code, _ = _run(
            tmp_path,
            payload={
                "tool_name": "ExitPlanMode",
                "tool_input": {"planFilePath": str(scratch)},
            },
        )

        assert code == 0
        assert len(_captured(tmp_path)) == 1

    def test_rejects_a_scratch_symlink_that_escapes_the_plan_directory(self, tmp_path):
        outside = tmp_path / "private.md"
        outside.write_text("# Private\n\nA secret that is not a Claude plan.\n")
        scratch = tmp_path / "home" / ".claude" / "plans" / "scratch.md"
        scratch.parent.mkdir(parents=True)
        scratch.symlink_to(outside)

        code, out = _run(
            tmp_path,
            payload={
                "tool_name": "ExitPlanMode",
                "tool_input": {"planFilePath": str(scratch)},
            },
        )

        assert code == 0
        assert out == ""
        assert _captured(tmp_path) == []

    def test_never_overwrites_an_existing_capture(self, tmp_path):
        """A second plan the same day keeps its own file - and so does a hand edit."""
        _run(tmp_path)
        first = _captured(tmp_path)[0]
        first.write_text(first.read_text() + "\n<!-- hand-edited -->\n")
        _run(tmp_path)
        files = _captured(tmp_path)
        assert len(files) == 2
        assert "hand-edited" in first.read_text()

    def test_untitled_plan_still_gets_a_file(self, tmp_path):
        code, _ = _run(
            tmp_path,
            payload={
                "tool_name": "ExitPlanMode",
                "tool_input": {"plan": "Just do the thing, carefully.\n"},
            },
        )
        assert code == 0
        files = _captured(tmp_path)
        assert len(files) == 1
        content = files[0].read_text()
        assert content.startswith("# Plan\n")
        assert "Just do the thing, carefully." in content

    def test_says_so_when_there_is_no_project_root_to_file_into(self, tmp_path):
        """No project root = nowhere to write - but never fail silently.

        The plan exists only in Claude Code's throwaway scratch file at this
        point, so swallowing the failure loses it with no way for the user to
        know. Tell them instead of guessing with cwd.
        """
        code, out = _run(tmp_path, project_root_env=False)
        assert code == 0
        assert "not" in out.lower() and "saved" in out.lower(), out
        assert _captured(tmp_path) == []

    def test_prefers_the_approved_plan_from_the_tool_response(self, tmp_path):
        """The user can edit a plan during native review; the response is truth.

        Capturing `tool_input.plan` files what was PROPOSED, so any edit made in
        the approval dialog leaves the saved document silently out of date.
        """
        _run(
            tmp_path,
            payload={
                "tool_name": "ExitPlanMode",
                "tool_input": {"plan": "# Proposed\n\nThe original idea.\n"},
                "tool_response": {"plan": "# Approved\n\nWhat they actually agreed to.\n"},
            },
        )
        files = _captured(tmp_path)
        assert len(files) == 1
        content = files[0].read_text()
        assert files[0].name.endswith("-approved.md")
        assert "What they actually agreed to." in content
        assert "The original idea." not in content

    def test_falls_back_to_the_request_when_the_response_carries_no_plan(self, tmp_path):
        """Not every build returns a plan in the response; the proposal still counts."""
        _run(
            tmp_path,
            payload={
                "tool_name": "ExitPlanMode",
                "tool_input": {"plan": "# Proposed\n\nThe original idea.\n"},
                "tool_response": {"is_error": False},
            },
        )
        assert "The original idea." in _captured(tmp_path)[0].read_text()

    def test_skips_when_an_orchestration_lane_owns_a_run(self, tmp_path):
        """A lane's /spec registers under lanes/<id>/, not the session slot.

        Reading only the session slot made a lane-owned run look like no run at
        all, so the capture filed a duplicate competing with the real plan.
        """
        lane_dir = tmp_path / "home" / ".pilot" / "sessions" / SESSION / "lanes" / "lane-a"
        lane_dir.mkdir(parents=True)
        plans_dir = tmp_path / "project" / "docs" / "plans"
        plans_dir.mkdir(parents=True)
        lane_plan = plans_dir / "2026-09-02-lane-run.md"
        lane_plan.write_text("# Lane\n\nStatus: PENDING\nApproved: Yes\nType: Feature\n")
        (lane_dir / "active_plan.json").write_text(json.dumps({"plan_path": str(lane_plan), "status": "PENDING"}))

        code, out = _run(tmp_path)
        assert code == 0
        assert out == ""
        assert _captured(tmp_path) == [lane_plan]

    def test_skips_when_workflow_ownership_cannot_be_determined(self, tmp_path):
        """A corrupt active_plan.json is ambiguous - never write a competing file.

        `_read_active_plan` swallows the parse error and returns None, which read
        as "no workflow is running" and produced exactly the duplicate this skip
        exists to prevent. Ambiguity must fail CLOSED.
        """
        session_dir = tmp_path / "home" / ".pilot" / "sessions" / SESSION
        session_dir.mkdir(parents=True)
        (session_dir / "active_plan.json").write_text("{ this is not json")

        code, out = _run(tmp_path)
        assert code == 0
        assert out == ""
        assert _captured(tmp_path) == []
