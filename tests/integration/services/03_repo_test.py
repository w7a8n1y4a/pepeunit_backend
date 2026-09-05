import logging

import pytest

from app import settings
from app.configs.errors import GitRepoError, NoAccessError, RepoError, ValidationError
from app.dto.enum import (
    OperationTaskStatus,
    OperationTaskType,
    VisibilityLevel,
)
from app.schemas.pydantic.repo import RepoFilter, RepoUpdate
from app.schemas.pydantic.user import UserAuth
from tests.integration.helpers.names import unique_name
from tests.integration.helpers.services import (
    registry_read,
    registry_service,
    repo_create_payload,
    repo_service,
    user_service,
)
from tests.integration.helpers.wait import wait_task_finish


def test_create_repo(live_repos) -> None:
    assert len(live_repos.all()) == 4


def test_create_repo_duplicate_name(
    live_repos, regular_user_token, database, cc
) -> None:
    service = repo_service(database, cc, regular_user_token)
    existing = service.get(live_repos.universal_public_repo.uuid)
    with pytest.raises(RepoError):
        service.create(repo_create_payload(existing))


@pytest.mark.private_repo
def test_create_repo_without_credentials(
    private_repo, extra_user, regular_user_token, database, cc
) -> None:
    token = user_service(database, cc, None).get_token(
        UserAuth(credentials=extra_user.login, password=extra_user._test_password)
    )
    existing = repo_service(database, cc, regular_user_token).get(private_repo.uuid)
    payload = repo_create_payload(existing)
    payload.name = unique_name("nopat")
    with pytest.raises(NoAccessError):
        repo_service(database, cc, token).create(payload)


def test_update_repo_name(universal_internal_repo, regular_user_token, database, cc) -> None:
    service = repo_service(database, cc, regular_user_token)
    logging.info(universal_internal_repo.name)
    new_name = unique_name("ren")
    service.update(universal_internal_repo.uuid, RepoUpdate(name=new_name))
    update_repo = service.get(universal_internal_repo.uuid)
    assert new_name == update_repo.name
    service.update(
        universal_internal_repo.uuid,
        RepoUpdate(name=universal_internal_repo.name),
    )


def test_update_repo_name_exists(
    live_repos, regular_user_token, database, cc
) -> None:
    service = repo_service(database, cc, regular_user_token)
    with pytest.raises(RepoError):
        service.update(
            live_repos.universal_public_repo.uuid,
            RepoUpdate(name=live_repos.universal_internal_repo.name),
        )


def test_update_repo_hand_update(
    universal_public_repo, universal_registry, regular_user_token, database, cc
) -> None:
    service = repo_service(database, cc, regular_user_token)
    registry = registry_read(database, regular_user_token, universal_registry)
    from app.schemas.pydantic.repository_registry import CommitFilter

    registry_svc = registry_service(database, regular_user_token)
    commits = registry_svc.get_branch_commits(
        registry.uuid,
        CommitFilter(repo_branch=registry.branches[0]),
    )
    update_repo = service.update(
        universal_public_repo.uuid,
        RepoUpdate(
            is_auto_update_repo=False,
            default_branch=registry.branches[0],
            default_commit=commits[0].commit,
        ),
    )
    assert update_repo.is_auto_update_repo is False


def test_get_available_platforms(
    universal_compile_repo, regular_user_token, database, cc
) -> None:
    service = repo_service(database, cc, regular_user_token)
    registry_svc = registry_service(database, regular_user_token)
    target_repo = universal_compile_repo

    platforms = service.get_available_platforms(target_repo.uuid)
    assert len(platforms) > 0

    platforms = service.get_available_platforms(target_repo.uuid, target_tag="0.0.9")
    assert len(platforms) > 0

    platforms = service.get_available_platforms(target_repo.uuid, target_tag="0.0.0.0")
    assert len(platforms) == 0

    commits = service.git_repo_repository.get_branch_commits_with_tag(
        registry_svc.get(target_repo.repository_registry_uuid),
        target_repo.default_branch,
    )
    platforms = service.get_available_platforms(
        target_repo.uuid, target_commit=commits[-1]["commit"]
    )
    assert len(platforms) == 0

    tags = service.git_repo_repository.get_tags_from_all_commits(commits)
    platforms = service.get_available_platforms(
        target_repo.uuid, target_commit=tags[0]["commit"]
    )
    assert len(platforms) > 0


def test_update_default_branch_repo(
    live_repos, regular_user_token, database, cc
) -> None:
    service = repo_service(database, cc, regular_user_token)
    registry_svc = registry_service(database, regular_user_token)

    for repo in live_repos.all():
        full_repo = service.get(repo.uuid)
        logging.info(repo.uuid)
        registry = registry_svc.mapper_registry_to_registry_read(
            registry_svc.get(full_repo.repository_registry_uuid)
        )
        if registry.branches:
            service.update(
                repo.uuid, RepoUpdate(default_branch=registry.branches[0])
            )


def test_update_default_branch_bad(
    universal_compile_repo, regular_user_token, database, cc
) -> None:
    service = repo_service(database, cc, regular_user_token)
    registry_svc = registry_service(database, regular_user_token)
    full_repo = service.get(universal_compile_repo.uuid)
    registry = registry_svc.mapper_registry_to_registry_read(
        registry_svc.get(full_repo.repository_registry_uuid)
    )
    with pytest.raises(GitRepoError):
        service.update(
            full_repo.uuid,
            RepoUpdate(default_branch=registry.branches[0] + "t"),
        )


def test_delete_repo(crud_repo, regular_user_token, database, cc) -> None:
    service = repo_service(database, cc, regular_user_token)
    service.delete(crud_repo.uuid)


def test_delete_repository_registry_with_repos(
    universal_registry, regular_user_token, database
) -> None:
    service = registry_service(database, regular_user_token)
    with pytest.raises(ValidationError):
        service.delete(universal_registry.uuid)


@pytest.mark.private_repo
def test_delete_repository_registry(
    private_registries, regular_user_token, database
) -> None:
    service = registry_service(database, regular_user_token)
    target = private_registries[-1]
    try:
        service.delete(target.uuid)
    except ValidationError:
        pytest.skip("private registry still has repos")


def test_get_many_repo(
    live_repos, regular_user, regular_user_token, database, cc, test_hash
) -> None:
    service = repo_service(database, cc, regular_user_token)
    count, repos = service.list(
        RepoFilter(creator_uuid=regular_user.uuid, is_auto_update_repo=True)
    )
    assert len(repos) >= 3

    count, repos = service.list(
        RepoFilter(
            creator_uuid=regular_user.uuid,
            search_string=test_hash,
            is_auto_update_repo=True,
            offset=0,
            limit=settings.pu_max_pagination_size,
        )
    )
    assert len(repos) >= 3


def test_update_repo_visibility_blocked_by_children(
    live_units, live_repos, regular_user_token, database, cc
) -> None:
    assert live_units.all()
    service = repo_service(database, cc, regular_user_token)
    with pytest.raises(ValidationError):
        service.update(
            live_repos.universal_public_repo.uuid,
            RepoUpdate(visibility_level=VisibilityLevel.PRIVATE),
        )
    assert (
        service.get(live_repos.universal_public_repo.uuid).visibility_level
        == VisibilityLevel.PUBLIC
    )


def test_schedule_update_units_firmware(
    live_units, universal_public_repo, regular_user_token, database, cc
) -> None:
    service = repo_service(database, cc, regular_user_token)
    task = service.schedule_update_units_firmware(universal_public_repo.uuid)

    assert task.task_type == OperationTaskType.UPDATE_UNITS_FIRMWARE.value
    assert task.status == OperationTaskStatus.RUNNING.value

    finished = wait_task_finish(database, task, timeout=300)
    logging.info(finished.result)
    assert finished.status == OperationTaskStatus.SUCCESS.value
    assert finished.result.startswith("Updated ")


def test_schedule_update_units_firmware_not_creator(
    universal_public_repo, extra_user_token, database, cc
) -> None:
    service = repo_service(database, cc, extra_user_token)
    with pytest.raises(NoAccessError):
        service.schedule_update_units_firmware(universal_public_repo.uuid)


def test_schedule_bulk_update_units_firmware_without_admin(
    regular_user_token, database, cc
) -> None:
    service = repo_service(database, cc, regular_user_token)
    with pytest.raises(NoAccessError):
        service.schedule_bulk_update_units_firmware()


def test_schedule_bulk_update_units_firmware(
    live_units, live_repos, admin_user_token, database, cc
) -> None:
    service = repo_service(database, cc, admin_user_token)
    task = service.schedule_bulk_update_units_firmware()

    assert task.task_type == OperationTaskType.UPDATE_ALL_UNITS_FIRMWARE.value

    finished = wait_task_finish(database, task, timeout=600)
    logging.info(finished.result)
    assert finished.status == OperationTaskStatus.SUCCESS.value
    assert finished.result.startswith("Repos ")
