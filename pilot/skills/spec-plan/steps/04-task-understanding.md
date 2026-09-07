## Step 4: Task Understanding, Discuss & Clarify

<!-- CC-ONLY -->
While native plan mode is active, omit the notification command below. Ask required clarification through the permitted native input surface; defer external notifications until native exit.
<!-- /CC-ONLY -->

1. Restate the task in your own words — core problem, assumptions
2. **Scope check:** Identify independent subsystems and dependencies. Organize them into coherent tasks while preserving the full request. Split into linked plans only when that improves execution or review; keep every requested subsystem accounted for rather than silently proceeding with only the first.
3. Identify gray areas:

   | Domain      | Typical Gray Areas                                 |
   | ----------- | -------------------------------------------------- |
   | UI/frontend | Layout, interaction patterns, empty/loading states |
   | API/backend | Response shape, error codes, auth, pagination      |
   | CLI/scripts | Output format, flags, exit codes                   |
   | Data/config | Schema, migration, validation, defaults            |

4. **Code-first rule: ground every question in the Step 3 Workspace Scan output.** Before formulating a question, ask "can I answer this from the codebase?" If yes, do that instead — don't ask. For questions you do ask, **option labels must reference real files and symbols when the scan found them** — e.g., `Extend LicenseAuth in launcher/auth.py:42`, not `Extend existing module`. Only ask the user about decisions the code can't make — purpose, priority trade-offs, scope boundaries, behavioral expectations not yet encoded.

   - If `Greenfield?: yes` in the scan output, fall back to generic options and note the fallback under "Autonomous Decisions" in Step 9.
   - If the scan output names symbols/files relevant to a question, generic labels are a regression — use the names. Asking the user about facts already in the codebase, or asking with abstract options when grounded ones are available, is the single biggest source of unnecessary friction in planning.

<!-- CC-ONLY -->
5. **Ask Batch 1 questions** → notify, then use `AskUserQuestion` with each question as a separate entry with predefined options:

   ```bash
   ~/.pilot/bin/pilot notify plan_approval "Input Needed" "<plan_name> — clarification questions" --plan-path "<plan_path>" 2>/dev/null || true
   ```

   Each question must have 2-4 concrete options. Use `multiSelect: true` when choices aren't mutually exclusive.

   Skip this interaction when the request and workspace already resolve the material decisions. Do not manufacture questions about exclusions, priorities, or edge cases merely because a plan has several files.
<!-- /CC-ONLY -->
<!-- CODEX-START
5. **Codex Batch 1 policy:** ask only when the answer would change task boundaries, architecture, or user-visible behavior and cannot be inferred from the request or code.

   - If no blocking question remains, continue and record any reversible defaults in the plan under "Assumptions" or "Autonomous Decisions".
   - If asking, notify first, use the current runtime's permitted structured input tool, bundling related questions; otherwise ask a concise prose question.
   - Do not ask the user to choose between facts the codebase can answer. Read the relevant file instead.
CODEX-END -->
