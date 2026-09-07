#!/usr/bin/env python3
"""Guard for /spec invocations (UserPromptSubmit hook).

- Always blocks /spec when the user is manually in plan mode (in Automated
  mode the skill, not the user, enters plan mode via EnterPlanMode).
- Preserves the user's permission mode without promoting bypassPermissions.
- Model gate (three-way Model Switching mode, read FRESH from config.json):
    * automated: the session must run `opusplan`, whose non-plan leg is Sonnet,
      so at /spec-submit time a correct user shows Sonnet. A non-Sonnet model
      (e.g. plain Opus or plain Fable) means they are not on `opusplan` --
      blocked, UNLESS settings.json shows `opusplan` is the selected model AND
      the cache is not a Fable id (the async statusline cache may lag the
      `/model opusplan` the user just ran; a Fable cache value, never an
      opusplan resolution, is proof the session is live on Fable and stays
      blocked). A user wrongly on plain Sonnet is indistinguishable from
      opusplan and is allowed (accepted false-negative).
    * manual / off: NO model gate. Manual mode's /spec flow reminds the user
      to pick their planning model themselves; off means Pilot stays out of
      model management entirely.

Reads:
  - `permission_mode` from hook stdin (plan-mode block)
  - the Model Switching mode fresh from ~/.pilot/config.json ("manual" fallback)
  - `model_id` from the statusline cache at ``~/.pilot/sessions/<sid>/context-pct.json``
  - `model` from ``$CLAUDE_CONFIG_DIR/settings.json`` (the *selected* alias,
    persisted synchronously by `/model`) as the opusplan tie-breaker
"""

from __future__ import annotations

import json
import re
import shlex
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lib.util import claude_config_dir, read_model_switch_mode, resolve_session_id

_CLAUDE_OPUS_PREFIX_RE = re.compile(r"^claude-opus(-|$)")
_CLAUDE_SONNET_PREFIX_RE = re.compile(r"^claude-sonnet(-|$)")
_CLAUDE_FABLE_MYTHOS_PREFIX_RE = re.compile(r"^claude-(fable|mythos)(-|$)")


_TRAILING_1M_RE = re.compile(r"(?:\[1[mM]\])+$")


def _strip_1m(model: str) -> str:
    """Strip trailing ``[1m]``/``[1M]`` alias suffixes (including doubled ones).

    Real-world cache values can carry a doubled suffix (env var + model name
    concatenation) and statusline renders may uppercase it. Anchored at the end
    so mid-string occurrences are never touched.
    """
    return _TRAILING_1M_RE.sub("", model)


def _is_opus(model: str) -> bool:
    """Return True iff ``model`` resolves to an Opus alias or explicit Opus ID.

    Strips the ``[1m]`` alias suffix (explicit IDs may legitimately carry it,
    e.g. ``claude-opus-4-8[1m]``). Accepts the bare ``opus`` alias and any
    explicit ID matching ``claude-opus(-|$)`` so misspellings like
    ``claude-opusculus-1`` are rejected.
    """
    if not isinstance(model, str) or not model:
        return False
    base = _strip_1m(model)
    if base == "opus":
        return True
    return bool(_CLAUDE_OPUS_PREFIX_RE.match(base))


def _is_sonnet(model: str) -> bool:
    """Return True iff ``model`` resolves to a Sonnet alias or explicit Sonnet ID.

    Mirror of :func:`_is_opus`. Under Model Switching ON the session runs the
    ``opusplan`` model, whose non-plan leg is Sonnet -- so at ``/spec``-submit
    time (before plan mode) a correctly-configured user resolves to Sonnet.
    Accepts the bare ``sonnet`` alias and any explicit ID matching
    ``claude-sonnet(-|$)``; rejects lookalikes like ``claude-sonnetics-1``.
    """
    if not isinstance(model, str) or not model:
        return False
    base = _strip_1m(model)
    if base == "sonnet":
        return True
    return bool(_CLAUDE_SONNET_PREFIX_RE.match(base))


def _is_fable(model: str) -> bool:
    """Return True iff ``model`` is a Fable-family alias or explicit ID.

    Mirror of :func:`_is_opus`. Fable-class models (Fable 5.x, Mythos 5.x) have no
    plan/execute alias split, so under Automated they are blocked (opusplan is
    required); under Manual/Off there is no gate at all. Accepts the bare ``fable``,
    ``mythos``, and ``best`` aliases (``best`` resolves to Fable where
    available) and any explicit ID matching ``claude-(fable|mythos)(-|$)``
    (e.g. ``claude-fable-5``); rejects lookalikes like ``claude-fabletastic-1``.

    Accepted set is kept byte-identical to
    ``launcher/model_config.py::_is_fable_family`` (vendored mirror -- the
    package boundary forbids imports between hooks and launcher).
    """
    if not isinstance(model, str) or not model:
        return False
    base = _strip_1m(model)
    if base in ("fable", "mythos", "best"):
        return True
    return bool(_CLAUDE_FABLE_MYTHOS_PREFIX_RE.match(base))


def _is_opusplan(model: str) -> bool:
    """Return True iff ``model`` is the opusplan alias.

    Mirror of :func:`_is_opus`. Matches the bare ``opusplan`` alias after
    stripping the ``[1m]`` suffix, so a legacy ``opusplan[1m]`` value an older
    Pilot wrote to settings.json still counts.
    """
    if not isinstance(model, str) or not model:
        return False
    return _strip_1m(model) == "opusplan"


def _managed_opusplan_pin_present() -> bool:
    """True when settings.json env carries a Pilot-managed ANTHROPIC_MODEL pin.

    In Automated mode the env pin outranks the ``model`` field on the next
    session start, so a Fable-family ``model`` value alongside the managed pin
    still boots as opusplan -- the pin, not the field, is decisive there.
    """
    claude_dir = claude_config_dir()
    if claude_dir is None:
        return False
    try:
        data = json.loads((claude_dir / "settings.json").read_text())
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return False
    env = data.get("env") if isinstance(data, dict) else None
    pin = env.get("ANTHROPIC_MODEL") if isinstance(env, dict) else None
    return _is_opusplan(pin) if isinstance(pin, str) else False


def _read_selected_model_from_settings() -> str | None:
    """Read the *selected* model alias from Claude Code's settings.json, or None.

    `/model <choice>` persists the selection here synchronously ("saved as your
    default for new sessions"). Unlike the statusline cache -- async, and only
    ever holding the *resolved* model id -- this is where the ``opusplan``
    alias itself is observable. The value is global across sessions while the
    cache is per-session, so it is only consulted as a tie-breaker when the
    cache would block, never to override a cache that already passes the gate.
    """
    claude_dir = claude_config_dir()
    if claude_dir is None:
        return None
    try:
        data = json.loads((claude_dir / "settings.json").read_text())
    except (OSError, json.JSONDecodeError):
        return None
    model = data.get("model") if isinstance(data, dict) else None
    return model if isinstance(model, str) and model else None


def _read_active_model_from_cache() -> str | None:
    """Read ``model_id`` from the statusline cache file, or None if unavailable.

    Falls through cleanly when no statusline render has run yet (e.g. the very
    first prompt after a session starts) — the caller treats None as "skip the
    Opus check" rather than as a block trigger.
    """
    cache_file = Path.home() / ".pilot" / "sessions" / resolve_session_id() / "context-pct.json"
    if not cache_file.exists():
        return None
    try:
        data = json.loads(cache_file.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    model_id = data.get("model_id") if isinstance(data, dict) else None
    return model_id if isinstance(model_id, str) and model_id else None


def _is_spec_invocation(prompt: str) -> bool:
    """Return True iff ``prompt`` is a /spec slash command (not /spec-implement etc.).

    `prompt.startswith("/spec")` overmatches sibling commands such as
    `/spec-implement`, `/spec-verify`, `/spec-plan`, `/spec-bugfix-plan`,
    `/spec-bugfix-verify`, which run on Sonnet under automated model switching
    (the opusplan default leg). Restrict to bare `/spec` or `/spec ` (with
    whitespace before any args).
    """
    if not prompt.startswith("/spec"):
        return False
    after = prompt[len("/spec") :]
    return after == "" or after[:1].isspace()


def _pause_control(prompt: str) -> str | None:
    """Return "pause"/"resume" when the prompt is exactly that dispatcher control.

    `/spec pause` and `/spec resume` drive the discussion-pause marker (dispatcher
    Step 1.0); they start no planning leg, so neither belongs behind the Opus
    gate. Only the exact single-token form counts: `/spec pause the video
    playback feature` is a task description and stays subject to every gate.
    """
    body = prompt[len("/spec") :].strip().lower()
    return body if body in ("pause", "resume") else None


def _is_resume_existing_plan(prompt: str) -> bool:
    """Return True when /spec is resuming an existing plan, not starting a new one.

    The dispatcher routes `/spec <path/to/plan.md>` to existing-plan handling
    (status-based dispatch). Such invocations must NOT be blocked by the Opus
    gate -- the resume path runs on whichever model is active (Sonnet under
    automated model switching) for implementation/verification.

    A "resume" prompt is `/spec` followed by a token ending in `.md` (case
    insensitive). Paths containing spaces are honored when quoted, via shlex.
    A "new plan" prompt is `/spec <free-form task description>` and stays
    subject to the Opus block.
    """
    # Strip the leading "/spec" and any whitespace.
    body = prompt[len("/spec") :].strip()
    if not body:
        return False
    try:
        tokens = shlex.split(body, posix=True)
    except ValueError:
        # Unbalanced quotes — fall back to a permissive whitespace split.
        tokens = body.split(maxsplit=1)
    if not tokens:
        return False
    # First arg only — trailing flags don't change the verdict.
    return tokens[0].lower().endswith(".md")


def run_spec_mode_guard() -> int:
    """Check permission mode and active model before allowing /spec invocation."""
    try:
        hook_data = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        return 0

    prompt = hook_data.get("prompt", "").strip()
    permission_mode = hook_data.get("permission_mode", "")

    if not _is_spec_invocation(prompt):
        return 0

    # `/spec pause` only touches the session's discussion-pause marker --
    # workflow-neutral, so it bypasses every gate, including the plan-mode block
    # (blocking it would strand a paused run behind the nags the pause stops).
    # `/spec resume` re-enters the workflow: it keeps the plan-mode block below
    # and skips only the model gate, like a `/spec <plan.md>` resume.
    control = _pause_control(prompt)
    if control == "pause":
        return 0

    if permission_mode == "plan":
        print(
            json.dumps(
                {
                    "decision": "block",
                    "reason": (
                        "[Pilot] /spec cannot run in Plan mode. "
                        "Leave native Plan mode using its normal controls, then invoke /spec "
                        "in your chosen editing permission mode."
                    ),
                }
            )
        )
        sys.stderr.write("\033[0;31m[Pilot] /spec blocked: Plan mode is incompatible with /spec workflow\033[0m\n")
        return 2

    # The model gate targets the *planning* leg of /spec. Resuming an existing
    # plan (`/spec <path/to/plan.md>`) dispatches to spec-implement / spec-verify,
    # which run on whichever model is active (Sonnet under automated switching).
    # Skipping the gate for resume keeps it reachable on Sonnet.
    if control == "resume" or _is_resume_existing_plan(prompt):
        return 0

    # Model gate -- Automated mode only (mode read FRESH from config.json; env
    # is startup-frozen and a Console change must reach running sessions).
    #
    #   * automated: the session runs the `opusplan` model, whose non-plan leg
    #     is Sonnet. At /spec-submit time the skill has NOT yet entered plan
    #     mode, so a correctly-configured user resolves to *Sonnet*. Anything
    #     else (plain Opus, plain Fable) means they never ran `/model opusplan`
    #     -- block and tell them to fix it. A user wrongly on plain Sonnet is
    #     indistinguishable from opusplan and is allowed (accepted
    #     false-negative, avoids false-blocking every correct user).
    #   * manual / off: NO model gate -- the user drives /model themselves.
    mode = read_model_switch_mode()

    if mode == "automated":
        active_model = _read_active_model_from_cache()
        cache_warn = (
            "\033[0;33m[Pilot] Warning: could not verify active model for /spec "
            "(statusline cache unavailable). Proceeding without the model check -- "
            "if you are not on the opusplan model, run '/model opusplan' before planning.\033[0m\n"
        )
        block_reason = (
            "[Pilot] /spec with Automated Model Switching requires the 'opusplan' model. "
            "Run '/model opusplan' and try again, or switch Model Switching to Manual or Off "
            "(Pilot Console -> Settings) to run /spec on whatever model you pick. "
            "(Resuming an existing plan with '/spec <path/to/plan.md>' is allowed on any model.)"
        )
        block_stderr = (
            "\033[0;31m[Pilot] /spec blocked: Automated Model Switching needs 'opusplan' "
            "(shows as Sonnet before planning) -- plain Fable/Opus won't switch. "
            "Current model: "
            + (active_model or "unknown")
            + ". Run '/model opusplan', or pick Manual/Off in the Console.\033[0m\n"
        )

        model_ok = active_model is not None and _is_sonnet(active_model)

        # The cache can never show 'opusplan' -- only its resolved leg -- so when
        # it would block, consult the alias the user actually SELECTED
        # (settings.json, written synchronously by /model) before issuing model
        # guidance. Read lazily: a passing cache never touches settings.
        if not model_ok:
            selected_model = _read_selected_model_from_settings()
            opusplan_selected = selected_model is not None and _is_opusplan(selected_model)
            if opusplan_selected:
                # A Fable cache value is NEVER an opusplan resolution (opusplan
                # resolves only to Opus or Sonnet), so it is proof the session is
                # live on Fable despite the selection -- block so the switch
                # actually engages. Any other cache value is either correct or a
                # transient post-`/model opusplan` lag -- allow.
                if active_model is not None and _is_fable(active_model):
                    print(json.dumps({"decision": "block", "reason": block_reason}))
                    sys.stderr.write(block_stderr)
                    return 2
            elif active_model is None:
                # Cache may not have been written yet (very first prompt of a
                # fresh session). A Fable-family SELECTION blocks even without a
                # cache (a fresh Fable session must not enter plan mode under
                # Automated) -- UNLESS the managed ANTHROPIC_MODEL env pin is
                # present: the pin outranks the model field on session start,
                # so the session actually boots on opusplan despite the Fable
                # field (the injector deliberately preserves both in Automated).
                if selected_model is not None and _is_fable(selected_model) and not _managed_opusplan_pin_present():
                    print(json.dumps({"decision": "block", "reason": block_reason}))
                    sys.stderr.write(block_stderr)
                    return 2
                sys.stderr.write(cache_warn)
            else:
                print(json.dumps({"decision": "block", "reason": block_reason}))
                sys.stderr.write(block_stderr)
                return 2

    return 0


if __name__ == "__main__":
    sys.exit(run_spec_mode_guard())
