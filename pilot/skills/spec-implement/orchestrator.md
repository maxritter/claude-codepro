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
- **NEVER stop during implementation on your own** — the stop guard blocks premature exits. If blocked with no user question to answer and no durable interaction pause: your very next action must be a tool call (TaskList, Read plan, or code change); never produce text-only responses when work remains. User messages follow the interaction-state rule below.
<!-- /CC-ONLY -->
<!-- CODEX-START
- **NEVER stop during implementation on your own** — the stop guard blocks premature exits. If blocked with no user question to answer and no durable interaction pause: your very next action must be a tool call (refresh the plan, read the plan, or make the next code/test change); never produce text-only responses when work remains. User messages follow the interaction-state rule below.
CODEX-END -->
- **User interruptions are answered, not steamrolled.** UserPromptSubmit records a discussion pause before this phase sees a real interruption. Answer it without restarting implementation and end with "⏸ Paused — say `resume` (or use `/spec resume`) to continue the plan." The pause persists across discussion, file edits, compaction, and Stop continuations. Only exact `resume`, `/spec resume`, or `$spec resume` clears it; words such as "continue" do not.
- **Decision and manual waits are explicit state.** Before asking about a material discovery, run `~/.pilot/bin/pilot plan-state pause --kind decision --message "<bounded question>" $LANE_FLAG`. Before handing over a user-owned task, use `--kind manual --task N --message "<exact action>"`. A manual wait accepts exact `done`; `resume` cannot clear it. Never create a discussion pause on your own to hand work back or dodge the next task.

---

## Feedback Loop Awareness

This phase may be called multiple times:
```
spec-implement → spec-verify → issues found → spec-implement → ...
```
When called after verification: read plan, check `Iterations` field, report "Starting Iteration N...", focus on uncompleted `[ ]` tasks (look for `[MISSING]` markers from verification).
