"""Tests for one-time model config migrations."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestMigrationV1:
    """Migration v0 -> v1: Update model routing from v7.0 to v7.1."""

    def test_v1_unit_spec_verify_opus_to_sonnet(self) -> None:
        """v1 migrates commands.spec-verify from opus to sonnet (in-memory raw dict)."""
        from installer.steps.config_migration import _migration_v1

        raw: dict = {"commands": {"spec-verify": "opus", "spec-plan": "opus"}}
        _migration_v1(raw)
        assert raw["commands"]["spec-verify"] == "sonnet"
        assert raw["commands"]["spec-plan"] == "opus"

    def test_v1_unit_spec_verify_sonnet_stays_sonnet(self) -> None:
        """v1 leaves spec-verify=sonnet alone (v8 later handles the sonnet->opus default)."""
        from installer.steps.config_migration import _migration_v1

        raw: dict = {"commands": {"spec-verify": "sonnet"}}
        _migration_v1(raw)
        assert raw["commands"]["spec-verify"] == "sonnet"

    def test_v1_unit_stale_agent_keys_removed(self) -> None:
        """Old agent keys from v7.0 are removed and plan-reviewer/spec-reviewer added."""
        from installer.steps.config_migration import _migration_v1

        raw: dict = {
            "agents": {
                "plan-challenger": "sonnet",
                "plan-verifier": "sonnet",
                "spec-reviewer-compliance": "sonnet",
                "spec-reviewer-quality": "opus",
                "spec-reviewer-goal": "sonnet",
            },
        }
        _migration_v1(raw)
        agents = raw["agents"]
        assert "plan-challenger" not in agents
        assert "plan-verifier" not in agents
        assert "spec-reviewer-compliance" not in agents
        assert "spec-reviewer-quality" not in agents
        assert "spec-reviewer-goal" not in agents
        assert agents["plan-reviewer"] == "sonnet"
        assert agents["spec-reviewer"] == "sonnet"

    def test_v1_unit_new_agent_keys_added_if_missing(self) -> None:
        """New plan-reviewer/spec-reviewer agent keys are added when they don't exist."""
        from installer.steps.config_migration import _migration_v1

        raw: dict = {
            "agents": {"plan-challenger": "sonnet", "plan-verifier": "sonnet"},
        }
        _migration_v1(raw)
        assert raw["agents"]["plan-reviewer"] == "sonnet"
        assert raw["agents"]["spec-reviewer"] == "sonnet"

    def test_config_version_set_after_migration(self, tmp_path: Path) -> None:
        """_configVersion is set to current after migration."""
        from installer.steps.config_migration import (
            CURRENT_CONFIG_VERSION,
            migrate_model_config,
        )

        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps({"model": "opus", "commands": {}}))

        migrate_model_config(config_path)

        migrated = json.loads(config_path.read_text())
        assert migrated["_configVersion"] == CURRENT_CONFIG_VERSION


class TestMigrationV2:
    """Migration v1 -> v2: Switch sync and learn commands from sonnet to opus."""

    def test_v2_unit_sync_and_learn_migrated_to_opus(self) -> None:
        """Both sync and learn skills are migrated from sonnet to opus."""
        from installer.steps.config_migration import _migration_v2

        raw: dict = {"commands": {"sync": "sonnet", "learn": "sonnet"}}
        _migration_v2(raw)
        assert raw["commands"]["sync"] == "opus"
        assert raw["commands"]["learn"] == "opus"

    def test_v2_unit_already_opus_not_changed(self) -> None:
        """Skills already set to opus are left alone."""
        from installer.steps.config_migration import _migration_v2

        raw: dict = {"commands": {"sync": "opus", "learn": "opus"}}
        result = _migration_v2(raw)
        assert result is False
        assert raw["commands"]["sync"] == "opus"
        assert raw["commands"]["learn"] == "opus"

    def test_v2_unit_partial_migration(self) -> None:
        """Only sonnet values are migrated; opus values are untouched."""
        from installer.steps.config_migration import _migration_v2

        raw: dict = {"commands": {"sync": "opus", "learn": "sonnet"}}
        _migration_v2(raw)
        assert raw["commands"]["sync"] == "opus"
        assert raw["commands"]["learn"] == "opus"


class TestMigrationIdempotency:
    """Migrations are skipped when already applied."""

    def test_skips_when_version_current(self, tmp_path: Path) -> None:
        """No changes when _configVersion matches current."""
        from installer.steps.config_migration import (
            CURRENT_CONFIG_VERSION,
            migrate_model_config,
        )

        config_path = tmp_path / "config.json"
        original = {
            "model": "opus",
            "commands": {"spec-verify": "opus"},
            "_configVersion": CURRENT_CONFIG_VERSION,
        }
        config_path.write_text(json.dumps(original))

        result = migrate_model_config(config_path)

        assert result is False
        assert json.loads(config_path.read_text()) == original

    def test_skips_when_no_config_file(self, tmp_path: Path) -> None:
        """Default behavior (create_if_missing=False) skips when config file is absent.

        Tests use this default so they don't trigger subprocess calls or write
        the user's real ~/.pilot/config.json as a side effect.
        """
        from installer.steps.config_migration import migrate_model_config

        result = migrate_model_config(tmp_path / "nonexistent.json")

        assert result is False

    def test_creates_subscription_aware_config_on_fresh_install(self, tmp_path: Path) -> None:
        """create_if_missing=True (used by installer) triggers fresh-install defaults.

        Regression: previously the installer skipped migrations entirely when no
        config file existed, leaving fresh Max installs to fall through to the
        legacy sonnet default for spec-implement/spec-verify - which doesn't work
        on Max plan because Max does not include sonnet 1M.
        """
        from installer.steps.config_migration import (
            CURRENT_CONFIG_VERSION,
            migrate_model_config,
        )

        config_path = tmp_path / "nonexistent.json"
        with patch("installer.steps.config_migration._get_subscription_type", return_value="max"):
            result = migrate_model_config(config_path, create_if_missing=True)

        assert result is True
        assert config_path.exists()
        written = json.loads(config_path.read_text())
        assert written.get("_configVersion") == CURRENT_CONFIG_VERSION

    def test_fresh_install_unknown_subscription_still_writes(self, tmp_path: Path) -> None:
        """When subscription can't be detected, fresh install still writes a versioned config."""
        from installer.steps.config_migration import migrate_model_config

        config_path = tmp_path / "nonexistent.json"
        with patch("installer.steps.config_migration._get_subscription_type", return_value=None):
            result = migrate_model_config(config_path, create_if_missing=True)

        assert result is True
        assert config_path.exists()

    def test_fresh_install_starts_in_manual_model_switch_mode(self, tmp_path: Path) -> None:
        """A first-time user drives /model themselves rather than getting opusplan.

        Upgraders are deliberately excluded - v20 keeps mapping their legacy ON/OFF
        toggle to "automated", so this is the one path that differs.
        """
        from installer.steps.config_migration import migrate_model_config

        config_path = tmp_path / "nonexistent.json"
        with patch("installer.steps.config_migration._get_subscription_type", return_value=None):
            migrate_model_config(config_path, create_if_missing=True)

        written = json.loads(config_path.read_text())
        assert written["specWorkflow"]["modelSwitchMode"] == "manual"

    def test_fresh_install_keeps_remaining_spec_workflow_defaults(self, tmp_path: Path) -> None:
        """The Manual seed must not displace the defaults v3/v4 write.

        Those migrations populate `specWorkflow` only when the key is absent
        entirely, so seeding the mode *before* the chain would silently drop
        branchIsolation / askQuestionsDuringPlanning / planApproval.
        """
        from installer.steps.config_migration import migrate_model_config

        config_path = tmp_path / "nonexistent.json"
        with patch("installer.steps.config_migration._get_subscription_type", return_value=None):
            migrate_model_config(config_path, create_if_missing=True)

        workflow = json.loads(config_path.read_text())["specWorkflow"]
        assert workflow["askQuestionsDuringPlanning"] is True
        assert workflow["planApproval"] is True
        assert workflow["branchIsolation"] is False

    def test_existing_config_without_mode_is_not_flipped_to_manual(self, tmp_path: Path) -> None:
        """An upgrader whose config predates the key keeps "automated"."""
        from installer.steps.config_migration import migrate_model_config

        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps({"_configVersion": 19, "specWorkflow": {"modelSwitch": True}}))
        migrate_model_config(config_path)

        written = json.loads(config_path.read_text())
        assert written["specWorkflow"]["modelSwitchMode"] == "automated"

    def test_second_run_is_noop(self, tmp_path: Path) -> None:
        """Running migration twice doesn't change anything the second time."""
        from installer.steps.config_migration import migrate_model_config

        config_path = tmp_path / "config.json"
        config_path.write_text(
            json.dumps(
                {
                    "model": "opus",
                    "commands": {"spec-verify": "opus"},
                    "agents": {"plan-challenger": "sonnet"},
                }
            )
        )

        migrate_model_config(config_path)
        first_result = config_path.read_text()

        result = migrate_model_config(config_path)

        assert result is False
        assert config_path.read_text() == first_result


class TestMigrationPreservesExistingData:
    """Migrations preserve non-model keys in config.json."""

    def test_preserves_non_model_keys(self, tmp_path: Path) -> None:
        """Non-model keys like auto_update survive the full migration chain through v12,
        while v12-pruned keys (model, agents, commands/skills, extendedContext) are removed."""
        from installer.steps.config_migration import migrate_model_config

        config_path = tmp_path / "config.json"
        config_path.write_text(
            json.dumps(
                {
                    "model": "opus",
                    "extendedContext": True,
                    "auto_update": True,
                    "commands": {"spec-verify": "opus"},
                    "agents": {},
                }
            )
        )

        migrate_model_config(config_path)

        migrated = json.loads(config_path.read_text())
        assert migrated["auto_update"] is True
        # v12 pruned the legacy model-routing keys
        assert "model" not in migrated
        assert "extendedContext" not in migrated
        assert "skills" not in migrated
        assert "agents" not in migrated

    def test_handles_missing_commands_key(self, tmp_path: Path) -> None:
        """Config without commands key doesn't crash."""
        from installer.steps.config_migration import (
            CURRENT_CONFIG_VERSION,
            migrate_model_config,
        )

        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps({"model": "opus"}))

        result = migrate_model_config(config_path)

        assert result is True
        migrated = json.loads(config_path.read_text())
        assert migrated["_configVersion"] == CURRENT_CONFIG_VERSION

    def test_handles_missing_agents_key(self, tmp_path: Path) -> None:
        """Config without agents key doesn't crash."""
        from installer.steps.config_migration import (
            CURRENT_CONFIG_VERSION,
            migrate_model_config,
        )

        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps({"model": "opus", "commands": {}}))

        result = migrate_model_config(config_path)

        assert result is True
        migrated = json.loads(config_path.read_text())
        assert migrated["_configVersion"] == CURRENT_CONFIG_VERSION


class TestMigrationV3:
    """Migration v2 -> v3: Disable plan review, spec review, and worktree support.

    Note: These tests use _configVersion: 2, so both v3 and v4 run.
    v3 disables, then v4 re-enables. Tests for v3 in isolation use
    the unit function directly.
    """

    def test_v3_disables_and_v4_preserves_user_choice(self, tmp_path: Path) -> None:
        """v3 disables worktree, v4 no longer force-re-enables it (preserves user choice)."""
        from installer.steps.config_migration import migrate_model_config

        config_path = tmp_path / "config.json"
        config_path.write_text(
            json.dumps(
                {
                    "model": "opus",
                    "reviewerAgents": {"planReviewer": True, "specReviewer": True},
                    "specWorkflow": {
                        "worktreeSupport": True,
                        "askQuestionsDuringPlanning": True,
                        "planApproval": True,
                    },
                    "_configVersion": 2,
                }
            )
        )

        result = migrate_model_config(config_path)

        assert result is True
        migrated = json.loads(config_path.read_text())
        # v3 disables worktree, v4 re-enables reviewers but NOT worktree, v7 renames, v11 renames to branchIsolation
        assert migrated["reviewerAgents"]["specReview"] is True
        assert migrated["reviewerAgents"]["changesReview"] is True
        # v4 no longer forces worktree back to True - respects whatever v3 set; v11 renamed worktreeSupport -> branchIsolation
        assert migrated["specWorkflow"]["branchIsolation"] is False
        assert "worktreeSupport" not in migrated["specWorkflow"]
        assert migrated["specWorkflow"]["askQuestionsDuringPlanning"] is True
        assert migrated["specWorkflow"]["planApproval"] is True

    def test_v3_unit_disables_when_enabled(self, tmp_path: Path) -> None:
        """v3 migration function disables enabled toggles."""
        from installer.steps.config_migration import _migration_v3

        raw = {
            "reviewerAgents": {"planReviewer": True, "specReviewer": True},
            "specWorkflow": {
                "worktreeSupport": True,
                "askQuestionsDuringPlanning": True,
                "planApproval": True,
            },
        }

        result = _migration_v3(raw)

        assert result is True
        assert raw["reviewerAgents"]["planReviewer"] is False
        assert raw["reviewerAgents"]["specReviewer"] is False
        assert raw["specWorkflow"]["worktreeSupport"] is False

    def test_v3_unit_creates_defaults_when_missing(self, tmp_path: Path) -> None:
        """v3 migration function creates defaults when keys are missing."""
        from installer.steps.config_migration import _migration_v3

        raw: dict = {"model": "opus"}

        result = _migration_v3(raw)

        assert result is True
        assert raw["reviewerAgents"]["planReviewer"] is False
        assert raw["reviewerAgents"]["specReviewer"] is False
        assert raw["specWorkflow"]["worktreeSupport"] is False
        assert raw["specWorkflow"]["askQuestionsDuringPlanning"] is True
        assert raw["specWorkflow"]["planApproval"] is True

    def test_preserves_other_spec_workflow_toggles(self, tmp_path: Path) -> None:
        """askQuestionsDuringPlanning and planApproval are preserved through v3+v4.

        Note: worktreeSupport is intentionally omitted from this input so v11 is
        a no-op for this test. The original intent is preserved - earlier-version
        migrations must not clobber unrelated keys.
        """
        from installer.steps.config_migration import migrate_model_config

        config_path = tmp_path / "config.json"
        config_path.write_text(
            json.dumps(
                {
                    "model": "opus",
                    "reviewerAgents": {"planReviewer": True, "specReviewer": True},
                    "specWorkflow": {
                        "askQuestionsDuringPlanning": False,
                        "planApproval": False,
                    },
                    "_configVersion": 2,
                }
            )
        )

        migrate_model_config(config_path)

        migrated = json.loads(config_path.read_text())
        assert migrated["specWorkflow"]["askQuestionsDuringPlanning"] is False
        assert migrated["specWorkflow"]["planApproval"] is False


class TestMigrationV4:
    """Migration v3 -> v4: Enable reviewer subagents, preserve worktree user choice."""

    def test_enables_reviewers_preserves_worktree(self, tmp_path: Path) -> None:
        """Reviewer agents are enabled but worktree is NOT force-enabled."""
        from installer.steps.config_migration import migrate_model_config

        config_path = tmp_path / "config.json"
        config_path.write_text(
            json.dumps(
                {
                    "model": "opus",
                    "reviewerAgents": {"planReviewer": False, "specReviewer": False},
                    "specWorkflow": {
                        "worktreeSupport": False,
                        "askQuestionsDuringPlanning": True,
                        "planApproval": True,
                    },
                    "_configVersion": 3,
                }
            )
        )

        result = migrate_model_config(config_path)

        assert result is True
        migrated = json.loads(config_path.read_text())
        # v4 enables reviewers, then v7 renames keys, v11 renames worktreeSupport -> branchIsolation
        assert migrated["reviewerAgents"]["specReview"] is True
        assert migrated["reviewerAgents"]["changesReview"] is True
        # v4 no longer forces worktree - user's False is preserved; v11 renamed key
        assert migrated["specWorkflow"]["branchIsolation"] is False
        assert "worktreeSupport" not in migrated["specWorkflow"]
        assert migrated["specWorkflow"]["askQuestionsDuringPlanning"] is True
        assert migrated["specWorkflow"]["planApproval"] is True

    def test_already_enabled_not_changed(self, tmp_path: Path) -> None:
        """Toggles already set to true are left alone."""
        from installer.steps.config_migration import migrate_model_config

        config_path = tmp_path / "config.json"
        config_path.write_text(
            json.dumps(
                {
                    "model": "opus",
                    "reviewerAgents": {"planReviewer": True, "specReviewer": True},
                    "specWorkflow": {
                        "worktreeSupport": True,
                        "askQuestionsDuringPlanning": True,
                        "planApproval": True,
                    },
                    "_configVersion": 3,
                }
            )
        )

        result = migrate_model_config(config_path)

        assert result is True
        migrated = json.loads(config_path.read_text())
        # v7 renames keys, v11 renames worktreeSupport -> branchIsolation
        assert migrated["reviewerAgents"]["specReview"] is True
        assert migrated["reviewerAgents"]["changesReview"] is True
        assert migrated["specWorkflow"]["branchIsolation"] is True
        assert "worktreeSupport" not in migrated["specWorkflow"]

    def test_partial_disabled(self, tmp_path: Path) -> None:
        """Only disabled toggles are enabled; already-true ones stay true."""
        from installer.steps.config_migration import migrate_model_config

        config_path = tmp_path / "config.json"
        config_path.write_text(
            json.dumps(
                {
                    "model": "opus",
                    "reviewerAgents": {"planReviewer": False, "specReviewer": True},
                    "specWorkflow": {
                        "worktreeSupport": True,
                        "askQuestionsDuringPlanning": True,
                        "planApproval": True,
                    },
                    "_configVersion": 3,
                }
            )
        )

        result = migrate_model_config(config_path)

        assert result is True
        migrated = json.loads(config_path.read_text())
        # v4 enables both, then v7 renames, v11 renames worktreeSupport -> branchIsolation
        assert migrated["reviewerAgents"]["specReview"] is True
        assert migrated["reviewerAgents"]["changesReview"] is True
        assert migrated["specWorkflow"]["branchIsolation"] is True
        assert "worktreeSupport" not in migrated["specWorkflow"]

    def test_missing_reviewer_agents_creates_enabled_defaults(self, tmp_path: Path) -> None:
        """Missing reviewerAgents key gets created with enabled defaults."""
        from installer.steps.config_migration import migrate_model_config

        config_path = tmp_path / "config.json"
        config_path.write_text(
            json.dumps(
                {
                    "model": "opus",
                    "commands": {},
                    "_configVersion": 3,
                }
            )
        )

        result = migrate_model_config(config_path)

        assert result is True
        migrated = json.loads(config_path.read_text())
        # v4 creates with old names enabled, v7 renames
        assert migrated["reviewerAgents"]["specReview"] is True
        assert migrated["reviewerAgents"]["changesReview"] is True

    def test_missing_spec_workflow_creates_safe_defaults(self, tmp_path: Path) -> None:
        """Missing specWorkflow key gets created with worktree disabled (safe default)."""
        from installer.steps.config_migration import migrate_model_config

        config_path = tmp_path / "config.json"
        config_path.write_text(
            json.dumps(
                {
                    "model": "opus",
                    "reviewerAgents": {"planReviewer": False, "specReviewer": False},
                    "_configVersion": 3,
                }
            )
        )

        result = migrate_model_config(config_path)

        assert result is True
        migrated = json.loads(config_path.read_text())
        # v11 renamed worktreeSupport -> branchIsolation
        assert migrated["specWorkflow"]["branchIsolation"] is False
        assert "worktreeSupport" not in migrated["specWorkflow"]
        assert migrated["specWorkflow"]["askQuestionsDuringPlanning"] is True
        assert migrated["specWorkflow"]["planApproval"] is True

    def test_preserves_other_spec_workflow_toggles(self, tmp_path: Path) -> None:
        """askQuestionsDuringPlanning and planApproval are preserved.

        Note: worktreeSupport is intentionally omitted from this input so v11 is
        a no-op for this test. The original intent is preserved - v4's migration
        must not clobber unrelated keys.
        """
        from installer.steps.config_migration import migrate_model_config

        config_path = tmp_path / "config.json"
        config_path.write_text(
            json.dumps(
                {
                    "model": "opus",
                    "reviewerAgents": {"planReviewer": False, "specReviewer": False},
                    "specWorkflow": {
                        "askQuestionsDuringPlanning": False,
                        "planApproval": False,
                    },
                    "_configVersion": 3,
                }
            )
        )

        migrate_model_config(config_path)

        migrated = json.loads(config_path.read_text())
        assert migrated["specWorkflow"]["askQuestionsDuringPlanning"] is False
        assert migrated["specWorkflow"]["planApproval"] is False


class TestMigrationV5:
    """Migration v4 -> v5: Enable extended context (1M) by default."""

    def test_full_chain_from_v4_lands_at_current_version_with_v12_post_state(self, tmp_path: Path) -> None:
        """End-to-end chain from v4 through v12: legacy model/extendedContext keys are pruned."""
        from installer.steps.config_migration import CURRENT_CONFIG_VERSION, migrate_model_config

        config_path = tmp_path / "config.json"
        config_path.write_text(
            json.dumps(
                {
                    "model": "opus",
                    "extendedContext": False,
                    "_configVersion": 4,
                }
            )
        )

        result = migrate_model_config(config_path)

        assert result is True
        migrated = json.loads(config_path.read_text())
        assert migrated["_configVersion"] == CURRENT_CONFIG_VERSION
        # v12 prunes the legacy model + extendedContext keys
        assert "model" not in migrated
        assert "extendedContext" not in migrated

    def test_v5_unit_returns_false_when_already_true(self) -> None:
        """Unit function returns False when no change needed."""
        from installer.steps.config_migration import _migration_v5

        raw: dict = {"extendedContext": True}
        assert _migration_v5(raw) is False

    def test_v5_unit_sets_true_when_false(self) -> None:
        """Unit function sets extendedContext to true."""
        from installer.steps.config_migration import _migration_v5

        raw: dict = {"extendedContext": False}
        result = _migration_v5(raw)

        assert result is True
        assert raw["extendedContext"] is True


class TestMigrationV6:
    """Migration v5 -> v6: Disable reviewer sub-agents for non-Max users."""

    def test_disables_agents_for_pro_users(self, tmp_path: Path) -> None:
        """Pro users get sub-agents disabled."""
        from installer.steps.config_migration import _migration_v6

        raw: dict = {
            "reviewerAgents": {"planReviewer": True, "specReviewer": True},
        }

        with patch("installer.steps.config_migration._get_subscription_type", return_value="pro"):
            result = _migration_v6(raw)

        assert result is True
        assert raw["reviewerAgents"]["planReviewer"] is False
        assert raw["reviewerAgents"]["specReviewer"] is False

    def test_disables_agents_for_team_users(self, tmp_path: Path) -> None:
        """Team users get sub-agents disabled."""
        from installer.steps.config_migration import _migration_v6

        raw: dict = {
            "reviewerAgents": {"planReviewer": True, "specReviewer": True},
        }

        with patch("installer.steps.config_migration._get_subscription_type", return_value="team"):
            result = _migration_v6(raw)

        assert result is True
        assert raw["reviewerAgents"]["planReviewer"] is False
        assert raw["reviewerAgents"]["specReviewer"] is False

    def test_disables_agents_for_enterprise_users(self, tmp_path: Path) -> None:
        """Enterprise users get sub-agents disabled."""
        from installer.steps.config_migration import _migration_v6

        raw: dict = {
            "reviewerAgents": {"planReviewer": True, "specReviewer": True},
        }

        with patch("installer.steps.config_migration._get_subscription_type", return_value="enterprise"):
            result = _migration_v6(raw)

        assert result is True
        assert raw["reviewerAgents"]["planReviewer"] is False
        assert raw["reviewerAgents"]["specReviewer"] is False

    def test_preserves_agents_for_max_users(self, tmp_path: Path) -> None:
        """Max users keep sub-agents enabled."""
        from installer.steps.config_migration import _migration_v6

        raw: dict = {
            "reviewerAgents": {"planReviewer": True, "specReviewer": True},
        }

        with patch("installer.steps.config_migration._get_subscription_type", return_value="max"):
            result = _migration_v6(raw)

        assert result is False
        assert raw["reviewerAgents"]["planReviewer"] is True
        assert raw["reviewerAgents"]["specReviewer"] is True

    def test_no_change_when_detection_fails(self, tmp_path: Path) -> None:
        """When subscription can't be detected, leave settings unchanged."""
        from installer.steps.config_migration import _migration_v6

        raw: dict = {
            "reviewerAgents": {"planReviewer": True, "specReviewer": True},
        }

        with patch("installer.steps.config_migration._get_subscription_type", return_value=None):
            result = _migration_v6(raw)

        assert result is False
        assert raw["reviewerAgents"]["planReviewer"] is True
        assert raw["reviewerAgents"]["specReviewer"] is True

    def test_creates_reviewer_agents_when_missing(self, tmp_path: Path) -> None:
        """Creates reviewerAgents dict with disabled values for non-Max users."""
        from installer.steps.config_migration import _migration_v6

        raw: dict = {"model": "opus"}

        with patch("installer.steps.config_migration._get_subscription_type", return_value="pro"):
            result = _migration_v6(raw)

        assert result is True
        assert raw["reviewerAgents"]["planReviewer"] is False
        assert raw["reviewerAgents"]["specReviewer"] is False

    def test_already_disabled_not_modified(self, tmp_path: Path) -> None:
        """Already-disabled agents are not re-modified."""
        from installer.steps.config_migration import _migration_v6

        raw: dict = {
            "reviewerAgents": {"planReviewer": False, "specReviewer": False},
        }

        with patch("installer.steps.config_migration._get_subscription_type", return_value="pro"):
            result = _migration_v6(raw)

        assert result is False
        assert raw["reviewerAgents"]["planReviewer"] is False
        assert raw["reviewerAgents"]["specReviewer"] is False

    def test_full_migration_for_pro_user(self, tmp_path: Path) -> None:
        """Full migrate_model_config disables agents for pro user at version 5."""
        from installer.steps.config_migration import CURRENT_CONFIG_VERSION, migrate_model_config

        config_path = tmp_path / "config.json"
        config_path.write_text(
            json.dumps(
                {
                    "model": "opus",
                    "reviewerAgents": {"planReviewer": True, "specReviewer": True},
                    "extendedContext": True,
                    "_configVersion": 5,
                }
            )
        )

        with patch("installer.steps.config_migration._get_subscription_type", return_value="pro"):
            result = migrate_model_config(config_path)

        assert result is True
        migrated = json.loads(config_path.read_text())
        # v6 disables, then v7 renames
        assert migrated["reviewerAgents"]["specReview"] is False
        assert migrated["reviewerAgents"]["changesReview"] is False
        assert migrated["_configVersion"] == CURRENT_CONFIG_VERSION

    def test_full_migration_for_max_user_preserves_agents(self, tmp_path: Path) -> None:
        """Full migrate_model_config preserves agents for max user at version 5."""
        from installer.steps.config_migration import CURRENT_CONFIG_VERSION, migrate_model_config

        config_path = tmp_path / "config.json"
        config_path.write_text(
            json.dumps(
                {
                    "model": "opus",
                    "reviewerAgents": {"planReviewer": True, "specReviewer": True},
                    "extendedContext": True,
                    "_configVersion": 5,
                }
            )
        )

        with patch("installer.steps.config_migration._get_subscription_type", return_value="max"):
            result = migrate_model_config(config_path)

        assert result is True
        migrated = json.loads(config_path.read_text())
        # v7 renames but preserves values
        assert migrated["reviewerAgents"]["specReview"] is True
        assert migrated["reviewerAgents"]["changesReview"] is True
        assert migrated["_configVersion"] == CURRENT_CONFIG_VERSION


class TestMigrationV7:
    """Migration v6 -> v7: Rename reviewer agents and add Codex reviewer config."""

    def test_renames_reviewer_agent_keys(self) -> None:
        """planReviewer -> specReview, specReviewer -> changesReview."""
        from installer.steps.config_migration import _migration_v7

        raw: dict = {
            "reviewerAgents": {"planReviewer": True, "specReviewer": False},
        }

        result = _migration_v7(raw)

        assert result is True
        assert raw["reviewerAgents"]["specReview"] is True
        assert raw["reviewerAgents"]["changesReview"] is False
        assert "planReviewer" not in raw["reviewerAgents"]
        assert "specReviewer" not in raw["reviewerAgents"]

    def test_renames_agent_model_keys(self) -> None:
        """plan-reviewer -> spec-review, spec-reviewer -> changes-review."""
        from installer.steps.config_migration import _migration_v7

        raw: dict = {
            "agents": {"plan-reviewer": "opus", "spec-reviewer": "sonnet"},
        }

        result = _migration_v7(raw)

        assert result is True
        assert raw["agents"]["spec-review"] == "opus"
        assert raw["agents"]["changes-review"] == "sonnet"
        assert "plan-reviewer" not in raw["agents"]
        assert "spec-reviewer" not in raw["agents"]

    def test_adds_codex_reviewers_defaults(self) -> None:
        """codexReviewers added with both disabled."""
        from installer.steps.config_migration import _migration_v7

        raw: dict = {"model": "opus"}

        result = _migration_v7(raw)

        assert result is True
        assert raw["codexReviewers"]["specReview"] is False
        assert raw["codexReviewers"]["changesReview"] is False

    def test_preserves_existing_codex_reviewers(self) -> None:
        """Existing codexReviewers not overwritten."""
        from installer.steps.config_migration import _migration_v7

        raw: dict = {
            "codexReviewers": {"specReview": True, "changesReview": True},
        }

        result = _migration_v7(raw)

        assert result is False
        assert raw["codexReviewers"]["specReview"] is True

    def test_noop_when_already_migrated(self) -> None:
        """No changes when keys already use new names."""
        from installer.steps.config_migration import _migration_v7

        raw: dict = {
            "reviewerAgents": {"specReview": True, "changesReview": True},
            "agents": {"spec-review": "sonnet", "changes-review": "sonnet"},
            "codexReviewers": {"specReview": False, "changesReview": False},
        }

        result = _migration_v7(raw)

        assert result is False


class TestGetSubscriptionType:
    """Tests for _get_subscription_type helper."""

    def test_returns_type_from_claude_auth_status(self) -> None:
        """Should return subscription type from claude auth status."""
        from installer.steps.config_migration import _get_subscription_type

        mock_result = MagicMock(
            returncode=0,
            stdout='{"loggedIn": true, "subscriptionType": "max"}',
        )

        with patch("subprocess.run", return_value=mock_result):
            result = _get_subscription_type()

        assert result == "max"

    def test_normalizes_to_lowercase(self) -> None:
        """Should normalize subscription type to lowercase."""
        from installer.steps.config_migration import _get_subscription_type

        mock_result = MagicMock(
            returncode=0,
            stdout='{"loggedIn": true, "subscriptionType": "Pro"}',
        )

        with patch("subprocess.run", return_value=mock_result):
            result = _get_subscription_type()

        assert result == "pro"

    def test_returns_none_when_claude_not_installed(self) -> None:
        """Should return None when claude CLI is not available."""
        from installer.steps.config_migration import _get_subscription_type

        with patch("subprocess.run", side_effect=FileNotFoundError("claude not found")):
            with patch("pathlib.Path.exists", return_value=False):
                result = _get_subscription_type()

        assert result is None

    def test_falls_back_to_credentials_file(self, tmp_path: Path) -> None:
        """Should fall back to credentials file when claude auth status fails."""
        from installer.steps.config_migration import _get_subscription_type

        mock_result = MagicMock(returncode=1, stdout="", stderr="not logged in")
        creds = {"claudeAiOauth": {"subscriptionType": "team"}}

        with (
            patch("subprocess.run", return_value=mock_result),
            patch("pathlib.Path.home", return_value=tmp_path),
        ):
            # Create the expected path structure
            claude_dir = tmp_path / ".claude"
            claude_dir.mkdir(exist_ok=True)
            creds_file = claude_dir / ".credentials.json"
            creds_file.write_text(json.dumps(creds))

            result = _get_subscription_type()

        assert result == "team"

    def test_returns_none_when_no_subscription_type(self) -> None:
        """Should return None when auth status has no subscriptionType."""
        from installer.steps.config_migration import _get_subscription_type

        mock_result = MagicMock(
            returncode=0,
            stdout='{"loggedIn": true}',
        )

        with (
            patch("subprocess.run", return_value=mock_result),
            patch("pathlib.Path.exists", return_value=False),
        ):
            result = _get_subscription_type()

        assert result is None


class TestMigrationV8:
    """Migration v7 -> v8: Rename commands->skills and default all to opus."""

    def test_v8_unit_commands_renamed_to_skills(self) -> None:
        """The 'commands' config key is renamed to 'skills' (direct call to _migration_v8)."""
        from installer.steps.config_migration import _migration_v8

        raw: dict = {"model": "opus", "commands": {"spec": "opus", "spec-plan": "opus"}}
        result = _migration_v8(raw)

        assert result is True
        assert "skills" in raw
        assert "commands" not in raw
        assert raw["skills"]["spec"] == "opus"

    def test_v8_unit_sonnet_defaults_migrated_to_opus(self) -> None:
        """spec, spec-implement, and spec-verify are migrated from sonnet to opus."""
        from installer.steps.config_migration import _migration_v8

        raw: dict = {
            "model": "opus",
            "commands": {
                "spec": "sonnet",
                "spec-plan": "opus",
                "spec-implement": "sonnet",
                "spec-verify": "sonnet",
            },
        }
        _migration_v8(raw)

        assert raw["skills"]["spec"] == "opus"
        assert raw["skills"]["spec-plan"] == "opus"
        assert raw["skills"]["spec-implement"] == "opus"
        assert raw["skills"]["spec-verify"] == "opus"

    def test_v8_unit_user_opus_choices_preserved(self) -> None:
        """Skills already set to opus are not changed."""
        from installer.steps.config_migration import _migration_v8

        raw: dict = {"model": "opus", "commands": {"spec": "opus", "spec-implement": "opus"}}
        _migration_v8(raw)

        assert raw["skills"]["spec"] == "opus"
        assert raw["skills"]["spec-implement"] == "opus"

    def test_v8_unit_extended_context_ensured(self) -> None:
        """extendedContext is set to true by v8 (before v12 prunes it)."""
        from installer.steps.config_migration import _migration_v8

        raw: dict = {"model": "opus", "extendedContext": False}
        _migration_v8(raw)

        assert raw["extendedContext"] is True

    def test_v8_unit_skills_key_not_overwritten_by_commands(self) -> None:
        """If both 'skills' and 'commands' exist, 'skills' is kept."""
        from installer.steps.config_migration import _migration_v8

        raw: dict = {"model": "opus", "skills": {"spec": "opus"}, "commands": {"spec": "sonnet"}}
        _migration_v8(raw)

        assert raw["skills"]["spec"] == "opus"


class TestMigrationV9:
    """Migration v8 -> v9: Set spec-implement/spec-verify to sonnet for non-Max users."""

    def test_sets_sonnet_for_pro_users(self) -> None:
        """Pro users get spec-implement and spec-verify set to sonnet."""
        from installer.steps.config_migration import _migration_v9

        raw: dict = {
            "skills": {"spec-implement": "opus", "spec-verify": "opus"},
        }

        with patch("installer.steps.config_migration._get_subscription_type", return_value="pro"):
            result = _migration_v9(raw)

        assert result is True
        assert raw["skills"]["spec-implement"] == "sonnet"
        assert raw["skills"]["spec-verify"] == "sonnet"

    def test_sets_sonnet_for_team_users(self) -> None:
        """Team users get spec-implement and spec-verify set to sonnet."""
        from installer.steps.config_migration import _migration_v9

        raw: dict = {
            "skills": {"spec-implement": "opus", "spec-verify": "opus"},
        }

        with patch("installer.steps.config_migration._get_subscription_type", return_value="team"):
            result = _migration_v9(raw)

        assert result is True
        assert raw["skills"]["spec-implement"] == "sonnet"
        assert raw["skills"]["spec-verify"] == "sonnet"

    def test_sets_sonnet_for_enterprise_users(self) -> None:
        """Enterprise users get spec-implement and spec-verify set to sonnet."""
        from installer.steps.config_migration import _migration_v9

        raw: dict = {
            "skills": {"spec-implement": "opus", "spec-verify": "opus"},
        }

        with patch("installer.steps.config_migration._get_subscription_type", return_value="enterprise"):
            result = _migration_v9(raw)

        assert result is True
        assert raw["skills"]["spec-implement"] == "sonnet"
        assert raw["skills"]["spec-verify"] == "sonnet"

    def test_sets_sonnet_for_api_users(self) -> None:
        """API-only users get spec-implement and spec-verify set to sonnet."""
        from installer.steps.config_migration import _migration_v9

        raw: dict = {
            "skills": {"spec-implement": "opus", "spec-verify": "opus"},
        }

        with patch("installer.steps.config_migration._get_subscription_type", return_value="api"):
            result = _migration_v9(raw)

        assert result is True
        assert raw["skills"]["spec-implement"] == "sonnet"
        assert raw["skills"]["spec-verify"] == "sonnet"

    def test_preserves_opus_for_max_users(self) -> None:
        """Max users keep spec-implement and spec-verify as opus."""
        from installer.steps.config_migration import _migration_v9

        raw: dict = {
            "skills": {"spec-implement": "opus", "spec-verify": "opus"},
        }

        with patch("installer.steps.config_migration._get_subscription_type", return_value="max"):
            result = _migration_v9(raw)

        assert result is False
        assert raw["skills"]["spec-implement"] == "opus"
        assert raw["skills"]["spec-verify"] == "opus"

    def test_no_change_when_detection_fails(self) -> None:
        """When subscription can't be detected, leave settings unchanged."""
        from installer.steps.config_migration import _migration_v9

        raw: dict = {
            "skills": {"spec-implement": "opus", "spec-verify": "opus"},
        }

        with patch("installer.steps.config_migration._get_subscription_type", return_value=None):
            result = _migration_v9(raw)

        assert result is False
        assert raw["skills"]["spec-implement"] == "opus"
        assert raw["skills"]["spec-verify"] == "opus"

    def test_creates_skills_dict_when_missing(self) -> None:
        """Creates skills dict with sonnet values for non-Max users when skills key absent."""
        from installer.steps.config_migration import _migration_v9

        raw: dict = {"model": "opus"}

        with patch("installer.steps.config_migration._get_subscription_type", return_value="pro"):
            result = _migration_v9(raw)

        assert result is True
        assert raw["skills"]["spec-implement"] == "sonnet"
        assert raw["skills"]["spec-verify"] == "sonnet"

    def test_already_sonnet_not_modified(self) -> None:
        """Skills already set to sonnet are not re-modified."""
        from installer.steps.config_migration import _migration_v9

        raw: dict = {
            "skills": {"spec-implement": "sonnet", "spec-verify": "sonnet"},
        }

        with patch("installer.steps.config_migration._get_subscription_type", return_value="pro"):
            result = _migration_v9(raw)

        assert result is False

    def test_handles_missing_skill_keys_in_existing_dict(self) -> None:
        """Skill keys absent from existing skills dict are treated as opus (migrated)."""
        from installer.steps.config_migration import _migration_v9

        raw: dict = {
            "skills": {"spec": "opus", "spec-plan": "opus"},
        }

        with patch("installer.steps.config_migration._get_subscription_type", return_value="pro"):
            result = _migration_v9(raw)

        assert result is True
        assert raw["skills"]["spec-implement"] == "sonnet"
        assert raw["skills"]["spec-verify"] == "sonnet"
        # Other skills unchanged
        assert raw["skills"]["spec"] == "opus"

    def test_full_migration_for_pro_user_runs_through_to_v12(self, tmp_path: Path) -> None:
        """Full migrate_model_config from v8 runs v9 (sonnet for pro) then v12 (prune model keys).
        The v9 effect is captured in the .bak.v11 backup; the on-disk config has the keys pruned."""
        from installer.steps.config_migration import CURRENT_CONFIG_VERSION, migrate_model_config

        config_path = tmp_path / "config.json"
        config_path.write_text(
            json.dumps(
                {
                    "model": "opus",
                    "skills": {
                        "spec": "opus",
                        "spec-plan": "opus",
                        "spec-implement": "opus",
                        "spec-verify": "opus",
                    },
                    "_configVersion": 8,
                }
            )
        )

        with patch("installer.steps.config_migration._get_subscription_type", return_value="pro"):
            result = migrate_model_config(config_path)

        assert result is True
        migrated = json.loads(config_path.read_text())
        assert migrated["_configVersion"] == CURRENT_CONFIG_VERSION
        # v12 pruned the legacy model + skills keys
        assert "model" not in migrated
        assert "skills" not in migrated
        # The pre-v12 backup captured the v8 input verbatim
        bak_path = config_path.with_suffix(".json.bak.v11")
        assert bak_path.exists()
        backup = json.loads(bak_path.read_text())
        assert backup["skills"]["spec-implement"] == "opus"  # v9 hasn't run on the backup

    def test_full_migration_for_max_user_runs_through_to_v12(self, tmp_path: Path) -> None:
        """Full migrate_model_config from v8 for max user runs the chain through v12.
        v9 leaves opus intact, v12 then prunes the keys; backup captures the v9 post-state."""
        from installer.steps.config_migration import CURRENT_CONFIG_VERSION, migrate_model_config

        config_path = tmp_path / "config.json"
        config_path.write_text(
            json.dumps(
                {
                    "model": "opus",
                    "skills": {
                        "spec": "opus",
                        "spec-plan": "opus",
                        "spec-implement": "opus",
                        "spec-verify": "opus",
                    },
                    "_configVersion": 8,
                }
            )
        )

        with patch("installer.steps.config_migration._get_subscription_type", return_value="max"):
            result = migrate_model_config(config_path)

        assert result is True
        migrated = json.loads(config_path.read_text())
        assert migrated["_configVersion"] == CURRENT_CONFIG_VERSION
        # v12 pruned the keys outright
        assert "model" not in migrated
        assert "skills" not in migrated
        # Backup preserves the v8 input
        bak_path = config_path.with_suffix(".json.bak.v11")
        backup = json.loads(bak_path.read_text())
        assert backup["skills"]["spec-implement"] == "opus"

    def test_no_spec_bugfix_verify_key_added(self) -> None:
        """Migration does not add spec-bugfix-verify key (alias handles it)."""
        from installer.steps.config_migration import _migration_v9

        raw: dict = {
            "skills": {"spec-implement": "opus", "spec-verify": "opus"},
        }

        with patch("installer.steps.config_migration._get_subscription_type", return_value="pro"):
            _migration_v9(raw)

        assert "spec-bugfix-verify" not in raw["skills"]


class TestMigrationV10:
    """Migration v9 -> v10: Issue #139 - strip alias [1m] from disk; preserve explicit-id [1m]."""

    def test_current_version_is_at_least_10(self) -> None:
        from installer.steps.config_migration import CURRENT_CONFIG_VERSION

        assert CURRENT_CONFIG_VERSION >= 10

    def test_strips_alias_1m_from_main_model(self) -> None:
        from installer.steps.config_migration import _migration_v10

        raw: dict = {"model": "opus[1m]"}
        modified = _migration_v10(raw)

        assert modified is True
        assert raw["model"] == "opus"

    def test_strips_alias_1m_from_skills(self) -> None:
        from installer.steps.config_migration import _migration_v10

        raw: dict = {
            "skills": {
                "spec-plan": "sonnet[1m]",
                "spec-implement": "opus[1m]",
                "spec-verify": "sonnet",
            }
        }
        modified = _migration_v10(raw)

        assert modified is True
        assert raw["skills"]["spec-plan"] == "sonnet"
        assert raw["skills"]["spec-implement"] == "opus"
        assert raw["skills"]["spec-verify"] == "sonnet"

    def test_preserves_explicit_id_1m_in_main_model(self) -> None:
        """Issue #139: <explicit-id>[1m] (e.g. claude-opus-4-7[1m]) preserved verbatim."""
        from installer.steps.config_migration import _migration_v10

        raw: dict = {"model": "claude-opus-4-7[1m]"}
        modified = _migration_v10(raw)

        assert modified is False
        assert raw["model"] == "claude-opus-4-7[1m]"

    def test_preserves_explicit_id_1m_in_skills(self) -> None:
        from installer.steps.config_migration import _migration_v10

        raw: dict = {"skills": {"spec-plan": "claude-opus-4-7[1m]"}}
        modified = _migration_v10(raw)

        assert modified is False
        assert raw["skills"]["spec-plan"] == "claude-opus-4-7[1m]"

    def test_does_not_touch_agents(self) -> None:
        """Issue #139: agents are out of scope; migration leaves any [1m] alone."""
        from installer.steps.config_migration import _migration_v10

        raw: dict = {"agents": {"spec-review": "sonnet[1m]"}}
        modified = _migration_v10(raw)

        assert modified is False
        assert raw["agents"]["spec-review"] == "sonnet[1m]"

    def test_noop_when_no_1m_anywhere(self) -> None:
        from installer.steps.config_migration import _migration_v10

        raw: dict = {"model": "opus", "skills": {"spec-plan": "sonnet"}}
        modified = _migration_v10(raw)

        assert modified is False

    def test_full_migration_strips_legacy_1m_runs_through_to_v12(self, tmp_path: Path) -> None:
        """End-to-end: a v9 config with legacy alias [1m] runs through v10 (strip [1m])
        and v12 (prune dead model keys) - final state has no model/skills keys."""
        from installer.steps.config_migration import CURRENT_CONFIG_VERSION, migrate_model_config

        config_path = tmp_path / "config.json"
        config_path.write_text(
            json.dumps(
                {
                    "_configVersion": 9,
                    "model": "opus[1m]",
                    "skills": {"spec-plan": "sonnet[1m]"},
                }
            )
        )

        result = migrate_model_config(config_path)

        assert result is True
        migrated = json.loads(config_path.read_text())
        assert migrated["_configVersion"] == CURRENT_CONFIG_VERSION
        # v12 pruned the dead keys outright
        assert "model" not in migrated
        assert "skills" not in migrated
        assert migrated["specWorkflow"]["modelSwitchMode"] == "manual"
        # v12 also wrote a backup with the pre-migration state
        bak_path = config_path.with_suffix(".json.bak.v11")
        assert bak_path.exists()
        backup = json.loads(bak_path.read_text())
        assert backup["model"] == "opus[1m]"
        assert backup["skills"]["spec-plan"] == "sonnet[1m]"

    def test_v10_idempotent(self, tmp_path: Path) -> None:
        """Re-running migrate on a fully-migrated config is a no-op.

        After v11, a config at version 10 with no legacy `worktreeSupport` key
        and no `branchIsolation` change still gets bumped to v11 - but only
        because the version sentinel is stale, not because the data needs
        rewriting. To keep the test's "data unchanged" intent, mark the input
        as already at CURRENT_CONFIG_VERSION.
        """
        from installer.steps.config_migration import CURRENT_CONFIG_VERSION, migrate_model_config

        config_path = tmp_path / "config.json"
        config_path.write_text(
            json.dumps({"_configVersion": CURRENT_CONFIG_VERSION, "model": "opus", "skills": {"spec-plan": "sonnet"}})
        )

        result = migrate_model_config(config_path)
        assert result is False


class TestMigrationV11:
    """Migration v10 -> v11: Rename specWorkflow.worktreeSupport -> branchIsolation."""

    def test_current_version_is_at_least_11(self) -> None:
        from installer.steps.config_migration import CURRENT_CONFIG_VERSION

        assert CURRENT_CONFIG_VERSION >= 11

    def test_v11_migrates_worktree_support_true(self) -> None:
        from installer.steps.config_migration import _migration_v11

        raw: dict = {"specWorkflow": {"worktreeSupport": True, "askQuestionsDuringPlanning": True}}
        modified = _migration_v11(raw)

        assert modified is True
        assert raw["specWorkflow"]["branchIsolation"] is True
        assert "worktreeSupport" not in raw["specWorkflow"]

    def test_v11_migrates_worktree_support_false(self) -> None:
        from installer.steps.config_migration import _migration_v11

        raw: dict = {"specWorkflow": {"worktreeSupport": False, "askQuestionsDuringPlanning": True}}
        modified = _migration_v11(raw)

        assert modified is True
        assert raw["specWorkflow"]["branchIsolation"] is False
        assert "worktreeSupport" not in raw["specWorkflow"]

    def test_v11_no_op_when_no_spec_workflow(self) -> None:
        from installer.steps.config_migration import _migration_v11

        raw: dict = {"model": "opus"}
        modified = _migration_v11(raw)

        assert modified is False
        assert "specWorkflow" not in raw

    def test_v11_no_op_when_no_worktree_support_key(self) -> None:
        from installer.steps.config_migration import _migration_v11

        raw: dict = {"specWorkflow": {"askQuestionsDuringPlanning": True, "planApproval": True}}
        modified = _migration_v11(raw)

        assert modified is False
        assert "branchIsolation" not in raw["specWorkflow"]

    def test_v11_unchanged_when_already_v11_and_no_legacy_keys(self) -> None:
        """A config at v11 with no legacy worktreeSupport gets no changes from _migration_v11."""
        from installer.steps.config_migration import _migration_v11

        raw: dict = {"specWorkflow": {"branchIsolation": True}}
        result = _migration_v11(raw)
        assert result is False
        assert raw["specWorkflow"]["branchIsolation"] is True

    def test_v11_preserves_other_spec_workflow_keys(self) -> None:
        from installer.steps.config_migration import _migration_v11

        raw: dict = {
            "specWorkflow": {
                "worktreeSupport": True,
                "askQuestionsDuringPlanning": False,
                "planApproval": False,
            }
        }
        modified = _migration_v11(raw)

        assert modified is True
        assert raw["specWorkflow"]["branchIsolation"] is True
        assert raw["specWorkflow"]["askQuestionsDuringPlanning"] is False
        assert raw["specWorkflow"]["planApproval"] is False

    def test_v11_both_keys_present_branchIsolation_wins(self) -> None:
        """If branchIsolation is already set, keep it - clean up legacy key only."""
        from installer.steps.config_migration import _migration_v11

        raw: dict = {
            "specWorkflow": {
                "worktreeSupport": True,
                "branchIsolation": False,
                "askQuestionsDuringPlanning": True,
            }
        }
        modified = _migration_v11(raw)

        assert modified is True
        # branchIsolation preserved at user's explicit value
        assert raw["specWorkflow"]["branchIsolation"] is False
        # legacy key cleaned up
        assert "worktreeSupport" not in raw["specWorkflow"]

    def test_v11_non_bool_worktree_support_defaults_to_false(self) -> None:
        """Non-bool legacy values fall back to False (safe default)."""
        from installer.steps.config_migration import _migration_v11

        raw: dict = {"specWorkflow": {"worktreeSupport": "yes"}}
        modified = _migration_v11(raw)

        assert modified is True
        assert raw["specWorkflow"]["branchIsolation"] is False
        assert "worktreeSupport" not in raw["specWorkflow"]

    def test_full_migration_renames_worktree_support_and_bumps_version(self, tmp_path: Path) -> None:
        """End-to-end: a v10 config with worktreeSupport reaches v11 with branchIsolation."""
        from installer.steps.config_migration import migrate_model_config

        config_path = tmp_path / "config.json"
        config_path.write_text(
            json.dumps(
                {
                    "_configVersion": 10,
                    "specWorkflow": {
                        "worktreeSupport": True,
                        "askQuestionsDuringPlanning": True,
                        "planApproval": True,
                    },
                }
            )
        )

        result = migrate_model_config(config_path)

        assert result is True
        migrated = json.loads(config_path.read_text())
        assert migrated["specWorkflow"]["branchIsolation"] is True
        assert "worktreeSupport" not in migrated["specWorkflow"]
        assert migrated["specWorkflow"]["askQuestionsDuringPlanning"] is True
        assert migrated["specWorkflow"]["planApproval"] is True


class TestMigrationV12:
    """Migration v11 -> v12: Strip dead model keys and write .bak.v11 once."""

    def test_v12_strips_dead_model_keys_without_enabling_model_switch(self, tmp_path: Path) -> None:
        from installer.steps.config_migration import migrate_model_config

        config_path = tmp_path / "config.json"
        config_path.write_text(
            json.dumps(
                {
                    "_configVersion": 11,
                    "model": "opus",
                    "skills": {"spec-plan": "opus", "spec-implement": "sonnet"},
                    "agents": {"spec-review": "sonnet"},
                    "extendedContext": True,
                    "extendedContextOverrides": {"main": True},
                    "specWorkflow": {
                        "branchIsolation": True,
                        "askQuestionsDuringPlanning": True,
                        "planApproval": True,
                    },
                    "reviewerAgents": {"specReview": True, "changesReview": True},
                }
            )
        )

        result = migrate_model_config(config_path)

        assert result is True
        migrated = json.loads(config_path.read_text())
        from installer.steps.config_migration import CURRENT_CONFIG_VERSION as _CCV2

        assert migrated["_configVersion"] == _CCV2
        for dead in ("model", "skills", "agents", "extendedContext", "extendedContextOverrides"):
            assert dead not in migrated, f"{dead} should have been pruned"
        assert migrated["specWorkflow"]["modelSwitchMode"] == "manual"
        assert migrated["specWorkflow"]["branchIsolation"] is True
        assert migrated["reviewerAgents"]["specReview"] is True

    def test_v12_writes_bak_v11_with_pre_migration_content(self, tmp_path: Path) -> None:
        from installer.steps.config_migration import migrate_model_config

        config_path = tmp_path / "config.json"
        pre_migration_payload = {
            "_configVersion": 11,
            "model": "opus",
            "skills": {"spec-plan": "opus"},
        }
        config_path.write_text(json.dumps(pre_migration_payload))

        migrate_model_config(config_path)

        bak_path = config_path.with_suffix(".json.bak.v11")
        assert bak_path.exists()
        backup = json.loads(bak_path.read_text())
        assert backup == pre_migration_payload

    def test_v12_bak_not_overwritten_on_second_run(self, tmp_path: Path) -> None:
        """Idempotency: backup holds genuine v11 snapshot even after re-runs."""
        from installer.steps.config_migration import migrate_model_config

        config_path = tmp_path / "config.json"
        original = {"_configVersion": 11, "model": "opus", "skills": {"spec-plan": "opus"}}
        config_path.write_text(json.dumps(original))

        migrate_model_config(config_path)
        first_backup = (config_path.with_suffix(".json.bak.v11")).read_text()

        # Re-run; config is already v12, but explicitly invoke again
        migrate_model_config(config_path)
        second_backup = (config_path.with_suffix(".json.bak.v11")).read_text()

        assert first_backup == second_backup
        assert json.loads(first_backup) == original

    def test_v12_config_migrates_forward_to_current(self, tmp_path: Path) -> None:
        """A config already at v12 still advances to the current version."""
        from installer.steps.config_migration import CURRENT_CONFIG_VERSION, migrate_model_config

        config_path = tmp_path / "config.json"
        config_path.write_text(
            json.dumps(
                {
                    "_configVersion": 12,
                    "specWorkflow": {"modelSwitch": True, "branchIsolation": True},
                }
            )
        )

        result = migrate_model_config(config_path)
        assert result is True
        migrated = json.loads(config_path.read_text())
        assert migrated["_configVersion"] == CURRENT_CONFIG_VERSION
        assert migrated["specWorkflow"]["modelSwitchMode"] == "automated"

    def test_v12_leaves_model_switch_manual_when_specworkflow_missing(self, tmp_path: Path) -> None:
        from installer.steps.config_migration import migrate_model_config

        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps({"_configVersion": 11}))

        migrate_model_config(config_path)
        migrated = json.loads(config_path.read_text())
        assert migrated["specWorkflow"]["modelSwitchMode"] == "manual"

    def test_v12_in_isolation_preserves_user_model_switch_false(self) -> None:
        """v12 ALONE preserves an explicit modelSwitch=false (v13 is what force-enables)."""
        from installer.steps.config_migration import _migration_v12

        raw: dict = {"specWorkflow": {"modelSwitch": False, "branchIsolation": True}}
        _migration_v12(raw)
        assert raw["specWorkflow"]["modelSwitch"] is False


class TestMigrationV13:
    """Migration v12 -> v13: force-enable automated model switching + strip dead isolated-impl keys."""

    def test_current_version_is_at_least_13(self) -> None:
        from installer.steps.config_migration import CURRENT_CONFIG_VERSION

        assert CURRENT_CONFIG_VERSION >= 13

    def test_v13_preserves_explicit_model_switch_false(self) -> None:
        from installer.steps.config_migration import _migration_v13

        # The historical force-enable is retired so v20 can map an explicit
        # pre-v13 OFF to modelSwitchMode "off" (ordering bug fix).
        raw: dict = {"specWorkflow": {"modelSwitch": False}}
        _migration_v13(raw)
        assert raw["specWorkflow"]["modelSwitch"] is False

    def test_v13_seeds_spec_workflow_when_missing(self) -> None:
        from installer.steps.config_migration import _migration_v13

        raw: dict = {}
        modified = _migration_v13(raw)
        assert modified is True
        assert raw["specWorkflow"] == {}

    def test_v13_no_change_when_already_true_and_no_dead_keys(self) -> None:
        from installer.steps.config_migration import _migration_v13

        raw: dict = {"specWorkflow": {"modelSwitch": True}}
        modified = _migration_v13(raw)

        assert modified is False
        assert raw["specWorkflow"]["modelSwitch"] is True

    def test_v13_strips_dead_isolated_impl_keys_when_model_switch_true(self) -> None:
        """Dead keys from the reverted isolated-implementation plan are removed."""
        from installer.steps.config_migration import _migration_v13

        raw: dict = {
            "specWorkflow": {
                "modelSwitch": True,
                "isolatedImplementation": False,
                "implementationModel": "sonnet",
                "branchIsolation": True,
            }
        }
        modified = _migration_v13(raw)

        assert modified is True
        sw = raw["specWorkflow"]
        assert "isolatedImplementation" not in sw
        assert "implementationModel" not in sw
        assert sw["modelSwitch"] is True
        assert sw["branchIsolation"] is True

    def test_v13_strips_dead_keys_and_preserves_model_switch(self) -> None:
        from installer.steps.config_migration import _migration_v13

        raw: dict = {
            "specWorkflow": {
                "modelSwitch": False,
                "isolatedImplementation": True,
                "implementationModel": "sonnet",
            }
        }
        modified = _migration_v13(raw)
        assert modified is True
        assert "isolatedImplementation" not in raw["specWorkflow"]
        assert "implementationModel" not in raw["specWorkflow"]
        assert raw["specWorkflow"]["modelSwitch"] is False  # explicit OFF preserved

    def test_full_migration_from_v12_false_lands_on_off(self, tmp_path: Path) -> None:
        from installer.steps.config_migration import CURRENT_CONFIG_VERSION, migrate_model_config

        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps({"_configVersion": 12, "specWorkflow": {"modelSwitch": False}}))
        result = migrate_model_config(config_path)
        assert result is True
        migrated = json.loads(config_path.read_text())
        assert migrated["_configVersion"] == CURRENT_CONFIG_VERSION
        # The explicit pre-v13 opt-out survives every historical force-enable
        # (v13 + v18 both retired theirs) and maps to "off" in v20.
        assert migrated["specWorkflow"]["modelSwitchMode"] == "off"
        assert "modelSwitch" not in migrated["specWorkflow"]

    def test_v13_advances_to_current_dropping_context_window(self, tmp_path: Path) -> None:
        """A config at v13 advances to current; the legacy per-model object is gone
        (v16) and the single contextWindow key is dropped entirely (v17)."""
        from installer.steps.config_migration import CURRENT_CONFIG_VERSION, migrate_model_config

        config_path = tmp_path / "config.json"
        config_path.write_text(
            json.dumps(
                {
                    "_configVersion": 13,
                    "specWorkflow": {"modelSwitch": True, "branchIsolation": True},
                }
            )
        )

        result = migrate_model_config(config_path)
        assert result is True
        migrated = json.loads(config_path.read_text())
        assert migrated["_configVersion"] == CURRENT_CONFIG_VERSION
        assert "contextWindow" not in migrated
        assert "contextWindows" not in migrated


class TestMigrationV14:
    """Migration v13 -> v14: seed contextWindows default {opus:1m, sonnet:200k}."""

    def test_current_version_is_at_least_14(self) -> None:
        from installer.steps.config_migration import CURRENT_CONFIG_VERSION

        assert CURRENT_CONFIG_VERSION >= 14

    def test_v14_seeds_context_windows_when_absent(self) -> None:
        from installer.steps.config_migration import _migration_v14

        raw: dict = {}
        modified = _migration_v14(raw)

        assert modified is True
        assert raw["contextWindows"] == {"opus": "1m", "sonnet": "200k"}

    def test_v14_preserves_existing_context_windows(self) -> None:
        from installer.steps.config_migration import _migration_v14

        existing = {"opus": "200k", "sonnet": "200k"}
        raw: dict = {"contextWindows": dict(existing)}
        modified = _migration_v14(raw)

        assert modified is False
        assert raw["contextWindows"] == existing

    def test_v14_seeds_when_context_windows_not_dict(self) -> None:
        from installer.steps.config_migration import _migration_v14

        raw: dict = {"contextWindows": "1m"}
        modified = _migration_v14(raw)

        assert modified is True
        assert raw["contextWindows"] == {"opus": "1m", "sonnet": "200k"}

    def test_full_migration_from_v13_lands_safe_context_window(self, tmp_path: Path) -> None:
        from installer.steps.config_migration import CURRENT_CONFIG_VERSION, migrate_model_config

        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps({"_configVersion": 13, "specWorkflow": {"modelSwitch": True}}))

        result = migrate_model_config(config_path)

        assert result is True
        migrated = json.loads(config_path.read_text())
        assert migrated["_configVersion"] == CURRENT_CONFIG_VERSION
        # v14 seeds the legacy object mid-chain, v16 collapses it to a single key,
        # v17 drops that key -- end state has no context-window config at all.
        assert "contextWindow" not in migrated
        assert "contextWindows" not in migrated

    def test_v14_config_advances_to_current_dropping_code_review(self, tmp_path: Path) -> None:
        """A config at v14 (legacy contextWindows present, codeReview absent) advances:
        v15 seeds codeReview, v16 collapses contextWindows to a single key, v17 drops
        that key entirely, and v21 removes codeReview along with the whole setting."""
        from installer.steps.config_migration import CURRENT_CONFIG_VERSION, migrate_model_config

        config_path = tmp_path / "config.json"
        config_path.write_text(
            json.dumps(
                {
                    "_configVersion": 14,
                    "specWorkflow": {"modelSwitch": True},
                    "contextWindows": {"opus": "200k", "sonnet": "200k"},
                }
            )
        )

        result = migrate_model_config(config_path)
        assert result is True
        migrated = json.loads(config_path.read_text())
        assert migrated["_configVersion"] == CURRENT_CONFIG_VERSION
        # v15 seeds effort xhigh, v18 relaxes it, v19 replaces effort with modes,
        # v21 removes the section outright.
        assert "codeReview" not in migrated
        # Both the legacy per-model object and the collapsed single key are gone.
        assert "contextWindows" not in migrated
        assert "contextWindow" not in migrated


class TestMigrationV15:
    """Migration v14 -> v15: seed codeReview default {effort: xhigh}."""

    def test_current_version_is_at_least_15(self) -> None:
        from installer.steps.config_migration import CURRENT_CONFIG_VERSION

        assert CURRENT_CONFIG_VERSION >= 15

    def test_v15_seeds_code_review_when_absent(self) -> None:
        from installer.steps.config_migration import _migration_v15

        raw: dict = {}
        modified = _migration_v15(raw)

        assert modified is True
        assert raw["codeReview"] == {"effort": "xhigh"}

    def test_v15_preserves_existing_code_review(self) -> None:
        from installer.steps.config_migration import _migration_v15

        raw: dict = {"codeReview": {"effort": "high"}}
        modified = _migration_v15(raw)

        assert modified is False
        assert raw["codeReview"] == {"effort": "high"}


class TestMigrationV16:
    """Migration v15 -> v16: collapse contextWindows{opus,sonnet} -> contextWindow="200k"."""

    def test_v16_drops_legacy_object_and_seeds_safe_default(self) -> None:
        from installer.steps.config_migration import _migration_v16

        # The legacy 1m value is NOT carried forward: v14 seeded opus=1m for every
        # config, so it is rarely deliberate, and 1M needs usage credits on Max.
        raw: dict = {"contextWindows": {"opus": "1m", "sonnet": "200k"}}
        modified = _migration_v16(raw)

        assert modified is True
        assert "contextWindows" not in raw
        assert raw["contextWindow"] == "200k"

    def test_v16_seeds_default_when_nothing_present(self) -> None:
        from installer.steps.config_migration import _migration_v16

        raw: dict = {}
        modified = _migration_v16(raw)

        assert modified is True
        assert raw["contextWindow"] == "200k"

    def test_v16_preserves_a_valid_new_context_window(self) -> None:
        from installer.steps.config_migration import _migration_v16

        # A contextWindow already set (e.g. by a newer Console build) is left as-is.
        raw: dict = {"contextWindow": "1m"}
        modified = _migration_v16(raw)

        assert modified is False
        assert raw["contextWindow"] == "1m"

    def test_v15_seeds_when_code_review_not_dict(self) -> None:
        from installer.steps.config_migration import _migration_v15

        raw: dict = {"codeReview": "high"}
        modified = _migration_v15(raw)

        assert modified is True
        assert raw["codeReview"] == {"effort": "xhigh"}

    def test_full_migration_from_v14_drops_code_review_and_bumps_version(self, tmp_path: Path) -> None:
        from installer.steps.config_migration import CURRENT_CONFIG_VERSION, migrate_model_config

        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps({"_configVersion": 14, "contextWindows": {"opus": "1m", "sonnet": "200k"}}))

        result = migrate_model_config(config_path)

        assert result is True
        migrated = json.loads(config_path.read_text())
        assert migrated["_configVersion"] == CURRENT_CONFIG_VERSION
        # v15 seeds effort xhigh, v18 relaxes it, v19 replaces effort with modes,
        # v21 removes the section outright.
        assert "codeReview" not in migrated

    def test_v15_config_advances_to_current_dropping_context_window(self, tmp_path: Path) -> None:
        from installer.steps.config_migration import CURRENT_CONFIG_VERSION, migrate_model_config

        config_path = tmp_path / "config.json"
        config_path.write_text(
            json.dumps(
                {
                    "_configVersion": 15,
                    "contextWindows": {"opus": "1m", "sonnet": "200k"},
                    "codeReview": {"effort": "high"},
                }
            )
        )

        result = migrate_model_config(config_path)
        # v15 -> v16 collapses the legacy object to contextWindow="200k"; v16 -> v17
        # then drops contextWindow entirely (Opus Plan is always 1M now).
        assert result is True
        migrated = json.loads(config_path.read_text())
        assert migrated["_configVersion"] == CURRENT_CONFIG_VERSION
        assert "contextWindows" not in migrated
        assert "contextWindow" not in migrated
        # v19 replaces the legacy effort with modes; v21 removes the section.
        assert "codeReview" not in migrated


class TestMigrationV17:
    """Migration v16 -> v17: drop the obsolete contextWindow key (Opus Plan is always 1M)."""

    def test_v17_drops_context_window(self) -> None:
        from installer.steps.config_migration import _migration_v17

        raw: dict = {"contextWindow": "200k"}
        modified = _migration_v17(raw)

        assert modified is True
        assert "contextWindow" not in raw

    def test_v17_noop_when_absent(self) -> None:
        from installer.steps.config_migration import _migration_v17

        raw: dict = {"codeReview": {"effort": "high"}}
        modified = _migration_v17(raw)

        assert modified is False
        assert raw == {"codeReview": {"effort": "high"}}

    def test_full_migration_from_v16_drops_context_window_and_bumps_version(self, tmp_path: Path) -> None:
        from installer.steps.config_migration import CURRENT_CONFIG_VERSION, migrate_model_config

        config_path = tmp_path / "config.json"
        config_path.write_text(
            json.dumps(
                {
                    "_configVersion": 16,
                    "contextWindow": "200k",
                    "codeReview": {"effort": "high"},
                }
            )
        )

        result = migrate_model_config(config_path)
        assert result is True
        migrated = json.loads(config_path.read_text())
        assert migrated["_configVersion"] == CURRENT_CONFIG_VERSION
        assert "contextWindow" not in migrated
        # v19 replaces the legacy effort with modes; v21 removes the section.
        assert "codeReview" not in migrated


class TestMigrationV18:
    """Migration v17 -> v18: force-enable modelSwitch; flip blanket codeReview xhigh -> high."""

    def test_v18_no_longer_touches_model_switch(self) -> None:
        from installer.steps.config_migration import _migration_v18

        # The historical force-enable is retired: a deliberate opt-out must
        # survive v18 so _migration_v20 can map it to "off" (ordering bug fix).
        raw: dict = {"specWorkflow": {"modelSwitch": False, "planApproval": True}}
        _migration_v18(raw)

        assert raw["specWorkflow"]["modelSwitch"] is False
        assert raw["specWorkflow"]["planApproval"] is True  # other toggles untouched

    def test_v18_seeds_spec_workflow_when_absent(self) -> None:
        from installer.steps.config_migration import _migration_v18

        raw: dict = {}
        modified = _migration_v18(raw)

        assert modified is True
        assert raw["specWorkflow"] == {}

    def test_v18_flips_blanket_xhigh_to_high(self) -> None:
        from installer.steps.config_migration import _migration_v18

        raw: dict = {"specWorkflow": {"modelSwitch": True}, "codeReview": {"effort": "xhigh"}}
        modified = _migration_v18(raw)

        assert modified is True
        assert raw["codeReview"]["effort"] == "high"

    def test_v18_preserves_deliberate_non_xhigh_effort(self) -> None:
        from installer.steps.config_migration import _migration_v18

        raw: dict = {"specWorkflow": {"modelSwitch": True}, "codeReview": {"effort": "max"}}
        modified = _migration_v18(raw)

        assert modified is False  # nothing to change: effort deliberate, switch untouched
        assert raw["codeReview"]["effort"] == "max"

    def test_full_migration_from_v17_forces_switch_and_flips_effort(self, tmp_path: Path) -> None:
        from installer.steps.config_migration import CURRENT_CONFIG_VERSION, migrate_model_config

        config_path = tmp_path / "config.json"
        config_path.write_text(
            json.dumps(
                {
                    "_configVersion": 17,
                    "specWorkflow": {"modelSwitch": False},
                    "codeReview": {"effort": "xhigh"},
                }
            )
        )

        result = migrate_model_config(config_path)
        assert result is True
        migrated = json.loads(config_path.read_text())
        assert migrated["_configVersion"] == CURRENT_CONFIG_VERSION
        # The explicit pre-v18 opt-out survives to v20 and maps to "off"
        # (the historical v18 force-enable is retired -- ordering bug fix).
        assert migrated["specWorkflow"]["modelSwitchMode"] == "off"
        # v18 flips xhigh -> high, v19 replaces effort with modes, v21 removes it.
        assert "codeReview" not in migrated


class TestMigrationV19:
    """Migration v18 -> v19: per-workflow changes-review modes replace codeReview.effort."""

    def test_v19_replaces_legacy_effort_with_agent_defaults(self) -> None:
        from installer.steps.config_migration import _migration_v19

        # Every stored effort tier is replaced -- deliberate product decision:
        # everyone starts on the cheap single sub-agent and re-opts into the
        # multi-agent /code-review via Console Settings.
        for effort in ("low", "medium", "high", "xhigh", "max"):
            raw: dict = {"codeReview": {"effort": effort}}
            assert _migration_v19(raw) is True
            assert raw["codeReview"] == {"spec": "agent", "fix": "agent"}

    def test_v19_seeds_default_when_absent_or_not_dict(self) -> None:
        from installer.steps.config_migration import _migration_v19

        raw: dict = {}
        assert _migration_v19(raw) is True
        assert raw["codeReview"] == {"spec": "agent", "fix": "agent"}

        raw = {"codeReview": "high"}
        assert _migration_v19(raw) is True
        assert raw["codeReview"] == {"spec": "agent", "fix": "agent"}

    def test_v19_preserves_valid_post_v19_shape(self) -> None:
        from installer.steps.config_migration import _migration_v19

        raw: dict = {"codeReview": {"spec": "high", "fix": "agent"}}
        assert _migration_v19(raw) is False
        assert raw["codeReview"] == {"spec": "high", "fix": "agent"}

    def test_v19_preserves_valid_partial_shape(self) -> None:
        from installer.steps.config_migration import _migration_v19

        # Upgrade window: a new Console bundle can merge a partial PUT (only one
        # workflow key) onto a pre-v19 config. A valid subset is a deliberate
        # choice -- runtime readers default the missing key to "agent".
        raw: dict = {"codeReview": {"spec": "high"}}
        assert _migration_v19(raw) is False
        assert raw["codeReview"] == {"spec": "high"}

    def test_v19_replaces_mixed_or_invalid_shape(self) -> None:
        from installer.steps.config_migration import _migration_v19

        # Mixed legacy + new keys, or invalid mode values, reset wholesale.
        raw: dict = {"codeReview": {"spec": "high", "effort": "xhigh"}}
        assert _migration_v19(raw) is True
        assert raw["codeReview"] == {"spec": "agent", "fix": "agent"}

        raw = {"codeReview": {"spec": "ultra", "fix": "agent"}}
        assert _migration_v19(raw) is True
        assert raw["codeReview"] == {"spec": "agent", "fix": "agent"}

    def test_v19_replaces_unhashable_values_without_raising(self) -> None:
        from installer.steps.config_migration import _migration_v19

        # A corrupt/hand-edited dict or list value must trigger the wholesale
        # replace, not a TypeError from the frozenset membership test.
        raw: dict = {"codeReview": {"spec": ["agent"], "fix": {"mode": "agent"}}}
        assert _migration_v19(raw) is True
        assert raw["codeReview"] == {"spec": "agent", "fix": "agent"}

    def test_full_migration_from_v18_replaces_effort(self, tmp_path: Path) -> None:
        from installer.steps.config_migration import CURRENT_CONFIG_VERSION, migrate_model_config

        config_path = tmp_path / "config.json"
        config_path.write_text(
            json.dumps(
                {
                    "_configVersion": 18,
                    "specWorkflow": {"modelSwitch": True},
                    "codeReview": {"effort": "high"},
                }
            )
        )

        result = migrate_model_config(config_path)
        assert result is True
        migrated = json.loads(config_path.read_text())
        assert migrated["_configVersion"] == CURRENT_CONFIG_VERSION
        # v19 replaced effort with per-workflow modes; v21 then removed the section.
        assert "codeReview" not in migrated
        assert migrated["specWorkflow"]["modelSwitchMode"] == "automated"  # v20 maps the forced switch to manual

    def test_idempotent_when_already_current(self, tmp_path: Path) -> None:
        from installer.steps.config_migration import CURRENT_CONFIG_VERSION, migrate_model_config

        config_path = tmp_path / "config.json"
        config_path.write_text(
            json.dumps(
                {
                    "_configVersion": CURRENT_CONFIG_VERSION,
                    "specWorkflow": {"modelSwitch": True},
                    "codeReview": {"spec": "high", "fix": "agent"},
                }
            )
        )

        result = migrate_model_config(config_path)
        assert result is False


class TestMigrationV20:
    """v19 -> v20: three-way modelSwitchMode replaces the pin-era keys."""

    def _migrate(self, tmp_path: Path, payload: dict) -> dict:
        from installer.steps.config_migration import migrate_model_config

        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps(payload))
        migrate_model_config(config_path=config_path)
        return json.loads(config_path.read_text())

    def test_legacy_true_maps_to_automated(self, tmp_path: Path) -> None:
        result = self._migrate(tmp_path, {"_configVersion": 19, "specWorkflow": {"modelSwitch": True}})
        sw = result["specWorkflow"]
        assert sw["modelSwitchMode"] == "automated"
        assert "modelSwitch" not in sw
        assert result["_configVersion"] == 21

    def test_legacy_false_maps_to_off(self, tmp_path: Path) -> None:
        result = self._migrate(
            tmp_path,
            {"_configVersion": 19, "specWorkflow": {"modelSwitch": False, "planModel": "fable", "execModel": "opus"}},
        )
        sw = result["specWorkflow"]
        assert sw["modelSwitchMode"] == "off"
        for retired in ("modelSwitch", "planModel", "execModel"):
            assert retired not in sw

    def test_absent_keys_default_to_manual(self, tmp_path: Path) -> None:
        result = self._migrate(tmp_path, {"_configVersion": 19, "specWorkflow": {"planApproval": True}})
        assert result["specWorkflow"]["modelSwitchMode"] == "manual"
        assert result["specWorkflow"]["planApproval"] is True  # untouched sibling

    @pytest.mark.parametrize("version", range(20))
    def test_full_migration_without_model_switch_opt_in_stays_manual(self, tmp_path: Path, version: int) -> None:
        result = self._migrate(tmp_path, {"_configVersion": version})
        assert result["specWorkflow"]["modelSwitchMode"] == "manual"

    @pytest.mark.parametrize("legacy", [None, "true", "false", 1, 0, [], {}])
    def test_invalid_legacy_switch_does_not_opt_in(self, tmp_path: Path, legacy: object) -> None:
        result = self._migrate(tmp_path, {"_configVersion": 19, "specWorkflow": {"modelSwitch": legacy}})
        assert result["specWorkflow"]["modelSwitchMode"] == "manual"

    def test_explicit_mode_from_newer_console_is_preserved(self, tmp_path: Path) -> None:
        result = self._migrate(
            tmp_path,
            {"_configVersion": 19, "specWorkflow": {"modelSwitchMode": "automated", "modelSwitch": True}},
        )
        sw = result["specWorkflow"]
        assert sw["modelSwitchMode"] == "automated"
        assert "modelSwitch" not in sw

    def test_second_run_is_noop(self, tmp_path: Path) -> None:
        from installer.steps.config_migration import migrate_model_config

        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps({"_configVersion": 19, "specWorkflow": {"modelSwitch": True}}))
        assert migrate_model_config(config_path=config_path) is True
        first = config_path.read_text()
        assert migrate_model_config(config_path=config_path) is False
        assert config_path.read_text() == first

    def test_v19_code_review_output_removed_by_v21(self, tmp_path: Path) -> None:
        # v20 leaves codeReview alone, but the v21 that follows in the same pass
        # removes it -- the full chain must land with the section gone.
        result = self._migrate(
            tmp_path,
            {"_configVersion": 19, "codeReview": {"spec": "high", "fix": "agent"}, "specWorkflow": {}},
        )
        assert "codeReview" not in result
        assert result["specWorkflow"]["modelSwitchMode"] == "manual"


class TestMigrationV21:
    """v20 -> v21: the codeReview section is removed entirely.

    `/code-review` carries `disable-model-invocation`, so the skill-mode tiers
    the section selected could never actually run -- the changes review is
    always the `changes-review` sub-agent, gated by the Changes Review toggle.
    """

    def _migrate(self, tmp_path: Path, payload: dict) -> dict:
        from installer.steps.config_migration import migrate_model_config

        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps(payload))
        migrate_model_config(config_path=config_path)
        return json.loads(config_path.read_text())

    def test_removes_per_workflow_modes(self, tmp_path: Path) -> None:
        result = self._migrate(
            tmp_path,
            {"_configVersion": 20, "codeReview": {"spec": "high", "fix": "xhigh"}},
        )
        assert "codeReview" not in result
        assert result["_configVersion"] == 21

    def test_removes_legacy_effort_shape(self, tmp_path: Path) -> None:
        result = self._migrate(tmp_path, {"_configVersion": 20, "codeReview": {"effort": "xhigh"}})
        assert "codeReview" not in result

    def test_removes_non_dict_value(self, tmp_path: Path) -> None:
        result = self._migrate(tmp_path, {"_configVersion": 20, "codeReview": "high"})
        assert "codeReview" not in result

    def test_absent_section_is_a_noop(self, tmp_path: Path) -> None:
        from installer.steps.config_migration import _migration_v21

        raw: dict = {"specWorkflow": {"planApproval": True}}
        assert _migration_v21(raw) is False
        assert raw == {"specWorkflow": {"planApproval": True}}

    def test_preserves_sibling_sections(self, tmp_path: Path) -> None:
        result = self._migrate(
            tmp_path,
            {
                "_configVersion": 20,
                "codeReview": {"spec": "high", "fix": "agent"},
                "reviewerAgents": {"specReview": True, "changesReview": False},
                "specWorkflow": {"modelSwitchMode": "manual", "planApproval": True},
                "teamRemote": "git@example.com:team/extensions.git",
            },
        )
        assert "codeReview" not in result
        assert result["reviewerAgents"] == {"specReview": True, "changesReview": False}
        assert result["specWorkflow"]["modelSwitchMode"] == "manual"
        assert result["teamRemote"] == "git@example.com:team/extensions.git"

    def test_second_run_is_noop(self, tmp_path: Path) -> None:
        from installer.steps.config_migration import migrate_model_config

        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps({"_configVersion": 20, "codeReview": {"spec": "high"}}))
        assert migrate_model_config(config_path=config_path) is True
        first = config_path.read_text()
        assert migrate_model_config(config_path=config_path) is False
        assert config_path.read_text() == first


class TestSubscriptionTypeInvalidConfigDir:
    """An undetectable subscription must return None, the "leave settings alone" signal.

    Every other failure path in _get_subscription_type returns None, and both
    callers guard only on `is None`. Returning "" would fall through that guard
    AND the `== "max"` guard, so the migration would proceed as if the user were
    a confirmed non-Max subscriber.
    """

    def test_invalid_config_dir_returns_none(self, monkeypatch):
        from installer.steps import config_migration

        monkeypatch.setenv("CLAUDE_CONFIG_DIR", "relative/path")
        # Force the `claude auth status` probe to fail so we reach the creds path.
        # subprocess is imported inside the function, so patch it at the source.
        import subprocess

        monkeypatch.setattr(subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(OSError("no claude binary")))

        assert config_migration._get_subscription_type() is None
