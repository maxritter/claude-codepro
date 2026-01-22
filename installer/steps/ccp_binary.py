"""CCP binary download and update step."""

from __future__ import annotations

import platform
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any

import httpx

from installer.context import InstallContext
from installer.steps.base import BaseStep

try:
    from installer import __version__ as INSTALLER_VERSION
except ImportError:
    INSTALLER_VERSION = None

GITHUB_REPO = "maxritter/claude-codepro"


def _get_platform_suffix() -> str | None:
    """Get the platform suffix for release artifacts (e.g., 'linux-x86_64')."""
    system = platform.system().lower()
    machine = platform.machine().lower()

    if system == "linux":
        os_name = "linux"
    elif system == "darwin":
        os_name = "darwin"
    else:
        return None

    if machine in ("x86_64", "amd64"):
        arch = "x86_64"
    elif machine in ("arm64", "aarch64"):
        arch = "arm64"
    else:
        return None

    return f"{os_name}-{arch}"


def _get_local_so_name() -> str:
    """Get the local .so filename with Python ABI tag."""
    impl = sys.implementation.name
    version = f"{sys.version_info.major}{sys.version_info.minor}"

    system = platform.system().lower()
    machine = platform.machine().lower()

    if system == "linux":
        if machine in ("x86_64", "amd64"):
            platform_tag = "x86_64-linux-gnu"
        elif machine in ("arm64", "aarch64"):
            platform_tag = "aarch64-linux-gnu"
        else:
            platform_tag = f"{machine}-linux-gnu"
    elif system == "darwin":
        platform_tag = "darwin"
    else:
        platform_tag = system

    return f"ccp.{impl}-{version}-{platform_tag}.so"


def _get_installed_version(ccp_path: Path, ui: Any = None) -> str | None:
    """Get the version of the installed CCP binary."""
    if not ccp_path.exists():
        return None

    def _run_version() -> str | None:
        try:
            result = subprocess.run(
                [str(ccp_path), "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                output = result.stdout.strip()
                if "v" in output:
                    return output.split("v")[-1].strip()
        except (subprocess.SubprocessError, OSError):
            pass
        return None

    if ui:
        with ui.spinner("Checking CCP version..."):
            return _run_version()
    else:
        return _run_version()


def _check_macos_gatekeeper(bin_dir: Path, ui: Any = None) -> bool:
    """Check if macOS Gatekeeper is blocking the binary and show instructions if so.

    Returns True if binary works, False if blocked.
    """
    if platform.system() != "Darwin":
        return True

    ccp_path = bin_dir / "ccp"
    if not ccp_path.exists():
        return True

    try:
        result = subprocess.run(
            [str(ccp_path), "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return True
    except (subprocess.SubprocessError, OSError):
        pass

    if ui:
        ui.warning("macOS Gatekeeper may be blocking the CCP binary")
        ui.info("")
        ui.info("To fix this, follow these steps:")
        ui.info("  1. Open System Settings → Privacy & Security")
        ui.info("  2. Scroll down to find a message about 'ccp' being blocked")
        ui.info("  3. Click 'Allow Anyway'")
        ui.info("  4. Run 'ccp' once in terminal, then click 'Open' when prompted")
        ui.info("")
        ui.info("Or run this command to remove the quarantine flag:")
        ui.info(f"  xattr -cr {bin_dir}")
        ui.info("")

    return False


def _download_file(
    url: str,
    dest_path: Path,
    executable: bool = True,
    progress_callback: Any | None = None,
) -> bool:
    """Download a file from URL to destination path with optional progress callback.

    Args:
        url: URL to download from
        dest_path: Destination file path
        executable: Whether to make the file executable
        progress_callback: Optional callback (downloaded_bytes, total_bytes) for progress display
    """
    try:
        with httpx.Client(timeout=240.0, follow_redirects=True) as client:
            with client.stream("GET", url) as response:
                if response.status_code != 200:
                    return False

                dest_path.parent.mkdir(parents=True, exist_ok=True)
                if dest_path.exists():
                    dest_path.unlink()

                total = int(response.headers.get("content-length", 0))
                downloaded = 0

                with open(dest_path, "wb") as f:
                    for chunk in response.iter_bytes(chunk_size=8192):
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback and total > 0:
                            progress_callback(downloaded, total)

            if executable:
                dest_path.chmod(dest_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

            if platform.system() == "Darwin":
                try:
                    subprocess.run(["xattr", "-cr", str(dest_path)], capture_output=True)
                except (subprocess.SubprocessError, OSError):
                    pass

            return True
    except (httpx.HTTPError, httpx.TimeoutException, OSError):
        return False


def _download_ccp_artifacts(version: str, bin_dir: Path, ui: Any = None) -> bool:
    """Download the CCP .so module and wrapper for the current platform."""
    platform_suffix = _get_platform_suffix()
    if not platform_suffix:
        return False

    base_url = f"https://github.com/{GITHUB_REPO}/releases/download/v{version}"

    so_url = f"{base_url}/ccp-{platform_suffix}.so"
    local_so_name = _get_local_so_name()
    so_path = bin_dir / local_so_name

    if ui:
        with ui.progress(100, "Downloading CCP module") as progress:

            def so_progress(downloaded: int, total: int) -> None:
                pct = int((downloaded / total) * 100) if total > 0 else 0
                progress.update(pct)

            if not _download_file(so_url, so_path, executable=True, progress_callback=so_progress):
                return False
    else:
        if not _download_file(so_url, so_path, executable=True):
            return False

    wrapper_url = f"{base_url}/ccp-wrapper"
    wrapper_path = bin_dir / "ccp"

    if ui:
        with ui.progress(100, "Downloading CCP wrapper") as progress:

            def wrapper_progress(downloaded: int, total: int) -> None:
                pct = int((downloaded / total) * 100) if total > 0 else 0
                progress.update(pct)

            if not _download_file(wrapper_url, wrapper_path, executable=True, progress_callback=wrapper_progress):
                if so_path.exists():
                    so_path.unlink()
                return False
    else:
        if not _download_file(wrapper_url, wrapper_path, executable=True):
            if so_path.exists():
                so_path.unlink()
            return False

    return True


class CcpBinaryStep(BaseStep):
    """Step that downloads/updates the CCP binary."""

    name = "ccp_binary"

    def __init__(self) -> None:
        """Initialize step with version cache."""
        self._cached_version: str | None = None
        self._version_checked: bool = False

    def check(self, ctx: InstallContext) -> bool:
        """Check if CCP binary needs to be updated.

        Returns True (skip) if binary exists and is at target version.
        """
        ccp_path = ctx.project_dir / ".claude" / "bin" / "ccp"

        if not ccp_path.exists():
            self._version_checked = True
            self._cached_version = None
            return False

        target_version = INSTALLER_VERSION or ctx.config.get("target_version")
        if not target_version:
            return True

        installed_version = _get_installed_version(ccp_path, ctx.ui)
        self._version_checked = True
        self._cached_version = installed_version

        if not installed_version:
            return False

        return installed_version == target_version

    def run(self, ctx: InstallContext) -> None:
        """Download or update the CCP binary."""
        ui = ctx.ui
        bin_dir = ctx.project_dir / ".claude" / "bin"
        ccp_path = bin_dir / "ccp"

        target_version = INSTALLER_VERSION or ctx.config.get("target_version")
        if not target_version:
            if ui:
                ui.info("CCP binary version unknown, skipping update")
            return

        if self._version_checked:
            installed_version = self._cached_version
        else:
            installed_version = _get_installed_version(ccp_path, ui)

        if installed_version == target_version:
            if ui:
                ui.info(f"CCP binary already at v{target_version}")
            return

        action = "Updating" if ccp_path.exists() else "Downloading"
        if ui:
            ui.status(f"{action} CCP binary to v{target_version}...")
            success = _download_ccp_artifacts(target_version, bin_dir, ui)
            if success:
                ui.success(f"CCP binary updated to v{target_version}")
                if ctx.is_local_install:
                    _check_macos_gatekeeper(bin_dir, ui)
            else:
                ui.warning("Could not update CCP binary - will update on next install")
        else:
            _download_ccp_artifacts(target_version, bin_dir)

    def rollback(self, ctx: InstallContext) -> None:
        """No rollback for binary updates - old binary in memory still works."""
        pass
