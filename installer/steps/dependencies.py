"""Dependencies step - installs required tools and packages."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from installer.claude_display_patch import apply_display_patch
from installer.claude_paths import get_claude_config_dir
from installer.context import InstallContext
from installer.manifest import UpstreamEntry
from installer.manifest import get as manifest_get
from installer.platform_utils import (
    command_exists,
    ensure_bun_on_path,
    ensure_sudo_credentials,
    is_claude_installed,
    is_codex_installed,
    is_linux_arm64,
    needs_sudo,
    npm_global_cmd,
    start_sudo_keepalive,
    stop_sudo_keepalive,
)
from installer.steps.base import BaseStep

MAX_RETRIES = 3
RETRY_DELAY = 2
GLOBAL_NPM_INSTALL_TIMEOUT = 300
UV_TOOL_INSTALL_TIMEOUT = 180
NPX_CACHE_WAIT_TIMEOUT = 180
DESIGN_PACKAGE_INSTALL_TIMEOUT = 300
OPEN_CLAUDE_DESIGN_CHECKSUM_MAX_BYTES = 64 * 1024
OPEN_CLAUDE_DESIGN_WHEEL_MAX_BYTES = 20 * 1024 * 1024
PILOT_OWNED_TOOLS_MANIFEST = ".pilot-owned-tools.json"

_OPEN_CLAUDE_DESIGN_WHEEL_RE = re.compile(r"^open_claude_design-(?P<version>[0-9][A-Za-z0-9_.!+]*)-py3-none-any[.]whl$")

_INSTALL_KEY_TO_TOOL_COMMANDS: dict[str, dict[str, str]] = {
    "python_tools": {"ruff": "ruff", "basedpyright": "basedpyright"},
    "typescript_lsp": {"vtsls": "vtsls", "typescript": "tsc"},
    "prettier": {"prettier": "prettier"},
    "golangci_lint": {"golangci-lint": "golangci-lint"},
    "pbt_tools": {"hypothesis": "hypothesis", "fast-check": "fast-check"},
    "semble": {"semble": "semble"},
    "ast_grep": {"ast-grep": "ast-grep"},
    "rtk": {"rtk": "rtk"},
    "codegraph": {"codegraph": "codegraph"},
    "open_claude_design": {"open-claude-design": "open-claude-design"},
    "impeccable": {"impeccable": "impeccable"},
    "agent_browser": {"agent-browser": "agent-browser"},
    "playwright_cli": {"playwright-cli": "playwright-cli"},
}


def _owned_tools_manifest_path() -> Path:
    """Return the per-user ownership record written by a real installer run."""
    return Path.home() / ".pilot" / PILOT_OWNED_TOOLS_MANIFEST


class _SudoReauthNeeded(Exception):
    """Raised when sudo -n fails and credentials need re-priming outside the spinner."""


_thread_local = threading.local()

_allow_sudo_fallback: bool = False


def _clear_last_error() -> None:
    _thread_local.last_retry_stderr = ""


def _get_last_error() -> str:
    return getattr(_thread_local, "last_retry_stderr", "")


# Outcome states for install_X functions. The sidechannel lets each install
# function tell the dispatcher whether it actually did work, without changing
# the bool return type that tests mock.
_OUTCOME_INSTALLED = "installed"  # was missing, now installed
_OUTCOME_UPDATED = "updated"  # was present, install/upgrade ran
_OUTCOME_UNCHANGED = "unchanged"  # was present, nothing done (no message)
_OUTCOME_REMOVED = "removed"  # was present, removed (for cleanup steps)


def _record_outcome(state: str) -> None:
    """Record the outcome of the current install/cleanup call.

    Install functions call this before `return True` to signal what actually
    happened. The dispatcher reads via `_take_outcome()` after the call. If
    nothing is recorded (or the function returns False), the dispatcher falls
    back to the legacy "{name} installed" message.
    """
    _thread_local.install_outcome = state


def _take_outcome() -> str:
    state = getattr(_thread_local, "install_outcome", "")
    _thread_local.install_outcome = ""
    return state


def _load_owned_tools() -> set[str]:
    """Load tool IDs that Pilot proved it originally installed."""
    path = _owned_tools_manifest_path()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    tools = payload.get("tools") if isinstance(payload, dict) else None
    if not isinstance(tools, list) or not all(isinstance(item, str) for item in tools):
        return set()
    allowed = {tool for values in _INSTALL_KEY_TO_TOOL_COMMANDS.values() for tool in values}
    return set(tools) & allowed


def _snapshot_tool_presence() -> dict[str, bool]:
    """Capture ownership evidence before Pilot installs or upgrades tools."""
    presence: dict[str, bool] = {}
    for values in _INSTALL_KEY_TO_TOOL_COMMANDS.values():
        for tool, command in values.items():
            if tool == "fast-check":
                try:
                    result = subprocess.run(
                        ["npm", "list", "-g", "--depth=0", "--json", "fast-check"],
                        capture_output=True,
                        timeout=15,
                    )
                    presence[tool] = result.returncode == 0
                except (OSError, subprocess.TimeoutExpired):
                    # Unknown ownership must fail safe: treat it as pre-existing.
                    presence[tool] = True
            else:
                presence[tool] = command_exists(command)
    return presence


def _write_owned_tools(existing: set[str], successful_keys: list[str], present_before: dict[str, bool]) -> None:
    """Persist the union of prior ownership and tools freshly installed now."""
    owned = set(existing)
    for key in successful_keys:
        for tool in _INSTALL_KEY_TO_TOOL_COMMANDS.get(key, {}):
            if not present_before.get(tool, True):
                owned.add(tool)

    path = _owned_tools_manifest_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps({"schema": 1, "tools": sorted(owned)}, indent=2) + "\n", encoding="utf-8")
    os.chmod(temporary, 0o600)
    os.replace(temporary, path)


def _run_bash_with_retry(command: str, cwd: Path | None = None, timeout: int = 120, stream: bool = False) -> bool:
    """Run a bash command with retry logic for transient failures.

    When stream=True, stdout/stderr are inherited (visible to the user)
    instead of captured. Use for long-running commands where progress matters.

    On failure, the last stderr output is stored in _last_retry_stderr
    for diagnostic display by the caller.

    When _allow_sudo_fallback is True and a sudo -n command fails with a
    permission error, raises _SudoReauthNeeded so the caller can stop
    the spinner, re-authenticate, and retry.

    Note: stream=True commands inherit stdio (stderr not captured), so
    sudo failures can't be detected — the user sees the error directly.
    """
    for attempt in range(MAX_RETRIES):
        try:
            if stream:
                subprocess.run(
                    ["bash", "-c", command],
                    check=True,
                    cwd=cwd,
                    timeout=timeout,
                )
            else:
                subprocess.run(
                    ["bash", "-c", command],
                    check=True,
                    capture_output=True,
                    cwd=cwd,
                    timeout=timeout,
                )
            return True
        except subprocess.CalledProcessError as e:
            if not stream and e.stderr:
                stderr = e.stderr if isinstance(e.stderr, str) else e.stderr.decode(errors="replace")
                _thread_local.last_retry_stderr = stderr
                if _allow_sudo_fallback and "sudo:" in stderr and "sudo -n" in command:
                    raise _SudoReauthNeeded()
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
            continue
        except subprocess.TimeoutExpired:
            _thread_local.last_retry_stderr = f"Command timed out after {timeout}s"
            break
    return False


def _download_verified_manifest_file(entry_id: str, destination: Path) -> bool:
    """Download one immutable manifest file and enforce its SHA-256."""
    entry = manifest_get(entry_id)
    if not entry.sha256:
        _thread_local.last_retry_stderr = f"{entry_id} has no SHA-256"
        return False
    try:
        request = urllib.request.Request(entry.source_url, headers={"User-Agent": "Pilot-Shell-Installer"})
        with urllib.request.urlopen(request, timeout=60) as response, destination.open("wb") as output:
            shutil.copyfileobj(response, output)
    except (OSError, urllib.error.URLError) as error:
        _thread_local.last_retry_stderr = str(error)
        return False
    actual = hashlib.sha256(destination.read_bytes()).hexdigest()
    if actual != entry.sha256:
        destination.unlink(missing_ok=True)
        _thread_local.last_retry_stderr = f"SHA-256 mismatch for {entry_id}"
        return False
    return True


def _get_nvm_source_cmd() -> str:
    """Get the command to source NVM for nvm-specific commands.

    Only needed for `nvm install`, `nvm use`, etc. - not for npm/node/claude.
    """
    nvm_locations = [
        Path.home() / ".nvm" / "nvm.sh",
        Path("/usr/local/share/nvm/nvm.sh"),
    ]

    for nvm_path in nvm_locations:
        if nvm_path.exists():
            return f"source {nvm_path} && "

    return ""


def _node_major_version() -> int | None:
    if not command_exists("node"):
        return None
    try:
        result = subprocess.run(
            ["node", "--version"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    match = re.search(r"\bv(\d+)\.", result.stdout)
    return int(match.group(1)) if result.returncode == 0 and match else None


def install_nodejs() -> bool:
    """Ensure Pilot-owned Node tooling runs on Node 24 or newer."""
    if (_node_major_version() or 0) >= 24:
        _record_outcome(_OUTCOME_UNCHANGED)
        return True

    was_present = command_exists("node")
    nvm_dir = Path.home() / ".nvm"
    if not nvm_dir.exists():
        if not _curl_pipe_from_manifest("nvm-curl", CurlPipeRunOptions(timeout=180)):
            return False

    nvm_src = _get_nvm_source_cmd()
    nvm_cmd = f'export NVM_DIR="$HOME/.nvm" && {nvm_src}nvm install 24 && nvm use 24'
    if not _run_bash_with_retry(nvm_cmd, timeout=300):
        return False

    nvm_versions = Path.home() / ".nvm" / "versions" / "node"
    if nvm_versions.exists():
        node_bins = sorted(nvm_versions.glob("*/bin"), reverse=True)
        if node_bins:
            node_bin = str(node_bins[0])
            if node_bin not in os.environ.get("PATH", ""):
                os.environ["PATH"] = f"{node_bin}:{os.environ.get('PATH', '')}"

    _record_outcome(_OUTCOME_UPDATED if was_present else _OUTCOME_INSTALLED)
    return True


def install_uv() -> bool:
    """Install uv package manager if not present (manifest-pinned curl)."""
    if command_exists("uv"):
        _record_outcome(_OUTCOME_UNCHANGED)
        return True
    if _curl_pipe_from_manifest(
        "uv-installer",
        CurlPipeRunOptions(interpreter="sh", timeout=180),
    ):
        _record_outcome(_OUTCOME_INSTALLED)
        return True
    return False


def install_python_tools() -> bool:
    """Install or upgrade Python development tools."""
    tools = ["ruff", "basedpyright"]
    for tool in tools:
        if not _run_bash_with_retry(f"uv tool install --no-config --upgrade {tool}"):
            return False
    _record_outcome(_OUTCOME_UPDATED)
    return True


@dataclass
class CurlPipeRunOptions:
    """Per-upstream knobs for curl-pipe execution.

    interpreter: shell to invoke (`bash`, `sh`, `/bin/bash`, ...).
    script_args: arguments appended after the script path.
    env: environment variables prepended to the exec command.
    stdin_devnull: redirect stdin from /dev/null (non-interactive installers).
    cwd: working directory for the exec phase.
    timeout: timeout in seconds for the exec phase.
    stream: inherit stdout/stderr (long-running installs).
    """

    interpreter: str = "bash"
    script_args: list[str] = field(default_factory=list)
    env: dict[str, str] | None = None
    stdin_devnull: bool = False
    cwd: Path | None = None
    timeout: int = 180
    stream: bool = False


def _curl_pipe_with_hash_verify(
    url: str,
    sha256: str,
    *,
    soft_pin: bool = False,
    options: CurlPipeRunOptions | None = None,
) -> bool:
    """Download a script to an owner-only temp file, verify sha256, then execute.

    Hard-pin (default): hash mismatch fails loud (returns False, no exec).
    Soft-pin: hash mismatch logs the new hash + a re-pin reminder via
    `_thread_local.last_retry_stderr`, then proceeds to execute.

    The exec phase still flows through `_run_bash_with_retry` so sudo
    keepalive and the `_SudoReauthNeeded` exception path are preserved.
    """
    import hashlib
    import shlex
    import tempfile

    opts = options or CurlPipeRunOptions()
    fd, tmp_str = tempfile.mkstemp(suffix=".sh")
    tmp_path = Path(tmp_str)
    try:
        os.fchmod(fd, 0o600)
        os.close(fd)
        if not _run_bash_with_retry(f'curl -fsSL "{url}" -o "{tmp_path}"', timeout=60):
            return False
        actual = hashlib.sha256(tmp_path.read_bytes()).hexdigest()
        if actual != sha256:
            msg = f"sha256 mismatch for {url}: expected {sha256}, got {actual}. " + (
                "WARNING: soft-pinned upstream changed; proceeding. "
                "Audit and re-pin (update manifest sha256 + last_audited)."
                if soft_pin
                else "Refusing to execute. Audit upstream and update manifest."
            )
            _thread_local.last_retry_stderr = msg
            if not soft_pin:
                return False
            # Soft-pin path: success-bound execution would bury the warning
            # because the success path doesn't print last_retry_stderr. Emit
            # to stderr now so the re-pin reminder is visible regardless of
            # downstream exit status.
            print(msg, file=sys.stderr)
        cmd_parts = [opts.interpreter, str(tmp_path), *opts.script_args]
        quoted = " ".join(shlex.quote(p) for p in cmd_parts)
        if opts.env:
            env_prefix = " ".join(f"{k}={shlex.quote(v)}" for k, v in opts.env.items())
            quoted = f"{env_prefix} {quoted}"
        if opts.stdin_devnull:
            quoted = f"{quoted} </dev/null"
        return _run_bash_with_retry(quoted, cwd=opts.cwd, timeout=opts.timeout, stream=opts.stream)
    finally:
        try:
            tmp_path.unlink()
        except OSError:
            pass


def _curl_pipe_from_manifest(entry_id: str, options: CurlPipeRunOptions | None = None) -> bool:
    """Run `_curl_pipe_with_hash_verify` for a manifest curl entry.

    Raises ManifestError when the entry has no sha256 — the schema validates
    this at load time, so this is a defense-in-depth guard rather than a
    common-path branch.
    """
    from installer.manifest import ManifestError

    entry = manifest_get(entry_id)
    if not entry.sha256:
        raise ManifestError(f"curl entry {entry.id} has no sha256; refusing to run curl-pipe")
    return _curl_pipe_with_hash_verify(
        entry.source_url,
        entry.sha256,
        soft_pin=entry.soft_pin,
        options=options,
    )


def _npm_install_cmd(
    *entries: UpstreamEntry,
    force: bool = False,
    extra_flags: tuple[str, ...] = (),
) -> str:
    """Build a manifest-pinned `npm install -g` command.

    Every entry contributes `<source_url>@<version>`. Postinstall scripts are
    denied (`--ignore-scripts`) unless ALL entries opt in via `scripts_policy:
    allow`; mixing policies in one command is rejected so the security
    contract is unambiguous.
    """
    if not entries:
        raise ValueError("at least one manifest entry required")
    policies = {e.scripts_policy for e in entries}
    if len(policies) > 1:
        raise ValueError(
            f"cannot mix scripts_policy=allow/deny in a single npm install command: {[e.id for e in entries]}"
        )
    flags: list[str] = []
    if "deny" in policies:
        flags.append("--ignore-scripts")
    if force:
        flags.append("--force")
    flags.extend(extra_flags)
    pkgs = " ".join(f"{e.source_url}@{e.version}" for e in entries)
    flag_str = " ".join(flags)
    cmd = f"npm install -g {flag_str} {pkgs}".replace("  ", " ").strip()
    return npm_global_cmd(cmd)


def install_semble() -> bool:
    """Install Semble code search tool at the manifest-pinned version.

    Semble is a Python package on PyPI, installed via `uv tool install` so the
    `semble` CLI is on PATH for the AGENTS.md/CLAUDE.md workflow.

    The version is pinned from the manifest rather than floated with
    `--upgrade`, and the `[mcp]` extra is included so the Pilot-installed
    binary can serve both CLI and MCP requests. pilot/.mcp.json launches that
    exact binary through ~/.pilot/bin instead of asking uvx to resolve and
    install a second environment at agent startup.
    `--reinstall` makes the pin authoritative — plain `uv tool install` is a
    no-op when any version is already present, which would strand an older
    install after a manifest bump.
    """
    was_present = command_exists("semble")
    entry = manifest_get("semble")
    if not _run_bash_with_retry(
        f'uv tool install --no-config --reinstall "semble[mcp]=={entry.version}"',
        timeout=UV_TOOL_INSTALL_TIMEOUT,
    ):
        return False

    source = _uv_tool_bin_semble()
    if source is None:
        _thread_local.last_retry_stderr = "Semble installed, but uv's executable could not be located"
        return False
    if not _symlink_to_pilot_bin("semble", source=source):
        _thread_local.last_retry_stderr = "Semble installed, but ~/.pilot/bin/semble could not be created"
        return False
    _record_outcome(_OUTCOME_UPDATED if was_present else _OUTCOME_INSTALLED)
    return True


def install_ast_grep() -> bool:
    """Keep an existing Brew/user install or install the pinned npm fallback.

    Homebrew runs first in PrerequisitesStep and is the preferred source. On a
    host without Brew, a Pilot-owned npm fallback is installed and can be
    upgraded on later Pilot runs. Pre-existing user installs are never replaced.
    """
    was_present = command_exists("ast-grep")
    pilot_owned = "ast-grep" in _load_owned_tools()
    if was_present and not pilot_owned:
        _symlink_to_pilot_bin("ast-grep")
        _record_outcome(_OUTCOME_UNCHANGED)
        return True

    if not _run_bash_with_retry(
        _npm_install_cmd(manifest_get("ast-grep-npm")),
        timeout=GLOBAL_NPM_INSTALL_TIMEOUT,
    ):
        return False

    _symlink_to_pilot_bin("ast-grep")
    _record_outcome(_OUTCOME_UPDATED if was_present else _OUTCOME_INSTALLED)
    return True


def install_rtk() -> bool:
    """Install or update RTK (Rust Token Killer) CLI.

    Always runs the installer to ensure the manifest-pinned version is current.
    Symlinks to ~/.pilot/bin/ so RTK is on PATH during hook execution.
    After install, heals an unusable binary (see ``_heal_broken_rtk``) and runs
    ``rtk init`` for both Claude Code and Codex (if installed).
    """
    was_present = command_exists("rtk")
    # RTK_VERSION is the only lever install.sh offers: without it the script
    # resolves GitHub's /releases/latest, so the manifest version would be a
    # record of what happened to be current rather than the pin it claims to be.
    # The script wants the git tag form (for example v0.48.0); the manifest
    # stores the bare release, same as rtk-brew.
    rtk_version = manifest_get("rtk-installer").version
    if not _curl_pipe_from_manifest(
        "rtk-installer",
        CurlPipeRunOptions(interpreter="sh", timeout=120, env={"RTK_VERSION": f"v{rtk_version}"}),
    ):
        if was_present:
            _symlink_to_pilot_bin("rtk")
            _heal_broken_rtk()
            _record_outcome(_OUTCOME_UNCHANGED)
            return True
        return False
    _symlink_to_pilot_bin("rtk")
    _heal_broken_rtk()
    _init_rtk()
    _record_outcome(_OUTCOME_UPDATED if was_present else _OUTCOME_INSTALLED)
    return True


def _rtk_executes(rtk_path: str | Path) -> bool:
    """Whether the rtk binary at `rtk_path` actually loads and runs.

    A ``--version`` call exiting non-zero (e.g. the arm64 release binary failing
    with a ``GLIBC_2.39 not found`` loader error on an older-glibc base) means
    the binary is present but unusable — it must not be left shadowing a working
    rtk on PATH.
    """
    try:
        result = subprocess.run(
            [str(rtk_path), "--version"],
            capture_output=True,
            timeout=10,
            stdin=subprocess.DEVNULL,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def _heal_broken_rtk() -> None:
    """Recover when the curl-pipe installer drops an unusable rtk that shadows a
    working build on PATH.

    Issue #155: on arm64 the rtk-ai ``install.sh`` installs a glibc-2.39 binary
    at ~/.local/bin/rtk; on a glibc-2.36 base (Debian 12) it cannot load, and
    because ~/.local/bin precedes ~/.pilot/bin and the Homebrew prefix on PATH it
    shadows the working brew rtk. If the rtk that wins on PATH does not execute,
    relink it — and ~/.pilot/bin/rtk — to the first rtk on PATH that does run.
    No-op when the resolved rtk already works.
    """
    resolved = shutil.which("rtk")
    if not resolved or _rtk_executes(resolved):
        return

    working: str | None = None
    seen: set[Path] = set()
    for entry in os.environ.get("PATH", "").split(os.pathsep):
        if not entry:
            continue
        candidate = Path(entry) / "rtk"
        try:
            if not candidate.exists():
                continue
            real = candidate.resolve()
        except OSError:
            continue
        if real in seen:
            continue
        seen.add(real)
        if _rtk_executes(candidate):
            working = str(candidate)
            break
    if not working:
        return

    target = Path(working).resolve()
    for link in (Path(resolved), Path.home() / ".pilot" / "bin" / "rtk"):
        try:
            if link.resolve() == target:
                continue
            link.parent.mkdir(parents=True, exist_ok=True)
            if link.is_symlink() or link.exists():
                link.unlink()
            link.symlink_to(target)
        except OSError:
            pass


def _init_rtk() -> None:
    """Initialize RTK for all detected agents (Claude Code, Codex).

    Each agent's init runs only when the agent CLI is detected — uses the
    canonical platform_utils helpers so the detection set matches cmd_install
    and the per-step agent gates (PATH + native installer fallback paths).
    """
    rtk = shutil.which("rtk")
    if not rtk:
        return
    try:
        subprocess.run(
            [rtk, "telemetry", "disable"],
            capture_output=True,
            timeout=10,
            stdin=subprocess.DEVNULL,
        )
    except (OSError, subprocess.TimeoutExpired):
        pass
    if is_claude_installed():
        try:
            subprocess.run(
                [rtk, "init", "-g", "--auto-patch", "--skip-env"],
                capture_output=True,
                timeout=30,
                stdin=subprocess.DEVNULL,
            )
        except (OSError, subprocess.TimeoutExpired):
            pass
    if is_codex_installed():
        try:
            subprocess.run(
                [rtk, "init", "-g", "--codex"],
                capture_output=True,
                timeout=30,
                stdin=subprocess.DEVNULL,
            )
        except (OSError, subprocess.TimeoutExpired):
            pass


def _uv_tool_bin_semble() -> Path | None:
    """Locate the semble executable via `uv tool dir --bin` (PATH-independent).

    shutil.which() is unreliable here: uv's tool bin dir (~/.local/bin) may be
    absent from the installer's PATH, or an earlier PATH dir may hold a
    shadowing semble without the [mcp] extra.
    """
    try:
        result = subprocess.run(
            ["uv", "tool", "dir", "--bin", "--no-config"],
            capture_output=True,
            text=True,
            timeout=15,
            check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    candidate = Path(result.stdout.strip()) / "semble"
    return candidate if candidate.is_file() and os.access(candidate, os.X_OK) else None


def _symlink_to_pilot_bin(binary_name: str, source: Path | str | None = None) -> bool:
    """Create a symlink in ~/.pilot/bin/ pointing to the installed binary.

    This ensures the binary is in PATH even when its install directory
    (e.g. ~/.nvm/versions/node/vXX/bin/) is not in PATH during hook execution.
    ~/.pilot/bin/ is added to PATH by the shell integration step. When
    `source` is given it is used directly; otherwise the binary is located
    via a PATH lookup.
    """
    pilot_bin = Path.home() / ".pilot" / "bin"
    pilot_bin.mkdir(parents=True, exist_ok=True)
    link_path = pilot_bin / binary_name

    if source is None:
        source = shutil.which(binary_name)
    if not source:
        return False

    source_path = Path(source).resolve()
    try:
        if link_path.is_symlink() or link_path.exists():
            link_path.unlink()
        link_path.symlink_to(source_path)
    except OSError:
        return False
    return link_path.is_file() and os.access(link_path, os.X_OK)


def _is_in_git_repo(directory: Path) -> bool:
    """Check if directory is inside a git repository by walking up the tree."""
    current = directory.resolve()
    while True:
        if (current / ".git").exists():
            return True
        parent = current.parent
        if parent == current:
            return False
        current = parent


def _has_git_commits(directory: Path) -> bool:
    """Whether the git repo containing `directory` has at least one commit.

    A fresh `git init` directory has `.git/` but no commits, so CodeGraph
    cannot build a meaningful symbol graph yet.
    """
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


def install_codegraph() -> bool:
    """Install CodeGraph's self-contained bundle and persist telemetry opt-out."""
    was_present = command_exists("codegraph")
    if not _run_bash_with_retry(
        _npm_install_cmd(manifest_get("codegraph"), force=True),
        timeout=GLOBAL_NPM_INSTALL_TIMEOUT,
    ):
        return False

    _symlink_to_pilot_bin("codegraph")
    if not _run_bash_with_retry("CODEGRAPH_TELEMETRY=0 codegraph telemetry off", timeout=60):
        return False
    _record_outcome(_OUTCOME_UPDATED if was_present else _OUTCOME_INSTALLED)
    return True


def _is_codegraph_indexed(project_dir: Path) -> bool:
    """Check if codegraph has already been indexed.

    Uses the database file size as a reliable indicator: a freshly-init'd
    but unindexed db is ~150KB, while an indexed project is typically >1MB.
    This avoids shelling out to `codegraph status`, which can contend with a
    running MCP server for the project database.
    """
    db_path = project_dir / ".codegraph" / "codegraph.db"
    if not db_path.exists():
        return False
    try:
        return db_path.stat().st_size > 1_000_000
    except OSError:
        return False


def _codegraph_reindex_recommended(project_dir: Path) -> bool:
    """Return CodeGraph's explicit migration signal for an existing index."""
    try:
        result = subprocess.run(
            ["codegraph", "status", "--json"],
            cwd=project_dir,
            env={**os.environ, "CODEGRAPH_TELEMETRY": "0"},
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    if result.returncode != 0:
        return False
    try:
        status = json.loads(result.stdout)
    except (json.JSONDecodeError, TypeError):
        return False
    index = status.get("index") if isinstance(status, dict) else None
    return isinstance(index, dict) and index.get("reindexRecommended") is True


def initialize_codegraph(project_dir: Path) -> bool:
    """Initialize CodeGraph in a project, then index and sync it.

    Streams output so users see indexing progress.
    Skips indexing if already up to date.
    Only indexes actual git repositories to avoid scanning unrelated files.
    """
    if not command_exists("codegraph"):
        return False

    if not _is_in_git_repo(project_dir):
        return False

    if not _has_git_commits(project_dir):
        return False

    codegraph_dir = project_dir / ".codegraph"

    if not codegraph_dir.exists():
        if not _run_bash_with_retry("CODEGRAPH_TELEMETRY=0 codegraph init", cwd=project_dir, timeout=60):
            return False

    is_indexed = _is_codegraph_indexed(project_dir)
    if not is_indexed or _codegraph_reindex_recommended(project_dir):
        if not _run_bash_with_retry(
            "CODEGRAPH_TELEMETRY=0 codegraph index",
            cwd=project_dir,
            timeout=600,
            stream=True,
        ):
            return False

    _run_bash_with_retry("CODEGRAPH_TELEMETRY=0 codegraph sync", cwd=project_dir, timeout=300)
    return True


def codegraph_needs_work(project_dir: Path) -> bool:
    """Check if codegraph initialization or indexing is needed.

    Returns False (no work) when .codegraph/ exists and index is up to date.
    Used by the installer to decide whether to show progress messages.
    Only applies to git repositories.
    """
    if not command_exists("codegraph"):
        return False
    if not _is_in_git_repo(project_dir):
        return False
    if not _has_git_commits(project_dir):
        return False
    codegraph_dir = project_dir / ".codegraph"
    if not codegraph_dir.exists():
        return True
    if not _is_codegraph_indexed(project_dir):
        return True
    return _codegraph_reindex_recommended(project_dir)


def install_typescript_lsp() -> bool:
    """Install or upgrade TypeScript language server and compiler globally (manifest-pinned)."""
    was_present = command_exists("vtsls")
    if not _run_bash_with_retry(
        _npm_install_cmd(manifest_get("vtsls"), manifest_get("typescript")),
        timeout=GLOBAL_NPM_INSTALL_TIMEOUT,
    ):
        return False
    _record_outcome(_OUTCOME_UPDATED if was_present else _OUTCOME_INSTALLED)
    return True


def install_prettier() -> bool:
    """Install or upgrade prettier code formatter globally (manifest-pinned)."""
    was_present = command_exists("prettier")
    if not _run_bash_with_retry(
        _npm_install_cmd(manifest_get("prettier")),
        timeout=GLOBAL_NPM_INSTALL_TIMEOUT,
    ):
        return False
    _record_outcome(_OUTCOME_UPDATED if was_present else _OUTCOME_INSTALLED)
    return True


def _open_claude_design_wheel_version(path: Path) -> str | None:
    match = _OPEN_CLAUDE_DESIGN_WHEEL_RE.fullmatch(path.name)
    return match.group("version") if match is not None else None


def _download_open_claude_design_bytes(url: str, *, maximum_bytes: int) -> bytes | None:
    """Download one bounded Open Claude Design release asset from GitHub over HTTPS."""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "github.com":
        _thread_local.last_retry_stderr = f"Open Claude Design release URL is not trusted: {url}"
        return None
    request = urllib.request.Request(url, headers={"User-Agent": "pilot-shell-installer"})
    try:
        from installer.downloads import _get_ssl_context

        with urllib.request.urlopen(request, timeout=30.0, context=_get_ssl_context()) as response:
            if getattr(response, "status", 200) != 200:
                _thread_local.last_retry_stderr = f"Open Claude Design download returned HTTP {response.status}: {url}"
                return None
            final_url = urllib.parse.urlparse(response.geturl())
            hostname = final_url.hostname or ""
            if final_url.scheme != "https" or not (
                hostname == "github.com" or hostname.endswith(".githubusercontent.com")
            ):
                _thread_local.last_retry_stderr = (
                    f"Open Claude Design download redirected to an untrusted host: {final_url.geturl()}"
                )
                return None
            content_length = response.headers.get("Content-Length")
            if content_length is not None and int(content_length) > maximum_bytes:
                _thread_local.last_retry_stderr = f"Open Claude Design release asset is too large: {url}"
                return None
            body = response.read(maximum_bytes + 1)
    except (OSError, TimeoutError, ValueError, urllib.error.URLError) as error:
        _thread_local.last_retry_stderr = f"Could not download Open Claude Design release asset: {error}"
        return None
    if len(body) > maximum_bytes:
        _thread_local.last_retry_stderr = f"Open Claude Design release asset exceeded its size limit: {url}"
        return None
    return body


def _download_latest_open_claude_design_wheel(destination_dir: Path) -> Path | None:
    """Resolve the latest stable release wheel and verify it against that release's checksum manifest."""
    entry = manifest_get("open-claude-design")
    checksum_url = entry.source_url
    checksum_data = _download_open_claude_design_bytes(
        checksum_url,
        maximum_bytes=OPEN_CLAUDE_DESIGN_CHECKSUM_MAX_BYTES,
    )
    if checksum_data is None:
        return None
    try:
        checksum_text = checksum_data.decode("utf-8")
    except UnicodeDecodeError:
        _thread_local.last_retry_stderr = "Open Claude Design SHA256SUMS is not valid UTF-8"
        return None
    matches: list[tuple[str, str]] = []
    for line in checksum_text.splitlines():
        fields = line.split()
        if len(fields) != 2:
            continue
        digest, filename = fields[0].lower(), fields[1].lstrip("*")
        if _OPEN_CLAUDE_DESIGN_WHEEL_RE.fullmatch(filename) is None:
            continue
        if re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            _thread_local.last_retry_stderr = "Open Claude Design SHA256SUMS contains an invalid wheel digest"
            return None
        matches.append((digest, filename))
    if len(matches) != 1:
        _thread_local.last_retry_stderr = (
            f"Open Claude Design SHA256SUMS must name exactly one universal wheel; found {len(matches)}"
        )
        return None
    expected_digest, filename = matches[0]
    wheel_url = f"{checksum_url.rsplit('/', 1)[0]}/{filename}"
    wheel_data = _download_open_claude_design_bytes(
        wheel_url,
        maximum_bytes=OPEN_CLAUDE_DESIGN_WHEEL_MAX_BYTES,
    )
    if wheel_data is None:
        return None
    actual_digest = hashlib.sha256(wheel_data).hexdigest()
    if actual_digest != expected_digest:
        _thread_local.last_retry_stderr = (
            f"Open Claude Design wheel checksum mismatch: expected {expected_digest}, got {actual_digest}"
        )
        return None
    destination = destination_dir / filename
    destination.write_bytes(wheel_data)
    destination.chmod(0o600)
    return destination


def _open_claude_design_source(ctx: InstallContext, destination_dir: Path) -> Path | None:
    """Resolve an explicit local development wheel or the checksum-verified latest stable release."""
    override = os.environ.get("OPEN_CLAUDE_DESIGN_PACKAGE")
    candidates: list[Path] = []
    if override:
        candidates.append(Path(override).expanduser())
    if ctx.local_mode and ctx.local_repo_dir is not None:
        local_dist = ctx.local_repo_dir.parent / "open-claude-design" / "dist"
        local_wheels = sorted(local_dist.glob("open_claude_design-*-py3-none-any.whl"))
        if len(local_wheels) > 1:
            _thread_local.last_retry_stderr = (
                f"Multiple local Open Claude Design wheels found in {local_dist}; rebuild the release directory"
            )
            return None
        candidates.extend(local_wheels)
    for candidate in candidates:
        if not candidate.is_file():
            continue
        if _open_claude_design_wheel_version(candidate) is None:
            _thread_local.last_retry_stderr = f"Invalid local Open Claude Design wheel filename: {candidate.name}"
            return None
        destination = destination_dir / candidate.name
        shutil.copy2(candidate, destination)
        return destination
    return _download_latest_open_claude_design_wheel(destination_dir)


def install_open_claude_design(ctx: InstallContext) -> bool:
    """Install Open Claude Design and materialize its implicit agent assets."""
    uv = shutil.which("uv")
    if uv is None:
        _thread_local.last_retry_stderr = "uv is required to install Open Claude Design"
        return False
    agents: list[str] = []
    if is_claude_installed():
        agents.append("claude-code")
    if is_codex_installed():
        agents.append("codex")
    if not agents:
        _thread_local.last_retry_stderr = "No supported Open Claude Design agent detected"
        return False

    was_present = command_exists("open-claude-design")
    uv_environment = os.environ.copy()
    for variable in (
        "UV_CONFIG_FILE",
        "UV_EXTRA_INDEX_URL",
        "UV_FIND_LINKS",
        "UV_INDEX",
        "UV_INDEX_URL",
        "UV_KEYRING_PROVIDER",
    ):
        uv_environment.pop(variable, None)
    uv_environment["UV_NO_CONFIG"] = "1"
    uv_environment["UV_DEFAULT_INDEX"] = "https://pypi.org/simple"
    with tempfile.TemporaryDirectory(prefix="pilot-open-claude-design-") as temporary:
        wheel = _open_claude_design_source(ctx, Path(temporary))
        if wheel is None:
            return False
        expected_version = _open_claude_design_wheel_version(wheel)
        if expected_version is None:
            _thread_local.last_retry_stderr = f"Open Claude Design wheel has an invalid filename: {wheel.name}"
            return False
        try:
            preflight = subprocess.run(
                [
                    uv,
                    "tool",
                    "run",
                    "--no-config",
                    "--from",
                    str(wheel),
                    "open-claude-design",
                    "sync",
                    "--help",
                ],
                env=uv_environment,
                capture_output=True,
                text=True,
                shell=False,
                timeout=60,
                check=False,
            )
            if preflight.returncode != 0:
                _thread_local.last_retry_stderr = (
                    preflight.stderr.strip()
                    or preflight.stdout.strip()
                    or "Latest Open Claude Design release is incompatible with Pilot's sync workflow"
                )
                return False
            installed = subprocess.run(
                [
                    uv,
                    "tool",
                    "install",
                    "--no-config",
                    "--default-index",
                    "https://pypi.org/simple",
                    "--no-sources",
                    "--force",
                    str(wheel),
                ],
                env=uv_environment,
                capture_output=True,
                text=True,
                shell=False,
                timeout=DESIGN_PACKAGE_INSTALL_TIMEOUT,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as error:
            _thread_local.last_retry_stderr = str(error)
            return False
        if installed.returncode != 0:
            _thread_local.last_retry_stderr = installed.stderr.strip() or installed.stdout.strip()
            return False

    executable = shutil.which("open-claude-design")
    if executable is None:
        fallback = Path.home() / ".local" / "bin" / "open-claude-design"
        executable = str(fallback) if fallback.is_file() else None
    if executable is None:
        _thread_local.last_retry_stderr = "Open Claude Design installed but its executable is not on PATH"
        return False

    try:
        materialized = subprocess.run(
            [
                executable,
                "install",
                f"--agents={','.join(agents)}",
                "--scope=global",
                "--yes",
                "--json",
            ],
            cwd=ctx.project_dir,
            capture_output=True,
            text=True,
            shell=False,
            timeout=DESIGN_PACKAGE_INSTALL_TIMEOUT,
            check=False,
        )
        compatible = subprocess.run(
            [executable, "sync", "--help"],
            cwd=ctx.project_dir,
            capture_output=True,
            text=True,
            shell=False,
            timeout=60,
            check=False,
        )
        verified = subprocess.run(
            [
                executable,
                "doctor",
                f"--agents={','.join(agents)}",
                "--scope=global",
                "--offline",
                "--json",
            ],
            cwd=ctx.project_dir,
            capture_output=True,
            text=True,
            shell=False,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as error:
        _thread_local.last_retry_stderr = str(error)
        return False
    if materialized.returncode != 0 or compatible.returncode != 0 or verified.returncode != 0:
        _thread_local.last_retry_stderr = (
            materialized.stderr.strip()
            or materialized.stdout.strip()
            or compatible.stderr.strip()
            or compatible.stdout.strip()
            or verified.stderr.strip()
            or verified.stdout.strip()
        )
        return False
    try:
        status = json.loads(verified.stdout)
        if status["package_version"] != expected_version:
            raise ValueError(
                f"installed version {status['package_version']!r} does not match resolved wheel {expected_version!r}"
            )
        skills_status = status["agent_skills"]
        if not skills_status["ready"] or not all(skills_status["skills"].values()):
            raise ValueError("installed artifact is incomplete")
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        _thread_local.last_retry_stderr = f"Open Claude Design doctor returned invalid status: {error}"
        return False

    _record_outcome(_OUTCOME_UPDATED if was_present else _OUTCOME_INSTALLED)
    return True


def install_impeccable(project_dir: Path) -> bool:
    """Install the pinned Impeccable CLI, skills, agents, and detector without provider hooks."""
    was_present = command_exists("impeccable")
    if not _run_bash_with_retry(
        _npm_install_cmd(manifest_get("impeccable")),
        timeout=GLOBAL_NPM_INSTALL_TIMEOUT,
    ):
        return False

    providers: list[str] = []
    if is_claude_installed():
        providers.append("claude")
    if is_codex_installed():
        providers.append("codex")
    if not providers:
        _thread_local.last_retry_stderr = "No supported Impeccable provider detected"
        return False

    executable = shutil.which("impeccable")
    if executable is None:
        _thread_local.last_retry_stderr = "Impeccable CLI was installed but is not on PATH"
        return False

    with tempfile.TemporaryDirectory(prefix="pilot-impeccable-") as temporary:
        bundle = Path(temporary) / "universal.zip"
        if not _download_verified_manifest_file("impeccable-skill-bundle", bundle):
            return False
        environment = os.environ.copy()
        environment["IMPECCABLE_BUNDLE_PATH"] = str(bundle)
        try:
            result = subprocess.run(
                [
                    executable,
                    "install",
                    "--yes",
                    f"--providers={','.join(providers)}",
                    "--scope=global",
                    "--no-hooks",
                ],
                cwd=project_dir,
                env=environment,
                capture_output=True,
                text=True,
                shell=False,
                timeout=DESIGN_PACKAGE_INSTALL_TIMEOUT,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as error:
            _thread_local.last_retry_stderr = str(error)
            return False
        if result.returncode != 0:
            _thread_local.last_retry_stderr = result.stderr.strip() or result.stdout.strip()
            return False
    _record_outcome(_OUTCOME_UPDATED if was_present else _OUTCOME_INSTALLED)
    return True


def _install_go_via_apt() -> bool:
    """Install Go and gopls via apt on Linux."""
    import platform

    if platform.system() != "Linux":
        return False
    if not command_exists("apt-get"):
        return False
    return _run_bash_with_retry(
        "sudo apt-get update -qq && sudo apt-get install -y -qq golang-go gopls",
        timeout=180,
    )


def _is_golangci_lint_installed() -> bool:
    """Check if golangci-lint is installed, including in GOPATH/bin."""
    if command_exists("golangci-lint"):
        return True
    if not command_exists("go"):
        return False
    try:
        result = subprocess.run(["go", "env", "GOPATH"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            gopath_bin = Path(result.stdout.strip()) / "bin" / "golangci-lint"
            if gopath_bin.exists():
                return True
    except Exception:
        pass
    return False


def install_golangci_lint() -> bool:
    """Install or upgrade golangci-lint for comprehensive Go code linting."""
    was_present = _is_golangci_lint_installed()
    if not command_exists("go"):
        if not _install_go_via_apt():
            return False
    try:
        gopath_result = subprocess.run(["go", "env", "GOPATH"], capture_output=True, text=True, timeout=10)
    except (subprocess.SubprocessError, OSError):
        return False
    gopath = gopath_result.stdout.strip()
    if gopath_result.returncode != 0 or not gopath:
        return False
    if _curl_pipe_from_manifest(
        "golangci-lint-installer",
        CurlPipeRunOptions(
            interpreter="sh",
            script_args=["-b", f"{gopath}/bin"],
            timeout=120,
        ),
    ):
        _record_outcome(_OUTCOME_UPDATED if was_present else _OUTCOME_INSTALLED)
        return True
    return False


def _refresh_marketplace(marketplace: str) -> bool:
    """Refresh a marketplace to get latest plugin versions.

    marketplace is in owner/repo format (e.g. "anthropics/claude-plugins-official").
    The update command needs only the short name (e.g. "claude-plugins-official").
    """
    short_name = marketplace.split("/", 1)[-1] if "/" in marketplace else marketplace
    return _run_bash_with_retry(
        f"claude plugins marketplace update {short_name}",
        timeout=60,
    )


def _ensure_plugin_enabled(plugin_id: str) -> bool:
    """Force-enable a Claude plugin idempotently.

    `claude plugins enable` exits non-zero with "already enabled" when the
    plugin is on — we treat that as success, since the desired post-condition
    (plugin enabled) holds either way.
    """
    try:
        result = subprocess.run(
            ["claude", "plugins", "enable", plugin_id],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (subprocess.TimeoutExpired, OSError):
        return False
    if result.returncode == 0:
        return True
    stderr = result.stderr if isinstance(result.stderr, str) else ""
    stdout = result.stdout if isinstance(result.stdout, str) else ""
    return "already enabled" in (stderr + stdout).lower()


def _install_or_update_plugin(
    plugin_id: str,
    marketplace: str,
) -> bool:
    """Install or update a Claude Code plugin via the marketplace.

    Refreshes the marketplace first, then installs or updates the plugin,
    and finally force-enables it. The Claude CLI tracks installed state
    (~/.claude/plugins/installed_plugins.json) and enabled state
    (~/.claude/settings.json → enabledPlugins) independently — `update`
    never auto-enables, and a Claude Code reset can wipe enabledPlugins
    while leaving installed_plugins intact, so we always force-enable.
    """
    if not command_exists("claude"):
        return False

    already_installed = False
    try:
        result = subprocess.run(
            ["claude", "plugins", "list", "--json"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip():
            plugins = json.loads(result.stdout)
            # Defensive: the historical shape is a bare list of {id,version}
            # dicts, but a future Claude CLI may wrap the list (e.g.
            # {"plugins": [...]}). Anything else falls through to
            # fresh-install rather than crashing the installer.
            if isinstance(plugins, list):
                already_installed = any(isinstance(p, dict) and p.get("id") == plugin_id for p in plugins)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError, AttributeError, TypeError):
        pass

    if already_installed:
        _refresh_marketplace(marketplace)
        if not _run_bash_with_retry(
            f"claude plugins update {plugin_id}",
            timeout=120,
        ):
            return False
        if not _ensure_plugin_enabled(plugin_id):
            return False
        _record_outcome(_OUTCOME_UPDATED)
        return True

    if not _run_bash_with_retry(
        f"claude plugins marketplace add {marketplace}",
        timeout=60,
    ):
        return False

    if not _run_bash_with_retry(
        f"claude plugins install {plugin_id}",
        timeout=120,
    ):
        return False

    if not _ensure_plugin_enabled(plugin_id):
        return False
    _record_outcome(_OUTCOME_INSTALLED)
    return True


_LEGACY_CONTEXT_MODE_PLUGIN_ID = "context-mode@context-mode"
_LEGACY_CONTEXT_MODE_MARKETPLACE = "context-mode"
_LEGACY_CONTEXT_MODE_HOOK_FILENAME = "context-mode-cache-heal.mjs"


def remove_legacy_context_mode() -> bool:
    """Remove the legacy context-mode plugin, marketplace, and orphan SessionStart hook.

    Pilot previously installed mksglu/context-mode as an MCP plugin. This cleanup
    runs on every install/upgrade and is idempotent — it pre-checks via JSON list
    output before invoking removal commands so re-runs stay silent. It also deletes
    the auto-deployed `~/.claude/hooks/context-mode-cache-heal.mjs` script and any
    SessionStart hook entry in `~/.claude/settings.json` that references it
    (neither is removed by `claude plugins uninstall`).

    Records outcome `removed` only when something was actually deleted, so
    fresh / already-clean installs stay silent.
    """
    if not command_exists("claude"):
        _record_outcome(_OUTCOME_UNCHANGED)
        return True

    removed_anything = False
    removed_anything |= _legacy_context_mode_uninstall_plugin()
    removed_anything |= _legacy_context_mode_remove_marketplace()
    removed_anything |= _legacy_context_mode_remove_orphan_hook()
    _record_outcome(_OUTCOME_REMOVED if removed_anything else _OUTCOME_UNCHANGED)
    return True


def _legacy_context_mode_uninstall_plugin() -> bool:
    """Uninstall the context-mode plugin if installed. Idempotent. Returns True if removed."""
    try:
        result = subprocess.run(
            ["claude", "plugins", "list", "--json"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return False
        plugins = json.loads(result.stdout)
        has_plugin = any(isinstance(p, dict) and p.get("id") == _LEGACY_CONTEXT_MODE_PLUGIN_ID for p in plugins)
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, json.JSONDecodeError, OSError):
        return False
    if not has_plugin:
        return False
    try:
        subprocess.run(
            ["claude", "plugins", "uninstall", _LEGACY_CONTEXT_MODE_PLUGIN_ID, "-y"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        return True
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, OSError):
        return False


def _legacy_context_mode_remove_marketplace() -> bool:
    """Remove the context-mode marketplace if configured. Idempotent. Returns True if removed."""
    try:
        result = subprocess.run(
            ["claude", "plugins", "marketplace", "list", "--json"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return False
        markets = json.loads(result.stdout)
        has_market = any(isinstance(m, dict) and m.get("name") == _LEGACY_CONTEXT_MODE_MARKETPLACE for m in markets)
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, json.JSONDecodeError, OSError):
        return False
    if not has_market:
        return False
    try:
        subprocess.run(
            ["claude", "plugins", "marketplace", "remove", _LEGACY_CONTEXT_MODE_MARKETPLACE],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return True
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, OSError):
        return False


def _legacy_context_mode_remove_orphan_hook() -> bool:
    """Delete cache-heal hook + matching SessionStart entry in settings.json. Returns True if anything was removed."""
    # Deletes a file and rewrites settings.json, and runs on every install - a
    # hardcoded ~/.claude would mutate the personal profile of a user who
    # installed elsewhere. An invalid value means touch nothing at all.
    try:
        claude_dir = get_claude_config_dir()
    except ValueError:
        return False

    hooks_dir = claude_dir / "hooks"
    orphan = hooks_dir / _LEGACY_CONTEXT_MODE_HOOK_FILENAME
    removed_anything = False
    if orphan.exists():
        try:
            orphan.unlink(missing_ok=True)
            removed_anything = True
        except OSError:
            pass

    settings_path = claude_dir / "settings.json"
    if not settings_path.exists():
        return removed_anything
    try:
        data = json.loads(settings_path.read_text())
    except (json.JSONDecodeError, OSError):
        return removed_anything
    if not isinstance(data, dict):
        return removed_anything
    hooks_section = data.get("hooks")
    if not isinstance(hooks_section, dict):
        return removed_anything
    session_start = hooks_section.get("SessionStart")
    if not isinstance(session_start, list):
        return removed_anything

    cleaned: list[Any] = []
    changed = False
    for entry in session_start:
        if not isinstance(entry, dict):
            cleaned.append(entry)
            continue
        sub_hooks = entry.get("hooks")
        if not isinstance(sub_hooks, list):
            cleaned.append(entry)
            continue
        filtered = [
            h
            for h in sub_hooks
            if not (isinstance(h, dict) and _LEGACY_CONTEXT_MODE_HOOK_FILENAME in str(h.get("command", "")))
        ]
        if len(filtered) == len(sub_hooks):
            cleaned.append(entry)
            continue
        changed = True
        if filtered:
            new_entry = dict(entry)
            new_entry["hooks"] = filtered
            cleaned.append(new_entry)

    if not changed:
        return removed_anything
    hooks_section["SessionStart"] = cleaned
    try:
        settings_path.write_text(json.dumps(data, indent=2) + "\n")
        return True
    except OSError:
        return removed_anything


def install_codex_plugin() -> bool:
    """Install or update the Codex plugin via the Claude CLI plugin system."""
    return _install_or_update_plugin(
        plugin_id="codex@openai-codex",
        marketplace="openai/codex-plugin-cc",
    )


_LSP_MARKETPLACE = "Piebald-AI/claude-code-lsps"
_LSP_PLUGIN_IDS = (
    "vtsls@claude-code-lsps",
    "basedpyright@claude-code-lsps",
    "gopls@claude-code-lsps",
)


def _list_installed_plugin_ids() -> set[str]:
    """Return the set of plugin IDs currently registered with the Claude CLI."""
    if not command_exists("claude"):
        return set()
    try:
        result = subprocess.run(
            ["claude", "plugins", "list", "--json"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return set()
        data = json.loads(result.stdout)
        return {p.get("id", "") for p in data if isinstance(p, dict) and p.get("id")}
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, json.JSONDecodeError, OSError):
        return set()


def _write_pilot_lsp_manifest(plugin_ids: list[str]) -> None:
    """Persist Pilot-installed LSP plugin IDs so uninstall stays surgical.

    Tracks ONLY IDs we freshly installed — user-pre-installed plugins are
    excluded. The uninstall script reads this file and removes only listed IDs.
    """
    manifest_path = Path.home() / ".pilot" / ".pilot-lsp-plugins.json"
    try:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps({"plugins": sorted(plugin_ids)}, indent=2) + "\n")
    except (OSError, IOError):
        pass


def _load_pilot_lsp_manifest() -> set[str]:
    """Load the set of plugin IDs Pilot has previously claimed ownership of."""
    manifest_path = Path.home() / ".pilot" / ".pilot-lsp-plugins.json"
    if not manifest_path.exists():
        return set()
    try:
        data = json.loads(manifest_path.read_text())
        plugins = data.get("plugins") if isinstance(data, dict) else None
        if isinstance(plugins, list):
            return {p for p in plugins if isinstance(p, str)}
    except (json.JSONDecodeError, OSError):
        pass
    return set()


def install_lsp_plugins() -> bool:
    """Install Piebald LSP plugins (vtsls, basedpyright, gopls) via the
    Claude CLI plugin system. Returns True iff ALL three succeed.

    Best-effort: missing claude CLI yields False without raising. Tracks
    Pilot-installed plugin IDs in ~/.pilot/.pilot-lsp-plugins.json so the
    uninstall script removes ONLY plugins Pilot installed (not user-managed ones).

    Ownership across reinstalls: a plugin's ownership is the UNION of
    (a) previously-Pilot-owned IDs (read from the existing manifest) and
    (b) plugins this run installed FRESH (absent from `claude plugins list`
    before our install call). This way, the second-install cycle does NOT
    erase ownership of IDs Pilot installed on the first run, even though those
    IDs now show up as "already present" pre-install. (Codex finding.)

    Sequential rather than parallel: all three share the same marketplace-add
    step inside `_install_or_update_plugin`; parallel execution would race.
    """
    if not command_exists("claude"):
        return False

    previously_owned = _load_pilot_lsp_manifest()
    pre_installed = _list_installed_plugin_ids()
    pilot_owned: set[str] = set(previously_owned)
    all_ok = True
    any_fresh = False
    any_update = False

    for plugin_id in _LSP_PLUGIN_IDS:
        was_present = plugin_id in pre_installed
        was_pilot_owned = plugin_id in previously_owned
        # `_install_or_update_plugin` records its own outcome, but the LSP batch
        # is a single dispatcher step — drain that sidechannel per-plugin so the
        # batched outcome reflects the whole set.
        _take_outcome()
        ok = _install_or_update_plugin(plugin_id, _LSP_MARKETPLACE)
        per_plugin = _take_outcome()
        if ok:
            if per_plugin == _OUTCOME_INSTALLED:
                any_fresh = True
            elif per_plugin == _OUTCOME_UPDATED:
                any_update = True
            # Pilot owns this ID iff we installed it fresh OR we already owned
            # it from a prior install. We do NOT claim ownership of a plugin
            # the user installed manually before Pilot ever ran AND that Pilot
            # has never owned before.
            if not was_present or was_pilot_owned:
                pilot_owned.add(plugin_id)
        else:
            all_ok = False

    # Always (re)write the manifest so callers can detect Pilot's claim set
    # — including the empty-set case where no plugins are Pilot-owned.
    _write_pilot_lsp_manifest(sorted(pilot_owned))

    if all_ok:
        if any_fresh:
            _record_outcome(_OUTCOME_INSTALLED)
        elif any_update:
            _record_outcome(_OUTCOME_UPDATED)
        else:
            _record_outcome(_OUTCOME_UNCHANGED)
    return all_ok


def install_chrome_devtools_plugin() -> bool:
    """Install or update the Chrome DevTools MCP plugin via the Claude CLI plugin system."""
    # Outcome is recorded inside _install_or_update_plugin; pass it through.
    return _install_or_update_plugin(
        plugin_id="chrome-devtools-mcp@chrome-devtools-plugins",
        marketplace="ChromeDevTools/chrome-devtools-mcp",
    )


def install_pbt_tools() -> bool:
    """Install or upgrade property-based testing packages: hypothesis (Python) and fast-check (TypeScript).

    Go PBT is handled by the built-in 'go test -fuzz' (Go 1.18+) — no install needed.
    Both packages are best-effort: failure does not block installation.
    """
    ok = True

    if not _run_bash_with_retry("uv tool install --no-config --upgrade hypothesis", timeout=UV_TOOL_INSTALL_TIMEOUT):
        ok = False

    if not _run_bash_with_retry(
        _npm_install_cmd(manifest_get("fast-check")),
        timeout=GLOBAL_NPM_INSTALL_TIMEOUT,
    ):
        ok = False

    if ok:
        _record_outcome(_OUTCOME_UPDATED)
    return ok


def _is_agent_browser_ready() -> bool:
    """Check if agent-browser is installed and Chrome is available."""
    if not command_exists("agent-browser"):
        return False

    try:
        result = subprocess.run(
            ["agent-browser", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except Exception:
        return False


def install_agent_browser() -> bool:
    """Install or update agent-browser for headless browser automation.

    On Linux ARM64, Chrome for Testing has no builds — install system chromium
    via apt instead. On other Linux, use --with-deps. On macOS, plain install.
    """
    had_browser = _is_agent_browser_ready()

    if not _run_bash_with_retry(_npm_install_cmd(manifest_get("agent-browser"))):
        return False

    if had_browser:
        _record_outcome(_OUTCOME_UPDATED)
        return True

    if is_linux_arm64():
        if not command_exists("apt-get"):
            return False
        if not _run_bash_with_retry(
            "sudo -n apt-get update -qq && sudo -n apt-get install -y -qq chromium",
            timeout=180,
        ):
            return False
        _record_outcome(_OUTCOME_INSTALLED)
        return True

    import platform

    install_cmd = "agent-browser install --with-deps" if platform.system() == "Linux" else "agent-browser install"
    if not _run_bash_with_retry(install_cmd, timeout=300):
        return False
    _record_outcome(_OUTCOME_INSTALLED)
    return True


def _get_playwright_cache_dirs() -> list[Path]:
    """Get possible Playwright cache directories for the current platform."""
    import platform as _platform

    dirs = []
    if _platform.system() == "Darwin":
        dirs.append(Path.home() / "Library" / "Caches" / "ms-playwright")
    dirs.append(Path.home() / ".cache" / "ms-playwright")
    return dirs


def _is_playwright_cli_ready() -> bool:
    """Check if playwright-cli is installed and Chromium is available."""
    if not command_exists("playwright-cli"):
        return False

    for cache_dir in _get_playwright_cache_dirs():
        if not cache_dir.exists():
            continue
        for chromium_dir in cache_dir.glob("chromium-*"):
            if (chromium_dir / "INSTALLATION_COMPLETE").exists():
                return True
        for chromium_dir in cache_dir.glob("chromium_headless_shell-*"):
            if (chromium_dir / "INSTALLATION_COMPLETE").exists():
                return True

    return False


def install_playwright_cli() -> bool:
    """Install or update playwright-cli for advanced browser automation.

    Always runs npm install to keep up to date. Skips browser download
    only if Chromium is already present in the Playwright cache.
    """
    had_cli_ready = _is_playwright_cli_ready()
    if not _run_bash_with_retry(
        _npm_install_cmd(manifest_get("playwright-cli")),
        timeout=GLOBAL_NPM_INSTALL_TIMEOUT,
    ):
        return False

    if had_cli_ready:
        _record_outcome(_OUTCOME_UPDATED)
        return True

    try:
        result = subprocess.run(
            ["playwright-cli", "install-browser", "chromium"],
            capture_output=True,
            text=True,
            timeout=600,
        )
        if result.returncode != 0:
            return False
        _record_outcome(_OUTCOME_INSTALLED)
        return True
    except Exception:
        return False


@dataclass
class _InstallTask:
    """A single install operation that can run in parallel."""

    name: str
    key: str
    fn: Callable[..., bool]
    args: tuple[Any, ...] = ()


@dataclass
class _InstallResult:
    """Result from a parallel install operation."""

    name: str
    key: str
    success: bool
    outcome: str = ""
    error: str = ""


def _run_install_silent(task: _InstallTask) -> _InstallResult:
    """Run an install function without UI, capturing result and error.

    Thread-safe: uses thread-local error tracking.
    """
    _clear_last_error()
    _take_outcome()  # clear any stale outcome from a previous run on this thread
    try:
        success = task.fn(*task.args) if task.args else task.fn()
        outcome = _take_outcome() if success else ""
        return _InstallResult(
            name=task.name,
            key=task.key,
            success=success,
            outcome=outcome,
            error=_get_last_error() if not success else "",
        )
    except _SudoReauthNeeded:
        return _InstallResult(
            name=task.name,
            key=task.key,
            success=False,
            error="sudo credentials expired — re-run the installer",
        )
    except Exception as e:
        return _InstallResult(
            name=task.name,
            key=task.key,
            success=False,
            error=str(e),
        )


def _report_parallel_outcome(ui: Any, result: _InstallResult, installed: list[str]) -> None:
    """Emit one completed parallel install's durable outcome and track success.

    Called as each future completes (not after the whole pool drains) so a slow
    or hung package can't leave `pilot update` with only the `[N/M]` header and a
    transient progress bar; every finished install reports its line immediately.
    Rich renders these prints above the still-active progress bar.
    """
    if result.success:
        installed.append(result.key)
        if ui:
            _report_install_outcome(ui, result.name, result.outcome)
    elif ui:
        ui.warning(f"Could not install {result.name} - please install manually")
        if result.error:
            last_line = result.error.strip().splitlines()[-1].strip()
            ui.info(f"  Error: {last_line}")


def _run_parallel_installs(
    tasks: list[_InstallTask],
    ui: Any,
    max_workers: int = 4,
) -> list[str]:
    """Run multiple installs in parallel, reporting each as it completes.

    Outcomes are emitted in completion order (not task order) so the user sees
    durable progress in real time rather than a silent gap until the slowest
    install finishes. Returns list of installed keys.
    """
    if not tasks:
        return []

    installed: list[str] = []

    if ui:
        with ui.progress(len(tasks), f"Installing {len(tasks)} packages") as progress:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [executor.submit(_run_install_silent, task) for task in tasks]
                for future in as_completed(futures):
                    progress.advance()
                    _report_parallel_outcome(ui, future.result(), installed)
    else:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(_run_install_silent, task) for task in tasks]
            for future in as_completed(futures):
                _report_parallel_outcome(None, future.result(), installed)

    return installed


def _report_install_outcome(ui: Any, name: str, outcome: str) -> None:
    """Print the success message based on what the install function recorded.

    - `unchanged` → silent (no message; the tool was already present and we did nothing)
    - `removed`   → "{name} removed" (for cleanup steps like the legacy plugin)
    - `updated`   → "{name} updated"
    - `installed` (or empty/unknown) → "{name} installed" (legacy default)
    """
    if outcome == _OUTCOME_UNCHANGED:
        return
    if outcome == _OUTCOME_REMOVED:
        ui.success(f"{name} removed")
        return
    if outcome == _OUTCOME_UPDATED:
        ui.success(f"{name} updated")
        return
    ui.success(f"{name} installed")


def _install_with_spinner(ui: Any, name: str, install_fn: Any, *args: Any) -> bool:
    """Run an installation function with a spinner.

    If sudo credentials expire mid-install, the spinner is stopped so the
    user can see the password prompt, credentials are re-primed, and the
    install is retried once.
    """
    _clear_last_error()
    _take_outcome()  # clear any stale outcome from a prior call on this thread
    if ui:
        try:
            with ui.spinner(f"Installing {name}..."):
                result = install_fn(*args) if args else install_fn()
        except _SudoReauthNeeded:
            ui.status("sudo credentials expired — re-authenticating...")
            if ensure_sudo_credentials():
                start_sudo_keepalive()
                try:
                    with ui.spinner(f"Installing {name}..."):
                        result = install_fn(*args) if args else install_fn()
                except _SudoReauthNeeded:
                    _thread_local.last_retry_stderr = "sudo credentials expired — re-run the installer"
                    result = False
            else:
                _thread_local.last_retry_stderr = "sudo credentials expired — re-run the installer"
                result = False
        if result:
            _report_install_outcome(ui, name, _take_outcome())
        else:
            error = _get_last_error()
            if error:
                last_line = error.strip().splitlines()[-1].strip()
                ui.warning(f"Could not install {name} - please install manually")
                ui.info(f"  Error: {last_line}")
            else:
                ui.warning(f"Could not install {name} - please install manually")
        return result
    else:
        try:
            return install_fn(*args) if args else install_fn()
        except _SudoReauthNeeded:
            if ensure_sudo_credentials():
                start_sudo_keepalive()
                try:
                    return install_fn(*args) if args else install_fn()
                except _SudoReauthNeeded:
                    _thread_local.last_retry_stderr = "sudo credentials expired — re-run the installer"
                    return False
            _thread_local.last_retry_stderr = "sudo credentials expired — re-run the installer"
            return False


def _install_plugin_dependencies(_project_dir: Path, ui: Any = None) -> bool:
    """Install Pilot's Node.js dependencies by running bun/npm install in ~/.pilot/.

    Reads ~/.pilot/package.json (installed by the claude_files step as part of
    the pilot_home category) and installs its dependencies — runtime deps for
    the bun worker scripts and MCP servers under ~/.pilot/scripts/.
    """
    pilot_home = Path.home() / ".pilot"

    if not pilot_home.exists():
        if ui:
            ui.warning("~/.pilot/ not found - skipping plugin dependencies")
        return False

    package_json = pilot_home / "package.json"
    if not package_json.exists():
        if ui:
            ui.warning("No package.json in ~/.pilot/ - skipping")
        return False

    # npm is a fallback for a FAILING `bun install`, not only for a missing bun.
    # Previously a bun that existed but errored out returned False here with npm
    # sitting unused, so the whole Node dependency set was simply absent.
    if ensure_bun_on_path():
        if _run_bash_with_retry("bun install", cwd=pilot_home):
            _record_outcome(_OUTCOME_UPDATED)
            return True
        if ui:
            ui.warning("bun install failed - retrying with npm")

    if command_exists("npm"):
        if not _run_bash_with_retry("npm install", cwd=pilot_home):
            return False
        _record_outcome(_OUTCOME_UPDATED)
        return True

    return False


def _setup_pilot_memory(ui: Any) -> bool:
    """Setup pilot-memory (no-op, kept for compatibility)."""
    _record_outcome(_OUTCOME_UNCHANGED)
    return True


def _extract_npx_package_name(package: str) -> str:
    """Extract npm package name without version/tag suffix.

    Examples: "fetcher-mcp" → "fetcher-mcp",
    "open-websearch@2.1.9" → "open-websearch",
    "@upstash/context7-mcp" → "@upstash/context7-mcp",
    "@scope/pkg@1.0" → "@scope/pkg"
    """
    if package.startswith("@"):
        parts = package[1:].split("@", 1)
        return "@" + parts[0]
    return package.split("@", 1)[0]


def _is_npx_package_cached(package: str) -> bool:
    """Check if an npx package is already cached in ~/.npm/_npx/."""
    npx_cache = Path.home() / ".npm" / "_npx"
    if not npx_cache.exists():
        return False
    pkg_name = _extract_npx_package_name(package)
    for hash_dir in npx_cache.iterdir():
        candidate = hash_dir / "node_modules" / pkg_name
        if candidate.is_dir():
            return True
    return False


def _kill_proc(proc: subprocess.Popen[Any]) -> None:
    """Terminate a process, escalating to kill if needed."""
    proc.terminate()
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=2)


def _precache_npx_mcp_servers(_ui: Any) -> bool:
    """Pre-cache npx-based MCP server packages so Claude Code can start them instantly.

    Reads ~/.pilot/.mcp.json (installed by the claude_files step), finds
    servers that use npx, and installs each package into the npx cache using
    --package + -c "true". This ensures packages are fully installed
    (including all dependencies) before returning, avoiding the race condition
    of launching the actual server and killing it mid-install.
    """
    mcp_config_path = Path.home() / ".pilot" / ".mcp.json"
    if not mcp_config_path.exists():
        _record_outcome(_OUTCOME_UNCHANGED)
        return True

    try:
        config = json.loads(mcp_config_path.read_text())
    except (json.JSONDecodeError, OSError):
        return False

    servers = config.get("mcpServers", {})
    npx_packages: list[str] = []

    for server_config in servers.values():
        cmd = server_config.get("command", "")
        args = server_config.get("args", [])
        if cmd == "npx" and len(args) >= 2 and args[0] == "-y":
            npx_packages.append(args[1])

    uncached = [p for p in npx_packages if not _is_npx_package_cached(p)]
    if not uncached:
        _record_outcome(_OUTCOME_UNCHANGED)
        return True

    procs: list[tuple[str, subprocess.Popen[Any]]] = []
    for package in uncached:
        try:
            proc = subprocess.Popen(
                ["npx", "-y", "--package", package, "-c", "true"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
            )
            procs.append((package, proc))
        except Exception:
            continue

    if not procs:
        _record_outcome(_OUTCOME_UNCHANGED)
        return True

    max_wait = NPX_CACHE_WAIT_TIMEOUT
    for _, proc in procs:
        try:
            proc.wait(timeout=max_wait)
        except subprocess.TimeoutExpired:
            _kill_proc(proc)

    _fix_npx_peer_dependencies()
    _record_outcome(_OUTCOME_INSTALLED)
    return True


def _fix_npx_peer_dependencies() -> None:
    """Install missing peer dependencies in npx cache directories.

    open-websearch depends on @modelcontextprotocol/sdk which declares zod
    as a peer dependency. npm's npx cache doesn't always resolve peer deps,
    causing 'Cannot find package zod' at runtime. This installs zod into
    any cache dir that has open-websearch but is missing zod.
    """
    npx_cache = Path.home() / ".npm" / "_npx"
    if not npx_cache.exists():
        return
    zod_entry = manifest_get("zod")
    zod_spec = f"{zod_entry.source_url}@{zod_entry.version}"
    for hash_dir in npx_cache.iterdir():
        nm = hash_dir / "node_modules"
        if (nm / "open-websearch").is_dir() and not (nm / "zod").is_dir():
            try:
                # Manifest-pinned + --ignore-scripts (zod has no postinstall, but
                # this matches the policy enforced everywhere else).
                subprocess.run(
                    ["npm", "install", "--ignore-scripts", zod_spec],
                    cwd=hash_dir,
                    capture_output=True,
                    timeout=60,
                )
            except Exception:
                pass


def _migrate_claude_display_mode() -> None:
    """Reset verbose once per Claude profile, then preserve future user choices."""
    profile = get_claude_config_dir()
    marker = profile / ".pilot-display-patch-migration.json"
    if marker.exists():
        return
    profile.mkdir(parents=True, exist_ok=True)
    settings_path = profile / "settings.json"
    before = settings_path.read_bytes() if settings_path.exists() else None
    settings = json.loads(before) if before is not None else {}
    if not isinstance(settings, dict):
        raise ValueError("Claude settings are not a JSON object")
    change = settings.get("verbose") is not False or settings.get("viewMode") == "verbose"
    if settings.get("viewMode") == "verbose":
        del settings["viewMode"]
    # /config writes verbose, while viewMode takes precedence over it. Keeping
    # a default viewMode override would hide the user's later verbose choice.
    settings["verbose"] = False
    with tempfile.TemporaryDirectory(prefix=".pilot-display-mode-", dir=profile) as work:
        staged_marker = Path(work) / "marker.json"
        staged_marker.write_text('{"version": 1}\n', encoding="utf-8")
        staged_settings = Path(work) / "settings.json"
        staged_settings.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
        staged_settings.chmod(settings_path.stat().st_mode & 0o777 if before is not None else 0o600)
        if (settings_path.read_bytes() if settings_path.exists() else None) != before:
            raise ValueError("Claude settings changed during display migration; preserving the newer settings")
        try:
            # Claim once before activation. An interrupted install must never
            # repeatedly reset a user who subsequently switches verbose back on.
            os.link(staged_marker, marker)
        except FileExistsError:
            return
        try:
            if change:
                os.replace(staged_settings, settings_path)
        except OSError:
            marker.unlink(missing_ok=True)
            raise


def _setup_claude_display_patch(ui: Any = None) -> bool:
    """Enable native display details after Bun/plugins, without blocking install."""
    result = apply_display_patch()
    if result.status == "failed":
        if ui:
            ui.warning(result.message)
        return False
    if result.status in {"patched", "unchanged"}:
        try:
            _migrate_claude_display_mode()
        except (OSError, ValueError) as error:
            if ui:
                ui.warning(f"Claude display details enabled, but the one-time view mode migration failed: {error}")
    if result.status == "patched" and ui:
        ui.success(result.message)
    return result.status in {"patched", "unchanged"}


class DependenciesStep(BaseStep):
    """Step that installs all required dependencies."""

    name = "dependencies"

    def check(self, ctx: InstallContext) -> bool:
        """Always returns False - dependencies should always be checked."""
        return False

    def run(self, ctx: InstallContext) -> None:
        """Install all required dependencies.

        Runs in three phases:
        1. Foundation (sequential) — Node.js, uv (each depends on the previous)
        2. Tools (parallel) — independent npm/uv/curl installs run concurrently
        3. Post-install (sequential) — CodeGraph init, MCP cache (depend on phase 2 binaries)

        Note: Claude Code and Codex CLI are user-installed (README prerequisites).
        The installer detects them in cmd_install; agent-side plugin/integration
        steps below silently no-op when their target agent is absent.
        """
        global _allow_sudo_fallback
        ui = ctx.ui
        installed: list[str] = []
        previously_owned = _load_owned_tools()
        present_before = _snapshot_tool_presence()
        try:
            requires_elevation = needs_sudo() or (is_linux_arm64() and command_exists("apt-get"))
            if requires_elevation and not ctx.non_interactive:
                _allow_sudo_fallback = True
                if ui:
                    ui.status("Some packages require elevated privileges — requesting sudo access...")
                if ensure_sudo_credentials():
                    start_sudo_keepalive()
                elif ui:
                    ui.warning("Could not obtain sudo credentials — some installations may fail")

            # --- Phase 1: Foundation (sequential — each depends on the previous) ---
            if _install_with_spinner(ui, "Node.js", install_nodejs):
                installed.append("nodejs")

            if _install_with_spinner(ui, "uv", install_uv):
                installed.append("uv")

            # Legacy cleanup — must run after Claude Code is installed and before
            # the parallel plugin installs so a single-threaded `claude` invocation
            # handles the uninstall cleanly.
            if _install_with_spinner(ui, "Removing legacy context-mode plugin", remove_legacy_context_mode):
                installed.append("legacy_context_mode_removed")

            # --- Phase 2: Independent tools (parallel) ---
            parallel_tasks = [
                _InstallTask("Python tools", "python_tools", install_python_tools),
                _InstallTask("Plugin dependencies", "plugin_deps", _install_plugin_dependencies, (ctx.project_dir, ui)),
                _InstallTask("vtsls (TypeScript LSP server)", "typescript_lsp", install_typescript_lsp),
                _InstallTask("prettier (TypeScript formatter)", "prettier", install_prettier),
                _InstallTask("golangci-lint (Go linter)", "golangci_lint", install_golangci_lint),
                _InstallTask("PBT tools (hypothesis, fast-check)", "pbt_tools", install_pbt_tools),
                _InstallTask("Semble (code search)", "semble", install_semble),
                _InstallTask("ast-grep (structural search)", "ast_grep", install_ast_grep),
                _InstallTask("RTK (token optimizer)", "rtk", install_rtk),
                _InstallTask("CodeGraph (code intelligence)", "codegraph", install_codegraph),
                _InstallTask("Codex plugin", "codex_plugin", install_codex_plugin),
                _InstallTask("Chrome DevTools MCP plugin", "chrome_devtools_plugin", install_chrome_devtools_plugin),
                _InstallTask("LSP plugins (vtsls, basedpyright, gopls)", "lsp_plugins", install_lsp_plugins),
            ]

            installed.extend(_run_parallel_installs(parallel_tasks, ui))

            # These two packages share agent skill/config directories. Install
            # them sequentially after Pilot has removed its legacy bundled
            # design assets so ownership and hook merges cannot race.
            if _install_with_spinner(ui, "Open Claude Design", install_open_claude_design, ctx):
                installed.append("open_claude_design")

            if _install_with_spinner(
                ui,
                "Impeccable (skills, agents, detector; hooks opt-in)",
                install_impeccable,
                ctx.project_dir,
            ):
                installed.append("impeccable")

            if _setup_pilot_memory(ui):
                installed.append("pilot_memory")

            # Bun is ready and all Claude plugin invocations have finished.
            # Stage/verify the existing native binary; never install Claude here.
            if _setup_claude_display_patch(ui):
                installed.append("claude_display_patch")

            # Browser tools run sequentially (shared Chromium download cache)
            if _install_with_spinner(ui, "agent-browser (browser automation)", install_agent_browser):
                installed.append("agent_browser")

            if _install_with_spinner(ui, "playwright-cli (advanced browser automation)", install_playwright_cli):
                installed.append("playwright_cli")

            # --- Phase 3: Post-install (depends on phase 2 binaries) ---
            needs_work = codegraph_needs_work(ctx.project_dir)
            if needs_work and ui:
                ui.status("Initializing CodeGraph (indexing may take a few minutes)...")
            if initialize_codegraph(ctx.project_dir):
                if needs_work and ui:
                    ui.success("CodeGraph project initialized")
                installed.append("codegraph_init")
            elif needs_work and ui:
                ui.warning("Could not initialize CodeGraph — please run 'codegraph init -i' manually")

            if _install_with_spinner(ui, "MCP server packages", _precache_npx_mcp_servers, ui):
                installed.append("mcp_npx_cache")

            ctx.config["installed_dependencies"] = installed
        finally:
            _write_owned_tools(previously_owned, installed, present_before)
            stop_sudo_keepalive()
            _allow_sudo_fallback = False
