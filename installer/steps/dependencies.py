"""Dependencies step - installs required tools and packages."""

from __future__ import annotations

import re
import subprocess
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from installer.platform_utils import command_exists
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
    tools = ["ruff", "mypy", "basedpyright"]

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


def _configure_firecrawl_mcp() -> bool:
    """Add firecrawl MCP server to ~/.claude.json if not already present.

    Only adds the firecrawl server - does not alter other MCP servers.
    """
    import json

    config_path = Path.home() / ".claude.json"

    firecrawl_config = {
        "command": "npx",
        "args": ["-y", "firecrawl-mcp"],
        "env": {"FIRECRAWL_API_KEY": "${FIRECRAWL_API_KEY}"},
    }

    try:
        if config_path.exists():
            config = json.loads(config_path.read_text())
        else:
            config = {}

        if "mcpServers" not in config:
            config["mcpServers"] = {}

        if "firecrawl" not in config["mcpServers"]:
            config["mcpServers"]["firecrawl"] = firecrawl_config
            config_path.write_text(json.dumps(config, indent=2) + "\n")

        return True
    except Exception:
        return False


def install_claude_code() -> bool:
    """Install/upgrade Claude Code CLI via npm and configure defaults."""
    _remove_native_claude_binaries()

    if not _run_bash_with_retry("npm install -g @anthropic-ai/claude-code@latest"):
        return False

    _configure_claude_defaults()
    _configure_firecrawl_mcp()
    return True


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


def install_dotenvx() -> bool:
    """Install dotenvx (environment variable management) via native shell installer."""
    if command_exists("dotenvx"):
        return True

    return _run_bash_with_retry("curl -sfS https://dotenvx.sh | sh")


def _ensure_official_marketplace() -> bool:
    """Ensure official Claude plugins marketplace is installed."""
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

    if not _ensure_official_marketplace():
        return False

    return _run_bash_with_retry("claude plugin install typescript-lsp")


def install_pyright_lsp() -> bool:
    """Install pyright language server and plugin via npm and claude plugin."""
    if not _run_bash_with_retry("npm install -g pyright"):
        return False

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
                "CLAUDE_MEM_MODEL": "opus",
            }
        )
        settings_path.write_text(json.dumps(settings, indent=2) + "\n")
        return True
    except Exception:
        return False


def _configure_vexor_defaults() -> bool:
    """Configure Vexor with recommended defaults for semantic search."""
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


def install_vexor() -> bool:
    """Install Vexor semantic search tool and configure defaults."""
    if command_exists("vexor"):
        _configure_vexor_defaults()
        return True

    try:
        subprocess.run(
            ["uv", "tool", "install", "vexor"],
            check=True,
            capture_output=True,
        )
        _configure_vexor_defaults()
        return True
    except subprocess.CalledProcessError:
        return False


def _ensure_maxritter_marketplace() -> bool:
    """Ensure claude-mem marketplace points to maxritter repo.

    Checks known_marketplaces.json for thedotmack entry. If it exists
    but doesn't contain 'maxritter' in the URL, removes and re-adds it.
    """
    import json

    marketplaces_path = Path.home() / ".claude" / "plugins" / "known_marketplaces.json"

    if marketplaces_path.exists():
        try:
            data = json.loads(marketplaces_path.read_text())
            thedotmack = data.get("thedotmack", {})
            source = thedotmack.get("source", {})
            url = source.get("url", "")

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
    if not _ensure_maxritter_marketplace():
        return False

    if not _run_bash_with_retry("claude plugin install claude-mem"):
        return False

    _configure_claude_mem_defaults()
    return True


def install_context7() -> bool:
    """Install context7 plugin via claude plugin."""
    return _run_bash_with_retry("claude plugin install context7")


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

        if ctx.install_python:
            if _install_with_spinner(ui, "uv", install_uv):
                installed.append("uv")

            if _install_with_spinner(ui, "Python tools", install_python_tools):
                installed.append("python_tools")

        if _install_with_spinner(ui, "Claude Code", install_claude_code):
            installed.append("claude_code")
            if ui:
                ui.success("Claude Code config defaults applied")

        if ctx.install_typescript:
            if _install_with_spinner(ui, "TypeScript LSP", install_typescript_lsp):
                installed.append("typescript_lsp")

        if ctx.install_python:
            if _install_with_spinner(ui, "Pyright LSP", install_pyright_lsp):
                installed.append("pyright_lsp")

        if _install_with_spinner(ui, "claude-mem plugin", install_claude_mem):
            installed.append("claude_mem")

        if _install_with_spinner(ui, "Context7 plugin", install_context7):
            installed.append("context7")

        if _install_with_spinner(ui, "Vexor semantic search", install_vexor):
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

        if _install_with_spinner(ui, "dotenvx", install_dotenvx):
            installed.append("dotenvx")

        ctx.config["installed_dependencies"] = installed

    def rollback(self, ctx: InstallContext) -> None:
        """Dependencies are not rolled back (would be too disruptive)."""
        pass
