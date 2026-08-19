from app.configs.rest import (
    get_grafana_service,
    get_permission_service,
    get_repo_service,
    get_repository_registry_service,
    get_unit_node_service,
    get_unit_service,
    get_user_service,
)
from app.schemas.pydantic.repo import RepoCreate
from app.schemas.pydantic.repository_registry import CommitFilter
from app.schemas.pydantic.user import UserAuth


def user_service(database, cc, token=None):
    return get_user_service(database, cc, token)


def registry_service(database, token=None):
    return get_repository_registry_service(database, token)


def repo_service(database, cc, token=None):
    return get_repo_service(database, cc, token)


def unit_service(database, cc, token=None):
    return get_unit_service(database, cc, token)


def unit_node_service(database, cc, token=None):
    return get_unit_node_service(database, cc, token)


def grafana_service(database, cc, token=None):
    return get_grafana_service(database, cc, token)


def permission_service(database, token=None):
    return get_permission_service(database, token)


def registry_read(database, token, registry_or_uuid):
    service = registry_service(database, token)
    registry_uuid = getattr(registry_or_uuid, "uuid", registry_or_uuid)
    return service.mapper_registry_to_registry_read(service.get(registry_uuid))


def repo_create_payload(repo) -> RepoCreate:
    return RepoCreate(
        repository_registry_uuid=repo.repository_registry_uuid,
        default_branch=repo.default_branch,
        visibility_level=repo.visibility_level,
        name=repo.name,
        is_compilable_repo=repo.is_compilable_repo,
    )


def branch_commits(database, token, registry_uuid, *, only_tag: bool = False):
    service = registry_service(database, token)
    read = service.mapper_registry_to_registry_read(service.get(registry_uuid))
    commits = service.get_branch_commits(
        registry_uuid,
        CommitFilter(repo_branch=read.branches[0], only_tag=only_tag),
    )
    return read, commits


def token_for(database, cc, login: str, password: str) -> str:
    return user_service(database, cc, None).get_token(
        UserAuth(credentials=login, password=password)
    )
