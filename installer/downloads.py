"""Download utilities using urllib with progress tracking."""

from __future__ import annotations

import filecmp
import hashlib
import json
import shutil
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass
class DownloadConfig:
    """Configuration for download operations."""

    repo_url: str
    repo_branch: str
    local_mode: bool = False
    local_repo_dir: Path | None = None


@dataclass
class FileInfo:
    """File information including path and optional SHA hash."""

    path: str
    sha: str | None = None


def compute_git_blob_sha(file_path: Path) -> str:
    """Compute git blob SHA1 hash for a file (same algorithm git uses)."""
    content = file_path.read_bytes()
    header = f"blob {len(content)}\0".encode()
    return hashlib.sha1(header + content).hexdigest()


def download_file(
    repo_path: str | FileInfo,
    dest_path: Path,
    config: DownloadConfig,
    progress_callback: Callable[[int, int], None] | None = None,
) -> bool:
    """Download a file from the repository or copy in local mode.

    Skips download if destination file exists and has matching content/hash.
    """
    if isinstance(repo_path, FileInfo):
        file_sha = repo_path.sha
        repo_path = repo_path.path
    else:
        file_sha = None

    dest_path.parent.mkdir(parents=True, exist_ok=True)

    if config.local_mode and config.local_repo_dir:
        source_file = config.local_repo_dir / repo_path
        if source_file.is_file():
            try:
                if source_file.resolve() == dest_path.resolve():
                    return True
                if dest_path.exists() and filecmp.cmp(source_file, dest_path, shallow=False):
                    return True
                shutil.copy2(source_file, dest_path)
                return True
            except (OSError, IOError):
                return False
        return False

    if file_sha and dest_path.exists():
        try:
            local_sha = compute_git_blob_sha(dest_path)
            if local_sha == file_sha:
                return True
        except (OSError, IOError):
            pass

    file_url = f"{config.repo_url}/raw/{config.repo_branch}/{repo_path}"
    try:
        request = urllib.request.Request(file_url)
        with urllib.request.urlopen(request, timeout=30.0) as response:
            if response.status != 200:
                return False

            total = int(response.headers.get("content-length", 0))
            downloaded = 0

            with open(dest_path, "wb") as f:
                while True:
                    chunk = response.read(8192)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback and total > 0:
                        progress_callback(downloaded, total)

        return True
    except (urllib.error.URLError, OSError, TimeoutError):
        return False


def get_repo_files(dir_path: str, config: DownloadConfig) -> list[FileInfo]:
    """Get all files from a repository directory.

    Returns FileInfo objects. Remote mode includes SHA hashes for skip-if-unchanged.
    Local mode has sha=None (uses filecmp for comparison instead).
    """
    if config.local_mode and config.local_repo_dir:
        source_dir = config.local_repo_dir / dir_path
        if source_dir.is_dir():
            result: list[FileInfo] = []
            for file_path in source_dir.rglob("*"):
                if file_path.is_file():
                    rel_path = file_path.relative_to(config.local_repo_dir)
                    result.append(FileInfo(path=str(rel_path), sha=None))
            return result
        return []

    try:
        repo_path = config.repo_url.replace("https://github.com/", "")
        tree_url = f"https://api.github.com/repos/{repo_path}/git/trees/{config.repo_branch}?recursive=true"

        request = urllib.request.Request(tree_url)
        with urllib.request.urlopen(request, timeout=30.0) as response:
            if response.status != 200:
                return []

            data = json.loads(response.read().decode("utf-8"))
            remote_files: list[FileInfo] = []
            if "tree" in data:
                for item in data["tree"]:
                    if item.get("type") == "blob":
                        path = item.get("path", "")
                        sha = item.get("sha")
                        if path.startswith(dir_path):
                            remote_files.append(FileInfo(path=path, sha=sha))
            return remote_files
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError):
        return []


def download_directory(
    repo_dir: str,
    dest_dir: Path,
    config: DownloadConfig,
    exclude_patterns: list[str] | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
) -> int:
    """Download an entire directory from the repository."""
    if exclude_patterns is None:
        exclude_patterns = []

    file_infos = get_repo_files(repo_dir, config)
    count = 0
    total = len(file_infos)

    for i, file_info in enumerate(file_infos):
        if any(pattern.replace("*", "") in file_info.path for pattern in exclude_patterns):
            continue

        rel_path = Path(file_info.path).relative_to(repo_dir)
        dest_path = dest_dir / rel_path

        if download_file(file_info, dest_path, config):
            count += 1

        if progress_callback:
            progress_callback(i + 1, total)

    return count
