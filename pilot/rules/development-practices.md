## Development Practices

### Change discipline

Read the relevant code and project instructions before editing. Make reasonable, reversible assumptions and continue; ask only when a missing decision materially changes the requested result.

- Keep each changed line traceable to the request. Preserve unrelated work and remove code made unused by your own changes.
- Prefer the existing architecture, standard library, platform facilities, and installed dependencies when they meet the requirement. Add abstractions or dependencies for demonstrated needs; line count and file count are not correctness criteria.
- Preserve existing public behaviour and compatibility contracts unless the task authorizes changing them. Do not upgrade language versions, frameworks, tooling, or architecture incidentally.
- Keep security, trust-boundary validation, accessibility, and protection against data loss intact. Simplicity must still satisfy the whole requested outcome.
- For a deliberate simplification with a known ceiling, leave a `SHORTCUT:` comment naming that ceiling and its upgrade trigger. Ordinary straightforward code needs no debt marker.
- Follow the existing encoding and naming conventions. Keep intentional Unicode in UI copy, localization, and data literals; investigate suspicious invisible characters or identifier confusables without mechanically converting text to ASCII.

### Exploration and impact

Use `mcp-servers.md` for tool routing. Read named paths directly, use Semble for intent and CodeGraph for structural relationships when available and relevant, and use exact search for exhaustive references. Tool availability or a fixed call budget must not determine when the investigation is complete.

Before changing shared behaviour, inspect relevant callers and contracts. An index is a navigation aid, not complete reachability proof: exports, callbacks, registries, routes, decorators, reflection, configuration, tests, and generated consumers can keep a zero-caller symbol live.

`/cleanup` is report-only: it installs nothing, changes nothing, and does not treat test-only code as automatically dead. Removing pre-existing code needs evidence that its removal belongs to the authorized request.

### Design and performance

Organize files and components by coherent responsibilities and project conventions. Split when boundaries improve comprehension or reuse in the current task; do not refactor to meet a global line limit.

Avoid redundant work on hot paths and inspect actual cost before adding caches or memoization. Account for invalidation, memory use, and framework/compiler optimizations. A cache is not proof of a performance improvement; use representative measurements when making that claim.

Use the project's configured formatter, linter, compiler, and test commands. Fix failures caused by the change and attribute unrelated baseline failures instead of rewriting user work or suppressing diagnostics.

### Debugging

Reproduce the reported failure and trace it to a concrete cause before choosing a fix. Read the complete error, relevant diff, and data flow; minimize the reproduction when that helps discriminate causes. Compare working implementations when useful.

When the cause remains uncertain, form falsifiable hypotheses and test the most informative one with a targeted observation or controlled change. Repeated failed attempts mean the current explanation needs revision; they do not prove an architectural defect or authorize a rewrite.

Add regression evidence as described in `testing.md`, fix the cause at the appropriate boundary, and run the affected checks. Avoid symptom-hiding fallbacks. Revert only your own experimental edits when appropriate, preserving concurrent work; do not discard a dirty worktree as a debugging step.

For asynchronous operations, wait for the actual condition with a bounded timeout and useful failure output. Choose a polling interval suitable for the operation or use events. Fixed timing is appropriate when timing itself is under test.

### Merge conflicts

Resolve hunk by hunk while preserving both intents. Read the reasons for each side when the code is insufficient; regenerate lockfiles and build output using the project's tools. Ask only for genuinely incompatible intents that the authorized merge goal cannot resolve. Run the affected project checks afterwards.

Do not abort an in-progress merge or rebase on your own initiative. Staging, committing, and continuing a rebase require the corresponding git-write authority.

### Git operations

Read git state freely. Preserve unrelated staged and unstaged work; file-edit authority does not grant permission to overwrite, discard, stage, commit, push, or move it. Existing authorization persists across the session.

- Git writes such as `add`, `commit`, `push`, `pull`, `merge`, `rebase`, `reset`, `stash`, and branch switches need authority for that operation. “Fix this bug” does not authorize a commit.
- Use targeted edits for requested reversions. Never discard all unstaged changes or use a destructive checkout/reset to undo a local mistake.
- Preserve the user's staging decisions. Before an authorized commit, inspect the exact staged set; do not silently unstage files or include unrelated work.
- Do not force-add ignored files or force-update history without explicit authorization.
- Respect the active branch. Create or switch branches only when authorized by the user or an explicitly selected workflow's worktree option.
- Use upstream tracking when pushing a new branch. Check the intended remote and branch first.
- Do not set a repository-local git identity as an incidental workaround. For an isolated temporary repository, pass a temporary identity per command with `git -c`; normal commits use the user's configured identity.
