"""SessionStart hook: rebuild Codex SKILL.md files from CC skill sources.

Runs on every session start for both Claude Code (native async) and Codex
(through Pilot's detached compatibility dispatcher).
If the license is invalid or deactivated, deletes built SKILL.md files so
unlicensed users cannot invoke the skills.

The build logic is self-contained (no launcher/installer imports) to respect
the package boundary. It replicates the same transformations as
``installer.steps.codex_files.build_codex_skill_md``:
  1. Concatenate orchestrator + steps from manifest.json
  2. Strip ``<!-- CC-ONLY -->`` blocks
  3. Unwrap ``<!-- CODEX-START ... CODEX-END -->`` blocks
  4. Transform ``Skill()`` calls to Codex skill-instruction handoffs
  5. Replace ``/skill-name`` with ``$skill-name``
  6. Adapt questions to native structured tools with a prose fallback
  7. Prepend Codex YAML frontmatter
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _lib.util import claude_config_dir, pilot_owned_skill_names  # noqa: E402

_SUPPORTED_SKILLS = frozenset(
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

_SKILL_DESCRIPTIONS = {
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

_EXPLICIT_ONLY_SKILLS = frozenset({"spec", "build", "fix", "prd", "investigate", "cleanup"})

# Keep in sync with installer/steps/codex_files.py:_CODEX_MANAGED_REVIEW_AGENTS
# (.claude/rules/pilot-shell-codex-skill-sync.md). Names only -- the sibling
# `<name>-codex.md` files are companion prompt templates for `task
# --prompt-file`, not custom agents, so they are never built.
_SUPPORTED_REVIEW_AGENTS = frozenset({"build-review", "changes-review", "spec-review"})
_CODEX_REVIEW_AGENT_MODEL = "codex-auto-review"
_SKILL_RESOURCES_MANIFEST = ".pilot-resources.json"
_SKILL_AUTHORING_ENTRIES = frozenset(
    {"manifest.json", "orchestrator.md", "tests", "SKILL.md", _SKILL_RESOURCES_MANIFEST}
)

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


def _get_codex_config_dir() -> Path:
    env_dir = os.environ.get("CODEX_HOME")
    if env_dir:
        path = Path(env_dir)
        if not path.is_absolute():
            raise ValueError(f"CODEX_HOME must be an absolute path, got: {env_dir}")
        return path
    return Path.home() / ".codex"


_CC_ONLY_RE = re.compile(r"<!-- CC-ONLY -->\n?.*?<!-- /CC-ONLY -->\n?", re.DOTALL)
_CODEX_BLOCK_RE = re.compile(r"<!-- CODEX-START\n(.*?)CODEX-END -->(?:\n?)", re.DOTALL)
_SKILL_CALL_RE = re.compile(
    r"Skill\(\s*(?:skill\s*=\s*)?['\"]([^'\"]+)['\"]\s*"
    r"(?:,\s*args\s*=\s*['\"]([^'\"]*)['\"])?\s*\)"
)

_ASK_USER_QUESTION_BLOCK_RE = re.compile(
    r"^(?P<indent>[ \t]*)AskUserQuestion\(\n(?P<body>.*?)(?=^[ \t]*\)\s*$)^[ \t]*\)\s*$",
    re.DOTALL | re.MULTILINE,
)


def _check_license() -> bool | None:
    pilot_bin = Path.home() / ".pilot" / "bin" / "pilot"
    if not pilot_bin.is_file():
        return True
    try:
        result = subprocess.run(
            [str(pilot_bin), "verify", "--json"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        data = json.loads(result.stdout)
        return data.get("valid", False)
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError, ValueError):
        return None


def _canonicalize(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.split("\n")]
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _build_progressive_index(steps: list[dict[str, object]]) -> str:
    lines = [
        "## Required phase resources",
        "",
        "Follow these phases in order. Each referenced file is part of this skill's contract; "
        "read it at the named point rather than loading every phase up front.",
        "",
    ]
    for index, step in enumerate(steps, start=1):
        lines.append(
            f"{index}. **{step['id']}** — Read `{step['file']}` completely, then execute this phase before "
            "continuing to the next one."
        )
    return "\n".join(lines)


def _safe_skill_path(skill_dir: Path, value: object) -> Path | None:
    """Resolve one manifest path without allowing traversal or symlink escape."""
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value or ":" in value:
        return None
    relative = Path(value)
    if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
        return None
    try:
        root = skill_dir.resolve()
        candidate = (skill_dir / relative).resolve()
    except (OSError, RuntimeError):
        return None
    return candidate if candidate.is_relative_to(root) else None


def _build_skill(skill_dir: Path) -> str | None:
    manifest_path = skill_dir / "manifest.json"
    if not manifest_path.is_file():
        return None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    orch_path = _safe_skill_path(skill_dir, manifest.get("orchestrator", "orchestrator.md"))
    if orch_path is None or not orch_path.is_file():
        return None

    parts = [orch_path.read_text(encoding="utf-8")]
    steps = manifest.get("steps", [])
    if not isinstance(steps, list):
        return None
    for step in steps:
        if not isinstance(step, dict) or not isinstance(step.get("file"), str):
            return None
        step_path = _safe_skill_path(skill_dir, step["file"])
        if step_path is None or not step_path.is_file():
            return None
        if manifest.get("delivery", "bundled") == "bundled":
            parts.append(step_path.read_text(encoding="utf-8"))

    if manifest.get("delivery") == "progressive":
        parts.append(_build_progressive_index(steps))

    return _canonicalize("\n\n".join(parts))


def _is_runtime_resource(relative: Path, *, progressive: bool) -> bool:
    if not relative.parts or relative.parts[0] in _SKILL_AUTHORING_ENTRIES:
        return False
    if relative.parts[0] == "steps" and not progressive:
        return False
    return relative.parts != ("agents", "openai.yaml")


def _runtime_inventory(skill_dir: Path) -> tuple[set[str], set[str]]:
    try:
        manifest = json.loads((skill_dir / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        manifest = {}
    progressive = isinstance(manifest, dict) and manifest.get("delivery") == "progressive"
    files: set[str] = set()
    directories: set[str] = set()
    for entry in sorted(skill_dir.iterdir()):
        candidates = [entry]
        if entry.is_dir() and not entry.is_symlink():
            candidates.extend(sorted(entry.rglob("*")))
        for candidate in candidates:
            relative = candidate.relative_to(skill_dir)
            if not _is_runtime_resource(relative, progressive=progressive):
                continue
            value = relative.as_posix()
            if candidate.is_dir() and not candidate.is_symlink():
                directories.add(value)
            else:
                files.add(value)
    return files, directories


def _load_resource_manifest(path: Path) -> tuple[set[str], set[str]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set(), set()
    if not isinstance(data, dict):
        return set(), set()

    def values(key: str) -> set[str]:
        raw = data.get(key)
        if not isinstance(raw, list):
            return set()
        result: set[str] = set()
        for value in raw:
            if not isinstance(value, str):
                continue
            relative = Path(value)
            if relative.is_absolute() or ".." in relative.parts:
                continue
            if _is_runtime_resource(relative, progressive=True):
                result.add(relative.as_posix())
        return result

    return values("files"), values("directories")


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    os.replace(str(temporary), str(path))


def _sync_skill_resources(skill_dir: Path, dest: Path) -> None:
    manifest_path = dest / _SKILL_RESOURCES_MANIFEST
    previous_files, previous_directories = _load_resource_manifest(manifest_path)
    current_files, current_directories = _runtime_inventory(skill_dir)

    for relative in sorted(previous_files - current_files, key=lambda value: (-value.count("/"), value)):
        target = dest / relative
        try:
            if target.is_file() or target.is_symlink():
                target.unlink()
        except OSError:
            pass
    for relative in sorted(previous_directories - current_directories, key=lambda value: (-value.count("/"), value)):
        try:
            (dest / relative).rmdir()
        except OSError:
            pass

    for relative in sorted(current_directories, key=lambda value: (value.count("/"), value)):
        (dest / relative).mkdir(parents=True, exist_ok=True)
    for relative in sorted(current_files):
        source = skill_dir / relative
        target = dest / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_file() or target.is_symlink():
            target.unlink()
        relative_path = Path(relative)
        if relative_path.parts[0] == "steps" and relative_path.suffix.lower() == ".md":
            _atomic_write(target, _adapt(source.read_text(encoding="utf-8")).rstrip("\n") + "\n")
        else:
            shutil.copy2(source, target, follow_symlinks=False)

    _atomic_write(
        manifest_path,
        json.dumps({"files": sorted(current_files), "directories": sorted(current_directories)}, indent=2) + "\n",
    )


def _extract_metadata(content: str) -> tuple[str, str]:
    if content.startswith("---\n"):
        end = content.find("\n---", 3)
        if end != -1:
            fm = content[4:end]
            name = desc = ""
            for line in fm.split("\n"):
                if line.startswith("name:"):
                    name = line[5:].strip()
                elif line.startswith("description:"):
                    desc = line[12:].strip()
            return name or "unknown", desc
    return "unknown", ""


def _adapt(content: str) -> str:
    adapted = _CC_ONLY_RE.sub("", content)
    adapted = _CODEX_BLOCK_RE.sub(lambda m: m.group(1), adapted)

    def _replace_skill_call(m: re.Match[str]) -> str:
        skill = m.group(1)
        args = m.group(2) or ""
        if args:
            return f"the `${skill}` skill instructions with arguments: `{args}`"
        return f"the `${skill}` skill instructions"

    adapted = _SKILL_CALL_RE.sub(_replace_skill_call, adapted)
    adapted = _ASK_USER_QUESTION_BLOCK_RE.sub(
        lambda m: (
            f"{m.group('indent')}Use a structured question if the runtime exposes and permits one for this purpose; "
            "otherwise ask in plain text. Preserve this prompt and its choices:\n"
            f"{m.group('body').rstrip()}"
        ),
        adapted,
    )
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


def _build_codex_skill(skill_dir: Path) -> str | None:
    content = _build_skill(skill_dir)
    if content is None:
        return None
    name, desc = _extract_metadata(content)
    manifest = _load_skill_metadata(skill_dir)
    desc = _manifest_codex_description(manifest) or _SKILL_DESCRIPTIONS.get(name, desc)
    desc = _adapt(desc)
    adapted = _adapt(content)
    if adapted.startswith("---\n"):
        end = adapted.find("\n---", 3)
        if end != -1:
            adapted = adapted[end + 4 :].lstrip("\n")
    return f"---\nname: {name}\ndescription: {desc}\n---\n\n{adapted}"


def _build_openai_yaml(skill_dir: Path) -> str | None:
    content = _build_skill(skill_dir)
    if content is None:
        return None
    name, description = _extract_metadata(content)
    manifest = _load_skill_metadata(skill_dir)
    description = _manifest_codex_description(manifest, short=True) or _SKILL_DESCRIPTIONS.get(name, description)
    description = _adapt(description)
    compact_description = " ".join(description.split())
    if len(compact_description) > 160:
        compact_description = compact_description[:157].rsplit(" ", 1)[0] + "..."
    display_name = name.replace("-", " ").title()
    implicit = (
        manifest.get("invocation") == "implicit" if manifest.get("version") == 2 else name not in _EXPLICIT_ONLY_SKILLS
    )
    return (
        "interface:\n"
        f"  display_name: {json.dumps(display_name)}\n"
        f"  short_description: {json.dumps(compact_description)}\n"
        "policy:\n"
        f"  allow_implicit_invocation: {'true' if implicit else 'false'}\n"
    )


def _load_skill_metadata(skill_dir: Path) -> dict[str, object]:
    try:
        data = json.loads((skill_dir / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _manifest_codex_description(manifest: dict[str, object], *, short: bool = False) -> str:
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


def _skill_targets(skill_dir: Path) -> frozenset[str]:
    manifest = _load_skill_metadata(skill_dir)
    if manifest.get("version") != 2:
        return frozenset({"claude", "codex"})
    targets = manifest.get("targets")
    return frozenset(value for value in targets if isinstance(value, str)) if isinstance(targets, list) else frozenset()


def _remove_skill_runtime(dest: Path) -> None:
    manifest_path = dest / _SKILL_RESOURCES_MANIFEST
    if not manifest_path.is_file():
        return
    previous_files, previous_directories = _load_resource_manifest(manifest_path)
    for relative in sorted(previous_files, key=lambda value: (-value.count("/"), value)):
        target = dest / relative
        try:
            if target.is_file() or target.is_symlink():
                target.unlink()
        except OSError:
            pass
    for relative in sorted(previous_directories, key=lambda value: (-value.count("/"), value)):
        try:
            (dest / relative).rmdir()
        except OSError:
            pass
    manifest_path.unlink(missing_ok=True)
    (dest / "SKILL.md").unlink(missing_ok=True)
    metadata = dest / "agents" / "openai.yaml"
    metadata.unlink(missing_ok=True)
    try:
        metadata.parent.rmdir()
    except OSError:
        pass
    try:
        dest.rmdir()
    except OSError:
        pass


def _remove_orphaned_skill_runtimes(root: Path, source_names: set[str]) -> None:
    if not root.is_dir():
        return
    try:
        candidates = list(root.iterdir())
    except OSError:
        return
    for candidate in candidates:
        if candidate.name in source_names or not (candidate / _SKILL_RESOURCES_MANIFEST).is_file():
            continue
        _remove_skill_runtime(candidate)


def _build_codex_review_agent(agent_file: Path) -> str | None:
    """Build a Codex custom-agent TOML file from a Pilot review-agent markdown file."""
    if not agent_file.is_file():
        return None
    try:
        content = agent_file.read_text(encoding="utf-8")
    except OSError:
        return None
    metadata, body = _extract_agent_metadata(content)
    name = metadata.get("name") or agent_file.stem
    description = metadata.get("description") or f"Pilot {name} review agent."
    instructions = _adapt_review_agent_instructions(body)
    return (
        "# pilot-shell managed Codex review agent\n"
        f"name = {_toml_string(name)}\n"
        f"description = {_toml_string(description)}\n"
        f"model = {_toml_string(_CODEX_REVIEW_AGENT_MODEL)}\n"
        f"developer_instructions = {_toml_string(instructions)}\n"
    )


def _extract_agent_metadata(content: str) -> tuple[dict[str, str], str]:
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


def _adapt_review_agent_instructions(body: str) -> str:
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
    return json.dumps(value)


def _is_pilot_managed_codex_review_agent(agent_file: Path) -> bool:
    try:
        content = agent_file.read_text(encoding="utf-8")
    except OSError:
        return False
    return "pilot-shell managed Codex review agent" in content or "Pilot-managed Codex review agent" in content


def _scoped_pilot_skill_names() -> frozenset[str]:
    """Pilot skill allowlist, narrowed to manifest-tracked skills when available.

    When ``<config dir>/.pilot-manifest.json`` lists installed skills, only skills
    Pilot actually installed are eligible for removal — a user skill that happens
    to share a Pilot name (e.g. their own ``fix``) is preserved. When the manifest
    is absent/unreadable, fall back to the static allowlist (legacy behavior).
    """
    owned = pilot_owned_skill_names()
    if owned:
        return frozenset(_PILOT_SKILL_NAMES & owned)
    return _PILOT_SKILL_NAMES


def _remove_codex_skills() -> int:
    agents_dir = Path.home() / ".agents" / "skills"
    removed = 0
    for skill_name in _scoped_pilot_skill_names():
        skill_dir = agents_dir / skill_name
        if not (skill_dir / _SKILL_RESOURCES_MANIFEST).is_file():
            continue
        managed = (skill_dir / "SKILL.md").is_file() or (skill_dir / "agents" / "openai.yaml").is_file()
        _remove_skill_runtime(skill_dir)
        if managed:
            removed += 1
    return removed


def _remove_codex_review_agents() -> int:
    agents_dir = _get_codex_config_dir() / "agents"
    removed = 0
    for agent_name in _SUPPORTED_REVIEW_AGENTS:
        agent_file = agents_dir / f"{agent_name}.toml"
        if agent_file.is_file() and _is_pilot_managed_codex_review_agent(agent_file):
            agent_file.unlink()
            removed += 1
    return removed


def _sync_codex_skills() -> tuple[int, int]:
    neutral_skills = Path.home() / ".pilot" / "skills"
    claude_dir = claude_config_dir()
    source_skills = neutral_skills if neutral_skills.is_dir() else (claude_dir / "skills" if claude_dir else None)
    # ~/.agents is NOT relocatable: Codex derives it from the home directory and
    # exposes no override (verified against codex-cli 0.144.5). CODEX_HOME only
    # governs ~/.codex.
    agents_dir = Path.home() / ".agents" / "skills"
    built = 0
    failed = 0

    if source_skills is None or not source_skills.is_dir():
        _remove_orphaned_skill_runtimes(agents_dir, set())
        return 0, 0

    source_names = {
        name
        for name in _SUPPORTED_SKILLS
        if (source_skills / name).is_dir() and (source_skills / name / "manifest.json").is_file()
    }
    for skill_name in _SUPPORTED_SKILLS:
        skill_dir = source_skills / skill_name
        if not skill_dir.is_dir() or not (skill_dir / "manifest.json").is_file():
            continue
        if "codex" not in _skill_targets(skill_dir):
            _remove_skill_runtime(agents_dir / skill_name)
            continue
        try:
            codex_content = _build_codex_skill(skill_dir)
            metadata = _build_openai_yaml(skill_dir)
            if codex_content is None or metadata is None:
                failed += 1
                continue
            dest = agents_dir / skill_name
            if _skill_runtime_has_unowned_core(dest):
                failed += 1
                continue
            dest.mkdir(parents=True, exist_ok=True)
            ownership_manifest = dest / _SKILL_RESOURCES_MANIFEST
            if not ownership_manifest.exists():
                _atomic_write(ownership_manifest, '{"files": [], "directories": []}\n')
            tmp = dest / "SKILL.md.tmp"
            tmp.write_text(codex_content, encoding="utf-8")
            os.replace(str(tmp), str(dest / "SKILL.md"))
            metadata_dir = dest / "agents"
            metadata_dir.mkdir(parents=True, exist_ok=True)
            metadata_tmp = metadata_dir / "openai.yaml.tmp"
            metadata_tmp.write_text(metadata, encoding="utf-8")
            os.replace(str(metadata_tmp), str(metadata_dir / "openai.yaml"))
            _sync_skill_resources(skill_dir, dest)
            built += 1
        except Exception:
            failed += 1

    _remove_orphaned_skill_runtimes(agents_dir, source_names)
    return built, failed


def _skill_runtime_has_unowned_core(dest: Path) -> bool:
    """Return whether a same-name user skill occupies Pilot's runtime paths."""
    if (dest / _SKILL_RESOURCES_MANIFEST).is_file():
        return False
    return (dest / "SKILL.md").is_file() or (dest / "agents" / "openai.yaml").is_file()


def _sync_codex_review_agents() -> tuple[int, int]:
    neutral_agents = Path.home() / ".pilot" / "agents"
    claude_dir = claude_config_dir()
    source_dir = neutral_agents if neutral_agents.is_dir() else (claude_dir / "agents" if claude_dir else None)
    dest_dir = _get_codex_config_dir() / "agents"
    built = 0
    failed = 0

    if source_dir is None or not source_dir.is_dir():
        for agent_name in _SUPPORTED_REVIEW_AGENTS:
            target = dest_dir / f"{agent_name}.toml"
            if target.is_file() and _is_pilot_managed_codex_review_agent(target):
                target.unlink(missing_ok=True)
        return 0, 0

    for agent_name in _SUPPORTED_REVIEW_AGENTS:
        source = source_dir / f"{agent_name}.md"
        target = dest_dir / f"{agent_name}.toml"
        if not source.is_file():
            if target.is_file() and _is_pilot_managed_codex_review_agent(target):
                target.unlink(missing_ok=True)
            continue
        try:
            codex_content = _build_codex_review_agent(source)
            if codex_content is None:
                failed += 1
                continue
            dest_dir.mkdir(parents=True, exist_ok=True)
            tmp = dest_dir / f"{agent_name}.toml.tmp"
            tmp.write_text(codex_content, encoding="utf-8")
            os.replace(str(tmp), str(target))
            built += 1
        except Exception:
            failed += 1

    return built, failed


_ENV_MARKER_START = "# --- pilot-shell managed env vars ---"
_ENV_MARKER_END = "# --- end pilot-shell managed env vars ---"
_ENV_SECTION_HEADER = "[shell_environment_policy.set]"


def _merge_env_block(existing: str, env_lines: list[str]) -> str:
    """Merge the pilot-managed env block into config.toml content.

    A TOML table may only be declared once, so when the config already has a
    [shell_environment_policy.set] header the managed lines are inserted inside
    that table; only otherwise is a self-contained block (header inside the
    markers) appended.

    The merge is idempotent and self-healing: every prior managed region is
    removed (not just the first), every [shell_environment_policy.set]
    declaration is collapsed into one, and any managed key left in that table
    outside the markers is dropped before the fresh block is written. Without
    this, managed state left behind by a double-write/race, a lost marker, or a
    manual edit would be emitted twice -- a duplicate key, or a duplicate table
    header -- and Codex aborts startup with a "duplicate key" error loading
    config.toml.
    """
    managed_keys = {line.split("=", 1)[0].strip() for line in env_lines}
    lines = existing.splitlines()

    # Drop every managed region, not just the first. Older formats kept the
    # section header inside the markers, so it is removed together with the
    # region. Marker pairs are matched explicitly so an orphaned marker can
    # never swallow unrelated config; a leftover marker comment is dropped alone.
    cleaned: list[str] = []
    i = 0
    while i < len(lines):
        if lines[i] == _ENV_MARKER_START:
            end = next((j for j in range(i + 1, len(lines)) if lines[j] == _ENV_MARKER_END), None)
            if end is not None:
                i = end + 1
                continue
        if lines[i] in (_ENV_MARKER_START, _ENV_MARKER_END):
            i += 1
            continue
        cleaned.append(lines[i])
        i += 1

    # Collapse every [shell_environment_policy.set] declaration into a single
    # managed table. Declaring that table twice is itself a fatal TOML error,
    # and a managed key repeated inside it is the "duplicate key" crash, so each
    # table's surviving (non-managed) keys are pulled out, every [set] header is
    # dropped, and one managed table is re-emitted at the position of the first.
    # Scoped to that table, so an identically-named key elsewhere is untouched.
    body_keys: list[str] = []
    rest: list[str] = []
    insert_at: int | None = None
    i = 0
    while i < len(cleaned):
        if cleaned[i].split("#", 1)[0].strip() == _ENV_SECTION_HEADER:
            if insert_at is None:
                insert_at = len(rest)
            i += 1
            while i < len(cleaned):
                inner = cleaned[i].split("#", 1)[0].strip()
                if inner.startswith("[") and inner.endswith("]"):
                    break
                if cleaned[i].strip() and cleaned[i].split("=", 1)[0].strip() not in managed_keys:
                    body_keys.append(cleaned[i])
                i += 1
            continue
        rest.append(cleaned[i])
        i += 1

    if insert_at is not None:
        rest[insert_at:insert_at] = [_ENV_SECTION_HEADER, _ENV_MARKER_START, *env_lines, _ENV_MARKER_END, *body_keys]
    else:
        while rest and not rest[-1].strip():
            rest.pop()
        rest += ["", _ENV_MARKER_START, _ENV_SECTION_HEADER, *env_lines, _ENV_MARKER_END]
    return "\n".join(rest) + "\n"


def _sync_codex_env_vars() -> int:
    """Read Console settings and inject PILOT_* env vars into Codex config."""
    config_path = Path.home() / ".pilot" / "config.json"
    codex_config = _get_codex_config_dir() / "config.toml"

    if not codex_config.is_file():
        return 0

    try:
        raw = json.loads(config_path.read_text(encoding="utf-8")) if config_path.is_file() else {}
    except (OSError, json.JSONDecodeError):
        raw = {}

    spec = raw.get("specWorkflow", {})
    reviewers = raw.get("reviewerAgents", {})
    codex_rev = raw.get("codexReviewers", {})

    env_vars = {
        "PILOT_BRANCH_ISOLATION_ENABLED": "true" if spec.get("branchIsolation", True) else "false",
        "PILOT_PLAN_QUESTIONS_ENABLED": "true" if spec.get("askQuestionsDuringPlanning", True) else "false",
        "PILOT_PLAN_APPROVAL_ENABLED": "true" if spec.get("planApproval", True) else "false",
        # PILOT_MODEL_SWITCH_MODE is intentionally NOT emitted for Codex:
        # Model Switching (opusplan + EnterPlanMode/ExitPlanMode, manual /model
        # pauses) is Claude-Code-only. Codex runs plan -> implement -> verify
        # continuously on the active Codex model.
        "PILOT_SPEC_REVIEW_ENABLED": "true" if reviewers.get("specReview", True) else "false",
        "PILOT_CHANGES_REVIEW_ENABLED": "true" if reviewers.get("changesReview", True) else "false",
        "PILOT_CODEX_SPEC_REVIEW_ENABLED": "true" if codex_rev.get("specReview", False) else "false",
        "PILOT_CODEX_CHANGES_REVIEW_ENABLED": "true" if codex_rev.get("changesReview", False) else "false",
    }

    env_lines = [f'{k} = "{v}"' for k, v in sorted(env_vars.items())]

    try:
        existing = codex_config.read_text(encoding="utf-8")
    except OSError:
        return 0

    new_content = _merge_env_block(existing, env_lines)

    if new_content != existing:
        tmp = codex_config.with_suffix(".toml.tmp")
        tmp.write_text(new_content, encoding="utf-8")
        os.replace(str(tmp), str(codex_config))
        return len(env_vars)
    return 0


def main() -> None:
    try:
        codex_config_dir = _get_codex_config_dir()
    except ValueError as e:
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "SessionStart",
                        "additionalContext": (
                            f"Pilot skipped Codex asset synchronization: {e}. "
                            "Treat this as internal maintenance context and fix it only when within task authority."
                        ),
                    }
                }
            )
        )
        return

    codex_bin = codex_config_dir / "bin" / "codex"
    app_codex_bin = Path("/Applications/ChatGPT.app/Contents/Resources/codex")
    codex_on_path = any((Path(p) / "codex").is_file() for p in os.environ.get("PATH", "").split(os.pathsep) if p)
    if not codex_bin.is_file() and not app_codex_bin.is_file() and not codex_on_path:
        return

    valid = _check_license()

    if valid is True:
        _sync_codex_skills()
        _sync_codex_review_agents()
        _sync_codex_env_vars()
    elif valid is False:
        removed = _remove_codex_skills() + _remove_codex_review_agents()
        detail = f" removed {removed} Codex managed asset(s)." if removed else ""
        msg = (
            "Pilot Shell access is inactive, so Pilot features are paused. "
            "Pilot workflows, context, quality hooks, Console, statusline metrics, and managed agents are unavailable. "
            "Codex remains usable, but without Pilot's engineering harness. Activate a new key with "
            "`pilot activate <LICENSE_KEY>`, get a license at https://pilot-shell.com/pricing, "
            "or uninstall Pilot safely with the documented uninstall command." + detail
        )
        print(json.dumps({"continue": True, "systemMessage": msg}))


if __name__ == "__main__":
    main()
