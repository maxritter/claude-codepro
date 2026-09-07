---
name: prd
description: "Turns a rough idea into a written, approved Product Requirements Document, with optional market and technical research. Runs only when the user explicitly types /prd. Not for work already scoped enough to plan — that is /spec, or /build when the approach is better discovered while building."
argument-hint: "<idea or feature description>"
user-invocable: true
---

# /prd - Generate Product Requirements Documents

<HARD-GATE>
Do NOT invoke `/spec`, `/spec-plan`, `/spec-implement`, `/build`, write any code, scaffold any project, or take any implementation action until you have written a PRD and the user has approved it. This applies to EVERY idea regardless of perceived simplicity.

`/prd`'s output is a written PRD at the path determined in Step 7 (write-prd). The terminal state is offering hand-off to `/spec` or `/build` and waiting for the user. The skill does not invoke implementation skills directly — Step 8 prints the command for the user to run.
</HARD-GATE>

**Strategic thought partner and brainstorming surface** — turns vague ideas into concrete Product Requirements Documents (PRDs) through one-on-one conversation, with optional research. Produces a PRD that can be handed off directly to `/spec` for implementation.

**Use `/prd` when:**
- You have an idea but aren't ready to spec it
- Requirements are unclear or you only have a problem statement, not a solution
- You want to **brainstorm back-and-forth** before locking anything down — pitch ideas, react, refine, then converge
- You need to explore trade-offs, challenge assumptions, or define scope before committing to a plan

**Use `/spec` or `/build` instead when:** requirements are well-defined. You know what to build and roughly how. Skip straight to planning (`/spec`) or to naming the goal (`/build`).

`/prd` chains into either: it produces the requirements doc, then hands off to `/spec` when the next question is *how, in what order*, or to `/build` when the next question is *how good, measured against what*.

---

## Workflow

```
Understand → Research (optional) → Ideate (if vague) → Clarify → Propose → Converge → Write PRD → Hand off to /spec or /build
```

**Two modes inside one flow:**
- **Divergent (Ideate):** free-form prose, the agent pitches directions, user reacts. Used when the idea is vague.
- **Convergent (Clarify → Converge):** structured `AskUserQuestion` forms with predefined options. Used once the shape is known.

The phase boundary is a default, not a wall — Clarify can drop back into 1-2 prose turns when a question opens a genuinely new unknown, then return to structured forms.

The entire flow is conversational. One question at a time. No rushing to solutions.

## Principles

- **Understand before solving.** The PRD describes WHAT and WHY; `/spec` handles HOW. The boundary has a named ceiling in Step 7 — the PRD points at the code that already exists and the constraints that bind it, and stops there.
- **Be a thought partner, not an order-taker.** Challenge assumptions, surface trade-offs, name red flags and scope-creep risks while they're still cheap to fix.
- **YAGNI ruthlessly.** Apply rung 1 of the ladder (`development-practices.md` → *Build the least that works*) to every proposed feature: does this need to exist at all? The cheapest scope to cut is the scope never specified.
- **Write for handoff.** The PRD is the contract between requirements and specification — a reader running `/spec` should need nothing else.

## Interaction budget

Questions are the expensive part of this skill, and every avoidable one costs the user a round-trip.

**Target: 2–4 user interactions total**, from first message to hand-off. A typical concrete idea spends one Clarify batch and one combined approach+scope confirmation. Ideation rounds (Step 3) are conversation, not interactions — they don't count against this, but they have their own 1–3 round ceiling.

Spend an interaction only when the answer would **change what gets built**. Before every question, ask in order:

1. Can the codebase answer this? → read it (Step 1's scan, `codegraph_explore`, Semble). Never ask the user about facts the code already encodes.
2. Was it answered by the original idea or an earlier answer? → don't re-ask.
3. Is the decision reversible and low-cost? → pick the sensible default, record it under Key Decisions, move on.

Combine related decisions into one call rather than serialising them — approach selection (Step 5) and scope confirmation (Step 6) belong in one interaction whenever the scope follows from the approach.

**When the user delegates the remaining choices** ("whatever you think", "you pick"), take reasonable defaults, record consequential assumptions under Key Decisions, and draft the PRD in Step 7 without another permission question. Step 7's read-the-file review is the backstop: a wrong default there costs one `Edit`, another question costs a round-trip.

<!-- CC-ONLY -->
**Use the `AskUserQuestion` tool for user questions during convergent phases (Steps 4-8)** — it renders a structured form; use a concise prose question when no permitted structured tool is available.

<!-- /CC-ONLY -->
<!-- CODEX-START
**Use the runtime's structured user-input tool when exposed and permitted for the question.** Otherwise ask a concise question in prose and wait for required input.
CODEX-END -->

### Product clarity and pacing

Draft once the user outcome, scope, important constraints, and acceptance signals are clear. Research unresolved facts that could change those decisions, then stop. Save useful findings across compaction; context percentages and tool counts are not reasons to narrow the requested scope.

Skip ideation or repeated confirmation when the user already chose a direction. Reversible defaults can be recorded as assumptions; never represent an assumption as a user-provided answer.



**Whenever you cannot render a structured question** — as a Claude Code subagent, where `AskUserQuestion` is absent, or wherever it degrades to plain text — read `$HOME/.pilot/agents/agent-gate-protocol.md` and follow it for every question in Steps 1–6 and 8, with `SENTINEL_PATH` = `none` (a PRD registers no plan, so no stop guard is holding the session open). These questions elicit rather than authorise, so the runbook's "never resolve the gate yourself" reads here as: **never invent the user's answer and write it into the PRD as though it were given.** A requirement nobody stated, recorded as if they had, is the PRD equivalent of a self-approved plan. Reasonable reversible defaults may be documented as assumptions; a material unresolved product decision still needs the user's answer.
