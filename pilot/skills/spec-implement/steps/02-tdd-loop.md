## Step 2: TDD Loop

### Anti-pattern: horizontal slicing

⛔ **Do NOT write all RED tests for the plan first, then all GREEN implementations.** That is "horizontal slicing" — it produces tests that test imagined behaviour and shapes, not actual behaviour. Tests written in bulk anchor on the function signatures you imagined, not the ones you'd actually want after writing the implementation.

The TDD loop runs **per task**, vertical slice: RED for this task → GREEN for this task → refactor → next task. One test → one implementation → repeat. Each cycle informs the next.

If you find yourself queuing 3+ RED tests before any GREEN, stop and complete the first cycle.

---

**For EVERY task (generic flow — features use this as-is; bugfixes use it via the Bugfix Lane overrides below):**

1. **Read plan's implementation steps** — list files to create/modify/delete
2. **Call chain analysis:** Reuse verified plan evidence. Use structural tracing when a changed runtime contract has non-local effects not yet understood; a local function or prose/config edit does not need another graph call merely because this is a new task.
<!-- CC-ONLY -->
3. **Mark in_progress:** `TaskUpdate(taskId, status="in_progress")`
<!-- /CC-ONLY -->
4. **TDD Flow:**
   - **RED:** Write failing test → verify it fails (feature missing, not syntax error)
   - **GREEN:** Implement minimal code to pass
   - **REFACTOR:** Improve while keeping tests green
   - Skip TDD for: docs, config, IaC, formatting-only changes (**features only** — the Bugfix Lane below removes this escape hatch)
   - **`Trivial:` escape.** If the task's `Trivial:` field is populated, skip RED. Apply the change, then run the existing covering test or verification command referenced in the justification (it must pass after the change — that is the GREEN signal), then continue to step 5. If the referenced check does NOT pass, the change is not trivial — remove the `Trivial:` field, return to RED. The changes review and `spec-verify` Step 2.1 audit the claim against the actual diff post-implementation; padding `Trivial:` to skip TDD is a `must_fix` finding.
   - **Discovery protocol:** The plan is a working document, not frozen — implementation legitimately learns things planning could not. When something contradicts how you expected it to work, check the plan's `## Assumptions` section, identify which task numbers are affected, and classify:
     - **Tactical** — the task's goal and approach hold; a detail differs (wrong helper name, an extra file to touch, a different signature). Adapt, record it under `## Deviations` (create the section if absent), continue. No user round-trip.
     - **Material** — invalidates a task or assumption, changes scope or approach, adds/removes tasks, or contradicts a decision the user made. Do NOT quietly plough on, and do NOT silently re-plan. Raise it: state the discovery and the options, then ask — `AskUserQuestion` where available; otherwise ask in prose per `agent-gate-protocol.md` with `SENTINEL_PATH` `$SESS_DIR/spec-discussion-paused` (recipe in the constraints above). If discussion follows, the pause holds turn to turn. On resume, apply the agreed amendments — task list, `## Assumptions`, `Files:` blocks — and record a `## Deviations` entry marked `user-agreed`. The discussion is the approval; there is no formal re-approval gate.
     - **Blocking** — cannot proceed either way: same ask, same pause.

     `## Deviations` entry shape: `- Task N (tactical|user-agreed): <discovery> → <what changed>`. ⛔ **A deviation that changes which files are touched must name the exact repository paths** — in the entry AND by updating the affected task's `Files:` block in the same edit. Verification scopes review staging and lineage to the plan's `Files:` blocks plus the paths in this section; a pathless entry like "used a different helper" leaves the extra file outside the review diff entirely, so it reads as out-of-scope drift.
5. **Verify tests pass** — run the focused tests that cover this task; the repository's broader required suite runs after the integrated change
6. **Execute the relevant behavior** when this task needs runtime evidence. Reuse a valid observed run or the plan's integration verification for unchanged paths; use the available browser/app tools for user-visible changes and preserve unrelated services
7. **Check diagnostics** — zero errors
8. **Validate Definition of Done** — all criteria from plan
9. **Self-review:** Completeness? Names clear? YAGNI? Tests verify behavior not implementation?
10. **Performance:** Is any expensive work (parsing, transforming, I/O) running on a hot path without caching or memoization? Are heavy dependencies imported fully when a lighter/tree-shaken alternative exists? Does repeated invocation (polling, re-render, request loop) redo work when input hasn't changed?
11. **Per-task commit (worktree only):** `git add <files> && git commit -m "{type}(spec): {task-name}"`
<!-- CC-ONLY -->
12. **Mark completed:** `TaskUpdate(taskId, status="completed")`
<!-- /CC-ONLY -->
13. **Update plan file immediately** — ⛔ **NON-NEGOTIABLE.** Change `[ ]` → `[x]` for the task in `## Progress Tracking`. Update any Completed/Remaining counts. Do NOT proceed to the next task until the checkbox is updated.

---

### Test parsimony reminder

Follow the testing rules already loaded for this task. Reuse behavioral tests when code moves; do not mirror production structure or duplicate coverage merely because a helper changes location. The bugfix lane still requires a reproducing regression signal and does not use the `Trivial:` annotation.

---

### ⛔ Bugfix Lane — Overrides When `Type: Bugfix`

**If the plan header contains `Type: Bugfix`, the rules below OVERRIDE the generic flow above. No exceptions — not for "obvious" bugs, typos, or one-line fixes.**

**Global rules (apply to all three tasks):**

1. The plan has THREE tasks: `Write Reproducing Test (RED)` → `Implement Fix at Root Cause` → `Quality Gate`. Do not merge them. Do not skip Task 1 because "I already see the fix."
2. The "Skip TDD for docs, config, IaC, formatting-only" escape hatch (step 4 above) does **NOT** apply to bugfixes. Even config-driven bugs need a reproducing test at the end-to-end boundary.
3. Re-use the plan's `## Investigation` section instead of re-running codegraph. If the plan already documents callers/callees/impact for the root-cause function, read it from the plan — skip generic step 2. Re-run `codegraph_explore(query="<fn> callers and callees")` only when the plan's breadcrumbs are missing or stale for a specific function you're about to modify.

**Per-task flows — run the flow matching the current task, not the generic loop above:**

#### Task 1 — Write Reproducing Test (RED)

Minimal flow. No production code here, so most generic steps (call-chain analysis, performance audit, self-review) are inapplicable.

1. Read Task 1's `Entry point:` and the `## Behavior Contract` from the plan.
2. Write a test that encodes `Currently → Expected` via the entry point, named `test_<function>_<bug>_<expected>`.
3. Run it → **must FAIL** with an error matching the Behavior Contract's `Currently (bug)`.
4. If it passes on first run: the test is wrong or the bug is already fixed. STOP, re-investigate, do not proceed to Task 2.
5. Worktree mode: commit as its own commit (`test(spec): add reproducing test for <bug>`). This keeps the test file separable from the fix — it does not skip any verification step.
6. Update plan checkbox (`[ ]` → `[x]`), mark task completed.

#### Task 2 — Implement Fix at Root Cause (GREEN)

This is the only task that modifies production code.

1. Call-chain analysis: use plan's Investigation if it covers the function; otherwise run `codegraph_explore(query="<root-cause fn> callers and callees")` on the root-cause function only.
2. Make the minimal change at `Root Cause: file:line`. Fix at the source, not at the symptom.
3. Forbidden: new broad `try/except` around the failing call, `if value is None: return default` at the caller when the bug is upstream, swallowed exceptions, silently normalised bad inputs. Legitimate defense-in-depth requires an explicit entry in the plan's `Defense-in-depth:` field.
4. Re-run the reproducing test → **must PASS**. Then run the test module(s) covering the root-cause file — fast, scoped (e.g. `pytest path/to/test_module.py -q`). The full anti-regression suite runs at the Quality Gate task, not here. Running the full suite per-fix-task is the single biggest token sink in bundled bugfix plans.
5. Diagnostics zero errors. Confirm the diff touches the root-cause file from the plan.
6. Worktree mode: commit (`fix(spec): <bug>`). Update plan, mark task completed.

#### Task 3 — Quality Gate

Runner-only task. Code may change only via lint/type/formatter auto-fixes; if it does, the suite must still be green at task close.

1. Run lint, type check, build (if applicable) — the commands listed in Task 3's `Verify:` field.
2. Fix any findings inline.
3. **Re-run the full test suite.** Lint/type/formatter changes can break tests — a green checkbox on this task means the suite is green AFTER those fixes, not before.
4. If the suite failed from an auto-fix: revert the offending change or write a targeted correction, re-run lint/types/suite until all green.
5. Worktree mode: amend onto Task 2's commit or add a small `chore(spec): lint/types` commit. Update plan, mark task completed.

**Then hand off to `spec-bugfix-verify` (via Step 3).** It audits the Behavior Contract and the original user-level symptom, reuses current valid RED/suite evidence, and reruns only checks whose inputs changed or evidence is missing. Any reconstruction of pre-fix behavior happens in an isolated snapshot.
