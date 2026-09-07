---
paths:
  - "**/*.go"
---

## Go Development Standards

Use the module/workspace, Go version, and toolchain declared by the project. Follow its package layout; `cmd/`, `internal/`, and `pkg/` are conventions, not a required scaffold.

### Tooling

Typical checks, when applicable:

```bash
go test ./...
go vet ./...
go test -race ./...
```

Use `gofmt` on changed Go files and the configured linter if present. Run the race detector for concurrency-sensitive work or when required by the project. Run `go mod tidy` after relevant dependency changes and inspect its diff. Do not run blanket `go get -u ./...` as routine verification.

### Implementation

- Follow Go naming and documentation conventions, including conventional initialisms such as `HTTPServer` and `userID`.
- Handle errors deliberately. Wrap with useful context and `%w` when callers should inspect the original error. Use sentinel errors or typed errors where their contract warrants them.
- Document intentional ignored errors where the reason is non-obvious; do not mechanically add error plumbing for operations whose failure cannot matter.
- Pass `context.Context` first to operations that need cancellation/deadlines. Propagate it rather than hiding request cancellation behind a new background context.
- Arrange resource cleanup with `defer` when appropriate, and check close/flush errors when they affect durability.
- Keep interfaces at useful consumer boundaries; do not add them solely to match a template.
- Use table-driven tests and `t.Run` where multiple cases share a contract. Keep tests isolated and check cancellation, failure, and concurrency behaviour that the change affects.

Use `testing.md` for test scope. A generic rule does not authorize reorganizing files or changing dependency versions.
