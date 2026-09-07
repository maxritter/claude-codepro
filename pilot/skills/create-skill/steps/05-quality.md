## Step 5: Quality Gates

### Structure Checklist

- [ ] Folder named in kebab-case
- [ ] `SKILL.md` file exists (exact spelling, case-sensitive)
- [ ] YAML frontmatter has `---` delimiters
- [ ] `name` field: kebab-case, no spaces, no capitals, matches folder name
- [ ] `description` includes WHAT and WHEN (under 1024 chars, no XML tags)
- [ ] Every bundled file serves the workflow; lengthy conditional detail is linked from the entrypoint
- [ ] The editable project source exists only under `.agents/skills/<name>/`; `.claude/skills/<name>/` was generated, not hand-edited

### Content Checklist

- [ ] Instructions are clear and actionable (commands > descriptions)
- [ ] Non-obvious failure handling, examples, and exclusions are included where they materially clarify the workflow
- [ ] Verification step (how to confirm it worked)
- [ ] No sensitive information (API keys, passwords → use env vars)
- [ ] No hardcoded paths (use relative paths or environment variables)
- [ ] References clearly linked (to `references/` or external docs)
- [ ] Steps (when the skill has them) end on a checkable completion criterion (agent can tell done from not-done)
- [ ] Description carries one trigger per distinct branch — no synonym restatements
- [ ] Sentence-level no-op scan done (each sentence changes behavior vs. the default, or it's deleted)
- [ ] Project skill wording works under both Claude Code and Codex capabilities, or `targets` is intentionally narrowed

### Synchronization Gate — PROJECT SKILLS

After the final canonical edit, verify the repository's configured synchronization contract. When this checker is installed, run:

```bash
node scripts/sync-agent-assets.mjs --check
```

If drift remains, repair the intended skill copy or hook installation, use `node scripts/sync-agent-assets.mjs --write` once for recovery, and rerun `--check`. Record both skill paths and the zero exit status. Verify the check itself leaves the worktree unchanged. A project skill is not complete while the checker reports drift.

### Triggering Test

Before finalizing, verify the description will activate correctly:

```
Should trigger:
- "[exact phrases a user would say]"
- "[paraphrased version of the request]"
- "[related but different phrasing]"

Should NOT trigger:
- "[unrelated topic that sounds similar]"
- "[general request the skill shouldn't handle]"
```

**Execution check:** when discovery changed, observe actual selection in the target runtime for representative requests and near-misses. A paraphrase of the description does not prove triggering behavior.
