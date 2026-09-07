## Code Review Reception

Applies to feedback from users, the `/code-review` skill, review agents, and external tools like CodeRabbit.

Read the feedback and verify each finding against the current code, requirements, and available evidence. Resolve clear, authorized items while investigating ambiguous ones; ask only when an unresolved decision materially changes the fix. Prioritize correctness and security, and batch related fixes and checks when they share a cause.

Preserve a review tool's structured findings, identifiers, severity, locations, and evidence when passing results to another consumer. Use its native schema-backed output when available; a user-facing summary can accompany the result only where the output contract permits it. Malformed output is not a clean review.

### How much to trust the source

| Source | Approach |
|--------|----------|
| **User** | Trusted — implement after understanding. Still ask if scope is unclear. |
| **External reviewers** | Verify first: is it correct *for this codebase*, does it break something, is there a reason the code is the way it is, does it conflict with the user's earlier decisions? If it conflicts, stop and discuss before changing anything. |
| **Workflow reviews** (`spec-review`, `changes-review`, `/code-review`, Codex companion) | Validate findings before acting; labels are priorities, not proof. Fix confirmed in-scope defects under the invoking workflow's finding-to-action contract. Explain rejected or unresolved findings with evidence. Suggestions still need a task-relevant benefit; being quick is insufficient. |

### Verify before you agree

When a reviewer requests additional implementation, inspect usage and the required contract. Lack of current callers can expose speculative work, but public APIs, generated consumers, or a requested new capability may still require it.

Push back with technical reasoning whenever the suggestion breaks existing behaviour, misses context the reviewer didn't have, is wrong for this stack, or contradicts an architectural decision the user already made. If you pushed back and were wrong, say so factually in one line and move on.

**Respond with the technical substance, not affirmation.** State the requirement, or the fix and what changed. "You're absolutely right", "great point", "thanks for catching that" are all noise where a description of the change belongs.
