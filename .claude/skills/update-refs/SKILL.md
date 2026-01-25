---
name: update-refs
description: Update naming and documentation references across the Claude CodePro codebase. Use when renaming features, updating descriptions, changing terminology, or ensuring consistency after modifying commands, skills, or workflows. Triggers on "update references", "rename X to Y across codebase", "sync documentation", or "update all mentions of X".
---

# Update References

Ensure naming and documentation consistency across all codebase locations.

## Checklist

When updating terminology, feature names, or descriptions, check ALL locations:

### 1. User-Facing Messages

| Location | What to Check |
|----------|---------------|
| `ccp/banner.py` | Welcome banner text, feature descriptions |
| `ccp/cli.py` | CCP CLI help text and messages |
| `installer/cli.py` | Installer CLI help text, prompts |
| `installer/steps/finalize.py` | Post-install instructions |
| `installer/ui.py` | UI banner and status messages |

### 2. Documentation & Site

| Location | What to Check |
|----------|---------------|
| `README.md` | Feature descriptions, usage examples, quick start |
| `docs/site/index.html` | SEO meta tags, page title, descriptions |
| `docs/site/src/components/*.tsx` | Marketing site content (WhatsInside, etc.) |

### 3. Package & Install

| Location | What to Check |
|----------|---------------|
| `pyproject.toml` | Package name, description, metadata |
| `install.sh` | Shell installer script messages |
| `ccp/__init__.py` | Package docstring |

### 4. Claude Configuration

| Location | What to Check |
|----------|---------------|
| `.claude/commands/*.md` | Command descriptions in frontmatter |
| `.claude/skills/*/SKILL.md` | Skill descriptions in frontmatter |
| `.claude/rules/standard/*.md` | Rule references to features |
| `.claude/rules/custom/*.md` | Project-specific rule content |
| `.claude/hooks/*.py` | Hook script messages |

### 5. Bundled Installer Copy

| Location | What to Check |
|----------|---------------|
| `.claude/installer/installer/*.py` | Bundled installer copy (mirrors installer/) |

## Workflow

1. **Search first** - Use grep to find all occurrences:
   ```bash
   grep -r "old term" --include="*.md" --include="*.py" --include="*.tsx" .
   ```

2. **Update systematically** - Work through checklist above

3. **Verify consistency** - Search again to confirm no misses:
   ```bash
   grep -r "old term" . | grep -v node_modules | grep -v .git
   ```

## Common Updates

| Change Type | Key Locations |
|-------------|---------------|
| Command rename | commands/*.md, README.md, banner.py, rules/*.md |
| Skill rename | skills/*/SKILL.md, README.md, WhatsInside.tsx |
| Feature description | banner.py, README.md, site components, index.html |
| Workflow change | commands/*.md, rules/*.md, README.md |
| Package rename | pyproject.toml, install.sh, ccp/__init__.py, README.md |
| Installer message | installer/*.py, .claude/installer/installer/*.py |
