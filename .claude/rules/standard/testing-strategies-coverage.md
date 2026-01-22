## Testing Strategies and Coverage

**Core Rule:** Unit tests for logic, integration tests for interactions, E2E tests for workflows. Minimum 80% coverage required.

### Test Organization

Check existing structure before creating tests:

```
tests/
├── unit/              # Fast, isolated (< 1ms each)
├── integration/       # Real dependencies
└── e2e/              # Complete workflows
    └── postman/      # API collections (if applicable)
```

### Test Type Selection

**Unit Tests - Use When:**
- Testing pure functions and calculations
- Business logic without external dependencies
- Data transformations and parsing
- Input validation rules
- Utility functions

**Requirements:**
- Fast execution (< 1ms per test)
- Zero external dependencies (mock databases, APIs, filesystem)
- Test single behavior per test
- Use test markers (`@pytest.mark.unit`)

**Integration Tests - Use When:**
- Testing database queries and transactions
- External API calls
- Message queue operations
- File system operations
- Authentication flows

**Requirements:**
- Use real dependencies (test databases, not production)
- Setup/teardown fixtures for isolation
- Clean up data after each test
- Use test markers (`@pytest.mark.integration`)

**E2E Tests - Use When:**
- Testing complete user workflows
- API endpoint chains
- Data pipeline end-to-end flows

### Test Naming Convention

**Mandatory Pattern:** `test_<function>_<scenario>_<expected_result>`

Examples:
- `test_process_payment_with_insufficient_funds_raises_error`
- `test_fetch_users_with_admin_role_returns_filtered_list`
- `test_parse_csv_with_missing_columns_uses_defaults`

Names must be self-documenting without reading code.

### Running Tests

Identify framework first (pytest, jest, vitest, mocha):

```bash
# Run all tests
pytest                    # Python
npm test                  # Node.js

# Run by type
pytest -m unit           # Unit only
pytest -m integration    # Integration only

# Run specific file/test
pytest tests/unit/test_auth.py
pytest tests/unit/test_auth.py::test_login_success

# With output
pytest -v -s            # Verbose with prints
```

### Coverage Requirements

**Before marking work complete:**

1. Run coverage: `pytest --cov=src --cov-report=term-missing --cov-fail-under=80`
2. Verify ≥ 80% coverage
3. Add tests for uncovered critical paths

**Must cover:**
- All business logic functions
- All API endpoints
- All data transformations
- All validation rules
- All error handling paths
- All conditional branches

**Exclude from coverage:**
- `if __name__ == "__main__"` blocks
- Generated code (migrations, protobuf)
- Configuration files
- Simple getters/setters with no logic

### Test Fixtures

Reuse setup code via fixtures:

```python
# Python (pytest)
@pytest.fixture
def db_session():
    session = create_test_session()
    yield session
    session.close()
```

```javascript
// JavaScript (Jest)
beforeEach(() => { /* Setup */ });
afterEach(() => { /* Cleanup */ });
```

Each test must start with clean, isolated state.

### AI Assistant Workflow

When implementing functionality:

1. Search codebase for similar test patterns
2. Determine test type (unit/integration/E2E) based on dependencies
3. Write failing test first (TDD)
4. Reuse existing fixtures
5. Follow naming convention
6. Run test to verify failure
7. Implement minimal code to pass
8. Run all tests to prevent regressions
9. Verify coverage ≥ 80%
10. Execute actual program

### E2E Testing Patterns

**For APIs:**

```bash
# Test with curl
curl -s http://localhost:8000/health | jq
curl -X POST http://localhost:8000/api/resource -H "Content-Type: application/json" -d '{"name": "test"}'
```

Test assertions:
- HTTP status codes (200, 201, 400, 401, 404, 500)
- Response time thresholds
- JSON schema validation
- State changes (database records)

**For Data Pipelines:**

Run actual pipeline, verify:
- Source extraction completes
- Transformations produce expected output
- Destination receives correct data
- Data quality checks pass
- Logs show expected flow

### ⛔ CRITICAL: Mandatory Mocking in Unit Tests

**Unit tests MUST mock ALL external calls. No exceptions.**

| Call Type | MUST Mock | Example |
|-----------|-----------|---------|
| HTTP/Network | `httpx`, `urllib`, `requests` | `@patch("module.httpx.Client")` |
| Subprocess | `subprocess.run`, `subprocess.Popen` | `@patch("module.subprocess.run")` |
| File I/O | `open`, `Path.read_text` | `@patch("builtins.open")` or use `tmp_path` |
| Database | SQLite, PostgreSQL connections | Use test fixtures |
| External APIs | Any third-party service | Mock the client |

**Why this is non-negotiable:**
- Real network calls make tests slow (5+ seconds vs milliseconds)
- Real calls cause flaky tests (network failures, rate limits)
- Tests must work offline and in CI without credentials
- Hanging tests waste developer time and CI resources

**Pattern - Mock at module level:**
```python
# GOOD - mock where imported, not where defined
@patch("mymodule.httpx.Client")
def test_fetch_data(mock_client):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": "test"}
    mock_client.return_value.__enter__.return_value.get.return_value = mock_response

    result = fetch_data()  # Uses mocked httpx
    assert result == {"data": "test"}

# BAD - no mock, makes real network call
def test_fetch_data():
    result = fetch_data()  # HANGS or fails without network
```

**Detecting unmocked calls:**
- Test takes > 1 second → likely unmocked I/O
- Test fails with "Connection refused" → unmocked network
- Test hangs indefinitely → unmocked blocking call

### Common Mistakes

**Dependent tests:**
```python
# BAD - test2 depends on test1 running first
def test1_create_user():
    create_user("test")

def test2_update_user():
    get_user("test")  # Assumes test1 ran
```

**Testing implementation instead of behavior:**
```python
# BAD - tests internal variable
def test_internal_counter_increments():
    obj._counter += 1
    assert obj._counter == 1

# GOOD - tests behavior
def test_process_increments_total():
    obj.process()
    assert obj.get_total() == 1
```

**Other mistakes to avoid:**
- Ignoring failing tests (fix or remove immediately)
- Committing commented-out tests
- Time-dependent assertions (causes flakiness)
- Relying on external services in unit tests
- Missing cleanup between tests
- **Making real network/subprocess calls in unit tests (NEVER)**

### ⛔ MANDATORY: Fix ALL Errors (Tests, Types, Lint)

**NEVER skip or ignore errors. No exceptions. No excuses.**

When verification finds ANY errors - tests, type checker, or linter - you MUST fix them before marking work complete. This applies to ALL errors, not just ones "related" to your changes.

The following justifications are INVALID and FORBIDDEN:

| ❌ Invalid Excuse | Why It's Wrong |
|------------------|----------------|
| "Pre-existing failure" | If it was broken before, fix it now. You found it, you own it. |
| "Unrelated to my changes" | You ran the checks, you saw the error. Fix it. |
| "Will fix later" | Later never comes. Fix it now. |
| "Not my code" | Irrelevant. The error exists. Fix it. |
| "Flaky test" | Either fix the flakiness or delete the test. No middle ground. |
| "Test/type error is wrong" | Then fix it. Don't leave it broken. |

**The Rule:**
1. Run tests → failures? **STOP** and fix
2. Run type checker → errors? **STOP** and fix
3. Run linter → errors? **STOP** and fix
4. All checks pass → Continue with your work

**Why this matters:**
- Broken checks erode trust in the quality gates
- "Pre-existing" failures multiply into more failures
- Skipping errors normalizes ignoring quality
- The user trusts you to leave the codebase better than you found it

**If you catch yourself about to say "pre-existing" or "unrelated":** STOP. Fix the error. Then continue.

### Test Markers

Organize tests by type for selective execution:

```python
# Python
@pytest.mark.unit
@pytest.mark.integration
@pytest.mark.slow
```

```javascript
// JavaScript
describe.skip('integration tests', () => {});
```

Use to run fast tests during development, full suite in CI/CD.

### Decision Tree

```
Does function use external dependencies?
├─ NO → Unit test (mock all external calls)
└─ YES → Integration test (use real dependencies)

Is this a complete user workflow?
├─ YES → E2E test (test entire flow)
└─ NO → Unit or integration test
```

### Completion Checklist

Before marking testing complete:

- [ ] All new functions have tests
- [ ] Tests follow naming convention
- [ ] Unit tests mock external dependencies
- [ ] Integration tests use real dependencies
- [ ] All tests pass
- [ ] Coverage ≥ 80% verified
- [ ] No flaky or dependent tests
- [ ] Actual program executed and verified

**If any checkbox unchecked, testing is incomplete.**
