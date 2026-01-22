"""Tests for license activation step."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from installer.context import InstallContext
from installer.steps.license_activation import (
    LICENSE_KEY_ENV_VAR,
    LicenseActivationStep,
    get_license_key,
    get_license_key_from_env_file,
    is_license_valid,
)
from installer.ui import Console


class TestLicenseActivationStep:
    """Test LicenseActivationStep class."""

    def test_license_activation_step_has_correct_name(self):
        """LicenseActivationStep has name 'license_activation'."""
        step = LicenseActivationStep()
        assert step.name == "license_activation"

    def test_check_returns_true_when_no_key_exists(self):
        """check() returns True (skip) when no license key found."""
        step = LicenseActivationStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            ctx = InstallContext(
                project_dir=project_dir,
                ui=Console(non_interactive=True),
            )

            # No .env file, no env var
            with patch.dict("os.environ", {}, clear=True):
                result = step.check(ctx)
                assert result is True

    def test_check_returns_true_when_license_already_valid(self):
        """check() returns True (skip) when license is already valid."""
        step = LicenseActivationStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)

            # Create .env with license key
            env_file = project_dir / ".env"
            env_file.write_text(f"{LICENSE_KEY_ENV_VAR}=TEST-KEY-1234\n")

            # Create mock ccp binary directory
            bin_dir = project_dir / ".claude" / "bin"
            bin_dir.mkdir(parents=True)
            ccp_bin = bin_dir / "ccp"
            ccp_bin.touch()

            ctx = InstallContext(
                project_dir=project_dir,
                ui=Console(non_interactive=True),
            )

            # Mock subprocess to return valid license status
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = '{"tier": "standard", "is_expired": false}'
            mock_result.stderr = ""

            with patch("installer.steps.license_activation.subprocess.run", return_value=mock_result):
                result = step.check(ctx)
                assert result is True

    def test_check_returns_false_when_key_exists_but_license_invalid(self):
        """check() returns False (run) when key exists but license not valid."""
        step = LicenseActivationStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)

            # Create .env with license key
            env_file = project_dir / ".env"
            env_file.write_text(f"{LICENSE_KEY_ENV_VAR}=TEST-KEY-1234\n")

            # Create mock ccp binary directory
            bin_dir = project_dir / ".claude" / "bin"
            bin_dir.mkdir(parents=True)
            ccp_bin = bin_dir / "ccp"
            ccp_bin.touch()

            ctx = InstallContext(
                project_dir=project_dir,
                ui=Console(non_interactive=True),
            )

            # Mock subprocess to return invalid/no license
            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_result.stdout = ""
            mock_result.stderr = "No valid license"

            with patch("installer.steps.license_activation.subprocess.run", return_value=mock_result):
                result = step.check(ctx)
                assert result is False

    def test_run_activates_license_with_key_from_env_file(self):
        """run() activates license using key from .env file."""
        step = LicenseActivationStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)

            # Create .env with license key
            env_file = project_dir / ".env"
            env_file.write_text(f"{LICENSE_KEY_ENV_VAR}=TEST-KEY-1234\n")

            # Create mock ccp binary
            bin_dir = project_dir / ".claude" / "bin"
            bin_dir.mkdir(parents=True)
            ccp_bin = bin_dir / "ccp"
            ccp_bin.touch()

            console = Console(non_interactive=True)
            ctx = InstallContext(
                project_dir=project_dir,
                ui=console,
            )

            # Mock successful activation
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = '{"success": true}'
            mock_result.stderr = ""

            # Clear env var to ensure .env file is used
            with patch.dict("os.environ", {LICENSE_KEY_ENV_VAR: ""}, clear=False):
                with patch("installer.steps.license_activation.subprocess.run", return_value=mock_result) as mock_run:
                    with patch.object(console, "success") as mock_success:
                        step.run(ctx)

                        # Verify ccp activate was called with correct args
                        mock_run.assert_called_once()
                        call_args = mock_run.call_args[0][0]
                        assert "activate" in call_args
                        assert "TEST-KEY-1234" in call_args
                        assert "--json" in call_args

                        # Verify success message
                        mock_success.assert_called()

    def test_run_activates_license_with_key_from_env_var(self):
        """run() activates license using key from environment variable."""
        step = LicenseActivationStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)

            # Create mock ccp binary
            bin_dir = project_dir / ".claude" / "bin"
            bin_dir.mkdir(parents=True)
            ccp_bin = bin_dir / "ccp"
            ccp_bin.touch()

            console = Console(non_interactive=True)
            ctx = InstallContext(
                project_dir=project_dir,
                ui=console,
            )

            # Mock successful activation
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = '{"success": true}'
            mock_result.stderr = ""

            with patch.dict("os.environ", {LICENSE_KEY_ENV_VAR: "ENV-VAR-KEY-5678"}):
                with patch("installer.steps.license_activation.subprocess.run", return_value=mock_result) as mock_run:
                    step.run(ctx)

                    # Verify ccp activate was called with env var key
                    call_args = mock_run.call_args[0][0]
                    assert "ENV-VAR-KEY-5678" in call_args

    def test_run_warns_but_continues_on_activation_failure(self):
        """run() warns but does not raise exception on activation failure."""
        step = LicenseActivationStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)

            # Create .env with license key
            env_file = project_dir / ".env"
            env_file.write_text(f"{LICENSE_KEY_ENV_VAR}=INVALID-KEY\n")

            # Create mock ccp binary
            bin_dir = project_dir / ".claude" / "bin"
            bin_dir.mkdir(parents=True)
            ccp_bin = bin_dir / "ccp"
            ccp_bin.touch()

            console = Console(non_interactive=True)
            ctx = InstallContext(
                project_dir=project_dir,
                ui=console,
            )

            # Mock failed activation
            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_result.stdout = ""
            mock_result.stderr = "Invalid license key"

            with patch("installer.steps.license_activation.subprocess.run", return_value=mock_result):
                with patch.object(console, "warning") as mock_warning:
                    # Should NOT raise exception
                    step.run(ctx)

                    # Should show warning
                    mock_warning.assert_called()

    def test_run_handles_missing_binary(self):
        """run() warns and continues when ccp binary not found."""
        step = LicenseActivationStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)

            # Create .env with license key but NO ccp binary
            env_file = project_dir / ".env"
            env_file.write_text(f"{LICENSE_KEY_ENV_VAR}=TEST-KEY\n")

            console = Console(non_interactive=True)
            ctx = InstallContext(
                project_dir=project_dir,
                ui=console,
            )

            with patch.object(console, "warning") as mock_warning:
                # Should NOT raise exception
                step.run(ctx)

                # Should show warning about missing binary
                mock_warning.assert_called()


class TestHelperFunctions:
    """Test helper functions for license activation."""

    def test_get_license_key_from_env_file_returns_value(self):
        """get_license_key_from_env_file() returns key value from .env."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / ".env"
            env_file.write_text(f"{LICENSE_KEY_ENV_VAR}=MY-LICENSE-KEY\n")

            result = get_license_key_from_env_file(env_file)
            assert result == "MY-LICENSE-KEY"

    def test_get_license_key_from_env_file_returns_none_when_missing(self):
        """get_license_key_from_env_file() returns None when key not in file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / ".env"
            env_file.write_text("OTHER_KEY=value\n")

            result = get_license_key_from_env_file(env_file)
            assert result is None

    def test_get_license_key_from_env_file_returns_none_when_no_file(self):
        """get_license_key_from_env_file() returns None when file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / ".env"
            # Don't create the file

            result = get_license_key_from_env_file(env_file)
            assert result is None

    def test_get_license_key_prefers_env_var_over_file(self):
        """get_license_key() prefers environment variable over .env file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / ".env"
            env_file.write_text(f"{LICENSE_KEY_ENV_VAR}=FILE-KEY\n")

            with patch.dict("os.environ", {LICENSE_KEY_ENV_VAR: "ENV-VAR-KEY"}):
                result = get_license_key(env_file)
                assert result == "ENV-VAR-KEY"

    def test_is_license_valid_returns_false_when_no_binary(self):
        """is_license_valid() returns False when ccp binary doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            ctx = InstallContext(
                project_dir=project_dir,
                ui=Console(non_interactive=True),
            )

            result = is_license_valid(ctx)
            assert result is False

    def test_is_license_valid_returns_true_for_valid_license(self):
        """is_license_valid() returns True for valid license."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)

            # Create mock ccp binary
            bin_dir = project_dir / ".claude" / "bin"
            bin_dir.mkdir(parents=True)
            (bin_dir / "ccp").touch()

            ctx = InstallContext(
                project_dir=project_dir,
                ui=Console(non_interactive=True),
            )

            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = '{"tier": "standard", "is_expired": false}'
            mock_result.stderr = ""

            with patch("installer.steps.license_activation.subprocess.run", return_value=mock_result):
                result = is_license_valid(ctx)
                assert result is True

    def test_is_license_valid_returns_false_for_expired_license(self):
        """is_license_valid() returns False for expired license."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)

            # Create mock ccp binary
            bin_dir = project_dir / ".claude" / "bin"
            bin_dir.mkdir(parents=True)
            (bin_dir / "ccp").touch()

            ctx = InstallContext(
                project_dir=project_dir,
                ui=Console(non_interactive=True),
            )

            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = '{"tier": "trial", "is_expired": true}'
            mock_result.stderr = ""

            with patch("installer.steps.license_activation.subprocess.run", return_value=mock_result):
                result = is_license_valid(ctx)
                assert result is False
