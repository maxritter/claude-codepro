"""Keep repository-owned agent instructions synchronized for both agents.

Repositories with agent instructions, rules, or skills are discovered
automatically. ``scripts/sync-agent-assets.mjs`` remains an optional recovery
and CI checker installed through ``/setup-rules`` or ``$setup-rules``; the
global hook always executes the trusted checker bundled with Pilot. The checker
owns this synchronization contract:

* ``AGENTS.md`` is the shared rule source and ``CLAUDE.md`` imports it, or one
  may be an exact in-repository symlink to the other for legacy shared layouts.
* Tracked skills use ``.agents/skills`` as canonical and ``.claude/skills`` as
  their managed mirror.
* Gitignored local skills synchronize in both directions using a trusted local
  baseline outside the repository worktree.

At SessionStart the bundled checker refreshes an enrolled repository's local
copy when present and converges drift. PreToolUse protects only the generated
``CLAUDE.md`` import; PostToolUse synchronizes skill edits in either direction
and refreshes rule availability.
Stop performs the same convergence as a backstop for clients or modes that do
not emit edit hooks, including Codex Code Mode.

Hook input is untrusted and best-effort.  Malformed payloads and repositories
without the opt-in checker are quiet no-ops.  Checker processes and the
cross-agent lock are bounded so an unrelated tool or broken repository cannot
stall the client indefinitely.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

_CHECKER_RELATIVE = Path("scripts") / "sync-agent-assets.mjs"
_BUNDLED_CHECKER_RELATIVE = Path("skills") / "setup-rules" / "scripts" / "sync-agent-assets.mjs"
_CANONICAL_SKILLS = Path(".agents") / "skills"
_MIRRORED_SKILLS = Path(".claude") / "skills"
_RUN_TIMEOUT_SECONDS = 8
_LOCK_WAIT_SECONDS = 3.0
_STALE_LOCK_SECONDS = 30.0
_SESSION_STOP_WORST_CASE_SECONDS = _LOCK_WAIT_SECONDS + _RUN_TIMEOUT_SECONDS * 2
_POST_TOOL_WORST_CASE_SECONDS = _LOCK_WAIT_SECONDS + _RUN_TIMEOUT_SECONDS
_PATCH_PATH_RE = re.compile(r"^\*\*\* (?:Add|Update|Delete) File:\s*(.+?)\s*$", re.MULTILINE)
_PATCH_MOVE_RE = re.compile(r"^\*\*\* Move to:\s*(.+?)\s*$", re.MULTILINE)


@dataclass(frozen=True)
class CheckerResult:
    """Bounded checker outcome used to build hook feedback."""

    ok: bool
    detail: str = ""


def _is_regular_file(candidate: Path) -> bool:
    try:
        return candidate.is_file() and not candidate.is_symlink()
    except OSError:
        return False


def _bundled_checker() -> Path | None:
    """Return Pilot's trusted bundled checker when installed with this hook."""
    candidate = Path(__file__).resolve().parent.parent / _BUNDLED_CHECKER_RELATIVE
    return candidate if _is_regular_file(candidate) else None


def _candidate_directory(value: object) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        candidate = Path(value).expanduser().resolve(strict=False)
    except (OSError, RuntimeError, ValueError):
        return None
    return candidate if candidate.is_dir() else candidate.parent


def _has_agent_assets(candidate: Path) -> bool:
    """Whether a repository root contains an agent surface worth syncing."""
    if _is_regular_file(candidate / _CHECKER_RELATIVE):
        return True
    if _is_regular_file(candidate / "AGENTS.md") or _is_regular_file(candidate / "CLAUDE.md"):
        return True
    for relative in (_CANONICAL_SKILLS, _MIRRORED_SKILLS, Path(".claude") / "rules"):
        root = candidate / relative
        try:
            if root.is_dir() and not root.is_symlink() and any(root.iterdir()):
                return True
        except OSError:
            continue
    return False


def _enrolled_repo_from(candidate: Path) -> Path | None:
    """Find the nearest syncable repo without crossing a nested git boundary."""
    current = candidate
    while True:
        if _has_agent_assets(current):
            return current
        if (current / ".git").exists():
            return None
        if current.parent == current:
            return None
        current = current.parent


def _input_base(payload: dict) -> Path:
    for value in (payload.get("cwd"), os.environ.get("CLAUDE_PROJECT_ROOT")):
        candidate = _candidate_directory(value)
        if candidate is not None:
            return candidate
    return Path.cwd().resolve(strict=False)


def _find_enrolled_repo(payload: dict, raw_paths: list[str]) -> Path | None:
    candidates: list[Path] = []
    base = _input_base(payload)
    candidates.append(base)

    for raw_path in raw_paths:
        try:
            path = Path(raw_path).expanduser()
            absolute = path if path.is_absolute() else base / path
            candidates.append(absolute.resolve(strict=False).parent)
        except (OSError, RuntimeError, ValueError):
            continue

    explicit_base = any(
        isinstance(value, str) and value.strip()
        for value in (payload.get("cwd"), os.environ.get("CLAUDE_PROJECT_ROOT"))
    )
    if not explicit_base:
        cwd = Path.cwd().resolve(strict=False)
        if cwd not in candidates:
            candidates.append(cwd)

    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        repo = _enrolled_repo_from(candidate)
        if repo is not None:
            return repo
    return None


def _extract_changed_paths(payload: dict) -> list[str]:
    """Extract Claude file paths and Codex apply_patch paths."""
    tool_name = payload.get("tool_name")
    tool_input = payload.get("tool_input")
    if not isinstance(tool_name, str) or not isinstance(tool_input, dict):
        return []

    normalized_tool = tool_name.rsplit(".", 1)[-1]
    if normalized_tool in {"Write", "Edit", "MultiEdit"}:
        file_path = tool_input.get("file_path")
        return [file_path] if isinstance(file_path, str) and file_path.strip() else []

    if normalized_tool != "apply_patch":
        return []
    command = tool_input.get("command")
    if not isinstance(command, str):
        return []
    return [*_PATCH_PATH_RE.findall(command), *_PATCH_MOVE_RE.findall(command)]


def _repo_relative_paths(repo: Path, payload: dict, raw_paths: list[str]) -> list[Path]:
    base = _input_base(payload)
    relative_paths: list[Path] = []
    for raw_path in raw_paths:
        try:
            candidate = Path(raw_path).expanduser()
            absolute = candidate if candidate.is_absolute() else base / candidate
            relative = absolute.resolve(strict=False).relative_to(repo.resolve(strict=False))
        except (OSError, RuntimeError, ValueError):
            continue
        if relative not in relative_paths:
            relative_paths.append(relative)
    return relative_paths


def _is_within(path: Path, parent: Path) -> bool:
    return path == parent or parent in path.parents


def _uses_shared_instructions(repo: Path) -> bool:
    """Whether exactly one root instruction file aliases its repo counterpart."""
    agents = repo / "AGENTS.md"
    claude = repo / "CLAUDE.md"
    try:
        linked = [candidate for candidate in (agents, claude) if candidate.is_symlink()]
        if len(linked) != 1:
            return False
        target = claude if linked[0] == agents else agents
        return (
            not target.is_symlink()
            and target.is_file()
            and linked[0].resolve(strict=True) == target.resolve(strict=True)
        )
    except (OSError, RuntimeError):
        return False


def _generated_instruction_source(contents: str, expected_target: str) -> str | None:
    header = "\n".join(contents.splitlines()[:16])
    if re.search(r"GENERATED FILE[^\n]*DO NOT EDIT", header, re.IGNORECASE) is None:
        return None
    source = re.search(r"\bSource:\s*([^|\r\n]+)", header, re.IGNORECASE)
    target = re.search(r"\bTarget:\s*([^|\r\n]+)", header, re.IGNORECASE)
    if source is None or target is None or target.group(1).strip() != expected_target:
        return None
    return source.group(1).strip() or None


def _external_generated_instruction_source(repo: Path) -> str | None:
    """Return shared external provenance for a generated AGENTS/CLAUDE pair."""
    agents = repo / "AGENTS.md"
    claude = repo / "CLAUDE.md"
    if not _is_regular_file(agents) or not _is_regular_file(claude):
        return None
    try:
        agents_source = _generated_instruction_source(agents.read_text(), "AGENTS.md")
        claude_source = _generated_instruction_source(claude.read_text(), "CLAUDE.md")
    except (OSError, UnicodeDecodeError):
        return None
    return agents_source if agents_source is not None and agents_source == claude_source else None


def _generated_edit_message(_paths: list[Path]) -> str:
    return "CLAUDE.md is generated from AGENTS.md. Apply the shared rule change to AGENTS.md instead."


def _pre_tool_payload(message: str, decision: str, updated_input: dict | None = None) -> dict:
    output: dict = {
        "hookEventName": "PreToolUse",
        "permissionDecision": decision,
    }
    if decision == "deny":
        output["permissionDecisionReason"] = message
    if updated_input is not None:
        output["updatedInput"] = updated_input
        output["additionalContext"] = message
    return {"systemMessage": message, "hookSpecificOutput": output}


def _short_detail(completed: subprocess.CompletedProcess[str]) -> str:
    detail = (completed.stderr or "").strip() or (completed.stdout or "").strip()
    if not detail:
        return f"checker exited with status {completed.returncode}"
    compact = " ".join(detail.split())
    return compact if len(compact) <= 700 else f"{compact[:697]}..."


def _run_checker(checker: Path, mode: str, repo: Path) -> CheckerResult:
    node = shutil.which("node")
    if node is None:
        return CheckerResult(False, "Node.js is unavailable; install Node.js and restart the agent session")
    try:
        completed = subprocess.run(
            [node, str(checker), f"--{mode}", "--repo", str(repo)],
            cwd=repo,
            capture_output=True,
            text=True,
            timeout=_RUN_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return CheckerResult(False, f"checker timed out after {_RUN_TIMEOUT_SECONDS} seconds")
    except (OSError, ValueError) as error:
        return CheckerResult(False, f"checker could not start: {error}")
    if completed.returncode != 0:
        return CheckerResult(False, _short_detail(completed))
    return CheckerResult(True)


def _lock_path(repo: Path) -> Path:
    digest = hashlib.sha256(str(repo.resolve(strict=False)).encode()).hexdigest()[:20]
    return Path(tempfile.gettempdir()) / f"pilot-repo-agent-sync-{digest}.lock"


@contextmanager
def _repo_lock(repo: Path) -> Iterator[bool]:
    """Serialize simultaneous Claude/Codex syncs without leaving repo files."""
    lock = _lock_path(repo)
    deadline = time.monotonic() + _LOCK_WAIT_SECONDS
    acquired = False
    while time.monotonic() < deadline:
        try:
            lock.mkdir(mode=0o700)
            acquired = True
            break
        except FileExistsError:
            try:
                if time.time() - lock.stat().st_mtime > _STALE_LOCK_SECONDS:
                    lock.rmdir()
                    continue
            except (FileNotFoundError, OSError):
                pass
            time.sleep(0.05)
        except OSError:
            break
    try:
        yield acquired
    finally:
        if acquired:
            try:
                lock.rmdir()
            except OSError:
                pass


def _is_codex_hook(payload: dict | None = None) -> bool:
    platform = str((payload or {}).get("platform") or os.environ.get("CLAUDE_PROJECT_PLATFORM") or "").lower()
    return platform == "codex" or (
        not os.environ.get("CLAUDE_CODE_SESSION_ID") and bool(os.environ.get("CODEX_THREAD_ID"))
    )


def _payload(payload: dict | None = None, event: str = "") -> dict:
    if _is_codex_hook(payload) and event in {"PreToolUse", "PostToolUse"}:
        return {}
    return {"continue": True}


def _context_payload(message: str = "", event: str = "", payload: dict | None = None) -> dict:
    """Inject agent-only context without printing a user-facing hook message."""
    if not message or event not in {"SessionStart", "PostToolUse"}:
        return {"continue": True}
    result: dict = {
        "hookSpecificOutput": {
            "hookEventName": event,
            "additionalContext": message,
        }
    }
    if not _is_codex_hook(payload):
        result.update({"continue": True, "suppressOutput": True})
    return result


def _same_contents(left: Path, right: Path) -> bool:
    try:
        return left.read_bytes() == right.read_bytes()
    except OSError:
        return False


def _rule_context(repo: Path) -> str:
    """Return a bounded on-demand index for Claude-style repository rules."""
    rules_root = repo / ".claude" / "rules"
    try:
        candidates = sorted(
            path.relative_to(repo).as_posix()
            for path in rules_root.rglob("*.md")
            if path.name != "README.md" and path.is_file() and not path.is_symlink()
        )
    except (OSError, ValueError):
        return ""
    if not candidates:
        return ""
    shown = candidates[:40]
    suffix = f" and {len(candidates) - len(shown)} more" if len(candidates) > len(shown) else ""
    paths = ", ".join(f"`{path}`" for path in shown)
    return (
        "Repository detailed rules are available to both agents on demand: "
        f"{paths}{suffix}. Read the matching rule before changing files in its scope."
    )


def _session_start(repo: Path, payload: dict) -> dict:
    local_checker = repo / _CHECKER_RELATIVE
    rules = _rule_context(repo)
    bundled = _bundled_checker()
    if bundled is None:
        return _context_payload(
            "Pilot found repository agent sync enrollment, but its trusted bundled checker is unavailable. "
            "Reinstall or update Pilot Shell; the repository-local checker was not executed.",
            "SessionStart",
            payload,
        )
    has_local_checker = _is_regular_file(local_checker)
    needs_install = has_local_checker and not _same_contents(bundled, local_checker)
    with _repo_lock(repo) as acquired:
        if not acquired:
            return _context_payload(
                "Pilot agent sync skipped because another synchronization did not finish in time.",
                "SessionStart",
                payload,
            )
        check = _run_checker(bundled, "check", repo)
        if check.ok and not needs_install:
            return _context_payload(rules, "SessionStart", payload)
        mode = "install" if needs_install else "write"
        result = _run_checker(bundled, mode, repo)
    if not result.ok:
        detail = f"Pilot preserved repository agent assets because synchronization could not converge: {result.detail}"
        return _context_payload(f"{detail} {rules}".strip(), "SessionStart", payload)
    return _context_payload(rules, "SessionStart", payload)


def _pre_tool_use(repo: Path, payload: dict, raw_paths: list[str]) -> dict:
    relative_paths = _repo_relative_paths(repo, payload, raw_paths)
    if Path("CLAUDE.md") in relative_paths and not _uses_shared_instructions(repo):
        external_source = _external_generated_instruction_source(repo)
        if external_source is not None:
            return _pre_tool_payload(
                f"CLAUDE.md is generated by an external tool. Apply the change to {external_source} instead.",
                "deny",
            )
        return _pre_tool_payload(
            "CLAUDE.md is generated and must remain exactly @AGENTS.md. Apply the rule change to AGENTS.md instead.",
            "deny",
        )

    # Skills are synchronized in both directions after the edit. Only the root
    # CLAUDE.md import remains generated because Codex officially reads AGENTS.md.
    return _payload(payload, "PreToolUse")


def _post_tool_use(repo: Path, payload: dict, raw_paths: list[str]) -> dict:
    relative_paths = _repo_relative_paths(repo, payload, raw_paths)
    shared_instructions = _uses_shared_instructions(repo)
    external_source = _external_generated_instruction_source(repo)
    generated = [path for path in relative_paths if path == Path("CLAUDE.md") and not shared_instructions]
    if generated:
        if external_source is not None:
            return _context_payload(
                f"Pilot preserved this external generated-file edit. Apply the source change to {external_source}.",
                "PostToolUse",
                payload,
            )
        return _context_payload(
            f"Pilot preserved this generated-side edit. {_generated_edit_message(generated)}",
            "PostToolUse",
            payload,
        )

    syncable = [
        path
        for path in relative_paths
        if path == Path("AGENTS.md")
        or (path == Path("CLAUDE.md") and shared_instructions)
        or _is_within(path, _CANONICAL_SKILLS)
        or _is_within(path, _MIRRORED_SKILLS)
        or _is_within(path, Path(".claude") / "rules")
    ]
    if not syncable:
        return _payload(payload, "PostToolUse")

    bundled = _bundled_checker()
    if bundled is None:
        return _context_payload(
            "Pilot could not synchronize this canonical agent edit because its trusted bundled checker is "
            "unavailable. The edit was preserved; reinstall or update Pilot Shell. The repository-local "
            "checker was not executed.",
            "PostToolUse",
            payload,
        )
    with _repo_lock(repo) as acquired:
        if not acquired:
            return _context_payload(
                "Pilot deferred repository agent synchronization because another sync is still running. "
                "The edit was preserved and Pilot will retry automatically after a later relevant edit or at completion.",
                "PostToolUse",
                payload,
            )
        result = _run_checker(bundled, "write", repo)
    if not result.ok:
        return _context_payload(
            f"Pilot deferred repository agent synchronization after this edit: {result.detail}. "
            "The edit was preserved; complete the related agent assets and Pilot will retry automatically "
            "after a later relevant edit or at completion.",
            "PostToolUse",
            payload,
        )
    return _payload(payload, "PostToolUse")


def _stop(repo: Path, payload: dict) -> dict:
    """Converge a syncable repo when a client emitted no edit lifecycle hook."""
    bundled = _bundled_checker()
    if bundled is None:
        return _payload()
    with _repo_lock(repo) as acquired:
        if not acquired:
            return _payload()
        check = _run_checker(bundled, "check", repo)
        if check.ok:
            return _payload()
        result = _run_checker(bundled, "write", repo)
    if not result.ok:
        return _payload()
    return _payload()


def handle(payload: object) -> dict:
    """Handle one hook payload and always return a valid fail-open response."""
    if not isinstance(payload, dict):
        return _payload()
    event = payload.get("hook_event_name")
    if event == "SessionStart":
        repo = _find_enrolled_repo(payload, [])
        return _session_start(repo, payload) if repo is not None else _payload(payload, event)
    if event == "Stop":
        repo = _find_enrolled_repo(payload, [])
        return _stop(repo, payload) if repo is not None else _payload(payload, event)
    if event not in {"PreToolUse", "PostToolUse"}:
        return _payload()

    raw_paths = _extract_changed_paths(payload)
    if not raw_paths:
        return _payload(payload, event)
    repo = _find_enrolled_repo(payload, raw_paths)
    if repo is None:
        return _payload(payload, event)
    if event == "PreToolUse":
        return _pre_tool_use(repo, payload, raw_paths)
    return _post_tool_use(repo, payload, raw_paths)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        result = handle(payload)
    except Exception:
        # Hook input and project state are untrusted. Never strand an agent
        # session because a best-effort synchronization hook could not parse it.
        result = _payload()
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
