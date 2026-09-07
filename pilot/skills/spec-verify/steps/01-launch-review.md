## Phase A — Finalize the Code

## Step 1: Early Background Review Launch

Read `$HOME/.pilot/agents/review-state-protocol.md` before launching any enabled reviewer. Persist each returned native or companion handle atomically with the plan, lane, role, and lifecycle state before independent work; reload that record after compaction and before collection.

### 1a: Establish this review's identity

Derive this plan's slug and retain the current plan path, lane (if any), and the actual agent/task handle returned by each native reviewer launch. Step 3 consumes that handle's completed final JSON response.

Prior planning findings, saved JSON, or another run's transcript are not completion evidence for this review. Do not sweep findings files or poll their timestamps. The parent may persist a validated result for bookkeeping only when writes are permitted, scoped to this plan and lane; a saved copy never replaces the authoritative agent result.



### 1b: Resolve the review diff scope and stage (before ANY reviewer launches)

**Resolve `DIFF_SCOPE` once with the resolver — every reviewer launch below AND every Step 2 audit uses exactly this value.** ⛔ Never derive it by hand; deriving the range from prose is what let issue #168 hide at nine sites at once.

> **`$LANE_FLAG`** is `--lane <id>` when this run was dispatched as an orchestration lane, and **nothing at all** otherwise — the value the invocation parsed from its arguments. It keeps worktree and plan identity scoped to this lane; an unflagged call resolves a different identity and silently finds nothing (issue #174).

```bash
SCOPE=$(~/.pilot/bin/pilot review-scope --slug <plan-slug> $LANE_FLAG --json 2>/dev/null \
  | python3 -c 'import json,sys; print(json.dumps(json.load(sys.stdin)))' 2>/dev/null)
echo "${SCOPE:-UNAVAILABLE — use the manual fallback below}"
# {"mode":"worktree","base_ref":"dev","diff_range":"dev...HEAD","diff_command":"git diff dev...HEAD"}
# {"mode":"working-tree","base_ref":"HEAD","diff_range":"HEAD","diff_command":"git diff HEAD"}
```

⛔ The `json.load` parse is a guard, not decoration. A `pilot` binary predating `review-scope` does not fail on it — it prints the "runs directly inside Claude Code" transition banner and exits **0**, so without the parse `$SCOPE` silently becomes that banner text. Empty `$SCOPE` means unavailable; use the manual fallback.

⛔ **`$LANE_FLAG` is load-bearing here, exactly as it is on every `pilot worktree` call.** A lane's branch is `spec/<slug>-<lane>` and its worktree registration lives under `lanes/<lane>/`, so an unflagged resolve finds neither and falls back to `git diff HEAD` — which on a lane that commits per task is EMPTY. Every reviewer then reads nothing and reports clean (issue #176).

**`DIFF_SCOPE` = `git diff <diff_range> -- <changed files>`**, and `mode` decides whether to stage:

| `mode` | Meaning | Action |
|---|---|---|
| `working-tree` | Uncommitted — `spec-implement` did not commit (the `Worktree: No` default) | **Stage the change's own files first**, so new files appear in the diff |
| `worktree` | Per-task-committed on the worktree branch | **Do NOT stage.** A plain `git diff HEAD` here reviews an EMPTY diff |

⛔ **If the JSON carries a `warning`, STOP and read it before launching anything.** The scope degraded to the working-tree diff, which misses every commit already on the branch — and when the work is fully committed there, that diff is empty and every reviewer below reviews nothing while reporting clean. The warning names what went wrong (usually a missing or wrong `--lane`); fix that and re-resolve rather than reviewing the degraded scope.

**If the command is unavailable** (older `pilot` binary), resolve by hand:

- Uncommitted → `git diff HEAD`.
- Worktree mode → `git diff <base_ref>...HEAD`, with `<base_ref>` from `~/.pilot/bin/pilot worktree detect --json <slug> $LANE_FLAG`.
- Three dots, always. Two dots diff against the base branch's live tip, rendering its post-fork commits into the review inverted.
- The *detected* base branch, never a hardcoded `main` — a worktree forked from `dev` would otherwise drag in every `dev`-only commit.
- `pilot worktree status` is the wrong command here: it takes no slug and is session-scoped, not plan-scoped.

Reviewing an unstaged tree misfires both ways: a reviewer reading `git status --untracked-files=all` reports a spurious `critical` ("deliverable depends on untracked files"), while one reading only `git diff HEAD` silently omits new files. Staging fixes both:

```bash
# `mode: working-tree` ONLY — stage the plan's files (paths from each task's `Files:` block)
# plus files named under the plan's `## Deviations` section — NOT unrelated dirty or untracked files.
git add <path/from/plan/Files-block-1> <path/from/plan/Files-block-2> ...
git status --short --untracked-files=all | grep '^??' || true   # anything still untracked must NOT be part of this change
```

A bare `git add -N` is not enough — `git status` still treats the path as untracked and a later commit can record empty content. **Staging is not committing**: the commit still waits for the review, doc-sync, and the Phase B worktree sync. `git add` is pre-authorized; the push is not.

**Mixed ownership:** if a listed file already contains unrelated user or concurrent edits, a whole-file `git add` is not a valid scope boundary. Preserve the index and distinguish this run's hunks using scoped staging or an isolated review artifact. Do not include unrelated work merely because it shares a path.

**Reviewable file preflight:** the `Files:` block must contain at least one non-ignored repository artifact. `docs/plans/...` is workflow state and may be gitignored, so it cannot be the sole review target — and do NOT `git add -f` an ignored plan file to force it in. If every planned file is ignored, outside the repo, or only the plan itself, set `Status: PENDING`, add a fix task producing a reviewable non-production artifact, and return to implementation before launching any reviewer.

---

<!-- CC-ONLY -->
#### Launch the changes-review sub-agent NOW, in the background

**Only when `PILOT_CHANGES_REVIEW_ENABLED` is not `"false"`.** It works while you run the Step 2 automated checks, and Step 3 collects its completed final JSON response.

⛔ **This sub-agent is the changes review — there is no deeper mode to select.** `Skill(skill='code-review', ...)` is rejected (`disable-model-invocation`), so reaching for it here yields no review at all. `/code-review` is the user's to type.

Read and reconcile the existing native review record for this plan, lane, and `changes-review` role before launching anything. Resume its live handle, collect an already completed result, or reconcile an interrupted `launching` attempt; only a confirmed terminal or missing prior attempt permits a replacement.

Atomically write `state: launching` with `provider: native`, this role, plan/lane identity, and `reviewed_sha256` of the exact review anchor before the spawn call below. Use `review-state-protocol.md`. If the write fails or the current mode forbids it, defer the launch; do not create an unrecorded background job.

Use the plan identity from 1a and retain the returned native agent/task handle as `CHANGES_REVIEW_AGENT_ID`.

```
Agent(
  subagent_type="changes-review",
  run_in_background=true,
  prompt="""
  **Plan file:** <plan-path>
  **Changed files:** <paths from the plan's Files: blocks + files named under the plan's ## Deviations section>
  **Runtime environment:** <plan's Runtime Environment section, if present>
  **Base ref:** <the `base_ref` field from the Step 1b resolver output, verbatim. Substitute the real value; never leave the placeholder, and never let the reviewer fall back to a guessed branch name.>
  **Diff range:** <the `diff_range` field from the Step 1b resolver output, verbatim.>

  Review the diff (`git diff <diff_range> -- <changed files>`, exactly as resolved in Step 1b) against the plan: compliance, quality, goal achievement.
  Remain read-only. Return ONLY valid JSON matching the changes-review schema as your final response.
  IMPORTANT: Include the plan file path in your output JSON as the "plan_file" field.
  """
)
```

Immediately persist the returned `native_agent_id` and `state: running` atomically in that same record before waiting, independent work, or a handoff. If saving fails, retain and reconcile this handle; do not spawn again.

Use the runtime's actual handle-based wait/result mechanism in Step 3, including `TaskOutput` when exposed. Do not request or poll an agent-authored findings file.

Step 3 performs collection after the independent automated checks. At native collection, confirm terminal completion and atomically write `state: completed`; validate the final JSON schema and matching `plan_file`, then write `state: collected` with the consumed result identity. If terminal output remains invalid or unavailable after correction/recovery, write `state: incomplete` with the reason and follow the explicit fallback. Observation timeouts leave the original live state and handle intact.

#### Codex adversarial review (optional — launch NOW, in the background)

**Only when `PILOT_CODEX_CHANGES_REVIEW_ENABLED` is `"true"`** (from Step 0). It works in the background through Step 2's checks and Step 3's collection.

**Codex-once:** at most one companion run per `/spec` invocation. Verify-phase iterations — re-verify after fixes, review-gate annotation fixes — never trigger a second run.

```bash
SESS_ID="${CLAUDE_CODE_SESSION_ID:-${CODEX_THREAD_ID:-${PILOT_SESSION_ID:-}}}"
case "$SESS_ID" in ""|*[!A-Za-z0-9_-]*) echo "Review state needs a confirmed session identity" >&2; exit 1 ;; esac
SESS_DIR="$HOME/.pilot/sessions/$SESS_ID"
[ -z "$LANE_ID" ] || SESS_DIR="$SESS_DIR/lanes/$LANE_ID"
CODEX_FLAG="$SESS_DIR/codex-changes-review-ran-<plan-slug>.flag"
[ -f "$CODEX_FLAG" ] && echo "Codex already reviewed this plan in this session — skipping (codex-once)."
```

Otherwise **read `$HOME/.pilot/agents/codex-companion-protocol.md` and follow §1–§3 now** (locate → render → launch). Step 3 runs §4–§6. Supply:

| Protocol input | Value for changes review |
|---|---|
| `PROMPT_TEMPLATE` | `$HOME/.pilot/agents/changes-review-codex.md` |
| `ROLE` | `changes-review` |
| `LANE_ID` | Original parsed `--lane <id>` value, or empty for this main-session run |
| `{{PLAN_PATH}}` | absolute path to the plan file |
| `{{PLAN_GOAL}}` | the Goal sentence from the plan's `## Summary` |
| `{{BASE_REF}}` | the `base_ref` from the Step 1b resolver, verbatim — `HEAD` in working-tree mode (the template then falls back to the staged `git diff HEAD`), the detected base branch in worktree mode. Never a hardcoded branch name. |
| `{{CHANGED_FILES}}` | the paths from each task's `Files:` block |
| `SLUG` | `<plan-slug>` |
| `CODEX_FLAG` | the path above |

Carry `JOB_ID` and `PROMPT_FILE` forward to Step 3. If the job never registers, skip Step 3's Codex collection and rely on the changes review alone; if Changes Review is also disabled, no automated review runs this iteration — record that gap explicitly in the verification report.

**Do NOT wait** — proceed to Step 2 immediately.
<!-- /CC-ONLY -->
<!-- CODEX-START
**If `PILOT_CHANGES_REVIEW_ENABLED` is `"false"` (from Step 0),** skip the rest of this step and proceed directly to Step 2 (Automated Checks).

**When enabled:** launch the managed Codex custom agent immediately. It runs while automated checks execute in Step 2.

Gather context first:

```bash
git status --short
```

Collect: changed files list, runtime environment info, test framework constraints, and plan risks section. Derive the plan slug from the plan filename by stripping the date prefix and `.md`.

Read and reconcile the existing native review record for this plan, lane, and `changes-review` role before launching anything. Resume its live handle, collect an already completed result, or reconcile an interrupted `launching` attempt; only a confirmed terminal or missing prior attempt permits a replacement.

Atomically write `state: launching` with `provider: native`, this role, plan/lane identity, and `reviewed_sha256` of the exact review anchor before the spawn call below. Use `review-state-protocol.md`. If the write fails or the current mode forbids it, defer the launch; do not create an unrecorded background job.

Use the spawn-agent tool exposed in the current Codex tool schema with `agent_type="changes-review"` and this message:

```
Plan file: <plan-path>
User request: <original task description that invoked $spec>
Changed files: [file list]
Base ref: <the `base_ref` field from the Step 1b resolver output, verbatim — never a guessed branch name.>
Diff range: <the `diff_range` field from the Step 1b resolver output, verbatim.>
Runtime environment: [how to start, port, deploy path]
Test framework constraints: [what it can/cannot test]

Review implementation: compliance, quality, and goal achievement.
Return ONLY valid JSON matching the changes-review schema.
Include the plan file path in the `plan_file` field.
```

Immediately persist the returned `native_agent_id` and `state: running` atomically in that same record before waiting, independent work, or a handoff. If saving fails, retain and reconcile this handle; do not spawn again.

Capture the returned id as `CHANGES_REVIEW_AGENT_ID`. Follow the current tool's actual parameters rather than copying a namespace or signature from another Codex version.

After spawning, atomically persist `CHANGES_REVIEW_AGENT_ID` in the `changes-review` record from `review-state-protocol.md`, including this plan and lane identity.

Step 3 performs collection after the independent automated checks. At native collection, confirm terminal completion and atomically write `state: completed`; validate the final JSON schema and matching `plan_file`, then write `state: collected` with the consumed result identity. If terminal output remains invalid or unavailable after correction/recovery, write `state: incomplete` with the reason and follow the explicit fallback. Observation timeouts leave the original live state and handle intact.

Do NOT wait here. Proceed directly to Step 2.

Self-review the implementation diff before proceeding: `git diff --stat` to verify scope matches the plan, and spot-check changed files for obvious issues (security, missing error handling, dead code).
CODEX-END -->
