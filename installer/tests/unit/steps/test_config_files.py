"""Tests for config files step."""

from __future__ import annotations

from pathlib import Path

from installer.context import InstallContext


class TestConfigFilesStep:
    """Test ConfigFilesStep class."""

    def test_config_files_step_has_correct_name(self):
        """ConfigFilesStep has name 'config_files'."""
        from installer.steps.config_files import ConfigFilesStep

        step = ConfigFilesStep()
        assert step.name == "config_files"

    def test_writes_node24_project_runtime(self, tmp_path: Path) -> None:
        from installer.steps.config_files import ConfigFilesStep

        ConfigFilesStep().run(InstallContext(project_dir=tmp_path, is_local_install=True))

        assert (tmp_path / ".nvmrc").read_text() == "24\n"
