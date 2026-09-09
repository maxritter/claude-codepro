"""Tests for Pilot's complete Impeccable installation."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch


class TestInstallImpeccable:
    """Impeccable CLI and skill bundle are separately pinned."""

    @patch("installer.steps.dependencies.subprocess.run")
    @patch("installer.steps.dependencies._download_verified_manifest_file", return_value=True)
    @patch("installer.steps.dependencies.shutil.which", return_value="/usr/local/bin/impeccable")
    @patch("installer.steps.dependencies.is_codex_installed", return_value=True)
    @patch("installer.steps.dependencies.is_claude_installed", return_value=True)
    @patch("installer.steps.dependencies.npm_global_cmd", side_effect=lambda value: value)
    @patch("installer.steps.dependencies._run_bash_with_retry", return_value=True)
    @patch("installer.steps.dependencies.command_exists", return_value=False)
    def test_installs_cli_and_verified_complete_bundle(
        self,
        _command_exists: MagicMock,
        npm_install: MagicMock,
        _npm_global: MagicMock,
        _claude: MagicMock,
        _codex: MagicMock,
        _which: MagicMock,
        download: MagicMock,
        run: MagicMock,
        tmp_path: Path,
    ) -> None:
        from installer.steps.dependencies import install_impeccable

        run.return_value.returncode = 0

        assert install_impeccable(tmp_path) is True

        assert "impeccable@" in str(npm_install.call_args)
        assert download.call_args.args[0] == "impeccable-skill-bundle"
        command = run.call_args.args[0]
        assert command == [
            "/usr/local/bin/impeccable",
            "install",
            "--yes",
            "--providers=claude,codex",
            "--scope=global",
            "--no-hooks",
        ]
        assert run.call_args.kwargs["cwd"] == tmp_path
        assert run.call_args.kwargs["shell"] is False
        assert "IMPECCABLE_BUNDLE_PATH" in run.call_args.kwargs["env"]

    @patch("installer.steps.dependencies.npm_global_cmd", side_effect=lambda value: value)
    @patch("installer.steps.dependencies._run_bash_with_retry", return_value=False)
    @patch("installer.steps.dependencies.command_exists", return_value=False)
    def test_returns_false_when_cli_install_fails(
        self,
        _command_exists: MagicMock,
        _run: MagicMock,
        _npm_global: MagicMock,
        tmp_path: Path,
    ) -> None:
        from installer.steps.dependencies import install_impeccable

        assert install_impeccable(tmp_path) is False

    @patch("installer.steps.dependencies._download_verified_manifest_file", return_value=False)
    @patch("installer.steps.dependencies.shutil.which", return_value="/usr/local/bin/impeccable")
    @patch("installer.steps.dependencies.is_codex_installed", return_value=True)
    @patch("installer.steps.dependencies.is_claude_installed", return_value=False)
    @patch("installer.steps.dependencies.npm_global_cmd", side_effect=lambda value: value)
    @patch("installer.steps.dependencies._run_bash_with_retry", return_value=True)
    @patch("installer.steps.dependencies.command_exists", return_value=True)
    def test_fails_closed_when_skill_bundle_cannot_be_verified(
        self,
        _command_exists: MagicMock,
        _run: MagicMock,
        _npm_global: MagicMock,
        _claude: MagicMock,
        _codex: MagicMock,
        _which: MagicMock,
        _download: MagicMock,
        tmp_path: Path,
    ) -> None:
        from installer.steps.dependencies import install_impeccable

        assert install_impeccable(tmp_path) is False
