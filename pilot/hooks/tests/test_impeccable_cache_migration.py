"""Tests for the one-time project-local Impeccable cache cleanup."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from impeccable_cache_migration import _get_project_dir, migrate_legacy_cache


def test_atomically_pretty_formats_valid_legacy_cache(tmp_path: Path) -> None:
    cache = tmp_path / ".impeccable" / "hook.cache.json"
    cache.parent.mkdir()
    cache.write_text('{"session":"abc","findings":[{"rule":"gradient"}]}')
    cache.chmod(0o640)

    assert migrate_legacy_cache(tmp_path) is True

    assert json.loads(cache.read_text()) == {
        "session": "abc",
        "findings": [{"rule": "gradient"}],
    }
    assert cache.read_text().endswith("\n")
    assert "\n  \"findings\"" in cache.read_text()
    assert cache.stat().st_mode & 0o777 == 0o640
    assert list(cache.parent.glob(".*.tmp")) == []


def test_already_pretty_cache_is_a_noop(tmp_path: Path) -> None:
    cache = tmp_path / ".impeccable" / "hook.cache.json"
    cache.parent.mkdir()
    cache.write_text(json.dumps({"editCount": 1}, indent=2) + "\n")
    before = cache.stat().st_mtime_ns

    assert migrate_legacy_cache(tmp_path) is False
    assert cache.stat().st_mtime_ns == before


def test_invalid_cache_is_preserved_byte_for_byte(tmp_path: Path) -> None:
    cache = tmp_path / ".impeccable" / "hook.cache.json"
    cache.parent.mkdir()
    cache.write_bytes(b'{"partial":')

    assert migrate_legacy_cache(tmp_path) is False
    assert cache.read_bytes() == b'{"partial":'


def test_symlink_cache_is_not_rewritten(tmp_path: Path) -> None:
    target = tmp_path / "target.json"
    target.write_text('{"editCount":1}')
    cache = tmp_path / ".impeccable" / "hook.cache.json"
    cache.parent.mkdir()
    cache.symlink_to(target)

    assert migrate_legacy_cache(tmp_path) is False
    assert target.read_text() == '{"editCount":1}'


def test_project_dir_prefers_codex_then_claude(monkeypatch) -> None:
    monkeypatch.setenv("CODEX_WORKSPACE", "/codex/project")
    monkeypatch.setenv("CLAUDE_PROJECT_ROOT", "/claude/project")
    assert _get_project_dir() == Path("/codex/project")

    monkeypatch.delenv("CODEX_WORKSPACE")
    assert _get_project_dir() == Path("/claude/project")


def test_race_preserves_newer_cache_contents(tmp_path: Path) -> None:
    cache = tmp_path / ".impeccable" / "hook.cache.json"
    cache.parent.mkdir()
    cache.write_text('{"editCount":1}')

    original_read_bytes = Path.read_bytes
    reads = 0

    def racing_read(path: Path) -> bytes:
        nonlocal reads
        value = original_read_bytes(path)
        if path == cache:
            reads += 1
            if reads == 1:
                cache.write_text('{"editCount":2}')
        return value

    with patch.object(Path, "read_bytes", racing_read):
        assert migrate_legacy_cache(tmp_path) is False

    assert cache.read_text() == '{"editCount":2}'
