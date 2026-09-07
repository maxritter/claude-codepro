## Step 5: Program Execution Verification

**If runtime profile is Minimal:** Run the changed CLI, hook, script, or library entry point with representative inputs in an isolated environment. For prose/config-only work, validate the generated or consumed artifact and its relevant behavior. Skip server-only checks below when no service exists.

**⚠️ Parallel spec warning:** Before starting a server, check port availability: `lsof -i :<port>`. If another `/spec` session occupies it, wait or use a different port.

- Program starts without errors
- Inspect logs for errors/warnings/stack traces
- **Verify output correctness** — fetch source data independently, compare against program output. If mismatch → BUG.
- Test with real/sample data
- **Performance check (UI changes):** Open the page, monitor for lag or high CPU. Watch for: components rendering expensive operations without `useMemo`/`useCallback`, eager loading of all data on mount (lazy-load instead), missing virtualization for large lists, network request storms (N+1 fetches). If page feels sluggish → profile and fix before proceeding.

**Bugs:** Minor → fix, re-run, continue. Major → add task to plan, then route the loop-back through Step 11's iteration-cap check (it sets `Status: PENDING`, increments `Iterations`, and re-invokes spec-implement — or surfaces to the user at the cap). Never loop back to implementation without passing that cap check.
