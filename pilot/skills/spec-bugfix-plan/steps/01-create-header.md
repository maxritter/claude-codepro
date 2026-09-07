## Step 1: Create Plan File Header (FIRST)

1. **Parse flags** from arguments: `--worktree=yes|no` or `--new-branch` (default: `No`), plus `--lane <id>` when the dispatcher forwarded one. Strip the flags.
2. **Branch / worktree setup — only when the flag is `--new-branch` or `--worktree=yes`.** Read `$HOME/.pilot/agents/spec-branch-setup.md` and follow it, using branch prefix `fix/` and `<plan_slug>` derived from the bug description (the same slug as the plan filename), plus `<lane>` when one was supplied. On the default `--worktree=no` there is nothing to do — work continues on the current branch.

   **`$LANE_FLAG`** stands for `--lane <id>` on a lane run and for **nothing at all** otherwise; every `pilot register-plan` call in this workflow and in `spec-bugfix-verify` carries it. ⛔ On a lane run, probe once with `~/.pilot/bin/pilot register-plan --help 2>&1 | grep -q -- --lane` and **abort if absent** — never fall back to an unflagged registration, which puts this lane's plan in the coordinator's slot (issue #174).
3. **Generate filename:** `docs/plans/YYYY-MM-DD-<bug-slug>.md`. Reuse the named registered draft when resuming it; for a new plan choose a free filename (`-2`, `-3`, etc. on collision) instead of overwriting an existing file.
4. **Fetch author email** (best-effort — omit the `Author:` line entirely if this returns empty or fails):

   ```bash
   ~/.pilot/bin/pilot status --json 2>/dev/null | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('email',''))" 2>/dev/null
   ```
<!-- CC-ONLY -->
4b. **Detect agent:** If `$CLAUDE_CODE_ENTRYPOINT` is set, agent is `Claude Code`. Otherwise, agent is `Codex`.
<!-- /CC-ONLY -->
<!-- CODEX-START
4b. **Set agent:** Use `Codex`.
CODEX-END -->
5. **Write header:**

   ```markdown
   # [Bug Description] Fix Plan

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
   Type: Bugfix

   > Investigating bug...

   ## Summary

   **Symptom:** [Bug description from user]

   ---

   _Tracing root cause..._
   ```

   **`Status:` is a closed set** — only `PENDING` | `COMPLETE` | `VERIFIED`, written as the bare keyword with no trailing prose or parentheticals, as enforced by `pilot spec validate`. At creation it is always `PENDING`; never invent a custom status (no `RESOLVED`/`DONE`/`CLOSED`).

6. **Register:** `~/.pilot/bin/pilot register-plan "<plan_path>" "PENDING" $LANE_FLAG`. Check that registration succeeded before continuing; a missing registration cannot track the workflow or authorize its native-planning handoff.

<!-- CC-ONLY -->
7. In Automated mode, follow `$HOME/.pilot/agents/spec-native-plan.md` now, before investigation. The reserved file above remains unchanged until native approval; all subsequent draft edits use the runtime's permitted native plan file.
<!-- /CC-ONLY -->
