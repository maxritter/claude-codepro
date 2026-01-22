"""Tests for the CCP binary download step."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from installer.context import InstallContext
from installer.steps.ccp_binary import (
    CcpBinaryStep,
    _download_ccp_artifacts,
    _download_file,
    _get_installed_version,
    _get_local_so_name,
    _get_platform_suffix,
)


class TestGetPlatformSuffix:
    """Tests for _get_platform_suffix function."""

    @patch("installer.steps.ccp_binary.platform")
    def test_linux_x86_64(self, mock_platform: MagicMock) -> None:
        mock_platform.system.return_value = "Linux"
        mock_platform.machine.return_value = "x86_64"
        assert _get_platform_suffix() == "linux-x86_64"

    @patch("installer.steps.ccp_binary.platform")
    def test_linux_amd64(self, mock_platform: MagicMock) -> None:
        mock_platform.system.return_value = "Linux"
        mock_platform.machine.return_value = "amd64"
        assert _get_platform_suffix() == "linux-x86_64"

    @patch("installer.steps.ccp_binary.platform")
    def test_linux_arm64(self, mock_platform: MagicMock) -> None:
        mock_platform.system.return_value = "Linux"
        mock_platform.machine.return_value = "arm64"
        assert _get_platform_suffix() == "linux-arm64"

    @patch("installer.steps.ccp_binary.platform")
    def test_linux_aarch64(self, mock_platform: MagicMock) -> None:
        mock_platform.system.return_value = "Linux"
        mock_platform.machine.return_value = "aarch64"
        assert _get_platform_suffix() == "linux-arm64"

    @patch("installer.steps.ccp_binary.platform")
    def test_darwin_x86_64(self, mock_platform: MagicMock) -> None:
        mock_platform.system.return_value = "Darwin"
        mock_platform.machine.return_value = "x86_64"
        assert _get_platform_suffix() == "darwin-x86_64"

    @patch("installer.steps.ccp_binary.platform")
    def test_darwin_arm64(self, mock_platform: MagicMock) -> None:
        mock_platform.system.return_value = "Darwin"
        mock_platform.machine.return_value = "arm64"
        assert _get_platform_suffix() == "darwin-arm64"

    @patch("installer.steps.ccp_binary.platform")
    def test_windows_returns_none(self, mock_platform: MagicMock) -> None:
        mock_platform.system.return_value = "Windows"
        mock_platform.machine.return_value = "AMD64"
        assert _get_platform_suffix() is None

    @patch("installer.steps.ccp_binary.platform")
    def test_unsupported_arch_returns_none(self, mock_platform: MagicMock) -> None:
        mock_platform.system.return_value = "Linux"
        mock_platform.machine.return_value = "i386"
        assert _get_platform_suffix() is None


class TestGetLocalSoName:
    """Tests for _get_local_so_name function."""

    @patch("installer.steps.ccp_binary.sys")
    @patch("installer.steps.ccp_binary.platform")
    def test_linux_x86_64_cpython312(self, mock_platform: MagicMock, mock_sys: MagicMock) -> None:
        mock_platform.system.return_value = "Linux"
        mock_platform.machine.return_value = "x86_64"
        mock_sys.implementation.name = "cpython"
        mock_sys.version_info.major = 3
        mock_sys.version_info.minor = 12
        assert _get_local_so_name() == "ccp.cpython-312-x86_64-linux-gnu.so"

    @patch("installer.steps.ccp_binary.sys")
    @patch("installer.steps.ccp_binary.platform")
    def test_linux_arm64_cpython312(self, mock_platform: MagicMock, mock_sys: MagicMock) -> None:
        mock_platform.system.return_value = "Linux"
        mock_platform.machine.return_value = "aarch64"
        mock_sys.implementation.name = "cpython"
        mock_sys.version_info.major = 3
        mock_sys.version_info.minor = 12
        assert _get_local_so_name() == "ccp.cpython-312-aarch64-linux-gnu.so"

    @patch("installer.steps.ccp_binary.sys")
    @patch("installer.steps.ccp_binary.platform")
    def test_darwin_arm64_cpython312(self, mock_platform: MagicMock, mock_sys: MagicMock) -> None:
        mock_platform.system.return_value = "Darwin"
        mock_platform.machine.return_value = "arm64"
        mock_sys.implementation.name = "cpython"
        mock_sys.version_info.major = 3
        mock_sys.version_info.minor = 12
        assert _get_local_so_name() == "ccp.cpython-312-darwin.so"


class TestDownloadFile:
    """Tests for _download_file function."""

    @patch("installer.steps.ccp_binary.platform")
    @patch("installer.steps.ccp_binary.httpx.Client")
    def test_successful_download(
        self, mock_client_class: MagicMock, mock_platform: MagicMock, tmp_path: Path
    ) -> None:
        mock_platform.system.return_value = "Linux"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-length": "14"}
        mock_response.iter_bytes.return_value = iter([b"binary content"])
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=None)

        mock_client = MagicMock()
        mock_client.stream.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=None)
        mock_client_class.return_value = mock_client

        dest = tmp_path / "test_binary"
        result = _download_file("https://example.com/binary", dest)

        assert result is True
        assert dest.exists()
        assert dest.read_bytes() == b"binary content"

    @patch("installer.steps.ccp_binary.httpx.Client")
    def test_failed_download_404(self, mock_client_class: MagicMock, tmp_path: Path) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=None)

        mock_client = MagicMock()
        mock_client.stream.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=None)
        mock_client_class.return_value = mock_client

        dest = tmp_path / "test_binary"
        result = _download_file("https://example.com/binary", dest)

        assert result is False
        assert not dest.exists()


class TestDownloadCcpArtifacts:
    """Tests for _download_ccp_artifacts function."""

    @patch("installer.steps.ccp_binary._download_file")
    @patch("installer.steps.ccp_binary._get_local_so_name")
    @patch("installer.steps.ccp_binary._get_platform_suffix")
    def test_downloads_both_artifacts(
        self,
        mock_suffix: MagicMock,
        mock_so_name: MagicMock,
        mock_download: MagicMock,
        tmp_path: Path,
    ) -> None:
        mock_suffix.return_value = "linux-x86_64"
        mock_so_name.return_value = "ccp.cpython-312-x86_64-linux-gnu.so"
        mock_download.return_value = True

        result = _download_ccp_artifacts("5.1.2", tmp_path)

        assert result is True
        assert mock_download.call_count == 2
        # First call: .so module
        so_call = mock_download.call_args_list[0]
        assert "ccp-linux-x86_64.so" in so_call[0][0]
        assert so_call[0][1] == tmp_path / "ccp.cpython-312-x86_64-linux-gnu.so"
        # Second call: wrapper
        wrapper_call = mock_download.call_args_list[1]
        assert "ccp-wrapper" in wrapper_call[0][0]
        assert wrapper_call[0][1] == tmp_path / "ccp"

    @patch("installer.steps.ccp_binary._get_platform_suffix")
    def test_unsupported_platform_returns_false(
        self, mock_suffix: MagicMock, tmp_path: Path
    ) -> None:
        mock_suffix.return_value = None
        result = _download_ccp_artifacts("5.1.2", tmp_path)
        assert result is False

    @patch("installer.steps.ccp_binary._download_file")
    @patch("installer.steps.ccp_binary._get_local_so_name")
    @patch("installer.steps.ccp_binary._get_platform_suffix")
    def test_so_download_failure(
        self,
        mock_suffix: MagicMock,
        mock_so_name: MagicMock,
        mock_download: MagicMock,
        tmp_path: Path,
    ) -> None:
        mock_suffix.return_value = "linux-x86_64"
        mock_so_name.return_value = "ccp.cpython-312-x86_64-linux-gnu.so"
        mock_download.return_value = False

        result = _download_ccp_artifacts("5.1.2", tmp_path)
        assert result is False

    @patch("installer.steps.ccp_binary._download_file")
    @patch("installer.steps.ccp_binary._get_local_so_name")
    @patch("installer.steps.ccp_binary._get_platform_suffix")
    def test_wrapper_download_failure_cleans_so(
        self,
        mock_suffix: MagicMock,
        mock_so_name: MagicMock,
        mock_download: MagicMock,
        tmp_path: Path,
    ) -> None:
        mock_suffix.return_value = "linux-x86_64"
        mock_so_name.return_value = "ccp.cpython-312-x86_64-linux-gnu.so"
        # First download (so) succeeds, second (wrapper) fails
        mock_download.side_effect = [True, False]

        # Create the .so file to simulate successful first download
        so_path = tmp_path / "ccp.cpython-312-x86_64-linux-gnu.so"
        so_path.write_bytes(b"fake so content")

        result = _download_ccp_artifacts("5.1.2", tmp_path)

        assert result is False
        # .so should be cleaned up
        assert not so_path.exists()


class TestGetInstalledVersion:
    """Tests for _get_installed_version function."""

    @patch("installer.steps.ccp_binary.subprocess.run")
    def test_returns_version_from_output(self, mock_run: MagicMock, tmp_path: Path) -> None:
        ccp_path = tmp_path / "ccp"
        ccp_path.write_text("#!/bin/bash\necho 'Claude CodePro v5.1.2'")
        mock_run.return_value = MagicMock(returncode=0, stdout="Claude CodePro v5.1.2")

        result = _get_installed_version(ccp_path)
        assert result == "5.1.2"

    @patch("installer.steps.ccp_binary.subprocess.run")
    def test_returns_none_on_failure(self, mock_run: MagicMock, tmp_path: Path) -> None:
        ccp_path = tmp_path / "ccp"
        ccp_path.write_text("#!/bin/bash\nexit 1")
        mock_run.return_value = MagicMock(returncode=1, stdout="")

        result = _get_installed_version(ccp_path)
        assert result is None

    def test_returns_none_if_not_exists(self, tmp_path: Path) -> None:
        ccp_path = tmp_path / "nonexistent"
        result = _get_installed_version(ccp_path)
        assert result is None


class TestCcpBinaryStep:
    """Tests for CcpBinaryStep class."""

    def _make_context(self, tmp_path: Path) -> InstallContext:
        return InstallContext(
            project_dir=tmp_path,
            ui=None,
            config={},
        )

    def test_check_returns_false_if_ccp_missing(self, tmp_path: Path) -> None:
        ctx = self._make_context(tmp_path)
        step = CcpBinaryStep()
        assert step.check(ctx) is False

    @patch("installer.steps.ccp_binary.INSTALLER_VERSION", "5.1.2")
    @patch("installer.steps.ccp_binary._get_installed_version")
    def test_check_returns_true_if_version_matches(
        self, mock_version: MagicMock, tmp_path: Path
    ) -> None:
        ctx = self._make_context(tmp_path)
        ccp_path = tmp_path / ".claude" / "bin" / "ccp"
        ccp_path.parent.mkdir(parents=True)
        ccp_path.write_text("#!/bin/bash")
        mock_version.return_value = "5.1.2"

        step = CcpBinaryStep()
        assert step.check(ctx) is True

    @patch("installer.steps.ccp_binary.INSTALLER_VERSION", "5.1.2")
    @patch("installer.steps.ccp_binary._get_installed_version")
    def test_check_returns_false_if_version_differs(
        self, mock_version: MagicMock, tmp_path: Path
    ) -> None:
        ctx = self._make_context(tmp_path)
        ccp_path = tmp_path / ".claude" / "bin" / "ccp"
        ccp_path.parent.mkdir(parents=True)
        ccp_path.write_text("#!/bin/bash")
        mock_version.return_value = "5.1.0"

        step = CcpBinaryStep()
        assert step.check(ctx) is False

    @patch("installer.steps.ccp_binary.INSTALLER_VERSION", "5.1.2")
    @patch("installer.steps.ccp_binary._download_ccp_artifacts")
    @patch("installer.steps.ccp_binary._get_installed_version")
    def test_run_downloads_binary(
        self, mock_version: MagicMock, mock_download: MagicMock, tmp_path: Path
    ) -> None:
        ctx = self._make_context(tmp_path)
        mock_version.return_value = None
        mock_download.return_value = True

        step = CcpBinaryStep()
        step.run(ctx)

        mock_download.assert_called_once()
        call_args = mock_download.call_args[0]
        assert call_args[0] == "5.1.2"
        assert call_args[1] == tmp_path / ".claude" / "bin"

    @patch("installer.steps.ccp_binary.INSTALLER_VERSION", None)
    def test_run_skips_if_no_version(self, tmp_path: Path) -> None:
        ctx = self._make_context(tmp_path)
        ctx.config = {}

        step = CcpBinaryStep()
        step.run(ctx)  # Should not raise

    def test_rollback_is_noop(self, tmp_path: Path) -> None:
        ctx = self._make_context(tmp_path)
        step = CcpBinaryStep()
        step.rollback(ctx)  # Should not raise
