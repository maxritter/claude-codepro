---
name: benchmark
description: Benchmark and evaluate rules, skills, and workflows with quantitative before/after comparisons. Use whenever the user wants to measure the impact of rules/skills/workflows, compare versions, or validate that a rule pack improves outputs.
user-invocable: true
---

# /benchmark — Benchmark & Evaluation Framework

Measure the real impact of rules and skills by running with/without comparisons, grading outputs against assertions, and presenting the findings inline.

## When to use this skill

- User wants to validate that a skill, rule, or rule pack actually improves outputs
- User says "benchmark", "evaluate", "measure", "before/after", "with vs without", "does this skill help?"
- User wants to extend a pilot eval matrix to more targets
- User wants to iterate on a skill or rule pack and needs quantitative feedback

## Supported target types

Two target types — both run in isolated `/tmp/pilot-bench-*` directories, one fresh directory per (eval, config, run):

| Target type | `with/` config | `without/` config | Use when |
|-------------|---------------|-------------------|----------|
<!-- CC-ONLY -->
| `skill` | Skill installed in `.claude/skills/<name>/` | Empty `.claude/` | Measuring "should we ship this skill?" |
| `rules` | Rule file(s) copied into `.claude/rules/` | Empty `.claude/` | Measuring "does this rule/pack improve behavior?" |
<!-- /CC-ONLY -->
<!-- CODEX-START
| `skill` | Skill installed in `.agents/skills/<name>/` | Empty root `AGENTS.md` | Measuring "should we ship this skill?" |
| `rules` | Rule file(s) composed into root `AGENTS.md` | Empty root `AGENTS.md` | Measuring "does this rule/pack improve behavior?" |
CODEX-END -->

Workflow-style skills like `/spec` are benchmarked as `type=skill` — present vs absent.

<!-- CC-ONLY -->
**Model selection:** Pilot-shipped skills (`spec-plan`, `fix`, `prd`, `create-skill`, `setup-rules`, …) don't carry a `model:` in their frontmatter — active model is controlled by Claude Code's `/model`. The runner defaults those benchmarks to `claude-sonnet-5`; pass `--model opus` (or `--model fable`) explicitly to run them on Opus or Fable instead.
<!-- /CC-ONLY -->
<!-- CODEX-START
**Model selection:** Pass the intended Codex model explicitly with `--model <model-id>`, including when benchmarking the current session's model. The runner isolates user configuration with `--ignore-user-config`, so omitting the flag selects Codex's built-in default, not necessarily this session's model or profile. Use that fallback only deliberately, and retain its `codex-default` label rather than attributing the run to an unverified model.
CODEX-END -->

## Isolation guarantees

- **Per-run filesystem sandbox.** Each (eval, config, run) triple gets its own `/tmp/pilot-bench-*/` cwd. Use relative paths in prompts, or the `{sandbox}` placeholder when you need an absolute path. Hardcoded `/tmp/<fixed-name>/` in prompts is flagged at load time.
<!-- CC-ONLY -->
- **Global-rule auto-hiding.** `~/.claude/rules/<basename>.md` and `~/.claude/skills/<name>/` are moved aside for the duration of the run when they duplicate the target, then restored automatically. Layered fail-safes (on-disk recovery manifest + atexit + SIGINT/SIGTERM/SIGHUP handlers + next-run sweep) make the restore robust against kill -9, power loss, and segfaults. Opt out with `--no-isolate-global` for realistic "day-to-day" measurement.
<!-- /CC-ONLY -->
<!-- CODEX-START
- **Global-skill auto-hiding.** `~/.agents/skills/<name>/` is moved aside for the duration of Codex skill benchmarks when it duplicates the target, then restored automatically. Codex rules benchmarks use an isolated root `AGENTS.md`; pass `--no-isolate-global` only when you intentionally want globally-installed skills present too.
CODEX-END -->

## Workflow

Follow these steps sequentially:

1. **Intake** (`steps/01-intake.md`) — Detect what the user wants to benchmark. If an existing `benchmarks/<target>/evals.json` exists, skip to execute.
2. **Target discovery** (`steps/02-target-discovery.md`) — Help the user pick a target and determine its type.
3. **Author evals** (`steps/03-author-evals.md`) — Draft realistic, outcome-based assertions and validate the concrete run scope against existing authorization.
4. **Execute** (`steps/04-execute.md`) — Run the runner, watch for failures, summarize results inline.
5. **Present findings** (`steps/05-review-iterate.md`) — Parse benchmark.json + per-run grading.json, render a per-eval matrix with evidence quotes in chat.
6. **Improvement plan** (`steps/06-improvement-plan.md`) — Interpret Signal / Baseline / Unreachable / Regression from evidence, propose or apply supported changes within the user's scope, and rerun when justified.

## Quick reference

**Config path:** `benchmarks/<target-name>/evals.json`
**Outputs:** `benchmarks/<target-name>/runs/<timestamp>/`
<!-- CC-ONLY -->
**Runner:** `PYTHONPATH="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/skills/benchmark" uv run python -m scripts.runner --config <evals.json> --skip-permissions`
<!-- /CC-ONLY -->
<!-- CODEX-START
**Runner:** `PYTHONPATH=~/.agents/skills/benchmark uv run python -m scripts.runner --config <evals.json> --skip-permissions --agent codex --grader-timeout 600`
CODEX-END -->

**Defaults worth knowing:**
- `--runs 1` (keeps token cost low; bump only for variance analysis)
- `--evals <id-or-name,...>` runs only selected evals while iterating; the final release gate still runs the full config
- `--workers 4` (bump to `min(total_runs, 8)` for small eval sets so all runs land in one wave)
- `--model` is read from the target skill's frontmatter for Claude (alias → ID); rules and model-less Claude skills fall back to `claude-sonnet-5`; Codex defaults to the active Codex model unless `--model` is passed
- `--grader-model` defaults to the same model as `--model` so executor and grader stay matched
<!-- CODEX-START
- Codex child runs execute inside fresh non-git temp directories; the runner passes `--skip-git-repo-check` to every `codex exec` child automatically.
- Codex grading can run longer than Claude-style stream grading because the grader reopens transcript and output files. Use `--grader-timeout 600` for file-writing evals or after any `grader-failed` timeout so you do not burn a full rerun on a missing `grading.json`.
CODEX-END -->
