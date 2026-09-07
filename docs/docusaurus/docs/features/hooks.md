---
sidebar_position: 2
title: Hooks Pipeline
description: Quality and lifecycle hooks for Claude Code and Codex, including context recovery, memory, workflow guards, and SessionEnd handling.
---

# Hooks Pipeline

Lifecycle hooks enforce quality automatically throughout **Claude Code** workflows and connect Pilot's context and memory lifecycle to **Codex**. They are registered in `~/.claude/settings.json` for Claude Code and `~/.codex/hooks.json` for Codex CLI and ChatGPT desktop's Codex runtime. The tables below show which hooks apply to each agent.

Hook guidance is private by default: quality, routing, context, and maintenance findings go to the agent as operational context without a user-facing warning. A hook blocks only for an explicit unavailable Pilot workflow, an active workflow's approval or completion contract, an incompatible `/spec` entry state, or a pre-mutation attempt to edit generated `CLAUDE.md`. License recovery and those pre-mutation denials are the only technical conditions surfaced directly to the user.

Claude Code receives that private guidance with output suppression. Codex tool events receive `additionalContext` without `systemMessage`; Pilot deliberately omits `suppressOutput` there because current Codex releases reject it on PreToolUse and PostToolUse.

Pilot installs and updates its lifecycle integrations as one managed set. The tables below describe the user-relevant behavior of that pipeline.

Codex runs the skill refresh, session registration, memory observer, and turn summarizer as native asynchronous command hooks. Repository synchronization, workflow guards, active-work recovery, and SessionEnd remain synchronous because their result must be observed before the lifecycle event completes. Pilot does not register an MCP hook merely as a transport substitute; an MCP handler belongs here only when an installed server owns a concrete lifecycle operation and returns the hook contract directly.

## SessionStart

*On startup, after `/clear`, or after compaction*

| Hook | Applies to | Description |
|------|------------|-------------|
| `session_announcements.py` | Claude Code | Delivers one-time announcements and re-injects them until acknowledged. |
| `config_dir_guard.py` | Claude Code | Privately tells the agent when the active Claude configuration directory differs from the installed profile; it is surfaced only if the mismatch actually prevents the requested work. |
| `session_startup_maintenance.py` | Claude Code | Cleans stale Claude task files and dead PID-backed session directories. |
| `codegraph_init.py` | Claude Code | Initializes CodeGraph for the current project. |
| Skill sync | Both | Refreshes managed skills for the active agent. |
| Repository asset sync | Both | Silently synchronizes project rules and skills. A bounded scoped-rule index is supplied to the agent as suppressed context without printing in the session UI or hook-status log. |
| Memory synchronization | Both | Refreshes shared storage silently. Agents retrieve task-relevant history and OKF knowledge on demand through `mem-search`; no automatic digest is injected. |
| `post_compact_restore.py` | Both | Re-injects active plan and task state after compaction. |
| `session_clear.py` | Both | Resets Pilot session state after `/clear`. |

## UserPromptSubmit

*When you send a message*

| Hook | Applies to | Description |
|------|------------|-------------|
| `spec_mode_guard.py` | Claude Code | Warns outside bypassPermissions, blocks manual plan mode, and applies the configured `/spec` model-switching checks; Manual/Off modes have no model gate. |
| Session initializer | Both | Registers the session with the Console worker. |

## PreToolUse

*Before Bash, search, or web tools run*

| Hook | Applies to | Description |
|------|------------|-------------|
| `tool_redirect.py` | Claude Code | Privately nudges recursive Bash, built-in search, and web calls toward the preferred indexed/MCP tools without denying the original operation. It also reminds the agent when a shell command edits a project file (`sed -i`, heredocs or redirects into a file, `tee`, inline scripts that write files) that changes belong in `Edit`/`Write`, where they show as a diff. Writes to `/tmp` and the scratchpad get no reminder. |
| `tool_token_saver.py` | Both | Rewrites eligible Bash commands through RTK using the response format required by the calling agent. |
| `plan_mode_tracker.py` | Claude Code | Tracks `/spec` plan-mode state, records who owns the plan-mode leg being entered (the only moment `/spec` and native plan mode are distinguishable), verifies the observed planning-leg model, and reports the result once per leg. |

The RTK hook registrations explicitly identify Claude or Codex. Codex rewrites include `permissionDecision: "allow"` alongside `updatedInput`; Claude rewrites omit that decision so normal permission checks remain in place. Older Codex registrations can be recognized from native hook metadata. If the runtime cannot be identified, the hook leaves the command unchanged.

## PermissionRequest *(Claude Code only)*

*When a tool call would show a permission dialog*

| Hook | Description |
|------|-------------|
| `auto_approve_plan.py` | Acts only on a `/spec` planning leg: allows `ExitPlanMode` there as the model-switch lever (and denies it while the registered spec plan still awaits approval). Claude Code's own plan mode is left alone — the plan-approval dialog is the user's, so the hook prints no decision and the plan is never approved on their behalf. It also restores `bypassPermissions` after a `/spec` plan exit — and only there: current Claude Code builds drop the session to `acceptEdits` or manual mode, so when the session was observed in bypass before the planning leg, the hook re-applies bypass on the first permission request that follows. In native plan mode the same choice is the user's own (`auto-accept edits` vs `manually approve edits`), so it is left untouched |

## PostToolUse

*After file edits, reads, and searches*

| Hook | Applies to | Description |
|------|------------|-------------|
| `plan_mode_tracker.py` | Claude Code | Tracks entry to and exit from Claude Code plan mode for `/spec`. |
| `native_plan_capture.py` | Claude Code | Files a plan approved in Claude Code's own plan mode into `docs/plans/` as `Status: SAVED`, `Type: Plan`, so it renders in the Console instead of vanishing into a scratch file. Skipped whenever a `/spec` or `/build` run already owns the plan. |
| `file_checker.py` | Claude Code | Runs the existing edit-time lint/format checks and TDD reminder. |
| `context_monitor.py` | Claude Code | Tracks context use and privately nudges the agent as compaction approaches. |
| Memory observer | Both | Saves decisions, discoveries, and bugfixes. |
| Repository asset sync | Both | Silently reconciles supported edits across the Claude Code and Codex project-asset trees. Temporarily incomplete multi-file updates are deferred and retried instead of blocking an edit that already landed. |

## PostToolUseFailure

After a failed `EnterPlanMode` call, Claude Code runs `plan_mode_tracker.py` to retire the unsuccessful native-planning handoff. The registered plan and draft remain available, and a later ordinary native plan can still be captured normally. This cleanup is silent and does not change permissions.

## PreCompact

| Hook | Applies to | Description |
|------|------------|-------------|
| `pre_compact.py` | Both | Snapshots active work before compaction so the next SessionStart can restore it. |

## Stop

*When the agent finishes*

| Hook | Applies to | Description |
|------|------------|-------------|
| `spec_stop_guard.py` | Both | Holds a registered `/spec` or `/build` open until its completion rules are met. Honors the user-initiated discussion pause (`/spec pause`, or the agent pausing when you question a decision mid-run) so discussion turns aren't blocked. |
| Repository asset sync | Both | Verifies parity silently and repairs safe drift automatically. Incomplete edits are already returned to the agent as private context; an unresolved maintenance error never blocks completion or creates a user-facing warning. |
| Session summarizer | Both | Saves the turn's durable observations. |

`spec_plan_validator.py` runs as a command-scoped Stop hook during the `/spec` planning phases, holding the turn open until the run's plan file exists. It is satisfied by **this session's own** registered plan, so a plan another session is working on in the same directory does not release your planning run. Without a registration it falls back to scanning for a plan dated today, skipping any file another session has registered — see [Registering a plan](plan-format#registering-a-plan).

## SessionEnd

| Hook | Applies to | Description |
|------|------------|-------------|
| `session_end.py --session-end` | Both | Completes the real session, waits for the team-memory export attempt, then stops the Console worker only when no other session remains. Codex now uses its native SessionEnd event rather than treating every Stop as a session boundary. |

:::info Compaction resilience
When a client emits the compaction lifecycle: **PreCompact** captures active state → compaction runs → **SessionStart** restores it via `post_compact_restore.py`. Native context management remains separate from cross-session memory; Pilot does not automatically inject a memory digest into either agent.
:::
