---
sidebar_position: 5
title: Model Routing
description: Drive /model yourself by default, or hand opusplan routing to Claude Code.
---

# Model Routing

:::warning Claude Code only
Model Switching is a Claude Code feature. It is not available in Codex CLI -- on Codex, set the model via `codex --model <name>` or in `~/.codex/config.toml`, and `/spec` runs on whatever model is active.
:::

## Codex model launches

The Console does not maintain a Codex model picker. It reads the model recorded
by Codex sessions, so a newly available model works without a Console settings
migration. Pilot adds a friendly usage label and offline pricing fallback for
known models; unknown models stay visible as unpriced instead of silently
reporting zero cost.

Pilot leaves model and reasoning effort to you in both Codex and Claude Code.
It does not seed a model or effort on fresh installs, and preserves your saved
choices on updates. Choose Astra, Sol, or another available model in your client.
Codex manages its own model catalog; Pilot only requests
[expanded context](./context-optimization.md).

**Model Switching** controls whether `/spec` keeps your selected model or uses Claude Code's native `opusplan` planning and execution legs. Choose the mode for your task and model preferences; implementation and verification can need as much reasoning as planning.

## The Three Modes

**Console -> Settings -> Model Switching** offers three mutually exclusive modes:

| Mode | What happens | Who switches |
|------|--------------|--------------|
| **Automated** | `/spec` uses `opusplan`: the Opus planning leg and Sonnet execution leg, subject to Claude Code's runtime availability | Claude Code, natively |
| **Manual** (default) | `/spec` runs start to finish on your active model and never pauses to switch; interrupt and run `/model` if you want to change mid-run | You, via `/model` |
| **Off** | No model-switch management; the active model runs every phase | Nobody -- the active `/model` choice is retained |

Pilot does **not** remap model aliases behind the scenes in any mode -- your `/model` picker always means what it says.

## Manual (default)

New installs start here. You stay in control of the model at every phase:

1. Select an available model with `/model`, then type `/spec <task>`. Fable 5.1, Opus 5, and other available models can run the whole workflow.
2. Plan, review, approve as usual.
3. After approval, implementation continues immediately on the active model. There is no extra switch prompt or pause. To change models during the run, interrupt and use `/model`.

Disabling Plan Approval removes that configured approval gate; it does not change the model or create another handoff gate.

## Automated

`/spec` drives Claude Code's native `opusplan` model:

- Pilot sets `model: opusplan` (and the matching `ANTHROPIC_MODEL` env pin) in `~/.claude/settings.json` when you select Automated.
- Before entering native plan mode, Pilot prepares the branch/worktree when requested, creates an unapproved plan header in `docs/plans/`, and registers the destination while writes are permitted.
- Planning then uses the draft file permitted by Claude Code's native plan mode. Its native approval presents the completed draft; the capture hook transfers the accepted result into the registered plan. Pilot preserves the native permission choice, completes any deferred configured review, and continues implementation without asking for the same approval again.
- Native restrictions still apply. The `spec_mode_guard` can block an incompatible selected model or a `/spec` invocation made while already in native plan mode. Follow its specific message: select `/model opusplan`, choose Manual/Off, or leave native plan mode through its normal controls before starting `/spec`.

Claude Code decides which model actually serves each request. Pilot checks the observed planning model and reports a mismatch when the expected Opus leg is not active. That observation does not establish the cause: check `/model` and `/usage` for selection or usage limits.

Pilot no longer uses a fixed 180K/200K preflight cutoff or forces compaction to obtain a particular model. A missing notice is not proof of a switch. If the runtime lacks the required native planning tools, Pilot keeps the current model and uses the normal permitted approval path instead of inventing tool support.

## Off

Pilot stays out of model-switch management. Direct requests, native Claude Code workflows, and Pilot workflows use the active `/model` choice; their normal approval and permission requirements still apply. Switching away from Automated removes Pilot's managed `opusplan` setting without selecting a replacement; any model you picked yourself -- including `opusplan` -- is left alone.

## Migration from earlier versions

The old boolean toggle (and the 9.12 configurable Plan/Execution model pair with its window-scoped alias pins) is gone:

| Old setting | New mode |
|-------------|----------|
| Explicit legacy `modelSwitch: true` | Automated |
| Explicit legacy `modelSwitch: false` | Off |
| Missing or invalid setting | Manual |

Explicit mode choices are preserved. Fresh installs and missing settings use Manual, so Automated always requires an opt-in. Updates also retire the old Claude Code effort default when it still matches Pilot's installation baseline; customized effort settings remain yours.

## The env var

Skills and hooks read the mode fresh from `~/.pilot/config.json` (`specWorkflow.modelSwitchMode`), so the next `/spec` sees a Console change without a session restart. A mode change does not itself close an already-open native plan mode or prove that the live model changed. `PILOT_MODEL_SWITCH_MODE` (`automated` | `manual` | `off`) is exported for display and subagents; it is not a fallback that overrides the current configuration.
