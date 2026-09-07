## Step 1: Reference

### What belongs in a skill

Capture reusable knowledge that changes the agent's decisions: project conventions, non-obvious tool contracts, domain constraints, or a workflow the user wants repeated. Assume the agent already knows general coding and writing practices.

State the outcome and real boundaries. Reserve fixed sequences and exact commands for fragile operations, data integrity, or permissions. Leave routine implementation choices to the agent; do not add generic verification loops, motivational wording, or a new prohibition for every past mistake.

### Scope and ownership

Respect the user's chosen name and location. Otherwise prefer a project skill under `.agents/skills/<name>/` for repository-specific work. Use a project prefix when it prevents collisions; a globally reusable skill does not need the current repository's name.

| Scope | Canonical location | Distribution |
|---|---|---|
| Project | `.agents/skills/<name>/` | Pilot synchronizes the complete tree with `.claude/skills/<name>/` |
<!-- CC-ONLY -->
| Local Claude Code | `${CLAUDE_CONFIG_DIR:-$HOME/.claude}/skills/<name>/` | Outside repository sync |
<!-- /CC-ONLY -->
<!-- CODEX-START
| Local Codex | `~/.agents/skills/<name>/` | Outside repository sync |
CODEX-END -->
| Pilot distribution | The skill library's canonical source | Build and verify both agent artifacts |

Keep repository-wide guidance in `AGENTS.md`. Preserve user-owned and ignored extensions and any independent edits on both sides of a synchronization conflict.

### Skill structure

A skill needs `SKILL.md`; add resources only when they support its work:

```text
skill-name/
  SKILL.md
  scripts/       # deterministic or repeated operations
  references/    # conditional detail loaded when relevant
  assets/        # files used in the deliverable
```

Keep the entrypoint short enough to scan. Link larger conditional procedures with an explanation of when to read them. Avoid mandatory empty sections, boilerplate documentation, or fixed word/line quotas.

### Frontmatter and invocation

Use a lowercase kebab-case name matching the folder and a concise description of what the skill does and when to use it. Preserve supported metadata and existing invocation policy.

```yaml
---
name: example-workflow
description: Produce the project's release evidence from an identified candidate build. Use when preparing or reviewing a release candidate.
targets: [claude, codex]
metadata:
  category: release
---
```

Use only fields supported by the target runtime or Pilot's documented packaging contract. Agent-specific discovery policy and tool permissions are not interchangeable: a callable skill can still require authorization immediately before a particular mutation.

Explicit-only Pilot workflows retain their existing explicit-invocation policy. For newly authored skills, choose invocation behavior from the user's intended workflow; do not make every skill explicit-only merely because one step has side effects.

### Description quality

Describe the capability and its relevant trigger, with an exclusion only when it prevents a plausible wrong match. Avoid keyword catchalls that attract adjacent work. Examples should clarify distinct use cases, not repeat synonyms for the same trigger.

A description is a discovery aid. The body holds the operational contract. Do not overload discovery text with the full ordered procedure.

### Writing useful instructions

- State what success looks like and which evidence proves it.
- Preserve user scope, prior decisions, and authorization. Do not redirect an ordinary task into additional workflows or unrelated configuration changes.
- Explain non-obvious constraints where the model needs them.
- Use the current runtime's exposed tools and schemas, with capability-based fallbacks for optional tools.
- Include concrete commands when their exact form matters; scope mutations to the intended resources.
- Distinguish required steps from recommendations and conditional detail. Real exceptions belong beside the requirement they qualify.
- Keep one authoritative statement per contract. Reference it from dependent steps instead of repeating slightly different versions.
- Remove instructions that do not improve decisions or output. Prefer demonstrated behavioral corrections over model-generation folklore.

### Portability and validation

Verify the artifact each supported agent actually consumes, including metadata, progressive references, scripts, and generated mirrors. Source similarity alone does not prove installed behavior.

Validate structure and referenced resources, then use realistic execution cases when the skill's complexity or risk warrants them. Keep model, prompt, tools, and fixture state comparable when evaluating before/after behavior. Test exact contracts, scope preservation, and observable outcomes rather than whether the agent repeats the instructions.
