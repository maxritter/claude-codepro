<div align="center">

<img src="docs/img/logo.png" alt="Claude CodePro" width="400">

### Professional Development Environment for Claude Code (CC)

Start shipping systematically with Endless Mode, Spec-Driven Development, Skills, TDD, LSP, Semantic Search, Persistent Memory, Quality Hooks, Modular Rules System, and much more 🚀

[![Version](https://img.shields.io/github/v/release/maxritter/claude-codepro?label=Version&color=orange)](https://github.com/maxritter/claude-codepro/releases)
![Endless Mode](https://img.shields.io/badge/Endless-Mode-red.svg)
![Spec-Driven](https://img.shields.io/badge/Spec-Driven-yellow.svg)
![TDD](https://img.shields.io/badge/TDD-Enforcement-green.svg)
![License](https://img.shields.io/badge/License-AGPL--3.0%20%2F%20Commercial-blue.svg)

#### ⭐ [Star this repository](https://github.com/maxritter/claude-codepro) · 🌐 [Visit the website](https://claude-code.pro) · 💼 [Follow for updates](https://www.linkedin.com/in/rittermax/) · ✉️ [Get in touch](mailto:mail@maxritter.net)

</div>

---

## 📑 Table of Contents

- [Getting Started](#-getting-started)
- [What's Inside](#-whats-inside)
- [Usage](#-usage)
- [Contributing](#-contributing)
- [License](#-license)
- [Acknowledgments](#-acknowledgments)

---

## 🚀 Getting Started

### Prerequisites

Choose your installation method:

**Option A: Dev Container (Recommended - All Platforms)**
- **Container Runtime** - [Docker Desktop](https://www.docker.com/products/docker-desktop) or compatible equivalent
- **IDE** - [VS Code](https://code.visualstudio.com/) or compatible IDE with Dev Container support
- **Dev Containers extension** - [Install from Marketplace](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)
- Works on **macOS**, **Linux**, and **Windows (with WSL2)**

**Option B: Local Installation (macOS/Linux)**
- **macOS or Linux** - Homebrew-compatible system
- **Homebrew** - Installed automatically if not present

### Installation

Run the following command in your **project folder root**:

```bash
curl -fsSL https://raw.githubusercontent.com/maxritter/claude-codepro/v4.5.22/install.sh | bash
```

You'll be asked to choose between **Dev Container** or **Local Installation**.

#### Dev Container Installation

1. Choose "Dev Container" when prompted
2. Reopen in Container: `Cmd+Shift+P` → "Dev Containers: Reopen in Container"
3. Dev Container installation completes automatically inside the container
4. Run the installation command again in the container terminal to finish CCP setup
5. Follow the post-setup instructions and run `ccp` to start Claude CodePro

#### Local Installation (macOS/Linux)

1. Choose "Local Installation" when prompted
2. Confirm the installation (Homebrew packages, shell config, Claude Code config)
3. Wait for installation to finish then follow the post-setup instructions
4. Reload your shell: `source ~/.zshrc` (or `~/.bashrc`)
5. Run `ccp` to start Claude CodePro

### Claude Subscription

Claude CodePro is designed to be token-efficient, but quality has its cost. For the best experience, use:

- **Claude Max 5x** — For individual developers with moderate usage
- **Claude Max 20x** — For heavy usage or professional development
- **Enterprise Plan** — For teams and organizations

---

## 📦 What's Inside

### Endless Mode

- **Works Everywhere** - With `/spec` workflow or Quick Mode - both get unlimited context
- **Unlimited Context** - Work on complex features across unlimited sessions automatically
- **Zero Manual Intervention** - Context Monitor detects when nearing limits and triggers seamless handoffs
- **Claude Mem Integration** - Relevant observations flow across sessions automatically

### Spec-Driven Development

- **Planning** - Creates a detailed implementation plan for your review as markdown in `docs/plans/`
- **Approval** - You review, edit if needed, and approve the plan before implementation
- **Implementation** - Executes the plan with TDD enforcement and context management
- **Verification** - Runs tests, quality checks, and validates completion based on the plan
- **Feedback Loop** - If verification finds issues, automatically loops back to fix and re-verify

### Modular Rules System

- **Standard Rules** - Best-Practices for TDD, Context Management, etc. in `.claude/rules/standard/`
- **Custom Rules** - Project-specific rules in `.claude/rules/custom/` (never touched by updates)
- **Command Skills** - Workflow-specific modes: `/spec`, `/setup`, `/plan`, `/implement`, `/verify`
- **Standards Skills** - Best-Practices for Frontend, Backend, Testing, etc. automatically injected

### Enhanced Context Capabilities

- **Claude Mem** - Cross-session persistent memory system that automatically ingest context
- **Vexor** - Local vector store based semantic code search for token-efficient retrieval
- **Context7 / Firecrawl** - External context retrieval for code and web search / scraping
- **agent-browser** - Headless browser automation and testing within the Dev Container

### Quality Hooks Automation

- **Python Quality** - Post-edit hook for ruff, basedpyright and Python LSP server (optional)
- **TypeScript Quality** - Post-edit hook for eslint, tsc, prettier and TypeScript LSP server (optional)
- **General Quality** - Post-edit hook using QLTY for all languages for automated formatting and checking
- **TDD Enforcer** - Pre-edit hook that warns when modifying code without failing tests first

### One-Command Installer

- **Automated Container Setup** - Isolated Linux environment with pre-configured tools and extensions
- **Extended Language Support** - Optionally install extended support for Python & TypeScript
- **Automated Updater** - Updates CCP to the latest version when launched over the binary
- **Shell Integration** - Auto-configures bash, fish and zsh with `ccp` alias

---

## ⚡ Usage

### First Time Setup

Run `/setup` once to initialize project context and semantic search:

```bash
ccp
> /setup
```

This is independent of which development mode you use - both modes benefit from the initialized context.

### Two Modes of Development

Claude CodePro supports two development modes:

| Mode | Command | Best For |
|------|---------|----------|
| **Spec-Driven** | `/spec "task"` | New features, major changes, complex work |
| **Quick Mode** | Just chat | Quick fixes, bug fixes, small changes |

#### Spec-Driven Mode (`/spec`)

For structured development with planning and verification:

```bash
ccp
> /spec "Describe your feature as detailed as possible"
```

**The workflow:**
1. **Plan** - Explores codebase, asks questions, generates detailed spec in `docs/plans/`
2. **Approve** - You review, edit if needed, and approve the plan
3. **Implement** - Executes tasks with TDD enforcement and quality hooks
4. **Verify** - Runs tests, quality checks, validates completion

Use this mode when you want a spec to review before implementation, or when the task is complex enough to benefit from structured planning.

#### Quick Mode

For quick work without a spec:

```bash
ccp
> Fix the null pointer bug in user.py
> Add a loading spinner to the submit button
```

Just describe what you need - no plan file, no approval gate. Claude CodePro still provides all the quality hooks, TDD enforcement, and context capabilities. Perfect for bug fixes, small improvements, and exploratory work.

### Customizing Rules

Claude CodePro uses [Claude Code's modular rules](https://code.claude.com/docs/en/memory#modular-rules-with-claude/rules/):

- **Standard Rules** in `.claude/rules/standard/` - Best-Practices updated on install, don't modify those
- **Custom Rules** in `.claude/rules/custom/` - Your project-specific rules, never touched by updates

---

## 🤝 Contributing

**Pull Requests** - New features, improvements, and bug fixes are welcome. Open a PR to contribute.

**Issues** - Found a bug or have a feature request? [Open an issue](https://github.com/maxritter/claude-codepro/issues).

---

## 📄 License

This project is dual-licensed. See the [LICENSE](LICENSE) file for details.

**Free (AGPL-3.0)** - Personal use, students, educators, nonprofits, and open source projects.

**Commercial License** - For proprietary or closed-source projects, [purchase a license](https://license.claude-code.pro).

---

## 🙏 Acknowledgments

- **[thedotmack/claude-mem](https://github.com/thedotmack/claude-mem)** - CC Persistent Memory system
- **[sirmalloc/ccstatusline](https://github.com/sirmalloc/ccstatusline)** - CC Status line integration
- **[scarletkc/vexor](https://github.com/scarletkc/vexor)** - CC Semantic code search capabilities
- **[philschmid/mcp-cli](https://github.com/philschmid/mcp-cli)** - CC MCP Servers lazy loading
- **[vercel-labs/agent-browser](https://github.com/vercel-labs/agent-browser)** - Headless browser automation CLI
- **[upstash/context7](https://github.com/upstash/context7)** - Library code context retrieval
- **[firecrawl/firecrawl](https://github.com/firecrawl/firecrawl)** - Web search and scraping tool
- **[astral-sh/uv](https://github.com/astral-sh/uv)** - Fast Python package manager
- **[astral-sh/ruff](https://github.com/astral-sh/ruff)** - Fast Python linter and formatter
- **[qltysh/qlty](https://github.com/qltysh/qlty)** - Code quality automation
- **[DetachHead/basedpyright](https://github.com/DetachHead/basedpyright)** - Enhanced Python type checker

