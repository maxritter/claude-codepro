#!/usr/bin/env python3
"""Honor native plan approval and explicitly configured Pilot handoffs.

A prepared native /spec handoff uses Claude Code's actual approval dialog,
unless the user disabled that workflow gate. The capture hook materializes
its accepted draft; this hook never changes the native dialog's permission
choice. Unapproved or unreadable legacy plans also fall through to the native
dialog, so Pilot cannot trap the model between incompatible approval rules.

For older installed skills that already collected separate approval, retain
the scoped permission handoff and prior-bypass restoration. Both require a
live Pilot planning leg classified at entry and a readable approved plan.
Ordinary native planning, Buildouts, sibling sessions, and unknown state never
receive that legacy automatic allowance or permission restoration.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

RESTORE_MARKER = "bypass-restore-pending"

_RESTORE_SETMODE = {
    "type": "setMode",
    "mode": "bypassPermissions",
    "destination": "session",
}


def _read_stdin() -> dict:
    """Parse the PermissionRequest stdin payload; fail open to {}."""
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw and raw.strip() else {}
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _marker_path(fallback_sid: str = "") -> Path | None:
    """Session-scoped restore-marker path; None on a version-skewed _lib.

    ``fallback_sid`` is the hook payload's session_id, consulted only when the
    env chain is empty (see resolve_session_id) - it keeps an env-less session
    from acting on the shared "default" bucket another session's state lives in.
    """
    try:
        from _lib.util import _sessions_base, resolve_session_id

        return _sessions_base() / resolve_session_id(fallback_sid) / RESTORE_MARKER
    except Exception:
        return None


def _arm_restore_marker(fallback_sid: str = "") -> None:
    marker = _marker_path(fallback_sid)
    if marker is None:
        return
    try:
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("")
    except OSError:
        pass


def _clear_restore_marker(fallback_sid: str = "") -> None:
    marker = _marker_path(fallback_sid)
    if marker is not None:
        try:
            marker.unlink(missing_ok=True)
        except OSError:
            pass


def _pre_plan_bypass_evidence(fallback_sid: str = "") -> bool:
    """True when plan_mode_tracker recorded bypassPermissions as the pre-plan mode.

    Consumes the record - evidence is per planning leg. Missing _lib, missing
    record (shift-tab plan entries record nothing), or any other recorded mode
    -> False: the restore must NEVER arm without positive evidence, or a
    session whose user deliberately runs without bypass would get its next
    permission prompt silently auto-allowed.
    """
    try:
        from _lib.util import PRE_PLAN_MODE_RECORD, _sessions_base, resolve_session_id

        record = _sessions_base() / resolve_session_id(fallback_sid) / PRE_PLAN_MODE_RECORD
        mode = record.read_text().strip()
        record.unlink(missing_ok=True)
        return mode == "bypassPermissions"
    except Exception:
        return False


def _is_spec_plan_leg(fallback_sid: str = "") -> bool:
    """True when this ExitPlanMode belongs to a registered Pilot planning leg.

    The gate on every allow path. Fail-closed for THIS consumer (False on any
    error, including a version-skewed _lib predating the predicate): "not a
    Pilot leg" hands the decision back to Claude Code's own plan dialog, which
    is always safe. The opposite default is what silently approved native
    plans.
    """
    try:
        from _lib.util import (
            _read_plan_approved_and_type,
            registered_pending_plan,
            resolve_session_id,
            spec_plan_leg_active,
        )

        sid = resolve_session_id(fallback_sid)
        plan = registered_pending_plan(sid)
        return bool(spec_plan_leg_active(sid) and plan is not None and _read_plan_approved_and_type(str(plan))[0])
    except Exception:
        return False


def _print_decision(decision: dict) -> None:
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PermissionRequest",
                    "decision": decision,
                }
            }
        )
    )


def _exit_plan_mode_decision(data: dict) -> dict | None:
    """Decision for an ExitPlanMode permission request, or None for "stay out".

    None means the hook prints nothing and Claude Code shows its normal plan
    dialog - the correct outcome for native plan mode, where that dialog IS the
    approval.
    """
    fallback_sid = str(data.get("session_id") or "")
    # New /spec planning uses the real native draft and approval boundary.
    # The explicit handoff is prepared before entering read-only mode; it is
    # not inferred from a generic plan-mode sentinel or an unrelated live run.
    restore_marker = _marker_path(fallback_sid)
    has_native_handoff = restore_marker is not None and (restore_marker.parent / "native-spec-planning.json").exists()
    try:
        from _lib.util import resolve_session_id
        from native_plan_capture import native_spec_exit_matches, pending_native_spec

        sid = resolve_session_id(fallback_sid)
        pending = pending_native_spec(sid)
    except (ImportError, OSError, ValueError):
        pending = None
    if has_native_handoff:
        _clear_restore_marker(fallback_sid)
        if pending is None:
            return None
        if pending["approval_required"]:
            return None  # show native approval and preserve the user's permission choice
        if data.get("permission_mode", "plan") != "plan" or not native_spec_exit_matches(
            pending,
            data.get("tool_input"),
            sid,
            require_active=True,
        ):
            return None
        # The user's Pilot setting explicitly disabled the workflow approval gate.
        # No permission-mode escalation or post-exit bypass restore is attached.
        decision = {"behavior": "allow", "message": "Pilot plan approval is disabled for this prepared spec."}
        if isinstance(data.get("tool_input"), dict):
            decision["updatedInput"] = dict(data["tool_input"])
        return decision
    if not _is_spec_plan_leg(fallback_sid):
        _clear_restore_marker(fallback_sid)
        # Claude Code's own plan mode. Two things must NOT happen here.
        #
        # The plan itself: ExitPlanMode IS the approval, so the dialog must
        # reach the user. Allowing it - let alone echoing updatedInput, which
        # tells CC the required interaction was already collected - approves
        # the plan on their behalf.
        #
        # The permission mode: the exit dialog's "auto-accept edits" vs
        # "manually approve edits" is the user CHOOSING a mode, not Claude Code
        # dropping one. Arming the bypass restore here would auto-allow their
        # next permission request and force bypassPermissions over the choice
        # they just made - a worse outcome than the plan approval this hook was
        # fixing. So the marker stays unarmed and the evidence record is left
        # for the next planning leg, which overwrites it at EnterPlanMode.
        return None
    # Arm the post-exit replay: CC drops the setMode below on the exit request
    # itself (#49525) and lands the session in acceptEdits (#39973). Only arm
    # for a real plan exit (missing field = older CC without permission_mode)
    # AND with positive evidence the session ran bypassPermissions before the
    # planning leg - never escalate a session that was not in bypass. /spec legs
    # only: there the mode change is an involuntary drop, not a user choice.
    restore_bypass = data.get("permission_mode", "plan") == "plan" and _pre_plan_bypass_evidence(fallback_sid)
    if restore_bypass:
        _arm_restore_marker(fallback_sid)
    decision = {
        "behavior": "allow",
        "message": "ExitPlanMode allowed (model switch) - permission action only, NOT plan approval",
    }
    if restore_bypass:
        # Positive evidence only. Asking for bypass without it would escalate a
        # session the user deliberately kept in manual/acceptEdits if Claude
        # Code starts honoring setMode on ExitPlanMode in a future release.
        decision["updatedPermissions"] = [dict(_RESTORE_SETMODE)]
        decision["message"] = (
            "ExitPlanMode allowed (model switch); restoring bypassPermissions - "
            "permission action only, NOT plan approval"
        )
    # ExitPlanMode is a "requires user interaction" tool: per the CC hooks
    # reference, behavior:"allow" ALONE does NOT skip its plan-approval prompt.
    # Echoing the injected tool_input (plan + planFilePath) back as updatedInput
    # signals the interaction was collected, so the tool runs without prompting.
    # The plan-approval gate in /spec is the separate AskUserQuestion step, so
    # suppressing this redundant confirmation is safe. Fail-open: a missing or
    # non-dict tool_input just omits updatedInput (falls back to today's prompt).
    tool_input = data.get("tool_input")
    if isinstance(tool_input, dict):
        decision["updatedInput"] = dict(tool_input)
    return decision


# Modes a plan exit involuntarily drops the session into: acceptEdits
# (#39973) or manual (the >=2.1.204 exit dialog). Per the CC 2.1.200
# changelog, "manual" is accepted alongside "default" as the same mode
# ("--permission-mode manual and defaultMode: manual are accepted alongside
# default"), so both spellings are drop states. Only these replay the
# restore - "plan" means the session is deliberately planning again,
# anything else is unknown territory.
_DROPPED_MODES = frozenset({"acceptEdits", "default", "manual"})


def _restore_decision(data: dict) -> dict | None:
    """Replay the bypass restore on the first prompt after a plan exit.

    Returns None (= no output, normal permission dialog) unless the marker is
    armed AND the session sits in one of the modes the plan exit drops it
    into. The marker is consumed either way (single-shot).
    """
    marker = _marker_path(str(data.get("session_id") or ""))
    if marker is None or not marker.exists():
        return None
    try:
        marker.unlink()
    except OSError:
        pass
    if (marker.parent / "native-spec-planning.json").exists():
        return None  # prepared native planning must never replay a legacy bypass choice
    if data.get("permission_mode") not in _DROPPED_MODES:
        return None
    return {
        "behavior": "allow",
        "updatedPermissions": [dict(_RESTORE_SETMODE)],
        "message": "Restoring bypassPermissions dropped by the plan-mode exit - permission action only, NOT plan approval",
    }


def main() -> int:
    data = _read_stdin()
    tool_name = data.get("tool_name", "")
    if tool_name == "ExitPlanMode":
        exit_decision = _exit_plan_mode_decision(data)
        if exit_decision is not None:
            _print_decision(exit_decision)
        return 0
    if tool_name == "EnterPlanMode":
        return 0  # never interfere with entering plan mode
    decision = _restore_decision(data)
    if decision is not None:
        _print_decision(decision)
    return 0


if __name__ == "__main__":
    sys.exit(main())
