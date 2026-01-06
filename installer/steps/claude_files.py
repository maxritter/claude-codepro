"""Claude files installation step - installs .claude directory files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from installer.downloads import DownloadConfig, download_file, get_repo_files
from installer.steps.base import BaseStep

if TYPE_CHECKING:
    from installer.context import InstallContext

SETTINGS_FILE = "settings.local.json"
PYTHON_CHECKER_HOOK = "python3 .claude/hooks/file_checker_python.py"
HOOKS_PATH_PATTERN = ".claude/hooks/"
SOURCE_REPO_PATH = "/workspaces/claude-codepro/.claude/hooks/"


def patch_hook_paths(content: str, project_dir: Path) -> str:
    """Patch hook paths to use absolute paths for the target project.

    Handles both relative paths (.claude/hooks/) and existing absolute paths
    from the source repo (/workspaces/claude-codepro/.claude/hooks/).
    """
    abs_hooks_path = str(project_dir / ".claude" / "hooks") + "/"

    content = content.replace(SOURCE_REPO_PATH, abs_hooks_path)

    content = content.replace(" " + HOOKS_PATH_PATTERN, " " + abs_hooks_path)
    content = content.replace('"' + HOOKS_PATH_PATTERN, '"' + abs_hooks_path)

    return content


def process_settings(settings_content: str, install_python: bool) -> str:
    """Process settings JSON, optionally removing Python-specific hooks.

    Args:
        settings_content: Raw JSON content of the settings file
        install_python: Whether Python support is being installed

    Returns:
        Processed JSON string with Python hooks removed if install_python=False
    """
    config: dict[str, Any] = json.loads(settings_content)

    if not install_python:
        try:
            for hook_group in config["hooks"]["PostToolUse"]:
                hook_group["hooks"] = [h for h in hook_group["hooks"] if h.get("command") != PYTHON_CHECKER_HOOK]
        except (KeyError, TypeError, AttributeError):
            pass

    return json.dumps(config, indent=2) + "\n"


class ClaudeFilesStep(BaseStep):
    """Step that installs .claude directory files from the repository."""

    name = "claude_files"

    def check(self, ctx: InstallContext) -> bool:
        """Check if .claude files are already installed.

        Note: Always returns False to ensure settings.local.json is updated.
        This step is idempotent - files are overwritten without backup.
        """
        return False

    def run(self, ctx: InstallContext) -> None:
        """Install all .claude files from repository."""
        ui = ctx.ui

        config = DownloadConfig(
            repo_url="https://github.com/maxritter/claude-codepro",
            repo_branch="main",
            local_mode=ctx.local_mode,
            local_repo_dir=ctx.local_repo_dir,
        )

        if ui:
            ui.status("Installing .claude files...")

        claude_files = get_repo_files(".claude", config)

        if not claude_files:
            if ui:
                ui.warning("No .claude files found in repository")
                if not config.local_mode:
                    ui.print("  This may be due to GitHub API rate limiting.")
                    ui.print("  Try running with --local flag if you have the repo cloned.")
            return

        installed_files: list[str] = []
        file_count = 0
        failed_files: list[str] = []

        categories: dict[str, list[str]] = {
            "commands": [],
            "rules": [],
            "hooks": [],
            "skills": [],
            "other": [],
        }

        settings_path: str | None = None

        for file_path in claude_files:
            if not file_path:
                continue

            if "__pycache__" in file_path:
                continue

            if file_path.endswith(".pyc"):
                continue

            if Path(file_path).name == SETTINGS_FILE:
                settings_path = file_path
                continue

            if not ctx.install_python:
                if "file_checker_python.py" in file_path:
                    continue
                if "python-rules.md" in file_path:
                    continue

            if "/commands/" in file_path:
                categories["commands"].append(file_path)
            elif "/rules/" in file_path:
                categories["rules"].append(file_path)
            elif "/hooks/" in file_path:
                categories["hooks"].append(file_path)
            elif "/skills/" in file_path:
                categories["skills"].append(file_path)
            else:
                categories["other"].append(file_path)

        category_names = {
            "commands": "slash commands",
            "rules": "rules",
            "hooks": "hooks",
            "skills": "skills",
            "other": "config files",
        }

        for category, files in categories.items():
            if not files:
                continue

            if ui:
                with ui.spinner(f"Installing {category_names[category]}..."):
                    for file_path in files:
                        dest_file = ctx.project_dir / file_path
                        if download_file(file_path, dest_file, config):
                            file_count += 1
                            installed_files.append(str(dest_file))
                        else:
                            failed_files.append(file_path)
                ui.success(f"Installed {len(files)} {category_names[category]}")
            else:
                for file_path in files:
                    dest_file = ctx.project_dir / file_path
                    if download_file(file_path, dest_file, config):
                        file_count += 1
                        installed_files.append(str(dest_file))
                    else:
                        failed_files.append(file_path)

        settings_dest = ctx.project_dir / ".claude" / "settings.local.json"

        if settings_path:
            if ui:
                with ui.spinner("Installing settings..."):
                    success = self._install_settings(
                        settings_path, settings_dest, config, ctx.install_python, ctx.project_dir
                    )
                    if success:
                        file_count += 1
                        installed_files.append(str(settings_dest))
                        ui.success("Installed settings.local.json")
                    else:
                        failed_files.append(settings_path)
                        ui.warning("Failed to install settings.local.json")
            else:
                success = self._install_settings(
                    settings_path, settings_dest, config, ctx.install_python, ctx.project_dir
                )
                if success:
                    file_count += 1
                    installed_files.append(str(settings_dest))
                else:
                    failed_files.append(settings_path)

        ctx.config["installed_files"] = installed_files

        hooks_dir = ctx.project_dir / ".claude" / "hooks"
        if hooks_dir.exists():
            for hook_file in hooks_dir.glob("*.sh"):
                hook_file.chmod(0o755)
            for hook_file in hooks_dir.glob("*.py"):
                hook_file.chmod(0o755)

        custom_dir = ctx.project_dir / ".claude" / "rules" / "custom"
        if not custom_dir.exists():
            custom_dir.mkdir(parents=True, exist_ok=True)
            (custom_dir / ".gitkeep").touch()

        skills_dir = ctx.project_dir / ".claude" / "skills"
        if not skills_dir.exists():
            skills_dir.mkdir(parents=True, exist_ok=True)
            (skills_dir / ".gitkeep").touch()

        if ui:
            if file_count > 0:
                ui.success(f"Installed {file_count} .claude files")
            else:
                ui.warning("No .claude files were installed")

            if failed_files:
                ui.warning(f"Failed to download {len(failed_files)} files")
                for failed in failed_files[:5]:
                    ui.print(f"  - {failed}")
                if len(failed_files) > 5:
                    ui.print(f"  ... and {len(failed_files) - 5} more")

    def _install_settings(
        self,
        source_path: str,
        dest_path: Path,
        config: DownloadConfig,
        install_python: bool,
        project_dir: Path,
    ) -> bool:
        """Download and process settings file.

        Args:
            source_path: Path to settings file in repository
            dest_path: Local destination path
            config: Download configuration
            install_python: Whether Python support is being installed
            project_dir: Project directory for absolute hook paths

        Returns:
            True if successful, False otherwise
        """
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            temp_file = Path(tmpdir) / "settings.json"
            if not download_file(source_path, temp_file, config):
                return False

            try:
                settings_content = temp_file.read_text()
                processed_content = process_settings(settings_content, install_python)
                processed_content = patch_hook_paths(processed_content, project_dir)
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                dest_path.write_text(processed_content)
                return True
            except (json.JSONDecodeError, OSError, IOError):
                return False

    def rollback(self, ctx: InstallContext) -> None:
        """Remove installed files."""
        installed_files = ctx.config.get("installed_files", [])

        for file_path in installed_files:
            path = Path(file_path)
            if path.exists():
                try:
                    path.unlink()
                except (OSError, IOError):
                    pass
