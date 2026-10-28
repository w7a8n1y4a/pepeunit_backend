import logging
import os
from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from app import runtime
from app.configs.errors import (
    GitRepoError,
    NoAccessError,
    RepoError,
)
from app.domain.repo_model import Repo
from app.repositories.git_platform_repository import GithubPlatformClient
from app.dto.enum import (
    CredentialStatus,
    OperationTaskStatus,
    OperationTaskType,
    RepoStatus,
)
from app.schemas.pydantic.repo import (
    CommitFilter,
    Credentials,
    RepoCreate,
    RepoFilter,
)
from app.services.icon_image import IconImage
from tests.integration.helpers.instance_settings import owner_setting
from tests.integration.helpers.names import UNIVERSAL_FIRST_COMMIT
from tests.integration.helpers.owner import as_owner
from tests.integration.helpers.services import (
    all_branch_commits,
    icon_service,
    repo_service,
)
from tests.integration.helpers.wait import wait_task_finish


def test_create_repo(
    public_repos, regular_user_token, database
) -> None:
    service = repo_service(database, regular_user_token)
    for repo in public_repos:
        logging.info(repo.repository_url)
        assert os.path.exists(
            service.git_repo_repository.get_path_physic_repository(repo)
        )
        expected = IconImage.generate(repo.repository_url)
        icon = icon_service(database).get(repo.icon_uuid)
        assert bytes(icon.image_bin) == expected
        assert icon.image_hash == IconImage.md5(expected)


def test_create_repo_duplicate(
    github_public_repo, regular_user_token, database
) -> None:
    service = repo_service(database, regular_user_token)
    with pytest.raises(RepoError):
        service.create(
            RepoCreate(
                repository_url=github_public_repo.repository_url,
                is_public_repository=True,
                platform=github_public_repo.platform,
            )
        )


def test_create_repo_bad_link(
    github_public_repo, regular_user_token, database
) -> None:
    service = repo_service(database, regular_user_token)
    with pytest.raises(RepoError):
        service.create(
            RepoCreate(
                repository_url=github_public_repo.repository_url + "t",
                is_public_repository=True,
                platform=github_public_repo.platform,
            )
        )


def test_get_commits_repository(
    universal_repo, regular_user_token, database
) -> None:
    service = repo_service(database, regular_user_token)
    logging.info(universal_repo.uuid)
    target_branch = service.git_repo_repository.get_branches(
        universal_repo
    )[0]

    branch_commits = all_branch_commits(
        database, regular_user_token, universal_repo.uuid, target_branch
    )
    assert branch_commits[-1].commit == UNIVERSAL_FIRST_COMMIT


def test_get_commits_bad_branch(
    universal_repo, regular_user_token, database
) -> None:
    service = repo_service(database, regular_user_token)
    target_branch = service.git_repo_repository.get_branches(
        universal_repo
    )[0]

    with pytest.raises(GitRepoError):
        service.get_branch_commits(
            universal_repo.uuid,
            CommitFilter(repo_branch=target_branch + "test"),
        )


@pytest.mark.private_repo
def test_get_set_credentials_private(
    private_repo, regular_user_token, admin_user_token, database
) -> None:
    service = repo_service(database, regular_user_token)
    logging.info(private_repo.uuid)

    credentials = service.get_credentials(private_repo.uuid)
    service.set_credentials(
        private_repo.uuid,
        Credentials(
            username=credentials.credentials.username,
            pat_token=credentials.credentials.pat_token,
        ),
    )

    two_service = repo_service(database, admin_user_token)
    two_service.set_credentials(
        private_repo.uuid,
        Credentials(
            username=credentials.credentials.username,
            pat_token=credentials.credentials.pat_token,
        ),
    )
    assert (
        two_service.get_credentials(private_repo.uuid).status
        == CredentialStatus.VALID.value
    )
    assert (
        service.get_credentials(private_repo.uuid).status
        == CredentialStatus.VALID.value
    )


def test_get_set_credentials_public_fails(
    github_public_repo, regular_user_token, database
) -> None:
    service = repo_service(database, regular_user_token)
    with pytest.raises(RepoError):
        service.get_credentials(github_public_repo.uuid)

    with pytest.raises(RepoError):
        service.set_credentials(
            github_public_repo.uuid,
            Credentials(username="test", pat_token="test"),
        )


@pytest.mark.private_repo
def test_invalid_credentials_private(
    private_repo, regular_user_token, database
) -> None:
    service = repo_service(database, regular_user_token)
    original = service.get_credentials(private_repo.uuid)
    service.set_credentials(
        private_repo.uuid,
        Credentials(username="invalid-user", pat_token="invalid-token"),
    )
    assert (
        service.get_credentials(private_repo.uuid).status
        == CredentialStatus.ERROR.value
    )
    service.set_credentials(
        private_repo.uuid,
        Credentials(
            username=original.credentials.username,
            pat_token=original.credentials.pat_token,
        ),
    )
    assert (
        service.get_credentials(private_repo.uuid).status
        == CredentialStatus.VALID.value
    )


def test_get_many_repository(
    public_repos, regular_user, regular_user_token, database
) -> None:
    service = repo_service(database, regular_user_token)
    count, repositories = service.list(
        RepoFilter(creator_uuid=regular_user.uuid)
    )
    assert count >= 3

    count, repositories = service.list(
        RepoFilter(
            creator_uuid=regular_user.uuid,
            search_string=".git",
            is_public_repository=True,
            offset=0,
            limit=runtime.get().pu_instance_max_pagination_size,
        )
    )
    assert count >= 3

    public_only = repo_service(database, None)
    count, repositories = public_only.list(
        RepoFilter(
            search_string=".git",
            offset=0,
            limit=runtime.get().pu_instance_max_pagination_size,
        )
    )
    assert all(item.is_public_repository for item in repositories)


def test_update_local_repository(
    github_public_repo, regular_user_token, database
) -> None:
    service = repo_service(database, regular_user_token)
    service.git_repo_repository.delete_repo(
        Repo(uuid=github_public_repo.uuid)
    )
    service.update_local_repository(github_public_repo.uuid)
    repo_api = service.get(github_public_repo.uuid)
    assert (
        repo_api.sync_status == RepoStatus.UPDATED
    )


def test_get_commits_only_tag(
    universal_repo, regular_user_token, database
) -> None:
    service = repo_service(database, regular_user_token)
    target_branch = service.git_repo_repository.get_branches(
        universal_repo
    )[0]
    commits = service.get_branch_commits(
        universal_repo.uuid,
        CommitFilter(repo_branch=target_branch, only_tag=True),
    )
    assert commits
    assert all(item.tag for item in commits)


def test_sync_not_available_while_processing(
    github_public_repo, regular_user_token, database
) -> None:
    service = repo_service(database, regular_user_token)
    repo = service.get(github_public_repo.uuid)
    original_status = repo.sync_status
    repo.sync_status = RepoStatus.PROCESSING
    repo.sync_last_datetime = datetime.now(UTC)
    repo.last_update_datetime = datetime.now(UTC)
    service.repo_repository.update(repo.uuid, repo)
    try:
        with pytest.raises(RepoError):
            service.update_local_repository(github_public_repo.uuid)
    finally:
        repo = service.get(github_public_repo.uuid)
        repo.sync_status = original_status
        repo.sync_error = None
        service.repo_repository.update(repo.uuid, repo)


def test_backend_force_sync_requires_backend(
    regular_user_token, database
) -> None:
    with pytest.raises(NoAccessError):
        repo_service(
            database, regular_user_token
        ).backend_force_sync_local_repository_storage()


def test_create_repo_by_api_duplicate(
    github_public_repo, admin_user, database
) -> None:
    """A repo discovered on another instance is created without an agent token"""
    with as_owner(database, admin_user):
        service = repo_service(database, None)
        with pytest.raises(RepoError):
            service.create(
                RepoCreate(
                    repository_url=github_public_repo.repository_url,
                    is_public_repository=True,
                    platform=github_public_repo.platform,
                ),
                is_api=True,
            )


def test_schedule_update_repo(
    github_public_repo, regular_user_token, database
) -> None:
    service = repo_service(database, regular_user_token)
    task = service.schedule_update(github_public_repo.uuid)

    assert task.task_type == OperationTaskType.UPDATE_REPO.value
    assert task.status == OperationTaskStatus.RUNNING.value

    finished = wait_task_finish(database, task, timeout=300)
    assert finished.status == OperationTaskStatus.SUCCESS.value
    assert finished.result == "Repo updated"
    assert (
        service.get(github_public_repo.uuid).sync_status
        == RepoStatus.UPDATED
    )


@pytest.mark.private_repo
def test_schedule_update_repo_without_credentials(
    private_repo, extra_user_token, database
) -> None:
    service = repo_service(database, extra_user_token)
    with pytest.raises(NoAccessError):
        service.schedule_update(private_repo.uuid)


def test_update_local_repository_sync_error(
    github_public_repo,
    regular_user_token,
    database,
    extra_user,
    extra_user_token,
) -> None:
    service = repo_service(database, regular_user_token)
    with (
        owner_setting(
            database,
            extra_user,
            extra_user_token,
            "pu_instance_repo_max_size",
            1,
        ),
        patch.object(
            GithubPlatformClient,
            "get_repo_size",
            return_value=2 * 2**20,
        ),
        pytest.raises(RepoError),
    ):
        service.update_local_repository(github_public_repo.uuid)

    repo = service.get(github_public_repo.uuid)
    assert repo.sync_status == RepoStatus.ERROR
    assert repo.sync_error

    assert (
        service.update_local_repository(github_public_repo.uuid)
        == "Repo updated"
    )


def test_sync_local_repository_storage(
    public_repos, regular_user_token, database
) -> None:
    service = repo_service(database, regular_user_token)
    summary = service.sync_local_repository_storage()

    logging.info(summary)
    assert summary.startswith("Synced ")
    assert f"of {len(service.repo_repository.get_all())}" in (
        summary
    )


def test_schedule_update_all_without_admin(
    regular_user_token, database
) -> None:
    service = repo_service(database, regular_user_token)
    with pytest.raises(NoAccessError):
        service.schedule_update_all()


def test_schedule_update_all(
    public_repos, admin_user_token, database
) -> None:
    service = repo_service(database, admin_user_token)
    task = service.schedule_update_all()

    assert task.task_type == OperationTaskType.UPDATE_ALL_REPOS.value

    finished = wait_task_finish(database, task, timeout=600)
    assert finished.status == OperationTaskStatus.SUCCESS.value
    assert finished.result.startswith("Synced ")


def test_get_available_platforms(
    universal_repo, regular_user_token, database
) -> None:
    service = repo_service(database, regular_user_token)
    branch = service.git_repo_repository.get_branches(universal_repo)[0]

    platforms = service.get_available_platforms(
        universal_repo.uuid, branch=branch
    )
    assert len(platforms) > 0

    platforms = service.get_available_platforms(
        universal_repo.uuid, target_tag="0.0.9"
    )
    assert len(platforms) > 0

    platforms = service.get_available_platforms(
        universal_repo.uuid, target_tag="0.0.0.0"
    )
    assert len(platforms) == 0

    commits = service.git_repo_repository.get_branch_commits_with_tag(
        universal_repo, branch
    )
    platforms = service.get_available_platforms(
        universal_repo.uuid,
        target_commit=commits[-1]["commit"],
        branch=branch,
    )
    assert len(platforms) == 0

    tags = service.git_repo_repository.get_tags_from_all_commits(commits)
    platforms = service.get_available_platforms(
        universal_repo.uuid,
        target_commit=tags[0]["commit"],
        branch=branch,
    )
    assert len(platforms) > 0
