# Agent Gate Protocol

Shared runbook for an actual user decision in Pilot workflows: spec plan approval, worktree merge/discard, verification sign-off, material scope changes, and unresolved product questions. Read it when a caller reaches such a decision.

`/build` has no routine approval, round-budget, or hand-back gate after its initial scope clarification. This protocol does not add one. All workflows still respect explicit user instructions and runtime permissions.

## Before asking

Reuse an explicit decision or authorization already supplied for the same scope and current reviewable result. A workflow phase boundary, compaction, or tool change does not revoke it. Do not infer approval from credentials, silence, a timeout, a hook's permission decision, green checks, or the agent's prediction of the user's choice.

The caller supplies:

| Value | Meaning |
|---|---|
| `GATE_NAME` | The actual decision in user terms |
| `OPTIONS` | The choices and their consequences |
| `SENTINEL_PATH` | The caller's pause sentinel, or `none` |
| `LANE_ID` | The invocation's parsed lane id, or empty for the main session |

Resolve gate files under the caller's run directory: `sessions/<session>/lanes/<lane>/` for a lane and `sessions/<session>/` otherwise. Current stop-guard readers consume only main-session sentinels; a lane marker records its pending decision but does not claim to release that guard. Lane agents relay unresolved decisions to their coordinator and yield using their native agent lifecycle. Never create, consume, or clear a coordinator's sentinel from a lane. If the coordinator itself needs to yield, it uses a main-session sentinel only for its own registered plan and matching gate; a sibling lane's pending marker cannot approve or pause that plan.

## Ask using the current runtime

Use a structured question tool only when it is exposed and permitted for this question in the current mode. Codex and Claude toolsets vary; neither the agent brand nor the presence of `AskUserQuestion` determines what is allowed. Follow the tool's actual schema, including restrictions on approval questions.

If an asynchronous input tool is available, ask early and continue independent work. Keep required input pending: dependent work cannot proceed until the answer arrives. Optional preferences may use a stated reasonable default when the runtime permits that.

Without a permitted structured tool, ask one concise question in prose with enough context for a decision. Describe relevant alternatives naturally, or as a list only when the runtime permits that format. A subagent with no user-facing question surface reports the unresolved decision to its coordinating agent; the coordinator can relay it or answer only within authority already delegated by the user.

## Yield when required input is pending

A synchronous permitted question needs no disk sentinel. Missing session identity blocks only an asynchronous persisted gate: keep the actual decision pending or use the permitted synchronous question surface. Never substitute a shared directory, and do not turn unavailable persistence into a task-wide denial. Before cleanup in a new shell call or after compaction, resolve and validate the same session/lane identity again.

If no independent work remains, touch the caller's sentinel when applicable and end the turn so the user can answer:

```bash
SESSION_ID="${CLAUDE_CODE_SESSION_ID:-${CODEX_THREAD_ID:-${PILOT_SESSION_ID:-}}}"
case "$SESSION_ID" in ""|*[!A-Za-z0-9_-]*) echo "Persisted gate needs a confirmed session identity" >&2; exit 1 ;; esac
SESS_DIR="$HOME/.pilot/sessions/$SESSION_ID"
[ -z "$LANE_ID" ] || SESS_DIR="$SESS_DIR/lanes/$LANE_ID"
mkdir -p "$SESS_DIR" && touch "$SESS_DIR/<sentinel-name>"
```

On resume, interpret the response in context. Explicit approval of the presented result is sufficient; an unrelated message or routine "continue" does not silently approve a merge or verification sign-off. Follow the caller's sentinel cleanup rules and retain the actual answer across compaction.

Never set `Approved: Yes` or pass a human sign-off merely because the form is unavailable. A configured workflow approval opt-out or explicit standing authorization is different from an inferred answer; apply only the authority the caller actually has.

If the stop guard blocks a genuine pending question, preserve the unresolved state, re-state the question briefly, and re-touch the applicable sentinel. Repeated guard failure is a blocker to report, not permission to self-approve.
