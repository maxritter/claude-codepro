## Step 4: Worktree Sync (if worktree active)

A synchronous permitted question needs no disk sentinel. For an asynchronous persisted gate, resolve and validate the actual session identity before creating or consuming its marker; missing identity blocks only that persistence path. Keep the real decision pending or use the permitted synchronous question surface, and never substitute a shared session directory. Recompute the validated session/lane path before cleanup after a new shell call or compaction.

> **`$LANE_FLAG`** is `--lane <id>` when this run was dispatched as an orchestration lane, and **nothing at all** otherwise — the value the invocation parsed from its arguments. It keeps worktree and plan identity scoped to this lane; an unflagged call resolves a different identity and silently finds nothing (issue #174).

1. Detect: `~/.pilot/bin/pilot worktree detect --json <plan_slug> $LANE_FLAG`
2. If no worktree: skip to Step 5 (the annotation check — it runs BEFORE the review gate regardless of worktree mode; never collapse Step 5 → Step 6).
3. Save plan to project root (only if gitignored):
   `git -C <project_root> check-ignore -q docs/plans/<plan_filename>` — if exit 0: `cp <worktree_plan> <project_root>/docs/plans/`; if exit 1 (tracked): skip — squash merge brings the updated plan.
4. Show diff: `~/.pilot/bin/pilot worktree diff --json <plan_slug> $LANE_FLAG`
5. Notify + AskUserQuestion: "Yes, squash merge" | "No, keep" | "Discard"

   ⛔ **When no structured input tool is exposed and permitted for this approval**, do not ask yet. Read `$HOME/.pilot/agents/agent-gate-protocol.md` and follow it, supplying `GATE_NAME` = `Worktree sync`, `OPTIONS` = the three above, `SENTINEL_PATH` = `verify-gate-pending`; arm the sentinel before emitting the prose question:

   ```bash
   SESSION_ID="${CLAUDE_CODE_SESSION_ID:-${CODEX_THREAD_ID:-${PILOT_SESSION_ID:-}}}"
case "$SESSION_ID" in ""|*[!A-Za-z0-9_-]*) echo "Persisted gate needs a confirmed session identity" >&2; exit 1 ;; esac
SESS_DIR="$HOME/.pilot/sessions/$SESSION_ID"
[ -z "$LANE_ID" ] || SESS_DIR="$SESS_DIR/lanes/$LANE_ID"
   mkdir -p "$SESS_DIR" && touch "$SESS_DIR/verify-gate-pending"
   ```

   Only after the command succeeds, ask the prose question and **end your turn**. The guard holds the sentinel for an approved plan at `Status: COMPLETE`, and UserPromptSubmit consumes it when the user's NEXT message arrives. ⛔ Do NOT run the sync in the same turn: it squash-merges onto the base branch and cannot be undone by asking again. Treat that message as the choice; `rm -f "$SESS_DIR/verify-gate-pending"` is a safe no-op on resume, and re-touch the sentinel before every later prose question.
6. Handle:
   - **Squash:** `worktree sync && cleanup --force + cd` — ALL in ONE Bash call chained with `&&`. Cleanup MUST NOT run if sync fails.
   - **Keep:** Report path
   - **Discard:** `~/.pilot/bin/pilot worktree cleanup --discard --json <plan_slug> $LANE_FLAG` + `cd` in SAME bash call (no sync needed — `--discard` explicitly allows deleting unmerged work). ⛔ `$LANE_FLAG` here too: an unflagged discard resolves a different worktree identity and silently no-ops.

   ⛔ NEVER split sync, cleanup, or cd into separate Bash calls — compaction between them can cause work loss.

   **`worktree sync` exit codes.** `0` clean · `1` nothing landed · **`2` the squash landed but the base checkout's own uncommitted work could not be restored** and is sitting in `git stash list`. The `&&` chain stops on 2 by itself, deliberately leaving the worktree in place. Do NOT re-run cleanup to "finish the job": surface the `stash_warning` from the JSON and the `git stash pop` recovery to the user first. `success: true` in the JSON is still correct — the merge did land; only the unrelated local work is stranded.

   **Lane contention.** Sync serializes on a repo-wide lock, so a concurrent lane's sync waits rather than interleaving. A failure naming lane contention means another lane held the lock past the timeout and **nothing was changed** — retry once it finishes.
7. **Post-merge verification — MANDATORY after a successful squash merge** (parity with `spec-verify` §8.2): the base branch may have diverged, so re-run the full test suite and type check on the merged base-branch tree. Any failure means the merge broke something — fix on the base branch before reporting the bugfix verified.
