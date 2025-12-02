<div align="center">

<img src="docs/img/logo.png" alt="Claude CodePro" width="400">

### A Professional System for Building Quality Code with Claude Code (CC)

Start shipping systematically with Spec-Driven Development, Skills, TDD, Semantic Search, Persistent Memory, Context Management, Quality Hooks, Modular Rules System, and much more 🚀

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Claude Code](https://img.shields.io/badge/Claude_Code-Optimized-blue)](https://claude.ai)
![Opus 4.5](https://img.shields.io/badge/Opus_4.5-Compatible-purple.svg)
![Spec-Driven](https://img.shields.io/badge/Spec-Driven-orange.svg)
![TDD](https://img.shields.io/badge/TDD-Test--Driven--Development-green.svg)
[![PRs Welcome](https://img.shields.io/badge/PRs-Welcome-brightgreen.svg)](http://makeapullrequest.com)

#### [⭐ Star this repo](https://github.com/maxritter/claude-codepro) • [💎 Premium Features (Coming Soon!)](https://www.claude-code.pro)

</div>

---

## 🚀 Getting Started

Run this command in **any project directory** for a **fresh install** or to **update to the latest version**:

```bash
curl -fsSL https://raw.githubusercontent.com/maxritter/claude-codepro/v3.0.1/install.sh | bash
```

The installer will guide you through the setup process with interactive prompts.

**Recommended:** Install via Dev Container for complete isolation from your host system. The installer will offer to set up the dev container configuration automatically.

**Alternative:** Install directly on your host system. This may interfere with existing packages and settings, therefore it is not recommended unless you know what you're doing.

---

## 📦 What's Inside

### 📋 Spec-Driven Workflow via Slash Commands

- `/setup` - Initialize project context, semantic search indexing, and persistent memory
- `/plan` - Based on your input asks the right questions → Detailed spec with exact code
- `/implement` - Execute spec with mandatory TDD → Auto-manages context when full
- `/verify` - End-to-end spec verification → All tests, quality, security
- `/remember` - Stores learnings in cross-session memory → Continue after /clear

### 💡 Context-Loaded Rules System

- **Auto-Generated** - Regenerated on every `ccp` command from `.claude/rules/` markdown files
- **Standard Rules** - Best-Practices for TDD, Context Management, etc. loaded into `.claude/CLAUDE.md`
- **Custom Rules** - Project-specific rules (never touched by updates) loaded into `CLAUDE.local.md`
- **Commands** - Workflow-specific modes: /plan, /implement, /verify, /remember, /setup
- **Skills** - Domain-specific @-referenceable guides (e.g., @backend-python-standards)

### 🔌 Enhanced Context and Capabilities via MCP Servers

- **Cipher** - Cross-session memory for persistent knowledge and learnings stored in Vector DB
- **Claude Context** - Semantic code search for optimal codebase context retrieval
- **Exa** - AI-powered web search, code context retrieval, and URL content extraction
- **MCP Funnel** - Allows to plug-in more MCP servers as needed without wasting context

### 🛠️ Testing and Quality via Automated Tool Installation

- **Post-Edit Hooks** - Automated formatting and code checking after every edit
- **Qlty** - Automated code quality hooks for all programming languages
- **uv, ruff, mypy, basedpyright** - Python linter, formatter, and type checker (optional)
- **Newman** - API end-to-end testing with Postman collections

### 🏗️ One-Command Installation

- **Dev Container Support** - Isolated development environment with pre-configured tools and extensions
- **Automated Setup Script** - Installs and configures everything in one command
- **Global Tools** - Python tools, qlty, Claude Code, Cipher, Newman installed globally
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

- **Standard Rules** in `.claude/rules/standard/` - Updated on install, don't modify
- **Custom Rules** in `.claude/rules/custom/` - Your project-specific rules, never touched by updates
- **Auto-Build** - `ccp` regenerates `.claude/CLAUDE.md` and `.claude/CLAUDE.local.md` at startup

Add custom rules by creating `.md` files in `.claude/rules/custom/` - they'll be included automatically on next `ccp` start.

---

## 💎 Premium Features (Coming Soon!)

Take your Claude Code workflow to the next level with these powerful premium features:

### 🔍 AI Rules Supervisor

AI-powered session analysis using Gemini 3.0 Pro that checks your entire coding session against project rules. When violations are found, Claude Code is automatically instructed to fix them - ensuring full compliance before you finish.

### 🧪 Automated TDD Enforcer

Automatically enforces Test-Driven Development by blocking code edits when no failing tests exist. Ensures you always write tests first, with a smart override mechanism for edge cases.

### 📊 Intelligent Context Monitor

Automatic context management that kicks in when you reach 100% context usage. Claude CodePro automatically stores learnings in cross-session memory and updates the plan file, so you can seamlessly continue after `/clear` without losing progress.

➡️ **[Coming soon at www.claude-code.pro](https://www.claude-code.pro)**

---

## 🤝 Contributing

Contributions welcome: custom skills, MCP integrations, workflow improvements, bug reports, etc.

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
- **[postmanlabs/newman](https://github.com/postmanlabs/newman)** - End-to-End API testing
- **[astral-sh/uv](https://github.com/astral-sh/uv)** - Fast Python package manager
- **[astral-sh/ruff](https://github.com/astral-sh/ruff)** - Fast Python linter and formatter
- **[DetachHead/basedpyright](https://github.com/DetachHead/basedpyright)** - Enhanced Python type checker
- **[python/mypy](https://github.com/python/mypy)** - Static type checker for Python
- **[dotenvx/dotenvx](https://github.com/dotenvx/dotenvx)** - Automatic .env loading for Claude Code

---

Made with ❤️ by [Max Ritter](https://www.maxritter.net) and [Manuel Vogel](https://manuel-vogel.de)

[🌐 claude-code.pro](https://www.claude-code.pro)

