"""Tests for Prerequisites installation step."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch


class TestPrerequisitesStep:
    """Test PrerequisitesStep class."""

    def test_prerequisites_step_has_correct_name(self):
        """PrerequisitesStep has name 'prerequisites'."""
        from installer.steps.prerequisites import PrerequisitesStep

        step = PrerequisitesStep()
        assert step.name == "prerequisites"

    def test_prerequisites_step_runs_when_packages_missing(self):
        """PrerequisitesStep.check returns False when packages are missing."""
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

            with patch("installer.steps.prerequisites.is_homebrew_available", return_value=True):
                with patch("installer.steps.prerequisites.command_exists", return_value=False):
                    assert step.check(ctx) is False

    @patch("installer.steps.prerequisites._node_at_least_24", return_value=True)
    def test_prerequisites_step_skips_when_all_packages_installed(self, _mock_node):
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

            with patch("installer.steps.prerequisites.is_homebrew_available", return_value=True):
                with patch("installer.steps.prerequisites.command_exists", return_value=True):
                    with patch("installer.steps.prerequisites._is_nvm_installed", return_value=True):
                        with patch("installer.steps.prerequisites._get_outdated_homebrew_packages", return_value=set()):
                            assert step.check(ctx) is True


class TestPrerequisitesStepRun:
    """Test PrerequisitesStep.run() method."""

    @patch("installer.steps.prerequisites._install_homebrew_package")
    @patch("installer.steps.prerequisites._add_bun_tap")
    @patch("installer.steps.prerequisites._is_nvm_installed")
    @patch("installer.steps.prerequisites.command_exists")
    @patch("installer.steps.prerequisites.is_homebrew_available")
    def test_prerequisites_run_installs_missing_packages(
        self, mock_homebrew_available, mock_cmd_exists, mock_nvm_installed, mock_tap, mock_install
    ):
        """PrerequisitesStep.run installs packages that are missing."""
        from installer.context import InstallContext
        from installer.steps.prerequisites import HOMEBREW_PACKAGES, PrerequisitesStep
        from installer.ui import Console

        mock_homebrew_available.return_value = True
        mock_cmd_exists.return_value = False
        mock_nvm_installed.return_value = False
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

    @patch("installer.steps.prerequisites._upgrade_homebrew_package")
    @patch("installer.steps.prerequisites._get_outdated_homebrew_packages")
    @patch("installer.steps.prerequisites._install_homebrew_package")
    @patch("installer.steps.prerequisites._add_bun_tap")
    @patch("installer.steps.prerequisites._is_nvm_installed")
    @patch("installer.steps.prerequisites.command_exists")
    @patch("installer.steps.prerequisites.is_homebrew_available")
    @patch("installer.steps.prerequisites._node_at_least_24", return_value=True)
    def test_prerequisites_run_skips_installed_packages(
        self,
        _mock_node,
        mock_homebrew_available,
        mock_cmd_exists,
        mock_nvm_installed,
        mock_tap,
        mock_install,
        mock_outdated,
        mock_upgrade,
    ):
        """PrerequisitesStep.run skips packages that are already installed and up-to-date."""
        from installer.context import InstallContext
        from installer.steps.prerequisites import PrerequisitesStep
        from installer.ui import Console

        mock_homebrew_available.return_value = True
        mock_cmd_exists.return_value = True
        mock_nvm_installed.return_value = True
        mock_tap.return_value = True
        mock_install.return_value = True
        mock_outdated.return_value = set()

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
            mock_upgrade.assert_not_called()


class TestPrerequisitesHelpers:
    """Test Prerequisites helper functions."""

    def test_homebrew_packages_list_exists(self):
        """HOMEBREW_PACKAGES constant exists and contains expected packages."""
        from installer.steps.prerequisites import HOMEBREW_PACKAGES

        assert isinstance(HOMEBREW_PACKAGES, list)
        assert "git" in HOMEBREW_PACKAGES
        assert "gh" in HOMEBREW_PACKAGES
        assert "python@3.12" in HOMEBREW_PACKAGES
        assert "node@24" in HOMEBREW_PACKAGES
        assert "bun" in HOMEBREW_PACKAGES
        assert "uv" in HOMEBREW_PACKAGES
        assert "go" in HOMEBREW_PACKAGES
        assert "ripgrep" in HOMEBREW_PACKAGES
        assert "ast-grep" in HOMEBREW_PACKAGES

    def test_get_command_for_package_maps_ripgrep_to_rg(self):
        """_get_command_for_package returns 'rg' for ripgrep package."""
        from installer.steps.prerequisites import _get_command_for_package

        assert _get_command_for_package("ripgrep") == "rg"

    def test_get_command_for_package_keeps_ast_grep_binary_name(self):
        from installer.steps.prerequisites import _get_command_for_package

        assert _get_command_for_package("ast-grep") == "ast-grep"

    @patch("installer.steps.prerequisites.is_linux")
    @patch("installer.steps.prerequisites.is_apt_available")
    def test_install_ripgrep_via_apt_skips_on_non_linux(self, mock_apt, mock_linux):
        """_install_ripgrep_via_apt returns False on non-Linux systems."""
        from installer.steps.prerequisites import _install_ripgrep_via_apt

        mock_linux.return_value = False
        mock_apt.return_value = True

        result = _install_ripgrep_via_apt()
        assert result is False

    @patch("installer.steps.prerequisites.is_linux")
    @patch("installer.steps.prerequisites.is_apt_available")
    def test_install_ripgrep_via_apt_skips_without_apt(self, mock_apt, mock_linux):
        """_install_ripgrep_via_apt returns False when apt not available."""
        from installer.steps.prerequisites import _install_ripgrep_via_apt

        mock_linux.return_value = True
        mock_apt.return_value = False

        result = _install_ripgrep_via_apt()
        assert result is False

    @patch("subprocess.run")
    @patch("installer.steps.prerequisites.is_linux")
    @patch("installer.steps.prerequisites.is_apt_available")
    def test_install_ripgrep_via_apt_runs_with_sudo_n_and_devnull_stdin(self, mock_apt, mock_linux, mock_run):
        """_install_ripgrep_via_apt uses sudo -n and stdin=DEVNULL to prevent hanging."""
        from installer.steps.prerequisites import _install_ripgrep_via_apt

        mock_linux.return_value = True
        mock_apt.return_value = True
        mock_run.return_value = MagicMock(returncode=0)

        result = _install_ripgrep_via_apt()

        assert result is True
        assert mock_run.call_count == 2
        first_call = mock_run.call_args_list[0]
        assert "update" in first_call[0][0]
        assert "sudo" in first_call[0][0]
        assert "-n" in first_call[0][0]
        second_call = mock_run.call_args_list[1]
        assert "install" in second_call[0][0]
        assert "ripgrep" in second_call[0][0]
        assert second_call[1].get("stdin") == subprocess.DEVNULL
        assert second_call[1].get("timeout") is not None

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

    @patch("installer.steps.prerequisites._verify_homebrew_tap", return_value=True)
    @patch("subprocess.run")
    def test_install_homebrew_package_runs_brew_install(self, mock_run, _mock_verify):
        """_install_homebrew_package runs brew install after tap verification."""
        from installer.steps.prerequisites import _install_homebrew_package

        mock_run.return_value = MagicMock(returncode=0)

        result = _install_homebrew_package("git")

        assert result is True
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "brew" in call_args
        assert "install" in call_args
        assert "git" in call_args

    @patch("installer.steps.prerequisites._verify_homebrew_tap", return_value=True)
    @patch("subprocess.run")
    def test_install_bun_uses_the_manifest_tap_qualified_formula(self, mock_run, _mock_verify):
        from installer.steps.prerequisites import _install_homebrew_package

        mock_run.return_value = MagicMock(returncode=0)

        assert _install_homebrew_package("bun") is True
        assert mock_run.call_args.args[0] == ["brew", "install", "oven-sh/bun/bun"]

    @patch("installer.steps.prerequisites._verify_homebrew_tap", return_value=False)
    @patch("subprocess.run")
    def test_install_homebrew_package_refuses_unexpected_tap(self, mock_run, _mock_verify):
        """_install_homebrew_package refuses to run brew install when tap mismatches."""
        from installer.steps.prerequisites import _install_homebrew_package

        result = _install_homebrew_package("git")

        assert result is False
        mock_run.assert_not_called()

    @patch("os.path.exists")
    def test_ensure_homebrew_in_path_adds_brew_path(self, mock_exists):
        """_ensure_homebrew_in_path adds Homebrew bin to PATH when missing."""
        import os

        from installer.steps.prerequisites import _ensure_homebrew_in_path

        mock_exists.side_effect = lambda p: p == "/opt/homebrew/bin/brew"
        original_path = os.environ.get("PATH", "")

        os.environ["PATH"] = "/usr/bin:/bin"
        try:
            _ensure_homebrew_in_path()
            assert "/opt/homebrew/bin" in os.environ["PATH"]
        finally:
            os.environ["PATH"] = original_path

    @patch("os.path.exists")
    def test_ensure_homebrew_in_path_skips_if_already_present(self, mock_exists):
        """_ensure_homebrew_in_path does nothing if brew path already in PATH."""
        import os

        from installer.steps.prerequisites import _ensure_homebrew_in_path

        mock_exists.side_effect = lambda p: p == "/opt/homebrew/bin/brew"
        original_path = os.environ.get("PATH", "")

        os.environ["PATH"] = "/opt/homebrew/bin:/usr/bin:/bin"
        try:
            _ensure_homebrew_in_path()
            assert os.environ["PATH"].count("/opt/homebrew/bin") == 1
        finally:
            os.environ["PATH"] = original_path


class TestEnsureGitInstalled:
    """Test _ensure_git_installed function."""

    @patch("installer.steps.prerequisites.command_exists")
    def test_returns_true_when_git_already_exists(self, mock_cmd):
        from installer.steps.prerequisites import _ensure_git_installed

        mock_cmd.return_value = True
        assert _ensure_git_installed() is True

    @patch("installer.steps.prerequisites.is_linux")
    @patch("installer.steps.prerequisites.command_exists")
    def test_returns_false_on_non_linux(self, mock_cmd, mock_linux):
        from installer.steps.prerequisites import _ensure_git_installed

        mock_cmd.return_value = False
        mock_linux.return_value = False
        assert _ensure_git_installed() is False

    @patch("subprocess.run")
    @patch("installer.steps.prerequisites.is_dnf_available")
    @patch("installer.steps.prerequisites.is_linux")
    @patch("installer.steps.prerequisites.command_exists")
    def test_uses_dnf_on_rhel_based(self, mock_cmd, mock_linux, mock_dnf, mock_run):
        from installer.steps.prerequisites import _ensure_git_installed

        mock_cmd.side_effect = [False, True]
        mock_linux.return_value = True
        mock_dnf.return_value = True
        mock_run.return_value = MagicMock(returncode=0)

        assert _ensure_git_installed() is True
        call_args = mock_run.call_args_list[0][0][0]
        assert "sudo" in call_args
        assert "-n" not in call_args
        assert "dnf" in call_args
        assert "git" in call_args

    @patch("subprocess.run")
    @patch("installer.steps.prerequisites.is_dnf_available")
    @patch("installer.steps.prerequisites.is_yum_available")
    @patch("installer.steps.prerequisites.is_linux")
    @patch("installer.steps.prerequisites.command_exists")
    def test_falls_back_to_yum(self, mock_cmd, mock_linux, mock_yum, mock_dnf, mock_run):
        from installer.steps.prerequisites import _ensure_git_installed

        mock_cmd.side_effect = [False, True]
        mock_linux.return_value = True
        mock_dnf.return_value = False
        mock_yum.return_value = True
        mock_run.return_value = MagicMock(returncode=0)

        assert _ensure_git_installed() is True
        call_args = mock_run.call_args_list[0][0][0]
        assert "yum" in call_args

    @patch("subprocess.run")
    @patch("installer.steps.prerequisites.is_dnf_available")
    @patch("installer.steps.prerequisites.is_yum_available")
    @patch("installer.steps.prerequisites.is_apt_available")
    @patch("installer.steps.prerequisites.is_linux")
    @patch("installer.steps.prerequisites.command_exists")
    def test_returns_false_when_no_package_manager(self, mock_cmd, mock_linux, mock_apt, mock_yum, mock_dnf, mock_run):
        from installer.steps.prerequisites import _ensure_git_installed

        mock_cmd.return_value = False
        mock_linux.return_value = True
        mock_dnf.return_value = False
        mock_yum.return_value = False
        mock_apt.return_value = False

        assert _ensure_git_installed() is False
        mock_run.assert_not_called()

    @patch("subprocess.run")
    @patch("installer.steps.prerequisites.is_dnf_available")
    @patch("installer.steps.prerequisites.is_linux")
    @patch("installer.steps.prerequisites.command_exists")
    def test_returns_false_on_install_failure(self, mock_cmd, mock_linux, mock_dnf, mock_run):
        from installer.steps.prerequisites import _ensure_git_installed

        mock_cmd.return_value = False
        mock_linux.return_value = True
        mock_dnf.return_value = True
        mock_run.return_value = MagicMock(returncode=1)

        assert _ensure_git_installed() is False


class TestPrerequisitesStepRunLinuxFallback:
    """Test that PrerequisitesStep.run continues on Linux when Homebrew fails."""

    @patch("installer.steps.prerequisites._install_bun_standalone", return_value=True)
    @patch("installer.steps.prerequisites._install_nodejs_via_pkg", return_value=True)
    @patch("installer.steps.prerequisites._install_ripgrep_via_apt")
    @patch("installer.steps.prerequisites.is_apt_available")
    @patch("installer.steps.prerequisites._install_homebrew_package")
    @patch("installer.steps.prerequisites._add_bun_tap")
    @patch("installer.steps.prerequisites._install_homebrew")
    @patch("installer.steps.prerequisites._ensure_git_installed")
    @patch("installer.steps.prerequisites.command_exists")
    @patch("installer.steps.prerequisites.is_linux")
    @patch("installer.steps.prerequisites.is_homebrew_available")
    def test_run_continues_after_homebrew_failure_on_linux(
        self,
        mock_brew_avail,
        mock_linux,
        mock_cmd_exists,
        _mock_git,
        mock_install_brew,
        _mock_tap,
        _mock_pkg_install,
        mock_apt,
        mock_ripgrep,
        _mock_nodejs_pkg,
        _mock_bun_standalone,
    ):
        """On Linux, PrerequisitesStep.run does not return early when Homebrew fails."""
        from installer.context import InstallContext
        from installer.steps.prerequisites import PrerequisitesStep
        from installer.ui import Console

        mock_brew_avail.return_value = False
        mock_linux.return_value = True
        mock_cmd_exists.return_value = False
        mock_install_brew.return_value = False
        mock_apt.return_value = True
        mock_ripgrep.return_value = True

        step = PrerequisitesStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = InstallContext(
                project_dir=Path(tmpdir),
                is_local_install=True,
                ui=Console(non_interactive=True),
            )
            step.run(ctx)

        mock_ripgrep.assert_called_once()

    @patch("installer.steps.prerequisites._install_ripgrep_via_apt")
    @patch("installer.steps.prerequisites.is_apt_available")
    @patch("installer.steps.prerequisites._install_homebrew")
    @patch("installer.steps.prerequisites.command_exists")
    @patch("installer.steps.prerequisites.is_linux")
    @patch("installer.steps.prerequisites.is_homebrew_available")
    def test_run_returns_early_on_macos_homebrew_failure(
        self,
        mock_brew_avail,
        mock_linux,
        mock_cmd_exists,
        mock_install_brew,
        mock_apt,
        mock_ripgrep,
    ):
        """On macOS, PrerequisitesStep.run still returns early when Homebrew fails (unchanged)."""
        from installer.context import InstallContext
        from installer.steps.prerequisites import PrerequisitesStep
        from installer.ui import Console

        mock_brew_avail.return_value = False
        mock_linux.return_value = False
        mock_cmd_exists.return_value = True
        mock_install_brew.return_value = False
        mock_apt.return_value = True
        mock_ripgrep.return_value = True

        step = PrerequisitesStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = InstallContext(
                project_dir=Path(tmpdir),
                is_local_install=True,
                ui=Console(non_interactive=True),
            )
            step.run(ctx)

        mock_ripgrep.assert_not_called()

    @patch("installer.steps.prerequisites._install_bun_standalone", return_value=True)
    @patch("installer.steps.prerequisites._install_nodejs_via_pkg", return_value=True)
    @patch("installer.steps.prerequisites._install_ripgrep_via_apt")
    @patch("installer.steps.prerequisites.is_apt_available")
    @patch("installer.steps.prerequisites._install_homebrew")
    @patch("installer.steps.prerequisites._ensure_git_installed")
    @patch("installer.steps.prerequisites.command_exists")
    @patch("installer.steps.prerequisites.is_linux")
    @patch("installer.steps.prerequisites.is_homebrew_available")
    def test_run_continues_after_homebrew_failure_on_linux_without_ui(
        self,
        mock_brew_avail,
        mock_linux,
        mock_cmd_exists,
        _mock_git,
        mock_install_brew,
        mock_apt,
        mock_ripgrep,
        _mock_nodejs_pkg,
        _mock_bun_standalone,
    ):
        """On Linux without UI, PrerequisitesStep.run does not return early when Homebrew fails."""
        from installer.context import InstallContext
        from installer.steps.prerequisites import PrerequisitesStep

        mock_brew_avail.return_value = False
        mock_linux.return_value = True
        mock_cmd_exists.return_value = False
        mock_install_brew.return_value = False
        mock_apt.return_value = True
        mock_ripgrep.return_value = True

        step = PrerequisitesStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = InstallContext(
                project_dir=Path(tmpdir),
                is_local_install=True,
                ui=None,
            )
            step.run(ctx)

        mock_ripgrep.assert_called_once()


class TestPrerequisitesStepRunGitInstall:
    """Test that PrerequisitesStep.run installs git before Homebrew."""

    @patch("installer.steps.prerequisites._install_homebrew")
    @patch("installer.steps.prerequisites._ensure_git_installed")
    @patch("installer.steps.prerequisites.command_exists")
    @patch("installer.steps.prerequisites.is_homebrew_available")
    def test_run_installs_git_before_homebrew_when_missing(self, mock_brew, mock_cmd, mock_git, mock_homebrew_install):
        from installer.context import InstallContext
        from installer.steps.prerequisites import PrerequisitesStep
        from installer.ui import Console

        mock_brew.return_value = False
        mock_cmd.return_value = False
        mock_git.return_value = True
        mock_homebrew_install.return_value = False

        step = PrerequisitesStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = InstallContext(
                project_dir=Path(tmpdir),
                is_local_install=True,
                ui=Console(non_interactive=True),
            )
            step.run(ctx)

        mock_git.assert_called_once()

    @patch("installer.steps.prerequisites._install_homebrew")
    @patch("installer.steps.prerequisites._ensure_git_installed")
    @patch("installer.steps.prerequisites.command_exists")
    @patch("installer.steps.prerequisites.is_homebrew_available")
    def test_run_skips_git_install_when_already_present(self, mock_brew, mock_cmd, mock_git, mock_homebrew_install):
        from installer.context import InstallContext
        from installer.steps.prerequisites import PrerequisitesStep
        from installer.ui import Console

        mock_brew.return_value = False
        mock_cmd.return_value = True
        mock_homebrew_install.return_value = False

        step = PrerequisitesStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = InstallContext(
                project_dir=Path(tmpdir),
                is_local_install=True,
                ui=Console(non_interactive=True),
            )
            step.run(ctx)

        mock_git.assert_not_called()


class TestManifestDrivenHomebrew:
    """Manifest replaces hardcoded HOMEBREW_PACKAGES + HOMEBREW_NO_UPGRADE_PACKAGES."""

    def test_brew_formulas_match_manifest(self):
        """HOMEBREW_PACKAGES is built from manifest brew entries."""
        from installer.manifest import load
        from installer.steps.prerequisites import _brew_formulas

        manifest_formulas = [e.brew_formula for e in load().entries if e.source_type == "brew"]
        assert _brew_formulas() == manifest_formulas

    def test_no_upgrade_set_matches_manifest(self):
        """HOMEBREW_NO_UPGRADE_PACKAGES = formulas with auto_upgrade=false."""
        from installer.manifest import load
        from installer.steps.prerequisites import _brew_no_upgrade_formulas

        expected = {e.brew_formula for e in load().entries if e.source_type == "brew" and not e.auto_upgrade}
        assert _brew_no_upgrade_formulas() == expected
        # Plan locks these specific formulas to manifest-pinned versions:
        assert {"python@3.12", "node@24", "nvm", "git", "gh"} <= expected

    @patch("subprocess.run")
    def test_verify_homebrew_tap_accepts_homebrew_core(self, mock_run):
        """_verify_homebrew_tap returns True for formulas from homebrew/core."""
        from installer.steps.prerequisites import _verify_homebrew_tap

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=b'{"formulae":[{"tap":"homebrew/core"}]}',
        )
        assert _verify_homebrew_tap("git") is True

    @patch("subprocess.run")
    def test_verify_homebrew_tap_rejects_unexpected_tap(self, mock_run):
        """_verify_homebrew_tap returns False when formula resolves from a different tap."""
        from installer.steps.prerequisites import _verify_homebrew_tap

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=b'{"formulae":[{"tap":"shady/typosquat"}]}',
        )
        assert _verify_homebrew_tap("git") is False

    @patch("subprocess.run")
    def test_verify_homebrew_tap_accepts_oven_sh_for_bun(self, mock_run):
        """_verify_homebrew_tap honors per-entry tap override (bun → oven-sh/bun)."""
        from installer.steps.prerequisites import _verify_homebrew_tap

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=b'{"formulae":[{"tap":"oven-sh/bun"}]}',
        )
        assert _verify_homebrew_tap("bun") is True
        assert mock_run.call_args.args[0] == ["brew", "info", "--json=v2", "oven-sh/bun/bun"]

    @patch("subprocess.run")
    def test_verify_homebrew_tap_unknown_formula_returns_false(self, mock_run):
        """Formulas not in manifest fail verification (no expected tap to compare)."""
        from installer.steps.prerequisites import _verify_homebrew_tap

        # Subprocess shouldn't even be called for unknown formulas.
        assert _verify_homebrew_tap("not-in-manifest") is False
        mock_run.assert_not_called()


class TestInstallHomebrew:
    """Test _install_homebrew function."""

    @patch("installer.steps.prerequisites.is_homebrew_available", return_value=True)
    def test_install_homebrew_routes_through_manifest_pinned_helper(self, _mock_brew_available):
        """_install_homebrew uses the manifest-pinned curl helper with NONINTERACTIVE+stdin_devnull."""
        from installer.steps.prerequisites import _install_homebrew

        with patch("installer.steps.dependencies._curl_pipe_from_manifest", return_value=True) as mock_helper:
            ok = _install_homebrew()

        assert ok is True
        mock_helper.assert_called_once()
        assert mock_helper.call_args[0][0] == "homebrew-installer"
        opts = mock_helper.call_args[0][1]
        assert opts.env == {"NONINTERACTIVE": "1"}, "Homebrew install must set NONINTERACTIVE=1"
        assert opts.stdin_devnull is True, "Homebrew install must redirect stdin to DEVNULL"
        assert opts.interpreter == "/bin/bash"
        assert opts.timeout >= 60

    @patch("installer.steps.prerequisites.is_homebrew_available", return_value=False)
    def test_install_homebrew_returns_false_when_helper_fails(self, _mock_brew_available):
        """_install_homebrew returns False when the manifest-pinned curl install fails."""
        from installer.steps.prerequisites import _install_homebrew

        with patch("installer.steps.dependencies._curl_pipe_from_manifest", return_value=False):
            assert _install_homebrew() is False


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


class TestLinuxFallbackBugCondition:
    """Linux fallback tests for the Node 24 and Bun runtime baseline."""

    @patch("installer.steps.prerequisites._install_bun_standalone")
    @patch("installer.steps.prerequisites._install_nodejs_via_pkg")
    @patch("installer.steps.prerequisites._install_ripgrep_via_apt")
    @patch("installer.steps.prerequisites.is_apt_available")
    @patch("installer.steps.prerequisites._install_homebrew")
    @patch("installer.steps.prerequisites._ensure_git_installed")
    @patch("installer.steps.prerequisites.command_exists")
    @patch("installer.steps.prerequisites.is_linux")
    @patch("installer.steps.prerequisites.is_homebrew_available")
    def test_linux_fallback_defers_node24_to_the_pinned_nvm_installer(
        self,
        mock_brew_avail,
        mock_linux,
        mock_cmd_exists,
        _mock_git,
        mock_install_brew,
        mock_apt,
        _mock_ripgrep,
        mock_nodejs_pkg,
        _mock_bun_standalone,
    ):
        """Distro Node 20/22 is not accepted as the Node 24 browser runtime."""
        from installer.context import InstallContext
        from installer.steps.prerequisites import PrerequisitesStep
        from installer.ui import Console

        mock_brew_avail.return_value = False
        mock_linux.return_value = True
        mock_cmd_exists.return_value = False
        mock_install_brew.return_value = False
        mock_apt.return_value = True
        step = PrerequisitesStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = InstallContext(
                project_dir=Path(tmpdir),
                is_local_install=True,
                ui=Console(non_interactive=True),
            )
            step.run(ctx)

        mock_nodejs_pkg.assert_not_called()

    # `ensure_bun_on_path` is patched False in the bun cases below so they describe the
    # installer rather than whether the machine running the suite already has bun.

    @patch("installer.steps.prerequisites.ensure_bun_on_path", return_value=False)
    @patch("installer.steps.prerequisites._install_bun_standalone")
    @patch("installer.steps.prerequisites._install_nodejs_via_pkg")
    @patch("installer.steps.prerequisites._install_ripgrep_via_apt")
    @patch("installer.steps.prerequisites.is_apt_available")
    @patch("installer.steps.prerequisites._install_homebrew")
    @patch("installer.steps.prerequisites._ensure_git_installed")
    @patch("installer.steps.prerequisites.command_exists")
    @patch("installer.steps.prerequisites.is_linux")
    @patch("installer.steps.prerequisites.is_homebrew_available")
    def test_linux_fallback_installs_bun_standalone_when_brew_unavailable(
        self,
        mock_brew_avail,
        mock_linux,
        mock_cmd_exists,
        _mock_git,
        mock_install_brew,
        mock_apt,
        _mock_ripgrep,
        _mock_nodejs_pkg,
        mock_bun_standalone,
        _mock_bun_on_path,
    ):
        """On Linux without Homebrew, bun is installed via standalone installer."""
        from installer.context import InstallContext
        from installer.steps.prerequisites import PrerequisitesStep
        from installer.ui import Console

        mock_brew_avail.return_value = False
        mock_linux.return_value = True
        mock_cmd_exists.return_value = False
        mock_install_brew.return_value = False
        mock_apt.return_value = True
        mock_bun_standalone.return_value = True

        step = PrerequisitesStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = InstallContext(
                project_dir=Path(tmpdir),
                is_local_install=True,
                ui=Console(non_interactive=True),
            )
            step.run(ctx)

        mock_bun_standalone.assert_called_once()

    @patch("installer.steps.prerequisites.ensure_bun_on_path", return_value=False)
    @patch("installer.steps.prerequisites._install_bun_standalone")
    @patch("installer.steps.prerequisites._install_nodejs_via_pkg")
    @patch("installer.steps.prerequisites._install_ripgrep_via_apt")
    @patch("installer.steps.prerequisites.is_apt_available")
    @patch("installer.steps.prerequisites._install_homebrew")
    @patch("installer.steps.prerequisites._ensure_git_installed")
    @patch("installer.steps.prerequisites._install_homebrew_package")
    @patch("installer.steps.prerequisites._add_bun_tap")
    @patch("installer.steps.prerequisites.command_exists")
    @patch("installer.steps.prerequisites.is_linux")
    @patch("installer.steps.prerequisites.is_homebrew_available")
    def test_bun_standalone_recovers_when_homebrew_did_not_provide_bun(
        self,
        mock_brew_avail,
        mock_linux,
        mock_cmd_exists,
        _mock_tap,
        _mock_brew_pkg,
        _mock_git,
        _mock_install_brew,
        mock_apt,
        _mock_ripgrep,
        _mock_nodejs_pkg,
        mock_bun_standalone,
        _mock_bun_on_path,
    ):
        """macOS with Homebrew, but brew never produced a working bun.

        Regression: `_install_bun_standalone` used to be reachable only through
        `_install_linux_fallbacks`, which returns early off Linux -- so a failed
        `oven-sh/bun` tap or formula left macOS with no bun at all, and the dependency
        step silently installed Pilot's Node deps with npm instead.
        """
        from installer.context import InstallContext
        from installer.steps.prerequisites import PrerequisitesStep
        from installer.ui import Console

        mock_brew_avail.return_value = True
        mock_linux.return_value = False
        mock_cmd_exists.return_value = False
        mock_apt.return_value = False
        mock_bun_standalone.return_value = True

        step = PrerequisitesStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = InstallContext(
                project_dir=Path(tmpdir),
                is_local_install=True,
                ui=Console(non_interactive=True),
            )
            step.run(ctx)

        mock_bun_standalone.assert_called_once()


class TestLinuxFallbackPreservation:
    """Preservation tests: behavior that must NOT change after the Linux fallback fix."""

    @patch("installer.steps.prerequisites._install_homebrew_package")
    @patch("installer.steps.prerequisites._add_bun_tap")
    @patch("installer.steps.prerequisites._is_nvm_installed")
    @patch("installer.steps.prerequisites.command_exists")
    @patch("installer.steps.prerequisites.is_linux")
    @patch("installer.steps.prerequisites.is_homebrew_available")
    def test_preservation_brew_install_called_when_homebrew_available_on_linux(
        self,
        mock_brew_avail,
        mock_linux,
        mock_cmd_exists,
        mock_nvm,
        mock_tap,
        mock_install,
    ):
        """PRESERVATION: On Linux when Homebrew IS available, brew install is used for packages."""
        from installer.context import InstallContext
        from installer.steps.prerequisites import HOMEBREW_PACKAGES, PrerequisitesStep
        from installer.ui import Console

        mock_brew_avail.return_value = True
        mock_linux.return_value = True
        mock_cmd_exists.return_value = False
        mock_nvm.return_value = False
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

        assert mock_install.call_count == len(HOMEBREW_PACKAGES)

    @patch("installer.steps.prerequisites._install_ripgrep_via_apt")
    @patch("installer.steps.prerequisites.is_apt_available")
    @patch("installer.steps.prerequisites._install_homebrew")
    @patch("installer.steps.prerequisites.command_exists")
    @patch("installer.steps.prerequisites.is_linux")
    @patch("installer.steps.prerequisites.is_homebrew_available")
    def test_preservation_macos_returns_early_without_linux_fallbacks(
        self,
        mock_brew_avail,
        mock_linux,
        mock_cmd_exists,
        mock_install_brew,
        mock_apt,
        mock_ripgrep,
    ):
        """PRESERVATION: On macOS with Homebrew failure, run() exits early and no apt/ripgrep fallbacks run."""
        from installer.context import InstallContext
        from installer.steps.prerequisites import PrerequisitesStep
        from installer.ui import Console

        mock_brew_avail.return_value = False
        mock_linux.return_value = False
        mock_cmd_exists.return_value = True
        mock_install_brew.return_value = False
        mock_apt.return_value = True
        mock_ripgrep.return_value = True

        step = PrerequisitesStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = InstallContext(
                project_dir=Path(tmpdir),
                is_local_install=True,
                ui=Console(non_interactive=True),
            )
            step.run(ctx)

        mock_ripgrep.assert_not_called()


class TestBrewUpgrade:
    """Tests for Homebrew upgrade logic."""

    def test_upgrade_homebrew_package_success(self):
        """_upgrade_homebrew_package returns True on success."""
        from installer.steps.prerequisites import _upgrade_homebrew_package

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = _upgrade_homebrew_package("rtk")

        assert result is True
        mock_run.assert_called_once_with(
            ["brew", "upgrade", "rtk"],
            capture_output=True,
            check=False,
            timeout=120,
        )

    def test_upgrade_homebrew_package_failure_returns_false(self):
        """_upgrade_homebrew_package returns False when brew upgrade fails."""
        from installer.steps.prerequisites import _upgrade_homebrew_package

        with patch("subprocess.run") as mock_run, patch("installer.steps.prerequisites.time.sleep"):
            mock_run.return_value = MagicMock(returncode=1)
            result = _upgrade_homebrew_package("rtk")

        assert result is False

    def test_upgrade_bun_uses_the_manifest_tap_qualified_formula(self):
        from installer.steps.prerequisites import _upgrade_homebrew_package

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            assert _upgrade_homebrew_package("bun") is True

        assert mock_run.call_args.args[0] == ["brew", "upgrade", "oven-sh/bun/bun"]

    def test_get_outdated_homebrew_packages_returns_matching(self):
        """_get_outdated_homebrew_packages returns packages that appear in brew outdated output."""
        from installer.steps.prerequisites import _get_outdated_homebrew_packages

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=b"rtk\nbun\n")
            result = _get_outdated_homebrew_packages(["rtk", "gh", "bun"])

        assert result == {"rtk", "bun"}

    def test_get_outdated_homebrew_packages_matches_tap_qualified_output(self):
        from installer.steps.prerequisites import _get_outdated_homebrew_packages

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=b"oven-sh/bun/bun\n")
            assert _get_outdated_homebrew_packages(["bun"]) == {"bun"}

    def test_get_outdated_homebrew_packages_empty_when_all_up_to_date(self):
        """_get_outdated_homebrew_packages returns empty set when nothing is outdated."""
        from installer.steps.prerequisites import _get_outdated_homebrew_packages

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=b"")
            result = _get_outdated_homebrew_packages(["rtk"])

        assert result == set()

    def test_get_outdated_homebrew_packages_returns_empty_on_error(self):
        """_get_outdated_homebrew_packages returns empty set when brew command fails."""
        from installer.steps.prerequisites import _get_outdated_homebrew_packages

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout=b"")
            result = _get_outdated_homebrew_packages(["rtk"])

        assert result == set()

    @patch("installer.steps.prerequisites._upgrade_homebrew_package")
    @patch("installer.steps.prerequisites._get_outdated_homebrew_packages")
    @patch("installer.steps.prerequisites._install_homebrew_package")
    @patch("installer.steps.prerequisites._add_bun_tap")
    @patch("installer.steps.prerequisites._is_nvm_installed")
    @patch("installer.steps.prerequisites.command_exists")
    @patch("installer.steps.prerequisites.is_homebrew_available")
    def test_run_upgrades_outdated_packages(
        self, mock_brew, mock_cmd_exists, mock_nvm, mock_tap, mock_install, mock_outdated, mock_upgrade
    ):
        """run() calls upgrade for installed packages that are outdated."""
        from installer.context import InstallContext
        from installer.steps.prerequisites import PrerequisitesStep
        from installer.ui import Console

        mock_brew.return_value = True
        mock_cmd_exists.return_value = True
        mock_nvm.return_value = True
        mock_tap.return_value = True
        mock_install.return_value = True
        mock_outdated.return_value = {"rtk"}
        mock_upgrade.return_value = True

        step = PrerequisitesStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = InstallContext(
                project_dir=Path(tmpdir),
                is_local_install=True,
                ui=Console(non_interactive=True),
            )
            step.run(ctx)

        mock_install.assert_not_called()
        upgraded = {call.args[0] for call in mock_upgrade.call_args_list}
        assert upgraded == {"rtk"}

    @patch("installer.steps.prerequisites._get_outdated_homebrew_packages")
    @patch("installer.steps.prerequisites._is_nvm_installed")
    @patch("installer.steps.prerequisites.command_exists")
    @patch("installer.steps.prerequisites.is_homebrew_available")
    def test_check_returns_false_when_outdated_packages_exist(
        self, mock_brew, mock_cmd_exists, mock_nvm, mock_outdated
    ):
        """check() returns False (run step) when upgradeable packages are outdated."""
        from installer.context import InstallContext
        from installer.steps.prerequisites import PrerequisitesStep

        mock_brew.return_value = True
        mock_cmd_exists.return_value = True
        mock_nvm.return_value = True
        mock_outdated.return_value = {"rtk"}

        step = PrerequisitesStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = InstallContext(project_dir=Path(tmpdir), is_local_install=True)
            result = step.check(ctx)

        assert result is False

    def test_no_upgrade_packages_excludes_version_pinned(self):
        """HOMEBREW_NO_UPGRADE_PACKAGES excludes version-pinned packages."""
        from installer.steps.prerequisites import HOMEBREW_NO_UPGRADE_PACKAGES

        assert "python@3.12" in HOMEBREW_NO_UPGRADE_PACKAGES
        assert "node@24" in HOMEBREW_NO_UPGRADE_PACKAGES
        assert "rtk" not in HOMEBREW_NO_UPGRADE_PACKAGES
