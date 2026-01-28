"""Dependencies step - installs required tools and packages."""

from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Any

from installer.context import InstallContext
from installer.platform_utils import command_exists
from installer.steps.base import BaseStep

MAX_RETRIES = 3
RETRY_DELAY = 2


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


def _remove_native_claude_binaries() -> None:
    """Remove native-installed Claude Code to avoid conflicts with npm install."""
    import shutil

    native_bin = Path.home() / ".local" / "bin" / "claude"
    native_data = Path.home() / ".local" / "share" / "claude"

    if native_bin.exists() or native_bin.is_symlink():
        try:
            native_bin.unlink()
        except Exception:
            pass

    if native_data.exists():
        shutil.rmtree(native_data, ignore_errors=True)


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


def _patch_claude_settings(settings_updates: dict) -> bool:
    """Patch ~/.claude/settings.json with the given settings updates.

    Creates the file if it doesn't exist. Merges updates with existing settings.
    """
    import json

    settings_dir = Path.home() / ".claude"
    settings_dir.mkdir(parents=True, exist_ok=True)
    settings_path = settings_dir / "settings.json"

    try:
        if settings_path.exists():
            settings = json.loads(settings_path.read_text())
        else:
            settings = {}

        settings.update(settings_updates)
        settings_path.write_text(json.dumps(settings, indent=2) + "\n")
        return True
    except Exception:
        return False


def _configure_claude_defaults() -> bool:
    """Configure Claude Code with recommended defaults after installation."""
    config_ok = _patch_claude_config(
        {
            "installMethod": "npm",
            "theme": "dark-ansi",
            "verbose": True,
            "autoCompactEnabled": False,
            "autoConnectIde": True,
            "autoUpdates": False,
            "lspRecommendationDisabled": True,
            "showTurnDuration": False,
            "terminalProgressBarEnabled": True,
        }
    )
    settings_ok = _patch_claude_settings(
        {
            "attribution": {"commit": "", "pr": ""},
            "respectGitignore": False,
            "cleanupPeriodDays": 7,
        }
    )
    return config_ok and settings_ok


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


def install_claude_code(project_dir: Path, ui: Any = None) -> tuple[bool, str]:
    """Install/upgrade Claude Code CLI via npm and configure defaults."""
    _remove_native_claude_binaries()

    forced_version = _get_forced_claude_version(project_dir)
    version = forced_version if forced_version else "latest"

    if version != "latest":
        npm_cmd = f"npm install -g @anthropic-ai/claude-code@{version}"
        if ui:
            ui.status(f"Installing Claude Code v{version}...")
    else:
        npm_cmd = "npm install -g @anthropic-ai/claude-code"
        if ui:
            ui.status("Installing Claude Code...")

    if not _run_bash_with_retry(npm_cmd):
        return False, version

    _configure_claude_defaults()
    return True, version


def _migrate_legacy_plugins(ui: Any = None) -> None:
    """Remove legacy plugins and marketplaces installed by previous CCP versions.

    MCP servers are now defined in plugin/.mcp.json, so we clean up:
    - Context7 from official marketplace
    - claude-mem from thedotmack marketplace
    - claude-mem from customable (maxritter) marketplace
    - LSP plugins (basedpyright, typescript-lsp, gopls) from claude-code-lsps
    - thedotmack marketplace
    - customable marketplace

    Uses 'claude plugin uninstall' CLI for proper cleanup.
    """
    import json
    import shutil
    import subprocess

    removed_plugins: list[str] = []
    removed_marketplaces: list[str] = []

    plugins_to_remove = [
        "context7",
        "claude-mem",
        "basedpyright",
        "typescript-lsp",
        "vtsls",
        "gopls",
        "pyright-lsp",
        "gopls-lsp",
    ]

    for plugin_name in plugins_to_remove:
        try:
            result = subprocess.run(
                ["claude", "plugin", "uninstall", plugin_name],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                removed_plugins.append(plugin_name)
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            pass

    cache_dir = Path.home() / ".claude" / "plugins" / "cache"
    marketplaces_to_clean = ["thedotmack", "customable", "claude-code-lsps"]
    for marketplace in marketplaces_to_clean:
        marketplace_cache = cache_dir / marketplace
        if marketplace_cache.exists():
            shutil.rmtree(marketplace_cache, ignore_errors=True)

    marketplaces_path = Path.home() / ".claude" / "plugins" / "known_marketplaces.json"
    if marketplaces_path.exists():
        try:
            data = json.loads(marketplaces_path.read_text())
            modified = False
            for marketplace in ["thedotmack", "customable", "claude-code-lsps"]:
                if marketplace in data:
                    del data[marketplace]
                    removed_marketplaces.append(marketplace)
                    modified = True
            if modified:
                marketplaces_path.write_text(json.dumps(data, indent=2))
        except (json.JSONDecodeError, OSError):
            pass

    marketplaces_dir = Path.home() / ".claude" / "plugins" / "marketplaces"
    for marketplace in ["thedotmack", "customable", "claude-code-lsps"]:
        marketplace_dir = marketplaces_dir / marketplace
        if marketplace_dir.exists():
            shutil.rmtree(marketplace_dir, ignore_errors=True)

    if ui and (removed_plugins or removed_marketplaces):
        total = len(removed_plugins) + len(removed_marketplaces)
        ui.success(f"Cleaned up {total} legacy plugins")


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


def _is_vexor_local_model_installed() -> bool:
    """Check if the local embedding model is already downloaded."""
    cache_dirs = [
        Path.home() / ".cache" / "huggingface" / "hub",
        Path.home() / ".cache" / "torch" / "sentence_transformers",
    ]
    model_name = "intfloat--multilingual-e5-small"

    for cache_dir in cache_dirs:
        if cache_dir.exists():
            for model_dir in cache_dir.glob(f"*{model_name}*"):
                if model_dir.is_dir():
                    return True
            for model_dir in cache_dir.glob(f"models--{model_name}*"):
                if model_dir.is_dir():
                    return True
    return False


def _setup_vexor_local_model(ui: Any = None) -> bool:
    """Download and setup the local embedding model for Vexor."""
    if _is_vexor_local_model_installed():
        return True

    try:
        if ui:
            with ui.spinner("Downloading local embedding model..."):
                result = subprocess.run(
                    ["vexor", "local", "--setup", "--model", "intfloat/multilingual-e5-small"],
                    capture_output=True,
                    text=True,
                )
            return result.returncode == 0
        else:
            result = subprocess.run(
                ["vexor", "local", "--setup", "--model", "intfloat/multilingual-e5-small"],
                capture_output=True,
                text=True,
            )
            return result.returncode == 0
    except Exception:
        return False


def install_vexor(use_local: bool = False, ui: Any = None) -> bool:
    """Install Vexor semantic search tool and configure defaults."""
    if use_local:
        if command_exists("vexor") and _is_vexor_local_model_installed():
            _configure_vexor_local()
            return True
        if not command_exists("vexor"):
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


def install_mcp_cli() -> bool:
    """Install mcp-cli via bun for MCP server interaction."""
    if not command_exists("bun"):
        return False

    return _run_bash_with_retry("bun install -g https://github.com/philschmid/mcp-cli")


def _is_vtsls_installed() -> bool:
    """Check if vtsls is already installed globally."""
    try:
        result = subprocess.run(
            ["npm", "list", "-g", "@vtsls/language-server"],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0 and "@vtsls/language-server" in result.stdout
    except Exception:
        return False


def install_typescript_lsp() -> bool:
    """Install TypeScript language server and compiler globally."""
    if _is_vtsls_installed():
        return True
    return _run_bash_with_retry("npm install -g @vtsls/language-server typescript")


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

    try:
        if ui:
            with ui.spinner("Downloading Chromium browser..."):
                result = subprocess.run(
                    ["bash", "-c", "echo 'y' | agent-browser install --with-deps"],
                    capture_output=True,
                    text=True,
                )
            return result.returncode == 0
        else:
            result = subprocess.run(
                ["bash", "-c", "echo 'y' | agent-browser install --with-deps"],
                capture_output=True,
                text=True,
            )
            return result.returncode == 0
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


def _install_plugin_dependencies(project_dir: Path, ui: Any = None) -> bool:
    """Install plugin dependencies by running bun/npm install in the plugin folder.

    This installs all Node.js dependencies defined in plugin/package.json,
    which includes runtime dependencies for MCP servers and hooks.
    """
    plugin_dir = project_dir / ".claude" / "ccp"

    if not plugin_dir.exists():
        if ui:
            ui.warning("Plugin directory not found - skipping plugin dependencies")
        return False

    package_json = plugin_dir / "package.json"
    if not package_json.exists():
        if ui:
            ui.warning("No package.json in plugin directory - skipping")
        return False

    success = False

    if command_exists("bun"):
        if _run_bash_with_retry("bun install", cwd=plugin_dir):
            success = True

    return success


def _setup_claude_mem(ui: Any) -> bool:
    """Migrate legacy plugins for claude-mem.

    Claude-mem MCP server is now defined in plugin/.mcp.json.
    This function removes any legacy plugin installations.
    """
    _migrate_legacy_plugins(ui)
    if ui:
        ui.success("claude-mem legacy plugins cleaned")
    return True


def _install_claude_code_with_ui(ui: Any, project_dir: Path) -> bool:
    """Install Claude Code with UI feedback."""
    if ui:
        ui.status("Installing Claude Code via npm...")
        success, version = install_claude_code(project_dir, ui)
        if success:
            if version != "latest":
                ui.success(f"Claude Code installed (pinned to v{version})")
                ui.info(f"Version {version} is the last stable release tested with CCP")
                ui.info("To change: edit FORCE_CLAUDE_VERSION in .claude/settings.local.json")
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


def _install_vexor_with_ui(ui: Any) -> bool:
    """Install Vexor with local embeddings (GPU auto-detected)."""
    from installer.platform_utils import has_nvidia_gpu

    use_cuda = has_nvidia_gpu()
    mode_str = "CUDA" if use_cuda else "CPU"

    if ui:
        ui.status(f"Installing Vexor with local embeddings ({mode_str})...")

    if install_vexor(use_local=True, ui=ui):
        if ui:
            ui.success(f"Vexor installed with local embeddings ({mode_str})")
        return True
    else:
        if ui:
            ui.warning("Could not install Vexor - please install manually")
        return False


def _clean_mcp_servers_from_claude_config(ui: Any) -> None:
    """Remove mcpServers section from ~/.claude.json (now in plugin/.mcp.json)."""
    import json

    claude_config_path = Path.home() / ".claude.json"

    try:
        if not claude_config_path.exists():
            return

        config = json.loads(claude_config_path.read_text())

        if "mcpServers" not in config:
            return

        del config["mcpServers"]
        claude_config_path.write_text(json.dumps(config, indent=2) + "\n")

        if ui:
            ui.success("Cleaned mcpServers from ~/.claude.json (now in plugin/.mcp.json)")
    except Exception as e:
        if ui:
            ui.warning(f"Could not clean mcpServers from config: {e}")


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

        if _setup_claude_mem(ui):
            installed.append("claude_mem")

        if _install_with_spinner(ui, "Plugin dependencies", _install_plugin_dependencies, ctx.project_dir, ui):
            installed.append("plugin_deps")

        if _install_with_spinner(ui, "mcp-cli", install_mcp_cli):
            installed.append("mcp_cli")

        if _install_with_spinner(ui, "vtsls (TypeScript LSP server)", install_typescript_lsp):
            installed.append("typescript_lsp")

        if ctx.enable_agent_browser:
            if _install_agent_browser_with_ui(ui):
                installed.append("agent_browser")

        if _install_vexor_with_ui(ui):
            installed.append("vexor")

        _clean_mcp_servers_from_claude_config(ui)

        ctx.config["installed_dependencies"] = installed
