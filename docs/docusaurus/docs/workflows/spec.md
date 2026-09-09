---
sidebar_position: 4
title: /spec
description: Plan, implement, and verify complex features with full automation — Spec-Driven Development with TDD, plan approval gates, code review, and worktree isolation.
---

# /spec

Plan, implement, and verify complex features with full automation using Spec-Driven Development.

Best for new features, refactoring, and architectural changes where an **approved, durable task list** adds value before writing code. Claude Code's native Plan mode and `/spec` are peer tools with different contracts: `/spec` persists its plan, implements with TDD, and verifies every task before completion.

For bugfixes, use [`/fix`](/docs/workflows/fix). For vague ideas, use [`/prd`](/docs/workflows/prd) first to produce a PRD, then hand off here.

:::tip `/spec` and `/build` are peers
[`/build`](/docs/workflows/build) is the other structured workflow, and **size does not decide between them**. Reach for `/spec` when the work is measured against an ordered list of tasks you want agreed first; reach for `/build` when it is measured against a defined end state and the approach is better found while building. A 30-screen migration can be `/build`; a modest feature with an unclear execution order is `/spec`.
:::

```bash
# Claude Code
claude
> /spec "Add user authentication with OAuth and JWT tokens"
> /spec "Migrate the REST API to GraphQL"

# Codex CLI
codex
> $spec "Add user authentication with OAuth and JWT tokens"
> $spec "Migrate the REST API to GraphQL"
```

## Workflow

```
Discuss → Plan → Approve → Implement → Verify → Done
```

Manual steps are **Approve** (required) and **Code Review** (optional, via Console). Everything else runs automatically. The Verify → Implement feedback loop repeats until all checks pass, then prompts for squash merge.

## Spec Types

### Feature Spec

Full exploration workflow for new functionality, refactoring, or any work where architecture decisions matter.

- Codebase exploration with Semble hybrid search and CodeGraph structural analysis
- Architecture design decisions via Q&A
- Concise plan: Goal, Approach, per-task Definition of Done — boundary, risks, and verification sections appear only when there's something concrete to say
- Unified verification agent (optional, configurable in Console Settings)

### Bugfixes

For a bugfix workflow without a plan file, use [`/fix`](/docs/workflows/fix). When the user types `/spec` with a bug description, the full bugfix workflow runs — root-cause investigation, three-task structure (RED test → fix → quality gate), Behavior Contract audit, revert-test proof in verify, iteration cap at 3.

## Three Phases

### Plan Phase

- Explores codebase with semantic search, asks clarifying questions
- Writes detailed spec with scope, tasks, and definition of done
- For UI/user-facing features: writes structured **E2E test scenarios** (TS-001, TS-002…) with step-by-step actions and expected results — these become the verification contract for the Verify phase
- Spec-review agent validates completeness in Claude Code or Codex (optional, enabled by default)
- Waits for your approval — edit the plan directly, or **annotate it visually** in the Console's Specifications tab (select any text, write a note — annotations save automatically). The agent reads your annotations at the approval checkpoint, revises the plan, and re-asks for approval

:::note Approval gates wait for you
Claude Code leaves an unanswered question open until you answer it (the `askUserQuestionTimeout` setting defaults to `"never"`), so `/spec` and `/fix` approval gates wait — even when you work in another window for an hour. Earlier Claude Code versions auto-continued after 60 seconds of idle; Pilot used to counter that with a `CLAUDE_AFK_TIMEOUT_MS` pin in `~/.claude/settings.json`. That variable is now the opt-in that turns auto-continue *on*, so Pilot no longer writes it and removes the value it wrote on the next start. The workflow rules additionally treat an auto-continued question as "not answered" and re-ask. Prefer auto-continue? Set `askUserQuestionTimeout` yourself; Pilot leaves your value alone.
:::

### Implement Phase

- Isolated git worktree, new branch from default, or current branch (your choice)
- Strict TDD for each task: RED → GREEN → REFACTOR
- Runs the relevant lint, format, and type checks. Claude Code also runs its edit-time quality hooks.
- Full test suite runs at the **Quality Gate** task (end), not after every task — running it per-fix-task is the single biggest token sink in bundled bugfix plans, so the targeted test module is used between fixes and the authoritative full-suite run happens once
- **Interruptions pause, not fight** — question a decision or raise a discovery mid-run and the agent answers, pauses the plan (`⏸ Paused`, the statusline shows `[paused]`), and discusses freely; the stop guard injects nothing while paused, even if the interruption landed inside a prior Stop continuation. The pause persists until exact **resume**, `/spec resume`, or `$spec resume`; wording such as "continue" cannot resume it accidentally. `/spec pause` controls it explicitly. The pause is `/spec`-only — `/build` keeps its autonomous loop and finishes through its own hand-back doors.
- **Plans aren't frozen** — implementation legitimately learns things planning could not. Tactical differences (a detail diverges, the approach holds) are adapted and recorded under the plan's `## Deviations` section; material discoveries (an invalidated task or assumption, a scope or approach change) pause the run, get discussed with you, and the agreed amendments are applied to the plan — the discussion is the approval. Verification treats files recorded under `## Deviations` as in-scope for review.
- **Manual tasks are part of the plan** — when a step cannot be automated, the approved plan marks it `Owner: User` and gives the exact `User Action`. The agent prompts once and waits without a Stop loop. Reply with exact **done** when the action is complete; the agent verifies anything it can observe before checking off the task.

### Verify Phase

- Full test suite + type checking + lint + build verification
- Features: required changes review when enabled, plus any additional subagents Claude Code or Codex decides are useful; Pilot never adds a delegation-permission prompt
- Bugfixes: regression test + full suite, with agent-controlled delegation when useful
- For UI features: executes the plan's **E2E test scenarios** step-by-step via browser automation — tracks pass/fail per scenario, auto-fixes failures (up to 2 attempts), escalates persistent failures to known issues; results written back to the plan file. Claude Code prefers its Chrome extension; Codex uses the Chrome DevTools MCP. Both fall back to playwright-cli / agent-browser.
- Auto-fixes findings, loops back until all checks pass
- After automated checks pass, prompts you to **review code changes** in the Console's Changes tab — each file shows a **T{N}** badge linking it to the spec task that changed it, and you can click **Spec** to group files by task for focused review. Enable Review mode to add inline annotations on any diff line (they save automatically), and the agent addresses them before marking the spec as verified

## Configurable Toggles

All interaction points in `/spec` are configurable via **Console Settings → Spec Workflow** and **Console Settings → Reviewers**.

### Spec Workflow Toggles

| Toggle               | Default | Effect when disabled                                                      |
| -------------------- | ------- | ------------------------------------------------------------------------- |
| **Worktree Support** | On      | Worktree and new-branch options are hidden — implementation always runs on the current branch |
| **Ask Questions**    | On      | Planning runs fully autonomous — no clarifying questions                  |
| **Plan Approval**    | On      | Implementation starts immediately after planning — no approval gate       |

When all three are disabled, `/spec` runs end-to-end without any user interaction. Start a task, come back to verified code.

### Reviewer Toggles

| Toggle          | Default | What it does                                                                                  |
| --------------- | ------- | --------------------------------------------------------------------------------------------- |
| **Spec Review** | On      | Validates the plan before implementation — checks alignment and flags risky assumptions       |
| **Changes Review** | On   | Reviews code after implementation — bugs, security, and cleanups; plan compliance and goal achievement stay covered on both agents (inline workflow audit on Claude Code, the native agent's own pass on Codex) |

Both run outside the main session context on both agents: Claude Code uses a sub-agent, Codex a custom agent installed under `~/.codex/agents/`. Optional **Codex Companion Reviewers** (off by default) add a Claude Code plugin second opinion using OpenAI Codex — best reserved for high-risk or security-sensitive specs. The **Changes Review** and **Codex Companion Changes Review** toggles also govern [`/fix`](/docs/workflows/fix), which runs the same reviews at finalise.

Claude Code's built-in `/code-review` remains a user-invocable command, so Pilot does not invoke that specific skill automatically. This does not restrict the workflow's own agent tools: Claude Code and Codex may spawn or nest additional review agents autonomously whenever useful. See the [Review Agents](/docs/features/console#workflows---review-agents) note.

**The configured Codex companion review runs at most once per `/spec` invocation.** Plan iterations reuse that named pass's first result instead of paying for it again. This cost control does not cap other Codex or Claude Code subagents chosen by the active workflow. The bugfix planning phase does not run the companion reviewer; adversarial review is most valuable on real code, not on a plan.

## Branch Strategy (Optional)

When starting a `/spec` task, you're asked how you want to work:

| Option | What happens |
| ------ | ------------ |
| **Use worktree** | Creates an isolated git worktree on a dedicated branch, in `.worktrees/` by default ([configurable](/docs/features/console#workflows---worktrees), along with the git timeout that large monorepos outrun). `main` stays clean. Pilot auto-stashes uncommitted changes, restores them after. Squash-merged after verification — or discard with no cleanup. |
| **Current branch** | Works directly on whatever branch you're on. Simplest option when you're already on a clean feature branch. |
| **New branch from default** | Fetches origin, creates `feat/<slug>` (or `fix/<slug>` for bugfixes) from `origin/main`, and checks it out. Best when your current branch isn't clean but you don't want full worktree isolation. |

Disable the **Worktree Support** toggle in Console Settings to skip this question entirely — `/spec` will always use the current branch.

For bugfixes, use [`/fix`](/docs/workflows/fix) — the worktree question is asked here in `/spec` because that's where it applies.
