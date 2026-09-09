## Step 4: Write the Bugfix Plan

**Save to:** `docs/plans/YYYY-MM-DD-<bug-name>.md`

<!-- CC-ONLY -->
> During a prepared Automated native-planning handoff, write this full plan to the runtime's permitted native draft instead. The capture hook materializes the accepted result into the registered `docs/plans/` destination after native approval. Follow `$HOME/.pilot/agents/spec-native-plan.md`; do not write outside the permitted draft while native plan mode is active.
<!-- /CC-ONLY -->

```markdown
# [Bug Description] Fix Plan

Created: [Date]
<!-- CC-ONLY -->
Agent: [Claude Code|Codex — from Step 1 detection]
<!-- /CC-ONLY -->
<!-- CODEX-START
Agent: Codex
CODEX-END -->
Status: PENDING
Approved: No
Iterations: 0
Worktree: [Yes|No]
Type: Bugfix

## Summary

**Symptom:** [What user observes]
**Trigger:** [When/how it happens]
**Root Cause:** `file/path.py:lineN` — [what's wrong and why]

## Investigation

- [Key findings from tracing — breadcrumb trail so implementer understands the bug]
- [Working example for comparison, if relevant]
- [Recent changes that may have caused it, if relevant]

## Behavior Contract

**Given:** [precondition / state / input that triggers the bug]
**When:** [the action or call that exercises the code path]
**Currently (bug):** [actual, incorrect behavior — the symptom]
**Expected (fix):** [correct behavior the fix must produce]
**Anti-regression:** [what must still work — behavior the fix must NOT break]

## Fix Approach

**Chosen:** [Name of selected approach]
**Why:** [1-2 sentences — what it fixes and what it costs. If a rejected option is one an implementer might re-derive, mention the rejection in one half-sentence here. Do NOT add a separate Alternatives list.]

**Files:** [files to modify]
**Strategy:** [how to fix — reference pattern from working code if applicable]
**Tests:** [test files to create/modify — MUST exist before any fix code]
**Defense-in-depth:** [additional validation layers, if applicable — skip for isolated fixes]

## Verification Scenario (only for UI-facing bugs — omit otherwise)

### TS-001: [Bug Trigger / Fix Confirmation]
**Preconditions:** [State that triggers the bug]

| Step | Action | Expected Result (after fix) |
|------|--------|-----------------------------|
| 1 | [User action that triggered bug] | [Correct behavior] |
| 2 | [Follow-up verification] | [No regression] |

## Tasks

> Always include the three agent tasks below. The `- [ ]` checkboxes immediately under this heading are the progress tracker (`spec-implement` toggles them `[ ]` → `[x]`); the `### Task N:` blocks hold the bodies. Insert separately numbered user-owned checkpoints only when investigation proves they are necessary. No separate `## Progress Tracking` section needed.

- [ ] Task 1: Write Reproducing Test (RED)
- [ ] Task 2: Implement Fix at Root Cause
- [ ] Task 3: Quality Gate

### Task 1: Write Reproducing Test (RED)

**Objective:** Encode the Behavior Contract as a failing test BEFORE writing any fix code.

**Files:**

- Test: `[test file to create/modify]`

**Key Decisions / Notes:**

- Entry point: [public function or endpoint the test exercises — not internal helpers]

**Definition of Done:**

- [ ] Test exists and is named `test_<function>_<bug>_<expected>`.
- [ ] Test fails with an error matching the documented `Currently (bug)` behavior.
- [ ] In worktree mode, the RED test is committed as its own commit.
- [ ] Verify: `[command that runs ONLY this test — must FAIL]`

### Task 2: Implement Fix at Root Cause

**Objective:** Minimal change at `Root Cause: file:line` that makes the reproducing test pass without breaking `Anti-regression`.

**Files:**

- Modify: `[root-cause file — must include Root Cause file]`
- Test: `[test file from Task 1]`

**Key Decisions / Notes:**

- Strategy: [how the fix satisfies the Behavior Contract — fix at source, not at symptom]

**Definition of Done:**

- [ ] Reproducing test passes.
- [ ] Diff touches the root-cause file.
- [ ] No try/except wrappers hide the bad value; no callsite patches work around the symptom.
- [ ] Verify: `[command that runs the reproducing test — must PASS]`

### Task 3: Quality Gate

**Objective:** Lint + type check + build clean, with the full suite re-run to catch regressions introduced by any auto-fixes applied in this task.

**Files:**

- No production files expected; update this plan's progress and status.

**Key Decisions / Notes:**

- The suite runs here after lint/type/build because those commands can auto-modify imports, types, or formatting.

**Definition of Done:**

- [ ] Lint is clean.
- [ ] Type check is clean.
- [ ] Build is green if the project has a build step.
- [ ] Full suite is green.
- [ ] Performance audit passed: no expensive uncached work on hot paths in the diff.
- [ ] Verify: `[lint] && [type check] && [build if applicable] && [full suite command]`

**Evidence freshness:** the suite must be green after this task's code changes. The verify phase can reuse that result while the tested code, configuration, and environment remain unchanged; rerun when later fixes invalidate it.
```

**Always three agent-owned tasks.** Never collapse Task 1 + Task 2 into "Fix (test + code)". The separation is what prevents "I'll just write the code and add a test after." If investigation proves a human-only action is required, insert a separate task with `**Owner:** User` and a concrete `**User Action:**`, renumber contiguously, and retain all three agent tasks unchanged. Never mix manual and agent work in one task.

**Do NOT include:** "Goal Verification" sections, "Risks and Mitigations" table, "Assumptions" section, per-task "Dependencies" field.

**Include `## Verification Scenario` only for UI-facing bugs** (from the Verification Scenario guidance in Step 3). Omit entirely for backend/non-UI bugs.

**The `## Behavior Contract` section is MANDATORY for every bugfix plan** — it is the source of truth for what the reproducing test encodes and what verification audits.

<!-- CODEX-START
Before asking for approval, verify every `### Task N:` under `## Tasks` contains the exact task-card labels `**Objective:**`, `**Files:**`, `**Key Decisions / Notes:**`, and `**Definition of Done:**`. Plain labels such as `Files:`, `DoD:`, or `Verify:` do not render as clickable task-card fields.
CODEX-END -->
