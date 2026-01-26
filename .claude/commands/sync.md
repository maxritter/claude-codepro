---
description: Sync project rules and skills with codebase - reads existing rules/skills, explores code, updates documentation, creates new skills
model: opus
---
# /sync - Sync Project Rules & Skills

**Sync custom rules and skills with the current state of the codebase.** Reads existing rules/skills, explores code patterns, identifies gaps, updates documentation, and creates new skills when workflows are discovered. Run anytime to keep rules and skills current.

## What It Does

1. **Read existing rules & skills** - Load all `.claude/rules/custom/*.md` and `.claude/skills/` to understand current state
2. **Build search index** - Initialize/update Vexor for semantic code search
3. **Explore codebase** - Use Vexor, Grep, and file analysis to discover patterns
4. **Compare & sync** - Update outdated rules, add missing patterns
5. **Create skills** - When reusable workflows are discovered, invoke skill-creator

All files in `.claude/rules/custom/` are project-specific rules loaded into every session.
Custom skills in `.claude/skills/` (non-standard names) are preserved during updates.

---

## Important Guidelines

- **Always use AskUserQuestion tool** when asking the user anything
- **Read before writing** — Always check existing rules before creating new ones
- **Write concise rules** — Every word costs tokens in the context window
- **Offer suggestions** — Present options the user can confirm or correct
- **Idempotent** — Running multiple times produces consistent results

---

## Execution Sequence

### Phase 1: Read Existing Rules

**MANDATORY FIRST STEP: Understand what's already documented.**

1. **List all custom rules:**
   ```bash
   ls -la .claude/rules/custom/*.md 2>/dev/null
   ```

2. **Read each existing rule file** to understand:
   - What patterns are already documented
   - What areas are covered (project, MCP, API, search, CDK, etc.)
   - What conventions are established
   - Last updated timestamps

3. **Build mental inventory:**
   ```
   Documented areas: [list from reading files]
   Documented patterns: [list key patterns found]
   Potential gaps to investigate: [areas not covered]
   Possibly outdated: [rules with old timestamps or suspicious content]
   ```

### Phase 2: Initialize Vexor Index

**Build/update the semantic search index before exploration.**

> **Note:** First-time indexing can take several minutes as embeddings are generated locally using CPU (or GPU if available). Subsequent syncs are much faster due to caching.

1. **Check Vexor availability:**
   ```bash
   vexor --version
   ```

2. **If Vexor not installed:** Inform user, will use Grep/Glob for exploration instead.

3. **Build or update the index (use extended timeout for first run):**
   ```bash
   vexor index --path /absolute/path/to/project
   ```
   Use Bash with `timeout: 300000` (5 minutes) for first-time indexing.

4. **Verify index is working:**
   ```bash
   vexor search "main entry point" --top 3
   ```

### Phase 3: Explore Codebase

**Discover current patterns using Vexor, Grep, and file analysis.**

1. **Scan directory structure:**
   ```bash
   tree -L 3 -I 'node_modules|.git|__pycache__|*.pyc|dist|build|.venv|.next|coverage|.cache|cdk.out|.pytest_cache|.ruff_cache'
   ```

2. **Identify technologies:**
   - Check `package.json`, `pyproject.toml`, `tsconfig.json`, `go.mod`, etc.
   - Note frameworks, build tools, test frameworks

3. **Search for patterns with Vexor:**
   ```bash
   # Find API patterns
   vexor search "API response format error handling" --top 5

   # Find test patterns
   vexor search "test fixtures mocking patterns" --top 5

   # Find configuration patterns
   vexor search "configuration settings environment" --top 5

   # Search based on gaps identified in Phase 1
   vexor search "[undocumented area]" --top 5
   ```

4. **Use Grep for specific conventions:**
   - Response structures, error formats
   - Naming conventions, prefixes/suffixes
   - Import patterns, module organization

5. **Read representative files** (5-10) in key areas to understand actual patterns

### Phase 4: Compare & Identify Gaps

**Compare discovered patterns against existing documentation.**

1. **For each existing rule, check:**
   - Is the documented pattern still accurate?
   - Are there new patterns not yet documented?
   - Has the technology stack changed?
   - Are commands/paths still correct?

2. **Identify gaps:**
   - Undocumented tribal knowledge
   - New conventions that emerged
   - Changed patterns not reflected in rules
   - Missing areas entirely

3. **Use AskUserQuestion to confirm findings:**
   ```
   Question: "I compared existing rules with the codebase. Here's what I found:"
   Header: "Sync Results"
   Options:
   - "Update all" - Apply all suggested changes
   - "Review each" - Walk through changes one by one
   - "Show details" - Explain what changed before updating
   - "Skip updates" - Keep existing rules as-is
   ```

### Phase 5: Sync Project Rule

**Update `project.md` with current project state.**

1. **If project.md exists:**
   - Compare documented tech stack with actual
   - Verify directory structure is current
   - Check if commands still work
   - Update "Last Updated" timestamp
   - Preserve custom "Additional Context" sections

2. **If project.md doesn't exist, create it:**

```markdown
# Project: [Name from package.json/pyproject.toml or directory]

**Last Updated:** [Current date]

## Overview

[Brief description from README.md or ask user]

## Technology Stack

- **Language:** [Primary language]
- **Framework:** [Main framework]
- **Build Tool:** [Vite, Webpack, etc.]
- **Testing:** [Jest, Pytest, etc.]
- **Package Manager:** [npm, yarn, pnpm, uv, etc.]

## Directory Structure

```
[Simplified tree - key directories only]
```

## Key Files

- **Configuration:** [Main config files]
- **Entry Points:** [src/index.ts, main.py, etc.]
- **Tests:** [Test directory location]

## Development Commands

- **Install:** `[command]`
- **Dev:** `[command]`
- **Build:** `[command]`
- **Test:** `[command]`
- **Lint:** `[command]`

## Architecture Notes

[Brief description of patterns]
```

### Phase 6: Sync MCP Rules

**Update MCP server documentation if configured.**

1. **Check mcp_servers.json:**
   ```bash
   cat mcp_servers.json 2>/dev/null | head -50
   ```

2. **If MCP servers configured:**
   - List servers with `mcp-cli`
   - Compare against existing `mcp-servers.md`
   - Add new servers, update changed ones
   - Remove documentation for removed servers

3. **If mcp-servers.md exists but servers changed:**
   - Use AskUserQuestion: "MCP servers have changed. Update documentation?"

4. **Skip if no mcp_servers.json or user declines**

### Phase 7: Discover New Standards

**Find and document undocumented tribal knowledge.**

#### Step 7.1: Identify Undocumented Areas

Based on Phase 1 (existing rules) and Phase 3 (codebase exploration):

1. **List areas NOT yet covered by existing rules**

2. **Prioritize by:**
   - Frequency of pattern usage in codebase
   - Uniqueness (not standard framework behavior)
   - Likelihood of mistakes without documentation

3. **Use AskUserQuestion:**
   ```
   Question: "I found these undocumented areas. Which should we add rules for?"
   Header: "New Standards"
   multiSelect: true
   Options:
   - "[Area 1]" - [Pattern found, why it matters]
   - "[Area 2]" - [Pattern found, why it matters]
   - "[Area 3]" - [Pattern found, why it matters]
   - "None" - Skip adding new standards
   ```

#### Step 7.2: Document Selected Patterns

For each selected pattern:

1. **Ask clarifying questions:**
   - "What problem does this pattern solve?"
   - "Are there exceptions to this pattern?"
   - "What mistakes do people commonly make?"

2. **Draft the rule** based on codebase examples + user input

3. **Confirm before creating:**
   ```
   Question: "Here's the draft for [filename]. Create this rule?"
   Header: "Confirm Rule"
   Options:
   - "Yes, create it"
   - "Edit first" - I want to modify it
   - "Skip this one"
   ```

4. **Write to `.claude/rules/custom/[pattern-name].md`**

#### Step 7.3: Rule Format

```markdown
## [Standard Name]

[One-line summary]

### When to Apply

- [Trigger 1]
- [Trigger 2]

### The Pattern

```[language]
[Code example]
```

### Why

[1-2 sentences if not obvious]

### Common Mistakes

- [Mistake to avoid]

### Examples

**Good:**
```[language]
[Correct usage]
```

**Bad:**
```[language]
[Incorrect usage]
```
```

### Phase 8: Discover & Create Skills

**Identify patterns that would be better as skills than rules.**

Skills are appropriate when you find:
- **Multi-step workflows** - Procedures with sequential steps
- **Tool integrations** - Working with specific file formats, APIs, or external tools
- **Reusable scripts** - Code that gets rewritten repeatedly
- **Domain expertise** - Complex knowledge that benefits from bundled references

#### Step 8.1: Identify Skill Candidates

Based on codebase exploration, look for:

1. **Repeated workflows** - Same sequence of steps in multiple places
2. **Complex tool usage** - Specific patterns for working with tools/formats
3. **Scripts that could be bundled** - Utility code that's reused

**Use AskUserQuestion:**
```
Question: "I found patterns that might work better as skills. Create any?"
Header: "New Skills"
multiSelect: true
Options:
- "[Workflow 1]" - [Description of multi-step process]
- "[Tool integration]" - [Description of tool/format handling]
- "[Domain area]" - [Description of specialized knowledge]
- "None" - Skip skill creation
```

#### Step 8.2: Create Selected Skills

For each selected skill, **invoke the skill-creator skill**:

```
Skill(skill="skill-creator", args="create skill for [selected pattern]")
```

The skill-creator will:
1. Ask clarifying questions about the workflow
2. Plan reusable contents (scripts, references, assets)
3. Create the skill directory in `.claude/skills/`
4. Write the SKILL.md with proper frontmatter

**Important:** Use a unique skill name (not `plan`, `implement`, `verify`, or `standards-*`) so it's preserved during updates.

#### Step 8.3: Verify Skill Creation

After skill-creator completes:
1. Verify skill directory exists in `.claude/skills/`
2. Confirm SKILL.md has proper frontmatter (name, description)
3. Test skill is recognized: mention it in conversation to trigger

---

### Phase 9: Summary

**Report what was synced:**

```
## Sync Complete

**Vexor Index:** Updated (X files indexed)

**Rules Updated:**
- project.md - Updated tech stack, commands
- mcp-servers.md - Added 2 new servers

**New Rules Created:**
- api-responses.md - Response envelope pattern

**New Skills Created:**
- my-workflow - Multi-step deployment process

**No Changes Needed:**
- cdk-rules.md - Still current
- opensearch-mcp-server.md - Still current
```

**Offer to continue:**
```
Question: "Sync complete. What next?"
Header: "Continue?"
Options:
- "Discover more standards" - Look for more patterns to document
- "Create more skills" - Look for more workflow patterns
- "Done" - Finish sync
```

---

## Writing Concise Rules

Rules are loaded into every session. Every word costs tokens.

- **Lead with the rule** — What to do first, why second
- **Use code examples** — Show, don't tell
- **Skip the obvious** — Don't document standard framework behavior
- **One concept per rule** — Don't combine unrelated patterns
- **Bullet points > paragraphs** — Scannable beats readable
- **Max ~100 lines per file** — Split large topics

**Good:**
```markdown
## API Response Envelope

All responses use `{ success, data, error }`.

```python
{"success": True, "data": {"id": 1}}
{"success": False, "error": {"code": "AUTH_001", "message": "..."}}
```

- Always include `code` and `message` in errors
- Never return raw data without envelope
```

**Bad:**
```markdown
## Error Handling Guidelines

When an error occurs in our application, we have established a consistent pattern...
[3 more paragraphs]
```

---

## Error Handling

| Issue | Action |
|-------|--------|
| Vexor not installed | Use Grep/Glob for exploration, skip indexing |
| mcp-cli not available | Skip MCP documentation |
| No README.md | Ask user for project description |
| No package.json/pyproject.toml | Infer tech stack from file extensions |

---

## Output Locations

**Custom rules** in `.claude/rules/custom/`:

| Rule Type | File | Purpose |
|-----------|------|---------|
| Project context | `project.md` | Tech stack, structure, commands |
| MCP servers | `mcp-servers.md` | Custom MCP server documentation |
| Discovered standards | `[pattern-name].md` | Tribal knowledge, conventions |

**Custom skills** in `.claude/skills/`:

| Skill Type | Directory | Purpose |
|------------|-----------|---------|
| Workflows | `[workflow-name]/` | Multi-step procedures |
| Tool integrations | `[tool-name]/` | File format or API handling |
| Domain expertise | `[domain-name]/` | Specialized knowledge with references |

**Note:** Use unique names (not `plan`, `implement`, `verify`, `standards-*`) for custom skills.

Vexor index: `.vexor/` (auto-managed)

---

## Important Notes

- **Read existing rules first** — Never create duplicates or conflicts
- **All custom rules load every session** — Keep them concise
- **Don't duplicate `.claude/rules/standard/`** — Those are framework/tooling rules
- **Run `/sync` anytime** — After major changes, new patterns emerge, or periodically
