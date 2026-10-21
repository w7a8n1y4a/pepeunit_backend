import asyncio

from app import runtime
from app.configs.rest import (
    get_grafana_service,
    get_icon_service,
    get_instance_service,
    get_instance_settings_service,
    get_metrics_service,
    get_notification_service,
    get_operation_task_service,
    get_permission_service,
    get_repo_service,
    get_unit_group_service,
    get_unit_io_service,
    get_unit_service,
    get_user_service,
)
from app.schemas.pydantic.repo import CommitFilter
from app.schemas.pydantic.user import AuthChallengeCreate, AuthTokenCreate


def user_service(database, cc, token=None):
    return get_user_service(database, cc, token)


def icon_service(database, token=None):
    return get_icon_service(database, token)


def repo_service(database, token=None):
    return get_repo_service(database, token)


def unit_service(database, cc, token=None):
    return get_unit_service(database, cc, token)


def unit_group_service(database, token=None):
    return get_unit_group_service(database, token)


def unit_io_service(database, cc, token=None):
    return get_unit_io_service(database, cc, token)


def grafana_service(database, cc, token=None):
    return get_grafana_service(database, cc, token)


def permission_service(database, token=None):
    return get_permission_service(database, token)


def instance_service(database, token=None):
    return get_instance_service(database, token)


def instance_settings_service(database, token=None):
    return get_instance_settings_service(database, token)


def operation_task_service(database, token=None):
    return get_operation_task_service(database, token)


def metrics_service(database, token=None):
    return get_metrics_service(database, token)


def notification_service(database, cc, token=None):
    return get_notification_service(database, cc, token)


def repo_read(database, token, repo_or_uuid):
    service = repo_service(database, token)
    repo_uuid = getattr(repo_or_uuid, "uuid", repo_or_uuid)
    return service.mapper_repo_to_repo_read(service.get(repo_uuid))


def _collect_commits(service, repo_uuid, branch, only_tag, count):
    """Commit pages, gathered the way an api client has to gather them.

    count is None for the whole branch history.
    """
    commits = []
    while count is None or len(commits) < count:
        page = service.get_branch_commits(
            repo_uuid,
            CommitFilter(
                repo_branch=branch,
                only_tag=only_tag,
                offset=len(commits),
                limit=runtime.get().pu_instance_max_pagination_size,
            ),
        )
        commits.extend(page)

        if len(page) < runtime.get().pu_instance_max_pagination_size:
            break

    return commits


def branch_commits(
    database, token, repo_uuid, *, only_tag: bool = False, count: int = 1
):
    """First count commits of the default branch, count is what the caller indexes"""
    service = repo_service(database, token)
    read = service.mapper_repo_to_repo_read(service.get(repo_uuid))

    return read, _collect_commits(
        service, repo_uuid, read.branches[0], only_tag, count
    )


def all_branch_commits(database, token, repo_uuid, branch, *, only_tag: bool = False):
    return _collect_commits(
        repo_service(database, token), repo_uuid, branch, only_tag, None
    )


def token_for(database, cc, key) -> str:
    service = user_service(database, cc, None)

    async def _issue() -> str:
        challenge = await service.create_challenge(
            AuthChallengeCreate(hash_public_key=key.hash_public_key)
        )
        return await service.get_token(
            AuthTokenCreate(
                challenge=challenge, signature=key.sign(challenge)
            )
        )

    return asyncio.run(_issue())
