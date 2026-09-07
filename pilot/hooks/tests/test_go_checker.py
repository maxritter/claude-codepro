"""Tests for Go file checker."""

from __future__ import annotations

import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from _checkers.go import check_go


@pytest.mark.skipif(shutil.which("go") is None, reason="Go toolchain unavailable")
def test_vet_uses_the_edited_files_package(tmp_path):
    """A valid reference to a sibling file must not produce a fabricated undefined-symbol error."""
    (tmp_path / "go.mod").write_text("module example.com/pilot-hook-regression\n\ngo 1.20\n")
    edited = tmp_path / "total.go"
    edited.write_text("package sample\n\nfunc Total() int { return quantity }\n")
    (tmp_path / "quantity.go").write_text("package sample\n\nconst quantity = 3\n")
    go_bin = shutil.which("go")
    with (
        patch("_checkers.go.check_file_length", return_value=""),
        patch("_checkers.go.shutil.which", side_effect=lambda name: go_bin if name == "go" else None),
    ):
        assert check_go(edited) == (0, "")


class TestCheckGoNoProject:
    """When no go.mod exists, skip go vet entirely."""

    def test_no_go_mod_skips_checks(self, tmp_path: Path) -> None:
        """No go.mod means go vet is skipped."""
        go_file = tmp_path / "main.go"
        go_file.write_text("package main\n")

        with patch("_checkers.go.check_file_length", return_value=""):
            exit_code, reason = check_go(go_file)

        assert exit_code == 0
        assert reason == ""

    def test_go_mod_enables_checks(self, tmp_path: Path) -> None:
        """go.mod in project root enables go vet."""
        go_file = tmp_path / "main.go"
        go_file.write_text("package main\n")
        (tmp_path / "go.mod").write_text("module example.com/foo\n")

        mock_result = MagicMock(returncode=0, stdout="", stderr="")

        with (
            patch("_checkers.go.check_file_length", return_value=""),
            patch("_checkers.go.shutil.which", side_effect=lambda name: f"/usr/bin/{name}" if name == "go" else None),
            patch("_checkers.go.subprocess.run", return_value=mock_result),
        ):
            exit_code, reason = check_go(go_file)

        assert exit_code == 0
        assert reason == ""


class TestCheckGoVetCounting:
    """Verify go vet issue counting excludes header lines."""

    def test_vet_count_excludes_package_header_lines(self, tmp_path: Path) -> None:
        """go vet prefixes output with '# package-name' headers that should not be counted as issues."""
        go_file = tmp_path / "main.go"
        go_file.write_text("package main\n")

        mock_result = MagicMock()
        mock_result.returncode = 2
        mock_result.stdout = ""
        mock_result.stderr = "# command-line-arguments\nvet: ./main.go:5:6: x declared and not used\n"

        with (
            patch("_checkers.go.check_file_length", return_value=""),
            patch("_checkers.go._has_go_project", return_value=True),
            patch("_checkers.go.shutil.which", side_effect=lambda name: f"/usr/bin/{name}" if name == "go" else None),
            patch("_checkers.go.subprocess.run", return_value=mock_result),
        ):
            exit_code, reason = check_go(go_file)

        assert exit_code == 0
        assert "1 vet" in reason, f"Expected '1 vet' but got: {reason}"

    def test_vet_count_with_multiple_issues_and_header(self, tmp_path: Path) -> None:
        """Multiple real issues should be counted, header excluded."""
        go_file = tmp_path / "main.go"
        go_file.write_text("package main\n")

        mock_result = MagicMock()
        mock_result.returncode = 2
        mock_result.stdout = ""
        mock_result.stderr = (
            "# command-line-arguments\n"
            "vet: ./main.go:5:6: x declared and not used\n"
            "vet: ./main.go:6:2: y declared and not used\n"
        )

        with (
            patch("_checkers.go.check_file_length", return_value=""),
            patch("_checkers.go._has_go_project", return_value=True),
            patch("_checkers.go.shutil.which", side_effect=lambda name: f"/usr/bin/{name}" if name == "go" else None),
            patch("_checkers.go.subprocess.run", return_value=mock_result),
        ):
            exit_code, reason = check_go(go_file)

        assert exit_code == 0
        assert "2 vet" in reason, f"Expected '2 vet' but got: {reason}"

    def test_vet_header_only_output_means_no_issues(self, tmp_path: Path) -> None:
        """If go vet returns only a header line with no actual issues, treat as clean."""
        go_file = tmp_path / "main.go"
        go_file.write_text("package main\n")

        mock_vet = MagicMock()
        mock_vet.returncode = 1
        mock_vet.stdout = ""
        mock_vet.stderr = "# command-line-arguments\n"

        with (
            patch("_checkers.go.check_file_length", return_value=""),
            patch("_checkers.go._has_go_project", return_value=True),
            patch("_checkers.go.shutil.which", side_effect=lambda name: f"/usr/bin/{name}" if name == "go" else None),
            patch("_checkers.go.subprocess.run", return_value=mock_vet),
        ):
            _, reason = check_go(go_file)

        assert reason == "", f"Expected no issues but got: {reason}"


class TestCheckGoCommentsPreserved:
    """Regression test: check_go must not strip comments from user files."""

    def test_regular_comment_survives_check(self, tmp_path: Path) -> None:
        """Regular comments are preserved after check_go runs."""
        go_file = tmp_path / "main.go"
        go_file.write_text("package main // important doc comment\n")

        with (
            patch("_checkers.go.check_file_length", return_value=""),
            patch("_checkers.go.shutil.which", return_value=None),
        ):
            check_go(go_file)

        assert "// important doc comment" in go_file.read_text()


class TestCheckGoReadOnly:
    """Hooks must never modify user files."""

    def test_no_write_commands_invoked(self, tmp_path: Path) -> None:
        """check_go must not run gofmt -w or any formatting command."""
        go_file = tmp_path / "main.go"
        go_file.write_text("package main\n")

        mock_result = MagicMock(returncode=0, stdout="", stderr="")
        called_commands: list[list[str]] = []

        def run_side_effect(cmd, **_kwargs):
            called_commands.append(list(cmd))
            return mock_result

        with (
            patch("_checkers.go.check_file_length", return_value=""),
            patch("_checkers.go._has_go_project", return_value=True),
            patch("_checkers.go._has_golangci_config", return_value=True),
            patch(
                "_checkers.go.shutil.which",
                side_effect=lambda name: f"/usr/bin/{name}" if name in ("go", "golangci-lint") else None,
            ),
            patch("_checkers.go.subprocess.run", side_effect=run_side_effect),
        ):
            check_go(go_file)

        for cmd in called_commands:
            assert "-w" not in cmd, f"Hook must not run gofmt -w: {cmd}"

    def test_file_content_unchanged_after_check(self, tmp_path: Path) -> None:
        """File content must be identical before and after check_go."""
        go_file = tmp_path / "main.go"
        original = "package main\n\nfunc main() {\n\tx := 1\n}\n"
        go_file.write_text(original)

        with (
            patch("_checkers.go.check_file_length", return_value=""),
            patch("_checkers.go.shutil.which", return_value=None),
        ):
            check_go(go_file)

        assert go_file.read_text() == original


class TestCheckGoTestFileSkip:
    """Test files should skip validation."""

    def test_test_files_skip_checks(self, tmp_path: Path) -> None:
        """Files ending in _test.go should return early."""
        go_file = tmp_path / "main_test.go"
        go_file.write_text("package main\n")

        exit_code, reason = check_go(go_file)

        assert exit_code == 0
        assert reason == ""


class TestCheckGoCleanFile:
    """Clean files should pass."""

    def test_clean_file_returns_success(self, tmp_path: Path) -> None:
        """Clean Go file should return exit 0 with empty reason."""
        go_file = tmp_path / "main.go"
        go_file.write_text("package main\n")

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""

        with (
            patch("_checkers.go.check_file_length", return_value=""),
            patch("_checkers.go._has_go_project", return_value=True),
            patch("_checkers.go.shutil.which", side_effect=lambda name: f"/usr/bin/{name}" if name == "go" else None),
            patch("_checkers.go.subprocess.run", return_value=mock_result),
        ):
            exit_code, reason = check_go(go_file)

        assert exit_code == 0
        assert reason == ""
