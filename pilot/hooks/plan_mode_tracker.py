#!/usr/bin/env python3
"""Track EnterPlanMode/ExitPlanMode state via a session-scoped sentinel file.

Registered as:
  PostToolUse(EnterPlanMode) -> writes the sentinel
  PostToolUse(ExitPlanMode)  -> deletes the sentinel
  PreToolUse(Edit|Write|MultiEdit) -> injects a warning if the sentinel is active
                                      and the target file is not a plan doc;
                                      for plan-doc writes, verifies the observed
                                      planning-leg model (see below)

The sentinel lives at:
  ~/.pilot/sessions/<session_id>/plan-mode-active

Purpose: ensure spec-implement never runs on Opus because ExitPlanMode was
accidentally skipped. The warning gives the model one last chance to call
ExitPlanMode before touching implementation files. Plan mode is only entered
by /spec in AUTOMATED Model Switching mode; Manual/Off never toggle it.

Planning-leg model check (Automated mode only): plan mode under opusplan
must run on Opus - but Claude Code can silently serve the Sonnet leg instead
(Opus usage-limit fallback, a conversation grown past the plan leg's
effective ~200K window - currently even with the Opus 1M entitlement, an
upstream regression (anthropics/claude-code#65512) - or the session was
never on the opusplan model). EnterPlanMode itself cannot observe this (the statusline has
not re-rendered in the new mode yet), so the check runs once the statusline
cache carries a post-lever render (cache mtime > sentinel mtime), whose
model_id is authoritative. Both outcomes are injected once per planning leg:
a mismatch warning so the workflow reports the real model instead of narrating
an unverified "switched to Opus", and an Opus confirmation so a switch that DID
work is visible. Claude Code prints nothing either way -- there is no "switching
to Opus" message in any 2.1.x build, and the skip conditions log at `warn` level
-- so warning-only left a working switch indistinguishable from a broken one.

The check is exposed as `planning_leg_model_context` because the plan-doc
write is far too rare an anchor on its own: the plan file is written right
after EnterPlanMode (while the cache-mtime gate still suppresses the check)
and then left alone while the model explores -- which is exactly when the
conversation crosses 200K and the downgrade happens. `context_monitor` runs
it on every tool call so the flip is caught in the turn it occurs.
"""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lib.util import (
    _sessions_base,
    pre_tool_use_context,
    read_hook_stdin,
    read_model_switch_mode,
    resolve_session_id,
)
from spec_mode_guard import _is_opus

try:
    from _lib.util import (
        PLAN_MODE_SENTINEL,
        PRE_PLAN_MODE_RECORD,
        record_plan_leg_owner,
        spec_plan_awaiting_approval,
    )
except ImportError:  # version-skewed _lib predating these names: legacy behavior
    PLAN_MODE_SENTINEL = "plan-mode-active"
    PRE_PLAN_MODE_RECORD = "pre-plan-permission-mode"

    def spec_plan_awaiting_approval(session_id: str | None = None) -> bool:
        return False

    def record_plan_leg_owner(session_id: str | None = None) -> None:
        return None


_WARNING = (
    "[Pilot] PLAN MODE STILL ACTIVE - ExitPlanMode has NOT been called yet. "
    "Keep edits within the runtime's permitted plan file. Finish native planning "
    "and its approval boundary before editing implementation files."
)

_PRE_APPROVAL_WARNING = (
    "[Pilot] SPEC PLAN NOT APPROVED - you are editing a non-plan file during "
    "the /spec planning leg. Keep edits within the runtime's permitted draft. "
    "Finish planning and use its native approval boundary before implementation. "
    "A Pilot status marker does not override native plan-mode restrictions."
)

# Written once per planning leg when the model check below fires; reset by the
# next EnterPlanMode so a new leg (uneven switching) gets a fresh report.
# The confirm and warn paths keep SEPARATE markers on purpose: a leg that starts
# on Opus and is silently downgraded past 200K mid-exploration must still get its
# warning, which a shared marker would swallow.
PLAN_MODEL_WARNED_MARKER = "plan-model-warned"
PLAN_MODEL_CONFIRMED_MARKER = "plan-model-confirmed"

_MODEL_MISMATCH_WARNING = (
    "[Pilot] PLANNING-LEG MODEL CHECK: Automated Model Switching is on and plan "
    "mode is active, but the observed session model is '{model_id}' - planning "
    "is NOT running on Opus. The cause is not established by this observation. "
    "The user can check /model opusplan and /usage for selection or usage limit "
    "fallback, or choose Manual model switching. Mention the actual model once "
    "and continue planning. Do not restart, force compaction, or claim a switch "
    "that the runtime has not confirmed."
)

_MODEL_CONFIRMED_NOTICE = (
    "[Pilot] PLANNING-LEG MODEL CHECK: plan mode is active and the observed "
    "session model is '{model_id}' -- the opusplan switch to Opus took effect. "
    "Claude Code prints nothing of its own when this works, so state it once, "
    "in one short sentence, the first time you report planning progress to the "
    "user (e.g. 'Planning is running on Opus.'). Then continue planning; do not "
    "repeat it and do not re-call EnterPlanMode."
)


def sentinel_path(session_id: str | None = None) -> Path:
    """``session_id`` is a caller-resolved id (env chain first, hook payload
    fallback); ``None`` keeps the env-only resolution. The payload fallback is
    what keeps an env-less session's sentinel out of the shared "default"
    bucket, where a SIBLING same-repo session would read it back as its own."""
    session_dir = _sessions_base() / (session_id or resolve_session_id())
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir / PLAN_MODE_SENTINEL


def planning_leg_model_context(session_id: str | None = None) -> str | None:
    """Report the observed planning-leg model: confirmation on Opus, warning otherwise.

    Fires at most once per planning leg PER OUTCOME, and only on evidence: the
    statusline cache must carry a render newer than the EnterPlanMode sentinel
    (an older render still shows the pre-lever leg and proves nothing). Opus is
    the only expected leg (Automated's pair is fixed); anything else -- Sonnet,
    Haiku, even a Fable render -- means the opusplan plan-mode switch did not
    take effect.

    Both outcomes are reported because Claude Code itself prints nothing either
    way: the opusplan upgrade is silent on success (there is no "switching to
    Opus" message in any 2.1.x build) and its skip conditions log at `warn`
    level, invisible in the UI. Reporting only the failure left a working switch
    indistinguishable from a broken one, which users read as the switch failing.

    Separate markers per outcome keep the mid-planning downgrade catchable: a
    leg confirmed on Opus that later crosses 200K still gets its warning. Each
    marker is claimed with an exclusive create, not check-then-write, because
    parallel tool calls put several hook processes on this line at once.

    Called from two anchors: the plan-doc write below, and every tool call via
    `context_monitor` (see that hook's `_planning_leg_notice`). The downgrade
    lands mid-exploration, when the plan file has not been touched for a while,
    so the plan-doc anchor alone misses it.
    """
    if read_model_switch_mode() != "automated":
        return None

    sentinel = sentinel_path(session_id)
    session_dir = sentinel.parent

    cache = session_dir / "context-pct.json"
    try:
        sentinel_mtime = sentinel.stat().st_mtime
        cache_mtime = cache.stat().st_mtime
        data = json.loads(cache.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    if cache_mtime <= sentinel_mtime:
        return None

    model_id = data.get("model_id") if isinstance(data, dict) else None
    if not isinstance(model_id, str) or not model_id:
        return None

    if _is_opus(model_id):
        marker = session_dir / PLAN_MODEL_CONFIRMED_MARKER
        notice = _MODEL_CONFIRMED_NOTICE
    else:
        marker = session_dir / PLAN_MODEL_WARNED_MARKER
        notice = _MODEL_MISMATCH_WARNING
    # Claim the marker atomically (O_CREAT|O_EXCL). Claude Code runs tools in
    # parallel and fires PostToolUse per tool, so overlapping hook processes
    # reach this line at once; a check-then-write would let every one of them
    # observe "no marker" and emit the same notice. Exactly one create wins.
    # An unwritable session dir stays silent rather than re-emitting each turn.
    try:
        marker.touch(exist_ok=False)
    except (FileExistsError, OSError):
        return None
    return notice.format(model_id=model_id)


def is_plan_file(file_path: str) -> bool:
    """Return True for plan doc files - legitimate writes during planning.

    Covers both registered-run directories: docs/plans/*.md for `/spec` plans
    and docs/builds/*.md for `/build` Buildouts.
    """
    p = Path(file_path)
    return p.suffix.lower() == ".md" and bool({"plans", "builds"} & set(p.parts))


def main() -> int:
    data = read_hook_stdin()
    tool_name = data.get("tool_name", "")
    is_post = "tool_response" in data
    # Env chain first (the id every writer in this session used), payload
    # fallback so an env-less session never reads/writes the shared "default"
    # bucket a sibling same-repo session's state lives in.
    sid = resolve_session_id(str(data.get("session_id") or ""))

    if data.get("hook_event_name") == "PostToolUseFailure":
        if tool_name == "EnterPlanMode":
            from native_plan_capture import finish_native_spec_entry

            finish_native_spec_entry(sid, str(data.get("tool_use_id") or ""), {"is_error": True}, "")
        return 0

    if is_post:
        # PostToolUse: update sentinel state
        if tool_name == "EnterPlanMode":
            response = data.get("tool_response")
            from native_plan_capture import finish_native_spec_entry

            leg_id = uuid.uuid4().hex
            finish_native_spec_entry(sid, str(data.get("tool_use_id") or ""), response, leg_id)
            if not isinstance(response, dict) or response.get("is_error"):
                # A failed EnterPlanMode means plan mode never engaged.
                return 0
            sentinel = sentinel_path(sid)
            sentinel.write_text(leg_id)
            # New planning leg: allow the model check to report again.
            (sentinel.parent / PLAN_MODEL_WARNED_MARKER).unlink(missing_ok=True)
            (sentinel.parent / PLAN_MODEL_CONFIRMED_MARKER).unlink(missing_ok=True)
        elif tool_name == "ExitPlanMode":
            response = data.get("tool_response")
            if not isinstance(response, dict):
                return 0
            if response.get("is_error"):
                message = str(response.get("message", "")).strip().lower().rstrip(".")
                if message not in {"not in plan mode", "not currently in plan mode"}:
                    return 0  # a rejected/failed exit does not prove the mode changed
            sentinel_path(sid).unlink(missing_ok=True)
    else:
        # PreToolUse(EnterPlanMode): the mode has not flipped to "plan" yet,
        # so permission_mode is the pre-plan mode. Record it as the bypass
        # evidence auto_approve_plan requires to arm the post-exit restore
        # (a shift-tab plan entry records nothing - it never calls the tool).
        if tool_name == "EnterPlanMode":
            from native_plan_capture import begin_native_spec_entry

            (sentinel_path(sid).parent / "bypass-restore-pending").unlink(missing_ok=True)
            begin_native_spec_entry(sid, str(data.get("tool_use_id") or ""))
            # Classify who this plan-mode leg belongs to BEFORE it opens. The
            # run state at exit cannot tell a /spec planning leg from native
            # plan mode opened on top of an already-approved run, so the answer
            # is captured here and read back by auto_approve_plan.
            record_plan_leg_owner(sid)
            record = sentinel_path(sid).parent / PRE_PLAN_MODE_RECORD
            mode = data.get("permission_mode")
            if isinstance(mode, str) and mode:
                record.write_text(mode)
            else:
                # No field (older Claude Code): clear stale evidence so a
                # previous leg's record cannot arm a later restore.
                record.unlink(missing_ok=True)
            return 0
        # PreToolUse: warn if editing a non-plan file while plan mode is active
        if not sentinel_path(sid).exists():
            return 0
        file_path = data.get("tool_input", {}).get("file_path", "")
        if not file_path:
            return 0
        from native_plan_capture import observe_native_spec_draft

        observe_native_spec_draft(sid, file_path)
        if is_plan_file(file_path):
            # The statusline has re-rendered since EnterPlanMode, so the observed
            # planning-leg model is now verifiable.
            context = planning_leg_model_context(sid)
            if context:
                print(pre_tool_use_context(context))
            return 0
        # Predicate last: it stats/reads session + plan state (and may shell
        # out to git), so the pure-string checks above short-circuit first.
        if spec_plan_awaiting_approval(sid):
            from native_plan_capture import pending_native_spec

            if pending_native_spec(sid) is not None:
                print(pre_tool_use_context(_WARNING))
                return 0
            # Planning leg with an unapproved plan: auto_approve_plan DENIES
            # ExitPlanMode right now, so the legacy "call ExitPlanMode NOW"
            # instruction would send the model straight into that denial.
            # Keep the edit-time tripwire, but point it at the approval gate.
            print(pre_tool_use_context(_PRE_APPROVAL_WARNING))
        else:
            print(pre_tool_use_context(_WARNING))

    return 0


if __name__ == "__main__":
    sys.exit(main())
