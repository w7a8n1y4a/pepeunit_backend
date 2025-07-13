from typing import Optional

import strawberry

from app.schemas.gql.type_input_mixin import TypeInputMixin


@strawberry.input()
class CredentialsInput(TypeInputMixin):
    username: str
    pat_token: str


@strawberry.input()
class CommitFilterInput(TypeInputMixin):
    repo_branch: str
    only_tag: bool = False

    offset: Optional[int] = 0
    limit: Optional[int] = 10
