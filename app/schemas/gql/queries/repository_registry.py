import uuid as uuid_pkg

import strawberry
from strawberry.types import Info

from app.configs.gql import get_repository_registry_service_gql
from app.schemas.gql.inputs.repository_registry import CommitFilterInput
from app.schemas.gql.types.repo import (
    CommitType,
)


@strawberry.field()
def get_branch_commits(uuid: uuid_pkg.UUID, filters: CommitFilterInput, info: Info) -> list[CommitType]:
    repository_registry_service = get_repository_registry_service_gql(info)
    return [CommitType(**commit.dict()) for commit in repository_registry_service.get_branch_commits(uuid, filters)]
