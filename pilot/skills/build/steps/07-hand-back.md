## Step 7: Hand Back

### 7.1 Check you are allowed to be here

Name which of the four arrivals applies before anything else: **Complete** (every criterion ticked by a judge pass), **Ceiling** (a real judge pass ran and `Rounds:` hit 4 at 5.3), **Blocked** (4.6's external blocker, named), or **Unachievable** (5.5's exit, its four conditions met).

⛔ **None of the four holds → you are not at hand-back.** An unticked task, an unjudged criterion, or a round that stopped early is Step 4. There is no fifth arrival and no partial one. "The user might want to look at it now" is not an arrival either — this run does not check in.

### 7.2 Close the Buildout

**Ceiling reached with criteria still failing (5.3):** leave `Status: PENDING`, registered, with the failing criteria unticked and their reasons in `## Round Log`. Do NOT set `VERIFIED` — nothing verified them. The `build-handback-pending` sentinel touched in 5.3 lets the session stop. Report (7.3) and finish.

**Blocked outside this session (4.6):** leave `Status: PENDING`, registered. The run is waiting, not finished, and the Buildout is how it resumes. The sentinel touched in 4.6 lets the session pause. Report and finish.

**Every remaining criterion unachievable (5.5):** leave `Status: PENDING`, registered, with each unachievable criterion unticked, its blocker named, and the two approaches that failed recorded. The sentinel touched in 5.5 lets the session stop. Report and finish.

**Complete:** report (7.3), then run the evidence gate (7.4) and write `VERIFIED` yourself. Nothing waits on a reply.

**Complete, but verification was switched off (6.0):** leave `Status: COMPLETE`, registered, with the `Verification: disabled` row in `## Not Verified`. The sentinel touched in 6.0 lets the session stop. Report, and lead with the fact that the criteria passed and nothing checked the code behind them. ⛔ `VERIFIED` is not available on this path — 7.4's check 2 fails by construction, and that is the toggle working, not a problem to route around.

⛔ **Never tick a criterion you did not judge**, and never set `VERIFIED` to tidy the statusline or to end a long session. An unresolved criterion recorded honestly is a good outcome; a ticked one nothing verified is the failure this workflow exists to prevent — and with the human gate gone, 7.4's three checks are what stands in its place.

### 7.3 Report

This report is the whole of the user's visibility into a run they did not supervise. Everything they would have caught at a gate, they now catch here — so it is written to be checked, not to be reassuring.

Lead with what now works, then the evidence:

- **The oracle criterion first, with the signal that settled it.** It is the one the user actually cares about; everything else is support. If it failed, that is the headline, whatever else passed.
- **Every other criterion, with the one line of evidence that settled it.** Not "all criteria pass" — the evidence *is* the report. Failing and unachievable ones get the same treatment: what fails, and why it would not close.
- **The misfire named at Step 1.5, and what ruled it out.** You wrote down how this run could pass everything and still be wrong; say which evidence shows it did not happen.
- **Rounds it took**, and what each one closed.
- **How the task list changed** — added, split, dropped. Often the most useful paragraph for the reader.
- **Any criterion that moved**, with the before and after and which of 5.4's two reasons applied.
- **What you assumed** — anything Step 1.5 decided for the user, or asked and had auto-continue on. They never saw it happen; this is where they find out.
- **From Step 6:** the checks that ran, the live-target tier reached, the reviewer findings closed, docs touched or "no doc impact", and the `## Not Verified` list verbatim.
- **On a `Worktree: Yes` run:** that the squash landed, and what it carried (7.6).
- **Where the artifact is** and the command to see it.

### 7.4 The evidence gate

There is no approval gate. `VERIFIED` is not granted by a reply, it is earned by what is written in the file — so these three checks are the only thing between a finished run and a run that says it is finished.

Before writing `VERIFIED`, all four must be true:

1. **Every criterion in `## Acceptance Criteria` is `- [x]`**, each ticked by a judge pass that had evidence it could point at (5.1). One unticked criterion means you are at Ceiling or Unachievable, not Complete — 7.2, not here.
2. **`## Verification Record` exists** (written by Step 6.9) and Step 6 actually ran. Verification switched off is 6.0's path, which ends `COMPLETE` and never reaches here.
3. **`## Not Verified` exists.** "None" is a valid entry; an absent section is not.
4. **Every layer in 6.10's table is either evidenced in `## Verification Record` or disclosed in `## Not Verified`.** Walk the table and check them off one by one — suite, types, lint, build, runs-at-all, user-facing paths, code review, docs, regression. A layer that appears in neither section is the gap this check exists to catch.

Any one missing → you are not finished. Go get the missing thing rather than writing the status.

⛔ **Check 4 is the one that decays.** By this point the run has been going for a while, everything looks green, and re-walking a nine-row table feels like ceremony. It is the last check anyone performs on this work — a human gate would have asked "did you run the tests?" and there is no human gate. Walk it.

⛔ **Do not ask the user to approve, and do not wait for a reply before writing `VERIFIED`.** Report (7.3), pass these three checks, write the status, and end the run in the same turn. `AskUserQuestion` at this point is the workflow refusing to finish; a run that reaches here has already cleared every criterion it set itself and verified the code behind them.

⛔ **Never write `VERIFIED` around a missing check by declaring it "not applicable".** The rows in `## Not Verified` are how a gap gets stated. A run may finish with gaps; it may not finish by hiding them.

**Issues the user raises afterwards** — a bug report, a screenshot, free text — are a new turn of work, not a re-opened gate. Fix them, then ⛔ **go back through Step 6**: the checks, review, doc pass, regression, and live target were all measured against the pre-fix build, so re-run what the profile calls for, re-judge any criterion the fix touched (5.1), and refresh `## Verification Record` before the Buildout claims verified again.

⛔ **On a `Worktree: Yes` run, do 7.6 FIRST.** `VERIFIED` clears the statusline and releases the stop guard, so writing it before the merge lands means a failed sync or a post-merge regression leaves the Buildout claiming success with nothing holding the session open to fix it. Integration is part of being done, not a step after it.

Then:

1. Set `Status: VERIFIED`.
2. `~/.pilot/bin/pilot register-plan "<buildout_path>" "VERIFIED" $LANE_FLAG 2>/dev/null || true`

That clears the statusline and releases the stop guard.

### 7.6 Merge back — `Worktree: Yes` only (runs BEFORE 7.5's status write)

The run owns the checkout it created, so it owns putting the work back. Skip this entirely when the header says `Worktree: No`.

1. **If `docs/builds/` is gitignored, copy the Buildout to the project root first** — otherwise the squash lands the work with no record of the run that produced it.
2. **Squash-merge it. Do not ask.** `--worktree=yes` was a request for an isolated checkout *that is squash-merged back at the end* — the merge is the second half of the flag, not a separate decision, and it is the one git write this run is authorised to make. Show what landed (`~/.pilot/bin/pilot worktree diff --json <slug> $LANE_FLAG`) in the report, not as a question.
3. One Bash call, chained, so a failed sync can never be followed by a cleanup that deletes the work:

```bash
~/.pilot/bin/pilot worktree sync --json <slug> $LANE_FLAG && \
  PROJECT_ROOT=$(~/.pilot/bin/pilot worktree cleanup --force --json <slug> $LANE_FLAG | jq -r '.project_root') && \
  cd "$PROJECT_ROOT"
```

⛔ Never split sync, cleanup, and `cd` across Bash calls — a compaction between them loses the thread mid-merge.

**Exit codes.** `0` clean · `1` nothing landed · **`2` the squash landed but the base checkout's own uncommitted work could not be restored** and is in `git stash list`. The chain stops on 2 by itself, leaving the worktree in place deliberately. Do NOT re-run cleanup: surface the JSON's `stash_warning` and the `git stash pop` recovery first. `success: true` is still correct — the merge landed; only the unrelated local work is stranded.

**Lane contention.** Sync serializes on a repo-wide lock. A failure naming lane contention means a sibling held it past the timeout and **nothing was changed** — retry once it finishes.

4. **After a successful merge, re-run Step 6's checks on the merged base branch.** The base may have moved since the worktree forked, and criteria that passed in isolation can fail on integration. A criterion that breaks here goes back to `- [ ]` and the run is not verified.

⛔ **Any failure in this step leaves the Buildout `PENDING` — never `VERIFIED`.** A sync that could not land, a `cleanup` refused for unmerged commits, a criterion that regressed on the merged base: in each case keep `Status: PENDING`, re-register it, say what failed and what it needs, and do NOT continue to 7.5. Registering `VERIFIED` releases the stop guard, so doing it on a failed integration ends the session with the work unmerged and the file claiming otherwise.

**Only once the merge has landed and the merged-base checks are green** do you continue to 7.5 and write `Status: VERIFIED`.

---

## Exporting the run

When the user wants this run in a fresh session, by a different agent, or on a machine without Pilot, hand back a portable brief instead of running it.

Without Pilot there is no Buildout file and no stop guard, so the goal condition has to move into the prompt.

<!-- CC-ONLY -->
**Paste first** (native Claude Code command — installs a session-scoped Stop hook, so the session cannot end while the condition reads false; `/goal clear` releases it early):

```
/goal Every acceptance criterion below passes a judge reading the finished artifact.
```

**Then paste:**
<!-- /CC-ONLY -->
<!-- CODEX-START
**Paste this brief.** Its first line is the goal condition — without Pilot's stop guard, that line is the only thing holding the run open:
CODEX-END -->

```
Build GOAL.

Work in rounds. A round is: do every open task, then judge.

Tasks to start from — add, split, or drop them as the work teaches you something:
1. ...
2. ...

Acceptance criteria, judged only at the end of a round, pass or fail, no scores:
1. ...
2. ...

Judge from the finished artifact, not from your reasoning about it or your memory of
what was hard. Rule each criterion with one line of evidence. Pass a criterion whose
evidence meets what it asks; do not raise the bar mid-judge. Any criterion that fails
becomes a task in the next round.

Do not judge until every task is done. Do not stop while a criterion is unjudged. Do not
ask me to approve anything, and do not check in between rounds — a failing criterion is
next round's tasks, not a question. After four rounds, stop and tell me what will not
close instead of starting a fifth.
```

Add the reference and its re-obtain command only if the run has one. The criteria block is the long part and earns it; keep the rest short. Leave out architecture, file layout, and stack unless the user demanded them — every extra instruction is one fewer decision the agent makes with the work actually in front of it.

## Common issues

**The session will not stop.** Pilot's stop guard is holding it because the Buildout is registered and not `VERIFIED`. That is the loop working — an autonomous run is *supposed* to be held to its criteria rather than allowed to trail off. If a criterion genuinely will not close, spend the rounds, then record it unresolved at the ceiling (5.3) or prove it unachievable (5.5). Never lower it, and never invent a question to escape the guard. The user's escape hatch is stopping twice within 60 seconds.

**The Buildout is not showing in the statusline or Console.** It must live under the project root's `docs/builds/` (`docs/plans/` still works for Buildouts written before the split) and be registered — `pilot register-plan` prints a warning when the path is outside the scanned directories. Check `Type: Build` is present and that `## Progress Tracking` uses top-level `- [ ] Task N:` lines. An owned worktree's Buildout is supported when its slug and lane registration match that checkout. Verify the detected worktree and registered absolute path; do not move another session's Buildout to make it appear.

**The judge keeps passing weak work.** The criteria are decidable by feel. Rewrite them to name the evidence that settles them (Step 2.2), then judge again from the round you are on.

**The run is on round 5.** There is no round 5. Four judge passes is the ceiling (5.3) — stop now, record what would not close, and report. The criteria were written against something this run cannot reach, which is a result worth having, not a failure to hide.

## Examples

### A visual goal

User: "landing page for my running brand, athletic, green and dark, has to feel alive."

Reference offered and picked: Nike's current running campaign page (a genuine A/B — both are landing pages, both screenshottable at 1440px).

Tasks (drafted): hero and motion · type scale and colour system · product section · responsive pass at 390px · accessibility pass.

Criteria (abridged): unlabelled hero A/B at 1440px and 390px, a viewer picks ours; motion still reads with `prefers-reduced-motion` set; LCP under 2.0s on a throttled 4G profile; every interactive element reachable by keyboard.

Round 1 built all five tasks and judged 2/4. Round 2 closed the motion and LCP criteria (splitting the responsive task once the hero turned out to need its own breakpoint) and judged 4/4. Two rounds, handed back.

### A writing goal

User: "a 2000-word explainer on vector databases for non-engineers."

Reference offered and picked: a named Julia Evans post.

Tasks: the opening · the core mechanism · the analogy set · the worked example · the ending.

Criteria (abridged): a reader new to the topic restates the core mechanism in one sentence after a single read; no undefined jargon; every analogy survives being pushed one step further; unlabelled A/B against three of her actual posts on which one a non-engineer finishes.

Mode: sequential. One artifact; the writer judges its own prose in a separate pass, from the page alone, with the Evans posts re-opened each round.

### A goal with no reference

User: "close the three measurement gaps in our eval — grade the cascade on speech, add an accent axis, make multi-turn a real measurement."

No reference: the nearest published benchmark is a paper, not something our report can sit beside and be picked over. Named none, said so in one line, and let the criteria carry the standard.

Criteria were written to be settleable **from data this run would actually produce** — the run's own results file, not a collection job scheduled to finish hours later. The gap that needed a long external run became a task with an explicit blocked hand-back (Step 4.4) rather than a criterion, so the run reported honestly at the point it ran out of things it could do, instead of spending rounds waiting.
