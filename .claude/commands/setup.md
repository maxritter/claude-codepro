---
description: Initialize project instruction rules, MCP server rules and semantic search indexing
model: opus
---
# /setup - Project Initialization

**Run once to initialize project context.** Scans project structure, creates documentation, and builds semantic search index. Benefits both Spec-Driven and Quick modes.

## What It Does

1. **Project Discovery** - Scans directories, identifies technologies and frameworks
2. **Documentation** - Creates `.claude/rules/custom/project.md` with project context
3. **MCP Documentation** - Documents external MCP servers if configured
4. **Semantic Search** - Initializes Vexor index for code search

---

## Execution Sequence

### Phase 1: Project Discovery

1. **Scan Directory Structure:**
   ```bash
   tree -L 3 -I 'node_modules|.git|__pycache__|*.pyc|dist|build|.venv|.next|coverage|.cache|cdk.out|.mypy_cache|.pytest_cache|.ruff_cache'
   ```

2. **Identify Technologies by checking for:**
   - `package.json` → Node.js/JavaScript/TypeScript
   - `tsconfig.json` → TypeScript
   - `pyproject.toml`, `requirements.txt`, `setup.py` → Python
   - `Cargo.toml` → Rust
   - `go.mod` → Go
   - `pom.xml`, `build.gradle` → Java
   - `Gemfile` → Ruby
   - `composer.json` → PHP

3. **Identify Frameworks by checking for:**
   - React, Vue, Angular, Svelte (frontend)
   - Next.js, Nuxt, Remix (fullstack)
   - Express, Fastify, NestJS (Node backend)
   - Django, FastAPI, Flask (Python backend)
   - Check `package.json` dependencies or `pyproject.toml` for framework indicators

4. **Analyze Configuration:**
   - Read README.md if exists for project description
   - Check for .env.example to understand required environment variables
   - Identify build tools (webpack, vite, rollup, esbuild)
   - Check testing frameworks (jest, pytest, vitest, mocha)

### Phase 2: Create Project Documentation

1. **Check if project.md already exists:**
   - If exists, ask user: "project.md already exists. Overwrite? (y/N)"
   - If user says no, skip to Phase 3

2. **Generate `.claude/rules/custom/project.md` with this structure:**

```markdown
# Project: [Project Name from package.json/pyproject.toml or directory name]

**Last Updated:** [Current date/time]

## Overview

[Brief description from README.md or ask user]

## Technology Stack

- **Language:** [Primary language]
- **Framework:** [Main framework if any]
- **Build Tool:** [Vite, Webpack, etc.]
- **Testing:** [Jest, Pytest, etc.]
- **Package Manager:** [npm, yarn, pnpm, uv, cargo, etc.]

## Directory Structure

```
[Simplified tree output - key directories only]
```

## Key Files

- **Configuration:** [List main config files]
- **Entry Points:** [Main entry files like src/index.ts, main.py]
- **Tests:** [Test directory location]

## Development Commands

- **Install:** [e.g., `npm install` or `uv sync`]
- **Dev:** [e.g., `npm run dev` or `uv run python main.py`]
- **Build:** [e.g., `npm run build`]
- **Test:** [e.g., `npm test` or `uv run pytest`]
- **Lint:** [e.g., `npm run lint` or `uv run ruff check`]

## Architecture Notes

[Brief description of architecture patterns used]

## Additional Context

[Any other relevant information discovered or provided by user]
```

3. **Write the file:**
   ```python
   Write(file_path=".claude/rules/custom/project.md", content=generated_content)
   ```

### Phase 3: Document External MCP Servers

**Purpose:** If the user has configured external MCP servers in `.mcp.json`, create documentation to help Claude use them effectively.

1. **Check for `.mcp.json` in project root:**
   ```bash
   cat .mcp.json 2>/dev/null || echo "NO_MCP_CONFIG"
   ```

2. **If `.mcp.json` exists with `mcpServers`:**
   - Parse the JSON to get server names
   - Filter out built-in servers: `firecrawl`, `context7`, `claude-mem`, `ide`, `plugin_*`
   - If external servers remain, proceed to step 3
   - If no external servers, skip to Phase 4

3. **Check if mcp-servers.md already exists:**
   - If exists, ask user: "mcp-servers.md already exists. Overwrite? (y/N)"
   - If user says no, skip to Phase 4

4. **For each external MCP server, gather information:**
   - Use `mcp-cli info <server>/<tool>` to discover available tools
   - Use `mcp-cli tools <server>` to list all tools for that server
   - Web search for official documentation if available

5. **Generate `.claude/rules/custom/mcp-servers.md`:**

```markdown
# External MCP Servers

**Last Updated:** [Current date]

This project has the following external MCP servers configured.

## [Server Name]

**Description:** [Brief description]

**Available Tools:**
- `tool_name` - [Description]

**Example:**
```bash
mcp-cli call [server]/[tool] '{"param": "value"}'
```
```

6. **Write the file:**
   ```python
   Write(file_path=".claude/rules/custom/mcp-servers.md", content=generated_content)
   ```

### Phase 4: Initialize Semantic Search with Vexor

1. **Check if Vexor is available:**
   ```bash
   vexor --version
   ```

2. **Build the index:**
   ```bash
   vexor index --path /absolute/path/to/project
   ```

3. **Verify with a test search:**
   ```bash
   vexor search "main entry point" --top 3
   ```

4. **Check index metadata:**
   ```bash
   vexor index --show
   ```

## Error Handling

- **If tree command not available:** Use `ls -la` recursively with depth limit
- **If Vexor not installed:** Inform user and skip indexing
- **If README.md missing:** Ask user for brief project description
- **If package.json/pyproject.toml missing:** Infer from file extensions

## Important Notes

- Use absolute paths when specifying `--path` for Vexor
- Don't overwrite existing project.md without confirmation
- Keep project.md concise - it's included in every session
- Vexor respects `.gitignore` by default
