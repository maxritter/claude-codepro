"""Tests for installer.steps.codex_files — Codex-specific file installation."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tomllib
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from installer.steps.codex_files import (
    MCP_BASELINE_FILE,
    CodexFilesStep,
    _TomlStructureError,
    _adapt_invocation_syntax,
    _codex_supports_context_management,
    _codex_supports_update_plan_config,
    _ensure_section_keys,
    _validate_toml_structure,
    build_codex_review_agent_toml,
    build_codex_skill_md,
    build_codex_skill_openai_yaml,
)


def _codex_runtime_text(skill_name: str) -> str:
    """Return the generated main file plus adapted progressive phase resources."""
    skill_dir = Path("pilot/skills") / skill_name
    parts = [build_codex_skill_md(skill_dir)]
    manifest = json.loads((skill_dir / "manifest.json").read_text())
    if manifest.get("delivery") == "progressive":
        parts.extend(_adapt_invocation_syntax((skill_dir / step["file"]).read_text()) for step in manifest["steps"])
    return "\n\n".join(parts)


def _claude_runtime_text(skill_name: str) -> str:
    from installer.skill_builder import build_skill_md

    skill_dir = Path("pilot/skills") / skill_name
    parts = [build_skill_md(skill_dir)]
    manifest = json.loads((skill_dir / "manifest.json").read_text())
    if manifest.get("delivery") == "progressive":
        parts.extend((skill_dir / step["file"]).read_text() for step in manifest["steps"])
    return "\n\n".join(parts)


@pytest.fixture(autouse=True)
def _disable_live_codex_version_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unit tests never execute the user's real Codex binary."""
    monkeypatch.setattr(
        "installer.steps.codex_files._codex_supports_context_management",
        lambda: True,
    )
    monkeypatch.setattr(
        "installer.steps.codex_files._codex_supports_update_plan_config",
        lambda: True,
    )


class TestCodexFilesStepCheck:
    def test_check_returns_false_always(self) -> None:
        step = CodexFilesStep()
        ctx = MagicMock()
        assert step.check(ctx) is False


class TestCodexContextManagementCompatibility:
    @pytest.mark.parametrize(
        ("version", "supported"),
        [
            ("codex-cli 0.152.1", False),
            ("codex-cli 0.153.0", True),
            ("codex-cli 1.0.0", True),
        ],
    )
    def test_detects_structured_feature_support(self, version: str, supported: bool) -> None:
        result = subprocess.CompletedProcess(["codex", "--version"], 0, stdout=version, stderr="")
        with patch("installer.steps.codex_files.subprocess.run", return_value=result):
            assert _codex_supports_context_management() is supported

    def test_fails_closed_when_version_cannot_be_detected(self) -> None:
        with patch("installer.steps.codex_files.subprocess.run", side_effect=OSError("missing")):
            assert _codex_supports_context_management() is False


class TestCodexUpdatePlanCompatibility:
    @pytest.mark.parametrize(
        ("version", "supported"),
        [
            ("codex-cli 0.151.0", False),
            ("codex-cli 0.152.0", True),
            ("codex-cli 1.0.0", True),
        ],
    )
    def test_detects_opt_in_config_support(self, version: str, supported: bool) -> None:
        result = subprocess.CompletedProcess(["codex", "--version"], 0, stdout=version, stderr="")
        with patch("installer.steps.codex_files.subprocess.run", return_value=result):
            assert _codex_supports_update_plan_config() is supported

    def test_fails_closed_when_version_cannot_be_detected(self) -> None:
        with patch("installer.steps.codex_files.subprocess.run", side_effect=OSError("missing")):
            assert _codex_supports_update_plan_config() is False


class TestCodexFilesStepSkipsWhenNoCodex:
    def test_run_is_noop_when_codex_not_installed(self, tmp_path: Path) -> None:
        step = CodexFilesStep()
        ctx = MagicMock()
        ctx.ui = None
        with patch(
            "installer.steps.codex_files.is_codex_installed",
            return_value=False,
        ):
            step.run(ctx)

    def test_run_does_not_request_sudo_for_desktop_open_file_limits(self) -> None:
        step = CodexFilesStep()
        ctx = MagicMock()
        ctx.ui = MagicMock()
        with (
            patch("installer.steps.codex_files.is_codex_installed", return_value=True),
            patch.object(step, "_install_codex_hooks", return_value=0),
            patch.object(step, "_install_codex_skills", return_value=0),
            patch.object(step, "_install_codex_agents", return_value=0),
            patch.object(step, "_install_codex_config", return_value=False),
            patch.object(step, "_install_codex_mcp", return_value=0),
            patch.object(step, "_install_codex_rules", return_value=0),
            patch.object(step, "_heal_codex_config_env"),
        ):
            step.run(ctx)

        messages = [str(call.args[0]) for call in ctx.ui.method_calls if call.args]
        assert not any("sudo" in message.lower() or "open-file limit" in message.lower() for message in messages)

    def test_run_warns_and_returns_when_codex_home_is_relative(self) -> None:
        step = CodexFilesStep()
        ctx = MagicMock()
        ctx.ui = MagicMock()

        with (
            patch("installer.steps.codex_files.is_codex_installed", return_value=True),
            patch(
                "installer.steps.codex_files._get_codex_config_dir",
                side_effect=ValueError("CODEX_HOME must be an absolute path, got: relative"),
            ),
            patch.object(step, "_install_codex_skills") as mock_install_skills,
        ):
            step.run(ctx)

        ctx.ui.warning.assert_called_once_with(
            "Skipping Codex file installation: CODEX_HOME must be an absolute path, got: relative"
        )
        mock_install_skills.assert_not_called()

    def test_run_warns_and_returns_when_codex_home_is_relative_during_rules_install(self, tmp_path: Path) -> None:
        rules_dir = tmp_path / ".claude" / "rules"
        rules_dir.mkdir(parents=True)
        (rules_dir / "test.md").write_text("# Test Rule\n")

        step = CodexFilesStep()
        ctx = MagicMock()
        ctx.ui = MagicMock()
        ctx.local_mode = False

        codex_dir = tmp_path / ".codex"
        with (
            patch("installer.steps.codex_files.is_codex_installed", return_value=True),
            patch("installer.steps.codex_files.Path.home", return_value=tmp_path),
            patch(
                "installer.steps.codex_files._get_codex_config_dir",
                side_effect=[
                    codex_dir,
                    codex_dir,
                    ValueError("CODEX_HOME must be an absolute path, got: relative"),
                ],
            ),
        ):
            step.run(ctx)

        ctx.ui.warning.assert_called_with(
            "Skipping Codex file installation: CODEX_HOME must be an absolute path, got: relative"
        )


class TestCodexHooksInstallation:
    def test_installs_hooks_json_to_codex_dir(self, tmp_path: Path) -> None:
        codex_dir = tmp_path / ".codex"
        pilot_home = tmp_path / ".pilot"
        hooks_src = pilot_home / "hooks"
        hooks_src.mkdir(parents=True)

        codex_hooks_template = tmp_path / "source" / "pilot" / "hooks" / "codex_hooks.json"
        codex_hooks_template.parent.mkdir(parents=True)
        codex_hooks_template.write_text(
            json.dumps({"hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "echo test"}]}]}})
        )

        step = CodexFilesStep()
        ctx = MagicMock()
        ctx.ui = None
        ctx.local_mode = True
        ctx.local_repo_dir = tmp_path / "source"
        ctx.project_dir = tmp_path / "project"

        with (
            patch("installer.steps.codex_files._get_codex_config_dir", return_value=codex_dir),
            patch("installer.steps.codex_files.Path.home", return_value=tmp_path),
        ):
            step._install_codex_hooks(ctx)

        hooks_file = codex_dir / "hooks.json"
        assert hooks_file.exists()
        data = json.loads(hooks_file.read_text())
        assert "hooks" in data
        assert "SessionStart" in data["hooks"]

    def test_real_template_leaves_codex_memory_retrieval_on_demand(self, tmp_path: Path) -> None:
        codex_dir = tmp_path / ".codex"
        repo_root = Path(__file__).resolve().parent.parent.parent.parent.parent

        step = CodexFilesStep()
        ctx = MagicMock()
        ctx.ui = None
        ctx.local_mode = True
        ctx.local_repo_dir = repo_root

        with patch("installer.steps.codex_files._get_codex_config_dir", return_value=codex_dir):
            step._install_codex_hooks(ctx)

        data = json.loads((codex_dir / "hooks.json").read_text())
        context_commands = [
            hook["command"] for entry in data["hooks"]["SessionStart"] for hook in entry.get("hooks", [])
        ]
        assert not any('worker-service.cjs" hook codex context' in command for command in context_commands)

    def test_upgrade_removes_previous_codex_memory_context_hook(self, tmp_path: Path) -> None:
        codex_dir = tmp_path / ".codex"
        codex_dir.mkdir(parents=True)
        repo_root = Path(__file__).resolve().parent.parent.parent.parent.parent
        old_context = {
            "matcher": "startup|resume|clear|compact",
            "hooks": [
                {
                    "type": "command",
                    "command": 'uv run python "$HOME/.pilot/scripts/worker-service.cjs" hook codex context',
                    "timeout": 15,
                }
            ],
        }
        user_hook = {
            "matcher": "startup",
            "hooks": [{"type": "command", "command": "echo user-startup"}],
        }
        (codex_dir / "hooks.json").write_text(json.dumps({"hooks": {"SessionStart": [old_context, user_hook]}}))
        (codex_dir / ".pilot-hooks-baseline.json").write_text(json.dumps({"SessionStart": [old_context]}))

        ctx = MagicMock(ui=None, local_mode=True, local_repo_dir=repo_root)
        with patch("installer.steps.codex_files._get_codex_config_dir", return_value=codex_dir):
            CodexFilesStep()._install_codex_hooks(ctx)

        session_start = json.loads((codex_dir / "hooks.json").read_text())["hooks"]["SessionStart"]
        commands = [hook["command"] for entry in session_start for hook in entry.get("hooks", [])]
        assert not any("hook codex context" in command for command in commands)
        assert "echo user-startup" in commands

    def test_real_template_has_all_hook_events(self, tmp_path: Path) -> None:
        codex_dir = tmp_path / ".codex"
        repo_root = Path(__file__).resolve().parent.parent.parent.parent.parent

        step = CodexFilesStep()
        ctx = MagicMock()
        ctx.ui = None
        ctx.local_mode = True
        ctx.local_repo_dir = repo_root

        with patch("installer.steps.codex_files._get_codex_config_dir", return_value=codex_dir):
            step._install_codex_hooks(ctx)

        data = json.loads((codex_dir / "hooks.json").read_text())
        hooks = data["hooks"]
        assert "SessionStart" in hooks
        assert "UserPromptSubmit" in hooks
        assert "PreToolUse" in hooks
        assert "PostToolUse" in hooks
        assert "Stop" in hooks
        assert "PreCompact" in hooks

    def test_real_template_uses_async_for_observers_and_silent_memory_sync(self, tmp_path: Path) -> None:
        codex_dir = tmp_path / ".codex"
        repo_root = Path(__file__).resolve().parent.parent.parent.parent.parent
        ctx = MagicMock(ui=None, local_mode=True, local_repo_dir=repo_root)

        with patch("installer.steps.codex_files._get_codex_config_dir", return_value=codex_dir):
            CodexFilesStep()._install_codex_hooks(ctx)

        hooks = json.loads((codex_dir / "hooks.json").read_text())["hooks"]
        handlers = [handler for entries in hooks.values() for entry in entries for handler in entry.get("hooks", [])]
        async_handlers = [handler for handler in handlers if handler.get("async") is True]
        assert len(async_handlers) == 4
        assert {handler["command"].split()[-1] for handler in async_handlers} >= {
            "session-init",
            "observation",
            "summarize",
            "memory-sync",
        }
        startup_sync = next(handler for handler in handlers if "codex_skill_sync.py" in handler["command"])
        assert "async" not in startup_sync
        control_handlers = [
            handler
            for handler in handlers
            if any(
                command in handler["command"]
                for command in ("repo_agent_sync.py", "spec_stop_guard.py", "session_end.py")
            )
        ]
        assert control_handlers
        assert all("async" not in handler for handler in control_handlers)
        session_end = [handler for entry in hooks["SessionEnd"] for handler in entry["hooks"]]
        assert session_end[0]["timeout"] == 3

    def test_upgrade_replaces_background_wrapper_and_preserves_user_async_hook(self, tmp_path: Path) -> None:
        codex_dir = tmp_path / ".codex"
        codex_dir.mkdir(parents=True)
        old = {
            "hooks": {
                "PostToolUse": [
                    {
                        "hooks": [
                            {
                                "type": "command",
                                "command": 'uv run --no-project --python python3 python "$HOME/.pilot/hooks/codex_background.py" -- bun "$HOME/.pilot/scripts/worker-service.cjs" hook codex observation',
                            }
                        ]
                    },
                    {"hooks": [{"type": "command", "command": "my-custom-hook.sh", "async": True}]},
                ]
            }
        }
        (codex_dir / "hooks.json").write_text(json.dumps(old))
        repo_root = Path(__file__).resolve().parent.parent.parent.parent.parent
        ctx = MagicMock(ui=None, local_mode=True, local_repo_dir=repo_root)

        with patch("installer.steps.codex_files._get_codex_config_dir", return_value=codex_dir):
            CodexFilesStep()._install_codex_hooks(ctx)

        hooks = json.loads((codex_dir / "hooks.json").read_text())["hooks"]
        post_tool_handlers = [handler for entry in hooks["PostToolUse"] for handler in entry["hooks"]]
        pilot = next(handler for handler in post_tool_handlers if "/.pilot/" in handler["command"])
        user = next(handler for handler in post_tool_handlers if handler["command"] == "my-custom-hook.sh")
        assert pilot["async"] is True
        assert "codex_background.py" not in pilot["command"]
        assert user["async"] is True

    def test_merge_preserves_user_posttooluse_hooks(self, tmp_path: Path) -> None:
        codex_dir = tmp_path / ".codex"
        codex_dir.mkdir(parents=True)
        repo_root = Path(__file__).resolve().parent.parent.parent.parent.parent

        user_hooks = {
            "hooks": {
                "PostToolUse": [
                    {
                        "matcher": "*",
                        "hooks": [{"type": "command", "command": "my-custom-hook.sh"}],
                    }
                ]
            }
        }
        (codex_dir / "hooks.json").write_text(json.dumps(user_hooks))

        step = CodexFilesStep()
        ctx = MagicMock()
        ctx.ui = None
        ctx.local_mode = True
        ctx.local_repo_dir = repo_root

        with patch("installer.steps.codex_files._get_codex_config_dir", return_value=codex_dir):
            step._install_codex_hooks(ctx)

        data = json.loads((codex_dir / "hooks.json").read_text())
        all_commands = [hook["command"] for entry in data["hooks"]["PostToolUse"] for hook in entry.get("hooks", [])]
        assert any("my-custom-hook.sh" in cmd for cmd in all_commands)
        assert any("observation" in cmd for cmd in all_commands)

    def test_upgrade_removes_pilot_hooks_from_mixed_entries_without_losing_user_hook(self, tmp_path: Path) -> None:
        codex_dir = tmp_path / ".codex"
        codex_dir.mkdir(parents=True)
        pilot_hook = {"type": "command", "command": "$HOME/.pilot/hooks/session_end.py", "timeout": 3}
        incoming = {"hooks": {"SessionEnd": [{"hooks": [pilot_hook]}]}}
        (codex_dir / ".pilot-hooks-baseline.json").write_text(json.dumps(incoming["hooks"]))
        (codex_dir / "hooks.json").write_text(json.dumps({"hooks": {"SessionEnd": [
            {"hooks": [pilot_hook, {"type": "command", "command": "my-session-end.sh"}]},
            {"hooks": [pilot_hook]},
        ]}}))

        CodexFilesStep()._merge_codex_hooks(codex_dir, incoming)

        hooks = json.loads((codex_dir / "hooks.json").read_text())["hooks"]["SessionEnd"]
        commands = [hook["command"] for entry in hooks for hook in entry["hooks"]]
        assert commands.count("$HOME/.pilot/hooks/session_end.py") == 1
        assert commands.count("my-session-end.sh") == 1

    def test_merge_preserves_invalid_existing_hooks_file(self, tmp_path: Path) -> None:
        codex_dir = tmp_path / ".codex"
        codex_dir.mkdir(parents=True)
        hooks_file = codex_dir / "hooks.json"
        invalid = '{"hooks": {"SessionStart": [}'
        hooks_file.write_text(invalid)

        incoming = {"hooks": {"SessionStart": [{"hooks": [{"command": "echo pilot"}]}]}}

        assert CodexFilesStep()._merge_codex_hooks(codex_dir, incoming) == 0
        assert hooks_file.read_text() == invalid

    def test_merge_keeps_existing_event_order_then_appends_new_events(self, tmp_path: Path) -> None:
        codex_dir = tmp_path / ".codex"
        codex_dir.mkdir(parents=True)
        existing = {
            "hooks": {
                "PreToolUse": [{"hooks": [{"command": "echo user-pre"}]}],
                "Stop": [{"hooks": [{"command": "echo user-stop"}]}],
            }
        }
        (codex_dir / "hooks.json").write_text(json.dumps(existing))
        incoming = {
            "hooks": {
                "SessionStart": [{"hooks": [{"command": "$HOME/.pilot/hooks/start.py"}]}],
                "Stop": [{"hooks": [{"command": "$HOME/.pilot/hooks/stop.py"}]}],
            }
        }

        CodexFilesStep()._merge_codex_hooks(codex_dir, incoming)

        merged = json.loads((codex_dir / "hooks.json").read_text())
        assert list(merged["hooks"]) == ["PreToolUse", "Stop", "SessionStart"]


class TestCodexSkillsInstallation:
    def test_builds_codex_skill_with_frontmatter(self, tmp_path: Path) -> None:
        from installer.steps.codex_files import build_codex_skill_md

        skill_dir = tmp_path / "skills" / "fix"
        skill_dir.mkdir(parents=True)
        (skill_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "version": 1,
                    "orchestrator": "orchestrator.md",
                    "steps": [{"id": "step-1", "file": "steps/01-impl.md"}],
                }
            )
        )
        (skill_dir / "orchestrator.md").write_text(
            "---\nname: fix\ndescription: Bugfix workflow\nuser-invocable: true\n---\n\n# /fix\n\nFix bugs fast."
        )
        steps_dir = skill_dir / "steps"
        steps_dir.mkdir()
        (steps_dir / "01-impl.md").write_text("## Step 1\n\nImplement the fix.")

        result = build_codex_skill_md(skill_dir)
        assert result.startswith("---\n")
        assert "name: fix" in result
        assert "Diagnose and repair a defect at its root cause" in result
        assert "Explicit $fix workflow" in result
        assert "# /fix" in result or "# $fix" in result
        assert "Implement the fix." in result

    def test_codex_skill_adapts_invocation_syntax(self, tmp_path: Path) -> None:
        from installer.steps.codex_files import build_codex_skill_md

        skill_dir = tmp_path / "skills" / "spec"
        skill_dir.mkdir(parents=True)
        (skill_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "version": 1,
                    "orchestrator": "orchestrator.md",
                    "steps": [],
                }
            )
        )
        (skill_dir / "orchestrator.md").write_text(
            "---\nname: spec\ndescription: Spec workflow\n---\n\nRun /spec to plan. Also /fix for bugs."
        )

        result = build_codex_skill_md(skill_dir)
        assert "$spec" in result
        assert "$fix" in result

    def test_codex_skill_does_not_corrupt_question_fallback_prose(self, tmp_path: Path) -> None:
        from installer.steps.codex_files import build_codex_skill_md

        skill_dir = tmp_path / "skills" / "setup-rules"
        skill_dir.mkdir(parents=True)
        (skill_dir / "manifest.json").write_text(
            json.dumps({"version": 1, "orchestrator": "orchestrator.md", "steps": []})
        )
        (skill_dir / "orchestrator.md").write_text(
            "---\nname: setup-rules\ndescription: Rules workflow\n---\n\n"
            "Use plain-text numbered options because the `AskUserQuestion` tool "
            "isn't callable in Codex."
        )

        result = build_codex_skill_md(skill_dir)

        assert "plain-text numbered options" in result
        assert "Claude structured-question tool" in result
        assert "`plain-text numbered options` format isn't callable" not in result

    def test_non_allowlisted_skill_is_never_shipped_to_codex(self, tmp_path: Path) -> None:
        """CC-only skills (the bot-* family) must not reach Codex.

        The mechanism is allowlist omission; this pins it so a future allowlist
        edit or auto-discovery refactor cannot silently ship a CC-only skill.
        """
        agents_skills_dir = tmp_path / ".agents" / "skills"
        pilot_skills_dir = tmp_path / ".claude" / "skills"

        for name in ("fix", "bot-jobs"):
            skill_dir = pilot_skills_dir / name
            skill_dir.mkdir(parents=True)
            (skill_dir / "manifest.json").write_text(
                json.dumps({"version": 1, "orchestrator": "orchestrator.md", "steps": []})
            )
            (skill_dir / "orchestrator.md").write_text(f"---\nname: {name}\ndescription: d\n---\n\n# {name}\n\nBody.")

        step = CodexFilesStep()
        ctx = MagicMock()
        ctx.ui = None

        with patch("installer.steps.codex_files.Path.home", return_value=tmp_path):
            step._install_codex_skills(ctx)

        assert (agents_skills_dir / "fix" / "SKILL.md").exists()  # allowlisted sibling proves the run
        assert not (agents_skills_dir / "bot-jobs").exists()

    def test_retiring_claude_only_skills_preserves_unowned_same_name_skill(self, tmp_path: Path) -> None:
        source = tmp_path / ".pilot" / "skills"
        source.mkdir(parents=True)
        custom = tmp_path / ".agents" / "skills" / "bot-jobs"
        custom.mkdir(parents=True)
        (custom / "SKILL.md").write_text("My independent Codex scheduler")
        (custom / "notes.txt").write_text("User notes")
        ctx = MagicMock()
        ctx.ui = None
        with patch("installer.steps.codex_files.Path.home", return_value=tmp_path):
            CodexFilesStep()._install_codex_skills(ctx)
        assert (custom / "SKILL.md").read_text() == "My independent Codex scheduler"
        assert (custom / "notes.txt").read_text() == "User notes"

    def test_installs_skills_to_agents_dir(self, tmp_path: Path) -> None:
        agents_skills_dir = tmp_path / ".agents" / "skills"
        pilot_skills_dir = tmp_path / ".claude" / "skills"

        skill_dir = pilot_skills_dir / "fix"
        skill_dir.mkdir(parents=True)
        (skill_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "version": 1,
                    "orchestrator": "orchestrator.md",
                    "steps": [],
                }
            )
        )
        (skill_dir / "orchestrator.md").write_text("---\nname: fix\ndescription: Bugfix\n---\n\n# Fix\n\nContent.")

        step = CodexFilesStep()
        ctx = MagicMock()
        ctx.ui = None

        with patch("installer.steps.codex_files.Path.home", return_value=tmp_path):
            step._install_codex_skills(ctx)

        skill_md = agents_skills_dir / "fix" / "SKILL.md"
        assert skill_md.exists()
        content = skill_md.read_text()
        assert content.startswith("---\n")
        assert "name: fix" in content

        metadata = yaml.safe_load((agents_skills_dir / "fix" / "agents" / "openai.yaml").read_text())
        assert metadata["interface"]["display_name"] == "Fix"
        assert metadata["policy"]["allow_implicit_invocation"] is False

    def test_installs_benchmark_and_setup_rules_runtime_resources_with_modes(self, tmp_path: Path) -> None:
        pilot_skills_dir = tmp_path / ".claude" / "skills"
        for name in ("benchmark", "setup-rules"):
            skill_dir = pilot_skills_dir / name
            skill_dir.mkdir(parents=True)
            (skill_dir / "manifest.json").write_text(
                json.dumps({"version": 1, "orchestrator": "orchestrator.md", "steps": []})
            )
            (skill_dir / "orchestrator.md").write_text(
                f"---\nname: {name}\ndescription: {name.title()} utility\n---\n\n# {name}\n"
            )
            (skill_dir / "steps").mkdir()
            (skill_dir / "steps" / "01-authoring.md").write_text("compiled into SKILL.md")
            (skill_dir / "tests").mkdir()
            (skill_dir / "tests" / "test_authoring.py").write_text("raise AssertionError")

        benchmark = pilot_skills_dir / "benchmark"
        (benchmark / "scripts").mkdir()
        benchmark_runner = benchmark / "scripts" / "runner.py"
        benchmark_runner.write_text("print('benchmark')\n")
        benchmark_runner.chmod(0o751)
        (benchmark / "agents").mkdir()
        (benchmark / "agents" / "grader.md").write_text("# Runtime grader\n")
        (benchmark / "agents" / "openai.yaml").write_text("source: must-not-win\n")

        setup_rules = pilot_skills_dir / "setup-rules"
        (setup_rules / "scripts").mkdir()
        setup_sync = setup_rules / "scripts" / "sync-agent-assets.mjs"
        setup_sync.write_text("print('sync')\n")
        setup_sync.chmod(0o754)
        (setup_rules / "references").mkdir()
        (setup_rules / "references" / "shared-rules.md").write_text("# Shared rules\n")

        ctx = MagicMock(ui=None)
        with patch("installer.steps.codex_files.Path.home", return_value=tmp_path):
            assert CodexFilesStep()._install_codex_skills(ctx) == 2

        installed = tmp_path / ".agents" / "skills"
        installed_runner = installed / "benchmark" / "scripts" / "runner.py"
        installed_sync = installed / "setup-rules" / "scripts" / "sync-agent-assets.mjs"
        assert installed_runner.read_text() == "print('benchmark')\n"
        assert installed_sync.read_text() == "print('sync')\n"
        assert installed_runner.stat().st_mode & 0o777 == 0o751
        assert installed_sync.stat().st_mode & 0o777 == 0o754
        assert (installed / "benchmark" / "agents" / "grader.md").exists()
        assert (installed / "setup-rules" / "references" / "shared-rules.md").exists()

        for name in ("benchmark", "setup-rules"):
            skill = installed / name
            assert (skill / "SKILL.md").exists()
            assert not (skill / "manifest.json").exists()
            assert not (skill / "orchestrator.md").exists()
            assert not (skill / "steps").exists()
            assert not (skill / "tests").exists()
            metadata = yaml.safe_load((skill / "agents" / "openai.yaml").read_text())
            assert metadata["interface"]["display_name"] == name.replace("-", " ").title()

    def test_progressive_skill_installs_platform_adapted_step_resources(self, tmp_path: Path) -> None:
        skill_dir = tmp_path / ".claude" / "skills" / "fix"
        steps = skill_dir / "steps"
        steps.mkdir(parents=True)
        (skill_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "version": 2,
                    "orchestrator": "orchestrator.md",
                    "delivery": "progressive",
                    "targets": ["claude", "codex"],
                    "visibility": "public",
                    "invocation": "explicit",
                    "steps": [{"id": "step-1", "file": "steps/01.md"}],
                }
            )
        )
        (skill_dir / "orchestrator.md").write_text("---\nname: fix\ndescription: Fix workflow\n---\n\n# Fix\n")
        (steps / "01.md").write_text(
            "## Step 1\n\n"
            "<!-- CC-ONLY -->\nClaude only.\n<!-- /CC-ONLY -->\n"
            "<!-- CODEX-START\nCodex only.\nCODEX-END -->\n"
            'Run /spec, then AskUserQuestion(\n  question="Ready?",\n  options=["Yes", "No"]\n).\n'
        )

        with patch("installer.steps.codex_files.Path.home", return_value=tmp_path):
            assert CodexFilesStep()._install_codex_skills(MagicMock(ui=None)) == 1

        installed = tmp_path / ".agents" / "skills" / "fix"
        main = (installed / "SKILL.md").read_text()
        step = (installed / "steps" / "01.md").read_text()
        assert "Required phase resources" in main
        assert "Codex only." not in main
        assert "Codex only." in step
        assert "Claude only." not in step
        assert "$spec" in step
        assert "structured question" in step
        assert "AskUserQuestion" not in step

    def test_claude_only_target_removes_managed_codex_artifacts_but_preserves_user_files(self, tmp_path: Path) -> None:
        skill_dir = tmp_path / ".claude" / "skills" / "fix"
        skill_dir.mkdir(parents=True)
        (skill_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "version": 2,
                    "orchestrator": "orchestrator.md",
                    "delivery": "bundled",
                    "targets": ["claude"],
                    "visibility": "public",
                    "invocation": "explicit",
                    "steps": [],
                }
            )
        )
        (skill_dir / "orchestrator.md").write_text("---\nname: fix\ndescription: Fix workflow\n---\n\n# Fix\n")
        installed = tmp_path / ".agents" / "skills" / "fix"
        (installed / "agents").mkdir(parents=True)
        (installed / "SKILL.md").write_text("managed")
        (installed / "agents" / "openai.yaml").write_text("managed")
        (installed / ".pilot-resources.json").write_text('{"files": [], "directories": []}\n')
        (installed / "user-note.md").write_text("keep")

        with patch("installer.steps.codex_files.Path.home", return_value=tmp_path):
            assert CodexFilesStep()._install_codex_skills(MagicMock(ui=None)) == 0

        assert not (installed / "SKILL.md").exists()
        assert not (installed / "agents" / "openai.yaml").exists()
        assert (installed / "user-note.md").read_text() == "keep"

    def test_missing_source_tree_removes_sidecar_managed_codex_artifacts(self, tmp_path: Path) -> None:
        installed = tmp_path / ".agents" / "skills" / "fix"
        installed.mkdir(parents=True)
        (installed / "SKILL.md").write_text("managed")
        (installed / ".pilot-resources.json").write_text('{"files": [], "directories": []}\n')
        (installed / "user-note.md").write_text("keep")
        step = CodexFilesStep()

        with (
            patch("installer.steps.codex_files.Path.home", return_value=tmp_path),
            patch.object(step, "_find_codex_skills_source", return_value=None),
        ):
            assert step._install_codex_skills(MagicMock(ui=None)) == 0

        assert not (installed / "SKILL.md").exists()
        assert not (installed / ".pilot-resources.json").exists()
        assert (installed / "user-note.md").read_text() == "keep"

    def test_removes_only_obsolete_managed_skill_resources(self, tmp_path: Path) -> None:
        skill_dir = tmp_path / ".claude" / "skills" / "benchmark"
        skill_dir.mkdir(parents=True)
        (skill_dir / "manifest.json").write_text(
            json.dumps({"version": 1, "orchestrator": "orchestrator.md", "steps": []})
        )
        (skill_dir / "orchestrator.md").write_text(
            "---\nname: benchmark\ndescription: Benchmark utility\n---\n\n# Benchmark\n"
        )
        scripts = skill_dir / "scripts"
        scripts.mkdir()
        (scripts / "current.py").write_text("CURRENT = True\n")
        (scripts / "obsolete.py").write_text("OBSOLETE = True\n")
        assets = skill_dir / "assets"
        assets.mkdir()
        (assets / "obsolete.txt").write_text("old\n")

        ctx = MagicMock(ui=None)
        step = CodexFilesStep()
        with patch("installer.steps.codex_files.Path.home", return_value=tmp_path):
            step._install_codex_skills(ctx)

        installed_skills = tmp_path / ".agents" / "skills"
        installed = installed_skills / "benchmark"
        (installed / "user-note.md").write_text("keep me\n")
        (installed / "scripts" / "user-helper.py").write_text("# keep me\n")
        custom_skill = installed_skills / "my-custom-skill"
        custom_skill.mkdir(parents=True)
        (custom_skill / "SKILL.md").write_text("# User skill\n")

        (scripts / "obsolete.py").unlink()
        shutil.rmtree(assets)
        with patch("installer.steps.codex_files.Path.home", return_value=tmp_path):
            step._install_codex_skills(ctx)

        assert (installed / "scripts" / "current.py").exists()
        assert not (installed / "scripts" / "obsolete.py").exists()
        assert not (installed / "assets").exists()
        assert (installed / "user-note.md").read_text() == "keep me\n"
        assert (installed / "scripts" / "user-helper.py").exists()
        assert (custom_skill / "SKILL.md").read_text() == "# User skill\n"
        assert (installed / "agents" / "openai.yaml").exists()

    def test_workflow_skills_are_explicit_but_utility_skills_remain_discoverable(self, tmp_path: Path) -> None:
        pilot_skills_dir = tmp_path / ".claude" / "skills"
        for name in ("build", "benchmark"):
            skill_dir = pilot_skills_dir / name
            skill_dir.mkdir(parents=True)
            (skill_dir / "manifest.json").write_text(
                json.dumps({"version": 1, "orchestrator": "orchestrator.md", "steps": []})
            )
            (skill_dir / "orchestrator.md").write_text(
                f"---\nname: {name}\ndescription: {name.title()} workflow\n---\n\n# {name}\n"
            )

        step = CodexFilesStep()
        ctx = MagicMock()
        ctx.ui = None
        with patch("installer.steps.codex_files.Path.home", return_value=tmp_path):
            step._install_codex_skills(ctx)

        skills = tmp_path / ".agents" / "skills"
        build_meta = yaml.safe_load((skills / "build" / "agents" / "openai.yaml").read_text())
        benchmark_meta = yaml.safe_load((skills / "benchmark" / "agents" / "openai.yaml").read_text())
        assert build_meta["policy"]["allow_implicit_invocation"] is False
        assert benchmark_meta["policy"]["allow_implicit_invocation"] is True

    def test_v2_internal_spec_phase_uses_manifest_invocation_policy(self) -> None:
        metadata = yaml.safe_load(build_codex_skill_openai_yaml(Path("pilot/skills/spec-plan")))

        assert metadata["policy"]["allow_implicit_invocation"] is False

    def test_v2_codex_short_description_comes_from_manifest(self, tmp_path: Path) -> None:
        skill_dir = tmp_path / "demo"
        skill_dir.mkdir()
        (skill_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "version": 2,
                    "orchestrator": "orchestrator.md",
                    "delivery": "bundled",
                    "targets": ["claude", "codex"],
                    "visibility": "public",
                    "invocation": "implicit",
                    "platform": {"codex": {"short_description": "Manifest description"}},
                    "steps": [],
                }
            )
        )
        (skill_dir / "orchestrator.md").write_text("---\nname: demo\ndescription: Source description\n---\n\n# Demo\n")

        metadata = yaml.safe_load(build_codex_skill_openai_yaml(skill_dir))

        assert metadata["interface"]["short_description"] == "Manifest description"
        assert metadata["policy"]["allow_implicit_invocation"] is True

    def test_visible_pilot_skill_descriptions_fit_a_lean_catalog_budget(self) -> None:
        visible_names = (
            "benchmark",
            "create-skill",
            "setup-rules",
        )
        descriptions: list[str] = []
        for name in visible_names:
            content = build_codex_skill_md(Path("pilot/skills") / name)
            description = yaml.safe_load(content.split("---", 2)[1])["description"]
            metadata = yaml.safe_load(build_codex_skill_openai_yaml(Path("pilot/skills") / name))
            assert metadata["interface"]["short_description"] == description
            assert metadata["policy"]["allow_implicit_invocation"] is True
            assert len(description) <= 120
            descriptions.append(description)

        assert sum(map(len, descriptions)) <= 360

    @pytest.mark.parametrize("skill_name", ["build", "spec", "fix", "prd", "investigate", "cleanup"])
    def test_explicit_workflow_descriptions_are_also_concise(self, skill_name: str) -> None:
        content = build_codex_skill_md(Path("pilot/skills") / skill_name)
        description = yaml.safe_load(content.split("---", 2)[1])["description"]

        assert len(description) <= 120
        assert "explicit" in description.casefold()
        assert not description.casefold().startswith("use only")

    @pytest.mark.parametrize(
        "skill_name",
        ["spec-plan", "spec-bugfix-plan", "spec-implement", "spec-verify", "spec-bugfix-verify"],
    )
    def test_internal_phase_descriptions_cannot_route_ordinary_requests(self, skill_name: str) -> None:
        content = build_codex_skill_md(Path("pilot/skills") / skill_name)
        description = yaml.safe_load(content.split("---", 2)[1])["description"]

        assert description.startswith("Internal $spec")
        assert "only after" in description
        metadata = yaml.safe_load(build_codex_skill_openai_yaml(Path("pilot/skills") / skill_name))
        assert metadata["policy"]["allow_implicit_invocation"] is False

    def test_openai_yaml_is_valid_for_codex_skill_discovery(self, tmp_path: Path) -> None:
        skill_dir = tmp_path / "skills" / "spec"
        skill_dir.mkdir(parents=True)
        (skill_dir / "manifest.json").write_text(
            json.dumps({"version": 1, "orchestrator": "orchestrator.md", "steps": []})
        )
        (skill_dir / "orchestrator.md").write_text(
            "---\nname: spec\ndescription: Plan and implement an approved task list.\n---\n\n# Spec\n"
        )

        metadata = yaml.safe_load(build_codex_skill_openai_yaml(skill_dir))

        assert metadata["interface"]["display_name"] == "Spec"
        description = metadata["interface"]["short_description"]
        assert "Plan, approve, implement, and verify" in description
        assert "explicit $spec workflow" in description
        assert not description.casefold().startswith("use only")
        assert "/spec" not in description
        assert metadata["policy"] == {"allow_implicit_invocation": False}

    def test_builds_codex_review_agent_toml_without_output_path_contract(self) -> None:
        result = build_codex_review_agent_toml(Path("pilot/agents/spec-review.md"))
        data = tomllib.loads(result)

        assert data["name"] == "spec-review"
        assert data["model"] == "codex-auto-review"
        assert "requirements" in data["description"]
        assert "developer_instructions" in data
        instructions = data["developer_instructions"]
        assert "Output ONLY valid JSON" in instructions
        assert '"issues"' in instructions
        assert "output_path" not in instructions
        assert "MANDATORY: Write output" not in instructions
        assert "Your LAST action MUST be `Write`" not in instructions
        assert "Write Output" not in instructions
        assert "write output" not in instructions.lower()

    def test_builds_changes_review_agent_with_final_status_guidance(self) -> None:
        result = build_codex_review_agent_toml(Path("pilot/agents/changes-review.md"))
        data = tomllib.loads(result)

        assert data["name"] == "changes-review"
        instructions = data["developer_instructions"]
        assert "Status: VERIFIED" in instructions
        assert "orchestrator after the user review gate" in instructions
        assert "do not emit a finding during changes review" in instructions

    def test_builds_build_review_agent_judging_criteria_not_spec_sections(self) -> None:
        result = build_codex_review_agent_toml(Path("pilot/agents/build-review.md"))
        data = tomllib.loads(result)

        assert data["name"] == "build-review"
        assert data["model"] == "codex-auto-review"
        instructions = data["developer_instructions"]
        assert "Output ONLY valid JSON" in instructions
        assert '"issues"' in instructions
        # A Buildout has none of these; reporting their absence would be noise.
        assert "does NOT have" in instructions
        assert "output_path" not in instructions

    def test_installs_review_agents_to_codex_agents_dir(self, tmp_path: Path) -> None:
        claude_agents_dir = tmp_path / ".claude" / "agents"
        claude_agents_dir.mkdir(parents=True)
        shutil.copyfile(Path("pilot/agents/spec-review.md"), claude_agents_dir / "spec-review.md")
        shutil.copyfile(Path("pilot/agents/changes-review.md"), claude_agents_dir / "changes-review.md")
        shutil.copyfile(Path("pilot/agents/build-review.md"), claude_agents_dir / "build-review.md")
        codex_agents_dir = tmp_path / ".codex" / "agents"
        codex_agents_dir.mkdir(parents=True)
        (codex_agents_dir / "user-agent.toml").write_text('name = "user-agent"\n')

        step = CodexFilesStep()
        ctx = MagicMock()
        ctx.ui = None

        with patch("installer.steps.codex_files.Path.home", return_value=tmp_path):
            installed = step._install_codex_agents(ctx)

        spec_agent = codex_agents_dir / "spec-review.toml"
        changes_agent = codex_agents_dir / "changes-review.toml"
        build_agent = codex_agents_dir / "build-review.toml"
        assert installed == 3
        assert spec_agent.exists()
        assert changes_agent.exists()
        assert build_agent.exists()
        assert (codex_agents_dir / "user-agent.toml").exists()
        spec_data = tomllib.loads(spec_agent.read_text())
        changes_data = tomllib.loads(changes_agent.read_text())
        build_data = tomllib.loads(build_agent.read_text())
        assert spec_data["name"] == "spec-review"
        assert spec_data["model"] == "codex-auto-review"
        assert changes_data["name"] == "changes-review"
        assert changes_data["model"] == "codex-auto-review"
        assert build_data["name"] == "build-review"
        assert build_data["model"] == "codex-auto-review"

    def test_build_review_codex_prompt_template_is_not_installed_as_an_agent(self, tmp_path: Path) -> None:
        """`*-codex.md` files are companion prompt templates, not Codex custom agents.

        `spec-review-codex.md` has always been skipped; `build-review-codex.md` must be
        too, or Codex gains a bogus agent whose body is a `task --prompt-file` prompt.
        """
        claude_agents_dir = tmp_path / ".claude" / "agents"
        claude_agents_dir.mkdir(parents=True)
        shutil.copyfile(Path("pilot/agents/build-review.md"), claude_agents_dir / "build-review.md")
        shutil.copyfile(Path("pilot/agents/build-review-codex.md"), claude_agents_dir / "build-review-codex.md")
        codex_agents_dir = tmp_path / ".codex" / "agents"
        codex_agents_dir.mkdir(parents=True)

        step = CodexFilesStep()
        ctx = MagicMock()
        ctx.ui = None

        with patch("installer.steps.codex_files.Path.home", return_value=tmp_path):
            step._install_codex_agents(ctx)

        assert (codex_agents_dir / "build-review.toml").exists()
        assert not (codex_agents_dir / "build-review-codex.toml").exists()

    def test_preserves_user_created_same_name_codex_agent(self, tmp_path: Path) -> None:
        claude_agents_dir = tmp_path / ".claude" / "agents"
        claude_agents_dir.mkdir(parents=True)
        shutil.copyfile(Path("pilot/agents/spec-review.md"), claude_agents_dir / "spec-review.md")
        codex_agents_dir = tmp_path / ".codex" / "agents"
        codex_agents_dir.mkdir(parents=True)
        user_content = 'name = "spec-review"\ndescription = "user agent"\n'
        (codex_agents_dir / "spec-review.toml").write_text(user_content)

        step = CodexFilesStep()
        ctx = MagicMock()
        ctx.ui = MagicMock()

        with patch("installer.steps.codex_files.Path.home", return_value=tmp_path):
            step._install_codex_agents(ctx)

        assert (codex_agents_dir / "spec-review.toml").read_text() == user_content
        ctx.ui.warning.assert_called_once()

    def test_removes_stale_managed_review_agent_when_source_disappears(self, tmp_path: Path) -> None:
        source_dir = tmp_path / ".pilot" / "agents"
        source_dir.mkdir(parents=True)
        codex_agents_dir = tmp_path / ".codex" / "agents"
        codex_agents_dir.mkdir(parents=True)
        stale = codex_agents_dir / "build-review.toml"
        stale.write_text('# pilot-shell managed Codex review agent\nname = "build-review"\n')
        user = codex_agents_dir / "spec-review.toml"
        user.write_text('name = "spec-review"\n')

        with patch("installer.steps.codex_files.Path.home", return_value=tmp_path):
            assert CodexFilesStep()._install_codex_agents(MagicMock(ui=None, local_mode=False)) == 0

        assert not stale.exists()
        assert user.read_text() == 'name = "spec-review"\n'

    def test_missing_review_source_tree_removes_only_managed_agents(self, tmp_path: Path) -> None:
        codex_agents_dir = tmp_path / ".codex" / "agents"
        codex_agents_dir.mkdir(parents=True)
        managed = codex_agents_dir / "build-review.toml"
        managed.write_text('# pilot-shell managed Codex review agent\nname = "build-review"\n')
        user = codex_agents_dir / "spec-review.toml"
        user.write_text('name = "spec-review"\n')
        step = CodexFilesStep()

        with (
            patch("installer.steps.codex_files._get_codex_config_dir", return_value=tmp_path / ".codex"),
            patch.object(step, "_find_codex_review_agents_source", return_value=None),
        ):
            assert step._install_codex_agents(MagicMock(ui=None)) == 0

        assert not managed.exists()
        assert user.read_text() == 'name = "spec-review"\n'

    def test_removes_stale_bot_skills_from_agents_dir(self, tmp_path: Path) -> None:
        agents_skills_dir = tmp_path / ".agents" / "skills"
        pilot_skills_dir = tmp_path / ".claude" / "skills"

        # Create a supported skill (fix) and stale bot-* skills
        for name in ["fix", "bot-boot", "bot-channel-task", "bot-defaults"]:
            skill_dir = pilot_skills_dir / name
            skill_dir.mkdir(parents=True)
            (skill_dir / "manifest.json").write_text(
                json.dumps({"version": 1, "orchestrator": "orchestrator.md", "steps": []})
            )
            (skill_dir / "orchestrator.md").write_text(
                f"---\nname: {name}\ndescription: {name}\n---\n\n# {name}\n\nContent."
            )

        # Pre-populate stale bot-* skills in agents dir (from older installer)
        for name in ["bot-boot", "bot-channel-task", "bot-defaults"]:
            stale_dir = agents_skills_dir / name
            stale_dir.mkdir(parents=True)
            (stale_dir / "SKILL.md").write_text(f"# stale {name}")
            (stale_dir / ".pilot-resources.json").write_text('{"files": [], "directories": []}')

        step = CodexFilesStep()
        ctx = MagicMock()
        ctx.ui = None

        with patch("installer.steps.codex_files.Path.home", return_value=tmp_path):
            step._install_codex_skills(ctx)

        # bot-* should be removed
        assert not (agents_skills_dir / "bot-boot").exists()
        assert not (agents_skills_dir / "bot-channel-task").exists()
        assert not (agents_skills_dir / "bot-defaults").exists()
        # fix should still be installed
        assert (agents_skills_dir / "fix" / "SKILL.md").exists()

    def test_setup_rules_codex_skill_creates_project_agents_md(self) -> None:
        from installer.steps.codex_files import build_codex_skill_md

        result = _codex_runtime_text("setup-rules")

        assert "Codex reads it directly; Claude Code imports it through `CLAUDE.md`" in result
        assert "Its absence is a setup gap for both Claude Code and Codex" in result
        assert "Pilot's shared hook synchronizes on SessionStart, supported edits made through either agent" in result
        assert "The shared hook normally performs every write" in result
        assert "Never create AGENTS.md if it doesn't exist" not in result

    def test_create_skill_codex_skill_uses_agents_skill_paths(self) -> None:
        from installer.steps.codex_files import build_codex_skill_md

        result = _codex_runtime_text("create-skill")

        assert ".agents/skills/{slug}-{name}/SKILL.md" in result
        assert "mkdir -p ~/.agents/skills/{slug}-{name}" in result
        assert "Pilot's shared hook synchronizes `.agents/skills/` and `.claude/skills/`" in result
        assert "Create or edit only the canonical directory" in result
        assert "Users normally do not run `--write`" in result
        assert "Keep manual `--write` as recovery" in result

    def test_benchmark_codex_skill_describes_codex_materialization(self) -> None:
        from installer.steps.codex_files import build_codex_skill_md

        result = _codex_runtime_text("benchmark")

        assert ".agents/skills/<name>/" in result
        assert "root `AGENTS.md`" in result
        assert "--agent codex" in result
        assert "with/.claude/skills/<name>/" not in result

    def test_fix_codex_skill_uses_selective_codegraph_guidance(self) -> None:
        from installer.steps.codex_files import build_codex_skill_md

        result = _codex_runtime_text("fix")

        assert 'Start with `codegraph_context(task="<bug description>")`' not in result
        assert "Use `codegraph_explore` only when the bug is structural" in result
        assert "For docs, rules, markdown, config, UI copy, or a named local file/function" in result

    def test_fix_skill_env_blocker_protocol_diverges_per_agent(self) -> None:
        """Run-the-repro-first + blocker protocol: shared content in both builds,
        the inline `!` login hint is CC-only, the separate-terminal hint Codex-only."""
        from installer.skill_builder import build_skill_md
        from installer.steps.codex_files import build_codex_skill_md

        codex_result = _codex_runtime_text("fix")
        assert "Read the COMPLETE output" in codex_result
        assert "Environment blocker protocol" in codex_result
        assert "separate terminal" in codex_result
        assert "! <command>" not in codex_result

        cc_result = _claude_runtime_text("fix")
        assert "Read the COMPLETE output" in cc_result
        assert "Environment blocker protocol" in cc_result
        assert "! <command>" in cc_result

    def test_spec_plan_codex_skill_strips_model_switch_mode(self) -> None:
        """Model Switching is CC-ONLY (Codex has no model switching).

        The three-way mode read in the planning skills must survive the CC
        build and be stripped from the Codex build (skill-sync parity rule).
        """
        from installer.skill_builder import build_skill_md
        from installer.steps.codex_files import build_codex_skill_md

        for skill in ("spec-plan", "spec-bugfix-plan"):
            codex_result = _codex_runtime_text(skill)
            assert "read_model_switch_mode" not in codex_result, skill
            assert "EnterPlanMode" not in codex_result, skill
            assert "ExitPlanMode" not in codex_result, skill

            cc_result = _claude_runtime_text(skill)
            assert "read_model_switch_mode" in cc_result, skill

    def test_build_codex_skill_drops_stop_hook_frontmatter(self) -> None:
        """`/build` registers a Stop hook in frontmatter; Codex must not inherit it.

        Codex resolves hooks from ~/.codex/hooks.json, not from a skill's
        frontmatter, and its SKILL.md carries only name + description. A leaked
        `hooks:` key would land in the body as prose the agent tries to follow.
        """
        from installer.skill_builder import build_skill_md
        from installer.steps.codex_files import build_codex_skill_md

        cc_result = build_skill_md(Path("pilot/skills/build"))
        assert 'spec_plan_validator.py" docs/builds Buildout' in cc_result

        codex_result = build_codex_skill_md(Path("pilot/skills/build"))
        assert "spec_plan_validator.py" not in codex_result
        assert "hooks:" not in codex_result

    def test_build_codex_skill_writes_buildouts_to_docs_builds(self) -> None:
        """The Buildout path must survive the Codex adaptation intact."""
        from installer.steps.codex_files import build_codex_skill_md

        codex_result = build_codex_skill_md(Path("pilot/skills/build"))
        assert "docs/builds/YYYY-MM-DD-<slug>.md" in codex_result
        assert "docs/plans/YYYY-MM-DD-<slug>.md" not in codex_result


class TestCodexRulesInstallation:
    def test_prefers_lean_codex_guidance_over_merged_global_rules(self, tmp_path: Path) -> None:
        codex_dir = tmp_path / ".codex"
        source = tmp_path / "source"
        guidance = source / "pilot" / "codex" / "AGENTS.md"
        guidance.parent.mkdir(parents=True)
        guidance.write_text("# Pilot for Codex\n\nExecute clear requests directly.\n")
        rules = source / "pilot" / "rules"
        rules.mkdir(parents=True)
        (rules / "legacy-core.md").write_text("FORCE A WORKFLOW CHOICE")

        step = CodexFilesStep()
        ctx = MagicMock()
        ctx.ui = None
        ctx.local_mode = True
        ctx.local_repo_dir = source

        with patch("installer.steps.codex_files._get_codex_config_dir", return_value=codex_dir):
            source_count = step._install_codex_rules(ctx)

        installed = (codex_dir / "AGENTS.md").read_text()
        assert "Execute clear requests directly." in installed
        assert "FORCE A WORKFLOW CHOICE" not in installed
        assert source_count == 1

    def test_distributed_install_uses_staged_lean_codex_guidance(self, tmp_path: Path) -> None:
        codex_dir = tmp_path / ".codex"
        guidance = tmp_path / ".pilot" / "codex" / "AGENTS.md"
        guidance.parent.mkdir(parents=True)
        guidance.write_text("# Pilot for Codex\n\nDirect work is the default.\n")
        rules = tmp_path / ".pilot" / "rules"
        rules.mkdir(parents=True)
        (rules / "legacy-core.md").write_text("FORCE A WORKFLOW CHOICE")

        step = CodexFilesStep()
        ctx = MagicMock()
        ctx.ui = None
        ctx.local_mode = False
        ctx.local_repo_dir = None

        with (
            patch("installer.steps.codex_files._get_codex_config_dir", return_value=codex_dir),
            patch("installer.steps.codex_files.Path.home", return_value=tmp_path),
        ):
            source_count = step._install_codex_rules(ctx)

        installed = (codex_dir / "AGENTS.md").read_text()
        assert "Direct work is the default." in installed
        assert "FORCE A WORKFLOW CHOICE" not in installed
        assert source_count == 1

    def test_creates_agents_md_with_markers(self, tmp_path: Path) -> None:
        codex_dir = tmp_path / ".codex"
        codex_dir.mkdir(parents=True)
        rules_dir = tmp_path / ".claude" / "rules"
        rules_dir.mkdir(parents=True)
        (rules_dir / "testing.md").write_text("## Testing\n\nTest rules here.")
        (rules_dir / "verification.md").write_text("## Verification\n\nVerify rules.")

        step = CodexFilesStep()
        ctx = MagicMock()
        ctx.ui = None
        ctx.local_mode = False

        with (
            patch("installer.steps.codex_files._get_codex_config_dir", return_value=codex_dir),
            patch("installer.steps.codex_files.Path.home", return_value=tmp_path),
        ):
            step._install_codex_rules(ctx)

        agents_md = codex_dir / "AGENTS.md"
        assert agents_md.exists()
        content = agents_md.read_text()
        assert "<!-- PILOT:START -->" in content
        assert "<!-- PILOT:END -->" in content
        assert "## Testing" in content
        assert "## Verification" in content

    def test_preserves_user_content_outside_markers(self, tmp_path: Path) -> None:
        codex_dir = tmp_path / ".codex"
        codex_dir.mkdir(parents=True)
        (codex_dir / "AGENTS.md").write_text(
            "# My Project\n\nCustom instructions.\n\n<!-- PILOT:START -->\nold pilot content\n<!-- PILOT:END -->\n\nMore user content."
        )
        rules_dir = tmp_path / ".claude" / "rules"
        rules_dir.mkdir(parents=True)
        (rules_dir / "testing.md").write_text("## Testing\n\nNew rules.")

        step = CodexFilesStep()
        ctx = MagicMock()
        ctx.ui = None
        ctx.local_mode = False

        with (
            patch("installer.steps.codex_files._get_codex_config_dir", return_value=codex_dir),
            patch("installer.steps.codex_files.Path.home", return_value=tmp_path),
        ):
            step._install_codex_rules(ctx)

        content = (codex_dir / "AGENTS.md").read_text()
        assert "# My Project" in content
        assert "Custom instructions." in content
        assert "More user content." in content
        assert "New rules." in content
        assert "old pilot content" not in content

    def test_adapts_invocation_syntax(self, tmp_path: Path) -> None:
        codex_dir = tmp_path / ".codex"
        codex_dir.mkdir(parents=True)
        rules_dir = tmp_path / ".claude" / "rules"
        rules_dir.mkdir(parents=True)
        (rules_dir / "workflow.md").write_text("## Workflow\n\nRun /spec to start. Use /fix for bugs.")

        step = CodexFilesStep()
        ctx = MagicMock()
        ctx.ui = None
        ctx.local_mode = False

        with (
            patch("installer.steps.codex_files._get_codex_config_dir", return_value=codex_dir),
            patch("installer.steps.codex_files.Path.home", return_value=tmp_path),
        ):
            step._install_codex_rules(ctx)

        content = (codex_dir / "AGENTS.md").read_text()
        assert "$spec" in content
        assert "$fix" in content

    def _install_rules(self, tmp_path: Path, files: dict[str, str]) -> Path:
        """Run the rule install against ``files`` and return the Codex config dir."""
        codex_dir = tmp_path / ".codex"
        codex_dir.mkdir(parents=True, exist_ok=True)
        rules_dir = tmp_path / ".claude" / "rules"
        rules_dir.mkdir(parents=True, exist_ok=True)
        for name, body in files.items():
            (rules_dir / name).write_text(body)

        step = CodexFilesStep()
        ctx = MagicMock()
        ctx.ui = None
        ctx.local_mode = False
        with (
            patch("installer.steps.codex_files._get_codex_config_dir", return_value=codex_dir),
            patch("installer.steps.codex_files.Path.home", return_value=tmp_path),
        ):
            step._install_codex_rules(ctx)
        return codex_dir

    def test_path_gated_rules_are_read_on_demand_not_inlined(self, tmp_path: Path) -> None:
        """Codex has no path-gating, so a stack rule inlined into AGENTS.md would put
        every stack's standards in front of every turn. They go to ~/.codex/rules/
        with only an index row in AGENTS.md; core rules stay inlined."""
        codex_dir = self._install_rules(
            tmp_path,
            {
                "standards-python.md": '---\npaths:\n  - "**/*.py"\n---\n\n## Python\n\nAlways use uv.',
                "testing.md": "## Testing\n\nCore rule body.",
            },
        )

        agents = (codex_dir / "AGENTS.md").read_text()
        assert "Core rule body." in agents
        assert "Always use uv." not in agents
        assert "**/*.py" in agents, "index must name the trigger so Codex knows when to read"
        assert str(codex_dir / "rules" / "standards-python.md") in agents

        written = (codex_dir / "rules" / "standards-python.md").read_text()
        assert "Always use uv." in written
        assert "paths:" not in written, "YAML frontmatter is Claude-only gating metadata"

    def test_unrelated_frontmatter_lists_are_not_treated_as_paths(self, tmp_path: Path) -> None:
        codex_dir = self._install_rules(
            tmp_path,
            {
                "tagged.md": "---\ntags:\n  - safety\n---\n\n## Tagged\n\nCore guidance.",
            },
        )

        agents = (codex_dir / "AGENTS.md").read_text()
        assert "Core guidance." in agents
        assert "`safety`" not in agents
        assert not (codex_dir / "rules" / "tagged.md").exists()

    def test_malformed_rule_frontmatter_fails_closed(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="invalid rule frontmatter"):
            self._install_rules(
                tmp_path,
                {"broken.md": "---\npaths:\n  - [broken\n---\n\n## Broken"},
            )

    def test_stale_stack_rule_removed_but_user_file_preserved(self, tmp_path: Path) -> None:
        """A renamed rule must not leave an orphan the index no longer points at,
        and the sidecar manifest is what keeps that cleanup off user files."""
        codex_dir = self._install_rules(tmp_path, {"standards-golang.md": '---\npaths:\n  - "**/*.go"\n---\n\n## Go'})
        (codex_dir / "rules" / "my-notes.md").write_text("mine")
        (tmp_path / ".claude" / "rules" / "standards-golang.md").unlink()

        codex_dir = self._install_rules(tmp_path, {"standards-rust.md": '---\npaths:\n  - "**/*.rs"\n---\n\n## Rust'})

        assert not (codex_dir / "rules" / "standards-golang.md").exists()
        assert (codex_dir / "rules" / "standards-rust.md").exists()
        assert (codex_dir / "rules" / "my-notes.md").read_text() == "mine"

    def test_stack_rule_bodies_are_codex_adapted(self, tmp_path: Path) -> None:
        """The on-demand files bypass the AGENTS.md merge, so they need the same
        CC-ONLY stripping the inlined rules get - otherwise Codex reads Claude-only
        instructions as if they applied to it."""
        codex_dir = self._install_rules(
            tmp_path,
            {
                "browser.md": (
                    '---\npaths:\n  - "**/*.tsx"\n---\n\n## Browser\n\n'
                    "<!-- CC-ONLY -->\nUse the Claude Chrome MCP.\n<!-- /CC-ONLY -->\n"
                    "Run /fix when it breaks."
                )
            },
        )

        written = (codex_dir / "rules" / "browser.md").read_text()
        assert "Use the Claude Chrome MCP." not in written
        assert "$fix" in written

    def test_preserves_unmanaged_same_name_stack_rule_across_updates(self, tmp_path: Path) -> None:
        codex_dir = tmp_path / ".codex"
        rules_dir = codex_dir / "rules"
        rules_dir.mkdir(parents=True)
        custom = rules_dir / "standards-python.md"
        custom.write_text("My Python project conventions.\n")
        files = {"standards-python.md": '---\npaths:\n  - "**/*.py"\n---\n\nPilot Python conventions.'}

        self._install_rules(tmp_path, files)
        self._install_rules(tmp_path, files)

        assert custom.read_text() == "My Python project conventions.\n"
        assert "standards-python.md" not in json.loads((rules_dir / ".pilot-rules.json").read_text())
        assert str(custom) in (codex_dir / "AGENTS.md").read_text()

    def test_cleans_last_managed_rule_without_touching_user_file(self, tmp_path: Path) -> None:
        codex_dir = self._install_rules(tmp_path, {"stack.md": '---\npaths:\n  - "**/*.py"\n---\n\nStack'})
        (codex_dir / "rules" / "mine.md").write_text("User guidance")
        (tmp_path / ".claude" / "rules" / "stack.md").unlink()

        self._install_rules(tmp_path, {"core.md": "General guidance"})

        assert not (codex_dir / "rules" / "stack.md").exists()
        assert (codex_dir / "rules" / "mine.md").read_text() == "User guidance"
        assert json.loads((codex_dir / "rules" / ".pilot-rules.json").read_text()) == []

    def test_rule_manifest_cannot_remove_files_outside_rule_directory(self, tmp_path: Path) -> None:
        codex_dir = tmp_path / ".codex"
        rules_dir = codex_dir / "rules"
        rules_dir.mkdir(parents=True)
        user_file = codex_dir / "user.md"
        user_file.write_text("Keep me")
        (rules_dir / ".pilot-rules.json").write_text(json.dumps(["../user.md", str(user_file), None]))

        self._install_rules(tmp_path, {"stack.md": '---\npaths:\n  - "**/*.py"\n---\n\nStack'})

        assert user_file.read_text() == "Keep me"

    def test_real_rules_generate_codex_safe_agents_md(self, tmp_path: Path) -> None:
        codex_dir = tmp_path / ".codex"
        codex_dir.mkdir(parents=True)
        rules_dir = tmp_path / ".claude" / "rules"
        shutil.copytree(Path("pilot/rules"), rules_dir, dirs_exist_ok=True)

        step = CodexFilesStep()
        ctx = MagicMock()
        ctx.ui = None
        ctx.local_mode = False

        with (
            patch("installer.steps.codex_files._get_codex_config_dir", return_value=codex_dir),
            patch("installer.steps.codex_files.Path.home", return_value=tmp_path),
        ):
            step._install_codex_rules(ctx)

        content = (codex_dir / "AGENTS.md").read_text()
        assert "## Codex Compatibility" in content
        assert "update_plan" in content
        assert "verify the generated artifacts directly" in content
        assert "agent/job ids" in content
        assert "session state" in content
        assert "| Start any new task | `codegraph_context(task=...)` — ALWAYS FIRST |" not in content
        assert "| Task orientation (FIRST on every task) | `codegraph_context` |" not in content
        # The CODEX-START variant of the CodeGraph guidance must survive unwrapping, and the
        # CC-ONLY variant must be stripped. Assert the load-bearing phrases rather than whole
        # sentences - the rules get reworded regularly, and a full-sentence match turns every
        # copy-edit into a red test without catching anything a phrase match misses.
        assert "skip CodeGraph for named paths, docs, rules, config, UI copy" in content
        preamble_end = "Skill invocation: use `$skill-name` (not `/skill-name`)."
        assert preamble_end in content
        rules_body = content.split(preamble_end, 1)[1]
        for forbidden in (
            "<!-- CC-ONLY -->",
            "<!-- CODEX-START",
            "AskUserQuestion",
            "TaskCreate",
            "TaskList",
            "TaskOutput",
            "Skill()",
            "Skill(",
            "Skill(skill=",
            "Skill('",
            "Agent(",
            "Task(",
            "suppressOutput",
            "hookSpecificOutput",
            "CLAUDE_CODE_TASK_LIST_ID",
            "CLAUDE_PROJECT_ROOT",
            "WebFetch",
            "WebSearch",
            "Bash(",
            "Read(",
            "Write(",
            "Edit(",
            "plain-text numbered options(",
            "plain-text numbered options tool",
            "/fix",
            "/prd",
            "SendMessage",
            "codex-companion.mjs",
            "codex:codex-rescue",
        ):
            assert forbidden not in rules_body
        assert re.search(r"(^|[^A-Za-z0-9_`])/(spec|fix|prd)([^A-Za-z0-9_/]|$)", rules_body) is None
        for forbidden in ("Run /spec", "Use /spec", "invoke /spec"):
            assert forbidden not in content


class TestCodexMcpConfiguration:
    def test_bundled_code_search_servers_use_managed_binaries_and_private_codegraph(self) -> None:
        """MCP startup reuses installed tools and keeps CodeGraph telemetry disabled."""
        repo_root = Path(__file__).resolve().parents[4]
        servers = json.loads((repo_root / "pilot" / ".mcp.json").read_text())["mcpServers"]

        assert servers["semble"] == {
            "type": "stdio",
            "command": "sh",
            "args": ["-c", 'exec "$HOME/.pilot/bin/semble"'],
        }
        assert servers["codegraph"]["env"]["CODEGRAPH_TELEMETRY"] == "0"

    def test_generates_toml_for_stdio_server(self) -> None:
        from installer.steps.codex_files import _mcp_json_to_toml

        mcp = {"mcpServers": {"context7": {"command": "npx", "args": ["-y", "@upstash/context7-mcp@2.2.4"]}}}
        toml = _mcp_json_to_toml(mcp)
        assert "[mcp_servers.context7]" in toml
        assert 'command = "npx"' in toml
        assert 'args = ["-y", "@upstash/context7-mcp@2.2.4"]' in toml

    def test_generates_toml_for_http_server(self) -> None:
        from installer.steps.codex_files import _mcp_json_to_toml

        mcp = {"mcpServers": {"grep-mcp": {"type": "http", "url": "https://mcp.grep.app"}}}
        toml = _mcp_json_to_toml(mcp)
        assert "[mcp_servers.grep-mcp]" in toml
        assert 'url = "https://mcp.grep.app"' in toml

    def test_generates_toml_with_env_vars(self) -> None:
        from installer.steps.codex_files import _mcp_json_to_toml

        mcp = {
            "mcpServers": {
                "web-search": {
                    "command": "npx",
                    "args": ["-y", "open-websearch"],
                    "env": {"MODE": "stdio", "ENGINE": "duckduckgo"},
                }
            }
        }
        toml = _mcp_json_to_toml(mcp)
        assert "[mcp_servers.web-search.env]" in toml
        assert 'MODE = "stdio"' in toml
        assert 'ENGINE = "duckduckgo"' in toml

    @staticmethod
    def _run_mcp_install(tmp_path: Path, existing_toml: str | None, mcp_servers: dict) -> tuple[str, MagicMock]:
        """Run _install_codex_mcp against a fixture config; return (final content, ctx)."""
        codex_dir = tmp_path / ".codex"
        codex_dir.mkdir(parents=True, exist_ok=True)
        if existing_toml is not None:
            (codex_dir / "config.toml").write_text(existing_toml)

        mcp_json = tmp_path / ".pilot" / ".mcp.json"
        mcp_json.parent.mkdir(parents=True, exist_ok=True)
        mcp_json.write_text(json.dumps({"mcpServers": mcp_servers}))

        step = CodexFilesStep()
        ctx = MagicMock()

        with (
            patch("installer.steps.codex_files._get_codex_config_dir", return_value=codex_dir),
            patch("installer.steps.codex_files.Path.home", return_value=tmp_path),
        ):
            step._install_codex_mcp(ctx)

        return (codex_dir / "config.toml").read_text(), ctx

    _CONTEXT7 = {"context7": {"command": "npx", "args": ["-y", "@upstash/context7-mcp@3.2.1"]}}

    @staticmethod
    def _run_mcp_install_with_baseline(
        tmp_path: Path, existing_toml: str, mcp_servers: dict, baseline: dict | None
    ) -> tuple[str, MagicMock]:
        """Same as _run_mcp_install but seeds the baseline of what Pilot last wrote."""
        codex_dir = tmp_path / ".codex"
        codex_dir.mkdir(parents=True, exist_ok=True)
        (codex_dir / "config.toml").write_text(existing_toml)
        if baseline is not None:
            (codex_dir / MCP_BASELINE_FILE).write_text(json.dumps(baseline))

        mcp_json = tmp_path / ".pilot" / ".mcp.json"
        mcp_json.parent.mkdir(parents=True, exist_ok=True)
        mcp_json.write_text(json.dumps({"mcpServers": mcp_servers}))

        step = CodexFilesStep()
        ctx = MagicMock()
        with (
            patch("installer.steps.codex_files._get_codex_config_dir", return_value=codex_dir),
            patch("installer.steps.codex_files.Path.home", return_value=tmp_path),
        ):
            step._install_codex_mcp(ctx)
        return (codex_dir / "config.toml").read_text(), ctx

    def test_user_modified_server_is_preserved_not_overwritten(self, tmp_path: Path) -> None:
        """The reported bug: Codex clobbered a user's edited semble entry that the
        Claude path preserved. Baseline says Pilot wrote the bare command; the user
        has since switched it to a pinned uvx launch."""
        existing = '[mcp_servers.semble]\ncommand = "uvx"\nargs = ["--from", "semble[mcp]==0.5.5", "semble"]\n'
        config, ctx = self._run_mcp_install_with_baseline(
            tmp_path,
            existing,
            {"semble": {"command": "semble"}},
            baseline={"semble": {"command": "semble"}},
        )
        assert 'args = ["--from", "semble[mcp]==0.5.5", "semble"]' in config, config
        assert config.count("[mcp_servers.semble]") == 1, config
        assert any("modified by the user" in str(c) for c in ctx.ui.warning.call_args_list)

    def test_unmodified_server_is_updated_silently(self, tmp_path: Path) -> None:
        """A table still identical to the baseline is Pilot's own — take the update."""
        existing = '[mcp_servers.semble]\ncommand = "semble"\n'
        config, ctx = self._run_mcp_install_with_baseline(
            tmp_path,
            existing,
            {"semble": {"command": "uvx", "args": ["--from", "semble[mcp]==0.5.5", "semble"]}},
            baseline={"semble": {"command": "semble"}},
        )
        assert 'args = ["--from", "semble[mcp]==0.5.5", "semble"]' in config, config
        assert not any("modified by the user" in str(c) for c in ctx.ui.warning.call_args_list)

    def test_known_legacy_semble_launcher_is_migrated(self, tmp_path: Path) -> None:
        """The former Pilot default must not become a permanent user override
        when the baseline was created only after Codex had stripped markers."""
        existing = (
            '[mcp_servers.semble]\ncommand = "uvx"\nargs = ["--no-config", "--from", "semble[mcp]==0.5.5", "semble"]\n'
        )
        config, ctx = self._run_mcp_install_with_baseline(
            tmp_path,
            existing,
            {"semble": {"command": "sh", "args": ["-c", 'exec "$HOME/.pilot/bin/semble"']}},
            baseline={"semble": {"command": "sh", "args": ["-c", 'exec "$HOME/.pilot/bin/semble"']}},
        )
        assert 'command = "sh"' in config, config
        assert 'exec \\"$HOME/.pilot/bin/semble\\"' in config, config
        assert 'command = "uvx"' not in config, config
        assert not any("modified by the user" in str(c) for c in ctx.ui.warning.call_args_list)

    def test_baseline_written_after_install(self, tmp_path: Path) -> None:
        """Without a persisted baseline the next run is blind again."""
        self._run_mcp_install_with_baseline(tmp_path, "", {"semble": {"command": "semble"}}, baseline=None)
        written = json.loads((tmp_path / ".codex" / MCP_BASELINE_FILE).read_text())
        assert written == {"semble": {"command": "semble"}}

    def test_installs_mcp_to_codex_config_toml(self, tmp_path: Path) -> None:
        config, _ = self._run_mcp_install(tmp_path, None, {"test-server": {"command": "echo", "args": ["hello"]}})
        assert "[mcp_servers.test-server]" in config

    def test_preserves_user_mcp_entries(self, tmp_path: Path) -> None:
        config, _ = self._run_mcp_install(
            tmp_path,
            '[mcp_servers.my-server]\ncommand = "my-cmd"\n\n',
            {"pilot-server": {"command": "echo", "args": ["hello"]}},
        )
        assert "my-server" in config
        assert "pilot-server" in config

    def test_silently_rehomes_pilot_tables_after_an_external_comment_strip(self, tmp_path: Path) -> None:
        """Codex CLI owns [projects.*] / [hooks.state.*] / [marketplaces.*] in the
        SAME config.toml and rewrites it through a TOML serializer, which drops
        every comment -- including Pilot's marker pair, since markers ARE
        comments. Pilot's own [mcp_servers.*] tables survive as data, so the next
        install finds them "outside the block". Re-homing them is correct; warning
        the user that their custom server is being replaced is not, because the
        content is byte-identical to what Pilot is about to write."""
        content, ctx = self._run_mcp_install(
            tmp_path,
            'approval_policy = "never"\n'
            "\n"
            "[mcp_servers.context7]\n"
            'command = "npx"\n'
            'args = ["-y", "@upstash/context7-mcp@3.2.1"]\n',
            self._CONTEXT7,
        )
        assert content.count("[mcp_servers.context7]") == 1
        assert content.count("# --- pilot-shell managed MCP servers ---") == 1
        ctx.ui.warning.assert_not_called()

    def test_still_warns_when_the_replaced_table_differs(self, tmp_path: Path) -> None:
        """A table under a Pilot-managed name whose content is NOT what Pilot
        writes is the user's -- replacing it loses their config, so say so."""
        _, ctx = self._run_mcp_install(
            tmp_path,
            '[mcp_servers.context7]\ncommand = "/opt/homebrew/bin/my-own-context7"\nargs = ["--port", "9999"]\n',
            self._CONTEXT7,
        )
        ctx.ui.warning.assert_called_once()
        assert "context7" in ctx.ui.warning.call_args[0][0]

    def test_names_only_the_edited_server_when_the_file_holds_a_duplicate(self, tmp_path: Path) -> None:
        """A hand-added table alongside an intact managed block is a duplicate,
        so the file as a whole will not parse. Judging each removed table on its
        own keeps the warning to the one server actually being overwritten,
        instead of listing every server Pilot ships."""
        _, ctx = self._run_mcp_install(
            tmp_path,
            "[mcp_servers.context7]\n"
            'command = "/opt/homebrew/bin/my-own-context7"\n'
            "\n"
            "# --- pilot-shell managed MCP servers ---\n"
            "[mcp_servers.context7]\n"
            'command = "npx"\n'
            'args = ["-y", "@upstash/context7-mcp@3.2.1"]\n'
            "\n"
            "[mcp_servers.semble]\n"
            'command = "semble"\n'
            'args = ["mcp"]\n'
            "# --- end pilot-shell managed MCP servers ---\n",
            {**self._CONTEXT7, "semble": {"command": "semble", "args": ["mcp"]}},
        )
        ctx.ui.warning.assert_called_once()
        message = ctx.ui.warning.call_args[0][0]
        assert "context7" in message
        assert "semble" not in message

    def test_heals_orphaned_mcp_block_missing_start_marker(self, tmp_path: Path) -> None:
        """A prior write that lost its start marker leaves [mcp_servers.context7]
        as plain (unmarked) content followed by a lone end marker. Appending a
        fresh managed block on top of that -- instead of recognizing and
        removing the orphaned table -- declares [mcp_servers.context7] a
        second time: a duplicate key/table that aborts Codex startup."""
        content, _ = self._run_mcp_install(
            tmp_path,
            'approval_policy = "never"\n'
            "\n"
            "[mcp_servers.context7]\n"
            'command = "npx"\n'
            'args = ["-y", "@upstash/context7-mcp@3.2.1"]\n'
            "\n"
            "[mcp_servers.herd]\n"
            'command = "php"\n'
            'args = ["/Applications/Herd.app/Contents/Resources/herd-mcp.phar"]\n'
            "\n"
            "# --- end pilot-shell managed MCP servers ---\n",
            self._CONTEXT7,
        )
        assert content.count("[mcp_servers.context7]") == 1
        assert "[mcp_servers.herd]" in content  # non-pilot entry preserved
        # the lone END marker must be gone; only the freshly appended pair remains
        assert content.count("# --- end pilot-shell managed MCP servers ---") == 1
        assert content.count("# --- pilot-shell managed MCP servers ---") == 1
        tomllib.loads(content)  # must not raise: duplicate key/table = Codex startup crash

    def test_orphaned_start_marker_does_not_swallow_user_content(self, tmp_path: Path) -> None:
        """An orphaned START marker must not greedily pair with a LATER region's
        END marker -- that span contains user content."""
        content, _ = self._run_mcp_install(
            tmp_path,
            "# --- pilot-shell managed MCP servers ---\n"
            "\n"
            "[mcp_servers.usercustom]\n"
            'command = "my-cmd"\n'
            "\n"
            "# --- pilot-shell managed MCP servers ---\n"
            "[mcp_servers.context7]\n"
            'command = "npx"\n'
            "# --- end pilot-shell managed MCP servers ---\n",
            self._CONTEXT7,
        )
        assert "[mcp_servers.usercustom]" in content
        assert content.count("[mcp_servers.context7]") == 1
        tomllib.loads(content)

    def test_heals_quoted_managed_table_name(self, tmp_path: Path) -> None:
        """[mcp_servers."context7"] is the same TOML table as the bare spelling;
        missing it would re-declare the table and abort Codex startup."""
        content, _ = self._run_mcp_install(
            tmp_path,
            '[mcp_servers."context7"]\ncommand = "old"\n',
            self._CONTEXT7,
        )
        parsed = tomllib.loads(content)
        assert parsed["mcp_servers"]["context7"]["command"] == "npx"

    def test_heals_managed_table_with_nested_array(self, tmp_path: Path) -> None:
        """A continuation line of a multi-line array starting with '[' must not
        truncate the table removal (dangling fragments fail the TOML gate)."""
        content, _ = self._run_mcp_install(
            tmp_path,
            "[mcp_servers.context7]\narg_matrix = [\n    [1, 2],\n    [3, 4],\n]\n",
            self._CONTEXT7,
        )
        assert content.count("[mcp_servers.context7]") == 1
        parsed = tomllib.loads(content)
        assert "arg_matrix" not in parsed["mcp_servers"]["context7"]

    def test_preserves_multiline_string_values(self, tmp_path: Path) -> None:
        """User values must survive byte-for-byte -- a global newline collapse
        previously corrupted multi-line strings containing blank lines."""
        existing = 'banner = """line1\n\n\n\nline2"""\n'
        content, _ = self._run_mcp_install(tmp_path, existing, self._CONTEXT7)
        assert tomllib.loads(content)["banner"] == tomllib.loads(existing)["banner"]

    def test_removes_non_env_subtables_of_managed_server(self, tmp_path: Path) -> None:
        """Leftover sub-tables of a managed server (.headers etc.) must not
        graft stale keys onto the freshly written server."""
        content, _ = self._run_mcp_install(
            tmp_path,
            '[mcp_servers.context7]\ncommand = "old"\n[mcp_servers.context7.headers]\nAuthorization = "Bearer stale"\n',
            self._CONTEXT7,
        )
        parsed = tomllib.loads(content)
        assert "headers" not in parsed["mcp_servers"]["context7"]

    def test_heals_marker_concatenated_with_header(self, tmp_path: Path) -> None:
        """The historical newline-loss corruption (marker glued to the next
        table header on one line) must still be recognized as a marker."""
        content, _ = self._run_mcp_install(
            tmp_path,
            'approval_policy = "never"\n'
            "# --- pilot-shell managed MCP servers ---[mcp_servers.context7]\n"
            'command = "npx"\n'
            "# --- end pilot-shell managed MCP servers ---\n",
            self._CONTEXT7,
        )
        parsed = tomllib.loads(content)
        assert "command" not in parsed  # stranded keys must not leak to top level
        assert content.count("[mcp_servers.context7]") == 1

    def test_warns_when_dropping_unmarked_managed_table(self, tmp_path: Path) -> None:
        """Deleting content the user may regard as their own must be surfaced."""
        _, ctx = self._run_mcp_install(
            tmp_path,
            '[mcp_servers.context7]\ncommand = "my-own-copy"\n',
            self._CONTEXT7,
        )
        warnings = [str(c.args[0]) for c in ctx.ui.warning.call_args_list]
        assert any("context7" in w for w in warnings)

    def test_reports_existing_invalid_config(self, tmp_path: Path) -> None:
        """A pre-existing user syntax error must be attributed to the existing
        file (actionable), not to Pilot's generated config."""
        with pytest.raises(_TomlStructureError, match="invalid TOML and could not be healed"):
            self._run_mcp_install(tmp_path, "key =\n", self._CONTEXT7)


class TestAdaptInvocationSyntax:
    def test_strips_cc_only_blocks(self) -> None:
        from installer.steps.codex_files import _adapt_invocation_syntax

        content = "Before.\n<!-- CC-ONLY -->\nCC-specific content here.\n<!-- /CC-ONLY -->\nAfter."
        result = _adapt_invocation_syntax(content)
        assert "CC-specific content" not in result
        assert "Before." in result
        assert "After." in result

    def test_shipped_rules_never_leak_claude_only_tool_names_to_codex(self) -> None:
        """No adapted rule body may name a Claude-only tool.

        `ToolSearch` does not exist in Codex (it is `tool_search`). Naming it in
        SHARED rule text (outside a CC-ONLY block) survives adaptation and sends
        every Codex install toward a nonexistent tool. Guards the real rule files,
        not a fixture, so a future edit to any of them trips this.
        """
        from installer.steps.codex_files import _adapt_invocation_syntax

        rules_dir = Path(__file__).parents[4] / "pilot" / "rules"
        assert rules_dir.is_dir(), f"rules source not found at {rules_dir}"

        offenders: list[str] = []
        for rule in sorted(rules_dir.glob("*.md")):
            adapted = _adapt_invocation_syntax(rule.read_text(encoding="utf-8"))
            for claude_only in ("ToolSearch", "AskUserQuestion("):
                if claude_only in adapted:
                    offenders.append(f"{rule.name}: {claude_only}")

        assert not offenders, (
            "Claude-only tool names survived Codex adaptation - move them inside a "
            f"<!-- CC-ONLY --> block or make them tool-neutral: {offenders}"
        )

    def test_unwraps_codex_blocks(self) -> None:
        from installer.steps.codex_files import _adapt_invocation_syntax

        content = "Before.\n<!-- CODEX-START\nCodex alternative here.\nCODEX-END -->\nAfter."
        result = _adapt_invocation_syntax(content)
        assert "Codex alternative here." in result
        assert "CODEX-START" not in result
        assert "CODEX-END" not in result
        assert "Before." in result
        assert "After." in result

    def test_real_task_workflow_codex_executes_clear_requests_directly(self) -> None:
        """Cross-cutting scope must not turn into a workflow-choice gate."""
        from installer.steps.codex_files import _adapt_invocation_syntax

        source = Path("pilot/rules/task-and-workflow.md").read_text(encoding="utf-8")
        result = _adapt_invocation_syntax(source)

        assert "A clear user request is authorization to execute" in result
        assert "Size, file count, architectural breadth, and cross-cutting scope" in result
        assert "do not trigger a workflow question" in result
        assert 'mentions like "make it good"' in result
        assert "Ask which workflow" not in result
        assert "offer both structured workflows" not in result
        assert "suggest `$build`" not in result

    def test_real_task_workflow_codex_leaves_agent_topology_autonomous(self) -> None:
        from installer.steps.codex_files import _adapt_invocation_syntax

        source = Path("pilot/rules/task-and-workflow.md").read_text(encoding="utf-8")
        result = _adapt_invocation_syntax(source)

        assert "The active agent owns the execution topology" in result
        assert "Never stop a running task to ask the user for permission" in result
        assert "Give each agent explicit ownership" in result
        assert "Do not redo a completed agent's exploration" in result
        assert "Do not assume Claude Code's sub-agent tools exist" in result

    def test_cc_only_stripped_and_codex_revealed(self) -> None:
        from installer.steps.codex_files import _adapt_invocation_syntax

        content = (
            "Shared.\n"
            "<!-- CC-ONLY -->\nLaunch subagent.\n<!-- /CC-ONLY -->\n"
            "<!-- CODEX-START\nSkip reviewers (Codex).\nCODEX-END -->\n"
            "More shared."
        )
        result = _adapt_invocation_syntax(content)
        assert "Launch subagent" not in result
        assert "Skip reviewers (Codex)." in result
        assert "Shared." in result
        assert "More shared." in result

    def test_transforms_skill_calls(self) -> None:
        from installer.steps.codex_files import _adapt_invocation_syntax

        content = "Then invoke Skill(skill='spec-implement', args='docs/plans/plan.md')"
        result = _adapt_invocation_syntax(content)
        assert "the `$spec-implement` skill instructions with arguments: `docs/plans/plan.md`" in result
        assert "Skill(" not in result

    def test_transforms_skill_calls_without_args(self) -> None:
        from installer.steps.codex_files import _adapt_invocation_syntax

        content = "Skill(skill='spec-verify')"
        result = _adapt_invocation_syntax(content)
        assert "the `$spec-verify` skill instructions" in result
        assert "Skill(" not in result

    def test_transforms_skill_calls_with_single_quotes(self) -> None:
        from installer.steps.codex_files import _adapt_invocation_syntax

        content = """Skill('spec', args='implement feature — PRD: docs/prd/file.md')"""
        result = _adapt_invocation_syntax(content)
        assert "$spec" in result
        assert "Skill(" not in result

    def test_transforms_ask_user_question_blocks(self) -> None:
        from installer.steps.codex_files import _adapt_invocation_syntax

        content = """AskUserQuestion(
  question="Ready?",
  options=["Yes", "No"]
)"""
        result = _adapt_invocation_syntax(content)
        assert "runtime exposes and permits" in result
        assert "otherwise ask in plain text" in result
        assert 'question="Ready?"' in result
        assert 'options=["Yes", "No"]' in result
        assert "AskUserQuestion" not in result
        assert "plain-text numbered options(" not in result

    def test_real_spec_skill_uses_codex_phase_handoff(self) -> None:
        from installer.steps.codex_files import build_codex_skill_md

        result = build_codex_skill_md(Path("pilot/skills/spec"))
        assert "Codex has no callable phase-dispatch tool" in result
        assert "continue immediately with the `$spec-plan` skill instructions" in result
        assert (
            "sub-agents (spec-review, changes-review), and the Codex companion reviewer are not available" not in result
        )
        assert "Native `spec-review` and `changes-review` run as managed Codex custom agents" in result
        assert (
            "The current running session may not expose newly generated skills or agent types until the next install or SessionStart sync"
            in result
        )
        assert "Skill(skill=" not in result
        assert "Skill('" not in result

    def test_real_spec_plan_codex_uses_native_review_agent(self) -> None:
        from installer.steps.codex_files import build_codex_skill_md

        result = _codex_runtime_text("spec-plan")
        assert "review agents are not available in Codex CLI" not in result
        assert "Skip automated plan review agents" not in result
        assert "multi_agent_v1" not in result
        assert "spawn-agent tool exposed in the current Codex tool schema" in result
        assert "wait mechanism exposed in the current Codex tool schema" in result
        assert 'agent_type="spec-review"' in result
        assert "PILOT_SPEC_REVIEW_ENABLED" in result
        assert "PILOT_CODEX_SPEC_REVIEW_ENABLED" not in result

    def test_real_spec_verify_codex_uses_native_review_agent(self) -> None:
        from installer.steps.codex_files import build_codex_skill_md

        result = _codex_runtime_text("spec-verify")
        assert "No reviewer agents in Codex" not in result
        assert "Skip automated code review agents" not in result
        assert "reviewer agents were launched (not available in Codex CLI)" not in result
        assert "multi_agent_v1" not in result
        assert "spawn-agent tool exposed in the current Codex tool schema" in result
        assert "wait mechanism exposed in the current Codex tool schema" in result
        assert 'agent_type="changes-review"' in result
        assert "review-state-protocol.md" in result
        assert "atomically persist `CHANGES_REVIEW_AGENT_ID`" in result
        assert "native_agent_id" in result
        assert "verifying this plan and lane identity" in result
        assert "Do not silently skip review" in result
        assert "completed final JSON response" in result
        assert "Do not sweep findings files" in result
        assert "Reviewable file preflight" in result
        assert "Broad-check failure classification" in result
        assert "Final-status-only findings are not implementation fixes" in result
        assert "PILOT_CHANGES_REVIEW_ENABLED" in result
        assert "PILOT_CODEX_CHANGES_REVIEW_ENABLED" not in result

    @pytest.mark.parametrize("skill_name", ["build", "spec-plan", "spec-verify", "fix"])
    def test_codex_review_skills_never_emit_stale_agent_namespace(self, skill_name: str) -> None:
        from installer.steps.codex_files import build_codex_skill_md

        result = build_codex_skill_md(Path("pilot/skills") / skill_name)
        assert "multi_agent_v1" not in result

    @pytest.mark.parametrize("skill_name", ["build", "spec", "fix", "prd", "investigate", "cleanup"])
    def test_codex_structured_workflows_are_explicit_invocation_only(self, skill_name: str) -> None:
        from installer.steps.codex_files import build_codex_skill_openai_yaml

        metadata = yaml.safe_load(build_codex_skill_openai_yaml(Path("pilot/skills") / skill_name))
        assert not metadata["interface"]["short_description"].casefold().startswith("use only")
        assert metadata["policy"]["allow_implicit_invocation"] is False

    def test_codex_fix_keeps_ownership_of_complex_defects(self) -> None:
        result = _codex_runtime_text("fix")

        for forbidden in (
            "re-invoke with $spec",
            "hand off to $spec",
            "bail out to $spec",
            "bail to $spec",
            "candidate for $spec",
        ):
            assert forbidden not in result
        assert "`$fix` never redirects because the defect is multi-component" in result
        assert "STAY WITH THE DEFECT" in result

        manifest = json.loads((Path("pilot/skills/fix") / "manifest.json").read_text())
        evals = json.loads((Path("pilot/skills/fix") / manifest["evals"]).read_text())
        assert [case["name"] for case in evals["evals"]] == [
            "architectural-preview-contract-stays-in-fix",
            "failed-attempt-challenges-hypothesis",
            "low-confidence-ui-defect-deepens-investigation",
        ]
        assert all(len(case["expectations"]) == 3 for case in evals["evals"])

    @pytest.mark.parametrize("skill_name", ["build", "spec-implement", "spec-bugfix-verify"])
    def test_codex_workflow_skills_leave_delegation_to_the_agent(self, skill_name: str) -> None:
        result = _codex_runtime_text(skill_name)
        assert "autonom" in result.lower()
        assert "permission" in result.lower()
        assert "NO sub-agents" not in result
        assert "No delegated agents inside the loop" not in result

    def test_codex_create_skill_uses_available_agent_and_web_tools(self) -> None:
        from installer.steps.codex_files import build_codex_skill_md

        result = _codex_runtime_text("create-skill")
        assert "Subagent and web tools are not available in Codex" not in result
        assert "Codex does not support parallel subagents" not in result
        assert "Tool absence is a reported validation gap" in result

    def test_real_spec_verify_codex_strips_inline_code_review_blocks(self) -> None:
        """The CC-only inline /code-review flow (Skill invocation + Plan
        Compliance & Goal-Truth Audit) must be fully stripped from the Codex
        build, and stripping the indented CC-ONLY block inside the Step 2
        checklist must not corrupt the numbered list (item 6 stays at
        column 0)."""
        from installer.steps.codex_files import build_codex_skill_md

        result = _codex_runtime_text("spec-verify")
        assert "code-review" not in result.replace("changes-review", "")
        assert "Plan Compliance & Goal-Truth Audit" not in result
        assert "\n6. **Build**" in result
        assert "\n   6. **Build**" not in result

    @pytest.mark.parametrize(
        "skill_name",
        [
            "spec",
            "spec-plan",
            "spec-bugfix-plan",
            "spec-implement",
            "spec-verify",
            "spec-bugfix-verify",
            "prd",
            "fix",
            "build",
            "benchmark",
            "setup-rules",
            "create-skill",
        ],
    )
    def test_real_codex_skills_do_not_expose_claude_tool_calls(self, skill_name: str) -> None:
        from installer.steps.codex_files import build_codex_skill_md

        result = build_codex_skill_md(Path("pilot/skills") / skill_name)
        assert "<!-- CC-ONLY -->" not in result
        assert "<!-- CODEX-START" not in result
        for forbidden in (
            "AskUserQuestion",
            "TaskList",
            "TaskCreate",
            "TaskOutput",
            "Skill()",
            "Skill(",
            "Agent(",
            "Task(",
            "suppressOutput",
            "hookSpecificOutput",
            "CLAUDE_CODE_TASK_LIST_ID",
            "CLAUDE_PROJECT_ROOT",
            "WebFetch",
            "WebSearch",
            "ToolSearch",
            "Bash(",
            "Read(",
            "Write(",
            "Edit(",
            "plain-text numbered options(",
            "plain-text numbered options tool",
            "SendMessage",
            "codex-companion.mjs",
            "codex:codex-rescue",
        ):
            assert forbidden not in result
        assert (
            re.search(
                r"(^|[^A-Za-z0-9_`])/(spec|fix|prd|build|setup-rules|create-skill|benchmark)([^A-Za-z0-9_/]|$)", result
            )
            is None
        )

    def test_multiline_cc_only_block(self) -> None:
        from installer.steps.codex_files import _adapt_invocation_syntax

        content = "Step 1.\n<!-- CC-ONLY -->\nLine 1.\nLine 2.\nLine 3.\n<!-- /CC-ONLY -->\nStep 2."
        result = _adapt_invocation_syntax(content)
        assert "Line 1" not in result
        assert "Line 2" not in result
        assert "Step 1." in result
        assert "Step 2." in result

    def test_preserves_user_hooks_in_existing_codex_hooks(self, tmp_path: Path) -> None:
        codex_dir = tmp_path / ".codex"
        codex_dir.mkdir(parents=True)

        existing = {
            "hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "echo user-hook"}]}]}
        }
        (codex_dir / "hooks.json").write_text(json.dumps(existing))

        incoming = {"hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "echo pilot"}]}]}}

        step = CodexFilesStep()
        step._merge_codex_hooks(codex_dir, incoming)

        result = json.loads((codex_dir / "hooks.json").read_text())
        assert "SessionStart" in result["hooks"]
        assert "PreToolUse" in result["hooks"]
        assert result["hooks"]["PreToolUse"][0]["hooks"][0]["command"] == "echo user-hook"

    def test_preserves_user_hook_stored_under_pilot_directory(self, tmp_path: Path) -> None:
        codex_dir = tmp_path / ".codex"
        codex_dir.mkdir(parents=True)
        user_entry = {
            "matcher": "Bash",
            "hooks": [{"type": "command", "command": 'python "$HOME/.pilot/custom/my-hook.py"'}],
        }
        (codex_dir / "hooks.json").write_text(json.dumps({"hooks": {"PreToolUse": [user_entry]}}))
        incoming = {
            "hooks": {
                "SessionStart": [{"hooks": [{"type": "command", "command": 'python "$HOME/.pilot/hooks/start.py"'}]}]
            }
        }

        CodexFilesStep()._merge_codex_hooks(codex_dir, incoming)

        merged = json.loads((codex_dir / "hooks.json").read_text())
        assert user_entry in merged["hooks"]["PreToolUse"]

    def test_replaces_only_entries_recorded_in_codex_hook_baseline(self, tmp_path: Path) -> None:
        codex_dir = tmp_path / ".codex"
        codex_dir.mkdir(parents=True)
        old = {"hooks": [{"type": "command", "command": "python OLD_PILOT_STOP"}]}
        user = {"hooks": [{"type": "command", "command": "echo user"}]}
        new = {"hooks": [{"type": "command", "command": "python NEW_PILOT_STOP"}]}
        (codex_dir / "hooks.json").write_text(json.dumps({"hooks": {"Stop": [old, user]}}))
        (codex_dir / ".pilot-hooks-baseline.json").write_text(json.dumps({"Stop": [old]}))

        CodexFilesStep()._merge_codex_hooks(codex_dir, {"hooks": {"Stop": [new]}})

        merged = json.loads((codex_dir / "hooks.json").read_text())
        assert merged["hooks"]["Stop"] == [new, user]
        assert json.loads((codex_dir / ".pilot-hooks-baseline.json").read_text()) == {"Stop": [new]}


class TestTomlValidation:
    def test_valid_toml_passes(self) -> None:
        content = (
            'approval_policy = "never"\n'
            "\n"
            "[notice]\n"
            "hide_full_access_warning = true\n"
            "\n"
            "[sandbox_workspace_write]\n"
            "network_access = true\n"
        )
        _validate_toml_structure(content)

    def test_section_concatenated_on_value_line(self) -> None:
        content = "[notice]\nhide_full_access_warning = true[sandbox_workspace_write]\nnetwork_access = true\n"
        with pytest.raises(_TomlStructureError, match="section header not at start of line"):
            _validate_toml_structure(content)

    def test_section_concatenated_on_key_line(self) -> None:
        content = "bypass_hook_trust = true[notice]\nhide_full_access_warning = true\n"
        with pytest.raises(_TomlStructureError, match="line 1"):
            _validate_toml_structure(content)

    def test_exact_regression_notice_sandbox(self) -> None:
        """Exact reproduction of the real-world bug: hide_full_access_warning = true[sandbox_workspace_write]."""
        content = "[notice]\nhide_full_access_warning = true[sandbox_workspace_write]\nnetwork_access = true\n"
        with pytest.raises(_TomlStructureError):
            _validate_toml_structure(content)

    def test_comments_and_blanks_ignored(self) -> None:
        content = "# comment with [fake] section\n\n[real]\nkey = true\n"
        _validate_toml_structure(content)

    def test_managed_marker_comments_ignored(self) -> None:
        content = (
            "# --- pilot-shell managed MCP servers ---\n"
            "[mcp_servers.codegraph]\n"
            'command = "codegraph"\n'
            "# --- end pilot-shell managed MCP servers ---\n"
        )
        _validate_toml_structure(content)

    def test_brackets_inside_quoted_values_ignored(self) -> None:
        content = 'args = ["--from", "semble[mcp]", "semble"]\n'
        _validate_toml_structure(content)

    def test_array_values_with_brackets_ignored(self) -> None:
        content = '[mcp_servers.semble]\ncommand = "uvx"\nargs = ["--from", "semble[mcp]", "semble"]\n'
        _validate_toml_structure(content)

    def test_dotted_and_quoted_section_names(self) -> None:
        content = '[hooks.state."/path/to/file:event:0:0"]\ntrusted_hash = "sha256:abc"\n'
        _validate_toml_structure(content)


class TestEnsureSectionKeys:
    def test_creates_section_when_missing(self) -> None:
        content = 'approval_policy = "never"\n'
        result, changed = _ensure_section_keys(content, "features", {"memories": "true", "hooks": "true"})
        assert changed is True
        assert "[features]" in result
        assert "memories = true" in result
        assert "hooks = true" in result
        _validate_toml_structure(result)

    def test_adds_missing_keys_to_existing_section(self) -> None:
        content = "[features]\nmemories = true\n\n[notice]\nhide = true\n"
        result, changed = _ensure_section_keys(content, "features", {"hooks": "true", "memories": "true"})
        assert changed is True
        assert "hooks = true" in result
        assert result.count("memories") == 1  # not duplicated

    def test_noop_when_all_keys_present(self) -> None:
        content = "[features]\nmemories = true\nhooks = true\n"
        result, changed = _ensure_section_keys(content, "features", {"memories": "true", "hooks": "true"})
        assert changed is False
        assert result == content


class TestTuiStatuslineConfiguration:
    def test_installs_tui_statusline_on_fresh_config(self, tmp_path: Path) -> None:
        codex_dir = tmp_path / ".codex"
        codex_dir.mkdir(parents=True)
        config = codex_dir / "config.toml"
        config.write_text('approval_policy = "never"\n')

        step = CodexFilesStep()
        ctx = MagicMock()
        ctx.ui = None
        with (
            patch("installer.steps.codex_files._get_codex_config_dir", return_value=codex_dir),
            patch("installer.steps.codex_files.Path.home", return_value=tmp_path),
        ):
            step._install_codex_config(ctx)

        result = config.read_text()
        assert "[tui]" in result
        assert "status_line" in result
        assert "project-name" in result
        assert "model-with-reasoning" in result
        assert "status_line_use_colors = true" in result
        _validate_toml_structure(result)

    def test_preserves_existing_tui_settings(self, tmp_path: Path) -> None:
        codex_dir = tmp_path / ".codex"
        codex_dir.mkdir(parents=True)
        config = codex_dir / "config.toml"
        config.write_text(
            'approval_policy = "never"\n'
            "\n"
            "[tui]\n"
            'status_line = ["project-name", "run-state"]\n'
            "status_line_use_colors = false\n"
        )

        step = CodexFilesStep()
        ctx = MagicMock()
        ctx.ui = None
        with (
            patch("installer.steps.codex_files._get_codex_config_dir", return_value=codex_dir),
            patch("installer.steps.codex_files.Path.home", return_value=tmp_path),
        ):
            step._install_codex_config(ctx)

        result = config.read_text()
        assert 'status_line = ["project-name", "run-state"]' in result
        assert "status_line_use_colors = false" in result
        assert result.count("status_line =") == 1


class TestDeprecatedKeyRemoval:
    def test_removes_bypass_hook_trust(self, tmp_path: Path) -> None:
        codex_dir = tmp_path / ".codex"
        codex_dir.mkdir(parents=True)
        config = codex_dir / "config.toml"
        config.write_text('approval_policy = "never"\nbypass_hook_trust = true\n\n[features]\nhooks = true\n')

        step = CodexFilesStep()
        ctx = MagicMock()
        ctx.ui = None
        with (
            patch("installer.steps.codex_files._get_codex_config_dir", return_value=codex_dir),
            patch("installer.steps.codex_files.Path.home", return_value=tmp_path),
        ):
            step._install_codex_config(ctx)

        result = config.read_text()
        assert "bypass_hook_trust" not in result
        assert "hooks = true" in result
        assert "undo" not in result
        assert "mentions_v2" not in result
        assert "tool_search" not in result
        assert "apps" not in result


class TestNativeWarningsPreserved:
    def test_does_not_suppress_codex_warnings_on_fresh_config(self, tmp_path: Path) -> None:
        codex_dir = tmp_path / ".codex"
        codex_dir.mkdir(parents=True)
        config = codex_dir / "config.toml"
        config.write_text('approval_policy = "never"\n')

        step = CodexFilesStep()
        ctx = MagicMock()
        ctx.ui = None
        with (
            patch("installer.steps.codex_files._get_codex_config_dir", return_value=codex_dir),
            patch("installer.steps.codex_files.Path.home", return_value=tmp_path),
        ):
            step._install_codex_config(ctx)

        result = config.read_text()
        assert "suppress_unstable_features_warning" not in result
        _validate_toml_structure(result)

    def test_preserves_user_selected_suppression(self, tmp_path: Path) -> None:
        codex_dir = tmp_path / ".codex"
        codex_dir.mkdir(parents=True)
        config = codex_dir / "config.toml"
        config.write_text('approval_policy = "never"\nsuppress_unstable_features_warning = true\n')

        step = CodexFilesStep()
        ctx = MagicMock()
        ctx.ui = None
        with (
            patch("installer.steps.codex_files._get_codex_config_dir", return_value=codex_dir),
            patch("installer.steps.codex_files.Path.home", return_value=tmp_path),
        ):
            step._install_codex_config(ctx)

        result = config.read_text()
        assert result.count("suppress_unstable_features_warning") == 1


class TestMcpMarkerReplacement:
    """Regression tests: MCP managed block replacement must not corrupt surrounding sections."""

    def _make_step_with_mcp_json(self, tmp_path: Path, mcp_data: dict) -> tuple[CodexFilesStep, Path]:
        pilot_home = tmp_path / ".pilot"
        pilot_home.mkdir(parents=True)
        (pilot_home / ".mcp.json").write_text(json.dumps(mcp_data))
        codex_dir = tmp_path / ".codex"
        codex_dir.mkdir(parents=True)
        return CodexFilesStep(), codex_dir / "config.toml"

    @patch("installer.steps.codex_files._get_codex_config_dir")
    @patch("installer.steps.codex_files.Path.home")
    def test_second_install_preserves_section_newlines(
        self, mock_home: MagicMock, mock_codex_dir: MagicMock, tmp_path: Path
    ) -> None:
        mock_home.return_value = tmp_path
        mock_codex_dir.return_value = tmp_path / ".codex"
        step, config_path = self._make_step_with_mcp_json(
            tmp_path, {"mcpServers": {"codegraph": {"command": "codegraph", "args": ["serve", "--mcp"]}}}
        )

        initial = (
            'approval_policy = "never"\n'
            "\n"
            "[notice]\n"
            "hide_full_access_warning = true\n"
            "\n"
            "# --- pilot-shell managed MCP servers ---\n"
            "[mcp_servers.codegraph]\n"
            'command = "codegraph"\n'
            'args = ["serve", "--mcp"]\n'
            "\n"
            "# --- end pilot-shell managed MCP servers ---\n"
            "\n"
            "[sandbox_workspace_write]\n"
            "network_access = true\n"
        )
        config_path.write_text(initial)

        ctx = MagicMock()
        step._install_codex_mcp(ctx)

        result = config_path.read_text()
        _validate_toml_structure(result)
        assert "[notice]" in result
        assert "[sandbox_workspace_write]" in result

    @patch("installer.steps.codex_files._get_codex_config_dir")
    @patch("installer.steps.codex_files.Path.home")
    def test_markers_between_user_sections_preserved(
        self, mock_home: MagicMock, mock_codex_dir: MagicMock, tmp_path: Path
    ) -> None:
        mock_home.return_value = tmp_path
        mock_codex_dir.return_value = tmp_path / ".codex"
        step, config_path = self._make_step_with_mcp_json(
            tmp_path, {"mcpServers": {"ctx7": {"command": "npx", "args": ["-y", "@upstash/context7-mcp"]}}}
        )

        initial = (
            "[notice]\n"
            "hide_full_access_warning = true\n"
            "\n"
            "# --- pilot-shell managed MCP servers ---\n"
            "[mcp_servers.old]\n"
            'command = "old"\n'
            "\n"
            "# --- end pilot-shell managed MCP servers ---\n"
            "\n"
            "[sandbox_workspace_write]\n"
            "network_access = true\n"
        )
        config_path.write_text(initial)

        ctx = MagicMock()
        step._install_codex_mcp(ctx)

        result = config_path.read_text()
        assert "[notice]" in result
        assert "[sandbox_workspace_write]" in result
        assert "mcp_servers.ctx7" in result
        assert "mcp_servers.old" not in result
        _validate_toml_structure(result)


class TestCodexModelDefaults:
    @pytest.mark.parametrize("catalog_exists", [False, True])
    @pytest.mark.parametrize("quoted_key", [False, True])
    def test_upgrade_retires_only_pilot_catalog_override(
        self, tmp_path: Path, catalog_exists: bool, quoted_key: bool
    ) -> None:
        codex_dir = tmp_path / "custom-codex-home"
        codex_dir.mkdir()
        catalog = codex_dir / ".pilot-model-catalog.json"
        if catalog_exists:
            catalog.write_text('{"models": [{"slug": "gpt-5.6-sol"}]}')
        key = '"model_catalog_json"' if quoted_key else "model_catalog_json"
        config = codex_dir / "config.toml"
        config.write_text(
            f"  {key} = '{catalog}' # legacy Pilot catalog\n"
            '[profiles.custom]\nmodel_catalog_json = "/custom/models.json"\n'
        )
        cache = self._write_models_cache(codex_dir)
        with patch("installer.steps.codex_files._get_codex_config_dir", return_value=codex_dir):
            step = CodexFilesStep()
            assert step._install_codex_config(MagicMock(ui=None)) is True
            assert step._install_codex_config(MagicMock(ui=None)) is False

        parsed = tomllib.loads(config.read_text())
        assert "model_catalog_json" not in parsed
        assert parsed["profiles"]["custom"]["model_catalog_json"] == "/custom/models.json"
        assert parsed["model_context_window"] == 1050000
        assert parsed["model_auto_compact_token_limit"] == 922000
        assert catalog.exists() is catalog_exists
        if catalog_exists:
            assert catalog.read_text() == '{"models": [{"slug": "gpt-5.6-sol"}]}'
        assert json.loads((codex_dir / "models_cache.json").read_text()) == cache

    @staticmethod
    def _write_models_cache(codex_dir: Path) -> dict[str, object]:
        cache: dict[str, object] = {
            "client_version": "0.147.0",
            "models": [
                {
                    "slug": "gpt-5.6-sol",
                    "context_window": 272000,
                    "max_context_window": 272000,
                },
                {
                    "slug": "gpt-5.6-terra",
                    "context_window": 272000,
                    "max_context_window": 272000,
                },
                {
                    "slug": "gpt-5.6-luna",
                    "context_window": 272000,
                    "max_context_window": 272000,
                },
                {
                    "slug": "gpt-6-astra",
                    "context_window": 1050000,
                    "max_context_window": 1050000,
                },
                {
                    "slug": "gpt-5.5",
                    "context_window": 272000,
                    "max_context_window": 272000,
                },
            ],
        }
        (codex_dir / "models_cache.json").write_text(json.dumps(cache))
        return cache

    def test_fresh_install_leaves_model_and_effort_to_codex(self, tmp_path: Path) -> None:
        codex_dir = tmp_path / ".codex"
        codex_dir.mkdir(parents=True)
        config = codex_dir / "config.toml"
        config.write_text("")
        source_cache = self._write_models_cache(codex_dir)

        step = CodexFilesStep()
        ctx = MagicMock()
        ctx.ui = None
        with (
            patch("installer.steps.codex_files._get_codex_config_dir", return_value=codex_dir),
            patch("installer.steps.codex_files.Path.home", return_value=tmp_path),
        ):
            step._install_codex_config(ctx)

        result = config.read_text()
        parsed = tomllib.loads(result)
        assert "model" not in parsed
        assert "model_reasoning_effort" not in parsed
        assert "plan_mode_reasoning_effort" not in parsed
        assert parsed["model_context_window"] == 1050000
        assert parsed["model_auto_compact_token_limit"] == 922000
        assert "model_catalog_json" not in parsed
        assert not (codex_dir / ".pilot-model-catalog.json").exists()
        assert json.loads((codex_dir / "models_cache.json").read_text()) == source_cache
        for key in (
            "approval_policy",
            "sandbox_mode",
            "model_reasoning_summary",
            "personality",
            "file_opener",
            "project_doc_max_bytes",
            "suppress_unstable_features_warning",
        ):
            assert key not in parsed
        assert parsed["features"] == {
            "hooks": True,
            "context_management": {"experimental_mode": True},
        }
        assert parsed["tools"]["update_plan"]["enabled"] is True
        assert "sandbox_workspace_write" not in parsed
        assert "notice" not in parsed
        _validate_toml_structure(result)

    def test_preserves_explicit_update_plan_opt_out(self, tmp_path: Path) -> None:
        codex_dir = tmp_path / ".codex"
        codex_dir.mkdir(parents=True)
        config = codex_dir / "config.toml"
        config.write_text("[tools.update_plan]\nenabled = false\n")

        step = CodexFilesStep()
        ctx = MagicMock(ui=None)
        with (
            patch("installer.steps.codex_files._get_codex_config_dir", return_value=codex_dir),
            patch("installer.steps.codex_files.Path.home", return_value=tmp_path),
        ):
            step._install_codex_config(ctx)

        parsed = tomllib.loads(config.read_text())
        assert parsed["tools"]["update_plan"]["enabled"] is False

    def test_legacy_codex_does_not_receive_update_plan_config(self, tmp_path: Path) -> None:
        codex_dir = tmp_path / ".codex"
        codex_dir.mkdir(parents=True)
        config = codex_dir / "config.toml"
        config.write_text("")

        step = CodexFilesStep()
        ctx = MagicMock(ui=None)
        with (
            patch("installer.steps.codex_files._get_codex_config_dir", return_value=codex_dir),
            patch("installer.steps.codex_files.Path.home", return_value=tmp_path),
            patch(
                "installer.steps.codex_files._codex_supports_update_plan_config",
                return_value=False,
            ),
        ):
            step._install_codex_config(ctx)

        assert "tools" not in tomllib.loads(config.read_text())

    @pytest.mark.parametrize(
        ("model", "effort", "plan_effort"),
        [("gpt-5.5", "medium", "low"), ("gpt-6-astra", "high", "medium"), ("gpt-5.6-sol", "xhigh", "xhigh")],
    )
    def test_preserves_model_effort_policy_and_profiles(
        self, tmp_path: Path, model: str, effort: str, plan_effort: str
    ) -> None:
        codex_dir = tmp_path / ".codex"
        codex_dir.mkdir(parents=True)
        config = codex_dir / "config.toml"
        config.write_text(
            'approval_policy = "on-request"\n'
            'sandbox_mode = "workspace-write"\n'
            f'  model = "{model}"\n'
            f'model_reasoning_effort = "{effort}"\n'
            f'plan_mode_reasoning_effort = "{plan_effort}"\n'
            "model_context_window = 272000\n"
            "model_auto_compact_token_limit = 200000\n"
            'personality = "friendly"\n'
            "project_doc_max_bytes = 65536\n\n"
            "[profiles.careful]\n"
            'model = "gpt-5.5"\n'
            'model_reasoning_effort = "low"\n'
        )

        step = CodexFilesStep()
        ctx = MagicMock()
        ctx.ui = None
        with (
            patch("installer.steps.codex_files._get_codex_config_dir", return_value=codex_dir),
            patch("installer.steps.codex_files.Path.home", return_value=tmp_path),
        ):
            step._install_codex_config(ctx)

        result = config.read_text()
        parsed = tomllib.loads(result)
        assert parsed["approval_policy"] == "on-request"
        assert parsed["sandbox_mode"] == "workspace-write"
        assert parsed["model"] == model
        assert parsed["model_reasoning_effort"] == effort
        assert parsed["plan_mode_reasoning_effort"] == plan_effort
        assert parsed["model_context_window"] == 1050000
        assert parsed["model_auto_compact_token_limit"] == 922000
        assert parsed["personality"] == "friendly"
        assert parsed["project_doc_max_bytes"] == 65536
        assert parsed["profiles"]["careful"] == {
            "model": "gpt-5.5",
            "model_reasoning_effort": "low",
        }

    @pytest.mark.parametrize(
        "feature_config",
        [
            "features.context_management.experimental_mode = false\n",
            "[features]\ncontext_management.experimental_mode = false\n",
            "[features.context_management]\nexperimental_mode = false\n",
            "[features]\ncontext_management = { experimental_mode = false }\n",
        ],
    )
    def test_preserves_explicit_context_management_opt_out(
        self,
        tmp_path: Path,
        feature_config: str,
    ) -> None:
        codex_dir = tmp_path / ".codex"
        codex_dir.mkdir(parents=True)
        config = codex_dir / "config.toml"
        config.write_text(feature_config)

        step = CodexFilesStep()
        ctx = MagicMock(ui=None)
        with (
            patch("installer.steps.codex_files._get_codex_config_dir", return_value=codex_dir),
            patch("installer.steps.codex_files.Path.home", return_value=tmp_path),
        ):
            step._install_codex_config(ctx)

        parsed = tomllib.loads(config.read_text())
        assert parsed["features"]["hooks"] is True
        assert parsed["features"]["context_management"]["experimental_mode"] is False

    def test_enables_context_management_in_existing_inline_table(self, tmp_path: Path) -> None:
        codex_dir = tmp_path / ".codex"
        codex_dir.mkdir(parents=True)
        config = codex_dir / "config.toml"
        config.write_text("[features]\ncontext_management = { future_option = true }\n")

        step = CodexFilesStep()
        ctx = MagicMock(ui=None)
        with (
            patch("installer.steps.codex_files._get_codex_config_dir", return_value=codex_dir),
            patch("installer.steps.codex_files.Path.home", return_value=tmp_path),
        ):
            step._install_codex_config(ctx)

        parsed = tomllib.loads(config.read_text())
        assert parsed["features"]["context_management"] == {
            "experimental_mode": True,
            "future_option": True,
        }

    def test_removes_pilot_context_management_for_legacy_codex(self, tmp_path: Path) -> None:
        codex_dir = tmp_path / ".codex"
        codex_dir.mkdir(parents=True)
        config = codex_dir / "config.toml"
        config.write_text("[features]\ncontext_management.experimental_mode = true\nhooks = true\n")

        step = CodexFilesStep()
        ctx = MagicMock(ui=None)
        with (
            patch("installer.steps.codex_files._get_codex_config_dir", return_value=codex_dir),
            patch("installer.steps.codex_files.Path.home", return_value=tmp_path),
            patch(
                "installer.steps.codex_files._codex_supports_context_management",
                return_value=False,
            ),
        ):
            step._install_codex_config(ctx)

        parsed = tomllib.loads(config.read_text())
        assert parsed["features"] == {"hooks": True}

    def test_fresh_install_without_cache_keeps_native_catalog(self, tmp_path: Path) -> None:
        codex_dir = tmp_path / ".codex"
        codex_dir.mkdir(parents=True)
        config = codex_dir / "config.toml"
        config.write_text("")

        step = CodexFilesStep()
        ctx = MagicMock(ui=None)
        with (
            patch("installer.steps.codex_files._get_codex_config_dir", return_value=codex_dir),
            patch("installer.steps.codex_files.Path.home", return_value=tmp_path),
            patch("installer.steps.codex_files.subprocess.run") as run,
        ):
            step._install_codex_config(ctx)

        run.assert_not_called()
        parsed = tomllib.loads(config.read_text())
        assert "model_catalog_json" not in parsed
        assert not (codex_dir / ".pilot-model-catalog.json").exists()

    @pytest.mark.parametrize("cache_exists", [False, True])
    @pytest.mark.parametrize("catalog_path", ["/custom/models.json", "/custom/.pilot-model-catalog.json"])
    def test_preserves_user_catalog(self, tmp_path: Path, cache_exists: bool, catalog_path: str) -> None:
        codex_dir = tmp_path / ".codex"
        codex_dir.mkdir(parents=True)
        config = codex_dir / "config.toml"
        config.write_text(f'model_catalog_json = "{catalog_path}"\n')
        if cache_exists:
            self._write_models_cache(codex_dir)

        step = CodexFilesStep()
        ctx = MagicMock(ui=None)
        with (
            patch("installer.steps.codex_files._get_codex_config_dir", return_value=codex_dir),
            patch("installer.steps.codex_files.Path.home", return_value=tmp_path),
        ):
            step._install_codex_config(ctx)

        assert tomllib.loads(config.read_text())["model_catalog_json"] == catalog_path
        assert not (codex_dir / ".pilot-model-catalog.json").exists()

    def test_model_defaults_are_idempotent(self, tmp_path: Path) -> None:
        codex_dir = tmp_path / ".codex"
        codex_dir.mkdir(parents=True)
        config = codex_dir / "config.toml"
        config.write_text("")
        self._write_models_cache(codex_dir)

        step = CodexFilesStep()
        ctx = MagicMock()
        ctx.ui = None
        with (
            patch("installer.steps.codex_files._get_codex_config_dir", return_value=codex_dir),
            patch("installer.steps.codex_files.Path.home", return_value=tmp_path),
        ):
            assert step._install_codex_config(ctx) is True
            first = config.read_text()
            assert step._install_codex_config(ctx) is False

        assert config.read_text() == first
        assert not (codex_dir / ".pilot-model-catalog.json").exists()


class TestCodexConfigEnvHeal:
    """CodexFilesStep heals ~/.codex/config.toml's managed env block at
    install/update time, so a duplicate-key leftover from a pre-fix version is
    repaired immediately rather than lazily via the license-gated,
    startup-only session hook (which misses Codex-only / resume-only / lapsed
    users)."""

    def test_run_heals_codex_config_via_sync_env(self, tmp_path: Path) -> None:
        pilot_bin = tmp_path / ".pilot" / "bin" / "pilot"
        pilot_bin.parent.mkdir(parents=True)
        pilot_bin.touch()

        step = CodexFilesStep()
        ctx = MagicMock()
        ctx.ui = None

        with (
            patch("installer.steps.codex_files.is_codex_installed", return_value=True),
            patch("installer.steps.codex_files.Path.home", return_value=tmp_path),
            patch("installer.steps.codex_files.subprocess.run") as mock_run,
            patch.object(step, "_install_codex_hooks", return_value=0),
            patch.object(step, "_install_codex_skills", return_value=0),
            patch.object(step, "_install_codex_agents", return_value=0),
            patch.object(step, "_install_codex_config", return_value=False),
            patch.object(step, "_install_codex_mcp", return_value=0),
            patch.object(step, "_install_codex_rules", return_value=0),
        ):
            mock_run.return_value = MagicMock(returncode=0)
            step.run(ctx)

        invoked = [call.args[0] for call in mock_run.call_args_list]
        # Codex-scoped heal: must NOT let `pilot sync-env` touch Claude settings.
        assert any(str(pilot_bin) in cmd and "sync-env" in cmd and "--codex-only" in cmd for cmd in invoked)

    def test_heal_skips_when_pilot_binary_missing(self, tmp_path: Path) -> None:
        step = CodexFilesStep()
        with (
            patch("installer.steps.codex_files.Path.home", return_value=tmp_path),
            patch("installer.steps.codex_files.subprocess.run") as mock_run,
        ):
            step._heal_codex_config_env()

        mock_run.assert_not_called()

    def test_heal_warns_on_nonzero_returncode(self, tmp_path: Path) -> None:
        """A failed heal must surface a warning, not be silently swallowed."""
        pilot_bin = tmp_path / ".pilot" / "bin" / "pilot"
        pilot_bin.parent.mkdir(parents=True)
        pilot_bin.touch()

        step = CodexFilesStep()
        ui = MagicMock()
        with (
            patch("installer.steps.codex_files.Path.home", return_value=tmp_path),
            patch("installer.steps.codex_files.subprocess.run") as mock_run,
        ):
            mock_run.return_value = MagicMock(returncode=1, stderr="permission denied", stdout="")
            step._heal_codex_config_env(ui)

        ui.warning.assert_called_once()


class TestCodexSourcesHonourClaudeConfigDir:
    """Codex adaptation reads skills/agents/rules FROM the Claude profile.

    With a custom profile these hardcoded reads find nothing, so a Codex user
    silently gets zero skills and no review agents.
    """

    def test_skills_source_follows_config_dir(self, tmp_path, monkeypatch):
        from installer.steps.codex_files import MCP_BASELINE_FILE, CodexFilesStep

        work = tmp_path / ".claude_work"
        skill_dir = work / "skills" / "spec"
        skill_dir.mkdir(parents=True)
        (skill_dir / "manifest.json").write_text(
            json.dumps({"version": 1, "orchestrator": "orchestrator.md", "steps": []})
        )
        (skill_dir / "orchestrator.md").write_text(
            "---\nname: spec\ndescription: Spec workflow\n---\n\nRun /spec to plan."
        )
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(work))
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        from installer.context import InstallContext

        ctx = InstallContext(project_dir=tmp_path)
        built = CodexFilesStep()._install_codex_skills(ctx)

        assert built > 0, "no skills adapted from the custom profile"
        assert (tmp_path / ".agents" / "skills" / "spec" / "SKILL.md").exists()

    def test_review_agents_source_follows_config_dir(self, tmp_path, monkeypatch):
        from installer.steps.codex_files import CodexFilesStep

        work = tmp_path / ".claude_work"
        (work / "agents").mkdir(parents=True)
        (work / "agents" / "spec-review.md").write_text("# spec review\n")
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(work))
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        from installer.context import InstallContext

        ctx = InstallContext(project_dir=tmp_path)
        found = CodexFilesStep()._find_codex_review_agents_source(ctx)

        assert found is not None, "review-agent source not found in the custom profile"
        assert str(work) in str(found)


class TestCodexSourcesFailClosedOnInvalidConfigDir:
    """A set-but-relative CLAUDE_CONFIG_DIR must never fall back to ~/.claude.

    Mirrors the invalid-value coverage dependencies.py already has; without it
    a regression could reintroduce the personal-profile read silently.
    """

    def test_skills_install_reads_nothing(self, tmp_path, monkeypatch):
        from installer.context import InstallContext
        from installer.steps.codex_files import CodexFilesStep

        personal = tmp_path / ".claude" / "skills" / "spec"
        personal.mkdir(parents=True)
        (personal / "manifest.json").write_text(
            json.dumps({"version": 1, "orchestrator": "orchestrator.md", "steps": []})
        )
        (personal / "orchestrator.md").write_text("---\nname: spec\ndescription: d\n---\n\nx")
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", "relative/path")
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        built = CodexFilesStep()._install_codex_skills(InstallContext(project_dir=tmp_path))

        assert built == 0
        assert not (tmp_path / ".agents" / "skills" / "spec").exists()

    def test_review_agents_source_is_none(self, tmp_path, monkeypatch):
        from installer.context import InstallContext
        from installer.steps.codex_files import CodexFilesStep

        (tmp_path / ".claude" / "agents").mkdir(parents=True)
        (tmp_path / ".claude" / "agents" / "spec-review.md").write_text("# x\n")
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", "relative/path")
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        assert CodexFilesStep()._find_codex_review_agents_source(InstallContext(project_dir=tmp_path)) is None

    def test_rules_fallback_is_none(self, tmp_path, monkeypatch):
        from installer.steps.codex_files import _claude_rules_dir_or_none

        monkeypatch.setenv("CLAUDE_CONFIG_DIR", "relative/path")
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        assert _claude_rules_dir_or_none() is None
