import logging
import os

import pytest

from app import settings
from app.configs.errors import GitRepoError, RepositoryRegistryError
from app.domain.repository_registry_model import RepositoryRegistry
from app.dto.enum import CredentialStatus, RepositoryRegistryStatus
from app.schemas.pydantic.repository_registry import (
    Credentials,
    RepositoryRegistryCreate,
    RepositoryRegistryFilter,
)
from tests.integration.helpers.names import UNIVERSAL_FIRST_COMMIT
from tests.integration.helpers.services import registry_service


def test_create_repository_registry(public_registries, regular_user_token, database) -> None:
    service = registry_service(database, regular_user_token)
    for registry in public_registries:
        logging.info(registry.repository_url)
        assert os.path.exists(
            service.git_repo_repository.get_path_physic_repository(registry)
        )


def test_create_repository_registry_duplicate(
    github_public_registry, regular_user_token, database
) -> None:
    service = registry_service(database, regular_user_token)
    with pytest.raises(RepositoryRegistryError):
        service.create(
            RepositoryRegistryCreate(
                repository_url=github_public_registry.repository_url,
                is_public_repository=True,
                platform=github_public_registry.platform,
            )
        )


def test_create_repository_registry_bad_link(
    github_public_registry, regular_user_token, database
) -> None:
    service = registry_service(database, regular_user_token)
    with pytest.raises(RepositoryRegistryError):
        service.create(
            RepositoryRegistryCreate(
                repository_url=github_public_registry.repository_url + "t",
                is_public_repository=True,
                platform=github_public_registry.platform,
            )
        )


def test_get_commits_repository(universal_registry, regular_user_token, database) -> None:
    service = registry_service(database, regular_user_token)
    logging.info(universal_registry.uuid)
    target_branch = service.git_repo_repository.get_branches(universal_registry)[0]

    from app.schemas.pydantic.repository_registry import CommitFilter

    branch_commits = service.get_branch_commits(
        universal_registry.uuid,
        CommitFilter(repo_branch=target_branch, limit=settings.pu_max_pagination_size),
    )
    assert UNIVERSAL_FIRST_COMMIT == branch_commits[-1].commit


def test_get_commits_bad_branch(universal_registry, regular_user_token, database) -> None:
    service = registry_service(database, regular_user_token)
    target_branch = service.git_repo_repository.get_branches(universal_registry)[0]
    from app.schemas.pydantic.repository_registry import CommitFilter

    with pytest.raises(GitRepoError):
        service.get_branch_commits(
            universal_registry.uuid,
            CommitFilter(repo_branch=target_branch + "test"),
        )


@pytest.mark.private_repo
def test_get_set_credentials_private(
    private_registry, regular_user_token, admin_user_token, database
) -> None:
    service = registry_service(database, regular_user_token)
    logging.info(private_registry.uuid)

    credentials = service.get_credentials(private_registry.uuid)
    service.set_credentials(
        private_registry.uuid,
        Credentials(
            username=credentials.credentials.username,
            pat_token=credentials.credentials.pat_token,
        ),
    )

    two_service = registry_service(database, admin_user_token)
    two_service.set_credentials(
        private_registry.uuid,
        Credentials(
            username=credentials.credentials.username,
            pat_token=credentials.credentials.pat_token,
        ),
    )
    assert two_service.get_credentials(private_registry.uuid).status == CredentialStatus.VALID.value
    assert service.get_credentials(private_registry.uuid).status == CredentialStatus.VALID.value


def test_get_set_credentials_public_fails(
    github_public_registry, regular_user_token, database
) -> None:
    service = registry_service(database, regular_user_token)
    with pytest.raises(RepositoryRegistryError):
        service.get_credentials(github_public_registry.uuid)

    with pytest.raises(RepositoryRegistryError):
        service.set_credentials(
            github_public_registry.uuid,
            Credentials(username="test", pat_token="test"),
        )


def test_get_many_repository(
    public_registries, regular_user, regular_user_token, database
) -> None:
    service = registry_service(database, regular_user_token)
    count, repositories = service.list(
        RepositoryRegistryFilter(creator_uuid=regular_user.uuid)
    )
    assert len(repositories) >= 3

    count, repositories = service.list(
        RepositoryRegistryFilter(
            creator_uuid=regular_user.uuid,
            search_string=".git",
            is_public_repository=True,
            offset=0,
            limit=settings.pu_max_pagination_size,
        )
    )
    assert len(repositories) >= 3

    public_only = registry_service(database, None)
    count, repositories = public_only.list(
        RepositoryRegistryFilter(
            search_string=".git",
            offset=0,
            limit=settings.pu_max_pagination_size,
        )
    )
    assert all(item.is_public_repository for item in repositories)


def test_update_local_repository(
    github_public_registry, regular_user_token, database
) -> None:
    service = registry_service(database, regular_user_token)
    service.git_repo_repository.delete_repo(
        RepositoryRegistry(uuid=github_public_registry.uuid)
    )
    service.update_local_repository(github_public_registry.uuid)
    repository_registry_api = service.get(github_public_registry.uuid)
    assert repository_registry_api.sync_status == RepositoryRegistryStatus.UPDATED
