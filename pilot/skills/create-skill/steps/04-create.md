## Step 4: Create or Edit the Canonical Skill

### Project Scope

If the repository already has Pilot's synchronization checker, inspect its state before authoring:

```bash
test -f scripts/sync-agent-assets.mjs
node scripts/sync-agent-assets.mjs --check
```

If the script is absent, follow the repository's existing asset conventions and keep the requested skill canonical. Do not run a repository-wide migration merely to author one skill. Resolve a relevant legacy conflict before editing its content, and report any unavailable synchronization check.

Create or edit only the canonical directory:

```bash
mkdir -p .agents/skills/{slug}-{name}
# Write .agents/skills/{slug}-{name}/SKILL.md and any supporting files
```

Pilot's shared hook converges on SessionStart and synchronizes complete skill trees under `.agents/skills/` and `.claude/skills/` after supported edits from either Claude Code or Codex. Its Stop backstop covers Code Mode when no edit event fired. Untracked and gitignored skills participate through a trusted local baseline; independent two-sided edits are preserved as conflicts. Users normally do not run `--write`.

If a task or tool presents `.claude/skills/<name>/...`, it may be edited directly. Pilot synchronizes the change back when the `.agents/skills/` copy still matches the trusted baseline. If both copies changed independently, stop and reconcile the preserved versions explicitly.

### Global Scope

Global skills are outside the repository sync contract:

<!-- CC-ONLY -->
```bash
mkdir -p "${CLAUDE_CONFIG_DIR:-$HOME/.claude}"/skills/{slug}-{name}
# Write SKILL.md
```
<!-- /CC-ONLY -->
<!-- CODEX-START
```bash
mkdir -p ~/.agents/skills/{slug}-{name}
# Write SKILL.md
```
CODEX-END -->

If a global skill should ship to both agents or other users, promote it through Pilot's skill library rather than maintaining two user-level copies by hand.

Edit the created `SKILL.md` with the template from Step 1.

**Cross-agent portability checklist:**

- Describe capabilities (read files, search text, execute commands, launch a bounded agent) rather than assuming one tool namespace or parameter schema.
- Prefer common shell commands and repository-relative paths when exact execution is needed.
- Provide a capability-based fallback for optional agent, browser, and web tools.
- Avoid Claude-only or Codex-only instructions in a project skill. If behavior must differ, key it to an observable capability in the current session.
- Never reference Pilot-only services such as Semble or Pilot MCP servers unless the skill declares them as prerequisites and has a portable fallback.
- Keep `targets: [claude, codex]` when both agents are supported; narrow it only when the workflow truly cannot run on one target.
- Rely on Pilot's shared hook for normal synchronization. Keep manual `--write` as recovery, not a required authoring step.

**Determinism checklist:**

- Use exact, scoped commands when their form matters; avoid a whole-repository formatter for a local edit
- Prefer scripts over multi-step instructions (reference `scripts/deploy.sh` not five prose steps)
- Use explicit values over judgment (`block files > 100KB` not "block large files")
- For high-risk operations: include exact commands, validation steps, and rollback plan
- For low-risk work: use general guidelines and let the agent apply judgment

**One skill = one purpose.** Split review, testing, and deployment when they are independent workflows.

**Security:** Skills must not contain malware, exploit code, credentials, or surprising data access. Use environment variables for secrets.
