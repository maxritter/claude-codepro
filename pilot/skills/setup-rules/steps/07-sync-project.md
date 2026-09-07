## Step 7: Sync Shared Core and Scoped Project Rules

Build one shared repository core for Claude Code and Codex, with detailed rules loaded only for matching work.

### Step 7.1: Classify Existing Guidance

Classify every instruction from existing `AGENTS.md`, `CLAUDE.md`, and `.claude/rules/` into exactly one destination:

| Kind | Destination |
|------|-------------|
| Stable repository-wide command, convention, safety boundary, or architecture rule | `AGENTS.md` |
| Detailed guidance tied to observable file paths | `.claude/rules/{slug}-{topic}.md` with `paths` frontmatter |
| On-demand repeatable workflow | `.agents/skills/{slug}-{name}/SKILL.md`, handled through `/create-skill` |
| Personal, untracked preference | `CLAUDE.local.md` or the agent's user configuration |

`AGENTS.md` must include a compact **matching-rule index**. For each scoped rule, list its repo-relative path, its `paths` globs, and a one-line instruction to read it before matching work. Claude Code receives the rule automatically; the index gives Codex the same on-demand route without inlining the detail.

Preserve existing headings and wording when they remain accurate. Never drop a line from an existing root file merely because the final `CLAUDE.md` becomes a one-line import.

### Step 7.2: Resolve Migration Choices — CONDITIONAL

If content migration is already authorized and its mapping is unambiguous, preserve unique content and proceed. Ask only when moving content exposes a material unresolved conflict or the user requested a preview before writes:

AskUserQuestion: "Pilot can make `AGENTS.md` the shared core, keep detailed rules path-scoped, and reduce `CLAUDE.md` to `@AGENTS.md`. How should I handle the existing content?"

- **"Migrate and preserve all (Recommended)"** — show the source-to-destination mapping, retain every unique user-authored instruction, then proceed
- **"Show full diff first"** — render proposed `AGENTS.md`, scoped rules, and `CLAUDE.md`; wait for confirmation
- **"Review each conflict"** — ask only where instructions conflict or their scope is ambiguous
- **"Skip shared sync"** — leave root files untouched; continue the audit but report that cross-agent parity is not installed

When instructions conflict, present both exact passages and ask which behavior is authoritative. Do not silently merge incompatible rules.

If no root guidance exists, create the shared core without asking; setting up project rules is the requested operation. If only one source exists and classification is unambiguous, preserve it in the appropriate destination.

### Step 7.3: Create or Update AGENTS.md

Keep `AGENTS.md` under about 400 lines. Use this shape, omitting empty sections:

```markdown
# [Project] repository instructions

## Project
[Stable overview, stack boundaries, and directory ownership]

## Commands
[Install, build, test, lint, and required focused verification]

## Repository rules
[Repo-wide conventions, safety boundaries, and non-obvious behavior]

## Matching detailed rules
- `.claude/rules/{slug}-{topic}.md` — `{path/glob/**}` — read before [matching work]
```

Do not add generated timestamps that create noise on every run. Preserve accurate user-authored sections in place rather than moving them into an `Additional Notes` dumping ground.

### Step 7.4: Create or Update Scoped Rules

Create a detailed rule only when its guidance has a narrower file scope than the whole repository. Every detailed rule requires `paths` frontmatter:

```yaml
---
paths:
  - "src/product-a/**"
  - "tests/product-a/**"
---
```

For a monorepo, keep the existing product/team directory model:

1. Product-level: `.claude/rules/{product}/{slug}-{product}-{topic}.md`
2. Team-level: `.claude/rules/{product}/{team}/{slug}-{team}-{topic}.md`
3. Shared library: `.claude/rules/common/{slug}-common-{topic}.md`

All three require real `paths` globs. Shared guidance without a meaningful path predicate belongs in `AGENTS.md`.

### Step 7.5: Generate Rules README — CONDITIONAL

If `.claude/rules/` contains files, create or update `.claude/rules/README.md` as a navigation aid:

```markdown
# Rules Directory Structure

> Maintained by `/setup-rules`. `AGENTS.md` is the shared core; these files hold path-scoped detail.

| Rule | Paths | Purpose |
|------|-------|---------|
| `{slug}-{topic}.md` | `src/example/**` | [One-line purpose] |
```

Generate the table from files on disk, list every scoped rule and its exact globs, and keep the README under 80 lines. Verify that the same inventory appears in the matching-rule index in `AGENTS.md`.
