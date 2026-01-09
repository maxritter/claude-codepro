#!/usr/bin/env python3
"""Claude Code wrapper with pipe-based control for session management.

Supervisor pattern: wrapper stays running and can restart Claude multiple times.
"""

from __future__ import annotations

import datetime
import logging
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types import FrameType


def clear_terminal() -> None:
    """Clear the terminal screen."""
    os.system("clear" if os.name != "nt" else "cls")


def print_banner() -> None:
    """Print the Claude CodePro wrapper banner."""
    print()
    print("  ╭─────────────────────────────────────────────╮")
    print("  │           Claude CodePro                    │")
    print("  │     Endless Mode enabled automatically      │")
    print("  ╰─────────────────────────────────────────────╯")
    print()
    print("  🔧 First time?  Run /setup to initialize project context")
    print()
    print('  📋 Spec-Driven  /spec "your task" → Plan, approve, implement, verify')
    print("  ⚡ Quick Mode   Just chat → For bug fixes and small changes")
    print()
    print("  ♾️  Endless Mode works in both - unlimited context automatically")
    print()


def setup_logging() -> logging.Logger:
    """Set up file logging for wrapper debugging."""
    log_dir = Path("/tmp/claude-wrapper-logs")
    log_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    log_file = log_dir / f"wrapper-{os.getpid()}-{timestamp}.log"

    logger = logging.getLogger("claude-wrapper")
    logger.setLevel(logging.DEBUG)

    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(file_handler)

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(logging.WARNING)
    stderr_handler.setFormatter(logging.Formatter("[Wrapper] %(message)s"))
    logger.addHandler(stderr_handler)

    logger.info(f"Wrapper started, PID: {os.getpid()}")
    logger.info(f"Log file: {log_file}")

    return logger


_logger: logging.Logger | None = None


def get_logger() -> logging.Logger:
    """Get or create the wrapper logger."""
    global _logger
    if _logger is None:
        _logger = setup_logging()
    return _logger


def interpret_exit_code(exit_code: int) -> str:
    """Interpret exit code and return human-readable explanation."""
    if exit_code == 0:
        return "normal exit"
    if exit_code < 0:
        sig = -exit_code
        signal_names = {
            1: "SIGHUP",
            2: "SIGINT",
            6: "SIGABRT",
            9: "SIGKILL (likely OOM)",
            11: "SIGSEGV",
            15: "SIGTERM",
        }
        return f"killed by signal {sig} ({signal_names.get(sig, 'unknown')})"
    if exit_code == 247:
        return "abnormal termination (possibly OOM or resource exhaustion)"
    if exit_code > 128:
        sig = exit_code - 128
        signal_names = {
            1: "SIGHUP",
            2: "SIGINT",
            6: "SIGABRT",
            9: "SIGKILL (likely OOM)",
            11: "SIGSEGV",
            15: "SIGTERM",
        }
        sig_name = signal_names.get(sig, f"signal {sig}")
        return f"killed by {sig_name}"
    return f"exit code {exit_code}"


class ClaudeWrapper:
    """Wrapper that launches Claude with pipe-based control."""

    SESSION_RESTART_DELAY_SECONDS = 5.0
    GRACEFUL_SHUTDOWN_TIMEOUT_SECONDS = 5.0
    PRE_SESSION_INIT_SECONDS = 3.0

    RECOVERABLE_EXIT_CODES = {137, 247, 139}

    def __init__(
        self,
        claude_args: list[str],
        pipe_dir: Path | None = None,
    ) -> None:
        """Initialize wrapper with claude arguments."""
        self.logger = get_logger()
        self.claude_args = claude_args
        self.pipe_dir = pipe_dir or self._default_pipe_dir()
        self.pipe_path: Path = self.pipe_dir / f"claude-{os.getpid()}.pipe"
        self.claude_process: subprocess.Popen[bytes] | None = None
        self._running = False
        self._shutdown_requested = False
        self._restart_pending = False
        self._restart_prompt: str | None = None
        self._reader_thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._consecutive_crashes = 0
        self._max_consecutive_crashes = 3

        self.pipe_dir.mkdir(parents=True, exist_ok=True)
        self.logger.info(f"Wrapper initialized, pipe: {self.pipe_path}")

    @staticmethod
    def _default_pipe_dir() -> Path:
        """Get default pipe directory."""
        return Path("/tmp") / "claude-pipes"

    def _create_pipe(self) -> None:
        """Create named pipe for receiving commands."""
        if self.pipe_path.exists():
            self.pipe_path.unlink()
        os.mkfifo(self.pipe_path)

    def _cleanup(self) -> None:
        """Clean up pipe and resources."""
        if self.pipe_path.exists():
            try:
                self.pipe_path.unlink()
            except OSError:
                pass

        try:
            if self.pipe_dir.exists() and not any(self.pipe_dir.iterdir()):
                self.pipe_dir.rmdir()
        except OSError:
            pass

    def _get_claude_env(self) -> dict[str, str]:
        """Get environment variables for Claude process."""
        env = os.environ.copy()
        env["WRAPPER_PIPE"] = str(self.pipe_path)
        return env

    def _handle_command(self, command: str) -> None:
        """Handle command received via pipe."""
        parts = command.strip().split(maxsplit=1)
        if not parts:
            return

        cmd = parts[0]
        arg = parts[1] if len(parts) > 1 else None
        self.logger.info(f"Received command: {cmd}, arg: {arg}")

        if cmd == "exit":
            self.logger.info("Exit command - shutting down")
            with self._lock:
                self._shutdown_requested = True
            self._kill_claude()

        elif cmd == "clear":
            self.logger.info("Clear command - restarting fresh")
            with self._lock:
                self._restart_pending = True
                self._restart_prompt = None
            self._kill_claude()

        elif cmd == "clear-continue":
            if arg:
                self.logger.info(f"Clear-continue with plan: {arg}")
                with self._lock:
                    self._restart_pending = True
                    self._restart_prompt = f"/spec --continue {arg}"
            else:
                self.logger.warning("Clear-continue missing plan path")
                with self._lock:
                    self._restart_pending = True
                    self._restart_prompt = None
            self._kill_claude()

        elif cmd == "clear-continue-general":
            self.logger.info("Clear-continue-general - restarting with continuation")
            with self._lock:
                self._restart_pending = True
                self._restart_prompt = (
                    "CONTINUING FROM PREVIOUS SESSION. "
                    "First, check for /tmp/claude-continuation.md - if it exists, read it for context. "
                    "Also check Claude Mem injected context for 'SESSION END - Continuation Summary'. "
                    "Execute the 'Next Steps' immediately. "
                    "Start by saying: 'Continuing from previous session...' then proceed with the work."
                )
            self._kill_claude()

        else:
            self.logger.warning(f"Unknown command received: {cmd}")

    def _kill_claude(self) -> None:
        """Kill the Claude process gracefully, allowing SessionEnd hooks to complete."""
        if self.claude_process and self.claude_process.poll() is None:
            pid = self.claude_process.pid
            self.logger.info(f"Terminating Claude process {pid}")
            self.claude_process.terminate()
            try:
                self.claude_process.wait(timeout=self.GRACEFUL_SHUTDOWN_TIMEOUT_SECONDS)
                self.logger.info(f"Claude {pid} exited gracefully")
            except subprocess.TimeoutExpired:
                self.logger.warning(f"Claude {pid} did not exit gracefully, force killing")
                self.claude_process.kill()
                self.claude_process.wait()
                self.logger.info(f"Claude {pid} force killed")

    def _start_claude(self, prompt: str | None = None) -> None:
        """Start a new Claude process."""
        cmd = ["claude"] + self.claude_args
        if prompt:
            cmd.append(prompt)

        self.logger.info(f"Starting Claude with args: {self.claude_args}")
        if prompt:
            self.logger.info(f"Prompt: {prompt[:100]}...")

        try:
            self.claude_process = subprocess.Popen(
                cmd,
                env=self._get_claude_env(),
            )
            self.logger.info(f"Claude started with PID: {self.claude_process.pid}")
        except Exception as e:
            self.logger.error(f"Failed to start Claude: {e}")
            raise

    def _read_pipe_command(self) -> None:
        """Read a single command from the pipe."""
        try:
            with open(self.pipe_path) as f:
                line = f.readline()
                if line:
                    self._handle_command(line)
        except OSError as e:
            self.logger.debug(f"Pipe read OSError (expected during shutdown): {e}")

    def _pipe_reader_loop(self) -> None:
        """Background thread that reads commands from pipe."""
        self.logger.debug("Pipe reader thread started")
        while self._running:
            try:
                self._read_pipe_command()
            except Exception as e:
                if self._running:
                    print(f"[Wrapper] Pipe read error: {e}", file=sys.stderr)
                    self.logger.error(f"Pipe read error: {e}")
        self.logger.debug("Pipe reader thread exiting")

    def _signal_handler(self, signum: int, frame: FrameType | None) -> None:
        """Handle termination signals."""
        _ = frame
        signal_name = signal.Signals(signum).name if signum in signal.Signals._value2member_map_ else str(signum)
        self.logger.info(f"Received signal {signal_name} ({signum}), initiating shutdown")
        with self._lock:
            self._shutdown_requested = True
            self._running = False
        self._kill_claude()

    def _handle_crash_recovery(self, exit_code: int) -> bool:
        """Handle crash recovery logic. Returns True if should restart."""
        explanation = interpret_exit_code(exit_code)
        self.logger.warning(f"Claude exited unexpectedly: {explanation}")

        is_recoverable = exit_code in self.RECOVERABLE_EXIT_CODES or exit_code > 128 or exit_code < 0

        if not is_recoverable:
            self.logger.info(f"Exit code {exit_code} not recoverable, stopping")
            return False

        self._consecutive_crashes += 1
        self.logger.warning(f"Crash {self._consecutive_crashes}/{self._max_consecutive_crashes}")

        if self._consecutive_crashes >= self._max_consecutive_crashes:
            print(f"\n  Session crashed too many times. Check logs: /tmp/claude-wrapper-logs/")
            self.logger.error(f"Max consecutive crashes reached ({self._max_consecutive_crashes}), giving up")
            return False

        crash_delay = self.SESSION_RESTART_DELAY_SECONDS * self._consecutive_crashes
        print(f"\n  Session crashed ({explanation}). Restarting in {crash_delay:.0f}s...")
        self.logger.info(f"Waiting {crash_delay}s before crash recovery restart")
        time.sleep(crash_delay)

        return True

    def start(self) -> int:
        """Start the wrapper and Claude process with supervisor loop."""
        self._create_pipe()
        self.logger.info("Starting wrapper supervisor loop")

        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGHUP, self._signal_handler)
        signal.signal(signal.SIGPIPE, signal.SIG_IGN)

        clear_terminal()
        print_banner()
        print("  Loading Claude Code...\n")
        time.sleep(1.5)
        clear_terminal()

        self._running = True
        self._reader_thread = threading.Thread(target=self._pipe_reader_loop, daemon=True)
        self._reader_thread.start()

        exit_code = 0
        first_run = True

        while True:
            with self._lock:
                if self._shutdown_requested:
                    self.logger.info("Shutdown requested, breaking main loop")
                    break

            with self._lock:
                prompt = self._restart_prompt
                self._restart_prompt = None
                self._restart_pending = False

            if first_run:
                self._start_claude(prompt=None)
                first_run = False
            else:
                self._start_claude(prompt=prompt)

            try:
                exit_code = self.claude_process.wait() if self.claude_process else 0
                self.logger.info(f"Claude process exited with code: {exit_code}")
            except KeyboardInterrupt:
                self.logger.info("KeyboardInterrupt received")
                with self._lock:
                    self._shutdown_requested = True
                self._kill_claude()
                exit_code = 130
                break

            with self._lock:
                if self._shutdown_requested:
                    self.logger.info("Shutdown requested after wait, breaking")
                    break

                if self._restart_pending:
                    self._consecutive_crashes = 0
                    self.logger.info("Intentional restart, resetting crash counter")
                    print("\n  Restarting session...")
                    time.sleep(self.SESSION_RESTART_DELAY_SECONDS)
                    time.sleep(self.PRE_SESSION_INIT_SECONDS)
                    clear_terminal()
                    continue

                if exit_code != 0:
                    if self._handle_crash_recovery(exit_code):
                        clear_terminal()
                        continue
                    break

                self._consecutive_crashes = 0
                self.logger.info("Claude exited normally")
                break

        self._running = False
        self._cleanup()
        self.logger.info(f"Wrapper exiting with code: {exit_code}")

        return exit_code

    def run(self) -> int:
        """Run the wrapper (alias for start)."""
        return self.start()


def main() -> int:
    """Main entry point for wrapper script."""
    claude_args = sys.argv[1:]

    wrapper = ClaudeWrapper(claude_args=claude_args)
    return wrapper.start()


if __name__ == "__main__":
    sys.exit(main())
