# Native Planning for Automated Model Switching

Use this runbook only for Claude Code's Automated `/spec` planning. Native plan mode changes both the `opusplan` model leg and the runtime's permitted actions. Follow its file restrictions and native approval mechanism.

## Before entering plan mode

1. Complete the planning skill's branch/worktree setup, create its unapproved `PENDING` header under `docs/plans/`, and register that exact file. Reuse an existing registered draft when resuming it; never overwrite another plan to reserve a filename.
2. Check that this runtime exposes `EnterPlanMode` and `ExitPlanMode`. An orchestration lane must not toggle its parent's permission mode: keep the current model there. If either tool is unavailable, continue planning on the current model with the normal structured approval gate and mention the limitation once.
3. Bind the registered draft before entering read-only mode:

   ```bash
   python3 "$HOME/.pilot/hooks/native_plan_capture.py" prepare-spec "<absolute-registered-plan-path>"
   ```

   If preparation fails, keep the current model and normal approval gate. Do not enter native plan mode without the handoff. A successful preparation records the plan's contents and the current approval setting; it does not approve anything.
4. Call `EnterPlanMode` using its exposed schema. Read the permitted native plan-file path from its result. Use that file as the working draft for the remaining planning steps; retain the registered destination separately. If entering fails, remove this session's `native-spec-planning.json` marker and continue the normal flow on the current model.

The registered destination must resolve inside the current project. A separately located Git worktree is supported only when this session's `worktree.json` names it and Git confirms it is a registered checkout of the same repository/common Git directory. Keep `Worktree: Yes` for that execution identity; do not move or relabel the plan to bypass the ownership check.

Preparation is single-use. The hooks bind it to the matching successful `EnterPlanMode` event and that leg's native draft. A later Enter invalidates the earlier handoff, and an unconfirmed/failed Enter grants nothing. If the runtime does not return the draft path, the hook observes its first native scratch edit and verifies that the file actually changed before using it for automatic approval. Missing binding evidence leaves the normal native dialog in place.

## While planning

Research the full requested scope and write the full Feature/Bugfix plan, including its normal header and task contract, into the permitted native draft. Keep `Status: PENDING` and `Approved: No` in the draft until the approval boundary.

Preserve the reserved plan's `Created`, `Agent`, `Worktree`, `Type`, and `Iterations` values exactly. All canonical header fields must be present once. The capture refuses a partial header or changed execution identity instead of silently deleting metadata. The user may revise the plan's substantive content during native review; the returned approved content remains authoritative.

Only write the file the runtime permits. Other planning steps' instructions to edit `docs/plans/`, update registration, write reviewer output files, create tests, or send notifications are deferred until native plan mode ends. Read-only validation may use the native draft path. Existing Console annotations on the registered plan remain inputs; do not modify them while read-only.

Defer configured reviewer launches until after native approval and before implementation: their durable handle records require writes outside the native draft. Read-only self-checks still run before the dialog. After exit, review the accepted registered plan, including any user edits in that dialog; incorporate material findings and obtain approval for substantive changes to the accepted plan. Do not silently drop a configured reviewer.

Report the observed model only when the runtime supplies evidence. An absent warning does not prove an Opus switch, and a large context does not establish a particular model limit.

## Approval and handoff

At the planning skill's approval step, present the completed native draft through `ExitPlanMode`. This is the approval gate for this path; do not ask for a second approval with `AskUserQuestion`. When Pilot's approval setting is disabled, the explicitly prepared handoff lets its permission hook complete this gate automatically. Runtime permission constraints still apply.

Approval-disabled automation requires the same active native leg, the unchanged unapproved registered target, and the corresponding trusted native draft with its complete matching header. A marker alone, another scratch file, or unrelated inline plan text cannot approve anything. Legacy bypass-restoration state is cleared so the native dialog's permission choice is preserved.

On a successful exit, the capture hook copies the accepted plan into the exact registered file and sets `Approved: Yes`. It prefers the tool's returned plan because the user may have edited it during review. It refuses to overwrite the registered file if that file changed during planning. The native dialog's permission-mode choice remains in effect.

Read the registered plan after exit. If the hook reports a conflict or missing metadata, reconcile the preserved registered file and the accepted native draft before implementation. A failed or rejected exit grants no approval; keep planning or honor the user's feedback. If the hook is unavailable, a confirmed successful native approval permits you to materialize the accepted draft yourself, preserving concurrent edits and repairing only workflow metadata. Remove the handoff marker after successful recovery.

Before implementation, run `pilot spec validate "<registered-plan-path>" --json` on the accepted registered file and complete every deferred configured review against that exact content. If an earlier review exists, compare its `reviewed_sha256` with the accepted plan; user dialog edits invalidate stale review evidence. Rerun the applicable review for substantive changes, and obtain approval for any subsequent substantive plan edits. Metadata-only changes such as `Approved` do not require another approval. Never treat the native dialog's success as proof that an edited task contract was reviewed or validated.

After validation and review, continue immediately with `spec-implement` using `<registered-plan-path> $LANE_FLAG` (empty lane flag for this native main-session path). Do not issue another model-switch prompt or re-enter plan mode merely because a Console setting changed mid-run.
