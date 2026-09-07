## Step 6: Test & Iterate

Scale validation to what changed. New scripts must run; metadata and reference changes need structural checks; complex workflows and substantial behavioral changes benefit from isolated execution tests.

### 6.1 Choose realistic cases

Use representative requests and minimal fixtures, including a near-miss when invocation scope changed and an authorization boundary when the workflow can mutate external state. Reuse existing cases where they exercise the behavior. Choose missing details from the user's request or workspace; do not require a review of the test plan before running safe local checks.

### 6.2 Execute in isolation

For project skills, validate the configured synchronization contract first. Test Claude Code from its generated skill artifact and Codex from its canonical/generated Codex artifact as applicable.

When an independent execution would add confidence and delegation is available and authorized, give the evaluator the realistic task, the skill, and the minimum raw fixtures. Do not provide the expected answer or the proposed fix. Assign exclusive output directories and preserve the surrounding workspace.

For a meaningful with-skill/baseline comparison:

- Hold model, tools, prompt, and initial fixture state constant.
- Use fresh isolated contexts. A baseline must not inherit the tested guidance through parent history, installed global skills, or repository rules.
- Keep side effects inside the fixtures. A live deployment, message, or account mutation needs its own existing authorization.
- Start with the minimum useful case set; add repetitions when observed variance could change the conclusion.
- Use native agent tools or an installed CLI whose flags you have checked. Tool absence is a reported validation gap, not permission to invent an invocation.

### 6.3 Evaluate outcomes

Inspect generated artifacts and execution traces. Did the skill preserve the full task, honor boundaries, use real tool contracts, and produce the required result? Prefer deterministic assertions for facts; use a concrete rubric for judgment-heavy output.

A model answering "yes, I would use this skill" is not evidence that actual discovery selected it. Test selection in the target runtime when trigger behavior matters.

Record which supported agents and model configurations were actually tested. Do not claim cross-model quality from a single model's result or from matching generated text alone.

### 6.4 Iterate on demonstrated gaps

Correct the smallest general cause of an observed failure, then rerun the affected cases. Broaden verification when a change affects shared behavior, results conflict, or an unresolved concern remains. Stop when the intended behavior is supported and no material gap remains; do not repeat all cases solely because another iteration began.

Present the result and material limitations. Ask for user judgment when it is the missing acceptance signal for a subjective deliverable, not as a routine gate for every skill edit.
