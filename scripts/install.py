"""
Claude CodePro Installation & Update Script

The VERSION constant below is automatically updated by releasebot during releases.
When installing from a version tag, all files are downloaded from that same version.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

# This VERSION is updated by releasebot during release
# - In main branch: VERSION = "main"
# - In release tags: VERSION = "v2.4.0" (or whatever the release version is)
VERSION = "v2.5.2"
REPO_URL = "https://github.com/maxritter/claude-codepro"


LIB_MODULES = [
    "ui.py",
    "utils.py",
    "downloads.py",
    "files.py",
    "dependencies.py",
    "shell_config.py",
    "migration.py",
    "env_setup.py",
    "devcontainer.py",
]

PYTHON_PERMISSIONS = [
    "Bash(basedpyright:*)",
    "Bash(mypy:*)",
    "Bash(python tests:*)",
    "Bash(python:*)",
    "Bash(pyright:*)",
    "Bash(pytest:*)",
    "Bash(ruff check:*)",
    "Bash(ruff format:*)",
    "Bash(uv add:*)",
    "Bash(uv pip show:*)",
    "Bash(uv pip:*)",
    "Bash(uv run:*)",
]


def bootstrap_download(repo_path: str, dest_path: Path, local_mode: bool, local_repo_dir: Path | None) -> bool:
    """
    Minimal download function for bootstrapping (before lib modules are loaded).

    Args:
        repo_path: Path in repository
        dest_path: Local destination path
        local_mode: Use local files instead of downloading
        local_repo_dir: Local repository directory (if local_mode)

    Returns:
        True on success, False on failure
    """
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    if local_mode and local_repo_dir:
        source_file = local_repo_dir / repo_path
        if source_file.is_file():
            try:
                import shutil

                shutil.copy2(source_file, dest_path)
                return True
            except Exception:
                return False
        return False
    else:
        file_url = f"{REPO_URL}/raw/{VERSION}/{repo_path}"
        try:
            with urllib.request.urlopen(file_url) as response:
                if response.status == 200:
                    dest_path.write_bytes(response.read())
                    return True
        except Exception:
            pass
        return False


def download_lib_modules(project_dir: Path, local_mode: bool, local_repo_dir: Path | None) -> None:
    """Download all library modules before importing (always overwrites for upgrades)."""
    lib_dir = project_dir / "scripts" / "lib"
    lib_dir.mkdir(parents=True, exist_ok=True)

    init_file = lib_dir / "__init__.py"
    if not init_file.exists():
        init_file.touch()

    for module in LIB_MODULES:
        repo_path = f"scripts/lib/{module}"
        dest_path = lib_dir / module

        if not bootstrap_download(repo_path, dest_path, local_mode, local_repo_dir):
            print(f"Warning: Failed to download lib/{module}", file=sys.stderr)


def generate_settings_file(template_file: Path, settings_file: Path, project_dir: Path, non_interactive: bool) -> None:
    """
    Generate settings.local.json from template.

    Args:
        template_file: Path to settings.local.template.json
        settings_file: Path to settings.local.json
        project_dir: Project directory for path substitution
        non_interactive: Whether running in non-interactive mode
    """
    if not template_file.exists():
        from lib import ui

        ui.print_warning("settings.local.template.json not found, skipping generation")
        return

    from lib import ui

    if settings_file.exists():
        should_regenerate = False
        if not non_interactive:
            ui.print_warning("settings.local.json already exists")
            print("This file may contain new features in this version.")
            regen = input("Regenerate settings.local.json from template? (y/N): ").strip()
            should_regenerate = regen.lower() in ["y", "yes"]
        else:
            overwrite = os.getenv("OVERWRITE_SETTINGS", "N")
            should_regenerate = overwrite.upper() in ["Y", "YES"]

        if should_regenerate:
            template_content = template_file.read_text()
            settings_content = template_content.replace("{{PROJECT_DIR}}", str(project_dir))
            settings_file.write_text(settings_content)
            ui.print_success("Regenerated settings.local.json with absolute paths")
        else:
            ui.print_success("Kept existing settings.local.json")
    else:
        template_content = template_file.read_text()
        settings_content = template_content.replace("{{PROJECT_DIR}}", str(project_dir))
        settings_file.write_text(settings_content)
        ui.print_success("Generated settings.local.json with absolute paths")


def remove_python_settings(settings_file: Path) -> None:
    """
    Remove Python-specific hooks and permissions from settings.local.json.

    Args:
        settings_file: Path to settings.local.json
    """
    if not settings_file.exists():
        return

    from lib import ui

    ui.print_status("Removing Python hook from settings.local.json...")

    try:
        settings_data = json.loads(settings_file.read_text())

        if "hooks" in settings_data and "PostToolUse" in settings_data["hooks"]:
            for hook_group in settings_data["hooks"]["PostToolUse"]:
                if "hooks" in hook_group:
                    hook_group["hooks"] = [
                        h for h in hook_group["hooks"] if "file_checker_python.py" not in h.get("command", "")
                    ]

        if "permissions" in settings_data and "allow" in settings_data["permissions"]:
            settings_data["permissions"]["allow"] = [
                p for p in settings_data["permissions"]["allow"] if p not in PYTHON_PERMISSIONS
            ]

        settings_file.write_text(json.dumps(settings_data, indent=2) + "\n")
        ui.print_success("Configured settings.local.json without Python support")

        custom_python_rules = settings_file.parent / "rules" / "custom" / "python-rules.md"
        if custom_python_rules.exists():
            custom_python_rules.unlink()
            ui.print_success("Removed custom/python-rules.md")

    except Exception as e:
        ui.print_warning(f"Failed to remove Python settings: {e}. You may need to manually edit settings.local.json")


def install_claude_files(project_dir: Path, config, install_python: str, local_mode: bool) -> int:
    """
    Install .claude files from repository.

    Args:
        project_dir: Project directory
        config: Download configuration
        install_python: Whether to install Python support ("Y"/"N")
        local_mode: Whether running in local mode (skip cleaning to preserve source files)

    Returns:
        Number of files installed
    """
    from lib import downloads, ui

    if not local_mode:
        import shutil

        standard_dir = project_dir / ".claude" / "rules" / "standard"
        if standard_dir.exists():
            ui.print_status("Cleaning standard rules directory...")
            shutil.rmtree(standard_dir)
        standard_dir.mkdir(parents=True, exist_ok=True)

    ui.print_status("Installing .claude files...")

    file_count = 0
    claude_files = downloads.get_repo_files(".claude", config)

    for file_path in claude_files:
        if not file_path:
            continue

        if "settings.local.json" in file_path and "settings.local.template.json" not in file_path:
            continue

        if install_python.lower() not in ["y", "yes"]:
            if "file_checker_python.py" in file_path:
                continue
            if "custom/python-rules.md" in file_path:
                continue

        dest_file = project_dir / file_path
        if downloads.download_file(file_path, dest_file, config):
            file_count += 1
            print(f"   ✓ {Path(file_path).name}")

    return file_count


def main() -> None:
    """Main installation flow."""

    parser = argparse.ArgumentParser(description="Claude CodePro Installation Script")
    parser.add_argument("--non-interactive", action="store_true", help="Run without interactive prompts")
    parser.add_argument("--skip-env", action="store_true", help="Skip environment setup (API keys)")
    parser.add_argument(
        "--local",
        action="store_true",
        help="Use local files instead of downloading from GitHub",
    )
    parser.add_argument(
        "--local-repo-dir",
        type=str,
        help="Local repository directory (auto-detected if --local)",
    )

    args = parser.parse_args()

    if not args.non_interactive and not sys.stdin.isatty():
        args.non_interactive = True
        print("⚠ Detected non-interactive environment (stdin not a TTY), enabling non-interactive mode")
        print("")

    project_dir = Path.cwd()

    local_mode = args.local
    local_repo_dir: Path | None = None
    if local_mode:
        if args.local_repo_dir:
            local_repo_dir = Path(args.local_repo_dir).resolve()
        else:
            script_location = Path(__file__).parent.resolve()
            local_repo_dir = script_location.parent

    download_lib_modules(project_dir, local_mode, local_repo_dir)

    sys.path.insert(0, str(project_dir / "scripts"))

    from lib import (
        dependencies,
        devcontainer,
        downloads,
        env_setup,
        files,
        migration,
        shell_config,
        ui,
        utils,
    )

    temp_dir = Path(tempfile.mkdtemp())

    try:
        config = downloads.DownloadConfig(
            repo_url=REPO_URL,
            repo_branch=VERSION,
            local_mode=local_mode,
            local_repo_dir=local_repo_dir,
        )

        ui.print_section("Claude CodePro Installation")

        if not utils.check_required_dependencies():
            sys.exit(1)

        ui.print_status(f"Installing into: {project_dir}")

        if (project_dir / ".claude").exists():
            ui.print_status(f"Upgrading Claude CodePro to {VERSION}")
        else:
            ui.print_status(f"Installing Claude CodePro {VERSION}")
        print("")

        devcontainer.offer_devcontainer_setup(project_dir, config, args.non_interactive)

        migration.run_migration(project_dir, args.non_interactive)

        if args.non_interactive:
            install_python = os.getenv("INSTALL_PYTHON", "Y")
            ui.print_status(f"Non-interactive mode: Python support = {install_python}")
            print("")
        else:
            print("Do you want to install advanced Python features?")
            print("This includes: uv, ruff, mypy, basedpyright, and Python quality hooks")
            sys.stdout.flush()
            install_python = input("Install Python support? (Y/n): ").strip() or "Y"
            print("")
            print("")

        ui.print_section("Installing Claude CodePro Files")

        file_count = install_claude_files(project_dir, config, install_python, local_mode)

        ui.print_status("Setting up custom rules directory...")
        custom_dir = project_dir / ".claude" / "rules" / "custom"
        if not custom_dir.exists():
            custom_dir.mkdir(parents=True, exist_ok=True)
            (custom_dir / ".gitkeep").touch()
            print("   ✓ Created custom/")

        ui.print_status("Setting up skills directory...")
        skills_dir = project_dir / ".claude" / "skills"
        if not skills_dir.exists():
            skills_dir.mkdir(parents=True, exist_ok=True)
            (skills_dir / ".gitkeep").touch()
            print("   ✓ Created skills/")

        ui.print_status("Generating settings.local.json from template...")
        template_file = project_dir / ".claude" / "settings.local.template.json"
        settings_file = project_dir / ".claude" / "settings.local.json"

        generate_settings_file(template_file, settings_file, project_dir, args.non_interactive)

        if install_python.lower() not in ["y", "yes"]:
            remove_python_settings(settings_file)

        hooks_dir = project_dir / ".claude" / "hooks"
        if hooks_dir.exists():
            for hook_file in hooks_dir.glob("*.sh"):
                hook_file.chmod(0o755)

        ui.print_success(f"Installed {file_count} .claude files")
        print("")

        if not (project_dir / ".cipher").exists():
            files.install_directory(".cipher", project_dir, config)
            print("")

        if not (project_dir / ".qlty").exists():
            files.install_directory(".qlty", project_dir, config)
            print("")

        files.merge_mcp_config(".mcp.json", project_dir / ".mcp.json", config, temp_dir)
        files.merge_mcp_config(".mcp-funnel.json", project_dir / ".mcp-funnel.json", config, temp_dir)
        print("")

        files.install_file(
            ".claude/rules/build.py",
            project_dir / ".claude" / "rules" / "build.py",
            config,
        )

        build_script = project_dir / ".claude" / "rules" / "build.py"
        if build_script.exists():
            build_script.chmod(0o755)
        print("")

        ui.print_status("Creating .nvmrc for Node.js 22...")
        (project_dir / ".nvmrc").write_text("22\n")
        ui.print_success("Created .nvmrc")
        print("")

        if args.skip_env or args.non_interactive:
            ui.print_section("Environment Setup")
            ui.print_status("Skipping interactive environment setup (non-interactive mode)")
            ui.print_warning("Make sure to set up .env file manually or via environment variables")
            print("")
        else:
            ui.print_section("Environment Setup")
            env_setup.setup_env_file(project_dir)

        ui.print_section("Installing Dependencies")

        dependencies.install_nodejs()
        print("")

        if install_python.lower() in ["y", "yes"]:
            dependencies.install_uv()
            print("")

            dependencies.install_python_tools()
            print("")

        dependencies.install_qlty(project_dir)
        print("")

        dependencies.install_claude_code()
        print("")

        dependencies.install_cipher()
        print("")

        dependencies.install_newman()
        print("")

        dependencies.install_dotenvx()
        print("")

        ui.print_section("Building Rules")
        build_script = project_dir / ".claude" / "rules" / "build.py"
        if build_script.exists():
            try:
                subprocess.run([sys.executable, str(build_script)], check=True, capture_output=True)
                ui.print_success("Rules Built!")
            except subprocess.CalledProcessError:
                ui.print_error("Failed to build rules")
                ui.print_warning("You may need to run 'python3 .claude/rules/build.py' manually")
        else:
            ui.print_warning("build.py not found, skipping")
        print("")

        ui.print_section("Installing Statusline Configuration")
        source_config = project_dir / ".claude" / "statusline.json"
        target_dir = Path.home() / ".config" / "ccstatusline"
        target_config = target_dir / "settings.json"

        if source_config.exists():
            ui.print_status("Installing statusline configuration...")
            target_dir.mkdir(parents=True, exist_ok=True)
            import shutil

            shutil.copy2(source_config, target_config)
            ui.print_success("Installed statusline configuration to ~/.config/ccstatusline/settings.json")
        else:
            ui.print_warning("statusline.json not found in .claude directory, skipping")
        print("")

        ui.print_section("Configuring Shell")
        shell_config.add_cc_alias(project_dir)

        ui.print_section("🎉 Installation Complete!")

        print("")
        print(f"{ui.GREEN}{'━' * 70}{ui.NC}")
        print(f"{ui.GREEN}  Claude CodePro has been successfully installed! 🚀{ui.NC}")
        print(f"{ui.GREEN}{'━' * 70}{ui.NC}")
        print("")
        print(f"{ui.BLUE}What's next?{ui.NC} Follow these steps to get started:")
        print("")
        print(f"{ui.YELLOW}STEP 1: Reload Your Shell{ui.NC}")
        print("   → For zsh: source ~/.zshrc")
        print("   → For bash: source ~/.bashrc")
        print("   → For fish: source ~/.config/fish/config.fish")
        print("")
        print(f"{ui.YELLOW}STEP 2: Start Claude Code{ui.NC}")
        print("   → Launch with: ccp")
        print("")
        print(f"{ui.YELLOW}STEP 3: Configure Claude Code{ui.NC}")
        print("   → In Claude Code, run: /config")
        print("   → Set 'Auto-connect to IDE' = true")
        print("   → Set 'Auto-compact' = false")
        print("")
        print(f"{ui.YELLOW}STEP 4: Verify Everything Works{ui.NC}")
        print("   → Run: /ide        (Connect to VS Code diagnostics)")
        print("   → Run: /mcp        (Verify all MCP servers are online)")
        print("   → Run: /context    (Check context usage is below 20%)")
        print("")
        print(f"{ui.YELLOW}STEP 5: Initialize Project Context{ui.NC}")
        print("   → Run: /setup      Scans project, creates context, indexes codebase")
        print("")
        print(f"{ui.YELLOW}STEP 6: Start Building!{ui.NC}")
        print("   → /plan            Create detailed spec with TDD")
        print("   → /implement       Execute spec with mandatory testing")
        print("   → /verify          Run end-to-end quality checks")
        print("")
        print(f"{ui.GREEN}{'━' * 70}{ui.NC}")
        print(f"{ui.GREEN}📚 Learn more: https://www.claude-code.pro{ui.NC}")
        print(f"{ui.GREEN}💬 Questions? https://github.com/maxritter/claude-codepro/issues{ui.NC}")
        print(f"{ui.GREEN}{'━' * 70}{ui.NC}")
        print("")

    finally:
        utils.cleanup(temp_dir)


if __name__ == "__main__":
    main()
