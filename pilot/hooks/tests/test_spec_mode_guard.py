"""Tests for explicit workflow mode boundaries and preservation of user choices."""

from __future__ import annotations

import json
import os
from io import StringIO
from unittest.mock import patch

import pytest
from spec_mode_guard import _is_fable, _is_opus, _is_sonnet, run_spec_mode_guard

# Hermetic default for CLAUDE_CONFIG_DIR: the guard reads the selected model
# from <config-dir>/settings.json, and legacy tests must never see the dev
# machine's real ~/.claude/settings.json (a real `model: opusplan` there would
# flip their outcomes). A nonexistent dir makes the read deterministically None.
_NO_CLAUDE_DIR = "/nonexistent/pilot-test-claude-config"


def _run_with_input(
    prompt: str,
    permission_mode: str,
    *,
    mode: str = "off",
    claude_config_dir: str = _NO_CLAUDE_DIR,
) -> tuple[int, str]:
    """Simulate hook invocation. Returns (exit_code, stdout_output).

    By default the cached active model is mocked as None (no cache yet).
    ``mode`` pins the three-way Model Switching mode (the guard reads it fresh
    from config.json in production; tests patch the reader).
    """
    hook_data = {"prompt": prompt, "permission_mode": permission_mode}
    stdin = StringIO(json.dumps(hook_data))
    with (
        patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": claude_config_dir}),
        patch("sys.stdin", stdin),
        patch("sys.stdout", new_callable=StringIO) as stdout,
        patch("spec_mode_guard.read_model_switch_mode", return_value=mode),
        patch("spec_mode_guard._read_active_model_from_cache", return_value=None),
    ):
        code = run_spec_mode_guard()
        return code, stdout.getvalue()


def _run_with_model_cache(
    prompt: str,
    permission_mode: str,
    model_id: str | None,
    *,
    mode: str = "off",
    claude_config_dir: str = _NO_CLAUDE_DIR,
) -> tuple[int, str]:
    """Simulate hook invocation with a specific cached model_id and mode."""
    hook_data = {"prompt": prompt, "permission_mode": permission_mode}
    stdin = StringIO(json.dumps(hook_data))
    with (
        patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": claude_config_dir}),
        patch("sys.stdin", stdin),
        patch("sys.stdout", new_callable=StringIO) as stdout,
        patch("spec_mode_guard.read_model_switch_mode", return_value=mode),
        patch("spec_mode_guard._read_active_model_from_cache", return_value=model_id),
    ):
        code = run_spec_mode_guard()
        return code, stdout.getvalue()


class TestPlanModeBlocking:
    """Plan mode must hard-block /spec."""

    def test_blocks_spec_in_plan_mode(self):
        code, output = _run_with_input("/spec fix login bug", "plan")
        assert code == 2
        result = json.loads(output)
        assert result["decision"] == "block"
        assert "Plan mode" in result["reason"]
        assert "leave" in result["reason"].lower()
        assert "Bypass Permissions" not in result["reason"]

    def test_blocks_bare_spec_in_plan_mode(self):
        code, output = _run_with_input("/spec", "plan")
        assert code == 2
        result = json.loads(output)
        assert result["decision"] == "block"

    def test_blocks_spec_with_path_in_plan_mode(self):
        code, output = _run_with_input("/spec docs/plans/my-plan.md", "plan")
        assert code == 2


class TestBypassPermissionsAllowed:
    """/spec in bypassPermissions mode passes through silently."""

    def test_allows_spec_in_bypass_mode(self):
        code, output = _run_with_input("/spec fix login bug", "bypassPermissions")
        assert code == 0
        assert output == ""

    def test_allows_bare_spec_in_bypass_mode(self):
        code, output = _run_with_input("/spec", "bypassPermissions")
        assert code == 0
        assert output == ""


class TestPermissionModePreserved:
    @pytest.mark.parametrize("permission_mode", ["default", "manual", "acceptEdits", "dontAsk", "auto"])
    def test_respects_permission_choice_without_promoting_bypass(self, permission_mode, capsys):
        code, output = _run_with_input("/spec fix bug", permission_mode)
        assert code == 0
        assert output == ""
        assert capsys.readouterr().err == ""


class TestNonSpecPrompts:
    """Non-/spec prompts pass through regardless of mode."""

    def test_allows_regular_prompt_in_plan_mode(self):
        code, output = _run_with_input("fix the login bug", "plan")
        assert code == 0
        assert output == ""

    def test_allows_regular_prompt_in_default_mode(self):
        code, output = _run_with_input("explain this code", "default")
        assert code == 0
        assert output == ""

    def test_allows_other_commands_in_plan_mode(self):
        code, output = _run_with_input("/setup-rules", "plan")
        assert code == 0
        assert output == ""

    def test_allows_create_skill_in_plan_mode(self):
        code, output = _run_with_input("/create-skill", "plan")
        assert code == 0
        assert output == ""


class TestEdgeCases:
    """Edge cases and malformed input."""

    def test_handles_invalid_json(self):
        stdin = StringIO("not json")
        with patch("sys.stdin", stdin):
            assert run_spec_mode_guard() == 0

    def test_handles_empty_stdin(self):
        stdin = StringIO("")
        with patch("sys.stdin", stdin):
            assert run_spec_mode_guard() == 0

    def test_handles_missing_prompt(self):
        stdin = StringIO(json.dumps({"permission_mode": "plan"}))
        with patch("sys.stdin", stdin), patch("sys.stdout", new_callable=StringIO):
            assert run_spec_mode_guard() == 0

    def test_handles_missing_permission_mode(self):
        code, output = _run_with_input("/spec fix bug", "")
        assert code == 0
        assert output == ""

    def test_handles_empty_prompt(self):
        code, output = _run_with_input("", "plan")
        assert code == 0
        assert output == ""


class TestIsOpus:
    """_is_opus helper accepts the right model strings and rejects the wrong ones."""

    def test_accepts_bare_opus(self) -> None:
        assert _is_opus("opus") is True

    def test_accepts_opus_with_1m_suffix(self) -> None:
        assert _is_opus("opus[1m]") is True

    def test_accepts_explicit_opus_id(self) -> None:
        assert _is_opus("claude-opus-4-6") is True
        assert _is_opus("claude-opus-4-7") is True
        assert _is_opus("claude-opus-4-8") is True

    def test_accepts_explicit_opus_id_with_1m(self) -> None:
        assert _is_opus("claude-opus-4-7[1m]") is True
        assert _is_opus("claude-opus-4-8[1m]") is True

    def test_rejects_sonnet(self) -> None:
        assert _is_opus("sonnet") is False
        assert _is_opus("sonnet[1m]") is False

    def test_rejects_claude_sonnet_id(self) -> None:
        assert _is_opus("claude-sonnet-4-6") is False

    def test_rejects_lookalike_prefix(self) -> None:
        """`claude-opusculus-1` starts with 'claude-opus' but is NOT an Opus model."""
        assert _is_opus("claude-opusculus-1") is False

    def test_rejects_empty_string(self) -> None:
        assert _is_opus("") is False

    def test_rejects_non_string(self) -> None:
        assert _is_opus(None) is False  # type: ignore[arg-type]


class TestIsSonnet:
    """_is_sonnet helper accepts Sonnet model strings and rejects the rest."""

    def test_accepts_bare_sonnet(self) -> None:
        assert _is_sonnet("sonnet") is True

    def test_accepts_sonnet_with_1m_suffix(self) -> None:
        assert _is_sonnet("sonnet[1m]") is True

    def test_accepts_explicit_sonnet_id(self) -> None:
        assert _is_sonnet("claude-sonnet-4-5") is True
        assert _is_sonnet("claude-sonnet-4-6") is True

    def test_accepts_explicit_sonnet_id_with_1m(self) -> None:
        assert _is_sonnet("claude-sonnet-4-6[1m]") is True

    def test_rejects_opus(self) -> None:
        assert _is_sonnet("opus") is False
        assert _is_sonnet("opus[1m]") is False
        assert _is_sonnet("claude-opus-4-8") is False
        assert _is_sonnet("claude-opus-4-8[1m][1m]") is False

    def test_rejects_lookalike_prefix(self) -> None:
        assert _is_sonnet("claude-sonnetics-1") is False

    def test_rejects_empty_string(self) -> None:
        assert _is_sonnet("") is False

    def test_rejects_non_string(self) -> None:
        assert _is_sonnet(None) is False  # type: ignore[arg-type]


class TestIsFable:
    """_is_fable helper accepts Fable model strings and rejects the rest."""

    def test_accepts_bare_fable(self) -> None:
        assert _is_fable("fable") is True
        assert _is_fable("fable[1m]") is True
        # Doubled / uppercase trailing suffixes occur in real cache values.
        assert _is_fable("fable[1m][1m]") is True
        assert _is_fable("fable[1M]") is True
        assert _is_fable("best[1m]") is True

    def test_strip_is_anchored_and_literal(self) -> None:
        # No whitespace normalization, no mid-string stripping -- the
        # normalizer must stay byte-identical to launcher _is_fable_family.
        assert _is_fable(" fable ") is False
        assert _is_fable("fa[1m]ble") is False

    def test_accepts_explicit_fable_id(self) -> None:
        assert _is_fable("claude-fable-5") is True
        assert _is_fable("claude-fable-5[1m]") is True
        # Real-world cache values can carry a doubled [1m] suffix.
        assert _is_fable("claude-fable-5[1m][1m]") is True

    def test_accepts_mythos_alias_and_id(self) -> None:
        assert _is_fable("mythos") is True
        assert _is_fable("claude-mythos-5") is True
        assert _is_fable("claude-mythos-5[1m]") is True

    def test_accepts_best_alias(self) -> None:
        # `best` resolves to Fable where available -- a frontier choice the
        # gate must not downgrade with a '/model opusplan' prompt.
        assert _is_fable("best") is True

    def test_rejects_opus_and_sonnet(self) -> None:
        assert _is_fable("opus") is False
        assert _is_fable("claude-opus-4-8[1m]") is False
        assert _is_fable("sonnet") is False
        assert _is_fable("claude-sonnet-4-6") is False

    def test_rejects_lookalike_prefix(self) -> None:
        assert _is_fable("claude-fabletastic-1") is False

    def test_rejects_empty_and_non_string(self) -> None:
        assert _is_fable("") is False
        assert _is_fable(None) is False  # type: ignore[arg-type]


class TestFableModelGate:
    """Fable passes the gate ONLY when Switching is OFF (single-model Fable).

    Under Switching ON the window-scoped pins remap opusplan's slots, so the
    switch is a no-op on plain Fable (it would plan AND execute on Fable, never
    engaging the configured execution model). Fable is therefore BLOCKED under
    ON and routed to '/model opusplan' or the Model Switching OFF toggle. Under
    OFF a Fable session runs the whole workflow single-model and is allowed.
    """

    # The two toggle states are the only behavioral axes of the gate's
    # or-branch; per-input variants live in TestIsFable (predicate unit tests).

    def test_on_blocks_spec_on_explicit_fable_id(self) -> None:
        code, output = _run_with_model_cache(
            "/spec build a feature", "bypassPermissions", "claude-fable-5[1m]", mode="automated"
        )
        assert code == 2
        reason = json.loads(output)["reason"]
        assert "opusplan" in reason
        assert "Manual" in reason

    def test_on_blocks_bare_fable_alias(self) -> None:
        code, output = _run_with_model_cache("/spec build a feature", "bypassPermissions", "fable", mode="automated")
        assert code == 2
        assert "opusplan" in json.loads(output)["reason"]

    def test_off_allows_spec_on_explicit_fable_id(self) -> None:
        code, output = _run_with_model_cache(
            "/spec build a feature", "bypassPermissions", "claude-fable-5[1m]", mode="off"
        )
        assert code == 0
        assert output == ""


class TestNoGateInManualAndOff:
    """Manual and Off modes have NO model gate: any model may start /spec."""

    def test_off_allows_spec_on_sonnet(self) -> None:
        code, output = _run_with_model_cache("/spec build a feature", "bypassPermissions", "sonnet", mode="off")
        assert code == 0
        assert output == ""

    def test_manual_allows_spec_on_any_model(self) -> None:
        for model in ("sonnet", "opus", "claude-fable-5[1m]", "haiku", None):
            code, output = _run_with_model_cache("/spec build a feature", "bypassPermissions", model, mode="manual")
            assert code == 0, model
            assert output == ""

    def test_plan_mode_block_is_mode_independent(self) -> None:
        """The plan-permission-mode block still fires in every mode."""
        for mode in ("automated", "manual", "off"):
            code, output = _run_with_model_cache("/spec build a feature", "plan", "sonnet", mode=mode)
            assert code == 2, mode
            assert "Plan mode" in json.loads(output)["reason"]


class TestResumeExistingPlanBypass:
    """`/spec <path/to/plan.md>` resumes an existing plan — must NOT be Opus-gated.

    This is the core modelSwitch=true return path: user plans on Opus, then
    switches to Sonnet (Option A: `/model sonnet[1m]` + any prompt; Option B:
    `/clear` + `/spec <plan.md>`). If the guard blocks the resume prompt, the
    entire modelSwitch flow is unreachable on non-Opus.
    """

    def test_resume_on_sonnet_passes_guard(self) -> None:
        code, output = _run_with_model_cache(
            "/spec docs/plans/2026-05-21-build-feature.md", "bypassPermissions", "sonnet"
        )
        assert code == 0
        assert output == ""

    def test_resume_on_sonnet_1m_passes_guard(self) -> None:
        code, output = _run_with_model_cache(
            "/spec docs/plans/2026-05-21-build-feature.md", "bypassPermissions", "sonnet[1m]"
        )
        assert code == 0

    def test_resume_with_explicit_sonnet_id_passes_guard(self) -> None:
        code, output = _run_with_model_cache(
            "/spec docs/plans/2026-05-21-build-feature.md", "bypassPermissions", "claude-sonnet-4-6"
        )
        assert code == 0

    def test_new_plan_on_wrong_model_still_blocks(self) -> None:
        """Sanity: new plan prompts (without a `.md` argument) still hit the
        Automated gate (plain Opus means the user never ran /model opusplan)."""
        code, output = _run_with_model_cache("/spec build a feature", "bypassPermissions", "opus", mode="automated")
        assert code == 2
        result = json.loads(output)
        assert "opusplan" in result["reason"]

    def test_plan_mode_still_blocks_resume(self) -> None:
        """Plan-mode block precedes the resume bypass — fix the permission mode first."""
        code, output = _run_with_model_cache("/spec docs/plans/2026-05-21-build-feature.md", "plan", "sonnet")
        assert code == 2
        result = json.loads(output)
        assert "Plan mode" in result["reason"]

    def test_resume_path_with_trailing_flag_passes_guard(self) -> None:
        """Tokenisation only inspects the first whitespace-delimited token —
        trailing flags/args don't change the verdict."""
        code, output = _run_with_model_cache(
            "/spec docs/plans/2026-05-21-build-feature.md --foo", "bypassPermissions", "sonnet"
        )
        assert code == 0

    def test_resume_with_bare_spec_does_not_match_resume(self) -> None:
        """`/spec` with no argument is NOT a resume -- still subject to the gate."""
        code, output = _run_with_model_cache("/spec", "bypassPermissions", "opus", mode="automated")
        assert code == 2


class TestDiscussionPauseControlBypass:
    """`/spec pause` and `/spec resume` are dispatcher controls, not workflow starts.

    `pause` only changes the active plan's durable interaction state, so it is
    workflow-neutral: no model gate, and legal even in plan mode (blocking it
    would strand a paused run behind the very nags the pause exists to stop).
    `resume` re-enters the workflow, so it keeps the plan-mode block but skips
    the Opus gate exactly like `/spec <path/to/plan.md>` -- implementation runs
    on whatever model is active.
    """

    def test_pause_skips_the_model_gate(self) -> None:
        """Plain Opus would block a new plan -- the pause control must pass anyway."""
        code, output = _run_with_model_cache("/spec pause", "bypassPermissions", "opus", mode="automated")
        assert code == 0
        assert output == ""

    def test_pause_allowed_even_in_plan_mode(self) -> None:
        code, _output = _run_with_model_cache("/spec pause", "plan", "sonnet", mode="automated")
        assert code == 0

    def test_resume_skips_the_model_gate(self) -> None:
        code, output = _run_with_model_cache("/spec resume", "bypassPermissions", "opus", mode="automated")
        assert code == 0
        assert output == ""

    def test_plan_mode_still_blocks_resume(self) -> None:
        code, output = _run_with_model_cache("/spec resume", "plan", "sonnet")
        assert code == 2
        assert "Plan mode" in json.loads(output)["reason"]

    def test_pause_as_first_word_of_a_task_is_not_the_control(self) -> None:
        """Only the exact single-token form is a control -- '/spec pause the video
        playback feature' is a new-plan task description and stays gated."""
        code, output = _run_with_model_cache(
            "/spec pause the video playback feature", "bypassPermissions", "opus", mode="automated"
        )
        assert code == 2
        assert "opusplan" in json.loads(output)["reason"]


class TestSpecFamilyPrefixMatch:
    """Regression for C1: prompt.startswith('/spec') must NOT overmatch sibling
    slash commands (`/spec-implement`, `/spec-verify`, `/spec-plan`,
    `/spec-bugfix-plan`, `/spec-bugfix-verify`). They're designed to run on
    Sonnet during the model-switch handoff and must not trip the Opus gate.
    """

    def test_spec_implement_on_sonnet_not_blocked(self) -> None:
        code, output = _run_with_model_cache("/spec-implement docs/plans/foo.md", "bypassPermissions", "sonnet")
        assert code == 0
        assert output == ""

    def test_spec_verify_on_sonnet_not_blocked(self) -> None:
        code, output = _run_with_model_cache("/spec-verify docs/plans/foo.md", "bypassPermissions", "sonnet")
        assert code == 0
        assert output == ""

    def test_spec_plan_on_sonnet_not_blocked(self) -> None:
        code, output = _run_with_model_cache("/spec-plan", "bypassPermissions", "sonnet")
        assert code == 0
        assert output == ""

    def test_spec_bugfix_plan_on_sonnet_not_blocked(self) -> None:
        code, output = _run_with_model_cache("/spec-bugfix-plan", "bypassPermissions", "sonnet")
        assert code == 0
        assert output == ""

    def test_spec_bugfix_verify_on_sonnet_not_blocked(self) -> None:
        code, output = _run_with_model_cache("/spec-bugfix-verify", "bypassPermissions", "sonnet")
        assert code == 0
        assert output == ""

    def test_spec_underscore_suffix_not_matched(self) -> None:
        """Defensive: `/spec_foo` is not a /spec invocation either."""
        code, output = _run_with_model_cache("/spec_foo bar", "bypassPermissions", "sonnet")
        assert code == 0
        assert output == ""

    def test_plain_spec_with_space_still_blocked(self) -> None:
        """Sanity: `/spec ...` (with whitespace) still triggers the Automated gate."""
        code, output = _run_with_model_cache("/spec build a feature", "bypassPermissions", "opus", mode="automated")
        assert code == 2

    def test_plain_spec_alone_still_blocked(self) -> None:
        """Sanity: bare `/spec` still triggers the Automated gate."""
        code, output = _run_with_model_cache("/spec", "bypassPermissions", "opus", mode="automated")
        assert code == 2


class TestResumePathRobustness:
    """Regression for C2: resume detection must be case-insensitive on `.md`
    and must handle quoted paths containing spaces.
    """

    def test_resume_uppercase_md_extension(self) -> None:
        code, output = _run_with_model_cache("/spec docs/plans/Foo.MD", "bypassPermissions", "sonnet")
        assert code == 0
        assert output == ""

    def test_resume_mixed_case_md_extension(self) -> None:
        code, output = _run_with_model_cache("/spec docs/plans/Foo.Md", "bypassPermissions", "sonnet")
        assert code == 0
        assert output == ""

    def test_resume_double_quoted_path_with_spaces(self) -> None:
        """`/spec "docs/plans/my plan.md"` — shlex must surface this as a single
        token ending in `.md`."""
        code, output = _run_with_model_cache('/spec "docs/plans/my plan.md"', "bypassPermissions", "sonnet")
        assert code == 0
        assert output == ""

    def test_resume_single_quoted_path_with_spaces(self) -> None:
        code, output = _run_with_model_cache("/spec 'docs/plans/my plan.md'", "bypassPermissions", "sonnet")
        assert code == 0
        assert output == ""


class TestCacheMissingEmitsWarning:
    """Regression for C3 (OFF mode): when the statusline cache is missing the
    Opus gate still fails open (per project preference), but it must emit a
    stderr warning so the user knows the Opus check did not run. The toggle is
    pinned OFF so these stay deterministic now that the gate is toggle-aware."""

    def test_warning_emitted_when_cache_missing(self) -> None:
        import io as _io

        hook_data = {"prompt": "/spec build a feature", "permission_mode": "bypassPermissions"}
        stdin = StringIO(json.dumps(hook_data))
        with (
            patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": _NO_CLAUDE_DIR}),
            patch("sys.stdin", stdin),
            patch("sys.stdout", new_callable=StringIO),
            patch("sys.stderr", new_callable=_io.StringIO) as stderr,
            patch("spec_mode_guard.read_model_switch_mode", return_value="automated"),
            patch("spec_mode_guard._read_active_model_from_cache", return_value=None),
        ):
            code = run_spec_mode_guard()
            assert code == 0
            err = stderr.getvalue()
            assert "Pilot" in err
            assert "opusplan" in err

    def test_no_warning_when_cache_has_opus(self) -> None:
        """Sanity: when the cache resolves to Opus, no warning fires."""
        import io as _io

        hook_data = {"prompt": "/spec build a feature", "permission_mode": "bypassPermissions"}
        stdin = StringIO(json.dumps(hook_data))
        with (
            patch("sys.stdin", stdin),
            patch("sys.stdout", new_callable=StringIO),
            patch("sys.stderr", new_callable=_io.StringIO) as stderr,
            patch("spec_mode_guard.read_model_switch_mode", return_value="off"),
            patch("spec_mode_guard._read_active_model_from_cache", return_value="opus"),
        ):
            code = run_spec_mode_guard()
            assert code == 0
            assert stderr.getvalue() == ""

    def test_no_warning_on_resume_path_even_when_cache_missing(self) -> None:
        """Resume invocations bypass the model check entirely -- no warning."""
        import io as _io

        hook_data = {"prompt": "/spec docs/plans/foo.md", "permission_mode": "bypassPermissions"}
        stdin = StringIO(json.dumps(hook_data))
        with (
            patch("sys.stdin", stdin),
            patch("sys.stdout", new_callable=StringIO),
            patch("sys.stderr", new_callable=_io.StringIO) as stderr,
            patch("spec_mode_guard.read_model_switch_mode", return_value="automated"),
            patch("spec_mode_guard._read_active_model_from_cache", return_value=None),
        ):
            code = run_spec_mode_guard()
            assert code == 0
            assert stderr.getvalue() == ""


class TestModelSwitchToggle:
    """With Model Switching ON the active model must be Sonnet (opusplan's
    non-plan leg) -- a non-Sonnet model (e.g. plain Opus) is blocked with a
    `/model opusplan` prompt. With it OFF the model must be Opus. The plan-mode
    block and bypass warning are independent of the toggle.
    """

    def test_on_allows_spec_on_sonnet(self) -> None:
        """ON: a new /spec on Sonnet (the opusplan non-plan leg) is allowed."""
        code, output = _run_with_model_cache("/spec build a feature", "bypassPermissions", "sonnet", mode="automated")
        assert code == 0
        assert output == ""

    def test_on_allows_spec_on_explicit_sonnet_id(self) -> None:
        code, output = _run_with_model_cache(
            "/spec build a feature", "bypassPermissions", "claude-sonnet-4-6", mode="automated"
        )
        assert code == 0
        assert output == ""

    def test_on_blocks_spec_on_plain_opus(self) -> None:
        """ON: plain Opus means the user never ran /model opusplan -- block."""
        code, output = _run_with_model_cache("/spec build a feature", "bypassPermissions", "opus", mode="automated")
        assert code == 2
        result = json.loads(output)
        assert result["decision"] == "block"
        assert "opusplan" in result["reason"]

    def test_on_blocks_spec_on_opus_1m(self) -> None:
        code, output = _run_with_model_cache("/spec build a feature", "bypassPermissions", "opus[1m]", mode="automated")
        assert code == 2
        assert "opusplan" in json.loads(output)["reason"]

    def test_on_blocks_spec_on_explicit_opus_double_suffix(self) -> None:
        """The real-world cache value carries a doubled [1m] suffix -- still blocked."""
        code, output = _run_with_model_cache(
            "/spec build a feature", "bypassPermissions", "claude-opus-4-8[1m][1m]", mode="automated"
        )
        assert code == 2
        assert "opusplan" in json.loads(output)["reason"]

    def test_on_resume_on_opus_not_blocked(self) -> None:
        """ON: resuming an existing plan bypasses the model gate on any model."""
        code, output = _run_with_model_cache(
            "/spec docs/plans/2026-06-03-foo.md", "bypassPermissions", "opus", mode="automated"
        )
        assert code == 0
        assert output == ""

    def test_on_emits_warning_when_cache_missing(self) -> None:
        """ON: cache missing -> fall open but warn (mentions opusplan)."""
        import io as _io

        hook_data = {"prompt": "/spec build a feature", "permission_mode": "bypassPermissions"}
        stdin = StringIO(json.dumps(hook_data))
        with (
            patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": _NO_CLAUDE_DIR}),
            patch("sys.stdin", stdin),
            patch("sys.stdout", new_callable=StringIO),
            patch("sys.stderr", new_callable=_io.StringIO) as stderr,
            patch("spec_mode_guard.read_model_switch_mode", return_value="automated"),
            patch("spec_mode_guard._read_active_model_from_cache", return_value=None),
        ):
            code = run_spec_mode_guard()
            assert code == 0
            err = stderr.getvalue()
            assert "Pilot" in err
            assert "opusplan" in err

    def test_on_still_blocks_manual_plan_mode(self) -> None:
        """ON: the plan-mode block is independent of the toggle -- still blocks."""
        code, output = _run_with_model_cache("/spec build a feature", "plan", "sonnet", mode="automated")
        assert code == 2
        result = json.loads(output)
        assert "Plan mode" in result["reason"]

    def test_off_has_no_model_gate(self) -> None:
        """Off: no model gate at all -- even Sonnet/Haiku pass (user decision)."""
        for model in ("sonnet", "haiku", "opus"):
            code, output = _run_with_model_cache("/spec build a feature", "bypassPermissions", model, mode="off")
            assert code == 0, model
            assert output == ""


class TestOpusplanSelectedModel:
    """The gate consults the *selected* model (settings.json `model`, written
    synchronously by /model) whenever the resolved statusline cache would
    block (Automated mode only -- Manual/Off have no gate). The cache can never
    show 'opusplan' -- only its resolved leg -- so on its own it cannot tell an
    opusplan user from a stale pre-switch render (the "run /model opusplan"
    loop the user just satisfied)."""

    @staticmethod
    def _settings_dir(tmp_path, model: str) -> str:
        (tmp_path / "settings.json").write_text(json.dumps({"model": model}))
        return str(tmp_path)

    def test_on_allows_stale_opus_cache_when_opusplan_selected(self, tmp_path) -> None:
        """ON + /model opusplan just ran: the async cache may still hold the
        pre-switch id. The persisted selection is authoritative -- never block
        the user with the very command they just ran."""
        code, output = _run_with_model_cache(
            "/spec add feature",
            "bypassPermissions",
            "claude-opus-4-8",
            mode="automated",
            claude_config_dir=self._settings_dir(tmp_path, "opusplan"),
        )
        assert code == 0
        assert output == ""

    def test_on_blocks_fable_cache_even_when_opusplan_selected(self, tmp_path) -> None:
        """ON + /model opusplan persisted, but the live session is on Fable (a
        manual `/model fable` overriding the selection): a Fable cache value is
        never an opusplan resolution, so the opusplan selection must NOT rescue
        it -- block so the window-scoped switch actually engages. This is the
        exact hole a plain-Fable session slipped through before."""
        code, output = _run_with_model_cache(
            "/spec add feature",
            "bypassPermissions",
            "claude-fable-5[1m]",
            mode="automated",
            claude_config_dir=self._settings_dir(tmp_path, "opusplan"),
        )
        assert code == 2
        reason = json.loads(output)["reason"]
        assert "opusplan" in reason
        assert "Manual" in reason

    def test_on_missing_cache_with_opusplan_selected_allows_without_warning(self, tmp_path) -> None:
        """ON + opusplan selected + cache never written: the persisted selection
        is positive evidence of a correct configuration, so /spec is allowed
        silently -- no 'could not verify active model' warning. (Documented
        decision: settings.json replaces the missing cache here, it does not
        fall through to the fail-open warn path.)"""
        import io as _io

        hook_data = {"prompt": "/spec add feature", "permission_mode": "bypassPermissions"}
        stdin = StringIO(json.dumps(hook_data))
        with (
            patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": self._settings_dir(tmp_path, "opusplan")}),
            patch("sys.stdin", stdin),
            patch("sys.stdout", new_callable=StringIO) as stdout,
            patch("sys.stderr", new_callable=_io.StringIO) as stderr,
            patch("spec_mode_guard.read_model_switch_mode", return_value="automated"),
            patch("spec_mode_guard._read_active_model_from_cache", return_value=None),
        ):
            code = run_spec_mode_guard()
        assert code == 0
        assert stdout.getvalue() == ""
        assert stderr.getvalue() == ""

    def test_off_opus_cache_wins_over_opusplan_selection(self, tmp_path) -> None:
        """OFF + this session actually on Opus: the per-session cache stays
        primary -- a (global) opusplan settings value must not block it."""
        code, output = _run_with_model_cache(
            "/spec add feature",
            "bypassPermissions",
            "claude-opus-4-8[1m]",
            mode="off",
            claude_config_dir=self._settings_dir(tmp_path, "opusplan"),
        )
        assert code == 0
        assert output == ""


def test_large_context_does_not_predict_a_model_failure_or_require_compaction(tmp_path, capsys):
    """Observe the actual planning model later; a historical cutoff is not a runtime limit."""
    session = tmp_path / ".pilot" / "sessions" / "large-context"
    session.mkdir(parents=True)
    (session / "context-pct.json").write_text(
        json.dumps({"pct": 42, "context_window_size": 1_000_000, "model_id": "sonnet"})
    )
    with (
        patch.dict(os.environ, {"PILOT_SESSION_ID": "large-context"}),
        patch("spec_mode_guard.Path.home", return_value=tmp_path),
    ):
        code, output = _run_with_model_cache("/spec add feature", "default", "sonnet", mode="automated")
    assert code == 0
    assert output == ""
    assert capsys.readouterr().err == ""


class TestFreshConfigModeResolution:
    """The guard reads the mode fresh from config.json -- a Console change must
    reach running sessions whose env is startup-frozen."""

    def test_config_wins_over_stale_env(self, tmp_path) -> None:
        import sys as _sys

        _lib = __import__("_lib.util", fromlist=["util"])
        config = tmp_path / ".pilot" / "config.json"
        config.parent.mkdir(parents=True)
        config.write_text(json.dumps({"specWorkflow": {"modelSwitchMode": "automated"}}))
        with (
            patch.dict(os.environ, {"PILOT_MODEL_SWITCH_MODE": "manual"}),
            patch.object(_lib.Path, "home", return_value=tmp_path),
        ):
            assert _lib.read_model_switch_mode() == "automated"

    def test_manual_fallback_when_config_unreadable(self, tmp_path) -> None:
        # Unified with the launcher's get_model_switch_mode: unreadable config
        # falls back to "manual" (the default) everywhere. The env var is
        # display metadata, deliberately NOT a decision fallback (startup-frozen;
        # readers could otherwise disagree mid-session).
        _lib = __import__("_lib.util", fromlist=["util"])
        with (
            patch.dict(os.environ, {"PILOT_MODEL_SWITCH_MODE": "off"}),
            patch.object(_lib.Path, "home", return_value=tmp_path / "nope"),
        ):
            assert _lib.read_model_switch_mode() == "manual"

    @pytest.mark.parametrize("config", [{}, {"specWorkflow": None}, {"specWorkflow": []}, {"specWorkflow": "manual"}])
    def test_missing_or_malformed_workflow_defaults_to_manual(self, tmp_path, config) -> None:
        _lib = __import__("_lib.util", fromlist=["util"])
        config_path = tmp_path / ".pilot" / "config.json"
        config_path.parent.mkdir(parents=True)
        config_path.write_text(json.dumps(config))
        with patch.object(_lib.Path, "home", return_value=tmp_path):
            assert _lib.read_model_switch_mode() == "manual"

    @pytest.mark.parametrize(
        "workflow, expected",
        [
            ({}, "manual"),
            ({"modelSwitchMode": "invalid"}, "manual"),
            ({"modelSwitch": "true"}, "manual"),
            ({"modelSwitch": True}, "automated"),
            ({"modelSwitch": False}, "off"),
            ({"modelSwitchMode": "manual", "modelSwitch": True}, "manual"),
        ],
    )
    def test_only_explicit_valid_settings_enable_automation(self, tmp_path, workflow, expected) -> None:
        _lib = __import__("_lib.util", fromlist=["util"])
        config = tmp_path / ".pilot" / "config.json"
        config.parent.mkdir(parents=True)
        config.write_text(json.dumps({"specWorkflow": workflow}))
        with patch.object(_lib.Path, "home", return_value=tmp_path):
            assert _lib.read_model_switch_mode() == expected

    def test_legacy_boolean_mapping_in_config(self, tmp_path) -> None:
        _lib = __import__("_lib.util", fromlist=["util"])
        config = tmp_path / ".pilot" / "config.json"
        config.parent.mkdir(parents=True)
        config.write_text(json.dumps({"specWorkflow": {"modelSwitch": False}}))
        with patch.object(_lib.Path, "home", return_value=tmp_path):
            assert _lib.read_model_switch_mode() == "off"
