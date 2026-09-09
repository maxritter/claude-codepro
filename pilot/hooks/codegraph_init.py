"""SessionStart hook: ensure CodeGraph is initialized and synced for the current project.

Mirrors the installer initialization logic as a Claude Code async hook. Codex
does not initialize repositories automatically; indexing remains an explicit
user decision there.

Non-fatal: failures are silent — the session proceeds without CodeGraph.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

SYNC_TIMEOUT_SECONDS = 60
STATUS_TIMEOUT_SECONDS = 10
INDEX_TIMEOUT_SECONDS = 90
INIT_TIMEOUT_SECONDS = 60
LOCK_STALE_SECONDS = 15 * 60
# Finish (and reap) before the 120s SessionStart hook timeout the harness enforces.
# If the harness kills the wrapper first, an in-flight process group is orphaned —
# so the cumulative work per invocation is clamped to stay under that ceiling.
HOOK_BUDGET_SECONDS = 110


def _is_in_git_repo(directory: Path) -> bool:
    current = directory.resolve()
    while True:
        if (current / ".git").exists():
            return True
        parent = current.parent
        if parent == current:
            return False
        current = parent


def _has_git_commits(directory: Path) -> bool:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"],
            capture_output=True,
            cwd=directory,
            timeout=5,
        )
        return result.returncode == 0
    except (subprocess.SubprocessError, OSError):
        return False


def _is_indexed(project_dir: Path) -> bool:
    db_path = project_dir / ".codegraph" / "codegraph.db"
    if not db_path.exists():
        return False
    try:
        return db_path.stat().st_size > 1_000_000
    except OSError:
        return False


def _kill_group(proc: subprocess.Popen[bytes]) -> None:
    """SIGKILL the subprocess's whole process group, then reap it.

    Worker children (e.g. CodeGraph's Node workers) must die with the parent;
    killing only proc.pid would orphan them.
    """
    try:
        if os.name == "posix":
            os.killpg(proc.pid, signal.SIGKILL)
        else:
            proc.kill()
    except (ProcessLookupError, OSError):
        pass
    try:
        proc.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        # SIGKILL'd but a pipe is still held; force-reap so we don't leak a zombie.
        proc.kill()
        try:
            proc.wait(timeout=5)
        except (subprocess.SubprocessError, OSError):
            pass
    except OSError:
        pass


def _run_group(cmd: list[str], cwd: Path, timeout: int) -> subprocess.CompletedProcess[bytes] | None:
    """Run cmd in its own process group; on timeout kill the entire group.

    subprocess.run(timeout=...) SIGKILLs only the direct child and leaves any
    worker subprocesses running — the orphan that piled up across session starts.
    Spawning in a new session and killpg-ing on timeout reaps the whole tree.
    Returns None on timeout or spawn failure.
    """
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=cwd,
            env={**os.environ, "CODEGRAPH_TELEMETRY": "0"},
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=os.name == "posix",
        )
    except OSError:
        return None
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except (subprocess.TimeoutExpired, OSError):
        _kill_group(proc)
        return None
    return subprocess.CompletedProcess(cmd, proc.returncode, stdout, stderr)


def _run(cmd: list[str], cwd: Path, timeout: int = 120) -> bool:
    result = _run_group(cmd, cwd, timeout)
    return result is not None and result.returncode == 0


def _reindex_recommended(project_dir: Path, timeout: int) -> bool:
    """Read CodeGraph's explicit index-migration signal without mutating state."""
    result = _run_group(["codegraph", "status", "--json"], project_dir, timeout)
    if result is None or result.returncode != 0:
        return False
    try:
        status = json.loads((result.stdout or b"").decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError):
        return False
    index = status.get("index") if isinstance(status, dict) else None
    return isinstance(index, dict) and index.get("reindexRecommended") is True


def _op_timeout(deadline: float, cap: int) -> int:
    """Timeout for the next op: its cap, clamped to the time left in the hook budget.

    Keeps the total wall-clock under the harness hook timeout so _run_group's own
    timeout (and its process-group reap) always fires before the harness can kill
    the wrapper and orphan an in-flight group. Floored at 1s.
    """
    return max(1, min(cap, int(deadline - time.monotonic())))


def _project_lock_dir(project_dir: Path) -> Path:
    digest = hashlib.sha256(str(project_dir.resolve()).encode("utf-8")).hexdigest()[:24]
    return Path.home() / ".pilot" / "cache" / "codegraph-init" / digest


def _is_stale_lock(lock_dir: Path) -> bool:
    try:
        return time.time() - lock_dir.stat().st_mtime > LOCK_STALE_SECONDS
    except OSError:
        return True


@contextmanager
def _project_lock(project_dir: Path) -> Iterator[bool]:
    lock_dir = _project_lock_dir(project_dir)
    acquired = False
    try:
        lock_dir.parent.mkdir(parents=True, exist_ok=True)
        try:
            lock_dir.mkdir()
        except FileExistsError:
            if not _is_stale_lock(lock_dir):
                yield False
                return
            shutil.rmtree(lock_dir, ignore_errors=True)
            try:
                lock_dir.mkdir()
            except FileExistsError:
                yield False
                return

        acquired = True
        try:
            (lock_dir / "pid").write_text(f"{os.getpid()}\n")
        except OSError:
            pass
        yield True
    except OSError:
        yield True
    finally:
        if acquired:
            shutil.rmtree(lock_dir, ignore_errors=True)


def _is_corrupt_db_error(stderr: str) -> bool:
    lower = stderr.lower()
    return (
        "database disk image is malformed" in lower
        or "file is not a database" in lower
        or "database is corrupt" in lower
        or "sqlite_corrupt" in lower
    )


def _recover_corrupt_db(project_dir: Path) -> bool:
    codegraph_dir = project_dir / ".codegraph"
    if not codegraph_dir.exists():
        return False
    try:
        shutil.rmtree(codegraph_dir)
    except OSError:
        return False
    return True


def _get_project_dir() -> Path:
    for var in ("CODEX_WORKSPACE", "CLAUDE_PROJECT_ROOT"):
        val = os.environ.get(var, "").strip()
        if val:
            return Path(val)
    return Path.cwd()


def main() -> None:
    if not shutil.which("codegraph"):
        return

    project_dir = _get_project_dir()

    if not _is_in_git_repo(project_dir):
        return

    deadline = time.monotonic() + HOOK_BUDGET_SECONDS

    with _project_lock(project_dir) as acquired:
        if not acquired:
            return

        if not _has_git_commits(project_dir):
            return

        codegraph_dir = project_dir / ".codegraph"

        if not codegraph_dir.exists():
            if os.environ.get("CLAUDE_PROJECT_PLATFORM") == "codex":
                return
            if not _run(["codegraph", "init"], project_dir, _op_timeout(deadline, INIT_TIMEOUT_SECONDS)):
                return
            if not codegraph_dir.exists():
                return

        if not _is_indexed(project_dir):
            _run(["codegraph", "index"], project_dir, _op_timeout(deadline, INDEX_TIMEOUT_SECONDS))
            return

        if _reindex_recommended(project_dir, _op_timeout(deadline, STATUS_TIMEOUT_SECONDS)):
            _run(["codegraph", "index"], project_dir, _op_timeout(deadline, INDEX_TIMEOUT_SECONDS))
            return

        result = _run_group(["codegraph", "sync", "-q"], project_dir, _op_timeout(deadline, SYNC_TIMEOUT_SECONDS))
        if result is not None and result.returncode != 0:
            stderr = (result.stderr or b"").decode("utf-8", errors="replace")
            if _is_corrupt_db_error(stderr) and _recover_corrupt_db(project_dir):
                _run(["codegraph", "init", "-i"], project_dir, _op_timeout(deadline, INDEX_TIMEOUT_SECONDS))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    finally:
        sys.exit(0)
