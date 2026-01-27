---
description: Spec-driven development - plan, implement, verify workflow
argument-hint: "<task description>" or "<path/to/plan.md>"
model: opus
---
# /spec - Unified Spec-Driven Development

**For new features, major changes, and complex work.** Creates a spec, gets your approval, implements with TDD, and verifies completion - all in one continuous flow.

## Arguments

```
/spec <task-description>           # Start new workflow from task
/spec <path/to/plan.md>            # Continue existing plan
/spec --continue <path/to/plan.md> # Resume after session clear
```

## ⛔ CRITICAL RULES

1. **NO sub-agents** - Never use `Task` tool to spawn sub-agents (loses context). Use Read, Grep, Glob, Bash directly.
   - Note: Task MANAGEMENT tools (TaskCreate, TaskList, TaskUpdate, TaskGet) ARE allowed for tracking progress
2. **NO stopping between phases** - Flow continuously from planning → implementation → verification
3. **NO built-in plan mode** - Never use EnterPlanMode or ExitPlanMode tools
4. **Quality over speed** - Never rush due to context pressure

---

## WORKFLOW DISPATCHER

Parse the arguments: $ARGUMENTS

### Determine Current State

```
IF arguments start with "--continue":
    plan_path = extract path after "--continue"
    1. Read /tmp/claude-continuation.md if it exists
    2. Delete the continuation file after reading
    3. Read plan file, check Status AND Approved fields
    → Jump to appropriate phase based on status

ELIF arguments end with ".md" AND file exists:
    plan_path = arguments
    → Read plan file, check Status AND Approved fields
    → Jump to appropriate phase based on status

ELSE:
    task_description = arguments
    → Go to PHASE 1: PLANNING
```

### Status-Based Dispatch

| Status | Approved | Action |
|--------|----------|--------|
| PENDING | No | PHASE 1: Get user approval |
| PENDING | Yes | PHASE 2: IMPLEMENTATION |
| COMPLETE | * | PHASE 3: VERIFICATION |
| VERIFIED | * | Report completion, workflow done |

### The Feedback Loop

```
LOOP until VERIFIED or context >= 90%:
  1. Read plan file status
  2. Execute appropriate phase (table above)
  3. After phase completes, go back to step 1
  4. EXIT only when: Status == VERIFIED OR context >= 90%
```

**Report iteration progress:**
```
🔄 Starting Iteration 1 implementation...  (after first verify failure)
✅ Iteration 1: All checks passed - VERIFIED
```

---

# PHASE 1: PLANNING

> **WARNING: DO NOT use the built-in `ExitPlanMode` or `EnterPlanMode` tools.**

## Using AskUserQuestion - Core Planning Tool

**Questions are grouped into batches for smooth user experience:**

| Batch | When | Purpose |
|-------|------|---------|
| **Batch 1** | Phase 0 (before exploration) | Clarify task, scope, priorities |
| **Batch 2** | Phase 2 (after exploration) | Architecture choices, design decisions |

**When to Use AskUserQuestion:**

| Situation | Example Question |
|-----------|------------------|
| **Unclear requirements** | "Should this feature support batch processing or single items only?" |
| **Multiple valid approaches** | Present 2-3 options with trade-offs for user to choose |
| **Ambiguous scope** | "Should we include error recovery, or fail fast?" |
| **Technology choices** | "Prefer async/await or callbacks for this integration?" |
| **Priority decisions** | "Performance or simplicity - which matters more here?" |
| **Missing domain knowledge** | "How does the existing auth flow work in production?" |

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

### Pre-Task Verification Gate

**Before finalizing tasks, verify:**

- [ ] All old files listed in Feature Inventory
- [ ] All functions/classes from old files identified
- [ ] Every feature mapped to a task OR explicitly marked "REMOVED" with user confirmation
- [ ] No row in Feature Mapping has "⬜ Not mapped" status
- [ ] User has confirmed any features marked for removal

**If any checkbox is unchecked, DO NOT proceed to implementation.**

---

## Creating New Plans

### Step 1: Early Plan File Creation (FIRST)

**Immediately upon starting planning, create the plan file header for status bar detection.**

1. **Generate filename:** `docs/plans/YYYY-MM-DD-<feature-slug>.md`
   - Use current date
   - Create slug from first 3-4 words of task description (lowercase, hyphens)
   - Example: "add user authentication" → `2026-01-24-add-user-authentication.md`

2. **Create directory if needed:** `mkdir -p docs/plans`

3. **Write initial header immediately:**
   ```markdown
   # [Feature Name] Implementation Plan

   Created: [Date]
   Status: PENDING
   Approved: No
   Iterations: 0

   > Planning in progress...

   ## Summary
   **Goal:** [Task description from user]

   ---
   *Exploring codebase and gathering requirements...*
   ```

4. **Why this matters:**
   - Status bar shows "Spec: <name> [/plan]" immediately
   - User sees progress even during exploration phase
   - Plan file exists for continuation if session clears

**CRITICAL:** Do this FIRST, before any exploration or questions.

---

### Step 2: Task Understanding & Clarification

**First, clearly state your understanding of the task.**

Before any exploration:
1. Restate what the user is asking for in your own words
2. Identify the core problem being solved
3. List any assumptions you're making

**Then gather all clarifications needed (Question Batch 1):**

Use AskUserQuestion to ask everything upfront in a single interaction.

**Don't proceed to exploration until clarifications are complete.**

### Step 3: Exploration

**Explore the codebase systematically.** Run explorations **one at a time** (sequentially, not in parallel).

#### 🔧 Tools for Exploration

| Tool | When to Use | Example |
|------|-------------|---------|
| **Context7** | Library/framework docs | `resolve-library-id(query="your question", libraryName="lib")` then `query-docs(libraryId, query)` |
| **Vexor** | Semantic code search | `vexor search "query" --mode code` |
| **Read/Grep/Glob** | Direct file exploration | Use directly, no sub-agents |

**Exploration areas (in order):**

1. **Architecture** - Project structure, entry points, how components connect
2. **Similar Features** - Existing patterns that relate to the task, what can be reused
3. **Dependencies** - Imports, modules, what will be impacted
4. **Tests** - Test infrastructure, existing patterns, available fixtures

**For each area:**
- Document hypotheses (not conclusions)
- Note full file paths for relevant code
- Track questions that remain unanswered

**After explorations complete:**
1. Read each identified file to verify hypotheses
2. Build a complete mental model of current architecture
3. Identify integration points and potential risks
4. Note reusable patterns

### Step 4: Design Decisions

**Present findings and gather all design decisions (Question Batch 2).**

Summarize what you found, then use AskUserQuestion with all decisions at once.

**After user answers:**
- Summarize the chosen design approach
- Confirm: "Does this design work for your needs?"
- Don't proceed until design is validated

### Step 5: Implementation Planning

**Task Count Guidance**
- Avoid bloating plans with unnecessary or overly granular tasks
- If the work genuinely requires more tasks, that's fine - the workflow handles multi-session execution
- Focus on keeping tasks meaningful and necessary

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

### Step 6: Write Full Plan

**Save plan to:** `docs/plans/YYYY-MM-DD-<feature-name>.md`

**Required plan template:**

```markdown
# [Feature Name] Implementation Plan

Created: [Date]
Status: PENDING
Approved: No
Iterations: 0

> **Status Lifecycle:** PENDING → COMPLETE → VERIFIED
> **Iterations:** Tracks implement→verify cycles (incremented by verify phase)
> - PENDING: Initial state, awaiting implementation
> - COMPLETE: All tasks implemented
> - VERIFIED: All checks passed
>
> **Approval Gate:** Implementation CANNOT proceed until `Approved: Yes`

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
[Full task structure]

### Task 2: [Component Name]
[Full task structure]

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

### Step 7: Get User Approval

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

   **If user selects "Yes, proceed with implementation":**
   - Edit the plan file to change `Approved: No` to `Approved: Yes`
   - **Continue immediately to PHASE 2: IMPLEMENTATION**

   **If user selects "No, I need to make changes":**
   - Tell user: "Please edit the plan file at `<plan-path>`, then say 'ready' when done"
   - Wait for user to confirm they're done editing
   - Re-read the plan file to see their changes
   - Ask for approval again using AskUserQuestion

   **If user provides OTHER feedback (corrections, config values, clarifications):**
   - This is NOT approval - they're giving you changes to incorporate
   - Update the plan with their feedback
   - Ask for approval AGAIN with a fresh AskUserQuestion

4. **DO NOT proceed to implementation until user explicitly selects "Yes, proceed"**

**⚠️ CRITICAL: Any response other than selecting "Yes, proceed with implementation" is NOT approval. Config feedback, threshold changes, clarifications = update plan, then re-ask.**

**⚠️ CRITICAL: Claude handles the `Approved:` field update - user never edits it manually**

---

# PHASE 2: IMPLEMENTATION

## Quality Over Speed - CRITICAL

**NEVER rush or compromise quality due to context pressure.**

- Context warnings are informational, not emergencies
- Work spans sessions seamlessly via plan file and continuation mechanisms
- Finish the CURRENT task with full quality, then hand off cleanly
- Do NOT skip tests, compress code, or cut corners to "beat" context limits
- **Quality is the #1 metric** - a well-done task split across sessions beats rushed work

## Feedback Loop Awareness

**This phase may be called multiple times in a feedback loop:**

```
PHASE 2 → PHASE 3 → issues found → PHASE 2 → PHASE 3 → ... → VERIFIED
```

**When called after verification found issues:**
1. Read the plan - verification will have added fix tasks (marked with `[MISSING]` or similar)
2. Check the `Iterations` field in the plan header
3. **Report iteration start:** "🔄 Starting Iteration N implementation..."
4. Focus on uncompleted tasks `[ ]` - these are the fixes needed
5. Complete all fix tasks, then set status to COMPLETE as normal

## ⛔ CRITICAL: Task Completion Tracking is MANDATORY

**After completing EACH task, you MUST:**

1. **IMMEDIATELY edit the plan file** to change `[ ]` to `[x]` for that task
2. **Update the Progress Tracking counts** (Completed/Remaining)
3. **DO NOT proceed to next task** until the checkbox is updated

**This is NON-NEGOTIABLE.**

**Example - After completing Task 5:**
```
Edit the plan file:
- [ ] Task 5: Implement X  →  - [x] Task 5: Implement X
Update counts:
**Completed:** 4 | **Remaining:** 8  →  **Completed:** 5 | **Remaining:** 7
```

## Mandatory Context Gathering Phase (REQUIRED)

**Before ANY implementation, you MUST:**

1. **Read the COMPLETE plan** - Understanding overall architecture and design
2. **Verify comprehension** - Summarize what you learned to demonstrate understanding
3. **Identify dependencies** - List files, functions, classes that need modification
4. **Check current state:**
   - Git status: `git status --short` and `git diff --name-only`
   - Plan progress: Check for `[x]` completed tasks

### 🔧 Tools for Implementation

| Tool | When to Use | Example |
|------|-------------|---------|
| **Context7** | Library API lookup | `resolve-library-id(query="how to use fixtures", libraryName="pytest")` then `query-docs(libraryId, query)` |
| **Vexor** | Find similar patterns | `vexor search "query" --mode code` |

## ⚠️ CRITICAL: Migration/Refactoring Tasks

**When the plan involves replacing existing code, perform these ADDITIONAL checks:**

### Before Starting Implementation

1. **Locate the Feature Inventory section** in the plan
2. **If Feature Inventory is MISSING** - STOP and inform user
3. **Verify ALL features are mapped** - Every row must have a Task #
4. **Read the OLD code completely** - Don't rely on the plan alone

### During Implementation

For EACH task that migrates old functionality:

1. **Read the corresponding old file(s)** listed in Feature Inventory
2. **Create a checklist** of functions/behaviors from old code
3. **Verify each function/behavior exists** in new code after implementation
4. **Test with same inputs** - Old and new code should produce same outputs

### Before Marking Task Complete

**For migration tasks, add this to Definition of Done:**

- [ ] All functions from old code have equivalents in new code
- [ ] Behavior matches old code (same inputs → same outputs)
- [ ] No features accidentally omitted

### Red Flags - STOP Implementation

If you notice ANY of these, STOP and report to user:

- Feature Inventory section missing from plan
- Old file has functions not mentioned in any task
- "Out of Scope" items that should actually be migrated
- Tests pass but functionality is missing compared to old code

## TDD is MANDATORY

**No production code without a failing test first.**

| Requires TDD | Skip TDD |
|--------------|----------|
| New functions/methods | Documentation changes |
| API endpoints | Config file updates |
| Business logic | IaC code (CDK, Terraform, Pulumi) |
| Bug fixes | Formatting/style changes |

## Per-Task Execution Flow

**For EVERY task, follow this exact sequence:**

1. **READ PLAN'S IMPLEMENTATION STEPS** - List all files to create/modify/delete
2. **Perform Call Chain Analysis:**
   - **Trace Upwards (Callers):** Identify what calls the code you're modifying
   - **Trace Downwards (Callees):** Identify what the modified code calls
   - **Side Effects:** Check for database, cache, external system impacts
3. **Mark task as in_progress** in TodoWrite
4. **Execute TDD Flow (RED → GREEN → REFACTOR):**
   - Write failing test first, **verify it fails**
   - Implement minimal code to pass
   - Refactor if needed (keep tests green)
5. **Verify tests pass** - `uv run pytest tests/path/to/test.py -v`
6. **Run actual program** - Show real output with sample data
7. **Check diagnostics** - Must be zero errors
8. **Validate Definition of Done** - Check all criteria from plan
9. **Mark task completed** in TodoWrite
10. **UPDATE PLAN FILE IMMEDIATELY:**
    ```
    Use Edit tool to change in the plan file:
    - [ ] Task N: ...  →  - [x] Task N: ...

    Also update Progress Tracking section:
    **Completed:** X | **Remaining:** Y
    ```
    **You MUST do this BEFORE proceeding to the next task.**
11. **Check context usage** - Run `$CLAUDE_PROJECT_ROOT/.claude/bin/ccp check-context --json`

## Critical Task Rules

**⚠️ NEVER SKIP TASKS:**
- EVERY task MUST be fully implemented
- NO exceptions for "MVP scope" or complexity
- If blocked: STOP and report specific blockers
- NEVER mark complete without doing the work

## When All Tasks Complete

**⚠️ CRITICAL: Follow these steps exactly:**

1. Quick verification: Check diagnostics and run `uv run pytest`
2. **FOR MIGRATIONS ONLY - Feature Parity Check:**
   - Run the NEW code and verify it produces expected output
   - Compare behavior with OLD code (if still available)
   - Check Feature Inventory - every feature should now be implemented
   - If ANY feature is missing: **DO NOT mark complete** - add tasks for missing features
3. **MANDATORY: Update plan status to COMPLETE**
   ```
   Edit the plan file and change the Status line:
   Status: PENDING  →  Status: COMPLETE
   ```
4. **Continue immediately to PHASE 3: VERIFICATION**

---

# PHASE 3: VERIFICATION

## The Process

**Unit tests → Integration tests → Program execution (with log inspection) → Rules audit → Coverage → Quality → Code review → E2E tests → Final verification**

**All test levels are MANDATORY:** Unit tests alone are insufficient. You must run integration tests AND E2E tests AND execute the actual program with real data.

### Step 1: Run & Fix Unit Tests

Run unit tests and fix any failures immediately.

**If failures:** Identify → Read test → Fix implementation → Re-run → Continue until all pass

### Step 2: Run & Fix Integration Tests

Run integration tests and fix any failures immediately.

**Common issues:** Database connections, mock configuration, missing test data

### Step 3: Build and Execute the Actual Program (MANDATORY)

**⚠️ CRITICAL: Tests passing ≠ Program works**

Run the actual program and verify real output.

**Execution checklist:**
- [ ] Build/compile succeeds without warnings
- [ ] Program starts without errors
- [ ] **Inspect logs** - Check for errors, warnings, stack traces
- [ ] Verify expected output matches actual output
- [ ] Test with real/sample data, not just mocks

**If bugs are found:**

| Bug Type | Action |
|----------|--------|
| **Minor** (typo, off-by-one, missing import) | Fix immediately, re-run, continue verification |
| **Major** (logic error, missing function, architectural issue) | Add task to plan, set PENDING, loop back to PHASE 2 |

**Rule of thumb:** If you can fix it in < 5 minutes without writing new tests, fix inline. Otherwise, add a task.

### Step 3a: Feature Parity Check (if applicable)

**For refactoring/migration tasks:** Verify ALL original functionality is preserved.

**Process:**
1. Compare old implementation with new implementation
2. Create checklist of features from old code
3. Verify each feature exists in new code
4. Run new code and verify same behavior as old code

**If features are MISSING:**

This is a serious issue - the implementation is incomplete.

1. **Add new tasks to the plan file:**
   - Read the existing plan
   - Add new tasks for each missing feature (follow existing task format)
   - Mark new tasks with `[MISSING]` prefix in task title
   - Update the Progress Tracking section with new task count
   - Add note: `> Extended [Date]: Tasks X-Y added for missing features found during verification`

2. **Set plan status to PENDING and increment Iterations:**
   ```
   Edit the plan file:
   Status: COMPLETE  →  Status: PENDING
   Iterations: N     →  Iterations: N+1
   ```

3. **Inform user:**
   ```
   🔄 Iteration N+1: Missing features detected, looping back to implement...

   Found [N] missing features that need implementation:
   - [Feature 1]
   - [Feature 2]

   The plan has been updated with [N] new tasks.
   ```

4. **Go back to PHASE 2** - Continue the loop

### Step 4: Rules Compliance Audit

**⚠️ MANDATORY: Actually READ every rule file and verify compliance. Don't skip this.**

This step exists because we often forget our own rules. By re-reading each rule file and explicitly checking compliance, we catch mistakes before they ship.

#### Process

**Step 4a: Discover and read ALL rules**

```bash
# List all rule files
ls -la .claude/rules/standard/*.md .claude/rules/custom/*.md
```

Then use `Read` tool to read EACH file completely:
- `.claude/rules/standard/*.md` - All standard rules
- `.claude/rules/custom/*.md` - All custom project rules

**Step 4b: For EACH rule file, create a compliance checklist**

After reading each rule file, extract the key requirements and check each one:

```markdown
## Rules Compliance Report

### [rule-filename.md]
- [ ] Requirement 1: [description] → ✅ Compliant / ❌ Violation
- [ ] Requirement 2: [description] → ✅ Compliant / ❌ Violation
...

### [next-rule-filename.md]
...
```

#### Common Rules to Check (examples)

| Rule File | Key Requirements to Verify |
|-----------|---------------------------|
| `execution-verification.md` | Did you RUN the actual program (not just tests)? Show output. |
| `tdd-enforcement.md` | Did each test FAIL before you wrote the code? |
| `verification-before-completion.md` | Did you show actual command output as evidence? |
| `testing-strategies-coverage.md` | Is coverage ≥ 80%? Did you mock external calls in unit tests? |
| `python-rules.md` | Did you use `uv` (not pip)? Did you run `ruff` and `basedpyright`? |
| `typescript-rules.md` | Did you detect the package manager? Run `tsc --noEmit`? |
| `git-commits.md` | Using `fix:` prefix? No AI attribution footers? |

**Step 4c: Fix ALL violations immediately**

For each violation found:

1. **Fixable Now** (missing command, missing test, formatting):
   - Execute the fix immediately
   - Show the fix output
   - Re-verify the requirement passes

2. **Structural** (missed TDD cycle, wrong architecture):
   - Document the violation
   - If critical, add fix task to plan and loop back

**Step 4d: Output the compliance report**

```
## Rules Compliance Audit Complete

### Rules Checked: [N] files
- .claude/rules/standard/execution-verification.md ✅
- .claude/rules/standard/tdd-enforcement.md ✅
- .claude/rules/standard/python-rules.md ✅
- .claude/rules/custom/git-commits.md ✅
...

### Violations Found: [N]
- [rule]: [violation] → [fix applied]

### Violations Remaining: [N]
- [structural violation that couldn't be fixed]
```

#### Completion Gate

**DO NOT proceed to Step 5 until:**
- Every rule file has been READ (not skipped)
- Every key requirement has been checked
- All fixable violations have been remediated
- Compliance report has been output

### Step 5: Call Chain Analysis

**Perform deep impact analysis for all changes:**

1. **Trace Upwards (Callers):**
   - Identify all code that calls modified functions
   - Verify they handle new return values/exceptions
   - Check for breaking changes in interfaces

2. **Trace Downwards (Callees):**
   - Identify all dependencies of modified code
   - Verify correct parameter passing
   - Check error handling from callees

3. **Side Effect Analysis:**
   - Database state changes
   - Cache invalidation needs
   - External system impacts
   - Global state modifications

### Step 6: Check Coverage

Verify test coverage meets requirements.

**If insufficient:** Identify uncovered lines → Write tests for critical paths → Verify improvement

### Step 7: Run Quality Checks

Run automated quality tools and fix any issues found.

### Step 8: Code Review Simulation

**Perform self-review using code review checklist:**

- [ ] **Logic Correctness:** Edge cases handled, algorithms correct
- [ ] **Architecture & Design:** SOLID principles, no unnecessary coupling
- [ ] **Performance:** No N+1 queries, efficient algorithms, no memory leaks
- [ ] **Security:** No SQL injection, XSS, proper auth/authz
- [ ] **Readability:** Clear naming, complex logic documented
- [ ] **Error Handling:** Graceful error handling, adequate logging
- [ ] **Convention Compliance:** Follows project standards

**If issues found:** Document and fix immediately

### Step 9: E2E Verification (MANDATORY for apps with UI/API)

**⚠️ Unit + Integration tests are NOT enough. You MUST also run E2E tests.**

Run end-to-end tests to verify the complete user workflow works.

#### For APIs: Manual or Automated API Testing

**When applicable:** REST APIs, GraphQL APIs, authentication systems, microservices

**Test with curl:**
```bash
# Health check
curl -s http://localhost:8000/health | jq

# CRUD operations
curl -X POST http://localhost:8000/api/resource -H "Content-Type: application/json" -d '{"name": "test"}'
curl -s http://localhost:8000/api/resource/1 | jq
curl -X PUT http://localhost:8000/api/resource/1 -H "Content-Type: application/json" -d '{"name": "updated"}'
curl -X DELETE http://localhost:8000/api/resource/1
```

**Verify:**
- All requests succeed with expected status codes
- Response times are acceptable
- Authentication flows work correctly
- CRUD operations complete successfully
- Error scenarios return proper error codes

**If failures:** Analyze failure → Check API endpoint → Fix implementation → Re-run → Continue until all pass

### Step 10: Final Verification

**Run everything one more time:**
- All tests
- Program build and execution
- Diagnostics
- Call chain validation

**Success criteria:**
- All tests passing
- No diagnostics errors
- Program builds and executes successfully with correct output
- Coverage ≥ 80%
- All Definition of Done criteria met
- Code review checklist complete
- No breaking changes in call chains

### Step 11: Update Plan Status

**Status Lifecycle:** `PENDING` → `COMPLETE` → `VERIFIED`

**When ALL verification passes (no missing features, no bugs, rules compliant):**

1. **MANDATORY: Update plan status to VERIFIED**
   ```
   Edit the plan file and change the Status line:
   Status: COMPLETE  →  Status: VERIFIED
   ```
2. Read the Iterations count from the plan file
3. Report completion:
   ```
   ✅ Workflow complete! Plan status: VERIFIED

   Summary:
   - [Brief summary of what was implemented]
   - [Key files created/modified]
   - [Test results]

   Is there anything else you'd like me to help with?
   ```

**When verification FAILS (missing features, serious bugs, or unfixed rule violations):**

1. Add new tasks to the plan for missing features/bugs
2. **Set status back to PENDING and increment Iterations:**
   ```
   Edit the plan file:
   Status: COMPLETE  →  Status: PENDING
   Iterations: N     →  Iterations: N+1
   ```
3. Inform user: "🔄 Iteration N+1: Issues found, fixing and re-verifying..."
4. **Go back to PHASE 2** - Continue the loop

---

# CONTEXT MANAGEMENT

After each major operation, check context:

```bash
$CLAUDE_PROJECT_ROOT/.claude/bin/ccp check-context --json
```

**Between iterations:**
1. If context >= 90%: hand off cleanly (don't rush!)
2. If context 80-89%: continue but wrap up current task with quality
3. If context < 80%: continue the loop freely

If response shows `"status": "CLEAR_NEEDED"` (context >= 90%):

**⚠️ CRITICAL: Execute ALL steps below in a SINGLE turn. DO NOT stop or wait for user response between steps.**

**Step 1: Write continuation file (GUARANTEED BACKUP)**

Write to `/tmp/claude-continuation.md`:

```markdown
# Session Continuation (/spec)

**Plan:** <plan-path>
**Phase:** [planning|implementation|verification]
**Current Task:** Task N - [description]

**Completed This Session:**
- [x] [What was finished]

**Next Steps:**
1. [What to do immediately when resuming]

**Context:**
- [Key decisions or blockers]
```

**Step 2: Trigger session clear**

```bash
$CLAUDE_PROJECT_ROOT/.claude/bin/ccp send-clear <plan-path>
```

CCP will restart with `/spec --continue <plan-path>`

## Error Handling

### No Active Session

If `send-clear` fails:
- Tell user: "Context at X%. Please run `/clear` manually, then `/spec --continue <plan-path>`"

### Plan File Not Found

- Tell user: "Plan file not found: <path>"
- Ask if they want to create a new plan

---

# CRITICAL RULES SUMMARY

1. **NO sub-agents** - Never use `Task` tool to spawn sub-agents. Task MANAGEMENT tools (TaskCreate/List/Update/Get) are fine.
2. **ONLY stopping point is plan approval** - Never stop/wait between phases, during context handoff, or for user acknowledgment. Execute session continuation automatically.
3. **Batch questions together** - Don't interrupt user flow
4. **Run explorations sequentially** - One at a time, never in parallel
5. **NEVER write implementation code during planning** - Planning and implementing are separate phases
6. **NEVER assume - verify by reading files** - Hypotheses must be confirmed
8. **ALWAYS re-read the plan after user edits** - If they chose to make changes, re-read before asking again
9. **The plan must be detailed enough that another developer could follow it**
10. **NEVER use built-in ExitPlanMode or EnterPlanMode tools**
12. **"Out of Scope" ≠ "Don't implement"** - Clarify with user
13. **TDD is MANDATORY** - No production code without failing test first
14. **Update plan checkboxes after EACH task** - Not at the end
15. **Quality over speed** - Never rush due to context pressure
16. **Plan file is source of truth** - Survives session clears
17. **Always ask follow-up after VERIFIED** - Ask if user needs anything else

ARGUMENTS: $ARGUMENTS
