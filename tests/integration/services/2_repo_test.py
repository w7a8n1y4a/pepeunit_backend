import fastapi
import pytest

from app.configs.gql import get_repo_service
from app.schemas.pydantic.repo import RepoCreate, RepoUpdate, CommitFilter
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

    # check change name on new
    current_user = pytest.users[0]
    repo_service = get_repo_service(Info({'db': database, 'jwt_token': pytest.user_tokens_dict[current_user.uuid]}))

    test_repo = pytest.repos[3]
    new_repo_name = test_repo.name + 'test'
    repo_service.update(str(test_repo.uuid), RepoUpdate(name=new_repo_name))

    update_repo = repo_service.get(test_repo.uuid)

    assert new_repo_name == update_repo.name

    # check change name on exist
    with pytest.raises(fastapi.HTTPException):
        current_user = pytest.users[0]
        repo_service.update(str(pytest.repos[0].uuid), RepoUpdate(name=pytest.repos[1].name))

    # check change repo auto update
    new_repo_state = RepoUpdate(is_auto_update_repo=False, update_frequency_in_seconds=600)
    update_repo = repo_service.update(str(pytest.repos[0].uuid), new_repo_state)

    assert update_repo.is_auto_update_repo == new_repo_state.is_auto_update_repo
    assert update_repo.update_frequency_in_seconds == new_repo_state.update_frequency_in_seconds


@pytest.mark.run(order=2)
def test_get_commits_repo(database) -> None:

    # check change repo name on new
    current_user = pytest.users[0]
    repo_service = get_repo_service(Info({'db': database, 'jwt_token': pytest.user_tokens_dict[current_user.uuid]}))

    target_repo = repo_service.get(pytest.repos[5].uuid)

    # todo add after unit create
    # # check tags repo
    # result = repo_service.get_versions(target_repo.uuid)
    # assert len(result.versions) > 0

    branch_commits = repo_service.get_branch_commits(target_repo.uuid, CommitFilter(repo_branch=target_repo.branches[0]))

    # check first commit repo
    assert '7b5804d4e945f87d0925c0480706a2c88320fce2' == branch_commits[-1].commit

    # check change name on exist
    with pytest.raises(fastapi.HTTPException):
        repo_service.get_branch_commits(target_repo.uuid, CommitFilter(repo_branch=target_repo.branches[0] + 'test'))