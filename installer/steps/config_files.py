"""Config files step - installs config files."""

from __future__ import annotations

from installer.context import InstallContext
from installer.steps.base import BaseStep


class ConfigFilesStep(BaseStep):
    """Step that installs config files."""

    name = "config_files"

    def check(self, ctx: InstallContext) -> bool:
        """Always returns False - config files should always be updated."""
        return False

    def run(self, ctx: InstallContext) -> None:
        """Install config files."""
        ui = ctx.ui

        nvmrc_file = ctx.project_dir / ".nvmrc"
        nvmrc_file.write_text("24\n")
        if ui:
            ui.success("Created .nvmrc for Node.js 24")
