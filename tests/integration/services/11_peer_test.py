import logging
import uuid as uuid_pkg

import pytest

from app import runtime, settings
from app.configs.errors import (
    FeatureFlagError,
    NoAccessError,
    OperationTaskError,
    PeerError,
    ValidationError,
)
from app.domain.instance_settings_model import InstanceSettings
from app.dto.enum import (
    OperationTaskStatus,
    OperationTaskType,
    PeerCollectionStatus,
    PeerTrustStatus,
)
from app.repositories.instance_settings_repository import (
    InstanceSettingsRepository,
)
from app.schemas.pydantic.peer import (
    PeerCreate,
    PeerFilter,
    PeerUpdate,
)
from app.schemas.pydantic.repo import RepoFilter
from app.services.peer_service import PeerService
from tests.integration.helpers.instance_settings import (
    owner_setting,
    wait_runtime,
)
from tests.integration.helpers.names import unique_peer_url
from tests.integration.helpers.services import (
    peer_service,
    repo_service,
)
from tests.integration.helpers.tasks import age_tasks
from tests.integration.helpers.wait import wait_task_finish


def test_create_peer(crud_peer) -> None:
    logging.info(crud_peer.url)
    assert crud_peer.trust_status == PeerTrustStatus.TRUST.value
    assert crud_peer.create_datetime


def test_create_peer_duplicate(crud_peer, admin_user_token, database) -> None:
    service = peer_service(database, admin_user_token)
    with pytest.raises(PeerError):
        service.create(PeerCreate(url=crud_peer.url))


def test_create_peer_bad_url(admin_user_token, database) -> None:
    service = peer_service(database, admin_user_token)
    with pytest.raises(PeerError):
        service.create(
            PeerCreate(url="https://pepeunit.test/pepeunit/api/v1/metrics")
        )


def test_peer_without_admin(crud_peer, regular_user_token, database) -> None:
    service = peer_service(database, regular_user_token)
    with pytest.raises(NoAccessError):
        service.create(PeerCreate(url=unique_peer_url("no_admin")))
    with pytest.raises(NoAccessError):
        service.update(
            crud_peer.uuid,
            PeerUpdate(trust_status=PeerTrustStatus.BLOCKING),
        )
    with pytest.raises(NoAccessError):
        service.delete(crud_peer.uuid)
    with pytest.raises(NoAccessError):
        service.scan_one(crud_peer.uuid)
    with pytest.raises(NoAccessError):
        service.scan_all()
    with pytest.raises(NoAccessError):
        service.start_integration_tests()


def test_get_peer(crud_peer, regular_user_token, database) -> None:
    service = peer_service(database, regular_user_token)
    assert service.get(crud_peer.uuid).url == crud_peer.url


def test_get_many_peers(crud_peer, regular_user_token, database) -> None:
    service = peer_service(database, regular_user_token)
    count, peers = service.list(PeerFilter.unlimited())
    assert count >= 1
    assert any(item.uuid == crud_peer.uuid for item in peers)

    count, peers = service.list(
        PeerFilter(
            trust_status=[PeerTrustStatus.TRUST.value],
            offset=0,
            limit=runtime.get().pu_instance_max_pagination_size,
        )
    )
    assert all(
        item.trust_status == PeerTrustStatus.TRUST.value for item in peers
    )


def test_list_peers_without_token(crud_peer, database) -> None:
    service = peer_service(database, None)
    count, peers = service.list(PeerFilter.unlimited())
    assert any(item.uuid == crud_peer.uuid for item in peers)


def test_update_peer(crud_peer, admin_user_token, database) -> None:
    service = peer_service(database, admin_user_token)
    updated = service.update(
        crud_peer.uuid,
        PeerUpdate(trust_status=PeerTrustStatus.BLOCKING),
    )
    assert updated.trust_status == PeerTrustStatus.BLOCKING.value
    assert (
        updated.last_collection_status == PeerCollectionStatus.BLOCKING.value
    )

    updated = service.update(
        crud_peer.uuid,
        PeerUpdate(trust_status=PeerTrustStatus.TRUST),
    )
    assert updated.trust_status == PeerTrustStatus.TRUST.value


def test_update_peer_pending_forbidden(
    crud_peer, admin_user_token, database
) -> None:
    service = peer_service(database, admin_user_token)
    with pytest.raises(PeerError):
        service.update(
            crud_peer.uuid,
            PeerUpdate(trust_status=PeerTrustStatus.PENDING),
        )


def test_delete_peer(admin_user_token, database) -> None:
    service = peer_service(database, admin_user_token)
    peer = service.create(PeerCreate(url=unique_peer_url("to_delete")))
    service.delete(peer.uuid)
    with pytest.raises(ValidationError):
        service.get(peer.uuid)


def test_get_current_instance(admin_user_token, database) -> None:
    service = peer_service(database, admin_user_token)
    service.refresh_cache()

    current = service.get_cached_current()
    assert current.schema_version == "v1"
    assert current.name == settings.project_name
    assert current.metrics.user_count >= 2
    assert current.state.instance_datetime


def test_get_cached_peers(
    crud_peer, pending_peer, admin_user_token, database
) -> None:
    service = peer_service(database, admin_user_token)
    service.refresh_cache()

    page = service.get_cached_peers(
        PeerFilter.unlimited(trust_status=[PeerTrustStatus.TRUST.value])
    )
    assert any(item.uuid == crud_peer.uuid for item in page.peers)
    assert all(item.uuid != pending_peer.uuid for item in page.peers)

    pending_page = service.get_cached_peers(
        PeerFilter.unlimited(trust_status=[PeerTrustStatus.PENDING.value])
    )
    assert any(item.uuid == pending_peer.uuid for item in pending_page.peers)


def test_get_cached_urls(crud_peer, admin_user_token, database) -> None:
    service = peer_service(database, admin_user_token)
    service.refresh_cache()

    cached_urls = service.get_cached_urls(PeerFilter.unlimited())
    assert crud_peer.url in cached_urls.urls
    assert cached_urls.total_count == service.list(PeerFilter())[0]


def test_get_cached_repos(
    public_repos, admin_user_token, regular_user_token, database
) -> None:
    service = peer_service(database, admin_user_token)
    service.refresh_cache()

    page = service.get_cached_repos(PeerFilter.unlimited())
    count, public = repo_service(database, regular_user_token).list(
        RepoFilter.unlimited(is_public_repository=True)
    )
    assert page.total_count == count
    assert {item.url for item in page.repos} >= {
        repo.repository_url for repo in public_repos
    }


@pytest.mark.federation
async def test_collect_own_peer(own_peer, admin_user_token, database) -> None:
    service = peer_service(database, admin_user_token)
    peer = await service.collect(own_peer.uuid)
    logging.info(peer.uuid)

    assert peer.last_collection_status == PeerCollectionStatus.SUCCESS.value
    assert peer.last_ping > 0
    assert peer.last_success_datetime
    assert peer.state["schema_version"] == "v1"


@pytest.mark.federation
async def test_collect_unreachable_peer(
    unreachable_peer, admin_user_token, database
) -> None:
    service = peer_service(database, admin_user_token)
    peer = await service.collect(unreachable_peer.uuid)

    assert peer.last_collection_status == PeerCollectionStatus.ERROR.value
    assert peer.last_collection_error


@pytest.mark.federation
async def test_collect_not_trusted_peer(
    pending_peer, admin_user_token, database
) -> None:
    service = peer_service(database, admin_user_token)
    with pytest.raises(PeerError):
        await service.collect(pending_peer.uuid)


@pytest.mark.federation
async def test_collect_response_size_limit(
    own_peer, admin_user_token, database
) -> None:
    service = peer_service(database, admin_user_token)
    repository = InstanceSettingsRepository(database)
    row = repository.get(InstanceSettings(uuid=InstanceSettings.ROW_UUID))
    original_size = row.pu_instance_max_state_size
    row.pu_instance_max_state_size = 1
    repository.update(row.uuid, row)
    wait_runtime("pu_instance_max_state_size", 1)
    try:
        peer = await service.collect(own_peer.uuid)
    finally:
        database.expire_all()
        row = repository.get(InstanceSettings(uuid=InstanceSettings.ROW_UUID))
        row.pu_instance_max_state_size = original_size
        repository.update(row.uuid, row)
        wait_runtime("pu_instance_max_state_size", original_size)

    assert peer.last_collection_status == PeerCollectionStatus.ERROR.value
    assert "exceeds the limit" in peer.last_collection_error

    peer = await service.collect(own_peer.uuid)
    assert peer.last_collection_status == PeerCollectionStatus.SUCCESS.value


@pytest.mark.federation
async def test_collect_all(trusted_peers, admin_user_token, database) -> None:
    service = peer_service(database, admin_user_token)
    summary = await service.collect_all(0)

    logging.info(summary)
    assert summary.startswith("Scanned ")
    assert "failed 0" not in summary
    assert (
        service.get(trusted_peers.own_peer.uuid).last_collection_status
        == PeerCollectionStatus.SUCCESS.value
    )


@pytest.mark.federation
async def test_federation_disabled(
    admin_user_token, database, extra_user, extra_user_token
) -> None:
    service = peer_service(database, admin_user_token)
    with owner_setting(
        database,
        extra_user,
        extra_user_token,
        "pu_ff_federation_enable",
        False,
    ):
        with pytest.raises(FeatureFlagError):
            service.scan_all()
        with pytest.raises(FeatureFlagError):
            await service.collect(uuid_pkg.uuid4())


@pytest.mark.federation
def test_insert_discovered_urls(crud_peer, admin_user_token, database) -> None:
    service = peer_service(database, admin_user_token)
    discovered_url = unique_peer_url("discovered")

    service.insert_discovered_urls(
        [discovered_url, discovered_url, crud_peer.url]
    )

    count, peers = service.list(PeerFilter.unlimited())
    discovered = [item for item in peers if item.url == discovered_url]
    assert len(discovered) == 1
    assert discovered[0].trust_status == PeerTrustStatus.PENDING.value

    service.delete(discovered[0].uuid)


@pytest.mark.federation
def test_scan_one(own_peer, admin_user_token, database) -> None:
    service = peer_service(database, admin_user_token)
    task = service.scan_one(own_peer.uuid)

    assert task.task_type == OperationTaskType.SCAN_PEER.value
    assert task.status == OperationTaskStatus.RUNNING.value

    finished = wait_task_finish(database, task)
    logging.info(finished.result)
    assert finished.status == OperationTaskStatus.SUCCESS.value
    origin = PeerService.peer_origin(own_peer.url)
    assert finished.result.startswith(f"Scanned {origin}")


@pytest.mark.federation
def test_scan_one_unreachable(
    unreachable_peer, admin_user_token, database
) -> None:
    service = peer_service(database, admin_user_token)
    task = service.scan_one(unreachable_peer.uuid)

    finished = wait_task_finish(database, task)
    assert finished.status == OperationTaskStatus.ERROR.value
    assert finished.result


@pytest.mark.federation
def test_scan_all(trusted_peers, admin_user_token, database) -> None:
    service = peer_service(database, admin_user_token)
    logging.info(trusted_peers.own_peer.uuid)
    age_tasks(database, OperationTaskType.SCAN_ALL_PEERS)

    task = service.scan_all()
    assert task.task_type == OperationTaskType.SCAN_ALL_PEERS.value
    assert task.status == OperationTaskStatus.RUNNING.value

    with pytest.raises(OperationTaskError):
        service.scan_all()
