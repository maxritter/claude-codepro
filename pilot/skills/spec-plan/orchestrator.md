---
name: spec-plan
description: "Planning phase of the /spec feature workflow — owns the plan file until the user approves it. Entered from the /spec dispatcher for a new feature task, or for an existing plan still marked Status: PENDING and Approved: No."
argument-hint: "<task description> or <path/to/plan.md>"
user-invocable: false
hooks:
  Stop:
    - command: uv run --no-project --python python3 python "$HOME/.pilot/hooks/spec_plan_validator.py"
---

# /spec-plan - Planning Phase

**Phase 1 of the /spec workflow.** Explores codebase, designs implementation plan, verifies it, gets user approval.

**Input:** Task description (new) or plan path (continue unapproved)
**Output:** Approved plan at `docs/plans/YYYY-MM-DD-<slug>.md`
<!-- CC-ONLY -->
**Next:** On approval → `Skill(skill='spec-implement', args='<plan-path> $LANE_FLAG')`
<!-- /CC-ONLY -->
<!-- CODEX-START
**Next:** On approval → continue immediately with the `$spec-implement` skill instructions using arguments: `<plan-path> $LANE_FLAG`.
CODEX-END -->

---

## Run identity on entry

Parse the plan path or description separately from optional `--lane <id>` before status detection or file access. Resolve `LANE_ID` and `$LANE_FLAG` (`--lane <id>` or nothing) from these arguments at every phase entry, including verification loopbacks and resumes. Retain them with the plan identity across compaction and pass `<plan-path> $LANE_FLAG` to every subsequent phase. Shell variables from another phase do not survive. A lane argument must never become part of the plan filename or silently disappear.

## ⛔ Critical Constraints

- **Choose planning delegation autonomously and sparingly.** Direct exploration is the baseline. Add the minimum number of read-only agents only for genuinely independent questions whose breadth would materially flood the main context; never fan out duplicate perspectives, and nest only when a flat assignment cannot represent the work. Never ask the user for permission to spawn qualifying agents. Prevent conflicting writes to the plan file and keep one coherent final plan; run the managed `spec-review` agent in Step 10 when enabled.
- **Run spec-review when enabled** — it runs for every feature spec when `$PILOT_SPEC_REVIEW_ENABLED` is not `"false"`. Context level is NOT a valid reason to skip. To disable, use Console Settings → Reviewers → Spec Review toggle.
- **NEVER write code during planning** — planning and implementation are separate phases
- **Verify repository facts; state consequential assumptions.** Ask only when a missing decision cannot be resolved from the request or workspace and materially changes the result.
- **Continue through planning to approval.** Resolve routine planning and review findings autonomously; pause earlier only for a genuine missing decision or blocker.
- **Re-read plan after user edits** — before asking for approval again
- **Plan file is source of truth** — survives across auto-compaction cycles
- **Keep progress updates brief and useful.** Report discoveries, decisions, and blockers during longer work; omit step-by-step narration and routine hook details.

### Planning depth

Draft once the requested scope, affected components, dependencies, and verification approach are supported by evidence. Investigate further only to resolve a concrete uncertainty that could invalidate the plan. Reuse earlier findings; do not repeat broad searches to satisfy a call count or phase checklist.

Preserve the full requested scope across long runs. Save findings and unresolved questions in the plan before context compaction; context usage is a reason to preserve state, never to trim the user's requirements or declare an unsupported plan ready.
