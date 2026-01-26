---
name: Testing Standards
description: Prevent common testing anti-patterns that undermine test effectiveness and code quality by ensuring tests verify real behavior rather than mock behavior, keeping production code free from test-only pollution, and enforcing thoughtful mocking strategies. Use this skill when writing or modifying any test files (.test.ts, .test.js, .spec.ts, _test.py, test_*.py, *_test.go, *_spec.rb), when adding mock objects, stubs, spies, or test doubles to test suites, when considering adding methods or properties to production classes that are only called from test code, when setting up complex test fixtures or test data, when tests are failing and you're tempted to adjust mocks to make them pass, when deciding how to isolate code under test from external dependencies, when implementing dependency injection or test seams, during code reviews when reviewing test implementation and mocking strategies, when refactoring tests that have become brittle or hard to maintain, when test setup code is becoming longer than the actual test assertions, or when choosing between integration tests with real components versus unit tests with mocks.
---

# Testing Standards

**Rule:** Test real behavior, not mock behavior. Never pollute production code with test-only methods.

## When to use this skill

- When writing new test files or test cases in any testing framework (Jest, Vitest, pytest, RSpec, Go testing, JUnit)
- When modifying existing tests that use mocks, stubs, spies, or test doubles
- When considering whether to add a method or property to a production class that would only be used in tests
- When test setup involves creating mock objects or configuring mock behavior
- When deciding between testing with real dependencies versus mocked dependencies
- When tests are failing and you need to determine if the issue is in the code or in how mocks are configured
- When implementing fixtures, test data builders, or test utilities
- During test code reviews to ensure testing best practices are followed
- When test files contain assertions that check for mock existence (e.g., `expect(screen.getByTestId('component-mock'))`)
- When refactoring production code and tests need to be updated accordingly
- When choosing isolation strategies for unit tests versus integration tests

## Core Principles

1. **Mocks are isolation tools, not test subjects** - Assert on real behavior, not mock existence
2. **Production code stays pure** - Test utilities handle test-specific needs
3. **Understand before mocking** - Know what side effects you're removing
4. **Complete mocks or none** - Partial mocks create silent failures
5. **TDD prevents anti-patterns** - Write failing tests first to avoid testing mocks

## Anti-Pattern 1: Testing Mock Behavior

**Violation:**
```typescript
// ❌ BAD: Asserting on mock existence
test('renders sidebar', () => {
  render(<Page />);
  expect(screen.getByTestId('sidebar-mock')).toBeInTheDocument();
});
```

**Why wrong:**
- Verifies mock works, not component behavior
- Test passes with mock present regardless of real functionality
- Provides zero confidence about production behavior

**Fix:**
```typescript
// ✅ GOOD: Test real component
test('renders sidebar', () => {
  render(<Page />);  // Use real sidebar
  expect(screen.getByRole('navigation')).toBeInTheDocument();
});

// OR if isolation required: Test Page's behavior, not mock presence
test('renders page with sidebar slot', () => {
  render(<Page />);
  expect(screen.getByTestId('sidebar-container')).toBeInTheDocument();
});
```

**Detection rule:**
```
IF assertion contains '*-mock' OR checks mock.toHaveBeenCalled():
  Ask: "Am I testing real behavior or mock existence?"
  IF testing mock existence → STOP, delete assertion or unmock
```

## Anti-Pattern 2: Test-Only Methods in Production Code

**Violation:**
```typescript
// ❌ BAD: Method only called from tests
class Session {
  async destroy() {
    await this._workspaceManager?.destroyWorkspace(this.id);
  }
}

afterEach(() => session.destroy());
```

**Why wrong:**
- Pollutes production API with test-specific code
- Risk of accidental production calls
- Violates YAGNI (You Aren't Gonna Need It)
- Confuses class responsibilities

**Fix:**
```typescript
// ✅ GOOD: Test utilities handle cleanup
// Session class has no destroy() method

// In test-utils.ts
export async function cleanupSession(session: Session) {
  const workspace = session.getWorkspaceInfo();
  if (workspace) {
    await workspaceManager.destroyWorkspace(workspace.id);
  }
}

// In tests
afterEach(() => cleanupSession(session));
```

**Detection rule:**
```
BEFORE adding method to production class:
  1. Search codebase: Is this method only called from test files?
  2. Ask: Does this class own this resource's lifecycle?

  IF only used in tests OR class doesn't own lifecycle:
    STOP - Create test utility function instead
```

## Anti-Pattern 3: Mocking Without Understanding Dependencies

**Violation:**
```typescript
// ❌ BAD: Mock removes side effect test depends on
test('detects duplicate server', () => {
  vi.mock('ToolCatalog', () => ({
    discoverAndCacheTools: vi.fn().mockResolvedValue(undefined)
  }));

  await addServer(config);
  await addServer(config);  // Should throw but won't - config never written!
});
```

**Why wrong:**
- Mocked method writes config that duplicate detection needs
- Over-mocking "to be safe" breaks test logic
- Test passes/fails for wrong reasons

**Fix:**
```typescript
// ✅ GOOD: Mock only external/slow operations
test('detects duplicate server', () => {
  vi.mock('MCPServerManager'); // Mock slow server startup only

  await addServer(config);  // Config written ✓
  await addServer(config);  // Duplicate detected ✓
});
```

**Decision process:**
```
BEFORE mocking:
  1. List method's side effects (DB writes, file I/O, API calls, state changes)
  2. Identify what test actually needs (duplicate detection needs config write)
  3. Mock ONLY external/slow operations, preserve test dependencies

  IF unsure what test needs:
    Run with real implementation FIRST
    Observe required behavior
    THEN mock minimally at lowest level

  Red flags indicating wrong approach:
    - "Mock this to be safe"
    - "Might be slow, better mock"
    - Can't explain why mocking
    - Mock setup longer than test
```

## Anti-Pattern 4: Incomplete Mock Data Structures

**Violation:**
```typescript
// ❌ BAD: Only fields you think you need
const mockResponse = {
  status: 'success',
  data: { userId: '123', name: 'Alice' }
  // Missing: metadata field
};

// Later: Silent failure when code accesses response.metadata.requestId
```

**Why wrong:**
- Partial mocks hide structural assumptions
- Downstream code may depend on omitted fields
- Tests pass, production fails
- False confidence in test coverage

**Fix:**
```typescript
// ✅ GOOD: Complete structure matching real API
const mockResponse = {
  status: 'success',
  data: { userId: '123', name: 'Alice' },
  metadata: { requestId: 'req-789', timestamp: 1234567890 }
};
```

**Mandatory process:**
```
BEFORE creating mock data:
  1. Check API documentation or real response examples
  2. Include ALL fields from actual structure
  3. Use realistic values (not null/undefined unless API returns them)
  4. Verify mock matches real schema completely

  IF uncertain about structure:
    - Examine real API response
    - Include all documented fields
    - Add comment linking to API docs
```

## Anti-Pattern 5: Tests as Afterthought

**Violation:**
```
Implementation complete → No tests → "Ready for review"
```

**Why wrong:**
- Testing is part of implementation, not optional
- Violates TDD workflow
- Cannot claim completion without tests

**Fix - TDD cycle:**
```
1. Write failing test (RED)
2. Implement minimal code (GREEN)
3. Refactor
4. THEN claim complete
```

## When Mocks Signal Deeper Issues

**Warning signs:**
- Mock setup > 50% of test code
- Mocking everything to make test pass
- Mocks missing methods real components have
- Test breaks when mock implementation changes
- Can't explain why each mock is needed

**Question to ask:** "Should this be an integration test with real components?"

Complex mocks often indicate integration tests would be simpler and more valuable.

## How TDD Prevents These Anti-Patterns

**TDD workflow naturally avoids anti-patterns:**

1. **Write test first** → Forces clarity on what you're testing
2. **Watch it fail** → Confirms test verifies real behavior, not mocks
3. **Minimal implementation** → Prevents test-only methods
4. **Real dependencies first** → See actual needs before mocking

**Key insight:** If you're testing mock behavior, you violated TDD by adding mocks before seeing test fail against real code.

## Detection Checklist

Before finalizing any test, verify:

- [ ] No assertions on mock existence (`*-mock` test IDs, `toHaveBeenCalled` without behavior verification)
- [ ] No methods in production classes only called from test files
- [ ] Understand what each mock removes (side effects, dependencies, behavior)
- [ ] Mock data structures complete (all fields from real API/response)
- [ ] Tests written before or during implementation (not after)
- [ ] Mock setup < 50% of test code (if more, consider integration test)
- [ ] Can explain necessity of each mock

## Quick Reference

| Anti-Pattern          | Detection Signal                              | Fix                                     |
| --------------------- | --------------------------------------------- | --------------------------------------- |
| Testing mock behavior | Assertions on `*-mock` elements or mock calls | Test real component or remove mock      |
| Test-only methods     | Method only in test file searches             | Move to test utilities                  |
| Blind mocking         | Can't explain mock purpose                    | Understand dependencies, mock minimally |
| Incomplete mocks      | Missing fields from real structure            | Include all documented fields           |
| Tests afterthought    | Implementation before tests                   | Follow TDD: test first                  |
| Over-complex mocks    | Setup > 50% of test                           | Use integration test                    |

## Red Flags - Stop and Reconsider

When you encounter these, stop and reassess your approach:

- Assertions check for `*-mock` test IDs
- Methods only called in test files
- Mock setup > 50% of test code
- Test fails when you remove mock
- Can't explain why mock is needed
- Mocking "just to be safe"
- Mock missing methods real component has

## Summary

**Mocks isolate code under test from external dependencies. They are not the subject of tests.**

**When uncertain:**
1. Write test with real dependencies first
2. Identify what's slow or external (API calls, DB queries, file I/O)
3. Mock only that specific dependency at lowest level
4. Verify test still validates real behavior, not mock presence
