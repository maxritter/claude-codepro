# Step 5 — Present Findings

Read the completed run artifacts and report what the comparison actually supports. Benchmarking alone does not authorize target edits or publishing a release.

## Artifacts

Use `benchmark.json`, every selected eval's `eval_metadata.json`, and all per-run `grading.json` or `failed.json` files. Inspect the underlying transcript/output when a verdict or quote is consequential or surprising.

The aggregate pass-rate delta describes this sample. It is not by itself a release gate, a causal proof, or a statistically significant effect. Report run counts, failures, model/configuration identity, time, and tokens beside the quality delta.

## Paired outcomes

Classify matched assertions from comparable runs:

| With | Without | Label | Interpretation |
|---|---|---|---|
| Pass | Fail | Signal | Guidance helped on this observed case |
| Pass | Pass | Baseline | Both succeeded; the guidance may be unnecessary here |
| Fail | Fail | Unreachable | Both failed in this sample; inspect task, environment, and grading before blaming the rule |
| Fail | Pass | Regression | Guidance may have hurt; inspect the evidence and variance |

These labels describe observations. "Unreachable" does not prove impossibility, and "Baseline" does not make a valid assertion defective.

For multiple repetitions, include every completed comparable pair or report per-assertion rates and counts. Never classify the whole experiment from `run-1` alone. Do not silently drop failed runs or pair different initial states. Show missing/failed data separately from pass-rate denominators.

## Report

Lead with the observed result and its practical limit:

- With/without pass counts and rates, delta, runs completed/failed.
- Model, effort, relevant tool/config identity, and whether the baseline was actually isolated.
- Time and token differences.
- Material regressions and divergent cases with concise evidence.
- Important unresolved failures or gaps in the eval.

Keep successful controls visible in the totals; expand individual rows only when they explain the conclusion. Do not say "ready to ship" solely because a small hand-authored sample has a large delta. If variance or incomplete data could change the decision, say so and identify the next discriminating check.

Proceed to Step 6 for evidence-based next steps within the user's requested scope.
