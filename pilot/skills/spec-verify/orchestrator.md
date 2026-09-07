---
name: spec-verify
description: "Verification phase of the /spec feature workflow — decides whether a finished plan earns VERIFIED, and sends it back to implementation when it does not. Entered from the /spec dispatcher for a feature plan marked Status: COMPLETE."
argument-hint: "<path/to/plan.md>"
user-invocable: false
---

# /spec-verify - Verification Phase

**Phase 3 of the /spec workflow (features).** Runs comprehensive verification: automated checks, code review, program execution, and E2E tests. For bugfix plans, use `spec-bugfix-verify` instead.

**Input:** Plan file with `Status: COMPLETE`
**Output:** Plan status → VERIFIED (success) or loop back to implementation (failure)

---

## Run identity on entry

Parse the plan path or description separately from optional `--lane <id>` before status detection or file access. Resolve `LANE_ID` and `$LANE_FLAG` (`--lane <id>` or nothing) from these arguments at every phase entry, including verification loopbacks and resumes. Retain them with the plan identity across compaction and pass `<plan-path> $LANE_FLAG` to every subsequent phase. Shell variables from another phase do not survive. A lane argument must never become part of the plan filename or silently disappear.

## ⛔ KEY CONSTRAINTS

<!-- CC-ONLY -->
1. **Run the changes review when enabled** — active whenever `PILOT_CHANGES_REVIEW_ENABLED` is not `"false"` (read in Step 0). Step 1 launches the `changes-review` sub-agent in the background; Step 3 collects its completed final JSON response through the returned native handle. To disable, use Console Settings → Spec Workflow → Review Agents → Changes Review.
2. **Do not reuse `spec-review` as a changes review** — its planning findings are stale in this phase. Beyond the required `changes-review`, keep verification in the current agent unless a concrete independent check would materially protect context; then use the minimum useful count without asking for delegation permission. Only the completed final result from this run's Step 1 agent/task handle is this review's evidence; a saved findings file alone is not.
   ⛔ **Never `Skill(skill='code-review', ...)`.** That specific skill carries `disable-model-invocation`, so the call is rejected. If a concrete independent review is explicitly required beyond the managed reviewer and meets the bounded delegation criteria above, use the minimum available agent tools directly.
<!-- /CC-ONLY -->
<!-- CODEX-START
1. **Run native Codex changes review when enabled** — Step 1 launches the managed `changes-review` custom agent with the spawn-agent tool exposed in the current Codex tool schema when `PILOT_CHANGES_REVIEW_ENABLED` is not `"false"` (read in Step 0). Step 3 waits for and applies its findings.
2. **Do not reuse spec-review as changes review** — planning findings are stale in this phase. Beyond the required `changes-review`, keep verification in the current agent unless a concrete independent check would materially protect context; then use the minimum useful count without asking for delegation permission.
CODEX-END -->
3. **NO stopping** — Everything automatic. Never ask "Should I fix these?"
4. **Fix ALL findings** — must_fix AND should_fix. No permission needed.
5. **Code changes finish BEFORE runtime testing** — Phase A then Phase B.
6. **Plan file is source of truth** — re-read it after auto-compaction, don't rely on conversation memory.
7. **Re-verification after fixes is MANDATORY** — fixes can introduce new bugs.
8. **Quality over speed** — never rush due to context pressure.
