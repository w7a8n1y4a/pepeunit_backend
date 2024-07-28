import fastapi
import pytest
import logging

from app.configs.gql import get_repo_service
from app.configs.sub_entities import InfoSubEntity
from app.domain.repo_model import Repo
from app.schemas.pydantic.repo import RepoCreate, RepoUpdate, CommitFilter, Credentials, RepoFilter


@pytest.mark.run(order=0)
def test_create_repo(test_repos, database) -> None:

    current_user = pytest.users[0]
    repo_service = get_repo_service(InfoSubEntity({'db': database, 'jwt_token': pytest.user_tokens_dict[current_user.uuid]}))

    # create test repos
    new_repos = []
    for test_repo in test_repos:
        logging.info(test_repo['name'])
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
    repo_service = get_repo_service(InfoSubEntity({'db': database, 'jwt_token': pytest.user_tokens_dict[current_user.uuid]}))

    # set default branch for all repos
    for update_repo in pytest.repos:
        logging.info(update_repo.uuid)
        new_repo_state = RepoUpdate(default_branch=update_repo.branches[0])
        repo_service.update(update_repo.uuid, new_repo_state)

    # check change name to new
    test_repo = pytest.repos[3]
    logging.info(test_repo.name)
    new_repo_name = test_repo.name + 'test'
    repo_service.update(test_repo.uuid, RepoUpdate(name=new_repo_name))

    update_repo = repo_service.get(test_repo.uuid)

    assert new_repo_name == update_repo.name

    # check change name when name is exist
    with pytest.raises(fastapi.HTTPException):
        repo_service.update(pytest.repos[0].uuid, RepoUpdate(name=pytest.repos[1].name))

    # check change repo auto update to hand update
    repo = pytest.repos[4]
    logging.info(repo.uuid)
    commits = repo_service.get_branch_commits(repo.uuid, CommitFilter(repo_branch=repo.branches[0]))
    new_repo_state = RepoUpdate(
        is_auto_update_repo=False,
        default_branch=repo.branches[0],
        default_commit=commits[0].commit,
    )
    update_repo = repo_service.update(repo.uuid, new_repo_state)

    assert update_repo.is_auto_update_repo == new_repo_state.is_auto_update_repo

    # set three type repos update
    for inc, repo in enumerate(pytest.repos[4:7]):

        logging.info(repo.uuid)

        if inc == 0:

            commits = repo_service.get_branch_commits(repo.uuid, CommitFilter(repo_branch=repo.branches[0]))

            new_repo_state = RepoUpdate(
                is_auto_update_repo=False,
                default_branch=repo.branches[0],
                default_commit=commits[0].commit,
            )
        elif inc == 1:
            new_repo_state = RepoUpdate(
                is_auto_update_repo=True,
                is_only_tag_update=False
            )
        elif inc == 2:
            new_repo_state = RepoUpdate(
                is_auto_update_repo=True,
                is_only_tag_update=True
            )

        repo_service.update(repo.uuid, new_repo_state)


@pytest.mark.run(order=2)
def test_get_commits_repo(database) -> None:

    current_user = pytest.users[0]
    repo_service = get_repo_service(InfoSubEntity({'db': database, 'jwt_token': pytest.user_tokens_dict[current_user.uuid]}))

    # check get repo commits - first 10
    target_repo = repo_service.get(pytest.repos[5].uuid)
    logging.info(target_repo.uuid)
    branch_commits = repo_service.get_branch_commits(
        target_repo.uuid, CommitFilter(repo_branch=target_repo.branches[0], limit=1000)
    )

    # check first commit repo
    assert '7b5804d4e945f87d0925c0480706a2c88320fce2' == branch_commits[-1].commit

    # check get commits for bad branch
    with pytest.raises(fastapi.HTTPException):
        repo_service.get_branch_commits(target_repo.uuid, CommitFilter(repo_branch=target_repo.branches[0] + 'test'))


@pytest.mark.run(order=3)
def test_update_credentials_repo(test_repos, database) -> None:

    current_user = pytest.users[0]
    repo_service = get_repo_service(InfoSubEntity({'db': database, 'jwt_token': pytest.user_tokens_dict[current_user.uuid]}))

    # change to invalid credentials for gitlab and github
    for inc, repo in enumerate(pytest.repos[:1]):
        logging.info(repo.uuid)

        # change to invalid credentials
        repo_service.update_credentials(repo.uuid, Credentials(username='test', pat_token='test'))

        # check update local repo with bad credentials
        with pytest.raises(fastapi.HTTPException):
            repo_service.update_local_repo(repo.uuid)

        # change credentials to normal
        repo_service.update_credentials(repo.uuid, test_repos[inc]['credentials'])


@pytest.mark.run(order=4)
def test_update_default_branch_repo(database) -> None:

    current_user = pytest.users[0]
    repo_service = get_repo_service(InfoSubEntity({'db': database, 'jwt_token': pytest.user_tokens_dict[current_user.uuid]}))

    # set default branch
    for repo in pytest.repos:
        full_repo = repo_service.get(repo.uuid)

        logging.info(repo.uuid)

        if len(full_repo.branches) > 0:
            repo_service.update_default_branch(repo.uuid, full_repo.branches[0])

    # set bad default branch
    with pytest.raises(fastapi.HTTPException):
        full_repo = repo_service.get(pytest.repos[-1].uuid)
        repo_service.update_default_branch(repo.uuid, full_repo.branches[0] + 't')


@pytest.mark.run(order=5)
def test_update_local_repo(database) -> None:

    current_user = pytest.users[0]
    repo_service = get_repo_service(InfoSubEntity({'db': database, 'jwt_token': pytest.user_tokens_dict[current_user.uuid]}))

    # del local repo
    repo_service.git_repo_repository.delete_repo(Repo(uuid=pytest.repos[0].uuid))

    # check update local repos
    for repo in pytest.repos:
        logging.info(repo.uuid)
        repo_service.update_local_repo(repo.uuid)


@pytest.mark.run(order=6)
def test_delete_repo(database) -> None:

    current_user = pytest.users[0]
    repo_service = get_repo_service(InfoSubEntity({'db': database, 'jwt_token': pytest.user_tokens_dict[current_user.uuid]}))

    # del repo
    repo_service.delete(pytest.repos[3].uuid)


@pytest.mark.run(order=7)
def test_get_many_repo(database) -> None:
    current_user = pytest.users[0]
    repo_service = get_repo_service(InfoSubEntity({'db': database, 'jwt_token': pytest.user_tokens_dict[current_user.uuid]}))

    # check for users is updated
    repos = repo_service.list(RepoFilter(creator_uuid=current_user.uuid, is_auto_update_repo=True))

    assert len(repos) == 5

    # check many get with all filters
    repos = repo_service.list(
        RepoFilter(
            creator_uuid=current_user.uuid,
            search_string=pytest.test_hash,
            is_auto_update_repo=True,
            offset=0,
            limit=1_000_000,
        )
    )
    assert len(repos) == 5
