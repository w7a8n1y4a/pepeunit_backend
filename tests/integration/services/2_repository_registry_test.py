import logging

import pytest

from app.configs.errors import GitRepoError, RepositoryRegistryError
from app.configs.rest import get_repository_registry_service
from app.domain.repository_registry_model import RepositoryRegistry
from app.dto.enum import CredentialStatus, RepositoryRegistryStatus
from app.schemas.pydantic.repository_registry import (
    CommitFilter,
    Credentials,
    RepositoryRegistryCreate,
    RepositoryRegistryFilter,
)


@pytest.mark.run(order=0)
def test_create_repository_registry(test_external_repository, database, cc) -> None:

    current_user = pytest.users[0]
    repository_registry_service = get_repository_registry_service(database, pytest.user_tokens_dict[current_user.uuid])

    # create test repos
    new_repositories = []
    for test_repository in test_external_repository:
        logging.info(test_repository['repository_url'])

        repository_registry = repository_registry_service.create(RepositoryRegistryCreate(**test_repository))

        new_repositories.append(repository_registry)

    assert len(new_repositories) >= len(test_external_repository)

    pytest.repository_registries = new_repositories

    # check create repository with exist url
    with pytest.raises(RepositoryRegistryError):
        repository_registry_service.create(RepositoryRegistryCreate(**test_external_repository[0]))

    # check create repository with bad link
    with pytest.raises(RepositoryRegistryError):
        bad_link_repo = RepositoryRegistryCreate(**test_external_repository[0])
        bad_link_repo.repository_url += 't'

        repository_registry_service.create(bad_link_repo)


@pytest.mark.run(order=1)
def test_get_commits_repository(database, cc) -> None:

    current_user = pytest.users[0]
    repository_registry_service = get_repository_registry_service(database, pytest.user_tokens_dict[current_user.uuid])

    # check get repository commits - first 10
    target_repository = pytest.repository_registries[-1]
    logging.info(target_repository.uuid)

    target_branch = repository_registry_service.git_repo_repository.get_branches(target_repository)[0]

    branch_commits = repository_registry_service.get_branch_commits(
        target_repository.uuid, CommitFilter(repo_branch=target_branch, limit=1000)
    )

    # check first commit repository
    assert '7b5804d4e945f87d0925c0480706a2c88320fce2' == branch_commits[-1].commit

    # check get commits for bad branch
    with pytest.raises(GitRepoError):
        repository_registry_service.get_branch_commits(
            target_repository.uuid, CommitFilter(repo_branch=target_branch + 'test')
        )


@pytest.mark.run(order=2)
def test_get_set_credentials(test_external_repository, database, cc) -> None:

    current_user = pytest.users[0]
    repository_registry_service = get_repository_registry_service(database, pytest.user_tokens_dict[current_user.uuid])

    # check set credentials github and gitlab registry
    for target_repository_registry in pytest.repository_registries[:1]:

        credentials = repository_registry_service.get_credentials(target_repository_registry.uuid)

        repository_registry_service.set_credentials(
            target_repository_registry.uuid,
            Credentials(
                username=credentials.credentials.username,
                pat_token=credentials.credentials.pat_token,
            ),
        )

    public_repository_registry = pytest.repository_registries[2]

    # check get Public repository
    with pytest.raises(RepositoryRegistryError):
        repository_registry_service.get_credentials(public_repository_registry.uuid)

    # check set Public repository
    with pytest.raises(RepositoryRegistryError):
        repository_registry_service.set_credentials(
            public_repository_registry.uuid,
            Credentials(
                username="test",
                pat_token="test",
            ),
        )

    # check set credentials for other user
    current_user = pytest.users[1]
    two_repository_registry_service = get_repository_registry_service(
        database, pytest.user_tokens_dict[current_user.uuid]
    )

    for target_repository_registry in pytest.repository_registries[:1]:

        credentials = repository_registry_service.get_credentials(target_repository_registry.uuid)

        two_repository_registry_service.set_credentials(
            target_repository_registry.uuid,
            Credentials(
                username=credentials.credentials.username,
                pat_token=credentials.credentials.pat_token,
            ),
        )

        # check get credentials for other user
        credentials = two_repository_registry_service.get_credentials(target_repository_registry.uuid)

        assert credentials.status == CredentialStatus.VALID.value

        # check get credentials for first user
        credentials = repository_registry_service.get_credentials(target_repository_registry.uuid)

        assert credentials.status == CredentialStatus.VALID.value


@pytest.mark.run(order=3)
def test_get_many_repo(database, cc) -> None:
    current_user = pytest.users[0]
    repository_registry_service = get_repository_registry_service(database, pytest.user_tokens_dict[current_user.uuid])

    # check all user repository
    count, repositories_registry = repository_registry_service.list(
        RepositoryRegistryFilter(
            creator_uuid=current_user.uuid,
        )
    )

    assert len(repositories_registry) >= 5

    # check many get with many filters
    count, repositories_registry = repository_registry_service.list(
        RepositoryRegistryFilter(
            creator_uuid=current_user.uuid,
            search_string='.git',
            is_public_repository=True,
            offset=0,
            limit=1_000_000,
        )
    )
    assert len(repositories_registry) >= 3

    # check get without user - only public repository
    zero_repository_registry_service = get_repository_registry_service(database, None)

    count, repositories_registry = zero_repository_registry_service.list(
        RepositoryRegistryFilter(
            search_string='.git',
            offset=0,
            limit=1_000_000,
        )
    )
    assert all([item.is_public_repository for item in repositories_registry]) == True


@pytest.mark.run(order=4)
def test_update_local_repo(database, cc) -> None:

    current_user = pytest.users[0]
    repository_registry_service = get_repository_registry_service(database, pytest.user_tokens_dict[current_user.uuid])

    target_repository = pytest.repository_registries[0]

    # del local repository
    repository_registry_service.git_repo_repository.delete_repo(RepositoryRegistry(uuid=target_repository.uuid))

    # check download local repository
    repository_registry_service.update_local_repository(target_repository.uuid)
    repository_registry_api = repository_registry_service.get(target_repository.uuid)
    assert repository_registry_api.sync_status == RepositoryRegistryStatus.UPDATED
