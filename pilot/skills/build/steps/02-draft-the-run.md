## Step 2: Draft the Tasks and Criteria

This is the artifact that matters. It is deliberately thin — `/build` exists because you do not want to plan the whole thing first.

### 2.1 Write 3–7 tasks

Each task is a **title and an objective**, and nothing else:

```markdown
### Task 2: Render the comparison table from the trial rows

**Objective:** Build the table that shows each system's pass rate side by side, generated
from the data rather than hand-written. It is the section a reader looks at first.
```

- **No `Files:`, no `Key Decisions:`, no per-task `Definition of Done:`.** Those are the upfront planning `/spec` charges for. Here you find the files while building.
- **Order them the way you would actually work.** Task order is the running order; there is no dependency syntax.
- **Cover the whole artifact, roughly.** Three to seven tasks that together produce something judgeable. Not a decomposition of every file you will touch.
- **They will change.** Adding, splitting, and dropping tasks mid-round is expected and logged (Step 4). Drafting them precisely now buys nothing.

**Size each task as the largest slice you can finish and verify in one go.** Small is not the goal; *useful* is. A good task produces a working screen, a working endpoint, a real bug fixed, a section that reads end to end — something whose completion visibly moves a criterion. A bad task adds one more helper, wrapper, config file, or note: safe-looking, cheap to tick, and the criteria do not move.

⛔ **Safe does not mean small.** Safe means bounded, verified, and reversible — all of which a large slice can be. Decomposing into tiny tasks feels like risk management and is usually the loop finding a way to look busy for a round.

Use more tasks when dependencies or distinct outcomes require them. The 3–7 range is guidance, not permission to reduce the user's scope to the first subsystem.

### 2.2 Write 3–6 acceptance criteria

**Draft them from `## Summary`, not from scratch.** The oracle, the constraints, and the misfire are what Step 1.5 spent the user's attention establishing; a criterion that does not trace back to one of them is a criterion you invented after the fact.

**Two of the set have fixed jobs:**

- **One criterion is the oracle** — the observable that proves the user's outcome is actually true, not that the work was done. Mark it in the file. Every other criterion can pass while this one fails, and when that happens the run has built something well that nobody asked for. It is the criterion that must never be the one relaxed, waived, or ruled from a proxy.
- **One criterion catches the misfire** — the failure named in `## Summary` where the run passes everything and is still wrong. Often the oracle already does this; when it does, say so and move on. When it does not, that criterion is the one this set is missing.

These are judged **once per round, at the end**, never worked one at a time. Each one:

- **Rules pass or fail, never a score.** Scores drift upward every round: "7/10" becomes "8/10" with no change to the work.
- **Is one sentence, carrying one claim.** If it needs "and" three times, it is three criteria — split it. **This rule outranks the 3–6 band**: splitting a compound criterion into two is right even when it takes the list to seven or eight, and dropping a real criterion to get back inside the band is lowering the bar with extra steps. The band describes a well-drafted set; the split rule is what makes each one judgeable.
- **Is decidable from the finished artifact**, by someone who did not build it.
- **Names the evidence that settles it**, so a lazy judge cannot pass it by default.
- **Names obtainable evidence.** If a required criterion depends on an external process, keep it visible and record that dependency. Continue available work; do not drop or weaken a requested outcome because its evidence takes longer.

Include **at least one measurable criterion** when the goal has a measurable half — load time, bundle size, token cost, word count, pass rate, error rate. Taste plus a number beats taste alone.

| Weak | Strong |
|---|---|
| The hero section is compelling. | Our hero and Nike's, screenshotted at 1440px and shown unlabelled, and a viewer told nothing picks ours. |
| Good error handling. | Every failure mode the module documents has a test asserting the user-facing message, and the suite passes. |
| The writing is clear. | A reader new to the topic restates the core mechanism in one sentence after a single read. |
| ≥95% of rows carry a transcript, and the report discloses per-voice counts, and the table lists both architectures. | Three separate criteria. Split them. |

⛔ **Write these before building.** Criteria written after a first draft describe that draft — the standard quietly becomes whatever you happened to make.

### 2.2a Settle the branch, before the Buildout exists

**Parse the flags** off the argument string and strip them from the goal: `--worktree=yes|no`, `--new-branch`, `--lane <id>`. Default `--worktree=no` — the run works on the current branch, exactly as before.

**Where the work lands was settled in Step 1.5**, before any of this existed — it is one of the questions that round is for, offering the same three options `/spec` does: **Continue on current branch** (recommended) · **New branch from default branch** · **Use worktree (isolated, squash-merged after)**. Apply what it settled here. ⛔ Do not ask now: the Buildout is about to be registered and the stop guard is about to start holding the session, so a question at this point is one the run cannot cleanly pause for. No flag, and `PILOT_BRANCH_ISOLATION_ENABLED` not `"true"` → `--worktree=no`.

**For `--new-branch` or `--worktree=yes`,** read `$HOME/.pilot/agents/spec-branch-setup.md` and follow it with `<plan_slug>` = the Buildout slug, prefix `feat/`, and `<lane>` when one was supplied. Record the outcome in the header's `Worktree:` field below.

⛔ **`--lane <id>` implies `--worktree=yes` and fails closed.** Reject `--lane` with `--worktree=no` or `--new-branch`, and abort rather than continuing if the worktree cannot be created — a lane sharing the coordinator's checkout races every sibling's edits, which is the whole reason it is a lane.

**Everything downstream resolves against the run's checkout, not the project root** — the artifact the judge looks at (5.1a), the `## Changed Files` ledger (4.3), and Step 6's diff scope. Getting this wrong means judging one tree while building another.

**`$LANE_FLAG`** stands for `--lane <id>` on a lane run and for **nothing at all** otherwise. Every `register-plan` call in Steps 2, 4, 5 and 7 carries it. Substitute it literally each time — shell state does not survive between Bash calls, so there is no variable to rely on.

⛔ **Old-binary check, before the first lane-flagged call.** Run it once:

```bash
~/.pilot/bin/pilot register-plan --help 2>&1 | grep -q -- --lane && echo LANE_OK || echo LANE_UNSUPPORTED
```

`LANE_UNSUPPORTED` on a lane run → **abort and tell the user to update Pilot.** Do NOT fall back to an unflagged `register-plan`: that writes this lane's Buildout into the coordinator's `active_plan.json`, where a sibling overwrites it and the coordinator's stop guard blocks on a run it does not own — reinstating both defects while printing something that reads like a warning. On a non-lane run there is nothing to check; `$LANE_FLAG` is empty and every call is exactly as before.

### 2.3 Create the Buildout file

**Do this before any building** — the statusline and the Console pick it up immediately, and the stop guard starts holding the run open.

1. **Filename:** `docs/builds/YYYY-MM-DD-<slug>.md` — slug from the first 3–4 words of the goal (lowercase, hyphens). `mkdir -p docs/builds` first; the directory may not exist yet.

   **Base directory:** the **project root** on an ordinary run; **the worktree** when this run created one (2.2a). The Console accepts a worktree file whose slug matches that worktree's own (`spec-<slug>`), which the 2.2a setup guarantees — it derives both from the same slug. A Buildout dropped into an *unrelated* worktree is still filtered out and never appears, so never write it into a checkout this run does not own.

   If `docs/builds/` is gitignored, copy the finished Buildout back to the project root before the Step 7 merge, the same way `spec-verify` Step 8.1 does for plans — otherwise the squash carries no record of the run.

2. **Author email** (best-effort, omit the line if it fails):

   ```bash
   ~/.pilot/bin/pilot status --json 2>/dev/null | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('email',''))" 2>/dev/null
   ```

<!-- CC-ONLY -->
3. **Agent:** `Claude Code` if `$CLAUDE_CODE_ENTRYPOINT` is set, otherwise `Codex`.
<!-- /CC-ONLY -->
<!-- CODEX-START
3. **Agent:** `Codex`.
CODEX-END -->

4. **Write the file:**

   ```markdown
   # [Name] Buildout

   Created: [Date]
   Author: [email if available]
   Agent: [Claude Code|Codex]
   Status: PENDING
   Approved: No
   Rounds: 0
   Worktree: [Yes|No]
   Type: Build

   ## Summary

   **Goal:** [one sentence — the end state]

   **Oracle:** [the one observable signal that proves this outcome is actually true — from 1.5, in the user's own words where they gave them]

   **Misfire:** [in one sentence: how this run could pass every criterion and still be the wrong thing — and which criterion catches it]

   **Constraints:** [what must not change, what is ruled out — or omit the line]

   **Assumed:** [anything 1.5 decided for the user: questions switched off, an auto-continued form, a reference picked without asking — or omit the line]

   **Reference:** [named artifact] — re-obtain with `[exact command, URL, or path]`

   ## Acceptance Criteria

   - [ ] Criterion 1: [one sentence, decidable from the artifact, naming its evidence]
   - [ ] Criterion 2: ...
   - [ ] Criterion 3: ...

   ## Out of Scope

   - [anything the user named that this build is deliberately not doing, or omit the section]

   ## Progress Tracking

   - [ ] Task 1: [one-line summary]
   - [ ] Task 2: ...

   ## Implementation Tasks

   ### Task 1: [imperative title]

   **Objective:** [1–2 sentences — what this task produces and why.]

   ### Task 2: [imperative title]

   **Objective:** ...

   ## Round Log

   _No rounds yet._

   ## Changed Files

   _None yet._
   ```

   **Omit the `**Reference:**` line entirely when there is none** (Step 1.3). An empty or hand-waved reference is worse than no reference. `**Oracle:**` and `**Misfire:**` are never omitted — they capture the outcome and the failure the criteria must catch. `**Assumed:**` is omitted only when nothing was assumed.

   `Type: Build` is what makes the statusline render the loop and the Console file it under **Buildouts** — the header, never the directory, is what identifies a Buildout, so a file moved between `docs/plans/` and `docs/builds/` keeps working either way. `Status:` is a closed set — `PENDING` | `COMPLETE` | `VERIFIED`, bare keyword, no trailing prose. `Rounds:` starts at 0 and is incremented by the judge, never by hand. `Worktree:` records what 2.2a settled — `Yes` when this run owns an isolated checkout, `No` otherwise.

   **The two checkbox lists have different jobs.** `## Progress Tracking` carries `- [ ] Task N:` lines — that is what the statusline and Console count. `## Acceptance Criteria` carries `- [ ] Criterion N:` lines — those are the judge's, and they stay unticked until a judge pass ticks them. Every task in `## Progress Tracking` has a matching `### Task N:` body under `## Implementation Tasks`.

   **`## Changed Files` starts empty.** Step 4 appends to it, Step 6 stages and diffs exactly it (see 4.3). It is absent from the Console's displayed-sections allowlist, so it stays off the rendered Buildout and any share link — leave it that way.

5. **Register it — with an ABSOLUTE path:**

   ```bash
   ~/.pilot/bin/pilot register-plan "$PWD/docs/builds/<file>.md" "PENDING" $LANE_FLAG 2>/dev/null || true
   ```

   ⛔ **A relative path is resolved against the shell's current directory, which is not always the project root.** The Bash tool keeps its working directory between calls, so one earlier `cd` into a subdirectory silently makes `docs/builds/...` mean `<subdir>/docs/builds/...`. `register-plan` then prints `WARNING: plan registered, but the Pilot Console will NOT display it: ... is outside <subdir>/docs/builds` and the run proceeds with an invisible Buildout — no statusline, no Console, and a stop guard holding a file the user cannot see. Pass the absolute path, or `cd` to the project root in the same command. The same applies to every later `register-plan` in Steps 4, 5 and 7.

### 2.4 Have the criteria reviewed before they become the contract

Read `$HOME/.pilot/agents/review-state-protocol.md` before launching any enabled reviewer. Persist each returned native or companion handle atomically with the plan, lane, role, and lifecycle state before independent work; reload that record after compaction and before collection.

You wrote these criteria, so you are the last one who can tell they are undecidable. This is the one pre-loop round-trip worth paying for.

**Gate the two reviewers independently** — the Console exposes them separately, so neither may depend on the other. Skip 2.4 only when `PILOT_BUILD_REVIEW_ENABLED` is `"false"` **and** `PILOT_CODEX_BUILD_REVIEW_ENABLED` is not `"true"`.

**Slug** = the Buildout filename minus the `YYYY-MM-DD-` prefix and `.md`.

<!-- CC-ONLY -->
> **Native reviewer-launch protocol** (Step 6.5 reuses this with its own inputs)
>
> Read and reconcile the existing native review record for this plan, lane, and selected role (`build-review` here, `changes-review` when reused by Step 6.5) before launching anything. Resume its live handle, collect an already completed result, or reconcile an interrupted `launching` attempt; only a confirmed terminal or missing prior attempt permits a replacement.
>
> Atomically write `state: launching` with `provider: native`, this role, plan/lane identity, and `reviewed_sha256` of the exact review anchor before the spawn call below. Use `review-state-protocol.md`. If the write fails or the current mode forbids it, defer the launch; do not create an unrecorded background job.
>

> Launch with the actual `Agent` schema, using `subagent_type` and background execution when supported. Pass the Buildout path and required context. Request a read-only review and **ONLY valid JSON in the final response**, matching that agent's schema and identifying the supplied Buildout in `plan_file`.
>
> Immediately persist the returned `native_agent_id` and `state: running` atomically in that same record before waiting, independent work, or a handoff. If saving fails, retain and reconcile this handle; do not spawn again.
>

> Retain the returned agent/task handle. Consume the completed final response through the runtime's wait/result mechanism, including `TaskOutput` when exposed, or directly from a foreground `Agent` return. Do not ask the agent to write a findings file, poll a file for completion, or invent a `jsonSchema` launch/frontmatter field.
>
> At native collection, confirm terminal completion and atomically write `state: completed`; validate the final JSON schema and matching `plan_file`, then write `state: collected` with the consumed result identity. If terminal output remains invalid or unavailable after correction/recovery, write `state: incomplete` with the reason and follow the explicit fallback. Observation timeouts leave the original live state and handle intact.
>

> Validate the final JSON and `plan_file`. Ask the same agent to correct malformed or mismatched output when supported; otherwise record the independent review as incomplete and self-review. Quiet output and observation timeouts do not justify a restart: inspect the original handle and wait while it is live. Replace it only after confirmed terminal failure or a missing handle.
>
> Persist the native handle and validated result identity using `review-state-protocol.md`. If native read-only planning is active, defer the launch until native exit permits the durable record; retaining a handle only in context is insufficient for recovery.



**Native reviewer** — when `PILOT_BUILD_REVIEW_ENABLED` is not `"false"`: run the protocol with `subagent_type="build-review"`, inputs = the goal as the user stated it and the reference choice if one was made.

**Codex companion** — when `PILOT_CODEX_BUILD_REVIEW_ENABLED` is `"true"`, whether or not the native reviewer ran. Resolve `SESS_DIR` to this run's session/lane directory using `review-state-protocol.md`. Skip if `$SESS_DIR/codex-build-review-ran-<slug>.flag` exists (codex-once). Otherwise follow `$HOME/.pilot/agents/codex-companion-protocol.md` with these explicit supplies:

| Protocol input | Value for Buildout review |
|---|---|
| `PROMPT_TEMPLATE` | `$HOME/.pilot/agents/build-review-codex.md` |
| `ROLE` | `build-review` |
| `LANE_ID` | Original parsed `--lane <id>` value, or empty for this main-session run |
| `SLUG` | Buildout filename minus the `YYYY-MM-DD-` prefix and `.md` |
| `CODEX_FLAG` | `$SESS_DIR/codex-build-review-ran-<slug>.flag` |
| `{{PLAN_PATH}}` | Absolute Buildout path |
| `{{PLAN_GOAL}}` | The goal sentence |
| `{{CONTEXT_FILES}}` | Newline-separated absolute paths named as references or patterns |

⛔ **`task --prompt-file`, never `adversarial-review --base`.** A diff-scoped launch reviews the working tree, and at this point nothing has been built — so the reviewer would receive an empty diff (and nothing at all where `docs/builds/` is gitignored). `task` lets Codex read the Buildout directly.

Launch Codex first so it overlaps, then collect the native reviewer. If the companion returns nothing after its one retry, continue without it and say so in 2.5.
<!-- /CC-ONLY -->
<!-- CODEX-START
Read and reconcile the existing native review record for this plan, lane, and `build-review` role before launching anything. Resume its live handle, collect an already completed result, or reconcile an interrupted `launching` attempt; only a confirmed terminal or missing prior attempt permits a replacement.

Atomically write `state: launching` with `provider: native`, this role, plan/lane identity, and `reviewed_sha256` of the exact review anchor before the spawn call below. Use `review-state-protocol.md`. If the write fails or the current mode forbids it, defer the launch; do not create an unrecorded background job.

Use the spawn-agent tool exposed in the current Codex tool schema with `agent_type="build-review"`. Supply this message:

```
Plan file: <buildout-path>
User request: <the goal as the user stated it>
Clarifications: <the reference choice, if one was made>

Audit the tasks and acceptance criteria before the build-judge loop starts.
Return ONLY valid JSON matching the build-review schema.
Include the Buildout path in the `plan_file` field.
```

Immediately persist the returned `native_agent_id` and `state: running` atomically in that same record before waiting, independent work, or a handoff. If saving fails, retain and reconcile this handle; do not spawn again.

Keep the returned agent id, then use the wait mechanism exposed in the current Codex tool schema. Follow the tool's actual parameter schema rather than inventing a namespace or copying parameters from another Codex version.

At native collection, confirm terminal completion and atomically write `state: completed`; validate the final JSON schema and matching `plan_file`, then write `state: collected` with the consumed result identity. If terminal output remains invalid or unavailable after correction/recovery, write `state: incomplete` with the reason and follow the explicit fallback. Observation timeouts leave the original live state and handle intact.

Validate the final JSON schema and `plan_file`. On malformed or mismatched output, request correction from the same agent when possible. If no valid result is available, record the independent review as incomplete and self-review the contract before proceeding; do not call the missing review passed.
CODEX-END -->

**Validate every finding against the actual plan, evidence, and requested scope. Fix every supported in-scope `must_fix` and `should_fix` before 2.5.** Treat `suggested_fix` as a proposal to evaluate, not authoritative replacement wording. Apply a suggestion only when it independently improves the requested result within scope; speed alone does not justify additional work. Record unsupported findings with the evidence that resolves them. Supported blocking findings must be closed before the criteria become the contract.

### 2.5 Post the contract, then start

Print the goal, the numbered tasks, and the numbered criteria in the conversation. If a reviewer changed anything, say so in one line — which criteria moved, and why. Name the Buildout path so the user can open, annotate, or share the file.

⛔ **This is a notification, not a gate.** Do not end your turn, do not ask whether it looks right, do not offer to change anything. The next action after printing it is Step 3, in the same turn. A user who wants something different says so, and 3.0 picks up Console annotations at the top of every round.

**Done when:** the Buildout file exists, is registered, every criterion states its pass condition, every task has an objective, the reviewers' blocking findings are closed, and both lists have been printed.
