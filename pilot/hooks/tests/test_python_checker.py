"""Tests for Python file checker."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from _checkers.python import check_python


class TestCheckPythonTestFileSkip:
    """Test files should skip validation."""

    def test_test_prefix_files_skip_checks(self, tmp_path: Path) -> None:
        """Files with test_ in name skip checks."""
        py_file = tmp_path / "test_app.py"
        py_file.write_text("x = undefined\n")

        exit_code, reason = check_python(py_file)

        assert exit_code == 0
        assert reason == ""

    def test_spec_files_skip_checks(self, tmp_path: Path) -> None:
        """Files with spec in name skip checks."""
        py_file = tmp_path / "app_spec.py"
        py_file.write_text("x = undefined\n")

        exit_code, reason = check_python(py_file)

        assert exit_code == 0
        assert reason == ""


class TestCheckPythonNoConfig:
    """When project has no ruff config, skip ruff entirely."""

    def test_no_ruff_config_skips_ruff(self, tmp_path: Path) -> None:
        """No pyproject.toml/ruff.toml means ruff is skipped."""
        py_file = tmp_path / "app.py"
        py_file.write_text("x = 1\n")

        with patch("_checkers.python.check_file_length", return_value=""):
            exit_code, reason = check_python(py_file)

        assert exit_code == 0
        assert reason == ""

    def test_pyproject_without_ruff_section_skips(self, tmp_path: Path) -> None:
        """pyproject.toml without [tool.ruff] means ruff is skipped."""
        py_file = tmp_path / "app.py"
        py_file.write_text("x = 1\n")
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'foo'\n")

        with patch("_checkers.python.check_file_length", return_value=""):
            exit_code, reason = check_python(py_file)

        assert exit_code == 0
        assert reason == ""

    def test_pyproject_with_ruff_section_runs_ruff(self, tmp_path: Path) -> None:
        """pyproject.toml with [tool.ruff] enables ruff."""
        py_file = tmp_path / "app.py"
        py_file.write_text("x = 1\n")
        (tmp_path / "pyproject.toml").write_text("[tool.ruff]\nline-length = 120\n")

        mock_result = MagicMock(returncode=0, stdout="", stderr="")

        with (
            patch("_checkers.python.check_file_length", return_value=""),
            patch("_checkers.python.shutil.which", return_value="/usr/bin/ruff"),
            patch("_checkers.python.subprocess.run", return_value=mock_result),
        ):
            exit_code, reason = check_python(py_file)

        assert exit_code == 0
        assert reason == ""

    def test_ruff_toml_enables_ruff(self, tmp_path: Path) -> None:
        """ruff.toml in project root enables ruff."""
        py_file = tmp_path / "app.py"
        py_file.write_text("x = 1\n")
        (tmp_path / "ruff.toml").write_text("line-length = 120\n")

        mock_result = MagicMock(returncode=0, stdout="", stderr="")

        with (
            patch("_checkers.python.check_file_length", return_value=""),
            patch("_checkers.python.shutil.which", return_value="/usr/bin/ruff"),
            patch("_checkers.python.subprocess.run", return_value=mock_result),
        ):
            exit_code, reason = check_python(py_file)

        assert exit_code == 0

    def test_dot_ruff_toml_enables_ruff(self, tmp_path: Path) -> None:
        """.ruff.toml in project root enables ruff."""
        py_file = tmp_path / "app.py"
        py_file.write_text("x = 1\n")
        (tmp_path / ".ruff.toml").write_text("line-length = 120\n")

        mock_result = MagicMock(returncode=0, stdout="", stderr="")

        with (
            patch("_checkers.python.check_file_length", return_value=""),
            patch("_checkers.python.shutil.which", return_value="/usr/bin/ruff"),
            patch("_checkers.python.subprocess.run", return_value=mock_result),
        ):
            exit_code, reason = check_python(py_file)

        assert exit_code == 0


class TestCheckPythonNoTools:
    """When no tools are available, skip gracefully."""

    def test_no_tools_returns_zero(self, tmp_path: Path) -> None:
        """No ruff installed returns 0."""
        py_file = tmp_path / "app.py"
        py_file.write_text("x = 1\n")

        with (
            patch("_checkers.python.check_file_length", return_value=""),
            patch("_checkers.python._has_ruff_config", return_value=True),
            patch("_checkers.python.shutil.which", return_value=None),
        ):
            exit_code, reason = check_python(py_file)

        assert exit_code == 0
        assert reason == ""


class TestCheckPythonRuffIssues:
    """Ruff issue detection and counting."""

    def test_ruff_errors_reported_in_reason(self, tmp_path: Path) -> None:
        """Ruff errors are counted and reported."""
        py_file = tmp_path / "app.py"
        py_file.write_text("x = 1\n")

        mock_check = MagicMock(
            returncode=1,
            stdout="app.py:1:1: F401 unused import\napp.py:2:1: E302 expected 2 blank lines\n",
            stderr="",
        )

        with (
            patch("_checkers.python.check_file_length", return_value=""),
            patch("_checkers.python._has_ruff_config", return_value=True),
            patch("_checkers.python.shutil.which", return_value="/usr/bin/ruff"),
            patch("_checkers.python.subprocess.run", return_value=mock_check),
        ):
            exit_code, reason = check_python(py_file)

        assert exit_code == 0
        assert "2 ruff" in reason

    def test_production_spec_module_is_linted(self, tmp_path: Path) -> None:
        py_file = tmp_path / "spec_validator.py"
        py_file.write_text("value = undefined\n")
        with (
            patch("_checkers.python.check_file_length", return_value=""),
            patch("_checkers.python._has_ruff_config", return_value=True),
            patch("_checkers.python.shutil.which", return_value="/usr/bin/ruff"),
            patch(
                "_checkers.python.subprocess.run",
                return_value=MagicMock(returncode=1, stdout="spec_validator.py:1:9: F821 undefined name\n", stderr=""),
            ),
        ):
            assert "F821" in check_python(py_file)[1]

    def test_ruff_clean_output_no_issues(self, tmp_path: Path) -> None:
        """Ruff with no errors means clean."""
        py_file = tmp_path / "app.py"
        py_file.write_text("x = 1\n")

        mock_result = MagicMock(returncode=0, stdout="", stderr="")

        def which_side_effect(name):
            if name == "ruff":
                return "/usr/bin/ruff"
            return None

        with (
            patch("_checkers.python.check_file_length", return_value=""),
            patch("_checkers.python._has_ruff_config", return_value=True),
            patch("_checkers.python.shutil.which", side_effect=which_side_effect),
            patch("_checkers.python.subprocess.run", return_value=mock_result),
        ):
            exit_code, reason = check_python(py_file)

        assert exit_code == 0
        assert reason == ""


class TestCheckPythonCommentsPreserved:
    """Regression test: check_python must not strip comments from user files."""

    def test_regular_comment_survives_check(self, tmp_path: Path) -> None:
        """Regular comments are preserved after check_python runs."""
        py_file = tmp_path / "app.py"
        py_file.write_text("x = 1  # important doc comment\n")

        with (
            patch("_checkers.python.check_file_length", return_value=""),
            patch("_checkers.python.shutil.which", return_value=None),
        ):
            check_python(py_file)

        assert "# important doc comment" in py_file.read_text()


class TestCheckPythonReadOnly:
    """Hooks must never modify user files."""

    def test_no_write_commands_invoked(self, tmp_path: Path) -> None:
        """check_python must not run ruff format or ruff check --fix."""
        py_file = tmp_path / "app.py"
        py_file.write_text("x = 1\n")

        mock_result = MagicMock(returncode=0, stdout="", stderr="")
        called_commands: list[list[str]] = []

        def run_side_effect(cmd, **_kwargs):
            called_commands.append(list(cmd))
            return mock_result

        with (
            patch("_checkers.python.check_file_length", return_value=""),
            patch("_checkers.python._has_ruff_config", return_value=True),
            patch("_checkers.python.shutil.which", return_value="/usr/bin/ruff"),
            patch("_checkers.python.subprocess.run", side_effect=run_side_effect),
        ):
            check_python(py_file)

        for cmd in called_commands:
            assert "format" not in cmd, f"Hook must not run ruff format: {cmd}"
            assert "--fix" not in cmd, f"Hook must not run ruff --fix: {cmd}"

    def test_file_content_unchanged_after_check(self, tmp_path: Path) -> None:
        """File content must be identical before and after check_python."""
        py_file = tmp_path / "app.py"
        original = "x = 'single quotes'\nimport os, sys\n"
        py_file.write_text(original)

        with (
            patch("_checkers.python.check_file_length", return_value=""),
            patch("_checkers.python.shutil.which", return_value=None),
        ):
            check_python(py_file)

        assert py_file.read_text() == original


class TestCheckPythonRuffOnly:
    """Verify basedpyright is NOT called (removed from per-edit hooks)."""

    def test_basedpyright_not_invoked_even_if_available(self, tmp_path: Path) -> None:
        """Even when basedpyright is on PATH, it is not called."""
        py_file = tmp_path / "app.py"
        py_file.write_text("x = 1\n")

        mock_result = MagicMock(returncode=0, stdout="", stderr="")
        called_commands: list[list[str]] = []

        def run_side_effect(cmd, **_kwargs):
            called_commands.append(cmd)
            return mock_result

        def which_side_effect(name):
            return f"/usr/bin/{name}" if name in ("ruff", "basedpyright") else None

        with (
            patch("_checkers.python.check_file_length", return_value=""),
            patch("_checkers.python._has_ruff_config", return_value=True),
            patch("_checkers.python.shutil.which", side_effect=which_side_effect),
            patch("_checkers.python.subprocess.run", side_effect=run_side_effect),
        ):
            check_python(py_file)

        invoked_binaries = [cmd[0] for cmd in called_commands]
        assert not any("basedpyright" in b for b in invoked_binaries)
