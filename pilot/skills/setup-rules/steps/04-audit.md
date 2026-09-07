## Step 4: Quality Audit

**Audit `AGENTS.md`, `CLAUDE.md`, scoped rules, project skills, and the sync checker against the shared Claude Code/Codex contract in Step 1.** For audit-only work, report findings. For an authorized setup or repair, apply evidenced corrections within scope; user confirmation is needed only for a genuinely unresolved decision.

**Skip this phase if:** None of those assets exists (nothing to audit).

### Step 4.1: Run Checks

For each shared instruction file, scoped rule, tracked skill tree, and checker/CI integration found in Step 2, evaluate:

| Check                          | What to look for                                                                                                                                 | Severity |
| ------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------ | -------- |
| **Size**                 | Files over 200 lines (context bloat, reduced adherence)                                                                                          | Warning  |
| **Specificity**          | Vague instructions: "format properly", "write clean code", "keep organized" — suggest concrete alternatives                                     | Warning  |
| **Redundancy**           | Standard conventions Claude already knows (e.g., "use const for immutable variables" in a JS project)                                            | Info     |
| **Conflicts**            | Contradicting instructions across different files (e.g., one rule says "use tabs", another says "use spaces")                                    | Error    |
| **Path-scoping**         | Detailed `.claude/rules/` files without `paths` frontmatter — scope them or move truly shared guidance into `AGENTS.md`                  | Warning  |
| **Nested path-scoping**  | Rules in team-level subdirectories (`.claude/rules/{product}/{team}/`) without `paths` frontmatter — MUST be scoped (see Step 1 → Recommended Directory Structure) | Error    |
| **Structure**            | Dense paragraphs without headers/bullets, poor scanability, missing section organization                                                         | Warning  |
| **Stale references**     | References to files, commands, paths, or tools that no longer exist in the codebase — verify with `ls` or Semble                              | Error    |
| **Import opportunities** | Large files that could split content using `@path/to/import` syntax                                                                            | Info     |
| **Unexplained absolutes** | Critical rules (security, data loss, breaking changes) asserted as bare commands — `ALWAYS`, `NEVER`, `YOU MUST` — with no reason attached. Current models follow a rule they understand and negotiate with one they don't, so the fix is to add *why it matters*, not louder emphasis | Info     |
| **Shared-core drift**    | `CLAUDE.md` is not exactly `@AGENTS.md`, or shared instructions are duplicated/conflicting across the two root files                            | Error    |
| **Skill drift**          | A tracked project skill exists only in `.claude/skills/`, or matching tracked `.agents/skills/` and `.claude/skills/` trees differ              | Error    |
| **Generated-mirror edits** | Tracked changes exist only in `.claude/skills/`; preserve them by migrating to `.agents/skills/` before regeneration                           | Error    |
| **Checker/CI gap**       | `scripts/sync-agent-assets.mjs` is absent, cannot pass `--check`, or no existing CI job invokes `--check`                                       | Warning  |

**How to check for specificity:** Look for adjectives without measurable criteria ("good", "clean", "proper", "nice"), instructions that restate language defaults, and rules without concrete examples or verifiable outcomes.

**How to check for stale references:** For each file path, command, or tool name referenced in rules, verify existence:

```bash
# File paths
ls -la <referenced-path> 2>/dev/null

# Commands
which <referenced-command> 2>/dev/null

# Code patterns (Semble if available, otherwise Grep)
semble search "<referenced-pattern>" ./ --top-k 1
# Fallback: Grep(pattern="<referenced-pattern>", head_limit=5)
```

### Step 4.2: Present Findings

Group findings by severity and present to user:

```
## Quality Audit Results

### Errors (should fix)
- ❌ **Conflict:** `.claude/rules/style.md` says "use tabs" but `CLAUDE.md` says "use 2-space indent"
- ❌ **Stale:** `.claude/rules/project.md` references `src/legacy/` which no longer exists
- ❌ **Shared-core drift:** `CLAUDE.md` duplicates 42 lines from `AGENTS.md` instead of importing it
- ❌ **Skill drift:** `.claude/skills/release/SKILL.md` differs from canonical `.agents/skills/release/SKILL.md`

### Warnings (recommended)
- ⚠️ **Size:** `CLAUDE.md` is 340 lines — preserve its shared content in `AGENTS.md`, scope file-specific detail, then replace it with the one-line import
- ⚠️ **Vague:** `.claude/rules/style.md` line 12: "Format code properly" → suggest: "Run `prettier --write` before committing"
- ⚠️ **Overlap:** Authentication instructions appear in both `AGENTS.md` and `.claude/rules/auth.md`

### Suggestions (nice to have)
- 💡 **Path-scope:** `.claude/rules/testing.md` only mentions `*.test.ts` files — add `paths: ["**/*.test.ts"]` frontmatter
- 💡 **Routing:** `.claude/rules/testing.md` is scoped correctly but missing from the `AGENTS.md` matching-rule index
- 💡 **Import:** `CLAUDE.md` inlines API docs — move shared constraints to `AGENTS.md`, scoped detail to a rule, and leave only `@AGENTS.md`
```

### Step 4.3: Resolve only material decisions

Use the user's requested mode and prior decisions. Clear setup or repair requests authorize routine corrections; do not ask the user to approve each finding. If existing instructions conflict, first check the request and authoritative project contracts. Ask only when those cannot determine which behavior is intended.

### Step 4.4: Apply in-scope fixes

Read the target, make the supported correction, and inspect the resulting diff. Preserve user-authored meaning and unrelated changes. In an audit-only request, leave these as concrete recommendations rather than writing them.



**For file splits:** Keep the shared core in `AGENTS.md`. Move file-specific detail into `{slug}-`-prefixed `.claude/rules/` files with `paths` frontmatter, then add those files to the matching-rule index in `AGENTS.md`.

**For unresolved conflict resolution:** present the conflicting passages and the decision needed. Once resolved, update the affected guidance consistently.
