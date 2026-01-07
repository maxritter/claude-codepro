---
description: Run tests and fix issues end-to-end with Claude CodePro
model: opus
---
# VERIFY MODE: Verification and Quality Assurance Process with Code Review

> **WARNING: DO NOT use the Task tool with any subagent_type (Explore, Plan, general-purpose).**
> Perform ALL verification yourself using direct tool calls (Read, Grep, Glob, Bash, MCP tools).
> Sub-agents lose context and make verification inconsistent.

## The Process

Tests → Program execution → **Rules compliance audit** → Call chain analysis → Coverage → Quality checks → Code review → E2E → Final verification

Active verification with comprehensive code review that immediately fixes issues as discovered, ensuring all tests pass, code quality is high, and system works end-to-end.

### Step 1: Run & Fix Unit Tests

Run unit tests and fix any failures immediately.

**If failures:** Identify → Read test → Fix implementation → Re-run → Continue until all pass

### Step 2: Run & Fix Integration Tests

Run integration tests and fix any failures immediately.

**Common issues:** Database connections, mock configuration, missing test data

### Step 3: Build and Execute the Actual Program (MANDATORY)

**⚠️ CRITICAL: Tests passing ≠ Program works**

Run the actual program and verify real output.

**If serious bugs (NOT simple fixes):**
1. Update plan with bug fixes as new tasks
2. Set plan status to `PENDING`
3. Tell user: "Found [N] bugs. Run `/clear` → `/implement [plan]`"
4. STOP

**If simple fixes:** Fix directly, re-run, continue

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

2. **Set plan status to PENDING:**
   ```
   Edit the plan file and change the Status line:
   Status: COMPLETE  →  Status: PENDING
   ```

3. **Inform user:**
   ```
   ⚠️ VERIFICATION FAILED - Missing Features Detected

   Found [N] missing features that need implementation:
   - [Feature 1]
   - [Feature 2]
   - ...

   The plan has been updated with [N] new tasks.

   Next steps:
   1. Run `/clear` to reset context
   2. Run `/implement @docs/plans/[plan-file].md` to implement missing features
   3. Run `/verify @docs/plans/[plan-file].md` again after implementation
   ```

4. **STOP** - Do not continue verification

### Step 4: Rules Compliance Audit

**MANDATORY: Verify work complies with ALL project rules before proceeding.**

#### Process

1. **Discover all rules:**
   ```
   Glob(".claude/rules/standard/*.md") → Read each file
   Glob(".claude/rules/custom/*.md") → Read each file
   ```

2. **For each rule file:**
   - Read the entire file
   - Extract the key requirements and constraints
   - Check if each requirement was followed during implementation
   - Note any violations

3. **Classify violations:**
   - **Fixable Now:** Can be remediated immediately (run missing commands, apply fixes)
   - **Structural:** Cannot be fixed retroactively (missed TDD cycle, architectural issues)

4. **Remediate:** Execute fixes for all fixable violations before continuing

#### Output Format

```
## Rules Compliance Audit

### Rules Checked
- `.claude/rules/standard/[filename].md` - [Brief description]
- `.claude/rules/custom/[filename].md` - [Brief description]
- ...

### ✅ Compliant
- [Rule file]: [Requirements that were followed]

### ⚠️ Violations Found (Fixable)
- [Rule file]: [Violation] → [Fix action to execute now]

### ❌ Violations Found (Structural)
- [Rule file]: [Violation] → [What should have been done differently]

### Remediation
[Execute each fix action listed above]
[Show output/evidence of fixes applied]
```

#### Completion Gate

**DO NOT proceed to Step 5 until:**
- All rule files have been read and checked
- All fixable violations have been remediated
- Structural violations have been documented

**If serious structural violations exist:** Consider whether to continue or restart implementation.

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

### Step 9: E2E Verification (if applicable)

Run end-to-end tests as appropriate for the application type.

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
2. Inform user: "✅ Verification complete. Plan status updated to VERIFIED."

**When verification FAILS (missing features, serious bugs, or unfixed rule violations):**

1. Add new tasks to the plan for missing features/bugs
2. **Set status back to PENDING:**
   ```
   Edit the plan file and change the Status line:
   Status: COMPLETE  →  Status: PENDING
   ```
3. Inform user to run `/clear` → `/implement [plan]` → `/verify [plan]`
4. STOP - do not continue

**Fix immediately | Test after each fix | No "should work" - verify it works | Keep fixing until green**
