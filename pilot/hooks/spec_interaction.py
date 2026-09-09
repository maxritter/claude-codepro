#!/usr/bin/env python3
"""Persist user-driven interaction pauses for an active /spec plan.

The Stop hook's ``stop_hook_active`` flag describes a continuation chain, not
whether the latest prompt came from a human.  UserPromptSubmit is the reliable
boundary for that distinction.  This hook therefore owns discussion-pause
transitions and keeps the Stop guard focused on completion enforcement.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lib.session_artifacts import DISCUSSION_PAUSE  # noqa: E402
from _lib.util import (  # noqa: E402
    _read_plan_approved_and_type,
    _sessions_base,
    plan_in_current_project,
    resolve_hook_session_id,
)

_PAUSE_COMMANDS = frozenset({"/spec pause", "$spec pause"})
_RESUME_COMMANDS = frozenset({"resume", "/spec resume", "$spec resume"})
_SPEC_COMMAND_PREFIXES = ("/spec", "$spec")
_LEGACY_PAUSE_FILE = DISCUSSION_PAUSE
_LEGACY_PAUSE_MAX_AGE_SECONDS = 3600


def _atomic_write_json(path: Path, data: dict) -> bool:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        temporary.write_text(json.dumps(data, sort_keys=True))
        os.replace(temporary, path)
        return True
    except OSError:
        try:
            temporary.unlink(missing_ok=True)
        except (OSError, UnboundLocalError):
            pass
        return False


def _load_registration(session_id: str) -> tuple[Path, dict, Path] | None:
    registration_path = _sessions_base() / session_id / "active_plan.json"
    try:
        data = json.loads(registration_path.read_text())
        plan = Path(data["plan_path"])
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        return None
    if not isinstance(data, dict) or not plan.is_file() or not plan_in_current_project(plan):
        return None
    return registration_path, data, plan


def _context(message: str) -> dict:
    return {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": message,
        }
    }


def _consume_expected_continuation(session_id: str, prompt: str) -> bool:
    state_path = _sessions_base() / session_id / "spec-stop-guard"
    try:
        state = json.loads(state_path.read_text())
    except (OSError, json.JSONDecodeError, TypeError):
        return False
    if not isinstance(state, dict):
        return False
    expected = state.pop("expected_prompt_sha256", None)
    if expected is None:
        return False
    _atomic_write_json(state_path, state)
    return expected == hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def _is_spec_command(prompt: str) -> bool:
    return any(prompt == prefix or prompt.startswith(f"{prefix} ") for prefix in _SPEC_COMMAND_PREFIXES)


def _migrate_legacy_pause(
    session_id: str,
    registration_path: Path,
    registration: dict,
    plan: Path,
    plan_type: str,
) -> dict:
    """Convert one valid pre-durable pause marker, then retire the marker."""
    marker = _sessions_base() / session_id / _LEGACY_PAUSE_FILE
    if not marker.exists():
        return registration
    valid = plan_type != "Build"
    try:
        if time.time() - marker.stat().st_mtime > _LEGACY_PAUSE_MAX_AGE_SECONDS:
            valid = False
        raw = marker.read_text().strip()
        if raw:
            binding = json.loads(raw)
            bound_plan = binding.get("plan_path") if isinstance(binding, dict) else None
            if not bound_plan or os.path.realpath(str(bound_plan)) != os.path.realpath(plan):
                valid = False
    except (OSError, json.JSONDecodeError, TypeError):
        valid = False

    if not valid:
        marker.unlink(missing_ok=True)
        return registration
    interaction = registration.get("interaction")
    if isinstance(interaction, dict) and interaction.get("state") == "paused":
        marker.unlink(missing_ok=True)
        return registration

    migrated = {**registration, "interaction": {"state": "paused", "kind": "discussion"}}
    if _atomic_write_json(registration_path, migrated):
        marker.unlink(missing_ok=True)
        return migrated
    return registration


def _consume_expected_verify_gate(
    session_id: str,
    plan: Path,
    status: str,
    plan_type: str,
) -> bool:
    """Consume the persisted marker for an expected COMPLETE-state answer."""
    marker = _sessions_base() / session_id / "verify-gate-pending"
    if not marker.exists():
        return False
    valid = status == "COMPLETE" and plan_type != "Build"
    try:
        if time.time() - marker.stat().st_mtime > _LEGACY_PAUSE_MAX_AGE_SECONDS:
            valid = False
        binding = json.loads(marker.read_text())
        expected_fingerprint = hashlib.sha256(plan.read_bytes()).hexdigest()
        valid = valid and isinstance(binding, dict)
        valid = valid and os.path.realpath(str(binding.get("plan_path", ""))) == os.path.realpath(plan)
        valid = valid and binding.get("expected_status") == status
        valid = valid and binding.get("plan_content_fingerprint") == expected_fingerprint
    except (OSError, json.JSONDecodeError, TypeError):
        valid = False
    marker.unlink(missing_ok=True)
    return valid


def _paused_context(interaction: dict) -> dict:
    if interaction.get("kind") == "manual":
        return _context(
            "The active /spec plan remains paused at its user-owned task. Answer without restarting "
            "implementation. Only exact `done` confirms the user action; `resume` does not complete it."
        )
    return _context(
        "The active /spec plan remains paused. Answer the user's message without restarting implementation. "
        "Only exact `resume`, `/spec resume`, or `$spec resume` clears the pause."
    )


def handle(payload: object) -> dict:
    """Return UserPromptSubmit context and update the registered interaction."""
    if not isinstance(payload, dict):
        return {}
    session_id = resolve_hook_session_id(payload.get("session_id", ""))
    loaded = _load_registration(session_id)
    if loaded is None:
        return {}
    registration_path, registration, plan = loaded
    approved, plan_type = _read_plan_approved_and_type(str(plan))
    registration = _migrate_legacy_pause(session_id, registration_path, registration, plan, plan_type)

    prompt_raw = payload.get("prompt")
    if not isinstance(prompt_raw, str):
        return {}
    prompt = prompt_raw.strip()
    normalized = prompt.lower()

    if _consume_expected_continuation(session_id, prompt):
        return {}
    status = str(registration.get("status", "")).upper()
    if _consume_expected_verify_gate(session_id, plan, status, plan_type):
        return _context(
            "This user message answers a pending /spec verification gate; it is expected input, not a new "
            "implementation interruption. Interpret it against the gate choices, preserve any explicit approval, "
            "and continue or re-arm the gate as required."
        )
    if plan_type == "Build" or status == "VERIFIED":
        return {}

    interaction = registration.get("interaction")
    paused = isinstance(interaction, dict) and interaction.get("state") == "paused"

    if normalized in _RESUME_COMMANDS:
        if paused and interaction.get("kind") == "manual":
            return _paused_context(interaction)
        if paused:
            registration.pop("interaction", None)
            if not _atomic_write_json(registration_path, registration):
                return {}
        return _context(
            f"Resume the active /spec plan at {plan} (Status: {registration.get('status', 'PENDING')}). "
            "Re-read it, apply any agreed amendments before implementation, and continue from its current task."
        )

    if normalized == "done" and paused and interaction.get("kind") == "manual":
        task_number = interaction.get("task_number")
        registration.pop("interaction", None)
        if not _atomic_write_json(registration_path, registration):
            return {}
        task_label = f"Task {task_number}" if isinstance(task_number, int) else "The manual task"
        return _context(
            f"The user explicitly confirmed {task_label} is done. Verify every observable criterion; "
            "only then mark it complete and continue. Re-enter the manual pause if verification fails."
        )

    if normalized in _PAUSE_COMMANDS:
        if paused:
            return _paused_context(interaction)
        registration["interaction"] = {"state": "paused", "kind": "discussion"}
        if not _atomic_write_json(registration_path, registration):
            return {}
        return _context(
            "The active /spec plan is paused for discussion and remains paused after this reply. "
            "Answer normally without resuming implementation. Only exact `resume`, `/spec resume`, or "
            "`$spec resume` clears it."
        )

    if paused:
        return _paused_context(interaction)

    # A slash/dollar workflow invocation owns its own dispatch semantics. The
    # hook must not reinterpret `/spec <plan>` or a new `/spec <task>` as an
    # interruption of the currently registered plan.
    if _is_spec_command(normalized) or not approved:
        return {}

    registration["interaction"] = {"state": "paused", "kind": "discussion"}
    if not _atomic_write_json(registration_path, registration):
        return {}
    return _context(
        "The user's new message interrupted an approved /spec run, so the plan is now paused for discussion. "
        "Answer the message without resuming implementation; the plan remains paused until exact `resume`, "
        "`/spec resume`, or `$spec resume`."
    )


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        result = handle(payload)
    except Exception:
        result = {}
    if result:
        print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
