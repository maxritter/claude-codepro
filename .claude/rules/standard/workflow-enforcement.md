# Workflow Enforcement Rules

## ⭐ MANDATORY: Task Management for Non-Spec Work

**Outside of /spec workflows, ALWAYS use task management tools to track work.**

This prevents forgetting steps, manages dependencies, and shows the user clear progress.

### When to Create Tasks (DO IT!)

| Situation | Action |
|-----------|--------|
| User asks for 2+ things | Create a task for each |
| Work has multiple steps | Create tasks with dependencies |
| Complex investigation | Create tasks for each area to explore |
| Bug fix with verification | Task for fix, task for test, task for verify |
| Any non-trivial request | Break it down into tasks FIRST |

### Task Management Tools

| Tool | Purpose | Use When |
|------|---------|----------|
| `TaskCreate` | Create new task | Starting any piece of work |
| `TaskList` | See all tasks | Check progress, find next task |
| `TaskGet` | Full task details | Need description/context |
| `TaskUpdate` | Change status/deps | Starting, completing, or blocking tasks |

### Task Workflow

```
1. User makes request
2. IMMEDIATELY create tasks (before any other work)
3. Set up dependencies with addBlockedBy
4. Mark task in_progress when starting
5. Mark task completed when done
6. Check TaskList for next task
7. Repeat until all tasks completed
```

### Dependencies - Don't Forget Them!

**Use `addBlockedBy` to ensure correct order:**

```
Task 1: Research existing code
Task 2: Implement feature [blockedBy: 1]
Task 3: Write tests [blockedBy: 2]
Task 4: Update documentation [blockedBy: 2]
```

Tasks 3 and 4 won't show as ready until Task 2 completes.

### Example: User asks "Fix the login bug and add password reset"

```
1. TaskCreate: "Fix login bug"
2. TaskCreate: "Add password reset feature"
3. TaskCreate: "Test both features" [blockedBy: 1, 2]
4. Start task 1, mark in_progress
5. Complete task 1, mark completed
6. TaskList → see task 2 is ready
7. Continue...
```

### Why This Matters

- **Never forget a step** - Tasks are your checklist
- **User sees progress** - Clear status visibility
- **Dependencies prevent mistakes** - Can't skip ahead
- **Context handoffs work** - Tasks persist across sessions
- **Accountability** - Clear record of what was done

## ⛔ ABSOLUTE BANS

### No Sub-Agents
**NEVER use the Task tool to spawn sub-agents.**
- Use `Read`, `Grep`, `Glob`, `Bash` directly for exploration
- Sub-agents lose context and make mistakes
- Note: Task management tools (TaskCreate, TaskList, etc.) are ALLOWED and preferred

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

## No Stopping - Automatic Continuation

**The ONLY user interaction point is plan approval.**

- Never stop after writing continuation file - trigger clear immediately
- Never wait for user acknowledgment before session handoff
- Execute session continuation in a single turn: write file → trigger clear
- Only ask user if a critical architectural decision is needed
