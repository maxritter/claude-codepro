---
sidebar_position: 7
title: Status Line
description: Real-time session dashboard rendered below every Claude Code response — token usage, cost, model, reasoning effort, branch, and active Pilot workflow progress at a glance.
---

# Status Line

:::warning Claude Code only
The status line is not available with Codex CLI. It uses a Claude Code-specific stdin API that Codex does not support.
:::

Compact session dashboard rendered below every Claude Code response. Idle sessions use two lines; an active Pilot Spec or Buildout adds its progress line between them.

**Idle session:**

```
Opus 5 [high] [1M] | █████░▓ 60% | 5h: 42% ⇡ 2h | 7d: 18% ⇣ 4d | +120 -38 | main ~5
Pilot 8.4.0 (Solo) · CC 2.1.80 (Max) · Console: localhost:41777
```

**Active Pilot workflow:**

```
Opus 5 [high] [1M] | █████░▓ 60% | 5h: 42% ⇡ 2h | 7d: 18% ⇣ 4d | +120 -38 | main ~5
Spec: my-feature feature [implement] ████░░░░ 3/6
Pilot 8.4.0 (Solo) · CC 2.1.80 (Max) · Console: localhost:41777
```

## Line 1 — Session Metrics

| Widget | What it shows |
|--------|---------------|
| **Model** | Active model with reasoning effort immediately after its name (`Opus 5 [high] [1M]`, `Fable 5.1 [xhigh]`) |
| **Context** | Runtime context usage bar + percentage. Green < 75%, Yellow 75–90%, Red 90%+ |
| **5h / 7d usage** | Rate-limit percentage with pacing arrow and reset countdown. Shown on Pro/Max subscriptions. ⇡ = over pace (red), ⇣ = under pace (green) |
| **Lines** | `+added -removed` for the session. |
| **Directory** | Working directory, shown only when the branch alone can't place you — see below. |
| **Git** | Branch with staged/unstaged file counts, resolved from the same directory shown beside it. |
| **Cost** | Session cost in USD. Shown on API/Enterprise only — suppressed on subscription plans. |

The effort label uses Claude Code's live [`effort.level`](https://code.claude.com/docs/en/statusline#available-data) value, including mid-session `/effort` changes. When Claude Code omits that field, no effort label is shown.

### When the directory appears

The directory would be noise for the common case — one checkout, sitting at its root — so it earns its columns only when the branch alone leaves you guessing:

| Where you are | Directory shown? |
|---|---|
| Inside a git worktree | **Yes** |
| In a subdirectory of a checkout | **Yes** |
| Outside a git repo entirely | **Yes** — no branch renders either |
| At the root of an ordinary checkout | No |

This is what makes a worktree readable at a glance. `claude -w` and similar tools name the directory independently of the branch you later switch to, so the two drift apart:

```
Opus 5 [high] [1M] | █████░▓ 60% | +120 -38 | ~/…/angry-purple-tiger | feat/pr-prep
```

Now you can see the branch you're preparing a PR for *and* the directory to `cd` into, without running `!pwd`.

The path is shortened from the left, keeping the trailing components (`~/…/angry-purple-tiger`), because the last part is what identifies the checkout. A Pilot-managed `/spec` worktree adds its own `wt` marker after the branch:

```
Opus 5 [high] [1M] | █████░▓ 60% | +120 -38 | ~/…/.worktrees/my-feature | spec/my-feature wt
```

## Active workflow line — when present

**Specification:** `Spec: my-feature feature [implement] ████░░░░ 3/6 iter:2`

Shows plan name, type (feature/bugfix), phase (plan/implement/verify), task progress bar, and iteration count.

**Buildout:** `Build: running-brand build ███░░░░░ 3/8 r:2`

A [`/build`](/docs/workflows/build) Buildout renders the same way, counting the same tasks, with rounds (`r:`) instead of iterations and the phases `goal` (goal, tasks, and criteria being drafted) -> `build` (working the task list) -> `judge` (acceptance criteria being ruled). The type tag is magenta. Its acceptance criteria are a separate list from its tasks and are not counted here.

During the **plan** phase (before tasks exist) the detail slot reads `models: auto` / `manual` / `off`, reflecting the Model Switching mode selected in your Console settings.

In `auto` mode it turns red and reads `models: auto ⚠ not-opus` (just `⚠` on a narrow line) when runtime evidence shows planning on something other than Opus. The warning identifies the observed mismatch, not its cause. Check `/model` and `/usage`, or select **Manual** to manage the model yourself. Pilot does not assume a universal 200K planning limit or force compaction to restore Opus.

## Final line — Version Info

`Pilot <version> (<tier>) · CC <version> (<subscription>) · Console: <host:port>`

This line carries the Console address — open it to reach sessions, memories, plans, Buildouts, changes, and settings.

## Configuration

Configured automatically during installation in `~/.claude/settings.json` — no manual setup required.

## Composing with your own status line

Pilot's status line isn't all-or-nothing. If you already had one — a shell-prompt prefix, a project label, anything — you can keep it and render Pilot's lines underneath. Point `statusLine.command` at a wrapper script instead of at Pilot directly.

**The one thing to get right:** Claude Code sends the session JSON on stdin, and stdin can only be read once. Capture it, then replay it into Pilot — otherwise Pilot receives nothing and its lines come out empty.

```bash title="~/.claude/pilot-statusline-wrapper.sh"
#!/usr/bin/env bash
input=$(cat)

# Your own line(s) first — anything you like.
printf '%s\n' "$(whoami)@$(hostname -s):$(basename "$PWD")"

# Then Pilot's two or three lines, fed the JSON you captured.
printf '%s' "$input" | ~/.pilot/bin/pilot statusline
```

Make it executable and point `~/.claude/settings.json` at it:

```json
"statusLine": {
  "type": "command",
  "command": "~/.claude/pilot-statusline-wrapper.sh",
  "padding": 0
}
```

### Reading the session JSON in your wrapper

The `input` variable holds everything Claude Code knows about the session, so your own lines can use it too. A small helper keeps this readable:

```bash
field() {
  printf '%s' "$input" | python3 -c "import json,sys; print(json.load(sys.stdin)$1)"
}

model=$(field '["model"]["display_name"]')
dir=$(field '["workspace"]["current_dir"]')
```

Fields Pilot itself reads, and therefore the ones you can rely on: `workspace.current_dir`, `model.display_name`, `model.id`, `effort.level` when reported, `session_id`, `version`, `cost.*` (`total_cost_usd`, `total_lines_added`, `total_lines_removed`), `context_window.*` (`used_percentage`, `context_window_size`, `total_input_tokens`), and `rate_limits.*` on Pro/Max plans.

### Does a wrapper survive `pilot update`?

Yes, in the normal case. Pilot merges `~/.claude/settings.json` three ways — baseline, your current file, and the incoming defaults — and a `statusLine.command` you changed away from the baseline is kept rather than overwritten.

The exception worth knowing: if `~/.claude/.pilot-settings-baseline.json` is missing (a first install, or the file was deleted), there is nothing to compare against and the incoming default wins — your wrapper would be replaced. Keep a copy of the script itself somewhere safe; re-pointing `statusLine.command` at it takes a second.
