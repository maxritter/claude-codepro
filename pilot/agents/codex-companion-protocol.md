# Codex Companion Run Protocol

> Shared runbook for every Pilot workflow step that launches a Codex companion review
> (`spec-plan` plan review, `spec-verify` changes review, `fix` bugfix review).
> Claude Code only — the companion broker ships with the `openai-codex` plugin.
>
> Skill steps reference this file instead of restating it. Read it only when the
> calling step has confirmed its Codex toggle is `"true"` and the codex-once
> sentinel is absent.

## What the caller supplies

| Value | Meaning |
|---|---|
| `PROMPT_TEMPLATE` | `$HOME/.pilot/agents/spec-review-codex.md` (plans) or `changes-review-codex.md` (code) |
| Placeholders | The template's `{{...}}` keys and their values — resolved by the caller, never guessed |
| `SLUG` | The run's own identifier: a plan slug (filename minus `YYYY-MM-DD-` prefix and `.md`), or `/fix`'s `<fix-slug>` derived from the bug description. ⛔ Never a per-workflow constant — `SLUG` names `codex-review-$SLUG.md` and `codex-result-$SLUG.json` under this run's own session/lane directory. Preserve both the unique slug and parsed lane so concurrent reviews cannot share prompts or results (issue #173). |
| `CODEX_FLAG` | Session sentinel path enforcing codex-once |
| `LANE_ID` | Parsed invocation lane, empty outside a lane |
| `ROLE` | The supplied template's basename with `-codex.md` removed: `spec-review`, `changes-review`, or `build-review` |

Everything below is identical across callers.

Read `review-state-protocol.md` first. Use its atomic record for this companion job and resolve all prompt, result, and codex-once paths in that same session/lane directory. Native read-only planning defers this entire write/launch protocol until successful exit. Never launch a replacement while the record identifies live or unreconciled work.

## Non-negotiables

These three exist because each has produced a real, reproduced failure:

- **Launch from the main conversation via `Bash`, never through a subagent** (`codex:codex-rescue` included). A subagent-launched job's ID is unreachable afterwards — no findings file, no `TaskOutput`, no `SendMessage`, no recovery.
- **Collect results only after the registered job is complete.** Partial output is not a review result and cannot be interpreted as "no findings".
- **Never pass `--model`.** Fast-model aliases are rejected on ChatGPT-plan auth (`400`). The user's default model always stays.

## 1. Locate the companion

```bash
CODEX_COMPANION=$(ls ${CLAUDE_CONFIG_DIR:-$HOME/.claude}/plugins/cache/openai-codex/codex/*/scripts/codex-companion.mjs 2>/dev/null | sort -V | tail -1)
PROJECT_ROOT="${CLAUDE_PROJECT_ROOT:-$(pwd)}"
SESSION_ID="${CLAUDE_CODE_SESSION_ID:-${CODEX_THREAD_ID:-${PILOT_SESSION_ID:-}}}"
# Stop this launch if identity is absent or violates review-state-protocol.md.
SESSION_ID="$SESSION_ID" LANE_ID="$LANE_ID" SLUG="$SLUG" ROLE="$ROLE" node -e '
const valid = /^[A-Za-z0-9][A-Za-z0-9_-]*$/;
for (const key of ["SESSION_ID", "SLUG", "ROLE"])
  if (!valid.test(process.env[key] || "")) process.exit(1);
if (process.env.LANE_ID && !/^[a-z0-9][a-z0-9-]{0,63}$/.test(process.env.LANE_ID)) process.exit(1);
' || exit 1
SESS_DIR="$HOME/.pilot/sessions/$SESSION_ID"
[ -z "$LANE_ID" ] || SESS_DIR="$SESS_DIR/lanes/$LANE_ID"
mkdir -p "$SESS_DIR"
[ -z "$CODEX_COMPANION" ] && echo "MISSING"
```

`MISSING` → tell the user "Codex companion not found — install the openai-codex plugin or disable the Codex reviewer in Console Settings", continue with the caller's other reviewer, and record the gap in the caller's report. Do not fail the workflow.

## 2. Render the prompt file

The template is the single source of truth for review semantics — never restate its prompt inline.

```bash
PROMPT_FILE="$SESS_DIR/codex-review-$SLUG.md"
# Export each placeholder the template declares, then substitute:
PROMPT_TEMPLATE="$PROMPT_TEMPLATE" PROMPT_FILE="$PROMPT_FILE" \
node -e '
const fs = require("fs");
let text = fs.readFileSync(process.env.PROMPT_TEMPLATE, "utf8");
for (const key of Object.keys(process.env))
  if (/^[A-Z_]+$/.test(key)) text = text.split("{{" + key + "}}").join(process.env[key]);
fs.writeFileSync(process.env.PROMPT_FILE, text);
'
grep -c "{{" "$PROMPT_FILE"   # must print 0 — an unsubstituted placeholder means the review runs blind
```

`node` (not `uv`/`python`) because the companion is itself node — it is guaranteed present on this path. `split`/`join` rather than `replace` so a value containing `$&` cannot trigger JS pattern expansion.

## 3. Launch in the background

Review effort defaults to `medium`; users can override with `PILOT_CODEX_REVIEW_EFFORT`. Validate supported values with the installed companion's help when the user requests a newer effort level. Do not infer review quality or runtime from a historical model generation.

```bash
CODEX_EFFORT="${PILOT_CODEX_REVIEW_EFFORT:-medium}"
case "$CODEX_EFFORT" in none|minimal|low|medium|high|xhigh) ;; *) CODEX_EFFORT=medium ;; esac
```

`task --background` is the only companion subcommand whose own background mode works (`review` / `adversarial-review` do not detach). It returns the job id on stdout immediately:

```
Bash(
  command="cd $PROJECT_ROOT && node $CODEX_COMPANION task --background --effort \"$CODEX_EFFORT\" --prompt-file \"$PROMPT_FILE\"",
  run_in_background=false,
  timeout=60000
)
```

Record `launching` before the call. Extract the `task-…` token as `JOB_ID` and immediately atomically record it with `PROMPT_FILE`, plan, slug, lane, role, and retry count, before any independent work. If the launch itself errors on the effort value (a model rejecting `reasoning.effort` fails within seconds with a `400`), first confirm no live job was registered, then retry once without `--effort` and retain both attempts in the record.

Verify the broker registered the job using the bounded status command in §4. A transient status error is not proof of a missing job. Keep the recorded id and reconcile the broker's authoritative state. If launch output has no handle, retain `launching` and inspect the broker inventory before considering a replacement; report incomplete evidence when it cannot be reconciled.

**Then return to the calling step and keep working.** The companion runs in parallel with the caller's own checks; do not idle waiting for it.

## 4. Wait for the registered job

Reload the atomic record after compaction or a phase handoff; keep its original `JOB_ID`. Each observation below bounds the status subprocess to 15 seconds. It only terminates a stalled status command, never the registered background review:

```bash
CODEX_COMPANION="$CODEX_COMPANION" JOB_ID="$JOB_ID" node - <<'JS'
const { spawnSync } = require('node:child_process');
const observation = spawnSync(process.execPath,
  [process.env.CODEX_COMPANION, 'status', process.env.JOB_ID, '--json'],
  { encoding: 'utf8', timeout: 15000, killSignal: 'SIGKILL' });
if (observation.stdout) process.stdout.write(observation.stdout);
if (observation.error || observation.status !== 0) {
  process.stderr.write('Observation incomplete; retain the original job handle.\n');
  process.exitCode = 1;
}
JS
```

Inspect the returned status, then return to independent work or yield through the runtime's wait mechanism for up to 15 seconds before the next observation. Give a progress update at least every 60 seconds. There is no arbitrary total review deadline: repeated observation windows preserve the same job until it reaches a confirmed terminal state or the user cancels it. Do not turn quiet output into a restart or a passed review.

- `completed` → collect the result in §5.
- `running` / `verifying` → keep waiting on this job. Log growth can help diagnose progress, but quiet logs do not prove a hung model.
- A transient status error or observation timeout → re-poll the same handle; do not restart.
- Confirmed `failed` / `cancelled`, or a confirmed missing broker handle → inspect the reason and retry once if it is recoverable.

Use the runtime's wait or background mechanism to remain responsive. Do not manufacture extra review passes or sanity checks merely to fill the wait.

If cancellation is needed because the user stops the work or a confirmed runtime execution limit is reached, request it and confirm terminal state with the bounded status observation above before any replacement launch:

```bash
node "$CODEX_COMPANION" cancel "$JOB_ID" --json
```

A retry gets a new job id after the original is terminal. Do not change the model or effort merely because observation was quiet. If the retry fails, report the missing companion evidence and continue the caller's other checks; never claim the review passed.

## 5. Fetch and act on findings

```bash
node "$CODEX_COMPANION" result "$JOB_ID" --json > "$SESS_DIR/codex-result-$SLUG.json"
```

Read that file. Deterministic name, never `$$` — each Bash call is a new shell with a new PID, so a PID-based path cannot be reconstructed by a later step.

- `storedJob.status` must be `"completed"`; otherwise return to §4 and inspect the original handle. A partial result is neither a pass nor automatic relaunch authority.
- `storedJob.result.rawOutput` — Codex's response; with these templates it is JSON matching `{verdict, summary, findings, next_steps}`.
- `storedJob.rendered` — diagnostic display fallback when `rawOutput` is invalid. Inspect it for useful evidence, but record the companion review as incomplete rather than treating the malformed response as a pass. Use any documented response-correction mechanism without launching a duplicate review; otherwise continue the caller's explicit fallback with the gap disclosed.

**Severity → action.** Evaluate lineage FIRST: a finding on a file outside the change's lineage is mention-only regardless of severity — out-of-lineage crashes get reported to the user, never auto-fixed. For in-lineage findings:

| Codex severity | Action |
|---|---|
| `critical` / `high` | must_fix — fix now, then re-run the caller's tests |
| `medium` / `low` | should_fix — fix now when single-site; summarise if it would expand scope |
| `info` | Mention in the report |

Verdict `approve` with no findings → report "Codex: no blocking findings" in one line.

Codex findings frequently surface architectural gaps the Claude reviewer misses (chained-command bypasses, fail-open paths, encoding edges) — weigh them at least equally.

## 6. Mark and clean up

After terminal confirmation and validated result collection, atomically record `collected` (or `incomplete` if invalid) with the handle and result identity. Retain that record for recovery. The codex-once flag records an attempted terminal review, never a successful verdict by itself.

```bash
[ -n "$JOB_ID" ] && touch "$CODEX_FLAG"      # only after terminal collection, never while live
rm -f "$PROMPT_FILE"
```

Retain the validated result at the record's `result_path` through workflow completion so recovery can inspect collected evidence. If cleanup later removes it, first atomically retain the consumed verdict/findings and mark that path as removed in the record. Never leave a record pointing to a supposedly saved result that no longer exists.
