---
paths:
  - "**/*.razor"
  - "**/*.razor.css"
  - "**/*.razor.cs"
---

## Blazor Standards

Follow the project's supported Blazor version, render model, and component conventions. These defaults do not require reorganizing existing components.

### Components

- **Parameters:** `[Parameter]` properties with sensible defaults; `[EditorRequired]` for mandatory ones.
- **Parent notification:** use `EventCallback<T>` — never call `StateHasChanged()` from a child to refresh a parent (`EventCallback` triggers it automatically).
- **Shared state:** prefer `[CascadingParameter]` or an injected, registered state service over deep parameter drilling.
- **Code organization:** use an inline `@code` block or code-behind partial class according to component complexity and project conventions.

### Styling

- Follow the established styling system. With CSS isolation (`MyComponent.razor.css`), account for generated scope attributes and use `::deep` deliberately when descendant markup requires it.

### Rendering & Lifecycle

- Use render modes supported by the project's framework version. Where static SSR is available and sufficient, do not add interactivity solely from a template.
- Use stable `@key` values where preserving list-item identity matters. Optimize rendering only after identifying unnecessary work; a `ShouldRender()` override must not suppress required updates.
- Dispose: `@implements IDisposable` / `IAsyncDisposable` to release timers, event handlers, and subscriptions (a common leak source in `InteractiveServer`).

Verify affected lifecycle, state, and user interactions using the project's existing checks and the relevant browser evidence.
