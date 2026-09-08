"""Shell config step - configures shell with claude alias."""

from __future__ import annotations

import os
import stat
import tempfile
from pathlib import Path

from installer.context import InstallContext
from installer.platform_utils import get_login_shell_config_files, get_shell_config_files
from installer.steps.base import BaseStep

OLD_CCP_MARKER = "# Claude CodePro alias"
OLD_CLAUDE_PILOT_MARKER = "# Claude Pilot"
CLAUDE_ALIAS_MARKER = "# Pilot Shell"
CLAUDE_ALIAS_END_MARKER = "# End Pilot Shell"
MANAGED_ELSEWHERE_MARKER = "# pilot-shell:managed-elsewhere"
PILOT_BIN = "$HOME/.pilot/bin/pilot"
PILOT_BIN_DIR = "$HOME/.pilot/bin"
BUN_BIN_PATH = "$HOME/.bun/bin"
CODEX_OPEN_FILES_TARGET = 1024

_CODEX_LIMIT_SH = (
    "_soft=$(ulimit -Sn); _hard=$(ulimit -Hn); "
    f"_desired={CODEX_OPEN_FILES_TARGET}; "
    'if [ "$_hard" != unlimited ] && [ "$_hard" -lt "$_desired" ] 2>/dev/null; '
    "then _desired=$_hard; fi; "
    'if [ "$_soft" != unlimited ] && [ "$_soft" -lt "$_desired" ] 2>/dev/null; '
    'then ulimit -Sn "$_desired" 2>/dev/null || true; fi'
)


def _atomic_write_text(path: Path, content: str) -> None:
    """Replace a config target atomically while preserving symlinks and mode."""
    target = path.resolve() if path.is_symlink() else path
    mode = target.stat().st_mode
    fd, temp_name = tempfile.mkstemp(prefix=".pilot-shell-", dir=target.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        temp_path.chmod(stat.S_IMODE(mode))
        os.replace(temp_path, target)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def is_managed_elsewhere(config_file: Path) -> bool:
    """Return True if the config file carries the opt-out marker."""
    if not config_file.exists():
        return False
    content = config_file.read_text(errors="replace")
    return MANAGED_ELSEWHERE_MARKER in content


def get_alias_lines(shell_type: str) -> str:
    """Get PATH, pilot alias, and claude/codex session wrapper functions."""
    if shell_type == "fish":
        path_line = f'set -gx PATH "{PILOT_BIN_DIR}" "{BUN_BIN_PATH}" $PATH'
        session_funcs = (
            "function claude; set -l _sid $fish_pid-(random); "
            "set -lx PILOT_SESSION_ID $_sid; "
            'set -lx CLAUDE_CODE_TASK_LIST_ID "pilot-$_sid"; '
            "command claude $argv; end\n"
            "function codex; set -l _sid $fish_pid-(random); "
            f"env PILOT_SESSION_ID=$_sid sh -c '{_CODEX_LIMIT_SH}; exec codex \"$@\"' sh $argv; end"
        )
    else:
        path_line = f'export PATH="{PILOT_BIN_DIR}:{BUN_BIN_PATH}:$PATH"'
        session_funcs = (
            'claude() { local _sid="$$-$RANDOM"; PILOT_SESSION_ID=$_sid CLAUDE_CODE_TASK_LIST_ID="pilot-$_sid" command claude "$@"; }\n'
            f"codex() ( local _soft _hard _desired; {_CODEX_LIMIT_SH}; "
            'PILOT_SESSION_ID="$$-$RANDOM" command codex "$@"; )'
        )
    return (
        f'{CLAUDE_ALIAS_MARKER}\n{path_line}\nalias pilot="{PILOT_BIN}"\n'
        f'alias ccp="{PILOT_BIN}"\n{session_funcs}\n{CLAUDE_ALIAS_END_MARKER}'
    )


def alias_exists_in_file(config_file: Path) -> bool:
    """Check if claude/ccp/pilot alias already exists in config file."""
    if not config_file.exists():
        return False
    content = config_file.read_text(errors="replace")
    return (
        CLAUDE_ALIAS_MARKER in content
        or CLAUDE_ALIAS_END_MARKER in content
        or OLD_CLAUDE_PILOT_MARKER in content
        or OLD_CCP_MARKER in content
        or "alias ccp" in content
        or "alias claude" in content
        or "alias pilot" in content
    )


def remove_old_alias(config_file: Path) -> bool:
    """Remove old ccp/claude alias from config file to allow clean update."""
    if not config_file.exists():
        return False

    content = config_file.read_text(errors="replace")
    has_old = (
        OLD_CCP_MARKER in content
        or OLD_CLAUDE_PILOT_MARKER in content
        or CLAUDE_ALIAS_MARKER in content
        or CLAUDE_ALIAS_END_MARKER in content
        or "alias ccp" in content
        or "alias claude" in content
        or "alias pilot" in content
        or "ccp()" in content
        or "claude()" in content
        or "codex()" in content
        or "pilot()" in content
        or "function ccp" in content
        or "function claude" in content
        or "function codex" in content
        or "function pilot" in content
        or 'PATH="$HOME/.bun/bin' in content
        or 'PATH="$HOME/.pilot/bin' in content
    )
    if not has_old:
        return False

    lines = content.split("\n")
    new_lines = []
    inside_function = False
    brace_count = 0

    for line in lines:
        stripped = line.strip()

        if (
            OLD_CCP_MARKER in line
            or OLD_CLAUDE_PILOT_MARKER in line
            or CLAUDE_ALIAS_MARKER in line
            or CLAUDE_ALIAS_END_MARKER in line
        ):
            continue

        if (
            stripped.startswith("alias ccp=")
            or stripped.startswith("alias claude=")
            or stripped.startswith("alias pilot=")
            or stripped.startswith("alias ccp ")
            or stripped.startswith("alias claude ")
            or stripped.startswith("alias pilot ")
        ):
            continue

        if (
            stripped == 'export PATH="$HOME/.bun/bin:$PATH"'
            or stripped == 'export PATH="$HOME/.pilot/bin:$HOME/.bun/bin:$PATH"'
            or stripped == 'set -gx PATH "$HOME/.bun/bin" $PATH'
            or stripped == 'set -gx PATH "$HOME/.pilot/bin" "$HOME/.bun/bin" $PATH'
        ):
            continue

        if stripped.startswith("ccp()") or stripped == "ccp () {":
            inside_function = True
            brace_count = 0
        elif stripped.startswith("claude()") or stripped == "claude () {":
            inside_function = True
            brace_count = 0
        elif stripped.startswith("codex()") or stripped == "codex () {":
            inside_function = True
            brace_count = 0
        elif stripped.startswith("pilot()") or stripped == "pilot () {":
            inside_function = True
            brace_count = 0
        if inside_function:
            brace_count += line.count("{") - line.count("}")
            if brace_count <= 0:
                inside_function = False
            continue

        if (
            stripped.startswith("function ccp")
            or stripped.startswith("function claude")
            or stripped.startswith("function codex")
            or stripped.startswith("function pilot")
        ):
            inside_function = not stripped.endswith("; end")
            continue

        if inside_function and stripped == "end":
            inside_function = False
            continue

        if not inside_function:
            new_lines.append(line)

    final_lines = []
    prev_blank = False
    for line in new_lines:
        is_blank = line.strip() == ""
        if is_blank and prev_blank:
            continue
        final_lines.append(line)
        prev_blank = is_blank

    _atomic_write_text(config_file, "\n".join(final_lines))
    return True


class ShellConfigStep(BaseStep):
    """Step that configures shell with claude alias."""

    name = "shell_config"

    def check(self, ctx: InstallContext) -> bool:
        """Always return False to ensure alias is updated on every install."""
        _ = ctx
        return False

    def run(self, ctx: InstallContext) -> None:
        """Configure shell with pilot alias."""
        ui = ctx.ui
        config_files = get_shell_config_files()
        login_files = set(get_login_shell_config_files())
        modified_files: list[str] = []
        needs_reload = False

        if ui:
            ui.status("Configuring shell alias...")

        for config_file in config_files:
            if not config_file.exists():
                # Login entry points are created on demand. Images routinely ship
                # .bashrc/.zshrc but no .profile/.zprofile, and without one the
                # PATH export never reaches `<shell> -c -l` -- the login,
                # non-interactive shell agents use for tool calls.
                if config_file not in login_files:
                    continue
                try:
                    config_file.touch()
                except OSError as e:
                    if ui:
                        ui.warning(f"Could not create {config_file.name}: {e}")
                    continue

            if is_managed_elsewhere(config_file):
                if ui:
                    ui.success(f"Skipping {config_file.name} (managed elsewhere)")
                continue

            alias_existed = alias_exists_in_file(config_file)
            shell_type = "fish" if "fish" in config_file.name else "bash"
            alias_lines = get_alias_lines(shell_type)

            try:
                base_content = config_file.read_text(errors="replace")
                if alias_existed:
                    fd, temp_name = tempfile.mkstemp(prefix=".pilot-shell-clean-", dir=config_file.parent)
                    os.close(fd)
                    temp_path = Path(temp_name)
                    try:
                        temp_path.write_text(base_content)
                        remove_old_alias(temp_path)
                        base_content = temp_path.read_text(errors="replace")
                    finally:
                        temp_path.unlink(missing_ok=True)
                _atomic_write_text(config_file, f"{base_content.rstrip()}\n\n{alias_lines}\n")
                modified_files.append(str(config_file))
                if ui:
                    if alias_existed:
                        ui.success(f"Updated alias in {config_file.name}")
                    else:
                        ui.success(f"Added alias to {config_file.name}")
                        needs_reload = True
            except (OSError, IOError) as e:
                if ui:
                    ui.warning(f"Could not modify {config_file.name}: {e}")

        ctx.config["modified_shell_configs"] = modified_files
        ctx.config["shell_needs_reload"] = needs_reload
