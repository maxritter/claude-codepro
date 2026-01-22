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

    @patch("installer.steps.dependencies.run_qlty_check")
    @patch("installer.steps.dependencies.install_qlty")
    @patch("installer.steps.dependencies.install_vexor")
    @patch("installer.steps.dependencies.install_context7")
    @patch("installer.steps.dependencies.install_claude_mem")
    @patch("installer.steps.dependencies.install_typescript_lsp")
    @patch("installer.steps.dependencies.install_claude_code")
    @patch("installer.steps.dependencies.install_nodejs")
    def test_dependencies_run_installs_core(
        self,
        mock_nodejs,
        mock_claude,
        mock_typescript_lsp,
        mock_claude_mem,
        mock_context7,
        mock_vexor,
        mock_qlty,
        mock_qlty_check,
    ):
        """DependenciesStep installs core dependencies."""
        from installer.context import InstallContext
        from installer.steps.dependencies import DependenciesStep
        from installer.ui import Console

        # Setup mocks
        mock_nodejs.return_value = True
        mock_claude.return_value = (True, "latest")  # Returns (success, version)
        mock_typescript_lsp.return_value = True
        mock_claude_mem.return_value = True
        mock_context7.return_value = True
        mock_vexor.return_value = True
        mock_qlty.return_value = (True, False)

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
            mock_typescript_lsp.assert_called_once()
            mock_claude.assert_called_once()

    @patch("installer.steps.dependencies.run_qlty_check")
    @patch("installer.steps.dependencies.install_qlty")
    @patch("installer.steps.dependencies.install_vexor")
    @patch("installer.steps.dependencies.install_context7")
    @patch("installer.steps.dependencies.install_claude_mem")
    @patch("installer.steps.dependencies.install_pyright_lsp")
    @patch("installer.steps.dependencies.install_typescript_lsp")
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
        mock_typescript_lsp,
        mock_pyright_lsp,
        mock_claude_mem,
        mock_context7,
        mock_vexor,
        mock_qlty,
        mock_qlty_check,
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
        mock_typescript_lsp.return_value = True
        mock_pyright_lsp.return_value = True
        mock_claude_mem.return_value = True
        mock_context7.return_value = True
        mock_vexor.return_value = True
        mock_qlty.return_value = (True, False)

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
            mock_pyright_lsp.assert_called_once()


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
    """Test Claude Code installation."""

    @patch("installer.steps.dependencies._download_claude_binary_with_progress", return_value=False)
    @patch("installer.steps.dependencies._get_forced_claude_version", return_value=None)
    @patch("installer.steps.dependencies._configure_firecrawl_mcp")
    @patch("installer.steps.dependencies._configure_claude_defaults")
    @patch("installer.steps.dependencies._run_bash_with_retry", return_value=True)
    @patch("installer.steps.dependencies._remove_npm_claude_binaries")
    def test_install_claude_code_removes_npm_binaries(
        self, mock_remove, mock_run, mock_config, mock_firecrawl, mock_version, mock_download
    ):
        """install_claude_code removes npm binaries before native install."""
        from installer.steps.dependencies import install_claude_code

        with tempfile.TemporaryDirectory() as tmpdir:
            install_claude_code(Path(tmpdir))

        mock_remove.assert_called_once()

    @patch("installer.steps.dependencies._download_claude_binary_with_progress", return_value=False)
    @patch("installer.steps.dependencies._get_forced_claude_version", return_value=None)
    @patch("installer.steps.dependencies._configure_firecrawl_mcp")
    @patch("installer.steps.dependencies._configure_claude_defaults")
    @patch("installer.steps.dependencies._run_bash_with_retry", return_value=True)
    @patch("installer.steps.dependencies._remove_npm_claude_binaries")
    def test_install_claude_code_uses_native_installer(
        self, mock_remove, mock_run, mock_config, mock_firecrawl, mock_version, mock_download
    ):
        """install_claude_code uses native installer from claude.ai."""
        from installer.steps.dependencies import install_claude_code

        with tempfile.TemporaryDirectory() as tmpdir:
            success, version = install_claude_code(Path(tmpdir))

        assert success is True
        assert version == "latest"
        # Verify native installer was called via _run_bash_with_retry
        mock_run.assert_called()

    @patch("installer.steps.dependencies._download_claude_binary_with_progress", return_value=False)
    @patch("installer.steps.dependencies._get_forced_claude_version", return_value=None)
    @patch("installer.steps.dependencies._configure_firecrawl_mcp")
    @patch("installer.steps.dependencies._configure_claude_defaults")
    @patch("installer.steps.dependencies._run_bash_with_retry", return_value=True)
    @patch("installer.steps.dependencies._remove_npm_claude_binaries")
    def test_install_claude_code_configures_defaults(
        self, mock_remove, mock_run, mock_config, mock_firecrawl, mock_version, mock_download
    ):
        """install_claude_code configures Claude defaults after native install."""
        from installer.steps.dependencies import install_claude_code

        with tempfile.TemporaryDirectory() as tmpdir:
            install_claude_code(Path(tmpdir))

        mock_config.assert_called_once()

    @patch("installer.steps.dependencies._download_claude_binary_with_progress", return_value=False)
    @patch("installer.steps.dependencies._get_forced_claude_version", return_value=None)
    @patch("installer.steps.dependencies._configure_firecrawl_mcp")
    @patch("installer.steps.dependencies._configure_claude_defaults")
    @patch("installer.steps.dependencies._run_bash_with_retry", return_value=True)
    @patch("installer.steps.dependencies._remove_npm_claude_binaries")
    def test_install_claude_code_does_not_configure_firecrawl(
        self, mock_remove, mock_run, mock_config, mock_firecrawl, mock_version, mock_download
    ):
        """install_claude_code does not configure Firecrawl (handled by DependenciesStep)."""
        from installer.steps.dependencies import install_claude_code

        with tempfile.TemporaryDirectory() as tmpdir:
            install_claude_code(Path(tmpdir))

        mock_firecrawl.assert_not_called()

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

    def test_configure_claude_defaults_sets_respect_gitignore_false(self):
        """_configure_claude_defaults sets respectGitignore to False."""
        import json

        from installer.steps.dependencies import _configure_claude_defaults

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, "home", return_value=Path(tmpdir)):
                result = _configure_claude_defaults()

                assert result is True
                config_path = Path(tmpdir) / ".claude.json"
                config = json.loads(config_path.read_text())
                assert config["respectGitignore"] is False


class TestFirecrawlMcpConfig:
    """Test Firecrawl MCP server configuration."""

    def test_configure_firecrawl_mcp_creates_config(self):
        """_configure_firecrawl_mcp creates config with mcpServers if not exists."""
        import json

        from installer.steps.dependencies import _configure_firecrawl_mcp

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, "home", return_value=Path(tmpdir)):
                result = _configure_firecrawl_mcp()

                assert result is True
                config_path = Path(tmpdir) / ".claude.json"
                assert config_path.exists()
                config = json.loads(config_path.read_text())
                assert "mcpServers" in config
                assert "firecrawl" in config["mcpServers"]
                assert config["mcpServers"]["firecrawl"]["command"] == "npx"
                assert config["mcpServers"]["firecrawl"]["args"] == ["-y", "firecrawl-mcp"]
                assert config["mcpServers"]["firecrawl"]["env"]["FIRECRAWL_API_KEY"] == "${FIRECRAWL_API_KEY}"

    def test_configure_firecrawl_mcp_preserves_existing_mcp_servers(self):
        """_configure_firecrawl_mcp preserves other MCP servers."""
        import json

        from installer.steps.dependencies import _configure_firecrawl_mcp

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".claude.json"
            existing_config = {"mcpServers": {"other_server": {"command": "other", "args": ["--flag"]}}}
            config_path.write_text(json.dumps(existing_config))

            with patch.object(Path, "home", return_value=Path(tmpdir)):
                result = _configure_firecrawl_mcp()

                assert result is True
                config = json.loads(config_path.read_text())
                assert "other_server" in config["mcpServers"]
                assert config["mcpServers"]["other_server"]["command"] == "other"
                assert "firecrawl" in config["mcpServers"]

    def test_configure_firecrawl_mcp_skips_if_already_exists(self):
        """_configure_firecrawl_mcp skips if firecrawl already configured."""
        import json

        from installer.steps.dependencies import _configure_firecrawl_mcp

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".claude.json"
            existing_config = {"mcpServers": {"firecrawl": {"command": "custom", "args": ["custom"]}}}
            config_path.write_text(json.dumps(existing_config))

            with patch.object(Path, "home", return_value=Path(tmpdir)):
                result = _configure_firecrawl_mcp()

                assert result is True
                config = json.loads(config_path.read_text())
                # Should preserve custom config, not overwrite
                assert config["mcpServers"]["firecrawl"]["command"] == "custom"

    def test_configure_firecrawl_mcp_adds_to_existing_config(self):
        """_configure_firecrawl_mcp adds mcpServers to existing config."""
        import json

        from installer.steps.dependencies import _configure_firecrawl_mcp

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".claude.json"
            existing_config = {"theme": "dark", "verbose": True}
            config_path.write_text(json.dumps(existing_config))

            with patch.object(Path, "home", return_value=Path(tmpdir)):
                result = _configure_firecrawl_mcp()

                assert result is True
                config = json.loads(config_path.read_text())
                assert config["theme"] == "dark"
                assert config["verbose"] is True
                assert "mcpServers" in config
                assert "firecrawl" in config["mcpServers"]


class TestTypescriptLspInstall:
    """Test TypeScript language server plugin installation."""

    def test_install_typescript_lsp_exists(self):
        """install_typescript_lsp function exists."""
        from installer.steps.dependencies import install_typescript_lsp

        assert callable(install_typescript_lsp)

    @patch("installer.steps.dependencies._is_marketplace_installed", return_value=False)
    @patch("installer.steps.dependencies._is_plugin_installed", return_value=False)
    @patch("subprocess.run")
    def test_install_typescript_lsp_calls_npm_and_plugin(self, mock_run, mock_plugin, mock_market):
        """install_typescript_lsp calls npm install and claude plugin install."""
        from installer.steps.dependencies import install_typescript_lsp

        mock_run.return_value = MagicMock(returncode=0)

        result = install_typescript_lsp()

        assert mock_run.call_count >= 2
        # Check npm install call
        first_call = mock_run.call_args_list[0][0][0]
        assert "bash" in first_call
        assert "typescript-language-server" in first_call[2]
        # Check marketplace add call
        second_call = mock_run.call_args_list[1][0][0]
        assert "claude plugin marketplace add anthropics/claude-plugins-official" in second_call[2]
        # Check plugin install call
        third_call = mock_run.call_args_list[2][0][0]
        assert "claude plugin install typescript-lsp" in third_call[2]


class TestPyrightLspInstall:
    """Test Pyright language server plugin installation."""

    def test_install_pyright_lsp_exists(self):
        """install_pyright_lsp function exists."""
        from installer.steps.dependencies import install_pyright_lsp

        assert callable(install_pyright_lsp)

    @patch("installer.steps.dependencies._is_marketplace_installed", return_value=False)
    @patch("installer.steps.dependencies._is_plugin_installed", return_value=False)
    @patch("subprocess.run")
    def test_install_pyright_lsp_calls_npm_and_plugin(self, mock_run, mock_plugin, mock_market):
        """install_pyright_lsp calls npm install and claude plugin install."""
        from installer.steps.dependencies import install_pyright_lsp

        mock_run.return_value = MagicMock(returncode=0)

        result = install_pyright_lsp()

        assert mock_run.call_count >= 3
        # Check npm install call
        first_call = mock_run.call_args_list[0][0][0]
        assert "bash" in first_call
        assert "pyright" in first_call[2]
        # Check marketplace add call
        second_call = mock_run.call_args_list[1][0][0]
        assert "claude plugin marketplace add anthropics/claude-plugins-official" in second_call[2]
        # Check plugin install call
        third_call = mock_run.call_args_list[2][0][0]
        assert "claude plugin install pyright-lsp" in third_call[2]


class TestClaudeMemInstall:
    """Test claude-mem plugin installation."""

    def test_install_claude_mem_exists(self):
        """install_claude_mem function exists."""
        from installer.steps.dependencies import install_claude_mem

        assert callable(install_claude_mem)

    @patch("installer.steps.dependencies._is_plugin_installed", return_value=False)
    @patch("subprocess.run")
    def test_install_claude_mem_uses_plugin_system(self, mock_run, mock_plugin):
        """install_claude_mem uses claude plugin marketplace and install."""
        from installer.steps.dependencies import install_claude_mem

        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, "home", return_value=Path(tmpdir)):
                result = install_claude_mem()

        assert mock_run.call_count >= 2
        # First call adds marketplace
        first_call = mock_run.call_args_list[0][0][0]
        assert "claude plugin marketplace add" in first_call[2]
        assert "maxritter/claude-mem" in first_call[2]
        # Second call installs plugin
        second_call = mock_run.call_args_list[1][0][0]
        assert "claude plugin install claude-mem" in second_call[2]

    @patch("subprocess.run")
    def test_install_claude_mem_succeeds_if_marketplace_already_added(self, mock_run):
        """install_claude_mem succeeds when marketplace already exists."""
        from installer.steps.dependencies import install_claude_mem

        def side_effect(*args, **kwargs):
            cmd = args[0] if args else kwargs.get("args", [])
            if isinstance(cmd, list) and "marketplace add" in cmd[2]:
                return MagicMock(returncode=1, stderr="already installed", stdout="")
            return MagicMock(returncode=0, stdout="", stderr="")

        mock_run.side_effect = side_effect

        result = install_claude_mem()

        assert result is True


class TestClaudeMemDepsPreinstall:
    """Test claude-mem bun dependencies pre-installation."""

    def test_preinstall_claude_mem_deps_exists(self):
        """preinstall_claude_mem_deps function exists."""
        from installer.steps.dependencies import preinstall_claude_mem_deps

        assert callable(preinstall_claude_mem_deps)

    def test_is_claude_mem_deps_installed_exists(self):
        """_is_claude_mem_deps_installed function exists."""
        from installer.steps.dependencies import _is_claude_mem_deps_installed

        assert callable(_is_claude_mem_deps_installed)

    def test_is_claude_mem_deps_installed_returns_false_when_no_node_modules(self):
        """_is_claude_mem_deps_installed returns False when node_modules missing."""
        from installer.steps.dependencies import _is_claude_mem_deps_installed

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, "home", return_value=Path(tmpdir)):
                # Create plugin dir but no node_modules
                plugin_dir = Path(tmpdir) / ".claude" / "plugins" / "marketplaces" / "thedotmack"
                plugin_dir.mkdir(parents=True)

                result = _is_claude_mem_deps_installed()

                assert result is False

    def test_is_claude_mem_deps_installed_returns_false_when_no_marker(self):
        """_is_claude_mem_deps_installed returns False when marker file missing."""
        from installer.steps.dependencies import _is_claude_mem_deps_installed

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, "home", return_value=Path(tmpdir)):
                # Create plugin dir with node_modules but no marker
                plugin_dir = Path(tmpdir) / ".claude" / "plugins" / "marketplaces" / "thedotmack"
                plugin_dir.mkdir(parents=True)
                (plugin_dir / "node_modules").mkdir()

                result = _is_claude_mem_deps_installed()

                assert result is False

    def test_is_claude_mem_deps_installed_returns_true_when_versions_match(self):
        """_is_claude_mem_deps_installed returns True when versions match."""
        import json

        from installer.steps.dependencies import _is_claude_mem_deps_installed

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, "home", return_value=Path(tmpdir)):
                plugin_dir = Path(tmpdir) / ".claude" / "plugins" / "marketplaces" / "thedotmack"
                plugin_dir.mkdir(parents=True)
                (plugin_dir / "node_modules").mkdir()

                # Create package.json and marker with matching versions
                (plugin_dir / "package.json").write_text(json.dumps({"version": "1.0.0"}))
                (plugin_dir / ".install-version").write_text(json.dumps({"version": "1.0.0"}))

                result = _is_claude_mem_deps_installed()

                assert result is True

    def test_is_claude_mem_deps_installed_returns_false_when_versions_mismatch(self):
        """_is_claude_mem_deps_installed returns False when versions don't match."""
        import json

        from installer.steps.dependencies import _is_claude_mem_deps_installed

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, "home", return_value=Path(tmpdir)):
                plugin_dir = Path(tmpdir) / ".claude" / "plugins" / "marketplaces" / "thedotmack"
                plugin_dir.mkdir(parents=True)
                (plugin_dir / "node_modules").mkdir()

                # Create package.json and marker with different versions
                (plugin_dir / "package.json").write_text(json.dumps({"version": "1.1.0"}))
                (plugin_dir / ".install-version").write_text(json.dumps({"version": "1.0.0"}))

                result = _is_claude_mem_deps_installed()

                assert result is False

    def test_preinstall_claude_mem_deps_returns_false_when_plugin_dir_missing(self):
        """preinstall_claude_mem_deps returns False when plugin dir doesn't exist."""
        from installer.steps.dependencies import preinstall_claude_mem_deps

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, "home", return_value=Path(tmpdir)):
                result = preinstall_claude_mem_deps()

                assert result is False

    def test_preinstall_claude_mem_deps_returns_true_when_already_installed(self):
        """preinstall_claude_mem_deps returns True when deps already installed."""
        import json

        from installer.steps.dependencies import preinstall_claude_mem_deps

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, "home", return_value=Path(tmpdir)):
                plugin_dir = Path(tmpdir) / ".claude" / "plugins" / "marketplaces" / "thedotmack"
                plugin_dir.mkdir(parents=True)
                (plugin_dir / "node_modules").mkdir()
                (plugin_dir / "package.json").write_text(json.dumps({"version": "1.0.0"}))
                (plugin_dir / ".install-version").write_text(json.dumps({"version": "1.0.0"}))

                result = preinstall_claude_mem_deps()

                assert result is True

    @patch("installer.steps.dependencies.command_exists")
    def test_preinstall_claude_mem_deps_returns_false_when_bun_missing(self, mock_cmd):
        """preinstall_claude_mem_deps returns False when bun not installed."""
        from installer.steps.dependencies import preinstall_claude_mem_deps

        mock_cmd.return_value = False

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, "home", return_value=Path(tmpdir)):
                plugin_dir = Path(tmpdir) / ".claude" / "plugins" / "marketplaces" / "thedotmack"
                plugin_dir.mkdir(parents=True)
                (plugin_dir / "package.json").write_text('{"version": "1.0.0"}')

                result = preinstall_claude_mem_deps()

                assert result is False

    @patch("subprocess.Popen")
    @patch("subprocess.run")
    @patch("installer.steps.dependencies.command_exists")
    def test_preinstall_claude_mem_deps_runs_bun_install(self, mock_cmd, mock_run, mock_popen):
        """preinstall_claude_mem_deps runs bun install and creates marker."""
        import json

        from installer.steps.dependencies import preinstall_claude_mem_deps

        mock_cmd.return_value = True
        mock_process = MagicMock()
        mock_process.stdout = iter([])
        mock_process.wait.return_value = None
        mock_process.returncode = 0
        mock_popen.return_value = mock_process
        mock_run.return_value = MagicMock(returncode=0, stdout="1.1.14")

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, "home", return_value=Path(tmpdir)):
                plugin_dir = Path(tmpdir) / ".claude" / "plugins" / "marketplaces" / "thedotmack"
                plugin_dir.mkdir(parents=True)
                (plugin_dir / "package.json").write_text(json.dumps({"version": "1.0.9"}))

                result = preinstall_claude_mem_deps()

                assert result is True
                mock_popen.assert_called_once()
                call_args = mock_popen.call_args
                assert call_args[0][0] == ["bun", "install"]
                assert call_args[1]["cwd"] == plugin_dir

                # Check marker file was created
                marker_path = plugin_dir / ".install-version"
                assert marker_path.exists()
                marker = json.loads(marker_path.read_text())
                assert marker["version"] == "1.0.9"

    @patch("installer.steps.dependencies.preinstall_claude_mem_deps")
    @patch("installer.steps.dependencies.run_qlty_check")
    @patch("installer.steps.dependencies.install_qlty")
    @patch("installer.steps.dependencies.install_vexor")
    @patch("installer.steps.dependencies.install_context7")
    @patch("installer.steps.dependencies.install_claude_mem")
    @patch("installer.steps.dependencies.install_typescript_lsp")
    @patch("installer.steps.dependencies.install_claude_code")
    @patch("installer.steps.dependencies.install_nodejs")
    def test_dependencies_step_calls_preinstall_after_claude_mem(
        self,
        mock_nodejs,
        mock_claude,
        mock_typescript_lsp,
        mock_claude_mem,
        mock_context7,
        mock_vexor,
        mock_qlty,
        mock_qlty_check,
        mock_preinstall,
    ):
        """DependenciesStep calls preinstall_claude_mem_deps after claude_mem succeeds."""
        from installer.context import InstallContext
        from installer.steps.dependencies import DependenciesStep
        from installer.ui import Console

        # Setup mocks
        mock_nodejs.return_value = True
        mock_claude.return_value = (True, "latest")
        mock_typescript_lsp.return_value = True
        mock_claude_mem.return_value = True
        mock_context7.return_value = True
        mock_vexor.return_value = True
        mock_qlty.return_value = (True, False)
        mock_preinstall.return_value = True

        step = DependenciesStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = InstallContext(
                project_dir=Path(tmpdir),
                enable_python=False,
                ui=Console(non_interactive=True),
            )

            step.run(ctx)

            # Verify preinstall was called after claude_mem
            mock_claude_mem.assert_called_once()
            mock_preinstall.assert_called_once()


class TestContext7Install:
    """Test Context7 plugin installation."""

    def test_install_context7_exists(self):
        """install_context7 function exists."""
        from installer.steps.dependencies import install_context7

        assert callable(install_context7)

    @patch("installer.steps.dependencies._is_marketplace_installed", return_value=False)
    @patch("installer.steps.dependencies._is_plugin_installed", return_value=False)
    @patch("subprocess.run")
    def test_install_context7_calls_plugin_install(self, mock_run, mock_plugin, mock_market):
        """install_context7 calls claude plugin install context7."""
        from installer.steps.dependencies import install_context7

        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        result = install_context7()

        assert result is True
        mock_run.assert_called()
        # Should have called marketplace add and plugin install
        assert mock_run.call_count >= 2


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
