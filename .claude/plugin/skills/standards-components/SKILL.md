---
name: Components Standards
description: Design reusable, composable UI components following single responsibility principle with clear interfaces, encapsulation, and minimal props. Use this skill when creating or modifying frontend components in any framework (React, Vue, Svelte, web components) or component files. Apply when working with .jsx, .tsx, .vue, .svelte files in component directories (components/, src/components/, ui/, lib/), defining component props and interfaces, implementing component composition patterns, managing component-level state, creating reusable UI elements (buttons, forms, cards, modals), documenting component APIs, or refactoring components for better reusability and maintainability.
---

# Components Standards

**Core Rule:** Build small, focused components with single responsibility. Compose complex UIs from simple pieces.

## When to use this skill

- When creating new component files (.jsx, .tsx, .vue, .svelte, etc.)
- When modifying existing components in component directories (components/, ui/, lib/)
- When defining component props, interfaces, or prop types
- When implementing component composition to build complex UIs from simpler components
- When managing component-level state and deciding when to lift state up
- When creating reusable UI elements like buttons, forms, cards, modals, or layouts
- When documenting component APIs, props, and usage examples
- When refactoring monolithic components into smaller, focused components
- When designing component interfaces for team adoption
- When implementing encapsulation to keep internal component details private

This Skill provides Claude Code with specific guidance on how to adhere to coding standards as they relate to how it should handle frontend components.

## Component Design Principles

### Single Responsibility

Each component does one thing well. If you need "and" to describe it, split it.

**Bad:**
```tsx
// UserProfileCardWithEditFormAndNotifications - does too much
function UserProfile() {
  return (
    <>
      <ProfileDisplay />
      <EditForm />
      <NotificationList />
    </>
  )
}
```

**Good:**
```tsx
// Three focused components
function UserProfileCard({ user }) { /* display only */ }
function UserEditForm({ user, onSave }) { /* editing only */ }
function UserNotifications({ userId }) { /* notifications only */ }
```

### Composition Over Configuration

Build complex UIs by combining simple components, not by adding props.

**Bad - Configuration:**
```tsx
<Card
  showHeader
  showFooter
  headerAlign="left"
  footerAlign="right"
  headerColor="blue"
>
  Content
</Card>
```

**Good - Composition:**
```tsx
<Card>
  <Card.Header align="left" color="blue">Title</Card.Header>
  <Card.Body>Content</Card.Body>
  <Card.Footer align="right">Actions</Card.Footer>
</Card>
```

### Minimal Props

Keep props under 5-7. More props = component doing too much.

**When you have many props:**
1. Group related props into objects
2. Split component into smaller pieces
3. Use composition instead of configuration

**Example - Group related props:**
```tsx
// Bad
function Button({ textColor, bgColor, borderColor, hoverColor }) {}

// Good
function Button({ colors: { text, bg, border, hover } }) {}
```

## Component Interface Design

### Explicit Prop Types

Always define prop types with TypeScript interfaces or PropTypes.

**React/TypeScript:**
```tsx
interface ButtonProps {
  variant?: 'primary' | 'secondary' | 'danger'
  size?: 'sm' | 'md' | 'lg'
  disabled?: boolean
  onClick: () => void
  children: React.ReactNode
}

function Button({
  variant = 'primary',
  size = 'md',
  disabled = false,
  onClick,
  children
}: ButtonProps) {
  // Implementation
}
```

**Vue:**
```vue
<script setup lang="ts">
interface Props {
  variant?: 'primary' | 'secondary' | 'danger'
  size?: 'sm' | 'md' | 'lg'
  disabled?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  variant: 'primary',
  size: 'md',
  disabled: false
})
</script>
```

### Sensible Defaults

Provide defaults for optional props. Component should work with minimal configuration.

```tsx
// User only needs to provide required props
<Button onClick={handleClick}>Save</Button>

// But can customize when needed
<Button variant="danger" size="lg" onClick={handleDelete}>Delete</Button>
```

## State Management

### Keep State Local

State lives in the component that uses it. Only lift state when multiple components need it.

**Decision tree:**
```
Does only this component need the state?
├─ YES → Keep it local with useState/ref
└─ NO → Do multiple children need it?
    ├─ YES → Lift to common parent
    └─ NO → Do unrelated components need it?
        └─ YES → Use global state (context/store)
```

**Example:**
```tsx
// Local state - only this component needs it
function SearchInput() {
  const [query, setQuery] = useState('')
  return <input value={query} onChange={e => setQuery(e.target.value)} />
}

// Lifted state - parent and siblings need it
function SearchPage() {
  const [query, setQuery] = useState('')
  return (
    <>
      <SearchInput value={query} onChange={setQuery} />
      <SearchResults query={query} />
    </>
  )
}
```

### Avoid Prop Drilling

If passing props through 3+ levels, use composition or context instead.

**Bad - Prop drilling:**
```tsx
<Page user={user}>
  <Layout user={user}>
    <Sidebar user={user}>
      <UserMenu user={user} />
    </Sidebar>
  </Layout>
</Page>
```

**Good - Context:**
```tsx
<UserContext.Provider value={user}>
  <Page>
    <Layout>
      <Sidebar>
        <UserMenu /> {/* Reads from context */}
      </Sidebar>
    </Layout>
  </Page>
</UserContext.Provider>
```

## Naming Conventions

**Components:** PascalCase, descriptive noun or noun phrase
- `Button`, `UserCard`, `SearchInput`, `NavigationMenu`
- Avoid: `MyComponent`, `Component1`, `Wrapper`, `Container`

**Props:** camelCase, descriptive
- `onClick`, `isDisabled`, `userName`, `maxLength`
- Boolean props: `is*`, `has*`, `should*`, `can*`

**Event handlers:** `on*` for props, `handle*` for internal functions
```tsx
function Form({ onSubmit }) {
  const handleSubmit = (e) => {
    e.preventDefault()
    onSubmit(data)
  }
  return <form onSubmit={handleSubmit}>...</form>
}
```

## Encapsulation

Keep implementation details private. Only expose what consumers need.

**Bad - Exposing internals:**
```tsx
function DataTable({ data, sortColumn, sortDirection, setSortColumn, setSortDirection }) {
  // Consumer must manage sorting state
}
```

**Good - Encapsulated:**
```tsx
function DataTable({ data, onSort }) {
  const [sortColumn, setSortColumn] = useState('name')
  const [sortDirection, setSortDirection] = useState('asc')
  // Component manages its own sorting state
}
```

## Component Organization

**File structure:**
```
components/
├── Button/
│   ├── Button.tsx          # Component implementation
│   ├── Button.test.tsx     # Tests
│   ├── Button.stories.tsx  # Storybook stories (if used)
│   └── index.ts            # Export
```

**Or for simple components:**
```
components/
├── Button.tsx
└── Button.test.tsx
```

## Documentation Requirements

Every reusable component needs:

1. **TypeScript types/interfaces** - Self-documenting props
2. **JSDoc comments** - For complex props or behavior
3. **Usage example** - In comments or Storybook

**Example:**
```tsx
/**
 * Primary button component for user actions.
 *
 * @example
 * <Button variant="primary" onClick={handleSave}>
 *   Save Changes
 * </Button>
 */
interface ButtonProps {
  /** Visual style variant */
  variant?: 'primary' | 'secondary' | 'danger'
  /** Size of the button */
  size?: 'sm' | 'md' | 'lg'
  /** Disables interaction */
  disabled?: boolean
  /** Click handler */
  onClick: () => void
  /** Button content */
  children: React.ReactNode
}
```

## When to Split Components

Split when:
- Component exceeds 200-300 lines
- Component has multiple responsibilities
- Part of component is reusable elsewhere
- Component has complex conditional rendering
- Testing becomes difficult due to complexity

**Example - Before split:**
```tsx
function UserDashboard() {
  // 400 lines of profile display, settings, notifications, activity feed
}
```

**After split:**
```tsx
function UserDashboard() {
  return (
    <DashboardLayout>
      <UserProfile />
      <UserSettings />
      <NotificationPanel />
      <ActivityFeed />
    </DashboardLayout>
  )
}
```

## Testing Components

Every component needs tests for:
- Rendering with default props
- Rendering with all prop variations
- User interactions (clicks, input, etc.)
- Conditional rendering logic
- Error states

**Example:**
```tsx
describe('Button', () => {
  it('renders with default props', () => {
    render(<Button onClick={jest.fn()}>Click me</Button>)
    expect(screen.getByRole('button')).toBeInTheDocument()
  })

  it('calls onClick when clicked', () => {
    const handleClick = jest.fn()
    render(<Button onClick={handleClick}>Click me</Button>)
    fireEvent.click(screen.getByRole('button'))
    expect(handleClick).toHaveBeenCalledTimes(1)
  })

  it('is disabled when disabled prop is true', () => {
    render(<Button onClick={jest.fn()} disabled>Click me</Button>)
    expect(screen.getByRole('button')).toBeDisabled()
  })
})
```

## Common Mistakes to Avoid

**God components:** Components that do everything. Split them.

**Prop drilling:** Passing props through many levels. Use composition or context.

**Premature abstraction:** Don't create reusable components until you need them in 2+ places.

**Too many props:** More than 7 props usually means component does too much.

**Unclear naming:** `Container`, `Wrapper`, `Component` don't describe purpose.

**Missing prop types:** Always define prop types for type safety and documentation.

## Decision Checklist

Before completing component work:

- [ ] Component has single, clear responsibility
- [ ] Props are typed with TypeScript/PropTypes
- [ ] Sensible defaults provided for optional props
- [ ] State is as local as possible
- [ ] Component name clearly describes purpose
- [ ] Internal implementation details are private
- [ ] Component is tested
- [ ] Usage is documented (types + example)
- [ ] No prop drilling beyond 2 levels
- [ ] Component is under 300 lines (or split if larger)
