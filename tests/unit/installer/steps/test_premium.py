"""Tests for premium features step."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


class TestPremiumStep:
    """Test PremiumStep class."""

    def test_premium_step_has_correct_name(self):
        """PremiumStep has name 'premium'."""
        from installer.steps.premium import PremiumStep

        step = PremiumStep()
        assert step.name == "premium"

    def test_check_always_returns_false(self):
        """check() always returns False - premium step always runs for setup or cleanup."""
        from installer.context import InstallContext
        from installer.steps.premium import PremiumStep
        from installer.ui import Console

        step = PremiumStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)

            # Without premium key
            ctx = InstallContext(
                project_dir=project_dir,
                premium_key=None,
                ui=Console(non_interactive=True),
            )
            assert step.check(ctx) is False

            # With premium key
            ctx = InstallContext(
                project_dir=project_dir,
                premium_key="TEST-LICENSE-KEY",
                ui=Console(non_interactive=True),
            )
            assert step.check(ctx) is False

            # Even with binary already installed
            bin_dir = project_dir / ".claude" / "bin"
            bin_dir.mkdir(parents=True)
            (bin_dir / "ccp-premium").write_text("binary")

            ctx = InstallContext(
                project_dir=project_dir,
                premium_key="TEST-LICENSE-KEY",
                ui=Console(non_interactive=True),
            )
            assert step.check(ctx) is False


class TestPremiumHelpers:
    """Test premium helper functions."""

    def test_get_platform_binary_name_returns_string(self):
        """get_platform_binary_name returns platform-specific name."""
        from installer.steps.premium import get_platform_binary_name

        name = get_platform_binary_name()
        assert isinstance(name, str)
        assert "ccp-premium" in name

    def test_remove_premium_hooks_from_settings(self):
        """remove_premium_hooks_from_settings removes ccp-premium hooks."""
        from installer.steps.premium import remove_premium_hooks_from_settings

        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.local.json"

            # Create settings with premium hooks
            settings = {
                "hooks": {
                    "PreToolUse": [
                        {"hooks": [{"command": "ccp-premium tdd-enforcer"}]}
                    ],
                    "PostToolUse": [
                        {"hooks": [{"command": "ccp-premium context-monitor"}]}
                    ],
                    "Stop": [
                        {"hooks": [{"command": "ccp-premium rules-hook"}]}
                    ]
                }
            }
            settings_file.write_text(json.dumps(settings))

            result = remove_premium_hooks_from_settings(settings_file)
            assert result is True

            # Check hooks were removed
            updated = json.loads(settings_file.read_text())
            # All hook types should be empty/removed since only premium hooks existed
            assert "hooks" not in updated or not updated.get("hooks")


class TestGetPremiumKey:
    """Test PremiumStep._get_premium_key()."""

    def test_get_premium_key_returns_context_key_if_set(self):
        """_get_premium_key returns key from context if already set."""
        from installer.context import InstallContext
        from installer.steps.premium import PremiumStep
        from installer.ui import Console

        step = PremiumStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = InstallContext(
                project_dir=Path(tmpdir),
                premium_key="EXISTING-KEY",
                ui=Console(non_interactive=True),
            )
            assert step._get_premium_key(ctx) == "EXISTING-KEY"

    def test_get_premium_key_returns_existing_if_env_key_set(self):
        """_get_premium_key returns EXISTING when CCP_LICENSE_KEY is already set."""
        from installer.context import InstallContext
        from installer.steps.premium import PremiumStep
        from installer.ui import Console

        step = PremiumStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = InstallContext(
                project_dir=Path(tmpdir),
                premium_key=None,
                ui=Console(non_interactive=True),
            )
            with patch.dict("os.environ", {"CCP_LICENSE_KEY": "ENV-KEY"}):
                assert step._get_premium_key(ctx) == "EXISTING"

    def test_get_premium_key_returns_none_in_non_interactive(self):
        """_get_premium_key returns None in non-interactive mode without key."""
        from installer.context import InstallContext
        from installer.steps.premium import PremiumStep
        from installer.ui import Console

        step = PremiumStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = InstallContext(
                project_dir=Path(tmpdir),
                premium_key=None,
                non_interactive=True,
                ui=Console(non_interactive=True),
            )
            with patch.dict("os.environ", {}, clear=True):
                assert step._get_premium_key(ctx) is None

    def test_get_premium_key_prompts_for_key_directly(self):
        """_get_premium_key prompts for key directly (not yes/no then key)."""
        from installer.context import InstallContext
        from installer.steps.premium import PremiumStep
        from installer.ui import Console

        step = PremiumStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            ui = Console(non_interactive=False)
            ctx = InstallContext(
                project_dir=Path(tmpdir),
                premium_key=None,
                non_interactive=False,
                ui=ui,
            )

            # Mock ui.input to return a license key directly
            with patch.object(ui, "input", return_value="DIRECT-KEY"):
                with patch.dict("os.environ", {}, clear=True):
                    result = step._get_premium_key(ctx)
                    assert result == "DIRECT-KEY"
                    # Verify input was called (not confirm)
                    ui.input.assert_called_once()

    def test_get_premium_key_returns_none_when_user_skips(self):
        """_get_premium_key returns None when user presses Enter to skip."""
        from installer.context import InstallContext
        from installer.steps.premium import PremiumStep
        from installer.ui import Console

        step = PremiumStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            ui = Console(non_interactive=False)
            ctx = InstallContext(
                project_dir=Path(tmpdir),
                premium_key=None,
                non_interactive=False,
                ui=ui,
            )

            # Mock ui.input to return empty string (user pressed Enter to skip)
            with patch.object(ui, "input", return_value=""):
                with patch.dict("os.environ", {}, clear=True):
                    result = step._get_premium_key(ctx)
                    assert result is None


class TestPremiumRun:
    """Test PremiumStep.run()."""

    def test_run_removes_hooks_when_no_premium(self):
        """run() removes premium hooks for non-premium users."""
        from installer.context import InstallContext
        from installer.steps.premium import PremiumStep
        from installer.ui import Console

        step = PremiumStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            claude_dir = project_dir / ".claude"
            claude_dir.mkdir()

            # Create settings with premium hooks
            settings = {
                "hooks": {
                    "PreToolUse": [
                        {"hooks": [{"command": "ccp-premium tdd-enforcer"}]}
                    ]
                }
            }
            settings_file = claude_dir / "settings.local.json"
            settings_file.write_text(json.dumps(settings))

            ctx = InstallContext(
                project_dir=project_dir,
                premium_key=None,
                non_interactive=True,
                ui=Console(non_interactive=True),
            )

            # Clear env var to ensure no license key is found
            with patch.dict(os.environ, {"CCP_LICENSE_KEY": ""}, clear=False):
                step.run(ctx)

            # Check hooks were removed
            updated = json.loads(settings_file.read_text())
            assert "hooks" not in updated or not updated.get("hooks")

    def test_run_validates_license_key(self):
        """run() validates license key with API."""
        from installer.context import InstallContext
        from installer.steps.premium import PremiumStep
        from installer.ui import Console

        step = PremiumStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            ctx = InstallContext(
                project_dir=project_dir,
                premium_key="INVALID-KEY",
                non_interactive=True,
                ui=Console(non_interactive=True),
            )

            # Mock the license validation to fail
            with patch("installer.steps.premium.validate_license_key") as mock_validate:
                mock_validate.return_value = (False, "Invalid license key")
                step.run(ctx)

                mock_validate.assert_called_once_with("INVALID-KEY")

    def test_run_downloads_binary_on_valid_license(self):
        """run() downloads premium binary on valid license."""
        from installer.context import InstallContext
        from installer.steps.premium import PremiumStep
        from installer.ui import Console

        step = PremiumStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            ctx = InstallContext(
                project_dir=project_dir,
                premium_key="VALID-KEY",
                non_interactive=True,
                ui=Console(non_interactive=True),
            )

            # Mock validation and download
            with patch("installer.steps.premium.validate_license_key") as mock_validate:
                mock_validate.return_value = (True, "License valid")
                with patch("installer.steps.premium.download_premium_binary") as mock_download:
                    mock_download.return_value = (True, str(project_dir / ".claude" / "bin" / "ccp-premium"))
                    step.run(ctx)

                    mock_download.assert_called_once()

    def test_run_saves_license_to_env(self):
        """run() saves valid license to .env file."""
        from installer.context import InstallContext
        from installer.steps.premium import PremiumStep
        from installer.ui import Console

        step = PremiumStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            ctx = InstallContext(
                project_dir=project_dir,
                premium_key="VALID-KEY",
                non_interactive=True,
                ui=Console(non_interactive=True),
            )

            # Mock validation and download
            with patch("installer.steps.premium.validate_license_key") as mock_validate:
                mock_validate.return_value = (True, "License valid")
                with patch("installer.steps.premium.download_premium_binary") as mock_download:
                    mock_download.return_value = (True, str(project_dir / ".claude" / "bin" / "ccp-premium"))
                    step.run(ctx)

                    # Check .env file
                    env_file = project_dir / ".env"
                    assert env_file.exists()
                    content = env_file.read_text()
                    assert "CCP_LICENSE_KEY=VALID-KEY" in content
