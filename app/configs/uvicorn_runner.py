import uvicorn

from app.configs.logging_config import LOGGING_CONFIG


def main() -> None:
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=5291,
        workers=2,
        log_config=LOGGING_CONFIG,
    )


if __name__ == "__main__":
    main()
