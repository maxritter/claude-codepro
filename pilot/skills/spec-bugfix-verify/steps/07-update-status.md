## Step 7: Update Plan Status

### Approval and evidence precondition

Before `Status: VERIFIED`, confirm:

1. The current reviewable result was presented through Step 6's permitted question mechanism.
2. The user explicitly approved that result after it was presented, or supplied applicable standing authorization.
3. No later code change or unresolved feedback invalidated that approval, and the required verification evidence still applies.

Preserve valid approval across turns and compaction. Do not require that the approval be the latest conversational message or match a fixed keyword list. An unrelated reply, bare resume nudge, silence, hook output, or passing tests is not approval. If required approval is missing, return to Step 6.

**All passes and user approves:** Set `Status: VERIFIED`, register:
```bash
~/.pilot/bin/pilot register-plan "<plan_path>" "VERIFIED" $LANE_FLAG 2>/dev/null || true
```

> **`$LANE_FLAG`** is `--lane <id>` when this run was dispatched as an orchestration lane, and **nothing at all** otherwise — the value the planning phase parsed from its arguments. It keeps the registration in `sessions/<id>/lanes/<lane>/` rather than the coordinator's single slot, which is what stops a lane's plan blocking the coordinator's stop guard (issue #174). Skills build into separate SKILL.md files, so this is restated wherever the placeholder is used.

Report:
```
Bugfix verified — regression test passes, full suite green.
Start a fresh context for unrelated work when useful; preserve this run's evidence and state.
```

**Fails:**

⛔ **Iteration cap.** Read `Iterations:` from the plan header. If `Iterations >= 3` BEFORE incrementing, stop the fix-on-fix loop:

<!-- CC-ONLY -->
```
AskUserQuestion(
  question="Three fix iterations have failed verification. This pattern usually means the bug is architectural — fixing symptoms in different places, each fix revealing a new failure mode. What now?",
  options=[
    "Continue — try one more fix (rarely the right answer)",
    "Pivot — let me re-investigate root cause with you",
    "Abandon — leave PENDING, I'll come back to it"
  ]
)
```
<!-- /CC-ONLY -->
<!-- CODEX-START
Use the current runtime's permitted structured input tool for this decision, or a concise prose question when unavailable. Wait for the required answer:

1. Continue — try one more fix (rarely the right answer)
2. Pivot — let me re-investigate root cause with you
3. Abandon — leave PENDING, I'll come back to it
CODEX-END -->

Handle:
<!-- CC-ONLY -->
- **Continue:** **set `Status: PENDING`**, add fix tasks, increment `Iterations`, invoke `Skill(skill='spec-implement', args='<plan-path> $LANE_FLAG')` as below. (Do NOT hand a `Status: COMPLETE` plan to spec-implement.)
<!-- /CC-ONLY -->
<!-- CODEX-START
- **Continue:** **set `Status: PENDING`**, add fix tasks, increment `Iterations`, then continue immediately with the `$spec-implement` skill instructions using arguments: `<plan-path> $LANE_FLAG`. (Do NOT hand a `Status: COMPLETE` plan to spec-implement.)
CODEX-END -->
- **Pivot:** set `Status: PENDING`, do NOT invoke spec-implement. Tell the user you're standing by for new investigation direction.
- **Abandon:** leave `Status: PENDING`, do not invoke spec-implement. Stop.

<!-- CC-ONLY -->
**When `Iterations < 3`:** Add fix tasks, set `Status: PENDING`, increment `Iterations`, invoke `Skill(skill='spec-implement', args='<plan-path> $LANE_FLAG')`.
<!-- /CC-ONLY -->
<!-- CODEX-START
**When `Iterations < 3`:** Add fix tasks, set `Status: PENDING`, increment `Iterations`, then continue immediately with the `$spec-implement` skill instructions using arguments: `<plan-path> $LANE_FLAG`.
CODEX-END -->

ARGUMENTS: $ARGUMENTS
