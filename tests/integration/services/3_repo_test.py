import logging

import pytest

from app.configs.errors import GitRepoError, NoAccessError, RepoError, ValidationError
from app.configs.rest import get_repo_service, get_repository_registry_service
from app.schemas.pydantic.repo import RepoCreate, RepoFilter, RepoUpdate
from app.schemas.pydantic.repository_registry import (
    CommitFilter,
    RepositoryRegistryFilter,
)


@pytest.mark.run(order=0)
def test_create_repo(test_repos, database, cc) -> None:
    current_user = pytest.users[0]
    repo_service = get_repo_service(
        database, cc, pytest.user_tokens_dict[current_user.uuid]
    )
    repository_registry_service = get_repository_registry_service(
        database, pytest.user_tokens_dict[current_user.uuid]
    )

    # create test repos
    new_repos = []
    for test_repo in test_repos:
        logging.info(test_repo["name"])

        if test_repo["is_compilable_repo"] and test_repo.get("is_auto_update_repo"):
            test_repo["is_only_tag_update"] = True

        count, repository_registry = repository_registry_service.list(
            RepositoryRegistryFilter(search_string=test_repo["repository_url"])
        )

        repository_registry = (
            repository_registry_service.mapper_registry_to_registry_read(
                repository_registry[0]
            )
        )

        repo = repo_service.create(
            RepoCreate(
                repository_registry_uuid=repository_registry.uuid,
                default_branch=repository_registry.branches[0],
                **test_repo,
            )
        )

        new_repos.append(repo)

    assert len(new_repos) >= len(test_repos)

    pytest.repos = new_repos

    # check create repo with exist name
    with pytest.raises(RepoError):
        repo_service.create(RepoCreate(**pytest.repos[0].dict()))

    current_user = pytest.users[1]
    two_repo_service = get_repo_service(
        database, cc, pytest.user_tokens_dict[current_user.uuid]
    )

    # check create repo without credentials
    bad_credentials_repo = RepoCreate(**pytest.repos[1].dict())
    bad_credentials_repo.name += "test"
    with pytest.raises(NoAccessError):
        two_repo_service.create(bad_credentials_repo)


@pytest.mark.run(order=1)
def test_update_repo(database, cc) -> None:
    pytest.repos = pytest.repos[:2] + pytest.repos[3:]

    current_user = pytest.users[0]
    repo_service = get_repo_service(
        database, cc, pytest.user_tokens_dict[current_user.uuid]
    )
    repository_registry_service = get_repository_registry_service(
        database, pytest.user_tokens_dict[current_user.uuid]
    )

    # set default branch for all repos
    for update_repo in pytest.repos:
        logging.info(update_repo.uuid)

        repository_registry = (
            repository_registry_service.mapper_registry_to_registry_read(
                repository_registry_service.get(update_repo.repository_registry_uuid)
            )
        )

        new_repo_state = RepoUpdate(
            default_branch=repository_registry.branches[0],
            is_only_tag_update=True
            if update_repo.is_compilable_repo
            else update_repo.is_only_tag_update,
        )
        repo_service.update(update_repo.uuid, new_repo_state)

    # check change name to new
    test_repo = pytest.repos[3]
    logging.info(test_repo.name)
    new_repo_name = test_repo.name + "test"
    repo_service.update(test_repo.uuid, RepoUpdate(name=new_repo_name))

    update_repo = repo_service.get(test_repo.uuid)

    assert new_repo_name == update_repo.name

    # check change name when name is exist
    with pytest.raises(RepoError):
        repo_service.update(pytest.repos[0].uuid, RepoUpdate(name=pytest.repos[1].name))

    # check change repo auto update to hand update
    repo = pytest.repos[4]
    repository_registry = repository_registry_service.mapper_registry_to_registry_read(
        repository_registry_service.get(repo.repository_registry_uuid)
    )
    logging.info(repo.uuid)
    commits = repository_registry_service.get_branch_commits(
        repository_registry.uuid,
        CommitFilter(repo_branch=repository_registry.branches[0]),
    )
    new_repo_state = RepoUpdate(
        is_auto_update_repo=False,
        default_branch=repository_registry.branches[0],
        default_commit=commits[0].commit,
    )
    update_repo = repo_service.update(repo.uuid, new_repo_state)

    assert update_repo.is_auto_update_repo == new_repo_state.is_auto_update_repo

    # set three type repos update
    for inc, repo in enumerate(pytest.repos[4:7]):
        logging.info(repo.uuid)

        if inc == 0:
            repository_registry = (
                repository_registry_service.mapper_registry_to_registry_read(
                    repository_registry_service.get(repo.repository_registry_uuid)
                )
            )
            commits = repository_registry_service.get_branch_commits(
                repository_registry.uuid,
                CommitFilter(repo_branch=repository_registry.branches[0]),
            )

            new_repo_state = RepoUpdate(
                is_auto_update_repo=False,
                default_branch=repository_registry.branches[0],
                default_commit=commits[0].commit,
            )
        elif inc == 1:
            new_repo_state = RepoUpdate(
                is_auto_update_repo=True, is_only_tag_update=False
            )
        elif inc == 2:
            new_repo_state = RepoUpdate(
                is_auto_update_repo=True, is_only_tag_update=True
            )

        repo_service.update(repo.uuid, new_repo_state)

    # set for compile repo default branch
    target_repo = pytest.repos[-1]
    repository_registry = repository_registry_service.mapper_registry_to_registry_read(
        repository_registry_service.get(target_repo.repository_registry_uuid)
    )
    new_repo_state = RepoUpdate(
        default_branch=repository_registry.branches[0],
    )
    pytest.repos[-1] = repo_service.update(target_repo.uuid, new_repo_state)


@pytest.mark.run(order=2)
def test_get_available_platforms(database, cc) -> None:
    current_user = pytest.users[0]
    repo_service = get_repo_service(
        database, cc, pytest.user_tokens_dict[current_user.uuid]
    )
    repository_registry_service = get_repository_registry_service(
        database, pytest.user_tokens_dict[current_user.uuid]
    )

    target_repo = pytest.repos[-1]

    # check get platforms
    platforms = repo_service.get_available_platforms(target_repo.uuid)
    assert len(platforms) > 0

    # check get platforms by tag
    platforms = repo_service.get_available_platforms(
        target_repo.uuid, target_tag="0.0.9"
    )
    assert len(platforms) > 0

    # check get with bad tag
    platforms = repo_service.get_available_platforms(
        target_repo.uuid, target_tag="0.0.0.0"
    )
    assert len(platforms) == 0

    repository_registry = repository_registry_service.mapper_registry_to_registry_read(
        repository_registry_service.get(target_repo.repository_registry_uuid)
    )
    commits = repo_service.git_repo_repository.get_branch_commits_with_tag(
        repository_registry, target_repo.default_branch
    )

    # check get by commit without tag
    platforms = repo_service.get_available_platforms(
        target_repo.uuid, target_commit=commits[-1]["commit"]
    )
    assert len(platforms) == 0

    repository_registry = repository_registry_service.mapper_registry_to_registry_read(
        repository_registry_service.get(target_repo.repository_registry_uuid)
    )
    commits = repo_service.git_repo_repository.get_branch_commits_with_tag(
        repository_registry, target_repo.default_branch
    )
    tags = repo_service.git_repo_repository.get_tags_from_all_commits(commits)

    # check get by commit with tag
    platforms = repo_service.get_available_platforms(
        target_repo.uuid, target_commit=tags[0]["commit"]
    )
    assert len(platforms) > 0


@pytest.mark.run(order=3)
def test_update_default_branch_repo(database, cc) -> None:
    current_user = pytest.users[0]
    repo_service = get_repo_service(
        database, cc, pytest.user_tokens_dict[current_user.uuid]
    )
    repository_registry_service = get_repository_registry_service(
        database, pytest.user_tokens_dict[current_user.uuid]
    )

    # set default branch
    for repo in pytest.repos:
        full_repo = repo_service.get(repo.uuid)

        logging.info(repo.uuid)

        repository_registry = (
            repository_registry_service.mapper_registry_to_registry_read(
                repository_registry_service.get(full_repo.repository_registry_uuid)
            )
        )

        if len(repository_registry.branches) > 0:
            repo_service.update(
                repo.uuid, RepoUpdate(default_branch=repository_registry.branches[0])
            )

    # set bad default branch
    with pytest.raises(GitRepoError):
        full_repo = repo_service.get(pytest.repos[-1].uuid)
        repository_registry = (
            repository_registry_service.mapper_registry_to_registry_read(
                repository_registry_service.get(full_repo.repository_registry_uuid)
            )
        )
        repo_service.update(
            full_repo.uuid,
            RepoUpdate(default_branch=repository_registry.branches[0] + "t"),
        )


@pytest.mark.run(order=4)
def test_delete_repo(database, cc) -> None:
    current_user = pytest.users[0]
    repo_service = get_repo_service(
        database, cc, pytest.user_tokens_dict[current_user.uuid]
    )

    # del repo
    repo_service.delete(pytest.repos[1].uuid)


@pytest.mark.run(order=5)
def test_delete_repository_registry(database, cc) -> None:
    current_user = pytest.users[0]
    repository_registry_service = get_repository_registry_service(
        database, pytest.user_tokens_dict[current_user.uuid]
    )

    # check del with repos
    with pytest.raises(ValidationError):
        repository_registry_service.delete(pytest.repository_registries[-1].uuid)

    # del repository registry
    repository_registry_service.delete(pytest.repository_registries[1].uuid)


@pytest.mark.run(order=6)
def test_get_many_repo(database, cc) -> None:
    current_user = pytest.users[0]
    repo_service = get_repo_service(
        database, cc, pytest.user_tokens_dict[current_user.uuid]
    )

    # check for users is updated
    count, repos = repo_service.list(
        RepoFilter(creator_uuid=current_user.uuid, is_auto_update_repo=True)
    )

    assert len(repos) == 7

    # check many get with all filters
    count, repos = repo_service.list(
        RepoFilter(
            creator_uuid=current_user.uuid,
            search_string=pytest.test_hash,
            is_auto_update_repo=True,
            offset=0,
            limit=1_000_000,
        )
    )
    assert len(repos) == 7
