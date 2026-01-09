# Context Continuation - Endless Mode for All Sessions

**Rule:** When context reaches critical levels, save state and continue seamlessly in a new session.

## How It Works

This enables "endless mode" for any development session, not just /spec workflows:

1. **Context Monitor** warns at 80% and 90% usage
2. **You save state** to Claude Mem before clearing
3. **Wrapper restarts** Claude with continuation prompt
4. **Claude Mem injects** your saved state
5. **You continue** where you left off

## When Context Warning Appears

When you see the context warning (80% or 90%), take action:

### At 80% - Prepare for Continuation

- Wrap up current task if possible
- Avoid starting new complex work
- Consider saving progress observation

### At 90% - Mandatory Continuation Protocol

**Step 1: Write Session Summary to File (GUARANTEED BACKUP)**

First, write the summary to `/tmp/claude-continuation.md` using the Write tool. This ensures the next session can read it even if Claude Mem doesn't capture it.

```markdown
# Session Continuation

**Task:** [Brief description of what you were working on]

**Files Modified:**
- `path/to/file1.py` - [what was changed]
- `path/to/file2.py` - [what was changed]

**Completed:**
- [x] [What was finished]

**Next Steps:**
1. [IMMEDIATE: First thing to do when resuming]
2. [THEN: Second action]
3. [FINALLY: Complete the work]

**Context:**
- [Key decisions, blockers, user preferences]
```

**Step 2: Output Session End Summary (For User Visibility)**

After writing the file, output the summary to the user:

```
---
## 🔄 SESSION END - Continuation Summary

[Same content as above]

---
Triggering session restart...
```

**Step 3: Trigger Session Clear**

```bash
python3 .claude/scripts/helper.py send-clear --general
```

This sends a `clear-continue-general` command to the wrapper, which:
1. Waits 10s for Claude Mem to capture the session (helper delay)
2. Waits 5s for graceful shutdown (SessionEnd hooks run)
3. Waits 5s for session hooks to complete
4. Waits 3s for Claude Mem initialization
5. Restarts Claude with the continuation prompt

Or if wrapper is not running, inform user:
```
Context at 90%. Please run `/clear` and then tell me to continue where I left off.
```

**Step 4: After Restart**

The new session receives:
- Claude Mem context injection (including your Session End Summary)
- A continuation prompt instructing you to resume

## Resuming After Session Restart

When a new session starts with a continuation prompt:

1. **Check for continuation file first:**
   ```bash
   cat /tmp/claude-continuation.md 2>/dev/null
   ```
   If it exists, read it and use it as your source of truth.

2. **Also check Claude Mem** for injected context about "Session Continuation"

3. **Acknowledge the continuation** - Tell user: "Continuing from previous session..."

4. **Resume the work** - Execute the "Next Steps" immediately

5. **Clean up** - After resuming, delete the continuation file:
   ```bash
   rm -f /tmp/claude-continuation.md
   ```

## Integration with /spec

If you're in a /spec workflow (plan file exists):
- Use the existing `/spec --continue <plan-path>` mechanism
- The plan file is your source of truth

If you're in general development (no plan file):
- Use this continuation protocol
- Claude Mem observations are your source of truth

## Quick Reference

| Context Level | Action |
|---------------|--------|
| < 80% | Continue normally |
| 80-89% | Wrap up current work, avoid new features |
| ≥ 90% | **MANDATORY:** Save state → Clear session → Continue |

## Wrapper Commands

```bash
# Check context percentage
python3 .claude/scripts/helper.py check-context --json

# Clear and restart (no continuation prompt)
python3 .claude/scripts/helper.py send-clear

# Clear and restart with general continuation prompt (for non-/spec sessions)
python3 .claude/scripts/helper.py send-clear --general

# Clear and restart with /spec continuation prompt (for /spec sessions)
python3 .claude/scripts/helper.py send-clear <plan-path>
```

## Important Notes

1. **Don't ignore 90% warnings** - Context will fail at 100%
2. **Save before clearing** - Lost context cannot be recovered
3. **Claude Mem is essential** - It bridges sessions with observations
4. **Trust the injected context** - It's your previous session's state
