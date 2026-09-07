"""Tests for session_announcements hook -- CC-only SessionStart one-time
announcements, re-injected until the user acknowledges (ack sentinel)."""

from __future__ import annotations

from pathlib import Path

from session_announcements import (
    ANNOUNCEMENTS,
    _ack_path,
    pending,
    render_context,
)


class TestRegistry:
    def test_stale_pin_era_announcements_pruned(self) -> None:
        ids = [a["id"] for a in ANNOUNCEMENTS]
        for stale in (
            "automated-model-switching",
            "model-switching-1m-planning",
            "configurable-plan-exec-models",
            "fable-5-support",
            "opusplan-sonnet-default",
            "model-switching-modes",
            "opus-5",
        ):
            assert stale not in ids

    def test_every_announcement_has_id_and_message(self) -> None:
        for a in ANNOUNCEMENTS:
            assert a["id"] and isinstance(a["id"], str)
            assert a["message"] and isinstance(a["message"], str)


class TestPending:
    def test_all_pending_when_no_ack_sentinels(self, tmp_path: Path) -> None:
        result = pending(tmp_path, ANNOUNCEMENTS)
        assert len(result) == len(ANNOUNCEMENTS)

    def test_acked_announcement_excluded(self, tmp_path: Path) -> None:
        _ack_path("automated-model-switching", tmp_path).touch()
        result = pending(tmp_path, ANNOUNCEMENTS)
        assert all(a["id"] != "automated-model-switching" for a in result)

    def test_custom_registry_all_acked_returns_empty(self, tmp_path: Path) -> None:
        reg = [{"id": "x", "message": "hello"}]
        _ack_path("x", tmp_path).touch()
        assert pending(tmp_path, reg) == []

    def test_ack_path_under_pilot_dir(self, tmp_path: Path) -> None:
        p = _ack_path("foo", tmp_path)
        assert p == tmp_path / ".announce-foo-ack"


class TestRenderContext:
    def test_includes_message(self) -> None:
        reg = [{"id": "x", "message": "BIG NEWS"}]
        ctx = render_context(reg)
        assert "BIG NEWS" in ctx
        # Ack is handled by the hook itself -- no touch instruction needed.
        assert "touch" not in ctx
        # Must instruct display-only, not interactive acknowledgment.
        assert "text output" in ctx

    def test_empty_pending_returns_empty_string(self) -> None:
        assert render_context([]) == ""
