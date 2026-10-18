import uvicorn

from app.configs.datapipe_process import DataPipeProcess
from app.configs.job_stop import JobStopWatchdog
from app.configs.logging_config import _build_logging_config
from app.configs.restart import restart
from app.configs.runtime import runtime

GRACEFUL_SHUTDOWN_SECONDS = 2


def main() -> None:
    # A flag left by a crashed reboot must not restart a manual stop.
    restart.discard()
    runtime.invalidate()
    data_pipe = DataPipeProcess()
    data_pipe.start()
    watchdog = JobStopWatchdog()
    watchdog.start()
    try:
        uvicorn.run(
            "app.main:app",
            host="0.0.0.0",
            port=5291,
            workers=2,
            timeout_graceful_shutdown=GRACEFUL_SHUTDOWN_SECONDS,
            log_config=_build_logging_config(),
        )
    finally:
        watchdog.stop()
        data_pipe.stop()
    if not restart.consume():
        return
    restart.reexec()


if __name__ == "__main__":
    main()
