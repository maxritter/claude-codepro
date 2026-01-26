---
name: Typescript Standards
description: Apply TypeScript development standards including package manager detection (npm/yarn/pnpm/bun), explicit return types on exports, ESLint/Prettier code quality, one-line JSDoc, and self-documenting code practices. Use this skill when working with TypeScript or JavaScript code, managing dependencies, running tests, or ensuring code quality. Apply when installing packages, writing tests, formatting code, type checking, adding type annotations, organizing imports, or deciding whether to create new files vs. extending existing ones. Use for any TypeScript/JavaScript development task requiring adherence to tooling standards and best practices.
---

# TypeScript Standards

**Core Rule:** Detect and use the project's package manager. Write self-documenting TypeScript with explicit types on exports.

## When to use this skill

- When installing packages or running scripts in a TypeScript project
- When writing or modifying TypeScript code
- When adding type annotations or organizing imports in a TypeScript project
- When writing tests or running code quality tools in a TypeScript project

## Package Manager Detection

**CRITICAL: Always detect and use the project's existing package manager. NEVER mix package managers.**

Check the project root for lock files:
- `bun.lockb` → use **bun**
- `pnpm-lock.yaml` → use **pnpm**
- `yarn.lock` → use **yarn**
- `package-lock.json` → use **npm**

If no lock file exists, check `packageManager` field in `package.json`, or default to npm.

**Quick command mapping:**

| Action           | npm                  | yarn              | pnpm              | bun              |
| ---------------- | -------------------- | ----------------- | ----------------- | ---------------- |
| Install all      | `npm install`        | `yarn`            | `pnpm install`    | `bun install`    |
| Add package      | `npm install pkg`    | `yarn add pkg`    | `pnpm add pkg`    | `bun add pkg`    |
| Add dev dep      | `npm install -D pkg` | `yarn add -D pkg` | `pnpm add -D pkg` | `bun add -D pkg` |
| Run script       | `npm run script`     | `yarn script`     | `pnpm script`     | `bun script`     |
| Execute binary   | `npx cmd`            | `yarn cmd`        | `pnpm cmd`        | `bunx cmd`       |

## Type Annotations

**Add explicit return types to all exported functions:**

```typescript
// Required for exports
export function processOrder(orderId: string, userId: number): Order {
  // implementation
}

// Required for async functions
export async function fetchUser(id: string): Promise<User> {
  // implementation
}

// Optional for internal functions (inference is fine)
function formatPrice(amount: number) {
  return `$${amount.toFixed(2)}`;
}
```

**Prefer interfaces for object shapes, types for unions:**
```typescript
interface User {
  id: string;
  email: string;
  createdAt: Date;
}

type Status = 'pending' | 'active' | 'suspended';
type Handler = (req: Request, res: Response) => Promise<void>;
```

## Code Style

**Write self-documenting code. Minimize comments.**

```typescript
// BAD - comment explains unclear code
if (u.r === 'admin' || u.r === 'moderator') {

// GOOD - code explains itself
if (user.isAdmin() || user.isModerator()) {
```

**Use concise one-line JSDoc for exported functions:**
```typescript
/** Calculate discounted price by applying rate. */
export function calculateDiscount(price: number, rate: number): number {
  return price * (1 - rate);
}
```

**Import organization:** Node built-ins → External packages → Internal modules → Relative imports

```typescript
import { readFile } from 'node:fs/promises';
import express from 'express';
import { User } from '@/models/user';
import { formatPrice } from './utils';
```

## Common Patterns

**Use async/await, optional chaining, and nullish coalescing:**
```typescript
const email = user?.profile?.email ?? 'default@example.com';

async function fetchData(): Promise<Data> {
  const response = await fetch(url);
  return response.json();
}
```

**Prefer `node:` prefix for built-in modules:**
```typescript
import { readFile } from 'node:fs/promises';
import path from 'node:path';
```

**Use `const` assertions for literal types:**
```typescript
const ROLES = ['admin', 'user', 'guest'] as const;
type Role = typeof ROLES[number]; // 'admin' | 'user' | 'guest'
```

**Don't swallow errors:**
```typescript
try {
  await process();
} catch (error) {
  logger.error('Processing failed', { error });
  throw error;
}
```

## File Organization

**Prefer editing existing files over creating new ones.**

Before creating a new file, ask:
1. Can this fit in an existing module?
2. Is there a related file to extend?

**Naming:** kebab-case for files (`user-service.ts`), `.test.ts` or `.spec.ts` for tests.

## Verification

Before marking work complete, **always run these checks** (using the detected package manager):

1. **Format code:** Check `package.json` scripts for `format` or `prettier`. Otherwise: `prettier --write .` or `biome format --write .`
2. **Lint code:** Check `package.json` scripts for `lint`. Otherwise: `eslint . --fix` or `biome check --fix .`
3. **Type check:** Check `package.json` scripts for `typecheck` or `tsc`. Otherwise: `tsc --noEmit`
4. **Run tests:** Check `package.json` scripts for `test`

**Tip:** Look at `package.json` scripts first — projects often have custom configurations. Use what's already defined.

Then verify:
- [ ] All commands pass without errors
- [ ] Explicit return types on exports
- [ ] Lock file committed (if dependencies changed)
