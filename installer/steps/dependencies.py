"""Dependencies step - installs required tools and packages."""

from __future__ import annotations

import os
import re
import subprocess
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from installer.platform_utils import command_exists, has_nvidia_gpu
from installer.steps.base import BaseStep

if TYPE_CHECKING:
    from installer.context import InstallContext

MAX_RETRIES = 3
RETRY_DELAY = 2

ANSI_ESCAPE_PATTERN = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]|\x1b\].*?\x07")


def _strip_ansi(text: str) -> str:
    """Strip ANSI escape codes from text."""
    return ANSI_ESCAPE_PATTERN.sub("", text)


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


def _remove_native_claude_binaries() -> None:
    """Remove native Claude Code binaries to avoid conflicts with npm install."""
    native_bin = Path.home() / ".local" / "bin" / "claude"
    native_data = Path.home() / ".local" / "share" / "claude"

    if native_bin.exists():
        native_bin.unlink()
    if native_data.exists():
        import shutil

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


def _configure_claude_defaults() -> bool:
    """Configure Claude Code with recommended defaults after installation."""
    return _patch_claude_config(
        {
            "installMethod": "npm-global",
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


def install_claude_code(project_dir: Path) -> tuple[bool, str]:
    """Install/upgrade Claude Code CLI via npm and configure defaults.

    Returns (success, version_installed).
    """
    _remove_native_claude_binaries()

    forced_version = _get_forced_claude_version(project_dir)
    version = forced_version if forced_version else "latest"

    if not _run_bash_with_retry(f"npm install -g @anthropic-ai/claude-code@{version}"):
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


def _get_vexor_pip_path() -> Path | None:
    """Get path to pip in vexor's uv tool environment."""
    vexor_pip = Path.home() / ".local" / "share" / "uv" / "tools" / "vexor" / "bin" / "pip"
    return vexor_pip if vexor_pip.exists() else None


def _is_vexor_in_project_venv() -> bool:
    """Check if vexor is installed in the project's .venv (not as uv tool)."""
    cwd = Path.cwd()
    venv_paths = [cwd / ".venv", cwd / "venv"]
    for venv_path in venv_paths:
        vexor_bin = venv_path / "bin" / "vexor"
        if vexor_bin.exists():
            return True
    return False


def _upgrade_venv_vexor_cuda() -> bool:
    """Upgrade vexor in project .venv with CUDA extras and fix onnxruntime conflict."""
    try:
        subprocess.run(
            ["uv", "pip", "install", "vexor[local-cuda]"],
            check=True,
            capture_output=True,
        )
        result = subprocess.run(
            ["uv", "pip", "list"],
            capture_output=True,
            text=True,
        )
        packages = result.stdout.lower()
        if "onnxruntime-gpu" in packages and "onnxruntime " in packages:
            subprocess.run(
                ["uv", "pip", "uninstall", "onnxruntime"],
                capture_output=True,
            )
        return True
    except subprocess.CalledProcessError:
        return False


def _fix_vexor_onnxruntime_conflict() -> bool:
    """Remove CPU-only onnxruntime from vexor to fix CUDA provider conflict."""
    vexor_pip = _get_vexor_pip_path()
    if not vexor_pip:
        return False

    try:
        result = subprocess.run(
            [str(vexor_pip), "list"],
            capture_output=True,
            text=True,
        )
        packages = result.stdout.lower()

        if "onnxruntime-gpu" in packages and "onnxruntime " in packages:
            subprocess.run(
                [str(vexor_pip), "uninstall", "-y", "onnxruntime"],
                capture_output=True,
            )
        return True
    except subprocess.SubprocessError:
        return False


def _configure_vexor_defaults(
    provider_mode: str = "cpu",
    api_key: str | None = None,
) -> bool:
    """Configure Vexor with defaults based on provider mode.

    Args:
        provider_mode: One of "cuda", "cpu", or "openai"
        api_key: OpenAI API key (used if provider_mode is "openai")
    """
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
                "batch_size": 64,
                "embed_concurrency": 4,
                "extract_concurrency": 4,
                "extract_backend": "auto",
                "auto_index": True,
                "rerank": "bm25",
            }
        )

        if provider_mode == "cuda":
            config.update(
                {
                    "provider": "local",
                    "local_cuda": True,
                    "model": "intfloat/multilingual-e5-small",
                }
            )
            config.pop("api_key", None)
        elif provider_mode == "openai":
            config.update(
                {
                    "provider": "openai",
                    "local_cuda": False,
                    "model": "text-embedding-3-small",
                }
            )
            if api_key:
                config["api_key"] = api_key
        else:
            config.update(
                {
                    "provider": "local",
                    "local_cuda": False,
                    "model": "intfloat/multilingual-e5-small",
                }
            )
            config.pop("api_key", None)

        config_path.write_text(json.dumps(config, indent=2) + "\n")
        return True
    except Exception:
        return False


def install_vexor(
    provider_mode: str | None = None,
    api_key: str | None = None,
) -> bool:
    """Install Vexor semantic search tool and configure defaults.

    Args:
        provider_mode: One of "cuda", "cpu", or "openai". If None, auto-detects based on GPU.
        api_key: OpenAI API key (used if provider_mode is "openai")
    """
    if provider_mode is None:
        gpu_available = has_nvidia_gpu()
        provider_mode = "cuda" if gpu_available else "cpu"

    if _is_vexor_in_project_venv():
        if provider_mode == "cuda":
            _upgrade_venv_vexor_cuda()
        _configure_vexor_defaults(provider_mode, api_key)
        return True

    if command_exists("vexor"):
        if provider_mode == "cuda":
            _fix_vexor_onnxruntime_conflict()
        _configure_vexor_defaults(provider_mode, api_key)
        return True

    try:
        if provider_mode == "cuda":
            package = "vexor[local-cuda]"
        elif provider_mode == "openai":
            package = "vexor"
        else:
            package = "vexor[local]"

        subprocess.run(
            ["uv", "tool", "install", package],
            check=True,
            capture_output=True,
        )

        if provider_mode == "cuda":
            _fix_vexor_onnxruntime_conflict()

        _configure_vexor_defaults(provider_mode, api_key)
        return True
    except subprocess.CalledProcessError:
        return False


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

    Shows verbose output during installation since it takes 1-2 minutes.
    Skips verbose output if already installed.
    """
    if _is_agent_browser_ready():
        return True

    if not _run_bash_with_retry("npm install -g agent-browser"):
        return False

    if _is_agent_browser_ready():
        return True

    if ui:
        ui.print("  [dim]Downloading Chromium browser (this may take 1-2 minutes)...[/dim]")

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

        if ui:
            with ui.spinner("Installing Claude Code..."):
                success, version = install_claude_code(ctx.project_dir)
            if success:
                installed.append("claude_code")
                if version != "latest":
                    ui.success(f"Claude Code installed (pinned to v{version})")
                else:
                    ui.success("Claude Code installed (latest)")
                ui.success("Claude Code config defaults applied")
            else:
                ui.warning("Could not install Claude Code - please install manually")
        else:
            success, _ = install_claude_code(ctx.project_dir)
            if success:
                installed.append("claude_code")

        if ctx.enable_typescript:
            if _install_with_spinner(ui, "TypeScript LSP", install_typescript_lsp):
                installed.append("typescript_lsp")

        if ctx.enable_python:
            if _install_with_spinner(ui, "Pyright LSP", install_pyright_lsp):
                installed.append("pyright_lsp")

        if _install_with_spinner(ui, "claude-mem plugin", install_claude_mem):
            installed.append("claude_mem")

        if _install_with_spinner(ui, "Context7 plugin", install_context7):
            installed.append("context7")

        if _install_with_spinner(ui, "mcp-cli", install_mcp_cli):
            installed.append("mcp_cli")

        if ctx.enable_agent_browser:
            if ui:
                ui.status("Installing agent-browser...")
            if install_agent_browser(ui):
                installed.append("agent_browser")
                if ui:
                    ui.success("agent-browser installed")
            else:
                if ui:
                    ui.warning("Could not install agent-browser - please install manually")

        gpu_info = has_nvidia_gpu(verbose=True)
        gpu_available = gpu_info["detected"] if isinstance(gpu_info, dict) else gpu_info

        if gpu_available:
            provider_mode = "cuda"
            api_key = None
            if ui:
                method = gpu_info.get("method", "unknown") if isinstance(gpu_info, dict) else "unknown"
                ui.status(f"NVIDIA GPU detected via {method}")
        else:
            if ui:
                ui.info("CUDA/GPU not available.")

            api_key = os.environ.get("OPENAI_API_KEY")

            if ui and not ctx.non_interactive:
                use_openai = ui.confirm(
                    "Use OpenAI API for embeddings instead of CPU?",
                    default=ctx.enable_openai_embeddings,
                )
                provider_mode = "openai" if use_openai else "cpu"
            else:
                provider_mode = "openai" if ctx.enable_openai_embeddings else "cpu"

            if ui:
                if provider_mode == "openai":
                    ui.info("Using OpenAI embeddings")
                else:
                    ui.info("Using CPU for local embeddings")

        if _install_with_spinner(
            ui,
            "Vexor semantic search",
            install_vexor,
            provider_mode,
            api_key if provider_mode == "openai" else None,
        ):
            installed.append("vexor")

        qlty_result = install_qlty(ctx.project_dir)
        if qlty_result[0]:
            installed.append("qlty")
            if ui:
                ui.success("qlty installed")
                ui.status("Downloading qlty prerequisites (linters)...")
            run_qlty_check(ctx.project_dir, ui)
            if ui:
                ui.success("qlty prerequisites ready")
        else:
            if ui:
                ui.warning("Could not install qlty - please install manually")

        if ctx.enable_firecrawl:
            api_key = os.environ.get("FIRECRAWL_API_KEY")
            if not api_key:
                env_file = ctx.project_dir / ".env"
                if env_file.exists():
                    for line in env_file.read_text().split("\n"):
                        if line.startswith("FIRECRAWL_API_KEY="):
                            api_key = line.split("=", 1)[1].strip()
                            break

            if api_key:
                _configure_firecrawl_mcp(api_key)
                if ui:
                    ui.success("Firecrawl MCP configured")

        ctx.config["installed_dependencies"] = installed

    def rollback(self, ctx: InstallContext) -> None:
        """Dependencies are not rolled back (would be too disruptive)."""
        pass
