"""Replace the server process so every worker reloads instance settings.

SIGTERM stops the master. A side process kills workers that do not exit.
This process then closes the listen socket and execs itself.
"""

import logging
import os
import signal
import subprocess
import sys
import time
from pathlib import Path


class ServerRestart:
    GRACE_SECONDS = 3
    WAIT_SECONDS = 30

    def __init__(self) -> None:
        self.flag = Path("tmp/instance_restart")
        self.lock_dir = Path("tmp")

    def discard(self) -> None:
        self.flag.unlink(missing_ok=True)

    def consume(self) -> bool:
        if not self.flag.is_file():
            return False
        self.flag.unlink(missing_ok=True)
        self._clear_locks()
        return True

    def reexec(self) -> None:
        # Workers inherit the listen socket. Close it before the new
        # process binds the same port.
        os.closerange(3, os.sysconf("SC_OPEN_MAX"))
        os.execv(sys.executable, [sys.executable, *sys.argv])  # noqa: S606

    def request(self) -> None:
        master_pid = os.getppid()
        if not self._is_server_master(master_pid):
            logging.error(
                "Refusing to reboot: parent %s is not the server master",
                master_pid,
            )
            return
        self.flag.parent.mkdir(parents=True, exist_ok=True)
        self.flag.write_text("1")
        logging.info("Rebooting server master %s", master_pid)
        self._spawn_rescue(master_pid)
        os.kill(master_pid, signal.SIGTERM)

    def rescue(self, master_pid: int) -> None:
        cwd = self._cwd(master_pid)
        if cwd:
            os.chdir(cwd)
        deadline = time.monotonic() + self.WAIT_SECONDS
        kill_at = time.monotonic() + self.GRACE_SECONDS
        killed = False
        while time.monotonic() < deadline:
            if not self.flag.is_file() or not self._alive(master_pid):
                return
            if not killed and time.monotonic() >= kill_at:
                for pid in self._child_pids(master_pid):
                    self._kill(pid, signal.SIGKILL)
                killed = True
            time.sleep(0.2)

    def _clear_locks(self) -> None:
        if not self.lock_dir.is_dir():
            return
        for path in self.lock_dir.glob("*.lock"):
            path.unlink(missing_ok=True)

    def _is_server_master(self, pid: int) -> bool:
        command = " ".join(self._cmdline(pid))
        return "uvicorn" in command or "gunicorn" in command

    def _spawn_rescue(self, master_pid: int) -> None:
        subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()), str(master_pid)],
            start_new_session=True,
            stdin=subprocess.DEVNULL,
            close_fds=True,
        )

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
    def _cwd(pid: int) -> str:
        try:
            return os.readlink(f"/proc/{pid}/cwd")
        except OSError:
            return ""

    @staticmethod
    def _child_pids(parent_pid: int) -> list[int]:
        pids: list[int] = []
        for entry in Path("/proc").iterdir():
            if not entry.name.isdigit():
                continue
            ppid = ServerRestart._status_field(int(entry.name), "PPid:")
            if ppid == str(parent_pid):
                pids.append(int(entry.name))
        return pids

    @staticmethod
    def _alive(pid: int) -> bool:
        state = ServerRestart._status_field(pid, "State:")
        return bool(state) and state.split()[0] != "Z"

    @staticmethod
    def _status_field(pid: int, prefix: str) -> str:
        try:
            status = Path(f"/proc/{pid}/status").read_text()
        except OSError:
            return ""
        for line in status.splitlines():
            if line.startswith(prefix):
                return line.removeprefix(prefix).strip()
        return ""

    @staticmethod
    def _kill(pid: int, sig: int) -> None:
        try:
            os.kill(pid, sig)
        except OSError:
            return


restart = ServerRestart()


if __name__ == "__main__":
    restart.rescue(int(sys.argv[1]))
