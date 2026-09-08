"""Tests for pilot files installation step."""

from __future__ import annotations

import contextlib
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


def _run_full_install_flow(
    ctx,
    *,
    home_dir: Path | None = None,
    claude_installed: bool = True,
) -> None:
    """Run PilotFilesStep then ClaudeFilesStep with Claude-detection mocked.

    Mirrors the production install order (PilotFilesStep cleans + installs
    agent-neutral assets + skill source; ClaudeFilesStep installs Claude-only
    rules/agents/settings and runs Claude post-install merges). Tests that
    exercise the full install flow use this helper.

    When ``home_dir`` is provided, ``Path.home`` is patched on both step
    modules so the install lands under the test's tempdir.
    """
    from installer.steps.claude_files import ClaudeFilesStep
    from installer.steps.pilot_files import PilotFilesStep

    with contextlib.ExitStack() as stack:
        stack.enter_context(patch("installer.steps.pilot_files.is_claude_installed", return_value=claude_installed))
        stack.enter_context(patch("installer.steps.claude_files.is_claude_installed", return_value=claude_installed))
        if home_dir is not None:
            stack.enter_context(patch("installer.steps.pilot_files.Path.home", return_value=home_dir))
            stack.enter_context(patch("installer.steps.claude_files.Path.home", return_value=home_dir))
        PilotFilesStep().run(ctx)
        ClaudeFilesStep().run(ctx)


class TestPatchClaudePaths:
    """Test the patch_claude_paths function."""

    def test_adapt_claude_rule_content_strips_codex_blocks(self):
        """Claude rule installation keeps Claude text and strips Codex alternatives."""
        from installer.steps.claude_files import adapt_claude_rule_content

        content = (
            "Shared.\n"
            "<!-- CC-ONLY -->\nClaude only.\n<!-- /CC-ONLY -->\n"
            "<!-- CODEX-START\nCodex only.\nCODEX-END -->\n"
            "Done."
        )

        result = adapt_claude_rule_content(content)

        assert "Shared." in result
        assert "Claude only." in result
        assert "Codex only." not in result
        assert "CC-ONLY" not in result
        assert "CODEX-START" not in result

    def test_real_task_and_workflow_rule_keeps_core_execution_contract(self):
        """Rule slimming must retain direct work, opt-in workflows, and autonomous delegation."""
        from installer.steps.claude_files import adapt_claude_rule_content

        source = Path("pilot/rules/task-and-workflow.md").read_text()
        content = adapt_claude_rule_content(source)

        assert "A clear user request is authorization to execute" in content
        assert "`/spec`, `/build`, `/fix`, and `/prd` run only when the user explicitly types them" in content
        assert "The active agent owns the execution topology" in content
        assert "Never stop a running task to ask the user for permission" in content
        assert "explicit ownership" in content

    def test_patch_claude_paths_leaves_non_bin_tilde_paths_unchanged(self):
        """patch_claude_paths only expands ~/.pilot/bin/. Other tilde paths
        (~/.claude/, ~/.pilot/scripts/, …) round-trip untouched — the shell
        expands them at hook-execution time."""
        from installer.steps.claude_files import patch_claude_paths

        content = '{"command": "~/.pilot/scripts/worker.cjs"}'
        result = patch_claude_paths(content)

        assert content == result

    def test_patch_claude_paths_expands_tilde_bin_path(self):
        """patch_claude_paths expands ~/.pilot/bin/ to absolute path."""
        from pathlib import Path as P

        from installer.steps.claude_files import patch_claude_paths

        content = '{"command": "~/.pilot/bin/pilot statusline"}'
        result = patch_claude_paths(content)

        expected_bin = str(P.home() / ".pilot" / "bin") + "/"
        assert '"~/.pilot/bin/' not in result
        assert expected_bin in result

    def test_patch_claude_paths_only_expands_bin_path(self):
        """patch_claude_paths only expands ~/.pilot/bin/, not other ~/.pilot/ subdirs."""
        from pathlib import Path as P

        from installer.steps.claude_files import patch_claude_paths

        content = """{
            "command": "~/.pilot/scripts/worker.cjs",
            "statusLine": {"command": "~/.pilot/bin/pilot statusline"}
        }"""
        result = patch_claude_paths(content)

        expected_bin = str(P.home() / ".pilot" / "bin") + "/"
        assert expected_bin in result
        # ~/.pilot/scripts/ is NOT touched — the shell expands it at hook-execution time.
        assert "~/.pilot/scripts/" in result

    def test_patch_claude_paths_preserves_non_tilde_paths(self):
        """patch_claude_paths leaves non-tilde paths unchanged."""
        from installer.steps.claude_files import patch_claude_paths

        content = '{"path": "/usr/local/bin/something"}'
        result = patch_claude_paths(content)

        assert result == content


class TestProcessSettings:
    """Test the process_settings function."""

    def test_process_settings_round_trips_json(self):
        """process_settings parses and re-serializes JSON with consistent formatting."""
        from installer.steps.claude_files import process_settings

        settings = {"hooks": {"PostToolUse": [{"matcher": "Write", "hooks": []}]}, "model": "opus"}
        result = process_settings(json.dumps(settings))
        parsed = json.loads(result)

        assert parsed == settings
        assert result.endswith("\n")

    def test_process_settings_preserves_all_hooks(self):
        """process_settings preserves all language hooks without filtering."""
        from installer.steps.claude_files import process_settings

        python_hook = "uv run --no-project python ~/.claude/hooks/file_checker_python.py"
        ts_hook = "uv run --no-project python ~/.claude/hooks/file_checker_ts.py"
        go_hook = "uv run --no-project python ~/.claude/hooks/file_checker_go.py"
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

        result = process_settings(json.dumps(settings))
        parsed = json.loads(result)

        hooks = parsed["hooks"]["PostToolUse"][0]["hooks"]
        assert len(hooks) == 3


class TestClaudeFilesStep:
    """Test ClaudeFilesStep class."""

    def test_claude_files_step_name(self):
        """ClaudeFilesStep handles Claude-specific assets; display label 'Claude Files'.

        The agent-neutral runtime + skill source live in PilotFilesStep (separate file,
        always runs). ClaudeFilesStep only runs when Claude Code CLI is detected.
        """
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
            assert step.check(ctx) is False

    def test_claude_files_run_installs_files(self):
        """ClaudeFilesStep.run installs pilot files."""
        from installer.context import InstallContext
        from installer.steps.claude_files import ClaudeFilesStep
        from installer.ui import Console

        ClaudeFilesStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            home_dir = Path(tmpdir) / "home"
            home_dir.mkdir()

            source_pilot = Path(tmpdir) / "source" / "pilot"
            source_pilot.mkdir(parents=True)
            (source_pilot / "test.md").write_text("test content")
            (source_pilot / "rules").mkdir()
            (source_pilot / "rules" / "rule.md").write_text("rule content")

            dest_dir = Path(tmpdir) / "dest"
            dest_dir.mkdir()

            ctx = InstallContext(
                project_dir=dest_dir,
                ui=Console(non_interactive=True),
                local_mode=True,
                local_repo_dir=Path(tmpdir) / "source",
            )

            _run_full_install_flow(ctx, home_dir=home_dir)

            assert (home_dir / ".claude" / "rules" / "rule.md").exists()

    def test_claude_files_installs_settings(self):
        """ClaudeFilesStep installs settings to ~/.claude/settings.json."""
        from installer.context import InstallContext
        from installer.steps.claude_files import ClaudeFilesStep
        from installer.ui import Console

        ClaudeFilesStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            home_dir = Path(tmpdir) / "home"
            home_dir.mkdir()

            source_pilot = Path(tmpdir) / "source" / "pilot"
            source_pilot.mkdir(parents=True)
            (source_pilot / "settings.json").write_text('{"hooks": {}}')

            dest_dir = Path(tmpdir) / "dest"
            dest_dir.mkdir()

            ctx = InstallContext(
                project_dir=dest_dir,
                ui=Console(non_interactive=True),
                local_mode=True,
                local_repo_dir=Path(tmpdir) / "source",
            )

            _run_full_install_flow(ctx, home_dir=home_dir)

            assert (home_dir / ".claude" / "settings.json").exists()
            assert not (dest_dir / ".claude" / "settings.local.json").exists()


class TestClaudeFilesCustomRulesPreservation:
    """Test that standard rules from repo are installed and project rules preserved."""

    def test_standard_rules_installed_and_project_rules_preserved(self):
        """ClaudeFilesStep installs repo standard rules to ~/.claude and preserves project rules."""
        from installer.context import InstallContext
        from installer.steps.claude_files import ClaudeFilesStep
        from installer.ui import Console

        ClaudeFilesStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            home_dir = Path(tmpdir) / "home"
            home_dir.mkdir()

            source_pilot = Path(tmpdir) / "source" / "pilot"
            source_rules = source_pilot / "rules"
            source_rules.mkdir(parents=True)

            (source_rules / "python-rules.md").write_text("python rules from repo")
            (source_rules / "standard-rule.md").write_text("standard rule")
            (source_rules / "conditional-rule.md").write_text(
                "Shared.\n"
                "<!-- CC-ONLY -->\nClaude only.\n<!-- /CC-ONLY -->\n"
                "<!-- CODEX-START\nCodex only.\nCODEX-END -->"
            )

            dest_dir = Path(tmpdir) / "dest"
            dest_claude = dest_dir / ".claude"
            dest_rules = dest_claude / "rules"
            dest_rules.mkdir(parents=True)
            (dest_rules / "my-project-rules.md").write_text("USER PROJECT RULES - PRESERVED")

            ctx = InstallContext(
                project_dir=dest_dir,
                ui=Console(non_interactive=True),
                local_mode=True,
                local_repo_dir=Path(tmpdir) / "source",
            )

            _run_full_install_flow(ctx, home_dir=home_dir)

            assert (dest_rules / "my-project-rules.md").exists()
            assert (dest_rules / "my-project-rules.md").read_text() == "USER PROJECT RULES - PRESERVED"

            global_rules = home_dir / ".claude" / "rules"
            assert (global_rules / "python-rules.md").exists()
            assert (global_rules / "python-rules.md").read_text() == "python rules from repo"
            assert (global_rules / "standard-rule.md").exists()
            conditional = (global_rules / "conditional-rule.md").read_text()
            assert "Shared." in conditional
            assert "Claude only." in conditional
            assert "Codex only." not in conditional
            assert "CC-ONLY" not in conditional
            assert "CODEX-START" not in conditional

    def test_pycache_files_not_copied(self):
        """ClaudeFilesStep skips __pycache__ directories and .pyc files."""
        from installer.context import InstallContext
        from installer.steps.claude_files import ClaudeFilesStep
        from installer.ui import Console

        ClaudeFilesStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            home_dir = Path(tmpdir) / "home"
            home_dir.mkdir()

            source_pilot = Path(tmpdir) / "source" / "pilot"
            source_rules = source_pilot / "rules"
            source_pycache = source_rules / "__pycache__"
            source_pycache.mkdir(parents=True)
            (source_rules / "test-rule.md").write_text("# rule")
            (source_pycache / "something.cpython-312.pyc").write_text("bytecode")

            dest_dir = Path(tmpdir) / "dest"
            dest_dir.mkdir()

            ctx = InstallContext(
                project_dir=dest_dir,
                ui=Console(non_interactive=True),
                local_mode=True,
                local_repo_dir=Path(tmpdir) / "source",
            )

            _run_full_install_flow(ctx, home_dir=home_dir)

            global_rules = home_dir / ".claude" / "rules"
            assert (global_rules / "test-rule.md").exists()
            assert not (global_rules / "__pycache__").exists()


class TestDirectoryClearing:
    """Test directory clearing behavior in local and normal mode."""

    def test_clears_managed_files_preserves_user_files(self):
        """Pilot-managed rules are removed on update; user-created files are preserved."""
        from installer.context import InstallContext
        from installer.ui import Console

        with tempfile.TemporaryDirectory() as tmpdir:
            home_dir = Path(tmpdir) / "home"
            home_dir.mkdir()

            old_global_rules = home_dir / ".claude" / "rules"
            old_global_rules.mkdir(parents=True)
            (old_global_rules / "old-rule.md").write_text("old Pilot rule to be removed")
            (old_global_rules / "my-custom-rule.md").write_text("user-created rule")

            manifest_path = home_dir / ".claude" / ".pilot-manifest.json"
            manifest_path.write_text(json.dumps({"files": ["rules/old-rule.md"]}, indent=2))

            source_dir = Path(tmpdir) / "source"
            source_pilot = source_dir / "pilot"
            source_rules = source_pilot / "rules"
            source_rules.mkdir(parents=True)
            (source_rules / "new-rule.md").write_text("new rule content")

            dest_dir = Path(tmpdir) / "dest"
            dest_dir.mkdir()

            ctx = InstallContext(
                project_dir=dest_dir,
                ui=Console(non_interactive=True),
                local_mode=True,
                local_repo_dir=source_dir,
            )

            _run_full_install_flow(ctx, home_dir=home_dir)

            global_rules = home_dir / ".claude" / "rules"
            assert (global_rules / "new-rule.md").exists()
            assert (global_rules / "new-rule.md").read_text() == "new rule content"
            assert not (global_rules / "old-rule.md").exists()
            assert (global_rules / "my-custom-rule.md").exists()
            assert (global_rules / "my-custom-rule.md").read_text() == "user-created rule"

    def test_legacy_upgrade_seeds_manifest_and_cleans_old_files(self):
        """Pre-manifest upgrade: old Pilot files are seeded into manifest and cleaned up."""
        from installer.context import InstallContext
        from installer.steps.claude_files import PILOT_MANIFEST_FILE
        from installer.ui import Console

        with tempfile.TemporaryDirectory() as tmpdir:
            home_dir = Path(tmpdir) / "home"
            home_dir.mkdir()

            old_global_rules = home_dir / ".claude" / "rules"
            old_global_rules.mkdir(parents=True)
            (old_global_rules / "old-pilot-rule.md").write_text("old Pilot rule")
            (old_global_rules / "another-old-rule.md").write_text("another old rule")

            old_global_cmds = home_dir / ".claude" / "commands"
            old_global_cmds.mkdir(parents=True)
            (old_global_cmds / "old-cmd.md").write_text("old Pilot command")

            manifest_path = home_dir / ".claude" / PILOT_MANIFEST_FILE
            assert not manifest_path.exists()

            source_dir = Path(tmpdir) / "source"
            source_pilot = source_dir / "pilot"
            source_rules = source_pilot / "rules"
            source_rules.mkdir(parents=True)
            (source_rules / "new-rule.md").write_text("new rule content")

            dest_dir = Path(tmpdir) / "dest"
            dest_dir.mkdir()

            ctx = InstallContext(
                project_dir=dest_dir,
                ui=Console(non_interactive=True),
                local_mode=True,
                local_repo_dir=source_dir,
            )

            _run_full_install_flow(ctx, home_dir=home_dir)

            global_rules = home_dir / ".claude" / "rules"
            assert (global_rules / "new-rule.md").exists()
            assert not (global_rules / "old-pilot-rule.md").exists()
            assert not (global_rules / "another-old-rule.md").exists()
            assert not (old_global_cmds / "old-cmd.md").exists()
            assert manifest_path.exists()

    def test_deprecated_pilot_skills_cleaned_from_home(self):
        """Regression for Sweep-Manifest: skills Pilot historically shipped but
        no longer ships (e.g., `notify`, `skill-build`) are removed from
        ~/.claude/skills/ by the explicit deprecated-name cleanup. User
        skills with non-deprecated names are preserved untouched."""
        from installer.steps.claude_files import ClaudeFilesStep

        step = ClaudeFilesStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            home_dir = Path(tmpdir) / "home"
            home_claude = home_dir / ".claude"

            skills_dir = home_claude / "skills"
            skills_dir.mkdir(parents=True)
            # Deprecated Pilot skills — must be removed.
            (skills_dir / "notify").mkdir()
            (skills_dir / "notify" / "SKILL.md").write_text("legacy notify")
            (skills_dir / "skill-build").mkdir()
            (skills_dir / "skill-build" / "SKILL.md").write_text("legacy skill-build")
            # User skill — must survive.
            (skills_dir / "my-custom-skill").mkdir()
            (skills_dir / "my-custom-skill" / "SKILL.md").write_text("user custom")

            step._cleanup_deprecated_pilot_skills_in_home(home_claude)  # type: ignore[attr-defined]

            assert not (skills_dir / "notify").exists()
            assert not (skills_dir / "skill-build").exists()
            assert (skills_dir / "my-custom-skill" / "SKILL.md").read_text() == "user custom"

    def test_deprecated_cleanup_idempotent_when_dirs_missing(self):
        """No-op when ~/.claude/skills/ does not exist (fresh install path)."""
        from installer.steps.claude_files import ClaudeFilesStep

        step = ClaudeFilesStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            home_dir = Path(tmpdir) / "home"
            home_claude = home_dir / ".claude"
            home_claude.mkdir(parents=True)
            # Should not raise; nothing to clean.
            step._cleanup_deprecated_pilot_skills_in_home(home_claude)  # type: ignore[attr-defined]

    def test_skips_clearing_when_source_equals_destination(self):
        """Directories are NOT cleared when source == destination (same dir)."""
        from installer.context import InstallContext
        from installer.steps.claude_files import ClaudeFilesStep
        from installer.ui import Console

        ClaudeFilesStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            home_dir = Path(tmpdir) / "home"
            home_dir.mkdir()

            pilot_dir = Path(tmpdir) / "pilot"
            rules_dir = pilot_dir / "rules"
            rules_dir.mkdir(parents=True)
            (rules_dir / "existing-rule.md").write_text("existing rule content")

            ctx = InstallContext(
                project_dir=Path(tmpdir),
                ui=Console(non_interactive=True),
                local_mode=True,
                local_repo_dir=Path(tmpdir),
            )

            _run_full_install_flow(ctx, home_dir=home_dir)

            assert (home_dir / ".claude" / "rules" / "existing-rule.md").exists()

    def test_stale_managed_rules_removed_when_source_equals_destination(self):
        """Stale Pilot-managed rules are removed even when source == destination."""
        from installer.context import InstallContext
        from installer.ui import Console

        with tempfile.TemporaryDirectory() as tmpdir:
            home_dir = Path(tmpdir) / "home"
            home_dir.mkdir()

            global_rules = home_dir / ".claude" / "rules"
            global_rules.mkdir(parents=True)
            (global_rules / "old-deleted-rule.md").write_text("stale rule from previous install")

            manifest_path = home_dir / ".claude" / ".pilot-manifest.json"
            manifest_path.write_text(json.dumps({"files": ["rules/old-deleted-rule.md"]}, indent=2))

            pilot_dir = Path(tmpdir) / "pilot"
            rules_dir = pilot_dir / "rules"
            rules_dir.mkdir(parents=True)
            (rules_dir / "current-rule.md").write_text("current rule content")

            ctx = InstallContext(
                project_dir=Path(tmpdir),
                ui=Console(non_interactive=True),
                local_mode=True,
                local_repo_dir=Path(tmpdir),
            )

            _run_full_install_flow(ctx, home_dir=home_dir)

            assert (global_rules / "current-rule.md").exists()
            assert not (global_rules / "old-deleted-rule.md").exists()

    def test_project_rules_never_cleared(self):
        """Project rules directory is NEVER cleared, only global standard rules."""
        from installer.context import InstallContext
        from installer.steps.claude_files import ClaudeFilesStep
        from installer.ui import Console

        ClaudeFilesStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            home_dir = Path(tmpdir) / "home"
            home_dir.mkdir()

            source_dir = Path(tmpdir) / "source"
            source_pilot = source_dir / "pilot"
            source_rules = source_pilot / "rules"
            source_rules.mkdir(parents=True)
            (source_rules / "new-rule.md").write_text("new standard rule")

            dest_dir = Path(tmpdir) / "dest"
            dest_claude = dest_dir / ".claude"
            dest_project_rules = dest_claude / "rules"
            dest_project_rules.mkdir(parents=True)
            (dest_project_rules / "my-project.md").write_text("USER PROJECT RULE")

            ctx = InstallContext(
                project_dir=dest_dir,
                ui=Console(non_interactive=True),
                local_mode=True,
                local_repo_dir=source_dir,
            )

            _run_full_install_flow(ctx, home_dir=home_dir)

            assert (dest_project_rules / "my-project.md").exists()
            assert (dest_project_rules / "my-project.md").read_text() == "USER PROJECT RULE"

            global_rules = home_dir / ".claude" / "rules"
            assert (global_rules / "new-rule.md").exists()

    def test_skills_installed_to_root_level(self):
        """Skills from pilot/skills/ are installed to ~/.claude/skills/."""
        from installer.context import InstallContext
        from installer.ui import Console

        with tempfile.TemporaryDirectory() as tmpdir:
            home_dir = Path(tmpdir) / "home"
            home_dir.mkdir()

            source_dir = Path(tmpdir) / "source"
            source_pilot = source_dir / "pilot"
            spec_dir = source_pilot / "skills" / "spec"
            spec_dir.mkdir(parents=True)
            (spec_dir / "SKILL.md").write_text("new spec skill")

            dest_dir = Path(tmpdir) / "dest"
            dest_dir.mkdir()

            ctx = InstallContext(
                project_dir=dest_dir,
                ui=Console(non_interactive=True),
                local_mode=True,
                local_repo_dir=source_dir,
            )

            _run_full_install_flow(ctx, home_dir=home_dir)

            global_skills = home_dir / ".claude" / "skills"
            assert (global_skills / "spec" / "SKILL.md").exists()
            assert (global_skills / "spec" / "SKILL.md").read_text() == "new spec skill"

    def test_pilot_assets_land_in_correct_global_locations(self):
        """Hooks go to ~/.pilot/hooks/, scripts and MCP config to ~/.pilot/,
        no files end up in the legacy ~/.claude/pilot/ directory."""
        from installer.context import InstallContext
        from installer.ui import Console

        with tempfile.TemporaryDirectory() as tmpdir:
            home_dir = Path(tmpdir) / "home"
            home_dir.mkdir()

            source_dir = Path(tmpdir) / "source"
            source_pilot = source_dir / "pilot"
            source_pilot.mkdir(parents=True)
            (source_pilot / "package.json").write_text('{"name": "pilot"}')
            (source_pilot / "plugin.json").write_text('{"version": "1.0"}')
            (source_pilot / ".mcp.json").write_text('{"servers": []}')
            (source_pilot / ".lsp.json").write_text('{"python": {}}')
            (source_pilot / "scripts").mkdir()
            (source_pilot / "scripts" / "mcp-server.cjs").write_text("// mcp server")
            (source_pilot / "hooks").mkdir()
            (source_pilot / "hooks" / "hook.py").write_text("# hook")

            dest_dir = Path(tmpdir) / "dest"
            dest_dir.mkdir()

            ctx = InstallContext(
                project_dir=dest_dir,
                ui=Console(non_interactive=True),
                local_mode=True,
                local_repo_dir=source_dir,
            )

            _run_full_install_flow(ctx, home_dir=home_dir)

            claude_dir = home_dir / ".claude"
            pilot_home = home_dir / ".pilot"

            # plugin.json and .lsp.json are SKIPPED entirely (Pilot is no longer
            # registered as a Claude Code plugin; LSP moved to the
            # Piebald-AI/claude-code-lsps marketplace).
            assert not (claude_dir / "pilot").exists(), "legacy ~/.claude/pilot/ must not be created"
            assert not (pilot_home / "plugin.json").exists()
            assert not (pilot_home / ".lsp.json").exists()

            # Hooks land at ~/.pilot/hooks/ (agent-neutral).
            assert (pilot_home / "hooks" / "hook.py").exists()

            # Pilot runtime assets land at ~/.pilot/ (scripts, MCP template, package.json).
            assert (pilot_home / "package.json").exists()
            assert (pilot_home / ".mcp.json").exists()
            assert (pilot_home / "scripts" / "mcp-server.cjs").exists()


class TestMergeAppConfig:
    """Test merging pilot/claude.json app preferences into ~/.claude.json."""

    def test_merge_sets_new_keys(self):
        """Keys in source that don't exist in target are added."""
        from installer.steps.settings_merge import merge_app_config

        target = {"numStartups": 500, "oauthAccount": {"email": "x"}}
        source = {"autoCompactEnabled": True, "theme": "dark"}

        result = merge_app_config(target, source)

        assert result is not None
        assert result["autoCompactEnabled"] is True
        assert result["theme"] == "dark"
        assert result["numStartups"] == 500
        assert result["oauthAccount"] == {"email": "x"}

    def test_merge_updates_existing_keys(self):
        """Keys in source that exist in target are updated to source value."""
        from installer.steps.settings_merge import merge_app_config

        target = {"autoCompactEnabled": False, "verbose": False}
        source = {"autoCompactEnabled": True, "verbose": True}

        result = merge_app_config(target, source)

        assert result is not None
        assert result["autoCompactEnabled"] is True
        assert result["verbose"] is True

    def test_merge_preserves_all_other_keys(self):
        """Keys not in source are never touched."""
        from installer.steps.settings_merge import merge_app_config

        target = {
            "numStartups": 500,
            "oauthAccount": {"email": "x"},
            "projects": {"path": {}},
            "skillUsage": {"spec": 10},
            "cachedGrowthBookFeatures": {"flag": True},
        }
        source = {"theme": "dark"}

        result = merge_app_config(target, source)

        assert result is not None
        assert result["numStartups"] == 500
        assert result["oauthAccount"] == {"email": "x"}
        assert result["projects"] == {"path": {}}
        assert result["skillUsage"] == {"spec": 10}
        assert result["cachedGrowthBookFeatures"] == {"flag": True}

    def test_merge_returns_none_when_no_changes(self):
        """Returns None when all source keys already match target values."""
        from installer.steps.settings_merge import merge_app_config

        target = {"autoCompactEnabled": True, "theme": "dark", "numStartups": 500}
        source = {"autoCompactEnabled": True, "theme": "dark"}

        result = merge_app_config(target, source)

        assert result is None

    def test_integration_merges_claude_json(self):
        """Installer merges pilot/claude.json preferences into ~/.claude.json."""
        from installer.context import InstallContext
        from installer.ui import Console

        with tempfile.TemporaryDirectory() as tmpdir:
            home_dir = Path(tmpdir) / "home"
            home_dir.mkdir()
            (home_dir / ".claude").mkdir(parents=True)

            claude_json_path = home_dir / ".claude.json"
            claude_json_path.write_text(
                json.dumps(
                    {
                        "numStartups": 500,
                        "autoCompactEnabled": False,
                        "oauthAccount": {"email": "user@test.com"},
                        "projects": {},
                    },
                    indent=2,
                )
                + "\n"
            )

            source_pilot = Path(tmpdir) / "source" / "pilot"
            source_pilot.mkdir(parents=True)
            (source_pilot / "settings.json").write_text(
                json.dumps({"env": {"X": "1"}, "permissions": {"defaultMode": "bypassPermissions"}}, indent=2)
            )
            (source_pilot / "claude.json").write_text(
                json.dumps(
                    {
                        "autoCompactEnabled": True,
                        "theme": "dark",
                        "verbose": True,
                    },
                    indent=2,
                )
            )

            dest_dir = Path(tmpdir) / "dest"
            dest_dir.mkdir()

            ctx = InstallContext(
                project_dir=dest_dir,
                ui=Console(non_interactive=True),
                local_mode=True,
                local_repo_dir=Path(tmpdir) / "source",
            )

            _run_full_install_flow(ctx, home_dir=home_dir)

            patched = json.loads(claude_json_path.read_text())

            assert patched["autoCompactEnabled"] is True
            assert patched["theme"] == "dark"
            assert patched["verbose"] is True
            assert patched["numStartups"] == 500
            assert patched["oauthAccount"] == {"email": "user@test.com"}
            assert patched["projects"] == {}

    def test_creates_claude_json_if_missing(self):
        """Installer creates ~/.claude.json if it doesn't exist."""
        from installer.context import InstallContext
        from installer.ui import Console

        with tempfile.TemporaryDirectory() as tmpdir:
            home_dir = Path(tmpdir) / "home"
            home_dir.mkdir()
            (home_dir / ".claude").mkdir(parents=True)

            source_pilot = Path(tmpdir) / "source" / "pilot"
            source_pilot.mkdir(parents=True)
            (source_pilot / "settings.json").write_text(
                json.dumps({"env": {"X": "1"}, "permissions": {"defaultMode": "bypassPermissions"}}, indent=2)
            )
            (source_pilot / "claude.json").write_text(
                json.dumps({"autoCompactEnabled": True, "theme": "dark"}, indent=2)
            )

            dest_dir = Path(tmpdir) / "dest"
            dest_dir.mkdir()

            ctx = InstallContext(
                project_dir=dest_dir,
                ui=Console(non_interactive=True),
                local_mode=True,
                local_repo_dir=Path(tmpdir) / "source",
            )

            claude_json_path = home_dir / ".claude.json"
            assert not claude_json_path.exists()

            _run_full_install_flow(ctx, home_dir=home_dir)

            assert claude_json_path.exists()
            patched = json.loads(claude_json_path.read_text())
            assert patched["autoCompactEnabled"] is True
            assert patched["theme"] == "dark"

    def test_app_config_lands_in_custom_config_dir(self, tmp_path, monkeypatch):
        """With CLAUDE_CONFIG_DIR set, app preferences must NOT touch ~/.claude.json."""
        from unittest.mock import patch

        from installer.steps.claude_files import ClaudeFilesStep

        home = tmp_path
        custom_dir = tmp_path / ".claude_work"
        custom_dir.mkdir()
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(custom_dir))

        pilot_home = tmp_path / ".pilot"
        pilot_home.mkdir(parents=True)
        (pilot_home / "claude.json").write_text(json.dumps({"theme": "dark"}, indent=2))
        personal = home / ".claude.json"
        personal.write_text(json.dumps({"oauthAccount": "personal"}, indent=2))
        before = personal.read_text()

        step = ClaudeFilesStep()
        with patch("installer.steps.claude_files.Path.home", return_value=home):
            step._merge_app_config()

        assert personal.read_text() == before, "personal ~/.claude.json was modified"
        assert json.loads((custom_dir / ".claude.json").read_text())["theme"] == "dark"

    def test_app_config_uses_dot_config_json_when_present_and_unset(self, tmp_path, monkeypatch):
        """A default-dir user with ~/.claude/.config.json resolves there, matching Claude Code.

        This is the one case where an existing default-directory user's resolution
        legitimately changes, so assert it rather than letting it ride on the
        general "no behaviour change when unset" claim.
        """
        from unittest.mock import patch

        from installer.steps.claude_files import ClaudeFilesStep

        monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
        home = tmp_path
        claude_dir = home / ".claude"
        claude_dir.mkdir()
        (claude_dir / ".config.json").write_text(json.dumps({"oauthAccount": "x"}, indent=2))

        pilot_home = tmp_path / ".pilot"
        pilot_home.mkdir(parents=True)
        (pilot_home / "claude.json").write_text(json.dumps({"theme": "dark"}, indent=2))

        step = ClaudeFilesStep()
        with patch("installer.steps.claude_files.Path.home", return_value=home):
            step._merge_app_config()

        assert json.loads((claude_dir / ".config.json").read_text())["theme"] == "dark"
        assert not (home / ".claude.json").exists()

    def test_no_crash_when_claude_json_template_missing(self):
        """Installer skips merge when pilot/claude.json was not installed."""
        from installer.context import InstallContext
        from installer.steps.claude_files import ClaudeFilesStep
        from installer.ui import Console

        ClaudeFilesStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            home_dir = Path(tmpdir) / "home"
            home_dir.mkdir()
            (home_dir / ".claude").mkdir(parents=True)

            source_pilot = Path(tmpdir) / "source" / "pilot"
            source_pilot.mkdir(parents=True)
            (source_pilot / "settings.json").write_text(
                json.dumps({"env": {"X": "1"}, "permissions": {"defaultMode": "bypassPermissions"}}, indent=2)
            )

            dest_dir = Path(tmpdir) / "dest"
            dest_dir.mkdir()

            ctx = InstallContext(
                project_dir=dest_dir,
                ui=Console(non_interactive=True),
                local_mode=True,
                local_repo_dir=Path(tmpdir) / "source",
            )

            _run_full_install_flow(ctx, home_dir=home_dir)

            assert not (home_dir / ".claude.json").exists()


class TestMergeSettings:
    """Tests for three-way settings merge."""

    def test_first_install_uses_incoming(self):
        """Without baseline or current, incoming settings are used as-is."""
        from installer.steps.settings_merge import merge_settings

        incoming = {
            "env": {"A": "1", "B": "2"},
            "permissions": {"defaultMode": "bypassPermissions"},
            "spinnerTipsEnabled": False,
        }
        result = merge_settings(None, {}, incoming)

        assert result["env"] == {"A": "1", "B": "2"}
        assert result["permissions"]["defaultMode"] == "bypassPermissions"
        assert result["spinnerTipsEnabled"] is False

    def test_preserves_user_changed_env_var(self):
        """If user changed an env var value, Pilot doesn't overwrite it."""
        from installer.steps.settings_merge import merge_settings

        baseline = {"env": {"DISABLE_TELEMETRY": "true", "ENABLE_LSP_TOOL": "true"}}
        current = {"env": {"DISABLE_TELEMETRY": "false", "ENABLE_LSP_TOOL": "true"}}
        incoming = {"env": {"DISABLE_TELEMETRY": "true", "ENABLE_LSP_TOOL": "true", "NEW_VAR": "1"}}

        result = merge_settings(baseline, current, incoming)

        assert result["env"]["DISABLE_TELEMETRY"] == "false"
        assert result["env"]["NEW_VAR"] == "1"
        assert result["env"]["ENABLE_LSP_TOOL"] == "true"

    def test_preserves_user_only_keys(self):
        """Keys the user added that Pilot doesn't manage are preserved."""
        from installer.steps.settings_merge import merge_settings

        baseline = {"spinnerTipsEnabled": False}
        current = {"spinnerTipsEnabled": False, "myCustomKey": "hello"}
        incoming = {"spinnerTipsEnabled": False}

        result = merge_settings(baseline, current, incoming)

        assert result["myCustomKey"] == "hello"

    def test_adds_new_pilot_keys(self):
        """New keys from Pilot are added on update."""
        from installer.steps.settings_merge import merge_settings

        baseline = {"env": {"A": "1"}}
        current = {"env": {"A": "1"}}
        incoming = {"env": {"A": "1", "B": "2"}, "newFeature": True}

        result = merge_settings(baseline, current, incoming)

        assert result["env"]["B"] == "2"
        assert result["newFeature"] is True

    def test_updates_unchanged_scalars(self):
        """Scalar values the user didn't touch get updated to new Pilot values."""
        from installer.steps.settings_merge import merge_settings

        baseline = {"alwaysThinkingEnabled": False}
        current = {"alwaysThinkingEnabled": False}
        incoming = {"alwaysThinkingEnabled": True}

        result = merge_settings(baseline, current, incoming)

        assert result["alwaysThinkingEnabled"] is True

    def test_preserves_user_changed_scalar(self):
        """Scalar values the user changed from baseline are kept."""
        from installer.steps.settings_merge import merge_settings

        baseline = {"alwaysThinkingEnabled": True}
        current = {"alwaysThinkingEnabled": False}
        incoming = {"alwaysThinkingEnabled": True}

        result = merge_settings(baseline, current, incoming)

        assert result["alwaysThinkingEnabled"] is False

    def test_preserves_existing_value_when_pilot_starts_managing_setting(self):
        """A pre-existing user preference wins when Pilot first adds the same key."""
        from installer.steps.settings_merge import merge_settings

        baseline = {"alwaysThinkingEnabled": True}
        current = {"alwaysThinkingEnabled": True, "viewMode": "default"}
        incoming = {"alwaysThinkingEnabled": True, "viewMode": "verbose"}

        result = merge_settings(baseline, current, incoming)

        assert result["viewMode"] == "default"

    def test_preserves_user_added_env_vars(self):
        """User-added env vars not in Pilot's set are preserved."""
        from installer.steps.settings_merge import merge_settings

        baseline = {"env": {"A": "1"}}
        current = {"env": {"A": "1", "MY_CUSTOM_VAR": "yes"}}
        incoming = {"env": {"A": "1"}}

        result = merge_settings(baseline, current, incoming)

        assert result["env"]["MY_CUSTOM_VAR"] == "yes"

    def test_pilot_removed_key_dropped_when_user_unchanged(self):
        """Key Pilot previously managed and user didn't change is removed when Pilot drops it."""
        from installer.steps.settings_merge import merge_settings

        baseline = {"spinnerTipsEnabled": False, "model": "sonnet"}
        current = {"spinnerTipsEnabled": False, "model": "sonnet"}
        incoming = {"spinnerTipsOverride": {"tips": ["tip1"], "excludeDefault": True}, "model": "sonnet"}

        result = merge_settings(baseline, current, incoming)

        assert "spinnerTipsEnabled" not in result
        assert result["spinnerTipsOverride"] == {"tips": ["tip1"], "excludeDefault": True}

    def test_pilot_removed_key_preserved_when_user_changed(self):
        """Key Pilot managed but user changed is preserved even when Pilot removes it."""
        from installer.steps.settings_merge import merge_settings

        baseline = {"spinnerTipsEnabled": False}
        current = {"spinnerTipsEnabled": True}
        incoming = {"spinnerTipsOverride": {"tips": ["tip1"], "excludeDefault": True}}

        result = merge_settings(baseline, current, incoming)

        assert result["spinnerTipsEnabled"] is True
        assert result["spinnerTipsOverride"] == {"tips": ["tip1"], "excludeDefault": True}

    def test_user_added_key_not_in_baseline_preserved_when_not_in_incoming(self):
        """User-added keys (never in Pilot baseline) are always preserved."""
        from installer.steps.settings_merge import merge_settings

        baseline = {"model": "sonnet"}
        current = {"model": "sonnet", "myCustomKey": "hello"}
        incoming = {"model": "opus"}

        result = merge_settings(baseline, current, incoming)

        assert result["myCustomKey"] == "hello"
        assert result["model"] == "opus"

    def test_pilot_removed_env_var_dropped_when_user_unchanged(self):
        """An env var Pilot stops shipping is removed when the user never changed it.

        Same rule as top-level keys: Pilot-written, untouched, gone from the new
        template -> drop. Otherwise retired Claude Code env vars linger forever
        in every install (a settings template can only ever grow)."""
        from installer.steps.settings_merge import merge_settings

        baseline = {"env": {"KEEP": "1", "RETIRED_FLAG": "true"}}
        current = {"env": {"KEEP": "1", "RETIRED_FLAG": "true"}}
        incoming = {"env": {"KEEP": "1"}}

        result = merge_settings(baseline, current, incoming)

        assert "RETIRED_FLAG" not in result["env"]
        assert result["env"]["KEEP"] == "1"

    def test_pilot_removed_env_var_preserved_when_user_changed(self):
        """A retired env var the user re-pointed to their own value is theirs now."""
        from installer.steps.settings_merge import merge_settings

        baseline = {"env": {"KEEP": "1", "RETIRED_FLAG": "true"}}
        current = {"env": {"KEEP": "1", "RETIRED_FLAG": "0"}}
        incoming = {"env": {"KEEP": "1"}}

        result = merge_settings(baseline, current, incoming)

        assert result["env"]["RETIRED_FLAG"] == "0"


class TestMergeAppConfigWithBaseline:
    """Tests for merge_app_config with baseline parameter."""

    def test_baseline_preserves_user_changes(self):
        """User changes to ~/.claude.json are preserved when baseline exists."""
        from installer.steps.settings_merge import merge_app_config

        target = {"autoCompactEnabled": False, "verbose": True}
        source = {"autoCompactEnabled": True, "verbose": True, "newKey": "value"}
        baseline = {"autoCompactEnabled": True, "verbose": True}

        result = merge_app_config(target, source, baseline)

        assert result is not None
        assert result["autoCompactEnabled"] is False
        assert result["newKey"] == "value"
        assert result["verbose"] is True

    def test_no_baseline_overwrites_like_before(self):
        """Without baseline (first install), all source keys are applied."""
        from installer.steps.settings_merge import merge_app_config

        target = {"autoCompactEnabled": False}
        source = {"autoCompactEnabled": True}

        result = merge_app_config(target, source, None)

        assert result is not None
        assert result["autoCompactEnabled"] is True


class TestMergePermissions:
    """Tests for permissions dict merge (scalar keys only, no allow/deny/ask lists)."""

    def test_user_default_mode_preserved_through_update(self):
        """User's defaultMode: bypassPermissions survives a Pilot update."""
        from installer.steps.settings_merge import merge_settings

        baseline = {"permissions": {"defaultMode": "bypassPermissions"}}
        current = {"permissions": {"defaultMode": "bypassPermissions"}}
        incoming = {"permissions": {"defaultMode": "bypassPermissions"}}

        result = merge_settings(baseline, current, incoming)

        assert result["permissions"]["defaultMode"] == "bypassPermissions"

    def test_default_mode_in_incoming_is_applied(self):
        """defaultMode from Pilot's incoming settings is applied on first install."""
        from installer.steps.settings_merge import merge_settings

        incoming = {"permissions": {"defaultMode": "bypassPermissions"}}
        result = merge_settings(None, {}, incoming)

        assert result["permissions"]["defaultMode"] == "bypassPermissions"

    def test_user_changed_default_mode_preserved(self):
        """User's manually changed defaultMode is preserved even if Pilot updates it."""
        from installer.steps.settings_merge import merge_settings

        baseline = {"permissions": {"defaultMode": "bypassPermissions"}}
        current = {"permissions": {"defaultMode": "default"}}
        incoming = {"permissions": {"defaultMode": "bypassPermissions"}}

        result = merge_settings(baseline, current, incoming)

        assert result["permissions"]["defaultMode"] == "default"

    def test_user_added_custom_key_preserved(self):
        """User-added keys in permissions survive a Pilot update."""
        from installer.steps.settings_merge import merge_settings

        baseline = {"permissions": {"defaultMode": "bypassPermissions"}}
        current = {"permissions": {"defaultMode": "bypassPermissions", "customKey": "userValue"}}
        incoming = {"permissions": {"defaultMode": "bypassPermissions"}}

        result = merge_settings(baseline, current, incoming)

        assert result["permissions"]["defaultMode"] == "bypassPermissions"
        assert result["permissions"]["customKey"] == "userValue"


class TestResolveRepoUrl:
    """Tests for _resolve_repo_url method."""

    def test_resolve_repo_url_returns_correct_url(self):
        """_resolve_repo_url returns the repository URL."""
        from installer.steps.claude_files import ClaudeFilesStep

        step = ClaudeFilesStep()
        result = step._resolve_repo_url("v5.0.0")

        assert result == "https://github.com/maxritter/pilot-shell"


class TestSkillsDeployment:
    """Test that skills from pilot/skills/ are deployed to ~/.claude/skills/."""

    def test_all_skills_categorized_as_skills(self):
        """All files in pilot/skills/ are categorized as 'skills' for root-level installation."""
        from installer.steps.claude_files import _categorize_file

        assert _categorize_file("pilot/skills/spec/SKILL.md") == "skills"
        assert _categorize_file("pilot/skills/setup-rules/SKILL.md") == "skills"
        assert _categorize_file("pilot/skills/mcp-servers/skill.md") == "skills"

    def test_benchmark_skill_nested_files_categorized_as_skills(self):
        """The benchmark skill ships scripts/ and agents/ subdirs.

        Regression guard: ensure the categorizer treats these as skill content, not
        as project-level Python source or rules.
        """
        from installer.steps.claude_files import _categorize_file

        assert _categorize_file("pilot/skills/benchmark/SKILL.md") == "skills"
        assert _categorize_file("pilot/skills/benchmark/manifest.json") == "skills"
        assert _categorize_file("pilot/skills/benchmark/orchestrator.md") == "skills"
        assert _categorize_file("pilot/skills/benchmark/steps/01-intake.md") == "skills"
        assert _categorize_file("pilot/skills/benchmark/scripts/runner.py") == "skills"
        assert _categorize_file("pilot/skills/benchmark/scripts/utils.py") == "skills"
        assert _categorize_file("pilot/skills/benchmark/agents/grader.md") == "skills"

    def test_skills_deployed_to_root_skills_dir(self):
        """Skills are installed to ~/.claude/skills/<name>/ (root level, not plugin)."""
        from installer.context import InstallContext
        from installer.ui import Console

        with tempfile.TemporaryDirectory() as tmpdir:
            home_dir = Path(tmpdir) / "home"
            home_dir.mkdir()

            source_dir = Path(tmpdir) / "source"
            source_pilot = source_dir / "pilot"
            skill_dir = source_pilot / "skills" / "mcp-servers"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text("---\nname: mcp-servers\n---\n# MCP Servers")

            dest_dir = Path(tmpdir) / "dest"
            dest_dir.mkdir()

            ctx = InstallContext(
                project_dir=dest_dir,
                ui=Console(non_interactive=True),
                local_mode=True,
                local_repo_dir=source_dir,
            )

            _run_full_install_flow(ctx, home_dir=home_dir)

            expected_path = home_dir / ".claude" / "skills" / "mcp-servers" / "SKILL.md"
            assert expected_path.exists(), f"Skill not at {expected_path}"
            assert "MCP Servers" in expected_path.read_text()


class TestCommandsToSkillsMigration:
    """Test migration from legacy commands/ to skills/ format."""

    def test_old_commands_cleaned_up_during_migration(self):
        """Legacy commands in manifest are removed when upgrading to skills format."""
        from installer.context import InstallContext
        from installer.steps.claude_files import PILOT_MANIFEST_FILE
        from installer.ui import Console

        with tempfile.TemporaryDirectory() as tmpdir:
            home_dir = Path(tmpdir) / "home"
            home_dir.mkdir()

            # Old commands exist from previous install
            old_commands = home_dir / ".claude" / "commands"
            old_commands.mkdir(parents=True)
            (old_commands / "spec.md").write_text("old spec command")
            (old_commands / "setup-rules.md").write_text("old setup-rules command")

            # Old manifest tracks commands
            manifest_path = home_dir / ".claude" / PILOT_MANIFEST_FILE
            manifest_path.write_text(json.dumps({"files": ["commands/spec.md", "commands/setup-rules.md"]}, indent=2))

            # Source now has skill folders
            source_dir = Path(tmpdir) / "source"
            spec_skill = source_dir / "pilot" / "skills" / "spec"
            spec_skill.mkdir(parents=True)
            (spec_skill / "SKILL.md").write_text("new spec skill")

            dest_dir = Path(tmpdir) / "dest"
            dest_dir.mkdir()

            ctx = InstallContext(
                project_dir=dest_dir,
                ui=Console(non_interactive=True),
                local_mode=True,
                local_repo_dir=source_dir,
            )

            _run_full_install_flow(ctx, home_dir=home_dir)

            # Old commands removed
            assert not (old_commands / "spec.md").exists()
            assert not (old_commands / "setup-rules.md").exists()

            # New skill installed
            global_skills = home_dir / ".claude" / "skills"
            assert (global_skills / "spec" / "SKILL.md").exists()
            assert (global_skills / "spec" / "SKILL.md").read_text() == "new spec skill"

            # Manifest updated with skills entries
            manifest = json.loads(manifest_path.read_text())
            assert "skills/spec/SKILL.md" in manifest["files"]
            assert "commands/spec.md" not in manifest["files"]

    def test_user_commands_preserved_during_migration(self):
        """User-created commands not in manifest are preserved during migration."""
        from installer.context import InstallContext
        from installer.steps.claude_files import PILOT_MANIFEST_FILE
        from installer.ui import Console

        with tempfile.TemporaryDirectory() as tmpdir:
            home_dir = Path(tmpdir) / "home"
            home_dir.mkdir()

            # Old Pilot command + user command
            old_commands = home_dir / ".claude" / "commands"
            old_commands.mkdir(parents=True)
            (old_commands / "spec.md").write_text("old spec command")
            (old_commands / "my-custom-cmd.md").write_text("user custom command")

            # Manifest only tracks Pilot files
            manifest_path = home_dir / ".claude" / PILOT_MANIFEST_FILE
            manifest_path.write_text(json.dumps({"files": ["commands/spec.md"]}, indent=2))

            source_dir = Path(tmpdir) / "source"
            spec_skill = source_dir / "pilot" / "skills" / "spec"
            spec_skill.mkdir(parents=True)
            (spec_skill / "SKILL.md").write_text("new spec skill")

            dest_dir = Path(tmpdir) / "dest"
            dest_dir.mkdir()

            ctx = InstallContext(
                project_dir=dest_dir,
                ui=Console(non_interactive=True),
                local_mode=True,
                local_repo_dir=source_dir,
            )

            _run_full_install_flow(ctx, home_dir=home_dir)

            # User command preserved
            assert (old_commands / "my-custom-cmd.md").exists()
            assert (old_commands / "my-custom-cmd.md").read_text() == "user custom command"

            # Pilot command removed
            assert not (old_commands / "spec.md").exists()

    def test_user_skills_not_seeded_into_manifest_on_legacy_upgrade(self):
        """User-owned global skills are NOT seeded into manifest during legacy upgrade."""
        from installer.context import InstallContext
        from installer.steps.claude_files import PILOT_MANIFEST_FILE, ClaudeFilesStep
        from installer.ui import Console

        ClaudeFilesStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            home_dir = Path(tmpdir) / "home"
            home_dir.mkdir()

            # Pre-existing user skill + Pilot skill (no manifest = legacy)
            skills_dir = home_dir / ".claude" / "skills"
            user_skill = skills_dir / "my-custom-skill"
            user_skill.mkdir(parents=True)
            (user_skill / "SKILL.md").write_text("user custom skill")

            pilot_skill = skills_dir / "spec"
            pilot_skill.mkdir(parents=True)
            (pilot_skill / "SKILL.md").write_text("old pilot spec skill")

            manifest_path = home_dir / ".claude" / PILOT_MANIFEST_FILE
            assert not manifest_path.exists()

            # Source has new spec skill
            source_dir = Path(tmpdir) / "source"
            spec_src = source_dir / "pilot" / "skills" / "spec"
            spec_src.mkdir(parents=True)
            (spec_src / "SKILL.md").write_text("new spec skill")

            dest_dir = Path(tmpdir) / "dest"
            dest_dir.mkdir()

            ctx = InstallContext(
                project_dir=dest_dir,
                ui=Console(non_interactive=True),
                local_mode=True,
                local_repo_dir=source_dir,
            )

            _run_full_install_flow(ctx, home_dir=home_dir)

            # User skill preserved — not seeded, not deleted
            assert (user_skill / "SKILL.md").exists()
            assert (user_skill / "SKILL.md").read_text() == "user custom skill"

            # Manifest does NOT contain user skill
            manifest = json.loads(manifest_path.read_text())
            assert not any("my-custom-skill" in f for f in manifest["files"])


def test_retired_bot_cleanup_preserves_personal_jobs(tmp_path, monkeypatch):
    from installer.context import InstallContext
    from installer.steps.claude_files import ClaudeFilesStep

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    claude = tmp_path / ".claude"
    neutral = tmp_path / ".pilot"
    entries = ["skills/bot-boot/manifest.json", "skills/bot-boot/orchestrator.md", "skills/bot-boot/SKILL.md"]
    for root in (claude, neutral):
        for entry in entries:
            dest = root / entry
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text("retired Pilot asset")
    personal = claude / "skills/bot-boot/personal.txt"
    personal.write_text("keep")
    jobs = neutral / "bot/JOBS.yaml"
    jobs.parent.mkdir(parents=True)
    jobs.write_text("jobs: {personal: keep}\n")
    (claude / ".pilot-manifest.json").write_text(json.dumps({"files": entries}))
    ClaudeFilesStep()._cleanup_stale_managed_files(InstallContext(project_dir=tmp_path))
    assert all(not (root / entry).exists() for root in (claude, neutral) for entry in entries)
    assert jobs.read_text() == "jobs: {personal: keep}\n"
    assert personal.read_text() == "keep"


def test_retired_neutral_cleanup_does_not_follow_a_skill_alias(tmp_path, monkeypatch):
    from installer.context import InstallContext
    from installer.steps.claude_files import ClaudeFilesStep

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    claude = tmp_path / ".claude"
    claude.mkdir()
    (claude / ".pilot-manifest.json").write_text(json.dumps({"files": ["skills/bot-boot/orchestrator.md"]}))
    personal = tmp_path / ".pilot/personal"
    personal.mkdir(parents=True)
    (personal / "orchestrator.md").write_text("keep")
    skills = tmp_path / ".pilot/skills"
    skills.mkdir()
    (skills / "bot-boot").symlink_to(personal, target_is_directory=True)
    ClaudeFilesStep()._cleanup_stale_managed_files(InstallContext(project_dir=tmp_path))
    assert (personal / "orchestrator.md").read_text() == "keep"


class TestReapplyCustomization:
    """Tests for _reapply_customization in ClaudeFilesStep."""

    def test_calls_pilot_binary_when_customization_configured(self, tmp_path):
        import json
        from unittest.mock import MagicMock, patch

        from installer.steps.claude_files import ClaudeFilesStep

        config_path = tmp_path / ".pilot" / "config.json"
        config_path.parent.mkdir(parents=True)
        config_path.write_text(
            json.dumps({"customization": {"source": "https://github.com/org/repo.git", "branch": "main"}})
        )

        pilot_bin = tmp_path / ".pilot" / "bin" / "pilot"
        pilot_bin.parent.mkdir(parents=True)
        pilot_bin.touch()

        step = ClaudeFilesStep()
        ui = MagicMock()

        with (
            patch("installer.steps.claude_files.Path.home", return_value=tmp_path),
            patch("installer.steps.claude_files.subprocess.run") as mock_run,
        ):
            mock_run.return_value = MagicMock(returncode=0)
            step._reapply_customization(ui)

        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "customize" in call_args
        assert "update" in call_args
        assert "--quiet" in call_args

    def test_skips_silently_when_no_customization(self, tmp_path):
        import json
        from unittest.mock import MagicMock, patch

        from installer.steps.claude_files import ClaudeFilesStep

        config_path = tmp_path / ".pilot" / "config.json"
        config_path.parent.mkdir(parents=True)
        config_path.write_text(json.dumps({"model": "opus"}))

        step = ClaudeFilesStep()
        ui = MagicMock()

        with (
            patch("installer.steps.claude_files.Path.home", return_value=tmp_path),
            patch("installer.steps.claude_files.subprocess.run") as mock_run,
        ):
            step._reapply_customization(ui)

        mock_run.assert_not_called()

    def test_warns_on_failure(self, tmp_path):
        import json
        from unittest.mock import MagicMock, patch

        from installer.steps.claude_files import ClaudeFilesStep

        config_path = tmp_path / ".pilot" / "config.json"
        config_path.parent.mkdir(parents=True)
        config_path.write_text(json.dumps({"customization": {"source": "https://github.com/org/repo.git"}}))

        pilot_bin = tmp_path / ".pilot" / "bin" / "pilot"
        pilot_bin.parent.mkdir(parents=True)
        pilot_bin.touch()

        step = ClaudeFilesStep()
        ui = MagicMock()

        with (
            patch("installer.steps.claude_files.Path.home", return_value=tmp_path),
            patch("installer.steps.claude_files.subprocess.run") as mock_run,
        ):
            mock_run.return_value = MagicMock(returncode=1)
            step._reapply_customization(ui)

        # Customization reapply failures now surface as visible errors, not silent warnings
        ui.error.assert_called_once()
        assert "FAILED" in ui.error.call_args.args[0]


class TestSyncPilotEnvVars:
    """Tests for _sync_pilot_env_vars in ClaudeFilesStep (issue #154)."""

    def test_calls_pilot_sync_env_when_binary_present(self, tmp_path):
        from unittest.mock import MagicMock, patch

        from installer.steps.claude_files import ClaudeFilesStep

        pilot_bin = tmp_path / ".pilot" / "bin" / "pilot"
        pilot_bin.parent.mkdir(parents=True)
        pilot_bin.touch()

        step = ClaudeFilesStep()

        with (
            patch("installer.steps.claude_files.Path.home", return_value=tmp_path),
            patch("installer.steps.claude_files.subprocess.run") as mock_run,
        ):
            mock_run.return_value = MagicMock(returncode=0)
            step._sync_pilot_env_vars()

        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert str(pilot_bin) in call_args
        assert "sync-env" in call_args

    def test_skips_silently_when_binary_missing(self, tmp_path):
        from unittest.mock import patch

        from installer.steps.claude_files import ClaudeFilesStep

        step = ClaudeFilesStep()

        with (
            patch("installer.steps.claude_files.Path.home", return_value=tmp_path),
            patch("installer.steps.claude_files.subprocess.run") as mock_run,
        ):
            step._sync_pilot_env_vars()

        mock_run.assert_not_called()


class TestBuildSkillMdFiles:
    """Tests for the _build_skill_md_files method (Task 3: installer integration)."""

    def _make_skill(self, skills_dir: Path, skill_name: str) -> Path:
        """Create a skill directory with manifest.json, orchestrator, and one step."""
        skill_dir = skills_dir / skill_name
        skill_dir.mkdir(parents=True)
        (skill_dir / "orchestrator.md").write_text("# Skill")
        (skill_dir / "steps").mkdir()
        (skill_dir / "steps" / "01.md").write_text("## Step 1\n\nContent.")
        (skill_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "version": 1,
                    "orchestrator": "orchestrator.md",
                    "steps": [{"id": "step-1", "file": "steps/01.md"}],
                }
            )
        )
        return skill_dir

    def _make_ctx(self, tmp_path: Path):
        """Build a minimal InstallContext for _build_skill_md_files tests."""
        from installer.context import InstallContext

        ctx = InstallContext(project_dir=tmp_path)
        skills_dir = tmp_path / ".claude" / "skills"
        ctx.config["installed_files"] = [str(path) for path in skills_dir.glob("*/manifest.json")]
        return ctx

    def test_builds_skill_md_for_each_skill(self, tmp_path):
        """Each decomposed skill gets a SKILL.md materialized in-process."""
        from unittest.mock import MagicMock, patch

        from installer.steps.claude_files import ClaudeFilesStep

        skills_dir = tmp_path / ".claude" / "skills"
        skills_dir.mkdir(parents=True)
        skill_a = self._make_skill(skills_dir, "skill-a")
        skill_b = self._make_skill(skills_dir, "skill-b")

        step = ClaudeFilesStep()
        ui = MagicMock()
        ctx = self._make_ctx(tmp_path)

        with (
            patch("installer.steps.claude_files.Path.home", return_value=tmp_path),
            patch(
                "installer.steps.claude_files.get_claude_config_dir",
                return_value=tmp_path / ".claude",
            ),
        ):
            step._build_skill_md_files(ctx, ui)

        for skill_dir in (skill_a, skill_b):
            built = skill_dir / "SKILL.md"
            assert built.is_file()
            text = built.read_text()
            assert "# Skill" in text
            assert "## Step 1" in text
            assert str(built) in ctx.config.get("installed_files", [])
            assert str(skill_dir / "hashes.json") in ctx.config.get("installed_files", [])

    def test_10_7_upgrade_replaces_progressive_claude_artifact_with_bundled_skill(self, tmp_path):
        from unittest.mock import MagicMock, patch

        from installer.steps.claude_files import ClaudeFilesStep

        skills_dir = tmp_path / ".claude" / "skills"
        skills_dir.mkdir(parents=True)
        skill_dir = self._make_skill(skills_dir, "spec-plan")
        manifest = json.loads((skill_dir / "manifest.json").read_text())
        manifest.update(
            {
                "version": 2,
                "delivery": "bundled",
                "targets": ["claude", "codex"],
                "visibility": "internal",
                "invocation": "explicit",
            }
        )
        (skill_dir / "manifest.json").write_text(json.dumps(manifest))
        (skill_dir / "SKILL.md").write_text(
            "## Required phase resources\n\nRead `steps/01.md` completely, then execute it.\n"
        )

        with (
            patch("installer.steps.claude_files.Path.home", return_value=tmp_path),
            patch("installer.steps.claude_files.get_claude_config_dir", return_value=tmp_path / ".claude"),
        ):
            ClaudeFilesStep()._build_skill_md_files(self._make_ctx(tmp_path), MagicMock())

        artifact = (skill_dir / "SKILL.md").read_text()
        assert "## Required phase resources" not in artifact
        assert "Read `steps/" not in artifact
        assert "## Step 1\n\nContent." in artifact

    def test_codex_only_target_removes_stale_claude_skill_md(self, tmp_path):
        from unittest.mock import MagicMock, patch

        from installer.steps.claude_files import ClaudeFilesStep

        skills_dir = tmp_path / ".claude" / "skills"
        skills_dir.mkdir(parents=True)
        skill_dir = self._make_skill(skills_dir, "codex-only")
        manifest = json.loads((skill_dir / "manifest.json").read_text())
        manifest.update(
            {
                "version": 2,
                "delivery": "bundled",
                "targets": ["codex"],
                "visibility": "public",
                "invocation": "implicit",
            }
        )
        (skill_dir / "manifest.json").write_text(json.dumps(manifest))
        (skill_dir / "SKILL.md").write_text("stale")
        (skill_dir / "hashes.json").write_text("{}")

        with (
            patch("installer.steps.claude_files.Path.home", return_value=tmp_path),
            patch("installer.steps.claude_files.get_claude_config_dir", return_value=tmp_path / ".claude"),
        ):
            ClaudeFilesStep()._build_skill_md_files(self._make_ctx(tmp_path), MagicMock())

        assert not (skill_dir / "SKILL.md").exists()
        assert not (skill_dir / "hashes.json").exists()

    def test_preserves_unowned_decomposed_claude_skill(self, tmp_path):
        from unittest.mock import MagicMock, patch

        from installer.context import InstallContext
        from installer.steps.claude_files import ClaudeFilesStep

        skills_dir = tmp_path / ".claude" / "skills"
        skills_dir.mkdir(parents=True)
        skill_dir = self._make_skill(skills_dir, "user-skill")
        manifest = json.loads((skill_dir / "manifest.json").read_text())
        manifest.update(
            {
                "version": 2,
                "delivery": "progressive",
                "targets": ["codex"],
                "visibility": "public",
                "invocation": "explicit",
            }
        )
        (skill_dir / "manifest.json").write_text(json.dumps(manifest))
        (skill_dir / "SKILL.md").write_text("user-owned skill\n")
        (skill_dir / "hashes.json").write_text('{"user": true}\n')
        ctx = InstallContext(project_dir=tmp_path)

        with (
            patch("installer.steps.claude_files.Path.home", return_value=tmp_path),
            patch("installer.steps.claude_files.get_claude_config_dir", return_value=tmp_path / ".claude"),
        ):
            ClaudeFilesStep()._build_skill_md_files(ctx, MagicMock())

        assert (skill_dir / "SKILL.md").read_text() == "user-owned skill\n"
        assert (skill_dir / "hashes.json").read_text() == '{"user": true}\n'

    def test_skips_skills_without_manifest(self, tmp_path):
        """Skills without manifest.json (legacy monolithic) are skipped."""
        from unittest.mock import MagicMock, patch

        from installer.steps.claude_files import ClaudeFilesStep

        skills_dir = tmp_path / ".claude" / "skills"
        skills_dir.mkdir(parents=True)
        new_skill = self._make_skill(skills_dir, "new-skill")
        # Legacy monolithic (no manifest.json) — pre-built SKILL.md is left alone
        legacy = skills_dir / "legacy"
        legacy.mkdir()
        (legacy / "SKILL.md").write_text("# Legacy")

        step = ClaudeFilesStep()
        ui = MagicMock()

        with (
            patch("installer.steps.claude_files.Path.home", return_value=tmp_path),
            patch(
                "installer.steps.claude_files.get_claude_config_dir",
                return_value=tmp_path / ".claude",
            ),
        ):
            step._build_skill_md_files(self._make_ctx(tmp_path), ui)

        assert (new_skill / "SKILL.md").is_file()
        assert (legacy / "SKILL.md").read_text() == "# Legacy"

    def test_reports_failures_as_visible_errors(self, tmp_path):
        """A persistent BuildError surfaces via ui.error AND raises to abort the install."""
        from unittest.mock import MagicMock, patch

        import pytest

        from installer.steps.claude_files import ClaudeFilesStep

        skills_dir = tmp_path / ".claude" / "skills"
        skills_dir.mkdir(parents=True)
        skill_dir = self._make_skill(skills_dir, "broken")
        # Corrupt the manifest so build fails and recovery cannot help
        (skill_dir / "manifest.json").write_text("{not valid json")

        step = ClaudeFilesStep()
        ui = MagicMock()

        with (
            patch("installer.steps.claude_files.Path.home", return_value=tmp_path),
            patch(
                "installer.steps.claude_files.get_claude_config_dir",
                return_value=tmp_path / ".claude",
            ),
        ):
            with pytest.raises(RuntimeError, match="skill-build failed"):
                step._build_skill_md_files(self._make_ctx(tmp_path), ui)

        ui.error.assert_called_once()
        assert "broken" in ui.error.call_args.args[0]
        assert "FAILED" in ui.error.call_args.args[0]

    def test_missing_fragment_triggers_lazy_recovery_and_retry(self, tmp_path):
        """Missing fragment causes BuildError → recovery downloads it → retry succeeds."""
        from unittest.mock import MagicMock, patch

        from installer.steps.claude_files import ClaudeFilesStep

        skills_dir = tmp_path / ".claude" / "skills"
        skills_dir.mkdir(parents=True)
        skill_dir = self._make_skill(skills_dir, "prd")
        missing = skill_dir / "steps" / "01.md"
        missing.unlink()
        assert not missing.exists()

        step = ClaudeFilesStep()
        ui = MagicMock()
        ctx = self._make_ctx(tmp_path)

        def fake_download(_repo_path: str, dest: Path, _config) -> bool:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text("## Step 1\n\nRecovered.")
            return True

        with (
            patch("installer.steps.claude_files.Path.home", return_value=tmp_path),
            patch(
                "installer.steps.claude_files.get_claude_config_dir",
                return_value=tmp_path / ".claude",
            ),
            patch("installer.steps.claude_files.download_file", side_effect=fake_download) as mock_dl,
        ):
            step._build_skill_md_files(ctx, ui)

        assert missing.exists()
        assert (skill_dir / "SKILL.md").is_file()
        assert "Recovered." in (skill_dir / "SKILL.md").read_text()
        mock_dl.assert_called_once()
        repo_path_arg = mock_dl.call_args.args[0]
        assert repo_path_arg == "pilot/skills/prd/steps/01.md"
        assert str(missing) in ctx.config.get("installed_files", [])

    def test_urllib_fallback_recovers_when_download_file_fails(self, tmp_path):
        """If download_file returns False, the single-threaded urllib fallback takes over."""
        from unittest.mock import MagicMock, patch

        from installer.steps.claude_files import ClaudeFilesStep

        skills_dir = tmp_path / ".claude" / "skills"
        skills_dir.mkdir(parents=True)
        skill_dir = self._make_skill(skills_dir, "prd")
        missing = skill_dir / "steps" / "01.md"
        missing.unlink()

        step = ClaudeFilesStep()
        ui = MagicMock()
        ctx = self._make_ctx(tmp_path)

        response_mock = MagicMock()
        response_mock.__enter__ = MagicMock(return_value=response_mock)
        response_mock.__exit__ = MagicMock(return_value=False)
        response_mock.status = 200
        response_mock.read.return_value = b"## Step 1\n\nFallback content."

        with (
            patch("installer.steps.claude_files.Path.home", return_value=tmp_path),
            patch(
                "installer.steps.claude_files.get_claude_config_dir",
                return_value=tmp_path / ".claude",
            ),
            patch("installer.steps.claude_files.download_file", return_value=False) as mock_dl,
            patch("urllib.request.urlopen", return_value=response_mock) as mock_urlopen,
        ):
            step._build_skill_md_files(ctx, ui)

        mock_dl.assert_called_once()
        mock_urlopen.assert_called_once()
        called_request = mock_urlopen.call_args.args[0]
        assert "pilot/skills/prd/steps/01.md" in called_request.full_url
        assert missing.is_file()
        assert missing.read_bytes() == b"## Step 1\n\nFallback content."
        assert (skill_dir / "SKILL.md").is_file()
        assert str(missing) in ctx.config.get("installed_files", [])

    def test_urllib_fallback_retries_transient_5xx(self, tmp_path):
        """A transient 502 on the urllib fallback retries and recovers (issue #158).

        Regression: a single CDN 502 on a fragment download used to abort the
        whole install with no retry, even though re-running succeeded.
        """
        import urllib.error
        from unittest.mock import MagicMock, patch

        from installer.steps.claude_files import ClaudeFilesStep

        skills_dir = tmp_path / ".claude" / "skills"
        skills_dir.mkdir(parents=True)
        skill_dir = self._make_skill(skills_dir, "prd")
        missing = skill_dir / "steps" / "01.md"
        missing.unlink()

        step = ClaudeFilesStep()
        ui = MagicMock()
        ctx = self._make_ctx(tmp_path)

        ok_response = MagicMock()
        ok_response.__enter__ = MagicMock(return_value=ok_response)
        ok_response.__exit__ = MagicMock(return_value=False)
        ok_response.status = 200
        ok_response.read.return_value = b"## Step 1\n\nRecovered after 502."

        # First attempt: transient CDN 502. Second attempt: succeeds.
        urlopen_results = [
            urllib.error.HTTPError("https://x/raw", 502, "Bad Gateway or Proxy Error", {}, None),  # type: ignore[arg-type]
            ok_response,
        ]

        with (
            patch("installer.steps.claude_files.Path.home", return_value=tmp_path),
            patch(
                "installer.steps.claude_files.get_claude_config_dir",
                return_value=tmp_path / ".claude",
            ),
            patch("installer.steps.claude_files.download_file", return_value=False),
            patch("installer.steps.claude_files.time.sleep"),
            patch("urllib.request.urlopen", side_effect=urlopen_results) as mock_urlopen,
        ):
            step._build_skill_md_files(ctx, ui)

        assert mock_urlopen.call_count == 2  # retried after the 502 instead of aborting
        assert missing.is_file()
        assert missing.read_bytes() == b"## Step 1\n\nRecovered after 502."
        assert (skill_dir / "SKILL.md").is_file()
        assert str(missing) in ctx.config.get("installed_files", [])

    def test_urllib_fallback_fails_fast_on_4xx(self, tmp_path):
        """A 404 means the file is genuinely missing — fail fast, never retry."""
        import urllib.error
        from unittest.mock import MagicMock, patch

        import pytest

        from installer.steps.claude_files import ClaudeFilesStep

        skills_dir = tmp_path / ".claude" / "skills"
        skills_dir.mkdir(parents=True)
        skill_dir = self._make_skill(skills_dir, "prd")
        (skill_dir / "steps" / "01.md").unlink()

        step = ClaudeFilesStep()
        ui = MagicMock()

        not_found = urllib.error.HTTPError("https://x/raw", 404, "Not Found", {}, None)  # type: ignore[arg-type]

        with (
            patch("installer.steps.claude_files.Path.home", return_value=tmp_path),
            patch(
                "installer.steps.claude_files.get_claude_config_dir",
                return_value=tmp_path / ".claude",
            ),
            patch("installer.steps.claude_files.download_file", return_value=False),
            patch("installer.steps.claude_files.time.sleep") as mock_sleep,
            patch("urllib.request.urlopen", side_effect=not_found) as mock_urlopen,
        ):
            with pytest.raises(RuntimeError):
                step._build_skill_md_files(self._make_ctx(tmp_path), ui)

        assert mock_urlopen.call_count == 1  # 4xx is not retried
        mock_sleep.assert_not_called()

    def test_diagnostics_emitted_when_skill_build_fails(self, tmp_path):
        """After recovery cannot fix the skill, diagnostics print on-disk state and URLs."""
        from unittest.mock import MagicMock, patch

        import pytest

        from installer.steps.claude_files import ClaudeFilesStep

        skills_dir = tmp_path / ".claude" / "skills"
        skills_dir.mkdir(parents=True)
        skill_dir = self._make_skill(skills_dir, "prd")
        # Drop a fragment AND make recovery fail, so BuildError persists
        (skill_dir / "steps" / "01.md").unlink()

        step = ClaudeFilesStep()
        ui = MagicMock()

        with (
            patch("installer.steps.claude_files.Path.home", return_value=tmp_path),
            patch(
                "installer.steps.claude_files.get_claude_config_dir",
                return_value=tmp_path / ".claude",
            ),
            patch("installer.steps.claude_files.download_file", return_value=False),
            patch.object(ClaudeFilesStep, "_direct_download_with_diagnostics", return_value=False),
        ):
            with pytest.raises(RuntimeError):
                step._build_skill_md_files(self._make_ctx(tmp_path), ui)

        printed = "\n".join(call.args[0] for call in ui.print.call_args_list if call.args)
        assert str(skill_dir) in printed
        assert "manifest.json" in printed
        assert "steps/01.md" in printed
        assert "pilot/skills/prd/steps/01.md" in printed

    def test_no_skills_dir_returns_silently(self, tmp_path):
        from unittest.mock import MagicMock, patch

        from installer.steps.claude_files import ClaudeFilesStep

        # No skills dir at all
        step = ClaudeFilesStep()
        ui = MagicMock()

        with (
            patch("installer.steps.claude_files.Path.home", return_value=tmp_path),
            patch(
                "installer.steps.claude_files.get_claude_config_dir",
                return_value=tmp_path / ".claude",
            ),
        ):
            step._build_skill_md_files(self._make_ctx(tmp_path), ui)

        ui.warning.assert_not_called()
        ui.error.assert_not_called()


class TestMergePilotHooks:
    """Tests for the Pilot-owned-entry-aware hooks merge.

    See docs/plans/2026-05-12-drop-plugin-system-native-install.md Task 1.
    """

    @staticmethod
    def _entry(matcher, command):
        return {"matcher": matcher, "hooks": [{"type": "command", "command": command}]}

    def test_first_install_no_baseline_no_current(self):
        """No baseline, empty current → incoming installed as-is."""
        from installer.steps.settings_merge import merge_pilot_hooks

        incoming = {"PostToolUse": [self._entry("Write|Edit", "py /a/file_checker.py")]}

        result = merge_pilot_hooks({}, incoming, None)

        assert result == incoming

    def test_first_install_user_added_event_preserved(self):
        """User defined a hook under a key Pilot doesn't ship → preserved alongside Pilot's."""
        from installer.steps.settings_merge import merge_pilot_hooks

        current = {"UserPromptSubmit": [self._entry("", "echo user")]}
        incoming = {"PostToolUse": [self._entry("Write", "py /a/file_checker.py")]}

        result = merge_pilot_hooks(current, incoming, None)

        assert result["UserPromptSubmit"] == [self._entry("", "echo user")]
        assert result["PostToolUse"] == [self._entry("Write", "py /a/file_checker.py")]

    def test_upgrade_baseline_matches_current_incoming_replaces(self):
        """Baseline == current Pilot entries → upgrade to incoming."""
        from installer.steps.settings_merge import merge_pilot_hooks

        baseline = {"PostToolUse": [self._entry("Write", "py /old/file_checker.py")]}
        current = {"PostToolUse": [self._entry("Write", "py /old/file_checker.py")]}
        incoming = {"PostToolUse": [self._entry("Write", "py /new/file_checker.py")]}

        result = merge_pilot_hooks(current, incoming, baseline)

        assert result["PostToolUse"] == [self._entry("Write", "py /new/file_checker.py")]

    def test_user_added_entry_under_pilot_event_preserved(self):
        """User added an entry to a Pilot event key → kept alongside Pilot's new entry."""
        from installer.steps.settings_merge import merge_pilot_hooks

        baseline = {"Stop": [self._entry("", "py /old/stop.py")]}
        current = {
            "Stop": [
                self._entry("", "py /old/stop.py"),
                self._entry("", "echo my-user-stop"),
            ]
        }
        incoming = {"Stop": [self._entry("", "py /new/stop.py")]}

        result = merge_pilot_hooks(current, incoming, baseline)

        # User's entry should remain; Pilot's entry should be the new one
        commands = [h["command"] for entry in result["Stop"] for h in entry["hooks"]]
        assert "echo my-user-stop" in commands
        assert "py /new/stop.py" in commands
        assert "py /old/stop.py" not in commands

    def test_signature_collision_raises_value_error(self):
        """Incoming with two entries sharing (matcher, sorted-commands) is a programmer error."""
        import pytest

        from installer.steps.settings_merge import merge_pilot_hooks

        incoming = {
            "PostToolUse": [
                self._entry("Write", "py /a/file_checker.py"),
                self._entry("Write", "py /a/file_checker.py"),  # exact duplicate
            ]
        }
        with pytest.raises(ValueError):
            merge_pilot_hooks({}, incoming, None)

    def test_pilot_event_removed_when_user_unchanged(self):
        """Pilot drops an event entirely; user hadn't touched it → dropped."""
        from installer.steps.settings_merge import merge_pilot_hooks

        baseline = {"PreCompact": [self._entry("", "py /old/pre_compact.py")]}
        current = {"PreCompact": [self._entry("", "py /old/pre_compact.py")]}
        incoming = {}

        result = merge_pilot_hooks(current, incoming, baseline)

        assert "PreCompact" not in result


class TestAgentsCategoryAndSkips:
    """Task 3: agents go to ~/.claude/agents/; plugin.json + .lsp.json skipped."""

    def test_categorize_agents_routes_to_agents_category(self):
        from installer.steps.claude_files import _categorize_file

        assert _categorize_file("pilot/agents/spec-review.md") == "agents"
        assert _categorize_file("pilot/agents/changes-review-codex.md") == "agents"

    def test_skip_plugin_json(self):
        from installer.steps.claude_files import _should_skip_file

        assert _should_skip_file("pilot/plugin.json") is True

    def test_skip_lsp_json(self):
        from installer.steps.claude_files import _should_skip_file

        assert _should_skip_file("pilot/.lsp.json") is True

    def test_get_dest_path_agents_goes_to_claude_agents_dir(self, tmp_path):
        from unittest.mock import MagicMock, patch

        from installer.steps.claude_files import ClaudeFilesStep

        step = ClaudeFilesStep()
        claude_dir = tmp_path / ".claude"
        with patch("installer.steps.claude_files.get_claude_config_dir", return_value=claude_dir):
            ctx = MagicMock()
            dest = step._get_dest_path("agents", "pilot/agents/spec-review.md", ctx)
        assert dest == claude_dir / "agents" / "spec-review.md"

    def test_gate_protocol_runbook_ships_to_the_agents_dir(self, tmp_path):
        """Every approval gate reads this file at runtime via ~/.claude/agents/.

        A shared runbook that does not get installed makes each referencing gate
        point at nothing, which is worse than the inline copies it replaced.
        """
        from pathlib import Path
        from unittest.mock import MagicMock, patch

        from installer.steps.claude_files import ClaudeFilesStep, _categorize_file

        repo_root = Path(__file__).resolve().parents[4]
        source = repo_root / "pilot" / "agents" / "agent-gate-protocol.md"
        assert source.is_file(), "the runbook the gates reference must exist in the repo"

        assert _categorize_file("pilot/agents/agent-gate-protocol.md") == "agents"

        step = ClaudeFilesStep()
        claude_dir = tmp_path / ".claude"
        with patch("installer.steps.claude_files.get_claude_config_dir", return_value=claude_dir):
            dest = step._get_dest_path("agents", "pilot/agents/agent-gate-protocol.md", MagicMock())
        assert dest == claude_dir / "agents" / "agent-gate-protocol.md"

    def test_categorize_hooks_routes_to_hooks_category(self):
        """pilot/hooks/*.py and the hooks.json config land in ~/.pilot/hooks/."""
        from installer.steps.claude_files import _categorize_file

        assert _categorize_file("pilot/hooks/spec_mode_guard.py") == "hooks"
        assert _categorize_file("pilot/hooks/_lib/console_settings.py") == "hooks"
        assert _categorize_file("pilot/hooks/hooks.json") == "hooks"

    def test_categorize_pilot_runtime_assets_route_to_pilot_home(self):
        """pilot/scripts/, pilot/ui/, and root-level configs land in ~/.pilot/."""
        from installer.steps.claude_files import _categorize_file

        assert _categorize_file("pilot/scripts/worker-service.cjs") == "pilot_home"
        assert _categorize_file("pilot/ui/viewer.html") == "pilot_home"
        assert _categorize_file("pilot/.mcp.json") == "pilot_home"
        assert _categorize_file("pilot/claude.json") == "pilot_home"

    def test_get_dest_path_hooks_lands_under_pilot_hooks(self, tmp_path):
        from unittest.mock import MagicMock, patch

        from installer.steps.claude_files import ClaudeFilesStep

        step = ClaudeFilesStep()
        with patch("installer.steps.claude_files.Path.home", return_value=tmp_path):
            ctx = MagicMock()
            dest = step._get_dest_path("hooks", "pilot/hooks/spec_mode_guard.py", ctx)
        assert dest == tmp_path / ".pilot" / "hooks" / "spec_mode_guard.py"

    def test_get_dest_path_pilot_home_lands_under_dotpilot(self, tmp_path):
        from unittest.mock import MagicMock, patch

        from installer.steps.claude_files import ClaudeFilesStep

        step = ClaudeFilesStep()
        pilot_home = tmp_path / ".pilot"
        with patch("installer.steps.claude_files.Path.home", return_value=tmp_path):
            ctx = MagicMock()
            scripts_dest = step._get_dest_path("pilot_home", "pilot/scripts/worker-service.cjs", ctx)
            mcp_dest = step._get_dest_path("pilot_home", "pilot/.mcp.json", ctx)
        assert scripts_dest == pilot_home / "scripts" / "worker-service.cjs"
        assert mcp_dest == pilot_home / ".mcp.json"

    def test_cleanup_preserves_user_placed_hook_scripts(self, tmp_path):
        """User-placed scripts in ~/.claude/hooks/ must survive cleanup.

        The manifest tracks Pilot-installed entries; anything else is the
        user's. Wiping the dir wholesale would clobber files the user dropped
        in there (e.g., for their own settings.json hook registrations).
        """
        from unittest.mock import MagicMock, patch

        from installer.steps.claude_files import ClaudeFilesStep

        claude_dir = tmp_path / ".claude"
        hooks_dir = claude_dir / "hooks"
        hooks_dir.mkdir(parents=True)

        # User's own hook file (not in manifest)
        user_hook = hooks_dir / "my-team-check.sh"
        user_hook.write_text("#!/bin/sh\necho user hook")
        # Pilot-managed hook file (in manifest)
        pilot_hook = hooks_dir / "pilot_owned.py"
        pilot_hook.write_text("# pilot")

        # Manifest records only the pilot-owned file.
        manifest_path = claude_dir / ".pilot-manifest.json"
        manifest_path.write_text(json.dumps({"files": ["hooks/pilot_owned.py"]}))

        ctx = MagicMock()
        ctx.project_dir = tmp_path / "project"
        config = MagicMock()
        config.local_mode = False
        config.local_repo_dir = None

        step = ClaudeFilesStep()
        with (
            patch("installer.steps.claude_files.get_claude_config_dir", return_value=claude_dir),
            patch("installer.steps.claude_files.Path.home", return_value=tmp_path),
        ):
            step._cleanup_old_directories(ctx, config, None)

        # Pilot-owned file removed (it's in the manifest, not in the new install).
        assert not pilot_hook.exists()
        # User's file untouched.
        assert user_hook.exists()
        assert user_hook.read_text() == "#!/bin/sh\necho user hook"

    def test_cleanup_removes_legacy_claude_pilot_dir(self, tmp_path):
        """The ~/.claude/pilot/ directory is wiped entirely — its assets have
        all moved to ~/.claude/hooks/, ~/.claude/agents/, or ~/.pilot/.

        ⛔ Must patch BOTH `get_claude_config_dir` AND `Path.home` — the
        production cleanup also wipes ~/.pilot/scripts/ and ~/.pilot/ui/ via
        `Path.home()`. Without the Path.home patch, this test destroys the
        developer's real ~/.pilot/ on every run.
        """
        from unittest.mock import MagicMock, patch

        from installer.steps.claude_files import ClaudeFilesStep

        claude_dir = tmp_path / ".claude"
        legacy_plugin = claude_dir / "pilot"
        (legacy_plugin / "hooks").mkdir(parents=True)
        (legacy_plugin / "hooks" / "hooks.json").write_text("{}")
        (legacy_plugin / "scripts").mkdir()
        (legacy_plugin / "scripts" / "worker.cjs").write_text("// worker")

        ctx = MagicMock()
        ctx.project_dir = tmp_path / "project"
        config = MagicMock()
        config.local_mode = False
        config.local_repo_dir = None

        step = ClaudeFilesStep()
        with (
            patch("installer.steps.claude_files.get_claude_config_dir", return_value=claude_dir),
            patch("installer.steps.claude_files.Path.home", return_value=tmp_path),
        ):
            step._cleanup_old_directories(ctx, config, None)

        assert not legacy_plugin.exists()


class TestMergePilotMcpServers:
    """Value-aware MCP server merge — preserves user-added AND user-modified servers."""

    def test_first_install_no_collision_installs_all(self):
        from installer.steps.settings_merge import merge_pilot_mcp_servers

        current = {}
        incoming = {"context7": {"command": "npx", "args": ["-y", "context7"]}}
        result, warnings = merge_pilot_mcp_servers(current, incoming, None)

        assert result == incoming
        assert warnings == []

    def test_first_install_name_collision_preserves_user(self):
        from installer.steps.settings_merge import merge_pilot_mcp_servers

        current = {"context7": {"command": "user-custom"}}
        incoming = {"context7": {"command": "npx"}}
        result, warnings = merge_pilot_mcp_servers(current, incoming, None)

        assert result["context7"]["command"] == "user-custom"
        assert any("context7" in w for w in warnings)

    def test_upgrade_user_untouched_pilot_server_updated(self):
        from installer.steps.settings_merge import merge_pilot_mcp_servers

        baseline = {"context7": {"command": "npx-old"}}
        current = {"context7": {"command": "npx-old"}}
        incoming = {"context7": {"command": "npx-new"}}
        result, warnings = merge_pilot_mcp_servers(current, incoming, baseline)

        assert result["context7"]["command"] == "npx-new"
        assert warnings == []

    def test_upgrade_user_modified_pilot_server_preserved_with_warning(self):
        """Codex finding #2 — value-aware preservation."""
        from installer.steps.settings_merge import merge_pilot_mcp_servers

        baseline = {"context7": {"command": "npx", "args": ["-y"]}}
        current = {"context7": {"command": "node", "args": ["-y"]}}  # user changed command
        incoming = {"context7": {"command": "npx-new", "args": ["-y"]}}
        result, warnings = merge_pilot_mcp_servers(current, incoming, baseline)

        assert result["context7"]["command"] == "node"
        assert any("context7" in w for w in warnings)

    def test_upgrade_pilot_ships_server_user_already_added(self):
        """Pilot newly ships a server with a name the user already created."""
        from installer.steps.settings_merge import merge_pilot_mcp_servers

        baseline = {"context7": {"command": "npx"}}  # only original Pilot server
        current = {
            "context7": {"command": "npx"},
            "super-tool": {"command": "user-added"},  # not in baseline
        }
        incoming = {
            "context7": {"command": "npx"},
            "super-tool": {"command": "pilot-version"},  # Pilot now adds this
        }
        result, warnings = merge_pilot_mcp_servers(current, incoming, baseline)

        assert result["super-tool"]["command"] == "user-added"
        assert any("super-tool" in w for w in warnings)

    def test_deprecated_pilot_server_removed_when_user_untouched(self):
        from installer.steps.settings_merge import merge_pilot_mcp_servers

        baseline = {"old-server": {"command": "npx-old"}, "context7": {"command": "npx"}}
        current = {"old-server": {"command": "npx-old"}, "context7": {"command": "npx"}}
        incoming = {"context7": {"command": "npx"}}  # old-server deprecated
        result, _ = merge_pilot_mcp_servers(current, incoming, baseline)

        assert "old-server" not in result
        assert "context7" in result

    def test_deprecated_pilot_server_preserved_when_user_customized(self):
        from installer.steps.settings_merge import merge_pilot_mcp_servers

        baseline = {"old-server": {"command": "npx-old"}}
        current = {"old-server": {"command": "user-custom"}}  # user modified
        incoming = {}  # Pilot deprecates
        result, warnings = merge_pilot_mcp_servers(current, incoming, baseline)

        assert result["old-server"]["command"] == "user-custom"
        assert any("old-server" in w for w in warnings)

    def test_user_added_non_pilot_server_always_preserved(self):
        from installer.steps.settings_merge import merge_pilot_mcp_servers

        baseline = {"context7": {"command": "npx"}}
        current = {
            "context7": {"command": "npx"},
            "my-server": {"command": "user-thing"},
        }
        incoming = {"context7": {"command": "npx"}}
        result, _ = merge_pilot_mcp_servers(current, incoming, baseline)

        assert result["my-server"]["command"] == "user-thing"


class TestMergeMcpServersIntoClaudeJson:
    """Integration tests for ClaudeFilesStep._merge_mcp_servers_into_claude_json."""

    def test_installs_pilot_servers_into_claude_json(self, tmp_path):
        from unittest.mock import patch

        from installer.steps.claude_files import ClaudeFilesStep

        claude_dir = tmp_path / ".claude"
        pilot_home = tmp_path / ".pilot"
        pilot_home.mkdir(parents=True)
        (pilot_home / ".mcp.json").write_text(json.dumps({"mcpServers": {"context7": {"command": "npx"}}}, indent=2))
        home = tmp_path
        # Pre-existing ~/.claude.json with non-MCP keys
        (home / ".claude.json").write_text(json.dumps({"oauthAccount": "x"}, indent=2))

        step = ClaudeFilesStep()
        with (
            patch("installer.steps.claude_files.get_claude_config_dir", return_value=claude_dir),
            patch("installer.steps.claude_files.Path.home", return_value=home),
        ):
            step._merge_mcp_servers_into_claude_json(ui=None)

        merged = json.loads((home / ".claude.json").read_text())
        assert merged["mcpServers"]["context7"]["command"] == "npx"
        assert merged["oauthAccount"] == "x"  # preserved
        # Dedicated MCP baseline (NOT .pilot-claude-baseline.json — that one is
        # owned by _merge_app_config and would clobber us on subsequent installs).
        baseline = json.loads((claude_dir / ".pilot-mcp-baseline.json").read_text())
        assert baseline["context7"]["command"] == "npx"

    def test_preserves_user_modified_pilot_server(self, tmp_path):
        """Second install: user modified context7; merge preserves it and warns."""
        from unittest.mock import MagicMock, patch

        from installer.steps.claude_files import ClaudeFilesStep

        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir(parents=True)
        pilot_home = tmp_path / ".pilot"
        pilot_home.mkdir(parents=True)
        (pilot_home / ".mcp.json").write_text(
            json.dumps({"mcpServers": {"context7": {"command": "npx-new"}}}, indent=2)
        )
        home = tmp_path
        # ~/.claude.json: user modified context7
        (home / ".claude.json").write_text(
            json.dumps({"mcpServers": {"context7": {"command": "node-custom"}}}, indent=2)
        )
        # baseline (from prior install) records what Pilot installed
        (claude_dir / ".pilot-mcp-baseline.json").write_text(json.dumps({"context7": {"command": "npx-old"}}, indent=2))

        step = ClaudeFilesStep()
        ui = MagicMock()
        with (
            patch("installer.steps.claude_files.get_claude_config_dir", return_value=claude_dir),
            patch("installer.steps.claude_files.Path.home", return_value=home),
        ):
            step._merge_mcp_servers_into_claude_json(ui=ui)

        merged = json.loads((home / ".claude.json").read_text())
        assert merged["mcpServers"]["context7"]["command"] == "node-custom"
        # UI got a warning
        ui.warning.assert_called()

    def test_servers_land_in_custom_config_dir(self, tmp_path, monkeypatch):
        """With CLAUDE_CONFIG_DIR set, MCP servers must NOT touch ~/.claude.json.

        Drives the real resolver via the env var rather than patching it, so this
        exercises the actual app-config rule. conftest's autouse fixture unsets
        the variable first; setting it here overrides that for this test only.
        """
        from unittest.mock import patch

        from installer.steps.claude_files import ClaudeFilesStep

        home = tmp_path
        custom_dir = tmp_path / ".claude_work"
        custom_dir.mkdir()
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(custom_dir))

        pilot_home = tmp_path / ".pilot"
        pilot_home.mkdir(parents=True)
        (pilot_home / ".mcp.json").write_text(json.dumps({"mcpServers": {"context7": {"command": "npx"}}}, indent=2))
        # Personal app config that must remain byte-identical.
        personal = home / ".claude.json"
        personal.write_text(json.dumps({"oauthAccount": "personal"}, indent=2))
        before = personal.read_text()

        step = ClaudeFilesStep()
        with patch("installer.steps.claude_files.Path.home", return_value=home):
            step._merge_mcp_servers_into_claude_json(ui=None)

        assert personal.read_text() == before, "personal ~/.claude.json was modified"
        merged = json.loads((custom_dir / ".claude.json").read_text())
        assert merged["mcpServers"]["context7"]["command"] == "npx"


class TestMergeHooksIntoSettings:
    """Integration tests for ClaudeFilesStep._merge_hooks_into_settings."""

    def test_writes_hooks_into_settings_with_shipped_paths(self, tmp_path):
        """After merge, ~/.claude/settings.json contains the absolute $HOME paths
        from the shipped hooks.json verbatim, and a dedicated baseline file exists.
        Bash expands $HOME natively when Claude Code shells out — no install-time
        path substitution is needed.
        """
        from unittest.mock import patch

        from installer.steps.claude_files import ClaudeFilesStep

        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir(parents=True)
        pilot_home = tmp_path / ".pilot"
        hooks_dir = pilot_home / "hooks"
        hooks_dir.mkdir(parents=True)
        hooks_json = {
            "hooks": {
                "PostToolUse": [
                    {
                        "matcher": "Write|Edit",
                        "hooks": [
                            {
                                "type": "command",
                                "command": 'uv run python "$HOME/.pilot/hooks/file_checker.py"',
                            }
                        ],
                    }
                ]
            }
        }
        (hooks_dir / "hooks.json").write_text(json.dumps(hooks_json, indent=2) + "\n")
        (claude_dir / "settings.json").write_text(json.dumps({"model": "sonnet"}, indent=2) + "\n")

        step = ClaudeFilesStep()
        with (
            patch("installer.steps.claude_files.get_claude_config_dir", return_value=claude_dir),
            patch("installer.steps.claude_files.Path.home", return_value=tmp_path),
        ):
            step._merge_hooks_into_settings()

        merged = json.loads((claude_dir / "settings.json").read_text())
        assert "hooks" in merged
        assert merged["model"] == "sonnet"
        cmd = merged["hooks"]["PostToolUse"][0]["hooks"][0]["command"]
        assert cmd == 'uv run python "$HOME/.pilot/hooks/file_checker.py"'

        baseline_path = claude_dir / ".pilot-hooks-baseline.json"
        assert baseline_path.exists()
        baseline = json.loads(baseline_path.read_text())
        assert "PostToolUse" in baseline
        settings_baseline = claude_dir / ".pilot-settings-baseline.json"
        if settings_baseline.exists():
            assert "hooks" not in json.loads(settings_baseline.read_text())

    def test_preserves_user_added_hook_on_re_install(self, tmp_path):
        """User added a Stop hook → preserved alongside Pilot's incoming hooks."""
        from unittest.mock import patch

        from installer.steps.claude_files import ClaudeFilesStep

        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir(parents=True)
        pilot_home = tmp_path / ".pilot"
        hooks_dir = pilot_home / "hooks"
        hooks_dir.mkdir(parents=True)

        # Incoming hooks.json from the new install
        hooks_json = {
            "hooks": {"Stop": [{"matcher": "", "hooks": [{"type": "command", "command": "py NEW_PILOT_STOP"}]}]}
        }
        (hooks_dir / "hooks.json").write_text(json.dumps(hooks_json, indent=2) + "\n")

        # Previous Pilot baseline (what was installed before)
        (claude_dir / ".pilot-hooks-baseline.json").write_text(
            json.dumps(
                {"Stop": [{"matcher": "", "hooks": [{"type": "command", "command": "py OLD_PILOT_STOP"}]}]},
                indent=2,
            )
            + "\n"
        )
        # Current settings.json has Pilot's old Stop + a user-added Stop entry
        (claude_dir / "settings.json").write_text(
            json.dumps(
                {
                    "model": "sonnet",
                    "hooks": {
                        "Stop": [
                            {"matcher": "", "hooks": [{"type": "command", "command": "py OLD_PILOT_STOP"}]},
                            {"matcher": "", "hooks": [{"type": "command", "command": "echo MY_USER_STOP"}]},
                        ]
                    },
                },
                indent=2,
            )
            + "\n"
        )

        step = ClaudeFilesStep()
        with (
            patch("installer.steps.claude_files.get_claude_config_dir", return_value=claude_dir),
            patch("installer.steps.claude_files.Path.home", return_value=tmp_path),
        ):
            step._merge_hooks_into_settings()

        merged = json.loads((claude_dir / "settings.json").read_text())
        commands = [h["command"] for entry in merged["hooks"]["Stop"] for h in entry["hooks"]]
        assert "echo MY_USER_STOP" in commands  # preserved
        assert "py NEW_PILOT_STOP" in commands  # installed
        assert "py OLD_PILOT_STOP" not in commands  # replaced

    def test_legacy_upgrade_without_baseline_removes_old_pilot_paths(self, tmp_path):
        """Pre-baseline Pilot installs left hook entries in settings.json with
        absolute ~/.claude/pilot/hooks/... or ${CLAUDE_PLUGIN_ROOT}/hooks/...
        commands. On upgrade with no baseline file, _merge_hooks_into_settings
        must auto-seed a synthetic baseline so those legacy entries are
        identified as Pilot-owned and REPLACED with the new $HOME/.pilot/hooks/
        entries — not preserved as duplicate user_only additions.
        """
        from unittest.mock import patch

        from installer.steps.claude_files import ClaudeFilesStep

        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir(parents=True)
        pilot_home = tmp_path / ".pilot"
        hooks_dir = pilot_home / "hooks"
        hooks_dir.mkdir(parents=True)

        new_command = 'uv run --no-project --python python3 python "$HOME/.pilot/hooks/spec_mode_guard.py"'
        hooks_json = {"hooks": {"UserPromptSubmit": [{"hooks": [{"type": "command", "command": new_command}]}]}}
        (hooks_dir / "hooks.json").write_text(json.dumps(hooks_json, indent=2) + "\n")

        # User's settings.json has two legacy entries (no baseline file on disk).
        legacy_abs = 'uv run --no-project python "/Users/x/.claude/pilot/hooks/spec_mode_guard.py"'
        legacy_template = 'uv run --no-project python "${CLAUDE_PLUGIN_ROOT}/hooks/spec_mode_guard.py"'
        user_command = "echo MY_OWN_UPS_HOOK"
        (claude_dir / "settings.json").write_text(
            json.dumps(
                {
                    "hooks": {
                        "UserPromptSubmit": [
                            {"hooks": [{"type": "command", "command": legacy_abs}]},
                            {"hooks": [{"type": "command", "command": legacy_template}]},
                            {"hooks": [{"type": "command", "command": user_command}]},
                        ]
                    },
                },
                indent=2,
            )
            + "\n"
        )

        step = ClaudeFilesStep()
        with (
            patch("installer.steps.claude_files.get_claude_config_dir", return_value=claude_dir),
            patch("installer.steps.claude_files.Path.home", return_value=tmp_path),
        ):
            step._merge_hooks_into_settings()

        merged_commands = [
            h["command"]
            for entry in json.loads((claude_dir / "settings.json").read_text())["hooks"]["UserPromptSubmit"]
            for h in entry["hooks"]
        ]
        # Legacy entries replaced
        assert legacy_abs not in merged_commands
        assert legacy_template not in merged_commands
        # User-added entry preserved
        assert user_command in merged_commands
        # New entry installed
        assert new_command in merged_commands


class TestShippedSettingsTemplate:
    """Model, effort, and transcript view remain the user's own choices."""

    SETTINGS_PATH = Path(__file__).parents[4] / "pilot" / "settings.json"

    def test_template_does_not_select_model_or_effort(self):
        data = json.loads(self.SETTINGS_PATH.read_text())

        assert "CLAUDE_CODE_EFFORT_LEVEL" not in data.get("env", {}), (
            "settings.json must not pin effort via env - it outranks --effort"
        )
        assert "effortLevel" not in data
        assert "model" not in data
        assert "ANTHROPIC_MODEL" not in data.get("env", {})

    def test_template_enables_flicker_free_rendering_but_preserves_explicit_opt_out(self):
        from installer.steps.settings_merge import merge_settings

        incoming = json.loads(self.SETTINGS_PATH.read_text())
        assert incoming["env"]["CLAUDE_CODE_NO_FLICKER"] == "true"
        current = {"env": {"CLAUDE_CODE_NO_FLICKER": "false"}}
        merged = merge_settings({"env": {}}, current, incoming)
        assert merged["env"]["CLAUDE_CODE_NO_FLICKER"] == "false"

    def test_template_enables_workflows_and_ide_without_disabling_native_memory(self):
        data = json.loads(self.SETTINGS_PATH.read_text())
        assert data["env"]["CLAUDE_CODE_WORKFLOWS"] == "true"
        assert data["env"]["CLAUDE_CODE_AUTO_CONNECT_IDE"] == "true"
        assert "CLAUDE_CODE_DISABLE_AUTO_MEMORY" not in data["env"]
        assert "CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING" not in data["env"]

    def test_template_restores_task_tools_gated_off_on_newer_models(self):
        """Claude Code 2.1.260 model-gates TaskCreate/Get/List/Update off on Opus
        4.8, Sonnet 5, Fable 5, Mythos 5 and newer. Without these the agent has no
        task-tracking tool at all -- TodoWrite is retired and does not come back.
        """
        data = json.loads(self.SETTINGS_PATH.read_text())
        assert data["env"]["CLAUDE_CODE_ENABLE_TODO_TOOLS"] == "true"
        assert data["env"]["CLAUDE_CODE_ENABLE_TASKS"] == "true"
        assert data["env"]["CLAUDE_CODE_TODO_REMINDER_MODE"] == "baseline"

    def test_task_tool_restore_preserves_explicit_opt_out(self):
        from installer.steps.settings_merge import merge_settings

        incoming = json.loads(self.SETTINGS_PATH.read_text())
        current = {"env": {"CLAUDE_CODE_ENABLE_TODO_TOOLS": "false"}}
        merged = merge_settings({"env": {}}, current, incoming)
        assert merged["env"]["CLAUDE_CODE_ENABLE_TODO_TOOLS"] == "false"

    @pytest.mark.parametrize("effort", ["low", "medium", "high", "xhigh", "max"])
    @pytest.mark.parametrize("has_baseline", [False, True])
    def test_effort_migration_preserves_user_choices(self, effort: str, has_baseline: bool):
        from installer.steps.settings_merge import merge_settings

        baseline = {"effortLevel": "xhigh"} if has_baseline else None
        current = {"effortLevel": effort, "model": "sonnet", "modelSettings": {"sonnet": {"effort": "low"}}}
        incoming = json.loads(self.SETTINGS_PATH.read_text())

        merged = merge_settings(baseline, current, incoming)

        if has_baseline and effort == "xhigh":
            assert "effortLevel" not in merged
        else:
            assert merged["effortLevel"] == effort
        assert merged["model"] == current["model"]
        assert merged["modelSettings"] == current["modelSettings"]

    def test_template_ships_the_concise_output_style(self):
        data = json.loads(self.SETTINGS_PATH.read_text())

        assert data.get("outputStyle") == "concise"

    def test_template_does_not_force_the_transcript_view(self):
        """`viewMode: verbose` expands every tool call inline for every user; that
        is an opt-in (`/config` or `Ctrl+O`), not something Pilot enforces."""
        data = json.loads(self.SETTINGS_PATH.read_text())

        assert "viewMode" not in data


class TestHookCommandsPythonVersion:
    """Hook command strings in source JSON must include --python python3 so uv
    ignores a local .python-version pin (e.g. 2.7) in the user's repo."""

    HOOKS_ROOT = Path(__file__).parents[4] / "pilot" / "hooks"

    def _collect_commands(self, filename: str) -> list[str]:
        path = self.HOOKS_ROOT / filename
        data = json.loads(path.read_text())
        commands = []
        for hook_list in data.get("hooks", {}).values():
            for entry in hook_list:
                for hook in entry.get("hooks", []):
                    if "command" in hook:
                        commands.append(hook["command"])
        return commands

    def test_hooks_json_commands_include_python_version_flag(self):
        """Every command in hooks.json must pass --python python3 to uv."""
        commands = self._collect_commands("hooks.json")
        assert commands, "hooks.json must contain at least one command"
        bad = [c for c in commands if "uv run" in c and "--python python3" not in c]
        assert not bad, f"Missing --python python3 in hooks.json:\n" + "\n".join(bad)

    def test_codex_hooks_json_commands_include_python_version_flag(self):
        """Every command in codex_hooks.json must pass --python python3 to uv."""
        commands = self._collect_commands("codex_hooks.json")
        assert commands, "codex_hooks.json must contain at least one command"
        bad = [c for c in commands if "uv run" in c and "--python python3" not in c]
        assert not bad, f"Missing --python python3 in codex_hooks.json:\n" + "\n".join(bad)
