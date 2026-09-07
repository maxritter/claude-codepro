"""Tests for the charset (decorative non-ASCII) checker."""

from __future__ import annotations

from pathlib import Path

from _checkers.charset import check_charset

EM_DASH = "\u2014"
SMART_APOS = "\u2019"
ELLIPSIS = "\u2026"
RIGHT_ARROW = "\u2192"


class TestCheckCharset:
    def test_em_dash_in_shell_file_flagged(self, tmp_path: Path) -> None:
        f = tmp_path / "deploy.sh"
        f.write_text(f"echo 'start{EM_DASH}done'\n")
        reason = check_charset(f)
        assert "U+2014" in reason
        assert "1 decorative non-ASCII char" in reason

    def test_php_file_flagged(self, tmp_path: Path) -> None:
        """PHP slips both existing gates; the charset check must cover it."""
        f = tmp_path / "Controller.php"
        f.write_text(f"<?php // note{ELLIPSIS}\n")
        assert "U+2026" in check_charset(f)

    def test_multiple_codepoint_classes_reported_with_line_numbers(self, tmp_path: Path) -> None:
        f = tmp_path / "settings.cfg"
        f.write_text(f"a = b{SMART_APOS}c\nx {RIGHT_ARROW} y\n")
        reason = check_charset(f)
        assert "2 decorative non-ASCII chars" in reason
        assert "line 1" in reason and "U+2019" in reason
        assert "line 2" in reason and "U+2192" in reason

    def test_plain_ascii_returns_empty(self, tmp_path: Path) -> None:
        f = tmp_path / "script.sh"
        f.write_text("echo 'start -> done; range a-b'\n")
        assert check_charset(f) == ""

    def test_advice_preserves_intentional_unicode_literals(self, tmp_path: Path) -> None:
        f = tmp_path / "messages.ts"
        text = f'export const next = "Weiter {RIGHT_ARROW}";\n'
        f.write_text(text)
        reason = check_charset(f)
        assert "intentional" in reason
        assert "user-facing" in reason
        assert "Replace with ASCII" not in reason
        assert f.read_text() == text

    def test_markdown_excluded(self, tmp_path: Path) -> None:
        f = tmp_path / "README.md"
        f.write_text(f"A heading {EM_DASH} fine in prose.\n")
        assert check_charset(f) == ""

    def test_csv_data_file_allowlisted(self, tmp_path: Path) -> None:
        f = tmp_path / "data.csv"
        f.write_text(f"name,note\nfoo,{EM_DASH}\n")
        assert check_charset(f) == ""

    def test_binary_file_skipped_gracefully(self, tmp_path: Path) -> None:
        f = tmp_path / "blob.bin"
        f.write_bytes(b"\xff\xfe\x00\x01decorative\x80\x81")
        assert check_charset(f) == ""

    def test_truncates_to_ten_with_more_marker(self, tmp_path: Path) -> None:
        f = tmp_path / "many.txt"
        f.write_text("\n".join(f"line{EM_DASH}{i}" for i in range(12)) + "\n")
        reason = check_charset(f)
        assert "12 decorative non-ASCII chars" in reason
        assert "... and 2 more" in reason

    def test_added_text_scopes_scan_to_the_edit(self, tmp_path: Path) -> None:
        """With added_text, only the edit's text is scanned; the file body is ignored."""
        f = tmp_path / "deploy.sh"
        f.write_text(f"# old {EM_DASH} comment\necho clean\n")  # file already has an em-dash
        # The edit only introduced an ASCII line -> no warning for the old em-dash.
        assert check_charset(f, added_text="echo clean") == ""
        # A decorative char in the added text is still flagged.
        assert "U+2014" in check_charset(f, added_text=f"echo {EM_DASH}")
