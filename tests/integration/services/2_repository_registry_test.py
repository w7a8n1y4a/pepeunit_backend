import logging

import pytest

from app.configs.errors import RepositoryRegistryError
from app.configs.rest import get_repository_registry_service
from app.schemas.pydantic.repository_registry import Credentials, RepositoryRegistryCreate


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

    # check create repo with bad link
    with pytest.raises(RepositoryRegistryError):
        bad_link_repo = RepositoryRegistryCreate(**test_external_repository[0])
        bad_link_repo.repository_url += 't'

        repository_registry_service.create(bad_link_repo)


@pytest.mark.run(order=1)
def test_credentials(test_external_repository, database, cc) -> None:

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
        two_repository_registry_service.get_credentials(target_repository_registry.uuid)

        # check get credentials for first user
        repository_registry_service.get_credentials(target_repository_registry.uuid)
