## Phase B — Verify the Running Program

All code is finalized. No more code changes except critical bugs found during execution.

**If runtime profile is Minimal:** Skip service deployment and browser setup. Execute the changed CLI, script, hook, or library entry point in Step 5, and complete Step 6 using the relevant command or artifact evidence.

For API and Full profiles, use Step 7's `7a-pre` to resolve an authorized live target before declaring runtime verification unavailable. Record a concrete blocker and its effect on the plan's criteria.

## Step 4: Build, Deploy, and Verify Code Identity

#### 4a: Build

Build/compile the project. Verify zero errors.

#### 4b: Deploy (if applicable)

If artifacts run separately from source, use an isolated test installation or an already-authorized deployment target. Confirm process ownership before restarting a service; do not disrupt shared or user-owned services merely to verify the change.

For platform deployments, follow `07-e2e-and-final-regression.md` § 7a-pre. Do not infer a safe preview target or permission from an authenticated CLI.

#### 4c: Code Identity Verification

**⛔ Prove the running instance uses your new code before testing it.**

1. Identify a behavioral change unique to this implementation
2. Craft a request only new code handles correctly (e.g., query with new parameter — new code returns filtered results, old code ignores parameter)
3. If response matches OLD behavior → redeploy, restart, re-verify
4. **Do NOT proceed** to execution testing until code identity is confirmed
