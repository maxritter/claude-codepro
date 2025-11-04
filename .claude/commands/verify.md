---
description: Active verification and fix command - runs all tests, immediately fixes any issues found, ensures everything works end-to-end
model: sonnet
---

# Active Verification & Fix

**Purpose:** Hands-on verification that immediately fixes issues as they're discovered, ensuring all tests pass and the system works end-to-end.

**Workflow Position:** Step 3 of 3 in spec-driven development
- **Previous command (/plan):** Idea → Design → Implementation Plan
- **Previous command (/implement):** Implementation Plan → Working Code
- **This command (/verify):** Working Code → Fixed & Verified Implementation

**Process:** Run tests → Fix failures immediately → Re-test → Run program → Fix issues → Repeat until all green

## Process

### Step 1: Gather Context & Fix Initial Issues

**Understand what needs verification and fix obvious problems:**
1. Check diagnostics: `getDiagnostics()`
   - **If errors/warnings found:** Fix them immediately before proceeding
2. Read plan (if exists): `Glob("docs/plans/*.md")` then `Read(latest_plan)`
   - Extract requirements, success criteria, architecture decisions
   - If no plan found, continue without (standalone verification)
3. Check changes: `git status --short` and `git diff --stat` - Understand scope
4. Query Cipher: `ask_cipher("What was implemented? Any known issues?")`

### Step 2: Run & Fix Unit Tests

**Start with the fastest tests and fix failures immediately:**

```bash
# Run unit tests first
uv run pytest -m unit -v --tb=short
```

**If failures occur:**
1. Identify the failing test and error message
2. Read the test file to understand expected behavior
3. Fix the implementation code (not the test unless it's wrong)
4. Re-run the specific failing test: `uv run pytest path/to/test.py::test_function -v`
5. Once fixed, re-run all unit tests to ensure no regression
6. Continue until all unit tests pass

### Step 3: Run & Fix Integration Tests

**Test component interactions and fix issues:**

```bash
# Run integration tests
uv run pytest -m integration -v --tb=short
```

**If failures occur:**
1. Analyze the failure - often related to:
   - Database connection issues
   - External service mocks not properly configured
   - Missing test data setup
2. Fix the issue in the code or test setup
3. Re-run the failing test specifically
4. Continue until all integration tests pass

### Step 4: Execute & Fix the Actual Program

**Run the real application and fix any runtime issues:**

```bash
# Identify the main entry point from the plan or codebase
# Examples based on common patterns:

# ETL Pipeline
uv run python src/main.py
# If fails: Check logs, fix configuration, retry

# API Server
uv run python src/app.py &  # Start server
sleep 2  # Wait for startup
curl -X GET localhost:8000/health  # Health check
# If fails: Fix startup issues, port conflicts, missing env vars

# CLI Tool
uv run python src/cli.py --help
# Then run actual commands based on implementation
# If fails: Fix argument parsing, missing dependencies

# Background Job/Worker
uv run python src/worker.py
# If fails: Fix queue connections, task definitions
```

**Common runtime fixes:**
- Missing environment variables → Add to .env file
- Database connection errors → Check credentials, network
- Import errors → Install missing packages with `uv add`
- Configuration issues → Update config files
- Permission errors → Fix file/directory permissions

### Step 5: Run & Fix Coverage Issues

**Check test coverage and add missing tests:**

```bash
# Run with coverage report
uv run pytest --cov=. --cov-report=term-missing --cov-fail-under=80
```

**If coverage < 80% or critical code uncovered:**
1. Identify uncovered lines from the report
2. Write tests for uncovered critical paths:
   - Create test file if it doesn't exist
   - Write test FIRST (TDD approach)
   - Verify test fails appropriately
   - Run again to confirm coverage improvement
3. Skip coverage for truly untestable code (e.g., if __name__ == "__main__")

### Step 6: Fix Code Quality Issues

**Run quality checks and fix all issues:**

```bash
# Linting - auto-fix what's possible
uv run ruff check . --fix
# If issues remain, manually fix them

# Format all files
uv run ruff format .
# No manual action needed - it auto-formats

# Type checking
uv run mypy src --strict
# If errors: Add type hints, fix type mismatches

# Security scan (if available)
uv run bandit -r src 2>/dev/null || echo "Bandit not installed"
# If issues: Fix security vulnerabilities immediately
```

**Common fixes:**
- Import errors → Reorder/remove unused imports
- Type errors → Add type hints or fix incorrect types
- Line too long → Break into multiple lines
- Undefined names → Import missing modules
- Security issues → Use secure functions/patterns

### Step 7: E2E Verification (if applicable)

**For API projects - test with real requests:**
```bash
# If Postman collection exists
if [ -d "postman/collections" ]; then
  newman run postman/collections/*.json -e postman/environments/dev.json
  # Fix any failing requests
fi

# Or test key endpoints manually
curl -X GET localhost:8000/api/health
curl -X POST localhost:8000/api/[endpoint] -H "Content-Type: application/json" -d '{}'
```

**For data pipelines - verify data flow:**
```sql
-- Check if data was loaded correctly
SELECT COUNT(*) FROM target_table WHERE created_at > NOW() - INTERVAL '1 hour';
-- If no data, debug the pipeline
```

### Step 8: Final Verification Loop

**Run everything one more time to ensure all fixes work together:**

```bash
# Quick final check
uv run pytest -q  # Quiet mode for quick pass/fail
uv run python src/main.py  # Or whatever the main entry point is
getDiagnostics()  # Must return zero issues
```

**If anything fails:** Go back to the specific step and fix it

## Store Progress in Cipher

**After fixing each major issue:**
```
ask_cipher("Fixed: [issue description] in [file].
Solution: [what was done]
Tests now passing: [test names]")
```

**After successful completion:**
```
ask_cipher("Verification complete for [feature/plan].
All tests passing, coverage at X%, program runs successfully.
Key fixes applied: [list of major fixes]")
```

## Key Principles

**Fix immediately** | **Test after each fix** | **No "should work" - verify it works** | **Keep fixing until green**

**Success = Everything works. No exceptions.**
