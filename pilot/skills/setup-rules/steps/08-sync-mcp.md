## Step 8: Sync MCP Rules

**Document user-configured MCP servers.** Skip framework-provided servers (e.g., Pilot core: context7, mem-search, web-search, web-fetch, grep-mcp) — only document servers the user added themselves.

### Step 8.1: Discover

Parse `.mcp.json`, exclude framework-provided servers (Pilot core servers if present: context7, mem-search, web-search, web-fetch, grep-mcp).

### Step 8.2: Smoke-Test

For each user server:

<!-- CC-ONLY -->
1. `ToolSearch(query="+server-name keyword")` to discover tools
<!-- /CC-ONLY -->
<!-- CODEX-START
1. Discover the server's tools through the current runtime's tool inventory or discovery helper, then use the exposed names and schemas. A configured server is not proof that a tool is currently connected.
CODEX-END -->
2. Call 1-2 read-only tools per server as a connectivity check (**safety: only read-only tools**) — no need to test every tool, just confirm the server responds
3. Record per-server: ✅ connected | ⚠️ partial (note issues) | ❌ unreachable
4. Report health check:
   ```
   ✅ polar — connected, tools responding
   ⚠️ typefully — connected, 1 permission error on write tools
   ❌ my-api — connection refused
   ```
5. Report connection problems separately from stable server guidance. Ask only when an unresolved server identity or purpose affects what should be documented.

Connection status is audit evidence for this run, not stable repository guidance. Report it in the final summary; do not persist a transient health result in `AGENTS.md` or a scoped rule.

### Step 8.3: Document

Compare against the MCP section in `AGENTS.md` and any scoped `{slug}-mcp-servers.md`. Apply supported changes within an authorized setup/refresh; keep an audit-only request read-only.

Also look for a legacy unscoped `mcp-servers.md`. Move repo-wide decision guidance into `AGENTS.md`; keep only path-specific detail in a `{slug}-mcp-servers.md` rule with `paths` frontmatter.

### Step 8.4: Write

**MCP tools are self-describing** — agents already get tool names, descriptions, and schemas when connected. Do NOT enumerate individual tools or create per-tool tables. That information is redundant and wastes context tokens.

**Focus on behavioral guidance** — what the rules should capture is context that tool descriptions alone cannot provide: when to consult the server, how it fits into the project's workflow, and decision-making guidance.

Put the concise, repo-wide decision boundary in `AGENTS.md`:

```markdown
## [server-name]

**Purpose:** [What this server provides — one line]
**Consult this MCP when:**
- [Situation where this server should be used instead of alternatives]
- [Decision point where the server provides relevant context]
- [Workflow step where consulting this server prevents mistakes]

**Usage:** Discover the server's tools from the active session, then use the exposed names and schemas. Do not hardcode one agent's tool namespace into shared guidance.
```

Only create `.claude/rules/{slug}-mcp-servers.md` when the server guidance applies to specific repository paths. Add `paths` frontmatter, keep the same behavioral format, and list it in the `AGENTS.md` matching-rule index.

**Do NOT include:**
- Per-tool tables (`| Tool | Description |`) — tools describe themselves
- Tool parameter documentation — schemas are provided by the server
- Usage examples for individual tools — agents read the tool schema

**DO include:**
- When to consult vs. when NOT to (decision boundaries)
- Project-specific workflow context (e.g., "check this before upgrading @dialpad/ deps")
- Gotchas or non-obvious behaviors specific to this project's usage
- Required env vars or auth setup if not obvious from server config

**Skip if:** no `.mcp.json`, no user-added servers, user declines.
