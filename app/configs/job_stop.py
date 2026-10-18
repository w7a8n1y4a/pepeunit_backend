"""Kill a local server job when Ctrl+C does not finish it.

Uvicorn's master process waits forever for a worker that ignores the
first signal, and make blocks further Ctrl+C while that wait lasts.
This process sits in the same terminal group. The first Ctrl+C leaves
a short grace period. A second one, or the end of that period, kills
the job. Ctrl+Z is left untouched, so the shell can suspend the group.
"""

import ctypes
import os
import signal
import subprocess
import sys
import time
from pathlib import Path


class JobStopWatchdog:
    """Side process that finishes a local server stuck on Ctrl+C."""

    GRACE_SECONDS = 2
    _PR_SET_PDEATHSIG = 1

    def __init__(self) -> None:
        self.proc: subprocess.Popen[bytes] | None = None
        self._hits = 0
        self._halted = False

    def start(self) -> None:
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "app.configs.job_stop", str(os.getpid())],
        )

    def stop(self) -> None:
        proc = self.proc
        self.proc = None
        if proc is None or proc.poll() is not None:
            return
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=self.GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=self.GRACE_SECONDS)

    def serve(self, parent: int) -> None:
        signal.signal(signal.SIGINT, self._interrupt)
        signal.signal(signal.SIGTERM, self._halt)
        signal.siginterrupt(signal.SIGINT, True)
        signal.siginterrupt(signal.SIGTERM, True)
        self._die_with_parent()
        while self._hits == 0 and not self._halted and self._alive(parent):
            time.sleep(0.2)
        if self._should_kill(parent):
            self._kill_job(parent)

    def _interrupt(self, _signum: int, _frame: object) -> None:
        self._hits += 1

    def _halt(self, _signum: int, _frame: object) -> None:
        self._halted = True

    def _should_kill(self, parent: int) -> bool:
        if self._hits < 2 and self._alive(parent) and not self._halted:
            self._wait_grace(parent)
        if self._halted or (self._hits < 2 and not self._alive(parent)):
            return False
        return self._hits >= 2 or self._alive(parent)

    def _wait_grace(self, parent: int) -> None:
        deadline = time.monotonic() + self.GRACE_SECONDS
        while time.monotonic() < deadline and self._hits < 2:
            if self._halted or not self._alive(parent):
                return
            time.sleep(0.1)

    def _kill_job(self, parent: int) -> None:
        sys.stderr.write("Server did not stop, killing it.\n")
        sys.stderr.flush()
        group = os.getpgrp()
        # A job-control shell keeps this group separate from itself.
        # In a session without job control the group is the session, so
        # only this server and its children are signaled.
        if group != os.getsid(0):
            os.killpg(group, signal.SIGKILL)
            return
        for pid in self._descendants(parent):
            if pid != os.getpid():
                self._signal(pid, signal.SIGKILL)
        self._signal(parent, signal.SIGKILL)

    @classmethod
    def _descendants(cls, root: int) -> list[int]:
        children: dict[int, list[int]] = {}
        for entry in Path("/proc").iterdir():
            if not entry.name.isdigit():
                continue
            pid = int(entry.name)
            children.setdefault(cls._ppid(pid), []).append(pid)
        found: list[int] = []
        stack = list(children.get(root, []))
        while stack:
            pid = stack.pop()
            found.append(pid)
            stack.extend(children.get(pid, []))
        return found

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

    @staticmethod
    def _ppid(pid: int) -> int:
        try:
            status = Path(f"/proc/{pid}/status").read_text()
        except OSError:
            return 0
        for line in status.splitlines():
            if line.startswith("PPid:"):
                return int(line.removeprefix("PPid:").strip())
        return 0

    @staticmethod
    def _alive(pid: int) -> bool:
        try:
            os.kill(pid, 0)
        except OSError:
            return False
        return True

    @staticmethod
    def _signal(pid: int, sig: int) -> None:
        try:
            os.kill(pid, sig)
        except OSError:
            return


if __name__ == "__main__":
    JobStopWatchdog().serve(int(sys.argv[1]))
