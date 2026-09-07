---
paths:
  - "**/*.py"
---

## Python Development Standards

### Environment and tools

Follow the project's declared Python versions, environment manager, lockfile, and scripts. Prefer `uv` for Pilot's own Python work and new projects without an existing choice; do not migrate a working Poetry, pip-tools, or other managed environment incidentally.

For a uv-managed project, `uv add <package>` updates declared dependencies and the lockfile; `uv pip install` changes the environment without declaring a project dependency. Use the appropriate operation for the task.

Typical commands, when configured:

```bash
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run basedpyright
```

Read configuration before assuming a source directory, type checker, pytest markers, coverage plugin, or CLI option. Retain enough failure output to diagnose errors. Scope automatic fixes/formatting to authorized changes.

### Implementation

- Use type hints for public interfaces and non-obvious contracts, consistent with project conventions and supported Python syntax.
- Follow configured import ordering and formatting.
- Document behaviour, invariants, or workarounds the signature does not explain; avoid boilerplate docstrings.
- Catch specific exceptions when recovery is possible. Preserve useful failure context; avoid swallowing failures or logging and re-raising at every layer.
- Use context managers for owned resources and existing path-handling conventions.
- Keep mutable defaults and shared test state from leaking between calls or tests.

Run the configured focused checks and required suite. Cover changed behaviour and relevant failure paths as described in `testing.md`; do not add numeric file-size or coverage gates from this generic rule.
