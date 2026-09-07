---
name: create-skill
description: Create, edit, synchronize, and test a reusable skill future agents can find and follow. Use when the user types /create-skill, asks to make, write, add, or extract a skill, wants a repeatable workflow or technique from this session captured for reuse, asks to change an existing skill's steps, description, or trigger keywords, or needs one project skill to work in both Claude Code and Codex.
user-invocable: true
---

# /create-skill — Skill Creator

**Create a reusable skill.** Provide a topic or workflow description, and this command explores the codebase, gathers relevant patterns, and builds a well-structured skill interactively with you. For tracked project skills, prefer `.agents/skills/`; Pilot's shared hook synchronizes `.agents/skills/` and `.claude/skills/` after supported edits from either agent and at Stop as a Code Mode backstop. If no topic is given, it evaluates the current session for extractable knowledge.

## Editing existing skills

For new or behavior-changing skills, validate structure, references, invocation boundaries, and affected behavior. Use Step 6's isolated execution comparison when the workflow is complex, risky, or a demonstrated behavior failure needs measurement. Cosmetic edits need only the checks they can affect.

Preserve existing invocation policy and user-owned resources. Scale evaluation to the change; a wording edit does not automatically require a multi-agent benchmark.

When uncertain, identify the behavior at risk and verify that behavior.
