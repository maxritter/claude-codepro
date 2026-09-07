"""Tests for private, non-blocking tool-routing nudges."""

from __future__ import annotations

import json
import subprocess
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest
from tool_redirect import run_tool_redirect

HOOK_PATH = Path(__file__).resolve().parent.parent / "tool_redirect.py"


def _run_with_input(tool_name: str, tool_input: dict | None = None) -> tuple[int, str]:
    """Simulate hook invocation via direct import. Returns (exit_code, stdout_output)."""
    hook_data: dict = {"tool_name": tool_name}
    if tool_input is not None:
        hook_data["tool_input"] = tool_input
    stdin = StringIO(json.dumps(hook_data))
    with patch("sys.stdin", stdin), patch("sys.stdout", new_callable=StringIO) as stdout:
        code = run_tool_redirect()
        return code, stdout.getvalue()


def _run_subprocess(tool_name: str, tool_input: dict | None = None) -> tuple[int, str, str]:
    """Run the hook as a subprocess. Returns (exit_code, stdout, stderr)."""
    hook_data: dict[str, object] = {"tool_name": tool_name}
    if tool_input:
        hook_data["tool_input"] = tool_input
    result = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(hook_data),
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout, result.stderr


def _is_denied(stdout: str) -> bool:
    """Check if the hook output contains a deny decision."""
    try:
        data = json.loads(stdout.strip())
        return data.get("permissionDecision") == "deny"
    except (json.JSONDecodeError, ValueError):
        return False


def _has_warning_context(stdout: str) -> bool:
    """Check if the hook output contains additionalContext (warning, not block)."""
    try:
        data = json.loads(stdout.strip())
        hook_output = data.get("hookSpecificOutput", {})
        return bool(hook_output.get("additionalContext"))
    except (json.JSONDecodeError, ValueError):
        return False


def _is_suppressed(stdout: str) -> bool:
    try:
        return json.loads(stdout.strip()).get("suppressOutput") is True
    except (json.JSONDecodeError, ValueError):
        return False


class TestWebToolNudges:
    """Web tools remain available while the engine receives a private alternative."""

    def test_nudges_web_search(self):
        code, output = _run_with_input("WebSearch", {"query": "python tutorial"})
        assert code == 0
        assert _has_warning_context(output)
        assert _is_suppressed(output)
        assert not _is_denied(output)

    def test_web_advice_is_once_per_tool_and_does_not_invent_a_tool_id(self):
        _, first = _run_with_input("WebSearch", {"query": "official API documentation"})
        _, second = _run_with_input("WebSearch", {"query": "official release notes"})
        assert _has_warning_context(first)
        assert "mcp__plugin_" not in first
        assert second == ""
        _, fetch = _run_with_input("WebFetch", {"url": "https://example.com"})
        assert _has_warning_context(fetch)

    @pytest.mark.parametrize(
        "url",
        [
            "https://example.com",
            "https://claude.ai/chats",
            "http://claude.ai/code/artifact/123e4567-e89b-12d3-a456-426614174000",
            "https://claude.ai.evil.example/code/artifact/123e4567-e89b-12d3-a456-426614174000",
            "https://preview.claude.ai.evil.example/123e4567-e89b-12d3-a456-426614174000",
        ],
    )
    def test_nudges_web_fetch(self, url: str):
        code, output = _run_with_input("WebFetch", {"url": url})
        assert code == 0
        assert _has_warning_context(output)
        assert _is_suppressed(output)
        assert not _is_denied(output)

    @pytest.mark.parametrize(
        "url",
        [
            "https://claude.ai/code/artifact/123e4567-e89b-12d3-a456-426614174000",
            "https://preview.claude.ai/123e4567-e89b-12d3-a456-426614174000",
        ],
    )
    def test_allows_web_fetch_for_authenticated_claude_artifacts(self, url: str):
        code, output = _run_with_input("WebFetch", {"url": url})
        assert code == 0
        assert output == ""


class TestAgentPassthrough:
    """All Agent calls pass through silently - no output."""

    def test_allows_plan_agent(self):
        code, output = _run_with_input("Agent", {"subagent_type": "Plan", "prompt": "plan impl"})
        assert code == 0
        assert output == ""

    def test_allows_explore_agent(self):
        code, output = _run_with_input("Agent", {"subagent_type": "Explore", "prompt": "find files"})
        assert code == 0
        assert output == ""

    def test_allows_agent_general_purpose(self):
        code, output = _run_with_input(
            "Agent", {"subagent_type": "general-purpose", "description": "Fix test failures", "prompt": "fix"}
        )
        assert code == 0
        assert output == ""

    def test_allows_agent_without_subagent_type(self):
        code, output = _run_with_input("Agent", {"description": "Run test suite", "prompt": "do something"})
        assert code == 0
        assert output == ""


class TestResearchDescriptionAllowed:
    """Agent with a 'Research' description passes through silently - the block was
    removed (Research is the same read-only fan-out category as Explore)."""

    def test_allows_research_first_word(self):
        code, output = _run_with_input("Agent", {"description": "Research Extensions system", "prompt": "explore"})
        assert code == 0
        assert output == ""

    def test_allows_research_case_insensitive(self):
        code, output = _run_with_input("Agent", {"description": "research codebase architecture", "prompt": "explore"})
        assert code == 0
        assert output == ""

    def test_allows_research_not_first_word(self):
        code, output = _run_with_input("Agent", {"description": "Find research papers", "prompt": "search"})
        assert code == 0
        assert output == ""

    def test_allows_research_midsentence(self):
        code, output = _run_with_input("Agent", {"description": "Do some research work", "prompt": "explore"})
        assert code == 0
        assert output == ""


class TestExploreDescriptionAllowed:
    """Agent with 'Explore' in the description passes through silently - the block
    was removed so an Explore / general-purpose fan-out is no longer denied."""

    def test_allows_explore_first_word(self):
        code, output = _run_with_input(
            "Agent",
            {"subagent_type": "general-purpose", "description": "Explore console UI codebase", "prompt": "look around"},
        )
        assert code == 0
        assert output == ""

    def test_allows_explore_mid_sentence(self):
        code, output = _run_with_input("Agent", {"description": "Deep explore of auth module", "prompt": "search"})
        assert code == 0
        assert output == ""

    def test_allows_explore_case_insensitive(self):
        code, output = _run_with_input("Agent", {"description": "EXPLORE the project structure", "prompt": "look"})
        assert code == 0
        assert output == ""

    def test_allows_explore_no_subagent_type(self):
        code, output = _run_with_input(
            "Agent", {"description": "Explore and understand the codebase", "prompt": "look"}
        )
        assert code == 0
        assert output == ""


class TestAllowedSpecReviewerAgents:
    """/spec reviewer agents pass through silently — no warning."""

    def test_allows_spec_review(self):
        code, output = _run_with_input("Agent", {"subagent_type": "spec-review", "prompt": "review plan"})
        assert code == 0
        assert output == ""

    def test_allows_changes_review(self):
        code, output = _run_with_input("Agent", {"subagent_type": "changes-review", "prompt": "review code"})
        assert code == 0
        assert output == ""


class TestAllowedReviewerAgents:
    """Whitelisted reviewer agents pass through silently, including when their
    description contains 'Research'/'Explore' (guards against a future
    description-based block re-catching a reviewer)."""

    def test_changes_review_bypasses_research_pattern(self):
        """A whitelisted reviewer with a 'Research' description must NOT be blocked."""
        code, output = _run_with_input(
            "Agent",
            {"subagent_type": "changes-review", "description": "Research competitor landscape", "prompt": "review"},
        )
        assert code == 0
        assert output == ""

    def test_spec_review_bypasses_explore_pattern(self):
        """spec-review with 'Explore' description must NOT be blocked."""
        code, output = _run_with_input(
            "Agent",
            {"subagent_type": "spec-review", "description": "Explore alignment with spec", "prompt": "review"},
        )
        assert code == 0
        assert output == ""

    def test_changes_review_bypasses_explore_pattern(self):
        """changes-review with 'Explore' description must NOT be blocked."""
        code, output = _run_with_input(
            "Agent",
            {"subagent_type": "changes-review", "description": "Explore code changes", "prompt": "review"},
        )
        assert code == 0
        assert output == ""


class TestAllowedTools:
    """Tests for tools that should pass through."""

    def test_allows_read(self):
        code, _ = _run_with_input("Read", {"file_path": "/foo.py"})
        assert code == 0

    def test_allows_write(self):
        code, _ = _run_with_input("Write", {"file_path": "/foo.py"})
        assert code == 0

    def test_allows_edit(self):
        code, _ = _run_with_input("Edit", {"file_path": "/foo.py"})
        assert code == 0

    def test_allows_bash(self):
        code, _ = _run_with_input("Bash", {"command": "ls"})
        assert code == 0

    def test_allows_grep(self):
        code, _ = _run_with_input("Grep", {"pattern": "where is config loaded"})
        assert code == 0

    def test_allows_task_create(self):
        code, _ = _run_with_input("TaskCreate", {"subject": "test"})
        assert code == 0

    def test_allows_bash_background(self):
        code, _ = _run_with_input("Bash", {"command": "npm run dev", "run_in_background": True})
        assert code == 0


class TestGrepPatterns:
    """Grep with both semantic and literal patterns passes through."""

    def test_grep_semantic_patterns_allowed(self):
        semantic_patterns = [
            "where is authentication handled",
            "how does the config loader work",
            "find the error handler",
            "locate the user validation",
            "what is the main entry point",
            "search for config files",
            "looking for authentication",
        ]
        for pattern in semantic_patterns:
            code, _ = _run_with_input("Grep", {"pattern": pattern})
            assert code == 0, f"Grep with pattern '{pattern}' should be allowed"

    def test_grep_literal_patterns_allowed(self):
        literal_patterns = [
            "def process_order",
            "class UserService",
            "import json",
            "TODO:",
            "FIXME",
            "config",
            "handler",
            "= None",
            "function handleClick",
            "const foo",
            "interface User",
        ]
        for pattern in literal_patterns:
            code, _ = _run_with_input("Grep", {"pattern": pattern})
            assert code == 0, f"Grep with literal pattern '{pattern}' should be allowed"


class TestEdgeCases:
    """Tests for malformed input and edge cases."""

    def test_handles_invalid_json(self):
        stdin = StringIO("not json")
        with patch("sys.stdin", stdin):
            assert run_tool_redirect() == 0

    def test_handles_empty_stdin(self):
        stdin = StringIO("")
        with patch("sys.stdin", stdin):
            assert run_tool_redirect() == 0

    def test_handles_missing_tool_name(self):
        stdin = StringIO(json.dumps({"tool_input": {}}))
        with patch("sys.stdin", stdin):
            assert run_tool_redirect() == 0


class TestSubprocessIntegration:
    """Subprocess-level tests — verify the hook works as a standalone process."""

    def test_websearch_is_privately_nudged(self):
        exit_code, stdout, stderr = _run_subprocess("WebSearch")
        assert exit_code == 0
        assert not _is_denied(stdout)
        assert _has_warning_context(stdout)
        assert _is_suppressed(stdout)
        assert stderr == ""

    def test_webfetch_is_privately_nudged(self):
        exit_code, stdout, stderr = _run_subprocess("WebFetch")
        assert exit_code == 0
        assert not _is_denied(stdout)
        assert _has_warning_context(stdout)
        assert _is_suppressed(stdout)
        assert stderr == ""

    def test_other_tools_allowed(self):
        for tool in ["Read", "Write", "Bash", "Glob", "Edit"]:
            exit_code, stdout, _ = _run_subprocess(tool)
            assert exit_code == 0, f"{tool} should be allowed"
            assert not _is_denied(stdout)

    def test_agent_passthrough_silent(self):
        exit_code, stdout, _ = _run_subprocess("Agent", {"description": "Fix test suite"})
        assert exit_code == 0
        assert stdout.strip() == ""

    def test_research_agent_allowed(self):
        exit_code, stdout, _ = _run_subprocess("Agent", {"description": "Research API design"})
        assert exit_code == 0
        assert not _is_denied(stdout)

    def test_spec_reviewers_silent(self):
        for subagent in ["changes-review", "spec-review"]:
            exit_code, stdout, _ = _run_subprocess("Agent", {"subagent_type": subagent})
            assert exit_code == 0
            assert not _is_denied(stdout)
            assert not _has_warning_context(stdout)

    def test_explore_agent_allowed(self):
        exit_code, stdout, _ = _run_subprocess("Agent", {"subagent_type": "Explore"})
        assert exit_code == 0
        assert not _is_denied(stdout)

    def test_plan_agent_allowed(self):
        exit_code, stdout, _ = _run_subprocess("Agent", {"subagent_type": "Plan"})
        assert exit_code == 0
        assert stdout == ""

    def test_explore_description_allowed(self):
        exit_code, stdout, _ = _run_subprocess(
            "Agent", {"subagent_type": "general-purpose", "description": "Explore console UI codebase"}
        )
        assert exit_code == 0
        assert not _is_denied(stdout)

    def test_whitelisted_reviewer_allowed_with_research_description(self):
        exit_code, stdout, _ = _run_subprocess(
            "Agent", {"subagent_type": "changes-review", "description": "Research competitor landscape"}
        )
        assert exit_code == 0
        assert not _is_denied(stdout)

    def test_whitelisted_reviewer_allowed_with_explore_description(self):
        exit_code, stdout, _ = _run_subprocess(
            "Agent", {"subagent_type": "spec-review", "description": "Explore alternatives"}
        )
        assert exit_code == 0
        assert not _is_denied(stdout)


# ---------------------------------------------------------------------------
# Search-nudge classifier tests (originally added 2026-04-29 for codegraph search-tool enforcement)
# ---------------------------------------------------------------------------


def _has_nudge(output: str) -> bool:
    """Check whether the hook stdout contains an additionalContext nudge."""
    if not output.strip():
        return False
    try:
        data = json.loads(output.strip())
    except (json.JSONDecodeError, ValueError):
        return False
    hook_output = data.get("hookSpecificOutput", {})
    return bool(hook_output.get("additionalContext"))


def _nudge_text(output: str) -> str:
    """Extract additionalContext string (or empty)."""
    try:
        data = json.loads(output.strip())
    except (json.JSONDecodeError, ValueError):
        return ""
    return data.get("hookSpecificOutput", {}).get("additionalContext", "")


@pytest.fixture(autouse=True)
def isolate_hook_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))


@pytest.fixture
def fresh_throttle(tmp_path, monkeypatch):
    """Redirect the throttle sentinel to a per-test file so each test starts fresh.

    The implementation exposes `_throttle_sentinel_path()` returning the sentinel
    Path; tests monkeypatch it to point at tmp_path.
    """
    import tool_redirect as tr

    sentinel = tmp_path / "search_nudge_sent.json"
    monkeypatch.setattr(tr, "_throttle_sentinel_path", lambda: sentinel)
    return sentinel


@pytest.mark.usefixtures("fresh_throttle")
class TestSearchNudgeBashGrep:
    """Bash(grep ...) recursive search → nudge."""

    def test_nudges_grep_short_recursive(self):
        code, output = _run_with_input("Bash", {"command": "grep -rn 'foo' ./src"})
        assert code == 0
        assert _has_nudge(output)
        text = _nudge_text(output)
        assert "codegraph_explore" in text or "codegraph" in text
        assert "semble search" in text or "semble" in text

    def test_nudges_grep_capital_R(self):
        code, output = _run_with_input("Bash", {"command": "grep -R pattern ."})
        assert code == 0
        assert _has_nudge(output)

    def test_nudges_grep_long_recursive(self):
        code, output = _run_with_input("Bash", {"command": "grep --recursive 'x' ."})
        assert code == 0
        assert _has_nudge(output)

    def test_nudges_grep_recursive_listfiles(self):
        code, output = _run_with_input("Bash", {"command": "grep -rl pattern ."})
        assert code == 0
        assert _has_nudge(output)

    def test_nudges_grep_with_include(self):
        code, output = _run_with_input("Bash", {"command": "grep --include='*.py' -r pattern ."})
        assert code == 0
        assert _has_nudge(output)

    def test_nudges_grep_with_time_prefix(self):
        code, output = _run_with_input("Bash", {"command": "time grep -r foo ."})
        assert code == 0
        assert _has_nudge(output)

    def test_nudges_grep_with_sudo_prefix(self):
        code, output = _run_with_input("Bash", {"command": "sudo grep -r foo ."})
        assert code == 0
        assert _has_nudge(output)

    def test_nudges_grep_with_nice_prefix(self):
        code, output = _run_with_input("Bash", {"command": "nice grep -r foo ."})
        assert code == 0
        assert _has_nudge(output)

    def test_nudges_compound_segment(self):
        code, output = _run_with_input("Bash", {"command": "cd src && grep -r foo ."})
        assert code == 0
        assert _has_nudge(output)


@pytest.mark.usefixtures("fresh_throttle")
class TestSearchNudgeBashRg:
    def test_nudges_rg_default_recursive(self):
        code, output = _run_with_input("Bash", {"command": "rg 'pattern' ."})
        assert code == 0
        assert _has_nudge(output)

    def test_nudges_rg_no_path(self):
        code, output = _run_with_input("Bash", {"command": "rg pattern"})
        assert code == 0
        assert _has_nudge(output)

    def test_nudges_rg_files_mode(self):
        code, output = _run_with_input("Bash", {"command": "rg --files"})
        assert code == 0
        assert _has_nudge(output)
        assert "codegraph_explore" in _nudge_text(output)


@pytest.mark.usefixtures("fresh_throttle")
class TestSearchNudgeBashFind:
    def test_nudges_find_with_name(self):
        code, output = _run_with_input("Bash", {"command": "find . -name '*.py'"})
        assert code == 0
        assert _has_nudge(output)
        assert "codegraph_explore" in _nudge_text(output)

    def test_nudges_find_with_iname(self):
        code, output = _run_with_input("Bash", {"command": "find . -iname '*.PY'"})
        assert code == 0
        assert _has_nudge(output)

    def test_nudges_find_with_type_only(self):
        code, output = _run_with_input("Bash", {"command": "find . -type f"})
        assert code == 0
        assert _has_nudge(output)

    def test_nudges_find_with_type_and_delete(self):
        code, output = _run_with_input("Bash", {"command": "find . -type f -delete"})
        assert code == 0
        assert _has_nudge(output)

    def test_nudges_find_subdir_with_name(self):
        code, output = _run_with_input("Bash", {"command": "find ./src -name '*.ts'"})
        assert code == 0
        assert _has_nudge(output)


@pytest.mark.usefixtures("fresh_throttle")
class TestSearchNudgeBashFdAg:
    def test_nudges_fd_with_pattern(self):
        code, output = _run_with_input("Bash", {"command": "fd config"})
        assert code == 0
        assert _has_nudge(output)

    def test_nudges_fd_no_args(self):
        code, output = _run_with_input("Bash", {"command": "fd"})
        assert code == 0
        assert _has_nudge(output)

    def test_nudges_ag_basic(self):
        code, output = _run_with_input("Bash", {"command": "ag 'TODO'"})
        assert code == 0
        assert _has_nudge(output)


@pytest.mark.usefixtures("fresh_throttle")
class TestSearchNudgeNegatives:
    """Cases that must NOT produce a nudge."""

    def test_native_read_preference_grep_single_file(self):
        code, output = _run_with_input("Bash", {"command": "grep ERROR /var/log/app.log"})
        assert code == 0
        assert "separate native tool calls" in _nudge_text(output)

    def test_native_read_preference_grep_n_single_file(self):
        code, output = _run_with_input("Bash", {"command": "grep -n pattern src/file.py"})
        assert code == 0
        assert "separate native tool calls" in _nudge_text(output)

    def test_native_read_preference_rg_single_file(self):
        code, output = _run_with_input("Bash", {"command": "rg pattern src/main.ts"})
        assert code == 0
        assert "separate native tool calls" in _nudge_text(output)

    def test_no_nudge_git_grep(self):
        code, output = _run_with_input("Bash", {"command": "git grep 'foo'"})
        assert code == 0
        assert not _has_nudge(output)

    def test_no_nudge_git_grep_with_args(self):
        code, output = _run_with_input("Bash", {"command": "git grep -n pattern -- '*.py'"})
        assert code == 0
        assert not _has_nudge(output)

    def test_no_nudge_curl_pipe_grep(self):
        code, output = _run_with_input("Bash", {"command": "curl https://example.com | grep error"})
        assert code == 0
        assert not _has_nudge(output)

    def test_native_read_preference_cat_pipe_grep(self):
        code, output = _run_with_input("Bash", {"command": "cat foo.log | grep WARN"})
        assert code == 0
        assert "separate native tool calls" in _nudge_text(output)

    def test_no_nudge_echo_pipe_grep(self):
        code, output = _run_with_input("Bash", {"command": "echo $PATH | grep node"})
        assert code == 0
        assert not _has_nudge(output)

    def test_no_nudge_xargs_grep(self):
        # Composed command via xargs — pipeline filtering, lean conservative.
        code, output = _run_with_input("Bash", {"command": "ls *.py | xargs grep foo"})
        assert code == 0
        assert not _has_nudge(output)

    def test_no_nudge_npm_install(self):
        code, output = _run_with_input("Bash", {"command": "npm install"})
        assert code == 0
        assert not _has_nudge(output)

    def test_no_nudge_uv_pytest(self):
        code, output = _run_with_input("Bash", {"command": "uv run pytest -q"})
        assert code == 0
        assert not _has_nudge(output)

    def test_no_nudge_ls_grep_filter(self):
        code, output = _run_with_input("Bash", {"command": "ls -la | grep '\\.py$'"})
        assert code == 0
        assert not _has_nudge(output)


class TestThrottleSentinelPath:
    """_throttle_sentinel_path() session-directory resolution."""

    def test_falls_back_to_agent_native_id_when_pilot_session_id_unset(self, tmp_path: Path) -> None:
        """Issue #157: a session launched outside the shell wrapper (IDE/desktop) has no
        PILOT_SESSION_ID but always has CLAUDE_CODE_SESSION_ID set by the harness. The
        search-nudge throttle sentinel must follow the same agent-native chain as the rest
        of the hook layer (_lib/util.py:resolve_session_id()), not collapse to the shared
        'default' bucket that every other non-wrapper session also writes to.
        """
        import os

        from tool_redirect import _throttle_sentinel_path

        with (
            patch.dict(os.environ, {"CLAUDE_CODE_SESSION_ID": "cc-uuid-9999"}, clear=True),
            patch("tool_redirect.Path.home", return_value=tmp_path),
        ):
            result = _throttle_sentinel_path()
            assert result == tmp_path / ".pilot" / "sessions" / "cc-uuid-9999" / "search_nudge_sent.json"


class TestSearchNudgeThrottle:
    @pytest.mark.usefixtures("fresh_throttle")
    def test_throttle_grep_only_first_call_nudges(self):
        code1, out1 = _run_with_input("Bash", {"command": "grep -r foo ."})
        assert code1 == 0
        assert _has_nudge(out1)
        code2, out2 = _run_with_input("Bash", {"command": "grep -r bar ."})
        assert code2 == 0
        assert not _has_nudge(out2)

    @pytest.mark.usefixtures("fresh_throttle")
    def test_throttle_separate_categories(self):
        _, out1 = _run_with_input("Bash", {"command": "grep -r foo ."})
        assert _has_nudge(out1)
        # Different category — must still nudge
        _, out2 = _run_with_input("Bash", {"command": "rg pattern ."})
        assert _has_nudge(out2)

    @pytest.mark.usefixtures("fresh_throttle")
    def test_throttle_find_separate_from_grep(self):
        _, out1 = _run_with_input("Bash", {"command": "grep -r foo ."})
        assert _has_nudge(out1)
        _, out2 = _run_with_input("Bash", {"command": "find src -name '*.py'"})
        assert _has_nudge(out2)

    def test_throttle_corrupt_sentinel_file(self, fresh_throttle):
        # Pre-write malformed JSON; throttle should treat as never-sent.
        fresh_throttle.parent.mkdir(parents=True, exist_ok=True)
        fresh_throttle.write_text("not json {{{")
        code, output = _run_with_input("Bash", {"command": "grep -r foo ."})
        assert code == 0
        assert _has_nudge(output)

    @pytest.mark.usefixtures("fresh_throttle")
    def test_throttle_no_session_id(self, monkeypatch):
        monkeypatch.delenv("PILOT_SESSION_ID", raising=False)
        code, output = _run_with_input("Bash", {"command": "grep -r foo ."})
        assert code == 0
        # With sentinel monkeypatched the env var isn't even read, but ensure no crash.
        assert _has_nudge(output)


@pytest.mark.usefixtures("fresh_throttle")
class TestSearchNudgeSafety:
    """Hook never denies or crashes on bad input."""

    def test_search_nudge_never_denies_on_bash_grep(self):
        code, output = _run_with_input("Bash", {"command": "grep -r foo ."})
        assert code == 0
        try:
            data = json.loads(output.strip())
            assert data.get("permissionDecision") != "deny"
        except (json.JSONDecodeError, ValueError):
            pass  # additionalContext payload is fine

    def test_search_nudge_never_denies_on_grep_tool(self):
        code, output = _run_with_input("Grep", {"pattern": "foo"})
        assert code == 0
        assert not _is_denied(output)

    def test_search_nudge_never_denies_on_glob_tool(self):
        code, output = _run_with_input("Glob", {"pattern": "**/*.py"})
        assert code == 0
        assert not _is_denied(output)

    def test_git_write_commands_no_longer_denied(self):
        # The dangerous-git deny-list was removed from the hook; git write commands
        # (force push, hard reset, etc.) now pass through untouched - authorization
        # is the social rule's job, not a hard block. Regression guard against
        # anyone re-introducing a git deny in this hook.
        code, output = _run_with_input("Bash", {"command": "git push --force origin main"})
        assert code == 0
        assert not _is_denied(output)

    def test_websearch_never_denies(self):
        code, output = _run_with_input("WebSearch", {"query": "x"})
        assert code == 0
        assert not _is_denied(output)
        assert _is_suppressed(output)

    def test_explore_agent_now_allowed(self):
        code, output = _run_with_input("Agent", {"subagent_type": "Explore", "prompt": "find files"})
        assert code == 0
        assert not _is_denied(output)


def _has_edit_tool_nudge(stdout: str) -> bool:
    """Check for the shell-file-edit reminder (additionalContext, never a deny)."""
    try:
        data = json.loads(stdout.strip())
    except (json.JSONDecodeError, ValueError):
        return False
    context = data.get("hookSpecificOutput", {}).get("additionalContext", "")
    return "Edit tool" in context and "Write" in context


class TestShellFileEditNudge:
    """Shell commands that edit files get a non-blocking reminder to use Edit/Write.

    Claude Code's bypass-permissions mode tells the model to prefer heredocs,
    sed and inline scripts over the dedicated edit tools; those edits render no
    diff in the terminal. The reminder steers the next edit back to Edit/Write
    without ever blocking a command - a false match must cost nothing.
    """

    SCRATCH = "/private/tmp/claude-501/-Users-max-repos-x/abc/scratchpad"

    @pytest.mark.parametrize(
        "command",
        [
            "sed -i 's/foo/bar/' src/app.py",
            "sed -i.bak -e 's/foo/bar/' launcher/cli.py",
            "perl -pi -e 's/foo/bar/' Makefile",
            "cat > src/new_module.py <<'EOF'\nprint('hi')\nEOF",
            "cat <<EOF > notes.md\nhello\nEOF",
            'echo "export X=1" >> .envrc',
            "printf '{}' > config.json",
            'python3 - <<\'EOF\'\nfrom pathlib import Path\nPath("a.py").write_text("x")\nEOF',
            "python3 -c \"open('a.py','w').write('x')\"",
            "uv run python - <<'EOF'\nimport json\njson.dump({}, open('cfg.json', 'w'))\nEOF",
            "node -e \"require('fs').writeFileSync('a.js','x')\"",
            "bun -e \"await Bun.write('a.ts', 'x')\"",
            "npm test 2>&1 | tee test-output.log",
            "cd console && bun run build && echo done > BUILD_OK",
        ],
    )
    def test_reminds_on_shell_file_edits_without_blocking(self, command: str):
        code, output = _run_with_input("Bash", {"command": command})
        assert code == 0, command
        assert not _is_denied(output), command
        assert _has_edit_tool_nudge(output), command

    def test_reminder_is_once_per_session(self, tmp_path):
        """A generic editing preference does not need repeating on every edit."""
        with patch("tool_redirect._throttle_sentinel_path", return_value=tmp_path / "nudge.json"):
            code, first = _run_with_input("Bash", {"command": "sed -i 's/a/b/' src/app.py"})
            assert code == 0
            assert _has_edit_tool_nudge(first)
            _, second = _run_with_input("Bash", {"command": "sed -i 's/b/c/' src/app.py"})
            assert second == ""

    @pytest.mark.parametrize(
        "command",
        [
            "cat src/app.py",
            "sed -n '1,40p' src/app.py",
            "grep -n foo src/app.py",
            "echo hi",
            "echo hi > /dev/null",
            "echo warn >&2",
            "uv run pytest -q 2>&1 | tail -3",
            "bun test > /tmp/out.txt",
            "bun test 2>&1 | tee /tmp/out.txt",
            'python3 -c "print(1)"',
            "python3 - <<'EOF'\nprint(open(\"a.py\").read())\nEOF",
            "git commit -m \"$(cat <<'EOF'\nfix: message\nEOF\n)\"",
            "git diff --stat",
            "ls -la && pwd",
        ],
    )
    def test_stays_silent_for_read_only_and_temp_shell(self, command: str):
        code, output = _run_with_input("Bash", {"command": command})
        assert code == 0, command
        assert not _has_edit_tool_nudge(output), command

    def test_stays_silent_for_writes_into_the_scratchpad(self):
        code, output = _run_with_input("Bash", {"command": f"cat > {self.SCRATCH}/verify.ts <<'EOF'\nx\nEOF"})
        assert code == 0
        assert not _has_edit_tool_nudge(output)

    def test_edit_reminder_takes_precedence_over_search_nudge(self, tmp_path):
        with patch("tool_redirect._throttle_sentinel_path", return_value=tmp_path / "nudge.json"):
            code, output = _run_with_input("Bash", {"command": "grep -rn foo . > matches.txt"})
        assert code == 0
        assert _has_edit_tool_nudge(output)


class TestNativeFileReadPreference:
    @pytest.mark.parametrize(
        "command",
        [
            "cat src/index.css",
            "cat src/pages/Index.tsx src/components/Header.tsx src/components/Footer.tsx",
            "cat app/src/lib/db-api.ts",
            "sed -n 36,62p docs/db-api-findings.md; echo '===== vite relay'; grep -n relay app/vite.config.ts | head -30",
            "sed -n '85,150p' app/vite.config.ts; curl -s https://example.com; sed -n '760,800p' app/src/lib/db-api.ts",
            "head -30 'docs/my notes.md'",
            "tail -40 src/main.ts",
            "grep -n 'const UA' app/vite.config.ts",
            "rg -n 'messages' app/src/lib/db-api.ts",
            "rtk read app/src/lib/db-api.ts",
            "rtk proxy sed -n '1,20p' app/vite.config.ts",
        ],
    )
    def test_each_file_inspection_gets_a_private_native_tool_reminder(self, command: str) -> None:
        code, first = _run_with_input("Bash", {"command": command})
        assert code == 0
        context = json.loads(first)["hookSpecificOutput"]["additionalContext"]
        assert "Read" in context and "Grep" in context and "Glob" in context
        assert "separate native tool calls" in context
        assert "echo" in context
        assert "permissionDecision" not in json.loads(first)["hookSpecificOutput"]
        assert _is_suppressed(first)
        _, second = _run_with_input("Bash", {"command": command})
        assert second == first

    @pytest.mark.parametrize(
        "tool,arguments",
        [
            ("Read", {"file_path": "app/vite.config.ts", "offset": 85, "limit": 65}),
            ("Grep", {"pattern": "relay", "path": "app/vite.config.ts"}),
            ("Glob", {"pattern": "app/src/**/*.ts"}),
        ],
    )
    def test_native_file_tools_are_silent(self, tool: str, arguments: dict) -> None:
        assert _run_with_input(tool, arguments) == (0, "")

    @pytest.mark.parametrize(
        "command",
        [
            "curl -s https://example.com | grep error",
            "git diff --stat",
            "git log -5 | head -20",
            "bun test 2>&1 | tail -30",
            "tail -f /tmp/service.log",
            "cat /dev/null",
            "cat <<'EOF'\nrequest body\nEOF",
            'python3 -c \'import json; print(json.load(open("package.json"))["version"])\'',
        ],
    )
    def test_shell_processing_and_live_streams_are_not_file_read_nudges(self, command: str) -> None:
        _, output = _run_with_input("Bash", {"command": command})
        assert "separate native tool calls" not in output

    def test_codex_payload_does_not_receive_claude_native_tool_names(self) -> None:
        payload = {"tool_name": "Bash", "turn_id": "codex-turn", "tool_input": {"command": "sed -n '1,20p' file.py"}}
        with patch("sys.stdin", StringIO(json.dumps(payload))), patch("sys.stdout", new_callable=StringIO) as out:
            assert run_tool_redirect() == 0
        assert out.getvalue() == ""
