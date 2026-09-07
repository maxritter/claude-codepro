<div align="center">

<img src="docs/img/logo.png" alt="Pilot Shell" width="400">

### How real engineers run Claude Code and Codex

Professional context and harness engineering around the coding agents you already use.</br>
**Persistent knowledge. Enforced quality. Runtime proof.**

[![Stars](https://img.shields.io/github/stars/maxritter/pilot-shell?style=flat&color=F59E0B)](https://github.com/maxritter/pilot-shell)
[![Star History](https://img.shields.io/badge/Star_History-chart-8B5CF6)](https://star-history.com/#maxritter/pilot-shell&Date)
[![Downloads](https://img.shields.io/github/downloads/maxritter/pilot-shell/total?color=3B82F6)](https://github.com/maxritter/pilot-shell/releases)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-10B981.svg)](https://github.com/maxritter/pilot-shell/pulls)

<p>
  <a href="#install">Install</a> •
  <a href="#features">Features</a> •
  <a href="https://pilot-shell.com/docs">Docs</a> •
  <a href="https://pilot-shell.com/blog">Blog</a> •
  <a href="https://pilot-shell.com">Website</a> •
  <a href="https://github.com/maxritter/pilot-shell/releases">Changelog</a>
</p>

```bash
curl -fsSL https://raw.githubusercontent.com/maxritter/pilot-shell/main/install.sh | bash
```

**macOS · Linux · Windows (WSL2)** — installs in under 2 minutes.

<br>

<img src="docs/img/demo.gif" alt="Pilot Shell Demo" width="700">

</div>

---

> [!TIP]
> **Pilot's open design companion:** [Open Claude Design](https://github.com/maxritter/open-claude-design) connects Claude Design to the coding agent you already use, with codebase-grounded creation and conflict-aware synchronization. Pilot installs it together with [Impeccable](https://github.com/pbakaus/impeccable), so product context, visual iteration, deterministic checks, and engineering verification work as one design layer.

---

## Why Pilot Shell

**Claude Code and Codex CLI write code fast** — but production-grade software still needs durable context, disciplined implementation, quality control, and proof that the finished system works.

**Pilot Shell is a professional context and harness engineering system—not a collection of rules and skills.** It coordinates the complete engineering process around the model:

- **Quality on every layer** — hooks, stop guards, independent reviews, full test/build gates, and browser or device verification prevent “looks done” handoffs
- **Persistent context** — relevant source, architecture, project standards, prior decisions, and session state survive long work and compaction, with useful findings remembered automatically across Claude Code and Codex
- **Professional toolchain** — Semble, CodeGraph, ast-grep, RTK, language servers, browser automation, and MCP integrations support discovery, structural search, impact analysis, implementation, and runtime proof
- **Runtime verification** — tests, builds, real CLI/API execution, browser automation, and device checks turn completion claims into evidence
- **Human control plane** — the Console connects plan and diff review, annotations, progress, evidence, session recovery, shared project knowledge, and usage
- **Workflow neutrality** — direct requests, native Plan/Goal tools, and Pilot workflows are peer ways to work inside the same harness
- **Structured delivery when wanted** — `/spec`, `/build`, `/fix`, and `/prd` add durable artifacts and explicit lifecycle contracts without becoming routing rules for ordinary requests
- **One system for Claude Code and Codex** — platform-specific adapters preserve one engineering standard while the underlying models continue to improve

Rules, skills, and persistent memory are coordinated parts of this harness. They supply context; they are not the product by themselves. For a longer practitioner’s explanation, read [How to build production-ready software assisted with AI tools](https://vogel-johnson.com/blog/2026-07-21-ai-assisted-production-ready-code).

---

<h2 id="install">Getting Started</h2>

### Prerequisites

**At least one AI agent:** Pilot Shell supports **Claude Code** (primary — full feature coverage) and **Codex** through Codex CLI or the ChatGPT desktop app (all workflows, fewer platform features). Install at least one before running the Pilot installer:

- **Claude Code:** Install via the [native installer](https://code.claude.com/docs/en/quickstart). If you have the `npm` or `brew` version, uninstall it first. Requires a Claude subscription — [Max 5x or 20x](https://claude.com/pricing) for solo, [Team Premium](https://claude.com/pricing) for teams, [Enterprise](https://claude.com/pricing) for organizations.
- **Codex:** Install [Codex CLI](https://developers.openai.com/codex/cli) or the ChatGPT desktop app. Pilot detects the CLI and the Codex binary bundled with ChatGPT on macOS. Requires an OpenAI subscription — [Plus or Pro](https://developers.openai.com/codex/pricing) for solo, [Business or Enterprise](https://developers.openai.com/codex/pricing) for teams.

**Terminal (Recommended on macOS):** [Zentty](https://zentty.org/) works especially well with Pilot Shell — its worklanes keep parallel agents and dev servers in separate contexts and show you when a pane needs attention. Any modern terminal works: [Ghostty](https://ghostty.org/), [iTerm2](https://iterm2.com/), or the built-in macOS/Linux terminal.

### Installation

**Works with any existing project.** Pilot Shell integrates with **Claude Code** and **Codex CLI or ChatGPT desktop**, using their built-in concepts (rules, hooks, skills, subagents, MCP) to improve your experience:

```bash
curl -fsSL https://raw.githubusercontent.com/maxritter/pilot-shell/main/install.sh | bash
```

Installs globally on macOS, Linux, and Windows (WSL2). After installation, run `claude` or `codex` directly. On macOS, you can instead restart ChatGPT desktop and open the project there. Pilot Shell loads automatically in either Codex client. Run `pilot update` to check for updates.

<details>
<summary><b>Downgrade</b></summary>

If you encounter an issue or unfixed bug in the latest version, you can always go back to a previous version (see [releases](https://github.com/maxritter/pilot-shell/releases)):

```bash
export VERSION=11.0.0
curl -fsSL https://raw.githubusercontent.com/maxritter/pilot-shell/main/install.sh | bash
```
</details>

<details>
<summary><b>Uninstalling</b></summary>

Removes Pilot's runtime, Console, statusline, hooks, managed skills/rules/agents, MCP entries, settings injections, and shell aliases. Claude Code, Codex, project files, shared external tools, and user data are preserved:

```bash
curl -fsSL https://raw.githubusercontent.com/maxritter/pilot-shell/main/uninstall.sh | bash
```

The interactive uninstaller asks separately whether to remove proven Pilot-owned external tools and whether to purge Pilot data, then shows the final removal preview. The prompts use the controlling terminal, so they also work with the piped command above.

Optional cleanup stays explicit:

```bash
# Also remove external tools that Pilot recorded as originally Pilot-installed
curl -fsSL https://raw.githubusercontent.com/maxritter/pilot-shell/main/uninstall.sh | bash -s -- --remove-tools

# Also delete Pilot memories, sessions, logs, configuration, and unknown files
curl -fsSL https://raw.githubusercontent.com/maxritter/pilot-shell/main/uninstall.sh | bash -s -- --purge-data
```
</details>

<details>
<summary><b>Reset & Refresh</b></summary>

Over time, accumulated session logs and Pilot Shell's caches can slow things down. A periodic reset gives you a clean baseline:

```bash
# 1. If using Claude Code, log out first
/logout

# 2. Back up your current config (just in case)
# Using CLAUDE_CONFIG_DIR? Substitute it for ~/.claude, and back up
# "$CLAUDE_CONFIG_DIR/.claude.json" instead of ~/.claude.json.
mv ~/.claude.json ~/.claude.json.bak
mv ~/.claude       ~/.claude.bak
mv ~/.codex        ~/.codex.bak
mv ~/.pilot        ~/.pilot.bak

# 3. Reinstall Pilot Shell from the official installer
curl -fsSL https://raw.githubusercontent.com/maxritter/pilot-shell/main/install.sh | bash

# 4. Re-activate your license, then start your agent
pilot activate <your-license-key>
claude   # or: codex
```

Once Pilot Shell is running smoothly again, you can delete the `.bak` copies. Forgot your license key? Recover it in the [Pilot members area](https://polar.sh/max-ritter/portal).
</details>

<details>
<summary><b>Using a Dev Container</b></summary>

Pilot Shell works inside Dev Containers. Copy the [`.devcontainer`](https://github.com/maxritter/pilot-shell/tree/main/.devcontainer) folder from this repository into your project, adapt it to your needs (base image, extensions, dependencies), and run the installer inside the container. The installer auto-detects the container environment and skips system-level dependencies like Homebrew.

For tighter isolation when working with untrusted code, combine the dev container with Claude Code's [`/sandbox`](https://code.claude.com/docs/en/sandboxing) — `bubblewrap`, `socat`, `iptables`, and `ipset` are pre-installed in the Dockerfile so it works out of the box on Linux. See Anthropic's [development containers](https://code.claude.com/docs/en/devcontainer) and [sandboxing](https://code.claude.com/docs/en/sandboxing) docs for hardening patterns (egress allowlist, managed settings, persistent volumes).

</details>

<details>
<summary><b>What the installer does</b></summary>

8-step installer with progress tracking, rollback on failure, and idempotent re-runs. Steps 3 and 4 are agent-conditional — they skip cleanly when the matching agent is not detected. The installer **does not install Claude Code, Codex CLI, or ChatGPT itself**; install at least one yourself per the prerequisites above.

1. **Prerequisites** — Checks/installs Homebrew, Node.js, Python 3.12+, uv, git, jq. Verifies at least one supported agent (Claude Code, Codex CLI, or the Codex binary bundled with ChatGPT on macOS) is on the system; aborts with a clear error otherwise.
2. **Pilot files** — Agent-neutral Pilot Shell-managed assets. Hooks → `~/.pilot/hooks/`, Console scripts/UI → `~/.pilot/`, MCP server template → `~/.pilot/.mcp.json`, canonical raw sources → `~/.pilot/rules/`, `~/.pilot/skills/`, and `~/.pilot/agents/`. Each agent's adapter consumes these sources in its own format. Always runs.
3. **Claude files** — Claude-specific assets under the Claude config directory (`$CLAUDE_CONFIG_DIR`, else `~/.claude`): rules, sub-agents, `settings.json` (three-way merged), plus the Claude post-install merges (hooks into settings, app-config MCP block, model config migration). **Skipped when Claude Code CLI is not detected.**
4. **Codex files** — Codex-specific assets: adapted skills → `~/.agents/skills/`, review agents → `~/.codex/agents/`, guidance → `~/.codex/AGENTS.md`, a provider-derived model catalog that preserves new entries while lifting GPT-5.6 and Astra to their published context ceiling → `~/.codex/.pilot-model-catalog.json`, plus merged `~/.codex/config.toml` and `~/.codex/hooks.json`. **Skipped when neither Codex CLI nor the ChatGPT-bundled Codex binary is detected.**
5. **Config files** — Creates `.nvmrc` and project config.
6. **Dependencies** — Installs the latest checksum-verified Open Claude Design release; the complete pinned Impeccable CLI/skill/agents/hooks package; Semble; RTK; CodeGraph; ast-grep; [Chrome DevTools MCP](https://github.com/ChromeDevTools/chrome-devtools-mcp); [playwright-cli](https://github.com/microsoft/playwright-cli); [agent-browser](https://agent-browser.dev/); language servers; and the `codex@openai-codex` Claude marketplace plugin. Agent-specific dependencies still skip when their target agent is absent. Homebrew is preferred for ast-grep, with an audited pinned npm fallback for hosts without Brew.
7. **Shell integration** — Auto-configures bash, fish, and zsh with the `pilot` admin alias and a Codex wrapper that raises a low per-process open-file soft limit without lowering a higher one.
8. **Finalize** — Success message with next steps.

</details>

### First Steps

Start either agent in any project. Work directly, use the agent's native Plan/Goal tools, or invoke a Pilot workflow — these are peer choices, and the same harness stays active around each one.

```bash
# Claude Code         # Codex CLI
claude                codex
```

When you want repository-specific shared guidance, run `/setup-rules` in Claude Code or `$setup-rules` in Codex. It reads the codebase, discovers conventions, and prepares synchronized rules and MCP guidance; it is useful setup, not a prerequisite for using Pilot.

Use `/create-skill` to capture a repeatable procedure and `/benchmark` to measure whether guidance improves output. See [Other Pilot Workflows](#other-pilot-workflows) for the full on-demand toolkit.

---


<h2 id="features">Ways of Working</h2>

Pilot supports three peer paths. Choose the contract that fits the work; none is the escalation path or preferred default for another.

| Path | What it adds |
|---|---|
| Direct request | The shortest route from a clear request to implementation and verification |
| Native agent Plan/Goal tools | The planning, task, approval, and persistence model built into Claude Code or Codex |
| Pilot workflows | Durable requirements, plans, criteria, TDD loops, reviews, and verification evidence |

## Pilot Workflows

Pilot's four structured workflows remain available when their explicit artifact or lifecycle contract is useful.

| Workflow | Use it when | Contract |
|---|---|---|
| [`/spec`](https://pilot-shell.com/docs/workflows/spec) · `$spec` | You want ordered tasks approved before implementation | Plan against the real codebase, implement with TDD, review independently, and verify end to end |
| [`/build`](https://pilot-shell.com/docs/workflows/build) · `$build` | The outcome is clear but the task list should evolve while building | Define acceptance criteria, build in rounds, and let an independent judge turn gaps into the next round |
| [`/fix`](https://pilot-shell.com/docs/workflows/fix) · `$fix` | Existing behavior is broken | Reproduce the defect, write the RED test, repair the root cause, run the quality gate, and audit the result |
| [`/prd`](https://pilot-shell.com/docs/workflows/prd) · `$prd` | The problem, audience, or scope is still unclear | Explore directions and produce a reviewable product requirement document |

`/spec` and `/build` are peers: choose `/spec` for an approved plan and `/build` for a goal measured by acceptance criteria. Size alone does not decide.

```text
Requirement or goal → plan / criteria → TDD implementation → quality gates
                                            ↑                 ↓
                                            └─ review and runtime verification loop
```

Requirements, plans, buildouts, tasks, criteria, and verification evidence live in durable files under `docs/`. Stop guards keep the workflow open until the obligations pass or are reported unresolved.

[Explore all workflow details →](https://pilot-shell.com/docs/category/pilot-workflows)

## Other Pilot Workflows

Use these on demand; the full procedures live in the documentation.

| Workflow | Purpose |
|---|---|
| [`/investigate` · `$investigate`](https://pilot-shell.com/docs/workflows/investigate) | Trace one codebase question with cited evidence and no edits |
| [`/cleanup` · `$cleanup`](https://pilot-shell.com/docs/workflows/cleanup) | Corroborate dead-code candidates without deleting anything |
| [`/setup-rules` · `$setup-rules`](https://pilot-shell.com/docs/workflows/setup-rules) | Generate modular project guidance from the real codebase |
| [`/create-skill` · `$create-skill`](https://pilot-shell.com/docs/workflows/create-skill) | Capture and test a reusable procedure |
| [`/benchmark` · `$benchmark`](https://pilot-shell.com/docs/workflows/benchmark) | Measure a rule or skill against falsifiable before/after evals |

## Visual Engineering

Pilot installs [Open Claude Design](https://github.com/maxritter/open-claude-design) and [Impeccable](https://github.com/pbakaus/impeccable) as complementary parts of the harness. Open Claude Design connects the real codebase and coding agent to Claude Design's visual workspace; Impeccable adds focused refinement workflows and deterministic checks.

Ask normally—the design workflow loads in the background, keeps code and design synchronized, and feeds the result into Pilot's implementation and verification process.

## Pilot Shell Console

The local Console at `localhost:41777` makes the harness visible and steerable.

<img src="docs/img/console/dashboard.webp" alt="Console — Dashboard" width="700">

- Review and annotate requirements, specifications, buildouts, and diffs; feedback flows back into the work that owns them.
- Recover Claude Code and Codex sessions and search source-linked project knowledge.
- Inspect progress, verification evidence, notifications, changes, usage, and costs.
- Manage workflow settings and shared rules, skills, commands, and agents.

Memory capture runs automatically in the background across Claude Code and Codex. Pilot selects an available low-cost provider, handles temporary quota failures, and keeps saved findings searchable without a model call. This adds project history alongside each agent's native context.

Team sharing is optional: keep stored memory local, or let useful findings travel through your project's normal Git commits and pulls. [How automatic memory works](docs/docusaurus/docs/features/knowledge.md).

[Explore the Console →](https://pilot-shell.com/docs/features/console)

---

## Documentation

For full details on every component, see the **[Documentation](https://pilot-shell.com/docs/)**.

---

## Changelog

See the full changelog at [GitHub Releases](https://github.com/maxritter/pilot-shell/releases).

---

## Contributing

Found a bug or missing a feature? [Open an issue](https://github.com/maxritter/pilot-shell/issues) on GitHub.

---

## License

See [LICENSE](LICENSE).

---

<div align="center">

**How real engineers run Claude Code and Codex**

Made with 🩵 by [Max Ritter](https://maxritter.net)

</div>

[osai-verify: 8d67182dee08d42091c5]: #
