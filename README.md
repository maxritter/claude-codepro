<div align="center">

<img src="docs/img/logo.png" alt="Claude CodePro" width="400">

### Production-Grade Development Environment for Claude Code

Quality automated. Context optimized. Testing enforced. Ship with confidence.</br>
A shortcut to state-of-the-art Claude Code development, continuously improved.

[![Version](https://img.shields.io/github/v/release/maxritter/claude-codepro?label=Version&color=orange)](https://github.com/maxritter/claude-codepro/releases)
[![Stars](https://img.shields.io/github/stars/maxritter/claude-codepro?style=flat&color=yellow)](https://github.com/maxritter/claude-codepro/stargazers)
[![Last Commit](https://img.shields.io/github/last-commit/maxritter/claude-codepro?color=blue)](https://github.com/maxritter/claude-codepro/commits/main)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](https://github.com/maxritter/claude-codepro/pulls)

#### ⭐ [Star this repository](https://github.com/maxritter/claude-codepro) · 🌐 [Visit the website](https://claude-code.pro) · 🔔 [Follow for updates](https://www.linkedin.com/in/rittermax/)

<br>

<img src="docs/img/demo.gif" alt="Claude CodePro Demo" width="800">

</div>

---

## ⚡ TL;DR

```bash
curl -fsSL https://raw.githubusercontent.com/maxritter/claude-codepro/v5.2.4/install.sh | bash
```

Then run `ccp` and `/sync` once to sync rules and skills. Use `/spec` or the quick mode for full quality.

---

## 📑 Table of Contents

- [Getting Started](#-getting-started)
- [What's Inside](#-whats-inside)
- [Why Claude CodePro?](#-why-claude-codepro)
- [Usage](#-usage)
- [Contributing](#-contributing)
- [License](#-license)

---

## 🚀 Getting Started

### ✅ Prerequisites

🖥️ **Platforms:** macOS, Linux, Windows (WSL2)

💳 **Claude:** [Max](https://www.anthropic.com/max), [Team](https://claude.com/pricing/team), or [Enterprise](https://www.anthropic.com/enterprise) recommended

Choose your installation method:

**Option A: 🐳 Dev Container (Recommended)**

Pre-configured, isolated environment with all tools ready. No system conflicts, consistent across machines, easy cleanup.

- **Container Runtime** - [Docker Desktop](https://www.docker.com/products/docker-desktop) or compatible equivalent
- **IDE with Dev Container Support** - Any IDE supporting the [Dev Container spec](https://containers.dev/):
  - VS Code and forks: [VS Code](https://code.visualstudio.com/), [Cursor](https://cursor.sh/), [Windsurf](https://windsurf.com/), [Antigravity](https://antigravity.google/) (with [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers))
  - JetBrains IDEs: [IntelliJ IDEA](https://www.jetbrains.com/help/idea/connect-to-devcontainer.html), WebStorm, PyCharm, GoLand, etc.
  - Cloud: [GitHub Codespaces](https://github.com/features/codespaces), [DevPod](https://devpod.sh/), [CodeSandbox](https://codesandbox.io/)

**Option B: 🍺 Local Installation**

Install directly on your system. Requires Homebrew (macOS/Linux/WSL2).

### 🔧 Installation

Run the following command in your **project folder root**:

```bash
curl -fsSL https://raw.githubusercontent.com/maxritter/claude-codepro/v5.2.4/install.sh | bash
```

You'll be asked to choose between **Dev Container** or **Local Installation**.

---

## 📦 What's Inside

### ♾️ Endless Mode

- **Seamless Continuity** - Work on complex features across multiple sessions without losing progress
- **Automatic Handoffs** - Context Monitor detects limits and continues seamlessly in new sessions
- **Persistent Memory** - Relevant observations automatically carry across all sessions
- **Works Everywhere** - Both `/spec` workflow and Quick Mode benefit from session continuity

### 📋 Spec-Driven Development

- **Planning** - Creates a detailed implementation plan for your review as markdown in `docs/plans/`
- **Approval** - You review, edit if needed, and approve the plan before implementation
- **Implementation** - Executes the plan with TDD enforcement and context management
- **Verification** - Runs tests, quality checks, and validates completion based on the plan

### 📚 Modular Rules, Commands & Skills

- **Rules** - Best practices for TDD, debugging, context management, and more
- **Commands** - `/spec` for Spec-Driven Development and `/sync` updating rules
- **Skills** - Coding standards for Python, TypeScript, Go, testing, and components
- **Customizable** - Add your own rules, commands, and skills that survive updates

### 🧠 Enhanced Context Capabilities

- **Persistent Memory** - Cross-session memory system that automatically ingests context
- **Semantic Search** - Local vector store based semantic code search for token-efficient retrieval
- **External Context** - Library docs via Context7, web search and scraping via MCP tools
- **Browser Automation** - Headless browser automation and testing even within the Dev Container

### ✅ Quality Automation

- **TDD Enforcer** - Pre-edit hook that warns when modifying code without failing tests first
- **Quality Hooks** - Language-specific hooks for Python, TypeScript and Go that auto-fix issues
- **LSP Integration** - Language servers installed for real-time diagnostics and go-to-definitions
- **Status Line** - Live display of context usage, memory status, usage limits, and license info

### 🛠️ One-Command Installer

- **Automated Container Setup** - Isolated Linux environment with pre-configured tools and extensions
- **Extended Language Support** - Optionally install extended support for Python, TypeScript & Go
- **Automated Updater** - Updates CCP to the latest version when launched over the binary
- **Shell Integration** - Auto-configures bash, fish and zsh with `ccp` alias

---

## 🔄 Why Claude CodePro?

Same task. Different results.

| Ad-hoc Prompting                 | With Claude CodePro                                   |
| -------------------------------- | ----------------------------------------------------- |
| ❌ Writes code without tests     | ✅ TDD enforced — tests first, then implementation    |
| ❌ No quality checks             | ✅ Auto-formatted, linted, type-checked on every edit |
| ❌ Inconsistent workflow         | ✅ Structured Plan → Implement → Verify cycle         |
| ❌ Context lost between sessions | ✅ Persistent memory carries observations forward     |
| ❌ No codebase awareness         | ✅ Semantic search understands your code              |
| ❌ Hope it works                 | ✅ Verified before marked complete                    |

**The result:** Production-grade code you can ship with confidence. Systematic. Tested. Verified.

---

## ⚡ Usage

### 🔄 Sync Rules & Skills

Run `/sync` to sync custom rules and skills with your codebase. Run it once initially, then anytime after major changes:

```bash
ccp
> /sync
```

### 📋 Spec-Driven Mode

Best for complex features, refactoring, or when you want to review a plan before implementation:

```bash
ccp
> /spec "Add user authentication with OAuth and JWT tokens"
```

**How it works:**

```
📋 Plan  →  ✅ Approve  →  🔨 Implement  →  🔍 Verify
                                ↑              ↓
                                └── 🔄 Loop ───┘
```

1. **📋 Plan** — Explores codebase, asks clarifying questions, writes spec to `docs/plans/`
2. **✅ Approve** — You review and edit the plan, then approve
3. **🔨 Implement** — Executes each task with TDD and quality hooks
4. **🔍 Verify** — Runs tests and checks; loops back if issues found

### 💬 Quick Mode

Just chat. No plan file, no approval gate. All quality hooks and TDD enforcement still apply.

Best for bug fixes, small improvements, and exploratory work:

```bash
ccp
> Fix the null pointer bug in user.py
```

### 📐 Rules, Commands & Skills

Claude CodePro extends Claude Code with a modular system of rules, commands, and skills:

**Managed by CCP** (updated on install):

- `.claude/commands/` - `spec` and `sync` commands are managed by CCP
- `.claude/rules/standard/` - Best practices and workflows
- `.claude/plugin/skills/` - Coding standards for languages and frameworks

**Yours to customize** (never touched by updates):

- `.claude/commands/` - Any command besides the standard ones
- `.claude/rules/custom/` - Project-specific rules
- `.claude/skills/` - Any skill besides the standards-* from CCP plugin

**When to use what:**

| Type         | Loaded                            | Best for                                |
| ------------ | --------------------------------- | --------------------------------------- |
| **Rules**    | Every session (always in context) | Guidelines Claude should always follow  |
| **Commands** | On demand via `/command`          | Specific workflows or multi-step tasks  |
| **Skills**   | Dynamically when relevant         | Specialized knowledge, coding standards |

---

## 🤝 Contributing

**Pull Requests** - New features, improvements, and bug fixes are welcome. Fun fact: CCP is built with CCP — a self-improving loop where your contributions make the tool that makes contributions better. 🔄

**Issues** - Found a bug or have a feature request? [Open an issue](https://github.com/maxritter/claude-codepro/issues).

---

## 📄 License

> **Try free for 7 days** — No signup, no credit card. Just install and go.

**Why subscribe?** Claude CodePro is actively developed with daily usage in production environments. Your subscription gives you instant access to the latest best practices, workflows, and learnings — a shortcut to state-of-the-art Claude Code development without spending weeks figuring it out yourself.

After your trial, choose the tier that fits your needs [here](https://license.claude-code.pro):

| Tier | Includes |
|:-----|:---------|
| **Standard** | All features, continuous updates with latest learnings, GitHub support |
| **Enterprise** | Standard + dedicated email support and priority feature requests |

See the [LICENSE](LICENSE) file for full terms.
