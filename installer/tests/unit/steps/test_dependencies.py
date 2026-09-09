"""Tests for dependencies step."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _isolate_owned_tool_manifest(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Mock installer runs must never write ownership metadata into the real home."""
    monkeypatch.setattr(
        "installer.steps.dependencies._owned_tools_manifest_path",
        lambda: tmp_path / ".pilot" / ".pilot-owned-tools.json",
    )
    from installer.claude_display_patch import PatchResult

    monkeypatch.setattr(
        "installer.steps.dependencies.apply_display_patch",
        MagicMock(return_value=PatchResult("skipped", "No native Claude in this test")),
        raising=False,
    )


class TestClaudeDisplayPatchIntegration:
    @pytest.mark.parametrize("patch_status", ["patched", "unchanged"])
    def test_success_resets_verbose_only_once(self, monkeypatch, tmp_path, patch_status):
        from installer.claude_display_patch import PatchResult
        from installer.steps import dependencies as deps

        monkeypatch.setattr(deps, "get_claude_config_dir", lambda: tmp_path)
        monkeypatch.setattr(deps, "apply_display_patch", lambda: PatchResult(patch_status, "Details enabled"))
        settings = tmp_path / "settings.json"
        settings.write_text(json.dumps({"viewMode": "verbose", "model": "user-model", "verbose": False}))
        assert deps._setup_claude_display_patch() is True
        assert json.loads(settings.read_text()) == {"model": "user-model", "verbose": False}
        marker = tmp_path / ".pilot-display-patch-migration.json"
        assert json.loads(marker.read_text()) == {"version": 1}
        settings.write_text(json.dumps({"verbose": True, "model": "new-user-model"}))
        assert deps._setup_claude_display_patch() is True
        assert json.loads(settings.read_text()) == {"verbose": True, "model": "new-user-model"}

    def test_profile_migrations_are_independent_and_keep_focus(self, monkeypatch, tmp_path):
        from installer.steps import dependencies as deps

        for name, initial, expected in [("first", {}, None), ("second", {"viewMode": "focus"}, "focus")]:
            profile = tmp_path / name
            profile.mkdir()
            monkeypatch.setattr(deps, "get_claude_config_dir", lambda selected=profile: selected)
            settings = profile / "settings.json"
            settings.write_text(json.dumps(initial))
            deps._migrate_claude_display_mode()
            assert json.loads(settings.read_text()).get("viewMode") == expected
            assert json.loads(settings.read_text())["verbose"] is False
            assert (profile / ".pilot-display-patch-migration.json").exists()

    def test_migration_failure_preserves_settings_and_remains_nonfatal(self, monkeypatch, tmp_path):
        from installer.claude_display_patch import PatchResult
        from installer.steps import dependencies as deps

        monkeypatch.setattr(deps, "get_claude_config_dir", lambda: tmp_path)
        monkeypatch.setattr(deps, "apply_display_patch", lambda: PatchResult("patched", "Details enabled"))
        settings = tmp_path / "settings.json"
        settings.write_text("{unreadable")
        ui = MagicMock()
        assert deps._setup_claude_display_patch(ui) is True
        assert settings.read_text() == "{unreadable"
        assert not (tmp_path / ".pilot-display-patch-migration.json").exists()
        ui.warning.assert_called_once()

    def test_failed_settings_write_releases_migration_claim(self, monkeypatch, tmp_path):
        from installer.steps import dependencies as deps

        monkeypatch.setattr(deps, "get_claude_config_dir", lambda: tmp_path)
        settings = tmp_path / "settings.json"
        settings.write_text('{"viewMode":"verbose","model":"my-model"}')
        before = settings.read_bytes()
        monkeypatch.setattr(deps.os, "replace", lambda *args: (_ for _ in ()).throw(OSError("read-only filesystem")))
        with pytest.raises(OSError, match="read-only"):
            deps._migrate_claude_display_mode()
        assert settings.read_bytes() == before
        assert not (tmp_path / ".pilot-display-patch-migration.json").exists()

    def test_patch_failure_warns_without_failing_install(self, monkeypatch):
        from installer.claude_display_patch import PatchResult
        from installer.steps import dependencies as deps

        monkeypatch.setattr(deps, "apply_display_patch", lambda: PatchResult("failed", "Required patch did not match"))
        ui = MagicMock()
        assert deps._setup_claude_display_patch(ui) is False
        ui.warning.assert_called_once()
        assert "Required patch did not match" in ui.warning.call_args.args[0]

    @pytest.mark.parametrize("status", ["failed", "skipped"])
    def test_unsuccessful_patch_never_migrates_mode(self, monkeypatch, tmp_path, status):
        from installer.claude_display_patch import PatchResult
        from installer.steps import dependencies as deps

        monkeypatch.setattr(deps, "get_claude_config_dir", lambda: tmp_path)
        monkeypatch.setattr(deps, "apply_display_patch", lambda: PatchResult(status, "No patch"))
        assert deps._setup_claude_display_patch() is False
        assert not (tmp_path / ".pilot-display-patch-migration.json").exists()

    def test_missing_native_is_a_quiet_skip(self):
        from installer.steps import dependencies as deps

        ui = MagicMock()
        assert deps._setup_claude_display_patch(ui) is False
        ui.warning.assert_not_called()
        ui.success.assert_not_called()

    def test_patch_runs_after_plugins_and_bun_setup(self, monkeypatch, tmp_path):
        from installer.context import InstallContext
        from installer.steps import dependencies as deps

        events = []
        monkeypatch.setattr(deps, "_snapshot_tool_presence", lambda: {})
        monkeypatch.setattr(deps, "_load_owned_tools", lambda: set())
        monkeypatch.setattr(deps, "_write_owned_tools", lambda *args: None)
        monkeypatch.setattr(deps, "needs_sudo", lambda: False)
        monkeypatch.setattr(deps, "is_linux_arm64", lambda: False)
        monkeypatch.setattr(deps, "_install_with_spinner", lambda *args: True)
        monkeypatch.setattr(deps, "_run_parallel_installs", lambda *args: events.append("plugins") or [])
        monkeypatch.setattr(deps, "_setup_pilot_memory", lambda *args: events.append("bun") or True)
        monkeypatch.setattr(deps, "_setup_claude_display_patch", lambda *args: events.append("patch") or True)
        monkeypatch.setattr(deps, "codegraph_needs_work", lambda *args: False)
        monkeypatch.setattr(deps, "initialize_codegraph", lambda *args: True)
        ctx = InstallContext(project_dir=tmp_path, non_interactive=True)
        deps.DependenciesStep().run(ctx)
        assert events == ["plugins", "bun", "patch"]
        assert "claude_display_patch" in ctx.config["installed_dependencies"]


class TestDependenciesStep:
    """Test DependenciesStep class."""

    def test_dependencies_step_has_correct_name(self):
        """DependenciesStep has name 'dependencies'."""
        from installer.steps.dependencies import DependenciesStep

        step = DependenciesStep()
        assert step.name == "dependencies"

    def test_dependencies_check_returns_false(self):
        """DependenciesStep.check returns False (always runs)."""
        from installer.context import InstallContext
        from installer.steps.dependencies import DependenciesStep
        from installer.ui import Console

        step = DependenciesStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = InstallContext(
                project_dir=Path(tmpdir),
                ui=Console(non_interactive=True),
            )
            assert step.check(ctx) is False

    @patch("installer.steps.dependencies.install_open_claude_design", return_value=True)
    @patch("installer.steps.dependencies.install_impeccable", return_value=True)
    @patch("installer.steps.dependencies.initialize_codegraph", return_value=True)
    @patch("installer.steps.dependencies.codegraph_needs_work", return_value=False)
    @patch("installer.steps.dependencies.install_playwright_cli", return_value=True)
    @patch("installer.steps.dependencies.install_lsp_plugins", return_value=True)
    @patch("installer.steps.dependencies.install_codex_plugin", return_value=True)
    @patch("installer.steps.dependencies.install_codegraph", return_value=True)
    @patch("installer.steps.dependencies.install_rtk", return_value=True)
    @patch("installer.steps.dependencies.install_ast_grep", return_value=True)
    @patch("installer.steps.dependencies.install_semble", return_value=True)
    @patch("installer.steps.dependencies.install_agent_browser", return_value=True)
    @patch("installer.steps.dependencies.install_pbt_tools", return_value=True)
    @patch("installer.steps.dependencies.install_golangci_lint", return_value=True)
    @patch("installer.steps.dependencies.install_prettier", return_value=True)
    @patch("installer.steps.dependencies.install_typescript_lsp", return_value=True)
    @patch("installer.steps.dependencies._precache_npx_mcp_servers", return_value=True)
    @patch("installer.steps.dependencies.install_chrome_devtools_plugin", return_value=True)
    @patch("installer.steps.dependencies.remove_legacy_context_mode", return_value=True)
    @patch("installer.steps.dependencies._install_plugin_dependencies")
    @patch("installer.steps.dependencies._setup_pilot_memory")
    @patch("installer.steps.dependencies.install_python_tools")
    @patch("installer.steps.dependencies.install_uv")
    @patch("installer.steps.dependencies.install_nodejs")
    def test_dependencies_run_installs_core(
        self,
        mock_nodejs,
        mock_uv,
        mock_python_tools,
        mock_setup_pilot_memory,
        mock_plugin_deps,
        _mock_remove_legacy_ctx_mode,
        _mock_chrome_devtools_plugin,
        _mock_precache,
        _mock_ts_lsp,
        _mock_prettier,
        _mock_golangci_lint,
        _mock_pbt_tools,
        _mock_agent_browser,
        _mock_semble,
        _mock_ast_grep,
        _mock_rtk,
        _mock_codegraph,
        _mock_codex_plugin,
        _mock_lsp_plugins,
        _mock_playwright,
        _mock_codegraph_needs_work,
        _mock_init_codegraph,
        _mock_impeccable,
        _mock_open_claude_design,
    ):
        """DependenciesStep installs all dependencies including Python tools."""
        from installer.context import InstallContext
        from installer.steps.dependencies import DependenciesStep
        from installer.ui import Console

        mock_nodejs.return_value = True
        mock_uv.return_value = True
        mock_python_tools.return_value = True
        mock_setup_pilot_memory.return_value = True
        mock_plugin_deps.return_value = True

        step = DependenciesStep()
        install_labels: list[str] = []

        def run_and_capture_label(_ui, label, install_fn, *args):
            install_labels.append(label)
            return install_fn(*args) if args else install_fn()

        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = InstallContext(
                project_dir=Path(tmpdir),
                ui=Console(non_interactive=True),
            )

            with patch(
                "installer.steps.dependencies._install_with_spinner",
                side_effect=run_and_capture_label,
            ):
                step.run(ctx)

            mock_nodejs.assert_called_once()
            mock_uv.assert_called_once()
            mock_python_tools.assert_called_once()
            mock_plugin_deps.assert_called_once()
            _mock_semble.assert_called_once()
            _mock_ast_grep.assert_called_once()
            _mock_rtk.assert_called_once()
            _mock_codegraph.assert_called_once()
            _mock_codex_plugin.assert_called_once()
            _mock_lsp_plugins.assert_called_once()
            _mock_playwright.assert_called_once()
            _mock_pbt_tools.assert_called_once()
            _mock_agent_browser.assert_called_once()
            _mock_impeccable.assert_called_once()
            _mock_open_claude_design.assert_called_once()
            assert "Impeccable (skills, agents, detector; hooks opt-in)" in install_labels
            assert "Impeccable (skills, agents, hooks, detector)" not in install_labels


class TestAgentInstallRemoved:
    """The installer no longer installs Claude Code or Codex CLI itself.

    README prerequisites require users to install agents via their native installers
    before running this installer. Regression guard: the dispatcher must not regain
    an install function for either agent.
    """

    def test_install_claude_code_no_longer_exists(self):
        """install_claude_code is removed — users install Claude Code themselves."""
        import installer.steps.dependencies as deps

        assert not hasattr(deps, "install_claude_code")


class TestOwnedToolManifest:
    """Only tools absent before Pilot ran become uninstall-owned."""

    def test_records_fresh_tools_and_preserves_prior_ownership(self, tmp_path: Path) -> None:
        from installer.steps.dependencies import _load_owned_tools, _write_owned_tools

        with patch("installer.steps.dependencies.Path.home", return_value=tmp_path):
            _write_owned_tools(
                {"rtk"},
                ["semble", "codegraph", "prettier"],
                {"semble": False, "codegraph": True, "prettier": False},
            )

            assert _load_owned_tools() == {"rtk", "semble", "prettier"}

    def test_ignores_unknown_manifest_entries(self, tmp_path: Path) -> None:
        from installer.steps.dependencies import PILOT_OWNED_TOOLS_MANIFEST, _load_owned_tools

        manifest = tmp_path / ".pilot" / PILOT_OWNED_TOOLS_MANIFEST
        manifest.parent.mkdir(parents=True)
        manifest.write_text('{"tools":["semble","user-tool","../../escape"]}\n')

        with patch("installer.steps.dependencies.Path.home", return_value=tmp_path):
            assert _load_owned_tools() == {"semble"}


class TestDependencyInstallFunctions:
    """Test individual dependency install functions."""

    def test_install_nodejs_exists(self):
        """install_nodejs function exists."""
        from installer.steps.dependencies import install_nodejs

        assert callable(install_nodejs)

    def test_install_uv_exists(self):
        """install_uv function exists."""
        from installer.steps.dependencies import install_uv

        assert callable(install_uv)

    def test_install_python_tools_exists(self):
        """install_python_tools function exists."""
        from installer.steps.dependencies import install_python_tools

        assert callable(install_python_tools)

    @patch("installer.steps.dependencies._uv_tool_bin_semble")
    @patch("installer.steps.dependencies._symlink_to_pilot_bin")
    @patch("installer.steps.dependencies.subprocess.run")
    @patch("installer.steps.dependencies.command_exists", return_value=False)
    @patch("installer.steps.dependencies._run_bash_with_retry", return_value=True)
    def test_uv_tool_install_commands_are_hermetic(self, mock_run, _mock_cmd, mock_sub, _mock_symlink, _mock_locator):
        """Every `uv tool install` command passes --no-config so an ambient
        uv.toml (e.g. authenticated corporate indexes with expired credentials)
        cannot break tool installation."""
        from installer.steps.dependencies import (
            install_pbt_tools,
            install_python_tools,
            install_semble,
        )

        mock_sub.return_value = MagicMock(returncode=1, stdout="")

        install_python_tools()
        install_semble()
        install_pbt_tools()

        uv_tool_cmds = [c.args[0] for c in mock_run.call_args_list if "uv tool install" in str(c.args[0])]
        assert uv_tool_cmds, "expected uv tool install commands to be issued"
        for cmd in uv_tool_cmds:
            assert "--no-config" in cmd, f"uv tool install missing --no-config: {cmd}"

    @patch("installer.steps.dependencies.command_exists", return_value=False)
    @patch("installer.steps.dependencies._run_bash_with_retry", return_value=True)
    def test_install_typescript_lsp_pins_vtsls_and_typescript(self, mock_run, _mock_cmd):
        """install_typescript_lsp pins both vtsls and typescript with --ignore-scripts."""
        from installer.manifest import get
        from installer.steps.dependencies import install_typescript_lsp

        result = install_typescript_lsp()
        assert result is True
        cmd = mock_run.call_args[0][0]
        assert f"@vtsls/language-server@{get('vtsls').version}" in cmd
        assert f"typescript@{get('typescript').version}" in cmd
        assert "--ignore-scripts" in cmd

    @patch("installer.steps.dependencies._is_agent_browser_ready", return_value=True)
    @patch("installer.steps.dependencies._run_bash_with_retry", return_value=True)
    def test_install_agent_browser_pins_version(self, mock_run, _mock_ready):
        """install_agent_browser pins manifest version with --ignore-scripts."""
        from installer.manifest import get
        from installer.steps.dependencies import install_agent_browser

        result = install_agent_browser()
        assert result is True
        first_cmd = mock_run.call_args_list[0][0][0]
        assert f"agent-browser@{get('agent-browser').version}" in first_cmd
        assert "--ignore-scripts" in first_cmd
        assert "@latest" not in first_cmd

    @patch("installer.steps.dependencies._is_playwright_cli_ready", return_value=True)
    @patch("installer.steps.dependencies._run_bash_with_retry", return_value=True)
    def test_install_playwright_cli_pins_version(self, mock_run, _mock_ready):
        """install_playwright_cli pins manifest version with --ignore-scripts (no @latest)."""
        from installer.manifest import get
        from installer.steps.dependencies import install_playwright_cli

        result = install_playwright_cli()
        assert result is True
        first_cmd = mock_run.call_args_list[0][0][0]
        assert f"@playwright/cli@{get('playwright-cli').version}" in first_cmd
        assert "--ignore-scripts" in first_cmd
        assert "@latest" not in first_cmd


class TestSetupPilotMemory:
    """Test pilot-memory setup."""

    def test_setup_pilot_memory_exists(self):
        """_setup_pilot_memory function exists."""
        from installer.steps.dependencies import _setup_pilot_memory

        assert callable(_setup_pilot_memory)

    def test_setup_pilot_memory_returns_true(self):
        """_setup_pilot_memory returns True."""
        from installer.steps.dependencies import _setup_pilot_memory

        result = _setup_pilot_memory(ui=None)

        assert result is True


class TestSembleInstall:
    """Test Semble code search installation."""

    def test_install_semble_exists(self):
        """install_semble function exists."""
        from installer.steps.dependencies import install_semble

        assert callable(install_semble)

    @patch("installer.steps.dependencies._uv_tool_bin_semble", return_value=Path("/home/u/.local/bin/semble"))
    @patch("installer.steps.dependencies._symlink_to_pilot_bin", return_value=True)
    @patch("installer.steps.dependencies._run_bash_with_retry")
    def test_install_semble_uses_uv_tool_install(self, mock_bash, _mock_symlink, _mock_locator):
        """install_semble installs the MCP-capable CLI at the manifest pin.

        The MCP entry launches this installed binary directly, so `--reinstall`
        keeps both CLI and MCP behavior on the audited release. Plain install is
        a no-op when another version exists; `--upgrade` would float past the pin.
        """
        from installer.manifest import get as manifest_get
        from installer.steps.dependencies import install_semble

        mock_bash.return_value = True

        result = install_semble()

        assert result is True
        mock_bash.assert_called_once()
        call_args = mock_bash.call_args[0][0]
        assert "uv tool install" in call_args
        assert f"semble[mcp]=={manifest_get('semble').version}" in call_args
        assert "--upgrade" not in call_args
        assert "--reinstall" in call_args

    @patch("installer.steps.dependencies._uv_tool_bin_semble")
    @patch("installer.steps.dependencies._symlink_to_pilot_bin", return_value=True)
    @patch("installer.steps.dependencies._run_bash_with_retry", return_value=True)
    def test_install_semble_symlinks_uv_tool_binary(self, _mock_bash, mock_symlink, mock_locator):
        """The symlink targets uv's tool bin dir, not a PATH lookup: which()
        can miss (~/.local/bin off the installer PATH) or hit a shadowing
        non-mcp semble, leaving the MCP entry pointing at a dead binary."""
        from pathlib import Path

        from installer.steps.dependencies import install_semble

        mock_locator.return_value = Path("/home/u/.local/bin/semble")

        result = install_semble()

        assert result is True
        mock_symlink.assert_called_once_with("semble", source=Path("/home/u/.local/bin/semble"))

    @patch("installer.steps.dependencies._uv_tool_bin_semble", return_value=None)
    @patch("installer.steps.dependencies._run_bash_with_retry", return_value=True)
    def test_install_semble_fails_when_uv_binary_is_missing(self, _mock_bash, _mock_locator):
        """MCP cannot start without the exact Pilot launcher target."""
        from installer.steps.dependencies import _get_last_error, install_semble

        assert install_semble() is False
        assert "could not be located" in _get_last_error()

    @patch("installer.steps.dependencies._uv_tool_bin_semble", return_value=Path("/home/u/.local/bin/semble"))
    @patch("installer.steps.dependencies._symlink_to_pilot_bin", return_value=False)
    @patch("installer.steps.dependencies._run_bash_with_retry", return_value=True)
    def test_install_semble_fails_when_launcher_link_fails(self, _mock_bash, _mock_symlink, _mock_locator):
        """A failed ~/.pilot/bin link must fail installation instead of reporting success."""
        from installer.steps.dependencies import _get_last_error, install_semble

        assert install_semble() is False
        assert "could not be created" in _get_last_error()

    @patch("installer.steps.dependencies.subprocess.run")
    def test_uv_tool_bin_semble_locates_binary(self, mock_run, tmp_path):
        """_uv_tool_bin_semble resolves <uv tool dir --bin>/semble when present."""
        from unittest.mock import MagicMock

        from installer.steps.dependencies import _uv_tool_bin_semble

        (tmp_path / "semble").write_text("#!/bin/sh\n")
        (tmp_path / "semble").chmod(0o755)
        mock_run.return_value = MagicMock(stdout=f"{tmp_path}\n")

        assert _uv_tool_bin_semble() == tmp_path / "semble"
        assert mock_run.call_args.args[0] == ["uv", "tool", "dir", "--bin", "--no-config"]

    @patch("installer.steps.dependencies.subprocess.run", side_effect=OSError("uv missing"))
    def test_uv_tool_bin_semble_none_on_failure(self, _mock_run):
        """_uv_tool_bin_semble returns None when uv cannot be queried, so the
        symlink helper falls back to a PATH lookup."""
        from installer.steps.dependencies import _uv_tool_bin_semble

        assert _uv_tool_bin_semble() is None

    @patch("installer.steps.dependencies._uv_tool_bin_semble", return_value=Path("/home/u/.local/bin/semble"))
    @patch("installer.steps.dependencies._symlink_to_pilot_bin", return_value=True)
    @patch("installer.steps.dependencies._run_bash_with_retry", return_value=True)
    def test_install_semble_uses_uv_tool_timeout(self, mock_bash, _mock_symlink, _mock_locator):
        """Semble install uses UV_TOOL_INSTALL_TIMEOUT, matching ruff/hypothesis/basedpyright."""
        from installer.steps.dependencies import UV_TOOL_INSTALL_TIMEOUT, install_semble

        result = install_semble()

        assert result is True
        assert mock_bash.call_args.kwargs["timeout"] == UV_TOOL_INSTALL_TIMEOUT

    @patch("installer.steps.dependencies._run_bash_with_retry")
    def test_install_semble_returns_false_on_failure(self, mock_bash):
        """install_semble returns False when `uv tool install` fails."""
        from installer.steps.dependencies import install_semble

        mock_bash.return_value = False

        result = install_semble()

        assert result is False


class TestCurlPipeHashVerify:
    """Tests for _curl_pipe_with_hash_verify — sha256-then-execute flow."""

    @staticmethod
    def _write_script(text: bytes, path: Path) -> None:
        path.write_bytes(text)

    def test_runs_when_hash_matches(self, tmp_path: Path):
        """Helper executes interpreter command when sha256 matches."""
        import hashlib

        from installer.steps.dependencies import (
            CurlPipeRunOptions,
            _curl_pipe_with_hash_verify,
        )

        script_bytes = b"#!/bin/bash\necho ok\n"
        digest = hashlib.sha256(script_bytes).hexdigest()
        run_calls: list[tuple[str, dict]] = []

        def _fake_run_bash(command: str, **kwargs):
            run_calls.append((command, kwargs))
            if command.startswith("curl -fsSL"):
                # Extract output path from command (-o "<path>")
                out = command.split('-o "')[1].split('"')[0]
                Path(out).write_bytes(script_bytes)
                return True
            return True

        with patch("installer.steps.dependencies._run_bash_with_retry", side_effect=_fake_run_bash):
            ok = _curl_pipe_with_hash_verify(
                "https://example.com/x.sh",
                digest,
                options=CurlPipeRunOptions(interpreter="bash"),
            )
        assert ok is True
        # Two runs: curl-fetch + bash exec
        assert len(run_calls) == 2
        assert run_calls[0][0].startswith('curl -fsSL "https://example.com/x.sh"')
        assert run_calls[1][0].startswith("bash ")

    def test_hard_pin_mismatch_returns_false(self, tmp_path: Path):
        """Hash mismatch with hard pin returns False and records diagnostic."""
        from installer.steps.dependencies import (
            _clear_last_error,
            _curl_pipe_with_hash_verify,
            _get_last_error,
        )

        _clear_last_error()
        wrong_digest = "0" * 64

        def _fake_run_bash(command: str, **kwargs):
            if command.startswith("curl -fsSL"):
                out = command.split('-o "')[1].split('"')[0]
                Path(out).write_bytes(b"different bytes\n")
                return True
            pytest.fail("execute phase must NOT run on hash mismatch")
            return False

        with patch("installer.steps.dependencies._run_bash_with_retry", side_effect=_fake_run_bash):
            ok = _curl_pipe_with_hash_verify("https://example.com/x.sh", wrong_digest)
        assert ok is False
        err = _get_last_error()
        assert "sha256 mismatch" in err
        assert wrong_digest in err

    def test_soft_pin_mismatch_proceeds(self, tmp_path: Path):
        """Soft-pin mismatch logs warning but still executes the script."""
        from installer.steps.dependencies import (
            _clear_last_error,
            _curl_pipe_with_hash_verify,
            _get_last_error,
        )

        _clear_last_error()
        wrong_digest = "0" * 64
        executed: list[bool] = []

        def _fake_run_bash(command: str, **kwargs):
            if command.startswith("curl -fsSL"):
                out = command.split('-o "')[1].split('"')[0]
                Path(out).write_bytes(b"different bytes\n")
                return True
            executed.append(True)
            return True

        with patch("installer.steps.dependencies._run_bash_with_retry", side_effect=_fake_run_bash):
            ok = _curl_pipe_with_hash_verify(
                "https://example.com/x.sh",
                wrong_digest,
                soft_pin=True,
            )
        assert ok is True
        assert executed, "soft-pin must execute script on mismatch"
        assert "soft-pinned" in _get_last_error().lower() or "soft" in _get_last_error().lower()

    def test_temp_file_cleaned_up_on_success(self):
        """Temp file is removed after successful execution."""
        import hashlib

        from installer.steps.dependencies import _curl_pipe_with_hash_verify

        script_bytes = b"#!/bin/bash\nexit 0\n"
        digest = hashlib.sha256(script_bytes).hexdigest()
        captured_paths: list[str] = []

        def _fake_run_bash(command: str, **kwargs):
            if command.startswith("curl -fsSL"):
                out = command.split('-o "')[1].split('"')[0]
                captured_paths.append(out)
                Path(out).write_bytes(script_bytes)
                return True
            return True

        with patch("installer.steps.dependencies._run_bash_with_retry", side_effect=_fake_run_bash):
            _curl_pipe_with_hash_verify("https://example.com/x.sh", digest)
        assert captured_paths
        assert not Path(captured_paths[0]).exists(), "temp file leaked"

    def test_temp_file_cleaned_up_on_mismatch(self):
        """Temp file is removed even when sha256 mismatch fails the install."""
        from installer.steps.dependencies import _curl_pipe_with_hash_verify

        captured_paths: list[str] = []

        def _fake_run_bash(command: str, **kwargs):
            if command.startswith("curl -fsSL"):
                out = command.split('-o "')[1].split('"')[0]
                captured_paths.append(out)
                Path(out).write_bytes(b"bad bytes")
                return True
            return False

        with patch("installer.steps.dependencies._run_bash_with_retry", side_effect=_fake_run_bash):
            _curl_pipe_with_hash_verify("https://example.com/x.sh", "0" * 64)
        assert captured_paths
        assert not Path(captured_paths[0]).exists(), "temp file leaked on mismatch path"

    def test_temp_file_has_owner_only_permissions(self):
        """Temp file is created with 0o600 (owner-only) permissions."""
        import hashlib

        from installer.steps.dependencies import _curl_pipe_with_hash_verify

        script_bytes = b"#!/bin/bash\nexit 0\n"
        digest = hashlib.sha256(script_bytes).hexdigest()
        observed_modes: list[int] = []

        def _fake_run_bash(command: str, **kwargs):
            if command.startswith("curl -fsSL"):
                out = command.split('-o "')[1].split('"')[0]
                # Mode at this point is what mkstemp + fchmod set.
                observed_modes.append(Path(out).stat().st_mode & 0o777)
                Path(out).write_bytes(script_bytes)
                return True
            return True

        with patch("installer.steps.dependencies._run_bash_with_retry", side_effect=_fake_run_bash):
            _curl_pipe_with_hash_verify("https://example.com/x.sh", digest)
        assert observed_modes == [0o600]

    def test_env_vars_wired_into_exec(self):
        """CurlPipeRunOptions.env vars appear as a prefix on the exec command."""
        import hashlib

        from installer.steps.dependencies import (
            CurlPipeRunOptions,
            _curl_pipe_with_hash_verify,
        )

        script_bytes = b"#!/bin/bash\nexit 0\n"
        digest = hashlib.sha256(script_bytes).hexdigest()
        run_calls: list[str] = []

        def _fake_run_bash(command: str, **kwargs):
            run_calls.append(command)
            if command.startswith("curl -fsSL"):
                out = command.split('-o "')[1].split('"')[0]
                Path(out).write_bytes(script_bytes)
            return True

        with patch("installer.steps.dependencies._run_bash_with_retry", side_effect=_fake_run_bash):
            _curl_pipe_with_hash_verify(
                "https://example.com/x.sh",
                digest,
                options=CurlPipeRunOptions(env={"NONINTERACTIVE": "1"}, stdin_devnull=True),
            )
        exec_cmd = run_calls[1]
        assert "NONINTERACTIVE=1" in exec_cmd
        assert exec_cmd.endswith("</dev/null")

    def test_script_args_propagated(self):
        """script_args are appended after the script path on the exec command."""
        import hashlib

        from installer.steps.dependencies import (
            CurlPipeRunOptions,
            _curl_pipe_with_hash_verify,
        )

        script_bytes = b"#!/bin/sh\nexit 0\n"
        digest = hashlib.sha256(script_bytes).hexdigest()
        run_calls: list[str] = []

        def _fake_run_bash(command: str, **kwargs):
            run_calls.append(command)
            if command.startswith("curl -fsSL"):
                out = command.split('-o "')[1].split('"')[0]
                Path(out).write_bytes(script_bytes)
            return True

        with patch("installer.steps.dependencies._run_bash_with_retry", side_effect=_fake_run_bash):
            _curl_pipe_with_hash_verify(
                "https://example.com/x.sh",
                digest,
                options=CurlPipeRunOptions(
                    interpreter="sh",
                    script_args=["-s", "--", "-b", "$(go env GOPATH)/bin"],
                ),
            )
        exec_cmd = run_calls[1]
        assert exec_cmd.startswith("sh ")
        assert "-s" in exec_cmd
        assert "-b" in exec_cmd
        assert "go env GOPATH" in exec_cmd

    def test_curl_failure_returns_false_no_exec(self):
        """When curl fetch fails, exec must not run and helper returns False."""
        from installer.steps.dependencies import _curl_pipe_with_hash_verify

        def _fake_run_bash(command: str, **kwargs):
            if command.startswith("curl -fsSL"):
                return False
            pytest.fail("exec must not run when curl fetch fails")
            return False

        with patch("installer.steps.dependencies._run_bash_with_retry", side_effect=_fake_run_bash):
            ok = _curl_pipe_with_hash_verify("https://example.com/x.sh", "0" * 64)
        assert ok is False


class TestInstallRtk:
    """Tests for install_rtk() — RTK CLI installation (brew primary, curl fallback)."""

    @patch("installer.steps.dependencies._init_rtk")
    @patch("installer.steps.dependencies._heal_broken_rtk")
    @patch("installer.steps.dependencies._symlink_to_pilot_bin")
    @patch("installer.steps.dependencies.command_exists", return_value=False)
    def test_install_rtk_pins_version_from_manifest(self, _cmd, _symlink, _heal, _init):
        """The docstring promises the manifest-pinned version; the rtk install.sh
        only honours that through RTK_VERSION, else it fetches whatever release
        GitHub currently serves as latest."""
        from installer.manifest import get as manifest_get
        from installer.steps.dependencies import install_rtk

        with patch("installer.steps.dependencies._curl_pipe_from_manifest", return_value=True) as mock_helper:
            assert install_rtk() is True

        opts = mock_helper.call_args[0][1]
        assert opts.env is not None, "no env passed: rtk install floats to latest"
        assert opts.env.get("RTK_VERSION") == f"v{manifest_get('rtk-installer').version}"

    def test_install_rtk_exists(self):
        """install_rtk function exists and is callable."""
        from installer.steps.dependencies import install_rtk

        assert callable(install_rtk)

    @patch("installer.steps.dependencies._symlink_to_pilot_bin")
    @patch("installer.steps.dependencies._curl_pipe_from_manifest", return_value=True)
    @patch("installer.steps.dependencies.command_exists", return_value=True)
    def test_install_rtk_upgrades_when_already_installed(self, _mock_cmd, mock_curl, _mock_symlink):
        """install_rtk always runs curl installer to upgrade even when rtk exists."""
        from installer.steps.dependencies import install_rtk

        result = install_rtk()
        assert result is True
        mock_curl.assert_called_once()

    @patch("installer.steps.dependencies._symlink_to_pilot_bin")
    @patch("installer.steps.dependencies.command_exists", return_value=False)
    def test_install_rtk_runs_curl_fallback(self, _mock_cmd, _mock_symlink):
        """install_rtk routes through manifest-pinned curl helper for rtk-installer."""
        from installer.steps.dependencies import install_rtk

        with patch("installer.steps.dependencies._curl_pipe_from_manifest", return_value=True) as mock_helper:
            result = install_rtk()

        assert result is True
        mock_helper.assert_called_once()
        assert mock_helper.call_args[0][0] == "rtk-installer"
        opts = mock_helper.call_args[0][1]
        assert opts.interpreter == "sh"
        assert opts.timeout == 120

    @patch("installer.steps.dependencies.command_exists", return_value=False)
    def test_install_rtk_returns_false_when_curl_fails(self, _mock_cmd):
        """install_rtk returns False when manifest-pinned curl install fails."""
        from installer.steps.dependencies import install_rtk

        with patch("installer.steps.dependencies._curl_pipe_from_manifest", return_value=False):
            result = install_rtk()

        assert result is False

    def test_install_rtk_relinks_broken_shadowing_binary(self, tmp_path: Path):
        """Regression #155: a glibc-incompatible rtk dropped by the curl installer
        at ~/.local/bin/rtk must not shadow a working build (e.g. Homebrew) on
        PATH — install_rtk relinks both it and ~/.pilot/bin/rtk to the working one.
        """
        from installer.steps import dependencies

        local_bin = tmp_path / ".local" / "bin"
        brew_bin = tmp_path / "brew" / "bin"
        local_bin.mkdir(parents=True)
        brew_bin.mkdir(parents=True)
        (tmp_path / ".pilot" / "bin").mkdir(parents=True)

        working = brew_bin / "rtk"
        working.write_text("#!/bin/sh\necho 'rtk 0.42.0'\n")
        working.chmod(0o755)

        # Simulates the GLIBC_2.39 loader failure: present but exits non-zero.
        broken = local_bin / "rtk"
        broken.write_text('#!/bin/sh\necho "GLIBC_2.39 not found" >&2\nexit 1\n')
        broken.chmod(0o755)

        with (
            patch.dict(os.environ, {"PATH": f"{local_bin}{os.pathsep}{brew_bin}"}),
            patch("installer.steps.dependencies.Path.home", return_value=tmp_path),
            patch("installer.steps.dependencies._curl_pipe_from_manifest", return_value=True),
            patch("installer.steps.dependencies._init_rtk"),
            patch("installer.steps.dependencies.command_exists", return_value=False),
        ):
            result = dependencies.install_rtk()

        assert result is True
        # The shadowing binary now resolves to the working build instead of itself.
        assert broken.is_symlink()
        assert broken.resolve() == working.resolve()
        # pilot's own symlink also points at the working build.
        assert (tmp_path / ".pilot" / "bin" / "rtk").resolve() == working.resolve()


class TestInitRtk:
    """_init_rtk runs agent-specific init only for the agents the user has installed.

    Agent detection delegates to ``installer.platform_utils.is_claude_installed`` /
    ``is_codex_installed`` (PATH + native-installer fallback paths) — same helpers
    used by ``cmd_install`` and ``ClaudeFilesStep``, so the gating is consistent
    across the install flow.
    """

    def _runs(self, mock_run):
        return [tuple(call.args[0]) for call in mock_run.call_args_list]

    @patch("installer.steps.dependencies.subprocess.run")
    @patch("installer.steps.dependencies.shutil.which", return_value="/fake/rtk")
    @patch("installer.steps.dependencies.is_codex_installed", return_value=True)
    @patch("installer.steps.dependencies.is_claude_installed", return_value=False)
    def test_init_rtk_skips_claude_init_when_claude_absent(self, _claude, _codex, _which, mock_run):
        """Codex-only systems must NOT receive rtk init for Claude."""
        from installer.steps.dependencies import _init_rtk

        _init_rtk()
        runs = self._runs(mock_run)
        assert all("--auto-patch" not in args for args in runs), (
            f"Claude rtk init must be skipped when claude is absent; got: {runs}"
        )
        assert any("--codex" in args for args in runs)

    @patch("installer.steps.dependencies.subprocess.run")
    @patch("installer.steps.dependencies.shutil.which", return_value="/fake/rtk")
    @patch("installer.steps.dependencies.is_codex_installed", return_value=False)
    @patch("installer.steps.dependencies.is_claude_installed", return_value=True)
    def test_init_rtk_skips_codex_init_when_codex_absent(self, _claude, _codex, _which, mock_run):
        """Claude-only systems must NOT receive rtk init for Codex (existing behavior)."""
        from installer.steps.dependencies import _init_rtk

        _init_rtk()
        runs = self._runs(mock_run)
        assert any("--auto-patch" in args for args in runs)
        assert all("--codex" not in args for args in runs), (
            f"Codex rtk init must be skipped when codex is absent; got: {runs}"
        )

    @patch("installer.steps.dependencies.subprocess.run")
    @patch("installer.steps.dependencies.shutil.which", return_value="/fake/rtk")
    @patch("installer.steps.dependencies.is_codex_installed", return_value=True)
    @patch("installer.steps.dependencies.is_claude_installed", return_value=True)
    def test_init_rtk_runs_both_when_both_agents_present(self, _claude, _codex, _which, mock_run):
        """Both-agents systems get both rtk inits."""
        from installer.steps.dependencies import _init_rtk

        _init_rtk()
        runs = self._runs(mock_run)
        assert any("--auto-patch" in args for args in runs)
        assert any("--codex" in args for args in runs)


class TestInstallCodegraph:
    """Tests for install_codegraph() — CodeGraph code knowledge graph."""

    def test_install_codegraph_exists(self):
        """install_codegraph function exists and is callable."""
        from installer.steps.dependencies import install_codegraph

        assert callable(install_codegraph)

    @patch("installer.steps.dependencies._symlink_to_pilot_bin")
    def test_install_codegraph_always_runs_npm_install(self, mock_symlink):
        """install_codegraph pins the bundle and disables optional telemetry."""
        from installer.manifest import get
        from installer.steps.dependencies import install_codegraph

        with patch("installer.steps.dependencies._run_bash_with_retry", side_effect=[True, True]) as mock_bash:
            result = install_codegraph()

        assert result is True
        assert mock_bash.call_count == 2
        install_call, telemetry_call = mock_bash.call_args_list
        call_args = str(install_call)
        expected_version = get("codegraph").version
        assert f"@colbymchenry/codegraph@{expected_version}" in call_args
        assert "--force" in call_args
        assert "--ignore-scripts" in call_args
        assert telemetry_call.args[0] == "CODEGRAPH_TELEMETRY=0 codegraph telemetry off"
        mock_symlink.assert_called_once_with("codegraph")

    @patch("installer.steps.dependencies._symlink_to_pilot_bin")
    def test_install_codegraph_uses_longer_timeout(self, mock_symlink):
        """CodeGraph's self-contained platform bundle gets the global npm timeout."""
        from installer.steps.dependencies import GLOBAL_NPM_INSTALL_TIMEOUT, install_codegraph

        with patch("installer.steps.dependencies._run_bash_with_retry", side_effect=[True, True]) as mock_bash:
            result = install_codegraph()

        assert result is True
        assert mock_bash.call_args_list[0].kwargs["timeout"] == GLOBAL_NPM_INSTALL_TIMEOUT
        mock_symlink.assert_called_once_with("codegraph")

    @patch("installer.steps.dependencies._symlink_to_pilot_bin")
    def test_install_codegraph_returns_false_when_npm_fails(self, _mock_symlink):
        """install_codegraph returns False when npm install fails."""
        from installer.steps.dependencies import install_codegraph

        with patch("installer.steps.dependencies._run_bash_with_retry", return_value=False):
            result = install_codegraph()

        assert result is False

    @patch("installer.steps.dependencies._symlink_to_pilot_bin")
    def test_install_codegraph_returns_false_when_telemetry_opt_out_fails(self, mock_symlink):
        """A Pilot-managed CodeGraph install must not silently retain telemetry."""
        from installer.steps.dependencies import install_codegraph

        with patch("installer.steps.dependencies._run_bash_with_retry", side_effect=[True, False]):
            result = install_codegraph()

        assert result is False
        mock_symlink.assert_called_once_with("codegraph")


class TestInstallAstGrep:
    """Tests for Homebrew-first ast-grep with an npm fallback."""

    @patch("installer.steps.dependencies._symlink_to_pilot_bin")
    @patch("installer.steps.dependencies._load_owned_tools", return_value=set())
    @patch("installer.steps.dependencies.command_exists", return_value=True)
    def test_preserves_existing_homebrew_or_user_install(self, _mock_exists, _mock_owned, mock_symlink):
        from installer.steps.dependencies import install_ast_grep

        with patch("installer.steps.dependencies._run_bash_with_retry") as mock_bash:
            assert install_ast_grep() is True

        mock_bash.assert_not_called()
        mock_symlink.assert_called_once_with("ast-grep")

    @patch("installer.steps.dependencies._symlink_to_pilot_bin")
    @patch("installer.steps.dependencies._load_owned_tools", return_value=set())
    @patch("installer.steps.dependencies.command_exists", return_value=False)
    def test_installs_manifest_pinned_npm_fallback(self, _mock_exists, _mock_owned, mock_symlink):
        from installer.manifest import get
        from installer.steps.dependencies import GLOBAL_NPM_INSTALL_TIMEOUT, install_ast_grep

        with patch("installer.steps.dependencies._run_bash_with_retry", return_value=True) as mock_bash:
            assert install_ast_grep() is True

        command = mock_bash.call_args.args[0]
        assert f"@ast-grep/cli@{get('ast-grep-npm').version}" in command
        assert "--ignore-scripts" not in command
        assert mock_bash.call_args.kwargs["timeout"] == GLOBAL_NPM_INSTALL_TIMEOUT
        mock_symlink.assert_called_once_with("ast-grep")

    @patch("installer.steps.dependencies._load_owned_tools", return_value=set())
    @patch("installer.steps.dependencies.command_exists", return_value=False)
    def test_returns_false_when_npm_fallback_fails(self, _mock_exists, _mock_owned):
        from installer.steps.dependencies import install_ast_grep

        with patch("installer.steps.dependencies._run_bash_with_retry", return_value=False):
            assert install_ast_grep() is False


class TestInitializeCodegraph:
    """Tests for initialize_codegraph() — init, index, and sync."""

    @patch("installer.steps.dependencies._has_git_commits", return_value=True)
    @patch("installer.steps.dependencies.command_exists", return_value=True)
    @patch("installer.steps.dependencies._is_codegraph_indexed", return_value=True)
    def test_skips_index_when_already_indexed(self, _mock_indexed, _mock_cmd, _mock_commits, tmp_path: Path):
        """Skips index and just syncs when already indexed."""
        from installer.steps.dependencies import initialize_codegraph

        (tmp_path / ".git").mkdir()
        codegraph_dir = tmp_path / ".codegraph"
        codegraph_dir.mkdir()

        with (
            patch("installer.steps.dependencies._codegraph_reindex_recommended", return_value=False),
            patch("installer.steps.dependencies._run_bash_with_retry", return_value=True) as mock_bash,
        ):
            result = initialize_codegraph(tmp_path)

        assert result is True
        calls = [str(c) for c in mock_bash.call_args_list]
        assert not any("codegraph init" in c for c in calls)
        assert not any("codegraph index" in c for c in calls)
        assert any("codegraph sync" in c for c in calls)

    @patch("installer.steps.dependencies._has_git_commits", return_value=True)
    @patch("installer.steps.dependencies.command_exists", return_value=True)
    @patch("installer.steps.dependencies._is_codegraph_indexed", return_value=True)
    @patch("installer.steps.dependencies._codegraph_reindex_recommended", return_value=True)
    def test_rebuilds_existing_index_when_codegraph_recommends_it(
        self,
        _mock_reindex,
        _mock_indexed,
        _mock_cmd,
        _mock_commits,
        tmp_path: Path,
    ):
        from installer.steps.dependencies import initialize_codegraph

        (tmp_path / ".git").mkdir()
        (tmp_path / ".codegraph").mkdir()

        with patch("installer.steps.dependencies._run_bash_with_retry", return_value=True) as mock_bash:
            assert initialize_codegraph(tmp_path) is True

        index_calls = [call for call in mock_bash.call_args_list if "codegraph index" in call.args[0]]
        assert len(index_calls) == 1
        assert index_calls[0].kwargs["stream"] is True

    @patch("installer.steps.dependencies.subprocess.run")
    def test_reindex_recommendation_comes_from_status_json(self, mock_run, tmp_path: Path):
        from installer.steps.dependencies import _codegraph_reindex_recommended

        mock_run.return_value = subprocess.CompletedProcess(
            ["codegraph", "status", "--json"],
            0,
            stdout='{"index":{"reindexRecommended":true}}',
            stderr="",
        )

        assert _codegraph_reindex_recommended(tmp_path) is True
        assert mock_run.call_args.args[0] == ["codegraph", "status", "--json"]
        assert mock_run.call_args.kwargs["env"]["CODEGRAPH_TELEMETRY"] == "0"

    @patch("installer.steps.dependencies.subprocess.run")
    def test_invalid_status_json_does_not_force_reindex(self, mock_run, tmp_path: Path):
        from installer.steps.dependencies import _codegraph_reindex_recommended

        mock_run.return_value = subprocess.CompletedProcess(
            ["codegraph", "status", "--json"], 0, stdout="not-json", stderr=""
        )

        assert _codegraph_reindex_recommended(tmp_path) is False

    @patch("installer.steps.dependencies.command_exists", return_value=False)
    def test_returns_false_when_codegraph_not_installed(self, _mock_cmd, tmp_path: Path):
        """Returns False when codegraph binary is not available."""
        from installer.steps.dependencies import initialize_codegraph

        result = initialize_codegraph(tmp_path)

        assert result is False

    @patch("installer.steps.dependencies._has_git_commits", return_value=True)
    @patch("installer.steps.dependencies.command_exists", return_value=True)
    @patch("installer.steps.dependencies._is_codegraph_indexed", return_value=False)
    def test_full_init_sequence(self, _mock_indexed, _mock_cmd, _mock_commits, tmp_path: Path):
        """Runs init, index, and sync in sequence."""
        from installer.steps.dependencies import initialize_codegraph

        (tmp_path / ".git").mkdir()
        codegraph_dir = tmp_path / ".codegraph"

        def fake_bash(command: str, cwd: Path | None = None, timeout: int = 120, stream: bool = False) -> bool:
            if "codegraph init" in command:
                codegraph_dir.mkdir(parents=True, exist_ok=True)
            return True

        with patch("installer.steps.dependencies._run_bash_with_retry", side_effect=fake_bash) as mock_bash:
            result = initialize_codegraph(tmp_path)

        assert result is True
        calls = [str(c) for c in mock_bash.call_args_list]
        assert any("codegraph init" in c for c in calls)
        assert any("codegraph index" in c for c in calls)
        assert any("codegraph sync" in c for c in calls)
        codegraph_commands = [c.args[0] for c in mock_bash.call_args_list]
        assert all(command.startswith("CODEGRAPH_TELEMETRY=0 codegraph ") for command in codegraph_commands)

    @patch("installer.steps.dependencies._has_git_commits", return_value=True)
    @patch("installer.steps.dependencies.command_exists", return_value=True)
    @patch("installer.steps.dependencies._is_codegraph_indexed", return_value=False)
    def test_index_streams_output(self, _mock_indexed, _mock_cmd, _mock_commits, tmp_path: Path):
        """Index is called with stream=True for visible progress."""
        from installer.steps.dependencies import initialize_codegraph

        (tmp_path / ".git").mkdir()
        codegraph_dir = tmp_path / ".codegraph"
        codegraph_dir.mkdir()

        with patch("installer.steps.dependencies._run_bash_with_retry", return_value=True) as mock_bash:
            initialize_codegraph(tmp_path)

        index_calls = [c for c in mock_bash.call_args_list if "codegraph index" in str(c)]
        assert len(index_calls) == 1
        assert index_calls[0].kwargs.get("stream") is True or (
            len(index_calls[0].args) > 3 and index_calls[0].args[3] is True
        )

    @patch("installer.steps.dependencies.command_exists", return_value=True)
    def test_returns_false_when_not_git_repo(self, _mock_cmd, tmp_path: Path):
        """Returns False when directory is not a git repository."""
        from installer.steps.dependencies import initialize_codegraph

        result = initialize_codegraph(tmp_path)

        assert result is False

    @patch("installer.steps.dependencies.command_exists", return_value=True)
    def test_returns_false_in_repo_without_commits(self, _mock_cmd, tmp_path: Path):
        """A `git init`'d directory with zero commits is treated like a non-git dir.

        Regression: previously the .git/ check passed but CodeGraph then crashed
        with "Failed to index: unable to open database file" because the repo
        had nothing to enumerate.
        """
        from installer.steps.dependencies import initialize_codegraph

        subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True, timeout=10)

        with patch("installer.steps.dependencies._run_bash_with_retry") as mock_bash:
            result = initialize_codegraph(tmp_path)

        assert result is False
        assert mock_bash.call_count == 0, (
            f"codegraph commands must not run in a commit-less repo; got: {mock_bash.call_args_list}"
        )

    @patch("installer.steps.dependencies._has_git_commits", return_value=True)
    @patch("installer.steps.dependencies.command_exists", return_value=True)
    @patch("installer.steps.dependencies._is_codegraph_indexed", return_value=True)
    def test_works_in_git_subdirectory(self, _mock_indexed, _mock_cmd, _mock_commits, tmp_path: Path):
        """Works when .git is in a parent directory (monorepo subdirectory)."""
        from installer.steps.dependencies import initialize_codegraph

        (tmp_path / ".git").mkdir()
        subdir = tmp_path / "packages" / "my-app"
        subdir.mkdir(parents=True)
        (subdir / ".codegraph").mkdir()

        with patch("installer.steps.dependencies._run_bash_with_retry", return_value=True):
            result = initialize_codegraph(subdir)

        assert result is True

    @patch("installer.steps.dependencies._has_git_commits", return_value=True)
    @patch("installer.steps.dependencies.command_exists", return_value=True)
    @patch("installer.steps.dependencies._is_codegraph_indexed", return_value=False)
    def test_returns_false_when_init_fails(self, _mock_indexed, _mock_cmd, _mock_commits, tmp_path: Path):
        """Returns False when codegraph init fails."""
        from installer.steps.dependencies import initialize_codegraph

        (tmp_path / ".git").mkdir()
        with patch("installer.steps.dependencies._run_bash_with_retry", return_value=False) as mock_bash:
            result = initialize_codegraph(tmp_path)

        assert result is False
        assert any("codegraph init" in str(c) for c in mock_bash.call_args_list), (
            "init must have been attempted to genuinely test the failure path"
        )

    @patch("installer.steps.dependencies._has_git_commits", return_value=True)
    @patch("installer.steps.dependencies.command_exists", return_value=True)
    @patch("installer.steps.dependencies._is_codegraph_indexed", return_value=False)
    def test_returns_false_when_index_fails(self, _mock_indexed, _mock_cmd, _mock_commits, tmp_path: Path):
        """Returns False when codegraph index fails."""
        from installer.steps.dependencies import initialize_codegraph

        (tmp_path / ".git").mkdir()
        codegraph_dir = tmp_path / ".codegraph"

        def fake_bash(command: str, cwd: Path | None = None, timeout: int = 120, stream: bool = False) -> bool:
            if "codegraph init" in command:
                codegraph_dir.mkdir(parents=True, exist_ok=True)
                return True
            if "codegraph index" in command:
                return False
            return True

        with patch("installer.steps.dependencies._run_bash_with_retry", side_effect=fake_bash):
            result = initialize_codegraph(tmp_path)

        assert result is False


class TestSymlinkToPilotBin:
    """Tests for _symlink_to_pilot_bin() — creates symlinks in ~/.pilot/bin/."""

    def test_creates_symlink_when_binary_exists(self, tmp_path: Path):
        """Creates a symlink in pilot bin dir pointing to the real binary."""
        from installer.steps.dependencies import _symlink_to_pilot_bin

        fake_bin = tmp_path / "src" / "codegraph"
        fake_bin.parent.mkdir(parents=True)
        fake_bin.write_text("#!/bin/sh\n")
        fake_bin.chmod(0o755)

        with (
            patch("installer.steps.dependencies.shutil.which", return_value=str(fake_bin)),
            patch("installer.steps.dependencies.Path.home", return_value=tmp_path),
        ):
            pilot_bin_dir = tmp_path / ".pilot" / "bin"
            pilot_bin_dir.mkdir(parents=True, exist_ok=True)
            _symlink_to_pilot_bin("codegraph")

        link = tmp_path / ".pilot" / "bin" / "codegraph"
        assert link.is_symlink()
        assert link.resolve() == fake_bin.resolve()

    def test_skips_when_binary_not_found(self, tmp_path: Path):
        """Does nothing when the binary is not in PATH."""
        from installer.steps.dependencies import _symlink_to_pilot_bin

        with (
            patch("installer.steps.dependencies.shutil.which", return_value=None),
            patch("installer.steps.dependencies.Path.home", return_value=tmp_path),
        ):
            _symlink_to_pilot_bin("codegraph")

        link = tmp_path / ".pilot" / "bin" / "codegraph"
        assert not link.exists()

    def test_replaces_existing_symlink(self, tmp_path: Path):
        """Replaces an existing symlink with the new target."""
        from installer.steps.dependencies import _symlink_to_pilot_bin

        fake_bin = tmp_path / "new_codegraph"
        fake_bin.write_text("#!/bin/sh\n")
        fake_bin.chmod(0o755)

        pilot_bin_dir = tmp_path / ".pilot" / "bin"
        pilot_bin_dir.mkdir(parents=True)
        old_link = pilot_bin_dir / "codegraph"
        old_link.symlink_to("/nonexistent/old/path")

        with (
            patch("installer.steps.dependencies.shutil.which", return_value=str(fake_bin)),
            patch("installer.steps.dependencies.Path.home", return_value=tmp_path),
        ):
            _symlink_to_pilot_bin("codegraph")

        assert old_link.is_symlink()
        assert old_link.resolve() == fake_bin.resolve()


class TestInstallPluginDependencies:
    """Test plugin dependencies installation via bun/npm install."""

    def test_install_plugin_dependencies_exists(self):
        """_install_plugin_dependencies function exists."""
        from installer.steps.dependencies import _install_plugin_dependencies

        assert callable(_install_plugin_dependencies)

    def test_install_plugin_dependencies_returns_false_if_no_pilot_home(self):
        """Returns False if ~/.pilot/ doesn't exist."""
        from installer.steps.dependencies import _install_plugin_dependencies

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, "home", return_value=Path(tmpdir)):
                result = _install_plugin_dependencies(Path(tmpdir), ui=None)
            assert result is False

    def test_install_plugin_dependencies_returns_false_if_no_package_json(self):
        """Returns False when ~/.pilot/ exists but package.json is missing."""
        from installer.steps.dependencies import _install_plugin_dependencies

        with tempfile.TemporaryDirectory() as tmpdir:
            pilot_home = Path(tmpdir) / ".pilot"
            pilot_home.mkdir(parents=True)

            with patch.object(Path, "home", return_value=Path(tmpdir)):
                result = _install_plugin_dependencies(Path(tmpdir), ui=None)
            assert result is False

    # `ensure_bun_on_path` is patched in every case below: it consults the real PATH and
    # ~/.bun/bin, so leaving it live makes these assertions depend on whether the machine
    # running the suite happens to have bun installed.

    @patch("installer.steps.dependencies._run_bash_with_retry")
    @patch("installer.steps.dependencies.ensure_bun_on_path", return_value=True)
    @patch("installer.steps.dependencies.command_exists")
    def test_install_plugin_dependencies_runs_bun_install(self, mock_cmd_exists, _mock_bun, mock_run):
        """Runs `bun install` in ~/.pilot/ when bun is available."""
        from installer.steps.dependencies import _install_plugin_dependencies

        mock_cmd_exists.side_effect = lambda cmd: cmd == "bun"
        mock_run.return_value = True

        with tempfile.TemporaryDirectory() as tmpdir:
            pilot_home = Path(tmpdir) / ".pilot"
            pilot_home.mkdir(parents=True)
            (pilot_home / "package.json").write_text('{"name": "test"}')

            with patch.object(Path, "home", return_value=Path(tmpdir)):
                result = _install_plugin_dependencies(Path(tmpdir), ui=None)

            assert result is True
            mock_run.assert_called_with("bun install", cwd=pilot_home)

    @patch("installer.steps.dependencies._run_bash_with_retry")
    @patch("installer.steps.dependencies.ensure_bun_on_path", return_value=False)
    @patch("installer.steps.dependencies.command_exists")
    def test_install_plugin_dependencies_falls_back_to_npm(self, mock_cmd_exists, _mock_bun, mock_run):
        """Falls back to `npm install` when bun is unavailable."""
        from installer.steps.dependencies import _install_plugin_dependencies

        mock_cmd_exists.side_effect = lambda cmd: cmd == "npm"
        mock_run.return_value = True

        with tempfile.TemporaryDirectory() as tmpdir:
            pilot_home = Path(tmpdir) / ".pilot"
            pilot_home.mkdir(parents=True)
            (pilot_home / "package.json").write_text('{"name": "test"}')

            with patch.object(Path, "home", return_value=Path(tmpdir)):
                result = _install_plugin_dependencies(Path(tmpdir), ui=None)

        assert result is True
        npm_calls = [c for c in mock_run.call_args_list if "npm" in str(c)]
        assert len(npm_calls) > 0, "npm install should be called when bun is unavailable"

    @patch("installer.steps.dependencies._run_bash_with_retry")
    @patch("installer.steps.dependencies.ensure_bun_on_path", return_value=True)
    @patch("installer.steps.dependencies.command_exists")
    def test_install_plugin_dependencies_falls_back_to_npm_when_bun_install_fails(
        self, mock_cmd_exists, _mock_bun, mock_run
    ):
        """A bun that exists but errors out must still leave the deps installed.

        Regression: a failing `bun install` returned False immediately with npm sitting
        unused, so ~/.pilot/ ended up with no node_modules at all.
        """
        from installer.steps.dependencies import _install_plugin_dependencies

        mock_cmd_exists.side_effect = lambda cmd: cmd == "npm"
        mock_run.side_effect = lambda cmd, **_kwargs: cmd != "bun install"

        with tempfile.TemporaryDirectory() as tmpdir:
            pilot_home = Path(tmpdir) / ".pilot"
            pilot_home.mkdir(parents=True)
            (pilot_home / "package.json").write_text('{"name": "test"}')

            with patch.object(Path, "home", return_value=Path(tmpdir)):
                result = _install_plugin_dependencies(Path(tmpdir), ui=None)

        assert result is True
        attempted = [c.args[0] for c in mock_run.call_args_list]
        assert "bun install" in attempted, "bun should still be tried first"
        assert "npm install" in attempted, "npm must pick up after bun install fails"

    @patch("installer.steps.dependencies.ensure_bun_on_path", return_value=False)
    @patch("installer.steps.dependencies.command_exists")
    def test_install_plugin_dependencies_returns_false_when_no_package_manager(self, mock_cmd_exists, _mock_bun):
        """Returns False when neither bun nor npm is available."""
        from installer.steps.dependencies import _install_plugin_dependencies

        mock_cmd_exists.return_value = False

        with tempfile.TemporaryDirectory() as tmpdir:
            pilot_home = Path(tmpdir) / ".pilot"
            pilot_home.mkdir(parents=True)
            (pilot_home / "package.json").write_text('{"name": "test"}')

            with patch.object(Path, "home", return_value=Path(tmpdir)):
                result = _install_plugin_dependencies(Path(tmpdir), ui=None)

        assert result is False


class TestNvmInstallBugCondition:
    """Bug-condition tests: verify NVM installation uses 300s timeout and explicit NVM_DIR."""

    @patch("installer.steps.dependencies._run_bash_with_retry")
    @patch("installer.steps.dependencies.command_exists")
    def test_nvm_install_uses_300s_timeout(self, mock_cmd_exists, mock_run):
        """nvm install 24 must use 300s timeout (not the default 120s)."""
        from installer.steps.dependencies import install_nodejs

        mock_cmd_exists.return_value = False
        mock_run.return_value = True

        with tempfile.TemporaryDirectory() as tmpdir:
            home_dir = Path(tmpdir)
            nvm_dir = home_dir / ".nvm"
            nvm_dir.mkdir()
            (nvm_dir / "nvm.sh").touch()

            with patch.object(Path, "home", return_value=home_dir):
                install_nodejs()

        nvm_install_calls = [c for c in mock_run.call_args_list if "nvm install" in str(c)]
        assert nvm_install_calls, "nvm install should be called"
        for call in nvm_install_calls:
            timeout = call.kwargs.get("timeout")
            assert timeout == 300, f"Expected timeout=300 for nvm install, got timeout={timeout}"

    @patch("installer.steps.dependencies._run_bash_with_retry")
    @patch("installer.steps.dependencies.command_exists")
    def test_nvm_install_sets_nvm_dir_in_command(self, mock_cmd_exists, mock_run):
        """nvm install 24 command must explicitly export NVM_DIR before sourcing nvm.sh."""
        from installer.steps.dependencies import install_nodejs

        mock_cmd_exists.return_value = False
        mock_run.return_value = True

        with tempfile.TemporaryDirectory() as tmpdir:
            home_dir = Path(tmpdir)
            nvm_dir = home_dir / ".nvm"
            nvm_dir.mkdir()
            (nvm_dir / "nvm.sh").touch()

            with patch.object(Path, "home", return_value=home_dir):
                install_nodejs()

        nvm_install_calls = [c for c in mock_run.call_args_list if "nvm install" in str(c)]
        assert nvm_install_calls, "nvm install should be called"
        nvm_cmd = nvm_install_calls[0][0][0]
        assert "NVM_DIR" in nvm_cmd, f"NVM_DIR must be explicitly set in nvm install command, got: {nvm_cmd}"


class TestNvmInstallPreservation:
    """Preservation tests: NVM behavior that must NOT change after the timeout/NVM_DIR fix."""

    @patch("installer.steps.dependencies._node_major_version", return_value=24)
    def test_preservation_install_nodejs_returns_true_when_node24_installed(self, _mock_node_version):
        """PRESERVATION: install_nodejs() returns immediately for a compatible Node."""
        import os

        from installer.steps.dependencies import install_nodejs

        original_path = os.environ.get("PATH", "")
        result = install_nodejs()
        assert result is True
        assert os.environ.get("PATH", "") == original_path

    @patch("installer.steps.dependencies._run_bash_with_retry")
    @patch("installer.steps.dependencies.command_exists")
    def test_preservation_install_nodejs_returns_false_when_nvm_install_fails(self, mock_cmd_exists, mock_run):
        """PRESERVATION: install_nodejs() returns False when NVM installation itself fails."""
        from installer.steps.dependencies import install_nodejs

        mock_cmd_exists.return_value = False
        mock_run.return_value = False

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, "home", return_value=Path(tmpdir)):
                result = install_nodejs()

        assert result is False

    @patch("installer.steps.dependencies._run_bash_with_retry", return_value=True)
    @patch("installer.steps.dependencies._node_major_version", return_value=22)
    @patch("installer.steps.dependencies.command_exists", return_value=True)
    def test_node22_is_upgraded_through_pinned_nvm(self, _mock_exists, _mock_node_version, mock_run, tmp_path: Path):
        """A present but incompatible Node must not bypass Pilot's Node 24 baseline."""
        nvm_dir = tmp_path / ".nvm"
        nvm_dir.mkdir()
        (nvm_dir / "nvm.sh").touch()

        from installer.steps.dependencies import install_nodejs

        with patch.object(Path, "home", return_value=tmp_path):
            assert install_nodejs() is True

        install_call = next(call for call in mock_run.call_args_list if "nvm install" in call.args[0])
        assert "nvm install 24" in install_call.args[0]
        assert "nvm use 24" in install_call.args[0]


class TestInstallNodejsPathUpdate:
    """Test that install_nodejs updates PATH after NVM installation."""

    @patch("installer.steps.dependencies._node_major_version", return_value=24)
    def test_install_nodejs_returns_true_when_already_installed(self, _mock_node_version):
        """install_nodejs leaves PATH alone when compatible Node is installed."""
        import os

        from installer.steps.dependencies import install_nodejs

        original_path = os.environ.get("PATH", "")

        result = install_nodejs()

        assert result is True
        assert os.environ.get("PATH", "") == original_path, "PATH should not be modified when node already installed"

    @patch("installer.steps.dependencies._run_bash_with_retry")
    @patch("installer.steps.dependencies.command_exists")
    def test_install_nodejs_updates_path_after_nvm_install(self, mock_cmd_exists, mock_run):
        """install_nodejs updates os.environ[PATH] after NVM successfully installs Node.js."""
        import os

        from installer.steps.dependencies import install_nodejs

        mock_cmd_exists.return_value = False
        mock_run.return_value = True

        original_path = os.environ.get("PATH", "")
        nvm_node_bin = None
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                home_dir = Path(tmpdir)
                nvm_dir = home_dir / ".nvm"
                nvm_dir.mkdir()
                (nvm_dir / "nvm.sh").touch()
                nvm_node_bin = nvm_dir / "versions" / "node" / "v24.20.0" / "bin"
                nvm_node_bin.mkdir(parents=True)

                with patch.object(Path, "home", return_value=home_dir):
                    result = install_nodejs()

            assert result is True
            assert str(nvm_node_bin) in os.environ.get("PATH", ""), (
                "NVM node bin dir should be added to PATH after successful install"
            )
        finally:
            current_path = os.environ.get("PATH", "")
            if nvm_node_bin and str(nvm_node_bin) in current_path:
                paths = [p for p in current_path.split(":") if p != str(nvm_node_bin)]
                os.environ["PATH"] = ":".join(paths)
            elif current_path != original_path:
                os.environ["PATH"] = original_path


class TestPrecacheNpxMcpServers:
    """Test pre-caching of npx-based MCP server packages."""

    def test_returns_true_when_no_mcp_json(self):
        """Returns True when .mcp.json doesn't exist."""
        from installer.steps.dependencies import _precache_npx_mcp_servers

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, "home", return_value=Path(tmpdir)):
                assert _precache_npx_mcp_servers(None) is True

    def test_returns_true_when_all_cached(self):
        """Returns True immediately when all packages are already cached."""
        import json

        from installer.steps.dependencies import _precache_npx_mcp_servers

        mcp_config = {
            "mcpServers": {
                "web-fetch": {"command": "npx", "args": ["-y", "fetcher-mcp"]},
            }
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            pilot_home = Path(tmpdir) / ".pilot"
            pilot_home.mkdir(parents=True)
            (pilot_home / ".mcp.json").write_text(json.dumps(mcp_config))

            with patch.object(Path, "home", return_value=Path(tmpdir)):
                with patch(
                    "installer.steps.dependencies._is_npx_package_cached",
                    return_value=True,
                ):
                    assert _precache_npx_mcp_servers(None) is True

    def test_extracts_npx_packages_from_mcp_json(self):
        """Extracts only npx -y packages from .mcp.json."""
        import json

        from installer.steps.dependencies import _precache_npx_mcp_servers

        mcp_config = {
            "mcpServers": {
                "web-fetch": {"command": "npx", "args": ["-y", "fetcher-mcp"]},
                "context7": {"command": "npx", "args": ["-y", "@upstash/context7-mcp"]},
                "grep": {"type": "http", "url": "https://mcp.grep.app"},
                "mem": {"command": "sh", "args": ["-c", "bun run server.cjs"]},
            }
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            pilot_home = Path(tmpdir) / ".pilot"
            pilot_home.mkdir(parents=True)
            (pilot_home / ".mcp.json").write_text(json.dumps(mcp_config))

            with patch.object(Path, "home", return_value=Path(tmpdir)):
                with patch(
                    "installer.steps.dependencies._is_npx_package_cached",
                    return_value=True,
                ):
                    assert _precache_npx_mcp_servers(None) is True

    def test_launches_and_kills_uncached_packages(self):
        """Launches npx for uncached pinned packages and kills after caching."""
        import json

        from installer.manifest import get
        from installer.steps.dependencies import _precache_npx_mcp_servers

        pinned_pkg = f"fetcher-mcp@{get('fetcher-mcp').version}"
        mcp_config = {
            "mcpServers": {
                "web-fetch": {"command": "npx", "args": ["-y", pinned_pkg]},
            }
        }

        mock_proc = MagicMock()
        mock_proc.wait = MagicMock(return_value=0)

        with tempfile.TemporaryDirectory() as tmpdir:
            pilot_home = Path(tmpdir) / ".pilot"
            pilot_home.mkdir(parents=True)
            (pilot_home / ".mcp.json").write_text(json.dumps(mcp_config))

            with patch.object(Path, "home", return_value=Path(tmpdir)):
                with patch(
                    "installer.steps.dependencies._is_npx_package_cached",
                    return_value=False,
                ):
                    with patch("installer.steps.dependencies.subprocess.Popen", return_value=mock_proc) as mock_popen:
                        result = _precache_npx_mcp_servers(None)

            assert result is True
            popen_args = mock_popen.call_args[0][0]
            assert popen_args[:2] == ["npx", "-y"]
            assert "--package" in popen_args
            # The --package value MUST be the pinned form, not bare "fetcher-mcp".
            pkg_idx = popen_args.index("--package") + 1
            assert popen_args[pkg_idx] == pinned_pkg
            assert "-c" in popen_args
            assert "true" in popen_args
            mock_proc.wait.assert_called_once()

    def test_is_npx_package_cached_finds_cached(self):
        """_is_npx_package_cached returns True when package exists in npx cache."""
        from installer.steps.dependencies import _is_npx_package_cached

        with tempfile.TemporaryDirectory() as tmpdir:
            npx_cache = Path(tmpdir) / ".npm" / "_npx" / "abc123" / "node_modules" / "fetcher-mcp"
            npx_cache.mkdir(parents=True)

            with patch.object(Path, "home", return_value=Path(tmpdir)):
                assert _is_npx_package_cached("fetcher-mcp") is True

    def test_is_npx_package_cached_returns_false_when_missing(self):
        """_is_npx_package_cached returns False when package not in cache."""
        from installer.steps.dependencies import _is_npx_package_cached

        with tempfile.TemporaryDirectory() as tmpdir:
            npx_cache = Path(tmpdir) / ".npm" / "_npx"
            npx_cache.mkdir(parents=True)

            with patch.object(Path, "home", return_value=Path(tmpdir)):
                assert _is_npx_package_cached("fetcher-mcp") is False

    def test_is_npx_package_cached_handles_scoped_packages(self):
        """_is_npx_package_cached handles @scope/package names."""
        from installer.steps.dependencies import _is_npx_package_cached

        with tempfile.TemporaryDirectory() as tmpdir:
            npx_cache = Path(tmpdir) / ".npm" / "_npx" / "abc123" / "node_modules" / "@upstash" / "context7-mcp"
            npx_cache.mkdir(parents=True)

            with patch.object(Path, "home", return_value=Path(tmpdir)):
                assert _is_npx_package_cached("@upstash/context7-mcp") is True

    def test_is_npx_package_cached_strips_version_tag(self):
        """_is_npx_package_cached strips @latest/@version from package names."""
        from installer.steps.dependencies import _is_npx_package_cached

        with tempfile.TemporaryDirectory() as tmpdir:
            npx_cache = Path(tmpdir) / ".npm" / "_npx" / "abc123" / "node_modules" / "open-websearch"
            npx_cache.mkdir(parents=True)

            with patch.object(Path, "home", return_value=Path(tmpdir)):
                assert _is_npx_package_cached("open-websearch@latest") is True

    def test_extract_npx_package_name(self):
        """_extract_npx_package_name strips version/tag suffixes correctly."""
        from installer.steps.dependencies import _extract_npx_package_name

        assert _extract_npx_package_name("fetcher-mcp") == "fetcher-mcp"
        assert _extract_npx_package_name("open-websearch@latest") == "open-websearch"
        assert _extract_npx_package_name("@upstash/context7-mcp") == "@upstash/context7-mcp"
        assert _extract_npx_package_name("@scope/pkg@1.0.0") == "@scope/pkg"

    def test_fix_npx_peer_dependencies_installs_zod(self):
        """_fix_npx_peer_dependencies installs manifest-pinned zod with --ignore-scripts."""
        from installer.manifest import get
        from installer.steps.dependencies import _fix_npx_peer_dependencies

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / ".npm" / "_npx" / "abc123" / "node_modules" / "open-websearch"
            cache_dir.mkdir(parents=True)

            with patch.object(Path, "home", return_value=Path(tmpdir)):
                with patch("installer.steps.dependencies.subprocess.run") as mock_run:
                    _fix_npx_peer_dependencies()

            mock_run.assert_called_once()
            assert mock_run.call_args[0][0] == [
                "npm",
                "install",
                "--ignore-scripts",
                f"zod@{get('zod').version}",
            ]

    def test_fix_npx_peer_dependencies_skips_when_zod_present(self):
        """_fix_npx_peer_dependencies skips when zod is already installed."""
        from installer.steps.dependencies import _fix_npx_peer_dependencies

        with tempfile.TemporaryDirectory() as tmpdir:
            hash_dir = Path(tmpdir) / ".npm" / "_npx" / "abc123" / "node_modules"
            (hash_dir / "open-websearch").mkdir(parents=True)
            (hash_dir / "zod").mkdir(parents=True)

            with patch.object(Path, "home", return_value=Path(tmpdir)):
                with patch("installer.steps.dependencies.subprocess.run") as mock_run:
                    _fix_npx_peer_dependencies()

            mock_run.assert_not_called()


class TestInstallPrettier:
    """Test prettier global installation."""

    def test_install_prettier_exists(self):
        """install_prettier function exists."""
        from installer.steps.dependencies import install_prettier

        assert callable(install_prettier)

    @patch("installer.steps.dependencies._run_bash_with_retry", return_value=True)
    @patch("installer.steps.dependencies.command_exists", return_value=True)
    def test_install_prettier_upgrades_when_already_installed(self, _mock_cmd, mock_run):
        """install_prettier always runs npm install to upgrade to manifest version."""
        from installer.steps.dependencies import install_prettier

        result = install_prettier()

        assert result is True
        mock_run.assert_called_once()

    @patch("installer.steps.dependencies._run_bash_with_retry", return_value=True)
    @patch("installer.steps.dependencies.command_exists", return_value=False)
    def test_install_prettier_installs_via_npm(self, _mock_cmd, mock_run):
        """install_prettier pins manifest version + --ignore-scripts."""
        from installer.manifest import get
        from installer.steps.dependencies import install_prettier

        result = install_prettier()

        assert result is True
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert f"prettier@{get('prettier').version}" in cmd
        assert "npm install -g" in cmd
        assert "--ignore-scripts" in cmd

    @patch("installer.steps.dependencies._run_bash_with_retry", return_value=False)
    @patch("installer.steps.dependencies.command_exists", return_value=False)
    def test_install_prettier_returns_false_on_failure(self, _mock_cmd, mock_run):
        """install_prettier returns False when npm install fails."""
        from installer.steps.dependencies import install_prettier

        result = install_prettier()

        assert result is False


class TestInstallGolangciLint:
    """Test golangci-lint installation."""

    def test_install_golangci_lint_exists(self):
        """install_golangci_lint function exists."""
        from installer.steps.dependencies import install_golangci_lint

        assert callable(install_golangci_lint)

    @patch("installer.steps.dependencies._curl_pipe_from_manifest", return_value=True)
    @patch("installer.steps.dependencies.subprocess.run")
    @patch("installer.steps.dependencies.command_exists", return_value=True)
    def test_install_golangci_lint_upgrades_when_already_installed(self, _mock_cmd, mock_subproc, mock_curl):
        """install_golangci_lint always runs installer to upgrade to manifest version."""
        from installer.steps.dependencies import install_golangci_lint

        mock_subproc.return_value = MagicMock(returncode=0, stdout="/go")
        result = install_golangci_lint()

        assert result is True
        mock_curl.assert_called_once()

    @patch("installer.steps.dependencies._install_go_via_apt", return_value=False)
    @patch("installer.steps.dependencies.command_exists", return_value=False)
    def test_install_golangci_lint_fails_without_go_and_no_apt(self, mock_cmd, mock_apt):
        """install_golangci_lint returns False when go missing and apt install fails."""
        from installer.steps.dependencies import install_golangci_lint

        result = install_golangci_lint()

        assert result is False
        mock_apt.assert_called_once()

    @patch("installer.steps.dependencies.subprocess.run")
    @patch("installer.steps.dependencies._curl_pipe_from_manifest", return_value=True)
    @patch("installer.steps.dependencies._install_go_via_apt", return_value=True)
    @patch("installer.steps.dependencies.command_exists")
    def test_install_golangci_lint_installs_go_via_apt_then_lint(self, mock_cmd, mock_apt, mock_helper, mock_sub):
        """install_golangci_lint resolves GOPATH and runs manifest-pinned curl helper."""
        from installer.steps.dependencies import install_golangci_lint

        mock_cmd.side_effect = lambda cmd: False
        mock_sub.return_value = MagicMock(returncode=0, stdout="/home/runner/go\n")

        result = install_golangci_lint()

        assert result is True
        mock_apt.assert_called_once()
        mock_helper.assert_called_once()
        assert mock_helper.call_args[0][0] == "golangci-lint-installer"
        opts = mock_helper.call_args[0][1]
        assert opts.interpreter == "sh"
        # GOPATH resolved to a concrete path, NOT the literal `$(go env GOPATH)`.
        assert "-b" in opts.script_args
        assert "/home/runner/go/bin" in opts.script_args
        assert not any("$(" in arg for arg in opts.script_args), (
            "script_args must not contain shell substitutions — the helper "
            "shell-quotes each arg, so the substitution would be literalized."
        )

    @patch("installer.steps.dependencies.subprocess.run")
    @patch("installer.steps.dependencies.command_exists", side_effect=lambda cmd: cmd == "go")
    @patch("installer.steps.dependencies._is_golangci_lint_installed", return_value=False)
    def test_install_golangci_lint_uses_official_script(self, mock_check, mock_cmd, mock_sub):
        """install_golangci_lint routes through manifest-pinned curl helper with concrete GOPATH."""
        from installer.steps.dependencies import install_golangci_lint

        mock_sub.return_value = MagicMock(returncode=0, stdout="/Users/runner/go\n")
        with patch("installer.steps.dependencies._curl_pipe_from_manifest", return_value=True) as mock_helper:
            result = install_golangci_lint()

        assert result is True
        mock_helper.assert_called_once()
        assert mock_helper.call_args[0][0] == "golangci-lint-installer"
        opts = mock_helper.call_args[0][1]
        assert "/Users/runner/go/bin" in opts.script_args

    @patch("installer.steps.dependencies._curl_pipe_from_manifest", return_value=False)
    @patch("installer.steps.dependencies.command_exists", side_effect=lambda cmd: cmd == "go")
    @patch("installer.steps.dependencies._is_golangci_lint_installed", return_value=False)
    def test_install_golangci_lint_returns_false_on_failure(self, mock_check, mock_cmd, mock_helper):
        """install_golangci_lint returns False when manifest-pinned install fails."""
        from installer.steps.dependencies import install_golangci_lint

        result = install_golangci_lint()

        assert result is False


class TestInstallPbtTools:
    """Tests for install_pbt_tools() — property-based testing packages."""

    @patch("installer.steps.dependencies.subprocess.run")
    @patch("installer.steps.dependencies._run_bash_with_retry", return_value=True)
    @patch("installer.steps.dependencies.command_exists", return_value=False)
    def test_install_pbt_tools_installs_both_when_missing(self, _mock_cmd, mock_run, mock_sub):
        """install_pbt_tools installs hypothesis and pinned fast-check with --ignore-scripts."""
        from installer.manifest import get
        from installer.steps.dependencies import install_pbt_tools

        mock_sub.return_value = MagicMock(returncode=1, stdout="")
        install_pbt_tools()

        calls = [str(c) for c in mock_run.call_args_list]
        assert any("hypothesis" in c for c in calls)
        fast_check_cmds = [c for c in calls if "fast-check" in c]
        assert fast_check_cmds, "fast-check install command missing"
        assert all(f"fast-check@{get('fast-check').version}" in c for c in fast_check_cmds)
        assert all("--ignore-scripts" in c for c in fast_check_cmds)

    @patch("installer.steps.dependencies.subprocess.run")
    @patch("installer.steps.dependencies._run_bash_with_retry", return_value=True)
    @patch("installer.steps.dependencies.command_exists", return_value=False)
    def test_install_pbt_tools_uses_longer_timeouts(self, _mock_cmd, mock_run, mock_sub):
        """Hypothesis and fast-check installs use timeouts sized for package downloads."""
        from installer.steps.dependencies import (
            GLOBAL_NPM_INSTALL_TIMEOUT,
            UV_TOOL_INSTALL_TIMEOUT,
            install_pbt_tools,
        )

        mock_sub.return_value = MagicMock(returncode=1, stdout="")

        result = install_pbt_tools()

        assert result is True
        timeouts = [call.kwargs["timeout"] for call in mock_run.call_args_list]
        assert UV_TOOL_INSTALL_TIMEOUT in timeouts
        assert GLOBAL_NPM_INSTALL_TIMEOUT in timeouts

    @patch("installer.steps.dependencies._run_bash_with_retry", return_value=True)
    @patch("installer.steps.dependencies.command_exists", return_value=True)
    def test_install_pbt_tools_upgrades_even_when_commands_exist(self, _mock_cmd, mock_run):
        """install_pbt_tools always runs upgrades to honor the installer contract."""
        from installer.steps.dependencies import install_pbt_tools

        result = install_pbt_tools()

        assert result is True
        calls = [str(c) for c in mock_run.call_args_list]
        assert any("hypothesis" in c for c in calls)
        assert any("fast-check" in c for c in calls)

    @patch("installer.steps.dependencies.subprocess.run")
    @patch("installer.steps.dependencies._run_bash_with_retry", return_value=False)
    @patch("installer.steps.dependencies.command_exists", return_value=False)
    def test_install_pbt_tools_returns_false_on_install_failure(self, _mock_cmd, _mock_run, mock_sub):
        """install_pbt_tools returns False when installations fail."""
        from installer.steps.dependencies import install_pbt_tools

        mock_sub.return_value = MagicMock(returncode=1, stdout="")
        result = install_pbt_tools()

        assert result is False


class TestRemoveLegacyContextMode:
    """Tests for remove_legacy_context_mode() — cleanup of the deprecated plugin."""

    def test_remove_legacy_context_mode_exists(self):
        from installer.steps.dependencies import remove_legacy_context_mode

        assert callable(remove_legacy_context_mode)

    @patch("installer.steps.dependencies.command_exists", return_value=False)
    def test_returns_true_when_claude_not_installed(self, _mock_cmd):
        """No-op when claude CLI is unavailable — cleanup cannot run, but the step succeeds."""
        from installer.steps.dependencies import remove_legacy_context_mode

        assert remove_legacy_context_mode() is True

    @patch("installer.steps.dependencies._legacy_context_mode_remove_orphan_hook")
    @patch("installer.steps.dependencies.subprocess.run")
    @patch("installer.steps.dependencies.command_exists", return_value=True)
    def test_uninstalls_plugin_and_removes_marketplace_when_present(self, _mock_cmd, mock_sub, _mock_orphan):
        """Plugin uninstall + marketplace remove are both invoked when both are present."""
        from installer.steps.dependencies import remove_legacy_context_mode

        plugin_list = json.dumps([{"id": "context-mode@context-mode", "version": "1.0.146"}])
        market_list = json.dumps([{"name": "context-mode", "source": "github"}])
        mock_sub.side_effect = [
            MagicMock(returncode=0, stdout=plugin_list, stderr=""),
            MagicMock(returncode=0, stdout="", stderr=""),
            MagicMock(returncode=0, stdout=market_list, stderr=""),
            MagicMock(returncode=0, stdout="", stderr=""),
        ]

        assert remove_legacy_context_mode() is True
        called_args = [c[0][0] for c in mock_sub.call_args_list]
        assert ["claude", "plugins", "list", "--json"] in called_args
        assert ["claude", "plugins", "uninstall", "context-mode@context-mode", "-y"] in called_args
        assert ["claude", "plugins", "marketplace", "list", "--json"] in called_args
        assert ["claude", "plugins", "marketplace", "remove", "context-mode"] in called_args

    @patch("installer.steps.dependencies._legacy_context_mode_remove_orphan_hook")
    @patch("installer.steps.dependencies.subprocess.run")
    @patch("installer.steps.dependencies.command_exists", return_value=True)
    def test_skips_uninstall_when_plugin_not_installed(self, _mock_cmd, mock_sub, _mock_orphan):
        """Pre-check via `plugin list --json` skips the uninstall command when nothing matches."""
        from installer.steps.dependencies import remove_legacy_context_mode

        mock_sub.side_effect = [
            MagicMock(returncode=0, stdout="[]", stderr=""),
            MagicMock(returncode=0, stdout="[]", stderr=""),
        ]

        assert remove_legacy_context_mode() is True
        called_args = [c[0][0] for c in mock_sub.call_args_list]
        assert not any(args[:3] == ["claude", "plugins", "uninstall"] for args in called_args)
        assert not any(args[:4] == ["claude", "plugins", "marketplace", "remove"] for args in called_args)

    @patch("installer.steps.dependencies._legacy_context_mode_remove_orphan_hook")
    @patch("installer.steps.dependencies.subprocess.run")
    @patch("installer.steps.dependencies.command_exists", return_value=True)
    def test_handles_plugin_list_timeout(self, _mock_cmd, mock_sub, _mock_orphan):
        """A timeout on `plugin list` must not crash — return True and continue."""
        from installer.steps.dependencies import remove_legacy_context_mode

        mock_sub.side_effect = [
            subprocess.TimeoutExpired("claude", 30),
            MagicMock(returncode=0, stdout="[]", stderr=""),
        ]

        assert remove_legacy_context_mode() is True

    @patch("installer.steps.dependencies._legacy_context_mode_remove_orphan_hook")
    @patch("installer.steps.dependencies.subprocess.run")
    @patch("installer.steps.dependencies.command_exists", return_value=True)
    def test_handles_malformed_plugin_list_json(self, _mock_cmd, mock_sub, _mock_orphan):
        """Malformed JSON from `plugin list` must not crash."""
        from installer.steps.dependencies import remove_legacy_context_mode

        mock_sub.side_effect = [
            MagicMock(returncode=0, stdout="not-json", stderr=""),
            MagicMock(returncode=0, stdout="[]", stderr=""),
        ]

        assert remove_legacy_context_mode() is True

    def test_removes_orphan_hook_file_and_settings_entry(self, tmp_path, monkeypatch):
        """The orphan ~/.claude/hooks/context-mode-cache-heal.mjs and any matching
        SessionStart hook entry in ~/.claude/settings.json are both removed."""
        from installer.steps.dependencies import _legacy_context_mode_remove_orphan_hook

        fake_home = tmp_path
        monkeypatch.setattr(Path, "home", lambda: fake_home)
        hooks_dir = fake_home / ".claude" / "hooks"
        hooks_dir.mkdir(parents=True)
        orphan = hooks_dir / "context-mode-cache-heal.mjs"
        orphan.write_text("// orphan\n")

        settings_path = fake_home / ".claude" / "settings.json"
        settings_path.write_text(
            json.dumps(
                {
                    "hooks": {
                        "SessionStart": [
                            {"hooks": [{"type": "command", "command": str(orphan)}]},
                            {
                                "matcher": "startup",
                                "hooks": [
                                    {"type": "command", "command": "echo keep"},
                                    {"type": "command", "command": str(orphan)},
                                ],
                            },
                        ]
                    }
                }
            )
        )

        _legacy_context_mode_remove_orphan_hook()

        assert not orphan.exists(), "Orphan hook script must be deleted."
        data = json.loads(settings_path.read_text())
        entries = data["hooks"]["SessionStart"]
        # First entry only referenced the orphan and is dropped; second is kept with one hook.
        assert len(entries) == 1
        assert entries[0]["matcher"] == "startup"
        assert entries[0]["hooks"] == [{"type": "command", "command": "echo keep"}]

    def test_orphan_hook_cleanup_no_op_when_nothing_present(self, tmp_path, monkeypatch):
        """No crash when the hook file and settings.json are absent."""
        from installer.steps.dependencies import _legacy_context_mode_remove_orphan_hook

        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        _legacy_context_mode_remove_orphan_hook()


class TestInstallChromeDevToolsPlugin:
    """Tests for install_chrome_devtools_plugin() — Claude CLI plugin system."""

    def test_install_chrome_devtools_plugin_exists(self):
        """install_chrome_devtools_plugin function exists and is callable."""
        from installer.steps.dependencies import install_chrome_devtools_plugin

        assert callable(install_chrome_devtools_plugin)

    @patch("installer.steps.dependencies.command_exists", return_value=False)
    def test_returns_false_when_claude_not_installed(self, _mock_cmd):
        """Returns False immediately when claude CLI is not available."""
        from installer.steps.dependencies import install_chrome_devtools_plugin

        result = install_chrome_devtools_plugin()
        assert result is False

    @patch("installer.steps.dependencies._run_bash_with_retry", return_value=True)
    @patch("installer.steps.dependencies.subprocess.run")
    @patch("installer.steps.dependencies.command_exists", return_value=True)
    def test_updates_when_already_installed(self, _mock_cmd, mock_sub, mock_bash):
        """Runs 'claude plugins update' then enable when plugin is already installed."""
        from installer.steps.dependencies import install_chrome_devtools_plugin

        mock_sub.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps([{"id": "chrome-devtools-mcp@chrome-devtools-plugins", "version": "1.0.0"}]),
        )

        result = install_chrome_devtools_plugin()

        assert result is True
        assert mock_bash.call_count == 2
        calls = [c[0][0] for c in mock_bash.call_args_list]
        assert any("marketplace update chrome-devtools-mcp" in c for c in calls)
        assert any("plugins update chrome-devtools-mcp@chrome-devtools-plugins" in c for c in calls)
        sub_calls = [c[0][0] for c in mock_sub.call_args_list]
        assert any(
            ["claude", "plugins", "enable", "chrome-devtools-mcp@chrome-devtools-plugins"] == args for args in sub_calls
        )

    @patch("installer.steps.dependencies._run_bash_with_retry", return_value=True)
    @patch("installer.steps.dependencies.subprocess.run")
    @patch("installer.steps.dependencies.command_exists", return_value=True)
    def test_fresh_install_adds_marketplace_then_installs(self, _mock_cmd, mock_sub, mock_bash):
        """Adds marketplace, installs plugin, then enables it when not already installed."""
        from installer.steps.dependencies import install_chrome_devtools_plugin

        mock_sub.return_value = MagicMock(returncode=0, stdout="[]")

        result = install_chrome_devtools_plugin()

        assert result is True
        assert mock_bash.call_count == 2
        assert "marketplace add" in mock_bash.call_args_list[0][0][0]
        assert "plugins install" in mock_bash.call_args_list[1][0][0]
        sub_calls = [c[0][0] for c in mock_sub.call_args_list]
        assert any(
            ["claude", "plugins", "enable", "chrome-devtools-mcp@chrome-devtools-plugins"] == args for args in sub_calls
        )

    @patch("installer.steps.dependencies._run_bash_with_retry")
    @patch("installer.steps.dependencies.subprocess.run")
    @patch("installer.steps.dependencies.command_exists", return_value=True)
    def test_fresh_install_fails_if_marketplace_add_fails(self, _mock_cmd, mock_sub, mock_bash):
        """Returns False when marketplace add fails."""
        from installer.steps.dependencies import install_chrome_devtools_plugin

        mock_sub.return_value = MagicMock(returncode=0, stdout="[]")
        mock_bash.return_value = False

        result = install_chrome_devtools_plugin()

        assert result is False
        mock_bash.assert_called_once()
        assert "marketplace add" in mock_bash.call_args[0][0]

    @patch("installer.steps.dependencies._run_bash_with_retry", return_value=True)
    @patch("installer.steps.dependencies.subprocess.run")
    @patch("installer.steps.dependencies.command_exists", return_value=True)
    def test_dict_shaped_plugins_list_does_not_crash(self, _mock_cmd, mock_sub, mock_bash):
        """Regression for C18: a future Claude CLI returning a dict (e.g.
        `{"plugins": [...]}`) instead of a bare list must NOT crash the
        installer with an uncaught AttributeError. The plugin should fall
        through to fresh-install (or no-op cleanly), not abort the run."""
        from installer.steps.dependencies import install_chrome_devtools_plugin

        # Dict shape — iterating yields keys (strings); 'plugins'.get('id')
        # would raise AttributeError under the buggy parser.
        mock_sub.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps({"plugins": [{"id": "chrome-devtools-mcp@chrome-devtools-plugins", "version": "1.0.0"}]}),
        )

        # Must not raise. Result may vary — what matters is no crash.
        result = install_chrome_devtools_plugin()
        # And the fresh-install path runs (marketplace add → install) since
        # the dict shape isn't iterable as a list of plugin dicts.
        assert result is True
        calls = [c[0][0] for c in mock_bash.call_args_list]
        assert any("marketplace add" in c for c in calls)
        assert any("plugins install" in c for c in calls)

    @patch("installer.steps.dependencies._run_bash_with_retry", return_value=True)
    @patch("installer.steps.dependencies.subprocess.run")
    @patch("installer.steps.dependencies.command_exists", return_value=True)
    def test_garbage_plugins_list_payload_does_not_crash(self, _mock_cmd, mock_sub, mock_bash):
        """Sanity for the broadened except: a non-JSON-but-stringy payload, a
        list of strings, or any other unexpected shape must be tolerated."""
        from installer.steps.dependencies import install_chrome_devtools_plugin

        # List of strings — `p.get(...)` would raise AttributeError.
        mock_sub.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps(["chrome-devtools-mcp@chrome-devtools-plugins"]),
        )
        result = install_chrome_devtools_plugin()
        assert result is True


class TestRunBashWithRetrySudoFallback:
    """Test sudo -n to sudo fallback in _run_bash_with_retry."""

    @patch("installer.steps.dependencies.subprocess.run")
    def test_sudo_fallback_raises_reauth_exception(self, mock_run):
        """When sudo -n fails with permission error, raises _SudoReauthNeeded."""
        import installer.steps.dependencies as deps
        from installer.steps.dependencies import _SudoReauthNeeded, _run_bash_with_retry

        deps._allow_sudo_fallback = True
        try:
            mock_run.side_effect = subprocess.CalledProcessError(1, "cmd", stderr=b"sudo: a password is required")
            with pytest.raises(_SudoReauthNeeded):
                _run_bash_with_retry("sudo -n npm install -g some-pkg")
        finally:
            deps._allow_sudo_fallback = False

    @patch("installer.steps.dependencies.subprocess.run")
    def test_no_sudo_fallback_when_disabled(self, mock_run):
        """When sudo fallback is disabled, sudo -n failure does not retry with sudo."""
        import installer.steps.dependencies as deps
        from installer.steps.dependencies import _run_bash_with_retry

        deps._allow_sudo_fallback = False
        mock_run.side_effect = subprocess.CalledProcessError(1, "cmd", stderr=b"sudo: a password is required")
        result = _run_bash_with_retry("sudo -n npm install -g some-pkg")
        assert result is False
        # All 3 retries should keep sudo -n
        for call in mock_run.call_args_list:
            assert "sudo -n" in " ".join(call[0][0])

    @patch("installer.steps.dependencies.subprocess.run")
    def test_no_sudo_fallback_for_non_sudo_errors(self, mock_run):
        """Regular errors (not sudo-related) don't trigger sudo fallback."""
        import installer.steps.dependencies as deps
        from installer.steps.dependencies import _run_bash_with_retry

        deps._allow_sudo_fallback = True
        try:
            mock_run.side_effect = subprocess.CalledProcessError(1, "cmd", stderr=b"npm ERR! code ENOENT")
            result = _run_bash_with_retry("sudo -n npm install -g some-pkg")
            assert result is False
            # All retries should keep sudo -n (no fallback for non-sudo errors)
            for call in mock_run.call_args_list:
                assert "sudo -n" in " ".join(call[0][0])
        finally:
            deps._allow_sudo_fallback = False


class TestErrorCapture:
    """Test error detail capture and display in _install_with_spinner."""

    @patch("installer.steps.dependencies.subprocess.run")
    def test_last_error_captured_on_failure(self, mock_run):
        """_run_bash_with_retry captures stderr from failed commands."""
        import installer.steps.dependencies as deps
        from installer.steps.dependencies import _run_bash_with_retry

        deps._thread_local.last_retry_stderr = ""
        mock_run.side_effect = subprocess.CalledProcessError(
            1, "cmd", stderr=b"npm ERR! code EACCES\nnpm ERR! permission denied"
        )
        _run_bash_with_retry("npm install -g foo")
        assert "permission denied" in deps._get_last_error()

    def test_install_with_spinner_shows_error_detail(self):
        """_install_with_spinner shows last error line when install fails."""
        import installer.steps.dependencies as deps
        from installer.steps.dependencies import _install_with_spinner

        ui = MagicMock()
        deps._thread_local.last_retry_stderr = ""

        def failing_install():
            deps._thread_local.last_retry_stderr = "npm ERR! code EACCES\nnpm ERR! permission denied /usr/lib"
            return False

        _install_with_spinner(ui, "TestPkg", failing_install)
        ui.warning.assert_called_once()
        assert "TestPkg" in ui.warning.call_args[0][0]
        ui.info.assert_called_once()
        assert "permission denied" in ui.info.call_args[0][0]

    def test_install_with_spinner_no_error_detail_when_stderr_empty(self):
        """_install_with_spinner shows generic message when no stderr captured."""
        import installer.steps.dependencies as deps
        from installer.steps.dependencies import _install_with_spinner

        ui = MagicMock()
        deps._thread_local.last_retry_stderr = ""

        _install_with_spinner(ui, "TestPkg", lambda: False)
        ui.warning.assert_called_once()
        assert "TestPkg" in ui.warning.call_args[0][0]
        ui.info.assert_not_called()


class TestInstallWithSpinnerSudoReauth:
    """Test _install_with_spinner handling of sudo re-authentication."""

    @patch("installer.steps.dependencies.start_sudo_keepalive")
    @patch("installer.steps.dependencies.ensure_sudo_credentials", return_value=True)
    def test_reauth_succeeds_retries_install(self, mock_ensure, mock_keepalive):
        """When sudo reauth succeeds, retries install outside spinner and succeeds."""
        from installer.steps.dependencies import _SudoReauthNeeded, _install_with_spinner

        ui = MagicMock()
        call_count = 0

        def install_fn():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise _SudoReauthNeeded()
            return True

        result = _install_with_spinner(ui, "TestPkg", install_fn)
        assert result is True
        assert call_count == 2
        mock_ensure.assert_called_once()
        mock_keepalive.assert_called_once()
        ui.status.assert_called_once()
        assert "re-authenticating" in ui.status.call_args[0][0]
        ui.success.assert_called_once()

    @patch("installer.steps.dependencies.ensure_sudo_credentials", return_value=False)
    def test_reauth_fails_reports_error(self, mock_ensure):
        """When sudo reauth fails, reports clear error without hanging."""
        import installer.steps.dependencies as deps
        from installer.steps.dependencies import _SudoReauthNeeded, _install_with_spinner

        ui = MagicMock()

        def install_fn():
            raise _SudoReauthNeeded()

        result = _install_with_spinner(ui, "TestPkg", install_fn)
        assert result is False
        mock_ensure.assert_called_once()
        assert "sudo credentials expired" in deps._get_last_error()
        ui.warning.assert_called_once()

    @patch("installer.steps.dependencies.start_sudo_keepalive")
    @patch("installer.steps.dependencies.ensure_sudo_credentials", return_value=True)
    def test_reauth_succeeds_but_retry_also_fails_does_not_crash(self, mock_ensure, mock_keepalive):
        """When reauth succeeds but retry also raises _SudoReauthNeeded, fails cleanly."""
        import installer.steps.dependencies as deps
        from installer.steps.dependencies import _SudoReauthNeeded, _install_with_spinner

        ui = MagicMock()

        def install_fn():
            raise _SudoReauthNeeded()

        result = _install_with_spinner(ui, "TestPkg", install_fn)
        assert result is False
        assert "sudo credentials expired" in deps._get_last_error()


class TestDependenciesCleanup:
    """Lifecycle cleanup around sudo state."""

    @patch("installer.steps.dependencies.stop_sudo_keepalive")
    @patch("installer.steps.dependencies.start_sudo_keepalive")
    @patch("installer.steps.dependencies.ensure_sudo_credentials", return_value=True)
    @patch("installer.steps.dependencies.needs_sudo", return_value=True)
    @patch("installer.steps.dependencies.install_nodejs", side_effect=RuntimeError("boom"))
    def test_run_resets_sudo_state_on_exception(
        self,
        _mock_install,
        _mock_needs_sudo,
        _mock_ensure,
        mock_start,
        mock_stop,
    ):
        """Dependency step always tears down keepalive and sudo fallback state."""
        import installer.steps.dependencies as deps
        from installer.context import InstallContext
        from installer.steps.dependencies import DependenciesStep
        from installer.ui import Console

        deps._allow_sudo_fallback = False
        step = DependenciesStep()

        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = InstallContext(
                project_dir=Path(tmpdir),
                ui=Console(non_interactive=False),
            )

            with pytest.raises(RuntimeError, match="boom"):
                step.run(ctx)

        mock_start.assert_called_once()
        mock_stop.assert_called_once()
        assert deps._allow_sudo_fallback is False

    @patch("installer.steps.dependencies.stop_sudo_keepalive")
    @patch("installer.steps.dependencies.start_sudo_keepalive")
    @patch("installer.steps.dependencies.ensure_sudo_credentials", side_effect=[True, True])
    @patch("installer.steps.dependencies.needs_sudo", return_value=True)
    @patch("installer.steps.dependencies._precache_npx_mcp_servers", return_value=True)
    @patch("installer.steps.dependencies.install_chrome_devtools_plugin", return_value=True)
    @patch("installer.steps.dependencies.remove_legacy_context_mode", return_value=True)
    @patch("installer.steps.dependencies.initialize_codegraph", return_value=True)
    @patch("installer.steps.dependencies.codegraph_needs_work", return_value=False)
    @patch("installer.steps.dependencies.install_codegraph", return_value=True)
    @patch("installer.steps.dependencies.install_rtk", return_value=True)
    @patch("installer.steps.dependencies.install_ast_grep", return_value=True)
    @patch("installer.steps.dependencies.install_agent_browser", return_value=True)
    @patch("installer.steps.dependencies.install_pbt_tools", return_value=True)
    @patch("installer.steps.dependencies.install_golangci_lint", return_value=True)
    @patch("installer.steps.dependencies.install_prettier", return_value=True)
    @patch("installer.steps.dependencies.install_typescript_lsp", return_value=True)
    @patch("installer.steps.dependencies._install_plugin_dependencies", return_value=True)
    @patch("installer.steps.dependencies._setup_pilot_memory", return_value=True)
    @patch("installer.steps.dependencies.install_python_tools", return_value=True)
    @patch("installer.steps.dependencies.install_uv", return_value=True)
    @patch("installer.steps.dependencies.install_nodejs", return_value=True)
    def test_run_reauths_after_spinner_closes_and_continues(
        self,
        _mock_node,
        _mock_uv,
        _mock_python,
        _mock_memory,
        _mock_plugin_deps,
        _mock_ts_lsp,
        _mock_prettier,
        _mock_golangci,
        _mock_pbt,
        _mock_agent_browser,
        _mock_ast_grep,
        _mock_rtk,
        _mock_codegraph,
        _mock_needs_work,
        _mock_initialize_codegraph,
        _mock_ctx_mode_plugin,
        _mock_chrome_devtools_plugin,
        _mock_precache,
        _mock_needs_sudo,
        mock_ensure,
        mock_start,
        mock_stop,
    ):
        """A sudo expiry during one package install closes the spinner, reauths, and completes."""
        from contextlib import contextmanager

        import installer.steps.dependencies as deps
        from installer.context import InstallContext
        from installer.steps.dependencies import DependenciesStep

        class _FakeProgress:
            def advance(self, amount: int = 1) -> None:
                pass

        class RecordingUI:
            quiet = False

            def __init__(self) -> None:
                self.events: list[tuple[str, str]] = []

            @contextmanager
            def spinner(self, message: str):
                self.events.append(("spinner_start", message))
                try:
                    yield
                finally:
                    self.events.append(("spinner_end", message))

            @contextmanager
            def progress(self, total: int, description: str = "Processing"):
                self.events.append(("progress_start", description))
                try:
                    yield _FakeProgress()
                finally:
                    self.events.append(("progress_end", description))

            def status(self, message: str) -> None:
                self.events.append(("status", message))

            def success(self, message: str) -> None:
                self.events.append(("success", message))

            def warning(self, message: str) -> None:
                self.events.append(("warning", message))

            def info(self, message: str) -> None:
                self.events.append(("info", message))

            def substep(self, name: str) -> None:
                self.events.append(("substep", name))

        ui = RecordingUI()
        step = DependenciesStep()
        deps._allow_sudo_fallback = False

        # Use agent-browser (still sequential) to test sudo reauth flow
        ab_attempts = 0

        def flaky_agent_browser() -> bool:
            nonlocal ab_attempts
            ab_attempts += 1
            if ab_attempts == 1:
                raise deps._SudoReauthNeeded()
            return True

        with patch("installer.steps.dependencies.install_agent_browser", side_effect=flaky_agent_browser):
            with tempfile.TemporaryDirectory() as tmpdir:
                ctx = InstallContext(
                    project_dir=Path(tmpdir),
                    non_interactive=False,
                    ui=ui,  # pyright: ignore[reportArgumentType]  # structural test double
                )
                step.run(ctx)

        assert ab_attempts == 2
        assert mock_ensure.call_count == 2
        assert mock_start.call_count == 2
        mock_stop.assert_called_once()
        assert deps._allow_sudo_fallback is False
        assert "agent_browser" in ctx.config["installed_dependencies"]

        ab_flow = [
            event
            for event in ui.events
            if event[1]
            in {
                "Installing agent-browser (browser automation)...",
                "sudo credentials expired — re-authenticating...",
                "agent-browser (browser automation) installed",
            }
        ]
        assert ab_flow == [
            ("spinner_start", "Installing agent-browser (browser automation)..."),
            ("spinner_end", "Installing agent-browser (browser automation)..."),
            ("status", "sudo credentials expired — re-authenticating..."),
            ("spinner_start", "Installing agent-browser (browser automation)..."),
            ("spinner_end", "Installing agent-browser (browser automation)..."),
            ("success", "agent-browser (browser automation) installed"),
        ]


class TestParallelInstalls:
    """Tests for parallel installation infrastructure."""

    def test_run_install_silent_success(self):
        """_run_install_silent returns success result for passing install."""
        from installer.steps.dependencies import _InstallTask, _run_install_silent

        task = _InstallTask(name="TestPkg", key="test_pkg", fn=lambda: True)
        result = _run_install_silent(task)

        assert result.success is True
        assert result.name == "TestPkg"
        assert result.key == "test_pkg"
        assert result.error == ""

    def test_run_install_silent_failure(self):
        """_run_install_silent captures error on failure."""
        from installer.steps.dependencies import _InstallTask, _run_install_silent

        def failing_fn():
            from installer.steps.dependencies import _thread_local

            _thread_local.last_retry_stderr = "npm ERR! code EACCES"
            return False

        task = _InstallTask(name="FailPkg", key="fail_pkg", fn=failing_fn)
        result = _run_install_silent(task)

        assert result.success is False
        assert "EACCES" in result.error

    def test_run_install_silent_catches_sudo_reauth(self):
        """_run_install_silent catches _SudoReauthNeeded and returns failure."""
        from installer.steps.dependencies import (
            _InstallTask,
            _SudoReauthNeeded,
            _run_install_silent,
        )

        def sudo_fn():
            raise _SudoReauthNeeded()

        task = _InstallTask(name="SudoPkg", key="sudo_pkg", fn=sudo_fn)
        result = _run_install_silent(task)

        assert result.success is False
        assert "sudo credentials expired" in result.error

    def test_run_install_silent_catches_exceptions(self):
        """_run_install_silent catches unexpected exceptions gracefully."""
        from installer.steps.dependencies import _InstallTask, _run_install_silent

        def exploding_fn():
            raise RuntimeError("disk full")

        task = _InstallTask(name="BoomPkg", key="boom_pkg", fn=exploding_fn)
        result = _run_install_silent(task)

        assert result.success is False
        assert "disk full" in result.error

    def test_run_parallel_installs_returns_installed_keys(self):
        """_run_parallel_installs returns keys of successfully installed packages."""
        from installer.steps.dependencies import _InstallTask, _run_parallel_installs

        tasks = [
            _InstallTask(name="Pkg A", key="pkg_a", fn=lambda: True),
            _InstallTask(name="Pkg B", key="pkg_b", fn=lambda: True),
            _InstallTask(name="Pkg C", key="pkg_c", fn=lambda: False),
        ]

        installed = _run_parallel_installs(tasks, ui=None)

        assert "pkg_a" in installed
        assert "pkg_b" in installed
        assert "pkg_c" not in installed

    def test_run_parallel_installs_with_ui_reports_results(self):
        """_run_parallel_installs reports success/failure via UI."""
        from installer.steps.dependencies import _InstallTask, _run_parallel_installs

        class _FakeProgress:
            def advance(self, amount: int = 1) -> None:
                pass

        class FakeUI:
            def __init__(self):
                self.successes = []
                self.warnings = []
                self.infos = []

            @contextmanager
            def progress(self, total, description="Processing"):
                yield _FakeProgress()

            def success(self, msg):
                self.successes.append(msg)

            def warning(self, msg):
                self.warnings.append(msg)

            def info(self, msg):
                self.infos.append(msg)

        ui = FakeUI()
        tasks = [
            _InstallTask(name="Good", key="good", fn=lambda: True),
            _InstallTask(name="Bad", key="bad", fn=lambda: False),
        ]

        installed = _run_parallel_installs(tasks, ui=ui)

        assert "good" in installed
        assert "bad" not in installed
        assert any("Good" in s for s in ui.successes)
        assert any("Bad" in w for w in ui.warnings)

    def test_run_parallel_installs_empty_list(self):
        """_run_parallel_installs handles empty task list."""
        from installer.steps.dependencies import _run_parallel_installs

        installed = _run_parallel_installs([], ui=None)
        assert installed == []

    def test_parallel_installs_are_actually_concurrent(self):
        """Verify parallel installs overlap in time (not sequential)."""
        from installer.steps.dependencies import _InstallTask, _run_parallel_installs

        def slow_fn():
            time.sleep(0.3)
            return True

        tasks = [_InstallTask(name=f"Pkg {i}", key=f"pkg_{i}", fn=slow_fn) for i in range(4)]

        start = time.monotonic()
        installed = _run_parallel_installs(tasks, ui=None, max_workers=4)
        elapsed = time.monotonic() - start

        assert len(installed) == 4
        # 4 tasks x 0.3s each = 1.2s sequential, should be ~0.3s parallel
        assert elapsed < 0.8, f"Expected parallel execution but took {elapsed:.1f}s"

    def test_run_parallel_installs_reports_each_outcome_as_it_completes(self):
        """A fast install's outcome must surface before a slow one finishes.

        Regression: outcomes were buffered until the whole pool drained, so a slow
        or hung package left `pilot update` with only the `[N/M]` header and a
        transient bar until it completed. Outcomes must emit in the as-completed
        loop so the user always sees real-time progress.
        """
        import threading

        from installer.steps.dependencies import (
            _OUTCOME_INSTALLED,
            _InstallTask,
            _record_outcome,
            _run_parallel_installs,
        )

        gate = threading.Event()
        reported: list[str] = []

        class _FakeProgress:
            def advance(self, amount: int = 1) -> None:
                pass

        class FakeUI:
            @contextmanager
            def progress(self, total, description="Processing"):
                yield _FakeProgress()

            def success(self, msg):
                reported.append(msg)

            def warning(self, msg):
                reported.append(msg)

            def info(self, msg):
                reported.append(msg)

        def fast():
            _record_outcome(_OUTCOME_INSTALLED)
            return True

        def slow():
            assert gate.wait(5), "slow task gate never released"
            _record_outcome(_OUTCOME_INSTALLED)
            return True

        tasks = [
            _InstallTask(name="slow-pkg", key="slow", fn=slow),
            _InstallTask(name="fast-pkg", key="fast", fn=fast),
        ]
        holder: dict[str, list[str]] = {}

        def run():
            holder["installed"] = _run_parallel_installs(tasks, ui=FakeUI(), max_workers=2)

        worker = threading.Thread(target=run, daemon=True)
        worker.start()
        try:
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline and not any("fast-pkg" in m for m in reported):
                time.sleep(0.01)
            # fast-pkg must report while slow-pkg is still blocked (not buffered)
            assert any("fast-pkg" in m for m in reported), "fast install was buffered until slow completed"
            assert not any("slow-pkg" in m for m in reported), "slow install reported before it finished"
        finally:
            gate.set()
            worker.join(5)

        assert set(holder["installed"]) == {"fast", "slow"}

    def test_thread_local_error_isolation(self):
        """Thread-local error tracking isolates errors between parallel installs."""
        from installer.steps.dependencies import _InstallTask, _run_install_silent, _thread_local

        def fn_sets_error():
            _thread_local.last_retry_stderr = "error from thread A"
            return False

        def fn_no_error():
            _thread_local.last_retry_stderr = ""
            return True

        task_a = _InstallTask(name="A", key="a", fn=fn_sets_error)
        task_b = _InstallTask(name="B", key="b", fn=fn_no_error)

        result_a = _run_install_silent(task_a)
        result_b = _run_install_silent(task_b)

        assert result_a.success is False
        assert "error from thread A" in result_a.error
        assert result_b.success is True
        assert result_b.error == ""

    def test_install_task_with_args(self):
        """_InstallTask passes args to fn correctly."""
        from installer.steps.dependencies import _InstallTask, _run_install_silent

        def fn_with_args(a, b):
            return a + b == 3

        task = _InstallTask(name="ArgPkg", key="arg", fn=fn_with_args, args=(1, 2))
        result = _run_install_silent(task)

        assert result.success is True


class TestInstallLspPlugins:
    """Tests for install_lsp_plugins() — Piebald-AI/claude-code-lsps marketplace."""

    def test_install_lsp_plugins_exists(self):
        from installer.steps.dependencies import install_lsp_plugins

        assert callable(install_lsp_plugins)

    @patch("installer.steps.dependencies.command_exists", return_value=False)
    def test_returns_false_when_claude_missing(self, _mock_cmd, tmp_path):
        """When claude CLI is missing, returns False and writes no manifest."""
        from installer.steps.dependencies import install_lsp_plugins

        with patch("installer.steps.dependencies.Path.home", return_value=tmp_path):
            result = install_lsp_plugins()

        assert result is False
        assert not (tmp_path / ".pilot" / ".pilot-lsp-plugins.json").exists()

    @patch("installer.steps.dependencies._run_bash_with_retry", return_value=True)
    @patch("installer.steps.dependencies.subprocess.run")
    @patch("installer.steps.dependencies.command_exists", return_value=True)
    def test_fresh_install_writes_manifest_with_all_three(self, _mock_cmd, mock_sub, _mock_bash, tmp_path):
        """Fresh install: all three plugins absent before → all installed → all manifested."""
        from installer.steps.dependencies import install_lsp_plugins

        mock_sub.return_value = MagicMock(returncode=0, stdout="[]")

        with patch("installer.steps.dependencies.Path.home", return_value=tmp_path):
            result = install_lsp_plugins()

        assert result is True
        manifest = json.loads((tmp_path / ".pilot" / ".pilot-lsp-plugins.json").read_text())
        assert set(manifest["plugins"]) == {
            "vtsls@claude-code-lsps",
            "basedpyright@claude-code-lsps",
            "gopls@claude-code-lsps",
        }

    @patch("installer.steps.dependencies._run_bash_with_retry", return_value=True)
    @patch("installer.steps.dependencies.subprocess.run")
    @patch("installer.steps.dependencies.command_exists", return_value=True)
    def test_pre_installed_plugin_not_in_manifest(self, _mock_cmd, mock_sub, _mock_bash, tmp_path):
        """If basedpyright was already installed before Pilot, it's NOT added to manifest."""
        from installer.steps.dependencies import install_lsp_plugins

        # claude plugins list --json returns basedpyright as pre-installed
        mock_sub.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps([{"id": "basedpyright@claude-code-lsps"}]),
        )

        with patch("installer.steps.dependencies.Path.home", return_value=tmp_path):
            result = install_lsp_plugins()

        assert result is True
        manifest = json.loads((tmp_path / ".pilot" / ".pilot-lsp-plugins.json").read_text())
        # basedpyright was pre-installed; only the other two are tracked
        assert "basedpyright@claude-code-lsps" not in manifest["plugins"]
        assert set(manifest["plugins"]) == {
            "vtsls@claude-code-lsps",
            "gopls@claude-code-lsps",
        }

    @patch("installer.steps.dependencies._run_bash_with_retry", return_value=True)
    @patch("installer.steps.dependencies.subprocess.run")
    @patch("installer.steps.dependencies.command_exists", return_value=True)
    def test_reinstall_preserves_pilot_ownership(self, _mock_cmd, mock_sub, _mock_bash, tmp_path):
        """Codex regression: second install must NOT erase Pilot's ownership.

        Pilot installs 3 LSP plugins on first run → manifest lists all 3.
        On a reinstall those same IDs are reported by `claude plugins list`,
        which would naively classify them as user-pre-installed and erase the
        manifest. The fix is to read the prior manifest and union ownership.
        """
        from installer.steps.dependencies import install_lsp_plugins

        # First run — claude plugins list reports no plugins; all three installed fresh.
        mock_sub.return_value = MagicMock(returncode=0, stdout="[]")
        with patch("installer.steps.dependencies.Path.home", return_value=tmp_path):
            assert install_lsp_plugins() is True
            manifest_after_first = json.loads((tmp_path / ".pilot" / ".pilot-lsp-plugins.json").read_text())
        assert set(manifest_after_first["plugins"]) == {
            "vtsls@claude-code-lsps",
            "basedpyright@claude-code-lsps",
            "gopls@claude-code-lsps",
        }

        # Second run — same three IDs now show as pre-installed.
        mock_sub.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps(
                [
                    {"id": "vtsls@claude-code-lsps"},
                    {"id": "basedpyright@claude-code-lsps"},
                    {"id": "gopls@claude-code-lsps"},
                ]
            ),
        )
        with patch("installer.steps.dependencies.Path.home", return_value=tmp_path):
            assert install_lsp_plugins() is True
            manifest_after_second = json.loads((tmp_path / ".pilot" / ".pilot-lsp-plugins.json").read_text())
        # Ownership preserved across reinstall — uninstall.sh can still find and remove these.
        assert set(manifest_after_second["plugins"]) == {
            "vtsls@claude-code-lsps",
            "basedpyright@claude-code-lsps",
            "gopls@claude-code-lsps",
        }

    @patch("installer.steps.dependencies.subprocess.run")
    @patch("installer.steps.dependencies.command_exists", return_value=True)
    def test_one_failure_returns_false_but_others_still_attempted(self, _mock_cmd, mock_sub, tmp_path):
        """If install of vtsls fails, the function still attempts basedpyright + gopls."""
        from installer.steps.dependencies import install_lsp_plugins

        mock_sub.return_value = MagicMock(returncode=0, stdout="[]")

        # _run_bash_with_retry: marketplace-add for vtsls fails; rest succeed.
        # Each successful plugin requires 2 bash calls (add + install). Enable
        # goes through subprocess.run directly (see _ensure_plugin_enabled).
        # Pattern: [add(vtsls)=F, add(bp)=T, install(bp)=T, add(gopls)=T, install(gopls)=T]
        bash_results = [False, True, True, True, True]
        with patch("installer.steps.dependencies._run_bash_with_retry", side_effect=bash_results) as mock_bash:
            with patch("installer.steps.dependencies.Path.home", return_value=tmp_path):
                result = install_lsp_plugins()

        assert result is False  # at least one failed
        # vtsls makes 1 bash call (failed marketplace add),
        # basedpyright + gopls make 2 each (add + install) = 5 total bash calls.
        assert mock_bash.call_count == 5
        bash_commands = [c[0][0] for c in mock_bash.call_args_list]
        # vtsls only got the marketplace-add (which references the marketplace, not plugin name)
        assert "marketplace add Piebald-AI/claude-code-lsps" in bash_commands[0]
        # basedpyright + gopls install commands reference the plugin id
        assert any("basedpyright@claude-code-lsps" in c for c in bash_commands)
        assert any("gopls@claude-code-lsps" in c for c in bash_commands)
        # Manifest reflects successes (basedpyright + gopls), not vtsls
        manifest = json.loads((tmp_path / ".pilot" / ".pilot-lsp-plugins.json").read_text())
        assert "vtsls@claude-code-lsps" not in manifest["plugins"]
        assert "basedpyright@claude-code-lsps" in manifest["plugins"]
        assert "gopls@claude-code-lsps" in manifest["plugins"]


class TestLegacyContextModeHonoursConfigDir:
    """The legacy cleanup deletes a hook file and rewrites settings.json.

    It runs on every install, so a hardcoded ~/.claude would mutate the personal
    profile even when the user installed into a different one.
    """

    def test_operates_on_custom_config_dir_only(self, tmp_path, monkeypatch):
        from installer.steps.dependencies import _legacy_context_mode_remove_orphan_hook

        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        work = tmp_path / ".claude_work"
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(work))

        # Orphan in BOTH profiles; only the work one may be touched.
        for base in (tmp_path / ".claude", work):
            (base / "hooks").mkdir(parents=True)
            (base / "hooks" / "context-mode-cache-heal.mjs").write_text("// orphan\n")
            (base / "settings.json").write_text(
                json.dumps(
                    {
                        "hooks": {
                            "SessionStart": [{"hooks": [{"type": "command", "command": "context-mode-cache-heal.mjs"}]}]
                        }
                    }
                )
            )

        _legacy_context_mode_remove_orphan_hook()

        assert not (work / "hooks" / "context-mode-cache-heal.mjs").exists(), "work profile not cleaned"
        assert (tmp_path / ".claude" / "hooks" / "context-mode-cache-heal.mjs").exists(), (
            "personal profile was modified"
        )

    def test_invalid_config_dir_touches_nothing(self, tmp_path, monkeypatch):
        from installer.steps.dependencies import _legacy_context_mode_remove_orphan_hook

        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", "relative/path")
        hooks_dir = tmp_path / ".claude" / "hooks"
        hooks_dir.mkdir(parents=True)
        orphan = hooks_dir / "context-mode-cache-heal.mjs"
        orphan.write_text("// orphan\n")

        _legacy_context_mode_remove_orphan_hook()

        assert orphan.exists(), "personal profile was modified on an invalid config dir"
