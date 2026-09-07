## Step 11: Update Plan Status

### Approval and evidence precondition

Before `Status: VERIFIED`, confirm:

1. The current reviewable result was presented through Step 10's permitted question mechanism.
2. The user explicitly approved that result after it was presented, or supplied applicable standing authorization.
3. No later code change or unresolved feedback invalidated that approval, and the required verification evidence still applies.

Preserve valid approval across turns and compaction. Do not require that the approval be the latest conversational message or match a fixed keyword list. An unrelated reply, bare resume nudge, silence, hook output, or passing tests is not approval. If required approval is missing, return to Step 10.

**When ALL passes AND user approves:**

1. Set `Status: VERIFIED` in plan
2. Register: `~/.pilot/bin/pilot register-plan "<plan_path>" "VERIFIED" $LANE_FLAG 2>/dev/null || true`

> **`$LANE_FLAG`** is `--lane <id>` when this run was dispatched as an orchestration lane, and **nothing at all** otherwise — the value the planning phase parsed from its arguments. It keeps the registration in `sessions/<id>/lanes/<lane>/` rather than the coordinator's single slot, which is what stops a lane's plan blocking the coordinator's stop guard (issue #174). Skills build into separate SKILL.md files, so this is restated wherever the placeholder is used.

3. Re-check any Goal Verification truth that was pending only on final status. At minimum, grep the plan header for `^Status: VERIFIED$`; if a truth also references task checkboxes or artifacts, re-check those exact paths/lines before reporting it verified.
4. Report completion with summary:
   ```
   ## Verification Complete
   **Issues Found:** X
   ### Goal Achievement: N/M truths verified
   ### Must Fix (N) | Should Fix (N) | Suggestions (N) | Out-of-lineage mentions (N)
   ### Docs: [files updated in Step 6.2, or "no doc impact"]
   ### Not Verified: [list items from Step 6.3, or "None"]
   ```

5. **Instruct the user:** Include in your completion message:
   ```
   Start a fresh context for unrelated work when useful; preserve this run's evidence and state.
   ```

**When verification FAILS (missing features, serious bugs — before reaching Step 10):**

⛔ **Iteration cap — check BEFORE re-invoking spec-implement.** Read `Iterations:` from the plan header. If `Iterations >= 3` BEFORE incrementing, stop the verify→implement loop and surface to the user. An infinite verify→implement loop on a feature plan is the single largest token-burn pattern in the workflow — three failed verifications means the plan is wrong, not that one more implement pass will fix it.

<!-- CC-ONLY -->
```
AskUserQuestion(
  question="Three verify iterations have failed for this plan. This pattern usually means the plan's design is incomplete or a verify check is mis-specified — not that one more implement pass will fix it. What now?",
  options=[
    "Continue — try one more iteration (rarely the right answer)",
    "Pivot — let me re-investigate the plan with you",
    "Abandon — leave PENDING, I'll come back to it"
  ]
)
```
<!-- /CC-ONLY -->
<!-- CODEX-START
Use the current runtime's permitted structured input tool for this decision, or a concise prose question when unavailable. Wait for the required answer:

1. Continue — try one more iteration (rarely the right answer)
2. Pivot — let me re-investigate the plan with you
3. Abandon — leave PENDING, I'll come back to it
CODEX-END -->

Handle:
<!-- CC-ONLY -->
- **Continue:** **set `Status: PENDING`**, increment `Iterations`, write `## Verification Gaps`, register status, invoke `Skill(skill='spec-implement', args='<plan-path> $LANE_FLAG')` as below. (Do NOT hand a `Status: COMPLETE` plan to spec-implement.)
<!-- /CC-ONLY -->
<!-- CODEX-START
- **Continue:** **set `Status: PENDING`**, increment `Iterations`, write `## Verification Gaps`, register status, then continue immediately with the `$spec-implement` skill instructions using arguments: `<plan-path> $LANE_FLAG`. (Do NOT hand a `Status: COMPLETE` plan to spec-implement.)
CODEX-END -->
- **Pivot:** set `Status: PENDING`, do NOT invoke spec-implement. Tell the user you're standing by for new investigation direction.
- **Abandon:** leave `Status: PENDING`, do not invoke spec-implement. Stop.

**When `Iterations < 3`:**

1. Add fix tasks to plan
2. Set `Status: PENDING`, increment `Iterations`
3. Register: `~/.pilot/bin/pilot register-plan "<plan_path>" "PENDING" $LANE_FLAG 2>/dev/null || true`
4. Write `## Verification Gaps` table to plan (overwrite if exists):
   ```markdown
   | Gap | Type | Severity | Affected Files | Fix Description |
   ```
<!-- CC-ONLY -->
5. Invoke `Skill(skill='spec-implement', args='<plan-path> $LANE_FLAG')`
<!-- /CC-ONLY -->
<!-- CODEX-START
5. Continue immediately with the `$spec-implement` skill instructions using arguments: `<plan-path> $LANE_FLAG`.
CODEX-END -->

ARGUMENTS: $ARGUMENTS
