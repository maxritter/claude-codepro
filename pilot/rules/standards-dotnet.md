---
paths:
  - "**/*.cs"
  - "**/*.csproj"
  - "**/*.sln"
  - "**/*.slnx"
---

## .NET / C# Development Standards

### Toolchain and checks

Follow `global.json`, target frameworks, solution format, central package management, and repository scripts. Preserve configured nullable/analyzer/warning policies; do not enable new global settings or change SDK versions as incidental cleanup.

Typical commands, adapted to the installed SDK and project:

```bash
dotnet build
dotnet test
dotnet format --verify-no-changes
```

Use configured test filters and the relevant solution/project. Keep sufficient diagnostic output for failures and scope formatting/dependency edits to the authorized change.

### Implementation

- Prefer `Task`/`Task<T>` for asynchronous operations; `async void` belongs only to required event-handler signatures. Avoid blocking async work and propagate cancellation where relevant.
- Use the project's managed HTTP-client lifetime, such as factory-created clients or properly configured long-lived clients; do not create and dispose a new client per request.
- Catch specific exceptions when recovery is possible. Re-throw with `throw;` to preserve the stack.
- Use structured logging without exposing secrets or sensitive payloads.
- Follow the existing ASP.NET routing, options, authorization, and error contracts. Use production error handling that does not expose internal stack traces.
- Respect nullable contracts. A null-forgiving operator or suppression needs an established invariant, not merely a failing build.

### Testing

Use existing dependency seams and fixtures. Add interfaces or abstraction packages only for an architectural need, not automatically for every file or clock access. Temporary files and controllable clocks can be appropriate for isolated checks.

Use `WebApplicationFactory` when the project uses ASP.NET integration tests. Database tests must represent the semantics being verified: an in-memory provider or mocked repository cannot establish production query translation, constraints, or transaction behaviour. Prefer the existing fixture using the target database for those contracts.

Dispose resources and avoid mutable shared state. Prefer event/task completion to arbitrary delays in asynchronous tests. Follow `testing.md` for focused checks and required suites.
