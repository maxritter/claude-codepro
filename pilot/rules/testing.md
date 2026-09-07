## Testing

### Default Posture: Parsimonious

Reuse existing behavioural coverage first. Add or extend tests for changed behaviour and credible failure modes; organize them around contracts rather than production classes or methods. There is no global quota for test counts, class counts, or coverage percentages. Project requirements and explicitly selected workflows may define stronger gates.

Tests should survive behaviour-preserving refactors. Reversible, low-impact edits do not need new tests that merely mirror the implementation. Documentation, formatting, and static copy normally use existing validation or rendered inspection; configuration and dependency changes need checks of the behaviour they can affect.

### Regression testing and TDD

For bug fixes and meaningful behaviour changes, establish a focused failing check before production edits when practical. Confirm it fails for the intended reason, implement the change, and run it again. Use existing tests or a reproducible command when they already expose the defect.

If an automated reproducer is impractical, capture the actual failing interaction or artifact and explain the coverage limit. If implementation already exists, verify regression sensitivity in an isolated copy or with a controlled mutation; do not discard work to reenact TDD. An explicitly selected workflow's recorded RED requirement still applies unless the user changes that requirement.

The optional `Trivial:` plan field records why existing verification is sufficient and names that check. It is evidence to assess against the actual change, not a line-count exemption or proof of correctness. Do not use it to conceal missing regression evidence.

### Choosing useful checks

- Unit checks exercise isolated behaviour. Use fakes or mocks for costly, unavailable, or nondeterministic boundaries; temporary files or in-process collaborators can be simpler and more faithful than mocking every call.
- Integration checks exercise contracts that doubles cannot establish, including database semantics, subprocess invocation, serialization, and third-party adapters. Keep them isolated from user data and external mutations.
- E2E checks exercise the affected user workflow. Browser or device interaction evidence is required for claims about the rendered UI; see `browser-automation.md` and `mobile-development.md`.
- Cover material security, data-integrity, business-rule, and error paths explicitly. Use coverage reports to find gaps, not to manufacture tests for a number.
- When a dependency changes, inspect existing consumer tests for isolation assumptions and exercise the real integration where relevant.

Run focused checks, then the repository's required suite. Once those pass, repeat or broaden only after relevant edits, failures, environment changes, or unresolved concerns. Results remain valid for the unchanged artifact and environment across messages.

### Assertions

Assert the observable contract using independently justified expected values. A test should fail for a plausible defect in that contract. Inspect relevant boundaries such as empty input, invalid input, authorization, state changes, and error handling; do not add cases mechanically where the contract excludes them.

Avoid expectations copied from the implementation, redundant cases on the same path, and assertions that only prove a mock was installed. Interaction assertions are appropriate when the interaction itself is the contract, such as preventing a write or sending the correct request.

Source-text assertions rarely prove runtime behaviour. Prefer executing the build, transform, parser, command, or rendered artifact. Exact text checks can protect an actual syntax or packaging contract; they cannot establish that a model follows prose instructions. Keep tests independent and avoid adding production APIs solely to expose internals to a test.

### Failing tests outside the request

Reproduce and attribute a failure before calling it pre-existing. Fix failures caused by the change or required to validate the requested result. Report unrelated failures with evidence, and obtain authority before expanding into unrelated repairs. Do not claim a broad suite passed while it contains failures.
