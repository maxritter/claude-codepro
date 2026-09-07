## Step 7: Write the PRD

**Save to:** `docs/prd/YYYY-MM-DD-<slug>.md`

Generate the filename from the first 3-4 words of the idea (lowercase, hyphens). Create the `docs/prd/` directory if it doesn't exist:

```bash
mkdir -p docs/prd
```

### PRD Format

```markdown
# [Feature Name]

Created: YYYY-MM-DD
Author: [user email from pilot status]
<!-- CC-ONLY -->
Agent: [Claude Code if $CLAUDE_CODE_ENTRYPOINT is set, otherwise Codex]
<!-- /CC-ONLY -->
<!-- CODEX-START
Agent: Codex
CODEX-END -->
Category: [one of: Feature, Infrastructure, UX, API, Performance, Security, Documentation, Integration]
Status: Draft
Research: [Quick | Standard | Deep | None]

## Problem Statement

[Concise paragraph: what problem, for whom, why now. This is the north star.]

## Core User Flows

[Step-by-step from the user's perspective. How does the primary user accomplish the core outcome?]

### Flow 1: [Name]
1. User does X
2. System responds with Y
3. ...

### Flow 2: [Name] (if applicable)
1. ...

## Scope

### In Scope
- [Concrete deliverable 1]
- [Concrete deliverable 2]

### Explicitly Out of Scope
- [What's excluded] — [why]
- [What's excluded] — [why]

## Technical Context

[Lightweight technical notes for the implementer. NOT a full technical design — that's /spec's job.]

- **Relevant architecture:** [existing patterns, integration points]
- **Constraints:** [technical limitations, dependencies]
- **Existing code:** [files/modules that relate to this feature]

## Key Decisions

[Trade-offs and decisions made during the conversation, with reasoning.]

| Decision | Choice | Why |
|----------|--------|-----|
| [What was decided] | [The choice] | [Reasoning] |
```

**Technical Context has a hard ceiling — this is the WHAT/HOW boundary made concrete.** The section may state what already exists and what constrains the work: the modules and files the feature touches, the pattern it should follow, a library or service already in the stack, a hard limit (a rate cap, the shape an API returns, a browser or runtime the project supports). That is the depth limit.

It may NOT prescribe the implementation — no names for functions or classes yet to be written, no signatures, no algorithm, no error-handling structure, no retry/timeout/caching strategy, no file layout for new code, no test design. **Apply the test:** does this line say something that is *already true* about the codebase, or does it answer *how the thing should be built*? An implementation detail inferred by the agent belongs in the later plan. Preserve an explicit user-supplied technical requirement or already-authorized design decision here as a constraint, even when it concerns how the product will be built. `/spec` re-derives it from the code with full exploration behind it; a guess written into the PRD skips that exploration and anchors the plan to it.

**Fetch author email** (best-effort):

```bash
~/.pilot/bin/pilot status --json 2>/dev/null | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('email',''))" 2>/dev/null
```

If the command returns a non-empty email, include `Author: <email>` in the header. If empty or fails, omit the Author line.

<!-- CC-ONLY -->
**Agent detection:** If `$CLAUDE_CODE_ENTRYPOINT` is set, write `Agent: Claude Code`. Otherwise, write `Agent: Codex`.
<!-- /CC-ONLY -->
<!-- CODEX-START
**Agent:** Write `Agent: Codex`.
CODEX-END -->

**Category selection:** the header needs one of Feature, Infrastructure, UX, API, Performance, Security, Documentation, Integration. **Infer it** from what the PRD describes — the conversation almost always makes it obvious, and it is a label, not a scope decision. Ask only when two categories genuinely fit and the choice would change how the work is planned; a wrong label costs nothing an `Edit` can't fix, while a question costs a round-trip from the interaction budget.

After writing:

1. **Self-review (4-point scan)** — read the file with fresh eyes and fix issues inline:
   - **Placeholders:** any `TBD`, `TODO`, bracketed `[...]` left from the template, or vague "etc." lists?
   - **Internal consistency:** do scope, user flows, and decisions agree with each other? Does anything contradict?
   - **Scope:** every requested deliverable remains accounted for. Organize a broad PRD into coherent sections or linked documents without silently trimming scope. Out-of-scope entries must be actual boundary decisions, not filler.
   - **Ambiguity:** could any requirement be read two different ways? Pick one and make it explicit.

   **Calibration — only flag what would actually cause problems during `/spec`.** A missing section, a contradiction, or a requirement so ambiguous it could be built two different ways → fix it. Minor wording improvements, stylistic preferences, sections that are less detailed than others, or "this paragraph could be tighter" → leave it alone. The goal is a PRD that produces a correct plan, not a perfect document.

2. **Tell the user the file is ready and ask them to read it.** Do NOT jump straight to a confirmation form — give them a chance to actually open the file first:

   > "PRD written to `docs/prd/YYYY-MM-DD-<slug>.md`. Please open it in your editor and read it through, then let me know if anything needs to change before we hand off to `/spec`."

   Wait for the user's response. They may reply with edits in chat ("change scope item 3 to ...") or confirm it's good.

3. **Apply any requested changes** with `Edit` directly on the file — don't rewrite the whole document. Then re-run the 4-point scan and ask the user to re-read **only the changed sections**.

4. **Set Status to Final** once the user approves, then proceed to **Step 8 (Hand Off)**. Content approval is sufficient; do not ask again merely to show the hand-off command. (If the user wants further changes at item 2/3, loop there until they approve.)
