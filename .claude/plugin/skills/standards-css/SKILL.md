---
name: CSS Standards
description: Write consistent, maintainable CSS following the project's methodology (Tailwind, BEM, utility classes, CSS modules) with design system adherence and performance optimization. Use this skill when writing or modifying styles, CSS files, utility classes, CSS-in-JS, styled components, or any styling code. Apply when working with .css, .scss, .module.css files, Tailwind utility classes, styled-components, CSS modules, design tokens (colors, spacing, typography), framework-specific styling approaches, optimizing CSS for production, implementing CSS purging or tree-shaking, or avoiding style overrides. Use for any task involving visual styling, layout styling, design system implementation, or CSS organization.
---

# CSS Standards

**Rule:** Follow project CSS methodology consistently, leverage framework patterns, maintain design system tokens.

## When to use this skill

- When writing or modifying CSS files (.css, .scss, .sass, .less, .module.css)
- When applying utility classes in Tailwind CSS or similar utility-first frameworks
- When implementing CSS-in-JS or styled-components in React/Vue/Svelte components
- When defining or using design tokens (colors, spacing, typography, shadows)
- When maintaining consistency with the project's CSS methodology (BEM, OOCSS, SMACSS, utility-first)
- When optimizing CSS for production with purging or tree-shaking unused styles
- When avoiding excessive framework style overrides by working with framework patterns
- When implementing global styles or theme configurations
- When refactoring inline styles or scattered CSS into organized, maintainable patterns
- When establishing or following CSS naming conventions for the project

This Skill provides Claude Code with specific guidance on how to adhere to coding standards as they relate to how it should handle frontend CSS.

## Identify Project Methodology First

Before writing any styles, check existing codebase for:

**Utility-first (Tailwind/UnoCSS):**
```jsx
<div className="flex items-center gap-4 p-6 bg-white rounded-lg shadow-md">
```

**CSS Modules:**
```jsx
import styles from './Component.module.css'
<div className={styles.container}>
```

**BEM (Block Element Modifier):**
```css
.card { }
.card__header { }
.card__header--highlighted { }
```

**CSS-in-JS (styled-components/emotion):**
```jsx
const Button = styled.button`
  padding: 1rem;
  background: ${props => props.theme.primary};
`
```

**Once identified, use that methodology exclusively. Never mix methodologies.**

## Design System Tokens

**Always use design tokens instead of hardcoded values:**

Bad:
```css
color: #3b82f6;
padding: 16px;
font-size: 14px;
```

Good (Tailwind):
```jsx
className="text-blue-500 p-4 text-sm"
```

Good (CSS variables):
```css
color: var(--color-primary);
padding: var(--spacing-4);
font-size: var(--text-sm);
```

**Check for existing tokens before creating new ones:**
1. Search for color/spacing/typography definitions
2. Use existing tokens if available
3. Only create new tokens if genuinely needed
4. Document new tokens in design system file

## Framework Patterns Over Overrides

**Work with framework, not against it:**

Bad (fighting Tailwind):
```jsx
<div className="flex items-center" style={{gap: '17px', padding: '13px'}}>
```

Good (using framework values):
```jsx
<div className="flex items-center gap-4 p-3">
```

Bad (overriding component library):
```css
.MuiButton-root {
  padding: 12px !important;
  background: red !important;
}
```

Good (using component API):
```jsx
<Button sx={{ padding: 3, bgcolor: 'error.main' }}>
```

**If you need `!important` or deep style overrides, reconsider your approach.**

## Minimize Custom CSS

**Prefer framework utilities over custom CSS:**

Bad:
```css
.custom-card {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  padding: 1.5rem;
  background: white;
  border-radius: 0.5rem;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}
```

Good (Tailwind):
```jsx
<div className="flex flex-col gap-4 p-6 bg-white rounded-lg shadow-sm">
```

**Only write custom CSS for:**
- Complex animations
- Unique visual effects not in framework
- Third-party library integration
- Browser-specific fixes

## Naming Conventions

**Follow project convention consistently:**

BEM:
```css
.block-name { }
.block-name__element { }
.block-name--modifier { }
```

CSS Modules (camelCase):
```css
.cardContainer { }
.cardHeader { }
.isActive { }
```

Utility-first (descriptive class names for custom components):
```css
.prose-headings { }
.custom-scrollbar { }
```

## Organization Patterns

**Structure CSS logically:**

```css
/* 1. Layout */
.component {
  display: flex;
  position: relative;
}

/* 2. Box model */
.component {
  width: 100%;
  padding: 1rem;
  margin: 0 auto;
}

/* 3. Typography */
.component {
  font-size: 1rem;
  line-height: 1.5;
}

/* 4. Visual */
.component {
  color: var(--text-primary);
  background: var(--bg-surface);
  border-radius: 0.5rem;
}

/* 5. Misc */
.component {
  cursor: pointer;
  transition: all 0.2s;
}
```

**Group related styles, separate concerns with comments.**

## Performance Optimization

**Production CSS should be optimized:**

Tailwind (purge unused):
```js
// tailwind.config.js
module.exports = {
  content: ['./src/**/*.{js,jsx,ts,tsx}'],
  // Only includes classes actually used
}
```

CSS Modules (automatic tree-shaking):
```js
// Unused styles automatically removed in production
```

**Avoid:**
- Importing entire CSS frameworks when using few components
- Duplicate style definitions across files
- Overly specific selectors (`.a .b .c .d .e`)
- Large inline styles that could be extracted

## Common Mistakes

**Mixing methodologies:**
```jsx
// BAD - mixing Tailwind with inline styles and CSS modules
<div className={`${styles.card} flex p-4`} style={{gap: '12px'}}>
```

**Hardcoding values:**
```css
/* BAD */
color: #3b82f6;
padding: 17px;

/* GOOD */
color: var(--color-primary);
padding: var(--spacing-4);
```

**Fighting framework:**
```css
/* BAD */
.override {
  margin: 13px !important;
}

/* GOOD - use framework's spacing scale */
className="m-3"
```

## Verification Checklist

Before completing CSS work:

- [ ] Identified and followed project CSS methodology
- [ ] Used design tokens instead of hardcoded values
- [ ] Leveraged framework utilities where possible
- [ ] Avoided `!important` and deep overrides
- [ ] Followed project naming conventions
- [ ] Organized styles logically
- [ ] Verified no unused styles in production build
- [ ] Tested visual output in browser

## Quick Reference

| Situation                      | Action                                |
| ------------------------------ | ------------------------------------- |
| New component styling          | Check existing patterns first         |
| Need specific color            | Use design token, not hex code        |
| Framework doesn't have utility | Write minimal custom CSS              |
| Styles not applying            | Check specificity, avoid `!important` |
| Large CSS file                 | Extract to utilities or components    |
| Production bundle large        | Enable CSS purging/tree-shaking       |
