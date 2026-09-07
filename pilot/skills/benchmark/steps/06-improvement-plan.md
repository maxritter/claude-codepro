# Step 6 — Decide What the Evidence Supports

Use Step 5's artifacts and paired outcomes to identify useful next steps. A valid benchmark can conclude that no change is needed or that an old instruction should be removed.

## Diagnose before editing

- **Signal:** identify the behavior improved, the cases supporting it, and any added time or complexity. Preserve useful guidance; do not infer universal benefit.
- **Baseline:** both models/configurations already succeeded. Keep valid controls. Consider simplifying or removing redundant guidance and testing the candidate on unchanged cases; do not harden assertions merely to force a positive delta.
- **Unreachable:** inspect failures, fixtures, actual tool access, and grader evidence. Both failing can mean a hard task, bad setup, or invalid assertion; it does not automatically call for stronger instructions.
- **Regression:** locate the misleading guidance or changed execution condition. Reproduce the important failure before expanding the change.
- **Incomplete or noisy:** recover missing artifacts or add proportionate repetitions only when that could resolve the decision.

An eval correction requires a task-grounded reason independent of the desired winner. Preserve the old result and identify the new eval version; comparisons across changed assertions do not isolate the target's effect.

## Propose or apply

For each justified edit, name the target path or assertion id, the evidence, the proposed replacement/removal, and the behavior it should improve.

If the user authorized improvement and reruns, apply supported changes and continue without another routine approval question. If they requested measurement only, deliver findings and concrete recommendations. Ask only when the next action introduces unapproved scope, cost, or side effects.

Do not generate a proposal for every passing baseline assertion or require changes merely because a benchmark finished.

## Re-run and finish

Keep the eval set, model, tools, and fixtures constant when measuring a target revision. Save outputs in a fresh run directory. Re-run affected cases during iteration, then the relevant full comparison before making a broad claim.

Report the outcome with evidence and limitations. Save the comparison artifacts for review; commit, push, publish, or release only with corresponding authorization.
