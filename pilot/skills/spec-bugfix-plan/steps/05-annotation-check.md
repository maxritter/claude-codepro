## Step 5: Check for Console Annotation Feedback (Before Approval)

<!-- CC-ONLY -->
While native plan mode is active, read annotations from the registered plan and incorporate them only into the permitted native draft. Defer deletion until successful native exit. Before cleanup, reread the annotation file and remove only entries actually incorporated; preserve new or unrelated feedback.
<!-- /CC-ONLY -->

**Run this before Step 6 (approval).** Check if the user has annotated the plan in the Console's Specifications tab. Annotations auto-save to JSON — no "Send Feedback" button needed.

1. Derive annotation file: `docs/plans/.annotations/<plan-filename>.json`
2. Read the annotation file with the Read tool. If the file doesn't exist, treat as `NO_FEEDBACK`. If it exists, check whether `planAnnotations` has any entries (`FEEDBACK_EXISTS`) or is empty/missing (`NO_FEEDBACK`).
3. **If `FEEDBACK_EXISTS`:** Each annotation in `planAnnotations` has `originalText` (selected passage) and `text` (user's note). Incorporate into plan, delete the annotation file via `rm -f "<annotation-file-path>"` (e.g. `rm -f "docs/plans/.annotations/2026-03-26-my-bug.json"`), note changes. Proceed to Step 6.
4. **If `NO_FEEDBACK`:** proceed directly to Step 6.
