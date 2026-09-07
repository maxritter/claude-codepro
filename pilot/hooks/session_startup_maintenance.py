#!/usr/bin/env python3
"""SessionStart hook (Claude Code only): startup housekeeping.

Reclaims cleanup that used to run in the launcher wrapper's `start()` but no
longer fires now that users run `claude` directly (Pilot is admin-only):

1. Stale Claude task files from PID reuse -- `~/.claude/tasks/pilot-<PID>/*.json`
   for the current PID (a recycled PID would otherwise inherit a dead session's
   tasks).
2. Dead-PID Pilot session dirs under `~/.pilot/sessions/` (`<PID>` or
   `<PID>-<suffix>`) whose process is gone.

Conservative by design: it does NOT kill orphaned wrapper processes or clean
worktrees (there are no wrapper processes in
a claude-direct session) and it never touches agent-native UUID/thread dirs
(no PID to probe). Stdlib only (package boundary); never raises.
"""

from __future__ import annotations

import os
import re
import shutil
import sys
from collections.abc import Callable
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lib.util import claude_config_dir  # noqa: E402

# Session dirs are named `<PID>` (Pilot wrapper) or `<PID>-<RANDOM>` (shell-alias
# sessions, where the suffix is bash `$RANDOM` -- all digits). The `-\d+` suffix
# is deliberately strict: agent-native dirs named by CLAUDE_CODE_SESSION_ID /
# CODEX_THREAD_ID (UUID/thread ids, including digit-leading ones like
# `12345678-90ab-cdef-1234`) must NOT match. A loose `-.*` matched them, parsed a
# bogus PID, found it not alive, and rmtree'd a live session's state.
_PID_DIR_RE = re.compile(r"^(\d+)(?:-\d+)?$")
_SKIP_NAMES = {"default", "pipes"}


def _is_pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def clean_task_list(claude_dir: Path, pid: int) -> int:
    """Remove ``*.json`` task files under ``<claude_dir>/tasks/pilot-<pid>/``.

    Returns the number of files removed. Never raises.
    """
    task_dir = claude_dir / "tasks" / f"pilot-{pid}"
    if not task_dir.is_dir():
        return 0
    removed = 0
    try:
        for f in task_dir.iterdir():
            if f.suffix == ".json":
                try:
                    f.unlink(missing_ok=True)
                    removed += 1
                except OSError:
                    pass
    except OSError:
        pass
    return removed


def clean_stale_session_dirs(
    sessions_base: Path,
    my_pid: int,
    is_alive: Callable[[int], bool] = _is_pid_alive,
) -> int:
    """Remove dead-PID session dirs under ``sessions_base``. Returns count removed.

    Skips ``default``/``pipes``, the current PID, dirs for live PIDs, and any
    dir whose name does not start with a PID (agent-native UUID/thread dirs).
    Never raises.
    """
    if not sessions_base.is_dir():
        return 0
    removed = 0
    try:
        entries = list(sessions_base.iterdir())
    except OSError:
        return 0
    for entry in entries:
        if not entry.is_dir() or entry.name in _SKIP_NAMES:
            continue
        match = _PID_DIR_RE.match(entry.name)
        if not match:
            continue
        pid = int(match.group(1))
        if pid == my_pid or is_alive(pid):
            continue
        try:
            shutil.rmtree(entry, ignore_errors=True)
            removed += 1
        except OSError:
            pass
    return removed


def main() -> None:
    # Claude Code only.
    if not os.environ.get("CLAUDE_CODE_ENTRYPOINT"):
        return
    try:
        claude_dir = claude_config_dir()
        if claude_dir is not None:
            clean_task_list(claude_dir, os.getpid())
        clean_stale_session_dirs(Path.home() / ".pilot" / "sessions", os.getpid())
    except Exception:
        # SessionStart hook: never raise / never block the session.
        return


if __name__ == "__main__":
    main()
