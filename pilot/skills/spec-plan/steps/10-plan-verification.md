## Step 10: Plan Verification

Read `$HOME/.pilot/agents/review-state-protocol.md` before launching any enabled reviewer. Persist each returned native or companion handle atomically with the plan, lane, role, and lifecycle state before independent work; reload that record after compaction and before collection.

<!-- CC-ONLY -->
**While native plan mode is active:** run only the read-only self-checks against the permitted native draft. Defer both native and companion reviewer launches until successful native exit, when their durable handle records can be written. Step 12 then reruns this review step on the accepted registered plan before implementation; this also covers user edits in the approval dialog.
<!-- /CC-ONLY -->

### 10.0: No-Placeholders Self-Check (always — before launching reviewers)

Read the plan once, fresh-eyed. **Every match below is a plan failure** — fix it inline before any reviewer sees the plan or the user is asked to approve it.

- `TBD`, `TODO`, `FIXME`, "implement later", "fill in details", "details below"
- "add appropriate error handling", "add validation", "handle edge cases" — without naming which cases
- "write tests for the above" — a task must name the actual test cases, not a meta-instruction
- Cross-references that omit information the implementer needs; references to a shared contract are fine
- Tasks without enough evidence or direction to implement; code blocks are optional when paths, patterns, and acceptance criteria suffice
- References to types, functions, files, or env vars no task defines
- `<your-code-here>` / `<insert-X>` outside the header's literal placeholders
- Goal Verification truths that aren't falsifiable ("works correctly", "is fast enough")

```bash
grep -nEi "TBD|TODO|FIXME|implement later|fill in details|appropriate error handling|similar to Task" "<plan_path>"
```

**Then check cross-task identifier consistency.** Types, function names, property names, and env vars introduced in one task must be spelled identically everywhere later tasks use them — `clearLayers()` in Task 3 and `clearFullLayers()` in Task 7 is a bug the implementer inherits, not a synonym. Tasks are written in sequence and read out of order, so drift here stays invisible until implementation. Sorting the plan's identifiers puts near-misses on adjacent lines:

```bash
grep -oE '`[A-Za-z_][A-Za-z0-9_]*(\(\))?`' "<plan_path>" | sort | uniq -c
```

Scan for two spellings of one thing, then `grep -n` the pair to see which tasks disagree and fix the loser.

---

<!-- CC-ONLY -->
### 10.1: Claude spec-review

**Skip when** `PILOT_SPEC_REVIEW_ENABLED` is `"false"`. When enabled, review the full plan with depth proportional to its actual risk and unresolved assumptions; task count alone does not disable the user's chosen reviewer.

⛔ **Skipping the reviewer never skips Step 11 (annotations) or Step 12 (approval).** Those always run.

**Derive the plan slug** from the filename: strip the `YYYY-MM-DD-` prefix and `.md`. Example: `2026-03-02-sku-builder-modal-cleanup.md` → `sku-builder-modal-cleanup`.

Use the registered plan path as `REVIEW_PLAN_PATH`; on the Automated native path, wait for successful exit and use the accepted registered content. The reviewer reads this exact plan and returns it as `plan_file`.

Read and reconcile the existing native review record for this plan, lane, and `spec-review` role before launching anything. Resume its live handle, collect an already completed result, or reconcile an interrupted `launching` attempt; only a confirmed terminal or missing prior attempt permits a replacement.

Atomically write `state: launching` with `provider: native`, this role, plan/lane identity, and `reviewed_sha256` of the exact review anchor before the spawn call below. Use `review-state-protocol.md`. If the write fails or the current mode forbids it, defer the launch; do not create an unrecorded background job.

Launch with the actual `Agent` schema exposed in this session:

```
Agent(
  subagent_type="spec-review",
  run_in_background=true,
  prompt="""
  **Plan file:** <REVIEW_PLAN_PATH>
  **User request:** <original task description>
  **Clarifications:** <any Q&A>

  Review alignment with requirements and concrete failure risks.
  Remain read-only. Return ONLY valid JSON matching the spec-review schema.
  Set "plan_file" to the supplied Plan file path.
  """
)
```

Immediately persist the returned `native_agent_id` and `state: running` atomically in that same record before waiting, independent work, or a handoff. If saving fails, retain and reconcile this handle; do not spawn again.

Keep the returned agent/task handle and collect its final response in 10.3. Do not ask the reviewer to write a result file. The parent persists validated findings only when writes are permitted.



### 10.2: Codex adversarial review (optional — launch immediately, runs in parallel)

**Only when `PILOT_CODEX_SPEC_REVIEW_ENABLED` is `"true"`** (from Step 0).

**Codex-once:** at most one companion run per `/spec` invocation. Plan iterations — annotation feedback, plan edits, fixing prior findings — never trigger a second run.

```bash
SESS_ID="${CLAUDE_CODE_SESSION_ID:-${CODEX_THREAD_ID:-${PILOT_SESSION_ID:-}}}"
case "$SESS_ID" in ""|*[!A-Za-z0-9_-]*) echo "Review state needs a confirmed session identity" >&2; exit 1 ;; esac
SESS_DIR="$HOME/.pilot/sessions/$SESS_ID"
[ -z "$LANE_ID" ] || SESS_DIR="$SESS_DIR/lanes/$LANE_ID"
CODEX_FLAG="$SESS_DIR/codex-spec-review-ran-<plan-slug>.flag"
[ -f "$CODEX_FLAG" ] && echo "Codex already reviewed this plan in this session — skipping (codex-once)."
```

Otherwise **read `$HOME/.pilot/agents/codex-companion-protocol.md` and follow it end to end** (locate → render → launch → stall monitor → collect → mark). Supply:

| Protocol input | Value for plan review |
|---|---|
| `PROMPT_TEMPLATE` | `$HOME/.pilot/agents/spec-review-codex.md` |
| `ROLE` | `spec-review` |
| `LANE_ID` | Original parsed `--lane <id>` value, or empty for this main-session run |
| `{{PLAN_PATH}}` | absolute path to the plan file |
| `{{PLAN_GOAL}}` | the Goal sentence from the plan's `## Summary` |
| `{{CONTEXT_FILES}}` | newline-separated absolute paths the plan ports from or extends (the files named in `## Context for Implementer`) |
| `SLUG` | `<plan-slug>` |
| `CODEX_FLAG` | the path above |

⛔ **Use the protocol's `task --prompt-file` launch — never `adversarial-review --base` or `--scope branch` for a plan.** Those bundle a git diff as the review target, and plan files are gitignored here, so Codex receives an empty diff and returns a meta-finding ("no implementation diff was provided") with nothing substantive about the plan. `task` lets Codex read the plan file directly. (`adversarial-review` stays correct in `spec-verify`, where real working-tree code exists.)

**Do NOT wait** — go collect the Claude reviewer first.

### 10.3: Collect and fix

**Claude reviewer:** use the original agent/task handle with the current runtime's wait/result mechanism (including `TaskOutput` when exposed), or consume the final response returned by a foreground `Agent` call. Read the completed JSON response, not an agent-authored file or a transcript's partial output.

At native collection, confirm terminal completion and atomically write `state: completed`; validate the final JSON schema and matching `plan_file`, then write `state: collected` with the consumed result identity. If terminal output remains invalid or unavailable after correction/recovery, write `state: incomplete` with the reason and follow the explicit fallback. Observation timeouts leave the original live state and handle intact.

Validate the schema and that `plan_file` equals `REVIEW_PLAN_PATH`. For malformed or mismatched output, ask the same agent for a corrected final JSON response when supported. If no valid result is available, report the independent review as incomplete and perform the documented self-review fallback; never turn missing output into "no findings."

An observation timeout or quiet output is not failure. Inspect the original handle and keep waiting while it is live. Retry only after confirmed terminal failure or a missing handle. Preserve the handle and any validated result across compaction without writing outside native plan permissions.



Validate findings against the actual plan, evidence, and requested scope. Fix every supported in-scope must_fix and should_fix. Treat suggested fixes as proposals; apply suggestions only when they independently improve the requested result within scope. Record the evidence resolving unsupported findings.

**Codex** — collect per the protocol's §5 once its monitor exits, and fix every must_fix and should_fix inline before requesting approval. Codex findings frequently surface architectural gaps the Claude reviewer misses; weigh them at least equally. If the companion never produced a result after its one retry, proceed on the Claude reviewer alone and say so before asking for approval.

Proceed to Step 11 once all must_fix and should_fix from both reviewers are resolved.
<!-- /CC-ONLY -->
<!-- CODEX-START
**If `PILOT_SPEC_REVIEW_ENABLED` is `"false"` (from Step 0),** skip native Codex plan review and proceed to the task-card format check below.

**When enabled:** launch the managed Codex custom agent and wait for its final JSON response before requesting approval.

Read and reconcile the existing native review record for this plan, lane, and `spec-review` role before launching anything. Resume its live handle, collect an already completed result, or reconcile an interrupted `launching` attempt; only a confirmed terminal or missing prior attempt permits a replacement.

Atomically write `state: launching` with `provider: native`, this role, plan/lane identity, and `reviewed_sha256` of the exact review anchor before the spawn call below. Use `review-state-protocol.md`. If the write fails or the current mode forbids it, defer the launch; do not create an unrecorded background job.

Use the spawn-agent tool exposed in the current Codex tool schema with `agent_type="spec-review"` and this message:

```
Plan file: <plan-path>
User request: <original task description>
Clarifications: <any Q&A>

Review for alignment with requirements and adversarial risks.
Return ONLY valid JSON matching the spec-review schema.
Include the plan file path in the `plan_file` field.
```

Immediately persist the returned `native_agent_id` and `state: running` atomically in that same record before waiting, independent work, or a handoff. If saving fails, retain and reconcile this handle; do not spawn again.

Keep the returned agent id and use the wait mechanism exposed in the current Codex tool schema. Follow the parameters shown by the current tools; do not copy a namespace or call signature from another Codex version.

At native collection, confirm terminal completion and atomically write `state: completed`; validate the final JSON schema and matching `plan_file`, then write `state: collected` with the consumed result identity. If terminal output remains invalid or unavailable after correction/recovery, write `state: incomplete` with the reason and follow the explicit fallback. Observation timeouts leave the original live state and handle intact.

Validate the final JSON against the required schema and plan identity. If invalid, request a corrected response from the same agent when possible. If a valid result remains unavailable, record the independent review as incomplete and perform the documented self-review fallback; never report malformed output as a passed review.

Validate `plan_file` matches the current plan. If it does not, discard the stale result and self-review instead of applying mismatched findings.

Validate each finding against the actual plan, evidence, and requested scope. Fix every supported in-scope `must_fix` and `should_fix`. Treat `suggested_fix` as a proposal; implement a suggestion only when it independently improves the requested result within scope. Record the evidence resolving unsupported findings; speed alone never expands the task.

Fix every `must_fix` and `should_fix` inline, then re-run the no-placeholders and task-card checks before approval.

Before Step 11, run this task-card format check on the plan:

```bash
grep -nE '^### Task [0-9]+:|^\*\*(Objective|Files|Key Decisions / Notes|Definition of Done):\*\*' "<plan_path>"
```

Every `### Task N:` block under `## Implementation Tasks` must contain all four bold labels: `**Objective:**`, `**Files:**`, `**Key Decisions / Notes:**`, and `**Definition of Done:**`. Fix any plain labels such as `Files:`, `Key Decisions:`, `Definition of Done:`, or `Verification:` before asking for approval.

Self-review the plan for obvious issues before requesting approval: missing edge cases, unclear DoD criteria, placeholder text, wrong task-card label format, and unresolved ambiguities.
CODEX-END -->
