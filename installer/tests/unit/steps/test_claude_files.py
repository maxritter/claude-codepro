"""Tests for .claude files installation step."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path


class TestPatchClaudePaths:
    """Test the patch_claude_paths function."""

    def test_patch_claude_paths_replaces_hooks_source_repo_path(self):
        """patch_claude_paths replaces source repo hooks path with target project path."""
        from installer.steps.claude_files import patch_claude_paths

        content = '{"command": "uv run python /workspaces/claude-codepro/.claude/hooks/file_checker.py"}'
        result = patch_claude_paths(content, Path("/home/user/myproject"))

        assert "/workspaces/claude-codepro/.claude/hooks/" not in result
        assert "/home/user/myproject/.claude/hooks/file_checker.py" in result

    def test_patch_claude_paths_replaces_bin_source_repo_path(self):
        """patch_claude_paths replaces source repo bin path with target project path."""
        from installer.steps.claude_files import patch_claude_paths

        content = '{"command": "/workspaces/claude-codepro/.claude/bin/ccp statusline"}'
        result = patch_claude_paths(content, Path("/home/user/myproject"))

        assert "/workspaces/claude-codepro/.claude/bin/" not in result
        assert "/home/user/myproject/.claude/bin/ccp statusline" in result

    def test_patch_claude_paths_replaces_relative_hooks_path(self):
        """patch_claude_paths replaces relative .claude/hooks/ paths."""
        from installer.steps.claude_files import patch_claude_paths

        content = '{"command": "uv run python .claude/hooks/file_checker.py"}'
        result = patch_claude_paths(content, Path("/home/user/myproject"))

        assert '".claude/hooks/' not in result
        assert "/home/user/myproject/.claude/hooks/file_checker.py" in result

    def test_patch_claude_paths_replaces_relative_bin_path(self):
        """patch_claude_paths replaces relative .claude/bin/ paths."""
        from installer.steps.claude_files import patch_claude_paths

        content = '{"command": ".claude/bin/ccp statusline"}'
        result = patch_claude_paths(content, Path("/home/user/myproject"))

        assert '".claude/bin/' not in result
        assert "/home/user/myproject/.claude/bin/ccp statusline" in result

    def test_patch_claude_paths_handles_both_hooks_and_bin(self):
        """patch_claude_paths replaces both hooks and bin paths in same content."""
        from installer.steps.claude_files import patch_claude_paths

        content = """{
            "hooks": {"command": "/workspaces/claude-codepro/.claude/hooks/checker.py"},
            "statusLine": {"command": "/workspaces/claude-codepro/.claude/bin/ccp statusline"}
        }"""
        result = patch_claude_paths(content, Path("/target"))

        assert "/target/.claude/hooks/checker.py" in result
        assert "/target/.claude/bin/ccp statusline" in result
        assert "/workspaces/claude-codepro" not in result


class TestPatchClaudePaths:
    """Test the patch_claude_paths function."""

    def test_patch_claude_paths_replaces_hooks_source_repo_path(self):
        """patch_claude_paths replaces source repo hooks path with target project path."""
        from installer.steps.claude_files import patch_claude_paths

        content = '{"command": "uv run python /workspaces/claude-codepro/.claude/hooks/file_checker.py"}'
        result = patch_claude_paths(content, Path("/home/user/myproject"))

        assert "/workspaces/claude-codepro/.claude/hooks/" not in result
        assert "/home/user/myproject/.claude/hooks/file_checker.py" in result

    def test_patch_claude_paths_replaces_bin_source_repo_path(self):
        """patch_claude_paths replaces source repo bin path with target project path."""
        from installer.steps.claude_files import patch_claude_paths

        content = '{"command": "/workspaces/claude-codepro/.claude/bin/ccp statusline"}'
        result = patch_claude_paths(content, Path("/home/user/myproject"))

        assert "/workspaces/claude-codepro/.claude/bin/" not in result
        assert "/home/user/myproject/.claude/bin/ccp statusline" in result

    def test_patch_claude_paths_replaces_relative_hooks_path(self):
        """patch_claude_paths replaces relative .claude/hooks/ paths."""
        from installer.steps.claude_files import patch_claude_paths

        content = '{"command": "uv run python .claude/hooks/file_checker.py"}'
        result = patch_claude_paths(content, Path("/home/user/myproject"))

        assert '".claude/hooks/' not in result
        assert "/home/user/myproject/.claude/hooks/file_checker.py" in result

    def test_patch_claude_paths_replaces_relative_bin_path(self):
        """patch_claude_paths replaces relative .claude/bin/ paths."""
        from installer.steps.claude_files import patch_claude_paths

        content = '{"command": ".claude/bin/ccp statusline"}'
        result = patch_claude_paths(content, Path("/home/user/myproject"))

        assert '".claude/bin/' not in result
        assert "/home/user/myproject/.claude/bin/ccp statusline" in result

    def test_patch_claude_paths_handles_both_hooks_and_bin(self):
        """patch_claude_paths replaces both hooks and bin paths in same content."""
        from installer.steps.claude_files import patch_claude_paths

        content = """{
            "hooks": {"command": "/workspaces/claude-codepro/.claude/hooks/checker.py"},
            "statusLine": {"command": "/workspaces/claude-codepro/.claude/bin/ccp statusline"}
        }"""
        result = patch_claude_paths(content, Path("/target"))

        assert "/target/.claude/hooks/checker.py" in result
        assert "/target/.claude/bin/ccp statusline" in result
        assert "/workspaces/claude-codepro" not in result


class TestProcessSettings:
    """Test the process_settings function."""

    def test_process_settings_preserves_python_hook_when_enabled(self):
        """process_settings keeps Python hook when enable_python=True."""
        from installer.steps.claude_files import process_settings

        # Use absolute path like real source file
        python_hook = "uv run python /workspaces/claude-codepro/.claude/hooks/file_checker_python.py"
        settings = {
            "hooks": {
                "PostToolUse": [
                    {
                        "matcher": "Write|Edit|MultiEdit",
                        "hooks": [
                            {"type": "command", "command": python_hook},
                        ],
                    }
                ]
            }
        }

        result = process_settings(json.dumps(settings), enable_python=True, enable_typescript=True, enable_golang=True)
        parsed = json.loads(result)

        hooks = parsed["hooks"]["PostToolUse"][0]["hooks"]
        commands = [h["command"] for h in hooks]
        assert any("file_checker_python.py" in cmd for cmd in commands)
        assert len(hooks) == 1

    def test_process_settings_removes_python_hook_when_disabled(self):
        """process_settings removes Python hook when enable_python=False."""
        from installer.steps.claude_files import process_settings

        # Use absolute path like real source file
        python_hook = "uv run python /workspaces/claude-codepro/.claude/hooks/file_checker_python.py"
        ts_hook = "uv run python /workspaces/claude-codepro/.claude/hooks/file_checker_ts.py"
        settings = {
            "hooks": {
                "PostToolUse": [
                    {
                        "matcher": "Write|Edit|MultiEdit",
                        "hooks": [
                            {"type": "command", "command": python_hook},
                            {"type": "command", "command": ts_hook},
                        ],
                    }
                ]
            }
        }

        result = process_settings(json.dumps(settings), enable_python=False, enable_typescript=True, enable_golang=True)
        parsed = json.loads(result)

        hooks = parsed["hooks"]["PostToolUse"][0]["hooks"]
        commands = [h["command"] for h in hooks]
        assert not any("file_checker_python.py" in cmd for cmd in commands)
        assert any("file_checker_ts.py" in cmd for cmd in commands)
        assert len(hooks) == 1

    def test_process_settings_handles_missing_hooks(self):
        """process_settings handles settings without hooks gracefully."""
        from installer.steps.claude_files import process_settings

        settings = {"model": "opus", "env": {"key": "value"}}

        result = process_settings(json.dumps(settings), enable_python=False, enable_typescript=False, enable_golang=True)
        parsed = json.loads(result)

        assert parsed["model"] == "opus"
        assert parsed["env"]["key"] == "value"

    def test_process_settings_preserves_other_settings(self):
        """process_settings preserves all other settings unchanged."""
        from installer.steps.claude_files import process_settings

        # Use absolute path like real source file
        python_hook = "uv run python /workspaces/claude-codepro/.claude/hooks/file_checker_python.py"
        settings = {
            "model": "opus",
            "env": {"DISABLE_TELEMETRY": "true"},
            "permissions": {"allow": ["Read", "Write"]},
            "hooks": {
                "PostToolUse": [
                    {
                        "matcher": "Write|Edit|MultiEdit",
                        "hooks": [{"type": "command", "command": python_hook}],
                    }
                ]
            },
        }

        result = process_settings(json.dumps(settings), enable_python=False, enable_typescript=True, enable_golang=True)
        parsed = json.loads(result)

        assert parsed["model"] == "opus"
        assert parsed["env"]["DISABLE_TELEMETRY"] == "true"
        assert parsed["permissions"]["allow"] == ["Read", "Write"]

    def test_process_settings_handles_malformed_structure(self):
        """process_settings handles malformed settings gracefully without crashing."""
        from installer.steps.claude_files import process_settings

        # Various malformed structures - all should not crash
        malformed_cases = [
            {"hooks": {"PostToolUse": None}},  # null PostToolUse
            {"hooks": {"PostToolUse": "not a list"}},  # wrong type
            {"hooks": {"PostToolUse": [{"hooks": None}]}},  # null hooks in group
            {"hooks": {"PostToolUse": [None, "string"]}},  # non-dict entries
            {"hooks": None},  # null hooks
            {"no_hooks": "at all"},  # missing hooks entirely
        ]

        for settings in malformed_cases:
            # Should not raise an exception
            result = process_settings(json.dumps(settings), enable_python=False, enable_typescript=False, enable_golang=True)
            # Should return valid JSON
            parsed = json.loads(result)
            assert parsed is not None

    def test_process_settings_removes_typescript_hook_when_disabled(self):
        """process_settings removes TypeScript hook when enable_typescript=False."""
        from installer.steps.claude_files import process_settings

        # Use absolute path like real source file
        ts_hook = "uv run python /workspaces/claude-codepro/.claude/hooks/file_checker_ts.py"
        go_hook = "uv run python /workspaces/claude-codepro/.claude/hooks/file_checker_go.py"
        settings = {
            "hooks": {
                "PostToolUse": [
                    {
                        "matcher": "Write|Edit|MultiEdit",
                        "hooks": [
                            {"type": "command", "command": go_hook},
                            {"type": "command", "command": ts_hook},
                        ],
                    }
                ]
            }
        }

        result = process_settings(json.dumps(settings), enable_python=True, enable_typescript=False, enable_golang=True)
        parsed = json.loads(result)

        hooks = parsed["hooks"]["PostToolUse"][0]["hooks"]
        commands = [h["command"] for h in hooks]
        assert not any("file_checker_ts.py" in cmd for cmd in commands)
        assert any("file_checker_go.py" in cmd for cmd in commands)
        assert len(hooks) == 1

    def test_process_settings_removes_both_hooks_when_both_disabled(self):
        """process_settings removes both Python and TypeScript hooks when both disabled."""
        from installer.steps.claude_files import process_settings

        # Use absolute paths like real source file
        python_hook = "uv run python /workspaces/claude-codepro/.claude/hooks/file_checker_python.py"
        ts_hook = "uv run python /workspaces/claude-codepro/.claude/hooks/file_checker_ts.py"
        go_hook = "uv run python /workspaces/claude-codepro/.claude/hooks/file_checker_go.py"
        settings = {
            "hooks": {
                "PostToolUse": [
                    {
                        "matcher": "Write|Edit|MultiEdit",
                        "hooks": [
                            {"type": "command", "command": python_hook},
                            {"type": "command", "command": ts_hook},
                            {"type": "command", "command": go_hook},
                        ],
                    }
                ]
            }
        }

        result = process_settings(json.dumps(settings), enable_python=False, enable_typescript=False, enable_golang=True)
        parsed = json.loads(result)

        hooks = parsed["hooks"]["PostToolUse"][0]["hooks"]
        commands = [h["command"] for h in hooks]
        assert not any("file_checker_python.py" in cmd for cmd in commands)
        assert not any("file_checker_ts.py" in cmd for cmd in commands)
        assert any("file_checker_go.py" in cmd for cmd in commands)
        assert len(hooks) == 1

    def test_process_settings_removes_golang_hook_when_disabled(self):
        """process_settings removes Go hook when enable_golang=False."""
        from installer.steps.claude_files import process_settings

        go_hook = "uv run python /workspaces/claude-codepro/.claude/hooks/file_checker_go.py"
        python_hook = "uv run python /workspaces/claude-codepro/.claude/hooks/file_checker_python.py"
        settings = {
            "hooks": {
                "PostToolUse": [
                    {
                        "matcher": "Write|Edit|MultiEdit",
                        "hooks": [
                            {"type": "command", "command": python_hook},
                            {"type": "command", "command": go_hook},
                        ],
                    }
                ]
            }
        }

        result = process_settings(json.dumps(settings), enable_python=True, enable_typescript=True, enable_golang=False)
        parsed = json.loads(result)

        hooks = parsed["hooks"]["PostToolUse"][0]["hooks"]
        commands = [h["command"] for h in hooks]
        assert not any("file_checker_go.py" in cmd for cmd in commands)
        assert any("file_checker_python.py" in cmd for cmd in commands)
        assert len(hooks) == 1

    def test_process_settings_preserves_golang_hook_when_enabled(self):
        """process_settings keeps Go hook when enable_golang=True."""
        from installer.steps.claude_files import process_settings

        go_hook = "uv run python /workspaces/claude-codepro/.claude/hooks/file_checker_go.py"
        python_hook = "uv run python /workspaces/claude-codepro/.claude/hooks/file_checker_python.py"
        settings = {
            "hooks": {
                "PostToolUse": [
                    {
                        "matcher": "Write|Edit|MultiEdit",
                        "hooks": [
                            {"type": "command", "command": python_hook},
                            {"type": "command", "command": go_hook},
                        ],
                    }
                ]
            }
        }

        result = process_settings(json.dumps(settings), enable_python=True, enable_typescript=True, enable_golang=True)
        parsed = json.loads(result)

        hooks = parsed["hooks"]["PostToolUse"][0]["hooks"]
        commands = [h["command"] for h in hooks]
        assert any("file_checker_go.py" in cmd for cmd in commands)
        assert len(hooks) == 2


class TestClaudeFilesStep:
    """Test ClaudeFilesStep class."""

    def test_claude_files_step_has_correct_name(self):
        """ClaudeFilesStep has name 'claude_files'."""
        from installer.steps.claude_files import ClaudeFilesStep

        step = ClaudeFilesStep()
        assert step.name == "claude_files"

    def test_claude_files_check_returns_false_when_empty(self):
        """ClaudeFilesStep.check returns False when no files installed."""
        from installer.context import InstallContext
        from installer.steps.claude_files import ClaudeFilesStep
        from installer.ui import Console

        step = ClaudeFilesStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = InstallContext(
                project_dir=Path(tmpdir),
                ui=Console(non_interactive=True),
                local_mode=True,
                local_repo_dir=Path(tmpdir),
            )
            # No .claude directory
            assert step.check(ctx) is False

    def test_claude_files_run_installs_files(self):
        """ClaudeFilesStep.run installs .claude files."""
        from installer.context import InstallContext
        from installer.steps.claude_files import ClaudeFilesStep
        from installer.ui import Console

        step = ClaudeFilesStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create source .claude directory
            source_claude = Path(tmpdir) / "source" / ".claude"
            source_claude.mkdir(parents=True)
            (source_claude / "test.md").write_text("test content")
            (source_claude / "rules").mkdir()
            (source_claude / "rules" / "standard").mkdir()
            (source_claude / "rules" / "standard" / "rule.md").write_text("rule content")

            dest_dir = Path(tmpdir) / "dest"
            dest_dir.mkdir()

            ctx = InstallContext(
                project_dir=dest_dir,
                ui=Console(non_interactive=True),
                local_mode=True,
                local_repo_dir=Path(tmpdir) / "source",
            )

            # Create destination .claude dir first (bootstrap would do this)
            (dest_dir / ".claude").mkdir()

            step.run(ctx)

            # Check files were installed
            assert (dest_dir / ".claude" / "test.md").exists()

    def test_claude_files_installs_settings_local(self):
        """ClaudeFilesStep installs settings.local.json."""
        from installer.context import InstallContext
        from installer.steps.claude_files import ClaudeFilesStep
        from installer.ui import Console

        step = ClaudeFilesStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create source with settings file
            source_claude = Path(tmpdir) / "source" / ".claude"
            source_claude.mkdir(parents=True)
            (source_claude / "settings.local.json").write_text('{"hooks": {}}')

            dest_dir = Path(tmpdir) / "dest"
            dest_dir.mkdir()
            (dest_dir / ".claude").mkdir()

            ctx = InstallContext(
                project_dir=dest_dir,
                ui=Console(non_interactive=True),
                local_mode=True,
                local_repo_dir=Path(tmpdir) / "source",
            )

            step.run(ctx)

            # settings.local.json should be copied
            assert (dest_dir / ".claude" / "settings.local.json").exists()

    def test_claude_files_installs_python_settings_when_enabled(self):
        """ClaudeFilesStep preserves Python hooks when enable_python=True."""
        import json

        from installer.context import InstallContext
        from installer.steps.claude_files import PYTHON_CHECKER_HOOK, ClaudeFilesStep
        from installer.ui import Console

        step = ClaudeFilesStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create source with settings file containing Python hook
            source_claude = Path(tmpdir) / "source" / ".claude"
            source_claude.mkdir(parents=True)
            settings_with_python = {
                "hooks": {
                    "PostToolUse": [
                        {
                            "matcher": "Write|Edit|MultiEdit",
                            "hooks": [
                                {"type": "command", "command": "uv run python .claude/hooks/file_checker_go.py"},
                                {"type": "command", "command": PYTHON_CHECKER_HOOK},
                            ],
                        }
                    ]
                }
            }
            (source_claude / "settings.local.json").write_text(json.dumps(settings_with_python))

            dest_dir = Path(tmpdir) / "dest"
            dest_dir.mkdir()
            (dest_dir / ".claude").mkdir()

            ctx = InstallContext(
                project_dir=dest_dir,
                enable_python=True,
                ui=Console(non_interactive=True),
                local_mode=True,
                local_repo_dir=Path(tmpdir) / "source",
            )

            step.run(ctx)

            # settings.local.json should contain Python hooks
            settings_file = dest_dir / ".claude" / "settings.local.json"
            assert settings_file.exists()
            settings = json.loads(settings_file.read_text())
            # Python hook should be preserved (with absolute path)
            hooks = settings["hooks"]["PostToolUse"][0]["hooks"]
            commands = [h["command"] for h in hooks]
            assert any("file_checker_python.py" in cmd for cmd in commands)

    def test_claude_files_removes_python_hooks_when_python_disabled(self):
        """ClaudeFilesStep removes Python hooks when enable_python=False."""
        import json

        from installer.context import InstallContext
        from installer.steps.claude_files import PYTHON_CHECKER_HOOK, ClaudeFilesStep
        from installer.ui import Console

        step = ClaudeFilesStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create source with settings file containing Python hook
            source_claude = Path(tmpdir) / "source" / ".claude"
            source_claude.mkdir(parents=True)
            settings_with_python = {
                "hooks": {
                    "PostToolUse": [
                        {
                            "matcher": "Write|Edit|MultiEdit",
                            "hooks": [
                                {"type": "command", "command": "uv run python .claude/hooks/file_checker_go.py"},
                                {"type": "command", "command": PYTHON_CHECKER_HOOK},
                            ],
                        }
                    ]
                }
            }
            (source_claude / "settings.local.json").write_text(json.dumps(settings_with_python))

            dest_dir = Path(tmpdir) / "dest"
            dest_dir.mkdir()
            (dest_dir / ".claude").mkdir()

            ctx = InstallContext(
                project_dir=dest_dir,
                enable_python=False,
                ui=Console(non_interactive=True),
                local_mode=True,
                local_repo_dir=Path(tmpdir) / "source",
            )

            step.run(ctx)

            # settings.local.json should NOT contain Python hooks
            settings_file = dest_dir / ".claude" / "settings.local.json"
            assert settings_file.exists()
            settings = json.loads(settings_file.read_text())
            # Python hook should be removed
            hooks = settings["hooks"]["PostToolUse"][0]["hooks"]
            commands = [h["command"] for h in hooks]
            assert PYTHON_CHECKER_HOOK not in commands
            # Other hooks should still be present (with absolute paths)
            assert any("file_checker_go.py" in cmd for cmd in commands)

    def test_claude_files_skips_python_when_disabled(self):
        """ClaudeFilesStep skips Python files when enable_python=False."""
        from installer.context import InstallContext
        from installer.steps.claude_files import ClaudeFilesStep
        from installer.ui import Console

        step = ClaudeFilesStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create source with Python file
            source_claude = Path(tmpdir) / "source" / ".claude"
            source_hooks = source_claude / "hooks"
            source_hooks.mkdir(parents=True)
            (source_hooks / "file_checker_python.py").write_text("# python hook")
            (source_hooks / "other_hook.sh").write_text("# other hook")
            # Add settings file (required by the step)
            (source_claude / "settings.local.json").write_text('{"hooks": {}}')

            dest_dir = Path(tmpdir) / "dest"
            dest_dir.mkdir()
            (dest_dir / ".claude").mkdir()
            (dest_dir / ".claude" / "hooks").mkdir()

            ctx = InstallContext(
                project_dir=dest_dir,
                enable_python=False,
                ui=Console(non_interactive=True),
                local_mode=True,
                local_repo_dir=Path(tmpdir) / "source",
            )

            step.run(ctx)

            # Python hook should NOT be copied
            assert not (dest_dir / ".claude" / "hooks" / "file_checker_python.py").exists()
            # Other hooks should be copied
            assert (dest_dir / ".claude" / "hooks" / "other_hook.sh").exists()

    def test_claude_files_skips_typescript_when_disabled(self):
        """ClaudeFilesStep skips TypeScript files when enable_typescript=False."""
        from installer.context import InstallContext
        from installer.steps.claude_files import ClaudeFilesStep
        from installer.ui import Console

        step = ClaudeFilesStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create source with TypeScript files
            source_claude = Path(tmpdir) / "source" / ".claude"
            source_hooks = source_claude / "hooks"
            source_rules_standard = source_claude / "rules" / "standard"
            source_hooks.mkdir(parents=True)
            source_rules_standard.mkdir(parents=True)
            (source_hooks / "file_checker_ts.py").write_text("# typescript hook")
            (source_hooks / "other_hook.sh").write_text("# other hook")
            # Python/TypeScript rules are now in standard/ folder
            (source_rules_standard / "typescript-rules.md").write_text("# typescript rules")
            (source_rules_standard / "python-rules.md").write_text("# python rules")
            # Add settings file (required by the step)
            (source_claude / "settings.local.json").write_text('{"hooks": {}}')

            dest_dir = Path(tmpdir) / "dest"
            dest_dir.mkdir()
            (dest_dir / ".claude").mkdir()
            (dest_dir / ".claude" / "hooks").mkdir()
            (dest_dir / ".claude" / "rules" / "standard").mkdir(parents=True)

            ctx = InstallContext(
                project_dir=dest_dir,
                enable_typescript=False,
                ui=Console(non_interactive=True),
                local_mode=True,
                local_repo_dir=Path(tmpdir) / "source",
            )

            step.run(ctx)

            # TypeScript hook should NOT be copied
            assert not (dest_dir / ".claude" / "hooks" / "file_checker_ts.py").exists()
            # TypeScript rules should NOT be copied (now in standard/)
            assert not (dest_dir / ".claude" / "rules" / "standard" / "typescript-rules.md").exists()
            # Other files should be copied
            assert (dest_dir / ".claude" / "hooks" / "other_hook.sh").exists()
            # Python rules should be copied (now in standard/)
            assert (dest_dir / ".claude" / "rules" / "standard" / "python-rules.md").exists()

    def test_claude_files_skips_golang_when_disabled(self):
        """ClaudeFilesStep skips Go files when enable_golang=False."""
        from installer.context import InstallContext
        from installer.steps.claude_files import ClaudeFilesStep
        from installer.ui import Console

        step = ClaudeFilesStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create source with Go files
            source_claude = Path(tmpdir) / "source" / ".claude"
            source_hooks = source_claude / "hooks"
            source_rules_standard = source_claude / "rules" / "standard"
            source_hooks.mkdir(parents=True)
            source_rules_standard.mkdir(parents=True)
            (source_hooks / "file_checker_go.py").write_text("# golang hook")
            (source_hooks / "other_hook.sh").write_text("# other hook")
            (source_rules_standard / "golang-rules.md").write_text("# golang rules")
            (source_rules_standard / "python-rules.md").write_text("# python rules")
            # Add settings file (required by the step)
            (source_claude / "settings.local.json").write_text('{"hooks": {}}')

            dest_dir = Path(tmpdir) / "dest"
            dest_dir.mkdir()
            (dest_dir / ".claude").mkdir()
            (dest_dir / ".claude" / "hooks").mkdir()
            (dest_dir / ".claude" / "rules" / "standard").mkdir(parents=True)

            ctx = InstallContext(
                project_dir=dest_dir,
                enable_golang=False,
                ui=Console(non_interactive=True),
                local_mode=True,
                local_repo_dir=Path(tmpdir) / "source",
            )

            step.run(ctx)

            # Go hook should NOT be copied
            assert not (dest_dir / ".claude" / "hooks" / "file_checker_go.py").exists()
            # Go rules should NOT be copied
            assert not (dest_dir / ".claude" / "rules" / "standard" / "golang-rules.md").exists()
            # Other files should be copied
            assert (dest_dir / ".claude" / "hooks" / "other_hook.sh").exists()
            # Python rules should be copied
            assert (dest_dir / ".claude" / "rules" / "standard" / "python-rules.md").exists()


class TestClaudeFilesCustomRulesPreservation:
    """Test that custom rules from repo are installed and user files preserved."""

    def test_custom_rules_installed_and_user_files_preserved(self):
        """ClaudeFilesStep installs repo standard rules and preserves user custom files."""
        from installer.context import InstallContext
        from installer.steps.claude_files import ClaudeFilesStep
        from installer.ui import Console

        step = ClaudeFilesStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create source with rules (simulating repo)
            source_claude = Path(tmpdir) / "source" / ".claude"
            source_rules_standard = source_claude / "rules" / "standard"
            source_rules_standard.mkdir(parents=True)

            # Repo has standard rules (including python-rules.md, now in standard/)
            (source_rules_standard / "python-rules.md").write_text("python rules from repo")
            (source_rules_standard / "standard-rule.md").write_text("standard rule")

            # Destination already has user's custom rules (not in repo)
            dest_dir = Path(tmpdir) / "dest"
            dest_claude = dest_dir / ".claude"
            dest_rules_custom = dest_claude / "rules" / "custom"
            dest_rules_custom.mkdir(parents=True)
            (dest_rules_custom / "my-project-rules.md").write_text("USER PROJECT RULES - PRESERVED")

            ctx = InstallContext(
                project_dir=dest_dir,
                ui=Console(non_interactive=True),
                local_mode=True,
                local_repo_dir=Path(tmpdir) / "source",
            )

            step.run(ctx)

            # User's custom rule should be PRESERVED (not deleted)
            assert (dest_rules_custom / "my-project-rules.md").exists()
            assert (dest_rules_custom / "my-project-rules.md").read_text() == "USER PROJECT RULES - PRESERVED"

            # Repo's python rules SHOULD be copied to standard/
            assert (dest_claude / "rules" / "standard" / "python-rules.md").exists()
            assert (dest_claude / "rules" / "standard" / "python-rules.md").read_text() == "python rules from repo"

            # Standard rules SHOULD be copied
            assert (dest_claude / "rules" / "standard" / "standard-rule.md").exists()

    def test_pycache_files_not_copied(self):
        """ClaudeFilesStep skips __pycache__ directories and .pyc files."""
        from installer.context import InstallContext
        from installer.steps.claude_files import ClaudeFilesStep
        from installer.ui import Console

        step = ClaudeFilesStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create source with __pycache__
            source_claude = Path(tmpdir) / "source" / ".claude"
            source_hooks = source_claude / "hooks"
            source_pycache = source_hooks / "__pycache__"
            source_pycache.mkdir(parents=True)
            (source_hooks / "hook.py").write_text("# hook")
            (source_pycache / "hook.cpython-312.pyc").write_text("bytecode")

            dest_dir = Path(tmpdir) / "dest"
            (dest_dir / ".claude").mkdir(parents=True)

            ctx = InstallContext(
                project_dir=dest_dir,
                ui=Console(non_interactive=True),
                local_mode=True,
                local_repo_dir=Path(tmpdir) / "source",
            )

            step.run(ctx)

            # Regular hook should be copied
            assert (dest_dir / ".claude" / "hooks" / "hook.py").exists()

            # __pycache__ should NOT be copied
            assert not (dest_dir / ".claude" / "hooks" / "__pycache__").exists()


class TestDirectoryClearing:
    """Test directory clearing behavior in local and normal mode."""

    def test_clears_directories_in_normal_local_mode(self):
        """Directories are cleared when source != destination in local mode."""
        from installer.context import InstallContext
        from installer.steps.claude_files import ClaudeFilesStep
        from installer.ui import Console

        step = ClaudeFilesStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create source with standard skill (standards-* is a standard skill name)
            source_dir = Path(tmpdir) / "source"
            source_claude = source_dir / ".claude"
            source_skills = source_claude / "skills" / "standards-testing"
            source_skills.mkdir(parents=True)
            (source_skills / "SKILL.md").write_text("new standards-testing skill")

            # Create destination with OLD standard skill (should be cleared)
            dest_dir = Path(tmpdir) / "dest"
            dest_claude = dest_dir / ".claude"
            dest_skills = dest_claude / "skills" / "standards-testing"
            dest_skills.mkdir(parents=True)
            (dest_skills / "SKILL.md").write_text("old standards-testing skill to be removed")

            ctx = InstallContext(
                project_dir=dest_dir,
                ui=Console(non_interactive=True),
                local_mode=True,
                local_repo_dir=source_dir,
            )

            step.run(ctx)

            # New standard skill should be installed (old was cleared)
            assert (dest_claude / "skills" / "standards-testing" / "SKILL.md").exists()
            assert (dest_claude / "skills" / "standards-testing" / "SKILL.md").read_text() == "new standards-testing skill"

    def test_skips_clearing_when_source_equals_destination(self):
        """Directories are NOT cleared when source == destination (same dir)."""
        from installer.context import InstallContext
        from installer.steps.claude_files import ClaudeFilesStep
        from installer.ui import Console

        step = ClaudeFilesStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create .claude directory (source AND destination are same)
            claude_dir = Path(tmpdir) / ".claude"
            skills_dir = claude_dir / "skills" / "standards-testing"
            skills_dir.mkdir(parents=True)
            (skills_dir / "SKILL.md").write_text("existing skill content")

            ctx = InstallContext(
                project_dir=Path(tmpdir),
                ui=Console(non_interactive=True),
                local_mode=True,
                local_repo_dir=Path(tmpdir),  # Same as project_dir!
            )

            step.run(ctx)

            # Skill should still exist (NOT cleared because source==dest)
            assert (skills_dir / "SKILL.md").exists()
            assert (skills_dir / "SKILL.md").read_text() == "existing skill content"

    def test_custom_rules_never_cleared(self):
        """Custom rules directory is NEVER cleared, only standard rules."""
        from installer.context import InstallContext
        from installer.steps.claude_files import ClaudeFilesStep
        from installer.ui import Console

        step = ClaudeFilesStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create source with standard rules only
            source_dir = Path(tmpdir) / "source"
            source_claude = source_dir / ".claude"
            source_standard = source_claude / "rules" / "standard"
            source_standard.mkdir(parents=True)
            (source_standard / "new-rule.md").write_text("new standard rule")

            # Create destination with custom rules AND old standard rules
            dest_dir = Path(tmpdir) / "dest"
            dest_claude = dest_dir / ".claude"
            dest_custom = dest_claude / "rules" / "custom"
            dest_standard = dest_claude / "rules" / "standard"
            dest_custom.mkdir(parents=True)
            dest_standard.mkdir(parents=True)
            (dest_custom / "my-project.md").write_text("USER CUSTOM RULE")
            (dest_standard / "old-rule.md").write_text("old standard rule")

            ctx = InstallContext(
                project_dir=dest_dir,
                ui=Console(non_interactive=True),
                local_mode=True,
                local_repo_dir=source_dir,
            )

            step.run(ctx)

            # Custom rules should be PRESERVED (never cleared)
            assert (dest_custom / "my-project.md").exists()
            assert (dest_custom / "my-project.md").read_text() == "USER CUSTOM RULE"

            # Old standard rule should be GONE (directory was cleared)
            assert not (dest_standard / "old-rule.md").exists()
            # New standard rule should be installed
            assert (dest_standard / "new-rule.md").exists()

    def test_custom_skills_never_cleared(self):
        """Custom skills (non-standard names) are NEVER cleared, only standard skills."""
        from installer.context import InstallContext
        from installer.steps.claude_files import ClaudeFilesStep
        from installer.ui import Console

        step = ClaudeFilesStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create source with standard skill (standards-testing)
            source_dir = Path(tmpdir) / "source"
            source_claude = source_dir / ".claude"
            source_standard = source_claude / "skills" / "standards-testing"
            source_standard.mkdir(parents=True)
            (source_standard / "SKILL.md").write_text("new standards-testing skill")

            # Create destination with custom skill AND old standard skill
            dest_dir = Path(tmpdir) / "dest"
            dest_claude = dest_dir / ".claude"
            dest_custom = dest_claude / "skills" / "my-custom-skill"  # Custom name
            dest_standard = dest_claude / "skills" / "standards-testing"  # Standard name (standards-* prefix)
            dest_custom.mkdir(parents=True)
            dest_standard.mkdir(parents=True)
            (dest_custom / "SKILL.md").write_text("USER CUSTOM SKILL")
            (dest_standard / "SKILL.md").write_text("old standards-testing skill")

            ctx = InstallContext(
                project_dir=dest_dir,
                ui=Console(non_interactive=True),
                local_mode=True,
                local_repo_dir=source_dir,
            )

            step.run(ctx)

            # Custom skill should be PRESERVED (not a standard name)
            assert (dest_custom / "SKILL.md").exists()
            assert (dest_custom / "SKILL.md").read_text() == "USER CUSTOM SKILL"

            # Standard skill should be updated
            assert (dest_standard / "SKILL.md").exists()
            assert (dest_standard / "SKILL.md").read_text() == "new standards-testing skill"

    def test_migrated_skills_are_removed(self):
        """Skills that were migrated to commands (plan, implement, verify) are removed."""
        from installer.context import InstallContext
        from installer.steps.claude_files import ClaudeFilesStep
        from installer.ui import Console

        step = ClaudeFilesStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create source with some files (so clearing logic runs - early return if no files)
            source_dir = Path(tmpdir) / "source"
            source_claude = source_dir / ".claude"
            source_rules = source_claude / "rules" / "standard"
            source_rules.mkdir(parents=True)
            (source_rules / "test-rule.md").write_text("# test rule")

            # Create destination with old plan/implement/verify skills (should be migrated/removed)
            dest_dir = Path(tmpdir) / "dest"
            dest_claude = dest_dir / ".claude"
            for skill_name in ["plan", "implement", "verify"]:
                skill_dir = dest_claude / "skills" / skill_name
                skill_dir.mkdir(parents=True)
                (skill_dir / "SKILL.md").write_text(f"old {skill_name} skill")

            ctx = InstallContext(
                project_dir=dest_dir,
                ui=Console(non_interactive=True),
                local_mode=True,
                local_repo_dir=source_dir,
            )

            step.run(ctx)

            # Migrated skill directories should be REMOVED
            for skill_name in ["plan", "implement", "verify"]:
                skill_dir = dest_claude / "skills" / skill_name
                assert not skill_dir.exists(), f"Skill '{skill_name}' should have been removed (migrated to command)"

    def test_standard_commands_are_cleared(self):
        """Standard commands (spec, sync, plan, implement, verify) are cleared and replaced."""
        from installer.context import InstallContext
        from installer.steps.claude_files import ClaudeFilesStep
        from installer.ui import Console

        step = ClaudeFilesStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create source with new standard command
            source_dir = Path(tmpdir) / "source"
            source_claude = source_dir / ".claude"
            source_commands = source_claude / "commands"
            source_commands.mkdir(parents=True)
            (source_commands / "spec.md").write_text("new spec command")

            # Create destination with OLD standard command
            dest_dir = Path(tmpdir) / "dest"
            dest_claude = dest_dir / ".claude"
            dest_commands = dest_claude / "commands"
            dest_commands.mkdir(parents=True)
            (dest_commands / "spec.md").write_text("old spec command")
            (dest_commands / "plan.md").write_text("old plan command")

            ctx = InstallContext(
                project_dir=dest_dir,
                ui=Console(non_interactive=True),
                local_mode=True,
                local_repo_dir=source_dir,
            )

            step.run(ctx)

            # New standard command should be installed
            assert (dest_commands / "spec.md").exists()
            assert (dest_commands / "spec.md").read_text() == "new spec command"

    def test_custom_commands_never_cleared(self):
        """Custom commands (non-standard names) are NEVER cleared."""
        from installer.context import InstallContext
        from installer.steps.claude_files import ClaudeFilesStep
        from installer.ui import Console

        step = ClaudeFilesStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create source with standard command
            source_dir = Path(tmpdir) / "source"
            source_claude = source_dir / ".claude"
            source_commands = source_claude / "commands"
            source_commands.mkdir(parents=True)
            (source_commands / "spec.md").write_text("new spec command")

            # Create destination with custom command AND standard command
            dest_dir = Path(tmpdir) / "dest"
            dest_claude = dest_dir / ".claude"
            dest_commands = dest_claude / "commands"
            dest_commands.mkdir(parents=True)
            (dest_commands / "my-custom-workflow.md").write_text("USER CUSTOM COMMAND")
            (dest_commands / "spec.md").write_text("old spec command")

            ctx = InstallContext(
                project_dir=dest_dir,
                ui=Console(non_interactive=True),
                local_mode=True,
                local_repo_dir=source_dir,
            )

            step.run(ctx)

            # Custom command should be PRESERVED
            assert (dest_commands / "my-custom-workflow.md").exists()
            assert (dest_commands / "my-custom-workflow.md").read_text() == "USER CUSTOM COMMAND"

            # Standard command should be updated
            assert (dest_commands / "spec.md").exists()
            assert (dest_commands / "spec.md").read_text() == "new spec command"
