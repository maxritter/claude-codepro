---
sidebar_position: 4
title: Rules & Standards
description: Shared guidance for Claude Code and Codex — proportionate testing, language standards, tool routing, and project conventions.
---

# Rules & Standards

Production-tested best practices loaded into every session.

Rules load automatically at session start or when their scoped files become relevant. Pilot ships 8 always-on rules and 9 path-gated stack rules, delivered in the format each agent handles best. Project conventions and user instructions shape how these defaults apply; the active runtime's safety and permission controls remain authoritative.

- **Claude Code:** rules in `~/.claude/rules/` (global) and `.claude/rules/` (project). Project rules take precedence.
- **Codex:** global guidance in `~/.codex/AGENTS.md`, adapted skills in `~/.agents/skills/`, and file-type standards loaded when relevant.

Run `/setup-rules` (or `$setup-rules` on Codex) to generate project-specific rules from your codebase.

## Built-in Rule Categories

### Core Harness (3 rules)

- `task-and-workflow.md` — Direct execution when no workflow is invoked, equal treatment of native and Pilot workflows, session state, agent-controlled delegation without permission prompts, and tool portability
- `testing.md` — Existing behavioural coverage first, regression checks for meaningful changes, and tests sized to the actual risk without global class or coverage quotas
- `verification.md` — Evidence matched to the affected command, API, rendered UI, or installed artifact; reuse valid results and complete required project checks

### Development Practices (3 rules)

- `development-practices.md` — Project policies, systematic debugging, git rules
- `code-review-reception.md` — How to receive and act on code review feedback
- `documentation-sync.md` — Update affected docs (README, API docs, CLAUDE.md, AGENTS.md) in the same change as the code

### Tooling & Context (4 rules)

- `cli-tools.md` — Pilot CLI, Semble hybrid code search, RTK token optimization
- `browser-automation.md` — Path-gated UI verification using the project's driver or the active runtime's available browser tools, plus reuse of [Impeccable](https://impeccable.style) hook evidence and a bounded advisory detector fallback
- `mcp-servers.md` — MCP server reference and tool selection guidance
- `mobile-development.md` — Path-gated installed-app verification, project-specific device drivers, and preservation of app data for Capacitor, React Native, Expo, Flutter, Android, and iOS projects

### UI Design Expertise (automatic skills)

- Open Claude Design's `open-claude-design-quality` skill supplies product-grounded visual hierarchy, content discipline, system thinking, interaction states, responsive/theme quality, and contextual anti-template guidance for user-visible changes. Logic-only changes remain visually neutral.
- `standards-frontend.md` remains the implementation owner for components, CSS, semantic accessibility, responsive engineering, and performance.
- `browser-automation.md` remains the runtime owner for interaction evidence; Impeccable owns hook/detector evidence and Open Claude Design owns the overall UI review workflow.

Detailed procedures live in five implicit Open Claude Design skills for stable design quality, creation, extraction, review, and real Claude Design project access. Users ask normally; the matching description loads only the required router and specialized references. See [UI Design and Claude Design](/docs/workflows/ui-design).

## Deterministic asset validation

Pilot's source checkout includes a no-model validation gate for the shipped rules and Codex skill catalog:

```bash
uv run python scripts/validate_agent_assets.py
```

The gate compiles the real Codex skill descriptions, checks public implicit-skill positives and owner-labelled negatives, proves explicit workflows cannot hijack natural-language requests, and tests internal phase routing only through parent handoffs. It also ratchets description similarity and keeps the always-loaded rule pack at no more than 500 lines and 7,500 words. Use `--json` for machine-readable findings and metrics; the check makes no API calls and spends no model tokens.

## Coding Standards — Activated by File Type

| Standard | Activates On | Coverage |
|----------|-------------|----------|
| Python | `*.py` | Project environment/version, configured checks, type hints, resources and errors |
| TypeScript | `*.ts, *.tsx, *.js, *.jsx, *.mjs, *.mts` | Project package manager/runtime, type boundaries, async behaviour |
| Go | `*.go` | Existing modules/layout, testing, formatting, errors and cancellation |
| .NET | `*.cs, *.csproj, *.sln, *.slnx` | Existing SDK/analyzer policy, async and HTTP lifetimes, faithful database tests |
| Frontend | `*.tsx, *.jsx, *.html, *.vue, *.css` | Components, CSS, accessibility, responsive design |
| Blazor | `*.razor, *.razor.css, *.razor.cs` | Components, CSS isolation, render modes, lifecycle |
| Backend | `**/models/**, **/routes/**, **/api/**` | API design, data models, query optimization, migrations |

:::tip Custom rules
Create `.claude/rules/my-rule.md` in your project. Add `paths: ["*.py"]` frontmatter to activate only for specific file types. Run `/setup-rules` to auto-discover patterns and generate project-specific rules.
:::

:::info Monorepo support
Organize rules in nested subdirectories by product and team (e.g. `.claude/rules/my-product/team-x/`). Team-level rules must use `paths` frontmatter to scope to the right files. `/setup-rules` generates a `README.md` in your rules directory to document the structure.
:::

## Testing posture: proportionate and behavioural

Pilot reuses existing behavioural tests before adding coverage. Meaningful behaviour changes and bug fixes should have a focused reproducer, preferably before implementation. If an automated test is impractical, the agent records the actual failing interaction or artifact and states the coverage limit.

There is no global test-class count, file-size limit, or numeric coverage target. Tests should protect contracts and credible failure modes while surviving internal refactors. Simple reversible edits can use existing checks; configuration and dependency changes receive the validation their runtime impact requires.

The agent runs focused checks and the repository's required suite. Passing results remain usable for the unchanged artifact and environment across messages and workflow phases. Relevant edits, failures, or unresolved concerns trigger additional checks.

An explicitly selected workflow may require a recorded RED/GREEN result or other review artifacts. The optional `Trivial:` field explains why a named existing check is sufficient; it is assessed against the actual change, rather than a five-line threshold. User instructions can change Pilot's default process without bypassing runtime permissions.

### Project-specific testing requirements

Keep stricter requirements in the repository's agent instructions or scoped project rule, such as `.claude/rules/testing-project.md`:

```markdown
---
paths: ["**/*.py", "**/*.ts", "**/*.tsx"]
---

## Testing requirements

- Reproduce every business-rule defect with an automated regression test.
- Exercise database constraints and transactions against the supported database.
- Run the project's configured coverage gate and required CI checks.
```

These requirements apply through the agent's instruction loading and precedence; a filename alone does not replace another rule. For Codex, ensure the project `AGENTS.md` exposes the relevant rule.

### What verification proves

CLI and API changes need execution evidence when their runtime boundary is affected. UI claims require the relevant interaction and rendered result. Native and packaged changes need the corresponding built or installed artifact; a desktop dev server does not establish mobile release behaviour.

Pilot uses documented local and authorized preview targets. A verification request does not itself authorize a deployment, replacement of a live installation, or mutation of user data. The agent prepares everything it can and reports a concrete remaining gate when needed.

Design detectors remain advisory. Model-written prose is not validated merely by asserting that a source file contains expected phrases: packaging checks can establish generated syntax and delivery, while behavioural evaluations are needed to assess how models follow the instructions.
