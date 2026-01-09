---
name: plan
description: Create a detailed implementation plan with exploration for Claude CodePro
---
# PLAN MODE: Five-Phase Planning Process

> **WARNING: DO NOT use the built-in `ExitPlanMode` or `EnterPlanMode` tools.**
> This project has its own planning workflow using `/plan`, `/implement`, and `/verify` skill commands that are automatically invoked via the `/spec` slash-command.
> The built-in Claude Code plan mode tools write to different paths and are incompatible.
> When planning is complete, simply inform the user and wait for confirmation - no special tool needed.

## Using AskUserQuestion - Core Planning Tool

**The AskUserQuestion tool is essential for effective planning.** Questions are grouped into batches so users answer related questions together without interruption.

### Question Batching Strategy

Questions are consolidated into two batches for a smooth user experience:

| Batch | When | Purpose |
|-------|------|---------|
| **Batch 1** | Phase 0 (before exploration) | Clarify task, scope, priorities |
| **Batch 2** | Phase 2 (after exploration) | Architecture choices, design decisions |

**Don't scatter questions across phases** - gather them and present together.

### When to Use AskUserQuestion

| Situation | Example Question |
|-----------|------------------|
| **Unclear requirements** | "Should this feature support batch processing or single items only?" |
| **Multiple valid approaches** | Present 2-3 options with trade-offs for user to choose |
| **Ambiguous scope** | "Should we include error recovery, or fail fast?" |
| **Technology choices** | "Prefer async/await or callbacks for this integration?" |
| **Priority decisions** | "Performance or simplicity - which matters more here?" |
| **Missing domain knowledge** | "How does the existing auth flow work in production?" |

### How to Structure Questions

**Use the AskUserQuestion tool with clear options:**
```
Question: "Which authentication approach should we use?"
Options:
- Option A: JWT tokens (stateless, scalable, requires token refresh logic)
- Option B: Session-based (simpler, requires session storage)
- Option C: OAuth integration (most secure, more complex setup)
```

**Key principles:**
- Present options, not open-ended questions when possible
- Include trade-offs for each option
- **Batch related questions together** - don't interrupt user flow
- Don't proceed with assumptions - ASK


## Extending Existing Plans

**When adding tasks to existing plan:**

1. Load existing plan: `Read(file_path="docs/plans/...")`
2. Parse structure (architecture, completed tasks, pending tasks)
3. Check git status for partially completed work
4. Verify new tasks are compatible with existing architecture
5. Check total: If original + new > 12 tasks, suggest splitting
6. Mark new tasks with `[NEW]` prefix
7. Update total count: `Total Tasks: X (Originally: Y)`
8. Add extension history: `> Extended [Date]: Tasks X-Y for [feature]`


## ⚠️ CRITICAL: Migration/Refactoring Tasks

**When the task involves migrating, refactoring, or replacing existing code, you MUST complete these additional steps to prevent missing features.**

### Mandatory Feature Inventory (Phase 1.5)

**After exploration but BEFORE creating tasks:**

1. **List ALL files being replaced:**
   ```markdown
   ## Feature Inventory - Files Being Replaced

   | Old File | Functions/Classes | Status |
   |----------|-------------------|--------|
   | `old/module1.py` | `func_a()`, `func_b()`, `ClassX` | ⬜ Not mapped |
   | `old/module2.py` | `func_c()`, `func_d()` | ⬜ Not mapped |
   ```

2. **Map EVERY function/feature to a new task:**
   ```markdown
   ## Feature Mapping - Old → New

   | Old Feature | New Location | Task # |
   |-------------|--------------|--------|
   | `module1.func_a()` | `new/step1.py` | Task 3 |
   | `module1.func_b()` | `new/step1.py` | Task 3 |
   | `module2.func_c()` | `new/step2.py` | Task 5 |
   | `module2.func_d()` | ❌ MISSING | ⚠️ NEEDS TASK |
   ```

3. **Verify 100% coverage before proceeding:**
   - Every row must have a Task # or explicit "Out of Scope" justification
   - "Out of Scope" means the feature is INTENTIONALLY REMOVED (with user confirmation)
   - "Out of Scope" does NOT mean "migrate as-is" - that still needs a task!

### "Out of Scope" Clarification

**CRITICAL: "Out of Scope" has a precise meaning:**

| Phrase | Meaning | Requires Task? |
|--------|---------|----------------|
| "Out of Scope: Changes to X" | X will be migrated AS-IS, no modifications | ✅ YES - migration task |
| "Out of Scope: Feature X" | X is intentionally REMOVED/not included | ❌ NO - but needs user confirmation |
| "Out of Scope: New features for X" | X migrates as-is, no NEW features added | ✅ YES - migration task |

**When in doubt, ASK THE USER:**
```
"The old code has [feature]. Should we:
A) Migrate it as-is (needs implementation task)
B) Intentionally remove it (truly out of scope)
C) Improve it (new feature, needs implementation task)"
```

### Pre-Task Verification Gate

**Before finalizing Phase 3 (Implementation Planning), verify:**

- [ ] All old files listed in Feature Inventory
- [ ] All functions/classes from old files identified
- [ ] Every feature mapped to a task OR explicitly marked "REMOVED" with user confirmation
- [ ] No row in Feature Mapping has "⬜ Not mapped" status
- [ ] User has confirmed any features marked for removal

**If any checkbox is unchecked, DO NOT proceed to Phase 4.**

---

## Creating New Plans

### Phase 0: Task Understanding & Clarification

**First, clearly state your understanding of the task.**

Before any exploration:
1. Restate what the user is asking for in your own words
2. Identify the core problem being solved
3. List any assumptions you're making

**Then gather all clarifications needed (Question Batch 1):**

Use AskUserQuestion to ask everything upfront in a single interaction:

```
I want to confirm my understanding and clarify a few things:

Questions:
1. "Is my understanding correct?"
   - Yes, that's correct
   - Partially correct (please clarify)
   - No, let me explain

2. "What's the priority for this feature?"
   - Performance (fast, optimized)
   - Simplicity (easy to maintain)
   - Flexibility (extensible)

3. "Should error handling be comprehensive or minimal?"
   - Comprehensive (recovery, retries, detailed logging)
   - Basic (fail fast, simple error messages)
```

**Don't proceed to exploration until clarifications are complete.**

### Phase 1: Exploration

**Explore the codebase systematically.** Run explorations **one at a time** (sequentially, not in parallel).

#### 🔧 Tools for Exploration

**Use these tools to gather context efficiently:**

| Tool | When to Use | Example |
|------|-------------|---------|
| **Context7** | Library/framework docs | Use `resolve-library-id` then `query-docs` to look up API usage |
| **Firecrawl** | Web scraping/content | Use `firecrawl_scrape` for single pages, `firecrawl_search` for research |

**Firecrawl MCP Tools (preferred for web content):**
- `firecrawl_scrape` - Single page content extraction (documentation, articles, code)
- `firecrawl_search` - Web search with scraped results (research, finding solutions)
- `firecrawl_map` - Discover all URLs on a website (site structure analysis)
- `firecrawl_crawl` - Crawl entire website (comprehensive extraction)
- `firecrawl_extract` - Structured data extraction with schema

**Before exploring, verify Vexor is available:**
```bash
vexor --version
```
First search will trigger automatic indexing. Use `vexor search "query" --mode code` for semantic code search.

**Exploration areas (in order):**

1. **Architecture** - Project structure, entry points, how components connect
2. **Similar Features** - Existing patterns that relate to the task, what can be reused
3. **Dependencies** - Imports, modules, what will be impacted
4. **Tests** - Test infrastructure, existing patterns, available fixtures

**⚠️ CRITICAL: NO SUB-AGENTS DURING PLANNING**
- **DO NOT use the Task tool with any subagent_type** during planning
- Perform ALL exploration yourself using direct tool calls (Read, Grep, Glob, Context7, Firecrawl)
- Sub-agents lose context and make planning inconsistent
- You must maintain full context throughout the planning process

**For each area:**
- Use `vexor search "query" --mode code` for semantic searches like "authentication middleware" or "database connection handling"
- Use Context7 (`resolve-library-id` then `query-docs`) when you need library/framework API details
- Use Firecrawl (`firecrawl_search`, `firecrawl_scrape`) for web research, fetching documentation, or extracting code examples
- Use `Read`, `Grep`, `Glob` tools directly for file exploration
- Document hypotheses (not conclusions)
- Note full file paths for relevant code
- Track questions that remain unanswered

**After explorations complete:**
1. Read each identified file to verify hypotheses
2. Build a complete mental model of current architecture
3. Identify integration points and potential risks
4. Note reusable patterns

### Phase 2: Design Decisions

**Present findings and gather all design decisions (Question Batch 2).**

Summarize what you found, then use AskUserQuestion with all decisions at once:

```
Based on my exploration, I found [summary of key findings].

I have some design questions:

Questions:
1. "Which architecture approach should we use?"
   - Option A: [description + trade-offs]
   - Option B: [description + trade-offs]
   - Option C: [description + trade-offs]

2. "How should we handle [specific concern found during exploration]?"
   - Option A: [approach]
   - Option B: [approach]

3. "The existing [component] uses [pattern]. Should we follow it or try something different?"
   - Follow existing pattern (consistency)
   - Use new approach (explain why)
```

**After user answers:**
- Summarize the chosen design approach
- Confirm: "Does this design work for your needs?"
- Don't proceed until design is validated

### Phase 3: Implementation Planning

**Task Count Guidance**
- **Aim for 10-12 tasks** as a general guideline for focused plans
- Avoid bloating plans with unnecessary or overly granular tasks
- If the work genuinely requires more tasks, that's fine - the `/spec` workflow handles multi-session execution, so longer plans will be executed across multiple context windows automatically
- Focus on keeping tasks meaningful and necessary, not on hitting a specific number

**Task Structure:**
```markdown
### Task N: [Component Name]

**Objective:** [1-2 sentences describing what to build]

**Files:**
- Create: `exact/path/to/file.py`
- Modify: `exact/path/to/existing.py`
- Test: `tests/exact/path/to/test.py`

**Implementation Steps:**
1. Write failing test - Define expected behavior
2. Implement minimal code - Make test pass
3. Verify execution - Run actual program
4. Integration test - Test with other components

**Definition of Done:**
- [ ] All tests pass (unit, integration if applicable)
- [ ] No diagnostics errors (linting, type checking)
- [ ] Code functions correctly with real data
- [ ] Edge cases handled appropriately
- [ ] Error messages are clear and actionable
```

**Zero-context assumption:**
- Assume implementer knows nothing about codebase
- Provide exact file paths
- Explain domain concepts
- List integration points
- Reference similar patterns in codebase

### Phase 4: Documentation

**Save plan to:** `docs/plans/YYYY-MM-DD-<feature-name>.md`

**Required plan template:**

```markdown
# [Feature Name] Implementation Plan

Created: [Date]
Status: PENDING
Approved: No

> **Status Lifecycle:** PENDING → COMPLETE → VERIFIED
> - PENDING: Initial state, awaiting implementation
> - COMPLETE: All tasks implemented (set by /implement)
> - VERIFIED: Rules supervisor passed (set automatically)
>
> **Approval Gate:** Implementation CANNOT proceed until `Approved: Yes`
> - Claude will ask for your approval after presenting the plan
> - You can request changes before approving
> - Claude updates this field automatically when you approve

## Summary
**Goal:** [One sentence describing what this builds]

**Architecture:** [2-3 sentences about chosen approach]

**Tech Stack:** [Key technologies/libraries]

## Scope

### In Scope
- [What WILL be changed/built]
- [Specific components affected]

### Out of Scope
- [What will NOT be changed]
- [Explicit boundaries]

## Prerequisites
- [Any requirements before starting]
- [Dependencies that must exist]
- [Environment setup needed]

## Context for Implementer
- [Key codebase convention or pattern]
- [Domain knowledge needed]
- [Integration points or dependencies]

## Feature Inventory (FOR MIGRATION/REFACTORING ONLY)

> **Include this section when replacing existing code. Delete if not applicable.**

### Files Being Replaced

| Old File | Functions/Classes | Mapped to Task |
|----------|-------------------|----------------|
| `old/file1.py` | `func_a()`, `func_b()` | Task 3 |
| `old/file2.py` | `ClassX`, `func_c()` | Task 4, Task 5 |

### Feature Mapping Verification

- [ ] All old files listed above
- [ ] All functions/classes identified
- [ ] Every feature has a task number
- [ ] No features accidentally omitted

**⚠️ If any feature shows "❌ MISSING", add a task before implementation!**

## Progress Tracking

**MANDATORY: Update this checklist as tasks complete. Change `[ ]` to `[x]`.**

- [ ] Task 1: [Brief summary]
- [ ] Task 2: [Brief summary]
- [ ] ...

**Total Tasks:** [Number] | **Completed:** 0 | **Remaining:** [Number]

## Implementation Tasks

### Task 1: [Component Name]
[Full task structure from Phase 3]

### Task 2: [Component Name]
[Full task structure from Phase 3]

## Testing Strategy
- Unit tests: [What to test in isolation]
- Integration tests: [What to test together]
- Manual verification: [Steps to verify manually]

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| [Risk 1] | Low/Med/High | Low/Med/High | [How to mitigate] |

## Open Questions
- [Any remaining questions for the user]
- [Decisions deferred to implementation]

```

### Phase 5: Implementation Handoff

**⛔ MANDATORY APPROVAL GATE - This is NON-NEGOTIABLE**

**After saving plan:**

1. **Summarize the plan** - Provide a brief overview of:
   - What will be built (goal)
   - Key tasks (numbered list)
   - Tech stack / approach

2. **Use AskUserQuestion to request approval:**
   ```
   Question: "Do you approve this plan for implementation?"
   Header: "Plan Review"
   Options:
   - "Yes, proceed with implementation" - I've reviewed the plan and it looks good
   - "No, I need to make changes" - I want to edit the plan first
   ```

3. **Based on user response:**

   **If user approves ("Yes, proceed..."):**
   - Edit the plan file to change `Approved: No` to `Approved: Yes`
   - Tell user: "Plan approved. Proceeding with implementation..."
   - The /spec workflow will continue to /implement automatically

   **If user wants changes ("No, I need to make changes"):**
   - Tell user: "Please edit the plan file at `<plan-path>`, then say 'ready' when done"
   - Wait for user to confirm they're done editing
   - Re-read the plan file to see their changes
   - Ask for approval again using AskUserQuestion

4. **DO NOT proceed to implementation until user explicitly approves**

**⚠️ CRITICAL: Claude handles the `Approved:` field update - user never edits it manually**
**DO NOT write or edit any implementation files until approved.**


## Critical Rules

These rules are non-negotiable:

1. **NEVER use sub-agents (Task tool) during planning** - Perform all exploration yourself with direct tool calls
2. **USE AskUserQuestion when uncertain** - Don't guess, ask the user
3. **Batch questions together** - Don't interrupt user with scattered questions
4. **Run explorations sequentially** - One at a time, never in parallel
5. **NEVER write implementation code during planning** - Planning and implementing are separate
6. **NEVER assume - verify by reading files** - Hypotheses must be confirmed
7. **⛔ NEVER proceed without user approval** - Use AskUserQuestion to get explicit approval, then update `Approved: Yes` yourself
8. **ALWAYS re-read the plan after user edits** - If they chose to make changes, re-read before asking again
9. **The plan must be detailed enough that another developer could follow it**
10. **NEVER use built-in ExitPlanMode or EnterPlanMode tools** - This project uses custom `/plan`, `/implement`, `/verify` skill commands. The built-in plan mode tools are incompatible with this workflow. They are orchestrated by the `/spec` slash command.
11. **FOR MIGRATIONS: Create Feature Inventory BEFORE tasks** - List every file, function, and class being replaced. Map each to a task. No unmapped features allowed.
12. **"Out of Scope" ≠ "Don't implement"** - "Out of Scope: Changes to X" means migrate X as-is (still needs a task). Only "Out of Scope: Remove X" means no task needed (requires user confirmation).
13. **Ask for approval after creating plan** - After Phase 5, use AskUserQuestion to get approval. If approved, update the file and let /spec continue automatically.
