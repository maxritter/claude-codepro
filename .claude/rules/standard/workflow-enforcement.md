# Workflow Enforcement Rules

## ⛔ ABSOLUTE BANS

### No Sub-Agents
**NEVER use the Task tool. Period.**
- Use `Read`, `Grep`, `Glob`, `Bash` directly
- Sub-agents lose context and make mistakes

### No Background Tasks
**NEVER use `run_in_background=true`.**
- Run commands synchronously
- Use `timeout` parameter if needed (up to 600000ms)

### No Built-in Plan Mode
**NEVER use `EnterPlanMode` or `ExitPlanMode` tools.**
- Use `/spec` command instead
- Built-in plan mode is incompatible with this workflow

## /spec Workflow

The `/spec` command handles everything in one flow:

```
Plan → Approve → Implement → Verify → Done
         ↑                      ↓
         └──── if issues ───────┘
```

**Status values in plan files:**
- `PENDING` - Awaiting implementation (or fixes from verify)
- `COMPLETE` - All tasks done, ready for verification
- `VERIFIED` - All checks passed, workflow complete

## Task Completion Tracking

**Update the plan file after EACH task:**
1. Change `[ ]` to `[x]` for completed task
2. Update counts: increment Done, decrement Left
3. Do this IMMEDIATELY, not at the end

## Quality Over Speed

- Context warnings are informational, not emergencies
- Finish current task properly, then hand off
- Never skip tests or cut corners
- A clean handoff beats rushed completion
