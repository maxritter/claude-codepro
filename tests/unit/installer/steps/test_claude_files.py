"""Tests for .claude files installation step."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


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
            # Create source with both settings files
            source_claude = Path(tmpdir) / "source" / ".claude"
            source_claude.mkdir(parents=True)
            (source_claude / "settings.local.json").write_text('{"python": true}')
            (source_claude / "settings.local.base.json").write_text('{"python": false}')

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
        """ClaudeFilesStep installs Python settings when install_python=True."""
        import json

        from installer.context import InstallContext
        from installer.steps.claude_files import ClaudeFilesStep
        from installer.ui import Console

        step = ClaudeFilesStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create source with both settings files
            source_claude = Path(tmpdir) / "source" / ".claude"
            source_claude.mkdir(parents=True)
            (source_claude / "settings.local.json").write_text('{"hasPythonHooks": true}')
            (source_claude / "settings.local.base.json").write_text('{"hasPythonHooks": false}')

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

            # settings.local.json should contain Python hooks config
            settings_file = dest_dir / ".claude" / "settings.local.json"
            assert settings_file.exists()
            settings = json.loads(settings_file.read_text())
            assert settings["hasPythonHooks"] is True

    def test_claude_files_installs_base_settings_when_python_disabled(self):
        """ClaudeFilesStep installs base settings (no Python hooks) when install_python=False."""
        import json

        from installer.context import InstallContext
        from installer.steps.claude_files import ClaudeFilesStep
        from installer.ui import Console

        step = ClaudeFilesStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create source with both settings files
            source_claude = Path(tmpdir) / "source" / ".claude"
            source_claude.mkdir(parents=True)
            (source_claude / "settings.local.json").write_text('{"hasPythonHooks": true}')
            (source_claude / "settings.local.base.json").write_text('{"hasPythonHooks": false}')

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

            # settings.local.json should contain base config (no Python hooks)
            settings_file = dest_dir / ".claude" / "settings.local.json"
            assert settings_file.exists()
            settings = json.loads(settings_file.read_text())
            assert settings["hasPythonHooks"] is False

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
            # Add settings files (required by the step)
            (source_claude / "settings.local.json").write_text('{"python": true}')
            (source_claude / "settings.local.base.json").write_text('{"python": false}')

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
