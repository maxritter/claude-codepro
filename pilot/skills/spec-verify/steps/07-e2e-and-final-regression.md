## Step 7: E2E Verification & Final Regression

**If runtime profile is not Full:** Skip directly to sub-section 7f (Final Regression). The Full-profile E2E sub-steps below assume a UI/browser entry point.

### 7a-pre: Resolve an Authorized Live Target

Use the plan's Runtime Environment and repository commands to establish a target that runs the changed code:

1. Reuse a relevant running local instance when its code identity can be verified.
2. Otherwise start the local test or development service on an available port. Keep its process handle, check readiness, and inspect relevant startup errors if it fails.
3. Use a remote preview or deployed instance only when that target and operation are already authorized. Verify the environment and deployment command from the project configuration before executing it. Available credentials are access, not deployment permission; a generic `deploy` command may update production.
4. If no authorized target can be established, record what was attempted, the blocker, and which scenarios lack live evidence. Continue independent checks. Ask for a missing decision only after the deployable result is concrete and reviewable.

Never report a unit or static check as `LIVE_PASS`. A `UNIT_VERIFIED` result describes its limited evidence; it does not satisfy a criterion that explicitly requires the running UI or service.

### 7a: Resolve Browser Tool

**Driver resolution** (see `browser-automation.md`): the tool the project's own rules name, else the 4-tier ladder — Chrome → Chrome DevTools MCP → playwright-cli → agent-browser.

<!-- CC-ONLY -->
1. **Claude Code Chrome:** Check if `mcp__claude-in-chrome__*` tools are in your available/deferred tools list. If available, use Chrome for all E2E steps below. Load tools via `ToolSearch(query="select:mcp__claude-in-chrome__<tool>")`. No session isolation needed.

2. **Chrome DevTools MCP:** If Chrome extension is unavailable, check for `mcp__plugin_chrome-devtools-mcp_chrome-devtools__*` tools. Load via `ToolSearch(query="chrome-devtools-mcp", max_results=30)`. Use `take_snapshot()` for a11y tree with uids, `click(uid=...)` / `fill(uid=...)` for interaction.
<!-- /CC-ONLY -->

3. **playwright-cli (CLI fallback):** If neither Chrome tool is available, use playwright-cli for thorough E2E.
```bash
playwright-cli -s="${CLAUDE_CODE_SESSION_ID:-${CODEX_THREAD_ID:-${PILOT_SESSION_ID:-default}}}" open <url>
```

4. **agent-browser (lightweight fallback):** If none of the above are available:
```bash
AB_SESSION="${CLAUDE_CODE_SESSION_ID:-${CODEX_THREAD_ID:-${PILOT_SESSION_ID:-default}}}"
agent-browser --session "$AB_SESSION" open <url>
```

### 7b: Check for Structured Scenarios

Read the plan's `## E2E Test Scenarios` section (if it exists).

**If structured scenarios exist (TS-NNN format):** Follow 7c below.

**If no structured scenarios:** Fall back to ad-hoc verification — test the primary user workflow (every view, interaction, state transition), then cover edge cases:

| Category | What to test |
|----------|-------------|
| Empty state | No data, no results |
| Invalid input | Bad params, wrong types, injection |
| Stale state | References to deleted data |
| Error state | Backend unreachable |
| Boundary | Max values, zero, single item |

Then skip to 7e (close browser + write results).

### 7c: Execute Structured Scenarios

Execute Critical first, then High, then Medium.

<!-- CC-ONLY -->
Create one task per scenario for tracking:

```
TaskCreate(subject="TS-NNN: [name]", description="[priority] | [preconditions]")
```
<!-- /CC-ONLY -->

**For each scenario:**

<!-- CC-ONLY -->
1. `TaskUpdate → in_progress`
<!-- /CC-ONLY -->
1. Execute each step using the resolved browser tool:
   - **Chrome:** `navigate` to open pages, `read_page` after interactions, `computer`/`form_input` per the step's action
   - **Chrome DevTools MCP:** `navigate_page` to open pages, `take_snapshot` after interactions, `click(uid=...)`/`fill(uid=...)` per the step's action
   - **playwright-cli:** `open`/`goto` to navigate, `snapshot` after interactions, `click`/`fill`/`press` per the step's action (refs are bare: `e1` not `@e1`)
   - **agent-browser:** `open`/`goto` to navigate, `snapshot -i` after interactions, `click`/`fill`/`press` per the step's action (refs use `@`: `@e1`)
   - Verify the expected result by reading the page output
3. **PASS:** All steps match expected results → note `TS-NNN: PASS`
4. **FAIL:** Step result doesn't match expected:
   - Analyze root cause, implement minimal fix, re-run relevant tests (stay in Phase B — no code changes that need re-review)
   - Re-execute the scenario (counts as fix attempt 1)
   - If still failing: implement second fix, re-execute (fix attempt 2)
   - After 2 failed fix attempts: note `TS-NNN: KNOWN_ISSUE — [description]`
<!-- CC-ONLY -->
5. **Critical KNOWN_ISSUE** → run the iteration-cap check from Step 11 (read `Iterations:` from the plan header; if `>= 3` ask the user Continue / Pivot / Abandon before incrementing). On Continue: set `Status: PENDING`, increment `Iterations`, register status change, invoke `Skill(skill='spec-implement', args='<plan-path> $LANE_FLAG')` — do not proceed to VERIFIED. On Pivot/Abandon: do not invoke spec-implement; surface to user per Step 11.
<!-- /CC-ONLY -->
<!-- CODEX-START
5. **Critical KNOWN_ISSUE** → run the iteration-cap check from Step 11 (read `Iterations:` from the plan header; if `>= 3` present the user with Continue / Pivot / Abandon options before incrementing). On Continue: set `Status: PENDING`, increment `Iterations`, register status change, then continue immediately with the `$spec-implement` skill instructions using arguments: `<plan-path> $LANE_FLAG` — do not proceed to VERIFIED. On Pivot/Abandon: do not invoke spec-implement; surface to user per Step 11.
CODEX-END -->
6. **High/Medium KNOWN_ISSUE** → document and continue (non-blocking)

### 7d: Write E2E Results to Plan

After all scenarios are executed, append to the plan file:

```markdown
## E2E Results

| Scenario | Priority | Result | Fix Attempts | Notes |
|----------|----------|--------|--------------|-------|
| TS-001   | Critical | PASS   | 0            |       |
| TS-002   | High     | PASS   | 1            | Fixed: missing validation on empty submit |
| TS-003   | Medium   | KNOWN_ISSUE | 2       | Tooltip misaligned on narrow viewport |
```

### 7d-design: UI Design Review

Full profile only, and only when the diff changes user-visible layout, styling, content hierarchy, theming, or interaction affordances. A logic-only change in a UI file skips this step with one line and does not authorize a redesign.

Invoke `Skill(skill='open-claude-ui-review', args='<plan-path> Review the changed UI against its existing product system. The parent /spec workflow authorizes fixes for in-scope blockers and quality issues. Use the runtime evidence and open browser from Step 7, apply only request-traceable fixes, re-run affected interactions after edits, and return the verdict plus unresolved findings and advisory Design Notes.')`.

The UI design review skill owns accessibility, hierarchy/rhythm, brand fidelity, interaction-state coverage, viewport/theme checks, and the bounded advisory detector contract. Do not duplicate those procedures here.

- If the skill edits code, re-run the affected E2E scenarios before closing the browser; Step 7f then runs the final regression.
- An unresolved **Blocker** is a Critical KNOWN_ISSUE and follows the existing iteration-cap route before VERIFIED.
- Record unresolved **Quality issue** findings with their evidence and scope decision.
- Record **Advisory** findings or detector skips in a single `Design Notes:` line; advisory findings alone never flip the plan away from VERIFIED.

### 7e: Close Browser

```bash
# Chrome / Chrome DevTools MCP: no explicit close needed
# playwright-cli: playwright-cli -s="${CLAUDE_CODE_SESSION_ID:-${CODEX_THREAD_ID:-${PILOT_SESSION_ID:-default}}}" close
# agent-browser: agent-browser --session "$AB_SESSION" close
```

### 7f: Final Regression

Confirm the required suite, type check, and build passed against the final code. Reuse successful checks from this run when their inputs have not changed. Re-run affected checks after Phase B fixes, generated-artifact changes, or environment changes; a phase boundary alone does not require another identical suite.
