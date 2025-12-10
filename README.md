<div align="center">

<img src="docs/img/logo.png" alt="Claude CodePro" width="400">

### 🛠️ Professional Development Environment for Claude Code (CC)

Start shipping systematically with Spec-Driven Development, Skills, TDD, Semantic Search, Persistent Memory, Context Management, Quality Hooks, Modular Rules System, and much more 🚀

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Claude Code](https://img.shields.io/badge/Claude_Code-Optimized-blue)](https://claude.ai)
[![Modular Rules](https://img.shields.io/badge/Modular_Rules-Integrated-brightgreen.svg)](https://code.claude.com/docs/en/memory#modular-rules-with-claude/rules/)
![Opus 4.5](https://img.shields.io/badge/Opus_4.5-Compatible-purple.svg)
![Spec-Driven](https://img.shields.io/badge/Spec-Driven-orange.svg)
![TDD](https://img.shields.io/badge/TDD-Test--Driven--Development-green.svg)

#### [⭐ Star this repo](https://github.com/maxritter/claude-codepro)

</div>

---

## 🚀 Getting Started

### Prerequisites

- **Container Runtime** - [Docker Desktop](https://www.docker.com/products/docker-desktop) or [OrbStack](https://orbstack.dev/) (macOS)
- **IDE** - [VS Code](https://code.visualstudio.com/), [Cursor](https://cursor.sh/), [Windsurf](https://windsurf.com/editor), or [Antigravity](https://antigravity.google/)
- **Dev Containers extension** - [Install from Marketplace](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)

> **Note:** Claude CodePro runs inside a Dev Container for complete isolation, consistent tooling, and cross-platform compatibility.

### Installation

Claude CodePro can be installed into any existing project:

1. Open your project folder in your IDE
2. Run this command in the terminal:

```bash
curl -fsSL https://raw.githubusercontent.com/maxritter/claude-codepro/v3.1.1/install.sh | bash
```

3. Reopen in Container: `Cmd+Shift+P` → "Dev Containers: Reopen in Container"
4. Installation completes automatically inside the container

> **Cursor, Windsurf, Antigravity users:** These IDEs don't auto-execute `postCreateCommand`. After the container starts, run the install command from step 2 again.

---

## 📦 What's Inside

### 📋 Spec-Driven Workflow via Slash Commands

- `/setup` - Initialize project context, semantic search indexing, and persistent memory
- `/plan` - Based on your input asks the right questions → Detailed spec with exact code
- `/implement` - Execute spec with mandatory TDD → Auto-manages context when full
- `/verify` - End-to-end spec verification → All tests, quality, security
- `/remember` - Stores learnings in cross-session memory → Continue after /clear

### 💡 Modular Rules System

Built on [Claude Code's modular rules](https://code.claude.com/docs/en/memory#modular-rules-with-claude/rules/) - rules are loaded automatically as project memory.

- **Auto Loading** - Claude Code automatically loads all `.claude/rules/*.md` files as project memory
- **Standard Rules** - Best-Practices for TDD, Context Management, etc. in `.claude/rules/standard/`
- **Custom Rules** - Project-specific rules in `.claude/rules/custom/` (never touched by updates)
- **Commands** - Workflow-specific modes: /plan, /implement, /verify, /remember, /setup
- **Skills** - Domain-specific @-referenceable guides (e.g., @backend-python-standards)

### 🔌 Enhanced Context and Capabilities via MCP Servers

- **Cipher** - Cross-session memory for persistent knowledge and learnings stored in Vector DB
- **Claude Context** - Semantic code search for optimal codebase context retrieval
- **Exa** - AI-powered web search, code context retrieval, and URL content extraction
- **MCP Funnel** - Allows to plug-in more MCP servers as needed without wasting context

### 🛠️ Intelligent Hooks for Quality, Standards and Context

- **Qlty Quality** - Post-edit hook for automated formatting and code checking for all languages
- **Python Quality** - Post-edit hook for uv, ruff, mypy, basedpyright linting and type checking (optional)
- **Rules Supervisor** - Stop hook that analyzes `/implement` sessions using Gemini AI
- **TDD Enforcer** - Pre-edit hook that warns when modifying code without failing tests first
- **Context Monitor** - Post-tool hook that warns at 85%/95% context usage

### 🏗️ One-Command Installation

- **Global Tools** - Python tools, qlty, Claude Code, dotenvx installed globally
- **Dev Container Required** - Isolated Linux environment with pre-configured tools and extensions
- **Automated Setup Script** - Installs and configures everything in one command
- **Shell Integration** - Auto-configures bash and zsh with `ccp` alias
- **IDE Compatible** - Works with VS Code, Cursor, Windsurf or Antigravity

---

## 📒 How-to-use

### ⚙️ Configuration

1. Open Claude Code in the IDE Terminal, Extension or an external Terminal with the `ccp` command

2. In CC, run `/config` to set `Auto-connect to IDE=true` and set `Auto-compact=false` for best experience
   <img src="docs/img/ide-setup-config.png" alt="Setup config Screenshot" width="600">

3. In CC, run `/ide` to connect to VS Code diagnostics and make sure all MCP servers for `/mcp` are online
   <img src="docs/img/ide-setup-mcp.png" alt="Setup mcp Screenshot" width="600">

4. In CC, run `/context` to verify context looks similar to this screenshot with less than 20% used
   <img src="docs/img/ide-setup-context.png" alt="Setup context Screenshot" width="600">

### 👣 First Steps

- Start with `/plan` - Provide your input and it will ask clarifying questions to create a spec
- Use `/implement` to execute the spec with automatic TDD, best practices and context management
- When context fills, `/remember` automatically updates your plan and stores learnings
- After spec completion, run `/verify` to run end-to-end review, all tests, and quality checks

### 🎯 Customizing Rules

Claude CodePro uses [Claude Code's modular rules](https://code.claude.com/docs/en/memory#modular-rules-with-claude/rules/):

- **Standard Rules** in `.claude/rules/standard/` - Updated on install, don't modify
- **Custom Rules** in `.claude/rules/custom/` - Your project-specific rules, never touched by updates
- **Path-Specific Rules** - Use YAML frontmatter with `paths:` to scope rules to specific files

Add custom rules by creating `.md` files in `.claude/rules/custom/`. You can also use path-specific rules:

```yaml
---
paths: src/**/*.py
---
# Python-specific rules for this project
```

---

## 🙏 Acknowledgments

- **[qltysh/qlty](https://github.com/qltysh/qlty)** - Code quality automation
- **[obra/superpowers](https://github.com/obra/superpowers)** - CC Skills inspiration
- **[buildermethods/agent-os](https://github.com/buildermethods/agent-os)** - CC Spec-Driven inspiration
- **[campfirein/cipher](https://github.com/campfirein/cipher)** - CC Cross-session memory
- **[zilliztech/claude-context](https://github.com/zilliztech/claude-context)** - CC Semantic code search
- **[sirmalloc/ccstatusline](https://github.com/sirmalloc/ccstatusline)** - CC Status line integration
- **[exa-labs/exa-mcp-server](https://github.com/exa-labs/exa-mcp-server)** - AI-powered web search and code context
- **[chris-schra/mcp-funnel](https://github.com/chris-schra/mcp-funnel)** - MCP Tool filtering
- **[astral-sh/uv](https://github.com/astral-sh/uv)** - Fast Python package manager
- **[astral-sh/ruff](https://github.com/astral-sh/ruff)** - Fast Python linter and formatter
- **[DetachHead/basedpyright](https://github.com/DetachHead/basedpyright)** - Enhanced Python type checker
- **[python/mypy](https://github.com/python/mypy)** - Static type checker for Python
- **[dotenvx/dotenvx](https://github.com/dotenvx/dotenvx)** - Automatic .env loading for Claude Code
