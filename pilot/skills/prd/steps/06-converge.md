## Step 6: Converge on Scope

Based on the chosen approach:

1. **State what's in scope** — concrete deliverables
2. **Propose what's explicitly out** — and why (prevent scope creep later)
3. **Identify the core user flows** — step by step from the user's perspective
4. **Note any technical context** that `/spec` will need — constraints, integration points, existing patterns

### Generating the out-of-scope list

Record concrete boundaries a reasonable implementer might otherwise misunderstand. Preserve every explicit user requirement; do not cut scope merely to simplify the PRD or fill an exclusion list. When an adjacent capability creates a real product choice, resolve it with the user.

Adjacent capabilities worth checking every time:

- **Surface** — mobile or native app, browser extension, CLI, public API, embeddable widget
- **Access** — SSO/OAuth, roles and permissions, team or multi-tenant scoping, audit trail
- **Lifecycle** — editing after the fact, history and versioning, undo, archive, soft delete, bulk actions
- **Scale** — search, filtering, pagination, import/export, migrating data that already exists
- **Money and comms** — billing, quotas, email or push notification, webhooks
- **AI features** — model selection, per-user API keys, multiple providers, streaming, evals

**Include only real boundary decisions, with no required count.** "No mobile app" on a CLI tool is filler — cut it. The items that earn their place are the ones an implementer would plausibly build if the PRD stayed silent. Anything the user pulls back becomes a scope item; anything they confirm goes to `## Scope → Explicitly Out of Scope` carrying its reason.

**This is context inside the existing confirmation, not a new question.** Present the proposed cuts as part of the scope question below (or Step 5's combined prompt) — a separate round-trip for them would breach the interaction budget.

**If scope still needs a material decision, ask using the permitted question mechanism:**
- "Yes, scope looks right — proceed to PRD"
- "No, I want to adjust scope" — let me specify what to add/remove
- "Let's discuss further" — I have questions about the scope

**Fold this into Step 5's approach question when the scope follows directly from the chosen approach** — that is the common case, and two prompts where one would do burns an interaction from the budget. Ask separately only when the approach genuinely leaves scope open.

<!-- CODEX-START
Codex override: combine scope confirmation with the approach decision when possible. If the scope follows directly from prior answers, write the PRD and mark the scope assumptions clearly instead of asking another confirmation prompt.
CODEX-END -->
