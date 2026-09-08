"""Cross-platform utilities for the installer."""

from __future__ import annotations

import os
import shutil
import subprocess
import threading
from pathlib import Path


def command_exists(command: str) -> bool:
    """Check if a command exists in PATH."""
    return shutil.which(command) is not None


def _agent_present(command: str, *fallback_paths: Path) -> bool:
    """True if `command` is on PATH or any fallback path exists and is executable."""
    if shutil.which(command):
        return True
    return any(p.is_file() and os.access(p, os.X_OK) for p in fallback_paths)


def ensure_bun_on_path() -> bool:
    """True if `bun` is runnable, putting the standalone install dir on PATH if needed.

    bun's standalone installer appends its PATH export to the user's shell rc files
    (`~/.zshrc` and friends), which a non-interactive installer process never sources.
    A machine that already has `~/.bun/bin/bun` therefore reports "no bun" and the
    dependency step silently installs with npm instead - leaving `~/.pilot/` carrying
    both a `bun.lock` and a `package-lock.json`. Checking the well-known location
    directly is what closes that gap; the PATH edit makes the later `bun install`
    (run through a shell) find it too.
    """
    if command_exists("bun"):
        return True
    bun_bin = Path.home() / ".bun" / "bin"
    if (bun_bin / "bun").is_file() and os.access(bun_bin / "bun", os.X_OK):
        os.environ["PATH"] = f"{bun_bin}{os.pathsep}{os.environ.get('PATH', '')}"
        return True
    return False


def is_claude_installed() -> bool:
    """Check whether Claude Code CLI is available.

    Per README prerequisites, users install Claude Code via the native installer;
    the installer only detects its presence (never installs it).

    Fallback paths cover Anthropic's native installer (~/.claude/local/bin/claude),
    system bin (/usr/local/bin/claude), and the macOS app bundle
    (/Applications/Claude.app).
    """
    home = Path.home()
    return _agent_present(
        "claude",
        home / ".claude" / "local" / "bin" / "claude",
        home / ".local" / "bin" / "claude",
        Path("/usr/local/bin/claude"),
        Path("/Applications/Claude.app/Contents/Resources/bin/claude"),
    )


def is_codex_installed() -> bool:
    """Check whether Codex CLI is available.

    Per README prerequisites, users install Codex CLI via the native installer;
    the installer only detects its presence (never installs it).

    Path list overlaps launcher/updater.py:_find_codex_binary; update both
    copies together.
    """
    home = Path.home()
    return _agent_present(
        "codex",
        home / ".codex" / "bin" / "codex",
        home / ".local" / "bin" / "codex",
        home / "Applications" / "ChatGPT.app" / "Contents" / "Resources" / "codex",
        Path("/usr/local/bin/codex"),
        Path("/Applications/ChatGPT.app/Contents/Resources/codex"),
    )


def needs_npm_sudo() -> bool:
    """Check if npm global installs require sudo.

    Returns True when the npm global prefix directory is not writable
    by the current user (e.g. /usr/lib/node_modules on system-wide installs).
    """
    if not command_exists("npm"):
        return False
    try:
        result = subprocess.run(
            ["npm", "prefix", "-g"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return False
        prefix = Path(result.stdout.strip())
        node_modules = prefix / "lib" / "node_modules"
        check_dir = node_modules if node_modules.exists() else prefix
        return not os.access(check_dir, os.W_OK)
    except Exception:
        return False


def npm_global_cmd(cmd: str) -> str:
    """Wrap an npm global command with sudo if needed.

    Uses sudo -n (non-interactive) so it fails fast if credentials
    aren't cached. Call ensure_sudo_credentials() first to prime them.
    """
    if needs_npm_sudo():
        return f"sudo -n {cmd}"
    return cmd


def needs_sudo() -> bool:
    """Check if any installer operations will require sudo.

    Only returns True when npm global installs actually need sudo
    (e.g. system-wide Node where prefix dir is not writable).
    Most users (nvm, Homebrew) never hit this.
    """
    return needs_npm_sudo()


def ensure_sudo_credentials() -> bool:
    """Prompt the user for sudo credentials and cache them.

    Runs `sudo -v` with inherited stdio so the user sees the password
    prompt and can type their password. Once authenticated, subsequent
    `sudo -n` commands succeed without prompting.

    Returns True if sudo credentials are available, False on failure.
    """
    try:
        result = subprocess.run(["sudo", "-v"], timeout=60)
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


_sudo_keepalive_stop: threading.Event | None = None
_sudo_keepalive_thread: threading.Thread | None = None


def start_sudo_keepalive() -> None:
    """Start a background thread that refreshes sudo credentials every 60s.

    macOS caches sudo credentials for ~5 minutes by default. Long install
    sequences exceed this, causing `sudo -n` to fail and interactive sudo
    to hang inside spinners where the user can't see the password prompt.

    Call stop_sudo_keepalive() when elevated operations are done.
    """
    global _sudo_keepalive_stop, _sudo_keepalive_thread

    if _sudo_keepalive_thread is not None and _sudo_keepalive_thread.is_alive():
        return

    _sudo_keepalive_stop = None
    _sudo_keepalive_thread = None

    _sudo_keepalive_stop = threading.Event()
    stop_event = _sudo_keepalive_stop

    def _keepalive() -> None:
        while not stop_event.wait(timeout=60):
            try:
                subprocess.run(
                    ["sudo", "-vn"],
                    capture_output=True,
                    timeout=5,
                )
            except Exception:
                pass

    _sudo_keepalive_thread = threading.Thread(target=_keepalive, daemon=True)
    _sudo_keepalive_thread.start()


def stop_sudo_keepalive() -> None:
    """Stop the sudo keepalive background thread."""
    global _sudo_keepalive_stop, _sudo_keepalive_thread

    if _sudo_keepalive_stop is not None:
        _sudo_keepalive_stop.set()
    if _sudo_keepalive_thread is not None and _sudo_keepalive_thread.is_alive():
        _sudo_keepalive_thread.join(timeout=5)
    _sudo_keepalive_stop = None
    _sudo_keepalive_thread = None


def is_homebrew_available() -> bool:
    """Check if Homebrew is available."""
    return shutil.which("brew") is not None


def is_apt_available() -> bool:
    """Check if apt is available (Debian/Ubuntu Linux)."""
    return shutil.which("apt-get") is not None


def is_dnf_available() -> bool:
    """Check if dnf is available (RHEL 8+/AlmaLinux/Rocky/Fedora)."""
    return shutil.which("dnf") is not None


def is_yum_available() -> bool:
    """Check if yum is available (older RHEL/CentOS)."""
    return shutil.which("yum") is not None


def is_linux() -> bool:
    """Check if running on Linux."""
    import platform

    return platform.system() == "Linux"


def is_linux_arm64() -> bool:
    """Check if running on Linux ARM64 (aarch64)."""
    import platform

    return platform.system() == "Linux" and platform.machine() in ("aarch64", "arm64")


def get_login_shell_config_files() -> list[Path]:
    """Login-shell entry points that must also carry the Pilot PATH export.

    Claude Code builds its Bash-tool shell snapshot with ``<shell> -c -l`` -- a
    *login, non-interactive* shell -- and neither interactive rc file is reached
    by one: Debian's ``.bashrc`` returns at the top on
    ``case $- in *i*) ;; *) return;; esac``, and zsh sources ``.zshrc`` only when
    the shell is interactive. With the PATH export living solely in an rc file,
    ``~/.pilot/bin`` (and therefore ``rtk``) is absent from every agent tool call
    in any session that did not inherit an interactive PATH -- a devcontainer or
    IDE-launched agent being the common case.

    Returned paths need not exist yet; ``ShellConfigStep`` creates them.
    """
    home = Path.home()
    files: list[Path] = []

    bashrc = home / ".bashrc"
    bash_profile = home / ".bash_profile"
    if bash_profile.exists():
        # Login bash reads the *first* of .bash_profile/.bash_login/.profile, so
        # an existing .bash_profile is already the login entry point.
        files.append(bash_profile)
    elif bashrc.exists():
        # The Debian layout: .bashrc with no .bash_profile, so login bash falls
        # through to .profile.
        files.append(home / ".profile")

    if (home / ".zshrc").exists():
        files.append(home / ".zprofile")

    # fish needs no companion file: config.fish is read by every fish shell,
    # login or not, interactive or not.
    return files


def get_shell_config_files() -> list[Path]:
    """Get list of shell configuration files for the current user.

    Interactive rc files plus the login entry points returned by
    :func:`get_login_shell_config_files`.
    """
    home = Path.home()
    configs = []

    bashrc = home / ".bashrc"
    bash_profile = home / ".bash_profile"
    if bashrc.exists():
        configs.append(bashrc)
    if bash_profile.exists():
        configs.append(bash_profile)

    zshrc = home / ".zshrc"
    if zshrc.exists():
        configs.append(zshrc)

    fish_config = home / ".config" / "fish" / "config.fish"
    if fish_config.exists():
        configs.append(fish_config)

    for login_file in get_login_shell_config_files():
        if login_file not in configs:
            configs.append(login_file)

    if not configs:
        configs = [bashrc, zshrc, fish_config]

    return configs
