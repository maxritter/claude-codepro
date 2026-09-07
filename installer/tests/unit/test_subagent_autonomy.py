"""Pilot leaves subagent topology to the active Claude Code or Codex agent."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from installer.skill_builder import build_skill_md
from installer.steps.codex_files import _adapt_invocation_syntax, build_codex_skill_md

ROOT = Path(__file__).resolve().parents[3]
SKILLS = ("build", "spec-plan", "spec-implement", "spec-verify", "spec-bugfix-verify")
ALL_SKILLS = tuple(sorted(path.parent.name for path in (ROOT / "pilot" / "skills").glob("*/manifest.json")))
BANNED = (
    "no sub-agents",
    "no subagents",
    "no writing sub-agents",
    "one research agent is allowed",
    "only reviewer sub-agent",
)
UNBOUNDED_DELEGATION = (
    "spawn any additional agents you judge useful",
    "use any available subagents, including nested agents",
    "may spawn, resume, or nest agents for any verification work",
    "use the harness's agent tools whenever useful",
    "allow them to delegate further",
    "subagent fan-out (read-only, cheap",
)


def _runtime_text(name: str, *, codex: bool) -> str:
    skill = ROOT / "pilot" / "skills" / name
    manifest = json.loads((skill / "manifest.json").read_text())
    main = build_codex_skill_md(skill) if codex else build_skill_md(skill)
    parts = [main]
    if manifest.get("delivery") == "progressive":
        for step in manifest["steps"]:
            content = (skill / step["file"]).read_text()
            parts.append(_adapt_invocation_syntax(content) if codex else content)
    return "\n".join(parts).lower()


@pytest.mark.parametrize("skill_name", SKILLS)
@pytest.mark.parametrize("codex", [False, True], ids=["claude", "codex"])
def test_workflow_skills_have_no_blanket_subagent_prohibition(skill_name: str, codex: bool) -> None:
    text = _runtime_text(skill_name, codex=codex)

    for phrase in BANNED:
        assert phrase not in text


@pytest.mark.parametrize("skill_name", ALL_SKILLS)
@pytest.mark.parametrize("codex", [False, True], ids=["claude", "codex"])
def test_workflow_skills_have_no_unbounded_delegation_prompt(skill_name: str, codex: bool) -> None:
    text = _runtime_text(skill_name, codex=codex)

    for phrase in UNBOUNDED_DELEGATION:
        assert phrase not in text


def test_shared_rules_forbid_delegation_permission_questions() -> None:
    rule = (ROOT / "pilot" / "rules" / "task-and-workflow.md").read_text().lower()
    codex = (ROOT / "pilot" / "codex" / "AGENTS.md").read_text().lower()

    assert "never stop a running task to ask the user for permission" in rule
    assert "never stop work to ask the user for permission to delegate" in codex


def test_shared_rules_keep_bounded_work_in_the_current_agent() -> None:
    rule = (ROOT / "pilot" / "rules" / "task-and-workflow.md").read_text().lower()
    codex = (ROOT / "pilot" / "codex" / "AGENTS.md").read_text().lower()

    for content in (rule, codex):
        assert "direct execution is the baseline" in content
        assert "a handful of tool calls" in content
        assert "start with the minimum useful count" in content


def test_shared_rules_authorize_qualifying_delegation_without_a_user_request() -> None:
    rule = (ROOT / "pilot" / "rules" / "task-and-workflow.md").read_text().lower()
    codex = (ROOT / "pilot" / "codex" / "AGENTS.md").read_text().lower()

    for content in (rule, codex):
        assert "is the authorization" in content
        assert "main-context headroom" in content


def test_shared_rules_make_agent_stop_requests_immediate() -> None:
    rule = (ROOT / "pilot" / "rules" / "task-and-workflow.md").read_text().lower()
    codex = (ROOT / "pilot" / "codex" / "AGENTS.md").read_text().lower()

    for content in (rule, codex):
        assert "treat that as an immediate interruption" in content
        assert "never claim that nothing is running from a peer-session list alone" in content
        assert "stop or interrupt controls" in content


def test_hook_matrix_has_no_subagent_permission_gate() -> None:
    matrix = json.loads((ROOT / "pilot" / "hooks" / "hook-lifecycle.json").read_text())

    for entry in matrix["entries"]:
        matcher = (entry.get("matcher") or "").lower()
        assert "agent" not in matcher
        assert "task" not in matcher


def test_hook_manifests_do_not_spawn_model_agents() -> None:
    for name in ("hooks.json", "codex_hooks.json"):
        manifest = json.loads((ROOT / "pilot" / "hooks" / name).read_text())
        for groups in manifest["hooks"].values():
            for group in groups:
                matcher = (group.get("matcher") or "").lower()
                assert "agent" not in matcher
                assert "task" not in matcher
                assert all(handler["type"] == "command" for handler in group["hooks"])
