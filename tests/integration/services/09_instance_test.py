import logging
import uuid as uuid_pkg
from datetime import UTC, datetime, timedelta

import pytest

from app import settings
from app.configs.errors import (
    FeatureFlagError,
    InstanceError,
    NoAccessError,
    OperationTaskError,
    ValidationError,
)
from app.domain.instance_model import Instance
from app.domain.operation_task_model import OperationTask
from app.dto.enum import (
    GitPlatform,
    InstanceCollectionStatus,
    InstanceTrustStatus,
    IntegrationTestsStatus,
    OperationTaskStatus,
    OperationTaskType,
    RepositoryRegistryStatus,
)
from app.dto.integration_tests import IntegrationTestsStats
from app.repositories.instance_cache_repository import instance_cache
from app.repositories.instance_repository import InstanceRepository
from app.repositories.operation_task_repository import OperationTaskRepository
from app.schemas.pydantic.instance import (
    InstanceCreate,
    InstanceFilter,
    InstancePublicRegistry,
    InstanceUpdate,
)
from app.schemas.pydantic.repository_registry import RepositoryRegistryFilter
from app.services.instance_service import InstanceService
from tests.integration.helpers.names import (
    TEST_HASH,
    unique_instance_url,
)
from tests.integration.helpers.services import (
    instance_service,
    registry_service,
)
from tests.integration.helpers.tasks import age_tasks
from tests.integration.helpers.wait import wait_task_finish


def _instance_by_url(database, url: str) -> Instance | None:
    return database.query(Instance).filter(Instance.url == url).first()


def _create_integration_tests_task(
    database,
    creator_uuid,
    status: OperationTaskStatus,
    result: str | None,
) -> OperationTask:
    now = datetime.now(UTC)
    return OperationTaskRepository(database).create(
        OperationTask(
            creator_uuid=creator_uuid,
            task_type=OperationTaskType.INTEGRATION_TESTS.value,
            status=status.value,
            result=result,
            create_datetime=now,
            start_datetime=now,
        )
    )


def test_create_instance(crud_instance, database) -> None:
    logging.info(crud_instance.url)
    assert crud_instance.trust_status == InstanceTrustStatus.TRUST.value
    assert crud_instance.create_datetime
    assert crud_instance.consecutive_success_count == 0
    assert _instance_by_url(database, crud_instance.url)


def test_create_instance_duplicate_url(
    crud_instance, admin_user_token, database
) -> None:
    service = instance_service(database, admin_user_token)
    with pytest.raises(InstanceError):
        service.create(InstanceCreate(url=crud_instance.url))


def test_create_instance_bad_url(admin_user_token, database) -> None:
    service = instance_service(database, admin_user_token)
    for url in (
        "ftp://pepeunit.test/pepeunit/api/v1/instances/current",
        "https:///pepeunit/api/v1/instances/current",
        "https://pepeunit.test/pepeunit/api/v1/instances/current?token=1",
        "https://pepeunit.test/pepeunit/api/v1/instances/current#state",
        "https://user:pass@pepeunit.test/pepeunit/api/v1/instances/current",
        "https://pepeunit.test/pepeunit/api/v1/metrics",
        "https://pepeunit.test",
    ):
        with pytest.raises(InstanceError):
            service.create(InstanceCreate(url=url))


def test_instance_without_admin(
    crud_instance, regular_user_token, database
) -> None:
    service = instance_service(database, regular_user_token)
    for operation in (
        lambda: service.create(
            InstanceCreate(url=unique_instance_url("no_admin"))
        ),
        lambda: service.update(
            crud_instance.uuid,
            InstanceUpdate(trust_status=InstanceTrustStatus.BLOCKING),
        ),
        lambda: service.delete(crud_instance.uuid),
        lambda: service.scan_one(crud_instance.uuid),
        lambda: service.scan_all(),
        lambda: service.start_integration_tests(),
    ):
        with pytest.raises(NoAccessError):
            operation()


def test_get_instance(crud_instance, regular_user_token, database) -> None:
    service = instance_service(database, regular_user_token)
    assert service.get(crud_instance.uuid).url == crud_instance.url


def test_list_instances(crud_instance, regular_user_token, database) -> None:
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

    count, instances = service.list(
        InstanceFilter(
            trust_status=[InstanceTrustStatus.BLOCKING.value],
        )
    )
    assert all(
        item.trust_status == InstanceTrustStatus.BLOCKING.value
        for item in instances
    )


def test_list_instances_without_token(crud_instance, database) -> None:
    """list is available to the Bot agent, so it works without a token too"""
    service = instance_service(database, None)
    count, instances = service.list(InstanceFilter.unlimited())
    assert any(item.uuid == crud_instance.uuid for item in instances)


def test_update_instance_blocking(
    crud_instance, admin_user_token, database
) -> None:
    service = instance_service(database, admin_user_token)
    instance = crud_instance
    instance.last_ping = 10.5
    instance.last_collection_error = "old error"
    instance.last_collection_status = InstanceCollectionStatus.SUCCESS.value
    InstanceRepository(db=database).update(instance.uuid, instance)

    updated = service.update(
        crud_instance.uuid,
        InstanceUpdate(trust_status=InstanceTrustStatus.BLOCKING),
    )
    assert updated.trust_status == InstanceTrustStatus.BLOCKING.value
    assert (
        updated.last_collection_status
        == InstanceCollectionStatus.BLOCKING.value
    )
    assert updated.last_ping is None
    assert updated.last_collection_error is None

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
    """The url is normalized on create, the host and the scheme are lowered"""
    service = instance_service(database, admin_user_token)
    url = unique_instance_url("to_delete")
    host, _, path = url.removeprefix("https://").partition("/")

    instance = service.create(
        InstanceCreate(url=f"  HTTPS://{host.upper()}/{path}/  ")
    )
    assert instance.url == url

    service.delete(instance.uuid)
    with pytest.raises(ValidationError):
        service.get(instance.uuid)


def test_refresh_cache(crud_instance, admin_user_token, database) -> None:
    service = instance_service(database, admin_user_token)
    service.refresh_cache()

    cached_urls = service.get_cached_urls(InstanceFilter.unlimited())
    assert crud_instance.url in cached_urls.urls
    assert cached_urls.total_count == service.list(InstanceFilter())[0]
    assert cached_urls.urls == sorted(cached_urls.urls)

    limited = service.get_cached_urls(InstanceFilter(offset=0, limit=1))
    assert limited.total_count == cached_urls.total_count
    assert limited.urls == cached_urls.urls[:1]

    tail = service.get_cached_urls(InstanceFilter(offset=1))
    assert tail.urls == cached_urls.urls[1 : 1 + settings.pu_max_pagination_size]


def test_get_cached_current(admin_user_token, database) -> None:
    service = instance_service(database, admin_user_token)
    service.refresh_cache()

    current = service.get_cached_current()
    assert current.schema_version == "v1"
    assert current.name == settings.project_name
    assert current.version == settings.version
    assert current.state.instance_datetime
    assert current.metrics.user_count >= 2
    assert (
        current.feature_flags.pu_ff_federation_enable
        == settings.pu_ff_federation_enable
    )


def test_get_cached_instances_filter(
    crud_instance, pending_instance, admin_user_token, database
) -> None:
    service = instance_service(database, admin_user_token)
    service.refresh_cache()

    page = service.get_cached_instances(
        InstanceFilter.unlimited(
            trust_status=[InstanceTrustStatus.TRUST.value]
        )
    )
    assert all(
        item.trust_status == InstanceTrustStatus.TRUST
        for item in page.instances
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

    limited = service.get_cached_instances(
        InstanceFilter(offset=0, limit=1)
    )
    assert len(limited.instances) == 1
    assert limited.total_count >= 2

    shifted = service.get_cached_instances(
        InstanceFilter(offset=1, limit=1)
    )
    assert shifted.instances[0].uuid != limited.instances[0].uuid


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

    limited = service.get_cached_registries(
        InstanceFilter(offset=0, limit=1)
    )
    assert len(limited.registries) == 1
    assert limited.total_count == page.total_count


def test_cache_not_initialized(admin_user_token, database) -> None:
    service = instance_service(database, admin_user_token)
    service.refresh_cache()
    snapshot = instance_cache.get()

    instance_cache._snapshot = None
    try:
        with pytest.raises(InstanceError):
            service.get_cached_current()
        with pytest.raises(InstanceError):
            service.get_cached_instances(InstanceFilter())
        with pytest.raises(InstanceError):
            service.get_cached_urls(InstanceFilter())
        with pytest.raises(InstanceError):
            service.get_cached_registries(InstanceFilter())
    finally:
        instance_cache.update(snapshot)


def test_integration_tests_stats() -> None:
    """The total is taken from the collection line of the log"""
    stats = IntegrationTestsStats.from_result(
        "collected 241 items\n"
        "======= 231 passed, 10 skipped, 3 warnings in 174.21s (0:02:54)"
        " =======\n"
    )
    assert stats.total == 241
    assert stats.executed == 231
    assert stats.success_percentage == 100.0
    assert stats.to_text() == (
        "total 241, passed 231, skipped 10, failed 0, error 0, warning 3"
        " in 174.21s"
    )

    # the deselected tests are collected, but they are never run
    stats = IntegrationTestsStats.from_result(
        "collected 250 items / 9 deselected / 241 selected\n"
        "==== 241 passed, 9 deselected in 174.21s ===="
    )
    assert stats.total == 241
    assert stats.to_text() == (
        "total 241, passed 241, skipped 0, failed 0, error 0, deselected 9"
        " in 174.21s"
    )

    # the quiet mode has no collection line, the counts are summed up
    stats = IntegrationTestsStats.from_result(
        "==== 2 errors, 1 xfailed, 1 xpassed, 1 passed in 3.00s ===="
    )
    assert stats.total == 5
    assert stats.success_percentage == 40.0

    # a log without the pytest summary line gives no counts at all
    for result in (None, "", "ImportError: cannot import name settings"):
        assert IntegrationTestsStats.from_result(result).to_text() is None

    # a full log is replaced by its counts, one without a summary by its tail
    assert IntegrationTestsStats.get_result_text(
        "collected 241 items\n" + "y" * 300 + "\n==== 241 passed in 10.00s =="
    ) == ("total 241, passed 241, skipped 0, failed 0, error 0 in 10.00s")

    tail = IntegrationTestsStats.get_result_text("y" * 300 + "no summary")
    assert len(tail) == IntegrationTestsStats.MAX_TELEGRAM_RESULT_LENGTH
    assert tail.endswith("no summary")


def test_get_integration_tests_state(
    admin_user, admin_user_token, database
) -> None:
    service = instance_service(database, admin_user_token)

    for status, result, expected_status, expected_percentage in (
        (OperationTaskStatus.RUNNING, None, IntegrationTestsStatus.RUNNING, None),
        (
            OperationTaskStatus.SUCCESS,
            "==== 13 passed in 10.00s ====",
            IntegrationTestsStatus.SUCCESS,
            100.0,
        ),
        (
            OperationTaskStatus.ERROR,
            "==== 1 failed, 12 passed in 10.00s ====",
            IntegrationTestsStatus.WARNING,
            92.31,
        ),
        (OperationTaskStatus.ERROR, None, IntegrationTestsStatus.ERROR, None),
    ):
        task = _create_integration_tests_task(
            database, admin_user.uuid, status, result
        )
        try:
            state = service.get_integration_tests_state()
            assert state.integration_tests_status == expected_status
            assert state.integration_tests_success_percentage == (
                expected_percentage
            )
            assert state.integration_tests_datetime
        finally:
            OperationTaskRepository(database).delete(task)


@pytest.mark.federation
async def test_collect_own_instance(
    own_instance, admin_user_token, database
) -> None:
    service = instance_service(database, admin_user_token)
    instance = await service.collect(own_instance.uuid)

    assert (
        instance.last_collection_status
        == InstanceCollectionStatus.SUCCESS.value
    )
    assert instance.last_ping > 0
    assert instance.last_success_datetime
    assert instance.last_attempt_datetime
    assert instance.last_collection_error is None
    assert instance.consecutive_success_count >= 1
    assert instance.state["schema_version"] == "v1"

    service.is_valid_collection_status(instance)

    previous_count = instance.consecutive_success_count
    instance = await service.collect(own_instance.uuid)
    assert instance.consecutive_success_count == previous_count + 1


@pytest.mark.federation
async def test_collect_unreachable_instance(
    unreachable_instance, admin_user_token, database
) -> None:
    service = instance_service(database, admin_user_token)
    instance = await service.collect(unreachable_instance.uuid)

    assert (
        instance.last_collection_status == InstanceCollectionStatus.ERROR.value
    )
    assert instance.last_ping is None
    assert instance.last_collection_error
    assert (
        len(instance.last_collection_error)
        <= InstanceService.MAX_COLLECTION_ERROR_LENGTH
    )
    assert instance.consecutive_success_count == 0

    with pytest.raises(InstanceError):
        service.is_valid_collection_status(instance)


@pytest.mark.federation
async def test_collect_not_trusted_instance(
    pending_instance, crud_instance, admin_user_token, database
) -> None:
    service = instance_service(database, admin_user_token)
    with pytest.raises(InstanceError):
        await service.collect(pending_instance.uuid)

    service.update(
        crud_instance.uuid,
        InstanceUpdate(trust_status=InstanceTrustStatus.BLOCKING),
    )
    try:
        with pytest.raises(InstanceError):
            await service.collect(crud_instance.uuid)
    finally:
        service.update(
            crud_instance.uuid,
            InstanceUpdate(trust_status=InstanceTrustStatus.TRUST),
        )


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
    own_instance, unreachable_instance, admin_user_token, database
) -> None:
    service = instance_service(database, admin_user_token)
    summary = await service.collect_all(0)

    logging.info(summary)
    assert summary.startswith("Scanned ")
    # unreachable_instance belongs to the Trust selection and must end up in failed
    assert "failed 0" not in summary
    assert (
        service.get(own_instance.uuid).last_collection_status
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
            service.scan_one(uuid_pkg.uuid4())
        with pytest.raises(FeatureFlagError):
            await service.collect_all(0)
        with pytest.raises(FeatureFlagError):
            await service.collect(uuid_pkg.uuid4())
        with pytest.raises(FeatureFlagError):
            await service.delete_stale_instances()
    finally:
        settings.pu_ff_federation_enable = original_flag


@pytest.mark.federation
def test_insert_discovered_urls(
    crud_instance, admin_user_token, database
) -> None:
    service = instance_service(database, admin_user_token)
    discovered_url = unique_instance_url("discovered")

    service.insert_discovered_urls(
        [
            discovered_url,
            discovered_url,
            crud_instance.url,
            InstanceService.get_own_url(),
            f"ftp://bad-{TEST_HASH}.pepeunit.test/instances/current",
        ]
    )

    discovered = _instance_by_url(database, discovered_url)
    assert discovered
    assert discovered.trust_status == InstanceTrustStatus.PENDING.value

    count, instances = service.list(InstanceFilter.unlimited())
    own_urls = [
        item for item in instances if item.url == InstanceService.get_own_url()
    ]
    assert len(own_urls) <= 1

    service.delete(discovered.uuid)


@pytest.mark.federation
def test_insert_discovered_registries_skipped(
    github_public_registry, admin_user_token, regular_user_token, database
) -> None:
    service = instance_service(database, admin_user_token)
    registry_svc = registry_service(database, regular_user_token)
    known = registry_svc.get(github_public_registry.uuid)

    service.insert_discovered_registries(
        [
            InstancePublicRegistry(
                url=known.repository_url,
                platform=GitPlatform(known.platform),
            ),
            InstancePublicRegistry(
                url=f"https://pepeunit.test/{TEST_HASH}/no_git_suffix",
                platform=GitPlatform.GITHUB,
            ),
        ]
    )

    count, registries = registry_svc.list(
        RepositoryRegistryFilter(search_string="no_git_suffix")
    )
    assert count == 0
    assert registry_svc.get(github_public_registry.uuid).uuid == known.uuid


@pytest.mark.federation
def test_insert_discovered_registries_created(
    github_public_registry,
    admin_user_token,
    regular_user_token,
    database,
) -> None:
    """A discovered registry is created on behalf of the first administrator"""
    service = instance_service(database, admin_user_token)
    registry_svc = registry_service(database, regular_user_token)
    known = registry_svc.get(github_public_registry.uuid)
    discovered = InstanceService.mapper_registry_to_public_registry(known)

    try:
        registry_svc.delete(known.uuid)
    except ValidationError:
        pytest.skip("public registry still has repos")

    service.insert_discovered_registries([discovered])

    count, registries = registry_svc.list(
        RepositoryRegistryFilter(search_string=discovered.url)
    )
    assert count == 1
    created = registries[0]
    assert created.is_public_repository
    assert created.creator_uuid == (
        registry_svc.user_repository.get_first_admin().uuid
    )
    assert created.sync_status == RepositoryRegistryStatus.UPDATED


@pytest.mark.federation
async def test_delete_stale_trusted(
    own_instance, unreachable_instance, admin_user_token, database
) -> None:
    """A stale instance is always polled before deletion, a live one survives"""
    service = instance_service(database, admin_user_token)

    await service.delete_stale_trusted(
        service.get_instance(own_instance.uuid),
        datetime.now(UTC) - timedelta(days=365),
    )
    assert service.get(own_instance.uuid)

    instance = unreachable_instance
    instance.create_datetime = datetime.now(UTC) - timedelta(days=365)
    instance = InstanceRepository(db=database).update(instance.uuid, instance)

    await service.delete_stale_trusted(instance, datetime.now(UTC))
    with pytest.raises(ValidationError):
        service.get(instance.uuid)


@pytest.mark.federation
def test_scan_one(own_instance, admin_user_token, database) -> None:
    service = instance_service(database, admin_user_token)
    task = service.scan_one(own_instance.uuid)

    assert task.task_type == OperationTaskType.SCAN_INSTANCE.value
    assert task.status == OperationTaskStatus.RUNNING.value

    finished = wait_task_finish(database, task)
    assert finished.status == OperationTaskStatus.SUCCESS.value
    assert finished.result.startswith(f"Scanned {own_instance.url}")
    assert finished.finish_datetime


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
def test_scan_all(own_instance, admin_user_token, database) -> None:
    service = instance_service(database, admin_user_token)
    age_tasks(database, OperationTaskType.SCAN_ALL_INSTANCES)

    task = service.scan_all()
    assert task.task_type == OperationTaskType.SCAN_ALL_INSTANCES.value
    assert task.status == OperationTaskStatus.RUNNING.value

    with pytest.raises(OperationTaskError):
        service.scan_all()
