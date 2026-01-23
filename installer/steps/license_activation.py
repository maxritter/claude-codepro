"""License activation step - auto-activates CCP license from .env file."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import ClassVar

from installer.context import InstallContext
from installer.steps.base import BaseStep

LICENSE_KEY_ENV_VAR = "CLAUDE_CODEPRO_LICENSE_KEY"


def get_license_key_from_env_file(env_file: Path) -> str | None:
    """Get the license key value from .env file."""
    if not env_file.exists():
        return None

    content = env_file.read_text()
    for line in content.split("\n"):
        line = line.strip()
        if line.startswith(f"{LICENSE_KEY_ENV_VAR}="):
            value = line[len(LICENSE_KEY_ENV_VAR) + 1 :].strip()
            return value if value else None
    return None


def get_license_key(env_file: Path) -> str | None:
    """Get license key from environment variable or .env file."""
    env_value = os.environ.get(LICENSE_KEY_ENV_VAR)
    if env_value:
        return env_value
    return get_license_key_from_env_file(env_file)


def get_ccp_binary_path(ctx: InstallContext) -> Path:
    """Get path to ccp binary, handling local mode."""
    bin_path = ctx.project_dir / ".claude" / "bin" / "ccp"

    if ctx.local_mode and ctx.local_repo_dir:
        local_bin = ctx.local_repo_dir / ".claude" / "bin" / "ccp"
        if local_bin.exists():
            return local_bin

    return bin_path


def is_license_valid(ctx: InstallContext) -> bool:
    """Check if a valid license already exists via ccp status."""
    bin_path = get_ccp_binary_path(ctx)
    if not bin_path.exists():
        return False

    try:
        result = subprocess.run(
            [str(bin_path), "status", "--json"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            output = result.stdout.strip() or result.stderr.strip()
            if output:
                data = json.loads(output)
                tier = data.get("tier")
                is_expired = data.get("is_expired", False)
                return tier in ("trial", "standard", "enterprise") and not is_expired
    except (subprocess.SubprocessError, json.JSONDecodeError, OSError):
        pass
    return False


class LicenseActivationStep(BaseStep):
    """Step that auto-activates CCP license from .env file."""

    name: ClassVar[str] = "license_activation"

    def check(self, ctx: InstallContext) -> bool:
        """Check if step should be skipped.

        Returns True (skip) if:
        - No license key found in env var or .env file
        - License is already valid

        Returns False (run) if:
        - License key exists but license is not valid
        """
        env_file = ctx.project_dir / ".env"
        license_key = get_license_key(env_file)

        if not license_key:
            return True

        if is_license_valid(ctx):
            return True

        return False

    def run(self, ctx: InstallContext) -> None:
        """Activate the license using the key from .env or environment."""
        ui = ctx.ui
        env_file = ctx.project_dir / ".env"
        license_key = get_license_key(env_file)

        if not license_key:
            return

        bin_path = get_ccp_binary_path(ctx)
        if not bin_path.exists():
            if ui:
                ui.warning("CCP binary not found - skipping license activation")
                ui.info("License will be activated on first run")
            return

        try:
            result = subprocess.run(
                [str(bin_path), "activate", license_key, "--json"],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                if ui:
                    ui.success("License activated successfully from .env")
            else:
                if ui:
                    ui.warning("License activation failed - continuing installation")
                    stderr = result.stderr.strip() if result.stderr else ""
                    if stderr:
                        ui.print(f"  [dim]{stderr}[/dim]")
                    ui.info("You can activate manually later with: ccp activate <key>")
        except subprocess.TimeoutExpired:
            if ui:
                ui.warning("License activation timed out - continuing installation")
                ui.info("You can activate manually later with: ccp activate <key>")
        except subprocess.SubprocessError as e:
            if ui:
                ui.warning(f"License activation error: {e}")
                ui.info("You can activate manually later with: ccp activate <key>")

    def rollback(self, ctx: InstallContext) -> None:
        """No rollback for license activation."""
        del ctx
