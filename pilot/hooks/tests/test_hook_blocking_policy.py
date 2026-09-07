"""Repository-wide policy for the few hooks allowed to block agent work."""

from __future__ import annotations

import re
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent.parent
ESSENTIAL_BLOCKERS = {
    "license_prompt_guard.py": "rejects only explicit unavailable Pilot workflow invocations",
    "repo_agent_sync.py": "prevents edits to the generated CLAUDE.md side before mutation",
    "spec_mode_guard.py": "rejects incompatible entry into an explicitly invoked Pilot workflow",
    "spec_plan_validator.py": "keeps an explicit planning workflow open until its artifact exists",
    "spec_stop_guard.py": "keeps an active explicit workflow open until its completion contract is met",
}
ESSENTIAL_USER_WARNINGS = {
    "codex_skill_sync.py": "Codex needs a visible recovery path when license removal disables its Pilot assets",
    "license_check.py": "the user must know why paid Pilot capabilities are unavailable",
    "repo_agent_sync.py": "a pre-mutation generated-file denial must explain the canonical target",
}
BLOCKING_PRIMITIVES = re.compile(
    r"(?:\bpost_tool_use_block\(|\bpre_tool_use_deny\(|\bstop_block\(|"
    r"[\"'](?:decision|permissionDecision|behavior)[\"']\s*:\s*[\"'](?:block|deny)[\"'])"
)


def test_only_essential_hooks_use_blocking_primitives() -> None:
    detected: set[str] = set()
    for path in HOOKS_DIR.rglob("*.py"):
        if "tests" in path.parts or path == HOOKS_DIR / "_lib" / "util.py":
            continue
        source = path.read_text(encoding="utf-8")
        if BLOCKING_PRIMITIVES.search(source):
            detected.add(path.name)

    repo_sync = (HOOKS_DIR / "repo_agent_sync.py").read_text(encoding="utf-8")
    if "_pre_tool_payload(" in repo_sync and '"deny"' in repo_sync:
        detected.add("repo_agent_sync.py")

    assert detected == set(ESSENTIAL_BLOCKERS), {
        "unexpected": sorted(detected - set(ESSENTIAL_BLOCKERS)),
        "missing": sorted(set(ESSENTIAL_BLOCKERS) - detected),
    }


def test_only_essential_hooks_surface_system_messages() -> None:
    detected = {path.name for path in HOOKS_DIR.glob("*.py") if '"systemMessage"' in path.read_text(encoding="utf-8")}
    assert detected == set(ESSENTIAL_USER_WARNINGS), {
        "unexpected": sorted(detected - set(ESSENTIAL_USER_WARNINGS)),
        "missing": sorted(set(ESSENTIAL_USER_WARNINGS) - detected),
    }
