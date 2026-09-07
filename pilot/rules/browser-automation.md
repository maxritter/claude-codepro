---
paths:
  - "**/*.{ts,tsx,js,jsx,mjs,cjs,html,css,scss,vue,svelte,astro}"
  - "**/{tests,test,e2e,playwright,cypress,__tests__}/**"
  - "**/playwright.config.*"
  - "**/cypress.config.*"
---

## Browser Automation for E2E Testing

Use actual interaction and rendered-state evidence for claims about a UI. API responses, source inspection, typechecks, and a page that loads without errors establish narrower facts.

### Choose the driver for the actual interface

Read the project's documented verification path first. These rules apply to browser pages; mobile WebViews, native mobile/desktop windows, extensions, terminal UIs, and canvas surfaces may need a platform-specific driver. For mobile, see `mobile-development.md`.

Use the current runtime's supported browser interface or the project's existing test harness. Prefer a suitable already-connected session when it has the required access; use an isolated profile for tests that need their own state. Driver capabilities and availability determine the choice, not a fixed vendor order.

| Need | Available options to consider |
|------|-------------------------------|
| Existing authenticated browser session | The runtime's browser/computer-use tool; Claude Code Chrome when exposed |
| DevTools inspection, network/performance tracing | Chrome DevTools MCP or the project's CDP-capable harness |
| Repeatable E2E with fixtures, network isolation, multiple pages | Existing Playwright/Cypress tests or `playwright-cli` |
| A bounded click-and-inspect check | Runtime browser tools or `agent-browser` |

Discover actual tool schemas or CLI `--help`. Do not assume a provider prefix, locator API, session flag, or capability is present in both Claude Code and Codex. If the driver fails, inspect the error and current UI state, then repair the concrete cause or use a suitable available alternative. Repeated selector failures warrant checking the target, frame/WebView, stale references, overlays, and documented driver; a fixed retry count does not prove the driver is wrong.

### Interaction evidence

Navigate to the affected state, inspect it, perform the action the change affects, and inspect the result. Verify the expected outcome and relevant error paths. A read-only visual change needs rendered comparison; it does not require an invented click or unrelated workflow.

Use fresh element references after navigation or dynamic changes. Prefer stable semantic locators where the driver supports them; use screenshot coordinates only when appropriate for that surface and refresh bounds after state changes. Wait for meaningful conditions with timeouts.

If execution is blocked, follow `verification.md` to inspect the project's usable targets and report the actual limitation. Do not claim E2E passed or deploy to an unrelated target solely to obtain a green result.

### Visual changes

Apply this section only when layout, styling, content hierarchy, theming, or interaction affordances change. Logic-only changes do not authorize a redesign.

- Read the existing tokens/components and compare the affected rendered state with the established product language.
- Inspect representative narrow/wide viewports and each affected supported theme.
- Exercise the states the change can affect: loading, empty, error, focus, disabled, or selected. Do not invent unsupported product states.
- Verify accessibility requirements from `standards-frontend.md`; a screenshot alone cannot prove keyboard or assistive-technology behaviour.

### Design-quality detector (advisory)

Impeccable owns deterministic design-pattern detection. Reuse its current edit/stop hook findings for the changed files. Use the fallback only when no applicable hook evidence exists or when rechecking a fixed finding. Findings are suggestions, not a verification failure or a reason to withhold completion.

```bash
impeccable detect --json <explicit-changed-ui-files-or-rendered-output>
```

- Check that the binary is available first. Exit `0` means clean and `2` means findings; inspect the JSON. A missing binary, other failure, invalid JSON, or timeout gets a brief skip note when material.
- Bound the target to explicit changed UI files or a narrowly scoped rendered-output directory. Never scan the repository root by default; use a timeout.
- An SPA's static `index.html` is usually an empty shell. Inspect its changed source or rendered DOM obtained through the supported browser interface; for SSG/SSR, the built HTML can be the relevant artifact. Do not invent a browser API or bypass the tool's access restrictions to extract it.
- Treat vendored-component findings in context. Do not create ignore configuration automatically.

### Session isolation

Keep parallel work in separately owned tabs/pages or profiles. Record the session/page identifiers in working state and close only resources this task created. A parent session id may be shared by subagents, so distinct workers need distinct tab/profile ownership.

For CLI tools, inspect the installed session option (`agent-browser --session` or `playwright-cli -s`) and choose a task-specific identifier. Do not reuse or overwrite a user's browser profile merely to isolate a test.

### Tool-specific notes

<!-- CC-ONLY -->
- Claude Code Chrome tools load through the exposed discovery mechanism. Blocking native `alert`/`confirm`/`prompt` dialogs may interrupt extension control; handle them through a supported dialog tool.
- Chrome DevTools snapshots use element references that become stale after navigation. Rediscover the current state before acting.
<!-- /CC-ONLY -->
<!-- CODEX-START
Use the browser/computer-use tools exposed by the current Codex session when suitable. Chrome DevTools MCP, playwright-cli, or agent-browser are alternatives when available; do not assume Claude Code's browser extension is available.
CODEX-END -->
- `agent-browser` and `playwright-cli` use different reference and session syntax. Read the installed help or loaded skill, then use that tool's current references.
