## Step 1: Name the Goal, Scope the Work

**Goal of this step:** know enough to draft tasks and criteria in Step 2 with concrete pass conditions. Research that would not change a task or a criterion is waste — stop there.

Settle consequential questions about what gets built before drafting criteria, then continue autonomously. Later user steering, genuine blockers, and missing authorization still apply; this step removes routine gates, not the user's ability to direct the work.

### 1.1 Restate the end state in one line

To yourself, not to the user. If you cannot say what the finished thing is in one sentence, the criteria will be mush and the tasks will be worse.

If who it serves or what done means remains materially unclear after workspace research, ask a focused question in 1.5. Preserve the user's chosen workflow instead of requiring a different command.

### 1.2 Research what determines the criteria

Focus on:

- **What already exists locally** that the build should reuse or match — the conventions, components, or prose style already in play.
- **What specifically "good" means here.** You need particulars to write criteria that name real dimensions. "Good typography" is what you write when you did not look.
- **A reference, if one exists.** See 1.3 — do not invent one.

<!-- CC-ONLY -->
For the local sweep, prefer `codegraph_explore(query="<area>")` for structure and `mcp__semble__search` for intent over raw Grep/Glob — one call returns the verbatim source plus the call path. Drop to Grep only to verify a result or find exact text in a known file.

For a reference on the web, prefer the web MCP tools when available: discover them with `ToolSearch(query="+web-fetch fetch")` and `ToolSearch(query="+web-search search")`. The hook privately nudges built-in `WebSearch` and ordinary `WebFetch` calls toward those alternatives without blocking them; authenticated `claude.ai/code/artifact/*` and `preview.claude.ai` URLs remain on the session-aware built-in path. For a live page whose *appearance* is the reference, screenshot it with the Chrome tools rather than reading its DOM — you cannot judge typography from HTML.
<!-- /CC-ONLY -->
<!-- CODEX-START
For the local sweep, use `codegraph_explore` when the area is structural or the entry point is unclear; for named files, docs, config, or UI copy, read them directly or use Semble. For a reference on the web, use the current Codex tool schema's web access, or the Pilot web MCP tools if they are listed (`tool_search(query="+web-fetch fetch")`). For a live page whose appearance is the reference, use playwright-cli or agent-browser to capture it — you cannot judge typography from HTML.
CODEX-END -->

Investigate further when an unfamiliar domain, unverified API, or reference changes the criteria. Stop when additional research no longer changes a task, constraint, or acceptance method; no call quota determines readiness.

Choose the useful execution topology yourself, with direct execution as the baseline. Spawn the minimum number of research agents only for genuinely independent, bounded questions whose results can arrive while useful local work continues; do not fan out agents for a simple ask or multiple takes on the same question. Give parallel agents distinct questions and evidence requirements, then use their results without repeating the same exploration. Never ask the user for permission merely to spawn or delegate.

### 1.3 A reference is optional

Some goals have a real thing to sit beside: a competitor's page, a named author's post, the pre-migration version of a screen. Others do not, and forcing one is worse than having none — a reference nobody can obtain is a comparison the judge invents, and an invented comparison passes everything.

**Use a reference only when all three hold:**

- **Named.** A specific thing. "Stripe's pricing page" works; "award-winning SaaS sites" does not.
- **Obtainable.** You can fetch it, screenshot it, read it, run it, or open it — and you do so *now*, in this step, not later.
- **Comparable.** Both artifacts can sit side by side and someone can pick one. If you cannot picture the A/B, it is not a reference.

| Goal | Reference that works |
|---|---|
| Website, app, UI | A named product's live page, screenshotted at the same viewport |
| Writing | A named author's published piece, same length and format |
| Code, tooling | A named repo's implementation, plus its benchmark or test suite |
| A rewrite or migration | The **existing** artifact, captured before you touch it |

**If the user named one, use it.** If they did not and a genuine A/B exists, **pick it yourself** — take the most useful candidate you can actually reach, name it in the Buildout, and say in one line which you took and why. A reference is a measuring stick, not a design decision; a run that stalls to have one chosen for it has spent a user's attention on the cheapest question it will face all session.

Take it to 1.5 only when the candidates would send the build somewhere genuinely different — matching a minimalist documentation site versus a maximalist marketing page is a different artifact, not a different yardstick.

**When there is no reference, say so in one line and move on.** The criteria carry the standard by themselves. Do not manufacture a comparison to fill the field.

### 1.4 Capture the reference so later rounds cannot drift

Only when you have one. Recalling a reference is how the comparison quietly becomes "whatever we already made", so pin it to something re-openable and record *how* in the Buildout:

- A URL plus the exact fetch or screenshot command.
- A file path under the project (a screenshot, a saved page, a reference doc).
- A command that reproduces it (`git show <ref>:<path>`, a benchmark invocation, a binary to run).

For a rewrite, capture the "before" **now** — once you start editing, the old version stops being obtainable.

### 1.5 Resolve material ambiguity

Before drafting, identify:

1. The **oracle**: the observable signal proving the user's outcome.
2. The evidence that settles each intended criterion.
3. The **misfire**: how a superficially successful artifact could still miss the user's request, and the criterion that catches it.

Derive these from the request, product context, and existing behavior. Choose reasonable reversible implementation and quality decisions yourself. Wording such as "better", "modernize", or "make it good" does not by itself require a question.

Ask only when an unresolved choice materially changes the intended artifact, its audience, a required invariant, or an operation's authorization. Bundle related questions and explain the practical trade-off. Do not ask the user to design test criteria or choose facts available in the repository.

When `PILOT_BRANCH_ISOLATION_ENABLED=true` and no branch flag was supplied, resolve the current-branch/new-branch/worktree choice here. Explicit supplied flags or prior decisions do not need reconfirmation.

Use a structured input tool when the current runtime permits it for this question; otherwise ask a concise prose question. Follow `$HOME/.pilot/agents/agent-gate-protocol.md` with `GATE_NAME=Build scope`, the relevant choices, and `SENTINEL_PATH=none`. The Buildout is not yet registered. While awaiting required input, continue independent research; do not act on the unresolved choice.

`PILOT_PLAN_QUESTIONS_ENABLED=false` suppresses optional clarification. Use a stated reasonable assumption when possible, but do not invent required authorization or silently redefine an outcome that cannot be established. An unanswered optional preference can use the recommended default; required input remains pending.

Record the outcome, oracle, misfire, consequential constraints, and assumptions in `## Summary`. Then draft the contract and build without asking for a nod to proceed.



**Done when:** you can name the oracle, the settling evidence for every criterion you intend to write, and the misfire; any reference has been obtained once by you with its re-obtain command written down; and the consequential decisions are in `## Summary`.
