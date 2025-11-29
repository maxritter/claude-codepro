"""E2E tests for install.py script."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def project_root():
    """Get the project root directory."""
    # This test file is in tests/e2e/, so go up two levels
    return Path(__file__).parent.parent.parent


@pytest.fixture(scope="module")
def installed_project(project_root):
    """Create a test project and run installation once for all tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)
        # Initialize git repo (required for installation)
        subprocess.run(["git", "init"], cwd=project_dir, check=True, capture_output=True)

        # Run installation once
        result = run_install(project_dir, project_root)
        if result.returncode != 0:
            pytest.fail(f"Installation failed: {result.stderr}")

        yield project_dir


def run_install(
    project_dir: Path,
    project_root: Path,
    *,
    non_interactive: bool = True,
    install_python: str = "Y",
) -> subprocess.CompletedProcess:
    """Run install.py script."""
    env = {
        **subprocess.os.environ,
        "INSTALL_PYTHON": install_python,
        "GIT_USER_NAME": "Test User",
        "GIT_USER_EMAIL": "test@example.com",
    }

    args = [
        "python3",
        str(project_root / "scripts" / "install.py"),
        "--local",
        "--local-repo-dir",
        str(project_root),
    ]

    if non_interactive:
        args.append("--non-interactive")

    return subprocess.run(
        args,
        cwd=project_dir,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


class TestBasicInstallation:
    """Test basic installation functionality."""

    def test_creates_claude_directory(self, installed_project):
        """Test that .claude directory is created."""
        assert (installed_project / ".claude").is_dir()

    def test_creates_hooks_directory(self, installed_project):
        """Test that hooks directory is created."""
        assert (installed_project / ".claude" / "hooks").is_dir()

    def test_creates_rules_directory(self, installed_project):
        """Test that rules directory is created."""
        assert (installed_project / ".claude" / "rules").is_dir()

    def test_creates_commands_directory(self, installed_project):
        """Test that commands directory is created."""
        # Commands dir is created by build script during install
        assert (installed_project / ".claude" / "commands").is_dir()

    def test_creates_skills_directory(self, installed_project):
        """Test that skills directory is created."""
        # Skills dir is created by build script during install
        assert (installed_project / ".claude" / "skills").is_dir()

    def test_creates_settings_template(self, installed_project):
        """Test that settings template is created."""
        assert (installed_project / ".claude" / "settings.local.template.json").exists()

    def test_creates_settings_file(self, installed_project):
        """Test that settings file is created from template."""
        assert (installed_project / ".claude" / "settings.local.json").exists()

    def test_settings_has_absolute_paths(self, installed_project):
        """Test that settings.local.json has absolute paths."""
        settings_file = installed_project / ".claude" / "settings.local.json"
        settings_data = json.loads(settings_file.read_text())

        # Check that hooks have absolute paths
        assert "hooks" in settings_data
        assert "PostToolUse" in settings_data["hooks"]

        for hook_group in settings_data["hooks"]["PostToolUse"]:
            for hook in hook_group.get("hooks", []):
                command = hook.get("command", "")
                # Should contain absolute path to project
                assert str(installed_project) in command

    def test_template_has_placeholders(self, installed_project):
        """Test that template still has placeholders."""
        template_file = installed_project / ".claude" / "settings.local.template.json"
        template_content = template_file.read_text()
        assert "{{PROJECT_DIR}}" in template_content

    def test_creates_nvmrc(self, installed_project):
        """Test that .nvmrc is created."""
        nvmrc_file = installed_project / ".nvmrc"
        assert nvmrc_file.exists()
        assert nvmrc_file.read_text().strip() == "22"

    def test_creates_cipher_directory(self, installed_project):
        """Test that .cipher directory is created."""
        assert (installed_project / ".cipher").is_dir()

    def test_creates_qlty_directory(self, installed_project):
        """Test that .qlty directory is created."""
        assert (installed_project / ".qlty").is_dir()

    def test_creates_mcp_config(self, installed_project):
        """Test that .mcp.json is created."""
        assert (installed_project / ".mcp.json").exists()

    def test_creates_mcp_funnel_config(self, installed_project):
        """Test that .mcp-funnel.json is created."""
        assert (installed_project / ".mcp-funnel.json").exists()

    def test_creates_build_script(self, installed_project):
        """Test that build.py is created."""
        build_script = installed_project / ".claude" / "rules" / "build.py"
        assert build_script.exists()
        assert build_script.stat().st_mode & 0o111  # Executable

    def test_creates_library_modules(self, installed_project):
        """Test that library modules are created."""
        lib_dir = installed_project / "scripts" / "lib"
        assert lib_dir.is_dir()

        required_modules = [
            "ui.py",
            "utils.py",
            "downloads.py",
            "files.py",
            "dependencies.py",
            "shell_config.py",
        ]

        for module in required_modules:
            assert (lib_dir / module).exists()


class TestPythonSupport:
    """Test Python support flag."""

    def test_python_hook_installed_when_enabled(self, installed_project):
        """Test that Python hook is installed when Python support is enabled."""
        python_hook = installed_project / ".claude" / "hooks" / "file_checker_python.py"
        assert python_hook.exists()

    def test_python_hook_not_installed_when_disabled(self, project_root):
        """Test that Python hook is not installed when Python support is disabled."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            subprocess.run(["git", "init"], cwd=project_dir, check=True, capture_output=True)
            run_install(project_dir, project_root, install_python="N")
            python_hook = project_dir / ".claude" / "hooks" / "file_checker_python.py"
            assert not python_hook.exists()

    def test_python_permissions_removed_when_disabled(self, project_root):
        """Test that Python permissions are removed from settings when disabled."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            subprocess.run(["git", "init"], cwd=project_dir, check=True, capture_output=True)
            run_install(project_dir, project_root, install_python="N")
            settings_file = project_dir / ".claude" / "settings.local.json"
            settings_data = json.loads(settings_file.read_text())

            # Check that Python-related permissions are not present
            allowed_tools = settings_data.get("allowedTools", [])
            python_tools = [
                "Bash(basedpyright:*)",
                "Bash(mypy:*)",
                "Bash(pytest:*)",
                "Bash(ruff check:*)",
            ]

            for tool in python_tools:
                assert tool not in allowed_tools


class TestIdempotency:
    """Test that installation is idempotent."""

    def test_second_run_preserves_settings(self, installed_project, project_root):
        """Test that second installation preserves settings.local.json."""
        settings_file = installed_project / ".claude" / "settings.local.json"
        original_content = settings_file.read_text()

        # Second install
        run_install(installed_project, project_root)
        new_content = settings_file.read_text()

        # Settings should be preserved (not overwritten)
        assert original_content == new_content


class TestBootstrapDownload:
    """Test bootstrap module download."""

    def test_downloads_all_modules(self, installed_project):
        """Test that all library modules are downloaded."""
        lib_dir = installed_project / "scripts" / "lib"
        required_modules = [
            "ui.py",
            "utils.py",
            "downloads.py",
            "files.py",
            "dependencies.py",
            "shell_config.py",
            "migration.py",
            "env_setup.py",
            "devcontainer.py",
            "git_setup.py",
        ]

        for module in required_modules:
            module_path = lib_dir / module
            assert module_path.exists(), f"Module {module} not downloaded"
