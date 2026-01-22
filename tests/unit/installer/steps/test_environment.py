"""Tests for installer/steps/environment.py."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from installer.context import InstallContext
from installer.steps.environment import (
    EnvironmentStep,
    create_claude_config,
    create_claude_credentials,
    credentials_exist,
    get_env_value,
)


class TestGetEnvValue:
    """Tests for get_env_value function."""

    def test_get_env_value_returns_value_for_existing_key(self, tmp_path: Path) -> None:
        """Should return the value when key exists."""
        env_file = tmp_path / ".env"
        env_file.write_text("API_KEY=secret123\nOTHER_KEY=other\n")

        result = get_env_value("API_KEY", env_file)

        assert result == "secret123"

    def test_get_env_value_returns_none_for_missing_key(self, tmp_path: Path) -> None:
        """Should return None when key doesn't exist."""
        env_file = tmp_path / ".env"
        env_file.write_text("OTHER_KEY=value\n")

        result = get_env_value("MISSING_KEY", env_file)

        assert result is None

    def test_get_env_value_returns_none_for_empty_value(self, tmp_path: Path) -> None:
        """Should return None when key exists but value is empty."""
        env_file = tmp_path / ".env"
        env_file.write_text("EMPTY_KEY=\n")

        result = get_env_value("EMPTY_KEY", env_file)

        assert result is None

    def test_get_env_value_returns_none_for_missing_file(self, tmp_path: Path) -> None:
        """Should return None when file doesn't exist."""
        env_file = tmp_path / ".env"  # Not created

        result = get_env_value("ANY_KEY", env_file)

        assert result is None


class TestCreateClaudeConfig:
    """Tests for create_claude_config function."""

    def test_create_claude_config_creates_file(self, tmp_path: Path) -> None:
        """Should create ~/.claude.json with hasCompletedOnboarding flag."""
        with patch("installer.steps.environment.Path.home", return_value=tmp_path):
            result = create_claude_config()

        config_file = tmp_path / ".claude.json"
        assert result is True
        assert config_file.exists()
        content = json.loads(config_file.read_text())
        assert content["hasCompletedOnboarding"] is True

    def test_create_claude_config_merges_with_existing(self, tmp_path: Path) -> None:
        """Should preserve existing keys when merging."""
        config_file = tmp_path / ".claude.json"
        config_file.write_text('{"existingKey": "existingValue"}\n')

        with patch("installer.steps.environment.Path.home", return_value=tmp_path):
            result = create_claude_config()

        assert result is True
        content = json.loads(config_file.read_text())
        assert content["hasCompletedOnboarding"] is True
        assert content["existingKey"] == "existingValue"

    def test_create_claude_config_returns_false_on_error(self, tmp_path: Path) -> None:
        """Should return False when file cannot be written."""
        with patch("installer.steps.environment.Path.home", return_value=tmp_path):
            # Make the directory read-only to cause write failure
            with patch.object(Path, "write_text", side_effect=PermissionError("No write permission")):
                result = create_claude_config()

        assert result is False


class TestCredentialsExist:
    """Tests for credentials_exist function."""

    def test_credentials_exist_returns_false_when_file_missing(self, tmp_path: Path) -> None:
        """Should return False when credentials file doesn't exist."""
        with patch("installer.steps.environment.Path.home", return_value=tmp_path):
            result = credentials_exist()

        assert result is False

    def test_credentials_exist_returns_false_for_invalid_json(self, tmp_path: Path) -> None:
        """Should return False when credentials file has invalid JSON."""
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        creds_file = claude_dir / ".credentials.json"
        creds_file.write_text("not valid json")

        with patch("installer.steps.environment.Path.home", return_value=tmp_path):
            result = credentials_exist()

        assert result is False

    def test_credentials_exist_returns_false_when_missing_oauth_key(self, tmp_path: Path) -> None:
        """Should return False when claudeAiOauth key is missing."""
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        creds_file = claude_dir / ".credentials.json"
        creds_file.write_text('{"otherKey": "value"}\n')

        with patch("installer.steps.environment.Path.home", return_value=tmp_path):
            result = credentials_exist()

        assert result is False

    def test_credentials_exist_returns_false_when_access_token_empty(self, tmp_path: Path) -> None:
        """Should return False when accessToken is empty."""
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        creds_file = claude_dir / ".credentials.json"
        creds_file.write_text('{"claudeAiOauth": {"accessToken": ""}}\n')

        with patch("installer.steps.environment.Path.home", return_value=tmp_path):
            result = credentials_exist()

        assert result is False

    def test_credentials_exist_returns_true_for_valid_credentials(self, tmp_path: Path) -> None:
        """Should return True when valid credentials exist."""
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        creds_file = claude_dir / ".credentials.json"
        creds_file.write_text('{"claudeAiOauth": {"accessToken": "valid-token"}}\n')

        with patch("installer.steps.environment.Path.home", return_value=tmp_path):
            result = credentials_exist()

        assert result is True


class TestCreateClaudeCredentials:
    """Tests for create_claude_credentials function."""

    def test_create_claude_credentials_creates_directory_and_file(self, tmp_path: Path) -> None:
        """Should create ~/.claude directory and .credentials.json file."""
        with patch("installer.steps.environment.Path.home", return_value=tmp_path):
            result = create_claude_credentials("test-token")

        assert result is True
        claude_dir = tmp_path / ".claude"
        creds_file = claude_dir / ".credentials.json"
        assert claude_dir.exists()
        assert creds_file.exists()

    def test_create_claude_credentials_writes_correct_structure(self, tmp_path: Path) -> None:
        """Should write credentials with correct JSON structure."""
        with patch("installer.steps.environment.Path.home", return_value=tmp_path):
            create_claude_credentials("my-oauth-token")

        creds_file = tmp_path / ".claude" / ".credentials.json"
        content = json.loads(creds_file.read_text())

        assert "claudeAiOauth" in content
        oauth = content["claudeAiOauth"]
        assert oauth["accessToken"] == "my-oauth-token"
        assert oauth["refreshToken"] == "my-oauth-token"
        assert oauth["scopes"] == ["user:inference", "user:profile", "user:sessions:claude_code"]
        assert oauth["subscriptionType"] == "max"
        assert oauth["rateLimitTier"] == "default_claude_max_20x"

    def test_create_claude_credentials_sets_expiry_365_days(self, tmp_path: Path) -> None:
        """Should set expiresAt to approximately 365 days from now."""
        import time

        before_time = int(time.time() * 1000)

        with patch("installer.steps.environment.Path.home", return_value=tmp_path):
            create_claude_credentials("token")

        after_time = int(time.time() * 1000)

        creds_file = tmp_path / ".claude" / ".credentials.json"
        content = json.loads(creds_file.read_text())
        expires_at = content["claudeAiOauth"]["expiresAt"]

        # 365 days in milliseconds
        year_ms = 365 * 24 * 60 * 60 * 1000

        # expiresAt should be between (before + 365 days) and (after + 365 days)
        assert before_time + year_ms <= expires_at <= after_time + year_ms

    def test_create_claude_credentials_sets_file_permissions(self, tmp_path: Path) -> None:
        """Should set restrictive file permissions (0o600)."""
        import stat

        with patch("installer.steps.environment.Path.home", return_value=tmp_path):
            create_claude_credentials("token")

        creds_file = tmp_path / ".claude" / ".credentials.json"
        file_mode = stat.S_IMODE(creds_file.stat().st_mode)

        # Should be 0o600 (owner read/write only)
        assert file_mode == 0o600

    def test_create_claude_credentials_returns_false_on_error(self, tmp_path: Path) -> None:
        """Should return False when credentials cannot be written."""
        with patch("installer.steps.environment.Path.home", return_value=tmp_path):
            with patch.object(Path, "mkdir", side_effect=OSError("Cannot create directory")):
                result = create_claude_credentials("token")

        assert result is False

    def test_create_claude_credentials_overwrites_existing(self, tmp_path: Path) -> None:
        """Should overwrite existing credentials file."""
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        creds_file = claude_dir / ".credentials.json"
        creds_file.write_text('{"claudeAiOauth": {"accessToken": "old-token"}}\n')

        with patch("installer.steps.environment.Path.home", return_value=tmp_path):
            create_claude_credentials("new-token")

        content = json.loads(creds_file.read_text())
        assert content["claudeAiOauth"]["accessToken"] == "new-token"


class TestEnvironmentStepOAuth:
    """Tests for OAuth behavior in EnvironmentStep.run()."""

    @pytest.fixture
    def mock_ui(self):
        """Create a mock UI object."""
        from unittest.mock import MagicMock

        ui = MagicMock()
        ui.confirm.return_value = False  # Default: don't use OAuth
        ui.input.return_value = ""  # Default: no token input
        return ui

    @pytest.fixture
    def install_context(self, tmp_path: Path, mock_ui):
        """Create an InstallContext for testing."""
        env_file = tmp_path / ".env"
        env_file.touch()  # Create empty .env file

        return InstallContext(
            project_dir=tmp_path,
            ui=mock_ui,
            skip_env=False,
            non_interactive=False,
        )

    def test_environment_prompts_for_oauth_when_not_set(self, install_context: InstallContext, tmp_path: Path) -> None:
        """Should prompt for OAuth token when neither .env nor credentials exist."""
        step = EnvironmentStep()

        with patch("installer.steps.environment.credentials_exist", return_value=False):
            with patch("installer.steps.environment.key_is_set", return_value=False):
                step.run(install_context)

        # Should have called ui.confirm to ask about OAuth
        install_context.ui.confirm.assert_called()

    def test_environment_skips_oauth_when_credentials_exist(
        self, install_context: InstallContext, tmp_path: Path
    ) -> None:
        """Should skip OAuth prompt when credentials already exist."""
        step = EnvironmentStep()

        with patch("installer.steps.environment.credentials_exist", return_value=True):
            with patch("installer.steps.environment.key_is_set", return_value=False):
                step.run(install_context)

        # Should have shown success message about existing credentials
        install_context.ui.success.assert_called()

    def test_environment_restores_credentials_from_env(self, install_context: InstallContext, tmp_path: Path) -> None:
        """Should restore credentials file when token in .env but credentials missing."""
        step = EnvironmentStep()
        env_file = tmp_path / ".env"
        env_file.write_text("CLAUDE_CODE_OAUTH_TOKEN=restored-token\n")

        with patch("installer.steps.environment.Path.home", return_value=tmp_path):
            with patch("installer.steps.environment.credentials_exist", return_value=False):
                # key_is_set returns True for CLAUDE_CODE_OAUTH_TOKEN
                with patch(
                    "installer.steps.environment.key_is_set",
                    side_effect=lambda k, _: k == "CLAUDE_CODE_OAUTH_TOKEN",
                ):
                    step.run(install_context)

        # Should have called status for restoring
        install_context.ui.status.assert_called()
        # Credentials file should be created
        creds_file = tmp_path / ".claude" / ".credentials.json"
        assert creds_file.exists()
        content = json.loads(creds_file.read_text())
        assert content["claudeAiOauth"]["accessToken"] == "restored-token"

    def test_environment_creates_credentials_on_new_token(
        self, install_context: InstallContext, tmp_path: Path
    ) -> None:
        """Should create credentials when user provides new token."""
        step = EnvironmentStep()
        install_context.ui.confirm.return_value = True  # User wants OAuth
        install_context.ui.input.return_value = "new-oauth-token"  # User inputs token

        with patch("installer.steps.environment.Path.home", return_value=tmp_path):
            with patch("installer.steps.environment.credentials_exist", return_value=False):
                with patch("installer.steps.environment.key_is_set", return_value=False):
                    step.run(install_context)

        # Token should be added to .env
        env_file = tmp_path / ".env"
        assert "CLAUDE_CODE_OAUTH_TOKEN=new-oauth-token" in env_file.read_text()

        # Credentials file should be created
        creds_file = tmp_path / ".claude" / ".credentials.json"
        assert creds_file.exists()
        content = json.loads(creds_file.read_text())
        assert content["claudeAiOauth"]["accessToken"] == "new-oauth-token"

    def test_e2e_workflow_existing_token_in_env_skips_prompt(
        self, install_context: InstallContext, tmp_path: Path
    ) -> None:
        """E2E: When token exists in .env, auto-restore credentials without prompting."""
        step = EnvironmentStep()
        env_file = tmp_path / ".env"
        env_file.write_text("CLAUDE_CODE_OAUTH_TOKEN=existing-token\n")
        original_env_content = env_file.read_text()

        with patch("installer.steps.environment.Path.home", return_value=tmp_path):
            with patch("installer.steps.environment.credentials_exist", return_value=False):
                with patch(
                    "installer.steps.environment.key_is_set",
                    side_effect=lambda k, _: k == "CLAUDE_CODE_OAUTH_TOKEN",
                ):
                    step.run(install_context)

        # POSITIVE ASSERTIONS: What SHOULD be called
        install_context.ui.status.assert_called()
        install_context.ui.success.assert_called()

        # NEGATIVE ASSERTIONS: What should NOT be called
        install_context.ui.confirm.assert_not_called()
        install_context.ui.input.assert_not_called()
        install_context.ui.info.assert_not_called()

        # FILE ASSERTIONS: Credentials file created with correct token
        creds_file = tmp_path / ".claude" / ".credentials.json"
        assert creds_file.exists(), "Credentials file should be created"
        content = json.loads(creds_file.read_text())
        assert content["claudeAiOauth"]["accessToken"] == "existing-token"

        # Original .env unchanged
        assert env_file.read_text() == original_env_content

    def test_e2e_workflow_no_token_user_says_yes_creates_all(
        self, install_context: InstallContext, tmp_path: Path
    ) -> None:
        """E2E: When no token exists and user says YES, create all files."""
        step = EnvironmentStep()
        env_file = tmp_path / ".env"
        env_file.write_text("")  # Empty .env

        # User accepts OAuth and provides token
        install_context.ui.confirm.return_value = True
        install_context.ui.input.return_value = "user-entered-token"

        with patch("installer.steps.environment.Path.home", return_value=tmp_path):
            with patch("installer.steps.environment.credentials_exist", return_value=False):
                with patch("installer.steps.environment.key_is_set", return_value=False):
                    step.run(install_context)

        # POSITIVE ASSERTIONS: What SHOULD be called
        install_context.ui.rule.assert_called()
        install_context.ui.confirm.assert_called_once()
        install_context.ui.input.assert_called_once()
        install_context.ui.success.assert_called()

        # NEGATIVE ASSERTIONS: What should NOT be called
        install_context.ui.info.assert_not_called()

        # FILE ASSERTIONS: .env file contains the token
        env_content = env_file.read_text()
        assert "CLAUDE_CODE_OAUTH_TOKEN=user-entered-token" in env_content

        # FILE ASSERTIONS: Credentials file exists with correct token
        creds_file = tmp_path / ".claude" / ".credentials.json"
        assert creds_file.exists(), "Credentials file should be created"
        creds_content = json.loads(creds_file.read_text())
        assert creds_content["claudeAiOauth"]["accessToken"] == "user-entered-token"

        # FILE ASSERTIONS: Config file exists with hasCompletedOnboarding
        config_file = tmp_path / ".claude.json"
        assert config_file.exists(), "Config file should be created"
        config_content = json.loads(config_file.read_text())
        assert config_content["hasCompletedOnboarding"] is True

    def test_e2e_workflow_no_token_user_says_no_skips_all(
        self, install_context: InstallContext, tmp_path: Path
    ) -> None:
        """E2E: When no token exists and user says NO, create nothing."""
        step = EnvironmentStep()
        env_file = tmp_path / ".env"
        env_file.write_text("")  # Empty .env
        original_env_content = env_file.read_text()

        # User declines OAuth
        install_context.ui.confirm.return_value = False

        with patch("installer.steps.environment.Path.home", return_value=tmp_path):
            with patch("installer.steps.environment.credentials_exist", return_value=False):
                with patch("installer.steps.environment.key_is_set", return_value=False):
                    step.run(install_context)

        # POSITIVE ASSERTIONS: What SHOULD be called
        install_context.ui.rule.assert_called()
        install_context.ui.confirm.assert_called_once()
        install_context.ui.info.assert_called_once()

        # NEGATIVE ASSERTIONS: What should NOT be called
        install_context.ui.input.assert_not_called()
        install_context.ui.success.assert_not_called()

        # FILE ASSERTIONS: .env file is unchanged (empty)
        assert env_file.read_text() == original_env_content

        # FILE ASSERTIONS: Credentials file does NOT exist
        creds_file = tmp_path / ".claude" / ".credentials.json"
        assert not creds_file.exists(), "Credentials file should NOT be created"

        # FILE ASSERTIONS: Config file does NOT exist
        config_file = tmp_path / ".claude.json"
        assert not config_file.exists(), "Config file should NOT be created"
