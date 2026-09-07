## Step 5: Judge the Criteria

**One judge pass per round, after every task is ticked.** This is the whole quality mechanism; the rest of the workflow exists to make it possible.

### 5.1a Get a running artifact first

**Only when a criterion rules on runtime behaviour** — otherwise skip in one recorded line. Ruling such a criterion from source is the easiest way to pass work that does not run.

⛔ **On a `Worktree: Yes` run, every tier resolves against the worktree, not the project root.** Resolve it once — `~/.pilot/bin/pilot worktree detect --json <slug> $LANE_FLAG` (add `--lane <id>` on a lane run) — and `cd` there before Tier 1. A dev server started in the base checkout, a build run from it, or a deploy uploaded from it all serve code this round did not write, and the judge then rules a criterion pass or fail against the wrong tree. That is the single most damaging way this loop can go wrong, because the verdict looks well-evidenced. The command you record below must resolve inside the worktree too, since later rounds replay it.

First tier that yields a target wins:

| Tier | What | Move on when |
|---|---|---|
| 1 | Reuse a running server — `curl -s --max-time 3 -o /dev/null -w '%{http_code}' http://localhost:<port>/` | Nothing listening |
| 2 | Start the documented dev server in the background, poll health up to 60s | No documented start command |
| 2b | **The artifact is something you install, not something you serve** — a mobile app, a desktop app, an extension, a CLI binary. Build it and install it the way this project's own docs say (emulator, simulator, device, local install), then drive the installed copy | No documented build-and-install path |
| 3 | Use an identified remote preview or deployment only when the target and operation are already authorized; verify the project's actual command and environment first | No authorized target or a concrete deploy failure |
| 4 | No live target: rule what you honestly can, record the rest unresolved | Applicable authorized local/remote options cannot establish a target |

Record applicable attempts and the exact blocker. Credentials and backend marker files do not authorize deployment; never attempt a generic deploy solely to satisfy this checklist.

⛔ **A dev server is not automatically the artifact.** For a mobile or desktop app the running dev server serves the *source*, while what the criteria rule is the installed build — a different thing, with a different bundle, sometimes different transport. Tier 2b exists so that project does not fall through to Tier 4 and get its UI criteria ruled from source. When both apply, take 2b: judge the thing the user would actually open.

**Record the winning tier and its command in the Buildout** so later rounds and Step 6 reuse it. ⛔ That record is a cached *resolution*, not a fresh artifact: an immutable preview deploy, a no-watch dev server, or a stale bundle keeps answering 200 for old code. So every judge pass re-asserts identity first — exercise a behaviour unique to the current artifact, and rebuild/restart/redeploy if the older one answers.

**UI evidence follows `browser-automation.md` in full** — including its first rule, that the project's own driver beats the generic ladder, and its rule 3, that three failed interactions with one driver means the driver is wrong rather than the selector. Read it before the first interaction, not after the third failure. A failing tier goes to the next tier, never to a substitute: `curl`, a fetched URL, source, an API 200, and a green unit test prove other things, not what a user sees.

Record in the Buildout which driver you settled on, so a later round and Step 6 start where this one finished instead of repeating its dead ends.

### 5.1 Judge

1. **Re-obtain the reference**, if the Buildout names one, using the command recorded there. Recalling it is how the comparison drifts toward what you already made. If there is no reference, skip this — the criteria stand on their own.
2. **Look at the finished artifact** — the running one, per 5.1a. Match the evidence to what the criterion asks:

   | Criterion is about | Evidence that settles it |
   |---|---|
   | Something visual | A screenshot at the viewport the criterion names |
   | An interaction | snapshot → click the thing → re-snapshot showing the new state |
   | Prose | The passage, read |
   | Code behaviour | The command, benchmark, or test the criterion names, actually run |

   Where a reference exists, put both side by side with the labels stripped.
3. **Rule each criterion pass or fail** with one line of evidence you can point at right now.
4. **Rule the oracle criterion last, and from the oracle signal itself.** It is the one that says the user's outcome is real rather than that the work got done, so a proxy for it is not evidence: the suite passing is not the walkthrough, the endpoint returning 200 is not the flow working, the word count is not the piece landing. If the other criteria pass and this one fails, the round produced good work aimed at the wrong thing — say exactly that in the round log, because it is the most useful sentence the run will write.
5. **Judge from the artifact only.** Not from your build reasoning, not from your intentions, not from your memory of what was hard. The judge must not know how hard the builder tried.

**Calibrated, not brutal.** Pass a criterion whose evidence meets what it asks. Raising the bar mid-judge — deciding that what the criterion said is not quite enough after all — is what turns `/build` into something slower than `/spec` for no gain in quality. If a criterion was written too loosely, that is a lesson for the next run, not a licence to fail work that met it.

**There are two verdicts.** "Partial" and "mostly" are scores wearing pass/fail clothing, and they drift upward the same way. A criterion not fully met is **fail**: leave it `- [ ]` and let its gap become next round's tasks. A verdict containing "should", "probably", "close enough", "partial", or "mostly" is not a verdict — look again at the artifact and rule it.

⛔ **Insufficient evidence is a fail, not a pass.** If you cannot point at the screenshot, the command output, the passage, or the measurement *right now*, the criterion has not been settled — whatever you believe about the work. "It must be fine by now", "nothing changed since it passed", and "the fix obviously covers it" are all the absence of evidence. Go get the evidence, or leave it `- [ ]` and let next round's tasks produce it. Since no user is standing between this verdict and `VERIFIED`, this rule is the only thing preventing a run from certifying itself on faith.

⛔ **Rule every criterion, every pass.** A criterion that passed in round 1 and regresses in round 2 goes back to `- [ ]`. The file must show the truth, not the high-water mark.

### 5.2 Record the round

In one edit:

- Tick `- [x] Criterion N:` for each criterion that now passes; untick any that regressed.
- Increment `Rounds:`.
- Append one entry to `## Round Log`:

  ```markdown
  - Round 2: closed the accent axis and the interval table (added task 8, dropped task 5 — the
    loader already handled it). Judge: 4/5 pass. Failing: Criterion 3 — the comparison table
    still prints bare rates in two cells.
  ```

The file is the run's memory. After a compaction you resume from it, not from the conversation.

### 5.3 Decide what happens next

You arrive here with `Status: COMPLETE` (set at the end of Step 4). Each branch below owns the transition out of it — a judge pass that does not move the status leaves the file claiming the judge never ran.

**Every criterion passes** → go to Step 6 (verify), then Step 7 (hand back). Leave `COMPLETE` in place; Step 7 sets `VERIFIED` once Step 6's evidence is in the file.

**Some criterion fails, and `Rounds:` is 1, 2, or 3** → turn each failure into one or more tasks:

- Append them to `## Progress Tracking` as `- [ ] Task N:` and to `## Implementation Tasks` with an objective.
- Set `Status: PENDING` and register it — the next round has open tasks again, so `COMPLETE` would be a lie and the stop guard would demand a judge pass instead of the build:

  ```bash
  ~/.pilot/bin/pilot register-plan "<buildout_path>" "PENDING" $LANE_FLAG 2>/dev/null || true
  ```

- Go back to Step 4 and work them.

⛔ **A failing criterion is never a question for the user, at any round number.** It is the next round's tasks. Round three used to stop and ask; it does not any more — the fourth round is the automatic, one-time extension, and it runs without being authorised because the round ceiling below is what bounds the run.

⛔ **Round three is where the temptation peaks.** Two passes have failed the same criterion, a fourth feels like more of the same, and "check in with the user" arrives dressed as diligence. It is the run declining to finish. Change the approach instead of repeating it: if the same tasks failed twice, the third attempt at them is worth less than one attempt at a different mechanism.

**Some criterion fails, and `Rounds:` is 4** → the ceiling. Leave the failing criteria unticked and append a `## Round Log` line recording each one as unresolved with the reason it would not close, in the terms 5.4 requires. Then make the hand-back actually reachable — the run ends with the Buildout still unfinished, so it stays `PENDING`, and only the one-shot sentinel lets the session stop:

```bash
BUILD_SESS="${CLAUDE_CODE_SESSION_ID:-${CODEX_THREAD_ID:-${PILOT_SESSION_ID:-default}}}"
mkdir -p "$HOME/.pilot/sessions/$BUILD_SESS" && touch "$HOME/.pilot/sessions/$BUILD_SESS/build-handback-pending"
~/.pilot/bin/pilot register-plan "<buildout_path>" "PENDING" $LANE_FLAG 2>/dev/null || true
```

Then go to Step 6 (verify — the code is finished even though a criterion is not), then Step 7 to hand back. ⛔ Without that sentinel the stop guard blocks the stop and reinjects the loop, which defeats the ceiling entirely — the one failure this budget exists to prevent.

### 5.4 Criteria do not move, and you are the only one who could move them

There is no approval gate on this run and no round-budget question. Nobody is going to catch a criterion that quietly became easier, which makes this the one rule the whole workflow rests on.

⛔ **You may never relax, reword, narrow, or drop an acceptance criterion because it is failing.** Not at round three, not at the ceiling, not "to reflect what we learned". A criterion that will not close is reported unresolved (5.3) or proven unachievable (5.5). Both are honest outcomes. A criterion edited to match the artifact is a run marking its own homework, and the file makes it look reviewed.

**Two changes are legitimate, and both come from outside your judgement:**

| Change | Where it comes from | What you record |
|---|---|---|
| The user rewrote or removed a criterion | A Console annotation picked up at 3.0 or 4.0, or a message in the conversation | The before and after in `## Round Log`, attributed to the user, then judge against the new wording |
| A criterion turned out to be undecidable *as written* — no evidence could ever settle it either way | Discovered while judging, not while failing | The original wording, why no evidence settles it, and the sharper replacement that rules the **same** bar. If the replacement is easier to pass, it is not this — it is the banned edit above. |

`Status:` stays `COMPLETE` for either; no tasks reopen and no round is spent. Re-judge against the new wording in the same pass.

⛔ **The oracle criterion is exempt from even those two.** A user who rewrites it is redefining the outcome — that is a new run, not an edit; say so and let them start one. An oracle you find undecidable means Step 1.5 never established one, and no rewording at round three recovers that. Everything else in the workflow exists to make this one criterion true; a run that edits it is a run grading its own exam.

### 5.5 The unachievable exit — the run's only early stop

Some criteria cannot be met in this session no matter how many rounds you spend: it contradicts another criterion, it needs a capability or resource that is not available here, or every distinct approach has been tried and exhausted. Burning the remaining rounds against it produces nothing but tokens.

⛔ **Your own conviction that something is impossible is evidence, not proof.** Believing it does not make it true, and this exit is exactly where a tired run wants to leave. Before taking it, all four must hold:

1. **Two genuinely different mechanisms have been tried** — not the same approach twice with better selectors, wording, or parameters.
2. **The blocker is named concretely** — the missing capability, the contradiction, the hard limit — in terms someone else could check.
3. **It is not "not yet".** Slow progress, a hard problem, a long build, a fiddly test, or a filling context window are none of them unachievable.
4. **No other criterion is still closable.** If work remains that would move something else, the run is not out of things to do.

When all four hold, stop **that criterion**, not the run: leave it `- [ ]`, append a `## Round Log` line naming the blocker and the two approaches that failed, and keep working every criterion that is still live. Only when every remaining criterion is unachievable is the run itself over — then touch the hand-back sentinel, leave `Status: PENDING`, and go to Step 6 and Step 7 exactly as the ceiling does:

```bash
BUILD_SESS="${CLAUDE_CODE_SESSION_ID:-${CODEX_THREAD_ID:-${PILOT_SESSION_ID:-default}}}"
mkdir -p "$HOME/.pilot/sessions/$BUILD_SESS" && touch "$HOME/.pilot/sessions/$BUILD_SESS/build-handback-pending"
~/.pilot/bin/pilot register-plan "<buildout_path>" "PENDING" $LANE_FLAG 2>/dev/null || true
```

The report says what could not be done and why, in the user's terms. That is a finished run with an honest result — not a failure, and not something to dress up as a pass.

### Status at a glance

Every path out of this step names its status, so the file never claims a state the run is not in:

| Situation | `Status:` | Sentinel | Next |
|---|---|---|---|
| Arrived from Step 4 | `COMPLETE` | — | judge |
| All criteria pass | `COMPLETE` → Step 7 sets `VERIFIED` on the evidence | — | Step 6 |
| Fails, rounds 1–3 | `PENDING` (registered) | — | Step 4 |
| Fails, round 4 (ceiling) | `PENDING` (registered) | **touched** | Step 6 |
| Criterion rewritten by the user or found undecidable (5.4) | `COMPLETE` | — | re-judge |
| Every remaining criterion unachievable (5.5) | `PENDING` (registered) | **touched** | Step 6 |

**Done when:** the status above matches the branch taken, and the run is either heading to Step 6 or back to Step 4.
