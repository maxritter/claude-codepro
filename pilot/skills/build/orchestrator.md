---
name: build
description: "Builds toward a named goal without writing a spec first — the goal-and-loop workflow with judged acceptance criteria. Runs only when the user explicitly types /build. Not for a defect in behaviour that already worked — that is /fix. Not when the approach has to be written down and agreed before any code exists — that is /spec."
argument-hint: "<what to build, and optionally what it should measure up to>"
user-invocable: true
hooks:
  Stop:
    - command: uv run --no-project --python python3 python "$HOME/.pilot/hooks/spec_plan_validator.py" docs/builds Buildout
---

# /build — Goal-and-Loop Development

The path for **"make this, and make it good"** when there is no spec and you do not want one. You name the end state; `/build` turns it into a short task list plus a handful of acceptance criteria, builds the tasks, then judges the result against those criteria. What the tasks actually are is allowed to change as the work teaches you something — that flexibility is the point.

**It runs autonomously from the goal to the hand-back.** The goal *is* the directive: once it is clear enough to build against, start and keep going until every criterion passes. There is no approval gate, no round-budget check-in, and no sign-off at the end.

Clarify a material uncertainty about the intended outcome before writing its criteria. A clear goal needs no question. After that, continue autonomously; pause only for user steering, a genuine missing decision, or an operation outside existing authorization.

**Autonomy raises the evidence bar; it does not lower it.** Nobody inspects this work before it is called done, so `VERIFIED` is earned only by what the Buildout can show: every criterion ticked against evidence a judge pointed at, and every verification layer either evidenced or explicitly disclosed as not run (Step 6.10). A criterion that will not close is reported unresolved — it is never quietly relaxed, and no round is ever skipped to reach a tidier ending.

```bash
> /build "landing page for my running brand — should feel as alive as Nike's"
> /build "port the admin screens to React, better than what we have, not just ported"
> /build "2000-word explainer on vector databases for non-engineers"
```

`/build` and `/spec` are **peers, not tiers**. Neither is the escalation path for the other.

| The request | Command |
|---|---|
| Something that already worked is broken | `/fix` |
| The approach should be written down and approved before any code | `/spec` |
| The idea is still vague about who it serves or what done means | `/prd` |
| A clear goal, and the approach can be found while building | **`/build`** |

Size is **not** the discriminator. A 30-screen migration can be `/build`; a 40-line change can be `/build`; a small feature whose execution order matters can be `/spec`. Pick on **what the work is measured against**: an approved task list (`/spec`) or a defined end state (`/build`).

---

## The shape of a run

```
Goal → Draft tasks + criteria → Round(build every task → judge) → Verify → Hand back
```

Three things carry it:

1. **The goal** — one sentence naming the end state.
2. **The tasks** — 3–7 of them, a title and an objective each, expected to change as you learn.
3. **The judge** — a separate pass at the end of each round that rules the acceptance criteria from the finished artifact.

A **round** is one full pass over the task list plus **one** judge pass. Criteria that fail become the next round's tasks. Most runs converge in two or three rounds.

Once the rounds are done, **Step 6 verifies** what the criteria do not cover and **Step 7 hands back** — a report, not a gate. `VERIFIED` is earned by evidence in the file, never by a sign-off.

---

## Rules that keep it converging

```
0. NO ORACLE, NO BUILD. One criterion is the observable that proves the user's
   outcome is actually true. Every other criterion can pass while it fails —
   that is the run building the wrong thing well. It is never relaxed, never
   waived, and never ruled from a proxy.
1. TASKS ARE THE UNIT OF WORK. Criteria are judged at the end of a round, not
   worked one at a time. A criterion is never "the current gap".
2. CRITERIA BEFORE BUILDING. Criteria written after a draft describe that draft.
3. JUDGE ONLY WHEN EVERY TASK IS TICKED. Judging a half-built artifact spends a
   round to learn what you already knew.
4. PASS/FAIL, NEVER A SCORE. Scores drift upward every round; pass/fail does not.
   "Partial" and "mostly" are scores. Not fully met is fail.
5. CALIBRATED, NOT BRUTAL. Pass a criterion whose evidence meets what it asks.
   Raising the bar mid-judge is what makes this slower than /spec for no gain.
6. NO EVIDENCE YOU CAN POINT AT RIGHT NOW IS A FAIL. Not a pass on the balance of
   probability, not "it must work by now". Insufficient evidence is a failing
   criterion, and its gap is next round's tasks.
7. FOUR JUDGE PASSES IS THE CEILING, AND NOBODY IS ASKED FOR MORE. Rounds 1-3
   turn failures into tasks; round 4 is the automatic one-time extension; a fifth
   never happens. What will not close is reported unresolved, never lowered.
8. WAITING IS NOT A ROUND. Work blocked on something that will not finish inside
   this session ends the run — it does not spend rounds. Context pressure is not
   such a blocker: the Buildout survives compaction, so re-read it and continue.
9. HAND-BACK HAS FOUR DOORS. Every criterion passed, the round ceiling reached
   after a real judge pass, a named external blocker, or a criterion proven
   unachievable in this session. Nothing else is one.
```

---

## What Pilot adds

`/build` is not a conversation that remembers a goal. The goal, tasks, and criteria are a **file**, registered with the session, and the loop is held open by Pilot's stop guard.

- **Buildout file** at `docs/builds/YYYY-MM-DD-<slug>.md` with `Type: Build` — its own directory, next to `/spec`'s `docs/plans/` and `/prd`'s `docs/prd/`. It survives compaction, shows up in the Console's **Buildouts** section, and can be shared and annotated like any other Pilot plan — annotations are picked up at the start of every round, so the file stays the way to steer a run without stopping it.
- **Two reviewers, outside the loop, switchable** in Console → Settings → Workflows: **Build Review** on the criteria before round one, **Changes Review** on the diff at the end. Each has an optional Codex companion.
- **A verification pass** (Step 6) before hand-back — suite, types, lint, build, live-target E2E, the code review, doc sync, regression — scaled to the artifact, so a prose build pays almost nothing. Its nine layers (6.10) are what `VERIFIED` is measured against: each is either evidenced in the file or disclosed as not run. **Switch the pass off and the run does not reach `VERIFIED`** — it hands back `COMPLETE` and says nothing checked the code.
- **The statusline tracks tasks and rounds** — `Build: <name> build ▓▓▓░░ 3/5 r2`.
- **The stop guard holds the loop open.** While the Buildout is registered and not `VERIFIED`, the session cannot quietly end at "good enough". You do **not** need `/goal` — Pilot's Stop hook is the same mechanism, on both Claude Code and Codex, with the acceptance criteria as its condition and the judge pass as its evaluator. The user's escape hatch is stopping twice within 60s.
- **`Status:` is the same closed set** as every other Pilot plan — `PENDING` → `COMPLETE` → `VERIFIED`, bare keyword, no trailing prose.

| Buildout state | Statusline phase | What it means |
|---|---|---|
| `PENDING` + `Approved: No` | `goal` | Goal, tasks, and criteria being drafted |
| `PENDING` + `Approved: Yes` | `build` | Contract locked, working the task list |
| `COMPLETE` | `judge` | Every task ticked; judge pass and verification outstanding |
| `VERIFIED` | *(cleared)* | Every criterion passed on evidence, and Step 6 recorded it |

`Approved: Yes` on a Buildout means **the contract is locked and the loop is live** — Step 3 writes it itself the moment the criteria stop moving. It is not a record of anyone signing off, and nothing in this workflow waits for one.

A hand-back does not always mean `VERIFIED`: a run that stops at the round-four ceiling with criteria unresolved, one blocked on something outside the session, and one that proved a criterion unachievable all stay `PENDING` so they can be resumed from the file. A one-shot sentinel lets the session stop in those cases.

---

## Autonomy and user steering

Step 1.5 resolves material uncertainty about the outcome. It does not require questions for phrases such as "make it good" when the request and workspace already establish what good means.

Once the contract is locked, build, judge, and verify without routine approval or round-budget check-ins. `PILOT_PLAN_APPROVAL_ENABLED` does not apply to this workflow. Existing permissions still govern deployment, messaging, data changes, and other external actions.

Use a reasonable stated default for an unanswered optional preference. Required input or authorization remains pending; a timeout is not an answer.

Answer user questions and incorporate corrections while preserving the original objective. A status request does not cancel the run. An explicit stop, pause, or cancellation does: interrupt this session's active work and preserve the Buildout accurately. The stop guard does not authorize ignoring the user.

If the guard blocks a premature agent stop while work is available, re-read the Buildout and take the next build, judge, or verification action. Context pressure is handled by saved state and compaction.

### Keep the contract intact

- Draft tasks and criteria before implementation.
- Complete every open task before the round's judge pass.
- Judge each criterion pass/fail from the evidence it names.
- Preserve requested scope; do not drop a requirement to fit a task count, call budget, or session estimate.
- A criterion missing evidence stays unresolved. Record genuine blockers and the hand-back reason instead of weakening the criterion.
- Keep `## Changed Files`, task checkboxes, and `## Round Log` current.
- Use Step 7's evidence gate before writing `VERIFIED`.


## When NOT to use

- **A defect in behaviour that already worked** → `/fix`.
- **The approach has to be written down and agreed before any code** → `/spec`. Size alone is not the trigger.
- **The idea is still vague about who it serves or what done means** → `/prd` first, then `/build` or `/spec`.
- Ordinary small edits without an explicit `/build` invocation do not need this workflow. If the user explicitly invokes `/build`, honor that choice and keep the Buildout proportional.
- **The result cannot be judged without data that will not arrive during this session** → say so and build it straight, or come back when the data lands.
