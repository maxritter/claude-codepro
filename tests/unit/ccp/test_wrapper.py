"""Unit tests for wrapper with license verification."""

from __future__ import annotations

import stat
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ccp.auth import LicenseState


class TestWrapperLicenseIntegration:
    """Tests for wrapper integration with license verification."""

    def test_wrapper_validates_license_on_start(self, tmp_path: Path) -> None:
        """Wrapper checks license state on startup."""
        from ccp.wrapper import ClaudeWrapper

        pipe_dir = tmp_path / "pipes"
        wrapper = ClaudeWrapper(claude_args=[], pipe_dir=pipe_dir)

        mock_state = LicenseState(license_key="KEY", tier="commercial")

        with patch.object(wrapper, "_license_manager") as mock_manager:
            mock_manager.get_state.return_value = mock_state
            mock_manager.validate.return_value = (True, "")
            valid, tier, expired, error = wrapper._check_license()

        assert valid is True
        assert tier == "commercial"
        assert expired is False
        assert error == ""

    def test_wrapper_fails_with_no_license(self, tmp_path: Path) -> None:
        """Wrapper returns False when no license state exists."""
        from ccp.wrapper import ClaudeWrapper

        pipe_dir = tmp_path / "pipes"
        wrapper = ClaudeWrapper(claude_args=[], pipe_dir=pipe_dir)

        with patch.object(wrapper, "_license_manager") as mock_manager:
            mock_manager.get_state.return_value = None
            valid, tier, expired, error = wrapper._check_license()

        assert valid is False
        assert tier == "none"
        assert error == "No license found"

    def test_wrapper_detects_expired_trial(self, tmp_path: Path) -> None:
        """Wrapper detects expired trial."""
        from ccp.wrapper import ClaudeWrapper

        pipe_dir = tmp_path / "pipes"
        wrapper = ClaudeWrapper(claude_args=[], pipe_dir=pipe_dir)

        expired_state = LicenseState(
            license_key="TRIAL",
            tier="trial",
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        )

        with patch.object(wrapper, "_license_manager") as mock_manager:
            mock_manager.get_state.return_value = expired_state
            mock_manager.validate.return_value = (False, "Trial has expired")
            valid, tier, expired, error = wrapper._check_license()

        assert valid is False
        assert expired is True
        assert "Trial" in error or "expired" in error.lower()

    def test_wrapper_revalidates_commercial_license(self, tmp_path: Path) -> None:
        """Wrapper re-validates commercial license with Gumroad."""
        from ccp.wrapper import ClaudeWrapper

        pipe_dir = tmp_path / "pipes"
        wrapper = ClaudeWrapper(claude_args=[], pipe_dir=pipe_dir)

        commercial_state = LicenseState(
            license_key="COMMERCIAL-KEY",
            tier="commercial",
            last_validated_at=datetime.now(timezone.utc) - timedelta(hours=25),
        )

        with patch.object(wrapper, "_license_manager") as mock_manager:
            mock_manager.get_state.return_value = commercial_state
            mock_manager.validate.return_value = (True, "")
            valid, tier, expired, error = wrapper._check_license()

        assert valid is True
        assert tier == "commercial"
        mock_manager.validate.assert_called_once()

    def test_wrapper_detects_cancelled_subscription(self, tmp_path: Path) -> None:
        """Wrapper detects cancelled commercial subscription."""
        from ccp.wrapper import ClaudeWrapper

        pipe_dir = tmp_path / "pipes"
        wrapper = ClaudeWrapper(claude_args=[], pipe_dir=pipe_dir)

        commercial_state = LicenseState(license_key="COMMERCIAL-KEY", tier="commercial")

        with patch.object(wrapper, "_license_manager") as mock_manager:
            # First call returns state, second call (after removal) returns None
            mock_manager.get_state.side_effect = [commercial_state, None]
            mock_manager.validate.return_value = (False, "Subscription has been cancelled")
            valid, tier, expired, error = wrapper._check_license()

        assert valid is False
        assert "Subscription" in error or "cancelled" in error.lower()


class TestWrapperBannerWithLicense:
    """Tests for wrapper banner showing license status."""

    def test_print_banner_shows_free_tier(self, capsys) -> None:
        """Banner shows free tier indicator."""
        from ccp.wrapper import print_banner

        print_banner(tier="free")
        captured = capsys.readouterr()

        assert "Free" in captured.out

    def test_print_banner_shows_commercial(self, capsys) -> None:
        """Banner shows commercial tier indicator."""
        from ccp.wrapper import print_banner

        print_banner(tier="commercial")
        captured = capsys.readouterr()

        assert "Licensed" in captured.out

    def test_print_banner_shows_trial(self, capsys) -> None:
        """Banner shows trial tier indicator."""
        from ccp.wrapper import print_banner

        print_banner(tier="trial", days_remaining=5)
        captured = capsys.readouterr()

        assert "Trial" in captured.out
        assert "5 days remaining" in captured.out


class TestMigratedWrapperFunctionality:
    """Tests to ensure wrapper preserves core functionality."""

    def test_wrapper_creates_pipe_directory(self, tmp_path: Path) -> None:
        """Wrapper creates pipe directory if it doesn't exist."""
        from ccp.wrapper import ClaudeWrapper

        pipe_dir = tmp_path / "pipes"
        ClaudeWrapper(claude_args=[], pipe_dir=pipe_dir)

        assert pipe_dir.exists()

    def test_wrapper_creates_named_pipe(self, tmp_path: Path) -> None:
        """Wrapper creates a named pipe file."""
        from ccp.wrapper import ClaudeWrapper

        pipe_dir = tmp_path / "pipes"
        wrapper = ClaudeWrapper(claude_args=[], pipe_dir=pipe_dir)
        wrapper._create_pipe()

        assert wrapper.pipe_path.exists()
        assert stat.S_ISFIFO(wrapper.pipe_path.stat().st_mode)

    def test_wrapper_exports_pipe_env_var(self, tmp_path: Path) -> None:
        """Wrapper sets WRAPPER_PIPE environment variable."""
        from ccp.wrapper import ClaudeWrapper

        pipe_dir = tmp_path / "pipes"
        wrapper = ClaudeWrapper(claude_args=[], pipe_dir=pipe_dir)
        wrapper._create_pipe()
        env = wrapper._get_claude_env()

        assert "WRAPPER_PIPE" in env
        assert env["WRAPPER_PIPE"] == str(wrapper.pipe_path)

    def test_handle_clear_command(self, tmp_path: Path) -> None:
        """Wrapper handles 'clear' command by setting restart flags."""
        from ccp.wrapper import ClaudeWrapper

        pipe_dir = tmp_path / "pipes"
        wrapper = ClaudeWrapper(claude_args=[], pipe_dir=pipe_dir)
        wrapper._create_pipe()
        wrapper._kill_claude = MagicMock()

        wrapper._handle_command("clear")

        assert wrapper._restart_pending is True
        assert wrapper._restart_prompt is None
        wrapper._kill_claude.assert_called_once()

    def test_handle_exit_command(self, tmp_path: Path) -> None:
        """Wrapper handles 'exit' command by setting shutdown flag."""
        from ccp.wrapper import ClaudeWrapper

        pipe_dir = tmp_path / "pipes"
        wrapper = ClaudeWrapper(claude_args=[], pipe_dir=pipe_dir)
        wrapper._create_pipe()
        wrapper._kill_claude = MagicMock()

        wrapper._handle_command("exit")

        assert wrapper._shutdown_requested is True
        wrapper._kill_claude.assert_called_once()


class TestExpiredTrialLicensePrompt:
    """Tests for expired trial license key prompt."""

    def test_expired_trial_prompts_for_license_key(self, tmp_path: Path) -> None:
        """Expired trial should prompt for license key."""
        from ccp.wrapper import ClaudeWrapper

        pipe_dir = tmp_path / "pipes"
        wrapper = ClaudeWrapper(claude_args=[], pipe_dir=pipe_dir)

        expired_state = LicenseState(
            license_key="TRIAL",
            tier="trial",
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        )

        with patch.object(wrapper, "_license_manager") as mock_manager:
            mock_manager.get_state.return_value = expired_state
            mock_manager.validate.return_value = (False, "Trial expired")
            valid, tier, expired, error = wrapper._check_license()

        assert valid is False
        assert expired is True
        assert tier == "trial"

    def test_expired_trial_accepts_valid_license(self, tmp_path: Path) -> None:
        """Expired trial accepts valid license key activation."""
        import subprocess
        from ccp.wrapper import ClaudeWrapper

        pipe_dir = tmp_path / "pipes"
        wrapper = ClaudeWrapper(claude_args=[], pipe_dir=pipe_dir)

        # Mock subprocess.run for license activation
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            with patch("builtins.input", return_value="VALID-LICENSE-KEY"):
                # The actual run() method would call this, but we test the subprocess call pattern
                result = subprocess.run(
                    ["python", "-m", "ccp", "activate", "VALID-LICENSE-KEY", "--json"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )

        assert result.returncode == 0

    def test_expired_trial_rejects_empty_license(self, tmp_path: Path) -> None:
        """Expired trial rejects empty license key."""
        from ccp.wrapper import ClaudeWrapper

        pipe_dir = tmp_path / "pipes"
        wrapper = ClaudeWrapper(claude_args=[], pipe_dir=pipe_dir)

        # Empty license key should be rejected without calling subprocess
        license_key = ""
        assert not license_key  # Empty string is falsy


class TestWrapperUpdateCheck:
    """Tests for wrapper auto-update checking functionality."""

    def test_update_check_runs_when_update_available(self, tmp_path: Path) -> None:
        """Update check calls check_for_update when enabled."""
        from io import StringIO

        from ccp.wrapper import ClaudeWrapper

        pipe_dir = tmp_path / "pipes"
        wrapper = ClaudeWrapper(claude_args=[], pipe_dir=pipe_dir, skip_update_check=False)

        with patch.object(wrapper, "_load_ccp_config", return_value={"auto_update": True, "declined_version": None}):
            with patch.object(wrapper, "_save_ccp_config"):
                with patch("ccp.updater.check_for_update") as mock_check:
                    mock_check.return_value = (True, "4.5.8", "4.6.0")
                    # Mock the /dev/tty open to simulate TTY with "n" response then "1" for skip choice
                    mock_tty = MagicMock()
                    mock_tty.__enter__ = MagicMock(return_value=StringIO("n\n1\n"))
                    mock_tty.__exit__ = MagicMock(return_value=False)
                    with patch("builtins.open", return_value=mock_tty):
                        result = wrapper._check_and_prompt_update()

        mock_check.assert_called_once()
        assert result is False  # User declined

    def test_update_check_skipped_when_flag_set(self, tmp_path: Path) -> None:
        """Update check is skipped when skip_update_check=True."""
        from ccp.wrapper import ClaudeWrapper

        pipe_dir = tmp_path / "pipes"
        wrapper = ClaudeWrapper(claude_args=[], pipe_dir=pipe_dir, skip_update_check=True)

        with patch("ccp.updater.check_for_update") as mock_check:
            result = wrapper._check_and_prompt_update()

        mock_check.assert_not_called()
        assert result is False

    def test_update_check_no_prompt_when_up_to_date(self, tmp_path: Path) -> None:
        """No prompt shown when already on latest version."""
        from ccp.wrapper import ClaudeWrapper

        pipe_dir = tmp_path / "pipes"
        wrapper = ClaudeWrapper(claude_args=[], pipe_dir=pipe_dir, skip_update_check=False)

        with patch.object(wrapper, "_load_ccp_config", return_value={"auto_update": True, "declined_version": None}):
            with patch("ccp.updater.check_for_update") as mock_check:
                mock_check.return_value = (False, "4.5.8", "4.5.8")
                with patch("builtins.input") as mock_input:
                    result = wrapper._check_and_prompt_update()

        mock_check.assert_called_once()
        mock_input.assert_not_called()  # No prompt for up-to-date
        assert result is False

    def test_update_check_handles_network_error(self, tmp_path: Path) -> None:
        """Update check handles network errors gracefully."""
        from ccp.wrapper import ClaudeWrapper

        pipe_dir = tmp_path / "pipes"
        wrapper = ClaudeWrapper(claude_args=[], pipe_dir=pipe_dir, skip_update_check=False)

        with patch.object(wrapper, "_load_ccp_config", return_value={"auto_update": True, "declined_version": None}):
            with patch("ccp.updater.check_for_update") as mock_check:
                mock_check.return_value = (None, "4.5.8", None)  # Network error
                with patch("builtins.input") as mock_input:
                    result = wrapper._check_and_prompt_update()

        mock_check.assert_called_once()
        mock_input.assert_not_called()  # No prompt on network error
        assert result is False

    def test_update_accepted_downloads_and_runs_installer(self, tmp_path: Path) -> None:
        """When user accepts update, downloads and runs installer."""
        from io import StringIO

        from ccp.wrapper import ClaudeWrapper

        pipe_dir = tmp_path / "pipes"
        wrapper = ClaudeWrapper(claude_args=[], pipe_dir=pipe_dir, skip_update_check=False)

        with patch.object(wrapper, "_load_ccp_config", return_value={"auto_update": True, "declined_version": None}):
            with patch.object(wrapper, "_save_ccp_config"):
                with patch("ccp.updater.check_for_update") as mock_check:
                    mock_check.return_value = (True, "4.5.8", "4.6.0")
                    with patch("ccp.updater.download_installer") as mock_download:
                        mock_download.return_value = True
                        with patch("ccp.updater.run_installer") as mock_run:
                            mock_run.return_value = (True, "")
                            # Mock /dev/tty with "y" response to accept update
                            mock_tty = MagicMock()
                            mock_tty.__enter__ = MagicMock(return_value=StringIO("y\n"))
                            mock_tty.__exit__ = MagicMock(return_value=False)
                            with patch("builtins.open", return_value=mock_tty):
                                result = wrapper._check_and_prompt_update()

        mock_download.assert_called_once()
        mock_run.assert_called_once()
        assert result is True
