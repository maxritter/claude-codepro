## Step 1: Special Cases (conditional — skip both sub-sections if neither applies)

This step handles the situational planning paths: extending an existing plan (1a), and migration/refactoring (1b) — which includes wide mechanical refactors that replace nothing. Most new plans skip both — when the request is a brand-new feature with no existing code replaced and no codebase-wide mechanical change, proceed directly to Step 2 (Create Header).

### 1a. Extending an Existing Plan

When adding tasks to an existing plan: load it, parse structure, verify compatibility, mark new tasks with `[NEW]`, update totals. If original + new > 12 tasks, suggest splitting.

### 1b. Migration/Refactoring — Feature Inventory & Wide Refactors

**When replacing existing code, complete a Feature Inventory BEFORE creating tasks** (for wide mechanical refactors that replace nothing, skip the inventory and use the expand–contract sequencing below):

1. List ALL files being replaced with their functions/classes
2. Map EVERY function to a task — no row may be "Not mapped"
3. Every row needs a Task # or explicit "Out of Scope" with user confirmation

"Out of Scope: Changes to X" = X migrates AS-IS (still needs migration task). "Out of Scope: Feature X" = X intentionally REMOVED (needs user confirmation, no task needed).

**Wide refactors — expand–contract.** Applies whenever ONE mechanical change (rename a column, retype a shared symbol) fans across the codebase so a single task can't land green — even when nothing is being replaced and no Feature Inventory is needed. Sequence the tasks as expand–contract:

1. **Expand** — add the new form beside the old (nothing breaks yet). First task.
2. **Migrate** — move call sites over in batches sized by blast radius (per package, per directory), one task per batch. The suite stays green after every batch because the old form still exists. A migrate batch is one coherent mechanical change repeated; size it by what can be verified together.
3. **Contract** — delete the old form once no caller remains. Final task.

Task order implies dependencies (Step 7.1), so the batches need no extra syntax. If a migrate batch cannot stay green on its own (old and new forms can't coexist for that slice), do NOT plan it as a separate task with a fake green: collapse the affected batches — and contract, if needed — into a single task whose DoD is the integrated green state, and state that consolidation explicitly in the plan.
