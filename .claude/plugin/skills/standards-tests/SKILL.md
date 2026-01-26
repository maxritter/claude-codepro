---
name: Tests Standards
description: Write focused tests for core user flows and critical paths with clear test names, behavior-focused assertions, mocked external dependencies, and fast execution, deferring edge case testing until explicitly required. Use this skill when creating or modifying test files, writing unit tests, integration tests, or test cases for any feature. Apply when writing test files (test/, __tests__/, spec/, .test.js, .spec.ts, test_*.py), implementing tests for core user workflows, testing critical business logic, mocking external dependencies (databases, APIs, file systems), writing descriptive test names, creating fast-running unit tests, or adding tests at logical completion points of feature development. Use for any task involving test creation, test coverage, test strategy, or test-driven development.
---

# Tests Standards

**Core Philosophy**: Write minimal, focused tests for critical paths. Defer comprehensive testing until explicitly requested.

## When to use this skill

- When creating or modifying test files (test/, __tests__/, *.test.js, *.spec.ts, test_*.py)
- When writing unit tests for core business logic and critical user workflows
- When implementing integration tests at logical feature completion points
- When writing test names that clearly describe what is being tested and expected outcome
- When mocking external dependencies like databases, APIs, or file systems to isolate units
- When focusing tests on behavior (what the code does) rather than implementation details
- When ensuring unit tests execute quickly (milliseconds) for frequent developer runs
- When testing core user flows and primary workflows (deferring edge cases unless critical)
- When writing minimal tests during feature development, focusing on main functionality
- When avoiding excessive testing of non-critical utilities or secondary workflows
- When deciding test coverage strategy for new features or refactoring

This Skill provides Claude Code with specific guidance on how to adhere to coding standards as they relate to how it should handle testing test writing.

## Strategic Test Writing

### Minimal Testing During Development

**Do NOT write tests for:**
- Every intermediate step or code change
- Non-critical utility functions
- Secondary workflows or helper functions
- Edge cases unless business-critical
- Error states unless explicitly required
- Validation logic unless core to feature

**DO write tests for:**
- Primary user workflows (happy path)
- Critical business logic
- Core feature functionality
- Features at logical completion points

**Pattern:**
```
1. Implement feature completely
2. Identify critical paths
3. Write tests for those paths only
4. Move to next feature
```

### Test Scope Priority

**Priority 1 - Always Test:**
- Main user flows (login, checkout, data submission)
- Business-critical calculations
- Data transformations affecting core features

**Priority 2 - Test When Requested:**
- Edge cases and boundary conditions
- Error handling and validation
- Non-critical utilities
- Secondary workflows

**Priority 3 - Defer:**
- Exhaustive input validation
- All possible error states
- Performance edge cases
- Rare user scenarios

## Test Quality Standards

### Test Naming Convention

Use descriptive names following pattern: `test_<function>_<scenario>_<expected_result>`

**Good:**
```python
test_checkout_with_valid_cart_creates_order()
test_login_with_correct_credentials_returns_token()
```

**Bad:**
```python
test_checkout()
test_user_login()
```

### Behavior Over Implementation

Test what the code does, not how it does it.

**Good - Tests behavior:**
```python
def test_discount_calculation_applies_percentage():
    result = calculate_discount(price=100, rate=0.2)
    assert result == 80
```

**Bad - Tests implementation:**
```python
def test_discount_uses_multiplication():
    # Don't test internal calculation method
    assert discount._multiply_called == True
```

### Mock External Dependencies

Isolate units by mocking external systems.

**Always mock:**
- Database connections
- API calls
- File system operations
- Network requests
- External services

**Example:**
```python
@mock.patch('app.database.query')
def test_fetch_user_returns_user_data(mock_query):
    mock_query.return_value = {'id': 1, 'name': 'Test'}
    result = fetch_user(1)
    assert result['name'] == 'Test'
```

### Fast Execution

Unit tests must execute in milliseconds.

**Fast tests enable:**
- Frequent test runs during development
- Quick feedback loops
- Developer confidence

**If test is slow:**
- Mock external dependencies
- Use in-memory databases
- Move to integration test suite

## Decision Framework

Before writing a test, ask:

1. **Is this a critical path?** → If no, defer
2. **Is this core business logic?** → If no, defer
3. **Was I explicitly asked to test this?** → If no, defer
4. **Is this the happy path?** → If yes, test it

## Integration with TDD

When following TDD:
1. Write minimal failing test for critical path only
2. Implement feature
3. Verify test passes
4. Stop - don't add more tests unless requested

## Common Mistakes to Avoid

**Over-testing during development:**
- Writing tests for every function
- Testing all edge cases upfront
- Testing implementation details
- Slowing down feature development

**Under-testing critical paths:**
- Skipping main user flow tests
- Not testing business logic
- Ignoring core feature validation

**Brittle tests:**
- Testing internal implementation
- Coupling tests to code structure
- Not mocking external dependencies

## Quick Reference

| Scenario                        | Action                         |
| ------------------------------- | ------------------------------ |
| Implementing new feature        | Test critical path only        |
| User requests edge case testing | Add those specific tests       |
| Non-critical utility function   | Skip testing unless requested  |
| Core business calculation       | Always test                    |
| Error handling                  | Defer unless business-critical |
| Integration point               | Test at completion             |
