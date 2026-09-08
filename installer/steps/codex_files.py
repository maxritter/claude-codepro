"""Installer step for Codex CLI-specific file installation.

Installs hooks, skills, MCP config, and rules for Codex users.
Only runs when a Codex CLI or ChatGPT-bundled Codex binary is detected.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tomllib
from pathlib import Path
from typing import Any, Callable

import yaml

from installer.claude_paths import get_claude_config_dir
from installer.context import InstallContext
from installer.platform_utils import is_codex_installed
from installer.steps.base import BaseStep

_CODEX_REVIEW_AGENT_MODEL = "codex-auto-review"
_CODEX_MODEL_CATALOG_FILENAME = ".pilot-model-catalog.json"
_CODEX_UPDATE_PLAN_CONFIG_MIN_VERSION = (0, 152, 0)
_CODEX_CONTEXT_MANAGEMENT_MIN_VERSION = (0, 153, 0)
_CODEX_CONTEXT_DEFAULTS = {
    # Opt into expanded context without replacing Codex's live model catalog.
    # Codex clamps this request and the compaction threshold to model limits.
    "model_context_window": "1050000",
    "model_auto_compact_token_limit": "922000",
}

_CODEX_SKILL_DESCRIPTIONS = {
    "spec": "Plan, approve, implement, and verify a scoped feature through the explicit /spec workflow.",
    "build": ("Pursue a named goal through autonomous build and verification loops with the explicit /build workflow."),
    "fix": (
        "Diagnose and repair a defect at its root cause, with a regression test and end-to-end proof. "
        "Explicit /fix workflow."
    ),
    "prd": ("Turn a rough product idea into an approved requirements document through the explicit /prd workflow."),
    "investigate": (
        "Produce an evidence-backed, read-only explanation of the current codebase through the explicit "
        "/investigate workflow."
    ),
    "cleanup": (
        "Report dead-code candidates with read-only evidence and no code changes through the explicit "
        "/cleanup workflow."
    ),
    "benchmark": "Benchmark and measure a rule, skill, or workflow with quantitative before/after evaluations.",
    "create-skill": (
        "Create, update, or test a reusable agent skill when the user asks for a skill or repeatable workflow."
    ),
    "setup-rules": "Set up, audit, or refresh repository agent rules such as AGENTS.md or CLAUDE.md.",
    "spec-plan": "Internal /spec feature-planning phase; use only after an explicitly invoked /spec routes here.",
    "spec-bugfix-plan": "Internal /spec bugfix-planning phase; use only after an explicitly invoked /spec routes here.",
    "spec-implement": "Internal /spec implementation phase for an approved plan; use only after /spec routes here.",
    "spec-verify": "Internal /spec feature-verification phase for a completed plan; use only after /spec routes here.",
    "spec-bugfix-verify": (
        "Internal /spec bugfix-verification phase for a completed plan; use only after /spec routes here."
    ),
}

_CODEX_EXPLICIT_ONLY_SKILL_NAMES = frozenset({"spec", "build", "fix", "prd", "investigate", "cleanup"})

# Sidecar listing the stack rules Pilot wrote to ~/.codex/rules/, so a later
# install can drop the ones it no longer ships without touching user files.
_CODEX_RULES_MANIFEST = ".pilot-rules.json"

# Per-skill sidecar listing the runtime resources copied from Pilot's
# decomposed skill. This lets upgrades remove only files Pilot previously
# installed while leaving user files (and unrelated skills) alone.
_CODEX_SKILL_RESOURCES_MANIFEST = ".pilot-resources.json"
_CODEX_HOOKS_BASELINE_FILE = ".pilot-hooks-baseline.json"
_CODEX_SKILL_AUTHORING_ENTRIES = frozenset(
    {
        "manifest.json",
        "orchestrator.md",
        "tests",
        "SKILL.md",
        _CODEX_SKILL_RESOURCES_MANIFEST,
    }
)


def _claude_rules_dir_or_none() -> Path | None:
    """Rules dir in the active Claude profile, for the Codex rules fallback.

    Returns None when CLAUDE_CONFIG_DIR is invalid, matching the caller's existing
    `Path | None` handling for its other two candidates, so the fallback is simply
    skipped rather than reading the personal profile. Read-only fallback; the
    primary source is ~/.pilot/rules.
    """
    try:
        return get_claude_config_dir() / "rules"
    except ValueError:
        return None


def _get_codex_config_dir() -> Path:
    """Resolve the Codex config directory, respecting CODEX_HOME env var."""
    env_dir = os.environ.get("CODEX_HOME")
    if env_dir:
        p = Path(env_dir)
        if not p.is_absolute():
            raise ValueError(f"CODEX_HOME must be an absolute path, got: {env_dir}")
        return p
    return Path.home() / ".codex"


def _retire_codex_model_catalog(content: str, codex_dir: Path) -> tuple[str, bool]:
    """Remove only the root catalog pointer previously installed by Pilot."""
    # Pilot only installed root keys. Leave profile overrides and catalog files
    # alone: a user profile may still explicitly reference the old file.
    section = re.search(r"(?m)^[ \t]*\[", content)
    end = section.start() if section else len(content)
    root = content[:end]
    try:
        parsed = tomllib.loads(root)
    except tomllib.TOMLDecodeError:
        return content, False

    catalog = parsed.get("model_catalog_json")
    if catalog != str(codex_dir / _CODEX_MODEL_CATALOG_FILENAME):
        return content, False
    key = "model_catalog_json"
    root = re.sub(rf"(?m)^[ \t]*(?:{key}|\"{key}\"|'{key}')[ \t]*=[^\n]*(?:\n|$)", "", root)
    updated = root + content[end:]
    return updated, updated != content


def _codex_binary_candidates() -> list[Path]:
    """Return installed Codex binaries in preference order.

    Keep these fallback locations aligned with
    :func:`installer.platform_utils.is_codex_installed`.
    """
    home = Path.home()
    candidates = [
        Path(path)
        for path in (
            shutil.which("codex"),
            home / ".codex" / "bin" / "codex",
            home / ".local" / "bin" / "codex",
            home / "Applications" / "ChatGPT.app" / "Contents" / "Resources" / "codex",
            Path("/usr/local/bin/codex"),
            Path("/Applications/ChatGPT.app/Contents/Resources/codex"),
        )
        if path is not None
    ]
    return list(dict.fromkeys(path for path in candidates if path.is_file() and os.access(path, os.X_OK)))


# Per-sub-install label formatters used by CodexFilesStep.run(). Each
# receives the sub-install's return value (count or bool) and returns the
# success-line string, or None to suppress (for empty/no-op installs).
def _label_hook_events(n: int) -> str | None:
    return f"Configured {n} hook events" if n else None


def _label_adapted_skills(n: int) -> str | None:
    return f"Installed {n} adapted skills" if n else None


def _label_review_agents(n: int) -> str | None:
    return f"Installed {n} review agents" if n else None


def _label_codex_config(changed: bool) -> str | None:
    return "Configured Codex config.toml" if changed else None


def _label_mcp_servers(n: int) -> str | None:
    return f"Configured {n} MCP servers" if n else None


def _label_codex_rules(n: int) -> str | None:
    return f"Installed Codex guidance ({n} source files)" if n else None


class _CodexReport:
    """Accumulator + reporter for CodexFilesStep sub-installs.

    Replaces the previous pattern of six ``if ui and n_X: ui.success(...)``
    inline calls scattered across :meth:`CodexFilesStep.run`. Adding a new
    sub-install now means: write the method, write its label formatter, and
    add ONE ``report.record(...)`` call — no extra UI gates or format strings
    to thread through ``run()``.
    """

    def __init__(self, ui: Any) -> None:
        self._ui = ui

    def record(self, value: int | bool, formatter: "Callable[[Any], str | None]") -> None:
        if self._ui is None:
            return
        line = formatter(value)
        if line:
            self._ui.success(line)


class CodexFilesStep(BaseStep):
    """Install Pilot Shell assets for Codex CLI."""

    name = "codex_files"

    def check(self, ctx: InstallContext) -> bool:
        return False

    def run(self, ctx: InstallContext) -> None:
        ui = ctx.ui
        if not is_codex_installed():
            if ui:
                ui.info("Codex CLI not detected — skipping Codex file installation")
            return

        if ui:
            ui.status("Installing Codex CLI integration...")

        # Sub-install pipeline: each entry is (method, label-formatter).
        # The formatter receives the method's return value and produces the
        # success line, or None to suppress (when nothing was installed).
        # Errors are caught around the right slice — TOML errors only happen
        # inside the config/mcp methods.
        report = _CodexReport(ui)

        try:
            report.record(self._install_codex_hooks(ctx), _label_hook_events)
            report.record(self._install_codex_skills(ctx), _label_adapted_skills)
            report.record(self._install_codex_agents(ctx), _label_review_agents)
        except ValueError as e:
            if ui:
                ui.warning(f"Skipping Codex file installation: {e}")
            return

        try:
            report.record(self._install_codex_config(ctx), _label_codex_config)
            report.record(self._install_codex_mcp(ctx), _label_mcp_servers)
        except _TomlStructureError as e:
            if ui:
                ui.warning(f"Skipping Codex TOML config due to structure error: {e}")
        except ValueError as e:
            if ui:
                ui.warning(f"Skipping Codex file installation: {e}")
            return

        try:
            report.record(self._install_codex_rules(ctx), _label_codex_rules)
        except ValueError as e:
            if ui:
                ui.warning(f"Skipping Codex file installation: {e}")

        self._heal_codex_config_env(ui)

    def _heal_codex_config_env(self, ui: Any = None) -> None:
        """Proactively heal the managed env block in ~/.codex/config.toml.

        ``pilot sync-env --codex-only`` collapses any duplicated / left-over
        ``[shell_environment_policy.set]`` managed region into one (the
        idempotent ``_merge_env_block``), so a config corrupted by a pre-fix
        version is repaired the moment the user updates, not lazily on the
        next Codex session start. The reactive session-start heal
        (``codex_skill_sync.py``) fires only on matcher ``"startup"`` and only
        when the license is valid, so resume-only, Codex-only, or lapsed-license
        users could otherwise keep the duplicate-key breakage that aborts Codex
        ``skills/list``.

        ``--codex-only`` keeps this scoped to the Codex config: it does NOT
        touch Claude Code settings (a Codex-only user must not get
        ~/.claude/settings.json as a side effect) and its exit code reflects the
        Codex heal, so a genuine failure is surfaced here rather than swallowed.

        Subprocesses the freshly-installed binary rather than importing launcher
        logic (package boundary). Non-fatal: a sync hiccup must never break the
        install.
        """
        pilot_bin = Path.home() / ".pilot" / "bin" / "pilot"
        if not pilot_bin.is_file():
            return

        try:
            result = subprocess.run(
                [str(pilot_bin), "sync-env", "--codex-only"],
                capture_output=True,
                text=True,
                timeout=30,
            )
        except (subprocess.SubprocessError, OSError):
            return

        if result.returncode != 0 and ui:
            detail = (result.stderr or result.stdout or "").strip().splitlines()
            reason = detail[-1] if detail else f"exit {result.returncode}"
            ui.warning(f"Could not heal ~/.codex/config.toml env block: {reason}")

    def _install_codex_hooks(self, ctx: InstallContext) -> int:
        """Install hooks.json for Codex CLI. Returns # of hook events configured."""
        codex_dir = _get_codex_config_dir()
        codex_dir.mkdir(parents=True, exist_ok=True)

        template_path = self._find_codex_hooks_template(ctx)
        if template_path is None:
            return 0

        try:
            incoming = json.loads(template_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return 0
        if not isinstance(incoming, dict):
            return 0

        return self._merge_codex_hooks(codex_dir, incoming)

    def _find_codex_hooks_template(self, ctx: InstallContext) -> Path | None:
        """Locate the codex_hooks.json template from install source."""
        if ctx.local_mode and ctx.local_repo_dir:
            candidate = ctx.local_repo_dir / "pilot" / "hooks" / "codex_hooks.json"
            if candidate.is_file():
                return candidate

        pilot_home = Path.home() / ".pilot"
        candidate = pilot_home / "hooks" / "codex_hooks.json"
        if candidate.is_file():
            return candidate

        return None

    def _merge_codex_hooks(self, codex_dir: Path, incoming: dict[str, Any]) -> int:
        """Write or merge hooks into ~/.codex/hooks.json.

        Pilot-owned entries are identified by exact signatures from the
        previous install baseline. A narrow legacy migration recognizes only
        the old managed hook/script locations; arbitrary user hooks elsewhere
        under ~/.pilot are preserved.
        Returns the number of Pilot-managed hook events present in the result.
        """
        hooks_file = codex_dir / "hooks.json"
        baseline_file = codex_dir / _CODEX_HOOKS_BASELINE_FILE
        incoming_hooks = incoming.get("hooks", {})
        if not isinstance(incoming_hooks, dict) or any(
            not isinstance(entries, list) for entries in incoming_hooks.values()
        ):
            return 0

        if not hooks_file.exists():
            hooks_file.parent.mkdir(parents=True, exist_ok=True)
            _atomic_write(hooks_file, json.dumps(incoming, indent=2) + "\n")
            _atomic_write(baseline_file, json.dumps(incoming_hooks, indent=2) + "\n")
            return len(incoming_hooks)

        try:
            existing = json.loads(hooks_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            # A malformed user file is not ours to replace. Leave it byte-for-byte
            # intact so the user can repair or recover it without losing custom hooks.
            return 0

        if not isinstance(existing, dict):
            return 0
        existing_hooks = existing.get("hooks", {})
        if not isinstance(existing_hooks, dict) or any(
            not isinstance(entries, list) for entries in existing_hooks.values()
        ):
            return 0

        baseline_hooks: dict[str, Any] | None = None
        if baseline_file.is_file():
            try:
                loaded_baseline = json.loads(baseline_file.read_text(encoding="utf-8"))
                if isinstance(loaded_baseline, dict):
                    baseline_hooks = loaded_baseline
            except (OSError, json.JSONDecodeError):
                baseline_hooks = None
        if baseline_hooks is None:
            baseline_hooks = _legacy_codex_hook_signature_baseline(existing_hooks)

        merged: dict[str, list[Any]] = {}

        # Dict insertion order makes the generated file stable across installs:
        # preserve the user's existing event order, then append new Pilot events.
        all_events = dict.fromkeys((*existing_hooks, *incoming_hooks))
        for event in all_events:
            existing_entries = existing_hooks.get(event, [])
            incoming_entries = incoming_hooks.get(event, [])

            baseline_signatures = {
                _hook_entry_signature(entry) for entry in baseline_hooks.get(event, []) if isinstance(entry, dict)
            }
            managed_commands = {
                command
                for entry in baseline_hooks.get(event, [])
                if isinstance(entry, dict)
                for command in _hook_entry_commands(entry)
            }
            managed_commands.update(
                command
                for entry in incoming_entries
                if isinstance(entry, dict)
                for command in _hook_entry_commands(entry)
            )
            user_entries: list[Any] = []
            for entry in existing_entries:
                if not isinstance(entry, dict):
                    user_entries.append(entry)
                    continue
                if _hook_entry_signature(entry) in baseline_signatures:
                    continue
                preserved = _without_hook_commands(entry, managed_commands)
                if preserved is not None:
                    user_entries.append(preserved)
            incoming_signatures = {
                _hook_entry_signature(entry) for entry in incoming_entries if isinstance(entry, dict)
            }
            merged[event] = incoming_entries + [
                entry
                for entry in user_entries
                if not isinstance(entry, dict) or _hook_entry_signature(entry) not in incoming_signatures
            ]

        result = dict(existing)
        result["hooks"] = merged
        _atomic_write(hooks_file, json.dumps(result, indent=2) + "\n")
        _atomic_write(baseline_file, json.dumps(incoming_hooks, indent=2) + "\n")
        return len(incoming_hooks)

    def _install_codex_mcp(self, ctx: InstallContext) -> int:
        """Generate MCP server config in ~/.codex/config.toml from .mcp.json.

        Returns the number of MCP servers written into the managed block.
        """
        pilot_home = Path.home() / ".pilot"
        mcp_json_path = pilot_home / ".mcp.json"
        if not mcp_json_path.is_file():
            return 0

        try:
            mcp_data = json.loads(mcp_json_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return 0

        toml_block = _mcp_json_to_toml(mcp_data)
        if not toml_block.strip():
            return 0

        codex_dir = _get_codex_config_dir()
        codex_dir.mkdir(parents=True, exist_ok=True)
        config_path = codex_dir / "config.toml"

        existing = ""
        if config_path.is_file():
            try:
                existing = config_path.read_text(encoding="utf-8")
            except OSError:
                pass

        managed_names = _managed_server_names(mcp_data)
        preserved, dropped = _clean_mcp_config(existing, managed_names)

        baseline_path = codex_dir / MCP_BASELINE_FILE
        baseline: dict[str, Any] | None = None
        if baseline_path.is_file():
            try:
                loaded = json.loads(baseline_path.read_text(encoding="utf-8"))
                baseline = loaded if isinstance(loaded, dict) else None
            except (OSError, json.JSONDecodeError):
                baseline = None

        user_owned, overwritten = _partition_dropped(dropped, toml_block, baseline)
        if ctx.ui:
            for name in sorted(user_owned):
                ctx.ui.warning(
                    f"MCP server '{name}' was modified by the user; "
                    "Pilot's update was NOT applied. Existing value preserved."
                )
            if overwritten:
                ctx.ui.warning(
                    "Replacing [mcp_servers.*] tables in ~/.codex/config.toml that sit outside the "
                    f"pilot-managed block and differ from Pilot's own: {', '.join(sorted(overwritten))} "
                    "-- the previous definitions have been overwritten. To keep a custom server, "
                    "re-add it under a different name."
                )

        if user_owned:
            # Re-home the user's tables ahead of the managed block instead of
            # dropping them: _clean_mcp_config removed them to keep Codex from
            # loading a duplicate [mcp_servers.<name>], not because they are ours.
            kept = [line for name in sorted(user_owned) for line in dropped[name]]
            preserved = preserved.rstrip("\n") + "\n" + "\n".join(kept) if preserved.strip() else "\n".join(kept)
            servers = {k: v for k, v in (mcp_data.get("mcpServers") or {}).items() if k not in user_owned}
            toml_block = _mcp_json_to_toml({"mcpServers": servers})

        managed_block = f"\n{_MCP_MARKER_START}\n{toml_block}{_MCP_MARKER_END}\n"
        final = preserved.rstrip("\n") + "\n" + managed_block if preserved.strip() else managed_block.lstrip("\n")
        try:
            tomllib.loads(final)
        except tomllib.TOMLDecodeError as e:
            # Attribute the failure: a pre-existing user syntax error needs a
            # different remediation than a bug in our own surgery/generation.
            try:
                tomllib.loads(existing)
            except tomllib.TOMLDecodeError as e_existing:
                raise _TomlStructureError(
                    "existing ~/.codex/config.toml is invalid TOML and could not be healed "
                    f"(fix it manually and re-run): {e_existing}"
                ) from e_existing
            raise _TomlStructureError(f"generated config.toml would be invalid: {e}") from e
        _atomic_write(config_path, final)
        # Record what Pilot SHIPPED, not what landed in the file: a preserved
        # user table must still read as "differs from Pilot's" on the next run,
        # or the run after this one would quietly overwrite it.
        try:
            baseline_path.write_text(json.dumps(mcp_data.get("mcpServers") or {}, indent=2) + "\n", encoding="utf-8")
        except OSError:
            pass
        return len(managed_names)

    def _install_codex_rules(self, ctx: InstallContext) -> int:
        """Install concise Codex guidance and path-specific rules.

        Current installs use ``pilot/codex/AGENTS.md`` as the global managed
        block. The longer shared rule set remains a fallback for older install
        payloads that do not yet contain the dedicated Codex source.
        """
        guidance_path = self._find_codex_guidance_source(ctx)
        rules_dir: Path | None = None
        if ctx.local_mode and ctx.local_repo_dir:
            candidate = ctx.local_repo_dir / "pilot" / "rules"
            if candidate.is_dir():
                rules_dir = candidate
        if rules_dir is None:
            pilot_home = Path.home() / ".pilot"
            candidate = pilot_home / "rules"
            if candidate.is_dir():
                rules_dir = candidate
        if rules_dir is None:
            rules_dir = _claude_rules_dir_or_none()
        if guidance_path is None and (rules_dir is None or not rules_dir.is_dir()):
            return 0

        rule_files = (
            sorted(f for f in rules_dir.iterdir() if f.suffix == ".md" and f.is_file())
            if rules_dir is not None and rules_dir.is_dir()
            else []
        )
        if guidance_path is None and not rule_files:
            return 0

        codex_dir = _get_codex_config_dir()
        codex_dir.mkdir(parents=True, exist_ok=True)

        parts: list[str] = []
        if guidance_path is not None:
            try:
                parts.append(guidance_path.read_text(encoding="utf-8").strip())
            except OSError:
                return 0
        stack_rules: list[tuple[str, list[str], str]] = []
        for rule_file in rule_files:
            try:
                content = rule_file.read_text(encoding="utf-8").strip()
            except OSError:
                continue
            globs, body = _split_rule_frontmatter(content)
            adapted = _adapt_invocation_syntax(body)
            if globs:
                stack_rules.append((rule_file.name, globs, adapted))
            elif guidance_path is None:
                parts.append(adapted)

        if not parts and not stack_rules:
            return 0

        if stack_index := self._write_codex_stack_rules(codex_dir, stack_rules):
            parts.append(stack_index)

        if guidance_path is None:
            codex_preamble = (
                "## Codex Compatibility\n\n"
                "Use the current Codex tool schema. "
                "Skill invocation: use `$skill-name` (not `/skill-name`).\n"
            )
            managed_content = codex_preamble + "\n\n" + "\n\n".join(parts)
        else:
            managed_content = "\n\n".join(parts)
        block = f"<!-- PILOT:START -->\n{managed_content}\n<!-- PILOT:END -->"

        agents_md = codex_dir / "AGENTS.md"

        if agents_md.is_file():
            try:
                existing = agents_md.read_text(encoding="utf-8")
            except OSError:
                existing = ""

            if "<!-- PILOT:START -->" in existing and "<!-- PILOT:END -->" in existing:
                start = existing.index("<!-- PILOT:START -->")
                end = existing.index("<!-- PILOT:END -->") + len("<!-- PILOT:END -->")
                if start < end:
                    final = existing[:start] + block + existing[end:]
                else:
                    final = existing.rstrip("\n") + "\n\n" + block + "\n"
            else:
                final = existing.rstrip("\n") + "\n\n" + block + "\n"
        else:
            final = block + "\n"

        _atomic_write(agents_md, final)
        return (1 + len(stack_rules)) if guidance_path is not None else len(rule_files)

    def _find_codex_guidance_source(self, ctx: InstallContext) -> Path | None:
        if getattr(ctx, "local_mode", False) is True and ctx.local_repo_dir is not None:
            candidate = ctx.local_repo_dir / "pilot" / "codex" / "AGENTS.md"
            if candidate.is_file():
                return candidate

        candidate = Path.home() / ".pilot" / "codex" / "AGENTS.md"
        return candidate if candidate.is_file() else None

    def _write_codex_stack_rules(self, codex_dir: Path, stack_rules: list[tuple[str, list[str], str]]) -> str:
        """Write path-gated rules to ~/.codex/rules/ and return their AGENTS.md index.

        Claude Code gates these on their ``paths:`` globs, so they cost nothing
        until a matching file is touched. Codex has no equivalent, and inlining
        them put every stack's standards (.NET, Blazor, Go, frontend, mobile...) in
        front of every turn regardless of the project. The index below keeps them
        discoverable at a fraction of the tokens; Codex reads the one that matches.

        Files Pilot wrote on a previous run but no longer ships are removed, so a
        renamed rule cannot leave a stale copy the index no longer points at. The
        sidecar manifest is what makes that non-destructive: anything not listed in
        it was not written by Pilot and is left alone.
        """
        rules_dir = codex_dir / "rules"
        rules_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = rules_dir / _CODEX_RULES_MANIFEST
        shipped = {name for name, _, _ in stack_rules}
        try:
            recorded = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            recorded = []
        previous = (
            {
                name
                for name in recorded
                if isinstance(name, str)
                and name not in {"", ".", ".."}
                and "/" not in name
                and "\\" not in name
            }
            if isinstance(recorded, list)
            else set()
        )
        for stale_name in previous - shipped:
            stale = rules_dir / stale_name
            if stale.is_file() or stale.is_symlink():
                stale.unlink(missing_ok=True)

        rows: list[str] = []
        managed: set[str] = set()
        for name, globs, body in sorted(stack_rules):
            target = rules_dir / name
            # Same-name user rules remain user-owned across repeated updates.
            # Do not adopt them into the manifest or replace symlink targets.
            if not target.is_symlink() and (name in previous or not target.exists()):
                _atomic_write(target, body.rstrip("\n") + "\n")
                managed.add(name)
            rows.append(f"| `{target}` | {', '.join(f'`{g}`' for g in globs)} |")
        _atomic_write(manifest_path, json.dumps(sorted(managed), indent=2) + "\n")

        if not rows:
            return ""

        return (
            "## Stack Rules (read on demand)\n\n"
            "These rules apply to specific file types, not to every task. Before writing "
            "or reviewing code that matches a pattern below, read that file and follow it. "
            "Read only the ones that match what you are working on.\n\n"
            "| Rule file | Applies to |\n|---|---|\n" + "\n".join(rows)
        )

    def _install_codex_config(self, ctx: InstallContext) -> bool:
        """Enable Pilot's Codex integration without selecting a model or effort.

        Permissions, personality, editor, warnings, network access, and document
        limits, model, and reasoning effort remain the user's Codex choices.
        Pilot requests expanded context; model discovery and context ceilings
        follow Codex's native catalog unless the user configures their own.
        """
        codex_dir = _get_codex_config_dir()
        codex_dir.mkdir(parents=True, exist_ok=True)
        config_path = codex_dir / "config.toml"

        existing = ""
        if config_path.is_file():
            try:
                existing = config_path.read_text(encoding="utf-8")
            except OSError:
                pass

        existing, changed = _retire_codex_model_catalog(existing, codex_dir)
        section_match = re.search(r"(?m)^\[", existing)
        top_level_scope = existing[: section_match.start()] if section_match else existing

        deprecated_keys = ["bypass_hook_trust"]
        for key in deprecated_keys:
            pattern = rf"(?m)^{re.escape(key)}\s*=\s*[^\n]*\n?"
            if re.search(pattern, top_level_scope):
                existing = re.sub(pattern, "", existing)
                changed = True

        existing, context_defaults_changed = _set_top_level_keys(existing, _CODEX_CONTEXT_DEFAULTS)
        changed = changed or context_defaults_changed

        if _codex_supports_context_management():
            existing, context_management_changed = _ensure_context_management_feature(existing)
        else:
            existing, context_management_changed = _remove_context_management_feature(existing)
        changed = changed or context_management_changed

        required_features = {"hooks": "true"}
        existing, features_changed = _ensure_section_keys(existing, "features", required_features)
        changed = changed or features_changed

        if _codex_supports_update_plan_config():
            # Codex 0.152.0 made its native task-progress checklist opt-in.
            # Restore it while preserving an explicit user opt-out.
            existing, update_plan_changed = _ensure_section_keys(
                existing,
                "tools.update_plan",
                {"enabled": "true"},
            )
            changed = changed or update_plan_changed

        required_tui = {
            "status_line": '["project-name", "model-with-reasoning", "branch-changes", "context-used", "task-progress", "run-state", "five-hour-limit", "weekly-limit"]',
            "status_line_use_colors": "true",
        }
        existing, tui_changed = _ensure_section_keys(existing, "tui", required_tui)
        changed = changed or tui_changed

        if changed:
            _validate_toml_structure(existing)
            _atomic_write(config_path, existing)
        return changed

    _CODEX_SUPPORTED_SKILLS = frozenset(
        {
            "spec",
            "spec-plan",
            "spec-bugfix-plan",
            "spec-implement",
            "spec-verify",
            "spec-bugfix-verify",
            "fix",
            "build",
            "prd",
            "investigate",
            "cleanup",
            "benchmark",
            "setup-rules",
            "create-skill",
        }
    )

    _CODEX_STALE_SKILLS = frozenset({"bot-boot", "bot-channel-task", "bot-defaults", "bot-heartbeat", "bot-jobs"})
    _CODEX_EXPLICIT_ONLY_SKILLS = _CODEX_EXPLICIT_ONLY_SKILL_NAMES
    # Keep in sync with pilot/hooks/codex_skill_sync.py:_SUPPORTED_REVIEW_AGENTS
    # (.claude/rules/pilot-shell-codex-skill-sync.md). Names only -- the sibling
    # `<name>-codex.md` files are companion prompt templates for `task
    # --prompt-file`, not custom agents, so they are never built.
    _CODEX_MANAGED_REVIEW_AGENTS = frozenset({"build-review", "changes-review", "spec-review"})

    def _install_codex_skills(self, ctx: InstallContext) -> int:
        """Install supported Pilot Shell skills to ~/.agents/skills/ for Codex.

        Only skills in _CODEX_SUPPORTED_SKILLS ship to Codex. Proven managed
        artifacts of retired skills are cleaned up. Returns the number of adapted SKILL.md files
        successfully written.
        """
        # Source is the ACTIVE Claude profile: with CLAUDE_CONFIG_DIR set, a
        # hardcoded ~/.claude finds nothing and Codex silently gets zero skills.
        # ~/.agents is NOT relocatable (Codex derives it from $HOME).
        agents_skills_dir = Path.home() / ".agents" / "skills"
        claude_skills_dir = self._find_codex_skills_source(ctx)
        if claude_skills_dir is None:
            _remove_orphaned_codex_skill_runtimes(agents_skills_dir, set())
            return 0

        if not claude_skills_dir.is_dir():
            return 0

        if agents_skills_dir.is_dir():
            for name in self._CODEX_STALE_SKILLS:
                stale = agents_skills_dir / name
                if stale.is_dir():
                    _remove_codex_skill_runtime(stale)

        candidates = [
            p
            for p in sorted(claude_skills_dir.iterdir())
            if p.is_dir() and (p / "manifest.json").is_file() and p.name in self._CODEX_SUPPORTED_SKILLS
        ]

        written = 0
        source_names = {skill_dir.name for skill_dir in candidates}
        for skill_dir in candidates:
            if "codex" not in _skill_targets(skill_dir):
                _remove_codex_skill_runtime(agents_skills_dir / skill_dir.name)
                continue
            try:
                codex_content = build_codex_skill_md(skill_dir)
            except Exception as e:
                if ctx.ui:
                    ctx.ui.warning(f"Failed to build SKILL.md for {skill_dir.name}: {e}")
                continue

            dest_dir = agents_skills_dir / skill_dir.name
            if _codex_skill_runtime_has_unowned_core(dest_dir):
                if ctx.ui:
                    ctx.ui.warning(
                        f"Skipped Codex skill '{skill_dir.name}': {dest_dir} already contains an unowned "
                        "SKILL.md or agents/openai.yaml. Move or rename that user skill to install Pilot's copy."
                    )
                continue
            dest_dir.mkdir(parents=True, exist_ok=True)
            ownership_manifest = dest_dir / _CODEX_SKILL_RESOURCES_MANIFEST
            if not ownership_manifest.exists():
                _atomic_write(ownership_manifest, '{"files": [], "directories": []}\n')
            _atomic_write(dest_dir / "SKILL.md", codex_content)
            _sync_codex_skill_resources(skill_dir, dest_dir)
            metadata_dir = dest_dir / "agents"
            metadata_dir.mkdir(parents=True, exist_ok=True)
            _atomic_write(metadata_dir / "openai.yaml", build_codex_skill_openai_yaml(skill_dir))
            written += 1
        _remove_orphaned_codex_skill_runtimes(agents_skills_dir, source_names)
        return written

    def _find_codex_skills_source(self, ctx: InstallContext) -> Path | None:
        if getattr(ctx, "local_mode", False) is True and ctx.local_repo_dir is not None:
            candidate = ctx.local_repo_dir / "pilot" / "skills"
            if candidate.is_dir():
                return candidate

        neutral = Path.home() / ".pilot" / "skills"
        if neutral.is_dir():
            return neutral

        try:
            fallback = get_claude_config_dir() / "skills"
        except ValueError:
            return None
        return fallback if fallback.is_dir() else None

    def _find_codex_review_agents_source(self, ctx: InstallContext) -> Path | None:
        """Locate the source markdown agents used to build Codex custom agents."""
        if getattr(ctx, "local_mode", False) is True:
            local_repo_dir = ctx.local_repo_dir
            if local_repo_dir is not None:
                candidate = local_repo_dir / "pilot" / "agents"
                if candidate.is_dir():
                    return candidate

        neutral = Path.home() / ".pilot" / "agents"
        if neutral.is_dir():
            return neutral

        try:
            candidate = get_claude_config_dir() / "agents"
        except ValueError:
            return None
        if candidate.is_dir():
            return candidate

        return None

    def _install_codex_agents(self, ctx: InstallContext) -> int:
        """Install Pilot-managed review agents as Codex custom-agent TOML files.

        Returns the number of agent files written.
        """
        codex_agents_dir = _get_codex_config_dir() / "agents"
        source_dir = self._find_codex_review_agents_source(ctx)
        if source_dir is None:
            for agent_name in self._CODEX_MANAGED_REVIEW_AGENTS:
                target = codex_agents_dir / f"{agent_name}.toml"
                if target.is_file() and _is_pilot_managed_codex_review_agent(target):
                    target.unlink(missing_ok=True)
            return 0

        codex_agents_dir.mkdir(parents=True, exist_ok=True)

        written = 0
        for agent_name in sorted(self._CODEX_MANAGED_REVIEW_AGENTS):
            source = source_dir / f"{agent_name}.md"
            target = codex_agents_dir / f"{agent_name}.toml"
            if not source.is_file():
                if target.is_file() and _is_pilot_managed_codex_review_agent(target):
                    target.unlink(missing_ok=True)
                continue
            try:
                codex_content = build_codex_review_agent_toml(source)
            except Exception as e:
                if ctx.ui:
                    ctx.ui.warning(f"Failed to build Codex agent for {agent_name}: {e}")
                continue
            if target.exists() and not _is_pilot_managed_codex_review_agent(target):
                if ctx.ui:
                    ctx.ui.warning(f"Preserving user-created Codex agent: {target}")
                continue
            _atomic_write(target, codex_content)
            written += 1
        return written


def _ensure_section_keys(
    content: str,
    section: str,
    keys: dict[str, str],
) -> tuple[str, bool]:
    """Ensure keys exist inside a ``[section]`` table, creating it if needed.

    Returns (updated_content, changed). Existing user values are preserved —
    only missing keys are added.
    """
    header = f"[{section}]"
    changed = False

    if header not in content:
        if content and not content.endswith("\n\n"):
            content = content.rstrip("\n") + "\n\n"
        lines = [header]
        for k, v in keys.items():
            lines.append(f"{k} = {v}")
        content += "\n".join(lines) + "\n"
        return content, True

    idx = content.index(header)
    end = content.index("\n", idx) + 1

    next_section = re.search(r"(?m)^\[", content[end:])
    section_end = end + next_section.start() if next_section else len(content)
    section_text = content[end:section_end]

    for key, value in keys.items():
        if not re.search(rf"(?m)^{re.escape(key)}\s*=", section_text):
            content = content[:end] + f"{key} = {value}\n" + content[end:]
            insertion_len = len(f"{key} = {value}\n")
            end += insertion_len
            section_end += insertion_len
            section_text = content[end:section_end]
            changed = True

    return content, changed


def _installed_codex_version() -> tuple[int, int, int] | None:
    """Return the first detectable CLI or desktop-bundled Codex version."""
    candidates = _codex_binary_candidates() or [Path("codex")]
    for binary in candidates:
        try:
            result = subprocess.run(
                [str(binary), "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        if result.returncode != 0:
            continue
        match = re.search(r"\b(\d+)\.(\d+)\.(\d+)\b", f"{result.stdout}\n{result.stderr}")
        if match is not None:
            return tuple(int(part) for part in match.groups())
    return None


def _codex_supports_update_plan_config() -> bool:
    """Whether Codex needs and accepts the opt-in task-progress setting."""
    version = _installed_codex_version()
    return version is not None and version >= _CODEX_UPDATE_PLAN_CONFIG_MIN_VERSION


def _codex_supports_context_management() -> bool:
    """Whether the installed Codex accepts structured feature configuration."""
    version = _installed_codex_version()
    return version is not None and version >= _CODEX_CONTEXT_MANAGEMENT_MIN_VERSION


def _remove_context_management_feature(content: str) -> tuple[str, bool]:
    """Remove structured context config that prevents legacy Codex startup."""
    original = content
    section_match = re.search(r"(?m)^\[", content)
    top_level_end = section_match.start() if section_match else len(content)
    top_level = content[:top_level_end]
    remainder = content[top_level_end:]
    top_level = re.sub(
        r"(?m)^[ \t]*features\.context_management\.experimental_mode[ \t]*=[^\r\n]*(?:\r?\n|$)",
        "",
        top_level,
    )
    content = top_level + remainder

    features_match = re.search(r"(?m)^\[features\][ \t]*(?:\r?\n|$)", content)
    if features_match is not None:
        next_section = re.search(r"(?m)^\[", content[features_match.end() :])
        features_end = features_match.end() + next_section.start() if next_section else len(content)
        features_body = content[features_match.end() : features_end]
        features_body = re.sub(
            r"(?m)^[ \t]*context_management\.experimental_mode[ \t]*=[^\r\n]*(?:\r?\n|$)",
            "",
            features_body,
        )
        features_body = re.sub(
            r"(?m)^[ \t]*context_management[ \t]*=[ \t]*\{[^\r\n]*\}[ \t]*(?:\r?\n|$)",
            "",
            features_body,
        )
        content = content[: features_match.end()] + features_body + content[features_end:]

    content = re.sub(
        r"(?ms)^\[features\.context_management\][^\r\n]*(?:\r?\n|$).*?(?=^\[|\Z)",
        "",
        content,
    )
    return content, content != original


def _ensure_context_management_feature(content: str) -> tuple[str, bool]:
    """Enable native Codex context management unless the user configured it."""
    section_match = re.search(r"(?m)^\[", content)
    top_level_scope = content[: section_match.start()] if section_match else content
    dotted_pattern = re.compile(
        r"(?m)^[ \t]*features\.context_management\.experimental_mode[ \t]*=[ \t]*"
        r"(?P<value>[^\r\n]+)(?:\r?\n)?"
    )
    dotted_match = dotted_pattern.search(top_level_scope)
    if dotted_match is not None:
        value = dotted_match.group("value").strip()
        content = content[: dotted_match.start()] + content[dotted_match.end() :]
        content, _ = _ensure_section_keys(
            content,
            "features",
            {"context_management.experimental_mode": value},
        )
        return content, True

    try:
        parsed = tomllib.loads(content)
    except tomllib.TOMLDecodeError:
        parsed = {}
    features = parsed.get("features")
    context_management = features.get("context_management") if isinstance(features, dict) else None
    if isinstance(context_management, dict) and "experimental_mode" in context_management:
        return content, False

    if "[features.context_management]" in content:
        return _ensure_section_keys(
            content,
            "features.context_management",
            {"experimental_mode": "true"},
        )

    if isinstance(context_management, dict):
        features_header = "[features]"
        features_start = content.index(features_header) + len(features_header)
        next_section = re.search(r"(?m)^\[", content[features_start:])
        features_end = features_start + next_section.start() if next_section else len(content)
        features_text = content[features_start:features_end]
        inline_pattern = re.compile(
            r"(?m)^(?P<indent>[ \t]*)context_management[ \t]*=[ \t]*"
            r"\{(?P<body>[^{}\r\n]*)\}[ \t]*$"
        )
        inline_match = inline_pattern.search(features_text)
        if inline_match is None:
            return content, False
        body = inline_match.group("body").strip()
        entries = "experimental_mode = true"
        if body:
            entries += f", {body}"
        replacement = f"{inline_match.group('indent')}context_management = {{ {entries} }}"
        start = features_start + inline_match.start()
        end = features_start + inline_match.end()
        return content[:start] + replacement + content[end:], True

    return _ensure_section_keys(
        content,
        "features",
        {"context_management.experimental_mode": "true"},
    )


def _insert_top_level_key(content: str, key: str, value: str) -> str:
    """Insert a key=value pair into the top-level scope of a TOML string.

    Inserts before the first ``[section]`` header so the key doesn't
    accidentally land inside an unrelated table.
    """
    line = f"{key} = {value}\n"
    m = re.search(r"(?m)^\[", content)
    if m:
        pos = m.start()
        prefix = content[:pos]
        if prefix and not prefix.endswith("\n"):
            prefix += "\n"
        return prefix + line + content[pos:]
    if content and not content.endswith("\n"):
        content += "\n"
    return content + line


def _set_top_level_keys(content: str, keys: dict[str, str]) -> tuple[str, bool]:
    """Set canonical values for top-level TOML keys without touching profiles."""
    changed = False
    for key, value in keys.items():
        section_match = re.search(r"(?m)^\[", content)
        scope_end = section_match.start() if section_match else len(content)
        top_level_scope = content[:scope_end]
        pattern = re.compile(rf"(?m)^[ \t]*{re.escape(key)}[ \t]*=[ \t]*[^\n]*$")
        match = pattern.search(top_level_scope)
        desired = f"{key} = {value}"

        if match is None:
            content = _insert_top_level_key(content, key, value)
            changed = True
        elif match.group(0) != desired:
            content = content[: match.start()] + desired + content[match.end() :]
            changed = True

    return content, changed


# Also hard-coded in uninstall.sh (marker_pairs + its grep gate) and
# test_uninstall_sh.py -- keep the literals in sync when editing.
# What Pilot last wrote into config.toml, as {server_name: config}. Codex CLI
# rewrites config.toml through a comment-stripping serializer, so the markers
# below cannot survive to tell Pilot's own tables from a user's hand edit. The
# baseline can: it is the same three-way-merge input ~/.claude/.pilot-mcp-baseline.json
# gives the Claude path, and it is why both agents now preserve user edits
# instead of only one of them doing so.
MCP_BASELINE_FILE = ".pilot-mcp-baseline.json"

# Exact previously shipped Pilot definitions that may pre-date the MCP
# baseline file. Treat these as Pilot-owned during one-way migrations while
# continuing to preserve any other same-name user customization.
_LEGACY_PILOT_MCP_SERVERS: dict[str, tuple[dict[str, Any], ...]] = {
    "semble": (
        {
            "command": "uvx",
            "args": ["--no-config", "--from", "semble[mcp]==0.5.5", "semble"],
        },
    ),
}

_MCP_MARKER_START = "# --- pilot-shell managed MCP servers ---"
_MCP_MARKER_END = "# --- end pilot-shell managed MCP servers ---"

# Matches the [mcp_servers.<name>] table header and ANY of its sub-tables
# (.env, .headers, ...). Name may be bare or quoted; whitespace inside the
# brackets is tolerated. No naive '#'-split: a comment after ']' simply isn't
# consumed, and quoted names containing '#' survive.
_MCP_TABLE_HEADER_RE = re.compile(r"^\[\s*mcp_servers\s*\.\s*(?:\"([^\"]+)\"|'([^']+)'|([^.\s\]\"']+))\s*[.\]]")

_TOML_HEADER_LINE_RE = re.compile(r"^\[.*\]\s*(?:#.*)?$")


def _mcp_table_name(line: str) -> str | None:
    """Return the server name when `line` is a table header of
    [mcp_servers.<name>] or any of its sub-tables, else None. Sibling of the
    env-block header check in pilot/hooks/codex_skill_sync.py."""
    m = _MCP_TABLE_HEADER_RE.match(line.strip())
    if not m:
        return None
    name = next((g for g in m.groups() if g is not None), None)
    return name or None


def _managed_server_names(mcp_data: dict[str, Any]) -> set[str]:
    """Server names Pilot will (re)write -- the single authority for which
    entries _mcp_json_to_toml emits and _clean_mcp_config strips."""
    servers = mcp_data.get("mcpServers", {})
    if not isinstance(servers, dict):
        return set()
    return {name for name, config in servers.items() if isinstance(config, dict)}


def _split_marker_lines(existing: str) -> list[str]:
    """splitlines(), additionally splitting any line that embeds a marker
    mid-line into (prefix, marker, suffix) lines. Heals the historical
    newline-loss corruption where a marker got concatenated with adjacent
    content (e.g. '# --- pilot-shell managed MCP servers ---[mcp_servers.x]'),
    which whole-line marker matching would otherwise miss entirely."""
    out: list[str] = []
    for raw in existing.splitlines():
        rest = raw
        while True:
            if rest.strip() in (_MCP_MARKER_START, _MCP_MARKER_END):
                out.append(rest.strip())
                break
            hits = [
                (idx, marker) for marker in (_MCP_MARKER_END, _MCP_MARKER_START) if (idx := rest.find(marker)) != -1
            ]
            if not hits:
                out.append(rest)
                break
            idx, marker = min(hits)
            prefix = rest[:idx]
            if prefix.strip():
                out.append(prefix)
            out.append(marker)
            rest = rest[idx + len(marker) :]
            if not rest.strip():
                break
    return out


def _clean_mcp_config(existing: str, managed_names: set[str]) -> tuple[str, dict[str, list[str]]]:
    """Strip prior pilot-shell managed MCP state from existing config.toml content.

    Returns (cleaned_content, dropped_tables): dropped_tables maps each
    managed-name table removed OUTSIDE any marker region to the exact lines
    removed for it. The caller compares that content against what Pilot is about
    to write to decide whether the removal is worth warning about; keeping the
    raw lines (rather than re-parsing the whole file) is what lets it judge each
    table independently when the file holds a duplicate it cannot parse as a
    whole. Two removal mechanisms, both required:

    - Marker regions: every well-formed START..END region is dropped whole.
      This is the only mechanism that removes tables whose names Pilot no
      longer ships (region content is Pilot-owned regardless of name). The
      forward scan is non-greedy: an orphaned START whose next marker is
      another START (or nothing) drops just the marker line, never the user
      content after it. Lone END markers are dropped as single lines.
    - Managed-name tables: any [mcp_servers.<name>] table (and its
      sub-tables) matching a name Pilot is about to (re)write is dropped
      wherever it appears. Without this, a table left outside the markers by
      a lost START marker would duplicate the freshly appended block -- a
      duplicate key/table that aborts Codex startup loading config.toml.
      The skip stops at header-shaped lines only, so multi-line values whose
      continuation happens to start with '[' don't truncate the removal.

    Line endings are normalized to LF; user bytes are otherwise preserved
    verbatim (deliberately no blank-line rewriting -- a global newline
    collapse previously corrupted multi-line TOML string values).
    """
    lines = _split_marker_lines(existing)

    cleaned: list[str] = []
    dropped: dict[str, list[str]] = {}
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if stripped == _MCP_MARKER_START:
            nxt = next(
                (j for j in range(i + 1, len(lines)) if lines[j].strip() in (_MCP_MARKER_START, _MCP_MARKER_END)),
                None,
            )
            if nxt is not None and lines[nxt].strip() == _MCP_MARKER_END:
                i = nxt + 1  # well-formed region: drop it whole
            else:
                i += 1  # orphaned START: drop the marker line, keep what follows
            continue
        if stripped == _MCP_MARKER_END:
            i += 1  # lone END marker
            continue
        name = _mcp_table_name(lines[i])
        if name is not None and name in managed_names:
            start = i
            i += 1
            while i < len(lines) and not _TOML_HEADER_LINE_RE.match(lines[i].strip()):
                i += 1
            dropped.setdefault(name, []).extend(lines[start:i])
            continue
        cleaned.append(lines[i])
        i += 1

    return "\n".join(cleaned), dropped


def _partition_dropped(
    dropped: dict[str, list[str]],
    toml_block: str,
    baseline: dict[str, Any] | None,
) -> tuple[set[str], set[str]]:
    """Split removed tables into (user_owned, overwritten).

    The markers are TOML *comments*, and Codex CLI rewrites this same
    config.toml through a serializer -- it owns [projects.*], [hooks.state.*]
    and [marketplaces.*] in there -- which drops every comment. Pilot's own
    [mcp_servers.*] tables then survive as data with no markers around them, and
    to the next install they look exactly like a hand-written override: the
    marker state alone cannot tell the two apart.

    A baseline of what Pilot last wrote can. With one, a table still equal to
    that baseline is Pilot's own and is replaced silently even when the new
    value differs -- an ordinary version bump; a table that differs is the
    user's edit, and is kept and reported, matching what the Claude path does
    with the same input. Those are `user_owned`.

    Without a baseline there is no evidence of authorship, so the older
    behaviour stands unchanged: every managed table is rewritten, and the ones
    whose content actually changes come back as `overwritten` for the warning.
    Preserving on a guess is not an option here -- removing stale managed tables
    is what repairs a config Codex would otherwise refuse to load (a duplicate
    [mcp_servers.<name>], a sub-table grafting stale keys onto a fresh server),
    and this path is the only thing performing that repair.

    Each table is parsed on its own rather than via the whole file, so a
    duplicate definition elsewhere -- the very breakage this cleanup exists to
    repair -- cannot collapse the judgement into one verdict for everything. A
    table that will not parse counts as changed: unable to tell means say
    something.
    """
    try:
        after = tomllib.loads(toml_block).get("mcp_servers", {})
    except tomllib.TOMLDecodeError:
        return (set(), set()) if baseline else (set(), set(dropped))
    if not isinstance(after, dict):
        return (set(), set()) if baseline else (set(), set(dropped))

    base_tables: dict[str, Any] = {}
    if baseline:
        try:
            parsed = tomllib.loads(_mcp_json_to_toml({"mcpServers": baseline})).get("mcp_servers", {})
        except tomllib.TOMLDecodeError:
            parsed = {}
        if isinstance(parsed, dict):
            base_tables = parsed

    legacy_tables: dict[str, tuple[Any, ...]] = {}
    for name, definitions in _LEGACY_PILOT_MCP_SERVERS.items():
        normalized: list[Any] = []
        for definition in definitions:
            try:
                parsed = tomllib.loads(_mcp_json_to_toml({"mcpServers": {name: definition}})).get("mcp_servers", {})
            except tomllib.TOMLDecodeError:
                continue
            if isinstance(parsed, dict):
                normalized.append(parsed.get(name))
        legacy_tables[name] = tuple(normalized)

    user_owned: set[str] = set()
    overwritten: set[str] = set()
    for name, table_lines in dropped.items():
        try:
            before = tomllib.loads("\n".join(table_lines)).get("mcp_servers", {})
        except tomllib.TOMLDecodeError:
            (user_owned if baseline else overwritten).add(name)
            continue
        current = before.get(name) if isinstance(before, dict) else None
        if not isinstance(before, dict):
            (user_owned if baseline else overwritten).add(name)
            continue
        if baseline:
            if current != base_tables.get(name) and current not in legacy_tables.get(name, ()):
                user_owned.add(name)
        elif current != after.get(name):
            overwritten.add(name)
    return user_owned, overwritten


def _mcp_json_to_toml(mcp_data: dict[str, Any]) -> str:
    """Convert .mcp.json mcpServers dict to TOML [mcp_servers.*] sections."""
    servers = mcp_data.get("mcpServers", {})
    if not isinstance(servers, dict):
        return ""

    lines: list[str] = []
    for name, config in servers.items():
        if not isinstance(config, dict):
            continue
        lines.append(f"[mcp_servers.{name}]")

        server_type = config.get("type", "")
        if server_type == "http" or "url" in config:
            url = config.get("url", "")
            if url:
                lines.append(f"url = {_toml_string(url)}")
        else:
            cmd = config.get("command", "")
            if cmd:
                lines.append(f"command = {_toml_string(cmd)}")
            args = config.get("args")
            if isinstance(args, list) and args:
                args_str = ", ".join(_toml_string(str(a)) for a in args)
                lines.append(f"args = [{args_str}]")

        env = config.get("env")
        if isinstance(env, dict) and env:
            lines.append("")
            lines.append(f"[mcp_servers.{name}.env]")
            for k, v in env.items():
                lines.append(f"{k} = {_toml_string(str(v))}")

        lines.append("")

    return "\n".join(lines) + "\n" if lines else ""


_PILOT_SKILL_NAMES = frozenset(
    {
        "spec",
        "spec-plan",
        "spec-bugfix-plan",
        "spec-implement",
        "spec-verify",
        "spec-bugfix-verify",
        "setup-rules",
        "create-skill",
        "prd",
        "investigate",
        "cleanup",
        "benchmark",
        "fix",
        "build",
    }
)

_SKILL_INVOCATION_RE = re.compile(
    r"(?<![a-zA-Z0-9_/])/"
    r"(" + "|".join(re.escape(s) for s in sorted(_PILOT_SKILL_NAMES, key=len, reverse=True)) + r")"
    r"(?![a-zA-Z0-9_/])"
)


def build_codex_skill_md(skill_dir: Path) -> str:
    """Build a Codex-format SKILL.md with YAML frontmatter from a decomposed skill.

    Reads the manifest.json, builds the skill content (same as Claude Code),
    extracts name/description from the orchestrator's frontmatter, prepends
    Codex-style YAML frontmatter, and adapts invocation syntax (/ → $).
    """
    from installer.skill_builder import build_skill_md

    content = build_skill_md(skill_dir)

    name, description = _extract_skill_metadata(content)
    manifest = _load_skill_manifest(skill_dir)
    description = _codex_manifest_description(manifest) or _CODEX_SKILL_DESCRIPTIONS.get(name, description)
    description = _adapt_invocation_syntax(description)

    adapted = _adapt_invocation_syntax(content)

    if adapted.startswith("---\n"):
        end = adapted.find("\n---", 3)
        if end != -1:
            adapted = adapted[end + 4 :].lstrip("\n")

    frontmatter = f"---\nname: {name}\ndescription: {description}\n---\n\n"
    return frontmatter + adapted


def build_codex_skill_openai_yaml(skill_dir: Path) -> str:
    """Build Codex UI metadata and invocation policy for a Pilot skill."""
    from installer.skill_builder import build_skill_md

    name, description = _extract_skill_metadata(build_skill_md(skill_dir))
    manifest = _load_skill_manifest(skill_dir)
    description = _codex_manifest_description(manifest, short=True) or _CODEX_SKILL_DESCRIPTIONS.get(name, description)
    description = _adapt_invocation_syntax(description)
    compact_description = " ".join(description.split())
    if len(compact_description) > 160:
        compact_description = compact_description[:157].rsplit(" ", 1)[0] + "..."

    display_name = name.replace("-", " ").title()
    implicit = (
        manifest.get("invocation") == "implicit"
        if manifest.get("version") == 2
        else name not in CodexFilesStep._CODEX_EXPLICIT_ONLY_SKILLS
    )
    return (
        "interface:\n"
        f"  display_name: {json.dumps(display_name)}\n"
        f"  short_description: {json.dumps(compact_description)}\n"
        "policy:\n"
        f"  allow_implicit_invocation: {'true' if implicit else 'false'}\n"
    )


def _load_skill_manifest(skill_dir: Path) -> dict[str, Any]:
    try:
        data = json.loads((skill_dir / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _skill_targets(skill_dir: Path) -> frozenset[str]:
    manifest = _load_skill_manifest(skill_dir)
    if manifest.get("version") != 2:
        return frozenset({"claude", "codex"})
    targets = manifest.get("targets")
    return frozenset(value for value in targets if isinstance(value, str)) if isinstance(targets, list) else frozenset()


def _codex_manifest_description(manifest: dict[str, Any], *, short: bool = False) -> str:
    platform = manifest.get("platform")
    if not isinstance(platform, dict):
        return ""
    codex = platform.get("codex")
    if not isinstance(codex, dict):
        return ""
    keys = ("short_description", "description") if short else ("description", "short_description")
    for key in keys:
        value = codex.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _is_codex_skill_runtime_resource(relative: Path, *, progressive: bool = False) -> bool:
    """Return whether a decomposed-skill path belongs in Codex's runtime copy."""
    if not relative.parts or relative.parts[0] in _CODEX_SKILL_AUTHORING_ENTRIES:
        return False
    if relative.parts[0] == "steps" and not progressive:
        return False
    # Codex's UI metadata is generated from the adapted SKILL.md. Never let a
    # source-side file replace it, but do copy other agent resources such as a
    # benchmark grader prompt.
    return relative.parts != ("agents", "openai.yaml")


def _codex_skill_runtime_inventory(skill_dir: Path) -> tuple[set[str], set[str]]:
    """Return the runtime files and directories shipped by a decomposed skill."""
    try:
        manifest = json.loads((skill_dir / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        manifest = {}
    progressive = isinstance(manifest, dict) and manifest.get("delivery") == "progressive"
    files: set[str] = set()
    directories: set[str] = set()
    for entry in sorted(skill_dir.iterdir()):
        relative = entry.relative_to(skill_dir)
        if not _is_codex_skill_runtime_resource(relative, progressive=progressive):
            continue
        candidates = [entry]
        if entry.is_dir() and not entry.is_symlink():
            candidates.extend(sorted(entry.rglob("*")))
        for candidate in candidates:
            candidate_relative = candidate.relative_to(skill_dir)
            if not _is_codex_skill_runtime_resource(candidate_relative, progressive=progressive):
                continue
            path = candidate_relative.as_posix()
            if candidate.is_dir() and not candidate.is_symlink():
                directories.add(path)
            else:
                files.add(path)
    return files, directories


def _load_codex_skill_resource_manifest(manifest_path: Path) -> tuple[set[str], set[str]]:
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set(), set()
    if not isinstance(data, dict):
        return set(), set()

    def valid_paths(key: str) -> set[str]:
        values = data.get(key)
        if not isinstance(values, list):
            return set()
        valid: set[str] = set()
        for value in values:
            if not isinstance(value, str):
                continue
            relative = Path(value)
            if relative.is_absolute() or ".." in relative.parts:
                continue
            # A previous progressive install may list step resources even when
            # the current source switched back to bundled delivery. Accept them
            # here so stale cleanup can remove those formerly-managed files.
            if _is_codex_skill_runtime_resource(relative, progressive=True):
                valid.add(relative.as_posix())
        return valid

    return valid_paths("files"), valid_paths("directories")


def _remove_stale_codex_skill_resources(
    dest_dir: Path,
    previous_files: set[str],
    previous_directories: set[str],
    current_files: set[str],
    current_directories: set[str],
) -> None:
    """Remove only resource paths recorded by an earlier Pilot installation."""
    for relative in sorted(previous_files - current_files, key=lambda path: (-path.count("/"), path)):
        target = dest_dir / relative
        try:
            if target.is_symlink() or target.is_file():
                target.unlink()
            elif target.is_dir():
                target.rmdir()
        except OSError:
            # A user-created child can keep a formerly managed directory alive.
            # Preserving that content is more important than forcing the cleanup.
            pass

    for relative in sorted(previous_directories - current_directories, key=lambda path: (-path.count("/"), path)):
        target = dest_dir / relative
        try:
            if target.is_dir() and not target.is_symlink():
                target.rmdir()
        except OSError:
            pass


def _sync_codex_skill_resources(skill_dir: Path, dest_dir: Path) -> None:
    """Mirror Pilot skill runtime resources into the adapted Codex skill.

    Decomposed-skill authoring inputs are compiled into SKILL.md and therefore
    stay out of the destination. Runtime-relative resources are copied with
    metadata intact, while a sidecar manifest makes removal of obsolete files
    deterministic and non-destructive.
    """
    manifest_path = dest_dir / _CODEX_SKILL_RESOURCES_MANIFEST
    previous_files, previous_directories = _load_codex_skill_resource_manifest(manifest_path)
    current_files, current_directories = _codex_skill_runtime_inventory(skill_dir)
    _remove_stale_codex_skill_resources(
        dest_dir,
        previous_files,
        previous_directories,
        current_files,
        current_directories,
    )

    for relative in sorted(current_directories, key=lambda value: (value.count("/"), value)):
        (dest_dir / relative).mkdir(parents=True, exist_ok=True)

    for relative in sorted(current_files):
        source = skill_dir / relative
        target = dest_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_symlink() or target.is_file():
            target.unlink()
        relative_path = Path(relative)
        if relative_path.parts[0] == "steps" and relative_path.suffix.lower() == ".md":
            adapted = _adapt_invocation_syntax(source.read_text(encoding="utf-8"))
            _atomic_write(target, adapted.rstrip("\n") + "\n")
        else:
            shutil.copy2(source, target, follow_symlinks=False)

    manifest = {
        "files": sorted(current_files),
        "directories": sorted(current_directories),
    }
    _atomic_write(manifest_path, json.dumps(manifest, indent=2) + "\n")


def _remove_codex_skill_runtime(dest_dir: Path) -> None:
    """Remove only generated artifacts when a skill no longer targets Codex."""
    manifest_path = dest_dir / _CODEX_SKILL_RESOURCES_MANIFEST
    if not manifest_path.is_file():
        return
    previous_files, previous_directories = _load_codex_skill_resource_manifest(manifest_path)
    _remove_stale_codex_skill_resources(dest_dir, previous_files, previous_directories, set(), set())
    manifest_path.unlink(missing_ok=True)
    (dest_dir / "SKILL.md").unlink(missing_ok=True)
    metadata = dest_dir / "agents" / "openai.yaml"
    metadata.unlink(missing_ok=True)
    try:
        metadata.parent.rmdir()
    except OSError:
        pass
    try:
        dest_dir.rmdir()
    except OSError:
        pass


def _codex_skill_runtime_has_unowned_core(dest_dir: Path) -> bool:
    """Return whether a same-name user skill occupies Pilot's runtime paths."""
    if (dest_dir / _CODEX_SKILL_RESOURCES_MANIFEST).is_file():
        return False
    return (dest_dir / "SKILL.md").is_file() or (dest_dir / "agents" / "openai.yaml").is_file()


def _remove_orphaned_codex_skill_runtimes(root: Path, source_names: set[str]) -> None:
    if not root.is_dir():
        return
    try:
        candidates = list(root.iterdir())
    except OSError:
        return
    for candidate in candidates:
        if candidate.name in source_names or not (candidate / _CODEX_SKILL_RESOURCES_MANIFEST).is_file():
            continue
        _remove_codex_skill_runtime(candidate)


def build_codex_review_agent_toml(agent_file: Path) -> str:
    """Build a Codex custom-agent TOML file from a Pilot review-agent markdown file."""
    content = agent_file.read_text(encoding="utf-8")
    metadata, body = _extract_agent_metadata(content)
    name = metadata.get("name") or agent_file.stem
    description = metadata.get("description") or f"Pilot {name} review agent."
    instructions = _adapt_review_agent_instructions_for_codex(body)
    return (
        "# pilot-shell managed Codex review agent\n"
        f"name = {_toml_string(name)}\n"
        f"description = {_toml_string(description)}\n"
        f"model = {_toml_string(_CODEX_REVIEW_AGENT_MODEL)}\n"
        f"developer_instructions = {_toml_string(instructions)}\n"
    )


def _split_rule_frontmatter(content: str) -> tuple[list[str], str]:
    """Split a rule's ``paths:`` frontmatter from its body.

    Returns ``(globs, body)``. A rule with no frontmatter yields ``([], content)``
    and is a *core* rule: it applies to every session and gets inlined into
    AGENTS.md. A rule that declares globs is a *stack* rule — Claude Code gates it
    on those paths natively, and Codex, which has no such mechanism, would
    otherwise carry every stack's standards in full on every turn.

    The globs are the trigger the rule already documents for itself, so they also
    serve as the AGENTS.md index entry telling Codex when to go read the file.
    """
    if not content.startswith("---\n"):
        return [], content

    end = content.find("\n---", 3)
    if end == -1:
        raise ValueError("invalid rule frontmatter: missing closing --- delimiter")

    try:
        metadata = yaml.safe_load(content[4:end]) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"invalid rule frontmatter: {exc}") from exc
    if not isinstance(metadata, dict):
        raise ValueError("invalid rule frontmatter: expected a YAML mapping")

    raw_paths = metadata.get("paths", [])
    if isinstance(raw_paths, str):
        raw_paths = [raw_paths]
    if not isinstance(raw_paths, list) or any(not isinstance(item, str) or not item.strip() for item in raw_paths):
        raise ValueError("invalid rule frontmatter: paths must be a string or non-empty string list")
    return [item.strip() for item in raw_paths], content[end + 4 :].lstrip("\n")


def _extract_agent_metadata(content: str) -> tuple[dict[str, str], str]:
    """Extract simple YAML frontmatter key/value pairs from a markdown agent."""
    if not content.startswith("---\n"):
        return {}, content

    end = content.find("\n---", 3)
    if end == -1:
        return {}, content

    metadata: dict[str, str] = {}
    for line in content[4:end].splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip().strip('"')
    return metadata, content[end + 4 :].lstrip("\n")


def _adapt_review_agent_instructions_for_codex(body: str) -> str:
    """Convert Claude Code output-file review agents into Codex final-response agents."""
    adapted = body
    adapted = adapted.replace(" (excluding the final Write)", "")
    adapted = adapted.replace(" → Write output (1)", " → final JSON response")
    adapted = re.sub(
        r"\*\*⛔ MANDATORY: Write output\.\*\*.*?(?=\n\n)",
        (
            "**⛔ MANDATORY: Return output.** Your final response MUST be the JSON object. "
            "At the tool-call budget, stop exploring and return what you have. "
            "No final JSON means the parent workflow cannot continue."
        ),
        adapted,
        flags=re.DOTALL,
    )
    adapted = re.sub(r"### (\d+)\. Write Output", r"### \1. Return Output", adapted)
    adapted = adapted.replace(
        "**Write JSON to `output_path` as your FINAL action.**", "**Return JSON as your final response.**"
    )
    adapted = adapted.replace(
        "Write JSON to `output_path` as your FINAL action.", "Return JSON as your final response."
    )
    adapted = adapted.replace("The orchestrator provides:", "The parent prompt provides:")
    adapted = adapted.replace(", `output_path`", "")
    adapted = adapted.replace("`output_path`, ", "")
    adapted = adapted.replace("`output_path`", "the parent prompt")
    adapted = adapted.replace("write what you have", "return what you have")
    adapted = adapted.replace("then write output", "then return output")
    adapted = adapted.replace("No file = orchestrator stalls.", "No final JSON = parent workflow cannot continue.")
    adapted = re.sub(r"\n{3,}", "\n\n", adapted).strip()
    return (
        "Pilot-managed Codex review agent. Return ONLY valid JSON as the final response. "
        "Do not write files, do not wrap JSON in markdown, and do not include commentary outside the JSON object.\n\n"
        + adapted
    )


def _toml_string(value: str) -> str:
    """Serialize a Python string as a TOML basic string."""
    return json.dumps(value)


def _is_pilot_managed_codex_review_agent(agent_file: Path) -> bool:
    try:
        content = agent_file.read_text(encoding="utf-8")
    except OSError:
        return False
    return "pilot-shell managed Codex review agent" in content or "Pilot-managed Codex review agent" in content


def _extract_skill_metadata(content: str) -> tuple[str, str]:
    """Extract name and description from Claude Code YAML frontmatter in skill content."""
    name = ""
    description = ""

    if content.startswith("---\n"):
        end = content.find("\n---", 3)
        if end != -1:
            fm_block = content[4:end]
            for line in fm_block.split("\n"):
                if line.startswith("name:"):
                    name = line[5:].strip()
                elif line.startswith("description:"):
                    description = line[12:].strip()

    return name or "unknown", description or ""


_CC_ONLY_RE = re.compile(
    r"<!-- CC-ONLY -->\n?.*?<!-- /CC-ONLY -->\n?",
    re.DOTALL,
)

_CODEX_BLOCK_RE = re.compile(
    r"<!-- CODEX-START\n(.*?)CODEX-END -->(?:\n?)",
    re.DOTALL,
)

_SKILL_CALL_RE = re.compile(
    r"Skill\(\s*(?:skill\s*=\s*)?['\"]([^'\"]+)['\"]\s*"
    r"(?:,\s*args\s*=\s*['\"]([^'\"]*)['\"])?\s*\)"
)

_ASK_USER_QUESTION_BLOCK_RE = re.compile(
    r"^(?P<indent>[ \t]*)AskUserQuestion\(\n(?P<body>.*?)(?=^[ \t]*\)\s*$)^[ \t]*\)\s*$",
    re.DOTALL | re.MULTILINE,
)


def _adapt_invocation_syntax(content: str) -> str:
    """Replace /skill-name with $skill-name and adapt Codex-incompatible tool references.

    Processing order:
    1. Strip ``<!-- CC-ONLY -->`` … ``<!-- /CC-ONLY -->`` blocks (CC-specific sections).
    2. Unwrap ``<!-- CODEX-START`` … ``CODEX-END -->`` blocks (Codex alternatives hidden as HTML comments).
    3. Replace ``Skill(skill='X', args='Y')`` calls with Codex skill-instruction handoffs.
    4. Replace ``/skill-name`` with ``$skill-name`` for user-facing references.
    5. Adapt questions to a permitted native structured tool or prose fallback.
    """
    adapted = _CC_ONLY_RE.sub("", content)

    adapted = _CODEX_BLOCK_RE.sub(lambda m: m.group(1), adapted)

    def _replace_skill_call(m: re.Match[str]) -> str:
        skill = m.group(1)
        args = m.group(2) or ""
        if args:
            return f"the `${skill}` skill instructions with arguments: `{args}`"
        return f"the `${skill}` skill instructions"

    adapted = _SKILL_CALL_RE.sub(_replace_skill_call, adapted)

    def _replace_ask_user_question_block(m: re.Match[str]) -> str:
        body = m.group("body").rstrip()
        return (
            f"{m.group('indent')}Use a structured question if the runtime exposes and permits one for this purpose; "
            f"otherwise ask in plain text. Preserve this prompt and its choices:\n{body}"
        )

    adapted = _ASK_USER_QUESTION_BLOCK_RE.sub(_replace_ask_user_question_block, adapted)

    adapted = _SKILL_INVOCATION_RE.sub(lambda m: "$" + m.group(1), adapted)
    adapted = adapted.replace(
        "AskUserQuestion(multiSelect: true)",
        "a structured multi-select question when the runtime exposes and permits one, otherwise a concise question in prose",
    )
    for old, new in (
        ("`AskUserQuestion` tool", "Claude structured-question tool"),
        ("AskUserQuestion tool", "Claude structured-question tool"),
        ("`AskUserQuestion` calls", "structured-question prompts"),
        ("AskUserQuestion calls", "structured-question prompts"),
        ("`AskUserQuestion` call", "structured-question prompt"),
        ("AskUserQuestion call", "structured-question prompt"),
    ):
        adapted = adapted.replace(old, new)
    adapted = adapted.replace(
        "AskUserQuestion",
        "structured question",
    )
    return adapted


def _hook_entry_signature(entry: dict[str, Any]) -> tuple[str, tuple[str, ...]]:
    matcher = entry.get("matcher") or ""
    if not isinstance(matcher, str):
        matcher = str(matcher)
    commands = sorted(
        hook["command"]
        for hook in entry.get("hooks", []) or []
        if isinstance(hook, dict) and isinstance(hook.get("command"), str)
    )
    return matcher, tuple(commands)


def _hook_entry_commands(entry: dict[str, Any]) -> tuple[str, ...]:
    return tuple(
        hook["command"]
        for hook in entry.get("hooks", []) or []
        if isinstance(hook, dict) and isinstance(hook.get("command"), str)
    )


def _without_hook_commands(entry: dict[str, Any], managed_commands: set[str]) -> dict[str, Any] | None:
    """Remove only known Pilot commands from a mixed user/Pilot entry."""
    hooks = entry.get("hooks")
    if not isinstance(hooks, list):
        return entry
    kept = [
        hook
        for hook in hooks
        if not (
            isinstance(hook, dict)
            and isinstance(hook.get("command"), str)
            and hook["command"] in managed_commands
        )
    ]
    if not kept:
        return None
    return {**entry, "hooks": kept}


def _legacy_codex_hook_signature_baseline(current_hooks: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Identify only known pre-baseline Pilot hook locations."""
    baseline: dict[str, list[dict[str, Any]]] = {}
    for event, entries in current_hooks.items():
        if not isinstance(entries, list):
            continue
        managed: list[dict[str, Any]] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            pilot_hooks = [
                hook
                for hook in entry.get("hooks", []) or []
                if isinstance(hook, dict)
                and isinstance(hook.get("command"), str)
                and (
                    "/.pilot/hooks/" in hook["command"]
                    or ("/.pilot/scripts/worker-service.cjs" in hook["command"] and " hook codex " in hook["command"])
                )
            ]
            if pilot_hooks:
                managed.append({**entry, "hooks": pilot_hooks})
        if managed:
            baseline[event] = managed
    return baseline


class _TomlStructureError(Exception):
    """Raised when generated TOML content has structural problems."""


_TOML_SECTION_RE = re.compile(r"\[[\w._-]+\]")
_TOML_QUOTED_RE = re.compile(r'"[^"]*"')


def _validate_toml_structure(content: str) -> None:
    """Validate TOML content won't cause Codex parse errors.

    Checks every line for a [section] header appearing mid-line — the
    corruption pattern that concatenates sections when newlines are lost.
    Quoted strings are blanked before matching so values like
    "semble[mcp]" don't trigger false positives.
    Raises _TomlStructureError with the offending line number and content.
    """
    for lineno, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        unquoted = _TOML_QUOTED_RE.sub("", stripped)
        match = _TOML_SECTION_RE.search(unquoted)
        if match and match.start() > 0:
            raise _TomlStructureError(f"line {lineno}: section header not at start of line: {stripped!r}")


def _atomic_write(path: Path, content: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(str(tmp), str(path))
