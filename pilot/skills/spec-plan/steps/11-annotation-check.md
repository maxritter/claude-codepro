## Step 11: Check for Console Annotation Feedback (Before Approval)

<!-- CC-ONLY -->
While native plan mode is active, read annotations from the registered plan and incorporate them only into the permitted native draft. Defer deletion until successful native exit. Before cleanup, reread the annotation file and remove only entries actually incorporated; preserve new or unrelated feedback.
<!-- /CC-ONLY -->

**Run this before Step 12 (approval).** Check if the user has annotated the plan in the Console's Specifications tab. Annotations auto-save to the unified JSON file — no "Send Feedback" button needed.

1. Derive the annotation file path from the plan path:
   - Plan: `docs/plans/2026-03-26-my-feature.md` → Annotations: `docs/plans/.annotations/2026-03-26-my-feature.json`

2. Read the annotation file with the Read tool. If the file doesn't exist, treat as `NO_FEEDBACK`. If it exists, check whether the `planAnnotations` array contains any entries (`FEEDBACK_EXISTS`) or is empty/missing (`NO_FEEDBACK`).

3. **If `FEEDBACK_EXISTS`:**
   - Each annotation in `planAnnotations` has `originalText` (selected text) and `text` (user's note)
   - Incorporate ALL annotations into the plan: treat each annotation's `text` as the user's instruction for that passage
   - After incorporating: delete the annotation file: `rm -f "<annotation-file-path>"` (e.g. `rm -f "docs/plans/.annotations/2026-03-26-my-feature.json"`). Direct file deletion is used instead of the DELETE API because curl is blocked in several hook environments.
   - Note: "Incorporated user annotations from Console — [N changes]"
   - Proceed to Step 12 with the updated plan

4. **If `NO_FEEDBACK`:** proceed directly to Step 12.
