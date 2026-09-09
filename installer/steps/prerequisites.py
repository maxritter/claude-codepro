"""Prerequisites installation step for local installations."""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any

from installer.context import InstallContext
from installer.manifest import UpstreamEntry
from installer.manifest import cached_load as manifest_load
from installer.platform_utils import (
    command_exists,
    ensure_bun_on_path,
    is_apt_available,
    is_dnf_available,
    is_homebrew_available,
    is_linux,
    is_yum_available,
)
from installer.steps.base import BaseStep

MAX_RETRIES = 3
RETRY_DELAY = 2


def _brew_entries() -> list[UpstreamEntry]:
    """Manifest-driven list of every Homebrew formula Pilot installs."""
    return [e for e in manifest_load().entries if e.source_type == "brew"]


def _brew_formulas() -> list[str]:
    """Formula names ordered by manifest position (replaces HOMEBREW_PACKAGES)."""
    seen: set[str] = set()
    out: list[str] = []
    for e in _brew_entries():
        f = e.brew_formula or ""
        if f and f not in seen:
            seen.add(f)
            out.append(f)
    return out


def _brew_no_upgrade_formulas() -> set[str]:
    """Formulas opted out of `brew upgrade` (replaces HOMEBREW_NO_UPGRADE_PACKAGES)."""
    return {e.brew_formula for e in _brew_entries() if not e.auto_upgrade and e.brew_formula}


# Module-level constants kept for backwards compat with any external readers;
# they always reflect the current manifest state.
HOMEBREW_PACKAGES = _brew_formulas()
HOMEBREW_NO_UPGRADE_PACKAGES = _brew_no_upgrade_formulas()


def _brew_formula_ref(formula: str) -> str:
    """Return a tap-qualified reference when the manifest requires a non-core tap."""
    for entry in _brew_entries():
        if entry.brew_formula != formula:
            continue
        if entry.brew_tap and entry.brew_tap != "homebrew/core" and "/" not in formula:
            return f"{entry.brew_tap}/{formula}"
        return formula
    return formula


def _verify_homebrew_tap(formula: str) -> bool:
    """Confirm the formula resolves from the manifest-declared tap.

    Returns False on any mismatch — used as a hard gate before `brew install`.
    Default expectation is `homebrew/core`; per-entry overrides (e.g. `bun`
    from `oven-sh/bun`) come from the manifest.
    """
    expected_tap: str | None = None
    for e in _brew_entries():
        if e.brew_formula == formula:
            expected_tap = e.brew_tap
            break
    if not expected_tap:
        return False
    try:
        result = subprocess.run(
            ["brew", "info", "--json=v2", _brew_formula_ref(formula)],
            capture_output=True,
            check=False,
            timeout=30,
        )
    except (subprocess.SubprocessError, OSError):
        return False
    if result.returncode != 0:
        return False
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return False
    formulae = data.get("formulae", [])
    if not formulae:
        return False
    tap = formulae[0].get("tap", "")
    return tap == expected_tap


def _is_nvm_installed() -> bool:
    """Check if nvm is installed (it's a shell function, not a binary)."""
    nvm_dir = Path.home() / ".nvm"
    if (nvm_dir / "nvm.sh").exists():
        return True
    try:
        result = subprocess.run(["brew", "list", "nvm"], capture_output=True, check=False, timeout=30)
        return result.returncode == 0
    except (subprocess.SubprocessError, OSError):
        return False


def _ensure_git_installed() -> bool:
    """Install git via system package manager if missing (required by Homebrew)."""
    if command_exists("git"):
        return True
    if not is_linux():
        return False

    pkg_cmds: list[list[str]] = []
    if is_dnf_available():
        pkg_cmds = [["sudo", "dnf", "install", "-y", "git"]]
    elif is_yum_available():
        pkg_cmds = [["sudo", "yum", "install", "-y", "git"]]
    elif is_apt_available():
        pkg_cmds = [
            ["sudo", "apt-get", "update", "-qq"],
            ["sudo", "apt-get", "install", "-y", "git"],
        ]
    else:
        return False

    try:
        for cmd in pkg_cmds:
            result = subprocess.run(
                cmd,
                check=False,
                timeout=120,
            )
            if result.returncode != 0:
                return False
        return command_exists("git")
    except (subprocess.SubprocessError, OSError):
        return False


def _install_homebrew() -> bool:
    """Install Homebrew non-interactively (manifest-pinned curl)."""
    from installer.steps.dependencies import (
        CurlPipeRunOptions,
        _curl_pipe_from_manifest,
    )

    try:
        ok = _curl_pipe_from_manifest(
            "homebrew-installer",
            CurlPipeRunOptions(
                interpreter="/bin/bash",
                env={"NONINTERACTIVE": "1"},
                stdin_devnull=True,
                timeout=300,
                stream=True,
            ),
        )
        if not ok:
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
    for attempt in range(MAX_RETRIES):
        try:
            result = subprocess.run(
                ["brew", "tap", "oven-sh/bun"],
                capture_output=True,
                check=False,
                timeout=60,
            )
            if result.returncode == 0 or b"already tapped" in result.stderr.lower():
                return True
        except (subprocess.SubprocessError, OSError):
            pass
        if attempt < MAX_RETRIES - 1:
            time.sleep(RETRY_DELAY)
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
    """Install a single Homebrew package after verifying its tap origin."""
    if not _verify_homebrew_tap(package):
        # Refuse to install from an unexpected tap — could be tap pollution
        # or a typo. The supply-chain gate considers this a security failure.
        return False
    for attempt in range(MAX_RETRIES):
        try:
            result = subprocess.run(
                ["brew", "install", _brew_formula_ref(package)],
                capture_output=True,
                check=False,
                timeout=120,
            )
            if result.returncode == 0:
                _ensure_homebrew_in_path()
                return True
        except (subprocess.SubprocessError, OSError):
            pass
        if attempt < MAX_RETRIES - 1:
            time.sleep(RETRY_DELAY)
    return False


def _upgrade_homebrew_package(package: str) -> bool:
    """Upgrade a single Homebrew package to its latest version."""
    for attempt in range(MAX_RETRIES):
        try:
            result = subprocess.run(
                ["brew", "upgrade", _brew_formula_ref(package)],
                capture_output=True,
                check=False,
                timeout=120,
            )
            if result.returncode == 0:
                return True
        except (subprocess.SubprocessError, OSError):
            pass
        if attempt < MAX_RETRIES - 1:
            time.sleep(RETRY_DELAY)
    return False


def _get_outdated_homebrew_packages(packages: list[str]) -> set[str]:
    """Return the subset of packages that have an available upgrade in Homebrew."""
    try:
        result = subprocess.run(
            ["brew", "outdated", "--quiet"],
            capture_output=True,
            check=False,
            timeout=30,
        )
        if result.returncode != 0:
            return set()
        outdated = set(result.stdout.decode().splitlines())
        return {
            package
            for package in packages
            if any(
                package == item
                or package.startswith(item + "@")
                or item.startswith(package + "@")
                or package.rsplit("/", 1)[-1] == item.rsplit("/", 1)[-1]
                for item in outdated
            )
        }
    except (subprocess.SubprocessError, OSError):
        return set()


def _get_command_for_package(package: str) -> str:
    """Get the command name to check for a given Homebrew package."""
    package_to_command = {
        "python@3.12": "python3",
        "node@24": "node",
        "gh": "gh",
        "git": "git",
        "nvm": "nvm",
        "pnpm": "pnpm",
        "bun": "bun",
        "uv": "uv",
        "go": "go",
        "gopls": "gopls",
        "ripgrep": "rg",
    }
    return package_to_command.get(package, package)


def _node_at_least_24() -> bool:
    if not command_exists("node"):
        return False
    try:
        result = subprocess.run(
            ["node", "--version"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    match = re.search(r"\bv(\d+)\.", result.stdout)
    return bool(result.returncode == 0 and match and int(match.group(1)) >= 24)


def _activate_versioned_node_formula(formula: str) -> bool:
    try:
        result = subprocess.run(
            ["brew", "--prefix", formula],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    if result.returncode != 0:
        return False
    node_bin = Path(result.stdout.strip()) / "bin"
    if not node_bin.is_dir():
        return False
    os.environ["PATH"] = f"{node_bin}:{os.environ.get('PATH', '')}"
    return _node_at_least_24()


def _install_ripgrep_via_apt() -> bool:
    """Install ripgrep via apt on Debian/Ubuntu Linux."""
    if not is_linux() or not is_apt_available():
        return False
    try:
        subprocess.run(
            ["sudo", "-n", "apt-get", "update", "-qq"],
            capture_output=True,
            check=False,
            stdin=subprocess.DEVNULL,
            timeout=60,
        )
        result = subprocess.run(
            ["sudo", "-n", "apt-get", "install", "-y", "ripgrep"],
            capture_output=True,
            check=False,
            stdin=subprocess.DEVNULL,
            timeout=120,
        )
        return result.returncode == 0
    except (subprocess.SubprocessError, OSError):
        return False


def _install_nodejs_via_pkg() -> bool:
    """Install Node.js via system package manager (dnf or apt) on Linux."""
    if is_dnf_available():
        try:
            subprocess.run(
                ["sudo", "-n", "dnf", "module", "enable", "nodejs:20", "-y"],
                capture_output=True,
                check=False,
                stdin=subprocess.DEVNULL,
                timeout=60,
            )
            result = subprocess.run(
                ["sudo", "-n", "dnf", "install", "-y", "nodejs", "npm"],
                capture_output=True,
                check=False,
                stdin=subprocess.DEVNULL,
                timeout=120,
            )
            return result.returncode == 0
        except (subprocess.SubprocessError, OSError):
            return False
    elif is_apt_available():
        try:
            subprocess.run(
                ["sudo", "-n", "apt-get", "update", "-qq"],
                capture_output=True,
                check=False,
                stdin=subprocess.DEVNULL,
                timeout=60,
            )
            result = subprocess.run(
                ["sudo", "-n", "apt-get", "install", "-y", "nodejs", "npm"],
                capture_output=True,
                check=False,
                stdin=subprocess.DEVNULL,
                timeout=120,
            )
            return result.returncode == 0
        except (subprocess.SubprocessError, OSError):
            return False
    return False


def _install_bun_standalone() -> bool:
    """Install bun via manifest-pinned curl installer."""
    from installer.steps.dependencies import (
        CurlPipeRunOptions,
        _curl_pipe_from_manifest,
    )

    try:
        if not _curl_pipe_from_manifest(
            "bun-installer",
            CurlPipeRunOptions(stdin_devnull=True, timeout=120),
        ):
            return False
        return ensure_bun_on_path()
    except (subprocess.SubprocessError, OSError):
        return False


def _ensure_bun_available(ui: Any) -> bool:
    """Last-resort bun install, on every platform rather than Linux only.

    Until this existed, `_install_bun_standalone` was reachable only through
    `_install_linux_fallbacks`, which returns early off Linux -- so on macOS bun came
    from Homebrew or not at all. When the `oven-sh/bun` tap or the formula failed, the
    install completed "successfully" and the dependency step quietly used npm instead.
    Running here (after Homebrew, on any platform) turns that into a real recovery.
    """
    if ensure_bun_on_path():
        return True

    if ui:
        with ui.spinner("Installing bun via standalone installer..."):
            success = _install_bun_standalone()
        if success:
            ui.success("bun installed")
        else:
            ui.warning("Could not install bun - falling back to npm for Pilot's Node dependencies")
        return success

    return _install_bun_standalone()


def _install_linux_fallbacks(ui: Any) -> None:
    """Install critical tools via native methods when Homebrew is unavailable on Linux.

    bun is deliberately absent here: `_ensure_bun_available` runs unconditionally right
    after this and covers the same ground on every platform.
    """
    if not is_linux():
        return

    # The dependency step installs the manifest-pinned NVM and Node 24. Distro
    # package managers commonly provide Node 20/22, which no longer satisfies
    # Pilot's browser-tool runtime and must not be reported as success here.


class PrerequisitesStep(BaseStep):
    """Step that installs prerequisite packages for local installations."""

    name = "prerequisites"

    def check(self, ctx: InstallContext) -> bool:
        """Check if this step should be skipped.

        Returns True (skip) if:
        - Homebrew is available AND all packages are installed AND none are outdated
        """
        ui = ctx.ui

        if not is_homebrew_available():
            return False

        if ui:
            ui.info("Checking installed packages...")

        for package in HOMEBREW_PACKAGES:
            if package == "nvm":
                if not _is_nvm_installed():
                    return False
            elif package == "node@24":
                if not _node_at_least_24():
                    return False
            else:
                cmd = _get_command_for_package(package)
                if not command_exists(cmd):
                    return False

        upgradeable = [p for p in HOMEBREW_PACKAGES if p not in HOMEBREW_NO_UPGRADE_PACKAGES]
        if upgradeable:
            if ui:
                ui.info("Checking for updates...")
            if _get_outdated_homebrew_packages(upgradeable):
                return False

        return True

    def run(self, ctx: InstallContext) -> None:
        """Install Homebrew (if needed) and missing prerequisite packages."""
        ui = ctx.ui

        if not is_homebrew_available():
            if not command_exists("git"):
                if ui:
                    with ui.spinner("Installing git (required by Homebrew)..."):
                        git_ok = _ensure_git_installed()
                    if git_ok:
                        ui.success("git installed")
                    else:
                        ui.warning("Could not install git - please install manually")
                else:
                    _ensure_git_installed()

            if ui:
                ui.info("Homebrew not found, installing...")
                with ui.spinner("Installing Homebrew..."):
                    success = _install_homebrew()
                if success:
                    ui.success("Homebrew installed")
                else:
                    if is_linux():
                        ui.warning(
                            "Could not install Homebrew - Node.js and tools will be installed via alternative methods"
                        )
                    else:
                        ui.error("Failed to install Homebrew")
                        ui.info("Please install Homebrew manually: https://brew.sh")
                        return
            else:
                if not _install_homebrew() and not is_linux():
                    return

        if is_homebrew_available():
            _add_bun_tap()

        upgradeable = [p for p in HOMEBREW_PACKAGES if p not in HOMEBREW_NO_UPGRADE_PACKAGES]
        outdated = _get_outdated_homebrew_packages(upgradeable) if is_homebrew_available() else set()

        for package in HOMEBREW_PACKAGES:
            if not is_homebrew_available():
                break
            if package == "nvm":
                is_installed = _is_nvm_installed()
            elif package == "node@24":
                is_installed = _node_at_least_24() or _activate_versioned_node_formula(package)
            else:
                cmd = _get_command_for_package(package)
                is_installed = command_exists(cmd)

            if is_installed:
                if package in outdated:
                    if ui:
                        with ui.spinner(f"Upgrading {package}..."):
                            success = _upgrade_homebrew_package(package)
                        if success:
                            ui.success(f"{package} upgraded")
                        else:
                            ui.warning(f"Could not upgrade {package}")
                    else:
                        _upgrade_homebrew_package(package)
                else:
                    if ui:
                        ui.info(f"{package} already up-to-date")
                continue

            if ui:
                with ui.spinner(f"Installing {package}..."):
                    success = _install_homebrew_package(package)
                if success:
                    if package == "node@24":
                        success = _activate_versioned_node_formula(package)
                if success:
                    ui.success(f"{package} installed")
                else:
                    ui.warning(f"Could not install {package} - please install manually")
            else:
                success = _install_homebrew_package(package)
                if success and package == "node@24":
                    _activate_versioned_node_formula(package)

        if not command_exists("rg") and is_linux() and is_apt_available():
            if ui:
                with ui.spinner("Installing ripgrep via apt..."):
                    success = _install_ripgrep_via_apt()
                if success:
                    ui.success("ripgrep installed via apt")
                else:
                    ui.warning("Could not install ripgrep - please run: sudo apt-get install ripgrep")
            else:
                _install_ripgrep_via_apt()

        if not is_homebrew_available():
            _install_linux_fallbacks(ui)

        _ensure_bun_available(ui)
