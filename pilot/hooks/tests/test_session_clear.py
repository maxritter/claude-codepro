"""Tests for session_clear hook — stale session state cleanup on /clear."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest
import session_clear


def test_removes_stale_findings_files_with_slug(tmp_path: Path):
    """Should delete slug-based reviewer findings from session directory."""
    session_dir = tmp_path / "sessions" / "1001"
    session_dir.mkdir(parents=True)
    (session_dir / "findings-spec-review-sku-builder-modal.json").write_text("{}")
    (session_dir / "findings-changes-review-sku-builder-modal.json").write_text("{}")
    # Also old format (no slug) for backward compat
    (session_dir / "findings-spec-review.json").write_text("{}")
    (session_dir / "findings-changes-review.json").write_text("{}")

    with (
        patch.dict(os.environ, {"PILOT_SESSION_ID": "1001"}),
        patch.object(session_clear, "SESSIONS_DIR", tmp_path / "sessions"),
    ):
        result = session_clear.main()

    assert result == 0
    assert not (session_dir / "findings-spec-review-sku-builder-modal.json").exists()
    assert not (session_dir / "findings-changes-review-sku-builder-modal.json").exists()
    assert not (session_dir / "findings-spec-review.json").exists()
    assert not (session_dir / "findings-changes-review.json").exists()


def test_removes_findings_from_multiple_specs(tmp_path: Path):
    """Should delete findings from multiple /spec runs in the same session."""
    session_dir = tmp_path / "sessions" / "1001"
    session_dir.mkdir(parents=True)
    # Two different specs ran in this session
    (session_dir / "findings-spec-review-dashboard-redesign.json").write_text("{}")
    (session_dir / "findings-changes-review-dashboard-redesign.json").write_text("{}")
    (session_dir / "findings-spec-review-webhook-ingestion.json").write_text("{}")
    (session_dir / "findings-changes-review-webhook-ingestion.json").write_text("{}")

    with (
        patch.dict(os.environ, {"PILOT_SESSION_ID": "1001"}),
        patch.object(session_clear, "SESSIONS_DIR", tmp_path / "sessions"),
    ):
        result = session_clear.main()

    assert result == 0
    findings = list(session_dir.glob("findings-*.json"))
    assert findings == [], f"Expected no findings files, found: {[f.name for f in findings]}"


def test_removes_all_stale_state(tmp_path: Path):
    """Should delete all stale session files (fixed names + pattern-matched)."""
    session_dir = tmp_path / "sessions" / "1001"
    session_dir.mkdir(parents=True)
    for name in session_clear.STALE_FILES:
        (session_dir / name).write_text("stale")
    # Also create pattern-matched findings files
    (session_dir / "findings-spec-review-some-plan.json").write_text("stale")
    (session_dir / "findings-changes-review-some-plan.json").write_text("stale")

    with (
        patch.dict(os.environ, {"PILOT_SESSION_ID": "1001"}),
        patch.object(session_clear, "SESSIONS_DIR", tmp_path / "sessions"),
    ):
        result = session_clear.main()

    assert result == 0
    for name in session_clear.STALE_FILES:
        assert not (session_dir / name).exists(), f"{name} should have been deleted"
    findings = list(session_dir.glob("findings-*.json"))
    assert findings == [], f"Expected no findings files, found: {[f.name for f in findings]}"


def test_clear_removes_every_current_pause_sentinel(tmp_path: Path):
    """The cleanup registry must cover approval, build hand-back, and verify gates."""
    from _lib.session_artifacts import PAUSE_SENTINELS

    session_dir = tmp_path / "sessions" / "1001"
    session_dir.mkdir(parents=True)
    for name in PAUSE_SENTINELS:
        (session_dir / name).write_text("")

    with (
        patch.dict(os.environ, {"PILOT_SESSION_ID": "1001"}, clear=True),
        patch.object(session_clear, "SESSIONS_DIR", tmp_path / "sessions"),
    ):
        assert session_clear.main() == 0

    assert all(not (session_dir / name).exists() for name in PAUSE_SENTINELS)


def test_clear_removes_plan_mode_and_preflight_markers(tmp_path: Path):
    markers = (
        "bypass-restore-pending",
        "pre-plan-permission-mode",
        "plan-model-warned",
        "plan-model-confirmed",
        "preflight-context-warned",
        "native-spec-planning.json",
    )
    session_dir = tmp_path / "sessions" / "1001"
    session_dir.mkdir(parents=True)
    for name in markers:
        (session_dir / name).write_text("stale")

    with (
        patch.dict(os.environ, {"PILOT_SESSION_ID": "1001"}, clear=True),
        patch.object(session_clear, "SESSIONS_DIR", tmp_path / "sessions"),
    ):
        assert session_clear.main() == 0

    assert all(not (session_dir / name).exists() for name in markers)


def test_preserves_worktree_json(tmp_path: Path):
    """Should NOT delete worktree.json — it tracks a physical git resource."""
    session_dir = tmp_path / "sessions" / "1001"
    session_dir.mkdir(parents=True)
    (session_dir / "worktree.json").write_text('{"path": "/tmp/wt"}')

    with (
        patch.dict(os.environ, {"PILOT_SESSION_ID": "1001"}),
        patch.object(session_clear, "SESSIONS_DIR", tmp_path / "sessions"),
    ):
        session_clear.main()

    assert (session_dir / "worktree.json").exists()


def test_cleans_task_list(tmp_path: Path):
    """Should remove stale task files from ~/.claude/tasks/pilot-<PID>/."""
    task_dir = tmp_path / ".claude" / "tasks" / "pilot-1001"
    task_dir.mkdir(parents=True)
    (task_dir / "task-abc.json").write_text('{"subject": "Old task"}')
    (task_dir / "task-def.json").write_text('{"subject": "Another old task"}')

    session_dir = tmp_path / "sessions" / "1001"
    session_dir.mkdir(parents=True)

    with (
        patch.dict(os.environ, {"PILOT_SESSION_ID": "1001"}),
        patch.object(session_clear, "SESSIONS_DIR", tmp_path / "sessions"),
        patch("session_clear.Path.home", return_value=tmp_path),
    ):
        session_clear.main()

    json_files = list(task_dir.glob("*.json"))
    assert json_files == [], f"Expected no task files, found: {[f.name for f in json_files]}"


def test_task_cleanup_skips_missing_dir(tmp_path: Path):
    """Should not fail when task directory doesn't exist."""
    session_dir = tmp_path / "sessions" / "1001"
    session_dir.mkdir(parents=True)

    with (
        patch.dict(os.environ, {"PILOT_SESSION_ID": "1001"}),
        patch.object(session_clear, "SESSIONS_DIR", tmp_path / "sessions"),
        patch("session_clear.Path.home", return_value=tmp_path),
    ):
        result = session_clear.main()

    assert result == 0


def test_stale_files_still_cleaned_when_pilot_session_id_unset(tmp_path: Path):
    """Issue #157: with EVERY session-id env var unset, resolve_session_id() falls all
    the way through to 'default' (same as the pre-fix narrow fallback) - so stale-file
    cleanup must still run against sessions/default/, not bail out of the whole hook.
    Task-list cleanup has no real PID to build 'pilot-<PID>' from, so it must be
    skipped without crashing - proven by not raising, since there's no task dir to
    assert against here.
    """
    session_dir = tmp_path / "sessions" / "default"
    session_dir.mkdir(parents=True)
    (session_dir / "active_plan.json").write_text("{}")

    with (
        patch.dict(os.environ, {}, clear=True),
        patch.object(session_clear, "SESSIONS_DIR", tmp_path / "sessions"),
    ):
        result = session_clear.main()

    assert result == 0
    assert not (session_dir / "active_plan.json").exists(), (
        "stale-file cleanup must run against the resolve_session_id() result even "
        "when PILOT_SESSION_ID is unset, not no-op the entire hook"
    )


def test_stale_files_cleaned_via_agent_native_id_when_pilot_session_id_unset(tmp_path: Path):
    """Issue #157: a session launched outside the shell wrapper (IDE/desktop) has no
    PILOT_SESSION_ID but always has CLAUDE_CODE_SESSION_ID set by the harness. /clear
    must find and remove THIS session's stale active_plan.json / plan-mode-active /
    findings files - which live under the resolve_session_id()-based directory, per
    _lib/util.py - not silently skip cleanup because the narrow PILOT_SESSION_ID-only
    lookup found nothing.
    """
    session_dir = tmp_path / "sessions" / "cc-uuid-9999"
    session_dir.mkdir(parents=True)
    (session_dir / "active_plan.json").write_text("{}")
    (session_dir / "plan-mode-active").write_text("1")
    (session_dir / "findings-spec-review-some-plan.json").write_text("{}")

    with (
        patch.dict(os.environ, {"CLAUDE_CODE_SESSION_ID": "cc-uuid-9999"}, clear=True),
        patch.object(session_clear, "SESSIONS_DIR", tmp_path / "sessions"),
    ):
        result = session_clear.main()

    assert result == 0
    assert not (session_dir / "active_plan.json").exists()
    assert not (session_dir / "plan-mode-active").exists()
    assert not (session_dir / "findings-spec-review-some-plan.json").exists()


def test_clear_with_payload_identity_does_not_wipe_shared_default_bucket(tmp_path: Path):
    """Same-repo sibling bleed, destructive direction: /clear in a session whose
    hook payload carries its own session_id (env chain empty) must sweep THAT
    session's directory - not the shared 'default' bucket, where it would silently
    unregister a plan a DIFFERENT env-less session is actively implementing."""
    import io
    import json
    from unittest.mock import patch as _patch

    default_dir = tmp_path / "sessions" / "default"
    default_dir.mkdir(parents=True)
    (default_dir / "active_plan.json").write_text("{}")
    own_dir = tmp_path / "sessions" / "session-b-uuid"
    own_dir.mkdir(parents=True)
    (own_dir / "active_plan.json").write_text("{}")

    with (
        patch.dict(os.environ, {}, clear=True),
        patch.object(session_clear, "SESSIONS_DIR", tmp_path / "sessions"),
        _patch("sys.stdin", io.StringIO(json.dumps({"session_id": "session-b-uuid"}))),
    ):
        assert session_clear.main() == 0

    assert (default_dir / "active_plan.json").exists(), (
        "/clear from a payload-identified session must not unregister the plan of "
        "the env-less session that owns the shared 'default' bucket"
    )
    assert not (own_dir / "active_plan.json").exists(), "/clear must still sweep the clearing session's own directory"


def test_clear_rejects_traversal_payload_session_id(tmp_path: Path):
    """A hook payload session_id is untrusted input feeding a DELETE path: a
    traversal value like '../victim' must never resolve to a directory outside
    SESSIONS_DIR (Codex review finding). It degrades to the legacy resolution
    instead."""
    import io
    import json
    from unittest.mock import patch as _patch

    victim_dir = tmp_path / "victim"
    victim_dir.mkdir(parents=True)
    (victim_dir / "active_plan.json").write_text("{}")
    (tmp_path / "sessions").mkdir()

    with (
        patch.dict(os.environ, {}, clear=True),
        patch.object(session_clear, "SESSIONS_DIR", tmp_path / "sessions"),
        _patch("sys.stdin", io.StringIO(json.dumps({"session_id": "../victim"}))),
    ):
        assert session_clear.main() == 0

    assert (victim_dir / "active_plan.json").exists(), (
        "a traversal payload session_id must not let /clear delete files outside SESSIONS_DIR"
    )


@pytest.mark.parametrize("payload_kind", ["absolute", "non-string"])
def test_clear_rejects_absolute_or_non_string_payload_session_id(tmp_path: Path, payload_kind: str):
    """Absolute and typed JSON values must not become deletion targets."""
    import io
    import json
    from unittest.mock import patch as _patch

    sessions = tmp_path / "sessions"
    default_dir = sessions / "default"
    default_dir.mkdir(parents=True)
    (default_dir / "active_plan.json").write_text("{}")

    victim_dir = tmp_path / "absolute-victim" if payload_kind == "absolute" else sessions / "123"
    victim_dir.mkdir(parents=True)
    (victim_dir / "active_plan.json").write_text("{}")
    payload_id = str(victim_dir) if payload_kind == "absolute" else 123

    with (
        patch.dict(os.environ, {}, clear=True),
        patch.object(session_clear, "SESSIONS_DIR", sessions),
        _patch("sys.stdin", io.StringIO(json.dumps({"session_id": payload_id}))),
    ):
        assert session_clear.main() == 0

    assert (victim_dir / "active_plan.json").exists()
    assert not (default_dir / "active_plan.json").exists()


def test_noop_when_session_dir_missing(tmp_path: Path):
    """Should return 0 when session directory doesn't exist."""
    with (
        patch.dict(os.environ, {"PILOT_SESSION_ID": "9999"}),
        patch.object(session_clear, "SESSIONS_DIR", tmp_path / "sessions"),
    ):
        result = session_clear.main()

    assert result == 0


def test_tolerates_already_missing_files(tmp_path: Path):
    """Should not fail when stale files don't exist."""
    session_dir = tmp_path / "sessions" / "1001"
    session_dir.mkdir(parents=True)
    (session_dir / "active_plan.json").write_text("{}")

    with (
        patch.dict(os.environ, {"PILOT_SESSION_ID": "1001"}),
        patch.object(session_clear, "SESSIONS_DIR", tmp_path / "sessions"),
    ):
        result = session_clear.main()

    assert result == 0
    assert not (session_dir / "active_plan.json").exists()


def test_clear_sweeps_lane_directories(tmp_path: Path):
    """Orchestration lanes keep their state in sessions/<id>/lanes/<lane>/.

    /clear must reach it: a lane's stale active_plan.json left behind would be read
    back by the next run that happens to reuse the same lane id, resurrecting a plan
    the user explicitly cleared.
    """
    session_dir = tmp_path / "sessions" / "42"
    alpha = session_dir / "lanes" / "alpha"
    beta = session_dir / "lanes" / "beta"
    for lane in (alpha, beta):
        lane.mkdir(parents=True)
        (lane / "active_plan.json").write_text("{}")
        (lane / "spec-approval-pending").write_text("")
        (lane / "findings-changes-review-x.json").write_text("{}")
    (session_dir / "active_plan.json").write_text("{}")

    with (
        patch.dict(os.environ, {"PILOT_SESSION_ID": "42"}, clear=True),
        patch.object(session_clear, "SESSIONS_DIR", tmp_path / "sessions"),
    ):
        assert session_clear.main() == 0

    assert not (session_dir / "active_plan.json").exists()
    for lane in (alpha, beta):
        assert not (lane / "active_plan.json").exists(), f"{lane.name} plan survived /clear"
        assert not (lane / "spec-approval-pending").exists()
        assert not (lane / "findings-changes-review-x.json").exists()
    assert not (session_dir / "lanes").exists(), "emptied lane dirs should not be left behind"


def test_clear_preserves_lane_worktree_records(tmp_path: Path):
    """worktree.json tracks a physical git resource that outlives /clear.

    The session-level rule already exempts it; the lane sweep must not be stricter
    than the sweep it mirrors, or /clear would orphan a live git worktree.
    """
    session_dir = tmp_path / "sessions" / "42"
    alpha = session_dir / "lanes" / "alpha"
    alpha.mkdir(parents=True)
    (alpha / "active_plan.json").write_text("{}")
    (alpha / "worktree.json").write_text('{"branch": "spec/x-alpha"}')

    with (
        patch.dict(os.environ, {"PILOT_SESSION_ID": "42"}, clear=True),
        patch.object(session_clear, "SESSIONS_DIR", tmp_path / "sessions"),
    ):
        assert session_clear.main() == 0

    assert not (alpha / "active_plan.json").exists()
    assert (alpha / "worktree.json").exists(), "a live git worktree record must survive /clear"
