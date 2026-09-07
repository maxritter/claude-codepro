"""Names of session-scoped artifacts shared by hook readers and cleanup."""

from __future__ import annotations

PAUSE_SENTINELS = (
    "spec-approval-pending",
    "build-handback-pending",
    "verify-gate-pending",
)

# User-consented discussion pause. NOT one of the one-shot gate sentinels
# above: the stop guard honors it only on user-initiated turns and never for a
# Type: Build plan -- repeatedly on Claude Code (sticky across discussion
# turns), consumed per honor on Codex (no stop_hook_active in its payload).
# The skill clears it on resume.
DISCUSSION_PAUSE = "spec-discussion-paused"
NATIVE_SPEC_PLANNING = "native-spec-planning.json"

STALE_SESSION_FILES = (
    "active_plan.json",
    "plan-mode-active",
    "bypass-restore-pending",
    "pre-plan-permission-mode",
    "plan-model-warned",
    "plan-model-confirmed",
    "preflight-context-warned",
    NATIVE_SPEC_PLANNING,
    "spec-stop-guard",
    *PAUSE_SENTINELS,
    DISCUSSION_PAUSE,
    "continuation.md",
    "context-cache.json",
    "context-pct.json",
    "pre-compact-state.json",
)

STALE_SESSION_PATTERNS = (
    "findings-spec-review*.json",
    "findings-changes-review*.json",
    "findings-codex-spec-review*.json",
    "findings-codex-changes-review*.json",
)
