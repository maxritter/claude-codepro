---
sidebar_position: 6
title: UI Design and Claude Design
description: Automatic product-design expertise, Claude Design synchronization, and deterministic Impeccable checks for Claude Code and Codex.
---

# UI Design and Claude Design

Pilot installs two complementary external design packages:

| Package | Owns |
|---|---|
| [Open Claude Design](https://github.com/maxritter/open-claude-design) | Claude Design access and synchronization, product context, visual direction, design-system extraction, and structured UI review |
| [Impeccable](https://github.com/pbakaus/impeccable) | Named refinement workflows, supporting agents, opt-in edit/stop hooks, and deterministic design checks |

There are no design commands to memorize. Describe the work normally; the relevant skill and rule load automatically.

```text
Pull the approved Claude Design changes into this app and verify the result.

Redesign this settings flow without losing the existing visual system.

Audit the finished interface before release.
```

## Context behavior

Open Claude Design installs five focused, implicit skills for stable design quality, Claude Design access, UI creation, design-system extraction, and review. Their descriptions are visible to the agent; full instructions and references load only when the request matches.

For remote authoring, it loads the affected project context, Anthropic's latest live Claude Design prompt, and exactly one relevant live authoring skill. That context is reused through the task instead of copying a mutable upstream prompt into every session or fetching both authoring skills for coverage.

Both agents receive the same portable design skills. Stable visual constraints load for user-visible work; logic-only changes do not become redesign tasks.

When Impeccable's hook already reported on the changed files, the UI review reuses those findings. The detector runs manually only as a fallback or targeted recheck, so the two packages do not duplicate work.

Pilot installs Impeccable's CLI, skills, supporting agents, and detector without activating provider hooks. Hooks are an explicit per-project choice through `/impeccable hooks on` (or `$impeccable hooks on` in Codex); the corresponding `hooks off` command disables them again. Upgrades preserve existing project hook configuration because Pilot cannot distinguish an older automatic registration from a later user opt-in safely.

When hooks are enabled, Pilot keeps their disposable state outside repositories at `~/.pilot/cache/impeccable` unless you already configured `IMPECCABLE_CACHE_ROOT`. After an upgrade, a valid older `.impeccable/hook.cache.json` is preserved and pretty-formatted once so repository-wide formatter checks no longer fail on that stale cache.

## Claude Design transport

Open Claude Design generalizes Pilot's proven compatibility bridge across macOS, Linux, and WSL2. It is a CLI that speaks MCP to Anthropic internally—not a separate MCP server added to each coding agent.

The CLI discovers Claude Design's complete live tool catalog progressively:

```bash
open-claude-design status --json
open-claude-design tools --json
open-claude-design describe <tool-name> --json
open-claude-design authoring-context <project-id> --design-system <design-system-id> --skill hifi-design --json
open-claude-design call <tool-name> --args '<json-object>' --json
open-claude-design preview <project-id> <remote-path> --json
```

Disk-backed helpers keep large files and concurrency data out of agent context:

```bash
open-claude-design files <project-id> --depth -1 --tsv
open-claude-design pull <project-id> <remote-path> --output <local-path> --json
open-claude-design push <project-id> \
  --file '<remote-path>=<local-path>' \
  --if-match '<remote-path>=<etag>' \
  --allow-write --json
open-claude-design delete <project-id> \
  --path '<remote-path>' \
  --if-match '<remote-path>=<etag>' \
  --confirm-delete '<remote-path>' \
  --allow-write --json
```

Capability-bearing operations are not raw passthrough calls: `push`, `delete`, `preview`, and `planned-call` keep signed plan tokens and short-lived preview URLs out of argv and output.

Synchronization compares current remote etags and local hashes with the last verified project mapping. Remote-only and local-only changes follow separate reviewed paths; when both sides changed, the agent stops for semantic reconciliation instead of choosing a winner. Remote deletes additionally require exact user authorization, a matching path confirmation, current etag, and an automatic local recovery backup. The baseline advances only after local verification plus remote preview and readback.

When creating a new Claude Design element from code, the workflow reads the real component variants, tokens, assets, copy, neighboring composition, and interaction states before authoring. One cached `authoring-context` operation retrieves the live project prompt plus the selected authoring skill without dumping either through the terminal. The live prompt owns Claude Design's current host format; the repository remains authoritative for actual product behavior.

`pilot design` remains a compatibility alias that forwards to this installed CLI. Pilot no longer owns a second implementation.

Pilot follows the latest stable Open Claude Design GitHub release automatically. The installer downloads that release's `SHA256SUMS`, verifies the selected universal wheel, and preflights Pilot's required sync command before replacing an installed version. New Open Claude Design releases therefore need no Pilot manifest update.

## Authentication

Pilot installation and background updates never open an authentication browser. On the first real Claude Design request, the installed skill checks the connection. If needed on a desktop host, it explains the one-time step and opens `open-claude-design login` automatically; `pilot design login` remains the explicit equivalent. This flow is independent of Claude Code and Anthropic API keys:

- macOS: dedicated encrypted Keychain item.
- Linux and WSL2: current-user-owned `0600` file at `~/.config/open-claude-design/credentials.json`.

For CI, SSH, or a headless dev container, run `pilot design login --manual` in an interactive terminal. Open the printed URL on the host machine, then paste the returned code into that terminal—not into Claude Code, Codex, or agent chat. Persist the Open Claude Design configuration directory if the credential should survive container rebuilds.

Claude Design currently requires a Pro, Max, Team, or Enterprise account. Enterprise administrators must enable the capability. Existing Claude Code Design credentials remain a read-only compatibility fallback.

## Design principles

- The existing product and design system control visual decisions unless the user requests a change.
- Real components, tokens, content, assets, and interaction states replace approximate mockups and invented filler.
- Accessibility facts remain distinct from platform recommendations and subjective taste.
- Review requests remain report-only unless the user authorizes fixes.
- Runtime proof requires interacting with the rendered interface.
