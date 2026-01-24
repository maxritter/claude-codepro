"""Environment step - sets up .env file with API keys."""

from __future__ import annotations

import os
from pathlib import Path

from installer.context import InstallContext
from installer.steps.base import BaseStep

OBSOLETE_ENV_KEYS = [
    "MILVUS_TOKEN",
    "MILVUS_ADDRESS",
    "VECTOR_STORE_USERNAME",
    "VECTOR_STORE_PASSWORD",
    "EXA_API_KEY",
    "GEMINI_API_KEY",
]


def remove_env_key(key: str, env_file: Path) -> bool:
    """Remove an environment key from .env file. Returns True if key was removed."""
    if not env_file.exists():
        return False

    lines = env_file.read_text().splitlines()
    new_lines = [line for line in lines if not line.strip().startswith(f"{key}=")]

    if len(new_lines) != len(lines):
        env_file.write_text("\n".join(new_lines) + "\n" if new_lines else "")
        return True
    return False


def cleanup_obsolete_env_keys(env_file: Path) -> list[str]:
    """Remove obsolete environment keys from .env file. Returns list of removed keys."""
    removed = []
    for key in OBSOLETE_ENV_KEYS:
        if remove_env_key(key, env_file):
            removed.append(key)
    return removed


def key_exists_in_file(key: str, env_file: Path) -> bool:
    """Check if key exists in .env file with a non-empty value."""
    if not env_file.exists():
        return False

    content = env_file.read_text()
    for line in content.split("\n"):
        line = line.strip()
        if line.startswith(f"{key}="):
            value = line[len(key) + 1 :].strip()
            return bool(value)
    return False


def get_env_value(key: str, env_file: Path) -> str | None:
    """Get the value of a key from .env file, or None if not found."""
    if not env_file.exists():
        return None

    content = env_file.read_text()
    for line in content.split("\n"):
        line = line.strip()
        if line.startswith(f"{key}="):
            value = line[len(key) + 1 :].strip()
            return value if value else None
    return None


def key_is_set(key: str, env_file: Path) -> bool:
    """Check if key exists in .env file OR is already set as environment variable."""
    if os.environ.get(key):
        return True
    return key_exists_in_file(key, env_file)


def add_env_key(key: str, value: str, env_file: Path) -> None:
    """Add environment key to .env file if it doesn't exist."""
    if key_exists_in_file(key, env_file):
        return

    with open(env_file, "a") as f:
        f.write(f"{key}={value}\n")


def create_claude_config() -> bool:
    """Create ~/.claude.json with hasCompletedOnboarding flag.

    Returns True if file was created/updated, False on error.
    """
    import json

    config_path = Path.home() / ".claude.json"
    config = {"hasCompletedOnboarding": True}

    try:
        if config_path.exists():
            existing = json.loads(config_path.read_text())
            existing.update(config)
            config = existing

        config_path.write_text(json.dumps(config, indent=2) + "\n")
        return True
    except Exception:
        return False


def credentials_exist() -> bool:
    """Check if valid Claude credentials exist in ~/.claude/.credentials.json.

    Returns True if file exists with a non-empty accessToken, False otherwise.
    """
    import json

    creds_path = Path.home() / ".claude" / ".credentials.json"

    try:
        if not creds_path.exists():
            return False

        content = json.loads(creds_path.read_text())
        oauth = content.get("claudeAiOauth", {})
        access_token = oauth.get("accessToken", "")
        return bool(access_token)
    except (json.JSONDecodeError, OSError):
        return False


def create_claude_credentials(token: str) -> bool:
    """Create ~/.claude/.credentials.json with OAuth token.

    Creates the ~/.claude/ directory if needed and writes credentials
    with restrictive permissions (0o600 for file, 0o700 for directory).

    Args:
        token: The OAuth token (used for both accessToken and refreshToken)

    Returns:
        True if credentials were created successfully, False on error.
    """
    import json
    import time

    claude_dir = Path.home() / ".claude"
    creds_path = claude_dir / ".credentials.json"

    expires_at = int(time.time() * 1000) + (365 * 24 * 60 * 60 * 1000)

    credentials = {
        "claudeAiOauth": {
            "accessToken": token,
            "refreshToken": token,
            "expiresAt": expires_at,
            "scopes": ["user:inference", "user:profile", "user:sessions:claude_code"],
            "subscriptionType": "max",
            "rateLimitTier": "default_claude_max_20x",
        }
    }

    try:
        claude_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        creds_path.write_text(json.dumps(credentials, indent=2) + "\n")
        creds_path.chmod(0o600)
        return True
    except OSError:
        return False


class EnvironmentStep(BaseStep):
    """Step that cleans up .env file (API keys are collected earlier in CLI)."""

    name = "environment"

    def check(self, ctx: InstallContext) -> bool:
        """Always returns False - environment step should always run for cleanup."""
        return False

    def run(self, ctx: InstallContext) -> None:
        """Clean up .env file and handle OAuth token setup."""
        ui = ctx.ui
        env_file = ctx.project_dir / ".env"

        if ctx.skip_env or ctx.non_interactive:
            return

        if env_file.exists():
            removed_keys = cleanup_obsolete_env_keys(env_file)
            if removed_keys and ui:
                ui.print(f"  [dim]Cleaned up obsolete keys: {', '.join(removed_keys)}[/dim]")

        token_in_env = key_is_set("CLAUDE_CODE_OAUTH_TOKEN", env_file)
        token_in_creds = credentials_exist()

        if token_in_env and not token_in_creds:
            existing_token = get_env_value("CLAUDE_CODE_OAUTH_TOKEN", env_file)
            if existing_token and ui:
                ui.status("Restoring OAuth credentials from .env...")
                if create_claude_credentials(existing_token):
                    create_claude_config()
                    ui.success("OAuth credentials restored to ~/.claude/.credentials.json")
                else:
                    ui.warning("Could not restore credentials file")

        if not token_in_env and not token_in_creds:
            if ui:
                ui.print()
                ui.rule("Claude Long Lasting Token (Optional)")
                ui.print()
                ui.print("  [bold]Used for:[/bold] Persistent OAuth authentication (Max subscription)")
                ui.print("  [bold]Why:[/bold] Avoids repeated OAuth prompts in container environments")
                ui.print("  [bold]Get token:[/bold] Run [cyan]claude setup-token[/cyan] outside container")
                ui.print()

                use_oauth = ui.confirm("Use Claude Long Lasting Token?", default=False)

                if use_oauth:
                    oauth_token = ui.input("CLAUDE_CODE_OAUTH_TOKEN", default="")
                    if oauth_token:
                        add_env_key("CLAUDE_CODE_OAUTH_TOKEN", oauth_token, env_file)
                        if create_claude_credentials(oauth_token):
                            create_claude_config()
                            ui.success("OAuth credentials saved to .env and ~/.claude/.credentials.json")
                        else:
                            ui.warning("Token saved to .env but could not create credentials file")
                        if key_is_set("ANTHROPIC_API_KEY", env_file):
                            ui.warning("ANTHROPIC_API_KEY is set - it may override OAuth token!")
                else:
                    ui.info("Skipping OAuth token setup")
        elif token_in_env or token_in_creds:
            if ui:
                if token_in_creds:
                    ui.success("OAuth credentials already configured, skipping")
                else:
                    ui.success("CLAUDE_CODE_OAUTH_TOKEN in .env, skipping")

    def rollback(self, ctx: InstallContext) -> None:
        """No rollback for environment setup."""
        pass
