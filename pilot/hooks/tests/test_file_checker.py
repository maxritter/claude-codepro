"""Tests for consolidated file_checker.py."""

from __future__ import annotations

import io
import json
from unittest.mock import patch

import pytest
from file_checker import _tdd_check, main

EM_DASH = "\u2014"


def _make_stdin(tool_name: str, file_path: str) -> io.StringIO:
    """Create a stdin mock with hook JSON data."""
    data = {"tool_name": tool_name, "tool_input": {"file_path": file_path}}
    return io.StringIO(json.dumps(data))


def _make_apply_patch_stdin(command: str) -> io.StringIO:
    """Create a stdin mock with apply_patch hook JSON data (Codex format)."""
    data = {"tool_name": "apply_patch", "tool_input": {"command": command}}
    return io.StringIO(json.dumps(data))


def _make_edit_stdin(file_path: str, old_string: str, new_string: str) -> io.StringIO:
    """Create a stdin mock for an Edit, including the old/new strings CC sends."""
    data = {
        "tool_name": "Edit",
        "tool_input": {
            "file_path": file_path,
            "old_string": old_string,
            "new_string": new_string,
        },
    }
    return io.StringIO(json.dumps(data))


def test_python_file_dispatches_to_python_checker(tmp_path):
    """Python files are handled by Python checker."""
    py_file = tmp_path / "test.py"
    py_file.write_text("print('hello')\n")

    with patch("sys.stdin", _make_stdin("Edit", str(py_file))):
        with patch("file_checker.check_python") as mock_check:
            mock_check.return_value = (0, "")
            result = main()

            mock_check.assert_called_once_with(py_file)
            assert result == 0


def test_typescript_file_dispatches_to_typescript_checker(tmp_path):
    """TypeScript files are handled by TypeScript checker."""
    ts_file = tmp_path / "test.ts"
    ts_file.write_text("const x = 1;\n")

    with patch("sys.stdin", _make_stdin("Edit", str(ts_file))):
        with patch("file_checker.check_typescript") as mock_check:
            mock_check.return_value = (0, "")
            result = main()

            mock_check.assert_called_once_with(ts_file)
            assert result == 0


def test_go_file_dispatches_to_go_checker(tmp_path):
    """Go files are handled by Go checker."""
    go_file = tmp_path / "test.go"
    go_file.write_text("package main\n")

    with patch("sys.stdin", _make_stdin("Edit", str(go_file))):
        with patch("file_checker.check_go") as mock_check:
            mock_check.return_value = (0, "")
            result = main()

            mock_check.assert_called_once_with(go_file)
            assert result == 0


def test_unsupported_file_returns_zero(tmp_path):
    """Unsupported files return 0."""
    md_file = tmp_path / "test.md"
    md_file.write_text("# Heading\n")

    with patch("sys.stdin", _make_stdin("Edit", str(md_file))):
        result = main()
        assert result == 0


def test_nonexistent_file_returns_zero():
    """Nonexistent files return 0."""
    with patch("sys.stdin", _make_stdin("Edit", "/nonexistent/file.py")):
        result = main()
        assert result == 0


@pytest.mark.parametrize(
    ("extension", "test_name", "test_body"),
    [
        (".py", "test_login_flow.py", "from src.auth import authenticate\n"),
        (".ts", "login-flow.test.ts", "import { authenticate } from '../src/auth';\n"),
    ],
)
def test_registered_checker_accepts_behavioral_coverage(tmp_path, extension, test_name, test_body):
    """The installed hook must accept coverage from tests named after a behavior."""
    source = tmp_path / "src"
    source.mkdir()
    implementation = source / f"auth{extension}"
    implementation.write_text("pass\n")
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / test_name).write_text(test_body)

    with patch("file_checker.should_skip", return_value=False):
        assert _tdd_check("Write", {"file_path": str(implementation)}, str(implementation)) == ""


@pytest.mark.parametrize("extension", [".py", ".ts", ".go", ".cs"])
def test_missing_test_reminder_does_not_require_a_new_test_file(tmp_path, extension):
    """File heuristics cannot prove a behavior is untested or mandate test layout."""
    implementation = tmp_path / f"auth{extension}"
    implementation.write_text("def authenticate(): return True\n")
    with patch("file_checker.should_skip", return_value=False):
        reason = _tdd_check("Write", {"file_path": str(implementation)}, str(implementation))

    assert reason
    assert "existing" in reason.lower()
    assert "creating" not in reason
    assert "No test covers" not in reason


class TestContextOutput:
    """Test additionalContext output on stdout."""

    def test_context_output_when_issues_found(self, tmp_path, capsys):
        """Should print additionalContext JSON when checker finds issues."""
        py_file = tmp_path / "app.py"
        py_file.write_text("x = 1\n")

        with patch("sys.stdin", _make_stdin("Edit", str(py_file))):
            with patch("file_checker.check_python") as mock_check:
                mock_check.return_value = (2, "Python: 3 ruff issues in app.py")
                main()

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert "hookSpecificOutput" in output
        assert output["hookSpecificOutput"]["hookEventName"] == "PostToolUse"
        assert "Python" in output["hookSpecificOutput"]["additionalContext"]

    def test_no_output_when_clean(self, tmp_path, capsys):
        """Should print nothing when checks pass."""
        py_file = tmp_path / "app.py"
        py_file.write_text("x = 1\n")

        with patch("sys.stdin", _make_stdin("Edit", str(py_file))):
            with patch("file_checker.check_python") as mock_check:
                mock_check.return_value = (0, "")
                with patch("file_checker._tdd_check", return_value=""):
                    main()

        captured = capsys.readouterr()
        assert captured.out == ""

    def test_no_output_for_unsupported_files(self, tmp_path, capsys):
        """Should not print anything for unsupported file types."""
        md_file = tmp_path / "readme.md"
        md_file.write_text("# Hello\n")

        with patch("sys.stdin", _make_stdin("Edit", str(md_file))):
            main()

        captured = capsys.readouterr()
        assert captured.out == ""


class TestCharsetEnforcement:
    """Charset check runs for all non-Markdown text files, including types the
    language checkers never open (shell, .cfg, Dockerfile, PHP, manifests)."""

    def test_shell_file_decorative_char_surfaced(self, tmp_path, capsys):
        """A shell file (never opened by language checkers) with an em-dash is flagged."""
        sh_file = tmp_path / "deploy.sh"
        sh_file.write_text("#!/bin/sh\necho 'start \u2014 done'\n")

        with patch("sys.stdin", _make_stdin("Edit", str(sh_file))):
            result = main()

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        context = output["hookSpecificOutput"]["additionalContext"]
        assert "U+2014" in context
        assert result == 0

    def test_markdown_file_decorative_char_ignored(self, tmp_path, capsys):
        """Markdown is excluded \u2014 decorative chars there produce no output."""
        md_file = tmp_path / "notes.md"
        md_file.write_text("A heading \u2014 with an em-dash is fine here.\n")

        with patch("sys.stdin", _make_stdin("Edit", str(md_file))):
            main()

        captured = capsys.readouterr()
        assert captured.out == ""

    def test_preexisting_decorative_char_in_untouched_code_not_flagged(self, tmp_path, capsys):
        """An edit that does not touch a pre-existing em-dash must not surface it.

        Reproduces the user report: editing one line should not flag decorative
        chars sitting in unrelated old code (which CC then 'fixes' and pushes).
        """
        sh_file = tmp_path / "deploy.sh"
        # Line 2 has a legacy em-dash; the edit only changes line 3.
        sh_file.write_text(f"#!/bin/sh\n# legacy note {EM_DASH} keep me\necho old\n")

        with patch("sys.stdin", _make_edit_stdin(str(sh_file), "echo old", "echo new")):
            main()

        captured = capsys.readouterr()
        assert captured.out == ""

    def test_newly_introduced_decorative_char_still_flagged(self, tmp_path, capsys):
        """A decorative char the edit actually adds is still surfaced."""
        sh_file = tmp_path / "deploy.sh"
        sh_file.write_text(f"#!/bin/sh\necho 'start {EM_DASH} done'\n")

        with patch(
            "sys.stdin",
            _make_edit_stdin(str(sh_file), "echo 'start done'", f"echo 'start {EM_DASH} done'"),
        ):
            result = main()

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert "U+2014" in output["hookSpecificOutput"]["additionalContext"]
        assert result == 0


class TestApplyPatchFormat:
    """Test Codex apply_patch tool_input format (command field instead of file_path)."""

    def test_apply_patch_extracts_file_path_from_update(self, tmp_path):
        """apply_patch with '*** Update File:' extracts the file path and runs checks."""
        py_file = tmp_path / "app.py"
        py_file.write_text("x = 1\n")

        command = f"*** Begin Patch\n*** Update File: {py_file}\n@@ -1,1 +1,1 @@\n-x = 1\n+x = 2\n*** End Patch"

        with patch("sys.stdin", _make_apply_patch_stdin(command)):
            with patch("file_checker.check_python") as mock_check:
                mock_check.return_value = (0, "")
                result = main()

                mock_check.assert_called_once_with(py_file)
                assert result == 0

    def test_apply_patch_extracts_file_path_from_add(self, tmp_path):
        """apply_patch with '*** Add File:' extracts the file path."""
        ts_file = tmp_path / "new.ts"
        ts_file.write_text("const x = 1;\n")

        command = f"*** Begin Patch\n*** Add File: {ts_file}\n+const x = 1;\n*** End Patch"

        with patch("sys.stdin", _make_apply_patch_stdin(command)):
            with patch("file_checker.check_typescript") as mock_check:
                mock_check.return_value = (0, "")
                result = main()

                mock_check.assert_called_once_with(ts_file)
                assert result == 0

    def test_apply_patch_handles_multiple_files(self, tmp_path):
        """apply_patch with multiple files runs checks on each."""
        py1 = tmp_path / "a.py"
        py2 = tmp_path / "b.py"
        py1.write_text("x = 1\n")
        py2.write_text("y = 2\n")

        command = (
            f"*** Begin Patch\n*** Update File: {py1}\n@@ -1 +1 @@\n-x = 1\n+x = 2\n"
            f"*** Update File: {py2}\n@@ -1 +1 @@\n-y = 2\n+y = 3\n*** End Patch"
        )

        with patch("sys.stdin", _make_apply_patch_stdin(command)):
            with patch("file_checker.check_python") as mock_check:
                mock_check.return_value = (0, "")
                result = main()

                assert mock_check.call_count == 2
                assert result == 0

    def test_apply_patch_no_command_returns_zero(self):
        """apply_patch without command field returns 0."""
        data = {"tool_name": "apply_patch", "tool_input": {}}
        with patch("sys.stdin", io.StringIO(json.dumps(data))):
            result = main()
            assert result == 0

    def test_apply_patch_decorative_char_scoped_to_its_own_file(self, tmp_path, capsys):
        """A decorative char added to one file in a multi-file patch must not be
        attributed to the other, clean file in the same patch."""
        dirty = tmp_path / "dirty.sh"
        clean = tmp_path / "clean.sh"
        dirty.write_text("echo old\n")
        clean.write_text("echo foo\n")

        command = (
            f"*** Begin Patch\n*** Update File: {dirty}\n@@ -1 +1 @@\n"
            f"-echo old\n+echo new {EM_DASH} done\n"
            f"*** Update File: {clean}\n@@ -1 +1 @@\n-echo foo\n+echo bar\n*** End Patch"
        )

        with patch("sys.stdin", _make_apply_patch_stdin(command)):
            main()

        context = capsys.readouterr().out
        assert "U+2014" in context  # the dirty file's added em-dash is flagged
        assert "dirty.sh" in context
        assert "clean.sh" not in context  # the clean file is NOT falsely flagged


class TestDotnetTddSuppression:
    """_tdd_check (the live path) suppresses reminders for logic-free C#, enforces otherwise.

    Each fixture lives in an isolated ``tmp_path`` with no accompanying ``*Tests.cs``,
    so ``has_dotnet_test_file``'s sibling/test-dir scan intentionally finds nothing and
    returns False — exercising the detector path under test, not real external I/O.
    """

    def _check(self, file_path: str) -> str:
        return _tdd_check("Write", {"file_path": file_path}, file_path)

    def test_logic_free_cs_file_emits_no_reminder(self, tmp_path):
        cs = tmp_path / "PersonDto.cs"
        cs.write_text("namespace App;\npublic record PersonDto(string Name, int Age);\n")
        assert self._check(str(cs)) == ""

    def test_cs_file_with_method_body_emits_reminder(self, tmp_path):
        cs = tmp_path / "Calc.cs"
        cs.write_text(
            "namespace App;\npublic class Calc\n{\n    public int Add(int a, int b)\n    {\n        return a + b;\n    }\n}\n"
        )
        assert "TDD Reminder" in self._check(str(cs))

    def test_razor_file_always_emits_reminder(self, tmp_path):
        razor = tmp_path / "Counter.razor"
        razor.write_text("<h1>Counter</h1>\n")
        assert "TDD Reminder" in self._check(str(razor))

    def test_integration_test_importing_module_suppresses_reminder(self, tmp_path):
        """A nearby test that references the module counts as coverage (parsimony),
        even without a sibling *Tests.cs — the live hook must honour it."""
        src = tmp_path / "src"
        src.mkdir()
        impl = src / "Order.cs"
        impl.write_text("namespace App;\npublic class Order\n{\n    public int Total() { return 1; }\n}\n")
        tests = tmp_path / "tests"
        tests.mkdir()
        (tests / "CheckoutFlowTests.cs").write_text(
            "using Xunit;\nnamespace T;\n"
            "public class CheckoutFlowTests\n{\n    [Fact] public void Pays() { var o = new Order(); }\n}\n"
        )
        assert self._check(str(impl)) == ""

    def test_file_inside_test_project_emits_no_reminder(self, tmp_path):
        """A .cs file inside a .NET test project (MyApp.Tests) is itself test code - the
        live TDD path must skip it, matching check_dotnet's project-name skip, even when
        the file's own stem does not end in Tests/Test."""
        proj = tmp_path / "MyApp.Tests"
        proj.mkdir()
        (proj / "MyApp.Tests.csproj").write_text("")
        helper = proj / "TestHelpers.cs"
        helper.write_text("namespace T;\npublic class TestHelpers\n{\n    public int Make() { return 1; }\n}\n")
        assert self._check(str(helper)) == ""

    def test_production_dir_with_test_in_name_still_enforces_tdd(self, tmp_path):
        """A production directory named ContextTest (PascalCase) must NOT skip TDD
        enforcement - only actual .NET test projects (with a .csproj) are exempt."""
        ctx = tmp_path / "ContextTest"
        ctx.mkdir()
        impl = ctx / "OrderService.cs"
        impl.write_text("namespace App;\npublic class OrderService\n{\n    public int Total() { return 1; }\n}\n")
        assert "TDD Reminder" in self._check(str(impl))

    def test_symbol_only_in_comment_does_not_suppress_reminder(self, tmp_path):
        """A test that mentions the module only in a comment must NOT count as coverage -
        the reference has to be in real code, not a `// TODO`."""
        src = tmp_path / "src"
        src.mkdir()
        impl = src / "Invoice.cs"
        impl.write_text("namespace App;\npublic class Invoice\n{\n    public int Total() { return 1; }\n}\n")
        tests = tmp_path / "tests"
        tests.mkdir()
        (tests / "OtherTests.cs").write_text(
            "using Xunit;\nnamespace T;\n"
            "public class OtherTests\n{\n    // TODO: test Invoice later\n"
            "    [Fact] public void Unrelated() { var x = 1; }\n}\n"
        )
        assert "TDD Reminder" in self._check(str(impl))
