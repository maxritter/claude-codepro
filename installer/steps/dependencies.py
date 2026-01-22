"""Dependencies step - installs required tools and packages."""

from __future__ import annotations

import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any

from installer.context import InstallContext
from installer.platform_utils import command_exists
from installer.steps.base import BaseStep

MAX_RETRIES = 3
RETRY_DELAY = 2

ANSI_ESCAPE_PATTERN = re.compile(
    r"\x1b\[\??[0-9;]*[a-zA-Z]"
    r"|\x1b\].*?\x07"
    r"|\x1b[PX^_][^\x1b]*\x1b\\\\"
    r"|\r"
)


def _strip_ansi(text: str) -> str:
    """Strip ANSI escape codes from text."""
    result = ANSI_ESCAPE_PATTERN.sub("", text)
    result = "".join(c for c in result if c == "\n" or (ord(c) >= 32 and ord(c) != 127))
    return result.strip()


def _run_bash_with_retry(command: str, cwd: Path | None = None) -> bool:
    """Run a bash command with retry logic for transient failures."""
    for attempt in range(MAX_RETRIES):
        try:
            subprocess.run(
                ["bash", "-c", command],
                check=True,
                capture_output=True,
                cwd=cwd,
            )
            return True
        except subprocess.CalledProcessError:
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
            continue
    return False


def _is_plugin_installed(plugin_name: str, marketplace: str | None = None) -> bool:
    """Check if a Claude plugin is already installed.

    Args:
        plugin_name: The plugin name (e.g., "claude-mem", "typescript-lsp")
        marketplace: Optional marketplace name (e.g., "thedotmack", "claude-plugins-official")

    Returns:
        True if the plugin is installed, False otherwise.
    """
    import json

    installed_path = Path.home() / ".claude" / "plugins" / "installed_plugins.json"
    if not installed_path.exists():
        return False

    try:
        data = json.loads(installed_path.read_text())
        plugins = data.get("plugins", {})

        if marketplace:
            key = f"{plugin_name}@{marketplace}"
            return key in plugins and len(plugins[key]) > 0

        for key in plugins:
            if key.startswith(f"{plugin_name}@") and len(plugins[key]) > 0:
                return True
        return False
    except (json.JSONDecodeError, OSError):
        return False


def _is_marketplace_installed(marketplace_name: str) -> bool:
    """Check if a Claude marketplace is already installed.

    Args:
        marketplace_name: The marketplace name (e.g., "claude-plugins-official", "thedotmack")

    Returns:
        True if the marketplace is installed, False otherwise.
    """
    import json

    marketplaces_path = Path.home() / ".claude" / "plugins" / "known_marketplaces.json"
    if not marketplaces_path.exists():
        return False

    try:
        data = json.loads(marketplaces_path.read_text())
        return marketplace_name in data
    except (json.JSONDecodeError, OSError):
        return False


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


def install_nodejs() -> bool:
    """Install Node.js via NVM if not present."""
    if command_exists("node"):
        return True

    nvm_dir = Path.home() / ".nvm"
    if not nvm_dir.exists():
        if not _run_bash_with_retry("curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.0/install.sh | bash"):
            return False

    nvm_src = _get_nvm_source_cmd()
    return _run_bash_with_retry(f"{nvm_src}nvm install 22 && nvm use 22")


def install_uv() -> bool:
    """Install uv package manager if not present."""
    if command_exists("uv"):
        return True

    return _run_bash_with_retry("curl -LsSf https://astral.sh/uv/install.sh | sh")


def install_python_tools() -> bool:
    """Install Python development tools."""
    tools = ["ruff", "basedpyright"]

    try:
        for tool in tools:
            if not command_exists(tool):
                subprocess.run(
                    ["uv", "tool", "install", tool],
                    check=True,
                    capture_output=True,
                )
        return True
    except subprocess.CalledProcessError:
        return False


def _remove_npm_claude_binaries() -> None:
    """Remove npm-installed Claude Code to avoid conflicts with native install."""
    import shutil

    nvm_source = _get_nvm_source_cmd()
    try:
        subprocess.run(
            ["bash", "-c", f"{nvm_source}npm uninstall -g @anthropic-ai/claude-code"],
            capture_output=True,
            timeout=30,
        )
    except Exception:
        pass

    npm_locations = [
        Path.home() / ".nvm" / "versions" / "node",
        Path("/usr/local/share/nvm/versions/node"),
        Path("/usr/local/lib/node_modules"),
        Path("/usr/lib/node_modules"),
    ]

    for base_path in npm_locations:
        if not base_path.exists():
            continue

        if "nvm" in str(base_path) and "versions" in str(base_path):
            for node_version in base_path.glob("v*"):
                claude_pkg = node_version / "lib" / "node_modules" / "@anthropic-ai" / "claude-code"
                claude_bin = node_version / "bin" / "claude"
                if claude_pkg.exists():
                    shutil.rmtree(claude_pkg, ignore_errors=True)
                if claude_bin.exists() or claude_bin.is_symlink():
                    try:
                        claude_bin.unlink()
                    except Exception:
                        pass
        else:
            claude_pkg = base_path / "@anthropic-ai" / "claude-code"
            if claude_pkg.exists():
                shutil.rmtree(claude_pkg, ignore_errors=True)


def _patch_claude_config(config_updates: dict) -> bool:
    """Patch ~/.claude.json with the given config updates.

    Creates the file if it doesn't exist. Merges updates with existing config.
    """
    import json

    config_path = Path.home() / ".claude.json"

    try:
        if config_path.exists():
            config = json.loads(config_path.read_text())
        else:
            config = {}

        config.update(config_updates)
        config_path.write_text(json.dumps(config, indent=2) + "\n")
        return True
    except Exception:
        return False


def _configure_claude_defaults() -> bool:
    """Configure Claude Code with recommended defaults after installation."""
    return _patch_claude_config(
        {
            "installMethod": "native",
            "theme": "dark-ansi",
            "verbose": True,
            "autoCompactEnabled": False,
            "autoConnectIde": True,
            "respectGitignore": False,
        }
    )


def _configure_firecrawl_mcp(api_key: str | None = None) -> bool:
    """Add firecrawl MCP server to ~/.claude.json if not already present.

    Only adds the firecrawl server - does not alter other MCP servers.
    If api_key is provided, stores it directly. Otherwise uses env var reference.
    """
    import json

    config_path = Path.home() / ".claude.json"

    env_value = api_key if api_key else "${FIRECRAWL_API_KEY}"
    firecrawl_config = {
        "command": "npx",
        "args": ["-y", "firecrawl-mcp"],
        "env": {"FIRECRAWL_API_KEY": env_value},
    }

    try:
        if config_path.exists():
            config = json.loads(config_path.read_text())
        else:
            config = {}

        if "mcpServers" not in config:
            config["mcpServers"] = {}

        if api_key or "firecrawl" not in config["mcpServers"]:
            config["mcpServers"]["firecrawl"] = firecrawl_config
            config_path.write_text(json.dumps(config, indent=2) + "\n")

        return True
    except Exception:
        return False


def _get_forced_claude_version(project_dir: Path) -> str | None:
    """Check settings.local.json for FORCE_CLAUDE_VERSION in env section."""
    import json

    settings_path = project_dir / ".claude" / "settings.local.json"
    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text())
            return settings.get("env", {}).get("FORCE_CLAUDE_VERSION")
        except (json.JSONDecodeError, OSError):
            pass
    return None


def _get_installed_claude_version() -> str | None:
    """Get the currently installed Claude Code version via native installer."""
    claude_bin = Path.home() / ".local" / "bin" / "claude"
    if not claude_bin.exists():
        return None

    try:
        result = subprocess.run(
            [str(claude_bin), "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            version_str = result.stdout.strip()
            for part in version_str.split():
                if part[0].isdigit():
                    return part
            return version_str
    except Exception:
        pass
    return None


GCS_BUCKET = "https://storage.googleapis.com/claude-code-dist-86c565f3-f756-42ad-8dfa-d59b1c096819/claude-code-releases"


def _get_claude_platform() -> str | None:
    """Get the platform string for Claude Code binary downloads."""
    import platform as plat

    system = plat.system().lower()
    machine = plat.machine().lower()

    if system == "darwin":
        os_name = "darwin"
    elif system == "linux":
        os_name = "linux"
    else:
        return None

    if machine in ("x86_64", "amd64"):
        arch = "x64"
    elif machine in ("arm64", "aarch64"):
        arch = "arm64"
    else:
        return None

    if os_name == "linux":
        libc_path_x86 = Path("/lib/libc.musl-x86_64.so.1")
        libc_path_arm = Path("/lib/libc.musl-aarch64.so.1")
        if libc_path_x86.exists() or libc_path_arm.exists():
            return f"linux-{arch}-musl"
        return f"linux-{arch}"

    return f"{os_name}-{arch}"


def _download_claude_binary_with_progress(
    version: str,
    dest_path: Path,
    ui: Any = None,
) -> bool:
    """Download Claude Code binary with progress display.

    Args:
        version: Version to download (e.g., "1.0.33")
        dest_path: Where to save the binary
        ui: Optional UI instance for progress display

    Returns:
        True if successful, False otherwise
    """
    import hashlib

    import httpx

    platform_str = _get_claude_platform()
    if not platform_str:
        return False

    try:
        with httpx.Client(timeout=30.0) as client:
            manifest_url = f"{GCS_BUCKET}/{version}/manifest.json"
            response = client.get(manifest_url)
            if response.status_code != 200:
                return False

            manifest = response.json()
            platform_info = manifest.get("platforms", {}).get(platform_str)
            if not platform_info:
                return False

            expected_checksum = platform_info.get("checksum", "")

        binary_url = f"{GCS_BUCKET}/{version}/{platform_str}/claude"
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        with httpx.Client(timeout=240.0, follow_redirects=True) as client:
            with client.stream("GET", binary_url) as response:
                if response.status_code != 200:
                    return False

                total = int(response.headers.get("content-length", 0))
                downloaded = 0
                sha256_hash = hashlib.sha256()

                if ui and total > 0:
                    with ui.progress(100, "Downloading Claude Code") as progress:
                        with open(dest_path, "wb") as f:
                            for chunk in response.iter_bytes(chunk_size=8192):
                                f.write(chunk)
                                sha256_hash.update(chunk)
                                downloaded += len(chunk)
                                pct = int((downloaded / total) * 100)
                                progress.update(pct)
                else:
                    with open(dest_path, "wb") as f:
                        for chunk in response.iter_bytes(chunk_size=8192):
                            f.write(chunk)
                            sha256_hash.update(chunk)

        actual_checksum = sha256_hash.hexdigest()
        if expected_checksum and actual_checksum != expected_checksum:
            dest_path.unlink(missing_ok=True)
            return False

        dest_path.chmod(dest_path.stat().st_mode | 0o755)
        return True

    except (httpx.HTTPError, httpx.TimeoutException, OSError):
        dest_path.unlink(missing_ok=True)
        return False


def _run_claude_installer(binary_path: Path, version: str, ui: Any = None) -> bool:
    """Run the Claude Code installer binary with clean output."""
    env = os.environ.copy()
    env["NO_COLOR"] = "1"
    env["TERM"] = "dumb"

    process: subprocess.Popen[str] | None = None
    try:
        process = subprocess.Popen(
            [str(binary_path), "install", "--force", version],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
        )

        if process.stdout:
            for line in process.stdout:
                cleaned = _strip_ansi(line)
                if cleaned and ui:
                    ui.print(f"  {cleaned}")

        process.wait(timeout=120)
        binary_path.unlink(missing_ok=True)
        return process.returncode == 0
    except subprocess.TimeoutExpired:
        if ui:
            ui.warning("Installer timed out after 120s")
        if process:
            process.kill()
        binary_path.unlink(missing_ok=True)
    except (subprocess.SubprocessError, OSError) as e:
        if ui:
            ui.warning(f"Installer error: {e}")
        binary_path.unlink(missing_ok=True)
    return False


def _fetch_latest_claude_version(ui: Any = None) -> str | None:
    """Fetch the latest Claude Code version from GCS bucket."""
    import httpx

    if ui:
        ui.status("Fetching latest Claude Code version...")
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(f"{GCS_BUCKET}/latest")
            if response.status_code == 200:
                version = response.text.strip()
                if ui:
                    ui.info(f"Latest version: v{version}")
                return version
    except (httpx.HTTPError, httpx.TimeoutException):
        if ui:
            ui.warning("Could not fetch latest version, using fallback installer")
    return None


def install_claude_code(project_dir: Path, ui: Any = None) -> tuple[bool, str]:
    """Install/upgrade Claude Code CLI via native installer and configure defaults."""
    _remove_npm_claude_binaries()

    forced_version = _get_forced_claude_version(project_dir)
    version = forced_version if forced_version else "latest"

    if version != "latest":
        installed_version = _get_installed_claude_version()
        if installed_version == version:
            _configure_claude_defaults()
            return True, version

    actual_version = version if version != "latest" else _fetch_latest_claude_version(ui)

    if actual_version:
        download_dir = Path.home() / ".claude" / "downloads"
        download_dir.mkdir(parents=True, exist_ok=True)
        binary_path = download_dir / f"claude-{actual_version}"

        if ui:
            ui.status(f"Downloading Claude Code v{actual_version}...")

        if _download_claude_binary_with_progress(actual_version, binary_path, ui):
            if ui:
                ui.status(f"Running Claude Code installer (v{actual_version})...")
            if _run_claude_installer(binary_path, actual_version, ui):
                _configure_claude_defaults()
                return True, actual_version
            elif ui:
                ui.warning("Installer failed, falling back to curl installer")
        elif ui:
            ui.warning("Download failed, falling back to curl installer")

    if ui:
        ui.status("Running fallback installer (curl)...")

    if not _run_bash_with_retry(f"curl -fsSL https://claude.ai/install.sh | bash -s {version}"):
        return False, version

    _configure_claude_defaults()
    return True, version


def install_qlty(project_dir: Path) -> tuple[bool, bool]:
    """Install qlty code quality tool. Returns (success, was_fresh_install)."""
    qlty_bin = Path.home() / ".qlty" / "bin" / "qlty"

    if command_exists("qlty") or qlty_bin.exists():
        return True, False

    success = _run_bash_with_retry("curl https://qlty.sh | bash", cwd=project_dir)
    return success, success


def run_qlty_check(project_dir: Path, ui) -> bool:
    """Run qlty check to download prerequisites (linters)."""
    import os

    qlty_bin = Path.home() / ".qlty" / "bin" / "qlty"
    if not qlty_bin.exists():
        return False

    env = os.environ.copy()
    env["PATH"] = f"{qlty_bin.parent}:{env.get('PATH', '')}"

    try:
        process = subprocess.Popen(
            [str(qlty_bin), "check", "--no-fix", "--no-formatters", "--no-fail", "--install-only"],
            cwd=project_dir,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        if process.stdout:
            for line in process.stdout:
                line = line.rstrip()
                if line and ui:
                    if "Installing" in line or "Downloading" in line or "✔" in line:
                        ui.print(f"  {line}")

        process.wait()
        return True
    except Exception:
        return False


def _ensure_official_marketplace() -> bool:
    """Ensure official Claude plugins marketplace is installed."""
    if _is_marketplace_installed("claude-plugins-official"):
        return True

    try:
        result = subprocess.run(
            ["bash", "-c", "claude plugin marketplace add anthropics/claude-plugins-official"],
            capture_output=True,
            text=True,
        )
        output = (result.stdout + result.stderr).lower()
        return result.returncode == 0 or "already installed" in output
    except Exception:
        return False


def install_typescript_lsp() -> bool:
    """Install TypeScript language server and plugin via npm and claude plugin."""
    if not _run_bash_with_retry("npm install -g typescript-language-server typescript"):
        return False

    if _is_plugin_installed("typescript-lsp", "claude-plugins-official"):
        return True

    if not _ensure_official_marketplace():
        return False

    return _run_bash_with_retry("claude plugin install typescript-lsp")


def install_pyright_lsp() -> bool:
    """Install pyright language server and plugin via npm and claude plugin."""
    if not _run_bash_with_retry("npm install -g pyright"):
        return False

    if _is_plugin_installed("pyright-lsp", "claude-plugins-official"):
        return True

    if not _ensure_official_marketplace():
        return False

    return _run_bash_with_retry("claude plugin install pyright-lsp")


def _configure_claude_mem_defaults() -> bool:
    """Configure Claude Mem with recommended defaults."""
    import json

    settings_dir = Path.home() / ".claude-mem"
    settings_path = settings_dir / "settings.json"

    try:
        settings_dir.mkdir(parents=True, exist_ok=True)

        if settings_path.exists():
            settings = json.loads(settings_path.read_text())
        else:
            settings = {}

        settings.update(
            {
                "CLAUDE_MEM_FOLDER_CLAUDEMD_ENABLED": "false",
                "CLAUDE_MEM_CONTEXT_SHOW_LAST_SUMMARY": "true",
                "CLAUDE_MEM_CONTEXT_SHOW_LAST_MESSAGE": "true",
                "CLAUDE_MEM_CONTEXT_OBSERVATIONS": "50",
                "CLAUDE_MEM_CONTEXT_SESSION_COUNT": "10",
                "CLAUDE_MEM_CONTEXT_FULL_COUNT": "10",
                "CLAUDE_MEM_CONTEXT_FULL_FIELD": "facts",
                "CLAUDE_MEM_MODEL": "sonnet",
            }
        )
        settings_path.write_text(json.dumps(settings, indent=2) + "\n")
        return True
    except Exception:
        return False


def _configure_vexor_defaults() -> bool:
    """Configure Vexor with recommended defaults for semantic search (OpenAI)."""
    import json

    config_dir = Path.home() / ".vexor"
    config_path = config_dir / "config.json"

    try:
        config_dir.mkdir(parents=True, exist_ok=True)

        if config_path.exists():
            config = json.loads(config_path.read_text())
        else:
            config = {}

        config.update(
            {
                "model": "text-embedding-3-small",
                "batch_size": 64,
                "embed_concurrency": 4,
                "extract_concurrency": 4,
                "extract_backend": "auto",
                "provider": "openai",
                "auto_index": True,
                "local_cuda": False,
                "rerank": "bm25",
            }
        )
        config_path.write_text(json.dumps(config, indent=2) + "\n")
        return True
    except Exception:
        return False


def _configure_vexor_local() -> bool:
    """Configure Vexor for local embeddings (no API key needed)."""
    import json

    config_dir = Path.home() / ".vexor"
    config_path = config_dir / "config.json"

    try:
        config_dir.mkdir(parents=True, exist_ok=True)

        if config_path.exists():
            config = json.loads(config_path.read_text())
        else:
            config = {}

        config.update(
            {
                "model": "intfloat/multilingual-e5-small",
                "batch_size": 64,
                "embed_concurrency": 4,
                "extract_concurrency": 4,
                "extract_backend": "auto",
                "provider": "local",
                "auto_index": True,
                "local_cuda": False,
                "rerank": "bm25",
            }
        )
        config_path.write_text(json.dumps(config, indent=2) + "\n")
        return True
    except Exception:
        return False


def _setup_vexor_local_model(ui: Any = None) -> bool:
    """Download and setup the local embedding model for Vexor."""
    if ui:
        ui.status("Downloading local embedding model...")

    try:
        process = subprocess.Popen(
            ["vexor", "local", "--setup", "--model", "intfloat/multilingual-e5-small"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        if process.stdout:
            for line in process.stdout:
                line = line.rstrip()
                if line and ui:
                    if any(kw in line.lower() for kw in ["download", "model", "%", "mb", "complete"]):
                        ui.print(f"  {line}")

        process.wait()
        return process.returncode == 0
    except Exception:
        return False


def install_vexor(use_local: bool = False, ui: Any = None) -> bool:
    """Install Vexor semantic search tool and configure defaults."""
    if use_local:
        if not _run_bash_with_retry("uv pip install 'vexor[local]'"):
            return False
        _configure_vexor_local()
        return _setup_vexor_local_model(ui)
    else:
        if command_exists("vexor"):
            _configure_vexor_defaults()
            return True
        _configure_vexor_defaults()
        return True


def _ensure_maxritter_marketplace() -> bool:
    """Ensure claude-mem marketplace points to maxritter repo.

    Checks known_marketplaces.json for thedotmack entry. If it exists
    with maxritter URL, returns True. If it exists with wrong URL, removes it.
    """
    import json

    marketplaces_path = Path.home() / ".claude" / "plugins" / "known_marketplaces.json"

    if marketplaces_path.exists():
        try:
            data = json.loads(marketplaces_path.read_text())
            thedotmack = data.get("thedotmack", {})
            source = thedotmack.get("source", {})
            url = source.get("url", "")

            if thedotmack and "maxritter" in url:
                return True

            if thedotmack and "maxritter" not in url:
                subprocess.run(
                    ["bash", "-c", "claude plugin marketplace rm thedotmack"],
                    capture_output=True,
                )
        except (json.JSONDecodeError, KeyError):
            pass

    try:
        result = subprocess.run(
            ["bash", "-c", "claude plugin marketplace add https://github.com/maxritter/claude-mem.git"],
            capture_output=True,
            text=True,
        )
        output = (result.stdout + result.stderr).lower()
        return result.returncode == 0 or "already installed" in output
    except Exception:
        return False


def install_claude_mem() -> bool:
    """Install claude-mem plugin via claude plugin marketplace."""
    if _is_plugin_installed("claude-mem", "thedotmack"):
        _configure_claude_mem_defaults()
        return True

    if not _ensure_maxritter_marketplace():
        return False

    if not _run_bash_with_retry("claude plugin install claude-mem"):
        return False

    _configure_claude_mem_defaults()
    return True


def _is_claude_mem_deps_installed() -> bool:
    """Check if claude-mem bun dependencies are already installed."""
    import json

    plugin_dir = Path.home() / ".claude" / "plugins" / "marketplaces" / "thedotmack"
    node_modules = plugin_dir / "node_modules"
    marker_file = plugin_dir / ".install-version"

    if not node_modules.exists():
        return False

    if not marker_file.exists():
        return False

    try:
        pkg_path = plugin_dir / "package.json"
        if not pkg_path.exists():
            return False

        pkg = json.loads(pkg_path.read_text())
        marker = json.loads(marker_file.read_text())

        return pkg.get("version") == marker.get("version")
    except (json.JSONDecodeError, OSError):
        return False


def preinstall_claude_mem_deps(ui: Any = None) -> bool:
    """Pre-install bun dependencies for claude-mem to speed up first start.

    This runs `bun install` in the plugin directory and creates the version
    marker file, so the smart-install.js hook skips installation on first start.
    """
    import datetime
    import json

    plugin_dir = Path.home() / ".claude" / "plugins" / "marketplaces" / "thedotmack"

    if not plugin_dir.exists():
        return False

    if _is_claude_mem_deps_installed():
        return True

    if not command_exists("bun"):
        return False

    if ui:
        ui.print("  [dim]Pre-installing claude-mem dependencies...[/dim]")

    try:
        process = subprocess.Popen(
            ["bun", "install"],
            cwd=plugin_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        if process.stdout:
            for line in process.stdout:
                line = line.rstrip()
                if line and ui:
                    if any(kw in line.lower() for kw in ["install", "package", "done", "+"]):
                        ui.print(f"  {line}")

        process.wait()

        if process.returncode != 0:
            return False

        pkg_path = plugin_dir / "package.json"
        marker_path = plugin_dir / ".install-version"

        if pkg_path.exists():
            pkg = json.loads(pkg_path.read_text())

            bun_version = None
            try:
                result = subprocess.run(
                    ["bun", "--version"],
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0:
                    bun_version = result.stdout.strip()
            except Exception:
                pass

            marker_data = {
                "version": pkg.get("version"),
                "bun": bun_version,
                "installedAt": datetime.datetime.now().isoformat(),
            }
            marker_path.write_text(json.dumps(marker_data))

        return True
    except Exception:
        return False


def install_context7() -> bool:
    """Install context7 plugin via claude plugin."""
    if _is_plugin_installed("context7", "claude-plugins-official"):
        return True

    if not _ensure_official_marketplace():
        return False

    return _run_bash_with_retry("claude plugin install context7")


def install_mcp_cli() -> bool:
    """Install mcp-cli via bun for MCP server interaction."""
    if not command_exists("bun"):
        return False

    return _run_bash_with_retry("bun install -g https://github.com/philschmid/mcp-cli")


def _is_agent_browser_ready() -> bool:
    """Check if agent-browser is installed and Chromium is available."""
    if not command_exists("agent-browser"):
        return False

    cache_dir = Path.home() / ".cache" / "ms-playwright"
    if not cache_dir.exists():
        return False

    for chromium_dir in cache_dir.glob("chromium-*"):
        if (chromium_dir / "chrome-linux" / "chrome").exists():
            return True
        if (chromium_dir / "chrome-mac" / "Chromium.app").exists():
            return True
        if (chromium_dir / "chrome-linux" / "headless_shell").exists():
            return True
        if (chromium_dir / "chrome-headless-shell-linux").exists():
            return True

    for headless_dir in cache_dir.glob("chromium-headless-shell-*"):
        if any(headless_dir.iterdir()):
            return True

    return False


def install_agent_browser(ui: Any = None) -> bool:
    """Install agent-browser CLI for headless browser automation.

    Shows verbose output during installation with download progress.
    Skips verbose output if already installed.
    """
    if _is_agent_browser_ready():
        return True

    if not _run_bash_with_retry("npm install -g agent-browser"):
        return False

    if _is_agent_browser_ready():
        return True

    if ui:
        ui.status("Downloading Chromium browser...")

    try:
        process = subprocess.Popen(
            ["bash", "-c", "echo 'y' | agent-browser install --with-deps"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        if process.stdout:
            for line in process.stdout:
                line = _strip_ansi(line.rstrip())
                if line and ui:
                    if any(kw in line.lower() for kw in ["download", "install", "extract", "chromium", "%", "mb"]):
                        ui.print(f"  {line}")

        process.wait()
        return process.returncode == 0
    except Exception:
        return False


def _install_with_spinner(ui: Any, name: str, install_fn: Any, *args: Any) -> bool:
    """Run an installation function with a spinner."""
    if ui:
        with ui.spinner(f"Installing {name}..."):
            result = install_fn(*args) if args else install_fn()
        if result:
            ui.success(f"{name} installed")
        else:
            ui.warning(f"Could not install {name} - please install manually")
        return result
    else:
        return install_fn(*args) if args else install_fn()


def _install_claude_mem_with_deps(ui: Any) -> bool:
    """Install claude-mem plugin and pre-install bun dependencies."""
    if not _install_with_spinner(ui, "claude-mem plugin", install_claude_mem):
        return False

    if ui:
        ui.status("Pre-installing claude-mem dependencies...")
    if preinstall_claude_mem_deps(ui):
        if ui:
            ui.success("claude-mem dependencies ready")
    else:
        if ui:
            ui.warning("Could not pre-install claude-mem deps - will install on first start")

    return True


def _install_claude_code_with_ui(ui: Any, project_dir: Path) -> bool:
    """Install Claude Code with UI feedback."""
    if ui:
        ui.status("Installing Claude Code via native installer...")
        success, version = install_claude_code(project_dir, ui)
        if success:
            if version != "latest":
                ui.success(f"Claude Code installed (pinned to v{version})")
            else:
                ui.success("Claude Code installed (latest)")
            ui.success("Claude Code config defaults applied")
        else:
            ui.warning("Could not install Claude Code - please install manually")
        return success
    else:
        success, _ = install_claude_code(project_dir)
        return success


def _install_agent_browser_with_ui(ui: Any) -> bool:
    """Install agent-browser with UI feedback."""
    if ui:
        ui.status("Installing agent-browser...")
    if install_agent_browser(ui):
        if ui:
            ui.success("agent-browser installed")
        return True
    else:
        if ui:
            ui.warning("Could not install agent-browser - please install manually")
        return False


def _install_vexor_with_ui(ui: Any, use_local: bool) -> bool:
    """Install Vexor with UI feedback."""
    if use_local:
        if ui:
            ui.status("Installing Vexor with local embeddings...")
        if install_vexor(use_local=True, ui=ui):
            if ui:
                ui.success("Vexor installed with local embeddings")
            return True
        else:
            if ui:
                ui.warning("Could not install Vexor local - please install manually")
            return False
    else:
        return _install_with_spinner(ui, "Vexor semantic search", install_vexor)


def _install_qlty_with_ui(ui: Any, project_dir: Path) -> bool:
    """Install qlty with UI feedback."""
    qlty_result = install_qlty(project_dir)
    if qlty_result[0]:
        if ui:
            ui.success("qlty installed")
            ui.status("Downloading qlty prerequisites (linters)...")
        run_qlty_check(project_dir, ui)
        if ui:
            ui.success("qlty prerequisites ready")
        return True
    else:
        if ui:
            ui.warning("Could not install qlty - please install manually")
        return False


def _configure_firecrawl_if_enabled(ui: Any, project_dir: Path, enabled: bool) -> None:
    """Configure firecrawl MCP if enabled and API key available."""
    if not enabled:
        return

    api_key = os.environ.get("FIRECRAWL_API_KEY")
    if not api_key:
        env_file = project_dir / ".env"
        if env_file.exists():
            for line in env_file.read_text().split("\n"):
                if line.startswith("FIRECRAWL_API_KEY="):
                    api_key = line.split("=", 1)[1].strip()
                    break

    if api_key:
        _configure_firecrawl_mcp(api_key)
        if ui:
            ui.success("Firecrawl MCP configured")


class DependenciesStep(BaseStep):
    """Step that installs all required dependencies."""

    name = "dependencies"

    def check(self, ctx: InstallContext) -> bool:
        """Always returns False - dependencies should always be checked."""
        return False

    def run(self, ctx: InstallContext) -> None:
        """Install all required dependencies."""
        ui = ctx.ui
        installed: list[str] = []

        if _install_with_spinner(ui, "Node.js", install_nodejs):
            installed.append("nodejs")

        if _install_with_spinner(ui, "uv", install_uv):
            installed.append("uv")

        if ctx.enable_python:
            if _install_with_spinner(ui, "Python tools", install_python_tools):
                installed.append("python_tools")

        if _install_claude_code_with_ui(ui, ctx.project_dir):
            installed.append("claude_code")

        if ctx.enable_typescript:
            if _install_with_spinner(ui, "TypeScript LSP", install_typescript_lsp):
                installed.append("typescript_lsp")

        if ctx.enable_python:
            if _install_with_spinner(ui, "Pyright LSP", install_pyright_lsp):
                installed.append("pyright_lsp")

        if _install_claude_mem_with_deps(ui):
            installed.append("claude_mem")

        if _install_with_spinner(ui, "Context7 plugin", install_context7):
            installed.append("context7")

        if _install_with_spinner(ui, "mcp-cli", install_mcp_cli):
            installed.append("mcp_cli")

        if ctx.enable_agent_browser:
            if _install_agent_browser_with_ui(ui):
                installed.append("agent_browser")

        if _install_vexor_with_ui(ui, use_local=not ctx.enable_openai_embeddings):
            installed.append("vexor")

        if _install_qlty_with_ui(ui, ctx.project_dir):
            installed.append("qlty")

        _configure_firecrawl_if_enabled(ui, ctx.project_dir, ctx.enable_firecrawl)

        ctx.config["installed_dependencies"] = installed

    def rollback(self, ctx: InstallContext) -> None:
        """Dependencies are not rolled back (would be too disruptive)."""
        pass
