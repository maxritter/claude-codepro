---
sidebar_label: Claude Code vs Codex
description: Pilot Shell support for Codex CLI and the ChatGPT desktop app, including shared workflows and platform differences from Claude Code.
---

# Claude Code vs Codex

Pilot Shell supports both agents. Claude Code has broader platform integration; Codex works for daily development with fewer platform-specific features. Pilot works with Codex CLI and with the Codex runtime bundled in the ChatGPT desktop app on macOS.

Direct requests, each agent's native Plan/Goal tools, and Pilot workflows are peer ways to work. Choose the contract you want; Pilot keeps its available context, quality, memory, and tools around all of them.

## Works on Both

All Pilot workflows run on both agents. Use `/` on Claude Code and `$` on Codex:

- **Structured workflows:** `/prd`, `/spec`, `/build`, `/fix`
- **Focused workflows:** `/investigate`, `/cleanup`, `/benchmark`, `/setup-rules`, `/create-skill`; Open Claude Design and Impeccable load automatically for matching visual work
- Console — all 11 views, persistent memory, sessions, and memories shared between agents
- Lifecycle hooks, active-work recovery, SessionEnd finalization, and workflow stop guards
- Workflow quality gates on both agents; Claude Code additionally keeps its edit-time lint, format, type, and TDD hooks
- MCP servers (CodeGraph, Semble, mem-search, web-search, and more)
- Rules, standards, context optimization, and team memories
- Spec-review and changes-review agents

## Codex context and Pilot memory

The installer enables Codex's experimental native context manager by default on Codex 0.153.0 and newer while preserving an explicit opt-out in `config.toml`. On older releases it keeps `[features]` boolean-only and removes Pilot's incompatible structured setting during upgrades. Eligible ChatGPT-backed sessions then keep notes across context windows and can search earlier thread history instead of repeatedly reducing it to one compaction summary.

Pilot retains a broader history across agents and editable [OKF knowledge](../features/knowledge.md) for on-demand recall. Both agents use available native context first and query `mem-search` when useful details are missing; neither receives a Pilot startup digest. Useful overlap between native memory and Pilot is allowed without mechanically copying records between stores.

Background capture automatically uses available Claude Code or Codex resources, including Codex-only setups. It handles provider selection, quota failures, retries, and memory maintenance automatically. Saved memory remains usable when no background provider can run. The only memory choice is whether to enable Team sharing for a project; local and shared knowledge are then handled automatically.

Pilot installs the same five Open Claude Design skills for both agents. For the real Claude Design service, `open-claude-design` supplies the cross-platform CLI bridge; `pilot design` remains a forwarding alias. Claude Code is not required for authentication: the first desktop use connects in a browser, while headless containers use `pilot design login --manual` in an interactive terminal. See [UI Design and Claude Design](../workflows/ui-design.md).

## Claude Code Only

- **Status line** — real-time session metrics below every response
- **Remote control** — connect from the Claude app / browser, plus channels (Telegram, Discord, iMessage)
- **Language Server integration** — LSP-driven diagnostics, hover docs, and go-to-definition (Codex uses repository lint/type commands during verification rather than an edit-time file-checker hook)
- **Model switching** — `/model` command to change models mid-session (Codex sets model via `codex --model` or `config.toml`)
- **`/effort ultracode`** — Claude Code's additional whole-project orchestration mode
- **Permission modes** — `Shift+Tab` cycle and Auto Mode classifier (Codex uses `approval_policy` in `config.toml`)
- **Codex companion reviews** — OpenAI adversarial review launched from within Claude Code
- **Team-sharing of extensions** — push/pull of `~/.claude/` extensions through a git remote
- **Commands** — slash-command extensions in `.claude/commands/` (Codex has no command primitive)

Claude's native LSP can strengthen exact reference checks during `/cleanup`; Codex combines repository analyzers with CodeGraph, Semble, and exact search. Neither path treats a missing LSP or graph edge as proof that code is unreachable.
