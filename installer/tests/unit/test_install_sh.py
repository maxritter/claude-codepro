"""Tests for install.sh bootstrap script."""

from __future__ import annotations

from pathlib import Path


def test_install_sh_runs_python_installer():
    """Verify install.sh runs the Python installer module via uv with Python 3.12."""
    install_sh = Path(__file__).parent.parent.parent.parent / "install.sh"
    content = install_sh.read_text()

    # The script must run the Python installer module via uv with Python 3.12
    assert "uv run --python 3.12" in content, "install.sh must run with Python 3.12"
    assert "python -m installer" in content, "install.sh must run Python installer"

    # Check that it passes the install command
    assert "install" in content, "install.sh must pass 'install' command"

    # Check for local-system flag support
    assert "--local-system" in content, "install.sh must support --local-system flag"


def test_install_sh_downloads_installer_files():
    """Verify install.sh downloads the installer Python package dynamically."""
    install_sh = Path(__file__).parent.parent.parent.parent / "install.sh"
    content = install_sh.read_text()

    # Must have download_installer function
    assert "download_installer" in content, "install.sh must have download_installer function"

    # Must use GitHub API to dynamically discover files
    assert "api.github.com" in content, "Must use GitHub API for file discovery"
    assert "git/trees" in content, "Must use git trees API endpoint"

    # Must filter for Python files in installer directory
    assert "installer/" in content, "Must filter for installer directory"
    assert ".py" in content, "Must filter for Python files"


def test_install_sh_runs_installer():
    """Verify install.sh runs the Python installer (which downloads CCP binary)."""
    install_sh = Path(__file__).parent.parent.parent.parent / "install.sh"
    content = install_sh.read_text()

    # Must run installer which handles CCP binary download
    assert "run_installer" in content, "install.sh must have run_installer function"
    assert "python -m installer" in content, "Must run Python installer"


def test_install_sh_ensures_uv_available():
    """Verify install.sh ensures uv is available."""
    install_sh = Path(__file__).parent.parent.parent.parent / "install.sh"
    content = install_sh.read_text()

    # Must check for uv and install if needed
    assert "check_uv" in content, "install.sh must have check_uv function"
    assert "install_uv" in content, "install.sh must have install_uv function"
    assert "astral.sh/uv/install.sh" in content, "Must use official uv installer"


def test_install_sh_is_executable_bash_script():
    """Verify install.sh has proper shebang."""
    install_sh = Path(__file__).parent.parent.parent.parent / "install.sh"
    content = install_sh.read_text()

    assert content.startswith("#!/bin/bash"), "install.sh must start with bash shebang"


def test_install_sh_has_devcontainer_support():
    """Verify install.sh supports dev container mode."""
    install_sh = Path(__file__).parent.parent.parent.parent / "install.sh"
    content = install_sh.read_text()

    assert "is_in_container" in content, "Must have container detection"
    assert "setup_devcontainer" in content, "Must have devcontainer setup"
    assert ".devcontainer" in content, "Must reference .devcontainer directory"


def test_install_sh_uses_with_flags():
    """Verify install.sh uses --with flags for inline deps (no venv created)."""
    install_sh = Path(__file__).parent.parent.parent.parent / "install.sh"
    content = install_sh.read_text()

    assert "--with rich" in content, "Must use --with for rich"
    assert "PYTHONPATH" in content, "Must set PYTHONPATH for installer module"


def test_install_sh_uses_python_312():
    """Verify install.sh uses Python 3.12 via uv run."""
    install_sh = Path(__file__).parent.parent.parent.parent / "install.sh"
    content = install_sh.read_text()

    # uv run --python 3.12 auto-downloads Python 3.12 if needed
    assert "--python 3.12" in content, "Must use --python 3.12 flag"
    assert "--no-project" in content, "Must use --no-project to avoid modifying user's venv"


def test_install_sh_has_get_saved_install_mode():
    """Verify install.sh can read saved install mode preference."""
    install_sh = Path(__file__).parent.parent.parent.parent / "install.sh"
    content = install_sh.read_text()

    # Must have get_saved_install_mode function
    assert "get_saved_install_mode()" in content, "Must have get_saved_install_mode function"

    # Must read from config file
    assert "ccp-config.json" in content, "Must read from ccp-config.json"
    assert '"install_mode"' in content, "Must read install_mode field"

    # Must handle case when file doesn't exist (check for -f)
    assert '[ -f "$config_file" ]' in content, "Must check if config file exists"


def test_install_sh_has_save_install_mode():
    """Verify install.sh can save install mode preference."""
    install_sh = Path(__file__).parent.parent.parent.parent / "install.sh"
    content = install_sh.read_text()

    # Must have save_install_mode function
    assert "save_install_mode()" in content, "Must have save_install_mode function"

    # Must create directory if needed
    assert 'mkdir -p "$(dirname "$config_file")"' in content, "Must create config directory"

    # Must handle both new file and update existing
    assert "echo " in content and "ccp-config.json" in content, "Must write to config file"


def test_install_sh_uses_saved_preference():
    """Verify install.sh checks for and uses saved install mode preference."""
    install_sh = Path(__file__).parent.parent.parent.parent / "install.sh"
    content = install_sh.read_text()

    # Must call get_saved_install_mode
    assert "saved_mode=$(get_saved_install_mode)" in content, "Must get saved mode"

    # Must check for both local and container modes
    assert 'saved_mode" = "local"' in content, "Must check for local mode"
    assert 'saved_mode" = "container"' in content, "Must check for container mode"

    # Must indicate saved preference to user
    assert "Using saved preference" in content, "Must inform user about saved preference"


def test_install_sh_saves_user_choice():
    """Verify install.sh saves user's install mode choice."""
    install_sh = Path(__file__).parent.parent.parent.parent / "install.sh"
    content = install_sh.read_text()

    # Must save local choice
    assert 'save_install_mode "local"' in content, "Must save local mode choice"

    # Must save container choice
    assert 'save_install_mode "container"' in content, "Must save container mode choice"

    # Must indicate preference was saved
    assert "preference saved" in content, "Must indicate preference was saved"


def test_install_sh_replaces_devcontainer_project_name():
    """Verify install.sh has sed commands to replace claude-codepro with project name."""
    install_sh = Path(__file__).parent.parent.parent.parent / "install.sh"
    content = install_sh.read_text()

    # Must generate PROJECT_SLUG from directory name
    assert "PROJECT_SLUG=" in content, "Must generate PROJECT_SLUG"
    assert "basename" in content, "Must use basename to get directory name"
    assert "tr '[:upper:]' '[:lower:]'" in content, "Must convert to lowercase"

    # Must replace quoted "claude-codepro" (for name and runArgs)
    assert '"claude-codepro"' in content, "Must have pattern for quoted claude-codepro"
    assert "${PROJECT_SLUG}" in content, "Must substitute PROJECT_SLUG"

    # Must replace workspace path
    assert "/workspaces/claude-codepro" in content, "Must have pattern for workspace path"


def test_install_sh_preserves_github_url_in_devcontainer(tmp_path: Path):
    """Verify sed commands replace project name but preserve GitHub URLs."""
    import subprocess

    # Create a mock devcontainer.json with the actual structure
    devcontainer_dir = tmp_path / ".devcontainer"
    devcontainer_dir.mkdir()
    devcontainer_json = devcontainer_dir / "devcontainer.json"
    devcontainer_json.write_text("""{
  "name": "claude-codepro",
  "runArgs": ["--name", "claude-codepro"],
  "workspaceFolder": "/workspaces/claude-codepro",
  "postCreateCommand": "curl -fsSL https://raw.githubusercontent.com/maxritter/claude-codepro/v5.0.6/install.sh | bash"
}""")

    # Run the sed commands from install.sh
    project_slug = "my-cool-project"
    subprocess.run(
        ["sed", "-i", f's/"claude-codepro"/"{project_slug}"/g', str(devcontainer_json)],
        check=True,
    )
    subprocess.run(
        ["sed", "-i", f"s|/workspaces/claude-codepro|/workspaces/{project_slug}|g", str(devcontainer_json)],
        check=True,
    )

    result = devcontainer_json.read_text()

    # Project name and slug should be replaced
    assert f'"name": "{project_slug}"' in result, "name field must be replaced"
    assert f'"--name", "{project_slug}"' in result, "runArgs name must be replaced"
    assert f'"/workspaces/{project_slug}"' in result, "workspaceFolder must be replaced"

    # GitHub URL must be preserved (not replaced)
    assert "maxritter/claude-codepro/v5.0.6" in result, "GitHub URL must be preserved"


def test_install_sh_sed_handles_special_project_names(tmp_path: Path):
    """Verify sed commands work with various project name formats."""
    import subprocess

    test_cases = [
        ("My Project", "my-project"),
        ("My_Project", "my-project"),
        ("MyProject", "myproject"),
        ("my-project", "my-project"),
        ("PROJECT", "project"),
    ]

    for project_name, expected_slug in test_cases:
        # Create fresh devcontainer.json for each test
        devcontainer_dir = tmp_path / ".devcontainer"
        devcontainer_dir.mkdir(exist_ok=True)
        devcontainer_json = devcontainer_dir / "devcontainer.json"
        devcontainer_json.write_text("""{
  "name": "claude-codepro",
  "workspaceFolder": "/workspaces/claude-codepro"
}""")

        # Generate slug the same way install.sh does
        result = subprocess.run(
            ["bash", "-c", f"echo '{project_name}' | tr '[:upper:]' '[:lower:]' | tr ' _' '-'"],
            capture_output=True,
            text=True,
            check=True,
        )
        project_slug = result.stdout.strip()

        assert project_slug == expected_slug, f"Slug for '{project_name}' should be '{expected_slug}', got '{project_slug}'"

        # Run sed replacements
        subprocess.run(
            ["sed", "-i", f's/"claude-codepro"/"{project_slug}"/g', str(devcontainer_json)],
            check=True,
        )
        subprocess.run(
            ["sed", "-i", f"s|/workspaces/claude-codepro|/workspaces/{project_slug}|g", str(devcontainer_json)],
            check=True,
        )

        content = devcontainer_json.read_text()
        assert f'"name": "{project_slug}"' in content, f"Failed for project '{project_name}'"
        assert f'"/workspaces/{project_slug}"' in content, f"Failed workspace for '{project_name}'"
