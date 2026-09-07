## Step 11: Install and Verify Cross-Agent Synchronization

The final repository contract is:

- `AGENTS.md` is the user-editable shared core.
- `CLAUDE.md` contains exactly `@AGENTS.md` plus a trailing newline.
- `.agents/skills/` is the durable source for tracked skills and the Codex project-skill tree.
- `.claude/skills/` is the Claude Code project-skill tree; supported edits synchronize safely in either direction.
- Existing exact in-repository aliases (`AGENTS.md` to `CLAUDE.md`, or one skill root to the other) remain supported because both agents already read the same physical source. Never replace those aliases merely to enforce the preferred new-repository layout.
- Pilot's shared hook synchronizes on SessionStart, supported edits made through either agent, and Stop as a Code Mode backstop.
- `scripts/sync-agent-assets.mjs` is the standalone recovery writer and CI drift checker.

Untracked and gitignored project skills participate in two-way local synchronization. Their baseline lives under `.git/pilot`, so private skill contents never enter shared CI metadata. Invalid one-sided directories remain untouched because they are not valid portable skills.

### Step 11.1: Confirm Destructive Reconciliation — CONDITIONAL

Reuse the migration decision from Step 7. Ask again only if Step 10 found independent edits on both sides or another conflict that cannot be resolved from the trusted baseline.

AskUserQuestion: "Both project-skill copies changed independently. Which content should become the shared version?"

- **"Preserve all unique content (Recommended)"** — copy unique instructions/skill files into `AGENTS.md`, scoped rules, or `.agents/skills/` as appropriate, then regenerate
- **"Use `.agents/skills/` and `AGENTS.md`"** — use the Codex-side skill copy and shared root instructions
- **"Review each conflict"** — show each conflicting file and choose its canonical content
- **"Skip synchronization"** — leave assets untouched and report the failed parity gate

Never overwrite either side while a two-sided conflict is unresolved.

### Step 11.2: Install the Repository Checker

Resolve the bundled script relative to this skill's loaded `SKILL.md` (its source path is `scripts/sync-agent-assets.mjs`). Run it from the target repository:

```bash
node <setup-rules-skill-dir>/scripts/sync-agent-assets.mjs --install --repo .
```

`--install` writes the standalone `scripts/sync-agent-assets.mjs` into the repository and performs the initial convergence of the root import and project skill mirror. Include the installed script in the reviewable change so recovery and CI use the same implementation without requiring Pilot Shell. Commit only when the user has authorized a commit.

The checker creates missing skill roots when a valid one-sided skill needs a counterpart.

If the bundled script cannot be resolved, stop this step before changing `CLAUDE.md` or `.claude/skills/` and report the installation gap.

### Step 11.3: Confirm Automatic Hook Coverage

Pilot installs one shared agent-asset hook through both its Claude Code and Codex adapters. Do not add repository-specific hooks. Confirm the installed adapters provide these behaviors:

1. **SessionStart:** detect repositories with agent assets, converge `CLAUDE.md`, and synchronize both skill trees before work begins.
2. **Either-side edit:** after either agent edits `AGENTS.md`, `.agents/skills/`, `.claude/skills/`, or `.claude/rules/`, run the trusted synchronizer.
3. **Conflict safety:** copy the side that diverged from the trusted baseline; when both diverged, preserve both and report the exact conflict.
4. **Ignored assets:** synchronize gitignored skills locally and expose ignored rule paths to Codex as a bounded on-demand index.
5. **Stop:** run a read-only check and repair drift only when needed. This covers Code Mode when nested edits emitted no PreToolUse/PostToolUse event.
6. **Shared aliases:** accept only an exact link to the corresponding in-repository instruction file or skill root; reject links anywhere else without modifying their targets.
7. **Silent success:** successful SessionStart and edit-time synchronization must not emit a user-facing status message. Keep the bounded rule index in agent-only context with status/debug output suppressed; surface output only for actionable failures or Stop blocks.

This makes the active agent irrelevant to authoring: Claude Code and Codex both edit the same canonical filesystem paths. If either adapter lacks the shared hook, report that Pilot installation needs repair; do not compensate with a second project hook.

The hook must execute only Pilot's installed bundled checker. Treat the repository copy as a CI/manual recovery command; never execute that repository-controlled copy from a trusted global hook.

### Step 11.4: Add the Check to Existing CI

When the repository has CI, add this command to an existing required validation, lint, or documentation job:

```bash
node scripts/sync-agent-assets.mjs --check
```

Choose the cheapest existing job that already checks out the complete repository. Do not create a new workflow or job for this check. Preserve the workflow's package-manager and step conventions. If no CI exists, document the local command instead of introducing a CI system.

### Step 11.5: Prove Automatic Parity

The shared hook normally performs every write. After all source edits and CI wiring, run the read-only backstop:

```bash
node scripts/sync-agent-assets.mjs --check
```

If `--check` reports drift, fix the canonical source or hook installation, run `node scripts/sync-agent-assets.mjs --write` once as recovery, then rerun `--check`. Users should not need `--write` during normal Claude Code or Codex work.

The check must exit zero. Then capture evidence for the summary:

1. `AGENTS.md` exists and retains every approved user-authored shared section.
2. `CLAUDE.md` is byte-for-byte `@AGENTS.md\n`, or one root instruction file is an exact in-repository alias to the other.
3. All valid one-sided skills have counterparts; tracked, untracked, and gitignored skill trees are synchronized, share one physical root through an exact in-repository alias, or have an explicit preserved conflict.
4. Every synchronized file under `.agents/skills/<name>/` is byte-identical to `.claude/skills/<name>/`.
5. `scripts/sync-agent-assets.mjs --check` exits zero without modifying the worktree.
6. Pilot's shared hook covers SessionStart, edits on either skill tree and `.claude/rules/`, root-instruction edits, and Stop for both agents.
7. An existing CI job invokes `--check`, or the repository has no CI and the local-only status is recorded.

If a conflict is reported, reconcile the two preserved copies explicitly, then run `--write` and `--check` again.
