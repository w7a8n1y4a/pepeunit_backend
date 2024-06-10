import pytest

from app.configs.gql import get_repo_service
from app.schemas.pydantic.repo import RepoCreate
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
