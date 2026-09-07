---
sidebar_position: 4
title: Pilot CLI
description: Command reference for the pilot binary — administration, worktrees, skill validation, and on-demand Claude Design access.
---

# Pilot CLI

Admin command reference for the `pilot` binary at `~/.pilot/bin/pilot`.

:::note Pilot does not launch your agent
Pilot Shell loads automatically when you run `claude` or `codex` — there is no wrapper command. The `pilot` CLI provides administration, worktrees, diagnostics, skill tooling, and narrowly scoped service bridges. Most commands support `--json` for structured output.
:::

## License & auth

| Command | Description |
|---------|-------------|
| `pilot activate <key>` | Activate a license key on this machine |
| `pilot deactivate` | Deactivate license on this machine |
| `pilot status [--json]` | Show current license status and tier |
| `pilot portal [--json] [--no-browser]` | Open Polar's customer portal (seats, invoices, payment method, license key recovery). Sign in there with the email address you used at checkout — Pilot never signs you in from your license key, so a key on a teammate's machine cannot reach your billing. `--no-browser` prints the URL instead of opening it |
| `pilot trial --check [--json]` | Check trial eligibility for this machine |
| `pilot trial --start [--json]` | Start a trial (one-time per machine) |

### When access is deactivated

When access is inactive, Pilot makes the change visible and pauses its licensed surfaces:

- Pilot workflows, managed skills and rules, review agents, context, memory capture and retrieval, and quality automation are unavailable.
- Pilot tool integrations, statusline metrics, and Console features stop working.
- The statusline becomes a calm recovery notice, and the Console opens only its license recovery screen.
- Claude Code and Codex themselves continue to work normally, including their native commands, planning, goals, models, and user-owned configuration.

License activation, status, account access, updates, and the uninstall instructions remain available. Activate a valid replacement key to restore Pilot. If you do not want another license, use the [safe uninstaller](../getting-started/installation#uninstall); it removes Pilot without removing either coding agent or user data.


## Updates

| Command | Description |
|---------|-------------|
| `pilot update [--yes] [--json]` | Update Pilot Shell. `pilot upgrade` is an alias. Pass `--yes` to skip the confirmation prompt. |
| `pilot --version` | Show Pilot Shell version |

Update Claude Code and Codex CLI through their own installers independently — `pilot update` only updates Pilot Shell itself.

## Spec authoring

Scaffold and check plan files from any tool — a skill of your own, a script, or by hand. The format these enforce is documented in [Plan File Format](plan-format).

| Command | Description |
|---------|-------------|
| `pilot spec init --type feature\|bugfix\|build --title <t>` | Write a conforming plan skeleton and print its path. `feature`/`bugfix` land in `docs/plans/`, `build` in `docs/builds/`. Optional: `--slug <s>`, `--dir <d>`, `--force`, `--json` |
| `pilot spec validate <plan> [--strict] [--json]` | Check a plan against the format contract |

`validate` reports three tiers, and only the first one fails the command:

- **errors** — the plan will render wrong (bad header value, task-numbering gap, a missing task-card label, the plan type's progress checklist disagreeing with its task headings, CRLF line endings)
- **warnings** — the plan is unfinished but renderable (`TODO` left in, a Definition of Done with no checkboxes, no tasks yet). `--strict` promotes these to errors
- **info** — worth knowing, never a failure (a section heading Pilot doesn't recognise; it still renders)

Exit codes: **0** no errors · **1** at least one error · **2** the file could not be read, or is not a plan file.

```bash
pilot spec init --type feature --title "Add user auth"
pilot spec validate docs/plans/2026-08-24-add-user-auth.md --json
```

`init` deliberately does not register the plan — run [`pilot register-plan`](plan-format#registering-a-plan) when you want Pilot's hooks to treat it as this session's active work.

## Skill source validation

Pilot's decomposed skill sources use `manifest.json`, an orchestrator, and ordered phase files. Version 2 manifests declare their target agents, invocation policy, visibility, and delivery mode. Every shipped Pilot workflow bundles its ordered phases into one generated `SKILL.md`, so Claude Code and Codex load the workflow with the skill instead of emitting a visible runtime read for each phase.

| Command | Description |
|---------|-------------|
| `pilot skill-build <skill-dir> [--dry-run] [--json]` | Build that source tree's `SKILL.md`; existing version 1 manifests keep their bundled behavior |
| `pilot skills validate [path] [--platform claude\|codex\|all] [--json]` | Validate manifests, safe paths, references, orphan phases, generated size budgets, and platform metadata without writing |
| `pilot skills validate [path] --check-installed` | Also check that the active installed skill tree contains every referenced runtime resource and no foreign tool syntax |

`path` defaults to `pilot/skills/` in a Pilot source checkout. Exit codes are **0** valid · **1** validation findings · **2** unreadable source or installation.

`progressive` remains a supported manifest mode for custom skills with genuinely optional runtime resources; it is not used for Pilot's sequential workflows. Compiled artifacts retain a runaway-size guard of 1,500 lines and 20,000 words.

## Claude Design bridge

Open Claude Design owns a standalone browser OAuth flow, so neither Claude Code nor an Anthropic API key is required. The scoped credential lives in a dedicated macOS Keychain item or current-user-only Linux/WSL2 file; an existing Claude Code Design login remains a compatibility fallback. Pilot installs the latest stable Open Claude Design release after verifying its release-local checksum and sync compatibility.

| Command | Description |
|---------|-------------|
| `pilot design login [--manual]` | Connect an eligible Claude.ai account directly through Open Claude Design |
| `pilot design logout --yes` | Remove only Open Claude Design's standalone credential |
| `pilot design status [--json]` | Forward to Open Claude Design and verify the platform credential, MCP connection, server identity, and protocol version |
| `pilot design sync review <project> --direction <to-design\|to-code> --pair <remote=local> [--json]` | Create the exact revision-bound diff and review id used for approval; repeat `--pair` for the complete sync set |
| `pilot design sync apply <review-id> --allow-write [--json]` | Revalidate the approved local hashes and remote etags before any write or implementation handoff |
| `pilot design sync finish <review-id> [--json]` | Advance the verified ledger only after preview, readback, implementation, and local checks succeed |
| `pilot design sync status [<review-id>] [--json]` | Inspect local review state without remote access; stale reviews require reapproval and unknown reviews require reconciliation |
| `pilot design authoring-context <project> --design-system <id> --skill <name> [--refresh] [--json]` | Fetch or reuse the current project prompt and one live authoring skill through one MCP session; writes complete texts to the git-ignored local cache instead of terminal output |
| `pilot design tools [--json]` | List compact live tool summaries without full input schemas |
| `pilot design describe <tool> [--json]` | Fetch one live tool's complete schema and annotations |
| `pilot design call <tool> --args '<json>' [--json]` | Call a read-only tool. Use `--args -` to read a JSON object from stdin |
| `pilot design files <project> [--path <dir>] [--depth <n>] [--json\|--tsv]` | Return normalized file metadata, or ledger-ready `path/etag/size` TSV, without file bodies or nested MCP envelopes |
| `pilot design call <tool> ... --allow-write` | Permit a tool not marked `readOnlyHint: true`; the implicit Claude Design workflow uses this only after explicit remote-write authorization |
| `pilot design preview <project> <remote-path> [--open] [--json]` | Render a remote file and return only its durable Claude Design URL; short-lived capability URLs remain internal |
| `pilot design pull <project> <remote-path> --output <local-path> [--json]` | Read one complete text file directly to disk without printing its body; confines the destination to the current worktree and refuses overwrite unless `--force` is explicit |
| `pilot design push <project> --file <remote=local> --if-match <remote=etag> --allow-write [--json]` | Read worktree-local bytes inside Pilot, mint an exact-path plan internally, compare fresh base etags, and write without putting files or tokens in model context; repeat file/etag flags for a batch, or pass `--plan-token -` to reuse a plan from stdin |
| `pilot design planned-call <copy_files\|create_support_js> <project> --args '<json>' --allow-write` | Mint and consume the operation's signed plan inside one process without exposing the capability token |
| `pilot design delete <project> --path <remote> --if-match <remote=etag> --confirm-delete <remote> --allow-write` | Delete only user-authorized exact paths after a conditional backup; verifies absence before success |
| `pilot design pull\|push ... --allow-external-local-path <local-path>` | Permit that exact local operand outside the worktree only when the user authorized it; repeat per external operand, while symlink components remain forbidden |

The local boundary falls back to the current directory outside Git. Reused push plan tokens are stdin-only: literal `--plan-token TOKEN` values are rejected without being echoed into errors. Raw capability-bearing tools such as `finalize_plan`, `render_preview`, and `delete_files` are unavailable through the generic call path; their guarded helpers keep authorization, backups, and verification together. These compatibility commands forward to the installed Open Claude Design CLI; Pilot does not keep a second bridge implementation. See [UI Design and Claude Design](/docs/workflows/ui-design).

## Worktree isolation

Used by the `/spec`, `/fix`, and `/build` workflows to keep work isolated until verification passes. All commands work with both Claude Code and Codex sessions.

| Command | Description |
|---------|-------------|
| `pilot worktree create --json <slug>` | Create isolated git worktree (in `.worktrees/` unless configured otherwise) |
| `pilot worktree detect --json <slug>` | Check if a worktree already exists |
| `pilot worktree diff --json <slug>` | List changed files in the worktree |
| `pilot worktree sync --json <slug>` | Squash merge worktree changes back to base branch. The landing commit carries the **branch's own** message: a single conventional commit lands verbatim (body and all — for `/fix` that body is the root-cause analysis), a single non-conventional one keeps its content under an inferred release prefix, and several are joined under the subject of the newest commit carrying the branch's release type, with every message kept in the body. A bugfix branch therefore lands as `fix:` rather than being recorded as a feature |
| `pilot worktree cleanup --json <slug>` | Remove worktree and branch (`--force` after a sync — still verifies the work reached the base branch; `--discard` to delete unmerged work) |
| `pilot worktree status --json` | Show active worktree info for current session |

Every command above also takes `--lane <id>` — see [Orchestration lanes](#orchestration-lanes) below.

:::info Slug format
The `<slug>` is the plan filename without the date prefix and `.md` extension. Example: `docs/plans/2026-02-22-add-auth.md` → `add-auth`.
:::

:::warning `worktree sync` exit codes
`0` clean · `1` nothing landed · **`2` the squash merge landed, but the base checkout's own uncommitted work could not be restored** and is sitting in `git stash list`. The JSON still reports `"success": true` — the merge really did succeed; only the unrelated local work is stranded, and the exit code is what stops a chained `&& pilot worktree cleanup` from deleting the worktree before you have seen the warning. Recover with `git stash pop`.

**Creation and sync both serialize** on a repo-wide lock, so concurrent lanes queue rather than interleaving their changes to the shared base checkout — `create` auto-stashes and restores that checkout, and `sync` merges into it. A failure naming lane contention means another lane held the lock past the timeout (`PILOT_SYNC_LOCK_TIMEOUT`, default 300s) and **nothing was changed**. If the lock itself cannot be opened, a lane run fails rather than proceeding unserialized; an ordinary single run continues as before.
:::

### Orchestration lanes

A coordinating session can dispatch `/spec`, `/fix`, and `/build` runs as concurrent subagents. Each one passes `--lane <id>`, and that flag is what keeps them apart.

| Command | With `--lane <id>` |
|---------|--------------------|
| `pilot register-plan <path> <status> --lane <id>` | Registers under `~/.pilot/sessions/<session>/lanes/<id>/` instead of the session's single slot |
| `pilot worktree create --json <slug> --lane <id>` | Keys the worktree directory and branch on `(slug, lane)`, so two lanes deriving the same slug get separate checkouts |
| `pilot worktree detect\|diff\|sync\|cleanup\|status --json --lane <id>` | Resolves that lane's worktree, never a sibling's |

Why it is needed: a Claude Code subagent resolves the **same** session id as its parent, and shell state does not survive between its tool calls, so a lane cannot identify itself any other way. Without the flag, every lane's plan lands in the coordinator's `active_plan.json` — siblings overwrite each other, and the coordinator's stop guard blocks its every turn over a plan it does not own.

**The contract is fail-closed.** `--lane` implies an isolated worktree; combining it with `--worktree=no` or `--new-branch` is rejected, and a lane whose worktree cannot be created aborts rather than dropping into the shared checkout. Lane ids match `[a-z0-9][a-z0-9-]{0,63}` and anything else is refused outright — the value becomes a directory name and a branch component.

Omit `--lane` and every command behaves exactly as it always has.

:::tip Monorepos: move the worktrees, give git more time
Worktrees land in `<project>/.worktrees/` and each git call gets 300 seconds. Both are configurable in Console → Settings → Spec Workflow → Worktrees, or per shell:

```bash
PILOT_WORKTREE_DIR=~/pilot-worktrees   # absolute, or relative to the project root
PILOT_WORKTREE_TIMEOUT=900             # seconds per git call
```

A location outside the repo keeps a second full checkout away from IDE indexers and file watchers, and is not written to `.gitignore`. Raise the timeout if `pilot worktree create` reports one — the error names both knobs.
:::

## Customization (Team / Enterprise)

Compose custom steps into core workflow skills and ship team rules, hooks, and agents. Source is either a git URL (team-wide) or a local directory (personal). See [Customization](/docs/features/customization) for the full overlay schema.

| Command | Description |
|---------|-------------|
| `pilot customize install <source> [--branch <b>] [--subfolder <p>] [--json]` | Install and apply. `<source>` = git URL or local directory path. |
| `pilot customize update [--json]` | Re-apply — pulls git sources, reads local sources in place |
| `pilot customize status [--json]` | Show active source, file counts, and drift warnings |
| `pilot customize diff <skill>/<step-id> [--json]` | Unified diff between pinned replacement and current upstream |
| `pilot customize remove [--json]` | Delete pack files and regenerate pristine `SKILL.md` |

## Internal commands

Called by hooks and the Console — you rarely need to run these directly.

| Command | Description |
|---------|-------------|
| `pilot check-context --json` | Get current context usage percentage |
| `pilot register-plan <path> <status> [--lane <id>]` | Associate a plan file or Buildout with the current session, or with an [orchestration lane](#orchestration-lanes). Prints a warning when `<path>` is outside the scanned directories — the Console only displays files in `<project>/docs/plans/`, `<project>/docs/builds/`, or the same pair under `<worktree base>/<slug>/` (the worktree base is `<project>/.worktrees/` unless configured otherwise) |
| `pilot review-scope [--slug <slug>] [--lane <id>] [--json]` | Resolve the `git diff` scope a code review should read — the single source of truth for review diff scope. Prints a range you splice directly (`git diff $(pilot review-scope) -- <files>`); `--json` adds `mode` (`working-tree` or `worktree`), `base_ref`, and a `warning` when the scope degraded or the resolved range is empty. Empty ranges remain empty rather than widening into unrelated code. In worktree mode it returns the fork-point range `<base_branch>...HEAD` against the branch's *detected* base — never a hardcoded `main`, and never a two-dot range against the base branch's live tip. Pass `--lane` for an [orchestration lane](#orchestration-lanes): its branch is `spec/<slug>-<lane>`, so an unflagged resolve finds nothing and degrades loudly. |
| `pilot sessions [--json]` | Show count of active Pilot sessions |
| `pilot statusline` | Status line formatter *(Claude Code only — called by Claude Code's statusLine hook)*. `pilot statusline -h` lists what each line renders and shows how to wrap it in your own status line |
| `pilot notify <type> <title> <message> [--plan-path PATH] [--json]` | Send a notification to the Console dashboard (type: `info`, `plan_approval`, `attention_needed`, `verification_complete`) |
| `pilot skill-build <skill-dir> [--output <path>] [--dry-run] [--json]` | Build `SKILL.md` and `hashes.json` from a skill's manifest + fragments |
