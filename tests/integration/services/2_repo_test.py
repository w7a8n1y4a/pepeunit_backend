import os
import shutil

import fastapi
import pytest

from app import settings
from app.configs.gql import get_repo_service
from app.schemas.pydantic.repo import RepoCreate, RepoUpdate, CommitFilter, Credentials
from tests.integration.conftest import Info


@pytest.mark.run(order=0)
def test_create_repo(test_repos, database) -> None:

    current_user = pytest.users[0]
    repo_service = get_repo_service(Info({'db': database, 'jwt_token': pytest.user_tokens_dict[current_user.uuid]}))

    # create test repos
    new_repos = []
    for test_repo in test_repos:
        repo = repo_service.create(RepoCreate(**test_repo))
        new_repos.append(repo)

    assert len(new_repos) >= len(test_repos)

    pytest.repos = new_repos

    # check create repo with exist name
    with pytest.raises(fastapi.HTTPException):
        repo_service.create(RepoCreate(**test_repos[0]))

    # check create repo with bad link
    with pytest.raises(fastapi.HTTPException):
        bad_link_repo = RepoCreate(**test_repos[0])
        bad_link_repo.name += 'test'
        bad_link_repo.repo_url += 't'

        repo_service.create(bad_link_repo)

    # check create repo with bad credentials
    with pytest.raises(fastapi.HTTPException):
        bad_credentials_repo = RepoCreate(**test_repos[0])
        bad_credentials_repo.name += 'test'
        bad_credentials_repo.repo_url += 't'
        bad_credentials_repo.credentials.pat_token += 't'

        repo_service.create(bad_credentials_repo)


@pytest.mark.run(order=1)
def test_update_repo(database) -> None:

    current_user = pytest.users[0]
    repo_service = get_repo_service(Info({'db': database, 'jwt_token': pytest.user_tokens_dict[current_user.uuid]}))

    # check change name to new
    test_repo = pytest.repos[3]
    new_repo_name = test_repo.name + 'test'
    repo_service.update(str(test_repo.uuid), RepoUpdate(name=new_repo_name))

    update_repo = repo_service.get(test_repo.uuid)

    assert new_repo_name == update_repo.name

    # check change name when name is exist
    with pytest.raises(fastapi.HTTPException):
        repo_service.update(str(pytest.repos[0].uuid), RepoUpdate(name=pytest.repos[1].name))

    # check change repo auto update
    new_repo_state = RepoUpdate(is_auto_update_repo=False, update_frequency_in_seconds=600)
    update_repo = repo_service.update(str(pytest.repos[0].uuid), new_repo_state)

    assert update_repo.is_auto_update_repo == new_repo_state.is_auto_update_repo
    assert update_repo.update_frequency_in_seconds == new_repo_state.update_frequency_in_seconds


@pytest.mark.run(order=2)
def test_get_commits_repo(database) -> None:

    current_user = pytest.users[0]
    repo_service = get_repo_service(Info({'db': database, 'jwt_token': pytest.user_tokens_dict[current_user.uuid]}))

    # todo add after unit create
    # # check tags repo
    # result = repo_service.get_versions(target_repo.uuid)
    # assert len(result.versions) > 0

    # check get repo commits - first 10
    target_repo = repo_service.get(pytest.repos[5].uuid)
    branch_commits = repo_service.get_branch_commits(target_repo.uuid, CommitFilter(repo_branch=target_repo.branches[0]))

    # check first commit repo
    assert '7b5804d4e945f87d0925c0480706a2c88320fce2' == branch_commits[-1].commit

    # check get commits for bad branch
    with pytest.raises(fastapi.HTTPException):
        repo_service.get_branch_commits(target_repo.uuid, CommitFilter(repo_branch=target_repo.branches[0] + 'test'))


@pytest.mark.run(order=3)
def test_update_credentials_repo(test_repos, database) -> None:

    current_user = pytest.users[0]
    repo_service = get_repo_service(Info({'db': database, 'jwt_token': pytest.user_tokens_dict[current_user.uuid]}))

    # change to invalid credentials for gitlab and github
    for inc, repo in enumerate(pytest.repos[:1]):

        # change to invalid credentials
        repo_service.update_credentials(repo.uuid, Credentials(username='test', pat_token='test'))

        # check update local repo with bad credentials
        with pytest.raises(fastapi.HTTPException):
            print(repo.uuid)
            repo_service.update_local_repo(repo.uuid)

        # change credentials to normal
        repo_service.update_credentials(repo.uuid, test_repos[inc]['credentials'])


@pytest.mark.run(order=4)
def test_update_default_branch_repo(database) -> None:

    current_user = pytest.users[0]
    repo_service = get_repo_service(Info({'db': database, 'jwt_token': pytest.user_tokens_dict[current_user.uuid]}))

    # set default branch
    for repo in pytest.repos:
        full_repo = repo_service.get(repo.uuid)

        if len(full_repo.branches) > 0:
            repo_service.update_default_branch(repo.uuid, full_repo.branches[0])

    # set bad default branch
    with pytest.raises(fastapi.HTTPException):
        full_repo = repo_service.get(pytest.repos[-1].uuid)
        repo_service.update_default_branch(repo.uuid, full_repo.branches[0] + 't')


@pytest.mark.run(order=5)
def test_update_local_repo(database) -> None:

    current_user = pytest.users[0]
    repo_service = get_repo_service(Info({'db': database, 'jwt_token': pytest.user_tokens_dict[current_user.uuid]}))

    # del local repo
    shutil.rmtree(f'{settings.save_repo_path}/{str(pytest.repos[0].uuid)}', ignore_errors=True)

    # check update local repos
    for repo in pytest.repos:
        repo_service.update_local_repo(repo.uuid)
