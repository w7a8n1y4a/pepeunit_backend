from typing import Annotated

from fastapi import Header


def get_jwt_token(token: Annotated[str | None, Header()] = None):
    return token
