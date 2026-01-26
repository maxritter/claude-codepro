---
name: Accessibility Standards
description: Build accessible user interfaces using semantic HTML, proper ARIA attributes, keyboard navigation, color contrast, and screen reader compatibility. Use this skill when creating or modifying frontend components, HTML templates, React/Vue/Svelte components, forms, interactive elements, navigation menus, modals, or any UI elements. Apply when working with HTML files, JSX/TSX components, template files, ensuring keyboard accessibility, implementing focus management, adding alt text to images, creating form labels, testing with screen readers, managing ARIA attributes, maintaining color contrast ratios, or building heading hierarchies. Use for any task involving UI accessibility compliance, WCAG standards, or inclusive design patterns.
---

# Accessibility Standards

**Core Rule:** Build accessible interfaces that work for all users, including those using assistive technologies.

## When to use this skill

- When creating or modifying frontend components (React, Vue, Svelte, web components, etc.)
- When writing HTML templates or JSX/TSX component markup
- When implementing forms and ensuring all inputs have proper labels
- When adding images and needing to provide descriptive alt text
- When building interactive elements that need keyboard navigation support
- When implementing focus management in modals, dialogs, or single-page applications
- When ensuring color contrast ratios meet WCAG standards (4.5:1 for normal text)
- When adding ARIA attributes to enhance complex component accessibility
- When creating proper heading hierarchies (h1-h6) for document structure
- When testing components with screen readers or accessibility testing tools
- When building navigation menus, buttons, or links that need to be keyboard accessible

This Skill provides Claude Code with specific guidance on how to adhere to coding standards as they relate to how it should handle frontend accessibility.

## Semantic HTML First

Use native HTML elements that convey meaning to assistive technologies.

**Correct elements:**
```html
<!-- Navigation -->
<nav><a href="/about">About</a></nav>

<!-- Buttons that perform actions -->
<button onClick={handleSubmit}>Submit</button>

<!-- Links that navigate -->
<a href="/profile">View Profile</a>

<!-- Main content area -->
<main><article>...</article></main>

<!-- Form structure -->
<form>
  <label for="email">Email</label>
  <input id="email" type="email" />
</form>
```

**Avoid:**
```html
<!-- BAD - div/span without semantic meaning -->
<div onClick={navigate}>Go to page</div>
<span onClick={handleClick}>Submit</span>
```

**When to use each element:**
- `<button>`: Actions (submit, open modal, toggle)
- `<a>`: Navigation to different pages/sections
- `<nav>`: Navigation landmarks
- `<main>`: Primary page content
- `<header>`, `<footer>`, `<aside>`: Page structure
- `<article>`, `<section>`: Content grouping

## Keyboard Navigation

All interactive elements must be keyboard accessible.

**Requirements:**
- Tab key moves focus through interactive elements
- Enter/Space activates buttons and links
- Escape closes modals and dialogs
- Arrow keys navigate menus and lists (when appropriate)
- Focus indicators are clearly visible

**Implementation:**
```jsx
// Native elements are keyboard accessible by default
<button onClick={handleClick}>Click me</button>

// Custom interactive elements need tabIndex
<div
  role="button"
  tabIndex={0}
  onClick={handleClick}
  onKeyDown={(e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      handleClick();
    }
  }}
>
  Custom button
</div>

// Focus styles must be visible
button:focus {
  outline: 2px solid blue;
  outline-offset: 2px;
}
```

**Never:**
- Remove focus outlines without providing alternative indicators
- Use `tabIndex` values other than 0 or -1
- Create keyboard traps (user can't escape with keyboard)

## Form Labels and Inputs

Every form input must have an associated label.

**Correct patterns:**
```html
<!-- Explicit label association -->
<label for="username">Username</label>
<input id="username" type="text" />

<!-- Implicit label wrapping -->
<label>
  Email
  <input type="email" />
</label>

<!-- aria-label for icon-only buttons -->
<button aria-label="Close dialog">
  <CloseIcon />
</button>

<!-- aria-describedby for help text -->
<label for="password">Password</label>
<input
  id="password"
  type="password"
  aria-describedby="password-help"
/>
<span id="password-help">Must be at least 8 characters</span>
```

**Required attributes:**
- `id` on input, matching `for` on label
- `type` attribute on inputs (text, email, password, etc.)
- `aria-label` or `aria-labelledby` when visual label isn't present
- `aria-describedby` for additional context or error messages

## Alternative Text for Images

Provide descriptive alt text that conveys the image's purpose.

**Guidelines:**
```jsx
<!-- Informative images -->
<img src="chart.png" alt="Sales increased 40% in Q4 2024" />

<!-- Functional images (buttons, links) -->
<a href="/search">
  <img src="search-icon.svg" alt="Search" />
</a>

<!-- Decorative images -->
<img src="decoration.png" alt="" />
{/* or */}
<img src="decoration.png" role="presentation" />

<!-- Complex images need longer descriptions -->
<img
  src="architecture.png"
  alt="System architecture diagram"
  aria-describedby="arch-description"
/>
<div id="arch-description">
  The system consists of three layers: frontend React app,
  Node.js API server, and PostgreSQL database...
</div>
```

**Alt text rules:**
- Describe the content and function, not "image of"
- Keep concise (under 150 characters when possible)
- Use empty alt (`alt=""`) for purely decorative images
- Don't include "image", "picture", "photo" (screen readers announce this)

## Color Contrast

Maintain sufficient contrast ratios for readability.

**WCAG Requirements:**
- Normal text (< 18pt): 4.5:1 contrast ratio
- Large text (≥ 18pt or ≥ 14pt bold): 3:1 contrast ratio
- UI components and graphics: 3:1 contrast ratio

**Don't rely on color alone:**
```jsx
// BAD - color only
<span style={{color: 'red'}}>Error</span>

// GOOD - color + icon + text
<span style={{color: 'red'}}>
  <ErrorIcon aria-hidden="true" />
  Error: Invalid email format
</span>

// BAD - color-coded status
<div style={{backgroundColor: status === 'active' ? 'green' : 'red'}} />

// GOOD - color + text label
<div>
  <StatusBadge color={status === 'active' ? 'green' : 'red'}>
    {status === 'active' ? 'Active' : 'Inactive'}
  </StatusBadge>
</div>
```

**Tools to verify contrast:**
- Browser DevTools (Chrome, Firefox have built-in checkers)
- WebAIM Contrast Checker
- Axe DevTools extension

## ARIA Attributes

Use ARIA to enhance semantics when HTML alone isn't sufficient.

**Common ARIA patterns:**
```jsx
// Roles for custom components
<div role="dialog" aria-modal="true">
  <h2 id="dialog-title">Confirm Action</h2>
  <div aria-describedby="dialog-desc">...</div>
</div>

// States and properties
<button aria-expanded={isOpen} aria-controls="menu">
  Menu
</button>
<ul id="menu" hidden={!isOpen}>...</ul>

// Live regions for dynamic content
<div aria-live="polite" aria-atomic="true">
  {statusMessage}
</div>

// Hide decorative elements
<span aria-hidden="true">→</span>
```

**ARIA rules:**
1. Use semantic HTML first, ARIA second
2. Don't override native semantics (`<button role="link">` is wrong)
3. All interactive ARIA roles need keyboard support
4. Test with actual screen readers

**Common ARIA attributes:**
- `aria-label`: Accessible name for element
- `aria-labelledby`: References element(s) that label this one
- `aria-describedby`: References element(s) that describe this one
- `aria-expanded`: Whether element is expanded (true/false)
- `aria-hidden`: Hide from assistive tech (use sparingly)
- `aria-live`: Announce dynamic content changes (polite/assertive)

## Heading Hierarchy

Use heading levels (h1-h6) in logical order to create document structure.

**Correct structure:**
```html
<h1>Page Title</h1>
  <h2>Section 1</h2>
    <h3>Subsection 1.1</h3>
    <h3>Subsection 1.2</h3>
  <h2>Section 2</h2>
    <h3>Subsection 2.1</h3>
```

**Rules:**
- One `<h1>` per page (page title)
- Don't skip levels (h2 → h4 is wrong)
- Don't choose headings based on visual size (use CSS for styling)
- Headings create an outline for screen reader navigation

**Styling headings:**
```css
/* Separate semantic level from visual appearance */
h1 { font-size: 2rem; }
h2 { font-size: 1.5rem; }

/* If you need h3 to look like h1 */
.h3-large {
  font-size: 2rem;
}
```

## Focus Management

Manage focus in dynamic interfaces to maintain keyboard navigation flow.

**Modal dialogs:**
```jsx
function Modal({ isOpen, onClose, children }) {
  const modalRef = useRef();

  useEffect(() => {
    if (isOpen) {
      // Save previously focused element
      const previousFocus = document.activeElement;

      // Move focus to modal
      modalRef.current?.focus();

      // Trap focus within modal
      // (use library like focus-trap-react)

      return () => {
        // Restore focus when modal closes
        previousFocus?.focus();
      };
    }
  }, [isOpen]);

  return (
    <div
      ref={modalRef}
      role="dialog"
      aria-modal="true"
      tabIndex={-1}
    >
      {children}
      <button onClick={onClose}>Close</button>
    </div>
  );
}
```

**Dynamic content:**
```jsx
// Announce content changes to screen readers
<div aria-live="polite">
  {loading ? 'Loading...' : `Loaded ${items.length} items`}
</div>

// Move focus to new content after navigation
function handlePageChange(newPage) {
  loadPage(newPage);
  // Focus the main heading of new content
  document.querySelector('h1')?.focus();
}
```

## Verification Checklist

Before marking UI work complete:

- [ ] All interactive elements are keyboard accessible
- [ ] Focus indicators are visible on all focusable elements
- [ ] All images have appropriate alt text
- [ ] All form inputs have associated labels
- [ ] Color contrast meets WCAG standards (4.5:1 for text)
- [ ] Heading hierarchy is logical (no skipped levels)
- [ ] ARIA attributes are used correctly (if needed)
- [ ] Modals and dialogs manage focus appropriately
- [ ] No information conveyed by color alone
- [ ] Tested with keyboard navigation (Tab, Enter, Escape)

## Common Mistakes to Avoid

**Using divs/spans for buttons:**
```jsx
// BAD
<div onClick={handleClick}>Submit</div>

// GOOD
<button onClick={handleClick}>Submit</button>
```

**Missing form labels:**
```jsx
// BAD
<input type="text" placeholder="Username" />

// GOOD
<label for="username">Username</label>
<input id="username" type="text" />
```

**Removing focus outlines:**
```css
/* BAD */
button:focus { outline: none; }

/* GOOD - provide alternative indicator */
button:focus {
  outline: 2px solid blue;
  outline-offset: 2px;
}
```

**Redundant ARIA:**
```jsx
// BAD - button already has button role
<button role="button">Click</button>

// GOOD - use native semantics
<button>Click</button>
```

**Inaccessible custom components:**
```jsx
// BAD - no keyboard support
<div onClick={handleClick}>Custom button</div>

// GOOD - full keyboard support
<div
  role="button"
  tabIndex={0}
  onClick={handleClick}
  onKeyDown={(e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      handleClick();
    }
  }}
>
  Custom button
</div>
```

## Testing Accessibility

**Manual testing:**
1. Navigate entire interface using only keyboard
2. Verify all interactive elements are reachable and activatable
3. Check focus indicators are visible
4. Test with browser zoom at 200%
5. Use browser DevTools accessibility inspector

**Automated testing:**
- Axe DevTools browser extension
- Lighthouse accessibility audit
- WAVE browser extension
- eslint-plugin-jsx-a11y (for React)

**Screen reader testing:**
- macOS: VoiceOver (Cmd+F5)
- Windows: NVDA (free) or JAWS
- Test critical user flows with screen reader enabled

**Remember:** Automated tools catch ~30% of issues. Manual testing is essential.
