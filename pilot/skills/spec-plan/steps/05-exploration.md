## Step 5: Exploration

Start from the Step 3 Workspace Scan. Read the affected source and relevant tests or nearby patterns until the plan can name the required changes and how they will be verified.

- Use Semble for unresolved intent or pattern questions, CodeGraph for non-local runtime relationships, and exact-text search when every literal occurrence matters. Consult authoritative library documentation when an API or behavior is uncertain.
- Check callers and integration points when a changed contract has effects beyond the files already read. Skip graph traversal for local or prose-only changes whose effects are already established.
- Batch independent reads and searches. Delegate only bounded, independent areas whose parallel investigation or context isolation materially helps; keep one coherent plan and do not duplicate a completed investigation.
- Reuse verified findings. Stop broad exploration once each task has an evidenced location, approach, dependencies, and verification method. Investigate remaining uncertainty only when it could change those decisions.

Record consequential assumptions and unresolved questions. Do not replace missing evidence with a forced confidence level or trim the requested scope to meet a tool-call or context quota.
