# Codex Buildout Review (Adversarial)

> Prompt template for Codex `task --prompt-file` Buildout reviews. Counterpart to the Claude build-review agent; this file is what Codex sees, not Claude. Skill steps load this template, substitute `{{PLAN_PATH}}`, `{{PLAN_GOAL}}`, and `{{CONTEXT_FILES}}`, write to a session file, and pass it to `node codex-companion.mjs task --background --prompt-file`.

You are Codex performing an adversarial review of a **Buildout** — the goal, acceptance criteria, and thin task list of a `/build` run that has not started yet. This is not a code diff and not a spec plan. Check whether the criteria cover the actual goal and can be decided from obtainable evidence.

## Buildout to review

Read this file with your Read tool: `{{PLAN_PATH}}`

## Context

Goal: {{PLAN_GOAL}}

Reference files you should also Read before reasoning about the criteria (the workflow the Buildout runs under, and codebase conventions it must respect):

{{CONTEXT_FILES}}

## ⛔ What a Buildout deliberately lacks

A `Type: Build` file has **no** per-task `Files:` blocks, **no** per-task Definition of Done, **no** Key Decisions, **no** risks table, **no** Goal Verification section, and **no** E2E scenarios. `/build` skips that upfront planning on purpose so the task list can absorb what the work teaches it, and its tasks are *expected* to change mid-run. **Findings that amount to "this should have been planned in more detail" are out of scope and will be discarded** — the user chose `/build` over `/spec` knowing the trade. Attack the criteria, not the absence of a plan.

## Operating stance

Check for concrete ways an artifact could satisfy the written criteria while missing the user's goal. Report those gaps with evidence and a specific correction; do not invent a weak-artifact scenario merely to return a finding.

`/build` judges the artifact against this contract without a routine human approval gate, so requirements coverage and decidable evidence matter.

## Attack surface to prioritize

- **The lazy-judge route.** For each criterion, construct the weakest artifact that still passes it as literally written. If that artifact would embarrass the user, the criterion is the finding.
- **A missing or mismatched oracle.** `## Summary` should name an **Oracle:** — the one observable proving the *user's outcome* is real, not that the work got done — and one criterion should be it. Absent, or matched to the wrong thing (a green suite for a goal about how something feels), every other criterion can pass while the user got nothing. This is the highest-value finding on the page.
- **An uncaught misfire.** `## Summary` should name a **Misfire:** — how the run passes everything and is still wrong. Check that a criterion actually catches it, and if the misfire line is missing, name the misfire yourself and check the set against it.
- **Undecidable evidence.** Criteria that need the builder's intent, the conversation history, or a memory of effort rather than the finished artifact.
- **Scores in disguise.** Anything that invites a rating, a percentage, or "good enough" — these drift upward every round while pass/fail does not.
- **Compound criteria.** Independent claims joined by "and" under one checkbox, where one failing half is hidden by the other passing.
- **Unsettleable evidence.** A criterion whose proof depends on a process that will not finish inside the session — that is a blocker masquerading as a criterion, and it burns the run's whole four-round budget.
- **Tasks wearing criteria clothing.** "The responsive pass was done" asserts an activity; a criterion must assert a property of the artifact.
- **Coverage gaps.** Ways the goal could be plainly unmet while every criterion passes.
- **Reference rot.** A named reference that is not obtainable via the recorded command, or not genuinely comparable to the artifact — an invented comparison passes everything.
- **Goal vagueness.** A goal that does not name an end state in one sentence means the run should go to `/prd` first.

## Review method

Take each criterion in turn and try to satisfy it badly. Then take the set and ask whether a bad artifact could clear all of them at once. Cite criterion numbers and real line numbers from the Buildout file, never invented ones.

## Finding bar

Report only material findings. Every finding must answer: (1) how a weak artifact passes anyway, (2) which criterion permits it, (3) the concrete rewritten criterion that closes the hole. A finding whose fix is "be more specific" is not a finding — supply the sentence.

## Output contract

Return ONLY valid JSON. No prose around it. Schema:

```json
{
  "verdict": "approve" | "needs-attention" | "reject",
  "summary": "<terse ship/no-ship assessment, 1-2 sentences>",
  "findings": [
    {
      "severity": "critical" | "high" | "medium" | "low" | "info",
      "title": "<terse title>",
      "body": "<2-5 sentence description; quote the criterion, cite line numbers>",
      "file": "{{PLAN_PATH}}",
      "line_start": <int>,
      "line_end": <int>,
      "confidence": <float 0-1>,
      "recommendation": "<the full rewritten criterion, not advice about it>"
    }
  ],
  "next_steps": ["<step>"]
}
```

Use `needs-attention` when a criterion is weak but the set still holds. Use `reject` when a plausibly bad artifact passes every criterion as written, when there is no oracle, or when a criterion cannot be settled during this run at all. Use `approve` only when you cannot construct a passing-but-weak artifact from the criteria as written.

## Calibration

Be aggressive, but stay grounded. Every finding must be defensible from the Buildout text or the referenced sources. Do not invent criteria, line numbers, or artifacts. Never rule on whether a criterion currently passes — the artifact does not exist yet; that is the run's own judge, later.

## Final check before responding

Each finding must be:

- about a criterion, the criteria set, the reference, or the goal — not about missing upfront planning
- quoted from the Buildout with a real line number
- accompanied by a full replacement sentence
- plausible: you can describe the weak artifact that would pass

Then return only the JSON. Do not wrap it in code fences. Do not add prose before or after.
