"""Tests for dependencies step."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


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
            # Dependencies always need to be checked
            assert step.check(ctx) is False

    @patch("installer.steps.dependencies.install_vexor")
    @patch("installer.steps.dependencies._install_plugin_dependencies")
    @patch("installer.steps.dependencies._setup_claude_mem")
    @patch("installer.steps.dependencies.install_claude_code")
    @patch("installer.steps.dependencies.install_nodejs")
    def test_dependencies_run_installs_core(
        self,
        mock_nodejs,
        mock_claude,
        mock_setup_claude_mem,
        mock_plugin_deps,
        mock_vexor,
    ):
        """DependenciesStep installs core dependencies."""
        from installer.context import InstallContext
        from installer.steps.dependencies import DependenciesStep
        from installer.ui import Console

        # Setup mocks
        mock_nodejs.return_value = True
        mock_claude.return_value = (True, "latest")  # Returns (success, version)
        mock_setup_claude_mem.return_value = True
        mock_plugin_deps.return_value = True
        mock_vexor.return_value = True

        step = DependenciesStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = InstallContext(
                project_dir=Path(tmpdir),
                enable_python=False,
                ui=Console(non_interactive=True),
            )

            step.run(ctx)

            # Core dependencies should be installed
            mock_nodejs.assert_called_once()
            mock_claude.assert_called_once()
            mock_plugin_deps.assert_called_once()

    @patch("installer.steps.dependencies.install_vexor")
    @patch("installer.steps.dependencies._install_plugin_dependencies")
    @patch("installer.steps.dependencies._setup_claude_mem")
    @patch("installer.steps.dependencies.install_claude_code")
    @patch("installer.steps.dependencies.install_python_tools")
    @patch("installer.steps.dependencies.install_uv")
    @patch("installer.steps.dependencies.install_nodejs")
    def test_dependencies_installs_python_when_enabled(
        self,
        mock_nodejs,
        mock_uv,
        mock_python_tools,
        mock_claude,
        mock_setup_claude_mem,
        mock_plugin_deps,
        mock_vexor,
    ):
        """DependenciesStep installs Python tools when enabled."""
        from installer.context import InstallContext
        from installer.steps.dependencies import DependenciesStep
        from installer.ui import Console

        # Setup mocks
        mock_nodejs.return_value = True
        mock_uv.return_value = True
        mock_python_tools.return_value = True
        mock_claude.return_value = (True, "latest")  # Returns (success, version)
        mock_setup_claude_mem.return_value = True
        mock_plugin_deps.return_value = True
        mock_vexor.return_value = True

        step = DependenciesStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = InstallContext(
                project_dir=Path(tmpdir),
                enable_python=True,
                ui=Console(non_interactive=True),
            )

            step.run(ctx)

            # Python tools should be installed
            mock_uv.assert_called_once()
            mock_python_tools.assert_called_once()


class TestDependencyInstallFunctions:
    """Test individual dependency install functions."""

    def test_install_nodejs_exists(self):
        """install_nodejs function exists."""
        from installer.steps.dependencies import install_nodejs

        assert callable(install_nodejs)

    def test_install_claude_code_exists(self):
        """install_claude_code function exists."""
        from installer.steps.dependencies import install_claude_code

        assert callable(install_claude_code)

    def test_install_uv_exists(self):
        """install_uv function exists."""
        from installer.steps.dependencies import install_uv

        assert callable(install_uv)

    def test_install_python_tools_exists(self):
        """install_python_tools function exists."""
        from installer.steps.dependencies import install_python_tools

        assert callable(install_python_tools)


class TestClaudeCodeInstall:
    """Test Claude Code installation via npm."""

    @patch("installer.steps.dependencies._get_forced_claude_version", return_value=None)
    @patch("installer.steps.dependencies._configure_claude_defaults")
    @patch("installer.steps.dependencies._run_bash_with_retry", return_value=True)
    @patch("installer.steps.dependencies._remove_native_claude_binaries")
    def test_install_claude_code_removes_native_binaries(self, mock_remove, mock_run, mock_config, mock_version):
        """install_claude_code removes native binaries before npm install."""
        from installer.steps.dependencies import install_claude_code

        with tempfile.TemporaryDirectory() as tmpdir:
            install_claude_code(Path(tmpdir))

        mock_remove.assert_called_once()

    @patch("installer.steps.dependencies._get_forced_claude_version", return_value=None)
    @patch("installer.steps.dependencies._configure_claude_defaults")
    @patch("installer.steps.dependencies._run_bash_with_retry", return_value=True)
    @patch("installer.steps.dependencies._remove_native_claude_binaries")
    def test_install_claude_code_uses_npm(self, mock_remove, mock_run, mock_config, mock_version):
        """install_claude_code uses npm install -g."""
        from installer.steps.dependencies import install_claude_code

        with tempfile.TemporaryDirectory() as tmpdir:
            success, version = install_claude_code(Path(tmpdir))

        assert success is True
        assert version == "latest"
        # Verify npm install was called
        mock_run.assert_called()
        # Check that npm install command was used
        call_args = mock_run.call_args[0][0]
        assert "npm install -g @anthropic-ai/claude-code" in call_args

    @patch("installer.steps.dependencies._get_forced_claude_version", return_value="2.1.19")
    @patch("installer.steps.dependencies._configure_claude_defaults")
    @patch("installer.steps.dependencies._run_bash_with_retry", return_value=True)
    @patch("installer.steps.dependencies._remove_native_claude_binaries")
    def test_install_claude_code_uses_version_tag(self, mock_remove, mock_run, mock_config, mock_version):
        """install_claude_code uses npm version tag for pinned version."""
        from installer.steps.dependencies import install_claude_code

        with tempfile.TemporaryDirectory() as tmpdir:
            success, version = install_claude_code(Path(tmpdir))

        assert success is True
        assert version == "2.1.19"
        # Verify npm install with version tag was called
        mock_run.assert_called()
        call_args = mock_run.call_args[0][0]
        assert "npm install -g @anthropic-ai/claude-code@2.1.19" in call_args

    @patch("installer.steps.dependencies._get_forced_claude_version", return_value=None)
    @patch("installer.steps.dependencies._configure_claude_defaults")
    @patch("installer.steps.dependencies._run_bash_with_retry", return_value=True)
    @patch("installer.steps.dependencies._remove_native_claude_binaries")
    def test_install_claude_code_configures_defaults(self, mock_remove, mock_run, mock_config, mock_version):
        """install_claude_code configures Claude defaults after npm install."""
        from installer.steps.dependencies import install_claude_code

        with tempfile.TemporaryDirectory() as tmpdir:
            install_claude_code(Path(tmpdir))

        mock_config.assert_called_once()

    @patch("installer.steps.dependencies._get_forced_claude_version", return_value="2.1.19")
    @patch("installer.steps.dependencies._configure_claude_defaults")
    @patch("installer.steps.dependencies._run_bash_with_retry", return_value=True)
    @patch("installer.steps.dependencies._remove_native_claude_binaries")
    def test_install_claude_code_with_ui_shows_pinned_version_info(
        self, mock_remove, mock_run, mock_config, mock_version
    ):
        """_install_claude_code_with_ui shows info about pinned version."""
        from installer.steps.dependencies import _install_claude_code_with_ui
        from installer.ui import Console

        ui = Console(non_interactive=True)
        # Capture printed output by mocking ui.info
        info_calls = []
        original_info = ui.info
        ui.info = lambda msg: info_calls.append(msg)

        with tempfile.TemporaryDirectory() as tmpdir:
            result = _install_claude_code_with_ui(ui, Path(tmpdir))

        assert result is True
        # Check that pinned version info was displayed
        assert any("last stable release" in call for call in info_calls)
        assert any("FORCE_CLAUDE_VERSION" in call for call in info_calls)

    def test_patch_claude_config_creates_file(self):
        """_patch_claude_config creates config file if it doesn't exist."""
        import json

        from installer.steps.dependencies import _patch_claude_config

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, "home", return_value=Path(tmpdir)):
                result = _patch_claude_config({"test_key": "test_value"})

                assert result is True
                config_path = Path(tmpdir) / ".claude.json"
                assert config_path.exists()
                config = json.loads(config_path.read_text())
                assert config["test_key"] == "test_value"

    def test_patch_claude_config_merges_existing(self):
        """_patch_claude_config merges with existing config."""
        import json

        from installer.steps.dependencies import _patch_claude_config

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".claude.json"
            config_path.write_text(json.dumps({"existing_key": "existing_value"}))

            with patch.object(Path, "home", return_value=Path(tmpdir)):
                result = _patch_claude_config({"new_key": "new_value"})

                assert result is True
                config = json.loads(config_path.read_text())
                assert config["existing_key"] == "existing_value"
                assert config["new_key"] == "new_value"

    def test_configure_claude_defaults_sets_settings(self):
        """_configure_claude_defaults sets settings in settings.json."""
        import json

        from installer.steps.dependencies import _configure_claude_defaults

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, "home", return_value=Path(tmpdir)):
                result = _configure_claude_defaults()

                assert result is True
                # Check settings.json for settings
                settings_path = Path(tmpdir) / ".claude" / "settings.json"
                settings = json.loads(settings_path.read_text())
                assert settings["respectGitignore"] is False
                assert settings["attribution"] == {"commit": "", "pr": ""}
                # Check .claude.json for preferences
                config_path = Path(tmpdir) / ".claude.json"
                config = json.loads(config_path.read_text())
                assert config["theme"] == "dark-ansi"


class TestMigrateLegacyPlugins:
    """Test legacy plugin migration."""

    def test_migrate_legacy_plugins_exists(self):
        """_migrate_legacy_plugins function exists."""
        from installer.steps.dependencies import _migrate_legacy_plugins

        assert callable(_migrate_legacy_plugins)

    @patch("installer.steps.dependencies.subprocess.run")
    def test_migrate_calls_plugin_uninstall(self, mock_run):
        """_migrate_legacy_plugins calls 'claude plugin uninstall' for each legacy plugin."""
        from installer.steps.dependencies import _migrate_legacy_plugins

        mock_run.return_value.returncode = 0

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, "home", return_value=Path(tmpdir)):
                _migrate_legacy_plugins(ui=None)

                # Check that uninstall was called for expected plugins
                expected_plugins = [
                    "context7",
                    "claude-mem",
                    "basedpyright",
                    "typescript-lsp",
                    "vtsls",
                    "gopls",
                    "pyright-lsp",
                    "gopls-lsp",
                ]
                assert mock_run.call_count == len(expected_plugins)

                for call_args in mock_run.call_args_list:
                    args = call_args[0][0]
                    assert args[:3] == ["claude", "plugin", "uninstall"]
                    assert args[3] in expected_plugins

    @patch("installer.steps.dependencies.subprocess.run")
    def test_migrate_removes_cache_directories(self, mock_run):
        """_migrate_legacy_plugins removes cache directories for legacy marketplaces."""
        from installer.steps.dependencies import _migrate_legacy_plugins

        mock_run.return_value.returncode = 0

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, "home", return_value=Path(tmpdir)):
                # Create cache directories
                cache_dir = Path(tmpdir) / ".claude" / "plugins" / "cache"
                for marketplace in ["thedotmack", "customable", "claude-code-lsps"]:
                    (cache_dir / marketplace).mkdir(parents=True)

                _migrate_legacy_plugins(ui=None)

                # Check that cache directories were removed
                assert not (cache_dir / "thedotmack").exists()
                assert not (cache_dir / "customable").exists()
                assert not (cache_dir / "claude-code-lsps").exists()

    @patch("installer.steps.dependencies.subprocess.run")
    def test_migrate_removes_marketplace_directories(self, mock_run):
        """_migrate_legacy_plugins removes marketplace directories."""
        from installer.steps.dependencies import _migrate_legacy_plugins

        mock_run.return_value.returncode = 0

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, "home", return_value=Path(tmpdir)):
                # Create marketplace directories
                marketplaces_dir = Path(tmpdir) / ".claude" / "plugins" / "marketplaces"
                for marketplace in ["thedotmack", "customable"]:
                    (marketplaces_dir / marketplace).mkdir(parents=True)

                _migrate_legacy_plugins(ui=None)

                # Check that directories were removed
                assert not (marketplaces_dir / "thedotmack").exists()
                assert not (marketplaces_dir / "customable").exists()

    @patch("installer.steps.dependencies.subprocess.run")
    def test_migrate_skips_when_nothing_to_migrate(self, mock_run):
        """_migrate_legacy_plugins does nothing when nothing to migrate."""
        from installer.steps.dependencies import _migrate_legacy_plugins

        mock_run.return_value.returncode = 1  # Simulate plugin not found

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, "home", return_value=Path(tmpdir)):
                # No files to migrate - should not raise
                _migrate_legacy_plugins(ui=None)


class TestSetupClaudeMem:
    """Test claude-mem setup (legacy plugin migration)."""

    def test_setup_claude_mem_exists(self):
        """_setup_claude_mem function exists."""
        from installer.steps.dependencies import _setup_claude_mem

        assert callable(_setup_claude_mem)

    @patch("installer.steps.dependencies._migrate_legacy_plugins")
    def test_setup_claude_mem_calls_migration(self, mock_migrate):
        """_setup_claude_mem calls legacy plugin migration."""
        from installer.steps.dependencies import _setup_claude_mem

        result = _setup_claude_mem(ui=None)

        assert result is True
        mock_migrate.assert_called_once()


class TestVexorInstall:
    """Test Vexor semantic search installation."""

    def test_install_vexor_exists(self):
        """install_vexor function exists."""
        from installer.steps.dependencies import install_vexor

        assert callable(install_vexor)

    @patch("installer.steps.dependencies._configure_vexor_defaults")
    @patch("installer.steps.dependencies.command_exists")
    def test_install_vexor_skips_if_exists(self, mock_cmd_exists, mock_config):
        """install_vexor skips installation if already installed."""
        from installer.steps.dependencies import install_vexor

        mock_cmd_exists.return_value = True
        mock_config.return_value = True

        result = install_vexor()

        assert result is True
        mock_config.assert_called_once()

    def test_configure_vexor_defaults_creates_config(self):
        """_configure_vexor_defaults creates config file."""
        import json

        from installer.steps.dependencies import _configure_vexor_defaults

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, "home", return_value=Path(tmpdir)):
                result = _configure_vexor_defaults()

                assert result is True
                config_path = Path(tmpdir) / ".vexor" / "config.json"
                assert config_path.exists()
                config = json.loads(config_path.read_text())
                assert config["model"] == "text-embedding-3-small"
                assert config["provider"] == "openai"
                assert config["rerank"] == "bm25"

    def test_configure_vexor_defaults_merges_existing(self):
        """_configure_vexor_defaults merges with existing config."""
        import json

        from installer.steps.dependencies import _configure_vexor_defaults

        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / ".vexor"
            config_dir.mkdir()
            config_path = config_dir / "config.json"
            config_path.write_text(json.dumps({"custom_key": "custom_value"}))

            with patch.object(Path, "home", return_value=Path(tmpdir)):
                result = _configure_vexor_defaults()

                assert result is True
                config = json.loads(config_path.read_text())
                assert config["custom_key"] == "custom_value"
                assert config["model"] == "text-embedding-3-small"


class TestInstallPluginDependencies:
    """Test plugin dependencies installation via bun/npm install."""

    def test_install_plugin_dependencies_exists(self):
        """_install_plugin_dependencies function exists."""
        from installer.steps.dependencies import _install_plugin_dependencies

        assert callable(_install_plugin_dependencies)

    def test_install_plugin_dependencies_returns_false_if_no_plugin_dir(self):
        """_install_plugin_dependencies returns False if plugin directory doesn't exist."""
        from installer.steps.dependencies import _install_plugin_dependencies

        with tempfile.TemporaryDirectory() as tmpdir:
            result = _install_plugin_dependencies(Path(tmpdir), ui=None)
            assert result is False

    def test_install_plugin_dependencies_returns_false_if_no_package_json(self):
        """_install_plugin_dependencies returns False if no package.json exists."""
        from installer.steps.dependencies import _install_plugin_dependencies

        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_dir = Path(tmpdir) / ".claude" / "ccp"
            plugin_dir.mkdir(parents=True)

            result = _install_plugin_dependencies(Path(tmpdir), ui=None)
            assert result is False

    @patch("installer.steps.dependencies._run_bash_with_retry")
    @patch("installer.steps.dependencies.command_exists")
    def test_install_plugin_dependencies_runs_bun_install(self, mock_cmd_exists, mock_run):
        """_install_plugin_dependencies runs bun install when bun is available."""
        from installer.steps.dependencies import _install_plugin_dependencies

        mock_cmd_exists.side_effect = lambda cmd: cmd == "bun"
        mock_run.return_value = True

        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_dir = Path(tmpdir) / ".claude" / "ccp"
            plugin_dir.mkdir(parents=True)
            (plugin_dir / "package.json").write_text('{"name": "test"}')

            result = _install_plugin_dependencies(Path(tmpdir), ui=None)

            assert result is True
            mock_run.assert_called_with("bun install", cwd=plugin_dir)


class TestCleanMcpServersFromClaudeConfig:
    """Test cleaning mcpServers from ~/.claude.json."""

    def test_clean_mcp_servers_removes_mcp_servers_section(self):
        """_clean_mcp_servers_from_claude_config removes mcpServers from config."""
        import json

        from installer.steps.dependencies import _clean_mcp_servers_from_claude_config

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".claude.json"
            config_path.write_text(
                json.dumps(
                    {
                        "theme": "dark",
                        "mcpServers": {
                            "web-search": {"command": "npx"},
                            "web-fetch": {"command": "npx"},
                        },
                    }
                )
            )

            with patch.object(Path, "home", return_value=Path(tmpdir)):
                _clean_mcp_servers_from_claude_config(ui=None)

                config = json.loads(config_path.read_text())
                assert "mcpServers" not in config
                assert config["theme"] == "dark"

    def test_clean_mcp_servers_preserves_other_config(self):
        """_clean_mcp_servers_from_claude_config preserves non-mcpServers config."""
        import json

        from installer.steps.dependencies import _clean_mcp_servers_from_claude_config

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".claude.json"
            config_path.write_text(
                json.dumps(
                    {
                        "theme": "dark",
                        "verbose": True,
                        "autoUpdates": False,
                        "mcpServers": {"web-search": {}},
                    }
                )
            )

            with patch.object(Path, "home", return_value=Path(tmpdir)):
                _clean_mcp_servers_from_claude_config(ui=None)

                config = json.loads(config_path.read_text())
                assert config["theme"] == "dark"
                assert config["verbose"] is True
                assert config["autoUpdates"] is False

    def test_clean_mcp_servers_handles_missing_file(self):
        """_clean_mcp_servers_from_claude_config handles missing config file."""
        from installer.steps.dependencies import _clean_mcp_servers_from_claude_config

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, "home", return_value=Path(tmpdir)):
                # Should not raise - just return early
                _clean_mcp_servers_from_claude_config(ui=None)

    def test_clean_mcp_servers_handles_no_mcp_servers_key(self):
        """_clean_mcp_servers_from_claude_config handles config without mcpServers."""
        import json

        from installer.steps.dependencies import _clean_mcp_servers_from_claude_config

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".claude.json"
            config_path.write_text(json.dumps({"theme": "dark"}))

            with patch.object(Path, "home", return_value=Path(tmpdir)):
                _clean_mcp_servers_from_claude_config(ui=None)

                # Config should remain unchanged
                config = json.loads(config_path.read_text())
                assert config == {"theme": "dark"}
