## Step 1: Setup — Read Plan, Detect Worktree, Set Up Task List

<!-- CC-ONLY -->
### 1.0 Native mode and approval

Read the registered plan and current runtime mode. If native plan mode is still active, complete its approval/exit boundary before implementation; follow `$HOME/.pilot/agents/spec-native-plan.md` when this run prepared that handoff. A missing tool or failed exit is not proof the mode changed and does not authorize writes. An explicit runtime response that plan mode is already closed is sufficient to clear a stale warning.

Once the approved registered plan is ready and writes are permitted, continue on the active model. Do not re-enter plan mode, emit another model-switch prompt, or repeat approval solely because this phase resumed after compaction.
<!-- /CC-ONLY -->

### 1.1 Read Plan & Gather Context

1. **Read the COMPLETE plan** — understand architecture and design
2. **Summarize understanding** — demonstrate comprehension
3. **Check current state:** `git status --short`, `git diff --name-only`, plan progress (`[x]` vs `[ ]`)

<!-- CC-ONLY -->
**Research tools during implementation:** CodeGraph (`codegraph_explore(query=...)` — one call orients on the task, returns deep source, and gives callers + blast radius before you modify a shared or non-trivial function), Context7 (library docs), Semble `semble search` or `mcp__semble__search` (find patterns by intent), `semble find-related` (discover parallel implementations), grep-mcp (production examples).

**Before modifying a shared or non-trivial function:** run `codegraph_explore(query="<fn> callers and impact")` — its response includes the call path and blast radius, catching callers you'd otherwise miss. A self-contained local function the plan already isolated doesn't need it.
<!-- /CC-ONLY -->
<!-- CODEX-START
**Research tools during implementation:** Use CodeGraph for structural runtime-code questions (`codegraph_explore(query=...)` — one call orients, returns known-symbol source, and gives callers + blast radius before a non-local change), Context7 for library docs, Semble for intent/pattern discovery, and grep-mcp for production examples.

**Codex proportionality:** Skip CodeGraph for docs, rules, markdown, config, UI copy, test-only edits, or named-path local changes unless the call graph itself is the uncertainty. Before modifying a runtime function with non-local effects, run `codegraph_explore(query="<fn> callers")`; for a local function already isolated by the plan and targeted reads, do not add graph calls just to satisfy a checklist.
CODEX-END -->

### 1.2 Detect or Resume Worktree (Conditional)

**Read `Worktree:` header from plan.** If `No` or missing: skip to 1.3.

**If `Worktree: Yes`:**

1. Extract plan slug: `docs/plans/2026-02-09-add-auth.md` → `add-auth`
> **`$LANE_FLAG`** is `--lane <id>` when this run was dispatched as an orchestration lane, and **nothing at all** otherwise — the value the invocation parsed from its arguments. It keeps worktree and plan identity scoped to this lane; an unflagged call resolves a different identity and silently finds nothing (issue #174).

2. Detect: `~/.pilot/bin/pilot worktree detect --json <plan_slug> $LANE_FLAG`
3. **If found:** `cd` to the worktree `path`
4. **If not found:** Create as fallback:
   ```bash
   ~/.pilot/bin/pilot worktree create --json <plan_slug> $LANE_FLAG
   ```
   Copy plan file into worktree if needed. `cd` to worktree path.

   ⛔ `$LANE_FLAG` here too, not just on the `detect` above. Worktree identity is keyed on `(slug, lane)`, so an unflagged create makes a worktree that the lane-flagged `sync`/`cleanup` in the verify phase can never find — the run's work ends up stranded in an orphaned checkout that never reaches the base branch.
5. If creation fails, diagnose a recoverable setup issue or report the isolation blocker. Do not silently continue in a shared checkout when the plan requests a worktree. A lane must abort if isolation cannot be established (`spec-branch-setup.md`).
6. Verify: `git branch --show-current` should show `spec/<plan_slug>`

All subsequent work happens inside the worktree directory.

### 1.3 Set Up Task List (MANDATORY)

<!-- CC-ONLY -->
1. **Check existing:** `TaskList` — if tasks exist from prior session, resume (don't recreate)
2. **If empty:** Create one task per uncompleted `[ ]` plan task:
   ```
   TaskCreate(subject="Task N: <title>", description="<objective>", activeForm="Implementing <desc>")
   ```
   Set dependencies: `TaskUpdate(taskId="...", addBlockedBy=["..."])`
3. Skip `[x]` (already completed) tasks
<!-- /CC-ONLY -->
<!-- CODEX-START
1. List uncompleted `[ ]` plan tasks — these are your work items.
2. Track progress by updating plan checkboxes (`[ ]` → `[x]`) after each task.
3. Skip `[x]` (already completed) tasks.
CODEX-END -->
