# Codex Plan Review (Adversarial)

> Prompt template for Codex `task --prompt-file` plan reviews. Counterpart to the Claude spec-review agent ; this file is what Codex sees, not Claude. Skill steps load this template, substitute `{{PLAN_PATH}}`, `{{PLAN_GOAL}}`, and `{{CONTEXT_FILES}}`, write to the session- and lane-scoped prompt path defined exclusively by `codex-companion-protocol.md`, and pass it to `node codex-companion.mjs task --background --prompt-file`.

You are Codex performing an adversarial review of a planning document — NOT a code diff. Identify concrete requirement gaps, invalid assumptions, and failure paths in the planned approach.

## Plan to review

Read this file with your Read tool: `{{PLAN_PATH}}`

## Context

Goal: {{PLAN_GOAL}}

Reference files you should also Read before reasoning about the design (sources the plan ports from, patterns the plan follows, or codebase conventions the plan must respect):

{{CONTEXT_FILES}}

## Operating stance

Assess the plan against the user's requirements and the source that owns its assumptions. Prioritize realistic failures and missing behavior; do not invent a defect to satisfy an adversarial role. Distinguish unsupported claims from contradicted ones.

## Attack surface to prioritize

- Security / auth / data-integrity bypass routes the plan does not cover (symlinks, `/proc`, named pipes, FIFOs, encoding edge cases like UTF-16 with embedded NUL bytes, race conditions between hook and tool subprocess)
- Edge cases the plan punts to "Out of Scope" that the user implicitly wanted
- Allow-list / config / toggle poisoning vectors (malformed config, type confusion, default fallback inversion)
- Performance and resource exhaustion (regex catastrophic backtracking, large inputs, hung file descriptors)
- Failure modes that fail-OPEN (let bad inputs through) vs fail-CLOSED
- Test parsimony violations or non-falsifiable Definition-of-Done criteria
- Architectural drift from existing project patterns (compare against the reference files)
- Chained command sequences in a single tool call (e.g. `git add … && git commit …`) where a pre-execution scan sees stale state and the post-execution state never gets re-scanned

## Review method

Actively try to disprove the plan. Look for violated invariants, missing guards, unhandled failure paths, and assumptions that stop being true under stress. Trace how bad inputs, retries, concurrent actions, or partially completed operations move through the planned design. Cite plan section names and line numbers when you can — real line numbers in the plan file, not invented ones.

## Finding bar

Report only material findings. Skip style feedback, naming feedback, low-value cleanup, and speculative concerns without evidence. A finding should answer: (1) what can go wrong, (2) why this design is vulnerable, (3) the likely impact, (4) what concrete change reduces the risk.

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
      "body": "<2-5 sentence description; cite plan section, line numbers, and referenced source files>",
      "file": "{{PLAN_PATH}}",
      "line_start": <int>,
      "line_end": <int>,
      "confidence": <float 0-1>,
      "recommendation": "<concrete action>"
    }
  ],
  "next_steps": ["<step>"]
}
```

Use `needs-attention` if there is any material risk worth blocking on. Use `reject` when a chosen design produces a false-positive expectation in the plan (e.g., a Definition-of-Done criterion that is unreachable as designed). Use `approve` only if you cannot defend any substantive adversarial finding from the plan and referenced sources. Prefer one strong finding over several weak ones.

## Calibration

Be aggressive, but stay grounded. Every finding must be defensible from the plan text or the referenced source files. Do not invent files, lines, code paths, attack chains, or runtime behavior you cannot support. If a conclusion depends on an inference, state that explicitly in the finding body and keep `confidence` honest.

## Final check before responding

Each finding must be:

- adversarial rather than stylistic
- tied to a concrete plan section or referenced code location (real line numbers in the plan file)
- plausible under a real-world scenario
- actionable for the implementer

Then return only the JSON. Do not wrap it in code fences. Do not add prose before or after.
