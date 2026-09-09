"""Shared utilities for hook scripts.

This module provides common constants, color codes, session path helpers,
and utility functions used across all hook scripts.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

RED = "\033[0;31m"
YELLOW = "\033[0;33m"
GREEN = "\033[0;32m"
CYAN = "\033[0;36m"
BLUE = "\033[0;34m"
MAGENTA = "\033[0;35m"
NC = "\033[0m"

FILE_LENGTH_WARN = 800
FILE_LENGTH_CRITICAL = 1000

_AUTOCOMPACT_BUFFER_TOKENS = 33_000

_VALID_MODEL_SWITCH_MODES = ("automated", "manual", "off")


def read_model_switch_mode() -> str:
    """Resolve the Model Switching mode FRESH from ~/.pilot/config.json.

    Session env vars are startup-frozen, so a Console mode change would be
    invisible to running sessions if hooks read $PILOT_MODEL_SWITCH_MODE alone.
    Resolution order: valid ``specWorkflow.modelSwitchMode`` from config.json ->
    legacy ``modelSwitch`` mapping (false -> "off", true -> "automated") ->
    "manual". Mirrors ``launcher.model_config.get_model_switch_mode``
    (vendored: hooks cannot import the Cython-compiled launcher). Reuses
    :func:`_read_pilot_config` so the config-read contract lives in one place.
    """
    config = _read_pilot_config()
    if config is not None:
        workflow = config.get("specWorkflow")
        if isinstance(workflow, dict):
            mode = workflow.get("modelSwitchMode")
            if isinstance(mode, str) and mode in _VALID_MODEL_SWITCH_MODES:
                return mode
            if workflow.get("modelSwitch") is False:
                return "off"
            if workflow.get("modelSwitch") is True:
                return "automated"
    # Unreadable/missing config falls back to "manual" -- the SAME default
    # the launcher's get_model_switch_mode uses, so hooks, skills, statusline,
    # and writers can never disagree on the effective mode.
    # ($PILOT_MODEL_SWITCH_MODE is display/subagent metadata, deliberately NOT a
    # decision fallback: it is startup-frozen and could contradict a launcher
    # that already fell back.)
    return "manual"


def _get_max_context_tokens() -> int:
    """Return context window size, auto-detected from Claude Code statusline.

    Reads context_window_size from the session cache (written by the statusline
    formatter from Claude Code's reported window size). Falls back to 200K
    if no cache exists yet (e.g., before the first statusline update).
    """
    try:
        cache_file = Path.home() / ".pilot" / "sessions" / resolve_session_id() / "context-pct.json"
        if cache_file.exists():
            data = json.loads(cache_file.read_text())
            window = data.get("context_window_size")
            if isinstance(window, int) and window > 0:
                return window
    except Exception:
        pass
    return 200_000


def _compaction_threshold_pct_for(window: int) -> float:
    """Return compaction threshold % for a specific window size."""
    return (window - _AUTOCOMPACT_BUFFER_TOKENS) / window * 100


def _get_compaction_threshold_pct() -> float:
    """Return compaction threshold as percentage of total context window.

    Formula: (window_size - buffer) / window_size * 100
    - 200K context: 83.5%
    - 1M context:  96.7%
    """
    return _compaction_threshold_pct_for(_get_max_context_tokens())


# ---------------------------------------------------------------------------
# Active-plan helpers
#
# Per-skill model overrides have been removed (config schema v12) — the active
# model is whatever Claude Code's `/model` set for the session. The context
# monitor therefore relies on the live statusline `context_window_size` alone
# and no longer needs orchestrator-aware window scaling. The helpers below
# remain because spec_stop_guard and notify code still consume active_plan.json.
# ---------------------------------------------------------------------------

_APPROVED_RE: re.Pattern[str] = re.compile(r"^Approved:\s*(\w+)\s*$", re.MULTILINE)
_TYPE_RE: re.Pattern[str] = re.compile(r"^Type:\s*(\w+)\s*$", re.MULTILINE)


def _read_active_plan(session_id: str | None = None) -> dict | None:
    """Read ~/.pilot/sessions/<session-id>/active_plan.json or return None.

    ``session_id`` is a caller-resolved id (env chain first, hook payload
    fallback - see :func:`resolve_session_id`); ``None`` keeps the env-only
    resolution. Passing the payload-resolved id is what keeps an env-less
    session from reading a SIBLING session's plan out of the shared "default"
    bucket - a bleed ``plan_in_current_project`` cannot catch when both
    sessions run in the same repo.
    """
    plan_file = get_session_plan_path(session_id)
    if not plan_file.exists():
        return None
    try:
        data = json.loads(plan_file.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    return data if isinstance(data, dict) else None


def plan_registered_by_other_session(plan_file: Path, session_id: str) -> bool:
    """True when a session OTHER than ``session_id`` has ``plan_file`` registered.

    Used by the planning stop guard's fallback: a plan file that a sibling session
    owns must not satisfy THIS session's "did you create your plan?" check.

    Fails CLOSED. A sibling ``active_plan.json`` that cannot be parsed -- a torn
    write, a crashed session -- returns True rather than being skipped. Skipping it
    would make the candidate look unowned, the fallback would accept it, and the
    guard would pass exactly when a sibling probably owned the file. Blocking is
    the cheap direction: it tells the session to keep working on its own plan.

    Deliberately id-comparing only, with no liveness probe. Liveness lives in
    ``launcher/session.py`` which hooks cannot import across the package boundary,
    and a stale sibling registration costing one extra "create your plan" nudge is
    the harmless failure.
    """
    try:
        target = os.path.realpath(plan_file)
    except (OSError, ValueError):
        return False

    sessions = _sessions_base()
    if not sessions.is_dir():
        return False

    try:
        candidates = list(sessions.glob("*/active_plan.json")) + list(sessions.glob("*/lanes/*/active_plan.json"))
    except OSError:
        return False

    for candidate in candidates:
        # sessions/<id>/active_plan.json -> <id>; sessions/<id>/lanes/<lane>/... -> <id>
        try:
            owner = candidate.relative_to(sessions).parts[0]
        except ValueError:
            continue
        if owner == session_id:
            continue
        try:
            data = json.loads(candidate.read_text())
            registered = str(data.get("plan_path", ""))
        except (json.JSONDecodeError, OSError, AttributeError, TypeError):
            return True  # fail closed: ambiguous ownership blocks
        if registered and os.path.realpath(registered) == target:
            return True
    return False


def _read_plan_approved_and_type(plan_path: str) -> tuple[bool, str]:
    """Extract Approved (bool) and Type (str) from a plan file body.

    Safe default (False, "Feature") on any read or parse failure — maps to
    spec-plan, the smallest blast radius for a non-impl phase.
    """
    try:
        content = Path(plan_path).read_text()
    except (OSError, UnicodeDecodeError):
        return False, "Feature"
    approved_match = _APPROVED_RE.search(content)
    approved = bool(approved_match and approved_match.group(1).lower() == "yes")
    type_match = _TYPE_RE.search(content)
    plan_type = type_match.group(1) if type_match else "Feature"
    return approved, plan_type


def _infer_active_skill(status: str, approved: bool, plan_type: str) -> str | None:
    """Map (status, approved, type) → orchestrator skill name, or None.

    Returns None for VERIFIED, unknown, or missing.
    """
    s = status.upper() if isinstance(status, str) else ""
    if s == "PENDING":
        if approved:
            return "spec-implement"
        return "spec-bugfix-plan" if plan_type == "Bugfix" else "spec-plan"
    if s == "COMPLETE":
        return "spec-bugfix-verify" if plan_type == "Bugfix" else "spec-verify"
    return None


def _read_pilot_config() -> dict | None:
    """Read ~/.pilot/config.json or return None on missing/corrupt."""
    config_file = Path.home() / ".pilot" / "config.json"
    if not config_file.exists():
        return None
    try:
        data = json.loads(config_file.read_text())
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return None
    return data if isinstance(data, dict) else None


# Ordered session-id sources — see launcher/session.py:_SESSION_ID_ENV_CHAIN for
# the rationale. Duplicated here because hook scripts ship without the launcher
# on sys.path (package boundary). Keep the two chains in sync.
# A native session deliberately never falls back to an old wrapper directory:
# legacy active_plan.json files have no native owner metadata, so claiming one
# would recreate the same cross-session leak this ordering prevents.
_SESSION_ID_ENV_CHAIN = ("CLAUDE_CODE_SESSION_ID", "CODEX_THREAD_ID", "PILOT_SESSION_ID")

# A payload-supplied session id becomes a single path component under
# ~/.pilot/sessions/ - and session_clear DELETES under that path - so anything
# that is not a plain component (separators, dot segments, absolute paths) is
# rejected rather than resolved. Mirrored in launcher/session.py - keep in sync.
_SAFE_SESSION_COMPONENT_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def _is_safe_session_component(value: str) -> bool:
    """True when ``value`` is usable as one directory name under sessions/."""
    return value not in (".", "..") and bool(_SAFE_SESSION_COMPONENT_RE.fullmatch(value))


def resolve_session_id(fallback: object = "") -> str:
    """Resolve the session id from the agent-native env chain.

    Returns the first non-empty agent-native id, then the legacy wrapper id,
    else "default". Agent-native ids are unique per conversation and exported
    to child processes; a wrapper id can be inherited by multiple conversations
    launched under one parent and therefore cannot safely take precedence.

    ``fallback`` (a hook payload's ``session_id``) is consulted ONLY when the whole
    env chain is empty, as a better last resort than the shared "default" bucket.
    A hook subprocess spawned without the env vars would otherwise read another
    session's state — and ``plan_in_current_project`` cannot catch that when the
    stale plan happens to live in the same repo.

    The writer and readers share this ordering, so ``pilot register-plan`` and
    hooks resolve the same native directory whenever one is available. The
    wrapper id remains a compatibility fallback for older agent runtimes.

    Most callers still invoke this with no argument and keep the plain env-chain
    behavior; only spec_stop_guard passes a fallback so far, because its stale-plan
    bleed is the one that has actually bitten. Passing a payload id is safe to adopt
    per hook, but each one needs the writer of the state it reads checked first --
    the fallback only helps where reader and writer resolve to the same id.
    """
    for var in _SESSION_ID_ENV_CHAIN:
        value = os.environ.get(var, "").strip()
        if value:
            return value
    if not isinstance(fallback, str):
        return "default"
    fallback = fallback.strip()
    # Reject a fallback that cannot be a single path component: the id is joined
    # under ~/.pilot/sessions/ and session_clear deletes there, so a traversal
    # value ("../other", "/etc") must degrade to legacy resolution instead.
    if fallback and _is_safe_session_component(fallback):
        return fallback
    return "default"


def resolve_payload_session_id(value: object) -> str:
    """Resolve a payload-first session id without trusting it as a path component.

    Compaction state is keyed by the hook payload so its pre- and post-compaction
    events meet even when the wrapper environment changes between them. Payloads
    are untrusted, though: only a string accepted by the same single-component
    policy as :func:`resolve_session_id` may override the environment chain.
    """
    if isinstance(value, str):
        candidate = value.strip()
        if candidate and _is_safe_session_component(candidate):
            return candidate
    return resolve_session_id()


def resolve_hook_session_id(value: object) -> str:
    """Resolve native hook identity without trusting a stale parent-agent id.

    Native Claude/Codex ids normally match the payload. When they differ, the
    payload names the event being handled while the environment belongs to a
    parent process that launched this client, so the safe payload component
    wins. A legacy ``PILOT_SESSION_ID`` still wins when no native id exists,
    because older wrapper-launched agents wrote their plan under that id.
    """
    payload = ""
    if isinstance(value, str):
        candidate = value.strip()
        if candidate and _is_safe_session_component(candidate):
            payload = candidate

    for variable in ("CLAUDE_CODE_SESSION_ID", "CODEX_THREAD_ID"):
        native = os.environ.get(variable, "").strip()
        if not native:
            continue
        if payload and native != payload:
            return payload
        return native

    legacy = os.environ.get("PILOT_SESSION_ID", "").strip()
    if legacy:
        return legacy
    return payload or "default"


def _sessions_base() -> Path:
    """Get base sessions directory."""
    return Path.home() / ".pilot" / "sessions"


def get_session_cache_path() -> Path:
    """Get session-scoped context cache path."""
    cache_dir = _sessions_base() / resolve_session_id()
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / "context-cache.json"


def get_session_plan_path(session_id: str | None = None) -> Path:
    """Get session-scoped active plan JSON path.

    ``session_id`` lets a hook pass an id it already resolved (env chain first,
    then its payload's ``session_id``) instead of re-deriving it from the env alone.
    """
    return _sessions_base() / (session_id or resolve_session_id()) / "active_plan.json"


def find_git_root() -> Path | None:
    """Find git repository root."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=False,
            timeout=2,
        )
        if result.returncode == 0:
            return Path(result.stdout.strip())
    except Exception:
        pass
    return None


def current_project_root() -> Path | None:
    """Authoritative current project root, or None when it cannot be determined.

    Resolves from CLAUDE_PROJECT_ROOT, else `git rev-parse --show-toplevel`
    (which returns the repo root even when a hook runs from a subdirectory).

    Deliberately does NOT fall back to ``Path.cwd()``: a bare cwd is not an
    authoritative containment boundary. When a hook runs from a project
    subdirectory with git unavailable, cwd is narrower than the real project
    root, and treating it as the boundary makes ``plan_in_current_project``
    wrongly reject a legitimate same-project plan. Returning None makes that
    guard fail open instead — matching its documented intent.
    """
    root = os.environ.get("CLAUDE_PROJECT_ROOT", "").strip()
    if root:
        return Path(root)
    return find_git_root()


PLAN_MODE_SENTINEL = "plan-mode-active"

# Pre-plan permission mode recorded by plan_mode_tracker at
# PreToolUse(EnterPlanMode) - i.e. BEFORE the mode flips to "plan" - and
# consumed by auto_approve_plan as the positive bypass evidence required to
# arm the post-plan-exit bypassPermissions restore.
PRE_PLAN_MODE_RECORD = "pre-plan-permission-mode"


def plan_mode_sentinel_path(session_id: str | None = None) -> Path:
    """Session-scoped plan-mode sentinel path (reader semantics - no mkdir).

    Written/removed by plan_mode_tracker on EnterPlanMode/ExitPlanMode; read by
    auto_approve_plan's deny guard and spec_plan_awaiting_approval below.
    ``session_id`` is a caller-resolved id (see :func:`_read_active_plan`);
    ``None`` keeps the env-only resolution.
    """
    return _sessions_base() / (session_id or resolve_session_id()) / PLAN_MODE_SENTINEL


# Who owns the current plan-mode leg, recorded by plan_mode_tracker at
# PreToolUse(EnterPlanMode) - i.e. at the only moment the answer is knowable.
# See :func:`classify_plan_leg_owner` for why the answer cannot be derived
# later from the run state alone.
PLAN_LEG_OWNER_RECORD = "plan-leg-owner"

# A Pilot planning leg: /spec entered plan mode as its Opus model lever, either
# with nothing registered yet (a fresh run, Step 0.1a precedes Step 2's
# register-plan) or resuming a plan still in its planning phase.
LEG_OWNER_PILOT_PLANNING = "pilot-planning"
# Someone else's plan mode: the user or the model entered it for ordinary work
# while a non-planning run (an approved /spec plan mid-implementation, a locked
# Buildout) was in flight, or no tool call recorded anything at all.
LEG_OWNER_NATIVE = "native"


def _plan_leg_owner_path(session_id: str | None = None) -> Path:
    return _sessions_base() / (session_id or resolve_session_id()) / PLAN_LEG_OWNER_RECORD


def classify_plan_leg_owner(session_id: str | None = None) -> str:
    """Decide who owns a plan-mode leg, from the state at the moment of entry.

    ⛔ This MUST be evaluated at PreToolUse(EnterPlanMode) and stored. It cannot
    be recomputed at exit, because the two cases are indistinguishable by then:
    a `/spec` plan at its Step 12.3 exit is PENDING + `Approved: Yes`, and so is
    an approved plan the model happened to open native plan mode on top of
    during implementation. Asking "is a run registered?" at exit answers "yes"
    for both and hands native plan mode to the `/spec` code path - which is the
    regression this record exists to prevent.

    At ENTRY the two separate cleanly:

    * nothing registered -> a fresh `/spec` planning leg (spec-plan Step 0.1a
      calls EnterPlanMode before Step 2 registers the plan), or genuinely
      nothing at all. Either way no other run can be harmed.
    * a registered run still in its PLANNING phase (PENDING + unapproved,
      Feature/Bugfix) -> `/spec` resuming that plan, which registers at the
      dispatcher's Step 2 and only then enters plan mode.
    * a registered run PAST planning - an approved `/spec` plan being
      implemented, or a `/build` Buildout, which sets `Approved: Yes` the
      moment its contract locks and never enters plan mode at all - means this
      plan mode belongs to somebody else.

    Fails to ``native``: an unreadable plan, an undeterminable project root, any
    exception. Native is the direction that only ever hands control back to
    Claude Code's own dialog.
    """
    try:
        plan_path = registered_pending_plan(session_id)
        if plan_path is None:
            return LEG_OWNER_PILOT_PLANNING
        approved, plan_type = _read_plan_approved_and_type(str(plan_path))
        if plan_type == "Build":
            # /build never enters plan mode, so a sentinel appearing while a
            # Buildout is registered is always somebody else's.
            return LEG_OWNER_NATIVE
        return LEG_OWNER_NATIVE if approved else LEG_OWNER_PILOT_PLANNING
    except Exception:
        return LEG_OWNER_NATIVE


def record_plan_leg_owner(session_id: str | None = None) -> None:
    """Persist :func:`classify_plan_leg_owner` for the leg being entered."""
    record = _plan_leg_owner_path(session_id)
    try:
        record.parent.mkdir(parents=True, exist_ok=True)
        record.write_text(classify_plan_leg_owner(session_id))
    except OSError:
        pass


def read_plan_leg_owner(session_id: str | None = None) -> str:
    """The recorded owner of the open plan-mode leg; ``native`` when unknown.

    A missing record is the normal shape of a shift-tab plan entry: the user
    flipped the mode without any tool call, so no hook ran to classify it. That
    is native plan mode by definition, and it is also the safe default for a
    torn or unreadable record.
    """
    try:
        value = _plan_leg_owner_path(session_id).read_text().strip()
    except (OSError, UnicodeDecodeError):
        return LEG_OWNER_NATIVE
    return value if value == LEG_OWNER_PILOT_PLANNING else LEG_OWNER_NATIVE


def registered_pending_plan(session_id: str | None = None) -> Path | None:
    """Path of this session's registered, in-flight run file, or None.

    "In flight" = ``pilot register-plan`` wrote an ``active_plan.json`` whose
    status is PENDING and whose file still exists inside the current project.
    Deliberately does NOT look at the plan-mode sentinel, so a caller can ask
    "is a Pilot run in progress?" independently of whether plan mode happens to
    be open (the two PostToolUse hooks on ExitPlanMode race over that sentinel).

    Lane-blind on purpose: it reads only this session's own ``active_plan.json``
    slot, matching every other plan reader. Callers that need "is ANY run,
    including an orchestration lane's, in flight" want
    :func:`pilot_run_in_flight` instead - widening THIS function would widen the
    permission gate built on it.

    Fails open (None = no run) on ANY read or parse error. Every consumer of
    this function treats None as "not a Pilot-managed run", which for a
    permission gate is the direction that hands control back to Claude Code.
    """
    try:
        plan = _read_active_plan(session_id)
        if not plan:
            return None
        if str(plan.get("status", "")).upper() != "PENDING":
            return None
        plan_path = Path(str(plan.get("plan_path", "")))
        if not plan_path.is_file():
            return None
        if current_project_root() is None:
            # plan_in_current_project fails open (True) when the root cannot be
            # determined - correct for its legacy consumers, but here that
            # direction is wrong twice over: a stale plan from another repo
            # could deny ExitPlanMode in a non-git cwd, and it could suppress a
            # native-plan capture that belongs to this directory. Bail out.
            return None
        if not plan_in_current_project(plan_path):
            return None
        return plan_path
    except Exception:
        return None


def pilot_run_in_flight(session_id: str | None = None) -> bool:
    """True when ANY registered run may be in flight for this session.

    The union of the session's own ``active_plan.json`` and every orchestration
    lane's (``sessions/<id>/lanes/<lane>/active_plan.json``), because a lane's
    `/spec` owns a plan file the session slot never mentions.

    ⛔ Fails CLOSED - an unreadable or unparseable registration returns True.
    This is the inverse of :func:`registered_pending_plan`, and deliberately so:
    the only consumer is a WRITER deciding whether to skip (native_plan_capture),
    where "I could not tell" must mean "do not write a competing file". Failing
    open there produces a duplicate plan in the Console next to the real run.

    The lane awareness here does not violate the lane-blind rule for plan
    readers: it can only ever cause MORE skipping, never grant a permission or
    resolve a lane's plan as this session's own.
    """
    if _pending_registration(get_session_plan_path(session_id)):
        return True
    try:
        lanes = get_session_plan_path(session_id).parent / "lanes"
        candidates = sorted(lanes.glob("*/active_plan.json")) if lanes.is_dir() else []
    except OSError:
        return True
    return any(_pending_registration(candidate) for candidate in candidates)


def _pending_registration(registration: Path) -> bool:
    """True when ``registration`` names a PENDING run, or cannot be read.

    Fail-closed helper for :func:`pilot_run_in_flight`; see its contract. A
    registration file that does not exist is simply absent, not ambiguous, so
    that alone returns False.
    """
    try:
        if not registration.exists():
            return False
    except OSError:
        return True
    try:
        data = json.loads(registration.read_text())
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return True  # present but unreadable: ambiguous, so assume a live run
    if not isinstance(data, dict):
        return True
    if str(data.get("status", "")).upper() != "PENDING":
        return False
    # A PENDING run in ANOTHER repository is not this directory's business. That
    # happens when no session id can be resolved and several sessions collapse
    # into the shared "default" bucket; without this check one repo's run would
    # mute captures in every other. plan_in_current_project fails open (True)
    # when the root cannot be determined, which keeps this predicate fail-closed.
    try:
        return plan_in_current_project(Path(str(data.get("plan_path", ""))))
    except (OSError, ValueError):
        return True


def spec_plan_leg_active(session_id: str | None = None) -> bool:
    """True while THIS session's open plan-mode leg belongs to `/spec`.

    The discriminator between the two things ExitPlanMode can mean:

    * `/spec` in Automated mode calls EnterPlanMode/ExitPlanMode purely as the
      opusplan model lever, with the real approval at a separate
      AskUserQuestion gate -> True here, and auto_approve_plan owns the
      decision (deny before approval, allow + suppress the redundant dialog
      after).
    * Claude Code's own plan mode, entered by the user or by the model for
      ordinary work -> False here, and ExitPlanMode is left completely alone
      so the native plan-approval dialog reaches the user.

    Three conditions, and all three are load-bearing:

    1. the plan-mode sentinel exists (this session really is in a plan-mode leg);
    2. the leg was classified as `/spec`'s AT ENTRY (see
       :func:`classify_plan_leg_owner` - the state at exit cannot tell the two
       apart, and reading it there is what let a native plan mode opened during
       a live Buildout or implementation run be auto-approved);
    3. a Feature/Bugfix run is registered PENDING in this project right now, so
       an abandoned record from an earlier leg cannot stand in for one.

    Fails open (False) on any error - "not a `/spec` leg" only ever hands
    control back to Claude Code's own dialog.
    """
    try:
        if not plan_mode_sentinel_path(session_id).exists():
            return False
        if read_plan_leg_owner(session_id) != LEG_OWNER_PILOT_PLANNING:
            return False
        plan_path = registered_pending_plan(session_id)
        if plan_path is None:
            return False
        return _read_plan_approved_and_type(str(plan_path))[1] != "Build"
    except Exception:
        return False


def spec_plan_awaiting_approval(session_id: str | None = None) -> bool:
    """True while a `/spec` planning leg is active and its plan is unapproved.

    Deny-guard predicate shared by auto_approve_plan (denies a premature
    ExitPlanMode) and plan_mode_tracker (suppresses its "call ExitPlanMode"
    warning in the same window, so the two hooks never issue contradictory
    instructions). Built on :func:`spec_plan_leg_active`, so a native plan mode
    opened while an unapproved `/spec` plan happens to sit registered is no
    longer denied with a `/spec` message it has nothing to do with.

    Fails open (False) on ANY read or parse error - a guard malfunction must
    never block ExitPlanMode or mute a legitimate warning permanently.
    """
    try:
        if not spec_plan_leg_active(session_id):
            return False
        plan_path = registered_pending_plan(session_id)
        if plan_path is None:
            return False
        approved_match = _APPROVED_RE.search(plan_path.read_text())
        return not (approved_match and approved_match.group(1).lower() == "yes")
    except Exception:
        # Includes unreadable/undecodable plan files: ANY failure means allow.
        return False


def plan_in_current_project(plan_file: Path) -> bool:
    """True if plan_file lives inside the current project root.

    Cross-session bleed guard: when no native, wrapper, or payload session id can
    be resolved, active_plan.json collapses to the shared "default" file and a
    plan from ANOTHER repo can leak into this session. Spec-workflow hooks only
    act on a plan that actually lives in the current project. Fails open (returns
    True -> legacy behavior) when the project root cannot be determined, so
    legitimate guarding is never weakened.
    """
    root = current_project_root()
    if root is None:
        return True
    try:
        root_real = os.path.realpath(root)
        plan_real = os.path.realpath(plan_file)
        return os.path.commonpath([root_real, plan_real]) == root_real
    except (ValueError, OSError):
        return True


def read_hook_stdin() -> dict:
    """Read and parse JSON from stdin.

    Returns empty dict on error or invalid JSON.
    """
    try:
        content = sys.stdin.read()
        if not content:
            return {}
        return json.loads(content)
    except (json.JSONDecodeError, OSError):
        return {}


def get_edited_file_from_stdin() -> Path | None:
    """Get the edited file path from PostToolUse hook stdin."""
    try:
        import select

        if select.select([sys.stdin], [], [], 0)[0]:
            data = json.load(sys.stdin)
            tool_input = data.get("tool_input", {})
            file_path = tool_input.get("file_path")
            if file_path:
                return Path(file_path)
    except Exception:
        pass
    return None


def is_waiting_for_user_input(transcript_path: str) -> bool:
    """Check if Claude's last action was asking the user a question."""
    try:
        transcript = Path(transcript_path)
        if not transcript.exists():
            return False

        last_assistant_msg = None
        with transcript.open() as f:
            for line in f:
                try:
                    msg = json.loads(line)
                    if msg.get("type") == "assistant":
                        last_assistant_msg = msg
                except json.JSONDecodeError:
                    continue

        if not last_assistant_msg:
            return False

        message = last_assistant_msg.get("message", {})
        if not isinstance(message, dict):
            return False

        content = message.get("content", [])
        if not isinstance(content, list):
            return False

        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                if block.get("name") == "AskUserQuestion":
                    return True

        return False
    except OSError:
        return False


def check_file_length(file_path: Path) -> str:
    """Check if file exceeds length thresholds.

    Returns a plain-text warning message or empty string if OK.
    """
    try:
        line_count = len(file_path.read_text().splitlines())
    except Exception:
        return ""

    if line_count > FILE_LENGTH_CRITICAL:
        return (
            f"Note: {file_path.name} has {line_count} lines (>{FILE_LENGTH_CRITICAL}). "
            f"Consider splitting if this file is the focus of your current task."
        )
    elif line_count > FILE_LENGTH_WARN:
        return (
            f"Note: {file_path.name} has {line_count} lines (>{FILE_LENGTH_WARN}). "
            f"Keep an eye on size — no action needed unless you're already refactoring this file."
        )
    return ""


def post_tool_use_context(context: str) -> str:
    """Build suppressed PostToolUse context for the agent only."""
    return json.dumps(
        {
            "continue": True,
            "suppressOutput": True,
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": context,
            },
        }
    )


def pre_tool_use_context(context: str) -> str:
    """Build suppressed PreToolUse context for the agent only."""
    return json.dumps(
        {
            "continue": True,
            "suppressOutput": True,
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": context,
            },
        }
    )


def stop_block(reason: str) -> str:
    """Build Stop block JSON (prevents session stop)."""
    return json.dumps({"decision": "block", "reason": reason})


# ---------------------------------------------------------------------------
# Plan-parsing helpers (best-effort — return [] / None on missing sections)
# ---------------------------------------------------------------------------


def _h2_text(line: str) -> str | None:
    """Return the heading text of an `## ` (h2) line, or None if not an h2."""
    m = re.match(r"^##\s+(.+?)\s*$", line)
    if not m or m.group(1).startswith("#"):
        return None
    return m.group(1).strip()


def _h3_text(line: str) -> str | None:
    """Return the heading text of an `### ` (h3) line, or None if not an h3."""
    m = re.match(r"^###\s+(.+?)\s*$", line)
    if not m or m.group(1).startswith("#"):
        return None
    return m.group(1).strip()


def _extract_section_bullets(content: str, h2: str, h3: str | None = None) -> list[str]:
    """Extract bullet/numbered-list items from a markdown section.

    Codex #3: heading matches are EXACT (after stripping `## ` / `### ` and
    surrounding whitespace), not substring — so `## Behavior Contract` does not
    also match `## Behavior Contract Notes`, and `## Scope` does not match
    `## Scope Considerations`.
    """
    in_target_h2 = False
    in_target_h3 = h3 is None
    items: list[str] = []

    for line in content.splitlines():
        h2_heading = _h2_text(line)
        if h2_heading is not None:
            if h2_heading == h2:
                in_target_h2 = True
                in_target_h3 = h3 is None
            elif in_target_h2:
                break
            else:
                in_target_h2 = False
            continue

        if not in_target_h2:
            continue

        h3_heading = _h3_text(line)
        if h3_heading is not None:
            if h3 is not None and h3_heading == h3:
                in_target_h3 = True
            elif in_target_h3 and h3 is not None:
                break
            continue

        if not in_target_h3:
            continue

        m_bullet = re.match(r"^[-*]\s+(.+)$", line)
        m_num = re.match(r"^\d+\.\s+(.+)$", line)
        if m_bullet:
            items.append(m_bullet.group(1).strip())
        elif m_num:
            items.append(m_num.group(1).strip())

    return items


def extract_plan_goal(path: Path) -> str | None:
    """Return the **Goal:** field from a plan file, or None if absent."""
    try:
        content = path.read_text()
    except (OSError, UnicodeDecodeError):
        return None
    m = re.search(r"^\*\*Goal:\*\*\s*(.+)$", content, re.MULTILINE)
    return m.group(1).strip() if m else None


def _extract_plan_truths_all(path: Path) -> list[str]:
    """Return all Goal Verification truths (uncapped)."""
    try:
        content = path.read_text()
    except (OSError, UnicodeDecodeError):
        return []
    return _extract_section_bullets(content, "Goal Verification", "Truths")


def extract_plan_truths(path: Path) -> list[str]:
    """Return up to 5 Goal Verification truths from a plan file."""
    return _extract_plan_truths_all(path)[:5]


def extract_plan_in_scope(path: Path) -> list[str]:
    """Return In-Scope items from a plan file."""
    try:
        content = path.read_text()
    except (OSError, UnicodeDecodeError):
        return []
    return _extract_section_bullets(content, "Scope", "In Scope")


_BEHAVIOR_CONTRACT_KEY_RE: re.Pattern[str] = re.compile(r"^\*\*([^*]+):\*\*\s*(.+)$")


def extract_behavior_contract(path: Path) -> list[str]:
    """Return Behavior Contract clauses from a bugfix plan file.

    Recognizes two formats:
    - Bullet list: `- When X, expect Y.` (older tests + ad-hoc plans)
    - Canonical paragraph form from spec-bugfix-plan template:
      `**Given:** ...` / `**When:** ...` / `**Currently (bug):** ...` /
      `**Expected (fix):** ...` / `**Anti-regression:** ...`

    Both are common in real bugfix plans. The hash gate requires at least one
    parseable format — without paragraph support, every real bugfix plan
    fell back to a single-row 'Goal' audit (Codex #7).
    """
    try:
        content = path.read_text()
    except (OSError, UnicodeDecodeError):
        return []

    bullets = _extract_section_bullets(content, "Behavior Contract")
    if bullets:
        return bullets

    # Fallback: scan the `## Behavior Contract` section for `**Key:** value` lines.
    paragraphs: list[str] = []
    in_section = False
    for line in content.splitlines():
        if re.match(r"^## [^#]", line):
            if "Behavior Contract" in line:
                in_section = True
            elif in_section:
                break
            else:
                in_section = False
            continue
        if not in_section:
            continue
        m = _BEHAVIOR_CONTRACT_KEY_RE.match(line)
        if m:
            # Reconstruct as "Key: value" — preserve colons inside the value.
            paragraphs.append(f"{m.group(1).strip()}: {m.group(2).strip()}")
    return paragraphs


_BUILD_CRITERION_RE: re.Pattern[str] = re.compile(r"^- \[([ xX])\] Criterion \d+:\s*(.+)$")


def _extract_h2_section(content: str, heading: str) -> str | None:
    """Return the body under an exact `## <heading>` line, or None when absent.

    Exact heading match, not substring: `## Criteria` must not also match
    `## Criteria Notes`. The body runs to the next top-level `## ` heading.
    """
    lines = content.splitlines()
    body: list[str] = []
    in_section = False
    for line in lines:
        if line.startswith("## "):
            if in_section:
                break
            in_section = line[3:].strip() == heading
            continue
        if in_section:
            body.append(line)
    return "\n".join(body) if in_section or body else None


def extract_build_criteria(path: Path) -> list[str]:
    """Return a `/build` Buildout's acceptance criteria, unmet first, tagged with state.

    For a build there is no Goal Verification section — the acceptance criteria
    ARE the verification. Ordering unmet first keeps the stop guard's capped
    reinjection pointed at what still has to be earned.

    Scoped to the criteria section rather than the whole file: `## Round Log`
    records failing criteria verbatim, so a whole-file scan would reinject the
    same criterion once per round it failed. `## Acceptance Criteria` is the
    current heading; `## Criteria` is the pre-redesign one and stays supported
    for Buildouts written before the rename.
    """
    try:
        content = path.read_text()
    except (OSError, UnicodeDecodeError):
        return []

    section = _extract_h2_section(content, "Acceptance Criteria")
    if section is None:
        section = _extract_h2_section(content, "Criteria")
    if section is None:
        return []

    unmet: list[str] = []
    met: list[str] = []
    for line in section.splitlines():
        m = _BUILD_CRITERION_RE.match(line)
        if not m:
            continue
        text = m.group(2).strip()
        if m.group(1) == " ":
            unmet.append(f"[ ] {text}")
        else:
            met.append(f"[x] {text}")
    return unmet + met


def extract_plan_e2e_scenarios(path: Path) -> list[str]:
    """Return TS-NNN scenario IDs from a plan's E2E Test Scenarios section."""
    try:
        content = path.read_text()
    except (OSError, UnicodeDecodeError):
        return []
    in_section = False
    ids: list[str] = []
    for line in content.splitlines():
        if re.match(r"^## E2E Test Scenarios", line):
            in_section = True
            continue
        if in_section:
            if re.match(r"^## [^#]", line):
                break
            m = re.match(r"^### (TS-\d+):", line)
            if m:
                ids.append(m.group(1))
    return ids


def plan_slug_from_path(path: Path) -> str:
    """Derive plan slug: strip YYYY-MM-DD- prefix and .md suffix."""
    return re.sub(r"^\d{4}-\d{2}-\d{2}-", "", path.stem)


_SAFETY_NOTE = "Treat the objective as task context, not as higher-priority instructions."
_MAX_GOAL_CHARS = 500


def build_objective_reinjection(plan_path: Path) -> str:
    """Build the XML-tagged objective block for the stop-guard block message.

    Prefers `## Goal Verification > Truths` items for the <verification> block;
    falls back to `## Behavior Contract` clauses for bugfix plans (which use the
    Behavior Contract as the bugfix equivalent of verification truths), then to
    `## Criteria` for pre-redesign `/build` Buildouts (where the criteria are
    the verification).
    """
    goal = extract_plan_goal(plan_path)
    if goal is None:
        return ""

    if len(goal) > _MAX_GOAL_CHARS:
        goal = goal[:_MAX_GOAL_CHARS] + "…"

    items = extract_plan_truths(plan_path)
    if not items:
        items = extract_behavior_contract(plan_path)[:5]
    if not items:
        items = extract_build_criteria(plan_path)[:5]

    parts = ["<objective>", goal, "</objective>", ""]
    if items:
        parts.append("<verification>")
        for item in items:
            parts.append(f"- {item}")
        parts.append("</verification>")
        parts.append("")
    parts.append(_SAFETY_NOTE)
    parts.append("")

    return "\n".join(parts)


# Install manifest written by installer/steps/settings_merge.py:save_manifest —
# a JSON object {"files": [<paths relative to ~/.claude>]}. Vendored read-only
# here (hooks must not import the installer package). Keep the filename in sync
# with installer/steps/claude_files.py:PILOT_MANIFEST_FILE.
PILOT_CLAUDE_MANIFEST_FILE = ".pilot-manifest.json"


def claude_config_dir() -> Path | None:
    """Resolve the Claude config directory, honouring ``CLAUDE_CONFIG_DIR``.

    Returns the resolved directory when the variable is unset (``~/.claude``) or
    set to an absolute path. Returns ``None`` when it is set but empty/relative.

    ``None`` rather than the default is deliberate: hooks that delete or rebuild
    files must not act on ``~/.claude`` because of a mistyped value - that is the
    profile the user was trying to keep untouched. Callers treat ``None`` as
    "skip all config-dir work".

    Never raises: a hook that throws breaks the user's session. This is the third
    copy of this rule (see installer/claude_paths.py and launcher/config.py);
    hooks may not import either package. Keep the three in lockstep.
    """
    env_dir = os.environ.get("CLAUDE_CONFIG_DIR")
    if env_dir is None:
        return Path.home() / ".claude"
    if not env_dir.strip():
        return None
    path = Path(env_dir)
    return path if path.is_absolute() else None


def pilot_owned_skill_names(claude_dir: Path | None = None) -> set[str]:
    """Return the names of skills Pilot installed, per <config dir>/.pilot-manifest.json.

    A skill is Pilot-owned iff its source manifest ``skills/<name>/manifest.json``
    is tracked in the install manifest. User-created skills are never listed, so
    callers can safely gate/remove only the returned names.

    Returns an empty set when the manifest is missing or unreadable — callers
    MUST treat "unknown" as "touch nothing" so a corrupt/absent manifest never
    causes user skills to be deleted. An invalid ``CLAUDE_CONFIG_DIR`` resolves
    the same way, so a bad value can never surface the personal profile's skills.
    """
    if claude_dir is None:
        claude_dir = claude_config_dir()
        if claude_dir is None:
            return set()
    base = claude_dir
    try:
        data = json.loads((base / PILOT_CLAUDE_MANIFEST_FILE).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return set()
    files = data.get("files", []) if isinstance(data, dict) else []
    names: set[str] = set()
    for rel in files:
        parts = str(rel).split("/")
        if len(parts) == 3 and parts[0] == "skills" and parts[2] == "manifest.json":
            names.add(parts[1])
    return names
