"""SessionStart hook: make legacy Impeccable state formatter-safe once.

Impeccable's current hook writes future state below IMPECCABLE_CACHE_ROOT. An
older project-local cache may still be minified and fail a repository-wide
Prettier check, so preserve its data while atomically normalizing the JSON.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path


def _get_project_dir() -> Path:
    for variable in ("CODEX_WORKSPACE", "CLAUDE_PROJECT_ROOT"):
        value = os.environ.get(variable, "").strip()
        if value:
            return Path(value)
    return Path.cwd()


def migrate_legacy_cache(project_dir: Path) -> bool:
    """Pretty-format a valid local hook cache without deleting or relocating it."""
    cache = project_dir / ".impeccable" / "hook.cache.json"
    if cache.is_symlink() or not cache.is_file():
        return False
    try:
        before = cache.read_bytes()
        payload = json.loads(before.decode("utf-8"))
        if not isinstance(payload, dict):
            return False
        formatted = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        if formatted == before:
            return False
        mode = cache.stat().st_mode & 0o777
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False

    temporary_path: Path | None = None
    try:
        descriptor, temporary_name = tempfile.mkstemp(
            dir=cache.parent,
            prefix=f".{cache.name}.",
            suffix=".tmp",
        )
        temporary_path = Path(temporary_name)
        with os.fdopen(descriptor, "wb") as temporary:
            temporary.write(formatted)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.chmod(temporary_path, mode)

        # Do not overwrite a cache that changed while the normalized copy was
        # staged (for example, an older hook still finishing during startup).
        if cache.read_bytes() != before:
            return False
        os.replace(temporary_path, cache)
        temporary_path = None
        return True
    except OSError:
        return False
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def main() -> None:
    try:
        migrate_legacy_cache(_get_project_dir())
    except Exception:
        # Maintenance must never block a session.
        return


if __name__ == "__main__":
    main()
