## Step 3: Plan the Fix

<!-- CC-ONLY -->
While native plan mode is active, omit the notification command below. Ask required clarification through the permitted native input surface; defer external notifications until native exit.
<!-- /CC-ONLY -->

### Gate — before writing the plan

Re-confirm the three Step 0 **Enforcement** questions (root cause stated as `file:lineN — function() does X but should do Y`; WHY it causes the symptom; confidence High or Medium). If any is NO → return to Step 2. No exceptions, even for "obvious" bugs.

### Fix approach selection

**Default: pick the obvious fix.** For most bugs the source-level change at the root cause is the only reasonable fix. Document it in one or two sentences and move on. Don't manufacture fake alternatives.

**Propose 2–3 approaches only when there is a genuine architectural choice** (patch at call site vs. fix at source vs. add validation layer, with materially different scope/regression/maintenance trade-offs). For each: name, what it fixes, trade-offs, recommendation.

**Ground approach labels in the root cause.** Step 2.5 already produced a concrete `Root Cause: file:line — function_name()` statement and Step 2.3 ran `codegraph_explore`. When proposing alternatives, option labels must reference the actual symbols/files involved — e.g., `Patch at OrderHandler.validate (call site, src/handlers/order.py:88)` vs. `Fix at source OrderValidator.check (src/validators/order.py:42)`. Generic labels ("patch at call site" / "fix at source") with no symbol names are a regression — the data to ground them is already in your investigation notes.

When a genuine choice exists AND `PILOT_PLAN_QUESTIONS_ENABLED` is not `"false"`: use `AskUserQuestion` to pick.

<!-- CODEX-START
Codex override: if the source-level fix is clearly correct and reversible, choose it without asking and record the decision in `## Fix Approach`. Use the current runtime's permitted structured input tool, with a concise prose fallback, only when the wrong choice would change multiple tasks, add a new dependency, or alter user-visible behavior outside the bug.
CODEX-END -->

```bash
~/.pilot/bin/pilot notify plan_approval "Fix Approach" "<plan-slug> — fix strategy" --plan-path "<plan_path>" 2>/dev/null || true
```

### Behavior Contract (MANDATORY)

```markdown
## Behavior Contract

**Given:** [precondition / state / input that triggers the bug]
**When:** [the action or call that exercises the code path]
**Currently (bug):** [actual, incorrect behavior — the symptom]
**Expected (fix):** [correct behavior the fix must produce]
**Anti-regression:** [named tests / flows / API contracts that must still pass]
```

`Anti-regression:` must name specific tests or flows — `test_search_with_filters_returns_200, test_search_pagination` not "existing search tests".

### Behavior Contract — completeness probe

Before locking the contract, work backward once: does the bug have a sibling that the current `Expected (fix):` does not cover? Walk these three prompts:

1. **What boundary inputs share the buggy code path?** Empty, zero, negative, max length, unicode, whitespace-only, duplicate, exactly-at-limit. If the bug repros on `""` but the contract only names "invalid input", tighten the language.
2. **Are there cancel / abort variants?** If the buggy path is user-initiated, is the cancel path also broken or already correct?
3. **Are there concurrency edges?** If two callers exercise the path simultaneously, does the bug surface only under contention, or only in isolation? The contract should name which.

For each gap found, either extend `Expected (fix):` to cover it OR document why it's out of scope in `## Investigation`. The reproducing test (Task 1) only catches what the contract names — gaps here become regression-prone follow-up bugs.

### Task structure — three tasks, no exceptions

⛔ Do NOT merge tasks. Separate checkboxes = separate proof.

**Task 1 — Write Reproducing Test (RED)**
Encode `Currently → Expected` via an existing public entry point. Run → must FAIL with the documented symptom. Worktree mode: commit alone before any fix code. Naming: `test_<function>_<bug>_<expected>`.

**Reuse > create.** If a test class already exists for this entry point, modify it (add one new test method that encodes the bug). Do NOT create a sister test class — that violates the parsimony rule (see the testing rules § Test Parsimony).

**`Trivial:` does not apply here.** The feature TDD loop's `Trivial:` escape (spec-implement's TDD loop) is feature-only. Bugfixes always require a reproducing RED test regardless of diff size — that is the bugfix lane's anti-regression guarantee, and removing it would destroy the lane's value.

**Task 2 — Implement Fix at Root Cause**
Minimal change at `Root Cause: file:line`. Fix at source, not symptom. Re-run reproducing test → must PASS. Run targeted test module(s), not full suite — full suite runs at Task 3. Diff must touch the root-cause file.

**Task 3 — Quality Gate**
Lint, type check, build (if applicable). Re-run full suite at the END (lint/type auto-fixes can break tests). UI-facing bugs: the Verification Scenario runs in verify phase, not here.

**Scope scaling:** simple bugs get short tasks, complex bugs get longer tasks — but always three tasks.

**Defense-in-depth:** when the bug propagated through multiple layers, plan validation at each layer (entry point, business logic, environment guards). Document as `Defense-in-depth:` in the Fix Approach section.

### Verification Scenario (UI-facing bugs only)

```markdown
### TS-001: [Bug Trigger / Fix Confirmation]
**Preconditions:** [State that triggers the bug]

| Step | Action | Expected Result (after fix) |
|------|--------|-----------------------------|
| 1 | [User action that triggered bug] | [Correct behavior now shown] |
| 2 | [Follow-up verification] | [No regression] |
```

Tool-agnostic — Claude Code Chrome, Chrome DevTools MCP, playwright-cli, or agent-browser per `browser-automation.md`.
