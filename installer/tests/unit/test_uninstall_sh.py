"""Tests for uninstall.sh — Codex cleanup coverage."""

from __future__ import annotations

import json
import os
import pty
import select
import subprocess
import sys
import time
from pathlib import Path

UNINSTALL_SH = Path(__file__).parent.parent.parent.parent / "uninstall.sh"


def _content() -> str:
    return UNINSTALL_SH.read_text()


def test_uninstall_sh_has_remove_codex_files_function():
    """uninstall.sh must define a remove_codex_files function."""
    assert "remove_codex_files()" in _content()


def test_uninstall_sh_remove_codex_files_called_in_main_flow():
    """remove_codex_files must be called in the main uninstall sequence."""
    content = _content()
    assert content.count("remove_codex_files") >= 2, (
        "Expected at least 2 occurrences: the function definition and a call site"
    )


def test_uninstall_sh_codex_dir_respects_codex_home():
    """CODEX_DIR must be defined honouring the CODEX_HOME env var."""
    content = _content()
    assert "CODEX_HOME" in content
    assert ".codex" in content


def test_uninstall_sh_agents_skills_dir_defined():
    """~/.agents/skills path must be referenced for skills cleanup."""
    assert ".agents/skills" in _content()


def test_uninstall_sh_codex_hooks_cleanup_uses_install_baseline():
    """Codex hook cleanup uses exact installed signatures, not a broad path match."""
    assert ".pilot-hooks-baseline.json" in _content()


def test_uninstall_sh_codex_config_toml_mcp_block_removed():
    """Managed MCP block start marker must be present so the removal logic can strip it."""
    assert "pilot-shell managed MCP servers" in _content()


def test_uninstall_sh_codex_agents_md_cleaned():
    """AGENTS.md cleanup must use the PILOT:START and PILOT:END markers."""
    content = _content()
    assert "PILOT:START" in content
    assert "PILOT:END" in content


def test_uninstall_sh_codex_skills_removed():
    """Known Pilot skill names must appear in the skills cleanup block."""
    content = _content()
    assert "spec-plan" in content
    assert "spec-implement" in content
    assert "spec-bugfix-plan" in content
    assert '"build"' in content
    assert '"investigate"' in content
    assert '"cleanup"' in content


def test_uninstall_sh_keeps_external_tool_cleanup_explicit_and_separate() -> None:
    """Shared tools are optional cleanup; native Claude and Codex are never targets."""
    content = _content()
    assert "--remove-tools" in content
    assert 'uninstall_npm_tool_if_owned "@colbymchenry/codegraph"' in content
    assert 'uninstall_uv_tool_if_owned "semble"' in content
    assert "semble uninstall" in content
    assert "rtk init -g --uninstall" in content
    assert "rtk init -g --codex --uninstall" in content
    assert 'uninstall_npm_tool_if_owned "impeccable"' in content
    assert 'uninstall_npm_tool_if_owned "@playwright/cli"' in content
    assert 'uninstall_npm_tool_if_owned "@ast-grep/cli"' in content
    assert 'uninstall_npm_tool_if_owned "fast-check"' in content
    assert 'uninstall_uv_tool_if_owned "hypothesis"' in content
    assert "npm uninstall -g @anthropic-ai/claude-code" not in content
    assert "claude plugins uninstall codex@openai-codex" not in content


def test_pilot_directory_is_removed_only_after_external_config_cleanup() -> None:
    """A best-effort cleanup failure must leave the CLI available for a retry."""
    content = _content()
    main = content[content.rindex("\nremove_shell_aliases\n") :]

    assert main.index("remove_codex_files") < main.index("remove_pilot_dir") < main.index("print_summary")


def test_uninstall_restores_claude_display_patch_before_removing_runtime(tmp_path: Path) -> None:
    home = tmp_path / "home"
    state_dir = home / ".pilot" / "claude-display-patch"
    state_dir.mkdir(parents=True)
    (state_dir / "state.json").write_text('{"schema":1,"entries":{}}\n')
    migration = home / ".claude" / ".pilot-display-patch-migration.json"
    migration.parent.mkdir()
    migration.write_text('{"version":1}\n')
    marker = home / "restored.txt"
    (state_dir / "restore.py").write_text(
        "import pathlib, sys\n"
        "assert sys.argv[1:] == ['--restore', '--state-dir', str(pathlib.Path(__file__).parent)]\n"
        f"pathlib.Path({str(marker)!r}).write_text('restored')\n"
    )

    result = _run_uninstall(home)

    assert result.returncode == 0, result.stderr
    assert marker.read_text() == "restored"
    assert not state_dir.exists()
    assert not migration.exists()


def test_uninstall_preserves_patch_backup_when_restore_fails(tmp_path: Path) -> None:
    home = tmp_path / "home"
    state_dir = home / ".pilot" / "claude-display-patch"
    state_dir.mkdir(parents=True)
    (state_dir / "state.json").write_text('{"schema":1,"entries":{}}\n')
    (state_dir / "restore.py").write_text("raise SystemExit(1)\n")
    backup = state_dir / "originals" / "original"
    backup.parent.mkdir()
    backup.write_text("official binary")

    result = _run_uninstall(home, script_args=["--yes", "--purge-data"])

    assert result.returncode == 1
    assert backup.read_text() == "official binary"
    assert "Claude Code display patch" in result.stdout


def test_uninstall_preserves_patch_state_when_restore_script_is_missing(tmp_path: Path) -> None:
    home = tmp_path / "home"
    state_dir = home / ".pilot" / "claude-display-patch"
    state_dir.mkdir(parents=True)
    state = state_dir / "state.json"
    state.write_text('{"schema":1,"entries":{}}\n')

    result = _run_uninstall(home)

    assert result.returncode == 1
    assert state.exists()


def test_default_uninstall_preserves_external_tools_even_when_pilot_owned(tmp_path: Path) -> None:
    home = tmp_path / "home"
    manifest = home / ".pilot" / ".pilot-owned-tools.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text('{"schema":1,"tools":["impeccable"]}\n')
    skill = home / ".agents" / "skills" / "impeccable" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("keep external tool\n")

    result = _run_uninstall(home)

    assert result.returncode == 0, result.stderr
    assert skill.read_text() == "keep external tool\n"
    assert manifest.exists()
    assert "Shared external tools were preserved" in result.stdout


def test_remove_tools_uninstalls_only_manifest_owned_tool_and_preserves_agents(tmp_path: Path) -> None:
    home = tmp_path / "home"
    manifest = home / ".pilot" / ".pilot-owned-tools.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text('{"schema":1,"tools":["impeccable"]}\n')
    for root in (home / ".agents" / "skills", home / ".claude" / "skills"):
        skill = root / "impeccable"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("managed external tool\n")

    claude_binary = home / ".claude" / "bin" / "claude"
    codex_binary = home / ".codex" / "bin" / "codex"
    claude_binary.parent.mkdir(parents=True, exist_ok=True)
    codex_binary.parent.mkdir(parents=True, exist_ok=True)
    claude_binary.write_text("native claude\n")
    codex_binary.write_text("native codex\n")

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    npm_log = tmp_path / "npm.log"
    npm = fake_bin / "npm"
    npm.write_text('#!/bin/bash\necho "$@" > "$NPM_LOG"\n')
    npm.chmod(0o755)

    result = _run_uninstall(
        home,
        {"PATH": f"{fake_bin}:{os.environ['PATH']}", "NPM_LOG": str(npm_log)},
        ["--yes", "--remove-tools"],
    )

    assert result.returncode == 0, result.stderr
    assert not (home / ".agents" / "skills" / "impeccable").exists()
    assert not (home / ".claude" / "skills" / "impeccable").exists()
    assert "uninstall -g impeccable" in npm_log.read_text()
    assert claude_binary.read_text() == "native claude\n"
    assert codex_binary.read_text() == "native codex\n"


def test_piped_script_reads_optional_choices_from_controlling_tty(tmp_path: Path) -> None:
    """`curl ... | bash` keeps script stdin separate from interactive answers."""
    home = tmp_path / "home"
    memory = home / ".pilot" / "memory" / "keep.json"
    memory.parent.mkdir(parents=True)
    memory.write_text('{"keep":true}\n')
    (home / ".pilot" / ".pilot-owned-tools.json").write_text('{"schema":1,"tools":["impeccable"]}\n')

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    npm = fake_bin / "npm"
    npm.write_text("#!/bin/bash\nexit 0\n")
    npm.chmod(0o755)

    result = _run_piped_uninstall_with_tty(
        home,
        [
            ("Also remove external tools", "y"),
            ("Also delete Pilot memories", "n"),
            ("Continue?", "y"),
        ],
        {"PATH": f"{fake_bin}:{os.environ['PATH']}"},
    )

    assert result.returncode == 0, result.stdout
    assert "Also remove external tools" in result.stdout
    assert "Also delete Pilot memories" in result.stdout
    assert memory.read_text() == '{"keep":true}\n'
    assert not (home / ".pilot" / ".pilot-owned-tools.json").exists()


def test_uninstall_stops_live_pilot_worker_without_signalling_unrelated_processes(tmp_path: Path) -> None:
    home = tmp_path / "home"
    worker_script = home / ".pilot" / "scripts" / "worker-service.cjs"
    worker_script.parent.mkdir(parents=True)
    worker_script.write_text("#!/bin/bash\nsleep 60\n")
    worker_script.chmod(0o755)
    worker = subprocess.Popen(["bash", str(worker_script)])
    try:
        pid_file = home / ".pilot" / "memory" / "worker.pid"
        pid_file.parent.mkdir(parents=True)
        pid_file.write_text(json.dumps({"pid": worker.pid, "port": 41777}))

        result = _run_uninstall(home)

        assert result.returncode == 0, result.stderr
        worker.wait(timeout=5)
        assert "Stopped Pilot Console worker" in result.stdout
    finally:
        if worker.poll() is None:
            worker.terminate()
            worker.wait(timeout=5)


def test_uninstall_sh_preserves_project_codegraph_indexes() -> None:
    """Global cleanup guidance must not suggest recursively deleting project indexes."""
    content = _content()
    assert "Project indexes (.codegraph/) were intentionally left intact." in content
    assert "codegraph uninit" in content
    assert "rm -rf .codegraph" not in content


def test_uninstall_sh_claude_dir_respects_claude_config_dir():
    """CLAUDE_DIR must honour CLAUDE_CONFIG_DIR, mirroring CODEX_DIR/CODEX_HOME."""
    assert "CLAUDE_CONFIG_DIR" in _content()


def _run_uninstall(
    home: Path,
    extra_env: dict[str, str] | None = None,
    script_args: list[str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["HOME"] = str(home)
    env.pop("CODEX_HOME", None)
    env.pop("CLAUDE_CONFIG_DIR", None)
    env.update(extra_env or {})
    return subprocess.run(
        ["bash", str(UNINSTALL_SH), *(script_args or ["--yes"])],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def _run_piped_uninstall_with_tty(
    home: Path,
    responses: list[tuple[str, str]],
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run `bash -s` with script stdin piped while answers arrive through /dev/tty."""
    env = os.environ.copy()
    env["HOME"] = str(home)
    env.pop("CODEX_HOME", None)
    env.pop("CLAUDE_CONFIG_DIR", None)
    env.update(extra_env or {})

    script_read, script_write = os.pipe()
    pid, master = pty.fork()
    if pid == 0:
        os.close(script_write)
        os.dup2(script_read, 0)
        os.close(script_read)
        os.execve("/bin/bash", ["bash", "-s"], env)

    os.close(script_read)
    payload = UNINSTALL_SH.read_bytes()
    while payload:
        written = os.write(script_write, payload)
        payload = payload[written:]
    os.close(script_write)

    output = bytearray()
    pending = list(responses)
    deadline = time.monotonic() + 30
    wait_status: int | None = None
    try:
        while time.monotonic() < deadline:
            readable, _, _ = select.select([master], [], [], 0.1)
            if readable:
                try:
                    chunk = os.read(master, 8192)
                except OSError:
                    chunk = b""
                output.extend(chunk)
                if pending and pending[0][0].encode() in output:
                    _, answer = pending.pop(0)
                    os.write(master, f"{answer}\n".encode())

            waited_pid, status = os.waitpid(pid, os.WNOHANG)
            if waited_pid == pid:
                wait_status = status
                break
        else:
            os.kill(pid, 9)
            _, wait_status = os.waitpid(pid, 0)
            raise AssertionError(f"Piped uninstaller timed out:\n{output.decode(errors='replace')}")
    finally:
        os.close(master)

    assert wait_status is not None
    assert pending == [], f"Prompts not observed: {pending}\n{output.decode(errors='replace')}"
    return subprocess.CompletedProcess(
        args=["bash", "-s"],
        returncode=os.waitstatus_to_exitcode(wait_status),
        stdout=output.decode(errors="replace"),
        stderr="",
    )


def _seed_pilot_profile(claude_dir: Path) -> None:
    """Minimal Pilot-installed profile: a manifest plus one managed rule."""
    (claude_dir / "rules").mkdir(parents=True, exist_ok=True)
    (claude_dir / "rules" / "testing.md").write_text("managed\n")
    (claude_dir / ".pilot-manifest.json").write_text('{"files": ["rules/testing.md"]}\n')


def test_relative_home_aborts_before_removing_anything(tmp_path: Path) -> None:
    """Every destructive target is HOME-derived, so HOME must be absolute."""
    sentinel = tmp_path / "relative" / ".pilot" / "keep.txt"
    sentinel.parent.mkdir(parents=True)
    sentinel.write_text("keep\n")
    env = os.environ.copy()
    env["HOME"] = "relative"

    result = subprocess.run(
        ["bash", str(UNINSTALL_SH), "--yes"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "HOME must be an absolute" in result.stderr
    assert sentinel.read_text() == "keep\n"


def test_home_resolving_to_filesystem_root_is_rejected() -> None:
    env = os.environ.copy()
    env["HOME"] = "/."

    result = subprocess.run(
        ["bash", str(UNINSTALL_SH), "--yes"],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "resolves to the filesystem root" in result.stderr


def test_relative_codex_home_aborts_before_removing_anything(tmp_path: Path) -> None:
    """A relative CODEX_HOME must never turn rm targets into cwd-relative paths."""
    home = tmp_path / "home"
    pilot = home / ".pilot" / "keep.txt"
    pilot.parent.mkdir(parents=True)
    pilot.write_text("keep\n")

    result = _run_uninstall(home, {"CODEX_HOME": "relative-codex"})

    assert result.returncode != 0
    assert "CODEX_HOME must be an absolute" in result.stderr
    assert pilot.read_text() == "keep\n"


def test_active_install_lock_refuses_uninstall_without_mutation(tmp_path: Path) -> None:
    """Uninstall cannot race an installer that owns the Pilot transaction lock."""
    home = tmp_path / "home"
    pilot = home / ".pilot"
    lock = pilot / ".bin-install.lock"
    lock.mkdir(parents=True)
    (lock / "pid").write_text(f"{os.getpid()}\n")
    (pilot / "keep.txt").write_text("keep\n")

    result = _run_uninstall(home)

    assert result.returncode != 0
    assert "install or update is currently running" in result.stderr
    assert (pilot / "keep.txt").read_text() == "keep\n"


def test_ownerless_install_lock_refuses_uninstall_without_mutation(tmp_path: Path) -> None:
    """An ownerless lock may be in mkdir-to-pid initialisation and fails closed."""
    home = tmp_path / "home"
    pilot = home / ".pilot"
    (pilot / ".bin-install.lock").mkdir(parents=True)
    (pilot / "keep.txt").write_text("keep\n")

    result = _run_uninstall(home)

    assert result.returncode != 0
    assert "has no owner" in result.stderr
    assert (pilot / "keep.txt").read_text() == "keep\n"


def test_stale_install_lock_fails_closed_then_allows_explicit_recovery(tmp_path: Path) -> None:
    """Dead-owner lock takeover is manual, race-free, and cleans transaction debris on retry."""
    home = tmp_path / "home"
    lock = home / ".pilot" / ".bin-install.lock"
    lock.mkdir(parents=True)
    (lock / "pid").write_text("999999999\n")
    (home / ".pilot" / ".bin-stage.crashed").mkdir()
    (home / ".pilot" / ".bin-backup.crashed").mkdir()
    (home / ".pilot" / ".bin-committed-backup.crashed").mkdir()

    blocked = _run_uninstall(home)

    assert blocked.returncode != 0
    assert "left a stale lock" in blocked.stderr
    assert (home / ".pilot").exists()

    (lock / "pid").unlink()
    lock.rmdir()
    result = _run_uninstall(home)

    assert result.returncode == 0, result.stderr
    assert not (home / ".pilot").exists()


def test_manifest_path_traversal_is_skipped(tmp_path: Path) -> None:
    """A corrupt manifest cannot delete a file outside the Claude profile."""
    home = tmp_path / "home"
    claude_dir = home / ".claude"
    (claude_dir / "rules").mkdir(parents=True)
    managed = claude_dir / "rules" / "testing.md"
    managed.write_text("managed\n")
    outside = home / "outside.txt"
    outside.write_text("keep\n")
    (claude_dir / ".pilot-manifest.json").write_text('{"files": ["rules/testing.md", "rules/../../outside.txt"]}\n')

    result = _run_uninstall(home)

    assert result.returncode == 0, result.stderr
    assert not managed.exists()
    assert outside.read_text() == "keep\n"
    assert "unsafe manifest entry" in result.stdout


def test_manifest_parent_symlink_escape_is_skipped(tmp_path: Path) -> None:
    """A managed-looking path cannot traverse a user-controlled parent symlink."""
    home = tmp_path / "home"
    claude_dir = home / ".claude"
    outside = home / "outside"
    outside.mkdir(parents=True)
    outside_file = outside / "managed.md"
    outside_file.write_text("keep\n")
    skills = claude_dir / "skills"
    skills.mkdir(parents=True)
    (skills / "escape").symlink_to(outside, target_is_directory=True)
    (claude_dir / ".pilot-manifest.json").write_text('{"files": ["skills/escape/managed.md"]}\n')

    result = _run_uninstall(home)

    assert result.returncode == 0, result.stderr
    assert outside_file.read_text() == "keep\n"
    assert "unsafe manifest entry" in result.stdout


def test_symlinked_pilot_root_is_rejected_without_touching_target(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    outside = tmp_path / "outside-pilot"
    (outside / "bin").mkdir(parents=True)
    sentinel = outside / "bin" / "pilot"
    sentinel.write_text("keep\n")
    (home / ".pilot").symlink_to(outside, target_is_directory=True)

    result = _run_uninstall(home)

    assert result.returncode != 0
    assert "~/.pilot is a symlink" in result.stderr
    assert sentinel.read_text() == "keep\n"


def test_malformed_claude_manifest_preserves_files_and_reports_partial(tmp_path: Path) -> None:
    home = tmp_path / "home"
    claude_dir = home / ".claude"
    managed = claude_dir / "rules" / "testing.md"
    managed.parent.mkdir(parents=True)
    managed.write_text("preserve until ownership is readable\n")
    manifest = claude_dir / ".pilot-manifest.json"
    manifest.write_text("{broken")
    (home / ".pilot" / "bin").mkdir(parents=True)

    result = _run_uninstall(home)

    assert result.returncode != 0
    assert managed.read_text() == "preserve until ownership is readable\n"
    assert manifest.read_text() == "{broken"
    assert "partially uninstalled" in result.stdout


def test_claude_plugin_cli_failure_does_not_abort_local_cleanup(tmp_path: Path) -> None:
    """Best-effort external plugin cleanup cannot strand the local uninstall."""
    home = tmp_path / "home"
    pilot = home / ".pilot"
    pilot.mkdir(parents=True)
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    claude = fake_bin / "claude"
    claude.write_text("#!/bin/bash\nexit 1\n")
    claude.chmod(0o755)

    result = _run_uninstall(home, {"PATH": f"{fake_bin}:{os.environ['PATH']}"})

    assert result.returncode == 0, result.stderr
    assert not pilot.exists()


def test_shell_cleanup_removes_only_pilot_block_and_preserves_user_commands(tmp_path: Path) -> None:
    """User aliases and multiline functions with overlapping names are never inferred as Pilot-owned."""
    home = tmp_path / "home"
    home.mkdir()
    zshrc = home / ".zshrc"
    zshrc.write_text(
        """# user commands
alias pilot='my-own-pilot'
claude() {
  echo user-claude
}

# Pilot Shell
export PATH="$HOME/.pilot/bin:$HOME/.bun/bin:$PATH"
alias pilot="$HOME/.pilot/bin/pilot"
alias ccp="$HOME/.pilot/bin/pilot"
claude() { local _sid="$$-$RANDOM"; PILOT_SESSION_ID=$_sid command claude "$@"; }
codex() ( PILOT_SESSION_ID="$$-$RANDOM" command codex "$@"; )

# after
"""
    )
    (home / ".pilot").mkdir()

    result = _run_uninstall(home)

    assert result.returncode == 0, result.stderr
    content = zshrc.read_text()
    assert "my-own-pilot" in content
    assert "echo user-claude" in content
    assert "PILOT_SESSION_ID" not in content
    assert "$HOME/.pilot/bin" not in content
    assert "# after" in content
    subprocess.run(["/bin/bash", "-n", str(zshrc)], check=True)


def test_alias_only_partial_install_is_detected_and_cleaned(tmp_path: Path) -> None:
    """A legacy shell-only install is not misreported as 'nothing to remove'."""
    home = tmp_path / "home"
    home.mkdir()
    zshrc = home / ".zshrc"
    zshrc.write_text('# Pilot Shell\nexport PATH="$HOME/.pilot/bin:$PATH"\nalias pilot="$HOME/.pilot/bin/pilot"\n')

    result = _run_uninstall(home)

    assert result.returncode == 0, result.stderr
    assert "$HOME/.pilot/bin" not in zshrc.read_text()
    assert "Cleaned .zshrc" in result.stdout


def test_user_session_environment_lines_are_preserved(tmp_path: Path) -> None:
    """Pilot owns wrapper functions, not every user-authored PILOT_SESSION_ID export."""
    home = tmp_path / "home"
    home.mkdir()
    zshrc = home / ".zshrc"
    zshrc.write_text("export PILOT_SESSION_ID='my-manual-session'\n")
    (home / ".pilot" / "bin").mkdir(parents=True)

    result = _run_uninstall(home)

    assert result.returncode == 0, result.stderr
    assert zshrc.read_text() == "export PILOT_SESSION_ID='my-manual-session'\n"


def test_user_modified_path_line_is_preserved(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    zshrc = home / ".zshrc"
    line = 'export PATH="$HOME/bin:$HOME/.pilot/bin:$PATH"\n'
    zshrc.write_text(line)
    (home / ".pilot" / "bin").mkdir(parents=True)

    result = _run_uninstall(home)

    assert result.returncode == 0, result.stderr
    assert zshrc.read_text() == line


def test_symlinked_shell_config_target_is_updated_without_replacing_symlink(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    dotfiles = tmp_path / "dotfiles"
    dotfiles.mkdir()
    target = dotfiles / "zshrc"
    target.write_text('# Pilot Shell\nexport PATH="$HOME/.pilot/bin:$PATH"\n# keep\n')
    (home / ".zshrc").symlink_to(target)
    (home / ".pilot" / "bin").mkdir(parents=True)

    result = _run_uninstall(home)

    assert result.returncode == 0, result.stderr
    assert (home / ".zshrc").is_symlink()
    assert target.read_text() == "# keep\n"


def test_modified_statusline_object_is_preserved_as_a_complete_value(tmp_path: Path) -> None:
    """Changing one nested field preserves required sibling fields from the baseline."""
    home = tmp_path / "home"
    claude_dir = home / ".claude"
    claude_dir.mkdir(parents=True)
    baseline = {
        "statusLine": {"type": "command", "command": "/old/pilot statusline", "padding": 0},
        "env": {"PILOT_MODE": "quick"},
    }
    current = {
        "statusLine": {"type": "command", "command": "/user/custom-statusline", "padding": 0},
        "env": {"PILOT_MODE": "quick"},
    }
    (claude_dir / ".pilot-settings-baseline.json").write_text(json.dumps(baseline))
    (claude_dir / "settings.json").write_text(json.dumps(current))
    (home / ".pilot").mkdir()

    result = _run_uninstall(home)

    assert result.returncode == 0, result.stderr
    settings = json.loads((claude_dir / "settings.json").read_text())
    assert settings["statusLine"] == current["statusLine"]
    assert "env" not in settings


def test_user_env_key_survives_while_pilot_env_keys_are_removed(tmp_path: Path) -> None:
    """Independent settings maps are cleaned recursively without losing user entries."""
    home = tmp_path / "home"
    claude_dir = home / ".claude"
    claude_dir.mkdir(parents=True)
    baseline = {"env": {"PILOT_MODE": "quick", "CLAUDE_PILOT_MODEL": "haiku"}}
    current = {"env": {**baseline["env"], "USER_API_HOST": "https://example.test"}}
    (claude_dir / ".pilot-settings-baseline.json").write_text(json.dumps(baseline))
    (claude_dir / "settings.json").write_text(json.dumps(current))
    (home / ".pilot").mkdir()

    result = _run_uninstall(home)

    assert result.returncode == 0, result.stderr
    settings = json.loads((claude_dir / "settings.json").read_text())
    assert settings == {"env": {"USER_API_HOST": "https://example.test"}}


def test_uninstall_preserves_plugins_without_pilot_ownership_manifest(tmp_path: Path) -> None:
    """Installed plugin presence alone is not proof that Pilot owns it."""
    home = tmp_path / "home"
    (home / ".pilot").mkdir(parents=True)
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    log = tmp_path / "claude.log"
    claude = fake_bin / "claude"
    claude.write_text(
        """#!/bin/bash
printf '%s\n' "$*" >> "$CLAUDE_TEST_LOG"
if [ "$1 $2" = "plugins list" ]; then
  printf '%s\n' 'codex@openai-codex' 'chrome-devtools-mcp@chrome-devtools-plugins'
fi
"""
    )
    claude.chmod(0o755)

    result = _run_uninstall(
        home,
        {"PATH": f"{fake_bin}:{os.environ['PATH']}", "CLAUDE_TEST_LOG": str(log)},
        ["--yes", "--remove-tools"],
    )

    assert result.returncode == 0, result.stderr
    assert not log.exists() or "plugins uninstall" not in log.read_text()


def test_uninstall_removes_only_marker_owned_codex_review_agents(tmp_path: Path) -> None:
    """Generated review agents are current managed artifacts; same-name user files survive."""
    home = tmp_path / "home"
    agents = home / ".codex" / "agents"
    agents.mkdir(parents=True)
    managed = agents / "spec-review.toml"
    managed.write_text("# pilot-shell managed Codex review agent\nname = 'spec-review'\n")
    user = agents / "changes-review.toml"
    user.write_text("name = 'changes-review'\ndescription = 'mine'\n")

    result = _run_uninstall(home)

    assert result.returncode == 0, result.stderr
    assert not managed.exists()
    assert user.read_text() == "name = 'changes-review'\ndescription = 'mine'\n"


def test_symlinked_codex_agents_directory_is_preserved_and_reported(tmp_path: Path) -> None:
    home = tmp_path / "home"
    codex_dir = home / ".codex"
    codex_dir.mkdir(parents=True)
    outside = tmp_path / "outside-agents"
    outside.mkdir()
    managed = outside / "spec-review.toml"
    managed.write_text("# pilot-shell managed Codex review agent\n")
    (codex_dir / "agents").symlink_to(outside, target_is_directory=True)
    (home / ".pilot" / "bin").mkdir(parents=True)

    result = _run_uninstall(home)

    assert result.returncode != 0
    assert managed.exists()
    assert "partially uninstalled" in result.stdout


def test_malformed_lsp_ownership_manifest_never_uninstalls_plugins(tmp_path: Path) -> None:
    home = tmp_path / "home"
    pilot = home / ".pilot"
    pilot.mkdir(parents=True)
    (pilot / ".pilot-lsp-plugins.json").write_text('{"note": "vtsls@claude-code-lsps"}')
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    log = tmp_path / "claude.log"
    claude = fake_bin / "claude"
    claude.write_text('#!/bin/bash\nprintf \'%s\\n\' "$*" >> "$CLAUDE_TEST_LOG"\n')
    claude.chmod(0o755)

    result = _run_uninstall(
        home,
        {"PATH": f"{fake_bin}:{os.environ['PATH']}", "CLAUDE_TEST_LOG": str(log)},
        ["--yes", "--remove-tools"],
    )

    assert result.returncode != 0
    assert not log.exists() or "plugins uninstall" not in log.read_text()
    assert (pilot / ".pilot-lsp-plugins.json").exists()


def test_default_uninstall_preserves_pilot_owned_lsp_plugins(tmp_path: Path) -> None:
    """Agent plugins are shared tools and require the explicit tool-removal choice."""
    home = tmp_path / "home"
    pilot = home / ".pilot"
    pilot.mkdir(parents=True)
    manifest = pilot / ".pilot-lsp-plugins.json"
    manifest.write_text('{"plugins":["vtsls@claude-code-lsps"]}\n')
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    log = tmp_path / "claude.log"
    claude = fake_bin / "claude"
    claude.write_text('#!/bin/bash\nprintf \'%s\\n\' "$*" >> "$CLAUDE_TEST_LOG"\n')
    claude.chmod(0o755)

    result = _run_uninstall(
        home,
        {"PATH": f"{fake_bin}:{os.environ['PATH']}", "CLAUDE_TEST_LOG": str(log)},
    )

    assert result.returncode == 0, result.stderr
    assert not log.exists()
    assert manifest.exists()


def test_failed_config_cleanup_keeps_baseline_and_pilot_home_for_retry(tmp_path: Path) -> None:
    """A partial uninstall is non-zero and retains recovery metadata plus the CLI."""
    home = tmp_path / "home"
    claude_dir = home / ".claude"
    claude_dir.mkdir(parents=True)
    baseline = claude_dir / ".pilot-settings-baseline.json"
    baseline.write_text(json.dumps({"statusLine": {"type": "command"}}))
    (claude_dir / "settings.json").write_text(json.dumps({"statusLine": {"type": "command"}}))
    pilot = home / ".pilot"
    (pilot / "bin").mkdir(parents=True)
    (pilot / "bin" / "pilot").write_text("working runtime\n")
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    python3 = fake_bin / "python3"
    python3.write_text("#!/bin/bash\nexit 1\n")
    python3.chmod(0o755)
    uv = fake_bin / "uv"
    uv.write_text("#!/bin/bash\nexit 1\n")
    uv.chmod(0o755)

    result = _run_uninstall(home, {"PATH": f"{fake_bin}:{os.environ['PATH']}"})

    assert result.returncode != 0
    assert "partially uninstalled" in result.stdout
    assert baseline.exists()
    assert pilot.exists()


def test_uv_python_fallback_completes_uninstall_without_working_system_python(tmp_path: Path) -> None:
    home = tmp_path / "home"
    claude_dir = home / ".claude"
    claude_dir.mkdir(parents=True)
    baseline = {"env": {"PILOT_MODE": "quick"}}
    (claude_dir / ".pilot-settings-baseline.json").write_text(json.dumps(baseline))
    (claude_dir / "settings.json").write_text(json.dumps(baseline))
    (home / ".pilot" / "bin").mkdir(parents=True)
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    python3 = fake_bin / "python3"
    python3.write_text("#!/bin/bash\nexit 1\n")
    python3.chmod(0o755)
    uv = fake_bin / "uv"
    uv.write_text(
        f'''#!/bin/bash
while [ "$#" -gt 0 ] && [ "$1" != python ]; do shift; done
[ "$#" -gt 0 ] && shift
exec "{sys.executable}" "$@"
'''
    )
    uv.chmod(0o755)

    result = _run_uninstall(home, {"PATH": f"{fake_bin}:{os.environ['PATH']}"})

    assert result.returncode == 0, result.stderr
    assert not (claude_dir / "settings.json").exists()


def test_default_uninstall_removes_runtime_but_preserves_user_data(tmp_path: Path) -> None:
    """Memory, sessions, settings, and unknown user files survive without --purge-data."""
    home = tmp_path / "home"
    pilot = home / ".pilot"
    (pilot / "bin").mkdir(parents=True)
    (pilot / "bin" / "pilot").write_text("runtime\n")
    (pilot / "hooks").mkdir()
    (pilot / "hooks" / "managed.py").write_text("runtime\n")
    (pilot / "memory").mkdir()
    (pilot / "memory" / "pilot-memory.db").write_text("memories\n")
    (pilot / "sessions").mkdir()
    (pilot / "sessions" / "session.json").write_text("session\n")
    (pilot / "config.json").write_text('{"customization": {"source": "team"}}\n')
    (pilot / "my-notes.txt").write_text("keep\n")

    result = _run_uninstall(home)

    assert result.returncode == 0, result.stderr
    assert not (pilot / "bin").exists()
    assert not (pilot / "hooks").exists()
    assert (pilot / "memory" / "pilot-memory.db").read_text() == "memories\n"
    assert (pilot / "sessions" / "session.json").read_text() == "session\n"
    assert (pilot / "config.json").exists()
    assert (pilot / "my-notes.txt").read_text() == "keep\n"
    assert "User data preserved" in result.stdout


def test_purge_data_removes_entire_pilot_home(tmp_path: Path) -> None:
    """Full data deletion is explicit and removes the remaining Pilot home."""
    home = tmp_path / "home"
    data = home / ".pilot" / "memory" / "pilot-memory.db"
    data.parent.mkdir(parents=True)
    data.write_text("memories\n")

    result = _run_uninstall(home, script_args=["--yes", "--purge-data"])

    assert result.returncode == 0, result.stderr
    assert not (home / ".pilot").exists()


class TestClaudeConfigDirIsolation:
    """uninstall.sh derives rm targets, so its path resolution is safety-critical."""

    def test_relative_config_dir_aborts_before_removing_anything(self, tmp_path: Path):
        """A relative value must abort, never resolve rm targets against cwd."""
        home = tmp_path / "home"
        personal = home / ".claude"
        _seed_pilot_profile(personal)

        result = _run_uninstall(home, {"CLAUDE_CONFIG_DIR": "relative/path"})

        assert result.returncode != 0, "expected a non-zero exit for a relative CLAUDE_CONFIG_DIR"
        assert (personal / "rules" / "testing.md").exists(), "personal profile was touched"
        assert (personal / ".pilot-manifest.json").exists()

    def test_explicit_config_dir_without_pilot_install_aborts(self, tmp_path: Path):
        """Pointing at a profile Pilot was never installed into must not half-clean."""
        home = tmp_path / "home"
        personal = home / ".claude"
        _seed_pilot_profile(personal)
        empty = home / ".claude_empty"
        empty.mkdir(parents=True)

        result = _run_uninstall(home, {"CLAUDE_CONFIG_DIR": str(empty)})

        assert result.returncode != 0
        assert "No Pilot install found" in result.stderr
        assert (personal / "rules" / "testing.md").exists()

    def test_missing_manifest_still_tolerated_when_unset(self, tmp_path: Path):
        """Legacy pre-manifest installs must still uninstall from the default dir."""
        home = tmp_path / "home"
        (home / ".claude").mkdir(parents=True)
        (home / ".pilot").mkdir(parents=True)

        result = _run_uninstall(home)

        assert result.returncode == 0, result.stderr
        assert not (home / ".pilot").exists(), "~/.pilot should still be removed"

    def test_custom_config_dir_leaves_personal_profile_untouched(self, tmp_path: Path):
        home = tmp_path / "home"
        personal = home / ".claude"
        _seed_pilot_profile(personal)
        work = home / ".claude_work"
        _seed_pilot_profile(work)

        result = _run_uninstall(home, {"CLAUDE_CONFIG_DIR": str(work)})

        assert result.returncode == 0, result.stderr
        assert not (work / "rules" / "testing.md").exists(), "custom profile was not cleaned"
        assert (personal / "rules" / "testing.md").exists(), "personal profile was cleaned"
        assert (personal / ".pilot-manifest.json").exists()


def test_uninstall_removes_shell_wrappers_and_codex_env_block(tmp_path: Path):
    """Uninstall should remove Pilot shell wrappers and Codex managed env vars."""
    home = tmp_path / "home"
    home.mkdir()
    zshrc = home / ".zshrc"
    zshrc.write_text(
        "\n".join(
            [
                "# before",
                "# Pilot Shell",
                'export PATH="$HOME/.pilot/bin:$HOME/.bun/bin:$PATH"',
                'alias pilot="$HOME/.pilot/bin/pilot"',
                'alias ccp="$HOME/.pilot/bin/pilot"',
                'claude() { local _sid="$$-$RANDOM"; PILOT_SESSION_ID=$_sid CLAUDE_CODE_TASK_LIST_ID="pilot-$_sid" command claude "$@"; }',
                'codex() { PILOT_SESSION_ID="$$-$RANDOM" command codex "$@"; }',
                "# after",
                "",
            ]
        )
    )

    codex_dir = home / ".codex"
    codex_dir.mkdir()
    (codex_dir / "config.toml").write_text(
        "\n".join(
            [
                'approval_policy = "never"',
                "# --- pilot-shell managed env vars ---",
                "[shell_environment_policy.set]",
                'PILOT_PLAN_APPROVAL_ENABLED = "false"',
                "# --- end pilot-shell managed env vars ---",
                'model = "gpt-5"',
                "",
            ]
        )
    )

    env = os.environ.copy()
    env["HOME"] = str(home)
    env.pop("CODEX_HOME", None)
    result = subprocess.run(["bash", str(UNINSTALL_SH), "--yes"], env=env, text=True, capture_output=True, check=False)

    assert result.returncode == 0, result.stderr
    shell_content = zshrc.read_text()
    assert "claude()" not in shell_content
    assert "codex()" not in shell_content
    assert "alias pilot=" not in shell_content
    assert "# before" in shell_content
    assert "# after" in shell_content

    codex_config = (codex_dir / "config.toml").read_text()
    assert "pilot-shell managed env vars" not in codex_config
    assert "PILOT_PLAN_APPROVAL_ENABLED" not in codex_config
    assert 'approval_policy = "never"' in codex_config
    assert 'model = "gpt-5"' in codex_config


def test_uninstall_removes_pilot_model_catalog_and_preserves_codex_config(tmp_path: Path):
    home = tmp_path / "home"
    codex_dir = home / ".codex"
    codex_dir.mkdir(parents=True)
    catalog = codex_dir / ".pilot-model-catalog.json"
    catalog.write_text('{"models": []}\n')
    config = codex_dir / "config.toml"
    config.write_text(f'approval_policy = "never"\nmodel_catalog_json = "{catalog}"\nmodel = "gpt-5.6-sol"\n')

    result = _run_uninstall(home)

    assert result.returncode == 0, result.stderr
    assert not catalog.exists()
    codex_config = config.read_text()
    assert "model_catalog_json" not in codex_config
    assert 'approval_policy = "never"' in codex_config
    assert 'model = "gpt-5.6-sol"' in codex_config


def test_uninstall_removes_baselined_codex_hook_and_preserves_user_pilot_hook(tmp_path: Path):
    home = tmp_path / "home"
    codex_dir = home / ".codex"
    codex_dir.mkdir(parents=True)
    managed = {"hooks": [{"type": "command", "command": 'python "$HOME/.pilot/hooks/stop.py"'}]}
    user = {
        "matcher": "Bash",
        "hooks": [{"type": "command", "command": 'python "$HOME/.pilot/custom/my-hook.py"'}],
    }
    (codex_dir / "hooks.json").write_text(json.dumps({"hooks": {"Stop": [managed], "PreToolUse": [user]}}))
    (codex_dir / ".pilot-hooks-baseline.json").write_text(json.dumps({"Stop": [managed]}))

    result = _run_uninstall(home)

    assert result.returncode == 0, result.stderr
    hooks = json.loads((codex_dir / "hooks.json").read_text())["hooks"]
    assert "Stop" not in hooks
    assert hooks["PreToolUse"] == [user]
    assert not (codex_dir / ".pilot-hooks-baseline.json").exists()


def test_missing_codex_hook_baseline_preserves_user_hook_and_reports_partial(tmp_path: Path) -> None:
    """A ~/.pilot hook path alone is not ownership evidence."""
    home = tmp_path / "home"
    codex_dir = home / ".codex"
    codex_dir.mkdir(parents=True)
    user = {
        "matcher": "Bash",
        "hooks": [{"type": "command", "command": 'python "$HOME/.pilot/hooks/my-own.py"'}],
    }
    hooks_file = codex_dir / "hooks.json"
    hooks_file.write_text(json.dumps({"hooks": {"PreToolUse": [user]}}))
    (home / ".pilot" / "bin").mkdir(parents=True)

    result = _run_uninstall(home)

    assert result.returncode != 0
    assert "partially uninstalled" in result.stdout
    assert json.loads(hooks_file.read_text())["hooks"]["PreToolUse"] == [user]


def test_malformed_codex_hook_file_keeps_baseline_and_runtime(tmp_path: Path) -> None:
    home = tmp_path / "home"
    codex_dir = home / ".codex"
    codex_dir.mkdir(parents=True)
    hooks_file = codex_dir / "hooks.json"
    hooks_file.write_text("{broken")
    baseline = codex_dir / ".pilot-hooks-baseline.json"
    baseline.write_text("{}")
    pilot = home / ".pilot" / "bin"
    pilot.mkdir(parents=True)

    result = _run_uninstall(home)

    assert result.returncode != 0
    assert hooks_file.read_text() == "{broken"
    assert baseline.exists()
    assert pilot.exists()


def test_reversed_codex_config_markers_are_preserved_and_report_partial(tmp_path: Path) -> None:
    home = tmp_path / "home"
    codex_dir = home / ".codex"
    codex_dir.mkdir(parents=True)
    config = codex_dir / "config.toml"
    original = "# --- end pilot-shell managed env vars ---\nuser = true\n# --- pilot-shell managed env vars ---\n"
    config.write_text(original)
    (home / ".pilot" / "bin").mkdir(parents=True)

    result = _run_uninstall(home)

    assert result.returncode != 0
    assert config.read_text() == original


def test_duplicate_codex_agents_markers_are_preserved_and_report_partial(tmp_path: Path) -> None:
    home = tmp_path / "home"
    codex_dir = home / ".codex"
    codex_dir.mkdir(parents=True)
    agents = codex_dir / "AGENTS.md"
    original = "<!-- PILOT:START -->\none\n<!-- PILOT:START -->\ntwo\n<!-- PILOT:END -->\n"
    agents.write_text(original)
    (home / ".pilot" / "bin").mkdir(parents=True)

    result = _run_uninstall(home)

    assert result.returncode != 0
    assert agents.read_text() == original


def test_malformed_codex_rules_manifest_is_preserved_and_reported(tmp_path: Path) -> None:
    home = tmp_path / "home"
    rules_dir = home / ".codex" / "rules"
    rules_dir.mkdir(parents=True)
    manifest = rules_dir / ".pilot-rules.json"
    manifest.write_text("{broken")
    managed = rules_dir / "managed.rules"
    managed.write_text("keep until retry\n")
    (home / ".pilot" / "bin").mkdir(parents=True)

    result = _run_uninstall(home)

    assert result.returncode != 0
    assert manifest.read_text() == "{broken"
    assert managed.read_text() == "keep until retry\n"


def test_uninstall_removes_generated_investigate_artifacts_and_preserves_user_files(tmp_path: Path):
    home = tmp_path / "home"
    skill_dir = home / ".agents" / "skills" / "investigate"
    references = skill_dir / "references"
    metadata_dir = skill_dir / "agents"
    references.mkdir(parents=True)
    metadata_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("generated skill\n")
    (metadata_dir / "openai.yaml").write_text("policy: {}\n")
    (references / "managed.md").write_text("managed\n")
    (references / "user-notes.md").write_text("keep\n")
    (skill_dir / "user-file.txt").write_text("keep\n")
    (skill_dir / ".pilot-resources.json").write_text(
        json.dumps({"files": ["references/managed.md"], "directories": ["references"]})
    )

    result = _run_uninstall(home)

    assert result.returncode == 0, result.stderr
    assert not (skill_dir / "SKILL.md").exists()
    assert not (metadata_dir / "openai.yaml").exists()
    assert not (skill_dir / ".pilot-resources.json").exists()
    assert not (references / "managed.md").exists()
    assert (references / "user-notes.md").read_text() == "keep\n"
    assert (skill_dir / "user-file.txt").read_text() == "keep\n"


def test_uninstall_detects_and_removes_generated_cleanup_skill(tmp_path: Path):
    """A cleanup-only Codex install is still Pilot content and fully reversible."""
    home = tmp_path / "home"
    skill_dir = home / ".agents" / "skills" / "cleanup"
    steps_dir = skill_dir / "steps"
    metadata_dir = skill_dir / "agents"
    steps_dir.mkdir(parents=True)
    metadata_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("generated cleanup skill\n")
    (metadata_dir / "openai.yaml").write_text("policy: {}\n")
    (steps_dir / "01-scope.md").write_text("managed\n")
    (skill_dir / ".pilot-resources.json").write_text(
        json.dumps({"files": ["steps/01-scope.md"], "directories": ["steps"]})
    )

    result = _run_uninstall(home)

    assert result.returncode == 0, result.stderr
    assert not skill_dir.exists()


def test_uninstall_removes_cleanup_resources_and_preserves_user_files(tmp_path: Path):
    home = tmp_path / "home"
    skill_dir = home / ".agents" / "skills" / "cleanup"
    steps_dir = skill_dir / "steps"
    scripts_dir = skill_dir / "scripts"
    metadata_dir = skill_dir / "agents"
    steps_dir.mkdir(parents=True)
    scripts_dir.mkdir()
    metadata_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("generated cleanup skill\n")
    (metadata_dir / "openai.yaml").write_text("policy: {}\n")
    (steps_dir / "01-scope.md").write_text("managed\n")
    (scripts_dir / "codegraph-candidates.mjs").write_text("managed\n")
    (scripts_dir / "user-helper.mjs").write_text("keep\n")
    (skill_dir / "user-notes.md").write_text("keep\n")
    (skill_dir / ".pilot-resources.json").write_text(
        json.dumps(
            {
                "files": ["steps/01-scope.md", "scripts/codegraph-candidates.mjs"],
                "directories": ["steps", "scripts"],
            }
        )
    )

    result = _run_uninstall(home)

    assert result.returncode == 0, result.stderr
    assert not (skill_dir / "SKILL.md").exists()
    assert not (metadata_dir / "openai.yaml").exists()
    assert not (steps_dir / "01-scope.md").exists()
    assert not (scripts_dir / "codegraph-candidates.mjs").exists()
    assert (scripts_dir / "user-helper.mjs").read_text() == "keep\n"
    assert (skill_dir / "user-notes.md").read_text() == "keep\n"


def test_uninstall_malformed_skill_resource_manifest_preserves_unknown_files(tmp_path: Path):
    home = tmp_path / "home"
    skill_dir = home / ".agents" / "skills" / "investigate"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("generated skill\n")
    (skill_dir / ".pilot-resources.json").write_text("{broken")
    (skill_dir / "unknown-resource.txt").write_text("keep\n")

    result = _run_uninstall(home)

    assert result.returncode != 0
    assert "partially uninstalled" in result.stdout
    assert (skill_dir / "SKILL.md").exists()
    assert (skill_dir / ".pilot-resources.json").exists()
    assert (skill_dir / "unknown-resource.txt").read_text() == "keep\n"


def test_uninstall_preserves_unowned_same_name_investigate_skill(tmp_path: Path):
    home = tmp_path / "home"
    skill_dir = home / ".agents" / "skills" / "investigate"
    metadata_dir = skill_dir / "agents"
    metadata_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("user-owned investigate\n")
    (metadata_dir / "openai.yaml").write_text("user-owned metadata\n")

    result = _run_uninstall(home)

    assert result.returncode == 0, result.stderr
    assert (skill_dir / "SKILL.md").read_text() == "user-owned investigate\n"
    assert (metadata_dir / "openai.yaml").read_text() == "user-owned metadata\n"


def test_uninstall_preserves_unowned_same_name_cleanup_skill(tmp_path: Path):
    home = tmp_path / "home"
    skill_dir = home / ".agents" / "skills" / "cleanup"
    metadata_dir = skill_dir / "agents"
    metadata_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("user-owned cleanup\n")
    (metadata_dir / "openai.yaml").write_text("user-owned metadata\n")

    result = _run_uninstall(home)

    assert result.returncode == 0, result.stderr
    assert (skill_dir / "SKILL.md").read_text() == "user-owned cleanup\n"
    assert (metadata_dir / "openai.yaml").read_text() == "user-owned metadata\n"
