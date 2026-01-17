"""Tests for CCP updater module."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestGetLatestVersion:
    """Test get_latest_version function."""

    @patch("httpx.Client")
    def test_get_latest_version_returns_version_from_github_api(self, mock_client_class):
        """get_latest_version fetches version from GitHub releases API."""
        from ccp.updater import get_latest_version

        mock_client = MagicMock()
        mock_client_class.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client_class.return_value.__exit__ = MagicMock(return_value=False)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"tag_name": "v4.5.9"}
        mock_client.get.return_value = mock_response

        version = get_latest_version()

        assert version == "4.5.9"

    @patch("httpx.Client")
    def test_get_latest_version_strips_v_prefix(self, mock_client_class):
        """get_latest_version strips 'v' prefix from tag."""
        from ccp.updater import get_latest_version

        mock_client = MagicMock()
        mock_client_class.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client_class.return_value.__exit__ = MagicMock(return_value=False)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"tag_name": "v1.2.3"}
        mock_client.get.return_value = mock_response

        version = get_latest_version()

        assert version == "1.2.3"

    @patch("httpx.Client")
    def test_get_latest_version_returns_none_on_network_error(self, mock_client_class):
        """get_latest_version returns None on network error."""
        import httpx

        from ccp.updater import get_latest_version

        mock_client_class.return_value.__enter__ = MagicMock(side_effect=httpx.HTTPError("Network error"))
        mock_client_class.return_value.__exit__ = MagicMock(return_value=False)

        version = get_latest_version()

        assert version is None

    @patch("httpx.Client")
    def test_get_latest_version_returns_none_on_non_200_status(self, mock_client_class):
        """get_latest_version returns None on non-200 status."""
        from ccp.updater import get_latest_version

        mock_client = MagicMock()
        mock_client_class.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client_class.return_value.__exit__ = MagicMock(return_value=False)

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_client.get.return_value = mock_response

        version = get_latest_version()

        assert version is None


class TestCheckForUpdate:
    """Test check_for_update function."""

    @patch("ccp.updater.get_latest_version")
    def test_check_for_update_returns_true_when_update_available(self, mock_get_latest):
        """check_for_update returns (True, current, latest) when update available."""
        from ccp.updater import check_for_update

        mock_get_latest.return_value = "4.6.0"

        with patch("ccp.updater.__version__", "4.5.8"):
            has_update, current, latest = check_for_update()

        assert has_update is True
        assert current == "4.5.8"
        assert latest == "4.6.0"

    @patch("ccp.updater.get_latest_version")
    def test_check_for_update_returns_false_when_up_to_date(self, mock_get_latest):
        """check_for_update returns (False, current, latest) when up to date."""
        from ccp.updater import check_for_update

        mock_get_latest.return_value = "4.5.8"

        with patch("ccp.updater.__version__", "4.5.8"):
            has_update, current, latest = check_for_update()

        assert has_update is False

    @patch("ccp.updater.get_latest_version")
    def test_check_for_update_returns_false_when_current_is_newer(self, mock_get_latest):
        """check_for_update returns False when current version is newer (dev build)."""
        from ccp.updater import check_for_update

        mock_get_latest.return_value = "4.5.8"

        with patch("ccp.updater.__version__", "4.6.0"):
            has_update, current, latest = check_for_update()

        assert has_update is False

    @patch("ccp.updater.get_latest_version")
    def test_check_for_update_returns_none_on_network_error(self, mock_get_latest):
        """check_for_update returns (None, current, None) on network error."""
        from ccp.updater import check_for_update

        mock_get_latest.return_value = None

        with patch("ccp.updater.__version__", "4.5.8"):
            has_update, current, latest = check_for_update()

        assert has_update is None
        assert current == "4.5.8"
        assert latest is None


class TestVersionComparison:
    """Test version comparison logic."""

    def test_compare_versions_major_difference(self):
        """Version comparison handles major version differences."""
        from ccp.updater import _is_newer_version

        assert _is_newer_version("5.0.0", "4.5.8") is True
        assert _is_newer_version("4.5.8", "5.0.0") is False

    def test_compare_versions_minor_difference(self):
        """Version comparison handles minor version differences."""
        from ccp.updater import _is_newer_version

        assert _is_newer_version("4.6.0", "4.5.8") is True
        assert _is_newer_version("4.5.8", "4.6.0") is False

    def test_compare_versions_patch_difference(self):
        """Version comparison handles patch version differences."""
        from ccp.updater import _is_newer_version

        assert _is_newer_version("4.5.9", "4.5.8") is True
        assert _is_newer_version("4.5.8", "4.5.9") is False

    def test_compare_versions_equal(self):
        """Version comparison returns False for equal versions."""
        from ccp.updater import _is_newer_version

        assert _is_newer_version("4.5.8", "4.5.8") is False


class TestDownloadInstaller:
    """Test download_installer function."""

    @patch("ccp.updater._get_installer_files")
    @patch("httpx.Client")
    def test_download_installer_creates_directory(self, mock_client_class, mock_get_files):
        """download_installer creates the installer directory."""
        from ccp.updater import download_installer

        mock_get_files.return_value = ["installer/__init__.py"]

        mock_client = MagicMock()
        mock_client_class.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client_class.return_value.__exit__ = MagicMock(return_value=False)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"# Python code"
        mock_client.get.return_value = mock_response

        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            result = download_installer("4.5.9", project_dir)

            installer_dir = project_dir / ".claude" / "installer"
            assert installer_dir.exists()

    @patch("ccp.updater._get_installer_files")
    @patch("httpx.Client")
    def test_download_installer_returns_true_on_success(self, mock_client_class, mock_get_files):
        """download_installer returns True on successful download."""
        from ccp.updater import download_installer

        mock_get_files.return_value = ["installer/__init__.py"]

        mock_client = MagicMock()
        mock_client_class.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client_class.return_value.__exit__ = MagicMock(return_value=False)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"# Python code"
        mock_client.get.return_value = mock_response

        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            result = download_installer("4.5.9", project_dir)

            assert result is True

    @patch("ccp.updater._get_installer_files")
    def test_download_installer_returns_false_when_no_files_found(self, mock_get_files):
        """download_installer returns False when API returns no files."""
        from ccp.updater import download_installer

        mock_get_files.return_value = []

        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            result = download_installer("4.5.9", project_dir)

            assert result is False


class TestRunInstaller:
    """Test run_installer function."""

    @patch("subprocess.run")
    def test_run_installer_calls_python_module(self, mock_run):
        """run_installer calls uv run python -m installer."""
        from ccp.updater import run_installer

        mock_run.return_value = MagicMock(returncode=0)

        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            success, error = run_installer(project_dir)

        assert success is True
        assert error == ""
        mock_run.assert_called_once()

        call_args = mock_run.call_args[0][0]
        assert "uv" in call_args
        assert "python" in call_args
        assert "-m" in call_args
        assert "installer" in call_args

    @patch("subprocess.run")
    def test_run_installer_returns_false_on_failure(self, mock_run):
        """run_installer returns False with error message on subprocess failure."""
        from ccp.updater import run_installer

        mock_run.return_value = MagicMock(returncode=1, stderr="Some error", stdout="")

        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            success, error = run_installer(project_dir)

        assert success is False
        assert "Some error" in error
