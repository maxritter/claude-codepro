## CLI Tools

<!-- CC-ONLY -->
### Native file tools first

For ordinary local file inspection, use **Read** (`offset`/`limit` for a range), **Grep** for exact text, and **Glob** for file patterns. Do not replace these with Bash `cat`, `sed -n`, `head`, `tail`, shell `grep`/`rg`, or Python/Node scripts that merely print files when the native tool is available.

Batch independent work as separate native tool calls in the same response. Do not combine file reads into a long Bash command with `echo` headings or separators. Keep Bash for tests, builds, git, API probes, live log streams, and actual computation or shell processing. Use Edit/Write for ordinary source changes; established generators and codemods remain appropriate.

RTK optimizes commands that need a shell. It is not a reason to replace native file tools with a shell wrapper. Follow an explicit user-requested command or a real capability limitation when it requires a different approach.

### Background output and waiting

For a command that needs resumable background execution, start it with `Bash` and `run_in_background: true`. Retain its returned task ID and output path; collect or wait through the native task tools exposed by this runtime. Reuse an existing job's handle instead of relaunching its command, and continue independent work while it runs.

Inspect available output directly with `Read` and a bounded range. An output snapshot does not prove the job finished. For a condition wait, use `Monitor` with an until-loop when that tool is exposed, or the runtime's supported wait mechanism. Do not prefix output reads with a long Bash `sleep`, or chain shorter sleeps to evade a native block.
<!-- /CC-ONLY -->

### Pilot CLI

`~/.pilot/bin/pilot`. This is a reference for non-obvious contracts, not an exhaustive command allowlist. Discover additional commands and flags through the installed CLI's `--help`; do not invent syntax from a likely name.

| Group | Commands |
|-------|----------|
| Session | `check-context --json`, `register-plan <path> <status> [--lane <id>]` |
| Review | `review-scope [--slug <slug>] [--lane <id>] [--json]` — resolver for a Pilot workflow review's `git diff` scope; use an explicit user-supplied patch/range directly when that is the requested review artifact |
| Worktree | `worktree detect\|create\|diff\|sync\|cleanup --json <slug> [--lane <id>]` (slug = plan filename without date prefix and `.md`; `create` auto-stashes). `worktree status --json [--lane <id>]` takes **no** slug — it reports the worktree for the *current session*. Use `detect` for a specific plan's branch or base branch. |
| License | `activate <key>`, `deactivate`, `status`, `verify`, `trial --check\|--start` |
| Updates | `update [--yes] [--json]` (alias `upgrade`) — user-initiated; don't run it unasked |
| Other | `greet`, `statusline`, `notify` |

**`review-scope`: scripts and skills must use `--json` and parse it.** A `pilot` older than this subcommand prints a banner and exits 0, so a `|| echo HEAD` fallback never fires and the banner text gets spliced into `git diff`. `--json` returns `mode` (`working-tree` | `worktree`), `base_ref`, `diff_range`, and a `warning` when the scope degraded.

⛔ **A `warning` from `review-scope` is a stop sign, not a footnote.** It means the resolver found a live worktree it could not claim (almost always a missing or wrong `--lane`) and fell back to `git diff HEAD`. That diff is EMPTY when the work is committed on the worktree branch, so a review run against it scans nothing and reports clean — indistinguishable from a genuinely clean review. Fix what the warning names and re-resolve. `review-scope` takes `--lane` for exactly this reason: pass it wherever the `worktree` subcommands take it.

**`worktree sync` has three exit codes.** `0` clean · `1` nothing landed · **`2` the squash landed but the base checkout's own uncommitted work could not be restored** and is in `git stash list`. The JSON still reports `"success": true` — the merge did succeed. Exit 2 exists so a chained `&& pilot worktree cleanup` stops before deleting the worktree; surface the `stash_warning` and the `git stash pop` recovery instead of re-running cleanup. `create` and `sync` both serialize on a repo-wide lock, so concurrent runs queue rather than interleaving their changes to the shared base checkout.

**`--lane <id>` is for orchestration lanes only.** A coordinating session dispatching `/spec`, `/fix`, or `/build` runs as concurrent subagents passes it on every `register-plan` and `worktree` call, because a subagent can resolve the same session id as its parent. It scopes session state to `~/.pilot/sessions/<session>/lanes/<id>/` and keys the worktree on `(slug, lane)`. Use the lane assigned to this workflow; do not invent or reuse another run's lane. Never fall back to an unflagged call when `--lane` is unsupported — that would put the lane's plan in the coordinator's slot.

### RTK — token-optimized CLI proxy

The Pilot shell hook auto-rewrites commands (`git status` → `rtk git status`), so normally you do nothing. Direct use: `rtk gain` (savings analytics), `rtk gain --history`, `rtk discover`, `rtk proxy <cmd>` (bypass filtering when debugging).

⚠️ If `rtk gain` errors, a different `rtk` (Rust Type Kit) is on PATH.

### Semble — code search CLI

Same engine as the Semble MCP server; see `mcp-servers.md` for when to reach for it over CodeGraph.

```bash
semble search "authentication flow" ./          # intent
semble search "save_pretrained" ./ --top-k 10   # symbol
semble find-related src/auth.ts 42 ./           # similar code from a location
semble savings                                  # token-saving report
```

Ranking adapts to the query shape (symbol-like queries weight lexical, natural language balances semantic + lexical), boosts definitions over references, and down-ranks test/legacy/example files. Auto-reindexes on file change. Defaults are usually right — snippets are already trimmed to the matched code.

**Not for:** callers/callees/impact (CodeGraph enumerates those; Semble only finds code that *mentions* a callee), AST pattern matching, or extracting the enclosing block at `file:line` (use `Read` with `offset`/`limit`).

### ast-grep — structural search and codemods

Use `ast-grep` when the question depends on syntax rather than literal text.
Keep Semble for intent, CodeGraph for relationships, and the agent's exact-search
tool for exhaustive literal search. Use the canonical command, not the deprecated `sg` alias.

```bash
ast-grep run --pattern '$ARR.filter($F).map($M)' --lang ts \
  --json=compact console/src \
  | jq '[.[] | {path: .file, line: (.range.start.line + 1)}]'
```

Quote metavariables with single quotes. ast-grep JSON lines are zero-based, so
add one for ordinary source line numbers. Project directly to requested fields;
raw JSON includes the matched source. For rewrites, preview the narrowest
pattern first, apply with `--rewrite ... --update-all`, then inspect the diff and
run focused compiler/tests. Preserve quoting for metavariables and inspect the
changed files before accepting a rewrite.
