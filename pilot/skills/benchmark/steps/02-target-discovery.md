# Step 2 — Target discovery

Determine the target's type (`skill` or `rules`) and its path.

## Decide the type

| User's artifact | Target type |
|-----------------|-------------|
| A skill directory (contains `SKILL.md`) | `skill` |
| A single rule file (`.md`) | `rules` |
| A directory of rule files (no `SKILL.md`) | `rules` |
| A skill that the user wants to benchmark "as a workflow" | Still `skill` — present vs absent is the right baseline |

When in doubt, ask: "Is this a reusable skill (has `SKILL.md`) or a rule pack (plain `.md` files)?"

## Resolve the path

- Prefer repo-relative paths (`pilot/skills/create-skill`) over absolute paths — makes `evals.json` portable.
- Validate the path exists before advancing. If it doesn't, ask the user for the correct location.

## List candidates when needed

If the user can't remember exact names, list them:

```bash
<!-- CC-ONLY -->
# Skills in this project
ls -1 pilot/skills/ "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/skills/"

# Rules in this project
ls -1 pilot/rules/ "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/rules/"
<!-- /CC-ONLY -->
<!-- CODEX-START
# Skills in this project
ls -1 pilot/skills/ .agents/skills/ ~/.agents/skills/ 2>/dev/null

# Rules in this project
ls -1 pilot/rules/ .claude/rules/ 2>/dev/null
# Codex project rules are materialized from repo-root AGENTS.md when benchmarking.
CODEX-END -->
```

Skip internal workflow phases unless the user specifically asks for them.

## Emit the target block

Once resolved, write to the in-memory state:

```json
{
  "type": "skill | rules",
  "path": "pilot/skills/create-skill",
  "name": "create-skill"
}
```

The `name` field (optional) is used for the output directory name under `benchmarks/`. Default to the basename of `path` if the user didn't specify.

## Exit

Go to Step 3 (author evals).
