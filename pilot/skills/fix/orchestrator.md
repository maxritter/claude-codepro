---
name: fix
description: "Structured bugfix workflow — diagnoses and repairs a reported defect at its root cause, scales across every required component, and proves the result end to end. Runs when the user explicitly types /fix."
argument-hint: "<bug description>"
user-invocable: true
---

# /fix — Bugfix Workflow

Bugfix with TDD: investigate the bug, write the failing test, fix at the root cause, verify end-to-end, done. No plan file, no mid-flow approval gate, no separate verify phase.

```bash
> /fix "annotation persistence drops fields between save and reload"
> /fix "off-by-one in pagination at boundary"
> /fix "wrong default for max_retries"
```

**Own the defect end to end.** Scope, file count, UI impact, and architectural breadth change how the work is organized; they never change which workflow owns it. `/fix` continues through investigation, implementation, review, and proof until the reported defect is resolved or a genuine external blocker requires the user.

**Unexpected classification.** If investigation shows the reported defect is actually a quality gap or missing behavior, state that finding and continue toward the concrete requested end state when it is safely inferable. Ask only when the different classification creates a material product decision; never stop merely to redirect the user to another workflow.

---

## Iron Laws

```
1. NO FIXES WITHOUT ROOT CAUSE — traced to file:line, explained WHY.
2. RUN THE REPRO BEFORE THEORIZING — execute the reproduction FIRST and read its
   COMPLETE output: warnings, stderr, and log lines above the failure, not just
   the assertion. If the environment blocks the run, ask the user to unblock it.
3. NO CODE WITHOUT A FAILING REPRODUCING TEST — TDD.
4. FIX AT THE SOURCE — not where the error appears.
5. END-TO-END VERIFICATION IS MANDATORY — Step 4 runs the actual program and
   captures concrete evidence. Unit tests alone are never accepted as proof.
6. STAY WITH THE DEFECT — complexity changes execution strategy, never workflow ownership.
```

Three failure modes are common enough to name, because each one *feels* reasonable in the moment:

| Tempting move | Why it fails |
|--------------|--------------|
| "I can find it by reading the code — no need to run the test" | The failing run's output (warnings, stderr, swallowed-exception notices) often names the root cause outright. Running it first is faster than tracing. |
| "The repro can't run here, I'll reason it out instead" | An environment blocker is a user-involvement point, not a licence to speculate. Ask for the unblock, then run (Step 1.1). |
| "This is larger than expected, so another workflow should own it" | The user already chose `/fix`. Expand the trace, decompose the work, and keep going without a workflow handoff. |

---

## Critical Constraints

- **No tracked spec plan file.** Preserve the current cause, evidence, changed files, active process handles, and next action in the conversation or session notes before compaction, then resume.
- **`/fix` owns its isolation.** It parses the same branch flags `/spec` does, creates the worktree, and owns the merge-back — see *Branch & Lane Setup* below. Where Steps 2/6 branch on "worktree mode", that branch applies whenever a worktree is active, whether `/fix` created it or the session was already inside one.
> **`$LANE_FLAG`** is `--lane <id>` when this run was dispatched as an orchestration lane, and **nothing at all** otherwise — the value the invocation parsed from its arguments. It keeps worktree and plan identity scoped to this lane; an unflagged call resolves a different identity and silently finds nothing (issue #174).

- **Detect a worktree with `pilot worktree detect --json <fix-slug> $LANE_FLAG`, never a path glob.** The old `.worktrees/spec-*` test keyed `/fix`'s isolation to a directory prefix another workflow produces; the resolver answers the same question without depending on the naming.
- **No artificial attempt or size ceiling.** A failed approach is evidence: revert the speculative edit, update the causal model, strengthen the reproducing signal, and continue. Do not accumulate patches that are not supported by the latest evidence.
- **No approval mid-flow.** A single end-of-flow confirmation, and only when `PILOT_PLAN_APPROVAL_ENABLED` is enabled. It sits at 6.2, **ahead of** the commit and merge at 6.3 — one gate, placed in front of the step that cannot be undone. Do not add a second gate for the merge; move nothing behind it.
- **Complex fixes stay in `/fix`.** Use a concise native plan, bounded subagents, additional regression seams, or broader verification when they materially help, while keeping every change traceable to the reported defect.
<!-- CC-ONLY -->
- **Use `AskUserQuestion` for user questions** — it renders a structured form; use a concise prose question when no permitted structured tool is available.
<!-- /CC-ONLY -->
<!-- CODEX-START
- **Use the runtime's structured user-input tool when available and permitted for this question**; otherwise ask a concise question in prose and wait for required input
- **Browser tools for E2E verification:** Use the browser or app tools exposed in this runtime, following the project's browser-automation rules. Do not infer tool availability from the agent name.
- **The Codex plugin companion review is not available** — its broker is Claude-Code-only. The native `changes-review` custom agent still runs in Step 6.1 when the Changes Review toggle is enabled.
CODEX-END -->

---

## Persistence and Genuine Blockers

`/fix` never redirects because the defect is multi-component, architectural, UI-heavy, difficult to reproduce, larger than expected, or still unresolved after an attempted repair. Those conditions call for deeper investigation or broader execution inside this workflow:

- **Low confidence:** keep tracing, instrumenting, minimizing, and cross-checking until the root cause is supported. Do not write speculative production code.
- **Several components or divergent logic:** decompose the causal chain into bounded work items, fix each required boundary, and verify their integration.
- **Architecture or new abstractions:** make the smallest coherent structural change that removes the root cause, with tests at the old failure boundary and the new contract.
- **Non-trivial UI implications:** record the interaction states and verify the complete user flow in the real browser or installed app.
- **Repeated failed attempts:** revert unsupported edits, re-run the original reproduction, challenge the hypothesis, and continue from the new evidence.
- **Large diff:** audit lineage by file and hunk; remove unrelated cleanup, but do not impose a line-count ceiling on a necessary repair.

Pause only for a genuine blocker that cannot be resolved inside the workspace: missing user-only information, credentials or authorization, an unavailable external system, or a product decision whose alternatives materially change the result. State the exact blocker and required user action, then resume `/fix` when it is cleared. Never recommend another Pilot workflow as the unblock path.

---

---

## Branch & Lane Setup (before Step 1)

**Parse the flags** off the argument string, then strip them from the bug description: `--worktree=yes|no`, `--new-branch`, `--lane <id>`. Default is `--worktree=no` — work continues on the current branch, exactly as before.

**Derive `<fix-slug>`** from the bug description: kebab-case, ~40 chars. It names the worktree, the branch, and every session artifact this run writes (Steps 1.1 and 6.1), so derive it once and reconstruct it the same way every time.

**Ask about branch isolation only when `PILOT_BRANCH_ISOLATION_ENABLED` is `"true"`** and the user supplied no flag — the same three options `/spec` offers, in the same order:

| Option | Flag | Behaviour |
|---|---|---|
| **Continue on current branch** (recommended) | `--worktree=no` | Works on the current branch as-is |
| New branch from default branch | `--new-branch` | Branches `fix/<fix-slug>` off `origin/<default>`, carrying your uncommitted work |
| Use worktree (isolated, squash-merged after) | `--worktree=yes` | Isolated checkout, merged back at Step 6.3, after the 6.2 approval gate |

When the toggle is `"false"`, ask nothing and use `--worktree=no`.

**For `--new-branch` or `--worktree=yes`,** read `$HOME/.pilot/agents/spec-branch-setup.md` and follow it with `<plan_slug>` = `<fix-slug>`, prefix `fix/`, and `<lane>` when one was supplied. Everything after this — the reproducing test included — is written inside the resulting checkout.

⛔ **`--lane <id>` implies `--worktree=yes` and fails closed.** Reject `--lane` combined with `--worktree=no` or `--new-branch`, and abort rather than continuing if the worktree cannot be created. A lane that quietly lands in the coordinator's checkout races every sibling's edits.

**`$LANE_FLAG`** stands for `--lane <id>` on a lane run and for **nothing at all** otherwise. **Every** `pilot worktree` call in this workflow carries it — `create`, `detect`, `diff`, `sync`, `cleanup` alike. The worktree directory and branch are keyed on `(slug, lane)`, so an unflagged `sync` resolves `spec/<slug>` rather than the `spec/<slug>-<lane>` the flagged `create` made, reports "not found", and the lane's finished work is stranded in an orphaned worktree that never reaches the base branch. Substitute it literally at each call site; shell state does not survive between Bash calls.

Probe once before the first flagged call and **abort if the binary predates the flag**, rather than dropping to an unflagged call that shares the coordinator's checkout:

```bash
~/.pilot/bin/pilot worktree create --help 2>&1 | grep -q -- --lane && echo LANE_OK || echo LANE_UNSUPPORTED
```

`/fix` registers no plan, so `register-plan` never appears here — the lane flag matters only for the worktree calls.

---

## Workflow — Six Steps, No Ceremony

Investigate → RED → Fix → Verify E2E → Quality → Finalise.
