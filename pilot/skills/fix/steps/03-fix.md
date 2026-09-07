## Step 3: Fix at the Root Cause

### 3.1 Make the minimal change

Edit only the file(s) at the root cause. One logical fix. No "while I'm here" cleanups, no bundled refactoring, no formatting passes. **Lineage rule:** every changed line traces directly to the bug.

Multi-site is fine when the causal chain requires it. Keep each change tied to the same reported defect, even when different boundaries need different logic.

### 3.2 Forbidden patterns — fix at source, not symptom

If the buggy data flows from upstream, fix upstream. Red flags in the diff:

- Broad new `try/except` around the failing call.
- `if value is None: return default` at the caller when the bug is that `value` is wrong upstream.
- Swallowed exceptions, silently normalised bad inputs.
- Early return that hides wrong state from the caller.
- Renamed/suppressed log lines that previously surfaced the bug.

When required boundaries need divergent logic, state the causal role of each site, implement the smallest coherent repair across them, and add coverage for both the local contracts and their integration. Exclude unrelated defects and opportunistic cleanup.

### 3.3 Run the reproducing test — it MUST pass

```bash
<same single-test command from Step 2.3>
```

If it doesn't pass: stop adding more code. Revert your edit. Return to Step 1.3 — your root cause hypothesis was wrong.

### 3.4 Run the targeted scope (NOT full suite)

Run the test module(s) covering the file you just changed. Fast, scoped:

```bash
# Python example
uv run pytest <path/to/test_module.py> -q
# TypeScript example
bun test <path/to/test-file.test.ts>
```

Zero failures. The full anti-regression suite runs once at Step 5; during investigation, rerun only the scopes that can confirm or falsify the current hypothesis.

### 3.5 Diff sanity

```bash
git diff --name-only
git diff | grep -E "^\+.*(SPEC-DEBUG|\b(try:|except|catch \(|return None|return \[\]|return \{\}|console\.log|console\.error|print\())"
```

- **Root-cause file IS in the diff.** If not, the fix is at a symptom — return to 3.1.
- **Every fix-owned change has a causal role.** Remove only unrelated edits this workflow introduced; preserve pre-existing and concurrent changes, even in the same files.
- **Diff is no larger than the repair requires.** Audit every file and hunk against the causal chain. Remove unrelated cleanup, but do not treat file count or line count as a workflow ceiling.
- **Every grep match must be justified or reverted.** Look for symptom-patching, swallowed returns, or leftover `print` / `console.log` / `SPEC-DEBUG:` markers.

### 3.6 If an attempted fix doesn't work

If Step 3.3 fails, revert the unsupported production edit, re-run the original reproduction, and return to Step 1.3 with the new evidence. Challenge the root-cause statement before trying another repair. Continue until the reproducing test and original user-level symptom both pass, or a genuine external blocker requires user action.
