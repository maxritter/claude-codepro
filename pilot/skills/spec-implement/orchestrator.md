---
name: spec-implement
description: "Implementation phase of the /spec workflow — turns an approved plan into working code, task by task. Entered from the /spec dispatcher for a plan marked Approved: Yes with tasks still unchecked, whether first pass or a re-entry after verification found gaps."
argument-hint: "<path/to/plan.md>"
user-invocable: false
---

# /spec-implement - Implementation Phase

**Phase 2 of the /spec workflow.** Reads approved plan, implements each task using TDD (Red → Green → Refactor).

**Input:** Approved plan file (`Approved: Yes`)
**Output:** All tasks completed, status → COMPLETE
**Next:** Verify phase (type-aware: `spec-verify` for features, `spec-bugfix-verify` for bugfixes)

---

## Run identity on entry

Parse the plan path or description separately from optional `--lane <id>` before status detection or file access. Resolve `LANE_ID` and `$LANE_FLAG` (`--lane <id>` or nothing) from these arguments at every phase entry, including verification loopbacks and resumes. Retain them with the plan identity across compaction and pass `<plan-path> $LANE_FLAG` to every subsequent phase. Shell variables from another phase do not survive. A lane argument must never become part of the plan filename or silently disappear.

## ⛔ Critical Constraints

- **Choose delegation autonomously and sparingly** — direct execution is the baseline. Claude Code or Codex adds the minimum number of agents only for genuinely independent plan tasks where parallelism or context isolation materially helps; never fan out duplicate perspectives or checks the active agent can run directly. Never ask the user for permission merely to spawn qualifying agents. Preserve task dependencies, prevent overlapping writes, and verify results from the diff and fresh commands.
- **TDD is MANDATORY** — no production code without failing test first
- **NEVER SILENTLY SKIP TASKS** — every task is fully implemented, no "MVP scope" exceptions. The only legal way a task changes or leaves the plan is the discovery protocol (Step 2), with the change recorded under `## Deviations`.
- **Quality over speed** — never rush due to context pressure. Context warnings are informational. Finish current task with full quality — auto-compaction handles the rest.
- **Plan file is source of truth** — re-read after auto-compaction, don't rely on conversation memory
<!-- CC-ONLY -->
- **NEVER stop during implementation on your own** — the stop guard blocks premature exits. If blocked with no user question to answer: your very next action must be a tool call (TaskList, Read plan, or code change); never produce text-only responses when work remains. A user message that just says "Continue" or asks for status: re-read the plan and resume from the current task.
<!-- /CC-ONLY -->
<!-- CODEX-START
- **NEVER stop during implementation on your own** — the stop guard blocks premature exits. If blocked with no user question to answer: your very next action must be a tool call (refresh the plan, read the plan, or make the next code/test change); never produce text-only responses when work remains. A user message that just says "Continue" or asks for status: re-read the plan and resume from the current task.
CODEX-END -->
- **User interruptions are answered, not steamrolled.** When the user's message questions a decision, raises a discovery, or asks something the plan does not answer: stop implementing and answer it, then engage the discussion pause so the stop guard lets the conversation breathe, and end the turn with "⏸ Paused — say resume (or `/spec resume`) to continue the plan."

  ```bash
  SESS_DIR="$HOME/.pilot/sessions/${CLAUDE_CODE_SESSION_ID:-${CODEX_THREAD_ID:-${PILOT_SESSION_ID:-default}}}"
[ -z "$LANE_ID" ] || SESS_DIR="$SESS_DIR/lanes/$LANE_ID"
  mkdir -p "$SESS_DIR" && touch "$SESS_DIR/spec-discussion-paused"
  ```

  Re-touch the marker on every further discussion turn. When the user signals resume ("resume", "continue with the plan", `/spec resume`): `rm -f "$SESS_DIR/spec-discussion-paused"`, apply any agreed plan amendments (Step 2 discovery protocol), and continue from the current task. ⛔ The pause is never yours to take for free: engage it only in response to the user's own message, or alongside a material-discovery question you have just put to them — never to hand work back or dodge the next task.

---

## Feedback Loop Awareness

This phase may be called multiple times:
```
spec-implement → spec-verify → issues found → spec-implement → ...
```
When called after verification: read plan, check `Iterations` field, report "Starting Iteration N...", focus on uncompleted `[ ]` tasks (look for `[MISSING]` markers from verification).
