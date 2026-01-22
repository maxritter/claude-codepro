# Context Continuation - Endless Mode for All Sessions

**Rule:** When context reaches critical levels, save state and continue seamlessly in a new session.

## Quality Over Speed - CRITICAL

**NEVER rush or compromise quality due to context pressure.**

- Context warnings are **informational**, not emergencies
- You can ALWAYS continue in the next session - work is never lost
- A well-done task split across 2 sessions is better than a rushed task in 1 session
- **Quality is the #1 metric** - clean code, proper tests, thorough implementation
- If context is high, finish the CURRENT task properly, then hand off cleanly
- Do NOT skip tests, compress explanations, or cut corners to "beat" context limits

**The context limit is not your enemy.** It's just a checkpoint. The plan file, Claude Mem, and continuation files ensure seamless handoff. Trust the system.

## How It Works

This enables "endless mode" for any development session, not just /spec workflows:

1. **Context Monitor** warns at 80% and 90% usage
2. **You save state** to Claude Mem before clearing
3. **CCP restarts** Claude with continuation prompt
4. **Claude Mem injects** your saved state
5. **You continue** where you left off

## When Context Warning Appears

When you see the context warning (80% or 90%), take action:

### At 80% - Prepare for Continuation

- Wrap up current task if possible
- Avoid starting new complex work
- Consider saving progress observation

### At 90% - Mandatory Continuation Protocol

**Step 1: VERIFY Before Writing (CRITICAL)**

Before writing the continuation file, you MUST run verification commands:
```bash
# Run tests
uv run pytest tests/ -q
# Run type checker
uv run basedpyright installer/
```

**DO NOT claim work is complete without showing verification output in the continuation file.**

**Step 2: Check for Active Plan (MANDATORY)**

**⚠️ CRITICAL: You MUST check for an active plan before deciding which handoff command to use.**

```bash
# Check for non-VERIFIED plans (most recent first by filename)
ls -1 docs/plans/*.md 2>/dev/null | sort -r | head -5
```

Then check the Status field in the most recent plan file(s). An **active plan** is any plan with `Status: PENDING` or `Status: COMPLETE` (not `VERIFIED`).

**Decision Tree:**
| Situation | Command to Use |
|-----------|----------------|
| Active plan exists (PENDING/COMPLETE) | `$PWD/.claude/bin/ccp send-clear docs/plans/YYYY-MM-DD-name.md` |
| No active plan (all VERIFIED or none exist) | `$PWD/.claude/bin/ccp send-clear --general` |

**NEVER use `--general` when there's an active plan file. This loses the plan context!**

**Step 3: Write Session Summary to File (GUARANTEED BACKUP)**

Write the summary to `/tmp/claude-continuation.md` using the Write tool. Include VERIFIED status with actual command output.

```markdown
# Session Continuation

**Task:** [Brief description of what you were working on]
**Active Plan:** [path/to/plan.md or "None"]

## VERIFIED STATUS (run just before handoff):
- `uv run pytest tests/ -q` → **X passed** or **X failed** (be honest!)
- `uv run basedpyright src/` → **X errors** or **0 errors**
- If tests fail or errors exist, document WHAT is broken

## Completed This Session:
- [x] [What was VERIFIED as finished]
- [ ] [What was started but NOT verified/complete]

## IN PROGRESS / INCOMPLETE:
- [Describe exactly what was being worked on]
- [What command was being run]
- [What error or issue was being fixed]

## Next Steps:
1. [IMMEDIATE: First thing to do - be SPECIFIC]
2. [Include exact file:line if fixing something]

## Files Changed:
- `path/to/file.py` - [what was changed]
```

**CRITICAL: If you were in the middle of fixing something, say EXACTLY what and where. The next agent cannot read your mind.**

**Step 4: Output Session End Summary (For User Visibility)**

After writing the file, output the summary to the user:

```
---
## 🔄 SESSION END - Continuation Summary

[Same content as above]

---
Triggering session restart...
```

**Step 5: Trigger Session Clear**

**Use the correct command based on Step 2:**

```bash
# If active plan exists (PREFERRED - preserves plan context):
$PWD/.claude/bin/ccp send-clear docs/plans/YYYY-MM-DD-name.md

# ONLY if NO active plan exists:
$PWD/.claude/bin/ccp send-clear --general
```

This triggers session continuation in Endless Mode:
1. Waits 10s for Claude Mem to capture the session
2. Waits 5s for graceful shutdown (SessionEnd hooks run)
3. Waits 5s for session hooks to complete
4. Waits 3s for Claude Mem initialization
5. Restarts Claude with the continuation prompt

Or if no active session, inform user:
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

## CCP Commands for Endless Mode

```bash
# Check context percentage
$PWD/.claude/bin/ccp check-context --json

# Trigger session continuation (no continuation prompt)
$PWD/.claude/bin/ccp send-clear

# Trigger continuation WITH plan (PREFERRED when plan exists):
$PWD/.claude/bin/ccp send-clear docs/plans/YYYY-MM-DD-name.md

# Trigger continuation WITHOUT plan (ONLY when no active plan):
$PWD/.claude/bin/ccp send-clear --general
```

**⚠️ ALWAYS check for active plans before using `--general`. See Step 2 above.**

## Important Notes

1. **Don't ignore 90% warnings** - Context will fail at 100%
2. **Save before clearing** - Lost context cannot be recovered
3. **Claude Mem is essential** - It bridges sessions with observations
4. **Trust the injected context** - It's your previous session's state
