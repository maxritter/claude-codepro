"""Names of session-scoped artifacts shared by hook readers and cleanup."""

from __future__ import annotations

PAUSE_SENTINELS = (
    "spec-approval-pending",
    "build-handback-pending",
    "verify-gate-pending",
)

# Retired discussion-pause marker retained only so SessionStart migration and
# stale-session cleanup can remove files written by older Pilot releases.
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
