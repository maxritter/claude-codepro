"""Shell config step - configures shell with ccp alias, fzf, dotenv, and zsh."""

from __future__ import annotations

import subprocess
from pathlib import Path

from installer.context import InstallContext
from installer.platform_utils import get_shell_config_files, is_in_devcontainer
from installer.steps.base import BaseStep

CCP_ALIAS_MARKER = "# Claude CodePro alias"
FZF_MARKER = "source <(fzf --zsh)"
DOTENV_MARKER = "ZSH_DOTENV_PROMPT"
QLTY_PATH_MARKER = "# qlty PATH"
BUN_PATH_MARKER = "# bun PATH"


def get_alias_line(shell_type: str) -> str:
    """Get the function/alias line for the given shell type.

    Creates a function that:
    1. If current dir is CCP project (.claude/bin/ccp exists) → use it
    2. If in devcontainer (/workspaces exists) → find CCP project there
    3. Otherwise → show error

    Uses a function (not alias) to properly forward arguments like 'ccp activate KEY'.
    """
    if shell_type == "fish":
        return (
            f"{CCP_ALIAS_MARKER}\n"
            "function ccp\n"
            "    if test -f .claude/bin/ccp\n"
            '        "$PWD/.claude/bin/ccp" $argv\n'
            "    else if test -d /workspaces\n"
            '        set ccp_dir ""\n'
            "        for d in /workspaces/*/\n"
            '            if test -f "$d.claude/bin/ccp"\n'
            '                set ccp_dir "$d"\n'
            "                break\n"
            "            end\n"
            "        end\n"
            '        if test -n "$ccp_dir"\n'
            '            cd "$ccp_dir" && "$PWD/.claude/bin/ccp" $argv\n'
            "        else\n"
            '            echo "Error: No CCP project found in /workspaces"\n'
            "        end\n"
            "    else\n"
            '        echo "Error: Not a Claude CodePro project. Run the installer first or cd to a CCP-enabled project."\n'
            "    end\n"
            "end"
        )
    else:
        return (
            f"{CCP_ALIAS_MARKER}\n"
            "ccp() {\n"
            "    if [ -f .claude/bin/ccp ]; then\n"
            '        "$PWD/.claude/bin/ccp" "$@"\n'
            "    elif [ -d /workspaces ]; then\n"
            '        ccp_dir=""\n'
            "        for d in /workspaces/*/; do\n"
            '            [ -f "$d.claude/bin/ccp" ] && ccp_dir="$d" && break\n'
            "        done\n"
            '        if [ -n "$ccp_dir" ]; then\n'
            '            cd "$ccp_dir" && "$PWD/.claude/bin/ccp" "$@"\n'
            "        else\n"
            '            echo "Error: No CCP project found in /workspaces"\n'
            "        fi\n"
            "    else\n"
            '        echo "Error: Not a Claude CodePro project. Run the installer first or cd to a CCP-enabled project."\n'
            "    fi\n"
            "}"
        )


def alias_exists_in_file(config_file: Path) -> bool:
    """Check if ccp alias already exists in config file."""
    if not config_file.exists():
        return False
    content = config_file.read_text()
    return "alias ccp" in content or CCP_ALIAS_MARKER in content


def remove_old_alias(config_file: Path) -> bool:
    """Remove old ccp alias/function from config file to allow clean update."""
    if not config_file.exists():
        return False

    content = config_file.read_text()
    if CCP_ALIAS_MARKER not in content and "ccp()" not in content and "alias ccp" not in content:
        return False

    lines = content.split("\n")
    new_lines = []
    inside_ccp_function = False
    brace_count = 0

    for line in lines:
        stripped = line.strip()

        if CCP_ALIAS_MARKER in line:
            continue

        if stripped.startswith("alias ccp="):
            continue

        if stripped.startswith("ccp()") or stripped == "ccp () {":
            inside_ccp_function = True
            brace_count = 0

        if inside_ccp_function:
            brace_count += line.count("{") - line.count("}")
            if brace_count <= 0 and "{" in content[content.find("ccp()") :]:
                inside_ccp_function = False
            continue

        if stripped.startswith("function ccp"):
            inside_ccp_function = True
            continue

        if inside_ccp_function and stripped == "end":
            inside_ccp_function = False
            continue

        if not inside_ccp_function:
            new_lines.append(line)

    final_lines = []
    prev_blank = False
    for line in new_lines:
        is_blank = line.strip() == ""
        if is_blank and prev_blank:
            continue
        final_lines.append(line)
        prev_blank = is_blank

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


def _configure_bun_path(config_file: Path, ui, quiet: bool = False) -> bool:
    """Add bun to PATH in shell config (idempotent)."""
    if not config_file.exists():
        return False

    content = config_file.read_text()
    if BUN_PATH_MARKER in content or ".bun/bin" in content:
        if ui and not quiet:
            ui.info(f"bun PATH already configured in {config_file.name}")
        return False

    if "fish" in config_file.name:
        bun_path_line = f"\n{BUN_PATH_MARKER}\nset -gx PATH $HOME/.bun/bin $PATH\n"
    else:
        bun_path_line = f'\n{BUN_PATH_MARKER}\nexport PATH="$HOME/.bun/bin:$PATH"\n'

    with open(config_file, "a") as f:
        f.write(bun_path_line)

    if ui:
        ui.success(f"Added bun to PATH in {config_file.name}")
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
        _ = ctx
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
            ui.status("Configuring bun PATH...")
        for config_file in config_files:
            _configure_bun_path(config_file, ui, quiet=True)

        if ui:
            ui.status("Configuring shell alias...")

        for config_file in config_files:
            if not config_file.exists():
                continue

            alias_existed = alias_exists_in_file(config_file)
            if alias_existed:
                remove_old_alias(config_file)

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
