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

- **Container Runtime** - [Docker Desktop](https://www.docker.com/products/docker-desktop) or [OrbStack](https://orbstack.dev/) (macOS)
- **IDE** - [VS Code](https://code.visualstudio.com/), [Cursor](https://cursor.sh/), [Windsurf](https://windsurf.com/editor), or [Antigravity](https://antigravity.google/)
- **Dev Containers extension** - [Install from Marketplace](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)

> **Note:** Claude CodePro automatically runs inside a Dev Container for complete isolation, consistent tooling, and cross-platform compatibility on Windows, Mac and Linux. You can bring your own Dev Container configuration if you prefer.

### Installation

Claude CodePro can be installed into any existing project:

1. Open your project folder in your IDE
2. Run this command in the terminal:

```bash
curl -fsSL https://raw.githubusercontent.com/maxritter/claude-codepro/v4.1.5/install.sh | bash
```

3. Reopen in Container: `Cmd+Shift+P` → "Dev Containers: Reopen in Container"
4. Installation completes automatically inside the container

> **Cursor, Windsurf, Antigravity users:** These IDEs don't auto-execute `postCreateCommand`. After the container starts, run the install command from step 2 again in the container terminal IDE.

---

## 📦 What's Inside

### ♾️ Endless Mode

- **Unlimited Context** - Work on complex features across unlimited sessions automatically
- **Zero Manual Intervention** - Context Monitor detects when nearing limits and triggers seamless handoffs
- **Works Everywhere** - With `/spec` workflow or Quick Mode - both get unlimited context
- **Claude Mem Integration** - Relevant observations flow across sessions automatically

### 📋 Spec-Driven Development

- **Planning** - Creates a detailed implementation plan for your review as markdown in `docs/plans/`
- **Approval** - You review, edit if needed, and approve the plan before implementation
- **Implementation** - Executes the plan with TDD enforcement and context management
- **Verification** - Runs tests, quality checks, and validates completion based on the plan

### 💡 Modular Rules System

- **Standard Rules** - Best-Practices for TDD, Context Management, etc. in `.claude/rules/standard/`
- **Custom Rules** - Project-specific rules in `.claude/rules/custom/` (never touched by updates)
- **Command Skills** - Workflow-specific modes: `/spec`, `/setup`, `/plan`, `/implement`, `/verify`
- **Standards Skills** - Best-Practices for Frontend, Backend, Testing, etc. automatically injected

### 🔌 Enhanced Context Capabilities

- **Claude Mem** - Cross-session persistent memory system that automatically ingest context
- **Vexor** - Local vector store based semantic code search for token-efficient retrieval
- **Context7 / Firecrawl** - External context retrieval for code and web search / scraping
- **LSP Servers** - Python and TypeScript CC Language Servers for extended code intelligence

### 🛠️ Quality Hooks Automation

- **Python Quality** - Post-edit hook for ruff, mypy, basedpyright linting and type checking (optional)
- **TypeScript Quality** - Post-edit hook for eslint, tsc, prettier checks (optional)
- **General Quality** - Post-edit hook using QLTY for all languages for automated formatting and checking
- **TDD Enforcer** - Pre-edit hook that warns when modifying code without failing tests first

### 🏗️ One-Command Installer

- **Automated Container Setup** - Isolated Linux environment with pre-configured tools and extensions
- **Extended Language Support** - Optionally install extended support for Python & TypeScript
- **Automated Setup Script** - Installs and configures everything in one installation command
- **Shell Integration** - Auto-configures bash, fish and zsh with `ccp` alias

---

## ⚡ Quick Start

### 🔧 First Time Setup

Run `/setup` once to initialize project context and semantic search:

```bash
ccp
> /setup
```

This is independent of which development mode you use - both modes benefit from the initialized context.

### 🔁 Two Modes of Development

Claude CodePro supports two development modes. **Endless Mode works in both** - you get unlimited context regardless of which mode you choose.

| Mode | Command | Best For |
|------|---------|----------|
| **Spec-Driven** | `/spec "task"` | New features, major changes, complex work |
| **Quick Mode** | Just chat | Quick fixes, bug fixes, small changes |

#### 📋 Spec-Driven Mode (`/spec`)

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

#### ⏩ Quick Mode

For quick work without a spec:

```bash
ccp
> Fix the null pointer bug in user.py
> Add a loading spinner to the submit button
```

Just describe what you need - no plan file, no approval gate. Claude CodePro still provides all the quality hooks, TDD enforcement, and context capabilities. Perfect for bug fixes, small improvements, and exploratory work.

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

### ♾️ Endless Mode

Both `/spec` and Quick Mode use the full 200K context window with automatic management via Endless Mode:

- **Automatic handoffs** - When context nears the limit, state is saved and work continues in a new session
- **Claude Mem preserves understanding** - Relevant observations flow across sessions
- **Auto-compact disabled** - Installation disables auto-compact, giving you 20% more usable context

---

## 📜 License

Claude CodePro is dual-licensed:

### Open Source (AGPL-3.0)

Free for:
- **Individuals** - Personal projects and learning
- **Freelancers** - Client work and consulting
- **Open Source Projects** - Projects that release source under AGPL-3.0

### Commercial License

**Companies using Claude CodePro in proprietary/closed-source products must obtain a commercial license.**

This applies to:
- Companies with closed-source software
- Internal tools at companies that don't want to open-source
- SaaS products using Claude CodePro

**Contact:** [mail@maxritter.net](mailto:mail@maxritter.net) for commercial licensing inquiries.

---

## 🤝 Contributing

**Pull Requests are welcome!** If you have new features, improvements, or bug fixes, feel free to open a PR.

**Note:** Issues are disabled. This project evolves alongside my professional work as a freelancer, and I don't have the capacity to maintain a public issue tracker. If you want a feature or find a bug, the best way to contribute is to submit a PR.

---

## 💼 Professional Services

I'm **Max Ritter**, a senior IT freelancer based near **Munich, Germany**, specializing in:

- **AWS Cloud** - Cloud Infrastructure, Architecture & Development
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
| ✉️ **Email** | [mail@maxritter.net](mailto:mail@maxritter.net) |
| 💼 **LinkedIn** | [linkedin.com/in/rittermax](https://www.linkedin.com/in/rittermax/) |
| 📄 **CV** | [flowcv.com/resume/hcaa0q4wdd](https://flowcv.com/resume/hcaa0q4wdd) |
| 📝 **Blog** | [blog.maxritter.net](http://blog.maxritter.net/) |
| 🌐 **Website** | [maxritter.net](https://maxritter.net) |

---

## 🙏 Acknowledgments

- **[thedotmack/claude-mem](https://github.com/thedotmack/claude-mem)** - CC Persistent Memory system
- **[sirmalloc/ccstatusline](https://github.com/sirmalloc/ccstatusline)** - CC Status line integration
- **[scarletkc/vexor](https://github.com/scarletkc/vexor)** - CC Semantic code search
- **[ManuelKugelmann/BitBot](https://github.com/ManuelKugelmann/BitBot)** - CC Wrapper control inspirations
- **[upstash/context7](https://github.com/upstash/context7)** - Library code context retrieval
- **[firecrawl/firecrawl](https://github.com/firecrawl/firecrawl)** - Web search and scraping tool
- **[astral-sh/uv](https://github.com/astral-sh/uv)** - Fast Python package manager
- **[astral-sh/ruff](https://github.com/astral-sh/ruff)** - Fast Python linter and formatter
- **[qltysh/qlty](https://github.com/qltysh/qlty)** - Code quality automation
- **[DetachHead/basedpyright](https://github.com/DetachHead/basedpyright)** - Enhanced Python type checker
- **[dotenvx/dotenvx](https://github.com/dotenvx/dotenvx)** - Automatic .env loading for Claude Code
