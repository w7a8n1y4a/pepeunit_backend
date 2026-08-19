from dataclasses import dataclass

import pytest

from app.dto.enum import VisibilityLevel
from app.schemas.pydantic.repo import RepoCreate, RepoUpdate
from tests.integration.helpers.names import entity_name, unique_name
from tests.integration.helpers.services import (
    branch_commits,
    registry_read,
    repo_service,
)


def _create_repo(
    database,
    cc,
    token,
    registry,
    *,
    name: str,
    visibility_level: VisibilityLevel,
    is_compilable_repo: bool = False,
):
    read = registry_read(database, token, registry)
    service = repo_service(database, cc, token)
    return service.create(
        RepoCreate(
            repository_registry_uuid=registry.uuid,
            default_branch=read.branches[0],
            visibility_level=visibility_level,
            name=name,
            is_compilable_repo=is_compilable_repo,
        )
    )


@dataclass
class LiveRepos:
    universal_public_repo: object
    universal_internal_repo: object
    universal_private_repo: object
    universal_compile_repo: object

    def all(self) -> list:
        return [
            self.universal_public_repo,
            self.universal_internal_repo,
            self.universal_private_repo,
            self.universal_compile_repo,
        ]


@pytest.fixture(scope="session")
def live_repos(
    public_registries,
    universal_registry,
    regular_user_token,
    database,
    cc,
) -> LiveRepos:
    token = regular_user_token
    public_repo = _create_repo(
        database,
        cc,
        token,
        universal_registry,
        name=entity_name("univ_pub"),
        visibility_level=VisibilityLevel.PUBLIC,
    )
    internal_repo = _create_repo(
        database,
        cc,
        token,
        universal_registry,
        name=entity_name("univ_int"),
        visibility_level=VisibilityLevel.INTERNAL,
    )
    private_repo = _create_repo(
        database,
        cc,
        token,
        universal_registry,
        name=entity_name("univ_priv"),
        visibility_level=VisibilityLevel.PRIVATE,
    )
    compile_repo = _create_repo(
        database,
        cc,
        token,
        universal_registry,
        name=entity_name("univ_cmp"),
        visibility_level=VisibilityLevel.PUBLIC,
        is_compilable_repo=True,
    )

    service = repo_service(database, cc, token)
    read, commits = branch_commits(database, token, universal_registry.uuid)

    public_repo = service.update(
        public_repo.uuid,
        RepoUpdate(
            is_auto_update_repo=False,
            default_branch=read.branches[0],
            default_commit=commits[0].commit,
        ),
    )
    internal_repo = service.update(
        internal_repo.uuid,
        RepoUpdate(is_auto_update_repo=True, is_only_tag_update=False),
    )
    private_repo = service.update(
        private_repo.uuid,
        RepoUpdate(is_auto_update_repo=True, is_only_tag_update=True),
    )
    compile_repo = service.update(
        compile_repo.uuid,
        RepoUpdate(default_branch=read.branches[0]),
    )

    return LiveRepos(
        universal_public_repo=public_repo,
        universal_internal_repo=internal_repo,
        universal_private_repo=private_repo,
        universal_compile_repo=compile_repo,
    )


@pytest.fixture(scope="session")
def universal_public_repo(live_repos) -> object:
    return live_repos.universal_public_repo


@pytest.fixture(scope="session")
def universal_internal_repo(live_repos) -> object:
    return live_repos.universal_internal_repo


@pytest.fixture(scope="session")
def universal_private_repo(live_repos) -> object:
    return live_repos.universal_private_repo


@pytest.fixture(scope="session")
def universal_compile_repo(live_repos) -> object:
    return live_repos.universal_compile_repo


@pytest.fixture
def crud_repo(github_public_registry, regular_user_token, database, cc):
    repo = _create_repo(
        database,
        cc,
        regular_user_token,
        github_public_registry,
        name=unique_name("crud"),
        visibility_level=VisibilityLevel.PUBLIC,
    )
    yield repo
    try:
        repo_service(database, cc, regular_user_token).delete(repo.uuid)
    except Exception:
        pass


@pytest.fixture
def private_repo(private_registry, regular_user_token, database, cc):
    repo = _create_repo(
        database,
        cc,
        regular_user_token,
        private_registry,
        name=unique_name("priv"),
        visibility_level=VisibilityLevel.PRIVATE,
        is_compilable_repo=True,
    )
    yield repo
    try:
        repo_service(database, cc, regular_user_token).delete(repo.uuid)
    except Exception:
        pass
