<div align="center">

<img src="docs/img/logo.png" alt="Claude CodePro" width="400">

### Professional Development Environment for Claude Code (CC)

Start shipping systematically with Endless Mode, Spec-Driven Development, Skills, TDD, LSP, Semantic Search, Persistent Memory, Quality Hooks, Modular Rules System, and much more 🚀


[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
![Opus 4.5](https://img.shields.io/badge/Opus_4.5-Compatible-purple.svg)
![Endless Mode](https://img.shields.io/badge/Endless-Mode-red.svg)
![Spec-Driven](https://img.shields.io/badge/Spec-Driven-yellow.svg)
![TDD](https://img.shields.io/badge/TDD-Enforcement-green.svg)

#### ⭐ [Star this repository](https://github.com/maxritter/claude-codepro) · 🌐 [Visit the website](https://claude-code.pro) · 💼 [Follow for updates](https://www.linkedin.com/in/rittermax/) · ✉️ [Get in touch](mailto:mail@maxritter.net)

</div>

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
curl -fsSL https://raw.githubusercontent.com/maxritter/claude-codepro/v4.4.5/install.sh | bash
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
- **Automated Setup Script** - Installs and configures everything in one installation command
- **Shell Integration** - Auto-configures bash, fish and zsh with `ccp` alias

---

## ⚡ Quick Start

### First Time Setup

Run `/setup` once to initialize project context and semantic search:

```bash
ccp
> /setup
```

This is independent of which development mode you use - both modes benefit from the initialized context.

### Two Modes of Development

Claude CodePro supports two development modes. **Endless Mode works in both** - you get unlimited context regardless of which mode you choose.

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

**Pull Requests are welcome!** If you have new features, improvements, or bug fixes, feel free to open a PR.

**Note:** Issues are disabled. This project evolves alongside my professional work as a freelancer, and I don't have the capacity to maintain a public issue tracker. If you want a feature or find a bug, the best way to contribute is to submit a PR.

---

## 💼 Professional Services

I'm **Max Ritter**, a senior IT freelancer based near **Munich, Germany**, specializing in:

- **AWS Cloud** - Cloud Infrastructure, Architecture & Development on AWS
- **Data Engineering** - Data Pipelines, ETL, Analytics Infrastructure
- **Artificial Intelligence** - LLM Integration, AI-Assisted Development, Agents
- **DevOps** - CI/CD, Infrastructure as Code, Automation

### Paid Services Available

| Service | Description |
|---------|-------------|
| **Custom Development** | Claude CodePro doesn't work in your setup? Containerized environment issues? Specific software restrictions? I can customize it for your needs. |
| **Enterprise Integration** | Need Claude CodePro integrated into your company's existing toolchain and workflows? |
| **Consulting** | General DevOps, Data Engineering, or AI consulting for your projects |

### Contact & Connect

| | |
|---|---|
| **Email** | [mail@maxritter.net](mailto:mail@maxritter.net) |
| **LinkedIn** | [linkedin.com/in/rittermax](https://www.linkedin.com/in/rittermax/) |
| **Blog** | [blog.maxritter.net](http://blog.maxritter.net/) |
| **Website** | [maxritter.net](https://maxritter.net) |

---

## 🙏 Acknowledgments

- **[thedotmack/claude-mem](https://github.com/thedotmack/claude-mem)** - CC Persistent Memory system
- **[sirmalloc/ccstatusline](https://github.com/sirmalloc/ccstatusline)** - CC Status line integration
- **[scarletkc/vexor](https://github.com/scarletkc/vexor)** - CC Semantic code search capabilities
- **[philschmid/mcp-cli](https://github.com/philschmid/mcp-cli)** - CC MCP Servers lazy loading
- **[vercel-labs/agent-browser](https://github.com/vercel-labs/agent-browser)** - Headless browser automation CLI
- **[ManuelKugelmann/BitBot](https://github.com/ManuelKugelmann/BitBot)** - CC Wrapper control inspirations
- **[upstash/context7](https://github.com/upstash/context7)** - Library code context retrieval
- **[firecrawl/firecrawl](https://github.com/firecrawl/firecrawl)** - Web search and scraping tool
- **[astral-sh/uv](https://github.com/astral-sh/uv)** - Fast Python package manager
- **[astral-sh/ruff](https://github.com/astral-sh/ruff)** - Fast Python linter and formatter
- **[qltysh/qlty](https://github.com/qltysh/qlty)** - Code quality automation
- **[DetachHead/basedpyright](https://github.com/DetachHead/basedpyright)** - Enhanced Python type checker
- **[dotenvx/dotenvx](https://github.com/dotenvx/dotenvx)** - Automatic .env loading for Claude Code

