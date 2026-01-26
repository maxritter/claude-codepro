"""Prerequisites installation step for local installations."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from installer.context import InstallContext
from installer.platform_utils import command_exists, is_homebrew_available, is_in_devcontainer
from installer.steps.base import BaseStep

HOMEBREW_PACKAGES = [
    "git",
    "gh",
    "python@3.12",
    "node@22",
    "nvm",
    "pnpm",
    "bun",
    "uv",
    "go",
    "gopls",
]


def _is_nvm_installed() -> bool:
    """Check if nvm is installed (it's a shell function, not a binary)."""
    nvm_dir = Path.home() / ".nvm"
    if (nvm_dir / "nvm.sh").exists():
        return True
    try:
        result = subprocess.run(["brew", "list", "nvm"], capture_output=True, check=False)
        return result.returncode == 0
    except (subprocess.SubprocessError, OSError):
        return False


def _install_homebrew() -> bool:
    """Install Homebrew."""
    try:
        result = subprocess.run(
            ["/bin/bash", "-c", "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"],
            shell=True,
            check=False,
        )
        if result.returncode != 0:
            return False

        brew_paths = [
            "/opt/homebrew/bin",
            "/usr/local/bin",
            "/home/linuxbrew/.linuxbrew/bin",
        ]
        for brew_path in brew_paths:
            if os.path.exists(os.path.join(brew_path, "brew")):
                os.environ["PATH"] = f"{brew_path}:{os.environ.get('PATH', '')}"
                break

        return is_homebrew_available()
    except (subprocess.SubprocessError, OSError):
        return False


def _add_bun_tap() -> bool:
    """Add the bun tap to Homebrew."""
    try:
        result = subprocess.run(
            ["brew", "tap", "oven-sh/bun"],
            capture_output=True,
            check=False,
        )
        return result.returncode == 0 or b"already tapped" in result.stderr.lower()
    except (subprocess.SubprocessError, OSError):
        return False


def _ensure_homebrew_in_path() -> None:
    """Ensure Homebrew bin directory is in PATH for current process."""
    brew_paths = [
        "/opt/homebrew/bin",
        "/usr/local/bin",
        "/home/linuxbrew/.linuxbrew/bin",
    ]
    current_path = os.environ.get("PATH", "")
    for brew_path in brew_paths:
        if os.path.exists(os.path.join(brew_path, "brew")):
            if brew_path not in current_path:
                os.environ["PATH"] = f"{brew_path}:{current_path}"
            break


def _install_homebrew_package(package: str) -> bool:
    """Install a single Homebrew package."""
    try:
        result = subprocess.run(
            ["brew", "install", package],
            capture_output=True,
            check=False,
        )
        if result.returncode == 0:
            _ensure_homebrew_in_path()
        return result.returncode == 0
    except (subprocess.SubprocessError, OSError):
        return False


def _get_command_for_package(package: str) -> str:
    """Get the command name to check for a given Homebrew package."""
    package_to_command = {
        "python@3.12": "python3",
        "node@22": "node",
        "gh": "gh",
        "git": "git",
        "nvm": "nvm",
        "pnpm": "pnpm",
        "bun": "bun",
        "uv": "uv",
        "go": "go",
        "gopls": "gopls",
    }
    return package_to_command.get(package, package)


class PrerequisitesStep(BaseStep):
    """Step that installs prerequisite packages for local installations."""

    name = "prerequisites"

    def check(self, ctx: InstallContext) -> bool:
        """Check if this step should be skipped.

        Returns True (skip) if:
        - Running in a dev container
        - Not a local installation
        - Homebrew is available AND all packages are already installed
        """
        if is_in_devcontainer():
            return True

        if not ctx.is_local_install:
            return True

        if not is_homebrew_available():
            return False

        for package in HOMEBREW_PACKAGES:
            if package == "nvm":
                if not _is_nvm_installed():
                    return False
            else:
                cmd = _get_command_for_package(package)
                if not command_exists(cmd):
                    return False

        return True

    def run(self, ctx: InstallContext) -> None:
        """Install Homebrew (if needed) and missing prerequisite packages."""
        ui = ctx.ui

        if not is_homebrew_available():
            if ui:
                ui.info("Homebrew not found, installing...")
                with ui.spinner("Installing Homebrew..."):
                    success = _install_homebrew()
                if success:
                    ui.success("Homebrew installed")
                else:
                    ui.error("Failed to install Homebrew")
                    ui.info("Please install Homebrew manually: https://brew.sh")
                    return
            else:
                if not _install_homebrew():
                    return

        _add_bun_tap()

        for package in HOMEBREW_PACKAGES:
            if package == "nvm":
                is_installed = _is_nvm_installed()
            else:
                cmd = _get_command_for_package(package)
                is_installed = command_exists(cmd)

            if is_installed:
                if ui:
                    ui.info(f"{package} already installed")
                continue

            if ui:
                with ui.spinner(f"Installing {package}..."):
                    success = _install_homebrew_package(package)
                if success:
                    ui.success(f"{package} installed")
                else:
                    ui.warning(f"Could not install {package} - please install manually")
            else:
                _install_homebrew_package(package)
