## Step 4: Build the Task List

Work every open task in `## Progress Tracking`, in order. When they are all ticked, go to Step 5 and judge. **Do not judge mid-pass** — judging a half-built artifact spends a round to learn what you already knew.

### 4.0 Re-read the annotations at the top of every round

One cheap read of `docs/builds/.annotations/<buildout-basename>.json` before the round's first task, folded in exactly as 3.0 describes, then `rm -f`. This is the user's only way into a loop that never stops to ask, so a round that skips it can spend itself ignoring a correction that was already waiting. Missing file or empty `planAnnotations` → nothing to do, one line of nothing, carry on.

### 4.1 Work a task

For each `- [ ] Task N:`:

1. Read its `**Objective:**` under `## Implementation Tasks`.
2. Build it. Find the files now — that is the part `/build` deliberately did not plan.
3. Append every path you created or modified to `## Changed Files` (4.2).
4. Tick `- [x] Task N:` in `## Progress Tracking` the moment it is done, not at the end of the round.

The project's rules apply in full inside the loop, and so does the least that works (`development-practices.md`). The criteria raise the standard for the output; they do not license a mess behind it.

**A task is not done while it is red.** Never tick a task whose tests fail or whose files carry open diagnostics.

⛔ **A failing command makes a task blocked, not done — and the failure stays visible as a failure.** Do not move it into prose ("mostly passing", "one unrelated flake"), do not tick the task and mention it in the round log, and do not narrow the command until it goes green. This is an observed failure mode in autonomous loops, not a hypothetical: the pressure to keep the round moving turns a red command into a sentence, and the sentence validates. Record the command and its status as a pair, and let a red one hold the task open.

⛔ **Ticking is how a task finishes, not bookkeeping you do afterwards.** The tick, the `## Changed Files` append, and the round-log line are one edit, made when the work goes green. `## Progress Tracking` is the only place task state exists — the statusline counts those boxes, the stop guard reads them, and the round that resumes after a compaction has nothing else to go on. A task whose work is done and whose box is still empty is an unfinished task, however green it was; your memory of having finished it does not survive the turn.

⛔ **Never name a task number in prose you have not just read out of the file.** "Starting Task 6" is a claim about `## Progress Tracking`, and the user is reading that same block through the statusline. Read it, then narrate — and when the two disagree, the file is right and the sentence is the bug. This is an observed failure mode: the narration runs ahead of the boxes, the statusline says `3/7` while the conversation says Task 6, and the user is left to catch it.

**A task waiting on a long job inside this session** — a re-run, a data collection, a build that takes twenty minutes — is not blocked. 4.6 is for what finishes *outside* the session; this one lands while you are still here, so it stays open and unticked until it does, and the round does not end without it. You may work a later task while it runs, on two conditions:

- **Say it in the same breath you say the number in** — "Task 4 is still running (~117/324); working Task 5 while it finishes." A silent jump to a later number is exactly what makes the statusline look wrong.
- **Nothing renumbers.** Task 4 stays Task 4 and stays unticked. Working ahead never reorders `## Progress Tracking`, never quietly converts a running task into a dropped one (4.4), and never lets 4.7 fire early — `Status: COMPLETE` needs *every* box ticked, the running one included.

**Standing stop conditions.** These halt the task and go in `## Round Log` instead of being improvised around:

- The behaviour the objective names is **ambiguous** and the artifact cannot settle it — do not pick a reading and build it silently; note the reading you took and why, so the judge and the report both carry it.
- **Verification failed twice** on the same task with different fixes — that is a wrong diagnosis, not a third fix. Re-read the failure from the top.
- The task needs a change **outside anything this run has touched or was asked to touch** — widening scope mid-task is how a build starts editing the codebase around it. Note it, and let the lineage rule decide.

### 4.2 Code tasks: test first

`testing.md` is the contract; the short form:

- **RED** — one minimal test for the behaviour the objective names, failing for that reason and not on a typo.
- **GREEN** — the simplest thing that passes. **REFACTOR** — with tests green.

Name the production change that would make the test fail before writing the assertion; if you cannot, it is a change detector — test the observable behaviour instead. Then run the mutation check: wrong constant, wrong branch, missing side effect, empty return, missing validation — each must fail something.

**Parsimony:** reuse existing behavioral coverage and add tests for uncovered behavior or distinct integration boundaries. Follow the project's structure without a class-count quota.

**Exempt:** prose, design, research, docs, config — say so in one line rather than inventing a test.

For a low-risk change already covered by an existing check, record that check and why it covers the change in `## Round Log`; a new test is unnecessary. Behavior changes and bug fixes need a regression signal before production edits when practical.

### 4.3 Keep the Changed Files ledger current

Append every path you create or modify to `## Changed Files`, in the same edit that ticks the task. A path enters only when this run wrote to it, and Step 6 stages nothing outside it. When a listed file already contained user or concurrent edits, preserve and distinguish those hunks; a file-level ledger alone does not authorize staging every hunk. The conversation is not an inventory; compaction erases it.

⛔ **Record paths repo-relative, never as absolute worktree paths.** On a `Worktree: Yes` run the files live under the checkout, but Step 6 stages this ledger and Step 7 merges it back to the base branch, where an absolute `/…/.worktrees/spec-<slug>-<hash>/src/x.ts` resolves to nothing. `src/x.ts` is correct in both trees.

### 4.4 Tasks are allowed to change — that is the design

`/build` skips upfront planning precisely so the task list can absorb what you learn. When the work teaches you something:

- **Add a task** when you find real work the draft missed.
- **Split a task** that turned out to be two.
- **Drop a task** that turned out to be unnecessary, and say why.

⛔ **Watch what the added tasks look like.** Two tiny ones in a row — a helper, a wrapper, a config file, a note — and the round has stopped moving criteria. Stop adding and ask which criterion the *next* task closes; if the answer is none, the task is busywork with a checkbox. A tiny task earns its place when it unblocks a large one, isolates a failure, or the risk is genuinely high; never as a third one in a row.

Every change gets one line in `## Round Log`, and `## Progress Tracking` and `## Implementation Tasks` are updated in the same edit so they never disagree. A task list that ends the run looking nothing like the drafted one is a successful run, not a failed plan — as long as the criteria did not move.

⛔ **The criteria do not change here.** Only Step 5, and only out loud.

⛔ **Dropping a task a criterion depends on is a criterion change.** Before dropping, ask whether any criterion's evidence needs that task. If so, removing it quietly lowers the bar — so **keep the task**. There is no gate to take it to and no one to relax it for you: a criterion only moves under 5.4's rules, out loud and recorded, and "the task was inconvenient" is not one of them.

### 4.5 Tool discipline

Loop pressure pushes toward batching everything into one giant call. It produces unreadable diffs, corrupted files, and orphaned processes. Inside the loop:

- **Use `Edit` / `Write` for every file change** — including the Buildout file itself. ⛔ Never patch a file with a `python3 - <<'PY' ... s.replace(...)` heredoc, `sed -i`, or any other string surgery. If `Edit` feels awkward, read the file first; that is the fix.
- **One purpose per `Bash` call.** Do not chain an edit, a formatter, a linter, a test run, and a render into a single command — when it fails you cannot tell which half broke.
- **Own process lifecycles.** Keep handles for processes this run starts, reuse a needed test server across judge/verify steps, and stop owned processes when no longer needed. Never kill a user's or another session's service.
- **One line of narration per task.** The round log is the record; the conversation is not the report. Save the writing for Step 6.

Keep work in the active agent unless a concrete task is independent and benefits materially from parallel execution or isolated context. Use the minimum number of subagents, never fan out duplicate perspectives, and do not ask the user to approve qualifying delegation. Keep concurrent writes non-overlapping, retain returned ids, inspect the resulting files, and run fresh verification before ticking an agent-owned task.

### 4.6 When the work is blocked on something outside this session

If the only remaining work is waiting on a process that will not finish while you are here — a multi-hour data collection, a third-party review, a deploy queue, a credential someone else has to issue — **that is not a round.** Spinning up side work and calling it progress is how a three-round run becomes fourteen.

⛔ **Context pressure is not one of these.** The test is what the run waits on: something in the world (legitimate) or its own context window (not). Everything needed is in the Buildout and compaction is expected — re-read it and keep working. Never tick a task, pass a criterion, or reach Step 7 because the window is filling up.

Stop and hand back:

1. Tick every task you genuinely finished.
2. Append one `## Round Log` line naming what is blocked and precisely what would unblock it.
3. Touch the hand-back sentinel so the stop guard lets the session pause:

   ```bash
   BUILD_SESS="${CLAUDE_CODE_SESSION_ID:-${CODEX_THREAD_ID:-${PILOT_SESSION_ID:-default}}}"
   mkdir -p "$HOME/.pilot/sessions/$BUILD_SESS" && touch "$HOME/.pilot/sessions/$BUILD_SESS/build-handback-pending"
   ```

4. Go to **Step 7** and report — what is done, what is blocked, what unblocks it. Skip Step 6: the artifact is half-built by design, so there is nothing coherent to verify. Leave `Status: PENDING`; the run resumes when the user comes back with the thing it was waiting for.

### 4.7 Hand the round to the judge

Once every `- [ ] Task N:` is ticked, mark the round's build half done **before** judging:

1. Set `Status: COMPLETE` in the Buildout.
2. Register it:

   ```bash
   ~/.pilot/bin/pilot register-plan "<buildout_path>" "COMPLETE" $LANE_FLAG 2>/dev/null || true
   ```

`COMPLETE` means *every task is ticked and the judge pass is outstanding* — the same meaning it carries in `/spec`, where it marks implementation done and verification pending. The statusline flips to `judge` for the duration of the pass, and the stop guard switches to demanding the judge run. Setting it only after judging succeeded would make the `judge` phase invisible and would tell the stop guard the opposite of the truth.

**Done when:** every task is ticked and `Status: COMPLETE` is registered — then Step 5. Or the run is blocked per 4.6 — then Step 7.
