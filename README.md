<div align="center">

<img src="docs/img/logo.png" alt="Claude CodePro" width="400">

### 🛠️ Professional Development Environment for Claude Code (CC)

Start shipping systematically with Spec-Driven Development, Skills, TDD, LSP, Semantic Search, Persistent Memory, Context Management, Quality Hooks, Modular Rules System, and much more 🚀

[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
![Opus 4.5](https://img.shields.io/badge/Opus_4.5-Compatible-purple.svg)
[![Modular Rules](https://img.shields.io/badge/Modular_Rules-Integrated-brightgreen.svg)](https://code.claude.com/docs/en/memory#modular-rules-with-claude/rules/)
![Spec-Driven](https://img.shields.io/badge/Spec-Driven-orange.svg)
![TDD](https://img.shields.io/badge/TDD-Test--Driven--Development-green.svg)

#### [⭐ Star this repository ](https://github.com/maxritter/claude-codepro) - [🌐 Visit the website](https://claude-code.pro)

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
curl -fsSL https://raw.githubusercontent.com/maxritter/claude-codepro/v3.3.6/install.sh | bash
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

### 💡 Modular Rules System

- **Auto Loading** - Claude Code automatically loads all `.claude/rules/*.md` files as project memory
- **Standard Rules** - Best-Practices for TDD, Context Management, etc. in `.claude/rules/standard/`
- **Custom Rules** - Project-specific rules in `.claude/rules/custom/` (never touched by updates)
- **Commands** - Workflow-specific modes: /plan, /implement, /verify, /setup
- **Skills** - Domain-specific @-referenceable guides (e.g., @backend-python-standards)

### 🔌 Enhanced Context and Capabilities via MCP Servers

- **Claude Mem** - Cross-session persistent memory system that automatically ingest context
- **Claude Context** - Local vector store based semantic code search for token-efficient retrieval
- **Tavily** - Real-time web search capabilities and powerful web mapping tool
- **Ref** - AI-powered code context retrieval, similar to Context7 but uses less context
- **MCP Lazy Loading** - Intelligently reduces context usage by lazy loading MCP servers

### 🛠️ Intelligent Hooks for Quality, Standards and Context

- **Qlty Quality** - Post-edit hook for automated formatting and code checking for all languages
- **Python Quality** - Post-edit hook for uv, ruff, mypy, basedpyright linting and type checking (optional)
- **TDD Enforcer** - Pre-edit hook that warns when modifying code without failing tests first
- **Context Monitor** - Post-tool hook that warns CC automatically at 85%/95% context usage
- **Claude Memory** - Various hooks that intelligently manage Claude Memory context injection via claude-mem

### 🏗️ One-Command Installation

- **LSP Servers** - Python and TypeScript CC Language Servers for extended code intelligence
- **Dev Container Required** - Isolated Linux environment with pre-configured tools and extensions
- **Automated Setup Script** - Installs and configures everything in one command
- **Shell Integration** - Auto-configures bash, fish and zsh with `ccp` alias
- **IDE Compatible** - Works with VS Code, Cursor, Windsurf or Antigravity

---

## 📒 How-to-use

### ⚙️ Configuration

1. Open Claude Code in the IDE Terminal, Extension or an external Terminal with the `ccp` command

2. In CC, run `/config` and make sure the configuration looks similar to this screenshot
   <img src="docs/img/ide-setup-config.png" alt="Setup config Screenshot" width="600">

3. In CC, run `/ide` to connect to VS Code diagnostics and make sure all MCP servers for `/mcp` are online
   <img src="docs/img/ide-setup-mcp.png" alt="Setup mcp Screenshot" width="600">

4. In CC, run `/context` to verify context looks similar to this screenshot with rules loaded
   <img src="docs/img/ide-setup-context.png" alt="Setup context Screenshot" width="600">

### ⚠️ Important: Context Management

**Never use `/compact`** - Claude CodePro is designed to use the full 200k context window:

- **Auto-compact must be disabled** in `/config`
- **Ignore the compact warning** in the bottom right of Claude Code - it appears too early
- **Use the full context** during `/implement` sessions until context is actually full
- **When context is full**, run `/clear` to start a fresh session
- **Claude Mem auto-injects** relevant context from your previous session when you continue with `/implement`

This approach ensures maximum context utilization and seamless session continuity via persistent memory.

### 👣 First Steps

- Start with `/plan` - Provide your input and it will ask clarifying questions to create a spec
- Use `/implement` to execute the spec with automatic TDD, best practices and context management
- When context fills up, run `/clear` then continue with `/implement` mentioning your plan file
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
- **[thedotmack/claude-mem](https://github.com/thedotmack/claude-mem)** - CC Persistent Memory system
- **[zilliztech/claude-context](https://github.com/zilliztech/claude-context)** - CC Semantic code search
- **[sirmalloc/ccstatusline](https://github.com/sirmalloc/ccstatusline)** - CC Status line integration
- **[Piebald-AI/tweakcc](https://github.com/Piebald-AI/tweakcc)** - CC Customizations and tweaks for LSP
- **[tavily-ai/tavily-mcp](https://github.com/tavily-ai/tavily-mcp)** - Web search and mapping capabilities
- **[ref-tools/ref-tools-mcp](https://github.com/ref-tools/ref-tools-mcp)** - Library code context retrieval
- **[astral-sh/uv](https://github.com/astral-sh/uv)** - Fast Python package manager
- **[astral-sh/ruff](https://github.com/astral-sh/ruff)** - Fast Python linter and formatter
- **[DetachHead/basedpyright](https://github.com/DetachHead/basedpyright)** - Enhanced Python type checker
- **[dotenvx/dotenvx](https://github.com/dotenvx/dotenvx)** - Automatic .env loading for Claude Code
