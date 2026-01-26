---
name: skill-creator
description: Guide for creating effective Claude Code skills. Use when users want to create a new skill or update an existing skill that extends Claude's capabilities with specialized knowledge, workflows, or tool integrations. Triggers on requests like "create a skill for X", "help me build a skill", "add a new skill", or "update the X skill".
---

# Skill Creator

Create effective skills that extend Claude's capabilities with specialized knowledge, workflows, and tools.

## What Skills Provide

1. **Specialized workflows** - Multi-step procedures for specific domains
2. **Tool integrations** - Instructions for working with specific file formats or APIs
3. **Domain expertise** - Company-specific knowledge, schemas, business logic
4. **Bundled resources** - Scripts, references, and assets for complex tasks

## Core Principles

### Concise is Key

The context window is shared with system prompt, conversation history, and user requests.

**Default assumption: Claude is already very smart.** Only add context Claude doesn't already have. Challenge each piece: "Does Claude really need this?" and "Does this justify its token cost?"

Prefer concise examples over verbose explanations.

### Set Appropriate Degrees of Freedom

Match specificity to task fragility:

| Freedom Level | When to Use | Format |
|---------------|-------------|--------|
| **High** | Multiple approaches valid, context-dependent | Text instructions |
| **Medium** | Preferred pattern exists, some variation OK | Pseudocode/scripts with params |
| **Low** | Fragile operations, consistency critical | Specific scripts, few params |

### Skill Anatomy

```
skill-name/
├── SKILL.md (required)
│   ├── YAML frontmatter (name, description)
│   └── Markdown instructions
└── Bundled Resources (optional)
    ├── scripts/      - Executable code
    ├── references/   - Documentation loaded as needed
    └── assets/       - Files used in output (templates, etc.)
```

#### SKILL.md Structure

- **Frontmatter (YAML)**: `name` and `description` fields - these determine when the skill triggers
- **Body (Markdown)**: Instructions loaded AFTER the skill triggers

#### Bundled Resources

| Type | Purpose | When to Include |
|------|---------|-----------------|
| `scripts/` | Deterministic, reusable code | Same code rewritten repeatedly |
| `references/` | Documentation loaded as needed | Large docs Claude should reference while working |
| `assets/` | Files used in output (not loaded into context) | Templates, images, boilerplate |

**Do NOT include**: README.md, CHANGELOG.md, INSTALLATION_GUIDE.md, or other auxiliary docs.

### Progressive Disclosure

Three-level loading system:

1. **Metadata** (name + description) - Always in context (~100 words)
2. **SKILL.md body** - When skill triggers (<5k words, ideally <500 lines)
3. **Bundled resources** - As needed by Claude

**Pattern: Domain-specific organization**

```
bigquery-skill/
├── SKILL.md (overview + navigation)
└── references/
    ├── finance.md
    ├── sales.md
    └── product.md
```

Claude loads only the relevant reference file.

## Skill Creation Process

### Step 1: Understand with Examples

Ask clarifying questions:
- "What functionality should this skill support?"
- "Can you give examples of how it would be used?"
- "What would trigger this skill?"

### Step 2: Plan Reusable Contents

For each example, identify:
1. What scripts would help (repeated code)
2. What references would help (schemas, docs)
3. What assets would help (templates, boilerplate)

### Step 3: Create the Skill

Create the skill directory in `.claude/skills/`:

```bash
mkdir -p .claude/skills/my-skill-name
```

**Naming Convention:**
- Standard skills: `plan`, `implement`, `verify`, `standards-*` (overwritten on install)
- Custom skills: Any other name (preserved during updates)

For project-specific skills, use a unique name that doesn't match standard patterns.

### Step 4: Write SKILL.md

#### Frontmatter

```yaml
---
name: skill-name
description: What the skill does AND when to use it. Include all trigger contexts here since the body is only loaded after triggering.
---
```

**Description guidelines:**
- Include both what it does AND specific triggers/contexts
- All "when to use" info goes here, not in the body
- Example: "PDF processing for rotation, merging, text extraction. Use when working with .pdf files for editing, combining, or extracting content."

#### Body

Write concise instructions:
- Use imperative/infinitive form
- Keep under 500 lines
- Reference bundled resources with clear "when to read" guidance
- Move detailed docs to `references/` files

### Step 5: Test and Iterate

1. Use the skill on real tasks
2. Notice struggles or inefficiencies
3. Update SKILL.md or bundled resources
4. Test again

## Writing Guidelines

### Good Patterns

```markdown
## Quick Start

Extract text with pdfplumber:
[concise code example]

## Advanced Features

- **Form filling**: See [references/forms.md](references/forms.md)
- **API reference**: See [references/api.md](references/api.md)
```

### Avoid

- Deeply nested references (keep one level deep)
- Duplicating info between SKILL.md and references
- Verbose explanations when examples suffice
- "When to Use" sections in the body (put in description)

## Checklist

Before finalizing:

- [ ] Frontmatter has `name` and comprehensive `description`
- [ ] Description includes trigger contexts
- [ ] Body is under 500 lines
- [ ] References exist for large documentation
- [ ] Scripts are tested and working
- [ ] No unnecessary auxiliary files (README, CHANGELOG, etc.)
- [ ] Skill name follows convention (custom = unique name, standard = `standards-*`)
