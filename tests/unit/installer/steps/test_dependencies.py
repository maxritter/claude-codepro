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

    @patch("installer.steps.dependencies._get_forced_claude_version", return_value=None)
    @patch("installer.steps.dependencies._configure_firecrawl_mcp")
    @patch("installer.steps.dependencies._configure_claude_defaults")
    @patch("subprocess.run")
    @patch("installer.steps.dependencies._remove_native_claude_binaries")
    def test_install_claude_code_removes_native_binaries(
        self, mock_remove, mock_run, mock_config, mock_firecrawl, mock_version
    ):
        """install_claude_code removes native binaries before npm install."""
        from installer.steps.dependencies import install_claude_code

        mock_run.return_value = MagicMock(returncode=0)

        with tempfile.TemporaryDirectory() as tmpdir:
            install_claude_code(Path(tmpdir))

        mock_remove.assert_called_once()

    @patch("installer.steps.dependencies._get_forced_claude_version", return_value=None)
    @patch("installer.steps.dependencies._configure_firecrawl_mcp")
    @patch("installer.steps.dependencies._configure_claude_defaults")
    @patch("subprocess.run")
    @patch("installer.steps.dependencies._remove_native_claude_binaries")
    def test_install_claude_code_always_runs_npm_install(
        self, mock_remove, mock_run, mock_config, mock_firecrawl, mock_version
    ):
        """install_claude_code always runs npm install (upgrades if exists)."""
        from installer.steps.dependencies import install_claude_code

        mock_run.return_value = MagicMock(returncode=0)

        with tempfile.TemporaryDirectory() as tmpdir:
            success, version = install_claude_code(Path(tmpdir))

        assert success is True
        assert version == "latest"
        # Verify npm install was called
        npm_calls = [c for c in mock_run.call_args_list if "npm install" in str(c)]
        assert len(npm_calls) >= 1

    @patch("installer.steps.dependencies._get_forced_claude_version", return_value=None)
    @patch("installer.steps.dependencies._configure_firecrawl_mcp")
    @patch("installer.steps.dependencies._configure_claude_defaults")
    @patch("subprocess.run")
    @patch("installer.steps.dependencies._remove_native_claude_binaries")
    def test_install_claude_code_configures_defaults(
        self, mock_remove, mock_run, mock_config, mock_firecrawl, mock_version
    ):
        """install_claude_code configures Claude defaults after npm install."""
        from installer.steps.dependencies import install_claude_code

        mock_run.return_value = MagicMock(returncode=0)

        with tempfile.TemporaryDirectory() as tmpdir:
            install_claude_code(Path(tmpdir))

        mock_config.assert_called_once()

    @patch("installer.steps.dependencies._get_forced_claude_version", return_value=None)
    @patch("installer.steps.dependencies._configure_firecrawl_mcp")
    @patch("installer.steps.dependencies._configure_claude_defaults")
    @patch("subprocess.run")
    @patch("installer.steps.dependencies._remove_native_claude_binaries")
    def test_install_claude_code_does_not_configure_firecrawl(
        self, mock_remove, mock_run, mock_config, mock_firecrawl, mock_version
    ):
        """install_claude_code does not configure Firecrawl (handled by DependenciesStep)."""
        from installer.steps.dependencies import install_claude_code

        mock_run.return_value = MagicMock(returncode=0)

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

        result = install_vexor(provider_mode="cpu")

        assert result is True
        mock_config.assert_called_once_with("cpu", None)

    @patch("installer.steps.dependencies._configure_vexor_defaults")
    @patch("installer.steps.dependencies._fix_vexor_onnxruntime_conflict")
    @patch("installer.steps.dependencies._is_vexor_in_project_venv")
    @patch("installer.steps.dependencies.command_exists")
    def test_install_vexor_cuda_mode_fixes_onnxruntime(self, mock_cmd_exists, mock_is_venv, mock_fix, mock_config):
        """install_vexor in cuda mode calls _fix_vexor_onnxruntime_conflict for uv tool vexor."""
        from installer.steps.dependencies import install_vexor

        mock_is_venv.return_value = False  # Not in project .venv
        mock_cmd_exists.return_value = True  # Installed as uv tool
        mock_fix.return_value = True
        mock_config.return_value = True

        result = install_vexor(provider_mode="cuda")

        assert result is True
        mock_fix.assert_called_once()
        mock_config.assert_called_once_with("cuda", None)

    @patch("installer.steps.dependencies._configure_vexor_defaults")
    @patch("subprocess.run")
    @patch("installer.steps.dependencies._is_vexor_in_project_venv")
    @patch("installer.steps.dependencies.command_exists")
    def test_install_vexor_installs_correct_package_for_cuda(
        self, mock_cmd_exists, mock_is_venv, mock_run, mock_config
    ):
        """install_vexor installs vexor[local-cuda] for cuda mode."""
        from installer.steps.dependencies import install_vexor

        mock_is_venv.return_value = False  # Not in project .venv
        mock_cmd_exists.return_value = False  # Not installed anywhere
        mock_run.return_value = MagicMock(returncode=0)
        mock_config.return_value = True

        with patch("installer.steps.dependencies._fix_vexor_onnxruntime_conflict", return_value=True):
            result = install_vexor(provider_mode="cuda")

        assert result is True
        # Check that uv tool install was called with vexor[local-cuda]
        install_calls = [c for c in mock_run.call_args_list if "uv" in str(c)]
        assert len(install_calls) >= 1
        assert "vexor[local-cuda]" in str(install_calls[0])

    @patch("installer.steps.dependencies._configure_vexor_defaults")
    @patch("subprocess.run")
    @patch("installer.steps.dependencies._is_vexor_in_project_venv")
    @patch("installer.steps.dependencies.command_exists")
    def test_install_vexor_installs_correct_package_for_openai(
        self, mock_cmd_exists, mock_is_venv, mock_run, mock_config
    ):
        """install_vexor installs vexor for openai mode."""
        from installer.steps.dependencies import install_vexor

        mock_is_venv.return_value = False  # Not in project .venv
        mock_cmd_exists.return_value = False  # Not installed anywhere
        mock_run.return_value = MagicMock(returncode=0)
        mock_config.return_value = True

        result = install_vexor(provider_mode="openai", api_key="sk-test")

        assert result is True
        install_calls = [c for c in mock_run.call_args_list if "uv" in str(c)]
        assert len(install_calls) >= 1
        # For openai mode, just "vexor" (no extras)
        call_str = str(install_calls[0])
        assert "vexor" in call_str
        assert "local" not in call_str

    def test_configure_vexor_defaults_cpu_mode(self):
        """_configure_vexor_defaults configures CPU mode correctly."""
        import json

        from installer.steps.dependencies import _configure_vexor_defaults

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, "home", return_value=Path(tmpdir)):
                result = _configure_vexor_defaults(provider_mode="cpu")

                assert result is True
                config_path = Path(tmpdir) / ".vexor" / "config.json"
                assert config_path.exists()
                config = json.loads(config_path.read_text())
                assert config["model"] == "intfloat/multilingual-e5-small"
                assert config["provider"] == "local"
                assert config["local_cuda"] is False
                assert config["rerank"] == "bm25"

    def test_configure_vexor_defaults_cuda_mode(self):
        """_configure_vexor_defaults configures CUDA mode correctly."""
        import json

        from installer.steps.dependencies import _configure_vexor_defaults

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, "home", return_value=Path(tmpdir)):
                result = _configure_vexor_defaults(provider_mode="cuda")

                assert result is True
                config_path = Path(tmpdir) / ".vexor" / "config.json"
                config = json.loads(config_path.read_text())
                assert config["model"] == "intfloat/multilingual-e5-small"
                assert config["provider"] == "local"
                assert config["local_cuda"] is True

    def test_configure_vexor_defaults_openai_mode(self):
        """_configure_vexor_defaults configures OpenAI mode correctly."""
        import json

        from installer.steps.dependencies import _configure_vexor_defaults

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, "home", return_value=Path(tmpdir)):
                result = _configure_vexor_defaults(provider_mode="openai", api_key="sk-test123")

                assert result is True
                config_path = Path(tmpdir) / ".vexor" / "config.json"
                config = json.loads(config_path.read_text())
                assert config["model"] == "text-embedding-3-small"
                assert config["provider"] == "openai"
                assert config["local_cuda"] is False
                assert config["api_key"] == "sk-test123"

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
                result = _configure_vexor_defaults(provider_mode="cpu")

                assert result is True
                config = json.loads(config_path.read_text())
                assert config["custom_key"] == "custom_value"
                assert config["model"] == "intfloat/multilingual-e5-small"


class TestVexorCudaHelpers:
    """Test vexor CUDA helper functions."""

    def test_get_vexor_pip_path_returns_path_when_exists(self):
        """_get_vexor_pip_path returns Path when pip exists in vexor env."""
        from installer.steps.dependencies import _get_vexor_pip_path

        with tempfile.TemporaryDirectory() as tmpdir:
            vexor_bin = Path(tmpdir) / ".local" / "share" / "uv" / "tools" / "vexor" / "bin"
            vexor_bin.mkdir(parents=True)
            pip_path = vexor_bin / "pip"
            pip_path.touch()

            with patch.object(Path, "home", return_value=Path(tmpdir)):
                result = _get_vexor_pip_path()

                assert result is not None
                assert str(result).endswith("pip")

    def test_get_vexor_pip_path_returns_none_when_missing(self):
        """_get_vexor_pip_path returns None when pip doesn't exist."""
        from installer.steps.dependencies import _get_vexor_pip_path

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, "home", return_value=Path(tmpdir)):
                result = _get_vexor_pip_path()

                assert result is None

    @patch("subprocess.run")
    def test_fix_vexor_onnxruntime_conflict_removes_cpu_onnxruntime(self, mock_run):
        """_fix_vexor_onnxruntime_conflict removes onnxruntime when onnxruntime-gpu exists."""
        from installer.steps.dependencies import _fix_vexor_onnxruntime_conflict

        mock_run.return_value = MagicMock(
            stdout="onnxruntime-gpu 1.16.0\nonnxruntime 1.16.0\nnumpy 1.24.0",
            returncode=0,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            vexor_bin = Path(tmpdir) / ".local" / "share" / "uv" / "tools" / "vexor" / "bin"
            vexor_bin.mkdir(parents=True)
            pip_path = vexor_bin / "pip"
            pip_path.touch()

            with patch.object(Path, "home", return_value=Path(tmpdir)):
                result = _fix_vexor_onnxruntime_conflict()

                assert result is True
                # Should have called pip list and pip uninstall
                assert mock_run.call_count >= 2

    @patch("subprocess.run")
    def test_fix_vexor_onnxruntime_conflict_skips_when_no_conflict(self, mock_run):
        """_fix_vexor_onnxruntime_conflict does nothing when no conflict exists."""
        from installer.steps.dependencies import _fix_vexor_onnxruntime_conflict

        mock_run.return_value = MagicMock(
            stdout="onnxruntime-gpu 1.16.0\nnumpy 1.24.0",
            returncode=0,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            vexor_bin = Path(tmpdir) / ".local" / "share" / "uv" / "tools" / "vexor" / "bin"
            vexor_bin.mkdir(parents=True)
            pip_path = vexor_bin / "pip"
            pip_path.touch()

            with patch.object(Path, "home", return_value=Path(tmpdir)):
                result = _fix_vexor_onnxruntime_conflict()

                assert result is True
                # Should only call pip list, not uninstall
                assert mock_run.call_count == 1

    def test_fix_vexor_onnxruntime_conflict_returns_false_when_no_pip(self):
        """_fix_vexor_onnxruntime_conflict returns False when vexor pip doesn't exist."""
        from installer.steps.dependencies import _fix_vexor_onnxruntime_conflict

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, "home", return_value=Path(tmpdir)):
                result = _fix_vexor_onnxruntime_conflict()

                assert result is False


class TestDependenciesStepGpuDetection:
    """Test DependenciesStep GPU detection integration."""

    @patch("installer.steps.dependencies.run_qlty_check")
    @patch("installer.steps.dependencies.install_qlty")
    @patch("installer.steps.dependencies.install_vexor")
    @patch("installer.steps.dependencies.install_context7")
    @patch("installer.steps.dependencies.install_claude_mem")
    @patch("installer.steps.dependencies.install_claude_code")
    @patch("installer.steps.dependencies.install_nodejs")
    @patch("installer.steps.dependencies.has_nvidia_gpu")
    def test_uses_cuda_when_gpu_detected(
        self,
        mock_gpu,
        mock_nodejs,
        mock_claude,
        mock_claude_mem,
        mock_context7,
        mock_vexor,
        mock_qlty,
        mock_qlty_check,
    ):
        """DependenciesStep uses CUDA mode when GPU is detected."""
        from installer.context import InstallContext
        from installer.steps.dependencies import DependenciesStep
        from installer.ui import Console

        mock_gpu.return_value = {"detected": True, "method": "nvidia_smi"}
        mock_nodejs.return_value = True
        mock_claude.return_value = (True, "latest")
        mock_claude_mem.return_value = True
        mock_context7.return_value = True
        mock_vexor.return_value = True
        mock_qlty.return_value = (True, False)

        step = DependenciesStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = InstallContext(
                project_dir=Path(tmpdir),
                enable_python=False,
                enable_typescript=False,
                ui=Console(non_interactive=True),
            )

            step.run(ctx)

            # Should call has_nvidia_gpu with verbose=True
            mock_gpu.assert_called_once_with(verbose=True)
            # Should call install_vexor with cuda mode
            mock_vexor.assert_called_once_with("cuda", None)

    @patch("installer.steps.dependencies.run_qlty_check")
    @patch("installer.steps.dependencies.install_qlty")
    @patch("installer.steps.dependencies.install_vexor")
    @patch("installer.steps.dependencies.install_context7")
    @patch("installer.steps.dependencies.install_claude_mem")
    @patch("installer.steps.dependencies.install_claude_code")
    @patch("installer.steps.dependencies.install_nodejs")
    @patch("installer.steps.dependencies.has_nvidia_gpu")
    def test_uses_flag_in_non_interactive_mode(
        self,
        mock_gpu,
        mock_nodejs,
        mock_claude,
        mock_claude_mem,
        mock_context7,
        mock_vexor,
        mock_qlty,
        mock_qlty_check,
    ):
        """DependenciesStep uses enable_openai_embeddings flag in non-interactive mode."""
        from installer.context import InstallContext
        from installer.steps.dependencies import DependenciesStep
        from installer.ui import Console

        mock_gpu.return_value = {"detected": False, "error": "not found"}
        mock_nodejs.return_value = True
        mock_claude.return_value = (True, "latest")
        mock_claude_mem.return_value = True
        mock_context7.return_value = True
        mock_vexor.return_value = True
        mock_qlty.return_value = (True, False)

        step = DependenciesStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            # Test with enable_openai_embeddings=True
            ctx = InstallContext(
                project_dir=Path(tmpdir),
                enable_python=False,
                enable_typescript=False,
                enable_openai_embeddings=True,
                non_interactive=True,
                ui=Console(non_interactive=True),
            )

            step.run(ctx)

            # Should call install_vexor with openai mode
            mock_vexor.assert_called_once()
            call_args = mock_vexor.call_args[0]
            assert call_args[0] == "openai"

    @patch("installer.steps.dependencies.run_qlty_check")
    @patch("installer.steps.dependencies.install_qlty")
    @patch("installer.steps.dependencies.install_vexor")
    @patch("installer.steps.dependencies.install_context7")
    @patch("installer.steps.dependencies.install_claude_mem")
    @patch("installer.steps.dependencies.install_claude_code")
    @patch("installer.steps.dependencies.install_nodejs")
    @patch("installer.steps.dependencies.has_nvidia_gpu")
    def test_uses_cpu_when_no_gpu_and_flag_false(
        self,
        mock_gpu,
        mock_nodejs,
        mock_claude,
        mock_claude_mem,
        mock_context7,
        mock_vexor,
        mock_qlty,
        mock_qlty_check,
    ):
        """DependenciesStep uses CPU mode when no GPU and flag is False."""
        from installer.context import InstallContext
        from installer.steps.dependencies import DependenciesStep
        from installer.ui import Console

        mock_gpu.return_value = {"detected": False, "error": "not found"}
        mock_nodejs.return_value = True
        mock_claude.return_value = (True, "latest")
        mock_claude_mem.return_value = True
        mock_context7.return_value = True
        mock_vexor.return_value = True
        mock_qlty.return_value = (True, False)

        step = DependenciesStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            # Test with enable_openai_embeddings=False
            ctx = InstallContext(
                project_dir=Path(tmpdir),
                enable_python=False,
                enable_typescript=False,
                enable_openai_embeddings=False,
                non_interactive=True,
                ui=Console(non_interactive=True),
            )

            step.run(ctx)

            # Should call install_vexor with cpu mode
            mock_vexor.assert_called_once()
            call_args = mock_vexor.call_args[0]
            assert call_args[0] == "cpu"


class TestVexorVenvDetection:
    """Test _is_vexor_in_project_venv() function."""

    def test_is_vexor_in_project_venv_returns_true_when_exists_in_venv(self):
        """_is_vexor_in_project_venv returns True when vexor exists in .venv."""
        from installer.steps.dependencies import _is_vexor_in_project_venv

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create .venv/bin/vexor
            venv_bin = Path(tmpdir) / ".venv" / "bin"
            venv_bin.mkdir(parents=True)
            vexor_bin = venv_bin / "vexor"
            vexor_bin.touch()

            # Change cwd to tmpdir
            import os

            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                result = _is_vexor_in_project_venv()
                assert result is True
            finally:
                os.chdir(original_cwd)

    def test_is_vexor_in_project_venv_returns_true_when_exists_in_venv_dir(self):
        """_is_vexor_in_project_venv returns True when vexor exists in venv/ (not .venv)."""
        from installer.steps.dependencies import _is_vexor_in_project_venv

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create venv/bin/vexor (alternative location)
            venv_bin = Path(tmpdir) / "venv" / "bin"
            venv_bin.mkdir(parents=True)
            vexor_bin = venv_bin / "vexor"
            vexor_bin.touch()

            import os

            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                result = _is_vexor_in_project_venv()
                assert result is True
            finally:
                os.chdir(original_cwd)

    def test_is_vexor_in_project_venv_returns_false_when_missing(self):
        """_is_vexor_in_project_venv returns False when vexor not in .venv."""
        from installer.steps.dependencies import _is_vexor_in_project_venv

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create .venv/bin but no vexor
            venv_bin = Path(tmpdir) / ".venv" / "bin"
            venv_bin.mkdir(parents=True)

            import os

            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                result = _is_vexor_in_project_venv()
                assert result is False
            finally:
                os.chdir(original_cwd)

    def test_is_vexor_in_project_venv_returns_false_when_no_venv(self):
        """_is_vexor_in_project_venv returns False when no .venv directory exists."""
        from installer.steps.dependencies import _is_vexor_in_project_venv

        with tempfile.TemporaryDirectory() as tmpdir:
            import os

            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                result = _is_vexor_in_project_venv()
                assert result is False
            finally:
                os.chdir(original_cwd)


class TestVexorVenvUpgrade:
    """Test _upgrade_venv_vexor_cuda() function."""

    @patch("subprocess.run")
    def test_upgrade_venv_vexor_cuda_calls_uv_pip_install(self, mock_run):
        """_upgrade_venv_vexor_cuda calls uv pip install vexor[local-cuda]."""
        from installer.steps.dependencies import _upgrade_venv_vexor_cuda

        # Mock pip list to show no conflict
        mock_run.return_value = MagicMock(returncode=0, stdout="onnxruntime-gpu 1.16.0")

        result = _upgrade_venv_vexor_cuda()

        assert result is True
        # First call should be uv pip install
        first_call = mock_run.call_args_list[0]
        assert first_call[0][0] == ["uv", "pip", "install", "vexor[local-cuda]"]

    @patch("subprocess.run")
    def test_upgrade_venv_vexor_cuda_removes_conflicting_onnxruntime(self, mock_run):
        """_upgrade_venv_vexor_cuda removes CPU onnxruntime when conflict exists."""
        from installer.steps.dependencies import _upgrade_venv_vexor_cuda

        def side_effect(*args, **kwargs):
            cmd = args[0]
            if cmd == ["uv", "pip", "list"]:
                # Simulate both packages installed (conflict)
                return MagicMock(stdout="onnxruntime-gpu 1.16.0\nonnxruntime 1.16.0")
            return MagicMock(returncode=0)

        mock_run.side_effect = side_effect

        result = _upgrade_venv_vexor_cuda()

        assert result is True
        # Should have called uninstall to remove the conflict
        uninstall_calls = [c for c in mock_run.call_args_list if "uninstall" in str(c)]
        assert len(uninstall_calls) == 1
        assert "onnxruntime" in str(uninstall_calls[0])

    @patch("subprocess.run")
    def test_upgrade_venv_vexor_cuda_skips_uninstall_when_no_conflict(self, mock_run):
        """_upgrade_venv_vexor_cuda skips uninstall when no conflict exists."""
        from installer.steps.dependencies import _upgrade_venv_vexor_cuda

        def side_effect(*args, **kwargs):
            cmd = args[0]
            if cmd == ["uv", "pip", "list"]:
                # Only GPU version installed (no conflict)
                return MagicMock(stdout="onnxruntime-gpu 1.16.0\nnumpy 1.24.0")
            return MagicMock(returncode=0)

        mock_run.side_effect = side_effect

        result = _upgrade_venv_vexor_cuda()

        assert result is True
        # Should NOT have called uninstall
        uninstall_calls = [c for c in mock_run.call_args_list if "uninstall" in str(c)]
        assert len(uninstall_calls) == 0

    @patch("subprocess.run")
    def test_upgrade_venv_vexor_cuda_returns_false_on_failure(self, mock_run):
        """_upgrade_venv_vexor_cuda returns False when subprocess fails."""
        import subprocess

        from installer.steps.dependencies import _upgrade_venv_vexor_cuda

        mock_run.side_effect = subprocess.CalledProcessError(1, "uv")

        result = _upgrade_venv_vexor_cuda()

        assert result is False


class TestVexorInstallVenvUpgrade:
    """Test install_vexor() .venv upgrade behavior."""

    @patch("installer.steps.dependencies._configure_vexor_defaults")
    @patch("installer.steps.dependencies._upgrade_venv_vexor_cuda")
    @patch("installer.steps.dependencies._is_vexor_in_project_venv")
    def test_install_vexor_upgrades_venv_vexor_when_cuda_detected(self, mock_is_venv, mock_upgrade, mock_config):
        """install_vexor upgrades .venv vexor with CUDA extras when GPU detected."""
        from installer.steps.dependencies import install_vexor

        mock_is_venv.return_value = True
        mock_upgrade.return_value = True
        mock_config.return_value = True

        result = install_vexor(provider_mode="cuda")

        assert result is True
        mock_is_venv.assert_called_once()
        mock_upgrade.assert_called_once()
        mock_config.assert_called_once_with("cuda", None)

    @patch("installer.steps.dependencies._configure_vexor_defaults")
    @patch("installer.steps.dependencies._upgrade_venv_vexor_cuda")
    @patch("installer.steps.dependencies._is_vexor_in_project_venv")
    def test_install_vexor_skips_upgrade_when_no_cuda(self, mock_is_venv, mock_upgrade, mock_config):
        """install_vexor skips upgrade when not in CUDA mode."""
        from installer.steps.dependencies import install_vexor

        mock_is_venv.return_value = True
        mock_config.return_value = True

        result = install_vexor(provider_mode="cpu")

        assert result is True
        mock_is_venv.assert_called_once()
        mock_upgrade.assert_not_called()
        mock_config.assert_called_once_with("cpu", None)

    @patch("installer.steps.dependencies._configure_vexor_defaults")
    @patch("installer.steps.dependencies._upgrade_venv_vexor_cuda")
    @patch("installer.steps.dependencies._is_vexor_in_project_venv")
    @patch("installer.steps.dependencies.command_exists")
    def test_install_vexor_checks_venv_before_command_exists(
        self, mock_cmd_exists, mock_is_venv, mock_upgrade, mock_config
    ):
        """install_vexor checks .venv vexor first, before command_exists."""
        from installer.steps.dependencies import install_vexor

        mock_is_venv.return_value = True
        mock_upgrade.return_value = True
        mock_config.return_value = True

        result = install_vexor(provider_mode="cuda")

        assert result is True
        # command_exists should NOT be called if venv vexor found
        mock_cmd_exists.assert_not_called()

    @patch("installer.steps.dependencies._configure_vexor_defaults")
    @patch("installer.steps.dependencies._fix_vexor_onnxruntime_conflict")
    @patch("installer.steps.dependencies._is_vexor_in_project_venv")
    @patch("installer.steps.dependencies.command_exists")
    def test_install_vexor_falls_back_to_uv_tool_when_no_venv(
        self, mock_cmd_exists, mock_is_venv, mock_fix, mock_config
    ):
        """install_vexor falls back to uv tool check when no .venv vexor."""
        from installer.steps.dependencies import install_vexor

        mock_is_venv.return_value = False
        mock_cmd_exists.return_value = True
        mock_fix.return_value = True
        mock_config.return_value = True

        result = install_vexor(provider_mode="cuda")

        assert result is True
        mock_is_venv.assert_called_once()
        mock_cmd_exists.assert_called_once_with("vexor")
        mock_fix.assert_called_once()  # Should call onnxruntime fix for uv tool vexor
