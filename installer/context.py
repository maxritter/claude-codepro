"""InstallContext - Shared state for installation pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from installer.ui import Console


@dataclass
class InstallContext:
    """Context object that flows through all installation steps."""

    project_dir: Path
    install_python: bool = True
    install_typescript: bool = True
    non_interactive: bool = False
    skip_env: bool = False
    local_mode: bool = False
    local_repo_dir: Path | None = None
    completed_steps: list[str] = field(default_factory=list)
    config: dict[str, Any] = field(default_factory=dict)
    ui: Console | None = None

    def mark_completed(self, step_name: str) -> None:
        """Mark a step as completed."""
        if step_name not in self.completed_steps:
            self.completed_steps.append(step_name)

    def is_completed(self, step_name: str) -> bool:
        """Check if a step is completed."""
        return step_name in self.completed_steps

    def needs_rollback(self) -> bool:
        """Check if rollback is needed (i.e., some steps completed)."""
        return len(self.completed_steps) > 0
