"""Tests for codex_skill_sync hook — Codex SKILL.md rebuild + license gating."""

from __future__ import annotations

import json
import re
import sys
import tomllib
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

# Add hooks dir to path so we can import the module
_hooks_dir = Path(__file__).resolve().parent.parent
if str(_hooks_dir) not in sys.path:
    sys.path.insert(0, str(_hooks_dir))

from codex_skill_sync import (  # noqa: E402
    _SKILL_DESCRIPTIONS,
    _SUPPORTED_SKILLS,
    _adapt,
    _build_codex_review_agent,
    _build_codex_skill,
    _build_openai_yaml,
    _build_skill,
    _check_license,
    _remove_codex_review_agents,
    _remove_codex_skills,
    _sync_codex_env_vars,
    _sync_codex_review_agents,
    _sync_codex_skills,
    main,
)


def test_description_overrides_match_the_installer_generator() -> None:
    from installer.steps.codex_files import _CODEX_SKILL_DESCRIPTIONS

    assert _SKILL_DESCRIPTIONS == _CODEX_SKILL_DESCRIPTIONS


def _codex_runtime_text(skill_name: str) -> str:
    skill_dir = Path("pilot/skills") / skill_name
    main = _build_codex_skill(skill_dir)
    assert main is not None
    parts = [main]
    manifest = json.loads((skill_dir / "manifest.json").read_text())
    if manifest.get("delivery") == "progressive":
        parts.extend(_adapt((skill_dir / step["file"]).read_text()) for step in manifest["steps"])
    return "\n\n".join(parts)


@pytest.fixture()
def skill_tree(tmp_path: Path) -> Path:
    """Create a minimal decomposed skill under tmp_path/.claude/skills/fix/."""
    skill_dir = tmp_path / ".claude" / "skills" / "fix"
    skill_dir.mkdir(parents=True)
    (skill_dir / "manifest.json").write_text(
        json.dumps(
            {
                "version": 1,
                "orchestrator": "orchestrator.md",
                "steps": [{"id": "s1", "file": "steps/01-impl.md"}],
            }
        )
    )
    (skill_dir / "orchestrator.md").write_text(
        "---\nname: fix\ndescription: Bugfix workflow\n---\n\n# /fix\n\nFix bugs."
    )
    steps = skill_dir / "steps"
    steps.mkdir()
    (steps / "01-impl.md").write_text("## Step 1\n\nRun /spec if needed.")
    return tmp_path


class TestBuildSkill:
    def test_concatenates_orchestrator_and_steps(self, skill_tree: Path) -> None:
        result = _build_skill(skill_tree / ".claude" / "skills" / "fix")
        assert result is not None
        assert "# /fix" in result
        assert "## Step 1" in result
        assert "Run /spec if needed." in result

    def test_returns_none_for_missing_manifest(self, tmp_path: Path) -> None:
        assert _build_skill(tmp_path / "nonexistent") is None

    @pytest.mark.parametrize("unsafe", ["../secret.md", "/tmp/secret.md", "steps\\secret.md"])
    def test_rejects_unsafe_manifest_paths(self, tmp_path: Path, unsafe: str) -> None:
        skill_dir = tmp_path / "skill"
        skill_dir.mkdir()
        (skill_dir / "manifest.json").write_text(json.dumps({"version": 1, "orchestrator": unsafe, "steps": []}))

        assert _build_skill(skill_dir) is None

    def test_progressive_manifest_builds_step_index_without_inlining_body(self, skill_tree: Path) -> None:
        skill_dir = skill_tree / ".claude" / "skills" / "fix"
        manifest = json.loads((skill_dir / "manifest.json").read_text())
        manifest.update(
            {
                "version": 2,
                "delivery": "progressive",
                "targets": ["claude", "codex"],
                "visibility": "public",
                "invocation": "explicit",
            }
        )
        (skill_dir / "manifest.json").write_text(json.dumps(manifest))

        result = _build_skill(skill_dir)

        assert result is not None
        assert "Required phase resources" in result
        assert "steps/01-impl.md" in result
        assert "Run /spec if needed." not in result


class TestAdapt:
    def test_strips_cc_only_blocks(self) -> None:
        content = "Before.\n<!-- CC-ONLY -->\nCC stuff.\n<!-- /CC-ONLY -->\nAfter."
        result = _adapt(content)
        assert "CC stuff" not in result
        assert "Before." in result
        assert "After." in result

    def test_unwraps_codex_blocks(self) -> None:
        content = "Before.\n<!-- CODEX-START\nCodex alt.\nCODEX-END -->\nAfter."
        result = _adapt(content)
        assert "Codex alt." in result
        assert "CODEX-START" not in result

    def test_transforms_skill_calls(self) -> None:
        content = "Skill(skill='spec-implement', args='plan.md')"
        result = _adapt(content)
        assert "the `$spec-implement` skill instructions with arguments: `plan.md`" in result
        assert "plan.md" in result

    def test_replaces_slash_invocations(self) -> None:
        content = "Run /spec to plan. Use /fix for bugs."
        result = _adapt(content)
        assert "$spec" in result
        assert "$fix" in result

    def test_replaces_ask_user_question(self) -> None:
        content = "Use AskUserQuestion to ask."
        result = _adapt(content)
        assert "structured question" in result

    def test_does_not_claim_plain_text_is_unavailable(self) -> None:
        content = "Use plain-text numbered options because the `AskUserQuestion` tool isn't callable in Codex."

        result = _adapt(content)

        assert "plain-text numbered options" in result
        assert "Claude structured-question tool" in result
        assert "`plain-text numbered options` format isn't callable" not in result

    def test_transforms_ask_user_question_blocks(self) -> None:
        content = """AskUserQuestion(
  question="Ready?",
  options=["Yes", "No"]
)"""
        result = _adapt(content)
        assert "runtime exposes and permits" in result
        assert "otherwise ask in plain text" in result
        assert 'question="Ready?"' in result
        assert 'options=["Yes", "No"]' in result
        assert "AskUserQuestion" not in result
        assert "plain-text numbered options(" not in result


class TestBuildCodexSkill:
    @pytest.mark.parametrize("skill_name", sorted(_SUPPORTED_SKILLS))
    def test_hook_compiler_matches_installer_compiler_for_every_shipped_skill(self, skill_name: str) -> None:
        from installer.steps.codex_files import build_codex_skill_md, build_codex_skill_openai_yaml

        skill_dir = Path("pilot/skills") / skill_name
        if not skill_dir.is_dir():
            pytest.skip(f"source skill not present: {skill_name}")

        assert _build_codex_skill(skill_dir) == build_codex_skill_md(skill_dir)
        assert _build_openai_yaml(skill_dir) == build_codex_skill_openai_yaml(skill_dir)

    def test_produces_frontmatter_and_adapted_content(self, skill_tree: Path) -> None:
        result = _build_codex_skill(skill_tree / ".claude" / "skills" / "fix")
        assert result is not None
        assert result.startswith("---\n")
        assert "name: fix" in result
        assert "$spec" in result  # /spec replaced
        assert "$fix" in result

    def test_real_spec_skill_uses_codex_phase_handoff(self) -> None:
        result = _build_codex_skill(Path("pilot/skills/spec"))
        assert result is not None
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

    def test_real_fix_codex_skill_uses_selective_codegraph_guidance(self) -> None:
        result = _codex_runtime_text("fix")
        assert 'Start with `codegraph_context(task="<bug description>")`' not in result
        assert "Use `codegraph_explore` only when the bug is structural" in result
        assert "For docs, rules, markdown, config, UI copy, or a named local file/function" in result

    def test_real_fix_codex_skill_env_blocker_uses_terminal_hint(self) -> None:
        result = _codex_runtime_text("fix")
        assert "Read the COMPLETE output" in result
        assert "Environment blocker protocol" in result
        assert "separate terminal" in result
        assert "! <command>" not in result

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
            "benchmark",
            "setup-rules",
            "create-skill",
        ],
    )
    def test_real_codex_skills_do_not_expose_claude_tool_calls(self, skill_name: str) -> None:
        result = _build_codex_skill(Path("pilot/skills") / skill_name)
        assert result is not None
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
            re.search(r"(^|[^A-Za-z0-9_`])/(spec|fix|prd|setup-rules|create-skill|benchmark)([^A-Za-z0-9_/]|$)", result)
            is None
        )


class TestSyncCodexSkills:
    def test_builds_skills_to_agents_dir(self, skill_tree: Path) -> None:
        agents_dir = skill_tree / ".agents" / "skills"
        with patch("codex_skill_sync.Path.home", return_value=skill_tree):
            built, failed = _sync_codex_skills()
        assert built == 1
        assert failed == 0
        assert (agents_dir / "fix" / "SKILL.md").is_file()
        content = (agents_dir / "fix" / "SKILL.md").read_text()
        assert "name: fix" in content

    def test_progressive_sync_copies_adapted_steps_and_runtime_resources(self, skill_tree: Path) -> None:
        source = skill_tree / ".claude" / "skills" / "fix"
        manifest = json.loads((source / "manifest.json").read_text())
        manifest.update(
            {
                "version": 2,
                "delivery": "progressive",
                "targets": ["claude", "codex"],
                "visibility": "public",
                "invocation": "explicit",
            }
        )
        (source / "manifest.json").write_text(json.dumps(manifest))
        (source / "steps" / "01-impl.md").write_text(
            "<!-- CC-ONLY -->\nClaude only.\n<!-- /CC-ONLY -->\n"
            "<!-- CODEX-START\nCodex only.\nCODEX-END -->\nRun /spec."
        )
        scripts = source / "scripts"
        scripts.mkdir()
        (scripts / "helper.py").write_text("print('ok')\n")

        with patch("codex_skill_sync.Path.home", return_value=skill_tree):
            assert _sync_codex_skills() == (1, 0)

        installed = skill_tree / ".agents" / "skills" / "fix"
        step = (installed / "steps" / "01-impl.md").read_text()
        assert "Codex only." in step
        assert "Claude only." not in step
        assert "$spec" in step
        assert (installed / "scripts" / "helper.py").read_text() == "print('ok')\n"

    def test_claude_only_target_removes_managed_codex_artifacts(self, skill_tree: Path) -> None:
        source = skill_tree / ".claude" / "skills" / "fix"
        manifest = json.loads((source / "manifest.json").read_text())
        manifest.update(
            {
                "version": 2,
                "delivery": "bundled",
                "targets": ["claude"],
                "visibility": "public",
                "invocation": "explicit",
            }
        )
        (source / "manifest.json").write_text(json.dumps(manifest))
        installed = skill_tree / ".agents" / "skills" / "fix"
        (installed / "agents").mkdir(parents=True)
        (installed / "SKILL.md").write_text("managed")
        (installed / "agents" / "openai.yaml").write_text("managed")
        (installed / ".pilot-resources.json").write_text('{"files": [], "directories": []}\n')
        (installed / "user-note.md").write_text("keep")

        with patch("codex_skill_sync.Path.home", return_value=skill_tree):
            assert _sync_codex_skills() == (0, 0)

        assert not (installed / "SKILL.md").exists()
        assert not (installed / "agents" / "openai.yaml").exists()
        assert (installed / "user-note.md").read_text() == "keep"

    def test_missing_source_tree_removes_sidecar_managed_codex_artifacts(self, tmp_path: Path) -> None:
        installed = tmp_path / ".agents" / "skills" / "fix"
        installed.mkdir(parents=True)
        (installed / "SKILL.md").write_text("managed")
        (installed / ".pilot-resources.json").write_text('{"files": [], "directories": []}\n')
        (installed / "user-note.md").write_text("keep")

        with patch("codex_skill_sync.Path.home", return_value=tmp_path):
            assert _sync_codex_skills() == (0, 0)

        assert not (installed / "SKILL.md").exists()
        assert not (installed / ".pilot-resources.json").exists()
        assert (installed / "user-note.md").read_text() == "keep"

    def test_skips_missing_skills(self, skill_tree: Path) -> None:
        with patch("codex_skill_sync.Path.home", return_value=skill_tree):
            built, failed = _sync_codex_skills()
        # Only "fix" exists, the rest of _SUPPORTED_SKILLS are missing → skipped
        assert built == 1

    def test_cc_only_skill_is_never_synced_to_codex(self, skill_tree: Path) -> None:
        """CC-only skills (the bot-* family) are excluded by allowlist omission. This
        mirrors the installer-side exclusion test so the session-start path cannot
        silently leak one either (weakest-point finding from a Codex review)."""
        skill_dir = skill_tree / ".claude" / "skills" / "bot-jobs"
        skill_dir.mkdir(parents=True)
        (skill_dir / "manifest.json").write_text(
            json.dumps({"version": 1, "orchestrator": "orchestrator.md", "steps": []})
        )
        (skill_dir / "orchestrator.md").write_text("---\nname: bot-jobs\ndescription: d\n---\n\n# bot-jobs\n\nBody.")
        with patch("codex_skill_sync.Path.home", return_value=skill_tree):
            built, failed = _sync_codex_skills()
        assert built == 1  # still only "fix"
        assert not (skill_tree / ".agents" / "skills" / "bot-jobs").exists()

    def test_sync_writes_explicit_invocation_policy_for_workflows(self, skill_tree: Path) -> None:
        with patch("codex_skill_sync.Path.home", return_value=skill_tree):
            built, failed = _sync_codex_skills()

        assert (built, failed) == (1, 0)
        metadata_path = skill_tree / ".agents" / "skills" / "fix" / "agents" / "openai.yaml"
        metadata = yaml.safe_load(metadata_path.read_text())
        assert metadata["interface"]["display_name"] == "Fix"
        assert "Diagnose and repair a defect at its root cause" in metadata["interface"]["short_description"]
        assert not metadata["interface"]["short_description"].casefold().startswith("use only")
        assert "/fix" not in metadata["interface"]["short_description"]
        assert metadata["policy"]["allow_implicit_invocation"] is False

    def test_v2_internal_spec_phase_uses_manifest_invocation_policy(self) -> None:
        rendered = _build_openai_yaml(Path("pilot/skills/spec-plan"))
        assert rendered is not None
        metadata = yaml.safe_load(rendered)

        assert metadata["policy"]["allow_implicit_invocation"] is False

    def test_synced_visible_skill_descriptions_fit_a_lean_catalog_budget(self) -> None:
        visible_names = (
            "benchmark",
            "create-skill",
            "setup-rules",
        )
        descriptions: list[str] = []
        for name in visible_names:
            content = _build_codex_skill(Path("pilot/skills") / name)
            metadata_text = _build_openai_yaml(Path("pilot/skills") / name)
            assert content is not None
            assert metadata_text is not None
            description = yaml.safe_load(content.split("---", 2)[1])["description"]
            metadata = yaml.safe_load(metadata_text)
            assert metadata["interface"]["short_description"] == description
            assert metadata["policy"]["allow_implicit_invocation"] is True
            assert len(description) <= 120
            descriptions.append(description)

        assert sum(map(len, descriptions)) <= 360


class TestSyncCodexReviewAgents:
    def test_builds_review_agent_toml_without_output_path_contract(self) -> None:
        result = _build_codex_review_agent(Path("pilot/agents/spec-review.md"))
        assert result is not None
        data = tomllib.loads(result)
        assert data["name"] == "spec-review"
        assert data["model"] == "codex-auto-review"
        instructions = data["developer_instructions"]
        assert "Output ONLY valid JSON" in instructions
        assert '"issues"' in instructions
        assert "output_path" not in instructions
        assert "MANDATORY: Write output" not in instructions
        assert "Your LAST action MUST be `Write`" not in instructions
        assert "Write Output" not in instructions
        assert "write output" not in instructions.lower()

    def test_builds_changes_review_agent_with_final_status_guidance(self) -> None:
        result = _build_codex_review_agent(Path("pilot/agents/changes-review.md"))
        assert result is not None
        data = tomllib.loads(result)
        assert data["name"] == "changes-review"
        instructions = data["developer_instructions"]
        assert "Status: VERIFIED" in instructions
        assert "orchestrator after the user review gate" in instructions
        assert "do not emit a finding during changes review" in instructions

    def test_builds_build_review_agent_judging_criteria_not_spec_sections(self) -> None:
        result = _build_codex_review_agent(Path("pilot/agents/build-review.md"))
        assert result is not None
        data = tomllib.loads(result)
        assert data["name"] == "build-review"
        assert data["model"] == "codex-auto-review"
        instructions = data["developer_instructions"]
        assert "Output ONLY valid JSON" in instructions
        assert '"issues"' in instructions
        # A Buildout has none of these; reporting their absence would be noise.
        assert "does NOT have" in instructions
        assert "output_path" not in instructions

    def test_syncs_review_agents_to_codex_agents_dir(self, tmp_path: Path) -> None:
        claude_agents_dir = tmp_path / ".claude" / "agents"
        claude_agents_dir.mkdir(parents=True)
        (claude_agents_dir / "spec-review.md").write_text(Path("pilot/agents/spec-review.md").read_text())
        (claude_agents_dir / "changes-review.md").write_text(Path("pilot/agents/changes-review.md").read_text())
        (claude_agents_dir / "build-review.md").write_text(Path("pilot/agents/build-review.md").read_text())
        codex_agents_dir = tmp_path / ".codex" / "agents"
        codex_agents_dir.mkdir(parents=True)
        (codex_agents_dir / "user-agent.toml").write_text('name = "user-agent"\n')

        with patch("codex_skill_sync.Path.home", return_value=tmp_path):
            built, failed = _sync_codex_review_agents()

        assert built == 3
        assert failed == 0
        spec_data = tomllib.loads((codex_agents_dir / "spec-review.toml").read_text())
        changes_data = tomllib.loads((codex_agents_dir / "changes-review.toml").read_text())
        build_data = tomllib.loads((codex_agents_dir / "build-review.toml").read_text())
        assert spec_data["name"] == "spec-review"
        assert spec_data["model"] == "codex-auto-review"
        assert changes_data["name"] == "changes-review"
        assert changes_data["model"] == "codex-auto-review"
        assert build_data["name"] == "build-review"
        assert build_data["model"] == "codex-auto-review"
        assert (codex_agents_dir / "user-agent.toml").exists()

    def test_removes_stale_managed_review_agent_when_source_disappears(self, tmp_path: Path) -> None:
        (tmp_path / ".pilot" / "agents").mkdir(parents=True)
        dest = tmp_path / ".codex" / "agents"
        dest.mkdir(parents=True)
        stale = dest / "build-review.toml"
        stale.write_text('# pilot-shell managed Codex review agent\nname = "build-review"\n')
        user = dest / "spec-review.toml"
        user.write_text('name = "spec-review"\n')

        with patch("codex_skill_sync.Path.home", return_value=tmp_path):
            assert _sync_codex_review_agents() == (0, 0)

        assert not stale.exists()
        assert user.read_text() == 'name = "spec-review"\n'

    def test_missing_review_source_tree_removes_only_managed_agents(self, tmp_path: Path) -> None:
        dest = tmp_path / ".codex" / "agents"
        dest.mkdir(parents=True)
        managed = dest / "build-review.toml"
        managed.write_text('# pilot-shell managed Codex review agent\nname = "build-review"\n')
        user = dest / "spec-review.toml"
        user.write_text('name = "spec-review"\n')

        with patch("codex_skill_sync.Path.home", return_value=tmp_path):
            assert _sync_codex_review_agents() == (0, 0)

        assert not managed.exists()
        assert user.read_text() == 'name = "spec-review"\n'

    def test_removes_build_review_agent_when_license_invalid(self, tmp_path: Path) -> None:
        """License gating must reach the new agent too, or it survives a revoked licence."""
        codex_agents_dir = tmp_path / ".codex" / "agents"
        codex_agents_dir.mkdir(parents=True)
        claude_agents_dir = tmp_path / ".claude" / "agents"
        claude_agents_dir.mkdir(parents=True)
        (claude_agents_dir / "build-review.md").write_text(Path("pilot/agents/build-review.md").read_text())

        with patch("codex_skill_sync.Path.home", return_value=tmp_path):
            _sync_codex_review_agents()
            assert (codex_agents_dir / "build-review.toml").exists()
            removed = _remove_codex_review_agents()

        assert removed >= 1
        assert not (codex_agents_dir / "build-review.toml").exists()

    def test_syncs_review_agents_to_codex_home_agents_dir(self, tmp_path: Path) -> None:
        claude_agents_dir = tmp_path / ".claude" / "agents"
        claude_agents_dir.mkdir(parents=True)
        (claude_agents_dir / "spec-review.md").write_text(Path("pilot/agents/spec-review.md").read_text())
        codex_home = tmp_path / "custom-codex"

        with (
            patch("codex_skill_sync.Path.home", return_value=tmp_path),
            patch.dict("codex_skill_sync.os.environ", {"CODEX_HOME": str(codex_home)}),
        ):
            built, failed = _sync_codex_review_agents()

        assert built == 1
        assert failed == 0
        assert (codex_home / "agents" / "spec-review.toml").exists()
        assert not (tmp_path / ".codex" / "agents" / "spec-review.toml").exists()


class TestRemoveCodexSkills:
    def test_removes_existing_skill_files(self, skill_tree: Path) -> None:
        agents_dir = skill_tree / ".agents" / "skills" / "fix"
        agents_dir.mkdir(parents=True)
        (agents_dir / "SKILL.md").write_text("old content")
        (agents_dir / ".pilot-resources.json").write_text('{"files": [], "directories": []}\n')

        with patch("codex_skill_sync.Path.home", return_value=skill_tree):
            removed = _remove_codex_skills()
        assert removed == 1
        assert not (agents_dir / "SKILL.md").exists()

    def test_noop_when_no_skills(self, skill_tree: Path) -> None:
        with patch("codex_skill_sync.Path.home", return_value=skill_tree):
            removed = _remove_codex_skills()
        assert removed == 0

    def test_manifest_scoping_preserves_user_skill_with_pilot_name(self, tmp_path: Path) -> None:
        # A user named their own skill "fix" (a Pilot name) — but it is NOT in
        # the install manifest, so it must survive license enforcement.
        agents = tmp_path / ".agents" / "skills"
        (agents / "spec").mkdir(parents=True)
        (agents / "spec" / "SKILL.md").write_text("pilot spec")
        (agents / "spec" / ".pilot-resources.json").write_text('{"files": [], "directories": []}\n')
        (agents / "fix").mkdir(parents=True)
        (agents / "fix" / "SKILL.md").write_text("user fix")
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / ".pilot-manifest.json").write_text(json.dumps({"files": ["skills/spec/manifest.json"]}))

        with patch("codex_skill_sync.Path.home", return_value=tmp_path):
            removed = _remove_codex_skills()

        assert removed == 1
        assert not (agents / "spec" / "SKILL.md").exists()
        assert (agents / "fix" / "SKILL.md").exists()  # user skill preserved


class TestRemoveCodexReviewAgents:
    def test_removes_managed_review_agent_files_only(self, tmp_path: Path) -> None:
        agents_dir = tmp_path / ".codex" / "agents"
        agents_dir.mkdir(parents=True)
        (agents_dir / "spec-review.toml").write_text('# pilot-shell managed Codex review agent\nname = "spec-review"\n')
        (agents_dir / "changes-review.toml").write_text(
            '# pilot-shell managed Codex review agent\nname = "changes-review"\n'
        )
        (agents_dir / "user-agent.toml").write_text('name = "user-agent"\n')

        with patch("codex_skill_sync.Path.home", return_value=tmp_path):
            removed = _remove_codex_review_agents()

        assert removed == 2
        assert not (agents_dir / "spec-review.toml").exists()
        assert not (agents_dir / "changes-review.toml").exists()
        assert (agents_dir / "user-agent.toml").exists()

    def test_preserves_unmarked_same_name_review_agents(self, tmp_path: Path) -> None:
        agents_dir = tmp_path / ".codex" / "agents"
        agents_dir.mkdir(parents=True)
        (agents_dir / "spec-review.toml").write_text('name = "spec-review"\n')

        with patch("codex_skill_sync.Path.home", return_value=tmp_path):
            removed = _remove_codex_review_agents()

        assert removed == 0
        assert (agents_dir / "spec-review.toml").exists()

    def test_removes_managed_review_agents_from_codex_home(self, tmp_path: Path) -> None:
        codex_home = tmp_path / "custom-codex"
        agents_dir = codex_home / "agents"
        agents_dir.mkdir(parents=True)
        (agents_dir / "changes-review.toml").write_text(
            '# pilot-shell managed Codex review agent\nname = "changes-review"\n'
        )

        with (
            patch("codex_skill_sync.Path.home", return_value=tmp_path),
            patch.dict("codex_skill_sync.os.environ", {"CODEX_HOME": str(codex_home)}),
        ):
            removed = _remove_codex_review_agents()

        assert removed == 1
        assert not (agents_dir / "changes-review.toml").exists()


class TestCheckLicense:
    def test_returns_true_when_pilot_missing(self, tmp_path: Path) -> None:
        with patch("codex_skill_sync.Path.home", return_value=tmp_path):
            assert _check_license() is True

    def test_returns_true_on_valid_license(self, tmp_path: Path) -> None:
        pilot_bin = tmp_path / ".pilot" / "bin" / "pilot"
        pilot_bin.parent.mkdir(parents=True)
        pilot_bin.write_text("#!/bin/sh\necho '{\"valid\": true}'")
        pilot_bin.chmod(0o755)
        with patch("codex_skill_sync.Path.home", return_value=tmp_path):
            with patch("codex_skill_sync.subprocess.run") as mock_run:
                mock_run.return_value.stdout = '{"valid": true}'
                assert _check_license() is True

    def test_returns_false_on_invalid_license(self, tmp_path: Path) -> None:
        pilot_bin = tmp_path / ".pilot" / "bin" / "pilot"
        pilot_bin.parent.mkdir(parents=True)
        pilot_bin.write_text("#!/bin/sh")
        pilot_bin.chmod(0o755)
        with patch("codex_skill_sync.Path.home", return_value=tmp_path):
            with patch("codex_skill_sync.subprocess.run") as mock_run:
                mock_run.return_value.stdout = '{"valid": false}'
                assert _check_license() is False

    def test_returns_unknown_on_transient_verification_failure(self, tmp_path: Path) -> None:
        pilot_bin = tmp_path / ".pilot" / "bin" / "pilot"
        pilot_bin.parent.mkdir(parents=True)
        pilot_bin.write_text("#!/bin/sh")
        pilot_bin.chmod(0o755)
        with (
            patch("codex_skill_sync.Path.home", return_value=tmp_path),
            patch("codex_skill_sync.subprocess.run", side_effect=OSError("temporarily unavailable")),
        ):
            assert _check_license() is None

    def test_main_is_silent_after_successful_background_sync(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        codex_bin = tmp_path / ".codex" / "bin" / "codex"
        codex_bin.parent.mkdir(parents=True)
        codex_bin.write_text("#!/bin/sh\n")

        with (
            patch("codex_skill_sync.Path.home", return_value=tmp_path),
            patch("codex_skill_sync._check_license", return_value=True),
            patch("codex_skill_sync._sync_codex_skills", return_value=(2, 0)),
            patch("codex_skill_sync._sync_codex_review_agents", return_value=(1, 0)),
            patch("codex_skill_sync._sync_codex_env_vars", return_value=7),
        ):
            main()

        assert capsys.readouterr().out == ""

    def test_main_config_error_is_agent_context_not_user_warning(self, capsys: pytest.CaptureFixture[str]) -> None:
        with patch("codex_skill_sync._get_codex_config_dir", side_effect=ValueError("CODEX_HOME is relative")):
            main()

        output = json.loads(capsys.readouterr().out)
        assert "systemMessage" not in output
        context = output["hookSpecificOutput"]["additionalContext"]
        assert "CODEX_HOME is relative" in context
        assert "internal maintenance context" in context

    def test_main_preserves_assets_when_license_status_is_unknown(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        codex_bin = tmp_path / ".codex" / "bin" / "codex"
        codex_bin.parent.mkdir(parents=True)
        codex_bin.write_text("#!/bin/sh\n")
        skill = tmp_path / ".agents" / "skills" / "fix" / "SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text("managed skill")

        with (
            patch("codex_skill_sync.Path.home", return_value=tmp_path),
            patch("codex_skill_sync._check_license", return_value=None),
        ):
            main()

        assert skill.read_text() == "managed skill"
        assert capsys.readouterr().out == ""

    def test_main_invalid_license_removes_skills_and_review_agents(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        codex_bin = tmp_path / ".codex" / "bin" / "codex"
        codex_bin.parent.mkdir(parents=True)
        codex_bin.write_text("#!/bin/sh\n")
        skill_dir = tmp_path / ".agents" / "skills" / "fix"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("old skill")
        (skill_dir / ".pilot-resources.json").write_text('{"files": [], "directories": []}\n')
        codex_agents_dir = tmp_path / ".codex" / "agents"
        codex_agents_dir.mkdir(parents=True)
        (codex_agents_dir / "spec-review.toml").write_text(
            '# pilot-shell managed Codex review agent\nname = "spec-review"\n'
        )

        with (
            patch("codex_skill_sync.Path.home", return_value=tmp_path),
            patch("codex_skill_sync._check_license", return_value=False),
        ):
            main()

        assert not (skill_dir / "SKILL.md").exists()
        assert not (codex_agents_dir / "spec-review.toml").exists()
        output = json.loads(capsys.readouterr().out)
        assert "removed 2 Codex managed asset(s)" in output["systemMessage"]


class TestSyncCodexEnvVars:
    def test_writes_env_vars_from_config(self, tmp_path: Path) -> None:
        config = tmp_path / ".pilot" / "config.json"
        config.parent.mkdir(parents=True)
        config.write_text(
            json.dumps(
                {
                    "specWorkflow": {
                        "planApproval": False,
                        "branchIsolation": True,
                        "askQuestionsDuringPlanning": True,
                    }
                }
            )
        )
        codex_config = tmp_path / ".codex" / "config.toml"
        codex_config.parent.mkdir(parents=True)
        codex_config.write_text('approval_policy = "never"\n')

        with patch("codex_skill_sync.Path.home", return_value=tmp_path):
            count = _sync_codex_env_vars()

        assert count == 7
        content = codex_config.read_text()
        assert "[shell_environment_policy.set]" in content
        assert 'PILOT_PLAN_APPROVAL_ENABLED = "false"' in content
        assert 'PILOT_BRANCH_ISOLATION_ENABLED = "true"' in content
        # Automated model switching is Claude-Code-only -- Codex never gets the var.
        assert "PILOT_MODEL_SWITCH_ENABLED" not in content
        assert 'PILOT_PLAN_QUESTIONS_ENABLED = "true"' in content

    def test_writes_env_vars_to_codex_home_config(self, tmp_path: Path) -> None:
        codex_home = tmp_path / "custom-codex"
        codex_config = codex_home / "config.toml"
        codex_config.parent.mkdir(parents=True)
        codex_config.write_text('approval_policy = "never"\n')

        with (
            patch("codex_skill_sync.Path.home", return_value=tmp_path),
            patch.dict("codex_skill_sync.os.environ", {"CODEX_HOME": str(codex_home)}),
        ):
            count = _sync_codex_env_vars()

        assert count == 7
        assert 'PILOT_CHANGES_REVIEW_ENABLED = "true"' in codex_config.read_text()
        assert not (tmp_path / ".codex" / "config.toml").exists()

    def test_replaces_existing_managed_block(self, tmp_path: Path) -> None:
        config = tmp_path / ".pilot" / "config.json"
        config.parent.mkdir(parents=True)
        config.write_text(json.dumps({"specWorkflow": {"planApproval": True}}))
        codex_config = tmp_path / ".codex" / "config.toml"
        codex_config.parent.mkdir(parents=True)
        codex_config.write_text(
            'approval_policy = "never"\n'
            "\n# --- pilot-shell managed env vars ---\n"
            "[shell_environment_policy.set]\n"
            'PILOT_PLAN_APPROVAL_ENABLED = "false"\n'
            "# --- end pilot-shell managed env vars ---\n"
        )

        with patch("codex_skill_sync.Path.home", return_value=tmp_path):
            _sync_codex_env_vars()

        content = codex_config.read_text()
        assert content.count("shell_environment_policy") == 1
        assert 'PILOT_PLAN_APPROVAL_ENABLED = "true"' in content
        tomllib.loads(content)

    def test_preexisting_user_env_section_keeps_single_header_and_valid_toml(self, tmp_path: Path) -> None:
        """A config that already declares [shell_environment_policy.set] must not gain a duplicate header (fatal TOML error), and PILOT_* vars must land inside that table even when it is not the last one."""
        codex_config = tmp_path / ".codex" / "config.toml"
        codex_config.parent.mkdir(parents=True)
        codex_config.write_text(
            'approval_policy = "never"\n'
            "\n"
            "[shell_environment_policy]\n"
            'inherit = "all"\n'
            "\n"
            "[shell_environment_policy.set]\n"
            'SOME_EXISTING_VAR = "1"\n'
            "\n"
            '[projects."/tmp/repo"]\n'
            'trust_level = "trusted"\n'
        )

        with patch("codex_skill_sync.Path.home", return_value=tmp_path):
            count = _sync_codex_env_vars()

        assert count == 7
        content = codex_config.read_text()
        assert content.count("[shell_environment_policy.set]") == 1
        parsed = tomllib.loads(content)
        env_set = parsed["shell_environment_policy"]["set"]
        assert env_set["SOME_EXISTING_VAR"] == "1"
        assert env_set["PILOT_PLAN_APPROVAL_ENABLED"] == "true"
        assert parsed["projects"]["/tmp/repo"]["trust_level"] == "trusted"

        # Second sync is a no-op (idempotent).
        with patch("codex_skill_sync.Path.home", return_value=tmp_path):
            assert _sync_codex_env_vars() == 0
        assert codex_config.read_text() == content

    def test_heals_duplicate_header_left_by_previous_sync(self, tmp_path: Path) -> None:
        """Configs already broken by the duplicate-header bug get repaired to a single header."""
        codex_config = tmp_path / ".codex" / "config.toml"
        codex_config.parent.mkdir(parents=True)
        codex_config.write_text(
            "[shell_environment_policy.set]\n"
            'SOME_EXISTING_VAR = "1"\n'
            "\n# --- pilot-shell managed env vars ---\n"
            "[shell_environment_policy.set]\n"
            'PILOT_PLAN_APPROVAL_ENABLED = "false"\n'
            "# --- end pilot-shell managed env vars ---\n"
        )

        with patch("codex_skill_sync.Path.home", return_value=tmp_path):
            _sync_codex_env_vars()

        content = codex_config.read_text()
        assert content.count("[shell_environment_policy.set]") == 1
        parsed = tomllib.loads(content)
        assert parsed["shell_environment_policy"]["set"]["SOME_EXISTING_VAR"] == "1"
        assert parsed["shell_environment_policy"]["set"]["PILOT_PLAN_APPROVAL_ENABLED"] == "true"

    def test_heals_duplicate_managed_key_from_two_regions(self, tmp_path: Path) -> None:
        """Two managed regions (left by a double-write/race) must collapse to one;
        Codex aborts with 'duplicate key' if PILOT_* appears twice in the table."""
        codex_config = tmp_path / ".codex" / "config.toml"
        codex_config.parent.mkdir(parents=True)
        codex_config.write_text(
            'approval_policy = "never"\n'
            "\n# --- pilot-shell managed env vars ---\n"
            "[shell_environment_policy.set]\n"
            'PILOT_BRANCH_ISOLATION_ENABLED = "false"\n'
            'PILOT_PLAN_APPROVAL_ENABLED = "false"\n'
            "# --- end pilot-shell managed env vars ---\n"
            "\n# --- pilot-shell managed env vars ---\n"
            "[shell_environment_policy.set]\n"
            'PILOT_BRANCH_ISOLATION_ENABLED = "false"\n'
            'PILOT_PLAN_APPROVAL_ENABLED = "false"\n'
            "# --- end pilot-shell managed env vars ---\n"
        )

        with patch("codex_skill_sync.Path.home", return_value=tmp_path):
            _sync_codex_env_vars()

        content = codex_config.read_text()
        assert content.count("PILOT_BRANCH_ISOLATION_ENABLED =") == 1
        parsed = tomllib.loads(content)
        assert parsed["shell_environment_policy"]["set"]["PILOT_BRANCH_ISOLATION_ENABLED"] == "true"

    def test_heals_stray_managed_key_outside_markers(self, tmp_path: Path) -> None:
        """A managed key left in the table outside the markers (lost START marker)
        must not be re-emitted as a duplicate."""
        codex_config = tmp_path / ".codex" / "config.toml"
        codex_config.parent.mkdir(parents=True)
        codex_config.write_text(
            'approval_policy = "never"\n'
            "\n[shell_environment_policy.set]\n"
            'PILOT_BRANCH_ISOLATION_ENABLED = "false"\n'
            "# --- end pilot-shell managed env vars ---\n"
        )

        with patch("codex_skill_sync.Path.home", return_value=tmp_path):
            _sync_codex_env_vars()

        content = codex_config.read_text()
        assert content.count("PILOT_BRANCH_ISOLATION_ENABLED =") == 1
        parsed = tomllib.loads(content)
        assert parsed["shell_environment_policy"]["set"]["PILOT_BRANCH_ISOLATION_ENABLED"] == "true"

    def test_collapses_duplicate_env_table_headers(self, tmp_path: Path) -> None:
        """A user [shell_environment_policy.set] followed by a markerless old managed
        table is two declarations of the same table -- a fatal TOML error. Sync must
        collapse them into one and preserve the user's key."""
        codex_config = tmp_path / ".codex" / "config.toml"
        codex_config.parent.mkdir(parents=True)
        codex_config.write_text(
            'approval_policy = "never"\n'
            "\n[shell_environment_policy.set]\n"
            'SOME_EXISTING_VAR = "1"\n'
            "\n[shell_environment_policy.set]\n"
            'PILOT_BRANCH_ISOLATION_ENABLED = "false"\n'
            'PILOT_PLAN_APPROVAL_ENABLED = "false"\n'
        )

        with patch("codex_skill_sync.Path.home", return_value=tmp_path):
            _sync_codex_env_vars()

        content = codex_config.read_text()
        assert content.count("[shell_environment_policy.set]") == 1
        parsed = tomllib.loads(content)
        assert parsed["shell_environment_policy"]["set"]["SOME_EXISTING_VAR"] == "1"
        assert parsed["shell_environment_policy"]["set"]["PILOT_BRANCH_ISOLATION_ENABLED"] == "true"

        # Second sync is a no-op (idempotent).
        with patch("codex_skill_sync.Path.home", return_value=tmp_path):
            assert _sync_codex_env_vars() == 0
        assert codex_config.read_text() == content

    def test_dedup_is_scoped_to_env_table_and_preserves_other_tables(self, tmp_path: Path) -> None:
        """The managed-key dedup only touches [shell_environment_policy.set]; an
        identically-named key in a different table must survive untouched."""
        codex_config = tmp_path / ".codex" / "config.toml"
        codex_config.parent.mkdir(parents=True)
        codex_config.write_text(
            'approval_policy = "never"\n'
            "\n[other.table]\n"
            'PILOT_BRANCH_ISOLATION_ENABLED = "keep-me"\n'
            "\n[shell_environment_policy.set]\n"
            'SOME_EXISTING_VAR = "1"\n'
        )

        with patch("codex_skill_sync.Path.home", return_value=tmp_path):
            _sync_codex_env_vars()

        parsed = tomllib.loads(codex_config.read_text())
        assert parsed["other"]["table"]["PILOT_BRANCH_ISOLATION_ENABLED"] == "keep-me"
        assert parsed["shell_environment_policy"]["set"]["SOME_EXISTING_VAR"] == "1"
        assert parsed["shell_environment_policy"]["set"]["PILOT_BRANCH_ISOLATION_ENABLED"] == "true"

    def test_defaults_branch_isolation_to_true_when_config_missing(self, tmp_path: Path) -> None:
        """When config.json is absent, branchIsolation should default to true (matching Console)."""
        codex_config = tmp_path / ".codex" / "config.toml"
        codex_config.parent.mkdir(parents=True)
        codex_config.write_text('approval_policy = "never"\n')

        with patch("codex_skill_sync.Path.home", return_value=tmp_path):
            _sync_codex_env_vars()

        content = codex_config.read_text()
        assert 'PILOT_BRANCH_ISOLATION_ENABLED = "true"' in content

    def test_noop_when_no_codex_config(self, tmp_path: Path) -> None:
        with patch("codex_skill_sync.Path.home", return_value=tmp_path):
            assert _sync_codex_env_vars() == 0
