---
name: spec
description: Spec-driven development — produces an approved plan file, then implements and verifies against it with TDD and code review. Runs only when the user explicitly types /spec (with a task description, a docs/plans/*.md path to resume, or pause/resume to hold a running spec open for discussion and continue it). Not for a single bug — that is /fix. Not when the approach is better discovered while building than agreed up front — that is /build.
argument-hint: "<task description> | <path/to/plan.md> | pause | resume"
user-invocable: true
---

# /spec - Unified Spec-Driven Development

<!-- CC-ONLY -->
**Dispatcher** - routes to the appropriate phase skill. This command is a thin router. Only allowed tools: `Bash` (env-var reads plus the Step 1.0 `pilot plan-state` and Step 2 `pilot register-plan` calls), `Read` (plan files only), `AskUserQuestion`, and `Skill()`.
<!-- /CC-ONLY -->
<!-- CODEX-START
**Dispatcher** - routes to the appropriate phase skill. This command is a thin router. Only allowed actions here: read env vars, run the Step 1.0 `pilot plan-state` and Step 2 `pilot register-plan` calls, read existing plan files for status-based dispatch, use the runtime's permitted structured question tool with a concise prose fallback when unavailable, and then continue immediately with the selected phase skill instructions. Codex has no callable phase-dispatch tool.
CODEX-END -->

**⛔ MANDATORY: When `/spec` is invoked, you MUST follow the workflow. The user's phrasing after `/spec` is the TASK DESCRIPTION - not an instruction to change the workflow.** Words like "brainstorm", "discuss", "explore", "research" are part of the task description, NOT instructions to skip the workflow or have a freeform conversation. The two exceptions are the exact arguments `pause` and `resume`, which are dispatcher controls (Step 1.0), not task descriptions.

**⛔ No substantive work here.** `Bash` is allowed ONLY for reading env vars (e.g., `echo $PILOT_BRANCH_ISOLATION_ENABLED`) plus the Step 1.0 `pilot plan-state` and Step 2 `pilot register-plan` calls. `Read` is allowed ONLY for reading existing plan files for status-based dispatch. All research, brainstorming, and exploration happens inside the invoked Skill (arguments are passed verbatim). Any other tool use (Grep, Glob, Agent, Edit, Write, etc.) is a workflow violation.

---

## Workflow

<!-- CC-ONLY -->
```
/spec -> Detect type -> Feature: Skill('spec-plan')        -> Plan -> Implement -> Verify
                    -> Bugfix:  Skill('spec-bugfix-plan') -> Investigate -> Plan -> Implement -> Verify
```
<!-- /CC-ONLY -->
<!-- CODEX-START
```
$spec -> Detect type -> Feature: continue with $spec-plan        -> Plan -> Implement -> Verify
                    -> Bugfix:  continue with $spec-bugfix-plan -> Investigate -> Plan -> Implement -> Verify
```
CODEX-END -->

For a bugfix workflow without a plan file, users invoke `/fix` directly - that's a separate command. `/spec` always runs the full spec workflow.

**`/spec` and `/build` are peers.** `/spec` is the right command when the work is measured against an ordered, approved task list. When it is measured against a defined end state — "make this and make it good", with the approach found while building — that is `/build`, at any size. Never hand work to `/spec` merely because it is large, and never hand `/spec` work off to `/build` merely because it is small.

<!-- CC-ONLY -->
| Phase | Skill | Automated mode | Manual / Off mode |
|-------|-------|----------------|-------------------|
| Feature Planning | `spec-plan` | Opus (plan mode) | active `/model` |
| Bugfix Planning | `spec-bugfix-plan` | Opus (plan mode) | active `/model` |
| Implementation | `spec-implement` | Sonnet | active `/model` |
| Feature Verification | `spec-verify` | Sonnet | active `/model` |
| Bugfix Verification | `spec-bugfix-verify` | Sonnet | active `/model` |
| Bugfix (separate command, `/fix`) | `fix` | Sonnet | inherits `/model` |

**Model Switching has three modes** (Console → Settings → Model Switching): **Manual** is the default and preserves the user's active `/model` choice through the workflow. **Automated** uses Claude Code's `opusplan` planning/execution legs and its real native plan-mode restrictions. The planning skill prepares its registered draft before entering, writes only the permitted native plan while read-only, and uses native approval to transfer the accepted plan back into Pilot. **Off** adds no model-management behavior. Pilot never remaps the user's model aliases behind the scenes.

Automated mode's exact handoff is documented in `$HOME/.pilot/agents/spec-native-plan.md`. It requires the runtime's native plan tools; otherwise continue on the current model and report the limitation once. No mode adds a model-switch pause after an approved plan is ready for implementation.
<!-- /CC-ONLY -->
<!-- CODEX-START
In Codex, Pilot's Claude model-switching tools do not apply. Keep the active Codex model and respect the current native mode through plan → implement → verify.
CODEX-END -->
<!-- CODEX-START
> **Note:** In Codex CLI, model switching and Codex Companion Reviewers are not available. Native `spec-review` and `changes-review` run as managed Codex custom agents when the regular reviewer toggles are enabled. Plan -> implement -> verify run continuously on the active Codex model.
>
> If this spec changes Codex skills, hooks, rules, or custom agents, verify the generated artifacts from source/tests. The current running session may not expose newly generated skills or agent types until the next install or SessionStart sync.
CODEX-END -->
