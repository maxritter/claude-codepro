"""Tests for cc_skill_sync hook — Claude Code SKILL.md license gating.

Verifies that Pilot-managed CC skills are removed when the license is invalid
and restored when valid, and that user-created skills are NEVER touched.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Add hooks dir to path so we can import the module + _lib.
_hooks_dir = Path(__file__).resolve().parent.parent
if str(_hooks_dir) not in sys.path:
    sys.path.insert(0, str(_hooks_dir))

from _lib.util import pilot_owned_skill_names  # noqa: E402
from cc_skill_sync import (  # noqa: E402
    _build_skill,
    _rebuild_cc_skills,
    _remove_cc_skills,
    main,
)


def _make_skill(skills_dir: Path, name: str, body: str = "Do the thing.") -> Path:
    """Create a decomposed skill dir with source fragments + a built SKILL.md."""
    skill_dir = skills_dir / name
    (skill_dir / "steps").mkdir(parents=True)
    (skill_dir / "manifest.json").write_text(
        json.dumps(
            {
                "version": 1,
                "orchestrator": "orchestrator.md",
                "steps": [{"id": "s1", "file": "steps/01.md"}],
            }
        )
    )
    (skill_dir / "orchestrator.md").write_text(
        f"---\nname: {name}\ndescription: {name} skill\n---\n\n# /{name}\n\n{body}"
    )
    (skill_dir / "steps" / "01.md").write_text("## Step 1\n\nFirst step.")
    (skill_dir / "SKILL.md").write_text(f"BUILT {name}")
    return skill_dir


def test_retired_owned_skill_cannot_self_heal(tmp_path: Path) -> None:
    skills = tmp_path / "skills"
    retired = _make_skill(skills, "bot-boot")
    personal = _make_skill(skills, "bot-jobs")
    for _ in range(2):
        assert _rebuild_cc_skills(skills, {"bot-boot"}) == 0
        assert not (retired / "SKILL.md").exists()
    assert (personal / "SKILL.md").read_text() == "BUILT bot-jobs"


@pytest.fixture()
def claude_tree(tmp_path: Path) -> Path:
    """~/.claude with a Pilot skill (`spec`) and a user skill (`myskill`).

    The manifest tracks only the Pilot skill's source manifest.
    """
    claude_dir = tmp_path / ".claude"
    skills_dir = claude_dir / "skills"
    _make_skill(skills_dir, "spec")
    _make_skill(skills_dir, "myskill")  # user skill — not in manifest
    (claude_dir / ".pilot-manifest.json").write_text(
        json.dumps(
            {
                "files": [
                    "skills/spec/manifest.json",
                    "skills/spec/orchestrator.md",
                    "skills/spec/steps/01.md",
                    "rules/testing.md",
                ]
            }
        )
    )
    return tmp_path


class TestPilotOwnedSkillNames:
    def test_returns_only_manifest_tracked_skills(self, claude_tree: Path) -> None:
        names = pilot_owned_skill_names(claude_tree / ".claude")
        assert names == {"spec"}

    def test_empty_when_manifest_missing(self, tmp_path: Path) -> None:
        (tmp_path / ".claude").mkdir()
        assert pilot_owned_skill_names(tmp_path / ".claude") == set()

    def test_empty_when_manifest_corrupt(self, tmp_path: Path) -> None:
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / ".pilot-manifest.json").write_text("{not json")
        assert pilot_owned_skill_names(claude_dir) == set()


class TestBuildSkill:
    def test_concatenates_orchestrator_and_steps(self, claude_tree: Path) -> None:
        result = _build_skill(claude_tree / ".claude" / "skills" / "spec")
        assert result is not None
        assert "# /spec" in result
        assert "## Step 1" in result

    def test_returns_none_for_missing_manifest(self, tmp_path: Path) -> None:
        assert _build_skill(tmp_path / "nope") is None

    @pytest.mark.parametrize("unsafe", ["../secret.md", "/tmp/secret.md", "steps\\secret.md"])
    def test_rejects_unsafe_manifest_paths(self, tmp_path: Path, unsafe: str) -> None:
        skill_dir = tmp_path / "skill"
        skill_dir.mkdir()
        (skill_dir / "manifest.json").write_text(json.dumps({"version": 1, "orchestrator": unsafe, "steps": []}))

        assert _build_skill(skill_dir) is None

    def test_progressive_manifest_builds_step_index_without_inlining_body(self, claude_tree: Path) -> None:
        skill_dir = claude_tree / ".claude" / "skills" / "spec"
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
        assert "steps/01.md" in result
        assert "First step." not in result


class TestRemoveCCSkills:
    def test_removes_skill_md_but_keeps_source(self, claude_tree: Path) -> None:
        skills_dir = claude_tree / ".claude" / "skills"
        removed = _remove_cc_skills(skills_dir, {"spec"})
        assert removed == 1
        assert not (skills_dir / "spec" / "SKILL.md").exists()
        # Source fragments survive so reactivation can rebuild.
        assert (skills_dir / "spec" / "manifest.json").exists()
        assert (skills_dir / "spec" / "orchestrator.md").exists()

    def test_never_touches_skills_outside_name_set(self, claude_tree: Path) -> None:
        skills_dir = claude_tree / ".claude" / "skills"
        _remove_cc_skills(skills_dir, {"spec"})
        assert (skills_dir / "myskill" / "SKILL.md").exists()


class TestRebuildCCSkills:
    def test_rebuilds_missing_skill_md(self, claude_tree: Path) -> None:
        skills_dir = claude_tree / ".claude" / "skills"
        (skills_dir / "spec" / "SKILL.md").unlink()
        rebuilt = _rebuild_cc_skills(skills_dir, {"spec"})
        assert rebuilt == 1
        content = (skills_dir / "spec" / "SKILL.md").read_text()
        assert "# /spec" in content and "## Step 1" in content

    def test_does_not_clobber_present_skill_md(self, claude_tree: Path) -> None:
        skills_dir = claude_tree / ".claude" / "skills"
        rebuilt = _rebuild_cc_skills(skills_dir, {"spec"})
        assert rebuilt == 0
        assert (skills_dir / "spec" / "SKILL.md").read_text() == "BUILT spec"

    def test_codex_only_target_removes_stale_claude_artifact(self, claude_tree: Path) -> None:
        skills_dir = claude_tree / ".claude" / "skills"
        skill_dir = skills_dir / "spec"
        manifest = json.loads((skill_dir / "manifest.json").read_text())
        manifest.update(
            {
                "version": 2,
                "delivery": "bundled",
                "targets": ["codex"],
                "visibility": "public",
                "invocation": "explicit",
            }
        )
        (skill_dir / "manifest.json").write_text(json.dumps(manifest))

        assert _rebuild_cc_skills(skills_dir, {"spec"}) == 0
        assert not (skill_dir / "SKILL.md").exists()


class TestMain:
    def test_invalid_license_removes_pilot_skill_only(self, claude_tree: Path) -> None:
        skills_dir = claude_tree / ".claude" / "skills"
        with (
            patch("cc_skill_sync.Path.home", return_value=claude_tree),
            patch("cc_skill_sync._check_license", return_value=False),
        ):
            main()
        assert not (skills_dir / "spec" / "SKILL.md").exists()
        assert (skills_dir / "myskill" / "SKILL.md").exists()  # user skill preserved

    def test_valid_license_restores_missing_skill(self, claude_tree: Path) -> None:
        skills_dir = claude_tree / ".claude" / "skills"
        (skills_dir / "spec" / "SKILL.md").unlink()
        with (
            patch("cc_skill_sync.Path.home", return_value=claude_tree),
            patch("cc_skill_sync._check_license", return_value=True),
        ):
            main()
        assert (skills_dir / "spec" / "SKILL.md").exists()

    def test_no_manifest_is_noop_even_when_invalid(self, tmp_path: Path) -> None:
        skills_dir = tmp_path / ".claude" / "skills"
        _make_skill(skills_dir, "spec")  # present, but no manifest at all
        with (
            patch("cc_skill_sync.Path.home", return_value=tmp_path),
            patch("cc_skill_sync._check_license", return_value=False),
        ):
            main()
        # Without a manifest we cannot prove ownership → touch nothing.
        assert (skills_dir / "spec" / "SKILL.md").exists()

    def test_invalid_config_dir_deletes_nothing_in_personal_profile(
        self, claude_tree: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A mistyped CLAUDE_CONFIG_DIR must not delete skills from ~/.claude.

        This hook removes SKILL.md files on an invalid license. Falling back to
        the default directory on a bad env var would mutate exactly the profile
        the user set the variable to protect.
        """
        skills_dir = claude_tree / ".claude" / "skills"
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", "relative/path")

        with (
            patch("cc_skill_sync.Path.home", return_value=claude_tree),
            patch("cc_skill_sync._check_license", return_value=False),
        ):
            main()

        assert (skills_dir / "spec" / "SKILL.md").exists()
        assert (skills_dir / "myskill" / "SKILL.md").exists()
        assert json.loads(capsys.readouterr().out)["continue"] is True

    def test_emits_continue_true(self, claude_tree: Path, capsys: pytest.CaptureFixture[str]) -> None:
        with (
            patch("cc_skill_sync.Path.home", return_value=claude_tree),
            patch("cc_skill_sync._check_license", return_value=False),
        ):
            main()
        out = json.loads(capsys.readouterr().out)
        assert out == {"continue": True}
