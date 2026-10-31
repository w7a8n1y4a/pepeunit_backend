import sys

from app.configs.logging_config import LOGGING_CONFIG

logconfig_dict = LOGGING_CONFIG

accesslog = "-"
errorlog = "-"

loglevel = LOGGING_CONFIG["root"]["level"].lower()


def post_fork(_server, _worker) -> None:
    # The master must not open Postgres. If it did, drop that pool here
    # without closing the parent's socket.
    module = sys.modules.get("app.configs.db")
    if module is not None:
        module.engine.dispose(close=False)
