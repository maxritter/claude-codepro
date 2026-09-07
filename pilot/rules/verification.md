## Verification

Evidence must support the specific completion claim. Use the focused checks and required project gates from `testing.md`; do not add a separate generic review loop or repeat a successful check solely because a new message or workflow phase began.

### Match evidence to the changed surface

| Claim | Relevant evidence |
|-------|-------------------|
| Tests pass | Completed run and exit status for the stated suite and artifact |
| Build succeeds | The relevant build completes successfully |
| Bug fixed | The original failing test, command, or interaction now produces the expected result |
| Regression test catches the defect | It fails without the fix and passes with it, using an isolated copy or controlled mutation if needed |
| CLI or API works | Execute the affected command or request and check its output and side effects |
| UI works | Exercise the affected interaction and inspect its resulting rendered state |
| Installed artifact works | Build/install identity plus execution of that installed copy |
| Performance improved | Representative measurements or profiling with a comparable baseline |
| Agent work integrated | Inspect the resulting files/diff and include them in the relevant checks |

Unit tests with doubles establish isolated behaviour; they cannot establish wiring, packaging, or remote service behaviour. Execute the affected runtime when those boundaries matter. Docs-only, test-only, and internal changes without an affected runtime entry point use their relevant validation instead.

### Find a usable runtime target

Use the project's documented verification path. Reuse an appropriate running server or start its documented local command, polling readiness with a timeout. For mobile, desktop, extensions, and packaged CLIs, verify the built/installed artifact when the change affects that boundary; a source dev server may be insufficient.

If local execution is unavailable, inspect the documented preview or deployed target and the available drivers. Use an already authorized target when it can represent this change. Creating a deployment, replacing a live install, mutating real data, or cleaning up remote resources requires authority for that action; verification is not an automatic grant. Prepare the local artifact and report the concrete remaining gate when that authority is missing.

Do not claim live E2E is impossible merely because no server is running. Check the relevant documented alternatives and report the attempted command/tool and observed blocker. Do not exhaust every cloud provider or force an authentication/deployment tour unrelated to the project's actual target.

### Correctness and reporting

Successful execution is not enough if the output is wrong. Check meaningful outputs and side effects against the contract; for external-data transformations, use an independent source sample or known fixture where necessary.

Confirm unfamiliar paths, environment variables, IDs, versions, library APIs, and tool parameters from current code, tool schemas, commands, or authoritative documentation. Search current sources when the user asks to verify, when facts may have changed, or when uncertainty affects the result. Distinguish evidence, inference, and unverified assumptions.

Completion reports identify what changed, what was checked, and material remaining uncertainty. Reuse still-valid evidence from this task and identify its scope; rerun after changes that could invalidate it. Never turn an unrun check, a pending process, a source-only inspection, or another agent's success message into a claim of passing runtime verification.

When execution reveals a defect, fix it within the authorized scope, then rerun the affected check. Attribute unrelated failures as described in `testing.md`. Surface any deliberate `SHORTCUT:` introduced or materially affected by this change with its practical ceiling and upgrade trigger; avoid scanning or reporting unrelated historical debt.
