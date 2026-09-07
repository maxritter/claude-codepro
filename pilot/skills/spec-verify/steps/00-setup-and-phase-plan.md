## Step 0: Setup, Process Overview, & Runtime Classification

### 0.1 Read Toggle Configuration

**Run first, before any other step.** Read the reviewer toggle env vars:

<!-- CC-ONLY -->
```bash
echo "REVIEWER=$PILOT_CHANGES_REVIEW_ENABLED CODEX_CHG=$PILOT_CODEX_CHANGES_REVIEW_ENABLED"
```

Codex reviewers are controlled entirely by Console Settings — the env vars are authoritative.

Reference these values in Steps 1 (changes-review + Codex companion launch) and 3 (review collection).
<!-- /CC-ONLY -->
<!-- CODEX-START
```bash
echo "REVIEWER=$PILOT_CHANGES_REVIEW_ENABLED"
```

Native Codex changes review is controlled by the regular reviewer toggle. Reference this value in Steps 1 and 3.
CODEX-END -->

### 0.2 Process Overview

<!-- CC-ONLY -->
```
Phase A — Finalize the code:
  Launch changes-review sub-agent + Codex companion (if enabled) → Automated Checks (tests + lint + verify commands + Plan Compliance & Goal-Truth Audit) → Feature Parity (if migration) → Collect review findings + Collect Codex Results → Fix

Phase B — Verify the running program (depth depends on runtime profile):
  Build → Program Execution → Per-Task DoD Audit → E2E

Final:
  Regression check → Worktree sync → Post-merge verification → Update status
```
<!-- /CC-ONLY -->
<!-- CODEX-START
```
Phase A — Finalize the code:
  Launch Reviewer → Automated Checks (tests + lint + verify commands) → Feature Parity (if migration) → Collect Review Results → Fix

Phase B — Verify the running program (depth depends on runtime profile):
  Build → Program Execution → Per-Task DoD Audit → E2E

Final:
  Regression check → Worktree sync → Post-merge verification → Update status
```
CODEX-END -->

### 0.3 Classify Runtime Profile

**Determine verification depth based on what changed:**

| Profile | Criteria | Phase B Scope |
|---------|----------|---------------|
| **Minimal** | No server or UI (libraries, CLI tools, hooks, scripts, prose/config) | Applicable build + changed entry-point execution or artifact validation + DoD audit; no browser/service setup |
| **API** | Server/API but no frontend changes | Build + program execution + DoD audit. Skip E2E. |
| **Full** | Frontend/UI changes or complex deployment | All Phase B steps |

Read the plan's Runtime Environment section (if present) and the changed file types to classify.
