"""Charset checker -- flags decorative non-ASCII codepoints in source files.

Enforces the no-emojis-in-source rule (em/en dashes, smart quotes, ellipsis,
arrows) at edit time. Unlike the language checkers, this runs for every written
text file, including types they never open (shell, .cfg, Dockerfile, PHP,
systemd units, manifests). Markdown and a small data-file allowlist are skipped.

The decorative codepoints are written as escape sequences (never literal) so
this module's own source stays pure ASCII and never trips its own check.
"""

from __future__ import annotations

import re
from pathlib import Path

# Decorative codepoints banned in non-Markdown source:
#   U+2010-2015  hyphens, en/em dashes, horizontal bar
#   U+2018/2019  curly single quotes
#   U+201C/201D  curly double quotes
#   U+2026       horizontal ellipsis
#   U+2190-21FF  arrows
_DECORATIVE_PATTERN = re.compile("[\u2010-\u2015\u2018\u2019\u201c\u201d\u2026\u2190-\u21ff]")

# Markdown + data files whose content may legitimately contain these chars.
_SKIP_SUFFIXES = frozenset({".md", ".markdown", ".csv", ".tsv"})

_MAX_REPORTED = 10


def check_charset(file_path: Path, added_text: str | None = None) -> str:
    """Scan for decorative non-ASCII. Returns a warning or empty string.

    When ``added_text`` is given (the text the current edit introduced), only
    that text is scanned, so pre-existing decorative chars in untouched code are
    left alone -- the edit hook must not nag about, or rewrite, old comments it
    never changed. When ``added_text`` is None the whole file is scanned.
    """
    if file_path.suffix.lower() in _SKIP_SUFFIXES:
        return ""

    if added_text is None:
        try:
            added_text = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            # Unreadable or binary (non-UTF-8) -- nothing to enforce.
            return ""

    hits: list[tuple[int, str]] = []
    for lineno, line in enumerate(added_text.splitlines(), start=1):
        for match in _DECORATIVE_PATTERN.finditer(line):
            hits.append((lineno, match.group()))

    if not hits:
        return ""

    return _format_charset_issues(file_path, hits)


def _format_charset_issues(file_path: Path, hits: list[tuple[int, str]]) -> str:
    """Format decorative-codepoint hits as a plain-text warning."""
    try:
        display_path = file_path.relative_to(Path.cwd())
    except ValueError:
        display_path = file_path

    count = len(hits)
    plural = "char" if count == 1 else "chars"
    lines = [f"Charset: {count} decorative non-ASCII {plural} in {display_path}"]
    for lineno, char in hits[:_MAX_REPORTED]:
        lines.append(f"  line {lineno}: {char!r} (U+{ord(char):04X})")
    if count > _MAX_REPORTED:
        lines.append(f"  ... and {count - _MAX_REPORTED} more")
    lines.append(
        "Use ASCII for incidental code decoration when it matches the project style. Preserve intentional "
        "Unicode in user-facing text, localization, data, and test fixtures; this heuristic cannot distinguish them."
    )
    return "\n".join(lines)
