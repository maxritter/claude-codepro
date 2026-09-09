#!/usr/bin/env python3
"""Stop guard for /spec workflow - prevents early finishing when plan is active.

Only allows stopping when:
1. Asking user for plan approval (AskUserQuestion tool)
2. Asking user for an important decision (AskUserQuestion tool)
3. No active plan exists (not in /spec mode)
4. A fresh pause sentinel applies to the plan's current state - the approval wait,
   a /build hand-back, or a verify-phase gate. These are the path for agents that
   cannot emit AskUserQuestion (Codex, and Claude Code subagents dispatched as
   orchestration lanes), which would otherwise answer their own gate rather than
   stop. NONE of them applies to an approved PENDING plan: the implement phase has
   no agent-unilateral pause (see the note where the retired manual-switch
   sentinel was).
5. A plan-bound durable interaction state is paused. UserPromptSubmit owns the
   human/synthetic distinction, and the pause remains authoritative even when
   `stop_hook_active` still describes an enclosing continuation chain. Buildouts
   never honor interaction pauses.
6. User stops again within 60s cooldown (escape hatch) - withheld while
   `stop_hook_active` marks the attempt as the agent's own continuation
7. Runaway cap: after MAX_BLOCKS blocks for the same plan with no user-question
   turn in between, OR MAX_CHAIN_BLOCKS blocks inside one continuation chain,
   emit one escalation block instructing the agent to AskUserQuestion. The next
   block-attempt after escalation is allowed through, breaking pathological
   infinite verify->implement loops. The per-chain bound is the one that matters
   on Claude Code, which silently ends the turn itself after
   CLAUDE_CODE_CONSECUTIVE_BLOCK_CAP consecutive blocks; the session-wide bound
   is the backstop for agents that report no continuation state.

`stop_hook_active` is deliberately NOT a reason to allow a stop: it is true for
every stop attempt after this guard blocks, so honoring it let the guard block
only once per continuation chain and left /build loops free to end mid-round.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
from collections.abc import Callable
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lib.session_artifacts import PAUSE_SENTINELS
from _lib.util import (
    _read_plan_approved_and_type,
    _sessions_base,
    build_objective_reinjection,
    get_session_plan_path,
    is_waiting_for_user_input,
    plan_in_current_project,
    resolve_hook_session_id,
    resolve_session_id,
    stop_block,
)

COOLDOWN_SECONDS = 60
# Session-wide backstop: blocks for the same plan since the last user-question
# turn. This is the only bound an agent that reports no continuation state (Codex
# sends no `stop_hook_active`) ever reaches, so it stays where it was.
MAX_BLOCKS = 30
# Claude Code overrides a Stop hook and ends the turn itself after this many
# consecutive blocks in ONE continuation chain, silently - no message, no
# question, the session simply stops. Documented under "Stop input" in the hooks
# reference.
CLAUDE_CODE_CONSECUTIVE_BLOCK_CAP = 8
# Per-chain bound, which must stay clear of the cap above so the runaway
# escalation (which ends the run by asking the user how to proceed) fires instead
# of being pre-empted by that silent override. At 5: blocks 1-5 are normal, block
# 6 escalates, attempt 7 releases - 6 consecutive blocks, two clear of the cap.
#
# It is deliberately NOT the same counter as MAX_BLOCKS. Measured over the local
# Claude Code transcripts (~/.claude/projects/*/*.jsonl: count Stop-hook attachments
# per session, `hook_blocking_error` = blocked, anything else ends the chain), real
# sessions accumulate up to 7 blocks each but never more than 1 within a single
# chain. So a session-wide counter at this depth would escalate on healthy runs and
# release them - reintroducing the silent stop this guard exists to prevent, at a
# new place. Re-run that count before changing either constant.
MAX_CHAIN_BLOCKS = 5
# Sentinel files older than this are treated as stale (PID reuse, crashed
# session, etc.) and unlinked without being honored. One hour is generous
# enough for any realistic approval-wait interaction.
SENTINEL_MAX_AGE_SECONDS = 3600

APPROVAL_SENTINEL, BUILD_HANDBACK_SENTINEL, VERIFY_GATE_SENTINEL = PAUSE_SENTINELS


def get_stop_guard_path(session_id: str | None = None) -> Path:
    """Get session-scoped stop guard state path."""
    guard_dir = _sessions_base() / (session_id or resolve_session_id())
    guard_dir.mkdir(parents=True, exist_ok=True)
    return guard_dir / "spec-stop-guard"


def get_approval_sentinel_path(session_id: str | None = None) -> Path:
    """Session-scoped path to the plan-approval-pending sentinel.

    Codex converts AskUserQuestion to a plain-text numbered prompt, so
    `is_waiting_for_user_input` (AskUserQuestion-only) never recognizes its
    approval-wait turn. Without a signal the stop guard would block the
    approval-wait stop and inject "IMMEDIATELY continue working", which a literal
    agent obeyed by editing `Approved: No -> Yes` itself and bypassing the user.

    The Codex approval step writes this sentinel before ending its turn; the stop
    guard honors it ONLY while the plan is still unapproved (Approved: No), so the
    implement-phase block (Approved: Yes) is preserved. Stale sentinels (older than
    SENTINEL_MAX_AGE_SECONDS — e.g. PID reuse / crashed session) are
    discarded, not honored.
    """
    guard_dir = _sessions_base() / (session_id or resolve_session_id())
    guard_dir.mkdir(parents=True, exist_ok=True)
    return guard_dir / APPROVAL_SENTINEL


# NO manual-switch sentinel, deliberately, and no agent-unilateral implement-phase
# pause. Manual Model Switching used to end the planning turn after approval so the
# user could run /model, and this guard honored a `manual-switch-pending` file to
# permit that stop. Its predicate was a bare "is the plan approved", which made it
# the ONLY sentinel that granted a stop at Approved: Yes + Status: PENDING -- the
# implement phase -- so /spec could hand back to the user with an approved plan and
# zero tasks done. That sentinel stays retired, and every one-shot gate sentinel is
# qualified away from that state (spec-approval-pending: Approved: No;
# build-handback-pending: Type: Build; verify-gate-pending: Status: COMPLETE).
#
# The one grant that DOES apply there is the plan-bound interaction state read
# near the start of ``main``. UserPromptSubmit writes it only for a real user
# interruption; an agent-discovered decision must use ``pilot plan-state``.


def get_build_handback_sentinel_path(session_id: str | None = None) -> Path:
    """Session-scoped path to the build-handback-pending sentinel.

    ``/build`` runs autonomously and asks nothing after its pre-work scoping
    round, so this sentinel is not for a question -- it is for the hand-backs
    that finish a run WITHOUT reaching ``VERIFIED``, where the guard would
    otherwise hold the session open forever: the four-round ceiling with
    criteria unresolved, the blocked-on-external pause, the unachievable-criteria
    exit, and a run whose verification pass is switched off (which ends
    ``COMPLETE`` by design).

    Honored ONE time (the sentinel is consumed on honor) and only for an
    APPROVED ``Type: Build`` plan, so ``/spec``'s implement-phase block and the
    pre-approval flow are both preserved. Stale sentinels are discarded.
    """
    guard_dir = _sessions_base() / (session_id or resolve_session_id())
    guard_dir.mkdir(parents=True, exist_ok=True)
    return guard_dir / BUILD_HANDBACK_SENTINEL


def get_verify_gate_sentinel_path(session_id: str | None = None) -> Path:
    """Session-scoped path to the verify-gate-pending sentinel.

    ``/spec``'s verify phase puts two decisions to the user: the worktree squash
    merge (``spec-verify`` 8.1.6, ``spec-bugfix-verify`` 4.5) and the code-review
    sign-off that precedes ``Status: VERIFIED`` (``spec-verify`` 10,
    ``spec-bugfix-verify`` 6). Both run with the plan at ``Approved: Yes`` and
    ``Status: COMPLETE`` -- a state neither of the two sentinels above covers, since
    the approval one needs ``Approved: No`` and the hand-back one needs
    ``Type: Build``. An agent that cannot emit ``AskUserQuestion`` therefore had no way to
    pause at either gate and resolved the contradiction by answering it: merging
    unreviewed, or writing ``VERIFIED`` nobody approved.

    Retained through the yield for an APPROVED, non-``Build`` plan so
    UserPromptSubmit can recognize and consume the expected response instead of
    auto-pausing it as a new interruption. It applies only while ``Status: COMPLETE``.
    ``/build`` is excluded because it has no gate after its pre-work scoping round;
    a sentinel it never writes must never release its loop. Stale sentinels are
    discarded, so a crashed run cannot silently disable the guard.
    """
    guard_dir = _sessions_base() / (session_id or resolve_session_id())
    guard_dir.mkdir(parents=True, exist_ok=True)
    return guard_dir / VERIFY_GATE_SENTINEL


def _sentinel_grants_stop(
    sentinel: Path,
    plan_path: Path,
    applies: Callable[[bool, str], bool],
    *,
    consume: bool,
    expected_status: str,
) -> bool:
    """True when a fresh sentinel permits this stop attempt.

    Shared by the three pause sentinels, which differ only in which plan state
    they apply to and whether honoring them burns the sentinel. A sentinel older
    than ``SENTINEL_MAX_AGE_SECONDS`` (PID reuse, crashed session) is discarded
    rather than honored, so a stale file cannot silently disable the guard.

    Empty files remain compatible with existing skill installations. On the first
    reusable grant, the hook upgrades that empty file to a JSON binding for this
    exact plan path and status. A sentinel left by an older plan can then never
    release a newer plan that happens to reuse the same session directory.

    ``applies`` receives the plan's ``(approved, plan_type)``.
    """
    if not sentinel.exists():
        return False
    try:
        age = time.time() - sentinel.stat().st_mtime
    except OSError:
        age = 0.0
    if age > SENTINEL_MAX_AGE_SECONDS:
        sentinel.unlink(missing_ok=True)
        return False

    try:
        raw = sentinel.read_text().strip()
    except OSError:
        return False
    if raw:
        try:
            binding = json.loads(raw)
        except json.JSONDecodeError:
            sentinel.unlink(missing_ok=True)
            return False
        plan_key = os.path.realpath(plan_path)
        if not isinstance(binding, dict) or binding.get("plan_path") != plan_key:
            sentinel.unlink(missing_ok=True)
            return False
        if binding.get("expected_status") != expected_status:
            sentinel.unlink(missing_ok=True)
            return False
        try:
            expected_fingerprint = hashlib.sha256(plan_path.read_bytes()).hexdigest()
        except OSError:
            sentinel.unlink(missing_ok=True)
            return False
        if binding.get("plan_content_fingerprint") != expected_fingerprint:
            sentinel.unlink(missing_ok=True)
            return False

    approved, plan_type = _read_plan_approved_and_type(str(plan_path))
    if not applies(approved, plan_type):
        return False
    if consume:
        sentinel.unlink(missing_ok=True)
    elif not raw:
        plan_key = os.path.realpath(plan_path)
        try:
            content_fingerprint = hashlib.sha256(plan_path.read_bytes()).hexdigest()
        except OSError:
            return False
        binding = {
            "plan_path": plan_key,
            "plan_content_fingerprint": content_fingerprint,
            "expected_status": expected_status,
            "created_at": time.time(),
        }
        try:
            sentinel.write_text(json.dumps(binding))
        except OSError:
            return False
    return True


def find_active_plan(session_id: str | None = None) -> tuple[Path | None, str | None]:
    """Find the active plan for THIS session via session-scoped active_plan.json."""
    plan_json = get_session_plan_path(session_id)
    if not plan_json.exists():
        return None, None

    try:
        data = json.loads(plan_json.read_text())
        plan_path_str = data.get("plan_path", "")
    except (json.JSONDecodeError, OSError):
        return None, None

    if not plan_path_str:
        return None, None

    plan_file = Path(plan_path_str)
    if not plan_file.is_absolute():
        project_root = os.environ.get("CLAUDE_PROJECT_ROOT", str(Path.cwd()))
        plan_file = Path(project_root) / plan_file
    if not plan_file.exists():
        return None, None

    # Cross-session bleed guard: ignore an active plan that isn't part of this
    # project (e.g. a COMPLETE plan from another repo's /spec session leaking in
    # through the shared "default" active_plan.json when no session id resolved).
    if not plan_in_current_project(plan_file):
        return None, None

    try:
        content = plan_file.read_text()
        status_match = re.search(r"^Status:\s*(\w+)", content, re.MULTILINE)
        if not status_match:
            return None, None
        status = status_match.group(1).upper()
        if status not in ("PENDING", "COMPLETE"):
            return None, None
        return plan_file, status
    except OSError:
        return None, None


def _last_assistant_requests_verification_approval(transcript_path: str) -> bool:
    """Recognize the narrow prose fallback for the COMPLETE-state review gate."""
    if not transcript_path:
        return False
    try:
        transcript = Path(transcript_path)
        if not transcript.is_file():
            return False
        last_assistant: dict | None = None
        with transcript.open(encoding="utf-8") as handle:
            for line in handle:
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(event, dict) and event.get("type") == "assistant":
                    last_assistant = event
    except OSError:
        return False
    message = last_assistant.get("message") if isinstance(last_assistant, dict) else None
    blocks = message.get("content") if isinstance(message, dict) else None
    if not isinstance(blocks, list):
        return False
    text = "\n".join(
        block.get("text", "")
        for block in blocks
        if isinstance(block, dict) and block.get("type") == "text" and isinstance(block.get("text"), str)
    )
    has_review_heading = bool(re.search(r"(?im)^## (?:Code Review Gate|Verification Summary)\b", text))
    asks_approval = bool(
        re.search(r"(?i)\b(?:do you approve|please (?:review and )?approve|reply (?:with )?(?:approve|lgtm))\b", text)
    )
    return has_review_heading and asks_approval


def _load_state(state_file: Path) -> dict:
    """Load stop-guard state. Returns {} on any error or missing file.

    Tolerates the legacy plain-float format from earlier versions.
    """
    if not state_file.exists():
        return {}
    try:
        raw = state_file.read_text().strip()
    except OSError:
        return {}
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, ValueError):
        pass
    try:
        return {"ts": float(raw), "count": 1, "plan": ""}
    except ValueError:
        return {}


def _save_state(state_file: Path, state: dict) -> None:
    try:
        state_file.write_text(json.dumps(state))
    except OSError:
        pass


def _registered_interaction_paused(session_id: str, plan_path: Path) -> bool:
    """Whether the active registration carries a valid durable pause."""
    registration = _sessions_base() / session_id / "active_plan.json"
    try:
        data = json.loads(registration.read_text())
    except (OSError, json.JSONDecodeError, TypeError):
        return False
    if not isinstance(data, dict) or os.path.realpath(str(data.get("plan_path", ""))) != os.path.realpath(plan_path):
        return False
    interaction = data.get("interaction")
    if not isinstance(interaction, dict) or interaction.get("state") != "paused":
        return False
    _approved, plan_type = _read_plan_approved_and_type(str(plan_path))
    return plan_type != "Build"


def _save_expected_continuation(state_file: Path, state: dict, reason: str) -> None:
    """Bind the next synthetic UserPromptSubmit event to this Stop reason."""
    state["expected_prompt_sha256"] = hashlib.sha256(reason.encode("utf-8")).hexdigest()
    _save_state(state_file, state)


def _next_action_for(status: str, plan_type: str = "Feature") -> str:
    """Return the outstanding-step instruction for a plan in ``status``.

    The instruction must name the step that is ACTUALLY outstanding. A COMPLETE
    plan has every task checked off, so the generic "next pending task" wording
    reads as "nothing left to do" and the agent stops -- skipping verification
    entirely, which is the one step COMPLETE exists to gate.

    ``/build`` Buildouts (``Type: Build``) count tasks exactly as a plan does,
    but have no verify skill to dispatch: their outstanding step is the next
    task, the next round, or the final blind judge pass, so they get their own
    wording rather than spec's.
    """
    if plan_type == "Build":
        if status == "COMPLETE":
            return (
                "Every task is ticked but the judge pass has not run. IMMEDIATELY re-obtain the "
                "reference if the Buildout names one, then rule every acceptance criterion from "
                "the finished artifact alone, pass or fail, with one line of evidence each. Do "
                "NOT set Status: VERIFIED without that pass, and do NOT summarise the work "
                "instead of judging it."
            )
        return (
            "The build loop is active. Your VERY NEXT action must be a tool call - re-read the "
            "Buildout, work the next unticked task under Progress Tracking, and once EVERY task "
            "is ticked, judge the acceptance criteria. Do NOT judge while a task is unticked, do "
            "NOT tick a criterion without evidence you can point at, and do NOT lower one "
            "silently."
        )
    if status == "COMPLETE":
        return (
            "Implementation is done but the plan has not reached VERIFIED. "
            "Continue with the verify phase: read the plan's `Type:` header, then "
            "use the `spec-verify` skill for a feature plan or the `spec-bugfix-verify` skill "
            "for a bugfix plan, passing the plan path. If its checks are already complete and a "
            "human review decision is pending without a permitted structured question tool, "
            "write `verify-gate-pending` BEFORE presenting the prose question, then yield. Do "
            "not repeatedly print an unarmed question. Do NOT re-implement or mark the plan "
            "VERIFIED without the required user approval."
        )
    return (
        "Continue working on the next pending task in the plan. "
        "Use the current plan and task state to choose the next useful action."
    )


def _block_reason(plan_path: Path, status: str) -> str:
    """Compose the stop-block message for an active plan or `/build` Buildout."""
    approved, plan_type = _read_plan_approved_and_type(str(plan_path))
    is_build = plan_type == "Build"
    workflow = "/build loop" if is_build else "/spec workflow"
    artifact = "Active buildout" if is_build else "Active plan"
    # The discussion-pause escape is /spec's alone: a /build agent taught this
    # exception would touch a marker the guard refuses for Type: Build, and the
    # mismatch reads as a broken guard rather than a denied pause.
    discussion_escape = (
        ""
        if is_build
        else (
            " EXCEPTION - the user is discussing: if the user's LATEST message questioned a "
            "decision, raised a discovery, or asked something the plan does not answer, do "
            "not plough on. Answer them and honor the plan-bound interaction pause created "
            "by UserPromptSubmit. For an agent-discovered material decision, record it with "
            "`pilot plan-state pause --kind decision --message <question>` before asking. "
            "Only exact `resume`, `/spec resume`, or `$spec resume` restarts implementation."
        )
    )
    next_action = _next_action_for(status, plan_type)
    if not approved:
        next_action = (
            "The plan is not approved. Finish planning and obtain approval through this workflow's "
            "approval gate before implementation. Honor any approval already provided or explicit "
            "approval-disabled configuration; do not invent approval to satisfy this guard. "
            "When asking the user, use the workflow's approval-wait mechanism so the turn can end."
        )
    base_reason = (
        f"{workflow} active — cannot stop without user interaction. "
        f"{artifact}: {plan_path} (Status: {status}). "
        f"Stop again within 60s to force exit.\n\n"
        f"{next_action} Do not present unfinished work as complete."
        f"{discussion_escape}"
    )
    objective_block = build_objective_reinjection(plan_path)
    return f"{objective_block}{base_reason}" if objective_block else base_reason


def main() -> int:
    """Check if stopping is allowed based on /spec or /build workflow state."""
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0

    # `stop_hook_active` is true on every stop attempt inside a hook-driven
    # continuation - the agent ending a turn AFTER this guard already blocked once.
    # That is exactly the case the guard exists to hold, so it is never permission
    # to stop. Returning 0 here capped the guard at ONE block per continuation
    # chain, which is how a /build loop ended mid-round with criteria unmet: block,
    # one more turn of work, then a silent exit that no one asked for.
    #
    # It still carries information - the attempt is the AGENT's, not the user's, and
    # a false value marks the start of a new chain - so it is kept, and used both to
    # withhold the user-only cooldown hatch and to scope MAX_CHAIN_BLOCKS below.
    in_hook_continuation = bool(input_data.get("stop_hook_active", False))

    # Native hook payload identity wins over a mismatched native id inherited
    # from a parent Codex/Claude process. A legacy PILOT_SESSION_ID still wins
    # when it is the only environment identity, matching older wrapper writers.
    session_id = resolve_hook_session_id(input_data.get("session_id"))

    plan_path, status = find_active_plan(session_id)
    if plan_path is None or status is None:
        return 0
    transcript_path = str(input_data.get("transcript_path") or "")

    # A durable interaction pause is authoritative for the whole discussion,
    # including a stop attempt whose payload still says stop_hook_active=true.
    # That flag describes the enclosing continuation chain; it does not prove
    # that no user interrupted it. UserPromptSubmit owns the human/synthetic
    # distinction and writes this plan-bound state before the model replies.
    if _registered_interaction_paused(session_id, plan_path):
        get_stop_guard_path(session_id).unlink(missing_ok=True)
        return 0

    # Approval-wait pause for agents that cannot emit AskUserQuestion (Codex):
    # while the plan is still unapproved, a fresh approval-pending sentinel grants
    # permission to stop so the user can actually answer the approval question.
    # Honored ONLY for unapproved plans — once Approved: Yes flips, the
    # implement-phase block re-engages. NOT consumed: the pre-approval flow may
    # legitimately pause more than once while the user deliberates.
    if _sentinel_grants_stop(
        get_approval_sentinel_path(session_id),
        plan_path,
        lambda approved, _type: not approved,
        consume=False,
        expected_status=status,
    ):
        return 0

    # /build hand-back pause: the ways a run finishes WITHOUT reaching VERIFIED
    # (round ceiling, blocked on external, criteria unachievable, verification
    # switched off) all need the session to actually stop while the Buildout is
    # approved and not yet VERIFIED. Honored ONE time, and only for a Type: Build
    # plan, so /spec's implement-phase block is untouched.
    if _sentinel_grants_stop(
        get_build_handback_sentinel_path(session_id),
        plan_path,
        lambda approved, plan_type: approved and plan_type == "Build",
        consume=True,
        expected_status=status,
    ):
        return 0

    # Verify-phase gate pause: the worktree merge and the code-review sign-off both
    # put a decision to the user while the plan is approved and COMPLETE, and an
    # agent with no AskUserQuestion has to yield to let it be answered. Retained
    # until UserPromptSubmit consumes the expected response, and only at COMPLETE,
    # so the implement-phase block (PENDING) is untouched; never for a Buildout.
    if status == "COMPLETE" and _sentinel_grants_stop(
        get_verify_gate_sentinel_path(session_id),
        plan_path,
        lambda approved, plan_type: approved and plan_type != "Build",
        consume=False,
        expected_status=status,
    ):
        return 0

    # Defensive real-client fallback: a model can correctly render the narrow
    # review-gate prose yet forget the preceding sentinel command. Arming it
    # here is no broader than the command the same model is already authorized
    # to run, and prevents one or more runaway continuation nags before the
    # user is allowed to answer. Status/type plus the explicit review heading
    # and approval wording keep ordinary summaries from bypassing the guard.
    if status == "COMPLETE" and _last_assistant_requests_verification_approval(transcript_path):
        sentinel = get_verify_gate_sentinel_path(session_id)
        try:
            sentinel.touch()
        except OSError:
            pass
        else:
            if _sentinel_grants_stop(
                sentinel,
                plan_path,
                lambda approved, plan_type: approved and plan_type != "Build",
                consume=False,
                expected_status=status,
            ):
                get_stop_guard_path(session_id).unlink(missing_ok=True)
                return 0

    state_file = get_stop_guard_path(session_id)
    state = _load_state(state_file)

    plan_key = str(plan_path)
    if state.get("plan") != plan_key:
        state = {"ts": 0.0, "count": 0, "chain": 0, "plan": plan_key}

    if transcript_path and is_waiting_for_user_input(transcript_path):
        state["count"] = 0
        state["chain"] = 0
        state["ts"] = 0.0
        _save_state(state_file, state)
        return 0

    # Double-stop escape hatch, for the USER. Withheld inside a hook-driven
    # continuation: there, a stop landing within COOLDOWN_SECONDS of the last block
    # means the agent produced a near-instant turn - a summary, a sign-off, a
    # "resume when you're ready" - which is the behaviour being guarded against, not
    # a request to exit. A user's force-exit arrives on a fresh turn instead, where
    # the flag is false and this still fires.
    now = time.time()
    last_ts = float(state.get("ts") or 0.0)
    if not in_hook_continuation and last_ts and (now - last_ts) < COOLDOWN_SECONDS:
        state_file.unlink(missing_ok=True)
        return 0

    count = int(state.get("count") or 0)
    # A stop attempt that is not a hook continuation starts a new chain, which is
    # also when Claude Code's own consecutive-block budget resets. Keeping the two
    # in step is what makes MAX_CHAIN_BLOCKS a bound on the harness's silent
    # override rather than a second, tighter session-wide cap.
    chain = int(state.get("chain") or 0) if in_hook_continuation else 0

    # Either bound releasing wipes BOTH counters, by design: the release is the end
    # of the runaway, not a partial reprieve. So the two bounds are not tracked
    # independently across a session - on Claude Code a pathological chain trips the
    # tighter per-chain bound first and resets the session-wide count with it.
    if count > MAX_BLOCKS or chain > MAX_CHAIN_BLOCKS:
        state_file.unlink(missing_ok=True)
        return 0

    state["count"] = count + 1
    state["chain"] = chain + 1
    state["ts"] = now
    _save_state(state_file, state)

    if count + 1 > MAX_BLOCKS or chain + 1 > MAX_CHAIN_BLOCKS:
        # Report the counter that actually tripped: the session-wide one runs ahead
        # of the chain, so max() would overstate how many blocks were consecutive.
        blocks = chain + 1 if chain + 1 > MAX_CHAIN_BLOCKS else count + 1
        reason = (
            f"RUNAWAY GUARD TRIPPED — {blocks} consecutive stop-block attempts on plan "
            f"{plan_path} (Status: {status}) without a user-question turn in between. "
            f"This pattern indicates the agent is stuck in a verify→implement loop and "
            f"burning tokens unsupervised. STOP. Your VERY NEXT action MUST be to ask the user, "
            f"using the structured question mechanism available on this platform, what you were "
            f"doing, what's blocking, and how to proceed (Continue / Pivot / Abandon). Do NOT "
            f"continue working. "
            f"Do NOT make further tool calls before asking. The next stop attempt after this "
            f"one will be allowed through to end the runaway."
        )
        _save_expected_continuation(state_file, state, reason)
        print(stop_block(reason))
        return 0

    reason = _block_reason(plan_path, status)
    _save_expected_continuation(state_file, state, reason)
    print(stop_block(reason))
    return 0


if __name__ == "__main__":
    sys.exit(main())
