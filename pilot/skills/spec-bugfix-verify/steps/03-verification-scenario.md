## Step 3: Verification Scenario (if exists in plan)

Check whether the plan has a `## Verification Scenario` section (only present for UI-facing bugs).

**If no Verification Scenario:** proceed to Step 4.

**If Verification Scenario exists:**

**Resolve the driver:** first check whether the project's own rules (`.claude/rules/`, `CLAUDE.md`, `AGENTS.md`) name the tool that reaches its UI — a mobile WebView or native window has one the ladder below does not cover. Otherwise use the available browser-control or Chrome DevTools tools according to their exposed schemas; fall back to installed playwright-cli or agent-browser when appropriate. Discover deferred tools using the current runtime's tool-discovery surface. See `browser-automation.md`.

```bash
<!-- CC-ONLY -->
# Chrome DevTools MCP: load via ToolSearch(query="chrome-devtools-mcp", max_results=30)
<!-- /CC-ONLY -->
<!-- CODEX-START
# Chrome DevTools MCP: use the available Chrome DevTools MCP tools if present; if deferred, load them with the available tool-discovery helper.
CODEX-END -->
# playwright-cli:
playwright-cli -s="${CLAUDE_CODE_SESSION_ID:-${CODEX_THREAD_ID:-${PILOT_SESSION_ID:-default}}}" open <url>
# agent-browser fallback:
AB_SESSION="${CLAUDE_CODE_SESSION_ID:-${CODEX_THREAD_ID:-${PILOT_SESSION_ID:-default}}}"
agent-browser --session "$AB_SESSION" open <url>
```

1. Execute each step from the scenario using the resolved browser tool
   - **Chrome:** `navigate`, `read_page`, `computer`/`form_input`
   - **Chrome DevTools MCP:** `navigate_page`, `take_snapshot`, `click(uid=...)`/`fill(uid=...)`
   - **playwright-cli:** `open`/`goto`, `snapshot`, `click`/`fill` (bare refs: `e1`)
   - **agent-browser:** `open`/`goto`, `snapshot -i`, `click`/`fill` (refs: `@e1`)
2. Verify the expected result for each step (read page after each interaction)
3. **PASS:** Scenario confirms fix works — close browser (CLI tools only), proceed to Step 4
4. **FAIL (attempt 1):** Analyze root cause, implement fix, re-run tests, re-execute scenario
5. **FAIL (attempt 2):** Implement second fix, re-run tests, re-execute scenario
<!-- CC-ONLY -->
6. **FAIL after 2 attempts:** The bug is not fully fixed — route the loop-back through Step 7's iteration-cap check (read `Iterations:`; if `>= 3`, surface Continue/Pivot/Abandon to the user before incrementing), which sets `Status: PENDING`, increments `Iterations`, and re-invokes `Skill(skill='spec-implement', args='<plan-path> $LANE_FLAG')`. Do not proceed to VERIFIED, and do not bypass the cap.
<!-- /CC-ONLY -->
<!-- CODEX-START
6. **FAIL after 2 attempts:** The bug is not fully fixed — route the loop-back through Step 7's iteration-cap check (read `Iterations:`; if `>= 3`, present Continue/Pivot/Abandon to the user before incrementing), which sets `Status: PENDING`, increments `Iterations`, and continues with the `$spec-implement` skill instructions using arguments: `<plan-path> $LANE_FLAG`. Do not proceed to VERIFIED, and do not bypass the cap.
CODEX-END -->

```bash
# Chrome DevTools MCP: no explicit close needed
# playwright-cli: playwright-cli -s="${CLAUDE_CODE_SESSION_ID:-${CODEX_THREAD_ID:-${PILOT_SESSION_ID:-default}}}" close
# agent-browser: agent-browser --session "$AB_SESSION" close
```
