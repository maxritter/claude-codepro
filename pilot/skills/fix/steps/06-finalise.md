## Step 6: Finalise

Read `$HOME/.pilot/agents/review-state-protocol.md` before launching any enabled reviewer. Persist each returned native or companion handle atomically with the plan, lane, role, and lifecycle state before independent work; reload that record after compaction and before collection.

### 6.1 Automated changes review (when enabled)

⛔ **Step 4 (Verify End-to-End) must be complete, with concrete evidence, before any reviewer runs.** Reviewers audit the fix; they never substitute for running the program.

The same Console Settings toggles that drive `/spec`'s post-implementation review govern `/fix`. Run whichever are enabled and **apply their findings before** the approval gate (6.2) and the worktree commit (6.3), so the user approves the reviewed fix and review-driven changes land in the single bundled commit.

<!-- CC-ONLY -->
```bash
echo "CHANGES_REVIEW=$PILOT_CHANGES_REVIEW_ENABLED"          # changes-review sub-agent — runs unless explicitly "false"
echo "CODEX_REVIEW=$PILOT_CODEX_CHANGES_REVIEW_ENABLED"      # Codex companion review — runs only when "true"
```

Skip straight to 6.2 **only** when `PILOT_CHANGES_REVIEW_ENABLED` IS `"false"` AND `PILOT_CODEX_CHANGES_REVIEW_ENABLED` is not `"true"`. Otherwise at least one reviewer runs — changes-review is on by default, so an unset value runs it.

⛔ **Never `Skill(skill='code-review', ...)` here.** It carries `disable-model-invocation`, so the call is rejected and the fix ships with no review while the report claims one. A deeper review is the user's to start by typing `/code-review`.
<!-- /CC-ONLY -->
<!-- CODEX-START
```bash
echo "CHANGES_REVIEW=$PILOT_CHANGES_REVIEW_ENABLED"          # native changes-review agent — runs unless explicitly "false"
```

The Codex companion (`PILOT_CODEX_CHANGES_REVIEW_ENABLED`) does NOT apply in Codex. Skip to 6.2 **only** when `PILOT_CHANGES_REVIEW_ENABLED` IS `"false"`; otherwise the native `changes-review` agent runs (an unset value runs it).
CODEX-END -->

#### 6.1.pre Instrumentation gate, then stage the fix (whenever any reviewer runs)

**Scan the unstaged tree before anything is staged or committed.** Step 3.5 was the primary gate; this is the last point at which a `SPEC-DEBUG` or stray `console.log` can still be caught pre-commit.

```bash
git diff | grep -nE "SPEC-DEBUG|^\+.*\b(console\.log|console\.error|print\()" && \
  { echo "Leftover instrumentation — remove before staging/commit"; } || echo "instrumentation clean"
```

Remove fix-owned temporary diagnostics. Preserve intentional program output and pre-existing logging; inspect each match before editing.

Then stage the change's own files. The fix and its new test sit unstaged, and a brand-new test file is untracked — which misfires reviewers both ways: one reading `git status --untracked-files=all` flags the new test as a spurious `critical` ("untracked deliverable"), while one reading only `git diff HEAD` silently omits it, leaving the test unreviewed.

```bash
git add <fix_file> <test_file>   # only the bugfix's own files — never unrelated dirty paths
git status --short --untracked-files=all | grep '^??' || true   # should list only files outside this fix
```

A bare `git add -N` is not enough — `git status` still reports the path as untracked. **Staging is not committing**: the commit (6.3) still waits for the review and the approval gate. All reviewers scope to `git diff HEAD`, which now includes the staged additions; a committed ref-range would be empty pre-commit and scan nothing.

**Mixed ownership:** if a listed file already contains unrelated user or concurrent edits, a whole-file `git add` is not a valid scope boundary. Preserve the index and distinguish this run's hunks using scoped staging or an isolated review artifact. Do not include unrelated work merely because it shares a path.

<!-- CC-ONLY -->
#### 6.1.0 Bugfix summary artifact

For `/fix` the "plan" is this conversation, not a file. Both reviewers anchor on a plan artifact — the changes-review sub-agent and the Codex companion — so build one:

```bash
SESSION_ID="${CLAUDE_CODE_SESSION_ID:-${CODEX_THREAD_ID:-${PILOT_SESSION_ID:-}}}"
case "$SESSION_ID" in ""|*[!A-Za-z0-9_-]*) echo "Review state needs a confirmed session identity" >&2; exit 1 ;; esac
SESS_DIR="$HOME/.pilot/sessions/$SESSION_ID"
[ -z "$LANE_ID" ] || SESS_DIR="$SESS_DIR/lanes/$LANE_ID"
RUN_DIR="$SESS_DIR"            # already scoped to this lane, if any
mkdir -p "$RUN_DIR"
FIX_PLAN_FILE="$RUN_DIR/fix-review-plan-<fix-slug>.md"
cat > "$FIX_PLAN_FILE" <<'PLAN_EOF'
# /fix Bugfix Summary
Bug: <one-line bug>
Root cause: <file>:<line> — <what>
Fix: <one-line fix description>
Reproducing test: <test file>::<test name> (added in Step 2 RED)
PLAN_EOF
```

Run-isolated and deterministic (no `/tmp`, no `$$`): later Bash calls, the reviewer prompt, and cleanup all reconstruct this path from outside that shell.

⛔ **`<fix-slug>` is not decoration.** Reuse the `<fix-slug>` derived in Step 1.1 and the lane directory resolved above. Together they prevent concurrent fixes from sharing a summary or reviewer record.

#### 6.1.a Codex companion review — launch FIRST when `PILOT_CODEX_CHANGES_REVIEW_ENABLED == "true"`

An independent second opinion, launched before the inline review so the two run in parallel.

**Codex-once:** at most one companion run per `/fix` invocation. Check the sentinel first; if it exists, a prior approval-gate loop already ran it — skip the launch and the Codex half of 6.1.c.

```bash
CODEX_FLAG="$RUN_DIR/codex-changes-review-ran-<fix-slug>.flag"
[ -f "$CODEX_FLAG" ] && echo "Codex already reviewed this fix in this session — skipping (codex-once)."
```

⛔ Slug-scoped, not fixed: a shared flag means a sibling lane's completed Codex run makes THIS lane skip its own review entirely, while its report still claims one ran.

Otherwise **read `$HOME/.pilot/agents/codex-companion-protocol.md` and follow it end to end** (locate → render → launch → stall monitor → collect → mark). It is the single source of truth for the companion run loop. Supply:

| Protocol input | Value for `/fix` |
|---|---|
| `PROMPT_TEMPLATE` | `$HOME/.pilot/agents/changes-review-codex.md` |
| `ROLE` | `changes-review` |
| `LANE_ID` | Original parsed `--lane <id>` value, or empty for this main-session run |
| `{{PLAN_PATH}}` | `$FIX_PLAN_FILE` from 6.1.0 |
| `{{PLAN_GOAL}}` | `Bugfix for: <one-line bug>. Root cause at <file>:<line>. The reproducing test must reliably fail before the fix and pass after.` |
| `{{BASE_REF}}` | `HEAD` — the fix is staged, not committed |
| `{{CHANGED_FILES}}` | `git status --short --untracked-files=all` paths for this fix |
| `SLUG` | `<fix-slug>` — never the literal `fix`; the protocol expands it into `codex-review-$SLUG.md` and `codex-result-$SLUG.json`, which two concurrent runs would otherwise share |
| `CODEX_FLAG` | the path above |

Launch, then **continue to 6.1.b immediately** — the changes review runs while Codex churns. Collect in 6.1.c. If the companion is missing or its job never registers, continue with the 6.1.b results and note the gap in the 6.6 report.

#### 6.1.b Changes review — when `PILOT_CHANGES_REVIEW_ENABLED` is not `"false"`

Read and reconcile the existing native review record for this plan, lane, and `changes-review` role before launching anything. Resume its live handle, collect an already completed result, or reconcile an interrupted `launching` attempt; only a confirmed terminal or missing prior attempt permits a replacement.

Atomically write `state: launching` with `provider: native`, this role, plan/lane identity, and `reviewed_sha256` of the exact review anchor before the spawn call below. Use `review-state-protocol.md`. If the write fails or the current mode forbids it, defer the launch; do not create an unrecorded background job.

Launch the changes-review sub-agent with the actual `Agent` schema and retain the returned native agent/task handle:

```
Agent(
  subagent_type="changes-review",
  run_in_background=true,
  prompt="""
  **Plan file:** <$FIX_PLAN_FILE path>
  **Changed files:** <fix file> <test file>

  Review the diff (git diff HEAD -- <fix file> <test file>) against the bugfix summary:
  root-cause fix quality, test quality, and regressions.
  Remain read-only. Return ONLY valid JSON matching the changes-review schema.
  Set "plan_file" to the supplied Plan file path.
  """
)
```

Immediately persist the returned `native_agent_id` and `state: running` atomically in that same record before waiting, independent work, or a handoff. If saving fails, retain and reconcile this handle; do not spawn again.

Use the current runtime's handle-based wait/result mechanism, including `TaskOutput` when exposed, or consume the final response directly from a foreground `Agent` call. Read the completed final JSON; do not request or poll an agent-authored findings file.

At native collection, confirm terminal completion and atomically write `state: completed`; validate the final JSON schema and matching `plan_file`, then write `state: collected` with the consumed result identity. If terminal output remains invalid or unavailable after correction/recovery, write `state: incomplete` with the reason and follow the explicit fallback. Observation timeouts leave the original live state and handle intact.

Validate the response schema and that `plan_file` matches `$FIX_PLAN_FILE`. For invalid output, request a corrected final response from the same agent when supported. If no valid result is available, record the native review as incomplete and use the documented self-review or companion fallback; never call malformed or missing output a pass.

Keep waiting on the original handle while it is live. Quiet output or an observation timeout is not a restart trigger. After a confirmed terminal failure or missing handle, retry once when recoverable; retain the new handle. The parent may save validated JSON for bookkeeping when writes are permitted, but that file is not the completion signal.

If no valid native result is obtained after recovery, report the gap in 6.6. Do not substitute `Skill(skill='code-review', ...)`, whose invocation is not permitted here.



#### 6.1.c Apply findings

Both reviewers receive the bug summary, so root-cause-vs-symptom judgment is theirs to challenge — but the final call stays here (Step 1.3 trace + the 6.5 checklist).

**Lineage is evaluated FIRST.** A finding on a file outside the bug's lineage — the fix file, its test, and files the fix legitimately touched — is mention-only regardless of severity. Out-of-lineage crashes get reported to the user, never auto-fixed. Only in-lineage findings run through the rows below.

| Finding class | Action |
|---------------|--------|
| Outside the bug's lineage (CHECK FIRST — overrides every row below) | Mention in one line; do not auto-apply |
| `failure_scenario` names a concrete crash, wrong output, security, or data-integrity problem | **must_fix** — fix now, then re-run Step 3.4's targeted tests + Step 5.2's full suite |
| Cleanup / efficiency finding, single-site, in-lineage | **should_fix** — fix |
| Requires additional in-scope files or structural work | Fix now when it follows the reported defect's causal chain; mention only unrelated suggestions |

Changes-review findings carry explicit severities — map them through the same lineage-first rule (`must_fix` → row 2, `should_fix` → row 3, `suggestion` → mention). Codex findings map by the table in the protocol file's §5.

If a reviewer returns nothing blocking, report "Review: no blocking findings" in one line and move on.
<!-- /CC-ONLY -->
<!-- CODEX-START
When `PILOT_CHANGES_REVIEW_ENABLED` is not `"false"`, run the managed Codex `changes-review` custom agent on the bugfix diff before finalising. (The Codex *companion* review — `PILOT_CODEX_CHANGES_REVIEW_ENABLED` — is a Claude-Code-only plugin path and does not run here.)

1. Build a one-page bugfix summary as the review anchor:

```bash
SESSION_ID="${CLAUDE_CODE_SESSION_ID:-${CODEX_THREAD_ID:-${PILOT_SESSION_ID:-}}}"
case "$SESSION_ID" in ""|*[!A-Za-z0-9_-]*) echo "Review state needs a confirmed session identity" >&2; exit 1 ;; esac
SESS_DIR="$HOME/.pilot/sessions/$SESSION_ID"
[ -z "$LANE_ID" ] || SESS_DIR="$SESS_DIR/lanes/$LANE_ID"
RUN_DIR="$SESS_DIR"            # already scoped to this lane, if any
mkdir -p "$RUN_DIR"
FIX_PLAN_FILE="$RUN_DIR/fix-review-plan-<fix-slug>.md"
cat > "$FIX_PLAN_FILE" <<'PLAN_EOF'
# Bugfix Summary
Bug: <one-line bug>
Root cause: <file>:<line> — <what>
Fix: <one-line fix description>
Reproducing test: <test file>::<test name>
PLAN_EOF
```

Read and reconcile the existing native review record for this plan, lane, and `changes-review` role before launching anything. Resume its live handle, collect an already completed result, or reconcile an interrupted `launching` attempt; only a confirmed terminal or missing prior attempt permits a replacement.

Atomically write `state: launching` with `provider: native`, this role, plan/lane identity, and `reviewed_sha256` of the exact review anchor before the spawn call below. Use `review-state-protocol.md`. If the write fails or the current mode forbids it, defer the launch; do not create an unrecorded background job.

Use the spawn-agent tool exposed in the current Codex tool schema with `agent_type="changes-review"` and this message:

```
Plan file: <FIX_PLAN_FILE path>
User request: Bugfix — <one-line bug>
Changed files: [git status --short list]

Review the bugfix diff: quality and goal achievement. The "plan" is a one-page bugfix
summary, not a multi-task spec — judge compliance against the bug, not absent feature tasks.
Return ONLY valid JSON matching the changes-review schema. Include the plan file path in `plan_file`.
```

Immediately persist the returned `native_agent_id` and `state: running` atomically in that same record before waiting, independent work, or a handoff. If saving fails, retain and reconcile this handle; do not spawn again.

Keep the returned agent id, then use the wait mechanism exposed in the current Codex tool schema. Follow the actual parameters shown by the tools; do not invent a namespace or reuse a call signature from another Codex version.

At native collection, confirm terminal completion and atomically write `state: completed`; validate the final JSON schema and matching `plan_file`, then write `state: collected` with the consumed result identity. If terminal output remains invalid or unavailable after correction/recovery, write `state: incomplete` with the reason and follow the explicit fallback. Observation timeouts leave the original live state and handle intact.

Validate the final JSON schema and that `plan_file` matches `$FIX_PLAN_FILE`. If invalid, request correction from the same agent when possible. If unavailable, record the independent review as incomplete and self-review the fix; never report malformed or mismatched output as a passed review.

Lineage first — a finding outside the fix file, its test, and files the fix legitimately touched is mention-only regardless of severity. Otherwise: `must_fix` → fix now; `should_fix` → fix when single-site (else summarise and let the user decide); `suggestion` → mention. After any fix, re-run the targeted test + full suite. Then `rm -f "$FIX_PLAN_FILE"`.
CODEX-END -->

### 6.2 Approval gate (when enabled)

⛔ **The approval summary must contain what you actually ran and observed in Step 4.** If you cannot fill in `E2E:` with concrete evidence, Step 4 is not finished — go back rather than asking for approval.

**This gate comes before the commit and the merge, and that ordering is the point.** It is the workflow's single interaction point, so it has to sit in front of the one step that cannot be taken back. Asking after the squash merge leaves only two answers — approve what already landed, or revert it — which is not a gate.

Read `PILOT_PLAN_APPROVAL_ENABLED`. `"false"` → skip this gate entirely and continue at 6.3; the run is autonomous and merges without asking.

Otherwise summarise and ask, offering: `"Approve — done"`, `"Request changes"`, and `"Explain the fix in more detail"` (present in the first ask only; drop it from any re-ask to avoid loops).

⛔ **When no structured input tool is exposed and permitted for this approval**, read `$HOME/.pilot/agents/agent-gate-protocol.md` and follow it, supplying `GATE_NAME` = `Bugfix approval`, `OPTIONS` = the three above, `SENTINEL_PATH` = `none` (`/fix` registers no plan, so no stop guard is holding the session open). Ask in prose and end your turn. Never record the fix as approved because the form was unavailable, and never run 6.3 in the same turn as the ask — under orchestration this gate is the coordinator's only chance to see the diff before it lands.

```
AskUserQuestion(
  question="Bugfix complete.\n\nBug: <one line>\nRoot cause: <file>:<line> — <what>\nFix: <one-line description of the change>\nTests: reproducing test added (<test_name>), full suite green.\nReview: <none | changes-review: N findings, all resolved | Codex: approve | ...>\nE2E: <command/URL you ran and the concrete observation that proves the fix — e.g. 'curl /search -d {} → 200 with [results]', 'opened /tasks page, saved end_date=2026-05-15, list shows 2026-05-15', 'ran pilot register-plan ./foo.md PENDING → exit 0, plan visible in console'>\n\nReview the diff in the Console's Changes tab. Nothing has been committed or merged yet — approving does that next.",
  options=[<see list above>]
)
```

- **Approve** → continue to 6.3 (worktree mode: commit, then merge back; otherwise the fix is finished and stays uncommitted).
- **Request changes** → the user describes the problem freely. Treat it as a new investigation: Step 1.3 (re-trace) → Step 2 onward. Nothing has landed yet, so there is nothing to revert. Reviews re-run on the new fix scoped to files changed since the previous review, not the whole diff again.
<!-- CC-ONLY -->
  Re-run mechanics: codex-once keeps the companion to one run per invocation. For the native changes review, refresh `$FIX_PLAN_FILE` and ask the same agent for a new final JSON response covering files changed since the prior review; if it cannot resume, launch a replacement only after the original is terminal and retain the new handle.
<!-- /CC-ONLY -->
<!-- CODEX-START
  Re-run mechanics: spawn the managed `changes-review` custom agent again on the updated diff (rebuild the one-page summary first so its `Plan file:` anchor exists), listing only the files changed since the previous review.
CODEX-END -->
- **Explain the fix in more detail** → write the fuller walkthrough (causal chain trigger → root cause; why that boundary is the right place to fix; what the diff means line by line; alternatives considered and rejected). Change no code, then re-ask without the Explain option.

### 6.3 Worktree mode — single commit, then merge back

**Runs only after 6.2 approved**, or after 6.2 was skipped because `PILOT_PLAN_APPROVAL_ENABLED` is `"false"`. Everything below lands on the base branch, so it must never run in the same turn as an unanswered gate.

Only when a worktree is active — confirm with `~/.pilot/bin/pilot worktree detect --json <fix-slug> $LANE_FLAG` (add `--lane <id>` on a lane run), never a path glob. Bundle test + fix + any review-driven fixes into one commit:

```bash
git add <test_file> <fix_file>
git commit -m "fix: <one-line description>" -m "Root cause: <file>:<line> — <what was wrong and why>"
```

The conventional `fix:` prefix triggers a patch release if this branch ships. Keep the workflow's test, repair, and review-driven changes in this one commit. The body is the Step 1.5 statement with its `Confidence` tail dropped (the template already carries the `Root cause:` prefix — don't repeat it inside the placeholder); it gives the next debugger the confirmed cause straight from `git log`.

**Then merge back — `/fix` owns this, it is not the caller's to bolt on.** One Bash call, chained, so a failed sync can never be followed by a cleanup that deletes the work:

```bash
~/.pilot/bin/pilot worktree sync --json <fix-slug> $LANE_FLAG && \
  PROJECT_ROOT=$(~/.pilot/bin/pilot worktree cleanup --force --json <fix-slug> $LANE_FLAG | jq -r '.project_root') && \
  cd "$PROJECT_ROOT"
```

⛔ Never split sync, cleanup, and `cd` across Bash calls — a compaction between them loses the thread mid-merge.

**Exit codes.** `0` clean · `1` nothing landed · **`2` the squash landed but the base checkout's own uncommitted work could not be restored** and is sitting in `git stash list`. The `&&` chain stops on 2 by itself, deliberately leaving the worktree in place. Do NOT re-run cleanup to finish the job: surface the JSON's `stash_warning` and the `git stash pop` recovery first. `success: true` is still correct — the merge landed; only the unrelated local work is stranded.

**Lane contention.** Sync serializes on a repo-wide lock. A failure naming lane contention means a sibling held it past the timeout and **nothing was changed** — retry once it finishes.

**After a successful merge, re-run the full suite on the merged base branch** (Step 5.2's command). The base may have moved since the worktree forked, and a clean lane branch can still break on integration. This runs after the gate, so a failure here is not something the user can veto — if it fails, fix it on the base branch, re-run, and report both the breakage and the fix in 6.6. Do NOT leave a red base branch and report success.

### 6.4 Console notification

```bash
~/.pilot/bin/pilot notify plan_approval "Bugfix complete" "<one-line bug>" 2>/dev/null || true
```

Best-effort — don't block on failure.

### 6.5 Pre-report checklist

Every box must hold before you write the report. Any gap → return to the step that owns it.

- [ ] Reproducing test passes against the current code (Step 3.3); later edits have not invalidated that evidence.
- [ ] Full anti-regression suite green — fresh run (Step 5.2).
- [ ] E2E executed against the actual program, concrete evidence captured (Step 4).
- [ ] Enabled reviewers ran; every `must_fix` / `should_fix` resolved or escalated (6.1).
- [ ] Instrumentation clean — no fix-owned `SPEC-DEBUG:` markers or temporary diagnostics remain. Check only this repair's added lines; intentional output or pre-existing logging is not a defect.
- [ ] Diff is small and every changed line traces to the bug.
- [ ] Docs updated if the fix changed documented behaviour, a flag, or a config default — or "no doc impact" stated deliberately.
- [ ] Worktree mode: one bundled `fix:` commit. Otherwise: changes ready, no commit.

### 6.6 Report

```
Bugfix complete — <bug>.
Root cause: <file>:<line>.
Tests: 1 new reproducing test, full suite green.
Review: <none enabled | changes-review sub-agent / native changes-review + Codex, no blocking findings | N findings resolved>.
E2E: <command/URL run> → <observation that proves the symptom is gone>.
Docs: <files updated | no doc impact>.

Run /clear before starting new work — this resets context while keeping project rules loaded.
```

The `E2E:` line is **mandatory** — it is the record that the actual program was exercised, not just the unit tests.

### 6.7 Post-mortem flag (optional, one line)

You know more now than when you started, so ask once: **what would have prevented this bug?** If the answer is architectural — no clean test seam, hidden coupling, validation absent at the boundary the bad data crossed, a repeated near-miss in this area — name it in one line:

```
Follow-up (architectural): <one-line prevention opportunity, kept separate from the completed defect repair>.
```

Skip when the honest answer is "nothing structural — a typo / off-by-one / wrong default". Don't manufacture follow-ups.

ARGUMENTS: $ARGUMENTS
