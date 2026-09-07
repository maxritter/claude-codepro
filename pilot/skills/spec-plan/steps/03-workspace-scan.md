## Step 3: Workspace Scan (before clarification)

Ground the plan in the current workspace before asking the user about repository facts. This also applies when `PILOT_PLAN_QUESTIONS_ENABLED=false`.

### 3.1: Orient on the affected area

Read concrete paths or an identified diff directly. When the location is unknown, use Semble for intent search; use `codegraph_explore` when runtime entry points, callers, or component relationships are the uncertainty. Use the exposed tool schemas and available fallbacks. A docs or config change does not need a call graph merely because it touches several files.

Batch independent reads or searches. Follow relevant results to source; if a result is irrelevant, change the query or tool based on what is missing rather than repeating the same search.

### 3.2: Capture working context

Keep a concise Workspace Scan in context:

```
Workspace Scan
- Entry points: [file:line, ...]
- Related symbols: [Name @ file:line, ...]
- Similar patterns: [file:line — relevant pattern]
- Greenfield?: [yes | no | unresolved]
```

Use `Greenfield?: yes` only when inspected workspace evidence establishes that the requested component does not exist. Empty tool results alone are not proof of absence.

### 3.3: Reuse downstream

Step 4 uses these findings to avoid unnecessary questions. Step 5 deepens only unresolved areas; it does not repeat this scan. Step 6 grounds consequential choices in actual components. The scan is working context; Step 9 writes the relevant findings into the plan.
