"""Premium features step - handles license validation and binary installation."""

from __future__ import annotations

import json
import platform
import stat
from pathlib import Path
from typing import TYPE_CHECKING

import httpx

from installer.steps.base import BaseStep
from installer.steps.environment import key_is_set

if TYPE_CHECKING:
    from installer.context import InstallContext

GUMROAD_VERIFY_URL = "https://api.gumroad.com/v2/licenses/verify"
PRODUCT_ID = "c3Sr8oRvWIimCH1zf5I02w=="
GITHUB_REPO = "maxritter/claude-codepro"


def get_platform_binary_name() -> str:
    """Get the correct binary name for the current platform."""
    system = platform.system().lower()
    machine = platform.machine().lower()

    if machine in ("x86_64", "amd64"):
        arch = "x86_64"
    elif machine in ("arm64", "aarch64"):
        arch = "arm64"
    else:
        arch = machine

    if system == "darwin":
        return f"ccp-premium-darwin-{arch}"
    elif system == "linux":
        return f"ccp-premium-linux-{arch}"
    elif system == "windows":
        return f"ccp-premium-windows-{arch}.exe"
    else:
        return f"ccp-premium-{system}-{arch}"


def validate_license_key(license_key: str) -> tuple[bool, str]:
    """Validate license key with Gumroad API."""
    try:
        response = httpx.post(
            GUMROAD_VERIFY_URL,
            data={
                "product_id": PRODUCT_ID,
                "license_key": license_key,
                "increment_uses_count": "false",
            },
            timeout=15,
        )

        if response.status_code == 404:
            return False, "Invalid license key"

        result = response.json()

        if result.get("success"):
            purchase = result.get("purchase", {})
            if purchase.get("refunded"):
                return False, "License has been refunded"
            if purchase.get("disputed"):
                return False, "License is disputed"

            return True, "License valid"

        return False, result.get("message", "Invalid license key")

    except httpx.HTTPStatusError as e:
        return False, f"License server error: HTTP {e.response.status_code}"
    except httpx.RequestError as e:
        return False, f"Network error: {e}"
    except json.JSONDecodeError:
        return False, "Invalid response from license server"
    except Exception as e:
        return False, f"Validation error: {e}"


def download_premium_binary(
    dest_dir: Path,
    version: str,
    local_mode: bool = False,
    local_repo_dir: Path | None = None,
) -> tuple[bool, str]:
    """Download premium binary from GitHub releases or copy from local dist."""
    import shutil

    binary_name = get_platform_binary_name()
    dest_path = dest_dir / "ccp-premium"

    if local_mode and local_repo_dir:
        source_path = local_repo_dir / "premium" / "dist" / binary_name
        if not source_path.exists():
            source_path = local_repo_dir / "premium" / "dist" / "ccp-premium"
        if not source_path.exists():
            return False, f"Premium binary not found at {local_repo_dir / 'premium' / 'dist'}"

        try:
            dest_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, dest_path)
            dest_path.chmod(dest_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            return True, str(dest_path)
        except Exception as e:
            return False, f"Copy error: {e}"

    if version == "latest":
        url = f"https://github.com/{GITHUB_REPO}/releases/latest/download/{binary_name}"
    else:
        url = f"https://github.com/{GITHUB_REPO}/releases/download/{version}/{binary_name}"

    try:
        with httpx.stream("GET", url, follow_redirects=True, timeout=120) as response:
            if response.status_code == 404:
                return False, "Premium binary not found (release may not exist yet)"
            response.raise_for_status()

            dest_dir.mkdir(parents=True, exist_ok=True)
            with open(dest_path, "wb") as f:
                for chunk in response.iter_bytes():
                    f.write(chunk)

            dest_path.chmod(dest_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            return True, str(dest_path)

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return False, "Premium binary not found (release may not exist yet)"
        return False, f"Download failed: HTTP {e.response.status_code}"
    except httpx.RequestError as e:
        return False, f"Network error: {e}"
    except Exception as e:
        return False, f"Download error: {e}"


def save_env_var(project_dir: Path, var_name: str, value: str) -> None:
    """Save an environment variable to .env file."""
    env_file = project_dir / ".env"

    existing_lines: list[str] = []
    if env_file.exists():
        existing_lines = env_file.read_text().splitlines()

    filtered_lines = [line for line in existing_lines if not line.startswith(f"{var_name}=")]
    filtered_lines.append(f"{var_name}={value}")

    env_file.write_text("\n".join(filtered_lines) + "\n")


def remove_premium_hooks_from_settings(settings_file: Path) -> bool:
    """Remove all premium hooks from settings.local.json for non-premium users."""
    if not settings_file.exists():
        return False

    try:
        settings = json.loads(settings_file.read_text())

        if "hooks" not in settings:
            return True

        for hook_type in ["PreToolUse", "PostToolUse", "Stop"]:
            if hook_type in settings["hooks"]:
                settings["hooks"][hook_type] = [
                    hook_group
                    for hook_group in settings["hooks"][hook_type]
                    if not any("ccp-premium" in h.get("command", "") for h in hook_group.get("hooks", []))
                ]
                if not settings["hooks"][hook_type]:
                    del settings["hooks"][hook_type]

        if not settings["hooks"]:
            del settings["hooks"]

        settings_file.write_text(json.dumps(settings, indent=2) + "\n")
        return True
    except (json.JSONDecodeError, OSError):
        return False


class PremiumStep(BaseStep):
    """Step that handles premium license validation and binary installation."""

    name = "premium"

    def _get_premium_key(self, ctx: InstallContext) -> str | None:
        """Get premium key from context, environment, or prompt. Returns 'EXISTING' if already validated."""
        if ctx.premium_key:
            return ctx.premium_key

        env_file = ctx.project_dir / ".env"
        if key_is_set("CCP_LICENSE_KEY", env_file):
            return "EXISTING"

        if not ctx.non_interactive and ctx.ui:
            ctx.ui.print()
            ctx.ui.box(
                "Premium features include:\n"
                "  • AI Rules Supervisor - Gemini-powered session analysis\n"
                "  • TDD Enforcer - Blocks edits without failing tests\n"
                "  • Context Monitor - Auto-saves learnings at 100% context",
                title="💎 Premium Features",
                style="magenta",
            )
            ctx.ui.print()
            ctx.ui.print("  Get a license at: [bold cyan]www.claude-code.pro[/bold cyan]")
            ctx.ui.print()

            key = ctx.ui.input("Enter premium license key (or press Enter to skip)")
            if key and key.strip():
                return key.strip()

        return None

    def _prompt_for_license_key(self, ctx: InstallContext) -> str | None:
        """Prompt user for license key with retry on invalid key."""
        if ctx.non_interactive or not ctx.ui:
            return None

        ctx.ui.print()
        key = ctx.ui.input("Enter premium license key (or press Enter to skip)")
        if key and key.strip():
            return key.strip()
        return None

    def check(self, ctx: InstallContext) -> bool:
        """Check if premium setup is needed."""
        return False

    def run(self, ctx: InstallContext) -> None:
        """Handle premium features installation."""
        ui = ctx.ui
        settings_file = ctx.project_dir / ".claude" / "settings.local.json"

        premium_key = self._get_premium_key(ctx)

        if not premium_key:
            if ui:
                ui.status("Skipping premium features (no license key)")
            remove_premium_hooks_from_settings(settings_file)
            return

        if ui:
            ui.section("Premium Features")

        if premium_key == "EXISTING":
            if ui:
                ui.success("License key already configured")
        else:
            ctx.premium_key = premium_key

            if ui:
                ui.status("Validating license key...")

            while True:
                valid, message = validate_license_key(ctx.premium_key)
                if valid:
                    break

                if ui:
                    ui.error(f"License validation failed: {message}")

                retry_key = self._prompt_for_license_key(ctx)
                if not retry_key:
                    if ui:
                        ui.status("Skipping premium features")
                    remove_premium_hooks_from_settings(settings_file)
                    return

                ctx.premium_key = retry_key
                if ui:
                    ui.status("Validating license key...")

            if ui:
                ui.success(message)

            save_env_var(ctx.project_dir, "CCP_LICENSE_KEY", ctx.premium_key)
            if ui:
                ui.success("Saved license key to .env")

        if ctx.local_mode:
            if ui:
                ui.status("Copying premium binary from local dist...")
        else:
            if ui:
                ui.status("Downloading premium binary...")

        bin_dir = ctx.project_dir / ".claude" / "bin"
        success, result = download_premium_binary(
            bin_dir,
            "latest",
            ctx.local_mode,
            ctx.local_repo_dir,
        )

        if not success:
            if ui:
                ui.error(f"{'Copy' if ctx.local_mode else 'Download'} failed: {result}")
                ui.warning("Premium features will not be available")
            remove_premium_hooks_from_settings(settings_file)
            return

        if ui:
            ui.success(f"Installed premium binary to {result}")

        if not ctx.non_interactive and ui:
            env_file = ctx.project_dir / ".env"
            gemini_already_set = key_is_set("GEMINI_API_KEY", env_file)

            if gemini_already_set:
                ui.success("GEMINI_API_KEY already set, skipping")
            else:
                ui.print()
                ui.section("Rules Supervisor (Gemini API)")
                ui.status("The Rules Supervisor uses Gemini to analyze coding sessions.")
                ui.print("  • Get API key at: https://aistudio.google.com/apikey")
                ui.print()

                gemini_key = ui.input("Enter Gemini API key (or press Enter to skip)", default="")
                if gemini_key and gemini_key.strip():
                    save_env_var(ctx.project_dir, "GEMINI_API_KEY", gemini_key.strip())
                    ui.success("Saved Gemini API key to .env")
                else:
                    ui.warning("No key entered. Rules Supervisor will be disabled.")

        if ui:
            ui.success("Premium features enabled")

    def rollback(self, ctx: InstallContext) -> None:
        """Remove premium binary and env entries."""
        import shutil

        bin_dir = ctx.project_dir / ".claude" / "bin"
        premium_binary = bin_dir / "ccp-premium"
        if premium_binary.exists():
            premium_binary.unlink()
