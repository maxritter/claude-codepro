## Step 0: Setup & Question Policy

### 0.1 Read Toggle Configuration

**Run first, before any other step.** Read all toggle env vars in a single Bash call:

<!-- CC-ONLY -->
```bash
MODE=$(python3 -c "import sys,os;sys.path.insert(0,os.path.expanduser('~/.pilot/hooks'));from _lib.util import read_model_switch_mode;print(read_model_switch_mode())" 2>/dev/null || echo "manual")
echo "QUESTIONS=$PILOT_PLAN_QUESTIONS_ENABLED REVIEWER=$PILOT_SPEC_REVIEW_ENABLED CODEX_SPEC=$PILOT_CODEX_SPEC_REVIEW_ENABLED APPROVAL=$PILOT_PLAN_APPROVAL_ENABLED MODE=$MODE"
```

Reference these values throughout: Steps 4/6 (questions), 10 (reviewers controlled by Console Settings), and 12 (approval + handoff). `MODE` is read fresh from config.json because session environment values can be stale. The helper preserves explicit mode choices, maps legacy `modelSwitch` true to Automated and false to Off, and defaults missing or invalid configuration to Manual.

### 0.1a Automated native planning

If `MODE` is `"automated"`, first complete Step 2's branch/worktree setup, unapproved plan header, and registration while writes are permitted. Then read `$HOME/.pilot/agents/spec-native-plan.md` and follow its native planning handoff before exploration. The remaining planning steps write only the runtime's permitted native draft until native approval completes.

In Manual or Off mode, keep the active model and do not enter plan mode for switching. In a runtime without the required native tools, or in an orchestration lane that shares its parent's mode, continue on the current model with the normal structured approval gate. Local workflow instructions never override native mode restrictions.
<!-- /CC-ONLY -->
<!-- CODEX-START
```bash
echo "QUESTIONS=$PILOT_PLAN_QUESTIONS_ENABLED REVIEWER=$PILOT_SPEC_REVIEW_ENABLED APPROVAL=$PILOT_PLAN_APPROVAL_ENABLED"
```

Reference these values throughout: Steps 4/6 (questions), 10 (native Codex `spec-review` subagent), and 12 (approval). Pilot's Claude model-switching tools do not apply to Codex; respect the current native mode.
CODEX-END -->

### 0.2 Asking User Questions

**If `PILOT_PLAN_QUESTIONS_ENABLED` is `"false"` (above),** skip all `AskUserQuestion` calls in Steps 4 and 6. Make reasonable default choices (including selecting the recommended approach in Step 6) and document them in the plan under an "Autonomous Decisions" sub-section. Continue to the next step immediately.

<!-- CC-ONLY -->
**Use `AskUserQuestion` for clarification when available and permitted.** Otherwise ask one concise question in prose and wait when its answer is required.
<!-- /CC-ONLY -->
<!-- CODEX-START
**Use the runtime's structured user-input tool when exposed and permitted for the question.** Otherwise ask one concise question in prose and wait when its answer is required. Tool availability alone does not override restrictions on approval questions or the active runtime mode.
CODEX-END -->

**Questions enabled means allowed, not required.** Proceed when the request and workspace supply enough information. Ask only about an unresolved decision that materially changes scope, architecture, or user-visible behavior; bundle related questions and give concrete trade-offs. A reversible implementation choice is yours to make and document. A disabled clarification toggle does not authorize inventing missing credentials, approval, or destructive scope.
