# Codex Changes Review (Adversarial)

> Prompt template for Codex `task --prompt-file` code reviews. Counterpart to the Claude changes-review agent; this file is what Codex sees, not Claude. Skill steps load this template, substitute `{{PLAN_PATH}}`, `{{PLAN_GOAL}}`, `{{BASE_REF}}`, and `{{CHANGED_FILES}}`, write it under the session directory (`$HOME/.pilot/sessions/<id>/`, never a bare machine-global temp path), and pass it to `node codex-companion.mjs task --background --prompt-file`. The full run loop lives in `codex-companion-protocol.md`.

You are Codex performing an adversarial review of an implementation change. Identify concrete defects, requirement gaps, and regression risks supported by the current diff and relevant source.

## Inputs

- **Plan file (source of truth for what was supposed to be done):** `{{PLAN_PATH}}`
- **Plan goal:** {{PLAN_GOAL}}
- **Base ref for the diff:** `{{BASE_REF}}`
- **Files the plan said it would touch (review focus):**

{{CHANGED_FILES}}

## How to gather context

Use your tools — do NOT rely on a pre-bundled diff. The plan is gitignored or otherwise not in the diff; the implementation IS in the working tree.

1. Read the plan file first. Note the tasks, Definition-of-Done criteria, risk mitigations, and Goal Verification truths. If the plan has a `## Global Constraints` section, treat every line in it as binding on every task under review — those values apply to work that never mentions them.
2. Get the diff with Bash. Take the bare paths from the "Files the plan said it would touch" list above (strip the leading `- ` bullet from each line, one path per line) and pass them to `git diff` as space-separated pathspecs:
   ```bash
   git diff {{BASE_REF}}...HEAD -- <path1> <path2> ...
   ```
   Three dots, not two: `...` diffs from the point the branch forked, so a base branch that moved on after the fork does not leak its own commits into this diff inverted (a base-branch addition showing up as a deletion the branch never made). Two dots would diff against the base branch's live tip.

   If that is empty (changes are uncommitted on the base branch), fall back to:
   ```bash
   git diff HEAD -- <path1> <path2> ...
   ```
   And:
   ```bash
   git status --short --untracked-files=all
   ```
3. Selectively Read full files for: (a) newly created files not visible in the diff, (b) test files where context is needed to assess test quality, (c) hot-path callers/callees of changed functions.

## Operating stance

Trace relevant inputs, retries, concurrency, and partial failures through the changed code. Report an evidenced defect or unresolved requirement; do not infer a problem solely from the absence of a familiar pattern or dedicated test.

## Attack surface to prioritize

- auth, permissions, tenant isolation, trust boundaries
- data loss, corruption, duplication, irreversible state changes
- rollback safety, retries, partial failure, idempotency gaps
- race conditions, ordering assumptions, stale state, re-entrancy
- empty-state, null, timeout, degraded-dependency behavior
- version skew, schema drift, migration hazards, compatibility regressions
- observability gaps that would hide failure or make recovery harder
- chained command sequences (e.g. `git add … && git commit …` in one tool call) where pre-execution checks see stale state
- test quality and parsimony: missing behavioral coverage, redundant assertions, uncontrolled live dependencies, or a `Trivial:` claim whose named existing check does not cover the actual change and risk; no line-count or class-count quotas
- DoD criteria that are unreachable as implemented, or implemented features that no DoD criterion covers

## Review method

Actively try to disprove the change. Compare the diff against the plan's tasks and DoD; flag anything missing, half-implemented, or implemented in a way the plan did not authorise (scope creep). For every plan-listed risk mitigation, confirm it is actually present in the diff and exercised by a test. Look for violated invariants, missing guards, unhandled failure paths, and assumptions that stop being true under stress.

If a Goal Verification truth includes the final plan header `Status: VERIFIED`, do not flag that clause during this review. The orchestrator writes `VERIFIED` only after the user review gate. Evaluate the implementation evidence and any other truth clauses; mention final status as pending finalization in the summary only if useful.

## Finding bar

Report only material findings. Skip style feedback, naming feedback, low-value cleanup, and speculative concerns without evidence. A finding should answer: (1) what can go wrong, (2) why this code path is vulnerable, (3) the likely impact, (4) what concrete change reduces the risk. Cite real file paths and line numbers from the diff or your `Read` calls.

**When the diff cannot settle it, say so instead of staying silent.** A plan requirement that cannot be checked from the diff — because it lives in unchanged code or spans tasks — is reported as an explicit cannot-verify item naming the requirement and why the diff cannot settle it; it is not a defect claim and must not be padded into one. Emit it at `severity: info` with the title prefixed `cannot verify from diff:` so the orchestrator can match on it, and let it never affect the verdict. This exists so you do NOT spend exploration on unchanged code — the orchestrator holds the cross-task context and resolves these itself.

**Design-smell baseline (the one sanctioned exception to the skip-style rule).** Match the diff hunks you have already read against this fixed Fowler baseline — no extra exploration for smell hunting, and report baseline-only matches at `severity: info`: Mysterious Name (rename), Duplicated Code (extract the shared shape), Feature Envy (move the method onto the data it envies), Data Clumps (bundle into one type), Primitive Obsession (give the concept its own type), Repeated Switches (polymorphism or one shared map), Shotgun Surgery (gather what changes together), Divergent Change (split per reason), Speculative Generality (delete; inline until a real need shows), Message Chains (hide the walk behind one method), Middle Man (cut it, call the target direct), Refused Bequest (drop inheritance, use composition). Every smell is a judgement call, never a hard violation; when the same defect independently qualifies as a material finding (unauthorised scope, plan violation, real defect risk), report it as that finding at its earned severity — the baseline never downgrades. A documented repo standard you have already seen overrides the baseline; skip anything tooling already enforces. Smell findings answer a maintainability template instead of the four-part risk template: what is duplicated/misplaced/over-abstracted, the maintenance cost, and the refactor. Keep this baseline in sync with `changes-review.md`.

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
      "body": "<2-5 sentence description; cite file path and line numbers>",
      "file": "<absolute or repo-relative file path>",
      "line_start": <int>,
      "line_end": <int>,
      "confidence": <float 0-1>,
      "recommendation": "<concrete action>"
    }
  ],
  "next_steps": ["<step>"]
}
```

Use `needs-attention` if there is any material risk worth blocking on. Use `reject` when a critical-path bug, security flaw, or unreachable DoD criterion makes the change unsafe to ship. Use `approve` only if you cannot defend any substantive adversarial finding from the diff and referenced files. Info-severity baseline smells never affect the verdict — `approve` remains correct when they are the only findings. Prefer one strong finding over several weak ones.

## Calibration

Be aggressive, but stay grounded. Every finding must be defensible from the diff or the files you Read. Do not invent files, lines, code paths, attack chains, or runtime behavior you cannot support. If a conclusion depends on an inference, state that explicitly in the finding body and keep `confidence` honest.

## Final check before responding

Each finding must be:

- adversarial rather than stylistic (info-severity baseline design smells are the sanctioned exception)
- tied to a concrete code location with real line numbers
- plausible under a real-world scenario
- actionable for the implementer

Then return only the JSON. Do not wrap it in code fences. Do not add prose before or after.
