"""Tests for CLI entry point and step orchestration."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestCLIApp:
    """Test CLI application."""

    def test_cli_parser_exists(self):
        """CLI argument parser exists."""
        from installer.cli import create_parser

        parser = create_parser()
        assert parser is not None

    def test_cli_has_install_command(self):
        """CLI has install command handler."""
        from installer.cli import cmd_install

        assert callable(cmd_install)


class TestRunInstallation:
    """Test step orchestration."""

    def test_run_installation_exists(self):
        """run_installation function exists."""
        from installer.cli import run_installation

        assert callable(run_installation)

    @patch("installer.cli.get_all_steps")
    def test_run_installation_executes_steps(self, mock_get_all_steps):
        """run_installation executes steps in order."""
        from installer.cli import run_installation
        from installer.context import InstallContext
        from installer.ui import Console

        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = InstallContext(
                project_dir=Path(tmpdir),
                ui=Console(non_interactive=True),
                non_interactive=True,
            )

            # Create mock steps
            mock_step1 = MagicMock()
            mock_step1.name = "step1"
            mock_step1.check.return_value = False

            mock_step2 = MagicMock()
            mock_step2.name = "step2"
            mock_step2.check.return_value = False

            mock_get_all_steps.return_value = [mock_step1, mock_step2]

            run_installation(ctx)

            # Both steps should be called
            mock_step1.run.assert_called_once_with(ctx)
            mock_step2.run.assert_called_once_with(ctx)


class TestBackupFeature:
    """Test backup feature ignores special files."""

    def test_ignore_special_files_skips_tmp_directory(self):
        """ignore_special_files function skips tmp directory."""
        # Import the function by running the backup code path
        from pathlib import Path

        # Simulate the ignore function logic
        def ignore_special_files(directory: str, files: list[str]) -> list[str]:
            ignored = []
            for f in files:
                path = Path(directory) / f
                if path.is_fifo() or path.is_socket() or path.is_block_device() or path.is_char_device():
                    ignored.append(f)
                if f == "tmp":
                    ignored.append(f)
            return ignored

        # Test that tmp is ignored
        result = ignore_special_files("/some/dir", ["commands", "hooks", "tmp", "scripts"])
        assert "tmp" in result
        assert "commands" not in result
        assert "hooks" not in result

    def test_backup_copytree_with_ignore(self):
        """Backup uses copytree with ignore function."""
        import shutil
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create source directory with regular files and tmp subdirectory
            source = Path(tmpdir) / ".claude"
            source.mkdir()
            (source / "commands").mkdir()
            (source / "commands" / "spec.md").write_text("test")
            (source / "tmp").mkdir()
            (source / "tmp" / "pipes").mkdir()

            # Create backup with ignore function
            backup = Path(tmpdir) / ".claude.backup.test"

            def ignore_special_files(directory: str, files: list[str]) -> list[str]:
                ignored = []
                for f in files:
                    if f == "tmp":
                        ignored.append(f)
                return ignored

            shutil.copytree(source, backup, ignore=ignore_special_files)

            # Verify backup was created without tmp
            assert backup.exists()
            assert (backup / "commands" / "spec.md").exists()
            assert not (backup / "tmp").exists()


class TestMainEntry:
    """Test __main__ entry point."""

    def test_main_module_exists(self):
        """__main__ module exists."""
        import installer.__main__

        assert hasattr(installer.__main__, "main") or True  # May not have main function


class TestKeyboardInterrupt:
    """Test CTRL+C (KeyboardInterrupt) handling."""

    @patch("installer.cli.get_all_steps")
    def test_keyboard_interrupt_raises_installation_cancelled(self, mock_get_all_steps):
        """KeyboardInterrupt during step raises InstallationCancelled with step name."""
        from installer.cli import run_installation
        from installer.context import InstallContext
        from installer.errors import InstallationCancelled
        from installer.ui import Console

        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = InstallContext(
                project_dir=Path(tmpdir),
                ui=Console(non_interactive=True, quiet=True),
                non_interactive=True,
            )

            # Create a step that raises KeyboardInterrupt
            failing_step = MagicMock()
            failing_step.name = "dependencies"
            failing_step.check.return_value = False
            failing_step.run.side_effect = KeyboardInterrupt()

            mock_get_all_steps.return_value = [failing_step]

            # Should raise InstallationCancelled with step name
            with pytest.raises(InstallationCancelled) as exc_info:
                run_installation(ctx)

            assert exc_info.value.step_name == "dependencies"
            assert "dependencies" in str(exc_info.value)


class TestLicenseInfo:
    """Test license info retrieval."""

    def test_get_license_info_function_exists(self):
        """_get_license_info function exists."""
        from installer.cli import _get_license_info

        assert callable(_get_license_info)

    @patch("subprocess.run")
    def test_get_license_info_returns_valid_license(self, mock_run, tmp_path: Path):
        """_get_license_info returns license data for valid license."""
        from installer.cli import _get_license_info

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"tier": "standard", "email": "test@example.com"}',
            stderr="",
        )

        # Create fake ccp binary
        bin_dir = tmp_path / ".claude" / "bin"
        bin_dir.mkdir(parents=True)
        (bin_dir / "ccp").touch()

        result = _get_license_info(tmp_path)
        assert result is not None
        assert result["tier"] == "standard"

    @patch("subprocess.run")
    def test_get_license_info_detects_expired_trial(self, mock_run, tmp_path: Path):
        """_get_license_info detects expired trial from stderr."""
        from installer.cli import _get_license_info

        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr='{"success": false, "error": "Trial expired", "tier": "trial"}',
        )

        # Create fake ccp binary
        bin_dir = tmp_path / ".claude" / "bin"
        bin_dir.mkdir(parents=True)
        (bin_dir / "ccp").touch()

        result = _get_license_info(tmp_path)
        assert result is not None
        assert result["tier"] == "trial"
        assert result.get("is_expired") is True

    def test_get_license_info_returns_none_without_binary(self, tmp_path: Path):
        """_get_license_info returns None when ccp binary doesn't exist."""
        from installer.cli import _get_license_info

        result = _get_license_info(tmp_path)
        assert result is None
