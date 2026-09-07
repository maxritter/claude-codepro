## Step 12: Approval and Implementation Handoff

A synchronous permitted question needs no disk sentinel. For an asynchronous persisted gate, resolve and validate the actual session identity before creating or consuming its marker; missing identity blocks only that persistence path. Keep the real decision pending or use the permitted synchronous question surface, and never substitute a shared session directory. Recompute the validated session/lane path before cleanup after a new shell call or compaction.

<!-- CC-ONLY -->
### 12.0 Prepared native-planning path

If this run prepared the native handoff in `$HOME/.pilot/agents/spec-native-plan.md`, follow that runbook's approval and handoff now. `ExitPlanMode` presents the native draft for approval, and the capture hook transfers the accepted result into the registered plan. Skip the normal question below; do not ask for the same approval twice. Complete any deferred configured review before implementation.

A Console mode change does not end an already-open native mode. Use the runtime's current state and preserve its permission choice. A failed exit grants neither approval nor write permission.
<!-- /CC-ONLY -->

### 12.1 Normal approval path

Use the current plan and the configured `PILOT_PLAN_APPROVAL_ENABLED` value. If this exact plan already has explicit user approval and has not changed substantively, preserve that approval across phase handoffs or compaction. Otherwise:

- `false`: the user configured autonomous approval; set `Approved: Yes` and continue.
- `true`: present the completed plan through the runtime's permitted structured question tool and wait for the user's decision. A hook's permission allowance, a stop-guard continuation, or an elapsed wait is not that decision.

Notify once when the plan is ready for review and the operation is permitted:

```bash
~/.pilot/bin/pilot notify plan_approval "Plan Ready for Review" "<plan_name> — annotate in Console or approve here" --plan-path "<plan_path>" 2>/dev/null || true
```

### 12.2 User decision

Summarize the goal, approach, and material tasks, then use `AskUserQuestion` when the runtime exposes and permits it (Codex: its native structured user-input equivalent) with these choices:

- **Yes, proceed with implementation** — approve the current plan.
- **No, I have feedback** — process Console annotations, direct plan edits, or feedback in the reply.

Do not ask about the worktree again; its header already records the choice. Clear equivalent approval in the user's own words also counts. Feedback or a side question alone does not.

For an asynchronous or absent structured tool, read `$HOME/.pilot/agents/agent-gate-protocol.md`. Supply `GATE_NAME` = `Plan approval`, the choices above, and `SENTINEL_PATH` = `spec-approval-pending`. Create the sentinel before yielding:

```bash
SESSION_ID="${CLAUDE_CODE_SESSION_ID:-${CODEX_THREAD_ID:-${PILOT_SESSION_ID:-}}}"
case "$SESSION_ID" in ""|*[!A-Za-z0-9_-]*) echo "Persisted gate needs a confirmed session identity" >&2; exit 1 ;; esac
SESS_DIR="$HOME/.pilot/sessions/$SESSION_ID"
[ -z "$LANE_ID" ] || SESS_DIR="$SESS_DIR/lanes/$LANE_ID"
mkdir -p "$SESS_DIR" && touch "$SESS_DIR/spec-approval-pending"
```

Independent permitted work may continue while a question is pending; implementation dependent on this approval may not. When there is no independent work left, end the turn so the answer can arrive. Preserve the pending question rather than repeatedly presenting it. On receiving an answer, remove the sentinel and act on what the user actually said:

```bash
SESSION_ID="${CLAUDE_CODE_SESSION_ID:-${CODEX_THREAD_ID:-${PILOT_SESSION_ID:-}}}"
case "$SESSION_ID" in ""|*[!A-Za-z0-9_-]*) echo "Persisted gate needs a confirmed session identity" >&2; exit 1 ;; esac
SESS_DIR="$HOME/.pilot/sessions/$SESSION_ID"
[ -z "$LANE_ID" ] || SESS_DIR="$SESS_DIR/lanes/$LANE_ID"
rm -f "$SESS_DIR/spec-approval-pending"
```

- **Approval:** set `Approved: Yes` and continue immediately to 12.3.
- **Feedback:** process Step 11, update the plan, then ask for approval of the revised result. Do not record a guessed answer.

### 12.3 Implementation handoff

<!-- CC-ONLY -->
Once the approved registered plan is ready and the runtime permits implementation, invoke `Skill(skill='spec-implement', args='<plan-path> $LANE_FLAG')`. Manual and Off preserve the active `/model`; a completed native Automated handoff uses the runtime's execution leg. No mode adds another model-switch prompt or an agent-invented pause after approval. The user can interrupt to change models.
<!-- /CC-ONLY -->
<!-- CODEX-START
Continue immediately with the `$spec-implement` skill instructions using arguments `<plan-path> $LANE_FLAG` on the active Codex model. Use the current native mode and tool schema; Pilot's Claude model-switching tools do not apply here.
CODEX-END -->

ARGUMENTS: $ARGUMENTS
