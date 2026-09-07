# Step 3 — Author evals

Draft 3 realistic prompts with **falsifiable**, **discriminating** assertions. This is the highest-leverage step — bad assertions produce noise, not signal.

## Structure of evals.json

```json
{
  "target": {
    "type": "skill",
    "path": "pilot/skills/create-skill",
    "name": "create-skill"
  },
  "evals": [
    {
      "id": 1,
      "name": "short-descriptive-name",
      "prompt": "Realistic user task — phrased the way a real engineer would type it. Save outputs to {sandbox}/<filename>.",
      "expected_output": "1-line description of what success looks like",
      "expectations": [
        "Specific, observable assertion 1",
        "Specific, observable assertion 2",
        "Specific, observable assertion 3"
      ]
    }
  ]
}
```

## Path isolation — required

Each run gets its own filesystem sandbox. Prompts must reference that sandbox, not a shared absolute path, or the `with` and `without` runs will read each other's outputs.

Two safe ways to specify where outputs go:

| Approach | Example | When to use |
|----------|---------|-------------|
| **Relative paths** (preferred) | `Save the result to slugify.py` | The subprocess cwd is already the per-run sandbox, so bare filenames land in the right place. Simpler, fewer tokens. |
| **`{sandbox}` placeholder** | `Save to {sandbox}/slugify.py` | Use when the prompt genuinely needs an absolute path — the runner substitutes `{sandbox}` with the per-run directory before executing. |

**Never write `/tmp/<fixed-name>/file.py` in a prompt.** The runner emits a warning and proceeds, but the benchmark is invalid — both configs write to the same path.

## What makes an assertion good

**Outcome-relevant.** Assertions must represent behavior users need, whether the baseline passes or fails. Include cases where the guidance plausibly helps and controls where it should not regress. A baseline that already succeeds is useful evidence that an instruction may add no value.

**Observable.** The grader reads the transcript and output files. Assertions like "the output is high quality" are unverifiable. Assertions like "the plan file contains sections named `## Summary`, `## Scope`, and `## Risks and Mitigations`" are observable.

**Genuine signal, not surface compliance.** "The output file is named `plan.md`" can pass by coincidence. Prefer "the plan.md contains a ### Task N heading for at least 3 tasks" — would pass only if the skill actually did structured task breakdown.

**Test the intended outcome, not added ceremony.** Exact names, headings, or tool use belong in assertions only when a real parser, runtime, or user contract requires them. Do not reward more tests, more steps, or stricter formatting solely because the rule asks for them.

## Validate the eval before expanding the run

Try a representative case and inspect whether its assertions can distinguish a correct artifact from a plausible wrong one. Use the same assertions and initial state for both configurations.

If the baseline passes every assertion, retain that result. Inspect for an invalid or trivial assertion, but do not rewrite a valid assertion merely to make baseline fail. Expand with realistic cases only when they cover an important missing behavior. Freeze the evaluation set before comparing revisions; changing both target and assertions prevents attribution.



## Examples by type

**Skill target** (e.g., `/create-skill`):
- "Response includes a complete SKILL.md with `---` frontmatter containing `name:` and `description:` fields"
- "Response references the existing skill-creation pattern from `pilot/skills/create-skill/orchestrator.md`"
- "Response suggests at least one test prompt for the new skill"

**Rules target** (examples of behavioral requirements):
- "The user-provided record survives a failed update unchanged."
- "The regression test fails for the original bug and passes after the repair."
- "The report distinguishes source inspection from an actually executed runtime check."



## Save the config

Save to `benchmarks/<target-name>/evals.json`. State the concrete run scope and expected resource use. Proceed when that execution is already authorized; ask only for a material expansion of cost, live side effects, or required permissions. Do not commit without separate authorization.

## Exit

Go to Step 4 (execute).
