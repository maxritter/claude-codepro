---
paths:
  - "**/*.ts"
  - "**/*.tsx"
  - "**/*.js"
  - "**/*.jsx"
  - "**/*.mjs"
  - "**/*.mts"
---

## TypeScript Development Standards

### Toolchain

Use the project's declared package manager/version, lockfile, runtime, and package scripts. Check `packageManager` and repository instructions alongside `bun.lock`/`bun.lockb`, `pnpm-lock.yaml`, `yarn.lock`, or `package-lock.json`; multiple lockfiles may belong to separate workspaces. Do not mix managers or regenerate an unrelated workspace's lockfile.

Use the existing build, typecheck, lint, format, and test commands. Test-runner flags differ; do not assume Jest flags such as `--silent` or `--reporters=dot` work with every `npm test` script.

### Types and behaviour

- Preserve the project's TypeScript strictness and JavaScript compatibility. Do not change compiler settings, module format, or filenames incidentally.
- Use explicit types where they clarify public contracts and inference for straightforward local code. Choose `interface` or `type` according to the existing design.
- Prefer `unknown` with narrowing over unchecked values. Keep unavoidable `any` or assertions narrow and justified at interoperability boundaries; do not suppress errors merely to pass typechecking.
- Validate untrusted runtime data; TypeScript declarations do not validate JSON or external input.
- Handle promise failures and clean up resources/subscriptions. Preserve meaningful error context without swallowing failures or logging the same exception at every layer.
- Follow configured import ordering, naming, and formatting. Use `node:` for Node built-ins when compatible with the target runtime; browser code must not acquire a Node-only dependency accidentally.
- Add comments for non-obvious contracts or workarounds, not a restatement of every export.

Run focused behavioural checks and the required project gates. Inspect dependency and lockfile changes for the intended scope; committing still requires authorization.
