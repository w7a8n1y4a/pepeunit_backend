"""Run the data pipe binary beside the backend.

The binary inherits this process environment. Importing the app loads
.env without overriding variables that are already set. The binary
reads instance settings from Postgres and exits when they change.
This supervisor starts it again. It stays in the backend process group,
so Ctrl+C and Ctrl+Z reach it together with the server. If the parent
disappears, this process exits and stops the binary.
"""

import ctypes
import logging
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from app.configs.runtime import runtime


class DataPipeSupervisor:
    """Keep one data pipe binary running for this working directory."""

    PID_PATH = Path("tmp/data_pipe.supervisor.pid")
    BINARY_PATH = Path("bin/data_pipe")
    FLAG_WAIT_SECONDS = 5
    POLL_SECONDS = 1
    STOP_TIMEOUT_SECONDS = 10
    KILL_WAIT_SECONDS = 5
    CRASH_SECONDS = 2
    _PR_SET_PDEATHSIG = 1
    _MODULE_NAME = "app.configs.datapipe_process"

    def __init__(self) -> None:
        self._stop = False
        self._proc: subprocess.Popen[bytes] | None = None
        self._enabled_flag = False
        self._settings_error = False

    def serve(self) -> None:
        signal.signal(signal.SIGTERM, self._request_stop)
        signal.signal(signal.SIGINT, self._request_stop)
        self._die_with_parent()
        self._stop_other_pipes()
        self._write_pid()
        try:
            self._loop()
        finally:
            self._stop_child()
            self.PID_PATH.unlink(missing_ok=True)

    def _request_stop(self, _signum: int, _frame: object) -> None:
        self._stop = True

    def _loop(self) -> None:
        while not self._stop:
            if not self._enabled():
                self._pause_while_disabled()
                continue
            if not self._spawn():
                if self._wait(self.FLAG_WAIT_SECONDS):
                    return
                continue
            if not self._finish_child(time.monotonic()):
                return

    def _pause_while_disabled(self) -> None:
        self._stop_child()
        self._proc = None
        self._wait(self.FLAG_WAIT_SECONDS)

    def _finish_child(self, started: float) -> bool:
        """False means the supervisor itself is stopping."""
        self._wait_child()
        code = self._return_code()
        lifetime = time.monotonic() - started
        self._proc = None
        if self._stop:
            return False
        if not self._enabled():
            return not self._wait(self.FLAG_WAIT_SECONDS)
        # A fast exit is a crash. A long clean exit is a settings change.
        if code != 0 or lifetime < self.CRASH_SECONDS:
            logging.info("Data pipe exited with code %s", code)
            return not self._wait(self.FLAG_WAIT_SECONDS)
        logging.info("Data pipe restarted after instance settings change")
        return True

    def _enabled(self) -> bool:
        try:
            self._enabled_flag = bool(runtime.get().pu_ff_datapipe_enable)
        except Exception:
            if not self._settings_error:
                logging.exception("Data pipe cannot read instance settings")
            self._settings_error = True
            return self._enabled_flag
        self._settings_error = False
        return self._enabled_flag

    def _spawn(self) -> bool:
        binary = self._binary_path()
        if binary is None:
            logging.error("Data pipe binary is missing: %s", self.BINARY_PATH)
            return False
        logging.info("Starting data pipe %s", binary)
        self._proc = subprocess.Popen([str(binary)])
        return True

    def _wait_child(self) -> None:
        if self._proc is None:
            return
        while not self._stop:
            try:
                self._proc.wait(timeout=self.POLL_SECONDS)
                return
            except subprocess.TimeoutExpired:
                if not self._enabled():
                    self._stop_child()
                    return

    def _stop_child(self) -> None:
        proc = self._proc
        if proc is None or proc.poll() is not None:
            return
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=self.STOP_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=self.KILL_WAIT_SECONDS)

    def _return_code(self) -> int:
        if self._proc is None or self._proc.returncode is None:
            return 0
        return self._proc.returncode

    def _wait(self, seconds: float) -> bool:
        deadline = time.monotonic() + seconds
        while not self._stop and time.monotonic() < deadline:
            time.sleep(min(self.POLL_SECONDS, deadline - time.monotonic()))
        return self._stop

    @classmethod
    def _binary_path(cls) -> Path | None:
        override = os.environ.get("PU_DATA_PIPE_BIN", "").strip()
        candidates = [Path(override)] if override else []
        candidates.append(cls.BINARY_PATH)
        for path in candidates:
            if path.is_file() and os.access(path, os.X_OK):
                return path
        return None

    @classmethod
    def _die_with_parent(cls) -> None:
        """Exit when the parent dies, including a parent killed with SIGKILL."""
        parent = os.getppid()
        libc = ctypes.CDLL(None, use_errno=True)
        prctl = libc.prctl
        prctl.argtypes = [ctypes.c_int, *([ctypes.c_ulong] * 4)]
        prctl.restype = ctypes.c_int
        if prctl(cls._PR_SET_PDEATHSIG, signal.SIGTERM, 0, 0, 0) != 0:
            return
        if os.getppid() != parent:
            os.kill(os.getpid(), signal.SIGTERM)

    @classmethod
    def _stop_other_pipes(cls) -> None:
        root = os.getcwd()
        victims = [
            pid
            for pid in cls._process_ids()
            if pid != os.getpid() and cls._is_data_pipe(pid, root)
        ]
        if not victims:
            return
        logging.info("Stopping leftover data pipe processes")
        cls._signal_pids(victims, signal.SIGTERM)
        deadline = time.monotonic() + cls.STOP_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            victims = [pid for pid in victims if cls._alive(pid)]
            if not victims:
                return
            time.sleep(0.1)
        cls._signal_pids(victims, signal.SIGKILL)

    @classmethod
    def _signal_pids(cls, pids: list[int], sig: int) -> None:
        for pid in pids:
            cls._signal_group(pid, sig)

    @staticmethod
    def _process_ids() -> list[int]:
        return [
            int(entry.name)
            for entry in Path("/proc").iterdir()
            if entry.name.isdigit()
        ]

    @classmethod
    def _is_data_pipe(cls, pid: int, root: str) -> bool:
        args = cls._cmdline(pid)
        if not args:
            return False
        binary = Path(args[0]).name == "data_pipe"
        module = cls._MODULE_NAME in args
        if not binary and not module:
            return False
        return cls._same_cwd(pid, root)

    @staticmethod
    def _cmdline(pid: int) -> list[str]:
        try:
            raw = Path(f"/proc/{pid}/cmdline").read_bytes()
        except OSError:
            return []
        return [
            part.decode(errors="replace") for part in raw.split(b"\0") if part
        ]

    @staticmethod
    def _same_cwd(pid: int, root: str) -> bool:
        try:
            return os.path.samefile(os.readlink(f"/proc/{pid}/cwd"), root)
        except OSError:
            return False

    @staticmethod
    def _alive(pid: int) -> bool:
        try:
            os.kill(pid, 0)
        except OSError:
            return False
        return True

    @classmethod
    def _write_pid(cls) -> None:
        cls.PID_PATH.parent.mkdir(parents=True, exist_ok=True)
        cls.PID_PATH.write_text(str(os.getpid()))

    @staticmethod
    def _signal_group(pid: int, sig: int) -> None:
        try:
            os.killpg(pid, sig)
            return
        except OSError:
            pass
        try:
            os.kill(pid, sig)
        except OSError:
            return


class DataPipeProcess:
    """Supervisor process launched next to uvicorn or gunicorn."""

    def __init__(self) -> None:
        self.proc: subprocess.Popen[bytes] | None = None

    def start(self) -> None:
        if self.proc is not None and self.proc.poll() is None:
            return
        DataPipeSupervisor._stop_other_pipes()
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "app.configs.datapipe_process"],
        )

    def stop(self) -> None:
        proc = self.proc
        self.proc = None
        if proc is None:
            return
        DataPipeSupervisor._signal_group(proc.pid, signal.SIGTERM)
        try:
            proc.wait(timeout=DataPipeSupervisor.STOP_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            DataPipeSupervisor._signal_group(proc.pid, signal.SIGKILL)
            try:
                proc.wait(timeout=DataPipeSupervisor.KILL_WAIT_SECONDS)
            except subprocess.TimeoutExpired:
                return


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    DataPipeSupervisor().serve()


if __name__ == "__main__":
    main()
