## Step 1: Parse & Route

First parse optional `--lane <id>` into `LANE_ID` and `$LANE_FLAG`, and remove it from the remaining arguments. Route using those remaining arguments, so `<plan.md> --lane <id>` still resolves as an existing plan. Preserve the lane on pause/resume and every phase dispatch.

```
IF arguments are exactly "pause" or "resume":
    → Discussion pause control (Section 1.0)
ELIF arguments end with ".md" AND file exists:
    → Read plan, dispatch by status (Section 2)
ELSE:
    → Detect type, ask worktree, route to the planning phase (Section 1.3)
```

### 1.0 Discussion pause control (`/spec pause`, `/spec resume`)

The stop guard honors a session-scoped `spec-discussion-paused` marker on user-initiated turns, so the user can hold a running /spec open for free-form discussion — questioning a decision, digesting a mid-implementation discovery — without "IMMEDIATELY continue" blocks on every reply.

For lane runs, read `agent-gate-protocol.md`: the lane marker records its own pending state, while the session-only stop reader remains the coordinator's responsibility. Relay the decision to the coordinator and yield through the native agent lifecycle; never touch the coordinator's marker.

```bash
SESS_DIR="$HOME/.pilot/sessions/${CLAUDE_CODE_SESSION_ID:-${CODEX_THREAD_ID:-${PILOT_SESSION_ID:-default}}}"
[ -z "$LANE_ID" ] || SESS_DIR="$SESS_DIR/lanes/$LANE_ID"
```

- **`pause`:** If `$SESS_DIR/active_plan.json` is missing, report that no /spec run is active in this session and stop. Read the registered plan's `Type:` header — if `Build`, report that the discussion pause is /spec-only (the stop guard refuses it for a Buildout; /build finishes through its own hand-back doors, and the double-stop escape still force-exits) and stop. Otherwise recreate the marker fresh so a stale binding from an earlier plan cannot linger — `mkdir -p "$SESS_DIR" && rm -f "$SESS_DIR/spec-discussion-paused" && touch "$SESS_DIR/spec-discussion-paused"` — confirm "⏸ Paused — the plan holds while we discuss. Say resume (or `/spec resume`) to continue.", and end the turn. While paused, answer the user normally and re-touch the marker each discussion turn.
- **`resume`:** `rm -f "$SESS_DIR/spec-discussion-paused"`, then read the plan from `active_plan.json` and dispatch by status (Section 2). ⛔ Do NOT edit the plan here — the dispatcher's tool boundary stands; amendments agreed during the discussion are applied by the dispatched phase skill (spec-implement's discovery protocol) before it continues the task list. No active plan → report that and stop.

### 1.1 Detect Type (new plans only)

- **Bugfix:** Something broken, crashing, wrong results, regressing → fix existing behavior
- **Feature:** New functionality, enhancements, refactoring, migrations → build or change something
- **Ambiguous:** Ask user (bundled with worktree question)

### 1.2 Read Environment & User Questions (new plans only)

**⛔ MANDATORY FIRST STEP — read env vars before ANY user interaction:**

```bash
echo "BRANCH_ISO=${PILOT_BRANCH_ISOLATION_ENABLED:-false} QUESTIONS=${PILOT_PLAN_QUESTIONS_ENABLED:-true} APPROVAL=${PILOT_PLAN_APPROVAL_ENABLED:-true}"
```

**⛔ When `BRANCH_ISO` is `"false"`: NEVER ask about branch choice. The dispatcher invokes the planning skill immediately with `--worktree=no` (defaults to the current branch).**

**Note:** The `QUESTIONS` toggle (`PILOT_PLAN_QUESTIONS_ENABLED`) does NOT affect the branch/type questions in this dispatcher. That toggle only controls Q&A questions during planning (Steps 4/6 in spec-plan). The dispatcher-level branch question is gated entirely by `PILOT_BRANCH_ISOLATION_ENABLED`.

**Reviewers are controlled entirely by Console Settings.** The planning and verification phases read their native reviewer toggles directly — no per-session question is needed.

| BRANCH_ISO | Type | Action |
|------------|------|--------|
| `false` | Clear | NO question; invoke skill with `--worktree=no` |
| `false` | Ambiguous | Ask ONLY the type question; invoke skill with `--worktree=no` |
| `true`  | Clear | Ask 3-option branch question; pass selected flag |
| `true`  | Ambiguous | Ask type + 3-option branch question (bundled); pass selected flag |

**Branch question options (only when `BRANCH_ISO` is `"true"` — use these as predefined AskUserQuestion options, listed in recommended order):**

| Option | Flag passed | Behavior |
|--------|-------------|----------|
| **Continue on current branch** (recommended) | `--worktree=no` | Works on current branch as-is |
| New branch from default branch | `--new-branch` | Creates a clean branch from origin/main (or master), checks it out, then works there |
| Use worktree (isolated branch, squash-merged after) | `--worktree=yes` | Creates isolated worktree |

**⛔ When the user selects "New branch" or sends a custom response mentioning "new branch", "clean branch", or "branch from master/main": pass `--new-branch`, NOT `--worktree=yes`.** `AskUserQuestion` allows users to type a free-text "Other" response, and previously such responses requesting a new branch were misinterpreted as worktree requests. This rule applies only when `BRANCH_ISO=true` — when off, the question is not asked.

### 1.2a Orchestration lanes (`--lane <id>`)

A coordinating session dispatching `/spec` runs as subagents passes `--lane <id>` on each. Parse it, strip it from the task description, and forward it verbatim to the planning skill alongside the branch flag.

A lane registers its plan under `sessions/<id>/lanes/<lane>/` instead of the session's single slot, because a Claude Code subagent resolves the *same* session id as its parent. Without the flag every lane's plan lands in the coordinator's `active_plan.json`: siblings overwrite each other, and the coordinator's stop guard blocks its every turn over a plan a live agent owns in another checkout (issue #174).

⛔ **`--lane` implies `--worktree=yes` and fails closed.** When a lane id is supplied, ask no branch question, reject `--lane` combined with `--worktree=no` or `--new-branch`, and abort rather than continue if isolation cannot be established.

⛔ **Never pass `--lane` the user did not supply.** An ordinary run stays byte-identical to today.

### 1.3 Route to Planning

<!-- CC-ONLY -->
Invoke the selected planning skill and stop in this dispatcher:

- **Bugfix:** `Skill(skill='spec-bugfix-plan', args='<task_description> --worktree=yes|no|--new-branch [--lane <id>]')`
- **Feature:** `Skill(skill='spec-plan', args='<task_description> --worktree=yes|no|--new-branch [--lane <id>]')`
<!-- /CC-ONLY -->
<!-- CODEX-START
Codex has no callable phase-dispatch tool. Continue immediately with the selected planning phase instructions instead of stopping in the dispatcher:

- **Bugfix:** continue immediately with the `$spec-bugfix-plan` skill instructions using arguments: `<task_description> --worktree=yes|no|--new-branch [--lane <id>]`
- **Feature:** continue immediately with the `$spec-plan` skill instructions using arguments: `<task_description> --worktree=yes|no|--new-branch [--lane <id>]`
CODEX-END -->

**Note:** Users who want a bugfix workflow without a plan file invoke `/fix` directly — that's a separate user-facing command. The `/spec` dispatcher does not route to `/fix`. When a user types `/spec`, they want the full spec workflow.
