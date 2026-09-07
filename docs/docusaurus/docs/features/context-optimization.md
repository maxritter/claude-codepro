---
sidebar_position: 3
title: Context Optimization
description: Keep the context window lean and recover cleanly when it fills up — strategies and memory persistence for Claude Code and Codex.
---

# Context Optimization

Two things matter for a long-running session: keeping the context window lean so tokens go to your code, and handling the moments when it fills up anyway.

These strategies apply to both **Claude Code** and **Codex CLI**.

## Native Codex context management

On Codex 0.153.0+, Pilot enables native context management unless you explicitly opt out:

```toml
[features]
context_management.experimental_mode = true
```

Eligible ChatGPT-backed sessions retain notes across windows and can search earlier thread history. Unsupported sessions use ordinary Codex context behavior; older runtimes skip this setting. Pilot memory remains available on demand across sessions, without an automatic digest.

Pilot requests expanded context with `model_context_window = 1050000` and `model_auto_compact_token_limit = 922000`; Codex enforces each model's native limits. Live checks on Codex 0.153.4 showed **828,400 usable tokens** for both Sol and Astra, versus 258,400 without overrides. A full million usable tokens is not guaranteed.

Codex manages model discovery, so new models do not require a Pilot release. Upgrades remove Pilot's old catalog pointer while preserving custom catalogs and profile settings. Restart Codex after upgrading.

## Keeping context lean

| Strategy | Savings | How |
|----------|---------|-----|
| **RTK proxy** | Varies by command | Rewrites dev tool output (`git status`, `npm test`, etc.) to remove noise before it enters the context window |
| **Semble code search** | Varies by query | Returns relevant matched chunks for intent searches rather than requiring whole-file reads |
| **Conditional rule loading** | Variable | Coding standards load only for matching file types — Python rules don't load when editing TypeScript |
| **Skill activation** | Variable | Descriptions expose available skills; the full SKILL.md loads when needed. Pilot's sequential workflows bundle their required phase instructions |
| **Scoped MCP tools** | Variable | MCP tool schemas are lazy-loaded via `ToolSearch` — only fetched when needed, not preloaded |
| **Routing hooks** | Variable | PreToolUse hooks privately nudge recursive search and ordinary built-in web calls toward dedicated indexed/MCP tools without blocking them, while authenticated Claude artifact URLs stay on the session-aware built-in tool |
| **Bounded native reads and searches** | Variable | Read relevant file ranges and request filenames, counts, or limited matches when full output is unnecessary |

## Status line display *(Claude Code only)*

The status line shows context usage as a visual progress bar:

```
Opus 5 [high] [1M] | █████░▓ 60% | ...
```

The bar uses Claude Code's reported context percentage, with correction only when live token evidence shows that the reported window size is stale. It does not rescale usage to an assumed compaction point; `▓` is the bar's end marker. Colors are green below 75%, yellow from 75% to below 90%, and red at 90% or more. The effort label, when supplied by the runtime, appears before the context-size label.

Pilot's retained compaction-budget helper uses a **33,000-token** reserve: 83.5% of a 200K window or 96.7% of a 1M window remains before that reserve. This is a budget estimate, not a universal compaction trigger or the scale used by the current status line. Claude Code controls actual compaction. The monitor issues one advisory when reported usage reaches 90%; there is no separate 80% warning, and work can continue normally.

## When compaction fires *(Claude Code only)*

Pilot captures and restores selected workflow state around Claude Code's compaction lifecycle:

```
PreCompact → Compact → SessionStart(compact)
```

1. **PreCompact** — `pre_compact.py` captures the registered plan path, status, current task, available task-list metadata, and supplied compaction instructions. It saves through the Console or falls back to a session file.
2. **Compact** — Claude Code compresses the conversation using its native context management.
3. **SessionStart(compact)** — `post_compact_restore.py` re-injects the registered plan reference and available task metadata so the agent can recover its working state.

Saved memory observations persist independently in SQLite. These mechanisms do not guarantee that every conversational detail survives. Preserve important decisions, constraints, approvals, and active process/agent identifiers in the relevant task or plan state; after compaction, read that state and recheck current files and live job handles before continuing.

## On-demand memory *(both agents)*

At startup, resume, and compaction, Pilot synchronizes memory storage silently. Neither Claude Code nor Codex receives an automatic memory digest or a terminal dump. Background observation and summarization continue independently.

Agents use `mem-search` when the task needs prior decisions: `search` with `scope="all"` returns compact history and [OKF knowledge](./knowledge.md) results, followed by selected `get_observations` or `get_knowledge` calls. Local full-text search works without the vector service and does not hide older records behind an automatic age cutoff. Knowledge sources, stale dates, and lifecycle state help the agent decide what to revalidate.

Legacy digest settings are retained for explicit Console context previews. They no longer control automatic injection. Memory is historical evidence, not proof of current code or another session's authority.

:::tip Don't rush the current task
Context limits do not justify shrinking the requested outcome. Preserve the information needed to resume, let the runtime manage compaction, and continue from current evidence. Report a genuine missing-state blocker rather than guessing or restarting completed work.
:::

## Running parallel sessions

Multiple Pilot Shell sessions can work on the same project with separate context and session-scoped workflow state. That separation does not prevent conflicts in shared files, the staging area, browser tabs, or external resources. Coordinate ownership or use authorized worktrees, and preserve changes made by other sessions. The Console dashboard helps identify active sessions.
