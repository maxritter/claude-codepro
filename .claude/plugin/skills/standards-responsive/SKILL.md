---
name: Responsive Design Standards
description: Build responsive, mobile-first layouts using fluid containers, flexible units, media queries, and touch-friendly design that works across all screen sizes. Use this skill when creating or modifying UI layouts, responsive grids, breakpoint styles, mobile navigation, or any interface that needs to adapt to different screen sizes. Apply when working with responsive CSS, media queries, viewport settings, flexbox/grid layouts, mobile-first styling, breakpoint definitions (mobile, tablet, desktop), touch target sizing, relative units (rem, em, %), image optimization for different screens, or testing layouts across multiple devices. Use for any task involving multi-device support, responsive design patterns, or adaptive layouts.
---

# Responsive Design Standards

**Rule:** Mobile-first development with consistent breakpoints, fluid layouts, relative units, and touch-friendly targets.

## When to use this skill

- When creating or modifying layouts that need to work on mobile, tablet, and desktop
- When implementing mobile-first design patterns starting with mobile layout
- When writing media queries or breakpoint-specific styles
- When using flexible units (rem, em, %) instead of fixed pixels for scalability
- When implementing fluid layouts with percentage-based widths or flexbox/grid
- When ensuring touch targets meet minimum size requirements (44x44px) for mobile
- When optimizing images and assets for different screen sizes and mobile networks
- When testing UI across multiple device sizes and breakpoints
- When maintaining readable typography across all screen sizes
- When prioritizing content display on smaller screens through layout decisions
- When using responsive design utilities in CSS frameworks (Tailwind, Bootstrap responsive classes)

This Skill provides Claude Code with specific guidance on how to adhere to coding standards as they relate to how it should handle frontend responsive.

## Mobile-First Development - Mandatory

**Always start with mobile layout, then enhance for larger screens.**

Bad (desktop-first):
```css
.container {
  width: 1200px;
  display: grid;
  grid-template-columns: repeat(4, 1fr);
}

@media (max-width: 768px) {
  .container {
    width: 100%;
    grid-template-columns: 1fr;
  }
}
```

Good (mobile-first):
```css
.container {
  width: 100%;
  display: grid;
  grid-template-columns: 1fr;
}

@media (min-width: 768px) {
  .container {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (min-width: 1024px) {
  .container {
    max-width: 1200px;
    grid-template-columns: repeat(4, 1fr);
  }
}
```

**Why mobile-first:**
- Forces content prioritization
- Better performance on mobile (no overriding)
- Progressive enhancement over graceful degradation

## Standard Breakpoints

**Identify and use project breakpoints consistently:**

Common breakpoint systems:

Tailwind:
```
sm: 640px   (small tablets)
md: 768px   (tablets)
lg: 1024px  (laptops)
xl: 1280px  (desktops)
2xl: 1536px (large desktops)
```

Bootstrap:
```
sm: 576px
md: 768px
lg: 992px
xl: 1200px
xxl: 1400px
```

**Check existing codebase for breakpoint definitions before creating new ones.**

Usage (Tailwind):
```jsx
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4">
```

Usage (CSS):
```css
@media (min-width: 768px) { }
@media (min-width: 1024px) { }
```

**Never use arbitrary breakpoints like 850px or 1150px unless explicitly required.**

## Fluid Layouts

**Use flexible containers that adapt to screen size:**

Bad (fixed widths):
```css
.container { width: 1200px; }
.sidebar { width: 300px; }
.content { width: 900px; }
```

Good (fluid):
```css
.container {
  width: 100%;
  max-width: 1200px;
  padding: 0 1rem;
}

.layout {
  display: grid;
  grid-template-columns: 1fr;
}

@media (min-width: 1024px) {
  .layout {
    grid-template-columns: 300px 1fr;
  }
}
```

**Patterns for fluid layouts:**
- Flexbox: `flex: 1`, `flex-grow`, `flex-shrink`
- Grid: `1fr`, `minmax()`, `auto-fit`, `auto-fill`
- Percentage widths: `width: 100%`, `max-width: 1200px`
- Container queries (modern): `@container (min-width: 400px)`

## Relative Units Over Fixed Pixels

**Use rem/em for scalability and accessibility:**

Bad:
```css
font-size: 16px;
padding: 20px;
margin: 10px;
border-radius: 8px;
```

Good:
```css
font-size: 1rem;      /* 16px base */
padding: 1.25rem;     /* 20px */
margin: 0.625rem;     /* 10px */
border-radius: 0.5rem; /* 8px */
```

**When to use each unit:**
- `rem`: Font sizes, spacing, layout dimensions (scales with root font size)
- `em`: Component-relative sizing (scales with parent font size)
- `%`: Widths, heights relative to parent
- `px`: Borders (1px), shadows, very small values
- `vw/vh`: Full viewport dimensions, hero sections
- `ch`: Text-based widths (e.g., `max-width: 65ch` for readable line length)

**Framework utilities handle this automatically:**
```jsx
<div className="text-base p-5 m-2.5 rounded-lg">
```

## Touch-Friendly Design

**Minimum touch target size: 44x44px (iOS) / 48x48px (Android)**

Bad:
```css
.icon-button {
  width: 24px;
  height: 24px;
}
```

Good:
```css
.icon-button {
  width: 24px;
  height: 24px;
  padding: 12px; /* Total: 48x48px */
  /* Or use min-width/min-height */
  min-width: 44px;
  min-height: 44px;
}
```

**Touch target checklist:**
- [ ] Buttons minimum 44x44px
- [ ] Links in text have adequate spacing
- [ ] Form inputs have sufficient height (min 44px)
- [ ] Icon buttons have padding for larger hit area
- [ ] Spacing between interactive elements (min 8px)

## Readable Typography

**Maintain readable font sizes without zoom:**

Bad:
```css
body { font-size: 12px; }
.small-text { font-size: 10px; }
```

Good:
```css
body { font-size: 1rem; } /* 16px minimum */
.small-text { font-size: 0.875rem; } /* 14px minimum */
```

**Typography guidelines:**
- Body text: 16px (1rem) minimum
- Small text: 14px (0.875rem) minimum
- Line height: 1.5 for body, 1.2 for headings
- Line length: 45-75 characters (use `max-width: 65ch`)
- Contrast: WCAG AA minimum (4.5:1 for normal text)

Responsive typography:
```css
h1 {
  font-size: 2rem;
}

@media (min-width: 768px) {
  h1 {
    font-size: 2.5rem;
  }
}

@media (min-width: 1024px) {
  h1 {
    font-size: 3rem;
  }
}
```

Or with clamp (fluid):
```css
h1 {
  font-size: clamp(2rem, 5vw, 3rem);
}
```

## Content Priority on Mobile

**Show most important content first, hide or collapse secondary content:**

Bad:
```jsx
<div>
  <Sidebar /> {/* Full sidebar on mobile */}
  <MainContent />
</div>
```

Good:
```jsx
<div className="flex flex-col lg:flex-row">
  <MainContent className="order-1" />
  <Sidebar className="order-2 hidden lg:block" />
</div>
```

**Strategies:**
- Hide non-essential elements on mobile
- Use hamburger menus for navigation
- Collapse accordions/tabs for secondary content
- Stack layouts vertically on mobile
- Use `order` property to reorder content

## Image Optimization

**Serve appropriate images for device size:**

Bad:
```html
<img src="hero-4000x3000.jpg" alt="Hero">
```

Good:
```html
<img
  src="hero-800x600.jpg"
  srcset="
    hero-400x300.jpg 400w,
    hero-800x600.jpg 800w,
    hero-1600x1200.jpg 1600w
  "
  sizes="(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 800px"
  alt="Hero"
>
```

Or with modern formats:
```html
<picture>
  <source srcset="hero.avif" type="image/avif">
  <source srcset="hero.webp" type="image/webp">
  <img src="hero.jpg" alt="Hero">
</picture>
```

**Framework-specific:**
```jsx
// Next.js
<Image
  src="/hero.jpg"
  width={800}
  height={600}
  sizes="(max-width: 768px) 100vw, 50vw"
  alt="Hero"
/>
```

## Testing Across Devices

**Verify layouts at key breakpoints before completing work:**

Test checklist:
- [ ] Mobile (375px - iPhone SE)
- [ ] Mobile large (414px - iPhone Pro Max)
- [ ] Tablet (768px - iPad)
- [ ] Laptop (1024px)
- [ ] Desktop (1440px)

**Testing methods:**
1. Browser DevTools responsive mode
2. Real device testing (iOS/Android)
3. Browser extensions (Responsive Viewer)
4. Automated visual regression tests

**Common issues to check:**
- Horizontal scrolling on mobile
- Text overflow or truncation
- Overlapping elements
- Unreadable font sizes
- Touch targets too small
- Images not loading or distorted

## Common Responsive Patterns

**Navigation:**
```jsx
// Mobile: Hamburger menu
// Desktop: Horizontal nav
<nav className="lg:flex lg:items-center">
  <button className="lg:hidden">Menu</button>
  <ul className="hidden lg:flex lg:gap-4">
    <li>Home</li>
    <li>About</li>
  </ul>
</nav>
```

**Grid layouts:**
```css
.grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 1rem;
}

@media (min-width: 640px) {
  .grid { grid-template-columns: repeat(2, 1fr); }
}

@media (min-width: 1024px) {
  .grid { grid-template-columns: repeat(4, 1fr); }
}
```

**Sidebar layouts:**
```css
.layout {
  display: flex;
  flex-direction: column;
}

@media (min-width: 1024px) {
  .layout {
    flex-direction: row;
  }
  .sidebar { width: 300px; }
  .content { flex: 1; }
}
```

## Verification Checklist

Before completing responsive work:

- [ ] Started with mobile layout
- [ ] Used project's standard breakpoints
- [ ] Implemented fluid layouts (no fixed widths)
- [ ] Used relative units (rem/em) for sizing
- [ ] Touch targets minimum 44x44px
- [ ] Typography readable without zoom (16px+ body)
- [ ] Prioritized content on mobile
- [ ] Optimized images for different sizes
- [ ] Tested at all key breakpoints
- [ ] No horizontal scrolling on mobile
- [ ] No overlapping or truncated content

## Quick Reference

| Situation           | Action                                     |
| ------------------- | ------------------------------------------ |
| Starting new layout | Begin with mobile (320-375px)              |
| Need breakpoint     | Use project standard (check existing code) |
| Setting width       | Use `width: 100%` + `max-width`            |
| Setting font size   | Use `rem` (16px = 1rem)                    |
| Setting spacing     | Use `rem` or framework utilities           |
| Button too small    | Ensure min 44x44px with padding            |
| Text too small      | Minimum 16px (1rem) for body               |
| Testing layout      | Check 375px, 768px, 1024px, 1440px         |
| Images loading slow | Use srcset and modern formats              |
