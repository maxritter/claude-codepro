#!/usr/bin/env python3
"""PostToolUse(ExitPlanMode) hook: file an approved native plan under docs/plans/.

Claude Code's own plan mode parks the plan in a throwaway
`~/.claude/plans/<random-words>.md` that nothing ever reads again: it is outside
the repo, invisible to the Pilot Console, and gone the moment the user forgets
the random name. This hook copies the plan the user just approved into the
project's registered-run directory (`docs/plans/`), in the Pilot plan format, so
it renders in the Console next to `/spec` plans and stays with the repo.

⛔ It captures ONLY plans that no Pilot workflow owns. `pilot_run_in_flight`
reporting a live run means `/spec` or `/build` already maintains its own file -
capturing there would write a duplicate that competes with the real plan in the
Console list. That predicate reads `active_plan.json` (the session slot AND every
orchestration lane's, since a lane's `/spec` owns a plan this session's slot never
names) and deliberately NOT the plan-mode sentinel, because `plan_mode_tracker`
deletes that sentinel on this same PostToolUse event and the two hooks would race
for it. It fails CLOSED: an unreadable registration means "a run may be running",
so an ambiguous state skips the capture rather than filing a competing document.

STATUS IS TERMINAL BY CONSTRUCTION. A captured plan is written `Status: SAVED`,
never PENDING, because nothing will ever advance it: native plan mode has no
implement phase, no verify phase, and no completion signal to hook. Pilot's
active-run surfaces (the Console top bar, `/api/plan`, the Spec view's
auto-selection) only track PENDING/COMPLETE, so a SAVED record can never rot
into a phantom in-flight spec - the exact failure that a "capture it as PENDING
and hope someone closes it" design produces on the first abandoned plan. It is a
record of a decision, and it is filed as one.

Fails silent and open: an unreadable payload, a missing project root, an
undeterminable plan body, or any write error simply skips the capture. A hook
that cannot file a document must never disturb the session that produced it.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _lib.util import (
    _sessions_base,
    claude_config_dir,
    current_project_root,
    get_session_plan_path,
    post_tool_use_context,
    read_hook_stdin,
    resolve_session_id,
)

PLANS_DIRNAME = ("docs", "plans")

# Terminal, non-workflow status. Outside the PENDING/COMPLETE lifecycle every
# Pilot active-run surface tracks, so a captured plan is listed and readable but
# never counted as work in flight.
CAPTURED_STATUS = "SAVED"

# `Type:` value the Console renders with its own badge (see specType.ts). A
# captured plan is not a Feature, Bugfix, or Buildout - it is a plan someone
# approved outside a workflow, and mislabelling it as a Feature is how it starts
# looking like a spec that was abandoned.
CAPTURED_TYPE = "Plan"

_MAX_SLUG_LEN = 60

# Same title, same day, this many times over: the suffix search gives up rather
# than spinning. Far beyond any real planning session.
_MAX_CAPTURES_PER_TITLE = 50
_H1_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
NATIVE_SPEC_MARKER = "native-spec-planning.json"
_SPEC_IDENTITY_FIELDS = ("Created", "Agent", "Worktree", "Type", "Iterations")


def native_spec_marker(session_id: str) -> Path:
    return _sessions_base() / session_id / NATIVE_SPEC_MARKER


def _spec_header(content: str) -> dict[str, str]:
    """Validate the bridge's canonical header without changing ordinary Plan capture."""
    header, separator, body = content.partition("\n## ")
    title = _H1_RE.match(header)
    if "\r" in content or title is None or not separator or not body.strip():
        raise ValueError("a complete spec header and body sections are required")
    values = {"title": title.group(1)}
    for field in (*_SPEC_IDENTITY_FIELDS, "Status", "Approved"):
        matches = re.findall(rf"^{field}: ([^\r\n]+)$", header, re.MULTILINE)
        if len(matches) != 1:
            raise ValueError(f"the spec header requires exactly one {field} field")
        values[field] = matches[0]
    if (
        values["Type"] not in {"Feature", "Bugfix"}
        or values["Status"] != "PENDING"
        or values["Approved"] not in {"Yes", "No"}
        or values["Worktree"] not in {"Yes", "No"}
        or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", values["Created"])
        or not re.fullmatch(r"0|[1-9]\d*", values["Iterations"])
        or not values["Agent"].strip()
    ):
        raise ValueError("invalid canonical spec header")
    datetime.date.fromisoformat(values["Created"])
    return values


def _git_output(directory: Path, *arguments: str) -> str:
    git_env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    result = subprocess.run(
        ["git", "-C", str(directory), *arguments],
        capture_output=True,
        text=True,
        timeout=2,
        check=False,
        env=git_env,
    )
    if result.returncode:
        raise ValueError("could not verify worktree Git identity")
    return result.stdout.strip()


def _git_common_dir(directory: Path) -> Path:
    lines = _git_output(directory, "rev-parse", "--show-toplevel", "--git-common-dir").splitlines()
    if len(lines) != 2 or Path(lines[0]).resolve() != directory.resolve():
        raise ValueError("worktree metadata must name an actual Git checkout root")
    common = Path(lines[1])
    return (common if common.is_absolute() else directory / common).resolve(strict=True)


def _plan_belongs_to_project(plan: Path, root: Path, sid: str) -> bool:
    """Containment first; external worktrees need both session and Git proof."""
    if plan.parts[-3:-1] != PLANS_DIRNAME:
        return False
    root = root.resolve()
    if plan.is_relative_to(root):
        return True
    try:
        record = json.loads((get_session_plan_path(sid).parent / "worktree.json").read_text())
        worktree = Path(record["worktree_path"])
        owner = Path(record["project_root"])
        if not worktree.is_absolute() or not owner.is_absolute():
            return False
        worktree, owner = worktree.resolve(strict=True), owner.resolve(strict=True)
        if plan.parent != worktree.joinpath(*PLANS_DIRNAME) or worktree == owner:
            return False
        common = _git_common_dir(root)
        if _git_common_dir(owner) != common or _git_common_dir(worktree) != common:
            return False
        registered = {
            Path(line.removeprefix("worktree ")).resolve()
            for line in _git_output(root, "worktree", "list", "--porcelain").splitlines()
            if line.startswith("worktree ")
        }
        return worktree in registered
    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError):
        return False


def pending_native_spec(session_id: str) -> dict | None:
    """Read an explicit native-planning handoff bound to this session's run."""
    try:
        marker = json.loads(native_spec_marker(session_id).read_text())
        registered = json.loads(get_session_plan_path(session_id).read_text())
        root = current_project_root()
        if not isinstance(marker, dict) or not isinstance(registered, dict) or root is None:
            return None
        plan = Path(marker["plan_path"])
        if (
            Path(marker["project_root"]).resolve() != root.resolve()
            or registered.get("status") != "PENDING"
            or Path(registered["plan_path"]).resolve() != plan.resolve()
            or not plan.is_absolute()
            or plan.is_symlink()
            or not plan.is_file()
            or not _plan_belongs_to_project(plan.resolve(), root, session_id)
            or not re.fullmatch(r"[0-9a-f]{64}", marker.get("sha256", ""))
            or not isinstance(marker.get("approval_required"), bool)
            or marker.get("state") not in {"prepared", "entering", "active"}
        ):
            return None
        return marker
    except (OSError, ValueError, TypeError, KeyError):
        return None


def prepare_native_spec(plan_path: str) -> int:
    """Bind a registered draft before EnterPlanMode; never relax native permissions."""
    sid = resolve_session_id()
    root = current_project_root()
    try:
        requested = Path(plan_path).expanduser()
        if requested.is_symlink() or not requested.is_file():
            raise ValueError("the registered spec must be a regular file, not a symlink")
        plan = requested.resolve(strict=True)
        content = plan.read_text()
        if root is None or not _plan_belongs_to_project(plan, root, sid):
            raise ValueError("the registered spec must belong to this project or its session-owned Git worktree")
        if (_sessions_base() / sid / "plan-mode-active").exists():
            raise ValueError("prepare the handoff before entering native plan mode")
        header = _spec_header(content)
        if not plan.is_relative_to(root.resolve()) and header["Worktree"] != "Yes":
            raise ValueError("an external worktree plan must preserve Worktree: Yes")
        if header["Status"] != "PENDING":
            raise ValueError("a registered PENDING spec plan is required")
        if header["Approved"] != "No":
            raise ValueError("native planning requires an unapproved draft")
        marker = native_spec_marker(sid)
        marker.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "project_root": str(root.resolve()),
            "plan_path": str(plan),
            "sha256": hashlib.sha256(plan.read_bytes()).hexdigest(),
            "approval_required": os.environ.get("PILOT_PLAN_APPROVAL_ENABLED", "true").lower() != "false",
            "state": "prepared",
        }
        registered = json.loads(get_session_plan_path(sid).read_text())
        if registered.get("status") != "PENDING" or Path(registered["plan_path"]).resolve() != plan:
            raise ValueError("the draft must be registered to this session before native planning")
        if plan.parts[-3:-1] != PLANS_DIRNAME:
            raise ValueError("the registered spec must live in docs/plans")
        _atomic_replace(marker, json.dumps(payload) + "\n")
        (marker.parent / "bypass-restore-pending").unlink(missing_ok=True)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"Could not prepare native spec planning: {exc}", file=sys.stderr)
        return 1
    print("Native spec handoff prepared. Enter plan mode and write only its permitted draft file.")
    return 0


def _atomic_replace(
    target: Path,
    content: str,
    *,
    expected_sha256: str | None = None,
    validate_spec: bool = False,
) -> None:
    original_stat = target.stat(follow_symlinks=False) if expected_sha256 is not None else None
    fd, name = tempfile.mkstemp(prefix=".pilot-plan-", dir=target.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        if validate_spec:
            from spec_plan_validator import _validation_errors

            errors = _validation_errors(temporary)
            if errors:
                raise ValueError("accepted spec validation failed: " + "; ".join(errors[:3]))
        if target.exists():
            temporary.chmod(target.stat().st_mode & 0o777)
        if original_stat is not None:
            # Recheck after staging and validation. A non-cooperating writer can
            # still race the final check and rename; this is not an OS-level CAS.
            current_stat = target.stat(follow_symlinks=False)
            identity = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
            if (
                target.is_symlink()
                or any(getattr(current_stat, field) != getattr(original_stat, field) for field in identity)
                or hashlib.sha256(target.read_bytes()).hexdigest() != expected_sha256
            ):
                raise ValueError("the registered spec changed before replacement; the concurrent edit was preserved")
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def _current_unapproved_spec(marker: dict) -> str | None:
    try:
        raw = Path(marker["plan_path"]).read_bytes()
        content = raw.decode("utf-8")
        if hashlib.sha256(raw).hexdigest() != marker["sha256"] or _spec_header(content)["Approved"] != "No":
            return None
        return content
    except (OSError, ValueError, KeyError):
        return None


def _save_native_marker(sid: str, marker: dict) -> None:
    _atomic_replace(native_spec_marker(sid), json.dumps(marker) + "\n")


def _retire_native_spec_entry(sid: str) -> None:
    """Discard an unusable entry binding without changing the registered plan or native mode."""
    directory = native_spec_marker(sid).parent
    for name in (NATIVE_SPEC_MARKER, "pre-plan-permission-mode", "plan-leg-owner", "bypass-restore-pending"):
        (directory / name).unlink(missing_ok=True)


def begin_native_spec_entry(sid: str, tool_use_id: str) -> None:
    """Consume a preparation once; a later Enter cannot reuse an earlier leg."""
    marker = pending_native_spec(sid)
    if marker is None:
        # Older hooks retained failed entries as `invalid`. A new native entry
        # must not inherit that permanent suppression of ordinary plan capture.
        try:
            stale = json.loads(native_spec_marker(sid).read_text())
            if isinstance(stale, dict) and stale.get("state") == "invalid":
                _retire_native_spec_entry(sid)
        except (OSError, ValueError):
            pass
        return
    if marker["state"] != "prepared" or _current_unapproved_spec(marker) is None:
        _retire_native_spec_entry(sid)
        return
    marker["state"] = "entering"
    marker["enter_tool_use_id"] = tool_use_id
    _save_native_marker(sid, marker)


def _native_draft_path(value: object, *, must_exist: bool = True) -> Path | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        candidate = Path(value).expanduser().resolve(strict=must_exist)
        if must_exist and not candidate.is_file():
            return None
        if candidate.suffix.lower() == ".md" and any(
            candidate.is_relative_to(directory) for directory in _trusted_scratch_dirs()
        ):
            return candidate
    except (OSError, ValueError):
        pass
    return None


def finish_native_spec_entry(sid: str, tool_use_id: str, response: object, leg_id: str) -> None:
    marker = pending_native_spec(sid)
    if marker is None:
        return
    if marker.get("enter_tool_use_id") != tool_use_id:
        return  # a delayed result must not retire another entry's binding
    if (
        marker["state"] != "entering"
        or not isinstance(response, dict)
        or response.get("is_error")
        or _current_unapproved_spec(marker) is None
    ):
        _retire_native_spec_entry(sid)
        return
    marker.update(state="active", leg_id=leg_id)
    draft = _native_draft_path(response.get("planFilePath") or response.get("filePath"), must_exist=False)
    if draft is not None and draft != Path(marker["plan_path"]):
        marker["draft_path"] = str(draft)
    _save_native_marker(sid, marker)


def observe_native_spec_draft(sid: str, file_path: str) -> None:
    """Fallback for runtimes that name the permitted file only at the write tool."""
    marker = pending_native_spec(sid)
    if marker is None or marker["state"] != "active" or marker.get("draft_path"):
        return
    try:
        if (_sessions_base() / sid / "plan-mode-active").read_text() != marker.get("leg_id"):
            return
        draft = _native_draft_path(file_path, must_exist=False)
        if draft is None or draft == Path(marker["plan_path"]):
            return
        marker["draft_path"] = str(draft)
        marker["draft_requires_change"] = True
        marker["draft_before_sha256"] = hashlib.sha256(draft.read_bytes()).hexdigest() if draft.exists() else None
        _save_native_marker(sid, marker)
    except OSError:
        return


def native_spec_exit_matches(marker: dict, tool_input: object, sid: str, *, require_active: bool) -> bool:
    """Require this leg's actual draft and the unchanged registered execution identity."""
    if (
        marker.get("state") != "active"
        or not isinstance(tool_input, dict)
        or not isinstance(marker.get("leg_id"), str)
        or not re.fullmatch(r"[0-9a-f]{32}", marker["leg_id"])
    ):
        return False
    try:
        if require_active and (_sessions_base() / sid / "plan-mode-active").read_text() != marker.get("leg_id"):
            return False
        current = _current_unapproved_spec(marker)
        draft = _native_draft_path(marker.get("draft_path"))
        if current is None or draft is None:
            return False
        raw = draft.read_bytes()
        content = raw.decode("utf-8")
        if marker.get("draft_requires_change") and hashlib.sha256(raw).hexdigest() == marker.get("draft_before_sha256"):
            return False  # a pre-tool event alone does not prove its write succeeded
        supplied_path = tool_input.get("planFilePath")
        supplied_plan = tool_input.get("plan")
        if supplied_path is not None and _native_draft_path(supplied_path) != draft:
            return False
        if supplied_plan is not None and (
            not isinstance(supplied_plan, str) or supplied_plan.strip() != content.strip()
        ):
            return False
        if supplied_path is None and supplied_plan is None:
            return False
        expected, actual = _spec_header(current), _spec_header(content)
        identity_fields = (*_SPEC_IDENTITY_FIELDS, "title") if require_active else _SPEC_IDENTITY_FIELDS
        return (not require_active or actual["Approved"] == "No") and all(
            actual[field] == expected[field] for field in identity_fields
        )
    except (OSError, ValueError, KeyError):
        return False


def _capture_native_spec(marker: dict, plan: str, sid: str) -> str:
    """Materialize the approved native draft without clobbering concurrent edits."""
    target = Path(marker["plan_path"])
    try:
        current = target.read_text()
        if hashlib.sha256(target.read_bytes()).hexdigest() != marker["sha256"]:
            return (
                "The registered spec changed during native planning; Pilot preserved it and the native draft. "
                "Reconcile the current plan with the approved draft before implementation, and obtain approval "
                "for substantive changes. Do not overwrite the concurrent edits."
            )
        try:
            expected, accepted = _spec_header(current), _spec_header(plan)
            valid_identity = all(accepted[field] == expected[field] for field in _SPEC_IDENTITY_FIELDS)
        except ValueError:
            valid_identity = False
        if not valid_identity:
            return (
                "Native approval succeeded, but the draft lacks the registered spec's canonical header or changes "
                "its execution identity. Pilot preserved both files. Repair the draft metadata before implementation."
            )
        header, separator, body = plan.partition("\n## ")
        header = re.sub(r"^Approved: (?:Yes|No)$", "Approved: Yes", header, flags=re.MULTILINE)
        _atomic_replace(
            target,
            header + separator + body.rstrip() + "\n",
            expected_sha256=marker["sha256"],
            validate_spec=True,
        )
        (native_spec_marker(sid).parent / "bypass-restore-pending").unlink(missing_ok=True)
        native_spec_marker(sid).unlink(missing_ok=True)
        return (
            f"Native plan approval recorded in {target}. The registered spec remains PENDING and is now Approved: Yes. "
            "Use this file for spec-implement and continue immediately. Native permission choices remain in effect."
        )
    except (OSError, ValueError) as exc:
        return f"Could not update the registered spec after native approval: {exc}. Preserve the native draft and recover the plan file before implementation."


def _slugify(title: str) -> str:
    """Filename-safe slug from a plan title, or "" when nothing usable remains."""
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug[:_MAX_SLUG_LEN].rstrip("-")


def _trusted_scratch_dirs() -> tuple[Path, ...]:
    """Claude-owned plan directories the hook may read from."""
    config_dir = claude_config_dir()
    if config_dir is None:
        return ()

    directories = [config_dir / "plans"]
    try:
        settings = json.loads((config_dir / "settings.json").read_text())
        configured = settings.get("plansDirectory") if isinstance(settings, dict) else None
        if isinstance(configured, str) and configured.strip():
            custom = Path(configured).expanduser()
            if not custom.is_absolute():
                project_root = current_project_root()
                if project_root is not None:
                    custom = project_root / custom
                else:
                    custom = config_dir / custom
            directories.append(custom)
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        pass

    resolved: list[Path] = []
    for directory in directories:
        try:
            candidate = directory.resolve()
        except OSError:
            continue
        if candidate not in resolved:
            resolved.append(candidate)
    return tuple(resolved)


def _read_scratch_plan(scratch: str) -> str:
    """Read a Claude-owned markdown scratch plan, never an arbitrary path."""
    try:
        candidate = Path(scratch).expanduser().resolve(strict=True)
        if candidate.suffix.lower() != ".md" or not any(
            candidate.is_relative_to(directory) for directory in _trusted_scratch_dirs()
        ):
            return ""
        return candidate.read_text()
    except (OSError, UnicodeDecodeError):
        return ""


def _plan_body(tool_input: dict, tool_response: dict) -> str:
    """The APPROVED plan markdown, preferring the response over the request.

    Three sources, in the order that keeps the captured document honest:

    1. ``tool_response.plan`` - what the tool actually approved. The user can
       edit a plan during the native review, so the response is the only source
       that reflects what they agreed to.
    2. ``tool_input.plan`` - what was proposed. Correct whenever the response
       carries no plan of its own, and the only source on builds that do not
       return one.
    3. ``tool_input.planFilePath`` - the scratch file Claude Code wrote, as a
       last resort when neither field carries the text.
    """
    for source in (tool_response.get("plan"), tool_input.get("plan")):
        if isinstance(source, str) and source.strip():
            return source
    scratch = tool_input.get("planFilePath")
    if isinstance(scratch, str) and scratch:
        return _read_scratch_plan(scratch)
    return ""


def _title_and_body(plan: str) -> tuple[str, str]:
    """Split the leading H1 off the plan; the rest becomes the Summary body.

    The H1 is lifted out because the captured file needs exactly one - the
    Console's parser takes the first `# ` line as the plan title and renders
    every `## ` heading below it as a section, so a second H1 in the body would
    read as stray text in the Summary card.
    """
    match = _H1_RE.search(plan)
    if match is None or plan[: match.start()].strip():
        return "", plan.strip()
    return match.group(1).strip(), plan[match.end() :].strip()


def _write_unique(plans_dir: Path, date: str, slug: str, render: Callable[[], str]) -> Path | None:
    """Write the capture to the first free `<date>-<slug>[-N].md`, or None.

    ⛔ Creation is exclusive (``O_CREAT|O_EXCL``), not check-then-write. Two
    sessions capturing plans with the same title on the same day would both see
    the same name as free and the second ``write_text`` would truncate the
    first. Losing a captured plan to a silent overwrite is the one failure this
    hook must not have, since the scratch copy it came from is throwaway.

    Never clobbers: a revised plan, a second planning session, or a re-run of
    this hook over an existing capture each get their own sibling file, leaving
    a document the user may have hand-edited untouched.
    """
    for counter in range(1, _MAX_CAPTURES_PER_TITLE + 1):
        suffix = "" if counter == 1 else f"-{counter}"
        target = plans_dir / f"{date}-{slug}{suffix}.md"
        try:
            with open(target, "x", encoding="utf-8") as handle:
                handle.write(render())
            return target
        except FileExistsError:
            continue
        except OSError:
            return None
    return None


def _render(title: str, body: str, date: str) -> str:
    """Compose the Pilot-format plan file.

    Every header field the format declares required is emitted, so the Console,
    the statusline, and the plan format's own readers agree on the file.

    The body is wrapped in `## Summary` only when it does not already open with
    a heading of its own. The Console renders one card per `## ` section, so
    wrapping a plan that starts with `## Context` would put an empty Summary
    card above it; a plan that is plain prose needs the wrapper, or its text
    belongs to no section at all.
    """
    sectioned = body.lstrip().startswith("## ")
    content = body if sectioned else f"## Summary\n\n{body}"
    return (
        f"# {title}\n"
        "\n"
        f"Created: {date}\n"
        "Agent: Claude Code\n"
        f"Status: {CAPTURED_STATUS}\n"
        "Approved: Yes\n"
        "Worktree: No\n"
        f"Type: {CAPTURED_TYPE}\n"
        "Iterations: 0\n"
        "\n"
        f"{content}\n"
    )


def _notice(target: Path, root: Path) -> str:
    try:
        shown = target.relative_to(root)
    except ValueError:
        shown = target
    return (
        f"[Pilot] Plan saved to {shown} (Status: {CAPTURED_STATUS} - a record, not a "
        "tracked run: no Pilot workflow will update it, and it stays out of the "
        "Console's active specs). Mention the path once, in one short sentence, the "
        "first time you report back. If the approach changes while you implement it, "
        "edit that file so the record matches what you actually did. Do NOT create a "
        "second plan file, and do NOT change its Status."
    )


_UNROOTED_NOTICE = (
    "[Pilot] Could not file this plan: no project root could be determined "
    "(no CLAUDE_PROJECT_ROOT and not inside a git repository), so there is no "
    "docs/plans/ to write to. Tell the user in one short sentence that the plan "
    "was NOT saved and still exists only in Claude Code's scratch copy."
)


def _write_failed_notice(root: Path) -> str:
    return (
        f"[Pilot] Could not file this plan into {root / Path(*PLANS_DIRNAME)} - the "
        "directory or file could not be written. Tell the user in one short "
        "sentence that the plan was NOT saved, so they can copy it out of "
        "Claude Code's scratch file before it is lost."
    )


def main() -> int:
    data = read_hook_stdin()
    if data.get("tool_name") != "ExitPlanMode":
        return 0

    raw_response = data.get("tool_response")
    response: dict = raw_response if isinstance(raw_response, dict) else {}
    if response.get("is_error"):
        return 0  # a rejected or failed exit approved nothing worth filing

    sid = resolve_session_id(str(data.get("session_id") or ""))
    pending = pending_native_spec(sid)
    if pending is not None:
        # A permission request or missing response is not proof that exit succeeded.
        # This branch precedes ordinary capture's live-run exclusion: it updates
        # the explicitly registered file instead of producing a SAVED duplicate.
        if not isinstance(raw_response, dict):
            return 0
        tool_input = data.get("tool_input")
        if not isinstance(tool_input, dict):
            return 0
        if pending.get("state") != "active":
            return 0
        if _current_unapproved_spec(pending) is None:
            print(
                post_tool_use_context(
                    "The registered spec changed during native planning; Pilot preserved it and the native draft. "
                    "Reconcile the files before implementation."
                )
            )
            return 0
        # Current Claude returns the accepted plan and native filePath in the
        # result, with empty tool_input. A returned path also supersedes stale
        # request text when the user edited the draft inside the approval UI.
        returned_path = response.get("planFilePath") or response.get("filePath")
        exit_identity = {"planFilePath": returned_path} if returned_path else tool_input
        if not native_spec_exit_matches(pending, exit_identity, sid, require_active=False):
            print(
                post_tool_use_context(
                    "Pilot could not bind this native exit to the prepared spec draft; both files were preserved. "
                    "Confirm the approved draft and repair the handoff before implementation."
                )
            )
            return 0
        plan = _plan_body(tool_input, response)
        if plan.strip():
            print(post_tool_use_context(_capture_native_spec(pending, plan, sid)))
        return 0
    if native_spec_marker(sid).exists():
        return 0  # an invalid/stale handoff cannot approve or become an unrelated SAVED capture

    try:
        from _lib.util import pilot_run_in_flight

        if pilot_run_in_flight(resolve_session_id(str(data.get("session_id") or ""))):
            return 0  # a Pilot workflow owns this plan mode leg and its own file
    except Exception:
        # Cannot tell whether a workflow is running: skip. A missing capture
        # costs a document; a wrong one puts a duplicate plan in the Console
        # list, competing with the run the user is actually watching.
        return 0

    tool_input = data.get("tool_input")
    if not isinstance(tool_input, dict):
        return 0
    plan = _plan_body(tool_input, response)
    if not plan.strip():
        return 0

    root = current_project_root()
    if root is None:
        # No authoritative project root, so there is no docs/plans/ this plan
        # provably belongs to. Say so instead of dropping it silently - the
        # scratch copy Claude Code wrote is the user's only remaining copy.
        print(post_tool_use_context(_UNROOTED_NOTICE))
        return 0

    title, body = _title_and_body(plan)
    date = datetime.date.today().isoformat()
    if not title:
        title = "Plan"
    slug = _slugify(title) or f"plan-{datetime.datetime.now().strftime('%H%M%S')}"

    try:
        plans_dir = root.joinpath(*PLANS_DIRNAME)
        plans_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        print(post_tool_use_context(_write_failed_notice(root)))
        return 0

    target = _write_unique(plans_dir, date, slug, lambda: _render(title, body, date))
    if target is None:
        print(post_tool_use_context(_write_failed_notice(root)))
        return 0

    print(post_tool_use_context(_notice(target, root)))
    return 0


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "prepare-spec":
        sys.exit(prepare_native_spec(sys.argv[2]))
    sys.exit(main())
