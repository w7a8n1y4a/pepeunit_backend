import logging
import os

import pytest

from app import settings
from app.domain.repository_registry_model import RepositoryRegistry
from app.dto.agent.abc import AgentBackend
from app.dto.enum import GitPlatform, RepositoryRegistryStatus
from app.schemas.pydantic.repository_registry import (
    Credentials,
    RepositoryRegistryCreate,
)
from tests.integration.helpers.http import patch_backend_sync_registry
from tests.integration.helpers.services import registry_service
from tests.integration.helpers.wait import wait_until


def _drop_known_registry(database, url: str) -> None:
    """The registry could return to the database through instance discovery, so it is recreated"""
    database.query(RepositoryRegistry).where(
        RepositoryRegistry.repository_url == url
    ).delete()
    database.commit()


def _create_registry(database, token, spec: dict, *, require_clone: bool = True):
    service = registry_service(database, token)
    _drop_known_registry(database, spec["link"])
    credentials = None
    if not spec["is_public"]:
        credentials = Credentials(
            username=spec["username"], pat_token=spec["pat_token"]
        )

    logging.info(spec["link"])
    registry = service.create(
        RepositoryRegistryCreate(
            repository_url=spec["link"],
            is_public_repository=spec["is_public"],
            platform=spec["platform"],
            credentials=credentials,
        )
    )
    wait_registry_sync(database, token, registry)

    clone_path = service.git_repo_repository.get_path_physic_repository(registry)
    cloned = os.path.exists(clone_path)
    if require_clone:
        assert cloned
    return registry, cloned


def wait_registry_sync(database, token, registry, *, timeout: float = 180) -> None:
    """create schedules the sync in the background, the clone does not appear immediately"""
    service = registry_service(database, token)
    wait_until(
        lambda: service.get(registry.uuid).sync_status
        in (
            RepositoryRegistryStatus.UPDATED,
            RepositoryRegistryStatus.ERROR,
        ),
        timeout=timeout,
        message=f"registry {registry.repository_url} not synced",
        session=database,
    )


@pytest.fixture(scope="session")
def github_public_registry(regular_user_token, database) -> object:
    registry, _ = _create_registry(
        database,
        regular_user_token,
        {
            "link": settings.pu_test_integration_github_public_repo_url,
            "is_public": True,
            "platform": GitPlatform.GITHUB,
        },
    )
    return registry


@pytest.fixture(scope="session")
def gitlab_public_registry(regular_user_token, database) -> object:
    registry, _ = _create_registry(
        database,
        regular_user_token,
        {
            "link": settings.pu_test_integration_gitlab_public_repo_url,
            "is_public": True,
            "platform": GitPlatform.GITLAB,
        },
    )
    return registry


@pytest.fixture(scope="session")
def universal_registry(regular_user_token, database) -> object:
    registry, _ = _create_registry(
        database,
        regular_user_token,
        {
            "link": settings.pu_test_integration_universal_repo_url,
            "is_public": True,
            "platform": GitPlatform.GITLAB,
        },
    )
    return registry


@pytest.fixture(scope="session")
def public_registries(
    github_public_registry, gitlab_public_registry, universal_registry
) -> list:
    registries = [
        github_public_registry,
        gitlab_public_registry,
        universal_registry,
    ]
    backend_token = AgentBackend(name=settings.pu_domain).generate_agent_token()
    assert patch_backend_sync_registry(backend_token) < 400
    return registries


@pytest.fixture(scope="session")
def private_registries(private_repo_enabled, regular_user_token, database) -> list:
    created = []
    for spec in private_repo_enabled:
        try:
            registry, cloned = _create_registry(
                database, regular_user_token, spec, require_clone=False
            )
        except Exception as exc:
            logging.warning("skip private registry %s: %s", spec.get("link"), exc)
            continue
        if not cloned:
            logging.warning(
                "skip private registry %s: clone failed (%s)",
                spec.get("link"),
                getattr(registry, "sync_error", None),
            )
            continue
        created.append(registry)

    if not created:
        pytest.skip("no private registries could be cloned")

    backend_token = AgentBackend(name=settings.pu_domain).generate_agent_token()
    assert patch_backend_sync_registry(backend_token) < 400
    return created


@pytest.fixture(scope="session")
def private_registry(private_registries):
    return private_registries[0]
