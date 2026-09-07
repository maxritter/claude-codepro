## Step 6: Approach Selection & Design Decisions

<!-- CC-ONLY -->
While native plan mode is active, omit the notification command below. Ask required clarification through the permitted native input surface; defer external notifications until native exit.
<!-- /CC-ONLY -->

Select an approach supported by the request and repository. Compare alternatives when there is a real architectural or product trade-off; do not manufacture options for an established, straightforward solution. The plan records the chosen path and consequential decisions.

#### Part A: Overall Approach

When alternatives matter, compare the plausible approaches based on exploration findings:

- **Name** — short label, **referencing real symbols/files from the Step 3 Workspace Scan when available and permitted for this question** (e.g., "Extend `OrderHandler` in `src/handlers/order.py`" vs "New `OrderService` module under `src/services/`"). Generic labels ("Extend existing handler") are a regression — only use them when `Greenfield?: yes` in the scan output.
- **How it works** — 2-3 sentences
- **Trade-offs** — frame as **"X at the cost of Y"** — never recommend without stating what it costs
- **Recommendation** — pick a preferred approach with reasoning

<!-- CC-ONLY -->
If exploration also revealed scope ambiguity (gaps, optional features, multiple directions), include scope items as part of this step. `AskUserQuestion(multiSelect: true)` for scope items; unselected items go to "Out of Scope" or "Deferred Ideas."
<!-- /CC-ONLY -->
<!-- CODEX-START
If exploration reveals scope ambiguity, prefer the smallest implementable scope that satisfies the request and record excluded items under "Out of Scope". Ask a Codex Batch 2 question only when choosing the wrong option would cause rework across multiple tasks or a user-visible mismatch.
CODEX-END -->

#### Part B: Design Decisions

Within the chosen approach, resolve remaining design choices. Explain trade-offs when they affect the implementation or user experience.

<!-- CC-ONLY -->
**If a material decision requires user input, notify, then ask (Batch 2):**

```bash
~/.pilot/bin/pilot notify plan_approval "Design Decisions" "<plan_name> — architecture choices" --plan-path "<plan_path>" 2>/dev/null || true
```

Use `AskUserQuestion` when available and permitted. Combine related approach and design decisions. Skip this interaction when you can make a reasonable choice within the authorized scope.

**When questions are disabled (`PILOT_PLAN_QUESTIONS_ENABLED=false`):** Still evaluate approaches and design decisions internally. Select the recommended approach, resolve design decisions with reasonable defaults, and document all choices with reasoning in the plan's "Autonomous Decisions" section.
<!-- /CC-ONLY -->
<!-- CODEX-START
**Codex Batch 2 policy:** do not ask a second question batch for ordinary trade-offs. Resolve them internally, state the chosen approach with one cost sentence, and proceed. If a Batch 2 question is unavoidable, notify first and use the current runtime's permitted structured input tool with a concise prose fallback; after the answer, write the plan immediately.

**When questions are disabled (`PILOT_PLAN_QUESTIONS_ENABLED=false`):** select the recommended approach, resolve design decisions with reasonable defaults, and document non-obvious choices in the plan's "Autonomous Decisions" section.
CODEX-END -->

**What ends up in the plan (`## Approach` section, Step 9):** only the chosen approach's **Name** and **Why** (1-2 sentences capturing what it gives us and what it costs). Do NOT list rejected alternatives in the plan — they're decision exhaust, not implementer information. The only exception: if a user-rejected option is one an implementer might re-derive ("why aren't we just doing X?"), capture that rejection as a single sentence inside the `Why:` line.

Incorporate choices into plan design, proceed to Step 7.
