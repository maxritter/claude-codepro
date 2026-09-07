## Step 6: Code Review Gate (User Confirmation)

A synchronous permitted question needs no disk sentinel. For an asynchronous persisted gate, resolve and validate the actual session identity before creating or consuming its marker; missing identity blocks only that persistence path. Keep the real decision pending or use the permitted synchronous question surface, and never substitute a shared session directory. Recompute the validated session/lane path before cleanup after a new shell call or compaction.

The user reviews the concrete verified change before the plan becomes `VERIFIED`. Reuse explicit approval already given for this same result; do not ask again because a phase changed or the context compacted. Changed code or unresolved new feedback may require a fresh review.

### Present the reviewable result

Summarize the changes, checks actually passed, runtime evidence, and material gaps. Point to the Console's Changes tab and mention that inline annotations are saved automatically.

Offer the decisions naturally: approve this result, address feedback, or wait while the user tests it.

<!-- CC-ONLY -->
Use `AskUserQuestion` when available and permitted for this approval. It intrinsically waits for the answer; do not add a second confirmation.
<!-- /CC-ONLY -->
<!-- CODEX-START
Use the runtime's structured user-input tool when exposed and permitted for approval in the current mode. Follow its actual schema. If it supports asynchronous questions, continue independent work while the answer is pending; do not finalize the plan before the required answer arrives.
CODEX-END -->

When no permitted structured tool can ask this approval, follow `$HOME/.pilot/agents/agent-gate-protocol.md` with `GATE_NAME=Code review gate` and `SENTINEL_PATH=verify-gate-pending`. Ask one concise prose question and yield:

```bash
SESSION_ID="${CLAUDE_CODE_SESSION_ID:-${CODEX_THREAD_ID:-${PILOT_SESSION_ID:-}}}"
case "$SESSION_ID" in ""|*[!A-Za-z0-9_-]*) echo "Persisted gate needs a confirmed session identity" >&2; exit 1 ;; esac
SESS_DIR="$HOME/.pilot/sessions/$SESSION_ID"
[ -z "$LANE_ID" ] || SESS_DIR="$SESS_DIR/lanes/$LANE_ID"
mkdir -p "$SESS_DIR" && touch "$SESS_DIR/verify-gate-pending"
```

The guard honors this sentinel for the applicable `Status: COMPLETE` state. Remove it on resume; re-touch it only when another genuine approval question needs a yield.

### Interpret the response

- **Explicit approval of this result** — "approve", "lgtm", "looks good", or an equally clear statement in context — proceed to Step 7.
- **Feedback** — read the annotations in Step 5 and the user's message, apply in-scope fixes, rerun affected checks, then present the updated result.
- **Manual testing** — keep the plan `COMPLETE` while the user tests. Do not repeatedly ask for the same pending answer.
- **Unrelated or ambiguous reply** — answer or clarify it without inventing approval. A bare "continue" or "proceed", silence, empty annotations, and green checks alone do not sign off the result.

Preserve the actual approval and reviewed-result identity across compaction. A stop-guard instruction is not user approval.
