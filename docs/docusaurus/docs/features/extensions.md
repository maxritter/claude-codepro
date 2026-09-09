---
sidebar_position: 1
title: Extensions
description: Manage skills, rules, commands, and agents for both Claude Code and Codex — from a unified interface with team sharing and plugin visibility.
---

# Extensions

Extensions customize how your AI agent behaves. Pilot Shell provides a unified Console view for both **Claude Code** and **Codex CLI** extensions, across multiple scopes: **global**, **project**, **plugin** (Claude Code plugins), and **remote** (connected team git repository). Use the **Agent toggle** (All / Claude Code / Codex) to filter by agent.

## Extension Categories

| Category     | What it does                                                | Claude Code Location             | Codex Location                   |
| ------------ | ----------------------------------------------------------- | -------------------------------- | -------------------------------- |
| **Skills**   | Reusable workflows that load automatically when relevant    | `.claude/skills/<name>/SKILL.md` | `.agents/skills/<name>/SKILL.md` |
| **Rules**    | Instructions the agent follows every session                | `.claude/rules/<name>.md`        | `~/.codex/rules/<name>.rules`    |
| **Commands** | Slash commands invoked on demand via `/<name>`              | `.claude/commands/<name>.md`     | *(not available in Codex)*       |
| **Agents**   | Sub-agent definitions for specialized tasks                 | `.claude/agents/<name>.md`       | `.codex/agents/<name>.toml`      |

## Scope: Global vs Project

**Global extensions** live in `~/.claude/` and are available in every project. They're personal to you.

**Project extensions** live in `.claude/` inside a specific project directory. They're visible only when that project is active and can be committed to the repository so teammates get them automatically.

## Plugin Extensions

Installed Claude Code plugins are automatically discovered and their extensions appear on the Extensions page. Plugin extensions are **read-only** — they come from the marketplace and cannot be edited, renamed, or deleted.

- Plugins are tracked in `~/.claude/settings.json` under `enabledPlugins`
- Plugin assets live at `~/.claude/plugins/marketplaces/<marketplace>/plugins/<name>/`
- Each plugin extension shows its plugin name as a badge (e.g., "code-review", "feature-dev")
- Filter by the **Plugin** scope button to see only plugin extensions

Install plugins via the Claude Code CLI: `claude plugin install <name>`

## Codex Extensions

The Extensions page supports both Claude Code and Codex. Codex stores extensions in different locations and formats than Claude Code.

### Agent Toggle

Use the **All / Claude Code / Codex** toggle at the top of the Extensions page to filter by agent. When "All" is selected, each extension card shows a small agent badge (CC or Codex) to distinguish its source.

### Format Differences

| Format | Used by | File extension | Notes |
| --- | --- | --- | --- |
| **Markdown** | Claude Code rules/commands/agents, both agents' skills | `.md` | Full markdown editor with preview |
| **Starlark** | Codex rules | `.rules` | Sandbox permission rules in Python-like syntax |
| **TOML** | Codex agents | `.toml` | Custom agent definitions with model/instruction config |

Starlark and TOML extensions are displayed as raw source in the detail modal. All formats support editing through the text editor.

### Codex Skills

Codex skills use the same `SKILL.md` format as Claude Code skills but live in a different directory (`~/.agents/skills/` instead of `~/.claude/skills/`). They are fully editable and support all operations (rename, delete, move between scopes).

### Codex System Skills

Built-in Codex skills (skill-creator, plugin-creator, etc.) are discovered from `~/.codex/skills/.system/` and displayed as read-only items with a "Codex System" badge, similar to Claude Code plugin extensions.

### Codex Rules

Codex rules use Starlark (`.rules`) format for sandbox permission control. They are global-only — there is no project-level equivalent. See [Codex Rules](https://developers.openai.com/codex/rules) for the format specification.

### Codex Agents (Subagents)

Custom Codex agents are TOML files defining specialized subagents with model selection, instructions, and optional MCP server configuration. They exist at both global (`~/.codex/agents/`) and project (`.codex/agents/`) scope. Pilot installs `spec-review` and `changes-review` as managed global Codex agents when Codex CLI is detected. See [Codex Subagents](https://developers.openai.com/codex/subagents) for the format specification.

### Limitations

- **Commands** are a Claude Code-only concept; they do not exist in Codex

## Team Sharing (Team and Enterprise)

:::note Agent-native formats
Team sharing supports both Claude Code and Codex extensions. Claude Code files keep their existing repository paths, while Codex-native files are stored under `codex/` so Starlark rules, TOML agents, and `SKILL.md` skills do not collide with Claude Code Markdown files.
:::

Share extensions with your team through a connected git repository. Available on the Team and Enterprise plans.

### How It Works

Team sharing uses `~/.claude/` as a git repository with a scoped `.gitignore` that tracks **only** extension directories. Claude Code extensions live at the repository root (`skills/`, `rules/`, `commands/`, `agents/`); Codex extensions live under `codex/skills/`, `codex/rules/`, and `codex/agents/`. Everything else in `~/.claude/` is ignored by git.

### Connecting a Remote

1. On the Console Extensions page, find the **Team Remote** card
2. Enter a git remote URL (e.g., `https://github.com/org/team-extensions.git`)
3. Optionally specify a **subfolder** if your extensions live in a subdirectory (e.g., `plugins/myteam`)
4. Click **Connect** — Pilot initializes the git repo and verifies connectivity

Authentication uses your existing system git credentials (SSH keys or credential helpers).

### Browsing Remote Extensions

After connecting, a **Remote** scope filter button appears in the filter bar. Select it to see all extensions available in the team repository. Each remote extension shows its file path in the repository.

### Push, Pull, and Diff

- **Push to Remote** — From any local extension's detail modal, click **Push** to upload it to the team repository
- **Download from Remote** — Click any remote extension and choose **Download to Global** or **Download to Project**
- **Diff and sync** — When an extension exists both locally and remotely, click the **Remote** compare button in the detail modal. A side-by-side diff view opens with sync options: **Use Remote → Local** or **Use Local → Remote**
- **Conflict detection** — If a push would overwrite a differing remote version, Pilot shows the diff and lets you choose

### APM Format (Cross-Tool Compatibility)

Pilot Shell supports pushing extensions in [APM (Agent Package Manager)](https://microsoft.github.io/apm/introduction/key-concepts/) format, making your team remote directly installable by anyone using `apm install owner/repo` — regardless of whether they use Copilot, Claude, Cursor, or other AI coding tools.

When **APM format** is enabled, Claude Code extensions are converted on push. Codex extensions stay in their Codex-native `codex/` paths and formats.

| Pilot Shell (local)             | APM (remote)                                |
| ------------------------------- | ------------------------------------------- |
| `rules/my-rule.md`             | `instructions/my-rule.instructions.md`      |
| `commands/my-cmd.md`           | `prompts/my-cmd.prompt.md`                  |
| `agents/my-agent.md`           | `agents/my-agent.agent.md`                  |
| `skills/my-skill/SKILL.md`    | `skills/my-skill/SKILL.md` (unchanged)      |

APM-compatible [frontmatter](https://microsoft.github.io/apm/introduction/key-concepts/#instructions-instructionsmd) is automatically injected (e.g., `applyTo: "**"` for instructions, `description` for prompts and agents). An `apm.yml` manifest is generated in the remote.

**Enabling APM format:**
1. Click the edit (pencil) button next to your connected remote
2. Check the **APM format** checkbox
3. Click **Update** — Pilot migrates all existing extensions in a single commit

**Migrating back:** Uncheck APM format and update. Extensions are renamed back to native format. Content (including any frontmatter) is preserved.

**Mixed-format resilience:** During migration or partial updates, Pilot reads both formats from the remote, so no extensions become invisible.

Learn more about APM: [Getting Started](https://microsoft.github.io/apm/getting-started/first-package/), [Team Sharing](https://microsoft.github.io/apm/enterprise/teams/), [Key Concepts](https://microsoft.github.io/apm/introduction/key-concepts/).

### Sharing Memories Too

Team sharing here covers extensions. To share a project's captured **memories** - the decisions and discoveries behind the code - see [Team Memories](./team-memories.md), which stores them in the project repository instead of a dedicated remote.

### Subfolder Support

Some teams organize their extensions repository with subfolder paths (e.g., `plugins/myteam/rules/`, `plugins/myteam/skills/`, `plugins/myteam/codex/rules/`). When you specify a subfolder during connection, all browse/push/pull operations automatically translate between the subfolder-prefixed remote paths and the correct local Claude Code or Codex paths.

## Console Extensions Page

The [Pilot Console](/docs/features/console) provides a full management interface at `http://localhost:41777/#/extensions` (substitute your custom port if you've changed it via Console Settings → **Worker Port**).

### Viewing Extensions

- All extensions from all scopes appear in a unified two-column grid
- **Agent toggle** (All / Claude Code / Codex) filters extensions by agent — when "All" is active, cards show agent badges
- Each category has a distinct color: Skills (violet), Rules (amber), Commands (green), Agents (blue)
- Filter by **scope** (All / Global / Project / Plugin / Remote) and **category** (Skills, Rules, Commands, Agents)
- Search by name in the top-right search bar
- Extensions that exist in both scopes show an "also in global/project" indicator so you can spot duplicates at a glance
- Plugin extensions display the plugin name as a badge; Codex system skills show "Codex System"
- Non-markdown formats show format badges (`.rules` for Starlark, `.toml` for TOML)
- Click any extension to see its full content

### Editing Extensions

Extensions support:

- **View** — rendered preview or raw source toggle
- **Edit** — in-place markdown editor, saved directly to disk
- **Rename** — rename the file/directory
- **Delete** — with confirmation prompt
- **Move** — transfer between project and global scope (physically moves the file, not a copy)
- **Compare** — diff between project and global versions, or between local and remote versions
- **Push** — upload a local extension to the connected team remote
- **Download** — pull a remote extension to local global or project scope

Plugin extensions are read-only — edit, rename, delete, and move are not available.

### Moving Between Scopes

Clicking "→ Global" on a project extension physically moves the file from `.claude/` to your Claude config directory (`$CLAUDE_CONFIG_DIR`, else `~/.claude/`). Clicking "→ Project" moves it back. This is a move, not a copy — the original is removed.

## Creating Extensions

Create extensions manually or via workflows:

- **Rules:** `/setup-rules` (Claude Code) or `$setup-rules` (Codex) — explores your codebase and generates project-specific rules
- **Skills:** `/create-skill` or `$create-skill` — builds a reusable skill interactively from any topic
- **Automatic design expertise:** Open Claude Design supplies progressively disclosed UI creation, system extraction, review, and real Claude Design project access; Impeccable supplies refinements, supporting agents, opt-in hooks, and deterministic checks
- **Commands:** Claude Code only — create `.claude/commands/<name>.md` manually
- **Agents:** Create `.claude/agents/<name>.md` (Claude Code) or `~/.codex/agents/<name>.toml` (Codex) manually

## File Locations Reference

### Global Extensions

```
~/.claude/
├── skills/         ← global skills
├── rules/          ← global rules
├── commands/       ← global commands
└── agents/         ← global agents
```

### Project Extensions

```
<project>/
├── .claude/
│   ├── skills/          ← project skills
│   ├── rules/           ← project rules (committed to repo)
│   ├── commands/        ← project commands
│   └── agents/          ← project agents
```

### Plugin Extensions (read-only)

```
~/.claude/plugins/marketplaces/<marketplace>/plugins/<name>/
├── .claude-plugin/plugin.json   ← plugin manifest
├── skills/                      ← plugin skills
├── rules/                       ← plugin rules
├── commands/                    ← plugin commands
└── agents/                      ← plugin agents
```

### Codex Global Extensions

```text
~/.agents/
└── skills/          ← Codex user skills (SKILL.md format)

~/.codex/
├── rules/           ← Codex rules (.rules Starlark format)
├── agents/          ← Codex custom agents (.toml format)
└── skills/
    └── .system/     ← Codex system skills (read-only)
```

### Codex Project Extensions

```text
<project>/
├── .agents/
│   └── skills/      ← Codex project skills
└── .codex/
    └── agents/      ← Codex project agents
```

## See Also

- **[Customization](/docs/features/customization)** — for team-wide workflow modification. Extensions are project-scoped; customization is a git-hosted overlay that applies across every project via `pilot customize install`. It composes custom steps into core workflow skills and adds team rules, hooks, and agents. Available on Team and Enterprise plans.
