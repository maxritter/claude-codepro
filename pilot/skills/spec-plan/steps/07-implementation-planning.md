## Step 7: Implementation Planning

### 7.0: File Structure (when 4+ tasks expected, otherwise inline per task)

When the plan will have 4+ tasks, write a `## File Structure` section before tasks listing every file with one-line responsibility — decomposition decisions get locked in here. For 1–3 task plans skip this; the per-task `Files:` block already gives the same view.

```markdown
## File Structure

- `src/foo/bar.ts` (create) — pure function: `parseFoo(input) → Foo`. No I/O.
- `src/foo/loader.ts` (create) — fetches and caches Foo from API. Wraps `parseFoo`.
- `tests/foo/bar.test.ts` (create) — unit tests for `parseFoo`.
```

One responsibility per file. Files that change together live together. In existing codebases, follow established patterns — don't restructure unrelated code.

### 7.1: Task Granularity

**Task Granularity:** Each task is a coherent, verifiable change. Size tasks by dependencies and observable outcomes, not file counts. Split unrelated outcomes; merge changes that cannot be tested independently. Fold setup with no standalone value into the first task that needs it. Task ORDER implies dependencies — no separate `Dependencies:` field needed.

**Task Structure (4 required fields — keep it tight):**

```markdown
### Task N: [Component Name — a short imperative title; the Objective below carries the description.]

**Objective:** [REQUIRED — 2-3 sentences describing what this task does and why. Reads as the "what this task does" line shown below the title in the Console / pilot-shell.com spec viewer. State the change in plain prose, not bullet form. If a specific E2E scenario verifies it, reference it inline: "verified by TS-002".]

**Files:**

- Create: `exact/path/to/file.py`
- Modify: `exact/path/to/existing.py`
- Test: `tests/exact/path/to/test.py`

**Key Decisions / Notes:**

- [Technical approach, pattern to follow with file:line ref]
- `Trivial:` [Optional for a low-risk change whose behavior is adequately covered by an existing test or direct verification: explain why a new regression test adds no useful coverage and name `<existing-test-or-verify-command>`. Otherwise omit.]

**Definition of Done:**

- [ ] [Verifiable behavioral criterion — e.g., "GET /api/users?role=admin returns only admin users"]
- [ ] [Additional verifiable criterion if the task has multiple observable outcomes]
- [ ] Verify: `uv run pytest tests/path/to/test.py -q` (and any other command that proves the criteria above)
```

**Rules:**

- **DoD must be verifiable.** ✅ "GET /api/users?role=admin returns only admin users" ❌ "Feature works correctly".
- **`Files:` must list reviewable implementation artifacts.** Do not use the plan file under `docs/plans/...` as the only file for a task; in Pilot Shell that directory is gitignored workflow state and `spec-verify` reviewers scope to reviewable repository diffs. For smoke tests or "no production behavior change" specs, create or modify a harmless non-production, non-ignored repository artifact (for example a root-level smoke evidence file) when the workflow needs a diff target.
- **Tests-pass and no-diagnostics are implicit** — every task must end with those. Do NOT add them as DoD bullets; only list task-specific behaviors.
- **The last DoD bullet IS the verify command.** No separate `Verify:` block.
- **`Trivial:` is a per-task annotation, not a section** — the changes review and `spec-verify` Step 2.1 audit it against the diff regardless of where it sits, as long as it's the literal token `Trivial:` somewhere in the task body.
- **Key Decisions: aim for ≤5 bullets per task.** Prefer `file:line` refs over prose. Multi-paragraph explanations belong in a comment in the code, not in the plan — the plan should point the implementer at WHERE to look and WHAT pattern to follow, not re-explain the existing system.
- **Never restate a `## Global Constraints` value in a task.** Every task already inherits that section; copying a version floor or required format into `Key Decisions` creates a second place to update it. Reference it instead.

#### Test plan parsimony

**Testing posture.** Follow repository requirements and choose coverage for the changed behavior and risk. Resolve routine choices about test placement and layers without a user round-trip.

When listing files for a task, do not auto-create a new `tests/.../test_<file>.py` line for every modified production file. Apply these rules in order:

1. Reuse existing behavioral tests when they cover the relevant contract; extend them where coverage is missing.
2. For a low-risk change already covered by an existing check, use the optional `Trivial:` field to record that evidence and omit unnecessary new test files.
3. Add tests for distinct behavior, regressions, or integration boundaries. Follow the project's test organization without imposing a class-count quota.
4. Avoid tests that merely mirror implementation structure or duplicate another layer's assertion without exercising a different failure mode.

The changes review and `spec-verify` Step 2 audit whether the chosen evidence covers the actual diff, including any `Trivial:` justification.

**Performance considerations:** When a task processes data on a hot path (render loops, request handlers, polling callbacks), note it in Key Decisions. Flag: expensive computations that should be cached/memoized, heavy dependencies that have lighter alternatives, and repeated work that can be avoided when input hasn't changed.

**Zero-context assumption:** Assume implementer knows nothing. Provide exact file paths, explain domain concepts, reference similar patterns.

**Assumptions (conditional):** Only write a `## Assumptions` section when an assumption — if wrong — would silently invalidate a task. One bullet per real assumption: what you assume + which task numbers depend on it. Omit the section when there are none; do NOT include tautological assumptions ("config.json is the authoritative store") just to fill space.

#### Step 7.2: Goal Verification Criteria (skip step if no cross-task observable outcomes exist)

After creating tasks — and considering the E2E scenarios you will write in Step 8 (revisit this decision after Step 8 if needed) — ask: **is there a user-facing observable outcome that NO single E2E scenario captures AND NO single task DoD captures?** If no → skip this step entirely; the `## Goal Verification` section does not appear in the plan. spec-verify then audits via the E2E and task-DoD source keys instead (spec-verify Steps 2/6/7).

If yes → write **at most 3 truths** for the `## Goal Verification > ### Truths` section. Each truth must be cross-task and not reducible to a single TS-NNN or task DoD reference. If you find yourself writing `[behavior] — TS-NNN passes`, that's not a truth — it's a redirect; delete it and rely on TS-NNN itself.

Do NOT list "supporting artifacts" — they duplicate the per-task `Files:` blocks. Do NOT paraphrase task titles as truths — the task list is the in-scope inventory.

#### Step 7.3: Completeness Probe

Review failure modes relevant to the change, especially security, authentication, data integrity, cancellation, and destructive operations. Reuse cases already covered by task DoD and E2E scenarios rather than adding duplicate truths.

Before locking the truth list, work backward from the success state to find missing observable behaviors. For the chosen approach, walk these four prompts once:

1. **What could prevent the success state?** For each prerequisite the success path assumes, is there a truth covering what the system does when the prerequisite fails (missing input, invalid input, conflicting state, expired credential, rate-limit exceeded, downstream dependency unavailable, concurrent modification)?
2. **What are the cancellation / abort paths?** If the user can initiate the success path, can they cancel mid-flight? Is the observable state after cancel specified?
3. **What are the boundary inputs?** Empty, zero, negative, max length, unicode, whitespace-only, duplicate, exactly-at-limit.
4. **What are the concurrency edges?** If two callers exercise the path simultaneously, is the observable outcome specified, or is implicit serialization being assumed?

For a relevant gap, add a task criterion, E2E scenario, or cross-task truth at the appropriate level. Do not manufacture requirements for impossible paths or exclude a requested behavior merely to close the checklist. Record actual boundary decisions under `## Out of Scope`.
