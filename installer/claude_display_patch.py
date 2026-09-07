"""Patch an existing native Claude safely; also ships as the standalone restorer."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import platform
import re
import shutil
import stat
import subprocess
import tarfile
import tempfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

SOURCE_ENTRY_ID = "claude-display-patch"
DISABLED_PATCHES = "welcome-badge,installer-label,disable-spinner-tips"
_SUPPORTED = {("Darwin", "arm64"), ("Linux", "x86_64"), ("Linux", "aarch64")}


@dataclass(frozen=True)
class PatchResult:
    status: str
    message: str


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run(argv: list[str], *, cwd: Path | None = None) -> str:
    return subprocess.run(argv, cwd=cwd, check=True, capture_output=True, text=True, timeout=300).stdout.strip()


def _version(path: Path) -> str:
    output = _run([str(path), "--version"]).replace("(patched)", "").strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:[-+][\w.-]+)? \(Claude Code\)", output):
        raise ValueError("Claude did not report a recognizable version")
    return output


def _load_state(state_dir: Path) -> dict[str, Any]:
    path = state_dir / "state.json"
    if not path.exists():
        return {"schema": 1, "entries": {}}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema") != 1 or not isinstance(payload.get("entries"), dict):
        raise ValueError("Unrecognized Claude display patch state; preserving existing files")
    return payload


def _write_state(state_dir: Path, state: dict[str, Any]) -> None:
    descriptor, name = tempfile.mkstemp(prefix=".state-", dir=state_dir)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(state, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, state_dir / "state.json")
    finally:
        temporary.unlink(missing_ok=True)


def _identity(command: Path) -> tuple[Path, tuple[int, int, int, int], tuple[int, int, int, int]]:
    target = command.resolve(strict=True)
    link = command.lstat()
    native = target.stat()
    return (
        target,
        (link.st_dev, link.st_ino, link.st_mtime_ns, link.st_size),
        (native.st_dev, native.st_ino, native.st_mtime_ns, native.st_size),
    )


def _native(path: Path) -> bool:
    with path.open("rb") as stream:
        magic = stream.read(4)
    return magic in {b"\xcf\xfa\xed\xfe", b"\xfe\xed\xfa\xcf", b"\x7fELF"}


def _download_source(destination: Path) -> Path:
    # Imported only by installation: the copied restore.py stays stdlib-only.
    from installer.manifest import get

    entry = get(SOURCE_ENTRY_ID)
    archive = destination / "source.tar.gz"
    request = urllib.request.Request(entry.source_url, headers={"User-Agent": "Pilot-Shell-Installer"})
    with urllib.request.urlopen(request, timeout=60) as response, archive.open("wb") as output:
        total = 0
        while chunk := response.read(1024 * 1024):
            total += len(chunk)
            if total > 20 * 1024 * 1024:
                raise ValueError("Claude display patch source download is too large")
            output.write(chunk)
    if _hash(archive) != entry.sha256:
        raise ValueError("Claude display patch source SHA-256 mismatch")
    extracted = destination / "source"
    extracted.mkdir()
    with tarfile.open(archive, "r:gz") as source:
        members = source.getmembers()
        if sum(member.size for member in members) > 50 * 1024 * 1024:
            raise ValueError("Claude display patch source archive is too large")
        for member in members:
            name = PurePosixPath(member.name)
            if name.is_absolute() or ".." in name.parts or not (member.isfile() or member.isdir()):
                raise ValueError("Unsafe path in Claude display patch source archive")
        source.extractall(extracted, members=members, filter="data")
    roots = list(extracted.iterdir())
    if (
        len(roots) != 1
        or not (roots[0] / "scripts" / "patch-native.ts").is_file()
        or not (roots[0] / "bun.lock").is_file()
    ):
        raise ValueError("Claude display patch source layout is incomplete")
    return roots[0]


def _backup_path(state_dir: Path, record: dict[str, Any]) -> Path:
    original_hash = record.get("original_hash", "")
    if not isinstance(original_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", original_hash):
        raise ValueError("Invalid original binary hash in Claude display patch state")
    expected = f"originals/{original_hash}"
    if record.get("backup") != expected:
        raise ValueError("Invalid Claude display patch backup path")
    backup = state_dir / expected
    if _hash(backup) != original_hash:
        raise ValueError("Claude display patch original backup SHA-256 mismatch")
    return backup


def _matching_record(record: Any, binary_hash: str) -> dict[str, Any] | None:
    """Retain restore provenance if activation of a newer patch was interrupted."""
    while isinstance(record, dict):
        if record.get("patched_hash") == binary_hash:
            return record
        record = record.get("previous")
    return None


def _apply(command: Path, state_dir: Path, bun: str) -> PatchResult:
    from installer.manifest import get

    entry = get(SOURCE_ENTRY_ID)
    snapshot = _identity(command)
    target = snapshot[0]
    expected_hash = _hash(target)
    state = _load_state(state_dir)
    record = _matching_record(state["entries"].get(str(target)), expected_hash)
    original = target
    if record is not None:
        original = _backup_path(state_dir, record)
        if record.get("source_commit") == entry.commit and record.get("options") == DISABLED_PATCHES:
            return PatchResult("unchanged", "Claude display details already enabled")

    with tempfile.TemporaryDirectory(prefix=".pilot-display-", dir=target.parent) as work:
        stage = Path(work)
        staged_original = stage / "original"
        candidate = stage / "candidate"
        shutil.copyfile(original, staged_original)
        original_mode = stat.S_IMODE(target.stat().st_mode)
        staged_original.chmod(original_mode)
        original_hash = _hash(staged_original)
        original_version = _version(staged_original)
        project = _download_source(stage)
        _run([bun, "install", "--frozen-lockfile", "--ignore-scripts"], cwd=project)
        patch_command = [
            bun,
            "scripts/patch-native.ts",
            "--input",
            str(staged_original),
            "--output",
            str(candidate),
            "--disable",
            DISABLED_PATCHES,
        ]
        _run([*patch_command, "--dry-run"], cwd=project)
        _run(patch_command, cwd=project)
        if not _native(candidate):
            raise ValueError("Patched Claude is not a native executable")
        candidate.chmod(original_mode)
        if _version(candidate) != original_version:
            raise ValueError("Patched Claude version does not match the installed version")
        patched_hash = _hash(candidate)
        if patched_hash == original_hash:
            raise ValueError("Claude display patches made no changes")

        backups = state_dir / "originals"
        backups.mkdir(exist_ok=True)
        backup = backups / original_hash
        if backup.exists():
            if _hash(backup) != original_hash:
                raise ValueError("Existing Claude original backup SHA-256 mismatch")
        else:
            shutil.copyfile(staged_original, backup)
            backup.chmod(0o600)
        if _hash(backup) != original_hash:
            raise ValueError("Claude original backup SHA-256 mismatch")
        shutil.copyfile(Path(__file__), state_dir / "restore.py")
        # Journal before activation: even interruption immediately after replace
        # leaves a verified original and enough provenance for standalone restore.
        state["entries"][str(target)] = {
            "original_hash": original_hash,
            "patched_hash": patched_hash,
            "backup": f"originals/{original_hash}",
            "source_commit": entry.commit,
            "source_url": entry.source_url,
            "source_sha256": entry.sha256,
            "options": DISABLED_PATCHES,
            "original_version": original_version,
            "original_mode": original_mode,
        }
        if record is not None:
            state["entries"][str(target)]["previous"] = record
        _write_state(state_dir, state)
        if _identity(command) != snapshot or _hash(target) != expected_hash:
            raise ValueError("Claude changed while preparing display patches; keeping the new binary")
        os.replace(candidate, target)
    return PatchResult("patched", "Claude display details enabled (original saved for uninstall)")


def apply_display_patch(*, claude_path: Path | None = None, state_dir: Path | None = None) -> PatchResult:
    """Apply pinned source patches to an existing writable native Claude only."""
    try:
        if (platform.system(), platform.machine()) not in _SUPPORTED:
            return PatchResult("skipped", "Claude display patches are unavailable on this platform")
        located = str(claude_path) if claude_path else shutil.which("claude")
        bun = shutil.which("bun")
        if not located or not bun:
            return PatchResult("skipped", "Claude display patches need an existing Claude and Bun")
        command = Path(located).absolute()
        if not command.exists() or not command.is_file():
            return PatchResult("skipped", "No existing native Claude executable")
        target = command.resolve(strict=True)
        if not _native(target):
            return PatchResult("skipped", "Claude display patches require a native install; npm wrappers are preserved")
        if not os.access(target, os.W_OK) or not os.access(target.parent, os.W_OK):
            return PatchResult("skipped", "Claude executable is not writable; no elevated privileges requested")
        directory = state_dir or Path.home() / ".pilot" / "claude-display-patch"
        directory.mkdir(parents=True, exist_ok=True)
        with (directory / ".lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return _apply(command, directory, bun)
    except (OSError, ValueError, subprocess.SubprocessError, tarfile.TarError) as error:
        return PatchResult("failed", f"Claude display patches skipped: {error}")


def restore_display_patch(state_dir: Path | None = None) -> PatchResult:
    """Restore only unchanged binaries whose patch hash and backup are verified."""
    directory = state_dir or Path(__file__).resolve().parent
    if not (directory / "state.json").exists():
        return PatchResult("restored", "No Claude display patches to restore")
    try:
        with (directory / ".lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            state = _load_state(directory)
            failures: list[str] = []
            for target_name, stored_record in list(state["entries"].items()):
                try:
                    target = Path(target_name)
                    if not target.is_absolute() or not isinstance(stored_record, dict):
                        raise ValueError("Invalid Claude display patch target record")
                    record = (
                        None
                        if target.is_symlink() or not target.exists()
                        else _matching_record(stored_record, _hash(target))
                    )
                    if record is None:
                        del state["entries"][target_name]
                        continue  # A user/Claude upgrade owns the changed target now.
                    snapshot = _identity(target)
                    backup = _backup_path(directory, record)
                    with tempfile.TemporaryDirectory(prefix=".pilot-restore-", dir=target.parent) as work:
                        candidate = Path(work) / "original"
                        shutil.copyfile(backup, candidate)
                        candidate.chmod(record["original_mode"])
                        if _hash(candidate) != record["original_hash"]:
                            raise ValueError("Claude restore candidate SHA-256 mismatch")
                        if _identity(target) != snapshot or _hash(target) != record["patched_hash"]:
                            del state["entries"][target_name]
                            continue  # A concurrent auto-update also supersedes our ownership.
                        os.replace(candidate, target)
                    del state["entries"][target_name]
                except (OSError, ValueError, KeyError, TypeError) as error:
                    failures.append(f"{target_name}: {error}")
            _write_state(directory, state)
            if failures:
                return PatchResult("failed", "Claude restore incomplete: " + "; ".join(failures))
        return PatchResult("restored", "Claude originals restored; newer or modified binaries preserved")
    except (OSError, ValueError) as error:
        return PatchResult("failed", f"Claude restore incomplete: {error}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Restore native Claude binaries patched by Pilot")
    parser.add_argument("--restore", action="store_true", required=True)
    parser.add_argument("--state-dir", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    result = restore_display_patch(args.state_dir)
    print(result.message)
    return 1 if result.status == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
