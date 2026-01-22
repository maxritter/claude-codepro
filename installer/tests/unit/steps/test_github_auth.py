"""Tests for GitHub auth step."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestGitHubAuthStep:
    """Test GitHubAuthStep class."""

    def test_github_auth_step_has_correct_name(self):
        """GitHubAuthStep has name 'github_auth'."""
        from installer.steps.github_auth import GitHubAuthStep

        step = GitHubAuthStep()
        assert step.name == "github_auth"

    def test_check_returns_true_when_already_authenticated(self):
        """check() returns True when gh is already authenticated."""
        from installer.context import InstallContext
        from installer.steps.github_auth import GitHubAuthStep
        from installer.ui import Console

        step = GitHubAuthStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = InstallContext(
                project_dir=Path(tmpdir),
                ui=Console(non_interactive=True),
            )

            with patch("installer.steps.github_auth.is_gh_authenticated", return_value=True):
                assert step.check(ctx) is True

    def test_check_returns_false_when_not_authenticated(self):
        """check() returns False when gh is not authenticated."""
        from installer.context import InstallContext
        from installer.steps.github_auth import GitHubAuthStep
        from installer.ui import Console

        step = GitHubAuthStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = InstallContext(
                project_dir=Path(tmpdir),
                ui=Console(non_interactive=True),
            )

            with patch("installer.steps.github_auth.is_gh_authenticated", return_value=False):
                assert step.check(ctx) is False


class TestGetGhToken:
    """Test get_gh_token helper function."""

    def test_get_gh_token_from_env_var(self):
        """get_gh_token reads from GH_TOKEN environment variable."""
        from installer.steps.github_auth import get_gh_token

        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / ".env"

            with patch.dict("os.environ", {"GH_TOKEN": "ghp_test_token_from_env"}):
                result = get_gh_token(env_file)
                assert result == "ghp_test_token_from_env"

    def test_get_gh_token_from_env_file(self):
        """get_gh_token reads from .env file when env var not set."""
        from installer.steps.github_auth import get_gh_token

        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / ".env"
            env_file.write_text("GH_TOKEN=ghp_test_token_from_file\n")

            with patch.dict("os.environ", {}, clear=True):
                # Ensure GH_TOKEN is not in environment
                import os

                os.environ.pop("GH_TOKEN", None)
                result = get_gh_token(env_file)
                assert result == "ghp_test_token_from_file"

    def test_get_gh_token_returns_none_when_not_set(self):
        """get_gh_token returns None when token not in env or file."""
        from installer.steps.github_auth import get_gh_token

        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / ".env"
            # Don't create the file

            with patch.dict("os.environ", {}, clear=True):
                import os

                os.environ.pop("GH_TOKEN", None)
                result = get_gh_token(env_file)
                assert result is None

    def test_get_gh_token_env_var_takes_precedence(self):
        """get_gh_token prefers environment variable over .env file."""
        from installer.steps.github_auth import get_gh_token

        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / ".env"
            env_file.write_text("GH_TOKEN=ghp_from_file\n")

            with patch.dict("os.environ", {"GH_TOKEN": "ghp_from_env"}):
                result = get_gh_token(env_file)
                assert result == "ghp_from_env"


class TestIsGhAuthenticated:
    """Test is_gh_authenticated helper function."""

    def test_is_gh_authenticated_returns_true_on_success(self):
        """is_gh_authenticated returns True when gh auth status succeeds."""
        from installer.steps.github_auth import is_gh_authenticated

        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("installer.steps.github_auth.subprocess.run", return_value=mock_result):
            assert is_gh_authenticated() is True

    def test_is_gh_authenticated_returns_false_on_failure(self):
        """is_gh_authenticated returns False when gh auth status fails."""
        from installer.steps.github_auth import is_gh_authenticated

        mock_result = MagicMock()
        mock_result.returncode = 1

        with patch("installer.steps.github_auth.subprocess.run", return_value=mock_result):
            assert is_gh_authenticated() is False

    def test_is_gh_authenticated_returns_false_on_exception(self):
        """is_gh_authenticated returns False when subprocess raises exception."""
        from installer.steps.github_auth import is_gh_authenticated

        with patch("installer.steps.github_auth.subprocess.run", side_effect=FileNotFoundError):
            assert is_gh_authenticated() is False


class TestGitHubAuthStepRun:
    """Test GitHubAuthStep.run() method."""

    def test_run_authenticates_with_token(self):
        """run() calls gh auth login when token is available."""
        from installer.context import InstallContext
        from installer.steps.github_auth import GitHubAuthStep
        from installer.ui import Console

        step = GitHubAuthStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            env_file = project_dir / ".env"
            env_file.write_text("GH_TOKEN=ghp_test_token\n")

            ctx = InstallContext(
                project_dir=project_dir,
                ui=Console(non_interactive=True),
            )

            mock_result = MagicMock()
            mock_result.returncode = 0

            with patch.dict("os.environ", {}, clear=True):
                import os

                os.environ.pop("GH_TOKEN", None)

                with patch("installer.steps.github_auth.subprocess.run", return_value=mock_result) as mock_run:
                    step.run(ctx)

                    # Verify gh auth login was called
                    mock_run.assert_called_once()
                    call_args = mock_run.call_args
                    assert call_args[0][0] == ["gh", "auth", "login", "--with-token"]
                    assert call_args[1]["input"] == "ghp_test_token"

    def test_run_shows_info_when_no_token(self):
        """run() shows info message when no token is available."""
        from installer.context import InstallContext
        from installer.steps.github_auth import GitHubAuthStep
        from installer.ui import Console

        step = GitHubAuthStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            # Don't create .env file

            mock_ui = MagicMock(spec=Console)
            ctx = InstallContext(
                project_dir=project_dir,
                ui=mock_ui,
            )

            with patch.dict("os.environ", {}, clear=True):
                import os

                os.environ.pop("GH_TOKEN", None)

                with patch("installer.steps.github_auth.subprocess.run") as mock_run:
                    step.run(ctx)

                    # gh auth login should NOT be called
                    mock_run.assert_not_called()

                    # Info message should be shown
                    mock_ui.info.assert_called_once()
                    assert "GH_TOKEN" in mock_ui.info.call_args[0][0]

    def test_run_handles_auth_failure(self):
        """run() shows error when gh auth login fails."""
        from installer.context import InstallContext
        from installer.steps.github_auth import GitHubAuthStep
        from installer.ui import Console

        step = GitHubAuthStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            env_file = project_dir / ".env"
            env_file.write_text("GH_TOKEN=ghp_invalid_token\n")

            mock_ui = MagicMock(spec=Console)
            ctx = InstallContext(
                project_dir=project_dir,
                ui=mock_ui,
            )

            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_result.stderr = "authentication failed"

            with patch.dict("os.environ", {}, clear=True):
                import os

                os.environ.pop("GH_TOKEN", None)

                with patch("installer.steps.github_auth.subprocess.run", return_value=mock_result):
                    step.run(ctx)

                    # Error message should be shown
                    mock_ui.error.assert_called_once()
                    assert "failed" in mock_ui.error.call_args[0][0].lower()

    def test_run_handles_gh_not_found(self):
        """run() shows error when gh CLI is not installed."""
        from installer.context import InstallContext
        from installer.steps.github_auth import GitHubAuthStep
        from installer.ui import Console

        step = GitHubAuthStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            env_file = project_dir / ".env"
            env_file.write_text("GH_TOKEN=ghp_test_token\n")

            mock_ui = MagicMock(spec=Console)
            ctx = InstallContext(
                project_dir=project_dir,
                ui=mock_ui,
            )

            with patch.dict("os.environ", {}, clear=True):
                import os

                os.environ.pop("GH_TOKEN", None)

                with patch("installer.steps.github_auth.subprocess.run", side_effect=FileNotFoundError):
                    step.run(ctx)

                    # Error message about gh not found should be shown
                    mock_ui.error.assert_called_once()
                    assert "not found" in mock_ui.error.call_args[0][0].lower()
