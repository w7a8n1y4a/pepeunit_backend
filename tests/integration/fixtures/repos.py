import logging
import os

import pytest

from app import settings
from app.domain.repo_model import Repo
from app.dto.agent.abc import AgentBackend
from app.dto.enum import GitPlatform, RepoStatus
from app.repositories.git_repo_repository import GitRepoRepository
from app.schemas.pydantic.repo import (
    Credentials,
    RepoCreate,
)
from tests.integration.helpers.http import patch_backend_sync_repo
from tests.integration.helpers.services import repo_service
from tests.integration.helpers.wait import wait_until


def _drop_known_repo(database, url: str) -> None:
    """The repo could return to the database through instance discovery, so it is recreated"""
    git_repo_repository = GitRepoRepository()
    repos = (
        database.query(Repo)
        .where(Repo.repository_url == url)
        .all()
    )
    for repo in repos:
        git_repo_repository.delete_repo(repo)
    database.query(Repo).where(
        Repo.repository_url == url
    ).delete()
    database.commit()


def _create_repo(database, token, spec: dict, *, require_clone: bool = True):
    service = repo_service(database, token)
    _drop_known_repo(database, spec["link"])
    credentials = None
    if not spec["is_public"]:
        credentials = Credentials(
            username=spec["username"], pat_token=spec["pat_token"]
        )

    logging.info(spec["link"])
    repo = service.create(
        RepoCreate(
            repository_url=spec["link"],
            is_public_repository=spec["is_public"],
            platform=spec["platform"],
            credentials=credentials,
        )
    )
    wait_repo_sync(database, token, repo)

    clone_path = service.git_repo_repository.get_path_physic_repository(repo)
    cloned = os.path.exists(clone_path)
    if require_clone:
        assert cloned
    return repo, cloned


def wait_repo_sync(database, token, repo, *, timeout: float = 180) -> None:
    """create schedules the sync in the background, the clone does not appear immediately"""
    service = repo_service(database, token)
    wait_until(
        lambda: service.get(repo.uuid).sync_status
        in (
            RepoStatus.UPDATED,
            RepoStatus.ERROR,
        ),
        timeout=timeout,
        message=f"repo {repo.repository_url} not synced",
        session=database,
    )


@pytest.fixture(scope="session")
def github_public_repo(regular_user_token, database) -> object:
    repo, _ = _create_repo(
        database,
        regular_user_token,
        {
            "link": settings.pu_test_integration_github_public_repo_url,
            "is_public": True,
            "platform": GitPlatform.GITHUB,
        },
    )
    return repo


@pytest.fixture(scope="session")
def gitlab_public_repo(regular_user_token, database) -> object:
    repo, _ = _create_repo(
        database,
        regular_user_token,
        {
            "link": settings.pu_test_integration_gitlab_public_repo_url,
            "is_public": True,
            "platform": GitPlatform.GITLAB,
        },
    )
    return repo


@pytest.fixture(scope="session")
def universal_repo(regular_user_token, database) -> object:
    repo, _ = _create_repo(
        database,
        regular_user_token,
        {
            "link": settings.pu_test_integration_universal_repo_url,
            "is_public": True,
            "platform": GitPlatform.GITLAB,
        },
    )
    return repo


@pytest.fixture(scope="session")
def public_repos(
    github_public_repo, gitlab_public_repo, universal_repo
) -> list:
    repos = [
        github_public_repo,
        gitlab_public_repo,
        universal_repo,
    ]
    backend_token = AgentBackend(name=settings.pu_domain).generate_agent_token()
    assert patch_backend_sync_repo(backend_token) < 400
    return repos


@pytest.fixture(scope="session")
def private_repos(private_repo_enabled, regular_user_token, database) -> list:
    created = []
    for spec in private_repo_enabled:
        try:
            repo, cloned = _create_repo(
                database, regular_user_token, spec, require_clone=False
            )
        except Exception as exc:
            logging.warning("skip private repo %s: %s", spec.get("link"), exc)
            continue
        if not cloned:
            logging.warning(
                "skip private repo %s: clone failed (%s)",
                spec.get("link"),
                getattr(repo, "sync_error", None),
            )
            continue
        created.append(repo)

    if not created:
        pytest.skip("no private repos could be cloned")

    backend_token = AgentBackend(name=settings.pu_domain).generate_agent_token()
    assert patch_backend_sync_repo(backend_token) < 400
    return created


@pytest.fixture(scope="session")
def private_repo(private_repos):
    return private_repos[0]
