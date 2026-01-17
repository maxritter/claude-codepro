"""CCP binary download and update step."""

from __future__ import annotations

import platform
import stat
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

import httpx

from installer.steps.base import BaseStep

if TYPE_CHECKING:
    from installer.context import InstallContext

try:
    from installer import __version__ as INSTALLER_VERSION
except ImportError:
    INSTALLER_VERSION = None

GITHUB_REPO = "maxritter/claude-codepro"


def _get_platform_binary_name() -> str | None:
    """Get the CCP binary name for the current platform."""
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

    return f"ccp-{os_name}-{arch}"


def _get_installed_version(ccp_path: Path) -> str | None:
    """Get the version of the installed CCP binary."""
    if not ccp_path.exists():
        return None

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


def _download_binary(version: str, dest_path: Path) -> bool:
    """Download the CCP binary for the current platform."""
    binary_name = _get_platform_binary_name()
    if not binary_name:
        return False

    url = f"https://github.com/{GITHUB_REPO}/releases/download/v{version}/{binary_name}"

    try:
        with httpx.Client(timeout=60.0, follow_redirects=True) as client:
            response = client.get(url)
            if response.status_code != 200:
                return False

            dest_path.parent.mkdir(parents=True, exist_ok=True)
            dest_path.write_bytes(response.content)

            dest_path.chmod(dest_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

            if platform.system() == "Darwin":
                try:
                    subprocess.run(["xattr", "-cr", str(dest_path)], capture_output=True)
                except (subprocess.SubprocessError, OSError):
                    pass

            return True
    except (httpx.HTTPError, httpx.TimeoutException, OSError):
        return False


class CcpBinaryStep(BaseStep):
    """Step that downloads/updates the CCP binary."""

    name = "ccp_binary"

    def check(self, ctx: InstallContext) -> bool:
        """Check if CCP binary needs to be updated.

        Returns True (skip) if binary exists and is at target version.
        """
        ccp_path = ctx.project_dir / ".claude" / "bin" / "ccp"

        if not ccp_path.exists():
            return False

        target_version = INSTALLER_VERSION or ctx.config.get("target_version")
        if not target_version:
            return True

        installed_version = _get_installed_version(ccp_path)
        if not installed_version:
            return False

        return installed_version == target_version

    def run(self, ctx: InstallContext) -> None:
        """Download or update the CCP binary."""
        ui = ctx.ui
        ccp_path = ctx.project_dir / ".claude" / "bin" / "ccp"

        target_version = INSTALLER_VERSION or ctx.config.get("target_version")
        if not target_version:
            if ui:
                ui.info("CCP binary version unknown, skipping update")
            return

        installed_version = _get_installed_version(ccp_path)

        if installed_version == target_version:
            if ui:
                ui.info(f"CCP binary already at v{target_version}")
            return

        action = "Updating" if ccp_path.exists() else "Downloading"
        if ui:
            with ui.spinner(f"{action} CCP binary to v{target_version}..."):
                success = _download_binary(target_version, ccp_path)
            if success:
                ui.success(f"CCP binary updated to v{target_version}")
            else:
                ui.warning("Could not update CCP binary - will update on next install")
        else:
            _download_binary(target_version, ccp_path)

    def rollback(self, ctx: InstallContext) -> None:
        """No rollback for binary updates - old binary in memory still works."""
        pass
