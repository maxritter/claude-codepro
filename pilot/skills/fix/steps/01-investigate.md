## Step 1: Investigate Root Cause

**Goal:** trace the bug to `file:lineN — function() does X but should do Y` with High or Medium confidence. If confidence is still Low, deepen the investigation before changing production code.

### 1.1 Reproduce & understand

- Restate **symptom**, **trigger**, **expected behaviour**.
- **Runnable reproduction? Run it early after confirming the command is safe and the required setup is understood.** For a named test, CI failure, or crashing command, the actual output is usually the strongest starting evidence. Inspect configuration or source first when needed to avoid unintended side effects. Capture relevant output:

  **Derive `<fix-slug>` first** — kebab-case the bug description, ~40 chars, the same shape `/spec` uses for a plan filename. Every session artifact this run writes carries it, and you must be able to reconstruct it in a later Bash call from the bug description alone, so keep it deterministic. **Running as an orchestration lane** (`--lane <id>` — Step 6.2)? Use `$SESS_DIR/lanes/<lane>` as `RUN_DIR` instead; the lane id is already unique, so it does the namespacing on its own.

  ```bash
  RUN_DIR="$HOME/.pilot/sessions/${CLAUDE_CODE_SESSION_ID:-${CODEX_THREAD_ID:-${PILOT_SESSION_ID:-default}}}"   # + /lanes/<lane> on a lane run
  REPRO_LOG="$RUN_DIR/fix-repro-<fix-slug>.log"; mkdir -p "$(dirname "$REPRO_LOG")"
  set -o pipefail; <repro command> 2>&1 | tee "$REPRO_LOG"
  ```

  (`pipefail` keeps the test's failing exit status visible through the pipe — without it, `tee` reports exit 0 and a failing run looks like a pass.)

  ⛔ **Never a fixed filename here.** `$SESS_DIR` resolves identically for a coordinating session and every subagent lane it dispatches, so `fix-repro.log` would be one file shared by every concurrent `/fix` (issue #173).

- **Read the COMPLETE output, not just the failing assertion.** Warning lines, stderr, "exception caught/swallowed/ignored" notices, and log output *above* the failure frequently name the root cause directly — one warning line read here can replace the entire tracing phase. Skim the whole capture, then sweep it as a completeness check:

  ```bash
  grep -niE "warn|error|exception|traceback|ignored|swallowed" "$REPRO_LOG"   # reconstruct it as above if this is a new Bash call
  ```

- **CI-only failure?** Still run the test locally first. A local pass against a CI fail is itself a finding (environment or mocking drift), and the local output is your baseline either way.
- **Multi-factor repro? Minimise first** (Systematic Debugging step 1) — the minimal repro becomes the Step 2 test.
- If the description is too vague to reproduce: one focused `AskUserQuestion` (only when `PILOT_PLAN_QUESTIONS_ENABLED` is not `"false"`).
- If you still cannot trigger it after two well-chosen attempts because inputs, steps, or data are missing, ask one focused question for the missing reproduction detail. Continue safe diagnostics with the evidence already available while waiting when useful; do not turn missing detail into a workflow redirect. A reproduction blocked by the *environment* follows the blocker protocol below.

**Environment blocker protocol — involve the user, NEVER speculate around it.** When the reproduction cannot run because the environment blocks it — expired cloud auth (`gcloud` / `aws` / `az`), dependencies behind a private registry, a credential or service only the user has:

1. Make at most ONE quick attempt at a workaround (an already-provisioned `.venv` / `.tox`, a cached environment). One. Not a research project.
2. Then STOP and ask the user to unblock — name the exact blocker and the exact unblock command (e.g. "dependency install needs Google Artifact Registry auth — run `gcloud auth application-default login`"). Ask via `AskUserQuestion` with two options: **"Unblocked — re-run the repro"** and **"Continue without running (static investigation, degraded confidence)"**.
3. This question is **exempt from the `PILOT_PLAN_QUESTIONS_ENABLED` toggle** — a blocked reproduction is a hard stop, not a planning preference.
<!-- CC-ONLY -->
4. For interactive logins, tell the user they can type `! <command>` (e.g. `! gcloud auth application-default login`) to run it inline in this session so the output lands in the conversation.
<!-- /CC-ONLY -->
<!-- CODEX-START
4. For interactive logins, ask the user to run the command in a separate terminal and reply here when it's done.
CODEX-END -->
5. Once unblocked, re-run the reproduction and continue from the top of 1.1.

⛔ Forbidden moves when the repro is blocked:

- "I might not need to run the test at all" — you do. The run's output is primary evidence; this exact rationalization is the documented derail the protocol exists to prevent.
- Pivoting to recent diffs or unrelated code as a *substitute* for the run. (Reading code while you WAIT for the user is fine; concluding from it without ever running is not.)
- Silently choosing the degraded static path. Only the USER may choose it, and if they do, the Step 6 report must state that the reproduction was never executed.

### 1.2 Recent changes (one bash call, then move on)

```bash
git log --oneline -10 -- <suspected_file_or_dir> 2>/dev/null
```

Look for the commit that introduced the bug. If recent, read that diff. If nothing obvious, skip.

**Bisect when it materially narrows the cause.** With known-good and known-bad states and a deterministic reproduction, use `git bisect` in an isolated temporary checkout. Preserve the active worktree, branches, and concurrent changes; do not run a history-changing investigation in the user's dirty checkout.

### 1.3 Trace to root cause

<!-- CC-ONLY -->
Read named locations directly. Use `codegraph_explore(query="<bug description>")` for unresolved runtime structure and Semble for unknown intent or cross-cutting mutation sites; do not repeat a graph and text search when the source already answers the question.
<!-- /CC-ONLY -->
<!-- CODEX-START
**Use `codegraph_explore` only when the bug is structural or the entry point is unclear.** For docs, rules, markdown, config, UI copy, or a named local file/function, start with targeted reads or Semble. If the user names a concrete path or the symptom points to one file, read that file first and add CodeGraph only if the call path becomes the actual question.
CODEX-END -->

For local bugs (single file, single function): one or two targeted `Read`s is enough. **Do not** run `codegraph_explore` for callers/callees/impact on local bugs — that's the full-lane bias and it's the single biggest time sink for trivial fixes.

For bugs that span 2 files in the same component (e.g. service.ts + service.test.ts): targeted `Read`s. Still no full call-graph traversal.

**Persistence check at end of 1.3:** if you cannot yet pin the root cause to `file:line`, expand the trace, add instrumentation, minimize the reproduction further, or inspect the next boundary in the causal chain. Do not move to production changes until the evidence supports a root cause.

### 1.4 Instrument when needed (UI / async / race / timing bugs)

For bugs that don't surface clearly through stack traces or static reading — UI rendering glitches, async timing, race conditions, integration-layer issues — add **temporary diagnostic logging** to the production code and trigger the bug to read the output:

- Log input values entering the suspect function.
- Log branch conditions (which path executed?).
- Log computed intermediate results.
- Log return values at layer boundaries.

**Mark every temporary log with `SPEC-DEBUG:`** (e.g. `console.log("SPEC-DEBUG: filters=", filters)`). Step 3.5 greps for this marker — any unremoved match fails the diff sanity check.

**Unknown caller?** If the bug is in shared code reached from many sites and you don't know which caller triggers it, capture the call chain inline:

```js
// SPEC-DEBUG: who is calling this with bad input?
console.error("SPEC-DEBUG:", { args, stack: new Error().stack });
```

Run, read the stack, identify the offending caller, then trace upward to the original trigger.

**Performance regressions are different.** Value-logging is the wrong tool — replace it with baseline measurement: timing harness, `performance.now()`, profiler, or query plan / `EXPLAIN`. Establish current vs expected timing first, then bisect against that signal (Step 1.2). Measure first, fix second.

Skip 1.4 when the stack trace already names the failing line, or when a static read of the file is enough to see the bug. Skip is the default.

### 1.5 State the root cause

Out loud, in one sentence to the user, before writing any test:

> "Root cause: `<file>:<line>` — `<function>()` does <X>, should do <Y>. This causes the symptom because <reason>. Confidence: <High|Medium>."

If confidence is Low: keep investigating. Do not guess, patch the symptom, or redirect the workflow.

### 1.6 Lock in a fast signal before Step 2

Your reproducing signal — what runs in <30s and definitively shows fail/pass — must be **fast and deterministic** before you write the fix. For most bugs that's the unit test you're about to write in Step 2. For UI / integration / async bugs the unit-test seam may be wrong, and your real signal is a `curl`, CLI invocation, or headless-browser command (the same one you'll run in Step 4 E2E).

Whichever it is, sharpen it now:

- **Slow loop (>30s)?** Narrow the test scope, skip unrelated setup, cache fixtures. A flaky 30s loop is the slowest path to a fix.
- **Flaky?** Pin time, seed RNG, isolate filesystem, freeze network. For non-deterministic bugs, raise the reproduction rate (loop the trigger 50–100×, parallelise) until it's debuggable — a 1% flake is not.
- **Wrong symptom?** The signal must fail with the **user's** reported symptom, not a different failure that happens to be nearby. Wrong bug = wrong fix.

If the signal cannot be made fast and deterministic after one pass, use the narrowest reliable integration or end-to-end reproduction as the working signal. Increase observability and repetition where needed; do not hypothesise into a flaky loop or redirect the workflow.

### User signal you're off track

If the user says "stop guessing", "is that not happening?", or "ultrathink this", they are telling you a hypothesis got treated as a finding. Return to 1.3 and trace.
