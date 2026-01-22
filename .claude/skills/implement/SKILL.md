---
name: implement
description: Execute implementation plans in batches with Claude CodePro
---
# IMPLEMENT MODE: Task Execution with Mandatory Context Gathering

> **WARNING: DO NOT use the Task tool with any subagent_type (Explore, Plan, general-purpose).**
> Perform ALL exploration and implementation yourself using direct tool calls (Read, Grep, Glob, MCP tools).
> Sub-agents lose context and make implementation inconsistent.

## Quality Over Speed - CRITICAL

**NEVER rush or compromise quality due to context pressure.**

- Context warnings are informational, not emergencies
- Work spans sessions seamlessly via plan file and continuation mechanisms
- Finish the CURRENT task with full quality, then hand off cleanly
- Do NOT skip tests, compress code, or cut corners to "beat" context limits
- **Quality is the #1 metric** - a well-done task split across sessions beats rushed work

**Execute tasks continuously with full quality. Hand off cleanly when context is high.**

## Feedback Loop Awareness

**This skill may be called multiple times in a feedback loop:**

```
/implement → /verify → issues found → /implement → /verify → ... → VERIFIED
```

**When called after /verify found issues:**
1. Read the plan - /verify will have added fix tasks (marked with `[MISSING]` or similar)
2. Check the `Iterations` field in the plan header
3. **Report iteration start:** "🔄 Starting Iteration N implementation..."
4. Focus on uncompleted tasks `[ ]` - these are the fixes needed
5. Complete all fix tasks, then set status to COMPLETE as normal

**The loop continues automatically until all checks pass (VERIFIED) or context hits 90%.**

## ⛔ CRITICAL: Task Completion Tracking is MANDATORY

**After completing EACH task, you MUST:**

1. **IMMEDIATELY edit the plan file** to change `[ ]` to `[x]` for that task
2. **Update the Progress Tracking counts** (Completed/Remaining)
3. **DO NOT proceed to next task** until the checkbox is updated

**This is NON-NEGOTIABLE. If you skip this step:**
- The rules supervisor will detect incomplete task tracking
- Verification will fail
- You will need to re-implement

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

**Use these tools throughout implementation:**

| Tool | When to Use | Example |
|------|-------------|---------|
| **Context7** | Library API lookup | `resolve-library-id(query="how to use fixtures", libraryName="pytest")` then `query-docs(libraryId, query)` |
| **mcp-cli** | Custom MCP servers | Use `mcp-cli <server>/<tool> '<json>'` for servers in `mcp_servers.json` |

**Context7 requires descriptive queries for both tools - see `context7-docs.md` for full docs.**

**Before starting, verify Vexor is available for semantic search:**
```bash
vexor --version
```

**During implementation:**
- Use `vexor search "query" --mode code` to find similar implementations and patterns
- Use Context7 when unsure about library/framework APIs: `resolve-library-id(query="your question", libraryName="lib")` then `query-docs(libraryId, query="specific question")` - descriptive queries required

## ⚠️ CRITICAL: Migration/Refactoring Tasks

**When the plan involves replacing existing code, perform these ADDITIONAL checks:**

### Before Starting Implementation

1. **Locate the Feature Inventory section** in the plan
2. **If Feature Inventory is MISSING** - STOP and inform user:
   ```
   "This migration plan is missing a Feature Inventory section.
   Without it, features may be accidentally omitted.
   Please run `/plan` again to add the inventory, or manually add it to the plan."
   ```
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

**No production code without a failing test first.** Follow the TDD rules in your context.

| Requires TDD | Skip TDD |
|--------------|----------|
| New functions/methods | Documentation changes |
| API endpoints | Config file updates |
| Business logic | IaC code (CDK, Terraform, Pulumi) |
| Bug fixes | Formatting/style changes |

**The TDD enforcer hook will warn you if you skip this.**

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
7. **Check diagnostics** - Must be zero errors - `mcp__ide__getDiagnostics()`
8. **Validate Definition of Done** - Check all criteria from plan
9. **Mark task completed** in TodoWrite

### ⛔ STEP 10 IS MANDATORY - DO NOT SKIP

10. **UPDATE PLAN FILE IMMEDIATELY:**
    ```
    Use Edit tool to change in the plan file:
    - [ ] Task N: ...  →  - [x] Task N: ...

    Also update Progress Tracking section:
    **Completed:** X | **Remaining:** Y
    ```
    **You MUST do this BEFORE proceeding to the next task.**
    **Failure to update = incomplete implementation.**

11. **Check context usage** - Run `$PWD/.claude/bin/ccp check-context --json`

## Critical Task Rules

**⚠️ NEVER SKIP TASKS:**
- EVERY task MUST be fully implemented
- NO exceptions for "MVP scope" or complexity
- If blocked: STOP and report specific blockers
- NEVER mark complete without doing the work

## Verification Checklist

Before marking complete:
- [ ] Test written and FAILED (RED phase)
- [ ] Implementation written
- [ ] Test PASSES (GREEN phase)
- [ ] Program executed with verified output
- [ ] No diagnostics errors

## When All Tasks Complete

**⚠️ CRITICAL: Follow these steps exactly:**

1. Quick verification: `mcp__ide__getDiagnostics()` and `uv run pytest`
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
4. Inform user: "✅ All tasks complete. Proceeding to verification..."
5. **The /spec workflow will automatically continue to /verify** - do not tell user to run another command

### Migration Completion Checklist

**For migration/refactoring tasks, verify before marking COMPLETE:**

- [ ] All tests pass
- [ ] New code runs without errors
- [ ] Feature Inventory shows all features mapped to completed tasks
- [ ] Old code functionality is replicated in new code
- [ ] "Out of Scope" items were intentional removals (user confirmed), not forgotten migrations

**If you cannot check ALL boxes, the migration is INCOMPLETE. Add new tasks.**
