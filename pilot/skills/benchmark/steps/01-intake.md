# Step 1 — Intake

Figure out what the user wants to benchmark and whether they have eval config already.

## Ask the user

1. **What are you benchmarking?** If they named a target (skill name, rule file), proceed. If they were vague ("benchmark my setup", "see if my rules help"), ask them to name one specific artifact.
2. **Does `benchmarks/<target-name>/evals.json` already exist in this project?**
   - Yes → skip to Step 4 (Execute).
   - No → go to Step 2 (Target discovery) to determine type and path.

## Default conventions

- Target name defaults to the directory basename (e.g., `testing` for `pilot/rules/testing.md`, `create-skill` for `pilot/skills/create-skill/`).
- Config path: `benchmarks/<target-name>/evals.json` relative to the project root.
- Results path: `benchmarks/<target-name>/runs/<ISO-timestamp>/`.

## When evals already exist

Read the existing `benchmarks/<target>/evals.json` and summarize it back to the user:

- Target type and path
- Number of evals and their prompts (one-liner each)
- Whether there are prior runs committed under `runs/`

If the user requested a rerun of this target, proceed with that config. Ask only if its scope, cost, or side effects differ materially from the request.

## When target is ambiguous

For a request covering several targets, inventory all of them and preserve that scope. Run per-target comparisons in useful batches; do not redefine "all" as one target. Calibrate a representative eval first when it helps avoid wasting the later runs, then continue through the requested set.



## Exits

- Have target + evals → Step 4
- Have target, no evals → Step 2
- No target → ask again before spending compute
