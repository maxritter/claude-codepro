#!/usr/bin/env python3
"""SessionEnd hook - complete the session, export memory, then stop the worker.

The complete request and optional worker stop run in one detached finalizer.
The Console waits for the session's memory export before acknowledging the
request, so stopping the worker only after that response avoids truncating the
export. Invocations without ``--session-end`` have no lifecycle side effects.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _lib.console_settings import get_console_url
from _lib.session_artifacts import NATIVE_SPEC_PLANNING
from _lib.util import read_hook_stdin, resolve_session_id

SESSIONS_DIR = Path.home() / ".pilot" / "sessions"
SKIP_NAMES = {"default", "pipes"}
_SESSION_STALENESS_THRESHOLD = 120.0
_AGENT_SESSION_ID_RE = re.compile(r"[0-9A-Fa-f]{8}(?:-[0-9A-Fa-f]{4}){3}-[0-9A-Fa-f]{12}")

# Marks an invocation as a genuine end-of-session rather than an end-of-turn.
SESSION_END_FLAG = "--session-end"

# Fallbacks for the agent's own session id when the hook payload has none.
# PILOT_SESSION_ID is deliberately absent: it is the shell-wrapper / PID id, not
# the ``contentSessionId`` the Console registered at session-init, so posting it
# would always resolve to not_found while looking like it worked.
_CONTENT_SESSION_ID_ENV_CHAIN = ("CLAUDE_CODE_SESSION_ID", "CODEX_THREAD_ID")

# Inlined script run by the detached finalizer. Kept minimal so subprocess
# startup is the only overhead when Console is down. A failed completion leaves
# the worker running so the export can be retried rather than discarded.
_COMPLETE_SESSION_WORKER = """
import json, subprocess, sys, urllib.request
url, sid, stop_script = sys.argv[1], sys.argv[2], sys.argv[3]
req = urllib.request.Request(
    url,
    data=json.dumps({'contentSessionId': sid}).encode(),
    headers={'Content-Type': 'application/json'},
    method='POST',
)
try:
    with urllib.request.urlopen(req, timeout=15) as response:
        response.read()
except Exception:
    sys.exit(0)
if stop_script:
    try:
        subprocess.run(
            ['bun', stop_script, 'stop'],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=15,
            check=False,
        )
    except Exception:
        pass
"""


def _resolve_content_session_id(hook_data: dict) -> str:
    """Resolve the agent's own session id, or "" when none is available.

    The hook payload is authoritative: its ``session_id`` is the exact value the
    Console stored as ``contentSessionId`` when the session was registered (see
    the platform adapters in console/src/cli/adapters/). The env chain is only a
    fallback for a harness that supplies no payload.
    """
    session_id = str(hook_data.get("session_id") or "").strip()
    if session_id:
        return session_id

    for var in _CONTENT_SESSION_ID_ENV_CHAIN:
        value = os.environ.get(var, "").strip()
        if value:
            return value

    return ""


def _complete_session(hook_data: dict, *, stop_worker: bool = False) -> None:
    """Complete the current session and optionally stop the worker afterwards.

    Fully detached fire-and-forget. The short-lived Python subprocess waits for
    the completion/export response before it runs the worker stop command.
    Errors inside the finalizer are swallowed.
    """
    session_id = _resolve_content_session_id(hook_data)
    if not session_id:
        return

    try:
        _ = subprocess.Popen(
            [
                sys.executable,
                "-c",
                _COMPLETE_SESSION_WORKER,
                f"{get_console_url()}/api/sessions/complete",
                session_id,
                (str(Path.home() / ".pilot" / "scripts" / "worker-service.cjs") if stop_worker else ""),
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            close_fds=True,
        )
    except OSError:
        pass


def _extract_session_pid(name: str) -> int | None:
    """Extract the PID from a PID-backed session directory name.

    PID-backed dirs have exactly two numeric shapes: ``{PID}`` (wrapper) and
    ``{PID}-{suffix}`` (shell alias). Everything else is agent-native, including
    digit-leading UUIDs such as ``12345678-e29b-...``.
    """
    if re.fullmatch(r"\d+(?:-\d+)?", name):
        return int(name.split("-", 1)[0])
    return None


def _is_agent_session_id(name: str) -> bool:
    """Return whether a directory name is a Claude/Codex UUID."""
    return _AGENT_SESSION_ID_RE.fullmatch(name) is not None


def _is_session_fresh(session_dir: Path) -> bool:
    """Return whether an agent-native session has a recent heartbeat."""
    cache_file = session_dir / "context-pct.json"
    now = time.time()

    if cache_file.exists():
        try:
            data = json.loads(cache_file.read_text())
            ts = data.get("ts", 0)
            if isinstance(ts, (int, float)):
                return (now - ts) < _SESSION_STALENESS_THRESHOLD
        except (json.JSONDecodeError, OSError, TypeError):
            pass

    try:
        return (now - session_dir.stat().st_mtime) < _SESSION_STALENESS_THRESHOLD
    except OSError:
        return False


def _live_agent_session_ids() -> set[str] | None:
    """Return agent-native ids found in live Claude/Codex processes."""
    try:
        result = subprocess.run(
            ["ps", "eww", "-axo", "command="],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=1,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None

    ids = set(re.findall(r"--session-id[= ](\S+)", result.stdout))
    ids |= set(re.findall(r"CODEX_THREAD_ID=(\S+)", result.stdout))
    return ids or None


def _has_other_active_sessions(fallback_session_id: str = "") -> bool:
    """Check if any other sessions are still active.

    PID-backed directories are probed directly. Agent-native Claude/Codex
    directories use the same live-process scan and heartbeat fallback as
    ``launcher.session.count_active_sessions``. The payload id is only a fallback
    when the native environment chain is empty. Returns True on any directory
    error (safe default: do not stop the worker).
    """
    try:
        if not SESSIONS_DIR.exists():
            return False

        my_session = resolve_session_id(fallback_session_id)
        live_ids: set[str] | None = None
        live_ids_scanned = False

        for entry in SESSIONS_DIR.iterdir():
            if not entry.is_dir() or entry.name in SKIP_NAMES:
                continue
            if entry.name == my_session:
                continue
            pid = _extract_session_pid(entry.name)
            if pid is None:
                if not _is_agent_session_id(entry.name):
                    continue
                if not live_ids_scanned:
                    live_ids = _live_agent_session_ids()
                    live_ids_scanned = True
                if live_ids is not None:
                    if entry.name in live_ids:
                        return True
                elif _is_session_fresh(entry):
                    return True
                continue
            try:
                os.kill(pid, 0)
            except OSError:
                continue

            return True

        return False
    except OSError:
        return True


def main() -> int:
    # A stray end-of-turn invocation must neither read stdin nor churn the
    # worker. Current Codex and Claude Code both expose a true SessionEnd event.
    if SESSION_END_FLAG not in sys.argv[1:]:
        return 0

    hook_data = read_hook_stdin()
    try:
        (SESSIONS_DIR / resolve_session_id(hook_data.get("session_id")) / NATIVE_SPEC_PLANNING).unlink(missing_ok=True)
    except OSError:
        pass
    _complete_session(
        hook_data,
        stop_worker=not _has_other_active_sessions(_resolve_content_session_id(hook_data)),
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
