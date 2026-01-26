---
name: Go Standards
description: Apply Go development standards including module management, go test testing, gofmt/go vet/golangci-lint code quality, idiomatic error handling, and self-documenting code practices. Use this skill when working with Go backend code, managing dependencies, running tests, or ensuring code quality. Apply when installing packages, writing tests, formatting code, handling errors, organizing imports, or deciding whether to create new files vs. extending existing ones. Use for any Go development task requiring adherence to tooling standards and best practices.
---

# Go Standards

**Core Rule:** Use Go modules for dependencies, go test for testing, gofmt + go vet + golangci-lint for quality. Write idiomatic Go with explicit error handling.

## When to use this skill

- When creating or managing Go modules and dependencies
- When writing or running tests in Go projects
- When formatting Go code or fixing linting issues
- When implementing error handling patterns
- When organizing package structure
- When deciding whether to create a new Go file or extend existing ones
- When setting up code quality checks (formatting, vetting, linting)
- When ensuring code follows Go idioms and best practices

## Module Management

**Use Go modules for all dependency management:**

```bash
# Initialize a new module
go mod init github.com/org/project

# Dependencies are added automatically via imports
# Then run tidy to update go.mod and go.sum
go mod tidy

# Update all dependencies
go get -u ./...

# Update specific dependency
go get -u github.com/pkg/name@latest

# Verify dependencies
go mod verify

# Clean module cache
go clean -modcache
```

**Module file structure:**
- `go.mod` - Module definition and direct dependencies
- `go.sum` - Cryptographic checksums for dependencies

## Testing with go test

**Run tests using standard go test:**

```bash
go test ./...                              # All tests
go test ./pkg/...                          # Tests in pkg/ and subdirs
go test -v ./...                           # Verbose output (debugging only)
go test -short ./...                       # Skip long-running tests
go test -race ./...                        # With race detector
go test -cover ./...                       # With coverage summary
go test -coverprofile=coverage.out ./...   # Generate coverage file
go tool cover -html=coverage.out           # View coverage in browser
```

**Test file naming:** Tests go in `*_test.go` files alongside the code they test.

**Test function naming:** `func TestFunctionName(t *testing.T)`

```go
func TestProcessOrder(t *testing.T) {
    order := Order{ID: "123", Amount: 100}
    result, err := ProcessOrder(order)

    if err != nil {
        t.Fatalf("unexpected error: %v", err)
    }
    if result.Status != "completed" {
        t.Errorf("got status %q, want %q", result.Status, "completed")
    }
}
```

**Table-driven tests:** Preferred for testing multiple cases:

```go
func TestValidateEmail(t *testing.T) {
    tests := []struct {
        name    string
        email   string
        wantErr bool
    }{
        {"valid email", "user@example.com", false},
        {"missing @", "userexample.com", true},
        {"empty", "", true},
    }

    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            err := ValidateEmail(tt.email)
            if (err != nil) != tt.wantErr {
                t.Errorf("ValidateEmail(%q) error = %v, wantErr %v", tt.email, err, tt.wantErr)
            }
        })
    }
}
```

## Code Quality Tools

**Formatting with gofmt:**
```bash
gofmt -w .           # Format all Go files in place
gofmt -d .           # Show diff without modifying
goimports -w .       # Format + organize imports
```

**Static analysis with go vet:**
```bash
go vet ./...         # Check for common mistakes
```

**Comprehensive linting with golangci-lint:**
```bash
golangci-lint run              # Run all enabled linters
golangci-lint run --fix        # Auto-fix where possible
golangci-lint run --fast       # Quick check (fewer linters)
```

**Run quality checks before marking work complete.**

## Error Handling

**Always handle errors explicitly. Never ignore them.**

```go
// REQUIRED - handle the error
result, err := doSomething()
if err != nil {
    return fmt.Errorf("doing something: %w", err)
}

// FORBIDDEN - ignoring errors
result, _ := doSomething()  // Never do this
```

**Error wrapping:** Add context when propagating errors:

```go
func ProcessUser(userID string) error {
    user, err := fetchUser(userID)
    if err != nil {
        return fmt.Errorf("fetching user %s: %w", userID, err)
    }

    if err := validateUser(user); err != nil {
        return fmt.Errorf("validating user %s: %w", userID, err)
    }

    return nil
}
```

**Custom errors:** Use for domain-specific error types:

```go
var ErrNotFound = errors.New("not found")
var ErrInvalidInput = errors.New("invalid input")

// Check with errors.Is
if errors.Is(err, ErrNotFound) {
    // handle not found
}
```

## Code Style

**Naming conventions:**

| Type | Convention | Example |
|------|------------|---------|
| Packages | lowercase, single word | `http`, `json`, `user` |
| Exported | PascalCase | `ProcessOrder`, `UserService` |
| Unexported | camelCase | `processOrder`, `userService` |
| Acronyms | ALL CAPS | `HTTPServer`, `XMLParser`, `ID` |
| Interfaces | -er suffix (often) | `Reader`, `Writer`, `Handler` |

**Comments for exported functions:**

```go
// ProcessOrder validates and processes the given order.
// It returns ErrInvalidOrder if the order is malformed.
func ProcessOrder(order Order) error {
    // implementation
}
```

**Import organization:** Standard library, then third-party, then local:

```go
import (
    "context"
    "fmt"
    "net/http"

    "github.com/gin-gonic/gin"
    "go.uber.org/zap"

    "github.com/myorg/myproject/internal/service"
)
```

## Common Patterns

**Context propagation:** Always pass context as first parameter:

```go
func ProcessRequest(ctx context.Context, req Request) (Response, error) {
    // Use ctx for cancellation, timeouts, and request-scoped values
    result, err := db.QueryContext(ctx, query)
    if err != nil {
        return Response{}, err
    }
    return Response{Data: result}, nil
}
```

**Defer for cleanup:**

```go
func ReadFile(path string) ([]byte, error) {
    f, err := os.Open(path)
    if err != nil {
        return nil, err
    }
    defer f.Close()  // Guaranteed to run on function exit

    return io.ReadAll(f)
}
```

**Struct initialization:**

```go
// Named fields (preferred for clarity)
user := User{
    ID:    "123",
    Name:  "Alice",
    Email: "alice@example.com",
}

// Zero values are valid - use them
var count int          // 0
var name string        // ""
var items []string     // nil (valid for append)
```

## File Organization

**Prefer editing existing files over creating new ones.**

Before creating a new Go file, ask:
1. Can this fit in an existing package?
2. Is there a related file to extend?
3. Does this truly need to be separate?

**Standard project structure:**

```
project/
├── cmd/                  # Main applications
│   └── server/
│       └── main.go
├── internal/             # Private packages (can't be imported externally)
│   ├── handler/
│   ├── service/
│   └── repository/
├── pkg/                  # Public packages (can be imported)
│   └── api/
├── go.mod
└── go.sum
```

## Verification Checklist

Before marking Go work complete:

- [ ] Code formatted: `gofmt -w .`
- [ ] Tests pass: `go test ./...`
- [ ] Static analysis clean: `go vet ./...`
- [ ] Linting clean: `golangci-lint run`
- [ ] All errors handled (no `_` for errors)
- [ ] Dependencies tidy: `go mod tidy`
- [ ] Context propagated where needed
- [ ] Exported functions have comments

## Quick Reference

| Task                 | Command                        |
| -------------------- | ------------------------------ |
| Init module          | `go mod init module-name`      |
| Add dependency       | `go get github.com/pkg/name`   |
| Run tests            | `go test ./...`                |
| Run with coverage    | `go test -cover ./...`         |
| Format code          | `gofmt -w .`                   |
| Static analysis      | `go vet ./...`                 |
| Lint                 | `golangci-lint run`            |
| Tidy dependencies    | `go mod tidy`                  |
| Build                | `go build ./...`               |
| Run                  | `go run ./cmd/app`             |
