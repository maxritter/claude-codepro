# Step 4 — Execute

<!-- CC-ONLY -->
Run the runner **in the background** so the user gets live status updates while it runs. Foreground bash blocks for the full duration (often 5-30 minutes) and shows nothing until the end — that's a bad UX, don't do it.
<!-- /CC-ONLY -->
<!-- CODEX-START
Run the runner with the Codex shell execution tool. If it yields a long-running session, keep the session id and poll it for status; otherwise read the command output directly when it completes.
CODEX-END -->

## Launch

<!-- CC-ONLY -->
Use the `Bash` tool with `run_in_background=true`. Capture the returned task ID; you will need it to read output and check completion.

```
Bash(
  command="PYTHONPATH=${CLAUDE_CONFIG_DIR:-$HOME/.claude}/skills/benchmark uv run python -m scripts.runner \
    --config benchmarks/<target-name>/evals.json",
  description="Run benchmark in background",
  run_in_background=true,
)
```
<!-- /CC-ONLY -->
<!-- CODEX-START
```bash
PYTHONPATH=~/.agents/skills/benchmark uv run python -m scripts.runner \
  --config benchmarks/<target-name>/evals.json \
  --agent codex --model <model-id> --grader-timeout 600
```
CODEX-END -->

<!-- CC-ONLY -->
That's it for arguments — defaults handle the rest. The runner reads the target skill's `model:` frontmatter and uses that for both executor and grader. Rules targets and skills without a `model:` field fall back to `claude-sonnet-5`.
<!-- /CC-ONLY -->
<!-- CODEX-START
With `--agent codex`, the runner installs skills in `.agents/skills/<name>/` and composes rules into root `AGENTS.md`. Set `<model-id>` to the actual model being evaluated. User configuration is isolated, so omitting it does not preserve the active session's model or selected profile. Use the same explicit model and effort for the paired runs and report those settings.
CODEX-END -->

<!-- CODEX-START
Codex runs happen in freshly-created temp directories, which are intentionally not git repositories. The runner adds `--skip-git-repo-check` to each child `codex exec` automatically; if you see `Not inside a trusted directory and --skip-git-repo-check was not specified`, update or fix the runner before rerunning the benchmark.
CODEX-END -->

**Why `uv run`:** every Python invocation in this project uses `uv run` — no system `python` or `python3`. It ensures the right interpreter and dependency set.

<!-- CC-ONLY -->
**`--skip-permissions` is a permission choice.** It passes `--dangerously-skip-permissions` to executor and grader subprocesses. Use it only when authorized and when prompts, fixtures, and output paths are trusted and isolated; a temporary working directory alone does not confine side effects.
<!-- /CC-ONLY -->
<!-- CODEX-START
**`--skip-permissions` is a permission choice, not a requirement of non-interactive execution.** It gives child runs full access. Use it only when authorized and when prompts, fixtures, and output paths are trusted and isolated; otherwise use the runner's restricted path and report any permission blocker. A temporary working directory alone is not a security sandbox.
CODEX-END -->

<!-- CODEX-START
**Why `--grader-timeout 600`:** Codex graders reopen transcripts and generated files from disk, and artifact-heavy evals can exceed the 300s default even when executor runs succeed. Prefer starting Codex comparisons with 600s so a single slow grader does not force a full rerun just to produce `grading.json`.
CODEX-END -->

## Surface the plan header to the user immediately

<!-- CC-ONLY -->
As soon as the runner starts, it prints a plan header (config path, target, output dir, evals × configs × runs, models). Read it with `BashOutput` and relay it verbatim to the user so they see the scope and ETA up front:

```
BashOutput(bash_id="<task_id>")
```

Then send a brief intro to the user, e.g.:
<!-- /CC-ONLY -->
<!-- CODEX-START
As soon as the runner starts, it prints a plan header (config path, target, output dir, evals × configs × runs, models). Relay it verbatim to the user so they see the scope and ETA up front.

Then send a brief intro to the user, e.g.:
CODEX-END -->

> Benchmark started. **Plan:** 6 evals × 2 configs × 1 run = 12 runs, executor=<model>. Estimated ~30-45 min. I'll surface progress as runs complete and the final summary when it finishes.

## Status updates while it runs

The runner emits these stdout patterns to watch for:

| Pattern | When | What to do |
|---------|------|-----------|
| `[N/M] ✓ eval-X config run-N  78.3s, 12.4k tok  · ... ETA Xm` | Per completed run | Once you've seen >2 of these, you have an ETA — relay the latest ETA to the user when they ask or every ~5 min. |
| `· [snapshot Xs elapsed] N done · M in-flight · K queued · F failed` | Every 30s while in-flight | Use these as quick "still alive" pings. |
| `✗ eval-X config run-N  failed: <reason>` | On run failure | Surface immediately to the user — failures often mean config issues (timeout, missing agent CLI, grader-no-output). |

<!-- CC-ONLY -->
**You will be notified automatically when the background task completes** — do NOT sleep, poll, or proactively check on its progress. Continue with other work or respond to the user's questions in the meantime. When the user asks "how's it going?", call `BashOutput(bash_id=...)` to fetch the latest lines and summarize them.
<!-- /CC-ONLY -->
<!-- CODEX-START
If the shell tool returns a running session id, poll that session for the latest lines when the user asks "how's it going?" or when the session completes.
CODEX-END -->

## When the runner completes

The runner's tail of output includes a summary block:

```
────────────────────────────────────────────────────────────────────────
Benchmark complete in 33m14s  (12 ok, 0 failed, 0 skipped)
────────────────────────────────────────────────────────────────────────
  With Skill                   ok 6/6  avg 110.5s, 568k tok total
  Without Skill                ok 6/6  avg 78.2s, 138k tok total
────────────────────────────────────────────────────────────────────────
Wrote benchmarks/<target>/runs/<ts>/benchmark.json
```

Read the final output and:
1. Quote the summary block to the user
2. Compute and surface the headline `delta.pass_rate` from `benchmark.json` (signed string like `+0.50`)
3. Note any per-eval outliers if `stddev > 0.3`

## Flags (override the defaults when you have a reason)

| Flag | Default | When to override |
|------|---------|------------------|
| `--runs N` | `1` | `2-3` only when measuring variance — N runs are now parallelized across workers, so wall time grows sub-linearly. |
| `--model <id>` | Claude: skill frontmatter → `claude-sonnet-5`; Codex: active Codex default | Cross-model comparison. Claude accepts `opus`/`sonnet`/`fable`/`haiku` aliases or explicit `claude-...` IDs. Codex passes the value directly to `codex exec --model`; omit it to use the active Codex model. |
| `--grader-model <id>` | same as `--model` | Run the grader at a different tier (rare — pairing them avoids "smart writer judged by dumb grader" artifacts). |
| `--configs with,without` | both | Smoke test one side. |
| `--evals <id-or-name,...>` | all | Re-run only the evals affected by a wording or assertion change; selectors preserve config-file order and fail on unknown values. |
| `--workers N` | `4` | Drop to `2` when running opus to be kinder to rate limits. For small eval sets bump to `min(total_runs, 8)` so every run lands in the first wave (3 evals × 2 configs × 1 run = 6 → `--workers 6` cuts wall time roughly in half). The runner submits one pool task per (eval, config, run_idx) so workers stay saturated. |
<!-- CC-ONLY -->
| `--no-isolate-global` | off | Disable auto-hiding of globally-installed counterparts during the run. Claude hides matching `~/.claude/rules/<basename>.md` and `~/.claude/skills/<name>/`. Use only when you want to measure the target **in addition to** global guidance. |
<!-- /CC-ONLY -->
<!-- CODEX-START
| `--no-isolate-global` | off | Disable auto-hiding of globally-installed counterparts during the run. Codex hides matching `~/.agents/skills/<name>/`. Use only when you want to measure the target **in addition to** global guidance. |
CODEX-END -->
| `--restore-hidden` | off | Exit after recovering any `.pilot-bench-hidden-*` files left by a crashed prior run (normally swept automatically on every startup). |
| `--timeout <sec>` | `600` | Bump for slow models or large prompts. |
| `--grader-timeout <sec>` | `300` | Bump if `grader-no-output` failures appear. |
<!-- CODEX-START
| `--grader-timeout 600` | override | Recommended for Codex file-writing evals; it prevents a successful executor run from becoming an unusable partial result because the grader timed out while reading artifacts. |
CODEX-END -->
| `--output <dir>` | `benchmarks/<target>/runs/<ts>/` | Override when you want a specific output path. |

## Failure handling

When you see `failed.json` referenced (or a `✗ failed:` line):

- `reason: timeout` — bump `--timeout` or reduce `--runs`.
- `reason: no-result-event` — stream-json stream was malformed. Inspect `outputs/transcript.jsonl` for the raw stream.
<!-- CC-ONLY -->
- `reason: claude-cli-not-found` — the `claude` CLI isn't on PATH. Install Claude Code first.
<!-- /CC-ONLY -->
<!-- CODEX-START
- `reason: codex-cli-not-found` — the `codex` CLI isn't on PATH. Install Codex CLI first.
- `reason: codex-exec-failed` with `Not inside a trusted directory and --skip-git-repo-check was not specified` — the runner is missing the Codex temp-directory trust flag. Add `--skip-git-repo-check` to executor and grader `codex exec` commands, then rerun.
- `reason: grader-failed` with `timed out after 300 seconds` — rerun with `--grader-timeout 600`; the executor output is usually usable, but the missing `grading.json` makes the aggregate incomplete.
CODEX-END -->
- `reason: grader-no-output` / `grader-invalid-json` — the grader subagent failed. Retry or bump `--grader-model` a tier.

A few failed runs do not abort the rest of the benchmark — each writes its own `failed.json` and the runner continues. Surface failures to the user but only stop everything if more than half are failing.

## Commit the snapshot

Preserve `benchmarks/<target>/runs/<timestamp>/benchmark.json` as a reviewable snapshot for future comparisons. Commit it only when the user authorized a commit.

## Exit

Go to Step 5 (present findings & iterate).
