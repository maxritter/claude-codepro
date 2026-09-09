"""UserPromptSubmit state transitions for durable /spec interaction pauses."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path
from unittest.mock import patch

HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR))

import spec_interaction  # noqa: E402

SESSION = "interaction-test"


def _register(tmp_path: Path, *, approved: str = "Yes", plan_type: str = "Feature") -> tuple[Path, Path]:
    plan = tmp_path / "plan.md"
    plan.parent.mkdir(parents=True, exist_ok=True)
    plan.write_text(f"# Plan\nStatus: PENDING\nApproved: {approved}\nType: {plan_type}\n")
    session = tmp_path / "sessions" / SESSION
    session.mkdir(parents=True)
    registration = session / "active_plan.json"
    registration.write_text(json.dumps({"plan_path": str(plan), "status": "PENDING"}))
    return plan, registration


def _handle(tmp_path: Path, prompt: str) -> dict:
    with (
        patch("spec_interaction._sessions_base", return_value=tmp_path / "sessions"),
        patch("spec_interaction.plan_in_current_project", return_value=True),
    ):
        return spec_interaction.handle(
            {
                "hook_event_name": "UserPromptSubmit",
                "session_id": SESSION,
                "prompt": prompt,
            }
        )


def _handle_payload(tmp_path: Path, payload: dict) -> dict:
    with (
        patch("spec_interaction._sessions_base", return_value=tmp_path / "sessions"),
        patch("spec_interaction.plan_in_current_project", return_value=True),
    ):
        return spec_interaction.handle(payload)


def _interaction(registration: Path) -> dict | None:
    return json.loads(registration.read_text()).get("interaction")


def test_real_user_prompt_pauses_an_approved_spec(tmp_path: Path) -> None:
    _plan, registration = _register(tmp_path)

    result = _handle(tmp_path, "Why are you changing that API?")

    assert _interaction(registration) == {"state": "paused", "kind": "discussion"}
    assert result["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
    assert "remains paused" in result["hookSpecificOutput"]["additionalContext"]


def test_payload_session_wins_over_stale_parent_codex_thread(tmp_path: Path) -> None:
    _plan, registration = _register(tmp_path)

    with patch.dict("spec_interaction.os.environ", {"CODEX_THREAD_ID": "parent-thread"}, clear=True):
        result = _handle(tmp_path, "Why is this changing?")

    assert _interaction(registration) == {"state": "paused", "kind": "discussion"}
    assert "now paused" in result["hookSpecificOutput"]["additionalContext"]


def test_discussion_text_never_resumes_implicitly(tmp_path: Path) -> None:
    _plan, registration = _register(tmp_path)
    _handle(tmp_path, "Please pause and explain")

    _handle(tmp_path, "continue explaining the tradeoff")

    assert _interaction(registration)["state"] == "paused"


def test_exact_resume_clears_pause_and_reinjects_plan(tmp_path: Path) -> None:
    plan, registration = _register(tmp_path)
    _handle(tmp_path, "Question about the implementation")

    result = _handle(tmp_path, "resume")

    assert _interaction(registration) is None
    context = result["hookSpecificOutput"]["additionalContext"]
    assert str(plan) in context
    assert "resume" in context.lower()


def test_exact_done_confirms_manual_task(tmp_path: Path) -> None:
    _plan, registration = _register(tmp_path)
    data = json.loads(registration.read_text())
    data["interaction"] = {
        "state": "paused",
        "kind": "manual",
        "task_number": 4,
        "message": "Complete the device login locally.",
    }
    registration.write_text(json.dumps(data))

    result = _handle(tmp_path, "done")

    assert _interaction(registration) is None
    context = result["hookSpecificOutput"]["additionalContext"]
    assert "Task 4" in context
    assert "confirmed" in context


def test_resume_does_not_complete_or_clear_a_manual_task(tmp_path: Path) -> None:
    _plan, registration = _register(tmp_path)
    data = json.loads(registration.read_text())
    data["interaction"] = {
        "state": "paused",
        "kind": "manual",
        "task_number": 4,
        "message": "Complete the device login locally.",
    }
    registration.write_text(json.dumps(data))

    result = _handle(tmp_path, "/spec resume")

    assert _interaction(registration)["kind"] == "manual"
    context = result["hookSpecificOutput"]["additionalContext"]
    assert "remains paused" in context
    assert "done" in context


def test_pause_command_does_not_downgrade_a_manual_wait(tmp_path: Path) -> None:
    _plan, registration = _register(tmp_path)
    data = json.loads(registration.read_text())
    data["interaction"] = {
        "state": "paused",
        "kind": "manual",
        "task_number": 4,
        "message": "Complete the device login locally.",
    }
    registration.write_text(json.dumps(data))

    result = _handle(tmp_path, "/spec pause")

    assert _interaction(registration)["kind"] == "manual"
    assert "done" in result["hookSpecificOutput"]["additionalContext"]


def test_stop_generated_prompt_is_not_mistaken_for_a_user_interrupt(tmp_path: Path) -> None:
    _plan, registration = _register(tmp_path)
    synthetic = "Continue working on the next pending task."
    state_file = registration.parent / "spec-stop-guard"
    state_file.write_text(
        json.dumps({"expected_prompt_sha256": hashlib.sha256(synthetic.encode()).hexdigest(), "count": 1})
    )

    result = _handle(tmp_path, synthetic)

    assert result == {}
    assert _interaction(registration) is None
    assert "expected_prompt_sha256" not in json.loads(state_file.read_text())


def test_unapproved_plan_and_buildout_are_not_auto_paused(tmp_path: Path) -> None:
    _plan, registration = _register(tmp_path, approved="No")
    assert _handle(tmp_path, "answer to planning question") == {}
    assert _interaction(registration) is None

    _plan, registration = _register(tmp_path / "build", plan_type="Build")
    assert _handle(tmp_path / "build", "status?") == {}
    assert _interaction(registration) is None


def test_explicit_pause_is_idempotent_and_spec_only(tmp_path: Path) -> None:
    _plan, registration = _register(tmp_path, approved="No")
    _handle(tmp_path, "/spec pause")
    _handle(tmp_path, "/spec pause")
    assert _interaction(registration) == {"state": "paused", "kind": "discussion"}

    _plan, registration = _register(tmp_path / "build", plan_type="Build")
    assert _handle(tmp_path / "build", "/spec pause") == {}
    assert _interaction(registration) is None


def test_session_start_migrates_a_valid_legacy_pause_once(tmp_path: Path) -> None:
    plan, registration = _register(tmp_path)
    marker = registration.parent / "spec-discussion-paused"
    marker.write_text(json.dumps({"plan_path": str(plan), "created_at": time.time()}))

    result = _handle_payload(
        tmp_path,
        {"hook_event_name": "SessionStart", "session_id": SESSION},
    )

    assert result == {}
    assert _interaction(registration) == {"state": "paused", "kind": "discussion"}
    assert not marker.exists()


def test_legacy_pause_can_be_resumed_during_migration(tmp_path: Path) -> None:
    plan, registration = _register(tmp_path)
    marker = registration.parent / "spec-discussion-paused"
    marker.write_text(json.dumps({"plan_path": str(plan)}))

    result = _handle(tmp_path, "/spec resume")

    assert _interaction(registration) is None
    assert not marker.exists()
    assert "Resume the active /spec plan" in result["hookSpecificOutput"]["additionalContext"]


def test_stale_or_mismatched_legacy_pause_is_discarded(tmp_path: Path) -> None:
    _plan, registration = _register(tmp_path)
    marker = registration.parent / "spec-discussion-paused"
    marker.write_text(json.dumps({"plan_path": "/different/plan.md"}))

    _handle_payload(tmp_path, {"hook_event_name": "SessionStart", "session_id": SESSION})
    assert _interaction(registration) is None
    assert not marker.exists()

    marker.write_text("")
    stale = time.time() - spec_interaction._LEGACY_PAUSE_MAX_AGE_SECONDS - 1
    os.utime(marker, (stale, stale))
    _handle_payload(tmp_path, {"hook_event_name": "SessionStart", "session_id": SESSION})
    assert _interaction(registration) is None
    assert not marker.exists()


def test_legacy_pause_is_discarded_for_buildouts(tmp_path: Path) -> None:
    _plan, registration = _register(tmp_path, plan_type="Build")
    marker = registration.parent / "spec-discussion-paused"
    marker.write_text("")

    _handle_payload(tmp_path, {"hook_event_name": "SessionStart", "session_id": SESSION})

    assert _interaction(registration) is None
    assert not marker.exists()


def test_expected_verify_gate_answer_is_not_auto_paused(tmp_path: Path) -> None:
    plan, registration = _register(tmp_path)
    plan.write_text("# Plan\nStatus: COMPLETE\nApproved: Yes\nType: Feature\n")
    data = json.loads(registration.read_text())
    data["status"] = "COMPLETE"
    registration.write_text(json.dumps(data))
    marker = registration.parent / "verify-gate-pending"
    marker.write_text(
        json.dumps(
            {
                "plan_path": os.path.realpath(plan),
                "plan_content_fingerprint": hashlib.sha256(plan.read_bytes()).hexdigest(),
                "expected_status": "COMPLETE",
            }
        )
    )

    result = _handle(tmp_path, "approve")

    assert _interaction(registration) is None
    assert not marker.exists()
    context = result["hookSpecificOutput"]["additionalContext"]
    assert "pending /spec verification gate" in context
