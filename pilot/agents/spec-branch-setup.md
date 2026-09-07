# Spec Branch & Worktree Setup

> Shared runbook for the `--new-branch` and `--worktree=yes` paths of `spec-plan`
> (Step 2), `spec-bugfix-plan` (Step 1), `/fix` (orchestrator), and `/build`
> (Step 2). Each skill builds into a separate SKILL.md, so none can see the
> others' steps — this file is the one place the sequence lives.
>
> Read it only when the parsed flag is `--new-branch` or `--worktree=yes`.
> The default (`--worktree=no`, and the whole flow when Branch Isolation is off)
> needs nothing from here: work continues on the current branch.

Callers supply `<plan_slug>` (the plan filename's slug, or `/fix`'s `<fix-slug>`)
and the branch prefix: `feat/` for features and builds, `fix/` for bugfixes.
A caller running as an orchestration lane also supplies its `<lane>` id.

## `--new-branch`

The explicit branch choice authorizes creating the requested branch. Preserve the user's working changes and do not change another session's active checkout.

1. Resolve the actual default remote branch from `refs/remotes/origin/HEAD` or verified remote refs. Refresh `origin` when appropriate. Do not invent `main` when no base exists.
2. Check the current branch, index, and worktree. Derive a free `<prefix>/<plan_slug>` name; if it already exists, choose a unique suffix without overwriting it.
3. On a clean checkout, run `git checkout -b <branch> <verified-base>`.
4. On a dirty checkout, preserve the exact staged/unstaged/untracked state before switching. If using a stash, capture its object id and the original branch, and restore that exact stash with `git stash apply --index <stash-id>`; never assume the top stash is still this run's. Keep the recovery identity across tool calls.
5. If checkout or restoration fails, stop the branch transition, report the actual branch and preserved recovery state, and resolve it before continuing. Do not claim restoration succeeded from an exit message alone. Do not drop a recovery stash until restoration is verified.

Use a single guarded command or persistent recorded state for the transition; transient shell variables are not available in later tool calls. If concurrent work makes switching this checkout unsafe, surface that concrete conflict rather than silently carrying other work into the new branch.

After verified branch creation and restoration, continue with `Worktree: No` semantics.

## `--worktree=yes`

```bash
~/.pilot/bin/pilot worktree detect --json <plan_slug>
# If not found:
~/.pilot/bin/pilot worktree create --json <plan_slug>
# → {"path": "...", "branch": "spec/<slug>", "base_branch": "main"}
```

**On a lane run, pass `--lane <lane>` to both commands.** The worktree directory and branch are keyed on `(slug, lane)`, so two lanes whose descriptions normalise to the same slug get separate checkouts instead of silently sharing one. Creation refuses outright when the resolved branch already belongs to a different lane.

All file writes — including the plan file — use the returned `path` as their base directory.

**If creation fails:**

- **Ordinary run** — diagnose and retry a recoverable setup failure. If the requested isolation cannot be established, report the blocker and preserve the current checkout; do not silently replace `--worktree=yes` with shared-checkout execution.
- ⛔ **Lane run (`--lane` was supplied) — ABORT.** Say which command failed and why, and stop. Continuing would drop the lane into the coordinator's shared checkout, where it races every sibling's edits and staging — exactly the collision the lane was created to avoid. A lane that silently loses its isolation is worse than a lane that never started, because nothing downstream can tell the difference.
