## Step 3: Code Review & Re-Verify

<!-- CC-ONLY -->
**If `PILOT_CHANGES_REVIEW_ENABLED` is `"false"` (from Step 0),** skip the review collection below. If the Codex companion was launched in Step 1, still collect it — then proceed to Step 4 (Phase B). If neither reviewer is enabled, skip this step entirely.

**When enabled — mandatory. Never skip**, however confident you are, however high the context, however green the tests.

#### Collect the findings from the sub-agent launched in Step 1

**Review freshness:** the Step 1 reviewer started before Step 2 checks. If fixes changed its inputs, tell the existing reviewer which files changed and request review of the current diff. Preserve valid findings for unchanged code. If a replacement is needed, confirm the original is terminal or stop it before a new launch, and retain the new handle. Do not use a stale report as evidence for changed code.

Collect `CHANGES_REVIEW_AGENT_ID` through the wait/result mechanism actually exposed by the runtime, including `TaskOutput` when available. A foreground `Agent` call can return the result directly. Consume the completed final JSON response; do not poll an agent-authored findings file or use partial transcript output as a verdict.

Validate the JSON schema and `plan_file` against this plan. If invalid, request a corrected final response from the same agent when possible. If no valid result can be obtained, record the independent review as incomplete in this report and the Not-Verified table, then use the documented self-review fallback. Malformed output is never a passed review.

Keep waiting on the original handle while it is live. Quiet output, transient observation failure, or a wait timeout does not justify restarting it. Only confirmed terminal failure or a missing handle can justify a replacement. Retain handle/result identity across compaction. The parent may save validated JSON for bookkeeping when writes are permitted; that file is not the completion signal.



**Validate agent findings against actual evidence and scope — lineage first** (same rule as the table below; out-of-lineage findings are mention-only regardless of severity). Fix every supported in-scope `must_fix` and `should_fix`; treat suggested fixes as proposals. Apply suggestions only when they independently improve the requested result within scope, otherwise report them. Record the evidence resolving unsupported findings. The agent's `truths` array feeds the report's Goal Achievement line. Then continue at "Collect Codex results".

⛔ **Resolve every cannot-verify item yourself — silence from the reviewer is not a pass.** A reviewer scoped to a diff cannot check a requirement living in unchanged code or spanning tasks, so it hands the question back: `category: cannot_verify` from the changes-review agent, a `cannot verify from diff:` info-severity finding from Codex, and any truth returned with `status: uncertain`. Each one is yours to settle before this step's report — you hold the plan and the cross-task context the reviewer lacks. Confirm the requirement is met (say so in the report) or find it genuinely missing, in which case it becomes a **must_fix** and runs the fix loop like any other. Neither fixing them blind nor listing them as mentions counts as resolving them.

⛔ **Do not substitute `Skill(skill='code-review', ...)` for a sub-agent that came back empty or failed.** The skill carries `disable-model-invocation`; the call is rejected and the iteration ends up with no review while the report claims one. If the sub-agent produced nothing after its one relaunch, record the gap in this step's report and the Step 6.3 Not-Verified table, and rely on the Step 2.2 audit for this iteration.

#### Apply findings (severity → action)

**Fix automatically — no user permission needed.** **Lineage is evaluated FIRST:** a finding outside the spec's lineage — the plan's `Files:` blocks plus files recorded under its `## Deviations` section — is mention-only regardless of severity. Out-of-lineage crashes get reported, never auto-fixed. Only in-lineage findings run through the rows below.

| Finding class | Action |
|---------------|--------|
| Outside the spec's lineage (CHECK FIRST — overrides every row below) | **Mention-only — do NOT fix** (mirrors the pre-existing-issue rule) |
| `category: cannot_verify`, a `cannot verify from diff:` Codex finding, or a truth with `status: uncertain` | **Resolve it yourself** — confirm the requirement is met, or find it missing and treat as **must_fix** |
| `failure_scenario` names a concrete crash, wrong output, security, or data-integrity problem | **must_fix** — fix immediately |
| Cleanup / efficiency / altitude finding (duplication, wasted work, maintainability), single-site | **should_fix** — fix immediately |
| Cleanup that would expand scope (3+ files, architectural) | **suggestion** — mention in the report; speed alone does not authorize expanding the task |

Rank order is the tiebreaker within a class. For each fix: implement → run relevant tests → log "Fixed: [title]".

#### Collect Codex results (if launched in Step 1)

**Never skip or defer it.** Follow `$HOME/.pilot/agents/codex-companion-protocol.md` §4–§6 with the `JOB_ID` and `PROMPT_FILE` from Step 1: wait on the registered job, distinguish live observation from terminal failure, then fetch and validate the result, apply supported findings by severity (lineage first), mark the codex-once flag, and clean up.

If the companion produced no result after its one retry, proceed WITHOUT the Codex pass and record the gap explicitly — in this step's report and the Step 6.3 Not-Verified table, noting how long it ran and when its log last advanced. Continue with this iteration's changes-review results.

**Report:**
```
## Code Verification Complete
**Issues Found:** X
### Goal Achievement: N/M truths verified   (from the Step 2.2 Plan Compliance & Goal-Truth Audit)
### Must Fix (N) | Should Fix (N) | Suggestions (N) | Out-of-lineage mentions (N)
```

#### Re-verification (only for structural fixes)

**Skip** when the fixes were localized (terminology, error handling, test updates, minor bugs) — run tests + lint to confirm, then proceed to Phase B.

**Re-verify** when fixes added functionality, changed APIs, or introduced significant new code paths: re-run the Step 2.2 Plan Compliance & Goal-Truth Audit on the post-fix diff (fixes can break mitigations or truths), then request another completed review response from the same changes-review agent when supported, or launch a new reviewer after the original is terminal, with `Changed files:` = the fixed files, so the review is SCOPED to what the fixes touched rather than the whole spec diff. Max 2 iterations before adding remaining issues to the plan.
<!-- /CC-ONLY -->
<!-- CODEX-START
**If `PILOT_CHANGES_REVIEW_ENABLED` is `"false"` (from Step 0 — Step 1 was skipped),** skip this step entirely and proceed to Step 4 (Phase B).

**When enabled — mandatory. Never skip.** Reload the `changes-review` record from `$HOME/.pilot/agents/review-state-protocol.md`, verifying this plan and lane identity. Use its `native_agent_id` as `CHANGES_REVIEW_AGENT_ID`. Reconcile an interrupted launch with the runtime inventory; do not relaunch merely because working notes or a shell variable are missing. Persist a replacement only after the original handle is confirmed terminal or missing.

Do not silently skip review while enabled; if the runtime cannot recover the recorded job, report the missing evidence and use the explicit self-review fallback below.

Wait for the final result with the wait mechanism exposed in the current Codex tool schema, using `CHANGES_REVIEW_AGENT_ID` and the tool's current parameters. Do not invent a namespace or reuse a stale call signature.

Validate the final JSON against the required schema and plan identity. If invalid, request correction from the same agent when possible. If no valid result can be collected, record the independent review as incomplete in the report and Not-Verified table, then perform the documented self-review fallback. Malformed output is never a passed review.

Validate `plan_file` matches the current plan. If it does not, discard the stale result and self-review the diff before proceeding.

Validate findings against actual evidence and scope, lineage first — a finding outside the plan's `Files:` blocks and its `## Deviations` section is mention-only regardless of severity. Fix every supported in-scope `must_fix` and `should_fix`, treating suggested fixes as proposals. Apply a suggestion only when it independently improves the requested result within scope; speed alone is insufficient. Record the evidence resolving unsupported findings.

⛔ **Resolve every cannot-verify item yourself — silence from the reviewer is not a pass.** A reviewer scoped to a diff cannot check a requirement living in unchanged code or spanning tasks, so it hands the question back: `category: cannot_verify`, or a truth returned with `status: uncertain`. Settle each one before the report — you hold the plan and the cross-task context the reviewer lacks. Confirm the requirement is met (say so in the report) or find it genuinely missing, in which case it becomes a **must_fix** and runs the fix loop like any other.

Final-status-only findings are not implementation fixes. If a finding only says the plan still reads `Status: COMPLETE` instead of `Status: VERIFIED`, record it as pending Step 11 finalization and do not loop back to implementation. Step 11 is responsible for writing `VERIFIED` after the user review gate and re-checking final-status truths.

For each fix: implement → run relevant tests → log `Fixed: [title]`.

After all findings are handled, re-run the relevant automated checks from Step 2 before proceeding to Step 4.
CODEX-END -->
