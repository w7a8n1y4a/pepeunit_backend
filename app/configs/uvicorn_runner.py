import uvicorn

from app.configs.logging_config import _build_logging_config
from app.configs.restart import restart
from app.configs.runtime import runtime


def main() -> None:
    # A flag left by a crashed reboot must not restart a manual stop.
    restart.discard()
    runtime.invalidate()
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=5291,
        workers=2,
        log_config=_build_logging_config(),
    )
    if not restart.consume():
        return
    restart.reexec()


if __name__ == "__main__":
    main()
