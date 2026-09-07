"""Tests for finalize step."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, call, patch


class TestGetPilotVersion:
    """Test _get_pilot_version function."""

    @patch("installer.steps.finalize.subprocess.run")
    def test_returns_version_from_pilot_binary(self, mock_run):
        """_get_pilot_version returns version from pilot --version output."""
        from installer.steps.finalize import _get_pilot_version

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Pilot Shell v5.2.3",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("installer.steps.finalize.Path.home", return_value=Path(tmpdir)):
                bin_dir = Path(tmpdir) / ".pilot" / "bin"
                bin_dir.mkdir(parents=True)
                pilot_path = bin_dir / "pilot"
                pilot_path.write_text("#!/bin/bash\necho 'Pilot Shell v5.2.3'")

                version = _get_pilot_version()
                assert version == "5.2.3"

    @patch("installer.steps.finalize.subprocess.run")
    def test_returns_dev_version_from_pilot_binary(self, mock_run):
        """_get_pilot_version returns dev version from pilot --version output."""
        from installer.steps.finalize import _get_pilot_version

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Pilot Shell vdev-abc1234-20260125",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("installer.steps.finalize.Path.home", return_value=Path(tmpdir)):
                bin_dir = Path(tmpdir) / ".pilot" / "bin"
                bin_dir.mkdir(parents=True)
                pilot_path = bin_dir / "pilot"
                pilot_path.write_text("#!/bin/bash")

                version = _get_pilot_version()
                assert version == "dev-abc1234-20260125"

    def test_returns_fallback_when_pilot_not_found(self):
        """_get_pilot_version returns installer version when pilot not found."""
        from installer import __version__
        from installer.steps.finalize import _get_pilot_version

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("installer.steps.finalize.Path.home", return_value=Path(tmpdir)):
                version = _get_pilot_version()
                assert version == __version__


class TestFinalizeStep:
    """Test FinalizeStep class."""

    def test_finalize_step_has_correct_name(self):
        """FinalizeStep has name 'finalize'."""
        from installer.steps.finalize import FinalizeStep

        step = FinalizeStep()
        assert step.name == "finalize"

    def test_check_always_returns_false(self):
        """check() always returns False (always runs)."""
        from installer.context import InstallContext
        from installer.steps.finalize import FinalizeStep
        from installer.ui import Console

        step = FinalizeStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            ctx = InstallContext(
                project_dir=project_dir,
                ui=Console(non_interactive=True),
            )

            assert step.check(ctx) is False


class TestKillStaleWorker:
    """Test FinalizeStep._kill_stale_worker."""

    @patch("installer.steps.finalize.time.sleep")
    @patch("installer.steps.finalize.subprocess.run")
    def test_kills_pids_found_by_lsof(self, mock_run, _mock_sleep):
        """Kills only listening processes, using SIGTERM before SIGKILL."""
        from installer.steps.finalize import FinalizeStep

        mock_run.side_effect = [
            MagicMock(stdout="1234\n5678\n"),  # lsof result
            MagicMock(),  # SIGTERM 1234
            MagicMock(returncode=0),  # kill -0 1234 (still alive)
            MagicMock(),  # SIGKILL 1234
            MagicMock(),  # SIGTERM 5678
            MagicMock(returncode=1),  # kill -0 5678 (already dead)
        ]

        with patch("installer.steps.finalize.get_worker_port", return_value=41777):
            FinalizeStep._kill_stale_worker()

        assert mock_run.call_args_list[0] == call(
            ["lsof", "-ti", ":41777", "-sTCP:LISTEN"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        mock_run.assert_any_call(["kill", "1234"], capture_output=True, timeout=5)
        mock_run.assert_any_call(["kill", "-9", "1234"], capture_output=True, timeout=5)
        mock_run.assert_any_call(["kill", "5678"], capture_output=True, timeout=5)
        # 5678 died after SIGTERM — no SIGKILL
        sigkill_5678_calls = [
            c for c in mock_run.call_args_list if c == call(["kill", "-9", "5678"], capture_output=True, timeout=5)
        ]
        assert len(sigkill_5678_calls) == 0

    @patch("installer.steps.finalize.subprocess.run")
    def test_does_nothing_when_no_pids(self, mock_run):
        """Does not call kill when lsof returns no PIDs."""
        from installer.steps.finalize import FinalizeStep

        mock_run.return_value = MagicMock(stdout="")

        FinalizeStep._kill_stale_worker()

        mock_run.assert_called_once()  # only lsof, no kill

    @patch("installer.steps.finalize.subprocess.run", side_effect=FileNotFoundError("lsof not found"))
    def test_swallows_exception_when_lsof_missing(self, _mock_run):
        """Does not raise when lsof is not installed."""
        from installer.steps.finalize import FinalizeStep

        FinalizeStep._kill_stale_worker()  # must not raise

    @patch("installer.steps.finalize.time.sleep")
    @patch("installer.steps.finalize.subprocess.run")
    def test_skips_invalid_pid_from_lsof(self, mock_run, _mock_sleep):
        """Ignores non-numeric PID lines from lsof output."""
        from installer.steps.finalize import FinalizeStep

        mock_run.side_effect = [
            MagicMock(stdout="1234\n; rm -rf /\nabc\n"),  # lsof returns mixed output
            MagicMock(),  # SIGTERM 1234
            MagicMock(returncode=1),  # kill -0 1234 (dead)
        ]

        FinalizeStep._kill_stale_worker()

        # Only "1234" should be killed — malicious lines skipped
        kill_calls = [c for c in mock_run.call_args_list if c[0][0][0] == "kill"]
        pid_args = [c[0][0][1] for c in kill_calls]
        assert "; rm -rf /" not in pid_args
        assert "abc" not in pid_args
        assert "1234" in pid_args


class TestFinalSuccessPanel:
    """Test final success panel display."""

    def test_run_displays_success_without_a_design_promotion(self):
        """Completion keeps product promotions out of the action list footer."""
        from installer.context import InstallContext
        from installer.steps.finalize import FinalizeStep
        from installer.ui import Console

        step = FinalizeStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            (project_dir / ".claude").mkdir()

            console = Console(non_interactive=True)
            ctx = InstallContext(
                project_dir=project_dir,
                ui=console,
            )

            with (
                patch.object(console, "next_steps") as mock_next_steps,
                patch.object(console, "print") as mock_print,
            ):
                step.run(ctx)

                mock_next_steps.assert_called()
                printed = " ".join(str(call.args[0]) for call in mock_print.call_args_list if call.args)
                assert "Open Claude Design is included" not in printed
                assert "github.com/maxritter/open-claude-design" not in printed

    def test_next_steps_has_five_neutral_actions(self):
        """Next steps teach the harness without prescribing a workflow."""
        from installer.context import InstallContext
        from installer.steps.finalize import FinalizeStep
        from installer.ui import Console

        step = FinalizeStep()
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            (project_dir / ".claude").mkdir()

            console = Console(non_interactive=True)
            ctx = InstallContext(
                project_dir=project_dir,
                ui=console,
            )

            with patch.object(console, "next_steps") as mock_next_steps:
                step.run(ctx)

                sections = mock_next_steps.call_args[0][0]
                section_titles = [title for title, _ in sections]
                assert section_titles == ["Next steps"]
                getting_started = dict(sections)["Next steps"]
                assert len(getting_started) == 5
                labels = [label for label, _ in getting_started]
                assert labels == [
                    "Start",
                    "Setup (optional)",
                    "Console",
                    "Docs",
                    "Update",
                ]
                assert ("Update", "pilot update") in getting_started
                rendered = " ".join(f"{label} {detail}" for label, detail in getting_started)
                assert ("Start", "claude or codex") in getting_started
                assert "/setup-rules" in rendered and "$setup-rules" in rendered
                assert "pilot-shell.com/docs" in rendered
                assert "Design visually" not in rendered
                assert "/spec · $spec" not in rendered


class TestClaudeProfileReport:
    """Install-time visibility of WHICH Claude profile is being written.

    This is the primary guard against the reported surprise ("it modified my
    personal ~/.claude"): the session-start hook cannot fire in a directory that
    has no Pilot install, so the installer must say where it is writing.
    """

    def test_reports_custom_dir_and_states_home_is_untouched(self, tmp_path, monkeypatch):
        from installer.steps.finalize import FinalizeStep

        custom = tmp_path / ".claude_work"
        custom.mkdir()
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(custom))
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))

        ui = MagicMock()
        ui.quiet = False
        FinalizeStep._report_claude_profile(ui)

        printed = " ".join(str(c) for c in ui.print.call_args_list)
        assert str(custom) in printed
        assert ".claude.json" in printed
        assert "not modified" in printed or "untouched" in printed

    def test_stays_quiet_on_default_profile(self, tmp_path, monkeypatch):
        """No env var means the documented default - no need to narrate it."""
        from installer.steps.finalize import FinalizeStep

        monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))

        ui = MagicMock()
        ui.quiet = False
        FinalizeStep._report_claude_profile(ui)

        ui.print.assert_not_called()

    def test_records_installed_dir_for_the_drift_guard(self, tmp_path, monkeypatch):
        from installer.steps.finalize import FinalizeStep

        custom = tmp_path / ".claude_work"
        custom.mkdir()
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(custom))
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))

        FinalizeStep._record_claude_profile()

        record = tmp_path / ".pilot" / "state" / "last-claude-config-dir"
        assert record.read_text(encoding="utf-8").strip() == str(custom)

    def test_record_never_raises_on_invalid_config_dir(self, tmp_path, monkeypatch):
        from installer.steps.finalize import FinalizeStep

        monkeypatch.setenv("CLAUDE_CONFIG_DIR", "relative/path")
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))

        FinalizeStep._record_claude_profile()
