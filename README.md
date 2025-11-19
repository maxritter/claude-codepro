<div align="center">

<img src="docs/img/logo.png" alt="Claude CodePro" width="400">

### A Professional System for Building Quality Code with Claude Code (CC)

Start shipping systematically with Spec-Driven Development, Skills, TDD, Semantic Search, Persistent Memory, Context Management, Quality Hooks, Modular Rules System, and much more 🚀

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Claude Code](https://img.shields.io/badge/Claude_Code-Optimized-blue)](https://claude.ai)
![Spec-Driven](https://img.shields.io/badge/Spec-Driven-orange.svg)
![TDD](https://img.shields.io/badge/TDD-Test--Driven--Development-green.svg)
[![PRs Welcome](https://img.shields.io/badge/PRs-Welcome-brightgreen.svg)](http://makeapullrequest.com)

#### [⭐ Star this repo](https://github.com/maxritter/claude-codepro) • [🎓 Join the Academy](https://www.claude-code.pro) • [📦 Releases](https://github.com/maxritter/claude-codepro/releases)

</div>

---

## 🚀 Getting Started

Run this command in **any project directory** for a **fresh install** or to **update to the latest version**:

```bash
curl -sSL https://raw.githubusercontent.com/maxritter/claude-codepro/v2.4.7/scripts/install.py -o /tmp/claude-codepro-install.py && python3 /tmp/claude-codepro-install.py
```

The installer will guide you through the setup process with interactive prompts.

**Recommended:** Install via Dev Container for complete isolation from your host system. The installer will offer to set up the dev container configuration automatically.

**Alternative:** Install directly on your host system. This may interfere with existing packages and settings, therefore it is not recommend unless you know what to do.

---

## 📦 What's Inside

### 📋 Flexible Development Workflows via Slash Commands

**Quick Development** (For fast fixes, refactoring, experiments):

- `/quick` - Fast, focused development without spec-driven overhead → No planning required (Sonnet 4.5)

**Spec-Driven Workflow** (For complex features requiring planning and testing):

- `/plan` - Based on your input asks the right questions → Detailed spec with exact code (Opus 4.1)
- `/implement` - Execute spec with mandatory TDD → Auto-manages context when full (Sonnet 4.5)
- `/remember` - Stores learnings in cross-session memory → Continue after /clear (Sonnet 4.5)
- `/verify` - End-to-end spec verification → All tests, quality, security (Sonnet 4.5)

### 💡 Modular Rules System with Auto-Generated Commands & Skills

- **Rules Builder** - Automatically assembles commands and skills from markdown rules on every `ccp` startup
- **Core Rules** - Coding standards, TDD enforcement, error handling, validation, context management
- **Extended Rules** - Domain-specific rules auto-converted to skills, f. ex. @frontend-components
- **Workflow Rules** - Command-specific behavior for /plan, /implement, /verify, /quick, /remember
- **Flexible Customization** - Edit `.claude/rules/config.yaml` to adjust which rules apply to which commands

### 🔌 Enhanced Context and Capabilities via MCP Servers

- **Cipher** - Cross-session memory for persistent knowledge and learnings stored in Vector DB
- **Claude Context** - Semantic code search for optimal codebase context retrieval
- **Ref** - Unified documentation search, web scraping, code snippets, and library docs
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

**For Quick Changes:**

- Use `/quick` - Fast development for fixes, refactoring, or experiments without spec-driven planning
- TDD not enforced, but best practices still apply via core rules and auto-injected skills

**For Complex Features (Spec-Driven & TDD):**

- Start with `/plan` - Provide your input and it will ask clarifying questions to create a spec
- Use `/implement` to execute the spec with automatic TDD, best practices and context management
- When context fills, `/remember` automatically updates your plan and stores learnings
- After spec completion, run `/verify` to run end-to-end review, all tests, and quality checks

### 🎯 Rules Builder

The system uses a modular rules-based architecture that automatically generates slash commands and skills:

**Standard Rules** (always updated by install script):

- `.claude/rules/standard/core/` - Fundamental rules injected into all commands
- `.claude/rules/standard/workflow/` - Command-specific behavior (plan.md, implement.md, verify.md, quick.md, remember.md)
- `.claude/rules/standard/extended/` - Domain-specific rules auto-converted to individual skills

**Custom Rules** (never touched by install script):

- `.claude/rules/custom/core/` - Your custom fundamental rules
- `.claude/rules/custom/workflow/` - Your custom command behaviors
- `.claude/rules/custom/extended/` - Your custom skills (auto-converted like standard rules)

**Configuration:**

- `.claude/rules/config.yaml` - Defines which rules are included in which commands
  - `standard:` section - Lists standard rules (updated on install)
  - `custom:` section - Lists your custom rules (always preserved)

**Auto-Rebuild:** Commands and skills are automatically regenerated on every `ccp` startup, making customization seamless.

**How Updates Work:** When you run the install script, standard rules are always updated to the latest version, while custom rules and the custom sections in config.yaml are never modified. This ensures you always get the latest features while preserving your customizations.

## ⚖️ What Makes This Different

**Compared to Other Spec-Driven Frameworks (SpecKit, AgentOS, OpenSpec):**

- 📦 **One-Line Installation** - No containers, no complex setup, just one curl command
- 🤓 **Language Agnostic** - Works with Python, Node.js, Go, Rust, or any language
- 💾 **Persistent Memory** - Cross-session memory maintains knowledge between resets
- ⚡ **Token-Optimized** - No tokens wasted during too complex planning, just works
- ✅ **Production-Grade** - Actively used in client and enterprise projects
- 📝 **Enforced TDD** - Code written before tests gets deleted automatically
- 💯 **Real Verification** - Must show actual outputs based on tests, not assumptions
- 🛠️ **Complete Ecosystem** - Skills, MCP servers, testing tools are integrated and configured

---

## 👥 Who This Is For

- **Professional Developers** - Shipping to production with quality standards
- **Solo Builders** - Managing complex features without losing context
- **Engineering Teams** - Ensuring consistent TDD and code quality
- **Frustrated Coders** - Tired of half-tested, "should work" implementations

---

## 🎓 Claude CodePro Academy Coming Soon!

If you want to dive deeper into the setup and advanced usage of Claude CodePro, check out the upcoming academy that starts with 10 comprehensive modules where we do a deep-dive into all important topics:

➡️ **[www.claude-code.pro](https://www.claude-code.pro)**

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
- **[ref-tools/ref-tools-mcp](https://github.com/ref-tools/ref-tools-mcp)** - MCP Unified documentation, web scraping, and code search
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
