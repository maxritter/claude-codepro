"""
Git Setup Functions - Git initialization and configuration

Ensures git is properly configured before tools like qlty that require it.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from . import ui


def is_git_initialized(project_dir: Path) -> bool:
    """Check if git repository is initialized."""
    return (project_dir / ".git").is_dir()


def get_git_config(key: str) -> str | None:
    """Get a git config value."""
    try:
        result = subprocess.run(
            ["git", "config", "--global", key],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def set_git_config(key: str, value: str) -> bool:
    """Set a git config value."""
    try:
        subprocess.run(
            ["git", "config", "--global", key, value],
            check=True,
            capture_output=True,
        )
        return True
    except Exception:
        return False


def has_commits(project_dir: Path) -> bool:
    """Check if the repository has at least one commit."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            cwd=project_dir,
        )
        return result.returncode == 0
    except Exception:
        return False


def create_initial_commit(project_dir: Path) -> bool:
    """Create an initial commit with any existing files."""
    try:
        # Stage all files
        subprocess.run(
            ["git", "add", "."],
            check=True,
            capture_output=True,
            cwd=project_dir,
        )

        # Create initial commit
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            check=True,
            capture_output=True,
            cwd=project_dir,
        )
        return True
    except Exception:
        return False


def setup_git(project_dir: Path, non_interactive: bool = False) -> bool:
    """
    Ensure git is properly set up for the project.

    Checks:
    1. Git repository is initialized
    2. Git user.name is configured
    3. Git user.email is configured
    4. Repository has at least one commit

    Args:
        project_dir: Project directory path
        non_interactive: Skip interactive prompts (use env vars)

    Returns:
        True if git is properly configured, False otherwise
    """
    ui.print_section("Git Configuration")

    # Check if git is installed
    try:
        subprocess.run(["git", "--version"], capture_output=True, check=True)
    except Exception:
        ui.print_error("Git is not installed. Please install git first.")
        return False

    # Initialize git if needed
    if not is_git_initialized(project_dir):
        ui.print_status("Initializing git repository...")
        try:
            subprocess.run(
                ["git", "init"],
                check=True,
                capture_output=True,
                cwd=project_dir,
            )
            ui.print_success("Git repository initialized")
        except Exception as e:
            ui.print_error(f"Failed to initialize git: {e}")
            return False
    else:
        ui.print_success("Git repository already initialized")

    # Check and configure user.name
    user_name = get_git_config("user.name")
    if not user_name:
        if non_interactive:
            user_name = os.getenv("GIT_USER_NAME")
            if not user_name:
                ui.print_error("Git user.name not configured. Set GIT_USER_NAME environment variable.")
                return False
        else:
            print("")
            print("Git user.name is not configured (required for commits).")
            sys.stdout.flush()
            user_name = input("Enter your name for git commits: ").strip()
            if not user_name:
                ui.print_error("Name cannot be empty")
                return False

        if set_git_config("user.name", user_name):
            ui.print_success(f"Git user.name set to: {user_name}")
        else:
            ui.print_error("Failed to set git user.name")
            return False
    else:
        ui.print_success(f"Git user.name: {user_name}")

    # Check and configure user.email
    user_email = get_git_config("user.email")
    if not user_email:
        if non_interactive:
            user_email = os.getenv("GIT_USER_EMAIL")
            if not user_email:
                ui.print_error("Git user.email not configured. Set GIT_USER_EMAIL environment variable.")
                return False
        else:
            print("")
            print("Git user.email is not configured (required for commits).")
            sys.stdout.flush()
            user_email = input("Enter your email for git commits: ").strip()
            if not user_email:
                ui.print_error("Email cannot be empty")
                return False

        if set_git_config("user.email", user_email):
            ui.print_success(f"Git user.email set to: {user_email}")
        else:
            ui.print_error("Failed to set git user.email")
            return False
    else:
        ui.print_success(f"Git user.email: {user_email}")

    # Check for initial commit
    if not has_commits(project_dir):
        ui.print_status("Creating initial commit...")

        # Create a .gitignore if it doesn't exist
        gitignore = project_dir / ".gitignore"
        if not gitignore.exists():
            gitignore.write_text("""# Environment
.env
.env.local
.env.*.local

# Dependencies
node_modules/
__pycache__/
*.pyc
.venv/
venv/

# IDE
.idea/
*.swp
*.swo

# Build
dist/
build/
*.egg-info/

# Data
data/
*.db
""")
            ui.print_success("Created .gitignore")

        if create_initial_commit(project_dir):
            ui.print_success("Initial commit created")
        else:
            ui.print_warning("Could not create initial commit (repository may be empty)")
            ui.print_warning("You may need to add files and commit manually")
    else:
        ui.print_success("Repository has commits")

    print("")
    return True
