"""Tests for Prerequisites installation step."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestPrerequisitesStep:
    """Test PrerequisitesStep class."""

    def test_prerequisites_step_has_correct_name(self):
        """PrerequisitesStep has name 'prerequisites'."""
        from installer.steps.prerequisites import PrerequisitesStep

        step = PrerequisitesStep()
        assert step.name == "prerequisites"

    def test_prerequisites_step_skips_in_devcontainer(self):
        """PrerequisitesStep.check returns True when in dev container (skip step)."""
        from installer.context import InstallContext
        from installer.steps.prerequisites import PrerequisitesStep
        from installer.ui import Console

        step = PrerequisitesStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = InstallContext(
                project_dir=Path(tmpdir),
                ui=Console(non_interactive=True),
            )

            with patch("installer.steps.prerequisites.is_in_devcontainer", return_value=True):
                assert step.check(ctx) is True

    def test_prerequisites_step_runs_when_not_in_devcontainer(self):
        """PrerequisitesStep.check returns False when not in dev container."""
        from installer.context import InstallContext
        from installer.steps.prerequisites import PrerequisitesStep
        from installer.ui import Console

        step = PrerequisitesStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = InstallContext(
                project_dir=Path(tmpdir),
                is_local_install=True,
                ui=Console(non_interactive=True),
            )

            with patch("installer.steps.prerequisites.is_in_devcontainer", return_value=False):
                with patch("installer.steps.prerequisites.is_homebrew_available", return_value=True):
                    with patch("installer.steps.prerequisites.command_exists", return_value=False):
                        assert step.check(ctx) is False

    def test_prerequisites_step_skips_when_all_packages_installed(self):
        """PrerequisitesStep.check returns True when all packages already installed."""
        from installer.context import InstallContext
        from installer.steps.prerequisites import PrerequisitesStep
        from installer.ui import Console

        step = PrerequisitesStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = InstallContext(
                project_dir=Path(tmpdir),
                is_local_install=True,
                ui=Console(non_interactive=True),
            )

            with patch("installer.steps.prerequisites.is_in_devcontainer", return_value=False):
                with patch("installer.steps.prerequisites.is_homebrew_available", return_value=True):
                    with patch("installer.steps.prerequisites.command_exists", return_value=True):
                        with patch("installer.steps.prerequisites._is_nvm_installed", return_value=True):
                            assert step.check(ctx) is True

    def test_prerequisites_step_skips_when_not_local_install(self):
        """PrerequisitesStep.check returns True when not a local install."""
        from installer.context import InstallContext
        from installer.steps.prerequisites import PrerequisitesStep
        from installer.ui import Console

        step = PrerequisitesStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = InstallContext(
                project_dir=Path(tmpdir),
                is_local_install=False,
                ui=Console(non_interactive=True),
            )

            with patch("installer.steps.prerequisites.is_in_devcontainer", return_value=False):
                assert step.check(ctx) is True

    def test_prerequisites_step_only_runs_in_local_mode_outside_devcontainer(self):
        """PrerequisitesStep only runs when is_local_install=True AND not in dev container."""
        from installer.context import InstallContext
        from installer.steps.prerequisites import PrerequisitesStep
        from installer.ui import Console

        step = PrerequisitesStep()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Test all 4 combinations
            test_cases = [
                # (is_local_install, in_devcontainer, should_skip)
                (False, False, True),   # Not local, not devcontainer -> skip
                (False, True, True),    # Not local, in devcontainer -> skip
                (True, True, True),     # Local but in devcontainer -> skip
                (True, False, False),   # Local and not devcontainer -> RUN (don't skip)
            ]

            for is_local, in_dc, should_skip in test_cases:
                ctx = InstallContext(
                    project_dir=Path(tmpdir),
                    is_local_install=is_local,
                    ui=Console(non_interactive=True),
                )

                with patch("installer.steps.prerequisites.is_in_devcontainer", return_value=in_dc):
                    with patch("installer.steps.prerequisites.is_homebrew_available", return_value=True):
                        with patch("installer.steps.prerequisites.command_exists", return_value=False):
                            result = step.check(ctx)
                            assert result == should_skip, (
                                f"is_local={is_local}, in_dc={in_dc}: "
                                f"expected skip={should_skip}, got skip={result}"
                            )


class TestPrerequisitesStepRun:
    """Test PrerequisitesStep.run() method."""

    @patch("installer.steps.prerequisites._install_homebrew_package")
    @patch("installer.steps.prerequisites._add_bun_tap")
    @patch("installer.steps.prerequisites.command_exists")
    def test_prerequisites_run_installs_missing_packages(
        self, mock_cmd_exists, mock_tap, mock_install
    ):
        """PrerequisitesStep.run installs packages that are missing."""
        from installer.context import InstallContext
        from installer.steps.prerequisites import HOMEBREW_PACKAGES, PrerequisitesStep
        from installer.ui import Console

        mock_cmd_exists.return_value = False
        mock_tap.return_value = True
        mock_install.return_value = True

        step = PrerequisitesStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = InstallContext(
                project_dir=Path(tmpdir),
                is_local_install=True,
                ui=Console(non_interactive=True),
            )

            step.run(ctx)

            mock_tap.assert_called_once()
            assert mock_install.call_count == len(HOMEBREW_PACKAGES)

    @patch("installer.steps.prerequisites._install_homebrew_package")
    @patch("installer.steps.prerequisites._add_bun_tap")
    @patch("installer.steps.prerequisites._is_nvm_installed")
    @patch("installer.steps.prerequisites.command_exists")
    def test_prerequisites_run_skips_installed_packages(
        self, mock_cmd_exists, mock_nvm_installed, mock_tap, mock_install
    ):
        """PrerequisitesStep.run skips packages that are already installed."""
        from installer.context import InstallContext
        from installer.steps.prerequisites import PrerequisitesStep
        from installer.ui import Console

        mock_cmd_exists.return_value = True
        mock_nvm_installed.return_value = True
        mock_tap.return_value = True
        mock_install.return_value = True

        step = PrerequisitesStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = InstallContext(
                project_dir=Path(tmpdir),
                is_local_install=True,
                ui=Console(non_interactive=True),
            )

            step.run(ctx)

            mock_tap.assert_called_once()
            mock_install.assert_not_called()


class TestPrerequisitesHelpers:
    """Test Prerequisites helper functions."""

    def test_homebrew_packages_list_exists(self):
        """HOMEBREW_PACKAGES constant exists and contains expected packages."""
        from installer.steps.prerequisites import HOMEBREW_PACKAGES

        assert isinstance(HOMEBREW_PACKAGES, list)
        assert "git" in HOMEBREW_PACKAGES
        assert "gh" in HOMEBREW_PACKAGES
        assert "python@3.12" in HOMEBREW_PACKAGES
        assert "node@22" in HOMEBREW_PACKAGES
        assert "bun" in HOMEBREW_PACKAGES
        assert "uv" in HOMEBREW_PACKAGES

    @patch("subprocess.run")
    def test_add_bun_tap_runs_brew_tap(self, mock_run):
        """_add_bun_tap runs brew tap command."""
        from installer.steps.prerequisites import _add_bun_tap

        mock_run.return_value = MagicMock(returncode=0)

        result = _add_bun_tap()

        assert result is True
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "brew" in call_args
        assert "tap" in call_args
        assert "oven-sh/bun" in call_args

    @patch("subprocess.run")
    def test_install_homebrew_package_runs_brew_install(self, mock_run):
        """_install_homebrew_package runs brew install command."""
        from installer.steps.prerequisites import _install_homebrew_package

        mock_run.return_value = MagicMock(returncode=0)

        result = _install_homebrew_package("git")

        assert result is True
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "brew" in call_args
        assert "install" in call_args
        assert "git" in call_args


class TestIsHomebrewAvailable:
    """Test is_homebrew_available function."""

    @patch("shutil.which")
    def test_is_homebrew_available_returns_true_when_found(self, mock_which):
        """is_homebrew_available returns True when brew is in PATH."""
        from installer.platform_utils import is_homebrew_available

        mock_which.return_value = "/opt/homebrew/bin/brew"
        assert is_homebrew_available() is True

    @patch("shutil.which")
    def test_is_homebrew_available_returns_false_when_not_found(self, mock_which):
        """is_homebrew_available returns False when brew not in PATH."""
        from installer.platform_utils import is_homebrew_available

        mock_which.return_value = None
        assert is_homebrew_available() is False
