"""Tests for shell config step."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from installer.steps.shell_config import (
    CLAUDE_ALIAS_MARKER,
    OLD_CCP_MARKER,
    PILOT_BIN,
    PILOT_BIN_DIR,
    ShellConfigStep,
    alias_exists_in_file,
    get_alias_lines,
    remove_old_alias,
)


class TestShellConfigStep:
    """Test ShellConfigStep class."""

    def test_shell_config_step_has_correct_name(self):
        """ShellConfigStep has name 'shell_config'."""
        step = ShellConfigStep()
        assert step.name == "shell_config"

    def test_shell_config_check_always_returns_false(self):
        """ShellConfigStep.check always returns False to ensure alias updates."""
        from installer.context import InstallContext
        from installer.ui import Console

        step = ShellConfigStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = InstallContext(
                project_dir=Path(tmpdir),
                ui=Console(non_interactive=True),
            )
            assert step.check(ctx) is False

    @patch("installer.steps.shell_config.get_shell_config_files")
    def test_shell_config_run_adds_pilot_alias(self, mock_get_files):
        """ShellConfigStep.run adds pilot and ccp aliases to shell configs."""
        from installer.context import InstallContext
        from installer.ui import Console

        step = ShellConfigStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            bashrc = Path(tmpdir) / ".bashrc"
            bashrc.write_text("# existing config\n")
            mock_get_files.return_value = [bashrc]

            ctx = InstallContext(
                project_dir=Path(tmpdir),
                ui=Console(non_interactive=True),
            )

            step.run(ctx)

            content = bashrc.read_text()
            assert CLAUDE_ALIAS_MARKER in content
            assert "alias pilot=" in content
            assert "alias ccp=" in content
            assert PILOT_BIN in content

    @patch("installer.steps.shell_config.get_shell_config_files")
    def test_shell_config_migrates_old_ccp_alias(self, mock_get_files):
        """ShellConfigStep.run removes old ccp alias during migration."""
        from installer.context import InstallContext
        from installer.ui import Console

        step = ShellConfigStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            bashrc = Path(tmpdir) / ".bashrc"
            bashrc.write_text(f"{OLD_CCP_MARKER}\nalias ccp='old wrapper.py version'\n# other config\n")
            mock_get_files.return_value = [bashrc]

            ctx = InstallContext(
                project_dir=Path(tmpdir),
                ui=Console(non_interactive=True),
            )

            step.run(ctx)

            content = bashrc.read_text()
            assert "wrapper.py" not in content
            assert OLD_CCP_MARKER not in content
            assert CLAUDE_ALIAS_MARKER in content
            assert "alias pilot=" in content

    @patch("installer.steps.shell_config.get_shell_config_files")
    def test_shell_config_run_skips_file_with_managed_elsewhere_marker(self, mock_get_files):
        """ShellConfigStep.run leaves a config file untouched when it carries the opt-out marker."""
        from installer.context import InstallContext
        from installer.ui import Console

        step = ShellConfigStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            zshrc = Path(tmpdir) / ".zshrc"
            original = "# pilot-shell:managed-elsewhere\n# my framework owns this file\nsource ~/.zshand/init.zsh\n"
            zshrc.write_text(original)
            mock_get_files.return_value = [zshrc]

            ctx = InstallContext(
                project_dir=Path(tmpdir),
                ui=Console(non_interactive=True),
            )

            step.run(ctx)

            content = zshrc.read_text()
            assert content == original
            assert CLAUDE_ALIAS_MARKER not in content
            assert "alias pilot=" not in content
            assert str(zshrc) not in ctx.config.get("modified_shell_configs", [])

    @patch("installer.steps.shell_config.get_shell_config_files")
    def test_shell_config_upgrades_old_bun_only_path(self, mock_get_files):
        """ShellConfigStep upgrades old config with only .bun/bin to include .pilot/bin."""
        from installer.context import InstallContext
        from installer.ui import Console

        step = ShellConfigStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            bashrc = Path(tmpdir) / ".bashrc"
            bashrc.write_text(
                "# before\n"
                f"{CLAUDE_ALIAS_MARKER}\n"
                'export PATH="$HOME/.bun/bin:$PATH"\n'
                f'alias pilot="{PILOT_BIN}"\n'
                f'alias ccp="{PILOT_BIN}"\n'
                "# after\n"
            )
            mock_get_files.return_value = [bashrc]

            ctx = InstallContext(
                project_dir=Path(tmpdir),
                ui=Console(non_interactive=True),
            )

            step.run(ctx)

            content = bashrc.read_text()
            assert "# before" in content
            assert "# after" in content
            assert PILOT_BIN_DIR in content
            assert content.count(CLAUDE_ALIAS_MARKER) == 1


class TestAliasLines:
    """Test alias line generation."""

    def test_get_alias_lines_returns_string(self):
        """get_alias_lines returns a string."""
        result = get_alias_lines("bash")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_get_alias_lines_contains_pilot_and_ccp_aliases(self):
        """Alias lines contain pilot and ccp aliases (not claude to avoid overriding binary)."""
        result = get_alias_lines("bash")
        assert "alias pilot=" in result
        assert "alias ccp=" in result
        assert "alias claude=" not in result
        assert PILOT_BIN in result
        assert CLAUDE_ALIAS_MARKER in result

    def test_get_alias_lines_fish_uses_alias_syntax(self):
        """Fish alias uses alias syntax for pilot and ccp aliases."""
        result = get_alias_lines("fish")
        assert "alias pilot=" in result
        assert "alias ccp=" in result
        assert "alias claude=" not in result
        assert PILOT_BIN in result
        assert CLAUDE_ALIAS_MARKER in result

    def test_bash_session_id_is_unique_per_invocation(self):
        """Bash/zsh session wrapper must NOT use bare $$ as session ID."""
        result = get_alias_lines("bash")
        assert "PILOT_SESSION_ID=$$" not in result.replace("PILOT_SESSION_ID=$_sid", ""), (
            "Bare $$ reuses the parent shell PID across invocations"
        )

    def test_fish_session_id_is_unique_per_invocation(self):
        """Fish session wrapper must use $fish_pid-(random) for unique session IDs."""
        result = get_alias_lines("fish")
        lines_without_sid_ref = result.replace("$_sid", "")
        assert "PILOT_SESSION_ID %self;" not in lines_without_sid_ref, (
            "Bare %self reuses the fish PID across invocations"
        )
        assert "$fish_pid-(random)" in result, "Fish wrapper must use $fish_pid for PID expansion in concatenation"

    def test_bash_codex_wrapper_raises_low_open_file_limit(self):
        result = get_alias_lines("bash")

        assert "ulimit -Sn" in result
        assert "ulimit -Hn" in result
        assert "1024" in result
        assert 'command codex "$@"' in result

    def test_fish_codex_wrapper_raises_low_open_file_limit(self):
        result = get_alias_lines("fish")

        assert "ulimit -Sn" in result
        assert "ulimit -Hn" in result
        assert "1024" in result
        assert 'exec codex "$@"' in result

    @pytest.mark.parametrize("shell_name", ["bash", "zsh"])
    def test_posix_codex_wrapper_raises_low_limit_and_preserves_high_limit(
        self, shell_name: str, tmp_path: Path
    ) -> None:
        shell = shutil.which(shell_name)
        if shell is None:
            pytest.skip(f"{shell_name} is not installed")

        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        fake_codex = bin_dir / "codex"
        fake_codex.write_text("#!/bin/sh\nulimit -Sn\n")
        fake_codex.chmod(0o755)
        wrapper = tmp_path / "pilot-wrapper.sh"
        wrapper.write_text(get_alias_lines(shell_name) + "\n")
        env = dict(os.environ)
        env["HOME"] = str(tmp_path)
        env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"

        def invoke(initial_limit: int, hard_limit: int | None = None) -> int:
            setup = f"ulimit -Sn {initial_limit};"
            if hard_limit is not None:
                setup += f" ulimit -Hn {hard_limit};"
            result = subprocess.run(
                [shell, "-c", f'{setup} source "{wrapper}"; codex'],
                capture_output=True,
                text=True,
                env=env,
                timeout=5,
                check=True,
            )
            return int(result.stdout.strip())

        assert invoke(256) == 1024
        assert invoke(256, 768) == 768
        assert invoke(2048) == 2048

    @pytest.mark.parametrize("shell_name", ["bash", "zsh"])
    def test_posix_codex_wrapper_leaves_parent_shell_limit_unchanged(self, shell_name: str, tmp_path: Path) -> None:
        shell = shutil.which(shell_name)
        if shell is None:
            pytest.skip(f"{shell_name} is not installed")

        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        fake_codex = bin_dir / "codex"
        fake_codex.write_text("#!/bin/sh\nulimit -Sn\n")
        fake_codex.chmod(0o755)
        wrapper = tmp_path / "pilot-wrapper.sh"
        wrapper.write_text(get_alias_lines(shell_name) + "\n")
        env = dict(os.environ)
        env["HOME"] = str(tmp_path)
        env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"

        result = subprocess.run(
            [shell, "-c", f'ulimit -Sn 256; source "{wrapper}"; codex; ulimit -Sn'],
            capture_output=True,
            text=True,
            env=env,
            timeout=5,
            check=True,
        )

        assert result.stdout.splitlines() == ["1024", "256"]


class TestAliasDetection:
    """Test alias detection in config files."""

    def test_alias_exists_in_file_detects_old_ccp_marker(self):
        """alias_exists_in_file detects old ccp alias marker."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Path(tmpdir) / ".bashrc"
            config.write_text(f"{OLD_CCP_MARKER}\nalias ccp='...'\n")
            assert alias_exists_in_file(config) is True

    def test_alias_exists_in_file_detects_claude_marker(self):
        """alias_exists_in_file detects claude alias marker."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Path(tmpdir) / ".bashrc"
            config.write_text(f"{CLAUDE_ALIAS_MARKER}\nalias claude='...'\n")
            assert alias_exists_in_file(config) is True

    def test_alias_exists_in_file_detects_alias_without_marker(self):
        """alias_exists_in_file detects alias ccp without marker."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Path(tmpdir) / ".bashrc"
            config.write_text("alias ccp='something'\n")
            assert alias_exists_in_file(config) is True

    def test_alias_exists_in_file_returns_false_when_missing(self):
        """alias_exists_in_file returns False when not configured."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Path(tmpdir) / ".bashrc"
            config.write_text("# some other config\n")
            assert alias_exists_in_file(config) is False

    def test_alias_exists_in_file_handles_non_utf8_bytes(self):
        """alias_exists_in_file handles shell configs with non-UTF-8 bytes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Path(tmpdir) / ".bashrc"
            config.write_bytes(b"# config\n\x9c\xfe invalid bytes\nalias pilot='test'\n")
            assert alias_exists_in_file(config) is True

    def test_alias_exists_in_file_no_alias_with_non_utf8_bytes(self):
        """alias_exists_in_file returns False for non-UTF-8 file without alias."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Path(tmpdir) / ".bashrc"
            config.write_bytes(b"# config\n\x9c\xfe invalid bytes\n")
            assert alias_exists_in_file(config) is False

    def test_alias_exists_in_file_detects_claude_alias_without_marker(self):
        """alias_exists_in_file detects alias claude without marker."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Path(tmpdir) / ".bashrc"
            config.write_text("alias claude='something'\n")
            assert alias_exists_in_file(config) is True


class TestAliasRemoval:
    """Test alias removal for updates and migration."""

    def test_remove_old_alias_removes_ccp_marker_and_alias(self):
        """remove_old_alias removes ccp marker and alias line."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Path(tmpdir) / ".bashrc"
            config.write_text(f"# before\n{OLD_CCP_MARKER}\nalias ccp='complex alias'\n# after\n")

            result = remove_old_alias(config)

            assert result is True
            content = config.read_text()
            assert "alias ccp" not in content
            assert OLD_CCP_MARKER not in content
            assert "# before" in content
            assert "# after" in content

    def test_remove_old_alias_removes_claude_marker_and_alias(self):
        """remove_old_alias removes claude marker and alias."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Path(tmpdir) / ".bashrc"
            config.write_text(f"# before\n{CLAUDE_ALIAS_MARKER}\nalias claude='...'\n# after\n")

            result = remove_old_alias(config)

            assert result is True
            content = config.read_text()
            assert CLAUDE_ALIAS_MARKER not in content
            assert "# before" in content
            assert "# after" in content

    def test_remove_old_alias_removes_claude_function(self):
        """remove_old_alias removes claude() function definition."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Path(tmpdir) / ".bashrc"
            config.write_text(f'# before\n{CLAUDE_ALIAS_MARKER}\nclaude() {{\n    ccp "$@"\n}}\n# after\n')

            result = remove_old_alias(config)

            assert result is True
            content = config.read_text()
            assert CLAUDE_ALIAS_MARKER not in content
            assert "claude()" not in content
            assert "# before" in content
            assert "# after" in content

    def test_remove_old_alias_removes_standalone_ccp_alias(self):
        """remove_old_alias removes alias without marker."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Path(tmpdir) / ".bashrc"
            config.write_text("# config\nalias ccp='something'\n# more\n")

            result = remove_old_alias(config)

            assert result is True
            content = config.read_text()
            assert "alias ccp" not in content

    def test_remove_old_alias_returns_false_when_no_alias(self):
        """remove_old_alias returns False when no alias exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Path(tmpdir) / ".bashrc"
            config.write_text("# just config\n")

            result = remove_old_alias(config)

            assert result is False

    def test_remove_old_alias_removes_claude_alias_without_marker(self):
        """remove_old_alias removes alias claude without marker."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Path(tmpdir) / ".bashrc"
            config.write_text("# config\nalias claude='something'\n# more\n")

            result = remove_old_alias(config)

            assert result is True
            content = config.read_text()
            assert "alias claude" not in content

    def test_remove_old_alias_handles_non_utf8_bytes(self):
        """remove_old_alias handles shell configs with non-UTF-8 bytes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Path(tmpdir) / ".bashrc"
            config.write_bytes(b"# before\n\x9c\xfe bytes\nalias ccp='old'\n# after\n")

            result = remove_old_alias(config)

            assert result is True
            content = config.read_text(errors="replace")
            assert "alias ccp" not in content
            assert "# before" in content
            assert "# after" in content

    def test_remove_old_alias_removes_fish_function(self):
        """remove_old_alias removes fish function definition."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Path(tmpdir) / "config.fish"
            config.write_text("# before\nfunction claude\n    echo 'hello'\nend\n# after\n")

            result = remove_old_alias(config)

            assert result is True
            content = config.read_text()
            assert "function claude" not in content
            assert "end" not in content or "# after" in content
            assert "# before" in content
            assert "# after" in content

    def test_remove_old_alias_preserves_user_content_after_one_line_fish_functions(self, tmp_path: Path) -> None:
        config = tmp_path / "config.fish"
        config.write_text(get_alias_lines("fish") + "\nset -gx USER_SETTING preserved\n")

        assert remove_old_alias(config) is True

        result = config.read_text()
        assert "function claude" not in result
        assert "function codex" not in result
        assert "set -gx USER_SETTING preserved" in result


class TestLoginShellPathReachability:
    """`<shell> -c -l` must see ~/.pilot/bin.

    That is the exact invocation Claude Code uses to build the shell snapshot
    backing its Bash tool. When the PATH export lives only in an interactive rc
    file, the login non-interactive shell never runs it and `rtk` is off PATH
    for every agent command -- the devcontainer failure this guards against.
    """

    @staticmethod
    def _path_from_login_shell(shell: str, home: Path) -> str:
        """PATH as a login, non-interactive shell sees it, from a clean env."""
        result = subprocess.run(
            [shell, "-c", "-l", 'echo "$PATH"'],
            capture_output=True,
            text=True,
            timeout=30,
            env={"HOME": str(home), "PATH": "/usr/bin:/bin"},
        )
        return result.stdout

    def _run_step(self, home: Path) -> None:
        from installer.context import InstallContext
        from installer.ui import Console

        with patch.dict(os.environ, {"HOME": str(home)}):
            ShellConfigStep().run(InstallContext(project_dir=home, ui=Console(non_interactive=True)))

    @pytest.mark.skipif(shutil.which("bash") is None, reason="bash not installed")
    def test_debian_bash_layout_reaches_login_shell(self):
        """.bashrc's non-interactive guard hides the export; .profile carries it."""
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir)
            # What today's installer leaves behind on a Debian base image.
            (home / ".bashrc").write_text(
                f'case $- in\n    *i*) ;;\n      *) return;;\nesac\nexport PATH="{PILOT_BIN_DIR}:$PATH"\n'
            )
            (home / ".profile").write_text(
                'if [ -n "$BASH_VERSION" ]; then\n    if [ -f "$HOME/.bashrc" ]; then . "$HOME/.bashrc"; fi\nfi\n'
            )
            pilot_bin = str(home / ".pilot" / "bin")

            assert pilot_bin not in self._path_from_login_shell("bash", home), (
                "precondition: an rc-only export must be invisible to `bash -c -l`"
            )

            self._run_step(home)

            assert pilot_bin in self._path_from_login_shell("bash", home)

    @pytest.mark.skipif(shutil.which("zsh") is None, reason="zsh not installed")
    def test_zsh_layout_reaches_login_shell(self):
        """Login zsh never sources .zshrc; .zprofile is created to carry PATH."""
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir)
            (home / ".zshrc").write_text(f'export PATH="{PILOT_BIN_DIR}:$PATH"\n')
            pilot_bin = str(home / ".pilot" / "bin")

            assert pilot_bin not in self._path_from_login_shell("zsh", home), (
                "precondition: an rc-only export must be invisible to `zsh -c -l`"
            )

            self._run_step(home)

            assert (home / ".zprofile").exists(), ".zprofile must be created"
            assert pilot_bin in self._path_from_login_shell("zsh", home)
