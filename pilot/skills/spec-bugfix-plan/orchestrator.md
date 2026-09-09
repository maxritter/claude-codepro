---
name: spec-bugfix-plan
description: "Planning phase of the /spec bugfix workflow — owns the bugfix plan file until the user approves it. Entered from the /spec dispatcher for a new bug task, or for an existing bugfix plan still marked Status: PENDING and Approved: No."
argument-hint: "<bug description> or <path/to/plan.md>"
user-invocable: false
hooks:
  Stop:
    - command: uv run --no-project --python python3 python "$HOME/.pilot/hooks/spec_plan_validator.py"
---

# /spec-bugfix-plan - Bugfix Planning Phase

**Phase 1 (bugfix).** Investigates root cause, creates lean fix plan, gets approval.

**Input:** Bug description (new) or plan path (continue unapproved)
**Output:** Approved bugfix plan at `docs/plans/YYYY-MM-DD-<slug>.md` with `Type: Bugfix`
<!-- CC-ONLY -->
**Next:** On approval → `Skill(skill='spec-implement', args='<plan-path> $LANE_FLAG')`
<!-- /CC-ONLY -->
<!-- CODEX-START
**Next:** On approval → continue immediately with the `$spec-implement` skill instructions using arguments: `<plan-path> $LANE_FLAG`.
CODEX-END -->

**Note:** This skill is invoked when the user types `/spec "<bug description>"` — they chose the full spec workflow. For a bugfix workflow without a plan file, users invoke `/fix` directly (separate user-facing command). The two are distinct entry points — honour the user's choice.

---

## Run identity on entry

Parse the plan path or description separately from optional `--lane <id>` before status detection or file access. Resolve `LANE_ID` and `$LANE_FLAG` (`--lane <id>` or nothing) from these arguments at every phase entry, including verification loopbacks and resumes. Retain them with the plan identity across compaction and pass `<plan-path> $LANE_FLAG` to every subsequent phase. Shell variables from another phase do not survive. A lane argument must never become part of the plan filename or silently disappear.

## Resuming an Unapproved Plan

When the argument ends with `.md`: read the plan, check `Status:` and `Approved:`. **Step 0 (runtime and workflow settings) always runs first**, then resume from wherever planning left off:

- No investigation yet → Step 2 (Investigation)
- Has investigation, no tasks → Step 3 (Plan the Fix)
- Complete but unapproved → Step 6 (Approval)

---

## Iron Laws

```
1. NO FIXES WITHOUT ROOT CAUSE — traced to file:line, explained WHY.
2. NO CODE WITHOUT A FAILING REPRODUCING TEST — the RED must exist first.
3. FIX AT THE SOURCE — not where the error appears.
4. ONE UNIFORM CORE — every bugfix plan has the same three agent-owned tasks; a proven non-automatable checkpoint may add a separate user-owned task without replacing them.
```

If Step 2 is incomplete, you cannot propose fixes. Symptom fixes are failure. Retroactive tests are failure. "I know the fix, I'll skip the test" is failure.

---

## Critical Constraints

- **NEVER write production code during planning** — planning and implementation are separate phases. When the runtime permits writes, temporary boundary instrumentation during Step 2 investigation (log/print lines marked `SPEC-DEBUG:`) is allowed to trace the root cause; it must be removed before the plan is written (and Step 1.5 of verification greps for the marker to catch leftovers).
- **NEVER assume — verify by reading files.** Trace the bug to actual file:line.
- **Lean ≠ skipping steps.** Small bugs get short tasks, not fewer tasks. The three agent tasks (Reproducing Test → Fix → Quality Gate) are non-negotiable; any user-owned checkpoint is additional and separately numbered.
- **Plan file is source of truth** — survives across auto-compaction cycles
- **Keep progress updates brief and useful.** Report evidence, decisions, and blockers during longer investigations; omit routine step narration.
<!-- CC-ONLY -->
- **Use the `AskUserQuestion` tool for clarifications** — it renders a structured form; use a concise prose question when no permitted structured tool is available
<!-- /CC-ONLY -->
<!-- CODEX-START
- **Use the runtime's structured user-input tool when available and permitted for this question**; otherwise ask a concise clarification question in prose and wait for required input
CODEX-END -->
- **If `PILOT_PLAN_QUESTIONS_ENABLED` is `"false"` (from Step 0),** skip all `AskUserQuestion` calls (Steps 2.1, 2.5 escalation, 3 approach selection). Make reasonable default assumptions (including selecting the recommended fix approach) and document them in the plan. Continue autonomously.

### Investigation depth

Investigate until the root-cause claim, reproducing test plan, and proposed source-level fix are supported by evidence. Read named locations directly; use intent search or call-graph tools for unresolved locations or cross-component relationships. Reuse findings and stop broad traversal once it no longer changes the fix.

Preserve the full requested bug scope across compaction. Do not force a confidence level, finalize an unsupported cause, or trim requirements to meet a context percentage or tool-call quota. If progress stops, identify the specific missing signal and ask only when it cannot be obtained from the available environment.

Follow the registered Pilot workflow and the current runtime's actual permissions; a skill does not override native read-only restrictions.

<!-- CC-ONLY -->
Automated Claude planning uses the native-plan bridge described in Step 0.
<!-- /CC-ONLY -->
