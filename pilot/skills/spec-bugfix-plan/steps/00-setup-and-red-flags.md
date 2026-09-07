## Step 0: Setup & Red Flags

### 0.1 Read Toggle Configuration

**Run first, before any other step.** Read all toggle env vars in a single Bash call:

<!-- CC-ONLY -->
```bash
MODE=$(python3 -c "import sys,os;sys.path.insert(0,os.path.expanduser('~/.pilot/hooks'));from _lib.util import read_model_switch_mode;print(read_model_switch_mode())" 2>/dev/null || echo "manual")
echo "QUESTIONS=$PILOT_PLAN_QUESTIONS_ENABLED APPROVAL=$PILOT_PLAN_APPROVAL_ENABLED MODE=$MODE"
```

Reference these values throughout: Steps 2.1/2.5 (questions) and 6 (approval + handoff). `MODE` is read fresh from config.json because session environment values can be stale. The helper preserves explicit mode choices, maps legacy `modelSwitch` true to Automated and false to Off, and defaults missing or invalid configuration to Manual. Bugfix planning does not launch the Codex companion reviewer; the verification phase owns implementation review.
<!-- /CC-ONLY -->
<!-- CODEX-START
```bash
echo "QUESTIONS=$PILOT_PLAN_QUESTIONS_ENABLED APPROVAL=$PILOT_PLAN_APPROVAL_ENABLED"
```

Reference these values throughout: Steps 2.1/2.5 (questions) and 6 (approval). Pilot's Claude model-switching tools do not apply to Codex; respect the current native mode. Bugfix planning does not run Codex adversarial review — it only runs once per `/spec` invocation, on the implementation in `spec-verify`.
CODEX-END -->

<!-- CC-ONLY -->
### 0.1a Automated native planning

If `MODE` is `"automated"`, first complete Step 1's branch/worktree setup, unapproved plan header, and registration while writes are permitted. Then read `$HOME/.pilot/agents/spec-native-plan.md` and follow its native planning handoff before exploration. The remaining planning steps write only the runtime's permitted native draft until native approval completes.

In Manual or Off mode, keep the active model and do not enter plan mode for switching. In a runtime without the required native tools, or in an orchestration lane that shares its parent's mode, continue on the current model with the normal structured approval gate. Local workflow instructions never override native mode restrictions.
<!-- /CC-ONLY -->

### 0.2 Evidence before a fix plan

Before proposing the repair, identify the source-level cause, explain how it produces the reported symptom, and name the observation that supports the claim. Use a concrete `file:line` or configuration boundary; distinguish confirmed cause from a hypothesis.

If the cause remains uncertain, gather a discriminating observation rather than inventing confidence. When repeated attempts add no evidence, revisit the reproduction, environment, and causal model. Ask only for a missing signal that cannot be obtained independently. Attempt counts and imagined rationalizations do not prove an architectural problem.

Plan the reproducing regression signal before the production repair. The plan must preserve the requested behavior and identify how the original failure and the corrected result will be verified.
