"""GitHub authentication step - authenticates gh CLI using GH_TOKEN."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import ClassVar

from installer.context import InstallContext
from installer.steps.base import BaseStep


def get_gh_token(env_file: Path) -> str | None:
    """Get GH_TOKEN from environment variable or .env file.

    Checks environment variable first, then falls back to .env file.
    """
    token = os.environ.get("GH_TOKEN")
    if token:
        return token

    if not env_file.exists():
        return None

    content = env_file.read_text()
    for line in content.split("\n"):
        line = line.strip()
        if line.startswith("GH_TOKEN="):
            value = line[len("GH_TOKEN=") :].strip()
            if value:
                return value
    return None


def is_gh_authenticated() -> bool:
    """Check if GitHub CLI is already authenticated."""
    try:
        result = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        return result.returncode == 0
    except Exception:
        return False


class GitHubAuthStep(BaseStep):
    """Step that authenticates GitHub CLI using GH_TOKEN from environment."""

    name: ClassVar[str] = "github_auth"

    def check(self, ctx: InstallContext) -> bool:
        """Check if GitHub CLI is already authenticated."""
        return is_gh_authenticated()

    def run(self, ctx: InstallContext) -> None:
        """Authenticate GitHub CLI using GH_TOKEN."""
        ui = ctx.ui

        if ui:
            ui.section("GitHub CLI Authentication")

        token = get_gh_token(ctx.project_dir / ".env")

        if not token:
            if ui:
                ui.info("Set GH_TOKEN in .env for automatic GitHub CLI authentication")
            return

        try:
            result = subprocess.run(
                ["gh", "auth", "login", "--with-token"],
                input=token,
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )

            if result.returncode == 0:
                if ui:
                    ui.success("GitHub CLI authenticated successfully")
            else:
                if ui:
                    error_msg = result.stderr.strip() if result.stderr else "Unknown error"
                    ui.error(f"GitHub CLI authentication failed: {error_msg}")
        except subprocess.TimeoutExpired:
            if ui:
                ui.error("GitHub CLI authentication timed out")
        except FileNotFoundError:
            if ui:
                ui.error("GitHub CLI (gh) not found. Please install it first.")
        except Exception as e:
            if ui:
                ui.error(f"GitHub CLI authentication error: {e}")

    def rollback(self, ctx: InstallContext) -> None:
        """No rollback for GitHub auth (would be too disruptive)."""
        pass
