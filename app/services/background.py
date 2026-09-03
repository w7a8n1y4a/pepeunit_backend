from contextlib import ExitStack


class BackgroundService:
    def __init__(self, jwt_token: str | None = None) -> None:
        self.jwt_token = jwt_token
        self._stack = ExitStack()

    def __enter__(self):
        from app.configs.clickhouse import get_hand_clickhouse_client
        from app.configs.db import get_hand_session
        from app.configs.rest import ServiceFactory

        db = self._stack.enter_context(get_hand_session())
        client = self._stack.enter_context(get_hand_clickhouse_client())
        return ServiceFactory(db, client, self.jwt_token)

    def __exit__(self, exc_type, exc, tb):
        return self._stack.__exit__(exc_type, exc, tb)
