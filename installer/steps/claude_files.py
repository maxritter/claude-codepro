"""Claude files installation step - installs pilot directory files."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from installer.claude_paths import get_claude_app_config_path, get_claude_config_dir
from installer.context import InstallContext
from installer.downloads import (
    MAX_RETRIES,
    RETRY_BACKOFF,
    DownloadConfig,
    FileInfo,
    download_file,
    download_files_parallel,
)
from installer.platform_utils import is_claude_installed
from installer.steps.base import BaseStep
from installer.steps.config_migration import migrate_model_config
from installer.steps.settings_merge import (
    cleanup_managed_files,
    load_manifest,
    merge_app_config,
    merge_pilot_hooks,
    merge_pilot_mcp_servers,
    merge_settings,
    save_manifest,
)

SETTINGS_FILE = "settings.json"
SETTINGS_BASELINE_FILE = ".pilot-settings-baseline.json"
HOOKS_BASELINE_FILE = ".pilot-hooks-baseline.json"
MCP_BASELINE_FILE = ".pilot-mcp-baseline.json"
PILOT_MANIFEST_FILE = ".pilot-manifest.json"


REPO_URL = "https://github.com/maxritter/pilot-shell"

SKIP_PATTERNS = (
    "__pycache__",
    ".pyc",
    "/node_modules/",
    "/dist/",
    "/.vite/",
    "/coverage/",
    "/.turbo/",
    "/tests/",
    ".lock",
    "-lock.yaml",
    ".install-version",
    ".DS_Store",
)

SKIP_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".webp")


def patch_claude_paths(content: str) -> str:
    """Expand ~/.pilot/bin/ paths to absolute paths."""
    home = Path.home()
    abs_bin_path = str(home / ".pilot" / "bin") + "/"
    return content.replace('"~/.pilot/bin/', '"' + abs_bin_path)


def process_settings(settings_content: str) -> str:
    """Process settings JSON - parse and re-serialize with consistent formatting."""
    config: dict[str, Any] = json.loads(settings_content)
    return json.dumps(config, indent=2) + "\n"


def _should_skip_file(file_path: str) -> bool:
    """Check if a file should be skipped during installation."""
    if not file_path:
        return True

    if any(pattern in file_path for pattern in SKIP_PATTERNS):
        return True

    if file_path.endswith(SKIP_EXTENSIONS):
        return True
    name = Path(file_path).name
    if name == ".gitignore":
        return True
    # Plugin metadata + LSP config are dropped now that Pilot is no longer a Claude plugin.
    if name == "plugin.json" or name == ".lsp.json":
        return True

    return False


_LEGACY_HOOK_COMMAND_MARKERS = (
    "${CLAUDE_PLUGIN_ROOT}",
    "/.claude/pilot/",
)

_CODEX_ONLY_RE = re.compile(r"<!-- CODEX-START\n.*?CODEX-END -->(?:\n?)", re.DOTALL)
_CC_ONLY_RE = re.compile(r"<!-- CC-ONLY -->\n?(.*?)<!-- /CC-ONLY -->\n?", re.DOTALL)


def adapt_claude_rule_content(content: str) -> str:
    """Strip Codex-only rule blocks and unwrap Claude-only rule blocks."""
    content = _CODEX_ONLY_RE.sub("", content)
    content = _CC_ONLY_RE.sub(lambda m: m.group(1), content)
    return content


def _legacy_hook_signature_baseline(current_hooks: dict[str, Any]) -> dict[str, Any]:
    """Return a synthetic baseline containing only legacy Pilot hook entries.

    Used on first install after the ~/.claude/pilot/ migration when the real
    baseline file is missing (pre-baseline Pilot install, file restored from
    backup that excluded dotfiles, etc.). Identifies legacy Pilot entries by
    a command-string substring match — these were Pilot-shipped, so seeding
    them into the baseline lets merge_pilot_hooks remove them as stale rather
    than preserving them as user additions.
    """
    legacy: dict[str, Any] = {}
    for event_key, entries in current_hooks.items():
        if not isinstance(entries, list):
            continue
        matching = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            for hook in entry.get("hooks", []) or []:
                if not isinstance(hook, dict):
                    continue
                cmd = hook.get("command", "")
                if isinstance(cmd, str) and any(m in cmd for m in _LEGACY_HOOK_COMMAND_MARKERS):
                    matching.append(entry)
                    break
        if matching:
            legacy[event_key] = matching
    return legacy


def _categorize_file(file_path: str) -> str:
    """Determine which category a file belongs to.

    Destination map:
      - settings    → ~/.claude/settings.json
      - agents      → ~/.claude/agents/        (subagents + codex prompt templates)
      - hooks       → ~/.pilot/hooks/          (Python hook scripts + hooks.json; agent-neutral)
      - skills      → ~/.claude/skills/
      - rules       → ~/.claude/rules/
      - pilot_home  → ~/.pilot/                (scripts/, ui/, .mcp.json, claude.json, package.json)

    The settings category is matched by EXACT path — any nested file named
    `settings.json` (e.g. a hook fixture) stays in its own category to avoid
    clobbering the user's real ~/.claude/settings.json.
    """
    if file_path == "pilot/settings.json":
        return "settings"
    elif file_path.startswith("pilot/agents/"):
        return "agents"
    elif file_path.startswith("pilot/hooks/"):
        return "hooks"
    elif "/skills/" in file_path:
        return "skills"
    elif "/rules/" in file_path:
        return "rules"
    else:
        return "pilot_home"


def _clear_directory_safe(path: Path, ui: Any = None, error_msg: str = "") -> None:
    """Safely remove a directory with error handling."""
    if not path.exists():
        return
    try:
        shutil.rmtree(path)
    except (OSError, IOError) as e:
        if ui and error_msg:
            ui.warning(f"{error_msg}: {e}")


class ClaudeFilesStep(BaseStep):
    """Installs Claude Code-specific assets to ``~/.claude/``.

    Scope: ``rules`` → ``~/.claude/rules/``, ``agents`` → ``~/.claude/agents/``,
    ``settings`` → ``~/.claude/settings.json`` (three-way merged), plus the
    Claude-side post-install merges (hooks-into-settings, app config,
    Claude app config MCP block, model config migration, customization
    reapply).

    Gated on ``is_claude_installed()`` — skipped cleanly when Claude Code CLI
    is not detected on the system.

    This class also owns all the shared download/categorize/install helper
    methods used by :class:`installer.steps.pilot_files.PilotFilesStep`
    (Pilot inherits and reuses them). The reduced ``run()`` here handles only
    the Claude-targeted categories; skills, hooks, and Pilot runtime files
    are installed by ``PilotFilesStep`` first, which caches the download
    metadata in ``ctx.config`` so this step can re-use it without a second
    GitHub round-trip.
    """

    name = "claude_files"

    _CLAUDE_CATEGORIES = ("rules", "agents", "settings")

    def check(self, ctx: InstallContext) -> bool:
        """Always run — gating happens inside ``run()`` so we can emit a
        clear skip message instead of the generic 'Already complete'."""
        return False

    def run(self, ctx: InstallContext) -> None:
        """Install Claude Code-specific assets when Claude Code is detected."""
        ui = ctx.ui
        if not is_claude_installed():
            if ui:
                ui.info("Claude Code CLI not detected — skipping Claude-specific assets")
            return

        categories, config = self._get_cached_pilot_files(ctx, ui)
        if categories is None or config is None:
            return

        if ui:
            ui.status("Installing Claude Code assets...")

        claude_categories = {
            cat: files for cat, files in categories.items() if cat in self._CLAUDE_CATEGORIES and files
        }
        installed_files, file_count, failed_files = self._install_categories(claude_categories, ctx, config, ui)

        merged = list(ctx.config.get("installed_files", [])) + installed_files
        ctx.config["installed_files"] = merged

        self._merge_hooks_into_settings()
        self._merge_app_config()
        self._merge_mcp_servers_into_claude_json(ui)
        migrate_model_config(create_if_missing=True)
        self._cleanup_stale_managed_files(ctx)
        self._save_pilot_manifest(ctx)
        self._reapply_customization(ui)
        self._sync_pilot_env_vars()

        self._report_results(ui, file_count, failed_files)

    def _get_cached_pilot_files(
        self,
        ctx: InstallContext,
        ui: Any,
    ) -> tuple[dict[str, list[FileInfo]] | None, DownloadConfig | None]:
        """Return categorized files + download config from PilotFilesStep's cache.

        ``PilotFilesStep`` is contracted to run first in ``get_all_steps()`` and
        populate the cache keys. If the cache is missing we surface that
        ordering violation loudly via the install UI rather than silently
        re-downloading (which would mask the regression and double the GitHub
        round-trip on the failure path).
        """
        from installer.steps.pilot_files import (
            PILOT_FILES_CACHE_CATEGORIES_KEY,
            PILOT_FILES_CACHE_CONFIG_KEY,
        )

        categories = ctx.config.get(PILOT_FILES_CACHE_CATEGORIES_KEY)
        config = ctx.config.get(PILOT_FILES_CACHE_CONFIG_KEY)
        if categories is not None and config is not None:
            return categories, config

        if ui:
            ui.warning(
                "PilotFilesStep cache missing — ClaudeFilesStep cannot install without it. "
                "Verify get_all_steps() in installer/cli.py runs PilotFilesStep before ClaudeFilesStep."
            )
        return None, None

    def _create_download_config(self, ctx: InstallContext) -> DownloadConfig:
        """Create download configuration based on context."""
        repo_branch = "main"
        if ctx.target_version:
            if ctx.target_version.startswith("dev-"):
                repo_branch = ctx.target_version
            else:
                repo_branch = f"v{ctx.target_version}"

        repo_url = self._resolve_repo_url(repo_branch)

        return DownloadConfig(
            repo_url=repo_url,
            repo_branch=repo_branch,
            local_mode=ctx.local_mode,
            local_repo_dir=ctx.local_repo_dir,
        )

    def _resolve_repo_url(self, branch: str) -> str:
        """Return the repository URL."""
        return REPO_URL

    def _handle_no_files(self, ui: Any, config: DownloadConfig) -> None:
        """Handle case when no pilot files are found."""
        if ui:
            ui.warning("No pilot files found in repository")
            if not config.local_mode:
                ui.print("  This may be due to GitHub API rate limiting.")
                ui.print("  Try running with --local flag if you have the repo cloned.")

    def _categorize_files(self, pilot_files: list[FileInfo], ctx: InstallContext) -> dict[str, list[FileInfo]]:
        """Categorize files and filter out ones to skip."""
        categories: dict[str, list[FileInfo]] = {
            "skills": [],
            "rules": [],
            "agents": [],
            "hooks": [],
            "pilot_home": [],
            "settings": [],
        }

        for file_info in pilot_files:
            file_path = file_info.path
            if _should_skip_file(file_path):
                continue

            category = _categorize_file(file_path)
            categories[category].append(file_info)

        return categories

    def _cleanup_old_directories(
        self,
        ctx: InstallContext,
        config: DownloadConfig,
        ui: Any,
    ) -> None:
        """Clean up Pilot-managed files before reinstallation.

        Uses manifests to track which files Pilot installed. Only removes
        Pilot-managed files — user-created files in commands/, rules/,
        agents/, and hooks/ are preserved.

        Also performs the one-shot ~/.claude/pilot/ migration: the directory
        is no longer used (hooks moved to ~/.claude/hooks/, scripts/ui moved
        to ~/.pilot/, MCP+app config merged into the Claude app config).
        """
        home_claude_dir = get_claude_config_dir()
        pilot_home_dir = Path.home() / ".pilot"

        # Legacy ~/.claude/pilot/ — removed entirely. Safe because every
        # asset previously under there has a new home (or is no longer needed).
        # Runs unconditionally (even with source_is_destination) — the legacy
        # dir is always stale post-migration and never the source.
        legacy_plugin_dir = home_claude_dir / "pilot"
        self._cleanup_legacy_standards_skills(legacy_plugin_dir)
        _clear_directory_safe(legacy_plugin_dir)

        source_is_destination = (
            config.local_mode and config.local_repo_dir and config.local_repo_dir.resolve() == ctx.project_dir.resolve()
        )
        if source_is_destination:
            return

        # ~/.pilot/scripts/ and ~/.pilot/ui/ are wholly Pilot-managed (no user
        # files there by convention; the dest path is what Pilot's hooks.json
        # and MCP config point to). Clear before install so renamed/removed
        # assets don't linger. Never touch other ~/.pilot/ subdirs (bin/,
        # sessions/, config.json). Guarded by source_is_destination so a
        # developer running --local from the repo doesn't lose their working
        # ~/.pilot/scripts/ on every iteration.
        _clear_directory_safe(pilot_home_dir / "scripts")
        _clear_directory_safe(pilot_home_dir / "ui")
        _clear_directory_safe(pilot_home_dir / "hooks")
        # ~/.pilot/rules/ is the raw-rule staging area read by
        # CodexFilesStep._install_codex_rules. Cleared with the other
        # Pilot-managed dirs so renamed/removed rule files don't linger.
        _clear_directory_safe(pilot_home_dir / "rules")

        manifest_path = home_claude_dir / PILOT_MANIFEST_FILE
        if not manifest_path.exists():
            self._seed_manifest_from_existing(home_claude_dir, manifest_path)
        self._cleanup_deprecated_pilot_skills_in_home(home_claude_dir)
        cleanup_managed_files(home_claude_dir / "commands", manifest_path, "commands/")
        cleanup_managed_files(home_claude_dir / "skills", manifest_path, "skills/")
        cleanup_managed_files(home_claude_dir / "rules", manifest_path, "rules/")
        cleanup_managed_files(home_claude_dir / "agents", manifest_path, "agents/")
        # Pilot hook scripts now live under ~/.pilot/hooks/ (agent-neutral).
        # Legacy installs may still have Pilot scripts in ~/.claude/hooks/ —
        # clean those up via manifest, then clean the new location too.
        cleanup_managed_files(home_claude_dir / "hooks", manifest_path, "hooks/")
        cleanup_managed_files(pilot_home_dir / "hooks", manifest_path, "pilot_hooks/")

    def _cleanup_legacy_standards_skills(self, plugin_dir: Path) -> None:
        """Remove old standards-* skill directories from plugin skills folder.

        Standards were migrated from pilot/skills/ to pilot/rules/ with frontmatter.
        Runs unconditionally (before source_is_destination check) to clean up stale installs.
        """
        skills_dir = plugin_dir / "skills"
        if not skills_dir.exists():
            return

        for item in skills_dir.iterdir():
            if item.is_dir() and item.name.startswith("standards-"):
                _clear_directory_safe(item)

        if skills_dir.exists() and not any(skills_dir.iterdir()):
            try:
                skills_dir.rmdir()
            except (OSError, IOError):
                pass

    def _seed_manifest_from_existing(self, home_claude_dir: Path, manifest_path: Path) -> None:
        """Seed manifest from existing files for legacy upgrades.

        When upgrading from a pre-manifest Pilot version, no manifest exists yet.
        The old installer nuked these directories entirely, so all existing files
        are Pilot-managed. Seed the manifest with them so cleanup_managed_files
        can remove stale ones while future user-added files remain safe.

        Limited to ``commands`` and ``rules`` — the legacy installer never let
        users add files there, so every existing entry is Pilot's. ``skills/``
        and ``agents/`` are SHARED with user-authored content; treating
        pre-existing entries as Pilot-owned would clobber user skills on the
        first cleanup pass. Deprecated Pilot skills/agents from older versions
        are removed via ``_cleanup_deprecated_pilot_skills_in_home`` (explicit
        name list) instead.
        """
        files: set[str] = set()
        for subdir in ("commands", "rules"):
            directory = home_claude_dir / subdir
            if not directory.exists():
                continue
            for item in directory.iterdir():
                if item.name.startswith("."):
                    continue
                files.add(f"{subdir}/{item.name}")
        if files:
            save_manifest(manifest_path, files)

    # Skill / agent directories Pilot historically shipped that are no longer
    # part of the current release. On legacy upgrades these survive in
    # ~/.claude/skills/ and ~/.claude/agents/ because the manifest can't
    # distinguish them from user-authored files. Remove them by exact name
    # only — never touch a name that's not on this list.
    _DEPRECATED_PILOT_SKILL_NAMES: tuple[str, ...] = (
        "notify",
        "skill-build",
    )
    _DEPRECATED_PILOT_AGENT_FILENAMES: tuple[str, ...] = ()

    def _cleanup_deprecated_pilot_skills_in_home(self, home_claude_dir: Path) -> None:
        """Remove known-deprecated Pilot skill directories and agent files from
        ``~/.claude/skills/`` and ``~/.claude/agents/``.

        Exact-name match only. Never deletes a name not on the explicit
        deprecation list — user files are safe.
        """
        skills_dir = home_claude_dir / "skills"
        if skills_dir.exists():
            for name in self._DEPRECATED_PILOT_SKILL_NAMES:
                target = skills_dir / name
                if target.exists() and target.is_dir():
                    _clear_directory_safe(target)

        agents_dir = home_claude_dir / "agents"
        if agents_dir.exists():
            for filename in self._DEPRECATED_PILOT_AGENT_FILENAMES:
                target = agents_dir / filename
                if target.exists() and target.is_file():
                    try:
                        target.unlink()
                    except OSError:
                        pass

    def _install_categories(
        self,
        categories: dict[str, list[FileInfo]],
        ctx: InstallContext,
        config: DownloadConfig,
        ui: Any,
    ) -> tuple[list[str], int, list[str]]:
        """Install files by category."""
        installed_files: list[str] = []
        file_count = 0
        failed_files: list[str] = []

        category_names = {
            "skills": "skills",
            "rules": "standard rules",
            "agents": "agents",
            "hooks": "hooks",
            "pilot_home": "Pilot runtime files",
            "settings": "settings",
        }

        for category, file_infos in categories.items():
            if not file_infos:
                continue

            count, installed, failed = self._install_category_files(
                category, file_infos, ctx, config, ui, category_names[category]
            )
            file_count += count
            installed_files.extend(installed)
            failed_files.extend(failed)

        return installed_files, file_count, failed_files

    def _install_category_files(
        self,
        category: str,
        file_infos: list[FileInfo],
        ctx: InstallContext,
        config: DownloadConfig,
        ui: Any,
        category_display_name: str,
    ) -> tuple[int, list[str], list[str]]:
        """Install files for a single category."""
        installed: list[str] = []
        failed: list[str] = []

        def install_files() -> None:
            if category == "settings":
                for file_info in file_infos:
                    file_path = file_info.path
                    dest_file = self._get_dest_path(category, file_path, ctx)
                    success = self._install_settings(
                        file_path,
                        dest_file,
                        config,
                    )
                    if success:
                        installed.append(str(dest_file))
                    else:
                        failed.append(file_path)
                return

            dest_paths = [self._get_dest_path(category, fi.path, ctx) for fi in file_infos]
            results = download_files_parallel(file_infos, dest_paths, config)

            for file_info, dest_path, success in zip(file_infos, dest_paths, results):
                if success:
                    if category == "rules":
                        try:
                            raw_content = dest_path.read_text(encoding="utf-8")
                            dest_path.write_text(adapt_claude_rule_content(raw_content), encoding="utf-8")
                        except OSError:
                            failed.append(file_info.path)
                            continue
                    installed.append(str(dest_path))
                else:
                    failed.append(file_info.path)

        if ui:
            with ui.spinner(f"Installing {category_display_name}..."):
                install_files()
            ui.success(self._format_install_summary(category, category_display_name, file_infos))
        else:
            install_files()

        return len(installed), installed, failed

    def _format_install_summary(
        self,
        category: str,
        category_display_name: str,
        file_infos: list,
    ) -> str:
        """Summarize an install run. For skills, report skill count + file count
        separately since a single decomposed skill contains manifest.json,
        orchestrator.md, and step fragments — raw file counts mislead users.
        """
        file_count = len(file_infos)
        if category == "skills":
            skill_names: set[str] = set()
            for fi in file_infos:
                # fi.path is like "pilot/skills/<skill-name>/..."
                parts = Path(fi.path).parts
                if len(parts) >= 3 and parts[0] == "pilot" and parts[1] == "skills":
                    skill_names.add(parts[2])
            skill_count = len(skill_names)
            if skill_count:
                file_word = "file" if file_count == 1 else "files"
                return f"Installed {skill_count} skills ({file_count} {file_word})"
        return f"Installed {file_count} {category_display_name}"

    def _get_dest_path(self, category: str, file_path: str, ctx: InstallContext) -> Path:
        """Determine destination path based on category."""
        home_claude_dir = get_claude_config_dir()
        pilot_home_dir = Path.home() / ".pilot"

        if category == "skills":
            rel_path = Path(file_path).relative_to("pilot/skills")
            return home_claude_dir / "skills" / rel_path
        elif category == "rules":
            rel_path = Path(file_path).relative_to("pilot/rules")
            return home_claude_dir / "rules" / rel_path
        elif category == "agents":
            rel_path = Path(file_path).relative_to("pilot/agents")
            return home_claude_dir / "agents" / rel_path
        elif category == "hooks":
            rel_path = Path(file_path).relative_to("pilot/hooks")
            return pilot_home_dir / "hooks" / rel_path
        elif category == "pilot_home":
            rel_path = Path(file_path).relative_to("pilot")
            return pilot_home_dir / rel_path
        elif category == "settings":
            return home_claude_dir / SETTINGS_FILE
        else:
            return ctx.project_dir / file_path

    def _save_pilot_manifest(self, ctx: InstallContext) -> None:
        """Save manifest of Pilot-managed files in skills/, rules/, agents/, hooks/.

        Records filenames (relative to ~/.claude/) so the next update
        can selectively remove only Pilot's files, preserving user files.
        Files installed under ~/.pilot/ (scripts/, ui/, MCP config) are
        managed by directory clearing in _cleanup_old_directories rather
        than per-file manifest tracking.
        """
        home_claude_dir = get_claude_config_dir()
        installed = ctx.config.get("installed_files", [])

        skills_dir = home_claude_dir / "skills"
        rules_dir = home_claude_dir / "rules"
        agents_dir = home_claude_dir / "agents"
        pilot_hooks_dir = Path.home() / ".pilot" / "hooks"
        managed_files: set[str] = set()

        for filepath_str in installed:
            filepath = Path(filepath_str)
            try:
                if filepath.is_relative_to(skills_dir):
                    managed_files.add("skills/" + str(filepath.relative_to(skills_dir)))
                elif filepath.is_relative_to(rules_dir):
                    managed_files.add("rules/" + str(filepath.relative_to(rules_dir)))
                elif filepath.is_relative_to(agents_dir):
                    managed_files.add("agents/" + str(filepath.relative_to(agents_dir)))
                elif filepath.is_relative_to(pilot_hooks_dir):
                    managed_files.add("pilot_hooks/" + str(filepath.relative_to(pilot_hooks_dir)))
            except (ValueError, TypeError):
                continue

        save_manifest(home_claude_dir / PILOT_MANIFEST_FILE, managed_files)

    def _build_skill_md_files(self, ctx: InstallContext, ui: Any) -> None:
        """Generate SKILL.md for each decomposed skill by concatenating fragments in-process.

        Iterates ~/.claude/skills/*/ and builds for any skill directory containing
        manifest.json. Skills without manifest.json are skipped (legacy monolithic
        skills copied as-is during the fragment+manifest rollout window).

        Builds in-process via the vendored installer.skill_builder — keeps the
        installer independent of the pilot binary at runtime
        (.claude/rules/pilot-shell-package-boundaries.md). Failures must be fatal:
        a silent continue would leave ~/.claude/skills/<skill>/SKILL.md missing,
        breaking /spec.

        Recovery is lazy: only on BuildError do we re-download missing fragments
        and retry once. This self-heals transient download failures (flaky
        networks, proxy hiccups) without paying stat-every-fragment overhead on
        the happy path.
        """
        from installer.skill_builder import BuildError, write_skill_md
        from installer.skill_hashes import write_hash_manifest

        skills_dir = get_claude_config_dir() / "skills"
        if not skills_dir.is_dir():
            return

        decomposed = [p for p in sorted(skills_dir.iterdir()) if p.is_dir() and (p / "manifest.json").is_file()]
        if not decomposed:
            return  # nothing to build — legacy monolithic skills or no skills installed

        config = self._create_download_config(ctx)
        installed_files: list[str] = list(ctx.config.get("installed_files", []))
        owned_manifests = {Path(value).resolve() for value in installed_files if Path(value).name == "manifest.json"}

        failures: list[str] = []
        for skill_dir in decomposed:
            if (skill_dir / "manifest.json").resolve() not in owned_manifests:
                continue
            try:
                manifest_data = json.loads((skill_dir / "manifest.json").read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                manifest_data = {}
            if (
                isinstance(manifest_data, dict)
                and manifest_data.get("version") == 2
                and "claude" not in manifest_data.get("targets", [])
            ):
                (skill_dir / "SKILL.md").unlink(missing_ok=True)
                (skill_dir / "hashes.json").unlink(missing_ok=True)
                continue
            first_err: BuildError | OSError | None = None
            try:
                write_skill_md(skill_dir)
                write_hash_manifest(skill_dir)
                self._record_generated_skill_outputs(skill_dir, installed_files)
                continue
            except (BuildError, OSError) as err:
                first_err = err

            recovered = self._recover_missing_fragments(skill_dir, config, ui)
            if recovered:
                installed_files.extend(recovered)
                try:
                    write_skill_md(skill_dir)
                    write_hash_manifest(skill_dir)
                    self._record_generated_skill_outputs(skill_dir, installed_files)
                    continue
                except (BuildError, OSError) as retry_err:
                    failures.append(f"{skill_dir.name}: {retry_err}")
                    self._log_skill_dir_diagnostics(skill_dir, config, ui)
                    continue

            failures.append(f"{skill_dir.name}: {first_err}")
            self._log_skill_dir_diagnostics(skill_dir, config, ui)

        ctx.config["installed_files"] = installed_files

        if failures:
            if ui:
                for msg in failures:
                    ui.error(f"⚠ SKILL.md generation FAILED — {msg}")
            raise RuntimeError(
                "skill-build failed for "
                + str(len(failures))
                + " skill(s); aborting install before manifests are finalized. "
                "Affected: " + ", ".join(f.split(":", 1)[0] for f in failures)
            )

    @staticmethod
    def _record_generated_skill_outputs(skill_dir: Path, installed_files: list[str]) -> None:
        """Track generated Claude skill artifacts so reinstall and uninstall own them."""
        known = set(installed_files)
        for name in ("SKILL.md", "hashes.json"):
            output = skill_dir / name
            value = str(output)
            if output.is_file() and value not in known:
                installed_files.append(value)
                known.add(value)

    def _recover_missing_fragments(
        self,
        skill_dir: Path,
        config: DownloadConfig,
        ui: Any,
    ) -> list[str]:
        """Ensure all fragments referenced by manifest.json exist on disk.

        Returns a list of absolute dest paths that were successfully re-downloaded
        (empty when nothing was missing or every download failed). Missing
        fragments are re-fetched from the repository. Two-stage recovery:
        (1) the parallel-install helper `download_file`, (2) a single-threaded
        urllib fallback with expanded diagnostics so a persistent failure gives
        actionable error output (URL, HTTP status, exception type).
        """
        try:
            manifest_data = json.loads((skill_dir / "manifest.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        if not isinstance(manifest_data, dict):
            return []

        skills_dir = get_claude_config_dir() / "skills"
        required: list[str] = []
        orchestrator = manifest_data.get("orchestrator")
        if isinstance(orchestrator, str) and orchestrator:
            required.append(orchestrator)
        for step in manifest_data.get("steps", []) or []:
            if isinstance(step, dict):
                rel = step.get("file")
                if isinstance(rel, str) and rel:
                    required.append(rel)

        recovered: list[str] = []
        for rel_path in required:
            dest = skill_dir / rel_path
            if dest.is_file():
                continue

            try:
                skill_rel = skill_dir.relative_to(skills_dir)
            except ValueError:
                continue
            repo_path = f"pilot/skills/{skill_rel}/{rel_path}"

            if ui:
                ui.warning(f"Missing fragment after install: {dest} — attempting recovery")

            if download_file(repo_path, dest, config) and dest.is_file():
                recovered.append(str(dest))
                continue

            # Stage 2: single-threaded urllib fallback with diagnostics.
            if self._direct_download_with_diagnostics(repo_path, dest, config, ui):
                recovered.append(str(dest))

        return recovered

    def _direct_download_with_diagnostics(
        self,
        repo_path: str,
        dest: Path,
        config: DownloadConfig,
        ui: Any,
    ) -> bool:
        """Direct urllib download that reports URL, status, and exception on failure.

        Bypasses the thread pool entirely (useful when ThreadPoolExecutor +
        DrvFs on WSL2 is suspected), reads the full body synchronously, writes
        atomically via temp + os.replace. Returns True only when the file is on
        disk with non-zero size after the write.
        """
        import urllib.error
        import urllib.request

        from installer.downloads import _get_ssl_context

        if config.local_mode and config.local_repo_dir:
            source_file = config.local_repo_dir / repo_path
            if not source_file.is_file():
                if ui:
                    ui.error(f"  diagnostic: local source missing: {source_file}")
                return False
            try:
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(source_file.read_bytes())
                return dest.is_file() and dest.stat().st_size > 0
            except OSError as e:
                if ui:
                    ui.error(f"  diagnostic: local copy failed: {type(e).__name__}: {e}")
                return False

        file_url = f"{config.repo_url}/raw/{config.repo_branch}/{repo_path}"
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            if ui:
                ui.error(f"  diagnostic: mkdir {dest.parent} failed: {type(e).__name__}: {e}")
            return False

        # Retry transient failures (5xx CDN hiccups, network blips) before giving
        # up — a single 502 here used to abort the whole install (issue #158).
        # Mirrors download_file's backoff so the final recovery stage is at least
        # as resilient as the parallel-install path it falls back from.
        body = b""
        for attempt in range(MAX_RETRIES):
            try:
                request = urllib.request.Request(file_url)
                with urllib.request.urlopen(request, timeout=60.0, context=_get_ssl_context()) as response:
                    status = getattr(response, "status", None)
                    if status != 200:
                        if attempt < MAX_RETRIES - 1:
                            time.sleep(RETRY_BACKOFF[min(attempt, len(RETRY_BACKOFF) - 1)])
                            continue
                        if ui:
                            ui.error(f"  diagnostic: {file_url} returned HTTP {status}")
                        return False
                    body = response.read()
                break
            except urllib.error.HTTPError as e:
                # 4xx → file genuinely missing, fail fast. 5xx → CDN hiccup, retry.
                if 500 <= e.code < 600 and attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_BACKOFF[min(attempt, len(RETRY_BACKOFF) - 1)])
                    continue
                if ui:
                    ui.error(f"  diagnostic: {file_url} HTTPError {e.code} {e.reason}")
                return False
            except (urllib.error.URLError, OSError, TimeoutError) as e:
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_BACKOFF[min(attempt, len(RETRY_BACKOFF) - 1)])
                    continue
                if ui:
                    ui.error(f"  diagnostic: {file_url} {type(e).__name__}: {e}")
                return False

        if not body:
            if ui:
                ui.error(f"  diagnostic: {file_url} returned empty body")
            return False

        tmp = dest.with_suffix(dest.suffix + ".tmp")
        try:
            tmp.write_bytes(body)
            os.replace(str(tmp), str(dest))
        except OSError as e:
            if ui:
                ui.error(f"  diagnostic: write to {dest} failed: {type(e).__name__}: {e}")
            return False

        return dest.is_file() and dest.stat().st_size > 0

    def _log_skill_dir_diagnostics(
        self,
        skill_dir: Path,
        config: DownloadConfig,
        ui: Any,
    ) -> None:
        """Dump on-disk state of a failed skill plus the URLs its manifest expected.

        Runs only when skill-build fails — so the operator sees exactly what's
        on disk vs. what's missing, with the exact URL that would have been
        used. Cheap and safe to emit: a few `ui.print` lines per failure.
        """
        if not ui:
            return

        try:
            ui.print(f"  diagnostic: skill dir = {skill_dir}")
        except Exception:
            return

        try:
            entries = sorted(p.relative_to(skill_dir).as_posix() for p in skill_dir.rglob("*") if p.is_file())
            ui.print(f"  diagnostic: on-disk files ({len(entries)}):")
            for entry in entries:
                full = skill_dir / entry
                size = full.stat().st_size if full.is_file() else 0
                ui.print(f"    - {entry} ({size} bytes)")
        except OSError as e:
            ui.print(f"  diagnostic: could not list skill dir: {type(e).__name__}: {e}")

        manifest_path = skill_dir / "manifest.json"
        if not manifest_path.is_file():
            ui.print("  diagnostic: manifest.json missing from skill dir")
            return

        try:
            manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            ui.print(f"  diagnostic: manifest.json unreadable: {type(e).__name__}: {e}")
            return

        skills_dir = get_claude_config_dir() / "skills"
        try:
            skill_rel = skill_dir.relative_to(skills_dir)
        except ValueError:
            return

        required: list[str] = []
        orchestrator = manifest_data.get("orchestrator")
        if isinstance(orchestrator, str) and orchestrator:
            required.append(orchestrator)
        for step in manifest_data.get("steps", []) or []:
            if isinstance(step, dict):
                rel = step.get("file")
                if isinstance(rel, str) and rel:
                    required.append(rel)

        ui.print(f"  diagnostic: manifest expects {len(required)} fragment file(s):")
        for rel in required:
            exists = (skill_dir / rel).is_file()
            url = f"{config.repo_url}/raw/{config.repo_branch}/pilot/skills/{skill_rel}/{rel}"
            marker = "OK" if exists else "MISSING"
            ui.print(f"    [{marker}] {rel}  <- {url}")

    def _reapply_customization(self, ui: Any) -> None:
        """Re-apply customization after core file installation.

        Reads ~/.pilot/config.json for an active customization, then calls
        the pilot binary to update and re-apply it. Non-fatal: warns on
        failure but never breaks the core install.
        """
        config_path = Path.home() / ".pilot" / "config.json"
        if not config_path.is_file():
            return

        try:
            raw = json.loads(config_path.read_text())
        except (json.JSONDecodeError, OSError):
            return

        cust = raw.get("customization")
        if not isinstance(cust, dict) or not cust.get("source"):
            return

        pilot_bin = Path.home() / ".pilot" / "bin" / "pilot"
        if not pilot_bin.is_file():
            if ui:
                ui.warning("Pilot binary not found — skipping customization re-apply")
            return

        try:
            # Try update first (pulls latest from remote + applies)
            result = subprocess.run(
                [str(pilot_bin), "customize", "update", "--quiet", "--json"],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode != 0:
                # Fall back to apply from cache (no network needed)
                fallback = subprocess.run(
                    [str(pilot_bin), "customize", "apply", "--quiet", "--json"],
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                if fallback.returncode != 0 and ui:
                    ui.error(
                        f"⚠ Customization reapply FAILED (update: {result.returncode}, "
                        f"apply: {fallback.returncode}) — your custom workflow may be broken. "
                        f"Run `pilot customize status` after install."
                    )
        except (subprocess.SubprocessError, OSError) as e:
            if ui:
                ui.error(
                    f"⚠ Customization reapply FAILED: {e} — your custom workflow may be broken. "
                    f"Run `pilot customize status` after install."
                )

    def _sync_pilot_env_vars(self) -> None:
        """Sync Pilot env vars into ~/.claude/settings.json post-install.

        Subprocesses the freshly-installed binary (`pilot sync-env`) rather than
        importing launcher logic across the package boundary. On root/container
        hosts this writes IS_SANDBOX=1 so a directly-launched
        `claude --dangerously-skip-permissions` clears Claude Code's root guard
        (issue #154); on native hosts it just refreshes the PILOT_* toggles.
        Non-fatal — a settings hiccup must never break the install.
        """
        pilot_bin = Path.home() / ".pilot" / "bin" / "pilot"
        if not pilot_bin.is_file():
            return

        try:
            subprocess.run(
                [str(pilot_bin), "sync-env"],
                capture_output=True,
                text=True,
                timeout=30,
            )
        except (subprocess.SubprocessError, OSError):
            pass

    def _make_scripts_executable(self, scripts_dir: Path) -> None:
        """Make .cjs script files executable."""
        if not scripts_dir.exists():
            return

        for script in scripts_dir.glob("*.cjs"):
            try:
                current_mode = script.stat().st_mode
                script.chmod(current_mode | 0o111)
            except (OSError, IOError):
                pass

    def _merge_hooks_into_settings(self) -> None:
        """Merge Pilot's hooks bundle into ~/.claude/settings.json.

        Reads the installed hooks.json (at ~/.pilot/hooks/hooks.json with
        absolute $HOME/.pilot/hooks/ and $HOME/.pilot/scripts/ paths — bash
        expands $HOME natively when Claude Code shells out, so no install-time
        path patching is needed). Merges the `hooks` dict into
        ~/.claude/settings.json using `merge_pilot_hooks`, which preserves
        user-added hook entries by signature membership in the dedicated
        `.pilot-hooks-baseline.json`.
        """
        claude_dir = get_claude_config_dir()
        pilot_home_dir = Path.home() / ".pilot"
        hooks_json_path = pilot_home_dir / "hooks" / "hooks.json"
        if not hooks_json_path.exists():
            return

        try:
            incoming_data = json.loads(hooks_json_path.read_text())
        except (json.JSONDecodeError, OSError, IOError):
            return

        incoming_hooks = incoming_data.get("hooks", {})
        if not isinstance(incoming_hooks, dict):
            return

        settings_path = claude_dir / SETTINGS_FILE
        try:
            settings: dict[str, Any] = json.loads(settings_path.read_text()) if settings_path.exists() else {}
        except (json.JSONDecodeError, OSError, IOError):
            settings = {}

        current_hooks = settings.get("hooks") or {}
        if not isinstance(current_hooks, dict):
            current_hooks = {}

        baseline_path = claude_dir / HOOKS_BASELINE_FILE
        baseline_hooks: dict[str, Any] | None = None
        if baseline_path.exists():
            try:
                baseline_hooks = json.loads(baseline_path.read_text())
            except (json.JSONDecodeError, OSError, IOError):
                baseline_hooks = None

        # Legacy upgrade: pre-baseline Pilot versions left hook entries in
        # settings.json with absolute paths under ~/.claude/pilot/hooks/ or
        # literal ${CLAUDE_PLUGIN_ROOT} strings. Without a baseline, merge would
        # treat them as user-added and preserve them alongside the new entries,
        # leaving the user with broken duplicates. Seed a synthetic baseline
        # from any current entry whose command references the legacy paths so
        # merge_pilot_hooks identifies and replaces them.
        if baseline_hooks is None and current_hooks:
            baseline_hooks = _legacy_hook_signature_baseline(current_hooks)

        try:
            merged = merge_pilot_hooks(current_hooks, incoming_hooks, baseline_hooks)
        except ValueError as e:
            # Defensive guard: duplicate hook signature in shipped hooks.json
            # (e.g. corrupted download, hand-edit). Skip the merge so we don't
            # crash the whole install. The reviewer audit in spec-verify
            # catches the upstream cause; here we degrade gracefully.
            # Surface via stderr so the user sees it even when no UI is wired —
            # otherwise settings.json silently retains stale entries from the
            # previous install and produces ENOENT noise at every hook event.
            print(f"WARN: skipping hook merge due to {e}", file=sys.stderr)
            return

        if merged:
            settings["hooks"] = merged
        elif "hooks" in settings:
            del settings["hooks"]

        try:
            settings_path.parent.mkdir(parents=True, exist_ok=True)
            settings_path.write_text(json.dumps(settings, indent=2) + "\n")
        except (OSError, IOError):
            return

        try:
            baseline_path.write_text(json.dumps(incoming_hooks, indent=2) + "\n")
        except (OSError, IOError):
            pass

    def _merge_mcp_servers_into_claude_json(self, ui: Any) -> None:
        """Merge Pilot's MCP servers into the Claude app config's `mcpServers` key.

        The app config is `~/.claude.json` by default, or
        `$CLAUDE_CONFIG_DIR/.claude.json` when that variable is set - see
        `get_claude_app_config_path`. Uses value-aware merge: user-added AND
        user-modified Pilot servers are preserved (with warnings to UI). Pilot's
        baseline of installed servers is stored in `.pilot-claude-baseline.json`
        `mcpServers` so uninstall and subsequent re-installs can identify
        Pilot-owned entries.
        """
        claude_dir = get_claude_config_dir()
        mcp_template = Path.home() / ".pilot" / ".mcp.json"
        if not mcp_template.exists():
            return

        try:
            incoming_data = json.loads(mcp_template.read_text())
        except (json.JSONDecodeError, OSError, IOError):
            return

        incoming_servers = incoming_data.get("mcpServers", {})
        if not isinstance(incoming_servers, dict):
            return

        claude_json_path = get_claude_app_config_path()
        try:
            claude_json: dict[str, Any] = json.loads(claude_json_path.read_text()) if claude_json_path.exists() else {}
        except (json.JSONDecodeError, OSError, IOError):
            claude_json = {}

        current_servers = claude_json.get("mcpServers") or {}
        if not isinstance(current_servers, dict):
            current_servers = {}

        # Use a DEDICATED baseline file (NOT .pilot-claude-baseline.json) —
        # _merge_app_config overwrites the claude-baseline on every install,
        # which would wipe our mcpServers and misclassify Pilot-owned servers
        # as user additions on the next run. The dedicated file mirrors the
        # .pilot-hooks-baseline.json pattern from Task 1.
        baseline_path = claude_dir / MCP_BASELINE_FILE
        baseline_servers: dict[str, Any] | None = None
        if baseline_path.exists():
            try:
                baseline_data = json.loads(baseline_path.read_text())
                if isinstance(baseline_data, dict):
                    baseline_servers = baseline_data
            except (json.JSONDecodeError, OSError, IOError):
                baseline_servers = None

        merged, warnings = merge_pilot_mcp_servers(current_servers, incoming_servers, baseline_servers)
        if ui is not None:
            for w in warnings:
                try:
                    ui.warning(w)
                except Exception:
                    pass

        if merged:
            claude_json["mcpServers"] = merged
        elif "mcpServers" in claude_json:
            del claude_json["mcpServers"]

        try:
            claude_json_path.write_text(json.dumps(claude_json, indent=2) + "\n")
        except (OSError, IOError):
            return

        try:
            baseline_path.parent.mkdir(parents=True, exist_ok=True)
            baseline_path.write_text(json.dumps(incoming_servers, indent=2) + "\n")
        except (OSError, IOError):
            pass

    def _merge_app_config(self) -> None:
        """Merge app-level preferences from pilot/claude.json into the Claude app config.

        Target is `~/.claude.json` by default, or `$CLAUDE_CONFIG_DIR/.claude.json`
        when that variable is set - see `get_claude_app_config_path`.

        Uses three-way merge with baseline to preserve user customizations.
        Reads the installed claude.json template and merges its keys into the
        user's app config. Preserves all existing app state (projects,
        oauthAccount, caches, etc.) - only sets/updates keys defined in the template.
        """
        template_path = Path.home() / ".pilot" / "claude.json"
        if not template_path.exists():
            return

        claude_json_path = get_claude_app_config_path()
        baseline_path = get_claude_config_dir() / ".pilot-claude-baseline.json"

        try:
            source = json.loads(template_path.read_text())
        except (json.JSONDecodeError, OSError, IOError):
            return

        try:
            target = json.loads(claude_json_path.read_text()) if claude_json_path.exists() else {}
        except (json.JSONDecodeError, OSError, IOError):
            target = {}

        baseline: dict[str, Any] | None = None
        if baseline_path.exists():
            try:
                baseline = json.loads(baseline_path.read_text())
            except (json.JSONDecodeError, OSError, IOError):
                baseline = None

        patched = merge_app_config(target, source, baseline)
        if patched is not None:
            try:
                claude_json_path.write_text(json.dumps(patched, indent=2) + "\n")
            except (OSError, IOError):
                pass

        try:
            baseline_path.parent.mkdir(parents=True, exist_ok=True)
            baseline_path.write_text(json.dumps(source, indent=2) + "\n")
        except (OSError, IOError):
            pass

    def _cleanup_stale_managed_files(self, ctx: InstallContext) -> None:
        """Remove stale Pilot-managed files not present in this installation.

        Only removes files that Pilot previously installed (tracked in manifest)
        but are no longer part of the current installation. User-created files
        are never touched. Handles rules/, skills/, and legacy commands/ entries.
        """
        home_claude_dir = get_claude_config_dir()
        manifest_path = home_claude_dir / PILOT_MANIFEST_FILE
        previous_managed = load_manifest(manifest_path)
        installed = {Path(p).resolve() for p in ctx.config.get("installed_files", [])}

        for entry in previous_managed:
            # The neutral tree mirrors these manifest-owned sources. Retire
            # only the recorded files; ~/.pilot/bot/JOBS.yaml is user data.
            parts = Path(entry).parts
            if (
                len(parts) >= 3
                and parts[0] == "skills"
                and parts[1] in {"bot-boot", "bot-channel-task", "bot-defaults", "bot-heartbeat", "bot-jobs"}
                and all(part not in {".", ".."} for part in parts)
            ):
                neutral_root = Path.home() / ".pilot"
                neutral_file = neutral_root / entry
                try:
                    has_alias = any((neutral_root / Path(*parts[:i])).is_symlink() for i in range(1, len(parts) + 1))
                    if (
                        not has_alias
                        and neutral_file.resolve().is_relative_to(neutral_root.resolve())
                        and neutral_file.is_file()
                    ):
                        neutral_file.unlink()
                except OSError:
                    pass
            file_path = home_claude_dir / entry
            if file_path.exists() and file_path.resolve() not in installed:
                try:
                    file_path.unlink()
                    parent = file_path.parent
                    if parent != home_claude_dir and parent.exists() and not any(parent.iterdir()):
                        parent.rmdir()
                except (OSError, IOError):
                    pass

    def _report_results(self, ui: Any, file_count: int, failed_files: list[str]) -> None:
        """Report installation results."""
        if not ui:
            return

        if file_count > 0:
            ui.success(f"Installed {file_count} pilot files")
        else:
            ui.warning("No pilot files were installed")

        if failed_files:
            ui.warning(f"Failed to download {len(failed_files)} files")
            for failed in failed_files[:5]:
                ui.print(f"  - {failed}")
            if len(failed_files) > 5:
                ui.print(f"  ... and {len(failed_files) - 5} more")

    def _install_settings(
        self,
        source_path: str,
        dest_path: Path,
        config: DownloadConfig,
    ) -> bool:
        """Download, merge, and install settings to ~/.claude/settings.json.

        Uses three-way merge to preserve user customizations:
        - baseline (~/.claude/.pilot-settings-baseline.json) = what Pilot installed last time
        - current (~/.claude/settings.json) = what's on disk now (may have user changes)
        - incoming (downloaded settings.json) = new Pilot settings
        """
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            temp_file = Path(tmpdir) / "settings.json"
            if not download_file(source_path, temp_file, config):
                return False

            try:
                raw_content = temp_file.read_text()
                processed_content = patch_claude_paths(process_settings(raw_content))
                incoming: dict[str, Any] = json.loads(processed_content)

                dest_path.parent.mkdir(parents=True, exist_ok=True)
                baseline_path = dest_path.parent / SETTINGS_BASELINE_FILE

                current: dict[str, Any] | None = None
                baseline: dict[str, Any] | None = None

                if dest_path.exists():
                    try:
                        current = json.loads(dest_path.read_text())
                    except (json.JSONDecodeError, OSError, IOError):
                        current = None

                if baseline_path.exists():
                    try:
                        baseline = json.loads(baseline_path.read_text())
                    except (json.JSONDecodeError, OSError, IOError):
                        baseline = None

                if current is not None:
                    merged = merge_settings(baseline, current, incoming)
                else:
                    merged = incoming

                dest_path.write_text(json.dumps(merged, indent=2) + "\n")

                baseline_path.write_text(json.dumps(incoming, indent=2) + "\n")

                return True
            except (json.JSONDecodeError, OSError, IOError):
                return False
