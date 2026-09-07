## Step 2: Create Plan File Header (FIRST)

1. **Parse flags** from arguments: `--worktree=yes|no` or `--new-branch` (default: `No`). Strip the flag from task description.

2. **Branch / worktree setup — only when the flag is `--new-branch` or `--worktree=yes`.** Read `$HOME/.pilot/agents/spec-branch-setup.md` and follow it, using branch prefix `feat/` and `<plan_slug>` derived from the task description (the same slug as the plan filename), plus `<lane>` when the dispatcher forwarded one. On the default `--worktree=no` there is nothing to do — work continues on the current branch.

   **`$LANE_FLAG`** stands for `--lane <id>` on a lane run and for **nothing at all** otherwise. Every `pilot register-plan` call in this workflow — here, in `spec-implement`, and in the verify phases — carries it. Substitute it literally each time; shell state does not survive between Bash calls.

   ⛔ **Old-binary check, before the first lane-flagged call** (lane runs only):

   ```bash
   ~/.pilot/bin/pilot register-plan --help 2>&1 | grep -q -- --lane && echo LANE_OK || echo LANE_UNSUPPORTED
   ```

   `LANE_UNSUPPORTED` → **abort and tell the user to update Pilot.** Do NOT fall back to an unflagged `register-plan`: that writes this lane's plan into the coordinator's `active_plan.json`, where a sibling overwrites it and the coordinator's stop guard blocks on a plan it does not own — reinstating both defects behind something that reads like a warning.

3. **Generate filename:** `docs/plans/YYYY-MM-DD-<feature-slug>.md`. If a worktree is active, use its returned path as the base directory. Reuse the named registered draft when resuming it; for a new plan choose a free filename (`-2`, `-3`, etc. on collision) instead of overwriting an existing file.

4. **Fetch author email** (best-effort, do not fail if unavailable):

   ```bash
   ~/.pilot/bin/pilot status --json 2>/dev/null | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('email',''))" 2>/dev/null
   ```

   If the command returns a non-empty email, include `Author: <email>` in the header. If empty or fails, omit the Author line entirely.

<!-- CC-ONLY -->
4b. **Detect agent:** If `$CLAUDE_CODE_ENTRYPOINT` is set, agent is `Claude Code`. Otherwise, agent is `Codex`.
<!-- /CC-ONLY -->
<!-- CODEX-START
4b. **Set agent:** Use `Codex`.
CODEX-END -->

5. **Write initial header:**

   ```markdown
   # [Feature Name] Implementation Plan

   Created: [Date]
   Author: [email if available]
   <!-- CC-ONLY -->
   Agent: [Claude Code|Codex]
   <!-- /CC-ONLY -->
   <!-- CODEX-START
   Agent: Codex
   CODEX-END -->
   Status: PENDING
   Approved: No
   Iterations: 0
   Worktree: [Yes|No]
   Type: Feature

   > Planning in progress...

   ## Summary

   **Goal:** [Task description from user]

   ---

   _Exploring codebase and gathering requirements..._
   ```

   **`Status:` is a closed set** — only `PENDING` | `COMPLETE` | `VERIFIED`, written as the bare keyword with no trailing prose or parentheticals, as enforced by `pilot spec validate`. At creation it is always `PENDING`; never invent a custom status (no `RESOLVED`/`DONE`/`CLOSED`).

6. **Register plan:** `~/.pilot/bin/pilot register-plan "<plan_path>" "PENDING" $LANE_FLAG`. Check that registration succeeded before continuing; a missing registration cannot track the workflow or authorize its native-planning handoff.

<!-- CC-ONLY -->
7. In Automated mode, follow `$HOME/.pilot/agents/spec-native-plan.md` now, before exploration. The reserved file above remains unchanged until native approval; all subsequent draft edits use the runtime's permitted native plan file.
<!-- /CC-ONLY -->

**Do this FIRST** — before any exploration or questions. Status bar shows progress immediately.
