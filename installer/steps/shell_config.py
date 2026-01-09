"""Shell config step - configures shell with ccp alias, fzf, dotenv, and zsh."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from installer.platform_utils import get_shell_config_files, is_in_devcontainer
from installer.steps.base import BaseStep

if TYPE_CHECKING:
    from installer.context import InstallContext

CCP_ALIAS_MARKER = "# Claude CodePro alias"
FZF_MARKER = "source <(fzf --zsh)"
DOTENV_MARKER = "ZSH_DOTENV_PROMPT"
QLTY_PATH_MARKER = "# qlty PATH"


def get_alias_line(shell_type: str) -> str:
    """Get the alias line for the given shell type.

    Creates an alias that:
    1. If current dir is CCP project (.claude/rules/ exists) → use it
    2. If in devcontainer (/workspaces exists) → find CCP project there
    3. Otherwise → show error

    The alias:
    - Uses nvm to set Node.js 22
    - Clears screen
    - Runs Claude via wrapper.py for /spec command support
    - Falls back to direct claude if wrapper not found

    Note: Rules are now natively loaded by Claude Code from .claude/rules/*.md
    """
    claude_cmd = (
        "if [ -f .claude/scripts/wrapper.py ]; then "
        "dotenvx run -- python3 .claude/scripts/wrapper.py; "
        "else dotenvx run -- claude; fi"
    )
    claude_cmd_fish = (
        "if test -f .claude/scripts/wrapper.py; "
        "dotenvx run -- python3 .claude/scripts/wrapper.py; "
        "else; dotenvx run -- claude; end"
    )

    if shell_type == "fish":
        return (
            f"{CCP_ALIAS_MARKER}\n"
            "alias ccp='"
            "if test -d .claude/rules; "
            f"nvm use 22; and clear; and {claude_cmd_fish}; "
            "else if test -d /workspaces; "
            'set ccp_dir ""; for d in /workspaces/*/; test -d "$d.claude/rules"; and set ccp_dir "$d"; and break; end; '
            f'if test -n "$ccp_dir"; cd "$ccp_dir"; and nvm use 22; and clear; and {claude_cmd_fish}; '
            'else; echo "Error: No CCP project found in /workspaces"; end; '
            "else; "
            'echo "Error: Not a Claude CodePro project. Please cd to a CCP-enabled project first."; '
            "end'"
        )
    else:
        return (
            f"{CCP_ALIAS_MARKER}\n"
            "alias ccp='"
            "if [ -d .claude/rules ]; then "
            f"nvm use 22 && clear && {claude_cmd}; "
            "elif [ -d /workspaces ]; then "
            'ccp_dir=""; for d in /workspaces/*/; do [ -d "$d.claude/rules" ] && ccp_dir="$d" && break; done; '
            f'if [ -n "$ccp_dir" ]; then cd "$ccp_dir" && nvm use 22 && clear && {claude_cmd}; '
            'else echo "Error: No CCP project found in /workspaces"; fi; '
            "else "
            'echo "Error: Not a Claude CodePro project. Please cd to a CCP-enabled project first."; '
            "fi'"
        )


def alias_exists_in_file(config_file: Path) -> bool:
    """Check if ccp alias already exists in config file."""
    if not config_file.exists():
        return False
    content = config_file.read_text()
    return "alias ccp" in content or CCP_ALIAS_MARKER in content


def remove_old_alias(config_file: Path) -> bool:
    """Remove old ccp alias from config file to allow clean update."""
    if not config_file.exists():
        return False

    content = config_file.read_text()
    if CCP_ALIAS_MARKER not in content and "alias ccp" not in content:
        return False

    lines = content.split("\n")
    new_lines = []
    skip_next = False

    for line in lines:
        if CCP_ALIAS_MARKER in line:
            skip_next = True
            continue
        if skip_next and ("alias ccp" in line or line.strip().startswith("if [")):
            if line.rstrip().endswith("'"):
                skip_next = False
            continue
        skip_next = False
        new_lines.append(line)

    final_lines = []
    for line in new_lines:
        if line.strip().startswith("alias ccp="):
            continue
        final_lines.append(line)

    config_file.write_text("\n".join(final_lines))
    return True


def _configure_zsh_fzf(zshrc: Path, ui) -> bool:
    """Configure fzf in zshrc (idempotent)."""
    if not zshrc.exists():
        return False

    content = zshrc.read_text()
    if FZF_MARKER in content:
        if ui:
            ui.info("fzf already configured")
        return False

    with open(zshrc, "a") as f:
        f.write(f"\n{FZF_MARKER}\n")
    if ui:
        ui.success("Added fzf configuration")
    return True


def _configure_zsh_dotenv(zshrc: Path, ui) -> bool:
    """Configure dotenv plugin in zshrc (idempotent)."""
    if not zshrc.exists():
        return False

    content = zshrc.read_text()
    modified = False

    if "plugins=(" in content and "dotenv" not in content:
        content = content.replace("plugins=(", "plugins=(dotenv ")
        zshrc.write_text(content)
        if ui:
            ui.success("Added dotenv plugin")
        modified = True
    elif "dotenv" in content:
        if ui:
            ui.info("dotenv plugin already configured")

    if DOTENV_MARKER not in content:
        content = zshrc.read_text()
        dotenv_setting = "# Auto-load .env files without prompting\nexport ZSH_DOTENV_PROMPT=false\n\n"

        if "source $ZSH/oh-my-zsh.sh" in content:
            content = content.replace("source $ZSH/oh-my-zsh.sh", dotenv_setting + "source $ZSH/oh-my-zsh.sh")
            zshrc.write_text(content)
        else:
            with open(zshrc, "a") as f:
                f.write(f"\n{dotenv_setting}")

        if ui:
            ui.success("Added ZSH_DOTENV_PROMPT setting")
        modified = True
    elif ui:
        ui.info("ZSH_DOTENV_PROMPT already configured")

    return modified


def _configure_qlty_path(config_file: Path, ui, quiet: bool = False) -> bool:
    """Add qlty to PATH in shell config (idempotent)."""
    if not config_file.exists():
        return False

    content = config_file.read_text()
    if QLTY_PATH_MARKER in content or ".qlty/bin" in content:
        if ui and not quiet:
            ui.info(f"qlty PATH already configured in {config_file.name}")
        return False

    if "fish" in config_file.name:
        qlty_path_line = f"\n{QLTY_PATH_MARKER}\nset -gx PATH $HOME/.qlty/bin $PATH\n"
    else:
        qlty_path_line = f'\n{QLTY_PATH_MARKER}\nexport PATH="$HOME/.qlty/bin:$PATH"\n'

    with open(config_file, "a") as f:
        f.write(qlty_path_line)

    if ui:
        ui.success(f"Added qlty to PATH in {config_file.name}")
    return True


def _set_zsh_default_shell(ui) -> bool:
    """Set zsh as default shell if not already (idempotent)."""
    import os

    current_shell = os.environ.get("SHELL", "")
    if current_shell.endswith("/zsh"):
        if ui:
            ui.info("zsh already default shell")
        return False

    zsh_path = subprocess.run(["which", "zsh"], capture_output=True, text=True).stdout.strip()

    if not zsh_path:
        if ui:
            ui.warning("zsh not found, skipping default shell change")
        return False

    try:
        subprocess.run(["chsh", "-s", zsh_path], check=True, capture_output=True)
        if ui:
            ui.success("Set zsh as default shell")
        return True
    except subprocess.CalledProcessError:
        if ui:
            ui.warning("Could not change default shell (may need sudo)")
        return False


class ShellConfigStep(BaseStep):
    """Step that configures shell with ccp alias, fzf, dotenv, and zsh."""

    name = "shell_config"

    def check(self, ctx: InstallContext) -> bool:
        """Always return False to ensure alias is updated on every install."""
        return False

    def run(self, ctx: InstallContext) -> None:
        """Configure shell with alias, fzf, dotenv, and zsh settings."""
        ui = ctx.ui
        config_files = get_shell_config_files()
        modified_files: list[str] = []

        if is_in_devcontainer():
            zshrc = Path.home() / ".zshrc"
            if zshrc.exists():
                if ui:
                    ui.status("Configuring zsh environment...")
                _configure_zsh_fzf(zshrc, ui)
                _configure_zsh_dotenv(zshrc, ui)
                _set_zsh_default_shell(ui)

        if ui:
            ui.status("Configuring qlty PATH...")
        for config_file in config_files:
            _configure_qlty_path(config_file, ui, quiet=True)

        if ui:
            ui.status("Configuring shell alias...")

        for config_file in config_files:
            if not config_file.exists():
                continue

            alias_existed = alias_exists_in_file(config_file)
            if alias_existed:
                remove_old_alias(config_file)
                if ui:
                    ui.info(f"Updating alias in {config_file.name}")

            shell_type = "fish" if "fish" in config_file.name else "bash"
            alias_line = get_alias_line(shell_type)

            try:
                with open(config_file, "a") as f:
                    f.write(f"\n{alias_line}\n")
                modified_files.append(str(config_file))
                if ui:
                    if alias_existed:
                        ui.success(f"Updated alias in {config_file.name}")
                    else:
                        ui.success(f"Added alias to {config_file.name}")
            except (OSError, IOError) as e:
                if ui:
                    ui.warning(f"Could not modify {config_file.name}: {e}")

        ctx.config["modified_shell_configs"] = modified_files

        if ui and modified_files:
            ui.print()
            ui.status("To use the 'ccp' command, reload your shell:")
            ui.print("  source ~/.bashrc  # or ~/.zshrc")

    def rollback(self, ctx: InstallContext) -> None:
        """Remove alias from modified config files."""
        modified_files = ctx.config.get("modified_shell_configs", [])

        for file_path in modified_files:
            config_file = Path(file_path)
            if not config_file.exists():
                continue

            try:
                content = config_file.read_text()
                lines = content.split("\n")
                new_lines = []
                skip_next = False

                for line in lines:
                    if CCP_ALIAS_MARKER in line:
                        skip_next = True
                        continue
                    if skip_next and line.startswith("alias ccp"):
                        skip_next = False
                        continue
                    skip_next = False
                    new_lines.append(line)

                config_file.write_text("\n".join(new_lines))
            except (OSError, IOError):
                pass
