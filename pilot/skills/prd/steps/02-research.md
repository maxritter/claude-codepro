## Step 2: Research (Optional)

Choose research depth from the request and the facts the PRD depends on. Repository-local ideas usually need only the verified project context. Current market, product, pricing, or external API claims need primary-source verification. Ask about depth only when the time/cost trade-off materially affects the user's intended work.

- **Quick:** proceed from existing project evidence when no external fact needs research.
- **Standard:** focused external research for facts that affect scope or decisions.
- **Deep:** honor an explicit deep-research request with broader source checking and a cited synthesis.



### Quick Tier

Skip web research. Proceed to Step 3 (Ideate) if the idea is still vague and would benefit from brainstorming; otherwise go straight to Step 4 (Clarify).

### Standard Tier

1. **Generate 5-8 search queries** based on the topic:
   - Competitor/alternative analysis ("alternatives to X", "X vs Y")
   - Prior art and existing solutions ("how companies solve X")
   - Technical approaches ("best practices for X")
   - User experience patterns ("UX patterns for X")
<!-- CC-ONLY -->
2. **Discover web-search tool:** `ToolSearch(query="+web-search search")`
3. **Batch independent searches**, gathering key findings from each
4. **Optionally fetch full pages** for promising results: `ToolSearch(query="+web-fetch fetch")` then `fetch_url(url="...")`
<!-- /CC-ONLY -->
<!-- CODEX-START
2. **Use the web tools exposed in the current Codex schema.** Follow their actual names and parameter schemas; do not assume a specific MCP namespace.
3. **Batch independent searches when the tool supports it**, gathering key findings from each.
4. **Fetch full pages selectively** for promising results with the available fetch/open capability.
CODEX-END -->
5. **Compile research summary:**
   - Key findings (3-5 bullet points)
   - Sources with links
   - Trade-offs and patterns discovered
   - Gaps or areas needing more exploration
6. **Present summary to user** before proceeding to ideation (Step 3) or clarification (Step 4)

### Deep Tier

<!-- CC-ONLY -->
Deep research is owned by the dedicated **`deep-research` skill** — a harness that decomposes the question into multiple angles, fans out parallel web searches, fetches and de-duplicates sources, adversarially verifies each claim, and synthesizes a cited report. Do **not** run searches or spawn your own sub-agents here; hand the whole research loop to the skill.

1. **Compose a focused research question** from the idea plus everything learned in Step 1 — weave in the concrete constraints, stack, audience, and context you've gathered so the research is scoped, not generic. A sharp, specific question is the single biggest driver of report quality.
2. **Invoke the skill:**
   ```
   Skill(skill="deep-research", args="<focused research question, constraints woven in>")
   ```
   - The skill may ask 2-3 clarifying questions if scope is still broad — answer them from PRD context where you can, otherwise relay them to the user.
   - It runs a multi-agent workflow (higher token cost) and returns a cited, fact-checked report.
3. **If the skill is unavailable or its run fails,** fall back to the **Standard tier** above (in-session web search) so research still happens — never silently skip it.
4. **Synthesize the returned report** into the research summary, preserving source links and any confidence/caveat notes.

**Cap:** none needed — the `deep-research` skill manages its own breadth and token budget.
<!-- /CC-ONLY -->
<!-- CODEX-START
Deep research in Codex uses bounded parallel angles when agent tools are exposed, with a direct in-session fallback:

1. **Generate a research outline** with 2-3 research angles based on the topic. Examples:
   - "Competitor landscape" — what exists, market positioning, pricing
   - "Technical approaches" — architectures, frameworks, implementation patterns
   - "User experience" — UX patterns, onboarding flows, common pain points
2. **Assign independent angles.** When the current Codex schema exposes agent tools, dispatch one bounded research agent per angle in parallel. Give each an exclusive question, the same source-quality rules, and a required cited findings format. Otherwise research the angles directly. For each angle:
   - Execute 2-3 targeted searches
   - Optionally fetch full pages for promising results via the available fetch/open capability
   - Compile findings per angle
3. **Collect and synthesize.** Keep returned agent ids and wait using the current tool schema. Verify citations before synthesizing findings across all angles into one research summary.

Choose the minimum useful independent research angles and deepen only unresolved claims that could change the PRD. Do not stop short of the requested research scope to meet a call quota.
CODEX-END -->

**Then (both agents):** present the synthesized findings to the user — organized by source/angle, key insights and caveats highlighted — before proceeding to ideation (Step 3) or clarification (Step 4).

### Research Output

When research was performed (Standard or Deep), the findings are embedded in the PRD under a `## Research Findings` section after Key Decisions.
