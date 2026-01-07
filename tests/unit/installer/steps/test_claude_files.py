"""Tests for .claude files installation step."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
import pytest


class TestProcessSettings:
    """Test the process_settings function."""

    def test_process_settings_preserves_python_hook_when_enabled(self):
        """process_settings keeps Python hook when install_python=True."""
        from installer.steps.claude_files import PYTHON_CHECKER_HOOK, process_settings

        settings = {
            "hooks": {
                "PostToolUse": [
                    {
                        "matcher": "Write|Edit|MultiEdit",
                        "hooks": [
                            {"type": "command", "command": "python3 .claude/hooks/file_checker_qlty.py"},
                            {"type": "command", "command": PYTHON_CHECKER_HOOK},
                        ],
                    }
                ]
            }
        }

        result = process_settings(json.dumps(settings), install_python=True, install_typescript=True)
        parsed = json.loads(result)

        hooks = parsed["hooks"]["PostToolUse"][0]["hooks"]
        commands = [h["command"] for h in hooks]
        assert PYTHON_CHECKER_HOOK in commands
        assert len(hooks) == 2

    def test_process_settings_removes_python_hook_when_disabled(self):
        """process_settings removes Python hook when install_python=False."""
        from installer.steps.claude_files import PYTHON_CHECKER_HOOK, process_settings

        settings = {
            "hooks": {
                "PostToolUse": [
                    {
                        "matcher": "Write|Edit|MultiEdit",
                        "hooks": [
                            {"type": "command", "command": "python3 .claude/hooks/file_checker_qlty.py"},
                            {"type": "command", "command": PYTHON_CHECKER_HOOK},
                        ],
                    }
                ]
            }
        }

        result = process_settings(json.dumps(settings), install_python=False, install_typescript=True)
        parsed = json.loads(result)

        hooks = parsed["hooks"]["PostToolUse"][0]["hooks"]
        commands = [h["command"] for h in hooks]
        assert PYTHON_CHECKER_HOOK not in commands
        assert any("file_checker_qlty.py" in cmd for cmd in commands)
        assert len(hooks) == 1

    def test_process_settings_handles_missing_hooks(self):
        """process_settings handles settings without hooks gracefully."""
        from installer.steps.claude_files import process_settings

        settings = {"model": "opus", "env": {"key": "value"}}

        result = process_settings(json.dumps(settings), install_python=False, install_typescript=False)
        parsed = json.loads(result)

        assert parsed["model"] == "opus"
        assert parsed["env"]["key"] == "value"

    def test_process_settings_preserves_other_settings(self):
        """process_settings preserves all other settings unchanged."""
        from installer.steps.claude_files import PYTHON_CHECKER_HOOK, process_settings

        settings = {
            "model": "opus",
            "env": {"DISABLE_TELEMETRY": "true"},
            "permissions": {"allow": ["Read", "Write"]},
            "hooks": {
                "PostToolUse": [
                    {
                        "matcher": "Write|Edit|MultiEdit",
                        "hooks": [{"type": "command", "command": PYTHON_CHECKER_HOOK}],
                    }
                ]
            },
        }

        result = process_settings(json.dumps(settings), install_python=False, install_typescript=True)
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
            result = process_settings(json.dumps(settings), install_python=False, install_typescript=False)
            # Should return valid JSON
            parsed = json.loads(result)
            assert parsed is not None

    def test_process_settings_removes_typescript_hook_when_disabled(self):
        """process_settings removes TypeScript hook when install_typescript=False."""
        from installer.steps.claude_files import TYPESCRIPT_CHECKER_HOOK, process_settings

        settings = {
            "hooks": {
                "PostToolUse": [
                    {
                        "matcher": "Write|Edit|MultiEdit",
                        "hooks": [
                            {"type": "command", "command": "python3 .claude/hooks/file_checker_qlty.py"},
                            {"type": "command", "command": TYPESCRIPT_CHECKER_HOOK},
                        ],
                    }
                ]
            }
        }

        result = process_settings(json.dumps(settings), install_python=True, install_typescript=False)
        parsed = json.loads(result)

        hooks = parsed["hooks"]["PostToolUse"][0]["hooks"]
        commands = [h["command"] for h in hooks]
        assert TYPESCRIPT_CHECKER_HOOK not in commands
        assert any("file_checker_qlty.py" in cmd for cmd in commands)
        assert len(hooks) == 1

    def test_process_settings_removes_both_hooks_when_both_disabled(self):
        """process_settings removes both Python and TypeScript hooks when both disabled."""
        from installer.steps.claude_files import PYTHON_CHECKER_HOOK, TYPESCRIPT_CHECKER_HOOK, process_settings

        settings = {
            "hooks": {
                "PostToolUse": [
                    {
                        "matcher": "Write|Edit|MultiEdit",
                        "hooks": [
                            {"type": "command", "command": "python3 .claude/hooks/file_checker_qlty.py"},
                            {"type": "command", "command": PYTHON_CHECKER_HOOK},
                            {"type": "command", "command": TYPESCRIPT_CHECKER_HOOK},
                        ],
                    }
                ]
            }
        }

        result = process_settings(json.dumps(settings), install_python=False, install_typescript=False)
        parsed = json.loads(result)

        hooks = parsed["hooks"]["PostToolUse"][0]["hooks"]
        commands = [h["command"] for h in hooks]
        assert PYTHON_CHECKER_HOOK not in commands
        assert TYPESCRIPT_CHECKER_HOOK not in commands
        assert any("file_checker_qlty.py" in cmd for cmd in commands)
        assert len(hooks) == 1


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
        from installer.downloads import DownloadConfig
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
        """ClaudeFilesStep preserves Python hooks when install_python=True."""
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
                                {"type": "command", "command": "python3 .claude/hooks/file_checker_qlty.py"},
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
                install_python=True,
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
        """ClaudeFilesStep removes Python hooks when install_python=False."""
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
                                {"type": "command", "command": "python3 .claude/hooks/file_checker_qlty.py"},
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
                install_python=False,
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
            assert any("file_checker_qlty.py" in cmd for cmd in commands)

    def test_claude_files_skips_python_when_disabled(self):
        """ClaudeFilesStep skips Python files when install_python=False."""
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
                install_python=False,
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
        """ClaudeFilesStep skips TypeScript files when install_typescript=False."""
        from installer.context import InstallContext
        from installer.steps.claude_files import ClaudeFilesStep
        from installer.ui import Console

        step = ClaudeFilesStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create source with TypeScript files
            source_claude = Path(tmpdir) / "source" / ".claude"
            source_hooks = source_claude / "hooks"
            source_rules = source_claude / "rules" / "custom"
            source_hooks.mkdir(parents=True)
            source_rules.mkdir(parents=True)
            (source_hooks / "file_checker_ts.py").write_text("# typescript hook")
            (source_hooks / "other_hook.sh").write_text("# other hook")
            (source_rules / "typescript-rules.md").write_text("# typescript rules")
            (source_rules / "other-rules.md").write_text("# other rules")
            # Add settings file (required by the step)
            (source_claude / "settings.local.json").write_text('{"hooks": {}}')

            dest_dir = Path(tmpdir) / "dest"
            dest_dir.mkdir()
            (dest_dir / ".claude").mkdir()
            (dest_dir / ".claude" / "hooks").mkdir()
            (dest_dir / ".claude" / "rules" / "custom").mkdir(parents=True)

            ctx = InstallContext(
                project_dir=dest_dir,
                install_typescript=False,
                ui=Console(non_interactive=True),
                local_mode=True,
                local_repo_dir=Path(tmpdir) / "source",
            )

            step.run(ctx)

            # TypeScript hook should NOT be copied
            assert not (dest_dir / ".claude" / "hooks" / "file_checker_ts.py").exists()
            # TypeScript rules should NOT be copied
            assert not (dest_dir / ".claude" / "rules" / "custom" / "typescript-rules.md").exists()
            # Other files should be copied
            assert (dest_dir / ".claude" / "hooks" / "other_hook.sh").exists()
            assert (dest_dir / ".claude" / "rules" / "custom" / "other-rules.md").exists()


class TestClaudeFilesCustomRulesPreservation:
    """Test that custom rules from repo are installed and user files preserved."""

    def test_custom_rules_installed_and_user_files_preserved(self):
        """ClaudeFilesStep installs repo custom rules and preserves user files."""
        from installer.context import InstallContext
        from installer.steps.claude_files import ClaudeFilesStep
        from installer.ui import Console

        step = ClaudeFilesStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create source with custom rules (simulating repo)
            source_claude = Path(tmpdir) / "source" / ".claude"
            source_rules_custom = source_claude / "rules" / "custom"
            source_rules_standard = source_claude / "rules" / "standard"
            source_rules_custom.mkdir(parents=True)
            source_rules_standard.mkdir(parents=True)

            # Repo has custom rules (these SHOULD be copied now)
            (source_rules_custom / "python-rules.md").write_text("python rules from repo")
            # Repo has standard rules (these SHOULD be copied)
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

            # Repo's custom rule SHOULD be copied
            assert (dest_rules_custom / "python-rules.md").exists()
            assert (dest_rules_custom / "python-rules.md").read_text() == "python rules from repo"

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


class TestClaudeFilesRollback:
    """Test ClaudeFilesStep rollback."""

    def test_rollback_removes_installed_files(self):
        """ClaudeFilesStep.rollback removes installed files."""
        from installer.context import InstallContext
        from installer.steps.claude_files import ClaudeFilesStep
        from installer.ui import Console

        step = ClaudeFilesStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = InstallContext(
                project_dir=Path(tmpdir),
                ui=Console(non_interactive=True),
            )

            # Create some files
            claude_dir = Path(tmpdir) / ".claude"
            claude_dir.mkdir()
            test_file = claude_dir / "test.md"
            test_file.write_text("test")

            # Track installed files
            ctx.config["installed_files"] = [str(test_file)]

            step.rollback(ctx)

            # File should be removed
            assert not test_file.exists()
