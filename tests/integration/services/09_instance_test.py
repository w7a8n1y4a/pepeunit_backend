import logging
import uuid as uuid_pkg

import pytest

from app import settings
from app.configs.errors import (
    FeatureFlagError,
    InstanceError,
    NoAccessError,
    OperationTaskError,
    ValidationError,
)
from app.dto.enum import (
    InstanceCollectionStatus,
    InstanceTrustStatus,
    OperationTaskStatus,
    OperationTaskType,
)
from app.schemas.pydantic.instance import (
    InstanceCreate,
    InstanceFilter,
    InstanceUpdate,
)
from app.schemas.pydantic.repository_registry import RepositoryRegistryFilter
from tests.integration.helpers.names import unique_instance_url
from tests.integration.helpers.services import (
    instance_service,
    registry_service,
)
from tests.integration.helpers.tasks import age_tasks
from tests.integration.helpers.wait import wait_task_finish


def test_create_instance(crud_instance) -> None:
    logging.info(crud_instance.url)
    assert crud_instance.trust_status == InstanceTrustStatus.TRUST.value
    assert crud_instance.create_datetime


def test_create_instance_duplicate(
    crud_instance, admin_user_token, database
) -> None:
    service = instance_service(database, admin_user_token)
    with pytest.raises(InstanceError):
        service.create(InstanceCreate(url=crud_instance.url))


def test_create_instance_bad_url(admin_user_token, database) -> None:
    service = instance_service(database, admin_user_token)
    with pytest.raises(InstanceError):
        service.create(
            InstanceCreate(url="https://pepeunit.test/pepeunit/api/v1/metrics")
        )


def test_instance_without_admin(
    crud_instance, regular_user_token, database
) -> None:
    service = instance_service(database, regular_user_token)
    with pytest.raises(NoAccessError):
        service.create(InstanceCreate(url=unique_instance_url("no_admin")))
    with pytest.raises(NoAccessError):
        service.update(
            crud_instance.uuid,
            InstanceUpdate(trust_status=InstanceTrustStatus.BLOCKING),
        )
    with pytest.raises(NoAccessError):
        service.delete(crud_instance.uuid)
    with pytest.raises(NoAccessError):
        service.scan_one(crud_instance.uuid)
    with pytest.raises(NoAccessError):
        service.scan_all()
    with pytest.raises(NoAccessError):
        service.start_integration_tests()


def test_get_instance(crud_instance, regular_user_token, database) -> None:
    service = instance_service(database, regular_user_token)
    assert service.get(crud_instance.uuid).url == crud_instance.url


def test_get_many_instance(
    crud_instance, regular_user_token, database
) -> None:
    service = instance_service(database, regular_user_token)
    count, instances = service.list(InstanceFilter.unlimited())
    assert count >= 1
    assert any(item.uuid == crud_instance.uuid for item in instances)

    count, instances = service.list(
        InstanceFilter(
            trust_status=[InstanceTrustStatus.TRUST.value],
            offset=0,
            limit=settings.pu_max_pagination_size,
        )
    )
    assert all(
        item.trust_status == InstanceTrustStatus.TRUST.value
        for item in instances
    )


def test_list_instances_without_token(crud_instance, database) -> None:
    service = instance_service(database, None)
    count, instances = service.list(InstanceFilter.unlimited())
    assert any(item.uuid == crud_instance.uuid for item in instances)


def test_update_instance(crud_instance, admin_user_token, database) -> None:
    service = instance_service(database, admin_user_token)
    updated = service.update(
        crud_instance.uuid,
        InstanceUpdate(trust_status=InstanceTrustStatus.BLOCKING),
    )
    assert updated.trust_status == InstanceTrustStatus.BLOCKING.value
    assert (
        updated.last_collection_status
        == InstanceCollectionStatus.BLOCKING.value
    )

    updated = service.update(
        crud_instance.uuid,
        InstanceUpdate(trust_status=InstanceTrustStatus.TRUST),
    )
    assert updated.trust_status == InstanceTrustStatus.TRUST.value


def test_update_instance_pending_forbidden(
    crud_instance, admin_user_token, database
) -> None:
    service = instance_service(database, admin_user_token)
    with pytest.raises(InstanceError):
        service.update(
            crud_instance.uuid,
            InstanceUpdate(trust_status=InstanceTrustStatus.PENDING),
        )


def test_delete_instance(admin_user_token, database) -> None:
    service = instance_service(database, admin_user_token)
    instance = service.create(
        InstanceCreate(url=unique_instance_url("to_delete"))
    )
    service.delete(instance.uuid)
    with pytest.raises(ValidationError):
        service.get(instance.uuid)


def test_get_current_instance(admin_user_token, database) -> None:
    service = instance_service(database, admin_user_token)
    service.refresh_cache()

    current = service.get_cached_current()
    assert current.schema_version == "v1"
    assert current.name == settings.project_name
    assert current.metrics.user_count >= 2
    assert current.state.instance_datetime


def test_get_cached_instances(
    crud_instance, pending_instance, admin_user_token, database
) -> None:
    service = instance_service(database, admin_user_token)
    service.refresh_cache()

    page = service.get_cached_instances(
        InstanceFilter.unlimited(
            trust_status=[InstanceTrustStatus.TRUST.value]
        )
    )
    assert any(item.uuid == crud_instance.uuid for item in page.instances)
    assert all(item.uuid != pending_instance.uuid for item in page.instances)

    pending_page = service.get_cached_instances(
        InstanceFilter.unlimited(
            trust_status=[InstanceTrustStatus.PENDING.value]
        )
    )
    assert any(
        item.uuid == pending_instance.uuid for item in pending_page.instances
    )


def test_get_cached_urls(crud_instance, admin_user_token, database) -> None:
    service = instance_service(database, admin_user_token)
    service.refresh_cache()

    cached_urls = service.get_cached_urls(InstanceFilter.unlimited())
    assert crud_instance.url in cached_urls.urls
    assert cached_urls.total_count == service.list(InstanceFilter())[0]


def test_get_cached_registries(
    public_registries, admin_user_token, regular_user_token, database
) -> None:
    service = instance_service(database, admin_user_token)
    service.refresh_cache()

    page = service.get_cached_registries(InstanceFilter.unlimited())
    count, public = registry_service(database, regular_user_token).list(
        RepositoryRegistryFilter.unlimited(is_public_repository=True)
    )
    assert page.total_count == count
    assert {item.url for item in page.registries} >= {
        registry.repository_url for registry in public_registries
    }


@pytest.mark.federation
async def test_collect_own_instance(
    own_instance, admin_user_token, database
) -> None:
    service = instance_service(database, admin_user_token)
    instance = await service.collect(own_instance.uuid)
    logging.info(instance.uuid)

    assert (
        instance.last_collection_status
        == InstanceCollectionStatus.SUCCESS.value
    )
    assert instance.last_ping > 0
    assert instance.last_success_datetime
    assert instance.state["schema_version"] == "v1"


@pytest.mark.federation
async def test_collect_unreachable_instance(
    unreachable_instance, admin_user_token, database
) -> None:
    service = instance_service(database, admin_user_token)
    instance = await service.collect(unreachable_instance.uuid)

    assert (
        instance.last_collection_status == InstanceCollectionStatus.ERROR.value
    )
    assert instance.last_collection_error


@pytest.mark.federation
async def test_collect_not_trusted_instance(
    pending_instance, admin_user_token, database
) -> None:
    service = instance_service(database, admin_user_token)
    with pytest.raises(InstanceError):
        await service.collect(pending_instance.uuid)


@pytest.mark.federation
async def test_collect_response_size_limit(
    own_instance, admin_user_token, database
) -> None:
    service = instance_service(database, admin_user_token)
    original_size = settings.pu_instance_max_state_size

    settings.pu_instance_max_state_size = 1
    try:
        instance = await service.collect(own_instance.uuid)
    finally:
        settings.pu_instance_max_state_size = original_size

    assert (
        instance.last_collection_status == InstanceCollectionStatus.ERROR.value
    )
    assert "exceeds the limit" in instance.last_collection_error

    instance = await service.collect(own_instance.uuid)
    assert (
        instance.last_collection_status
        == InstanceCollectionStatus.SUCCESS.value
    )


@pytest.mark.federation
async def test_collect_all(
    trusted_instances, admin_user_token, database
) -> None:
    service = instance_service(database, admin_user_token)
    summary = await service.collect_all(0)

    logging.info(summary)
    assert summary.startswith("Scanned ")
    assert "failed 0" not in summary
    assert (
        service.get(trusted_instances.own_instance.uuid).last_collection_status
        == InstanceCollectionStatus.SUCCESS.value
    )


@pytest.mark.federation
async def test_federation_disabled(admin_user_token, database) -> None:
    service = instance_service(database, admin_user_token)
    original_flag = settings.pu_ff_federation_enable

    settings.pu_ff_federation_enable = False
    try:
        with pytest.raises(FeatureFlagError):
            service.scan_all()
        with pytest.raises(FeatureFlagError):
            await service.collect(uuid_pkg.uuid4())
    finally:
        settings.pu_ff_federation_enable = original_flag


@pytest.mark.federation
def test_insert_discovered_urls(
    crud_instance, admin_user_token, database
) -> None:
    service = instance_service(database, admin_user_token)
    discovered_url = unique_instance_url("discovered")

    service.insert_discovered_urls(
        [discovered_url, discovered_url, crud_instance.url]
    )

    count, instances = service.list(InstanceFilter.unlimited())
    discovered = [item for item in instances if item.url == discovered_url]
    assert len(discovered) == 1
    assert discovered[0].trust_status == InstanceTrustStatus.PENDING.value

    service.delete(discovered[0].uuid)


@pytest.mark.federation
def test_scan_one(own_instance, admin_user_token, database) -> None:
    service = instance_service(database, admin_user_token)
    task = service.scan_one(own_instance.uuid)

    assert task.task_type == OperationTaskType.SCAN_INSTANCE.value
    assert task.status == OperationTaskStatus.RUNNING.value

    finished = wait_task_finish(database, task)
    logging.info(finished.result)
    assert finished.status == OperationTaskStatus.SUCCESS.value
    assert finished.result.startswith(f"Scanned {own_instance.url}")


@pytest.mark.federation
def test_scan_one_unreachable(
    unreachable_instance, admin_user_token, database
) -> None:
    service = instance_service(database, admin_user_token)
    task = service.scan_one(unreachable_instance.uuid)

    finished = wait_task_finish(database, task)
    assert finished.status == OperationTaskStatus.ERROR.value
    assert finished.result


@pytest.mark.federation
def test_scan_all(trusted_instances, admin_user_token, database) -> None:
    service = instance_service(database, admin_user_token)
    logging.info(trusted_instances.own_instance.uuid)
    age_tasks(database, OperationTaskType.SCAN_ALL_INSTANCES)

    task = service.scan_all()
    assert task.task_type == OperationTaskType.SCAN_ALL_INSTANCES.value
    assert task.status == OperationTaskStatus.RUNNING.value

    with pytest.raises(OperationTaskError):
        service.scan_all()
