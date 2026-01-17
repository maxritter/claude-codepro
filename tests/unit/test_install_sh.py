"""Tests for install.sh bootstrap script."""

from __future__ import annotations

from pathlib import Path


def test_install_sh_runs_python_installer():
    """Verify install.sh runs the Python installer module via uv."""
    install_sh = Path(__file__).parent.parent.parent / "install.sh"
    content = install_sh.read_text()

    # The script must run the Python installer module via uv
    assert "uv run python -m installer" in content, "install.sh must run Python installer via uv"

    # Check that it passes the install command
    assert "install" in content, "install.sh must pass 'install' command"

    # Check for local-system flag support
    assert "--local-system" in content, "install.sh must support --local-system flag"


def test_install_sh_downloads_installer_files():
    """Verify install.sh downloads the installer Python package dynamically."""
    install_sh = Path(__file__).parent.parent.parent / "install.sh"
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
    install_sh = Path(__file__).parent.parent.parent / "install.sh"
    content = install_sh.read_text()

    # Must run installer which handles CCP binary download
    assert "run_installer" in content, "install.sh must have run_installer function"
    assert "python -m installer" in content, "Must run Python installer"


def test_install_sh_ensures_uv_available():
    """Verify install.sh ensures uv is available."""
    install_sh = Path(__file__).parent.parent.parent / "install.sh"
    content = install_sh.read_text()

    # Must check for uv and install if needed
    assert "check_uv" in content, "install.sh must have check_uv function"
    assert "install_uv" in content, "install.sh must have install_uv function"
    assert "astral.sh/uv/install.sh" in content, "Must use official uv installer"


def test_install_sh_is_executable_bash_script():
    """Verify install.sh has proper shebang."""
    install_sh = Path(__file__).parent.parent.parent / "install.sh"
    content = install_sh.read_text()

    assert content.startswith("#!/bin/bash"), "install.sh must start with bash shebang"


def test_install_sh_has_devcontainer_support():
    """Verify install.sh supports dev container mode."""
    install_sh = Path(__file__).parent.parent.parent / "install.sh"
    content = install_sh.read_text()

    assert "is_in_container" in content, "Must have container detection"
    assert "setup_devcontainer" in content, "Must have devcontainer setup"
    assert ".devcontainer" in content, "Must reference .devcontainer directory"


def test_install_sh_sets_pythonpath():
    """Verify install.sh sets PYTHONPATH for the installer."""
    install_sh = Path(__file__).parent.parent.parent / "install.sh"
    content = install_sh.read_text()

    assert "PYTHONPATH" in content, "Must set PYTHONPATH for installer module"
    assert ".claude/installer" in content, "Must reference installer directory"


def test_install_sh_installs_dependencies():
    """Verify install.sh installs Python dependencies via uv."""
    install_sh = Path(__file__).parent.parent.parent / "install.sh"
    content = install_sh.read_text()

    assert "install_dependencies" in content, "Must have install_dependencies function"
    assert "uv pip install" in content, "Must use uv pip install for dependencies"
