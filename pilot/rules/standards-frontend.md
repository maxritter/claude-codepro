---
paths:
  - "**/*.tsx"
  - "**/*.jsx"
  - "**/*.html"
  - "**/*.vue"
  - "**/*.svelte"
  - "**/*.razor"
  - "**/*.css"
  - "**/*.scss"
  - "**/*.sass"
  - "**/*.less"
  - "**/*.module.css"
  - "**/*.razor.css"
---

# Frontend Standards

## Components

Use the existing component system and separate responsibilities when that improves comprehension, reuse, or state ownership.

- **Props:** Define clear contracts; defaults belong to optional values and should not conceal missing required input. Prop counts do not determine component quality.
- **State:** Keep ownership near its consumers. Use composition, shared state, or context when actual sharing and lifecycle needs warrant it.
- **Naming:** Follow the framework and project's conventions.
- **Boundaries:** Split for coherent responsibilities and useful reuse, not a global line-count or nesting-depth quota.

## CSS

Follow the project's established styling system, including intentional combinations of utilities, component styles, and scoped/global CSS.

- Use design tokens (`var(--color-primary)`) over hardcoded values
- Understand specificity and cascade layers before adding overrides. Use `!important` only for a concrete need, not as a substitute for finding the conflicting rule.
- Add custom CSS where it is appropriate for that system; do not introduce a new styling dependency incidentally.

## Accessibility

- **Semantic HTML first:** `<button>` for actions, `<a>` for navigation, landmarks (`<nav>`/`<main>`/`<header>`)
- **Keyboard:** Tab navigates, Enter/Space activates, Escape closes. Visible focus indicators always.
- **Labels:** Every input needs a label. `aria-label` for icon-only buttons.
- **Images:** Informative: descriptive alt text. Decorative: `alt=""`
- **Color contrast — verify, never eyeball:** Body/label text needs 4.5:1 against its *actual* background; large text (at least 18 point regular or 14 point bold) needs 3:1; meaningful non-text UI boundaries and states need 3:1. Re-check tokens on every surface and supported theme. Button-label text is measured against the button fill. Never convey information by color alone. (`impeccable detect` flags many candidates; compute exact ratios.)
- **ARIA:** Semantic HTML first, ARIA second. `aria-live="polite"` for dynamic content.
- **Headings:** Use a coherent hierarchy and do not skip levels merely for visual sizing. Give the page a clear primary heading; multiple sectioning roots are not automatically an accessibility failure.

## Responsive Design

**Follow the project's breakpoint strategy.** For a new layout with no established approach, start from the narrowest supported viewport and add content-driven `min-width` breakpoints.

- **Fluid layouts:** `width: 100%` + `max-width`, grid with `1fr`/`minmax()`/`auto-fit`
- **Units:** Prefer `rem` for scalable spacing and type, `em` for component-relative values, `ch` for readable text widths, and `px` where fixed device-independent CSS pixels are intentional.
- **Pointer targets:** Meet WCAG 2.2 AA's 24×24 CSS-pixel minimum or its spacing exception. On touch-first product surfaces, follow the platform's larger target guidance (commonly 44×44 on iOS and 48×48 on Android).
- **Typography:** Use the product's readable type scale and spacing. Verify zoom/text resizing and reflow; fixed font-size or line-height recipes do not prove accessibility.
- **Images:** Use `srcset` and `sizes`

## Performance

- **Expensive work:** Identify actual render/update costs before adding memoization. Account for compiler/framework optimizations, invalidation, and memory overhead.
- **Re-renders:** Isolate costly unrelated updates when profiling or the code path shows a problem. Do not wrap every component in memoization mechanically.
- **Minimize dependency weight:** Import only what you use. Full library imports where tree-shaken alternatives exist waste bandwidth and parse time.
- **Polling:** Avoid unnecessary expensive work and overlapping requests. Handle cancellation and stale responses where the interaction requires them.

## Checklist

- [ ] Components: single responsibility, typed props, local state
- [ ] CSS: project methodology, design tokens, deliberate cascade
- [ ] Accessible: keyboard, labels, alt text, and applicable WCAG contrast ratios verified on every surface and theme
- [ ] Responsive: follows project breakpoints, remains fluid, and meets pointer-target requirements
- [ ] Performance: relevant expensive paths checked, dependency weight justified, stale/overlapping updates handled
- [ ] Design: user-visible changes also satisfy Open Claude Design's `open-claude-design-quality` skill
