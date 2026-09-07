---
sidebar_position: 2
title: Installation
description: One-command installation that works with any existing project — no scaffolding, no restructuring. Run the installer once, then use Pilot across all repos.
---

# Installation

Works with any existing project — no scaffolding required.

## One-Command Installation

```bash
curl -fsSL https://raw.githubusercontent.com/maxritter/pilot-shell/main/install.sh | bash
```

Run from any directory — it installs globally to `~/.pilot/` and your Claude config directory (and `~/.codex/` when Codex CLI or the ChatGPT-bundled Codex runtime is detected). After installation, run `claude` or `codex` directly. On macOS, you can instead restart ChatGPT desktop and open the project there. Pilot Shell loads automatically in either Codex client.

The Claude config directory is `~/.claude` unless you set `CLAUDE_CONFIG_DIR`. See [Using a non-default Claude config directory](#using-a-non-default-claude-config-directory).

## What the Installer Does

8 steps with progress tracking and rollback on failure. Steps 3 and 4 are agent-conditional — they skip cleanly when the matching agent is not detected on your system. The installer **does not install Claude Code, Codex CLI, or ChatGPT itself**; you install at least one of them yourself per [Prerequisites](./prerequisites).

| Step | Title | Description |
|------|-------|-------------|
| 1 | Prerequisites | Checks/installs Homebrew, Node.js, Python 3.12+, uv, git, jq. Verifies at least one supported agent (Claude Code, Codex CLI, or the Codex runtime bundled with ChatGPT on macOS) is present; aborts with a clear error otherwise. |
| 2 | Pilot files | Installs agent-neutral assets: hooks and Console files under `~/.pilot/`, plus canonical raw sources under `~/.pilot/rules/`, `~/.pilot/skills/`, and `~/.pilot/agents/`. Each agent's adapter consumes those sources in its native format. Always runs. |
| 3 | Claude files | Installs Claude-specific assets to the Claude config directory: rules, sub-agents, and `settings.json` (three-way merged); plus Claude post-install merges (hooks into settings, app-config MCP block, model config). **Skipped when Claude Code CLI is not detected.** |
| 4 | Codex files | Installs adapted skills to `~/.agents/skills/`, review agents to `~/.codex/agents/`, guidance to `~/.codex/AGENTS.md`, and merged `~/.codex/config.toml` / `~/.codex/hooks.json`. **Skipped when neither Codex CLI nor the ChatGPT-bundled runtime is detected.** |
| 5 | Config files | Creates `.nvmrc` and project config |
| 6 | Dependencies | Installs Semble, RTK, CodeGraph, ast-grep, Chrome DevTools MCP, playwright-cli, agent-browser, language servers, plus the `codex@openai-codex` Claude marketplace plugin. ast-grep uses Homebrew when available and a pinned npm fallback otherwise. Claude-side plugins (Codex companion plugin, Chrome DevTools MCP plugin, LSP plugins) are skipped on Codex-only systems. |
| 7 | Shell integration | Auto-configures bash, fish, and zsh with the `pilot` alias and a Codex wrapper that raises a low per-process open-file soft limit without lowering an existing higher value. Add `# pilot-shell:managed-elsewhere` to a config file to opt out. |
| 8 | Finalize | Success message with next steps |

## What to Do Next

The completion panel stays deliberately short:

1. Start `claude` or `codex`; direct requests, native Plan/Goal tools, and Pilot workflows use the same harness.
2. Run `/setup-rules` or `$setup-rules` when you want repository-specific shared guidance.
3. Open the local Console to review sessions, memories, workflow artifacts, changes, and settings.
4. Browse the documentation for native integrations, Pilot workflows, skills, and tools.
5. Run `pilot update` when you want to check for a newer Pilot release.

Direct requests, native Plan/Goal tools, and Pilot workflows are peer ways to work inside the same harness.

## Using a non-default Claude config directory

Claude Code reads its configuration from `~/.claude` unless you set `CLAUDE_CONFIG_DIR`. Pilot Shell honours the same variable, so you can install it into a work profile while leaving a personal `~/.claude` completely untouched.

Set the variable for the install **and** for every launch:

```bash
# Install into the work profile
CLAUDE_CONFIG_DIR=~/.claude_work bash <(curl -fsSL https://raw.githubusercontent.com/maxritter/pilot-shell/main/install.sh)

# Launch against it
CLAUDE_CONFIG_DIR=~/.claude_work claude
```

Everything follows the variable: skills, rules, sub-agents, `settings.json`, the app config (`$CLAUDE_CONFIG_DIR/.claude.json`), hooks, the Console, and the uninstaller. Running plain `claude` afterwards uses your default profile, which has no Pilot assets in it — that is the point.

The value must be an **absolute path**. A relative or empty value is rejected rather than silently falling back to `~/.claude`, so a typo can never write the profile you were protecting.

Claude Code keys its stored credentials per config directory, so the two profiles log in independently.

### Two limitations to know about

- **`~/.pilot/` is shared across profiles.** The binary, hooks, license, memory database and session store live in one place regardless of which Claude profile you use. Memory and sessions are therefore pooled across profiles.
- **`~/.agents/` cannot be relocated.** Codex derives its agents-skills directory from your home directory and provides no override. `CODEX_HOME` relocates `~/.codex` and is honoured, but `~/.agents/skills/` always sits under `$HOME`.

If you install into one profile and later start a session in another, a session-start check warns you that the assets live elsewhere. It cannot warn when the profile has no Pilot install at all (no Pilot hook is registered there to run), which is why the installer prints the resolved paths before writing.

## macOS open-file limit for Codex

A low macOS default can surface as `Too many open files` while Codex loads its configuration.

When Codex is detected, Pilot's bash, zsh, and fish wrappers raise a low soft limit toward 1024 for each CLI process. The wrapper never lowers a higher limit, never exceeds the hard cap, and does not change the parent shell.

Modern macOS does not give Pilot a reliable way to change the limit inherited by ChatGPT when it is launched normally from the Dock, so the installer does not request administrator access for this. If ChatGPT itself reports the error, restart or update the app; that desktop process must set its own limit.

## Browser Automation

Pilot installs three browser tools automatically: **Chrome DevTools MCP**, **playwright-cli**, and **agent-browser**.

- **Claude Code:** also install the [Claude Code Chrome extension](https://code.claude.com/docs/en/chrome) for the richest browser context. Tier order: Chrome extension → Chrome DevTools MCP → playwright-cli → agent-browser.
- **Codex CLI:** the Chrome extension is not available. Tier order: Chrome DevTools MCP → playwright-cli → agent-browser.

## Claude Code display patch

For supported native Claude Code installs, Pilot applies
[patch-claude-code](https://github.com/a-connoisseur/patch-claude-code) from a
checksum-verified source revision. It shows detailed tool calls, subagent prompts,
and live thinking summaries without verbose mode. Pilot preserves the original
branding and spinner tips; model and effort choices remain yours.

After successful patching, Pilot turns verbose mode off once for the active
Claude profile. Later changes through `/config` are preserved; future Pilot
updates do not repeat the reset. Flicker-free rendering remains enabled by
default through `CLAUDE_CODE_NO_FLICKER`.

The installer patches a copy, verifies its version, and retains the original in
`~/.pilot/claude-display-patch/` before replacing the executable. On macOS, the
patched copy is ad-hoc signed. The binary is shared across Claude config profiles.
Unsupported binaries or patch failures leave Claude unchanged. Claude's own
updates can remove the patch; the next Pilot installation or update reapplies it
when compatible. Claude updates are never disabled or pinned by this integration.
If an upstream change breaks the required patch patterns, only the extra display
features are unavailable until the patcher is updated; Claude remains usable.

Pilot's uninstaller restores originals only while the installed binaries still
match Pilot's patches. You can also restore them directly:

```bash
uv run --python 3.12 ~/.pilot/claude-display-patch/restore.py --restore
```

## Codex Companion Plugin (Included)

The [Codex companion plugin](https://github.com/openai/codex-plugin-cc) is installed automatically by the Pilot installer. It provides adversarial code review powered by OpenAI — an independent second opinion during Claude Code's `/spec` planning and verification.

1. Run `/codex:setup` in any Pilot session to authenticate with your OpenAI account
2. Enable the Codex Companion Reviewers in Console Settings → Reviewers

This is separate from [Codex CLI support](/docs/getting-started/codex-cli) — the companion plugin runs from within Claude Code, while Codex CLI is a standalone agent.

## Dev Container

Pilot Shell works inside Dev Containers. Copy the `.devcontainer` folder from the [Pilot Shell repository](https://github.com/maxritter/pilot-shell/tree/main/.devcontainer) into your project, adapt it to your needs (base image, extensions, dependencies), and run the installer inside the container. The installer auto-detects the container environment and skips system-level dependencies like Homebrew.

For tighter isolation when working with untrusted code, layer Claude Code's [`/sandbox`](https://code.claude.com/docs/en/sandboxing) on top — `bubblewrap`, `socat`, `iptables`, and `ipset` are pre-installed in the Dockerfile so it works out of the box on Linux.

### Further reading

- [Claude Code · Development containers](https://code.claude.com/docs/en/devcontainer) — Anthropic's reference container, persistent volumes, organization policy, network egress, the `--dangerously-skip-permissions` flag.
- [Claude Code · Sandboxing](https://code.claude.com/docs/en/sandboxing) — Seatbelt (macOS) and bubblewrap (Linux/WSL2), `/sandbox` modes, `allowedDomains`, filesystem allow/deny rules, security limitations.

## Install Specific Version

```bash
export VERSION=8.4.0
curl -fsSL https://raw.githubusercontent.com/maxritter/pilot-shell/main/install.sh | bash
```

See [releases](https://github.com/maxritter/pilot-shell/releases) for all available versions. Useful when a specific version is known stable.

## Uninstall

```bash
curl -fsSL https://raw.githubusercontent.com/maxritter/pilot-shell/main/uninstall.sh | bash
```

The default removes Pilot's runtime, Console, statusline, hooks, managed skills/rules/agents, MCP entries, settings injections, and shell aliases. It stops a running Pilot worker first. Claude Code, Codex, project files, custom agent configuration, shared external tools, project indexes, and all user data remain available.

Before the final preview, the interactive uninstaller asks two independent questions: whether to remove proven Pilot-owned external tools, and whether to purge Pilot data. It reads those answers from the controlling terminal rather than the script's standard input, so the prompts continue to work when the script itself arrives through `curl ... | bash`. Answering no keeps the safe defaults.

External tools are deliberately separate: provenance does not prove that a user no longer relies on a tool. Pilot records tools that were absent before installation, and removes only those when you explicitly request it:

```bash
curl -fsSL https://raw.githubusercontent.com/maxritter/pilot-shell/main/uninstall.sh | bash -s -- --remove-tools
```

Pilot data is a third, independent choice:

```bash
curl -fsSL https://raw.githubusercontent.com/maxritter/pilot-shell/main/uninstall.sh | bash -s -- --purge-data
```

Pass both options together only when you want both cleanups. The confirmation preview names the exact categories before anything is removed.

For unattended execution, `--yes` accepts the safe defaults and skips every prompt. Combine it with `--remove-tools` and/or `--purge-data` only when automation explicitly intends those additional removals.

## Reset & Refresh

Accumulated session logs and Pilot's caches grow over time and can degrade performance. A periodic reset every few weeks restores a clean baseline.

```bash
# 1. If using Claude Code, log out first
/logout

# 2. Back up your current config (just in case)
#    Using CLAUDE_CONFIG_DIR? Substitute it for ~/.claude below, and back up
#    "$CLAUDE_CONFIG_DIR/.claude.json" instead of ~/.claude.json.
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
