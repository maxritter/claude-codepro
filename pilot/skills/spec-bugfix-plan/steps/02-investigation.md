## Step 2: Root Cause Investigation

Establish a reproduction, causal trace, and supported fix strategy. Use the relevant checks below; skip redundant steps when existing evidence already settles them.

### Investigation efficiency

Use each reproduction or hypothesis test to distinguish a specific cause. When repeated attempts produce no new evidence, revisit assumptions, inspect the environment, and identify the missing signal. Ask the user when that signal cannot be obtained independently; attempt counts alone do not prove an architectural problem.

### 2.1 Reproduce & understand

- Restate **symptom** (what user observes), **trigger** (when/how), **expected behaviour**.
- Vague? One focused `AskUserQuestion`.
- Reliable repro? Steps?
- **If reproduction stalls because a signal is missing:** identify the exact command, input, environment, stack trace, or recording needed. Gather it independently where possible; otherwise ask using the current permitted question mechanism.
- **Multi-factor repro? Minimise first** (Systematic Debugging step 1 in `development-practices.md`): the minimal repro shrinks the Step 2.3 trace space and becomes the RED test in implementation.
- **Intermittent (flaky / race):** trigger 10+ times, record state at failure. Flaky bugs need a test that **forces** the race (deterministic ordering, frozen clock, blocked event loop), not one that hopes to hit it.

### 2.2 Recent changes

- `git log --oneline -10 -- <file>`, `git diff` for the obvious suspects.
- **A specific token appeared/disappeared?** `git log -S "<string>" -- <path>` (added/removed). Regex: `git log -G "<pattern>"`. Faster than bisect when correlated with a symbol.
- New deps, config changes, env differences?

### 2.3 Trace the root cause

<!-- CC-ONLY -->
Read a named bug location directly. Use `codegraph_explore(query="<bug description and symptoms>")` when runtime relationships or entry points are unknown, and Semble for unresolved intent or cross-cutting mutation sites. Reuse source already read.
<!-- /CC-ONLY -->
<!-- CODEX-START
Use `codegraph_explore(query="<bug description and symptoms>")` only when the bug location is not already named and the problem appears to involve runtime-code structure. Add one `mcp__semble__search` only when CodeGraph is weak or the bug is cross-cutting. If the user names concrete paths, docs, rules, markdown, config, UI copy, or the symptom points to a specific file, read that file instead of spending a graph call.
CODEX-END -->

<!-- CC-ONLY -->
**Deep dive when needed:** `codegraph_explore(query="<symbol names>")` for full source of a specific symbol (it accepts symbol names directly — no separate search step). Use `mcp__semble__find_related` from the bug site to discover parallel implementations that may share the same flaw.
<!-- /CC-ONLY -->
<!-- CODEX-START
Deep dive only when the root-cause candidate remains unclear after targeted reads. Use one focused `codegraph_explore`, `mcp__semble__find_related`, or exact-text search, then return to the root-cause statement.
CODEX-END -->

**Backward tracing (symptom → source):**

1. Find where the wrong behaviour appears — note `file:line`.
2. `codegraph_explore(query="<fn> callers")` traces what called this with the bad value/state.
3. Keep tracing until you find the **source** where the bad data originates.
4. **Fix at the source, not where the error appears.**

<!-- CC-ONLY -->
**Native plan mode:** production instrumentation and scratch diagnostic files are deferred until native exit; the only writable file is the runtime-permitted native draft. Use existing logs, read-only inspection, or non-mutating commands to trace boundaries. If fresh instrumentation is essential, document the missing signal and obtain the necessary native exit before running an isolated diagnostic; do not claim a verified root cause from missing evidence.
<!-- /CC-ONLY -->

**Multi-component systems — instrument at boundaries before concluding (only when the current mode permits those writes):**

```bash
# Layer 1: entry point
echo "=== enter handler — input: ==="
echo "$INPUT"

# Layer 2: business logic
echo "=== leave handler / enter service — payload: ==="
jq . <<< "$PAYLOAD"

# Layer 3: storage
echo "=== query result: ==="
psql -c "SELECT id, status FROM jobs WHERE id=$JOB_ID"
```

This reveals **which** layer breaks. Investigate that layer next — don't speculate across layers.

**⛔ Mark every temporary log/print with `SPEC-DEBUG:`** (e.g. `console.log("SPEC-DEBUG: filters=", filters)`, `# SPEC-DEBUG: print(x)`). Verification greps the diff for this marker — any match fails verification and forces cleanup. Only way temporary diagnostics are allowed in the fix diff.

**Structural tracing — proportional to bug scope.** For bugs spanning 2+ files, modules, or components, run `codegraph_explore(query="<root-cause fn> callers, callees, and impact")` — one call returns the call graph and blast radius. For local bugs (typo, off-by-one, wrong constant in one function, missing null check at one call site), the `codegraph_explore` orientation from above plus a targeted Read is enough — skip the full call-graph traversal.

<!-- CODEX-START
Codex override: skip callers/callees/impact for docs, rules, markdown, UI-copy, single-file parser, or single-file config bugs unless the call path itself is the suspected failure.
CODEX-END -->

Tools: CodeGraph, Semble (`semble search`/`semble find-related` or `mcp__semble__search`/`mcp__semble__find_related`), Read/Grep/Glob for exact patterns.

### 2.4 Pattern analysis

1. Find **working examples** — similar code in the codebase that works correctly.
2. Compare: what's different between working and broken?
3. List every difference — don't assume "that can't matter".

### 2.5 Root cause statement

**Trace inconclusive? Rank hypotheses before testing any** (Systematic Debugging step 3 in `development-practices.md`): when 2.3/2.4 did not conclusively pin the cause, list 2–3 ranked, specific, falsifiable hypotheses and test the top one first; the ranked list goes into the plan's `## Investigation` section.

State clearly:

- **Root cause:** `file/path.py:lineN` — `function_name()` does X but should do Y
- **Why:** WHY it causes the symptom (not just what is wrong)
- **Confidence:** High (traced fully) / Medium (strong hypothesis) / Low (needs more data)

Low confidence → gather more evidence. Don't guess.

**Escalation:** when hypotheses repeatedly fail without new evidence, revisit the causal model and identify what observation would distinguish the remaining possibilities. Ask for a missing signal only when it cannot be gathered safely from the workspace.
