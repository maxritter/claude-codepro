## Step 6: Per-Task DoD Audit & Not-Verified Acknowledgment

### 6.1 Per-Task DoD Audit

For EACH task, match its Definition of Done criteria to authoritative evidence: command output, generated artifact, API response, or observed UI. Reuse current-tree evidence already collected in this run; execute a new check when a criterion remains unproven.

If any criterion unmet: fix inline if possible, or add a task and route the loop-back through Step 11's iteration-cap check (which sets `Status: PENDING`, increments `Iterations`, and re-invokes spec-implement — or surfaces to the user at the cap). Never loop back without passing that check.

### 6.2 Documentation Sync

The Step 1b staging note defers doc-sync to here — this is where it happens, before the review gate and any commit.

Ask once: **did this change something a reader of the docs is told?** A public API or CLI flag added/renamed/removed, documented behaviour changed, a config field or default changed, a new command/route/endpoint, a breaking change, or a shifted directory layout — each of those means the docs are now wrong, and a stale doc is a bug this spec introduced.

If yes, update them in this same change (`documentation-sync.md` has the full trigger table and the locate → update-minimally → verify-counts procedure), then re-stage. Grep the docs tree for the symbols and flags the diff touched rather than trusting memory; off-by-one counts ("supports 3 backends") are the most common stale-doc defect.

If genuinely doc-irrelevant — internal refactor, test-only change, a fix restoring already-documented behaviour — record "no doc impact" explicitly so the reader knows it was considered, not forgotten.

### 6.3 Not Verified Acknowledgment

List what was **NOT** verified and why. Include in the verification report (Step 10). Every gap must have a reason:

| Not Verified | Reason |
|-------------|--------|
| [criterion or scenario] | No test environment / Out of scope / Untestable statically / Deferred |

"None — all criteria have automated verification" is a valid answer if true. Do not omit this section: absence of acknowledged gaps ≠ absence of real gaps.
