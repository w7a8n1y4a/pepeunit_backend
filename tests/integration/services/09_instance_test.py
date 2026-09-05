import logging
import uuid as uuid_pkg
from datetime import UTC, datetime, timedelta

import httpx
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
from app.repositories.instance_cache_repository import instance_cache
from app.repositories.instance_external_repository import (
    InstanceExternalRepository,
)
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
from app.services.metrics_service import MetricsService
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
    count, instances = InstanceRepository(db=database).list(InstanceFilter())
    for instance in instances:
        if instance.url == url:
            return instance
    return None


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


def test_create_instance_without_admin(regular_user_token, database) -> None:
    service = instance_service(database, regular_user_token)
    with pytest.raises(NoAccessError):
        service.create(InstanceCreate(url=unique_instance_url("no_admin")))


def test_create_instance_anonymous(database) -> None:
    service = instance_service(database, None)
    with pytest.raises(NoAccessError):
        service.create(InstanceCreate(url=unique_instance_url("anon")))


def test_create_instance_duplicate_url(
    crud_instance, admin_user_token, database
) -> None:
    service = instance_service(database, admin_user_token)
    with pytest.raises(InstanceError):
        service.create(InstanceCreate(url=crud_instance.url))


@pytest.mark.parametrize(
    "url",
    [
        "ftp://pepeunit.test/pepeunit/api/v1/instances/current",
        "https:///pepeunit/api/v1/instances/current",
        "https://pepeunit.test/pepeunit/api/v1/instances/current?token=1",
        "https://pepeunit.test/pepeunit/api/v1/instances/current#state",
        "https://user:pass@pepeunit.test/pepeunit/api/v1/instances/current",
        "https://pepeunit.test/pepeunit/api/v1/metrics",
        "https://pepeunit.test",
    ],
)
def test_create_instance_bad_url(url, admin_user_token, database) -> None:
    service = instance_service(database, admin_user_token)
    with pytest.raises(InstanceError):
        service.create(InstanceCreate(url=url))


def test_is_valid_url_normalization() -> None:
    assert (
        InstanceService.is_valid_url(
            "  HTTPS://Example.COM:8080/pepeunit/api/v1/instances/current/  "
        )
        == "https://example.com:8080/pepeunit/api/v1/instances/current"
    )
    assert (
        InstanceService.is_valid_url(
            "http://PEPEUNIT.test/pepeunit/api/v1/instances/current"
        )
        == "http://pepeunit.test/pepeunit/api/v1/instances/current"
    )


def test_get_own_url() -> None:
    own_url = InstanceService.get_own_url()
    assert own_url.endswith("/instances/current")
    assert own_url == InstanceService.is_valid_url(own_url)


def test_get_instance(crud_instance, regular_user_token, database) -> None:
    service = instance_service(database, regular_user_token)
    assert service.get(crud_instance.uuid).url == crud_instance.url


def test_get_instance_not_exist(admin_user_token, database) -> None:
    service = instance_service(database, admin_user_token)
    with pytest.raises(ValidationError):
        service.get(uuid_pkg.uuid4())


def test_get_instance_anonymous(crud_instance, database) -> None:
    service = instance_service(database, None)
    with pytest.raises(NoAccessError):
        service.get(crud_instance.uuid)


def test_list_instances(crud_instance, regular_user_token, database) -> None:
    service = instance_service(database, regular_user_token)

    count, instances = service.list(InstanceFilter())
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
    """list доступен агенту Bot, поэтому работает и без токена"""
    service = instance_service(database, None)
    count, instances = service.list(InstanceFilter())
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


def test_update_instance_without_admin(
    crud_instance, regular_user_token, database
) -> None:
    service = instance_service(database, regular_user_token)
    with pytest.raises(NoAccessError):
        service.update(
            crud_instance.uuid,
            InstanceUpdate(trust_status=InstanceTrustStatus.BLOCKING),
        )


def test_update_instance_not_exist(admin_user_token, database) -> None:
    service = instance_service(database, admin_user_token)
    with pytest.raises(ValidationError):
        service.update(
            uuid_pkg.uuid4(),
            InstanceUpdate(trust_status=InstanceTrustStatus.TRUST),
        )


def test_delete_instance(admin_user_token, database) -> None:
    service = instance_service(database, admin_user_token)
    instance = service.create(
        InstanceCreate(url=unique_instance_url("to_delete"))
    )

    service.delete(instance.uuid)
    with pytest.raises(ValidationError):
        service.get(instance.uuid)


def test_delete_instance_without_admin(
    crud_instance, regular_user_token, database
) -> None:
    service = instance_service(database, regular_user_token)
    with pytest.raises(NoAccessError):
        service.delete(crud_instance.uuid)


def test_delete_instance_not_exist(admin_user_token, database) -> None:
    service = instance_service(database, admin_user_token)
    with pytest.raises(ValidationError):
        service.delete(uuid_pkg.uuid4())


def test_refresh_cache(crud_instance, admin_user_token, database) -> None:
    service = instance_service(database, admin_user_token)
    service.refresh_cache()

    cached_urls = service.get_cached_urls(InstanceFilter())
    assert crud_instance.url in cached_urls.urls
    assert cached_urls.total_count == len(
        service.list(InstanceFilter())[1]
    )
    assert cached_urls.urls == sorted(cached_urls.urls)


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


def test_get_current_instance(admin_user_token, database) -> None:
    service = instance_service(database, admin_user_token)
    MetricsService._cache.clear()

    current = service.get_current_instance()
    api_metrics = service.metrics_service.get_instance_metrics(is_api=False)

    assert current.metrics.repo_count <= api_metrics.repo_count
    assert current.metrics.unit_count <= api_metrics.unit_count
    assert current.metrics.unit_node_count <= api_metrics.unit_node_count


def test_get_cached_instances_filter(
    crud_instance, pending_instance, admin_user_token, database
) -> None:
    service = instance_service(database, admin_user_token)
    service.refresh_cache()

    page = service.get_cached_instances(
        InstanceFilter(trust_status=[InstanceTrustStatus.TRUST.value])
    )
    assert all(
        item.trust_status == InstanceTrustStatus.TRUST
        for item in page.instances
    )
    assert any(item.uuid == crud_instance.uuid for item in page.instances)
    assert all(item.uuid != pending_instance.uuid for item in page.instances)

    pending_page = service.get_cached_instances(
        InstanceFilter(trust_status=[InstanceTrustStatus.PENDING.value])
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

    page = service.get_cached_registries(InstanceFilter())
    count, public = registry_service(database, regular_user_token).list(
        RepositoryRegistryFilter(
            is_public_repository=True,
            offset=0,
            limit=settings.pu_max_pagination_size,
        )
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


def test_get_cached_urls_pagination(
    crud_instance, admin_user_token, database
) -> None:
    service = instance_service(database, admin_user_token)
    service.refresh_cache()

    full = service.get_cached_urls(InstanceFilter())
    limited = service.get_cached_urls(InstanceFilter(offset=0, limit=1))
    assert limited.total_count == full.total_count
    assert limited.urls == full.urls[:1]

    tail = service.get_cached_urls(InstanceFilter(offset=1))
    assert tail.urls == full.urls[1:]


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


def test_mapper_instance_to_instance_read(crud_instance) -> None:
    read = InstanceService.mapper_instance_to_instance_read(crud_instance)
    assert read.uuid == crud_instance.uuid
    assert read.url == crud_instance.url
    assert read.trust_status == InstanceTrustStatus.TRUST


def test_mapper_registry_to_public_registry(
    github_public_registry, regular_user_token, database
) -> None:
    registry = registry_service(database, regular_user_token).get(
        github_public_registry.uuid
    )
    public = InstanceService.mapper_registry_to_public_registry(registry)
    assert public.url == registry.repository_url
    assert public.platform == GitPlatform(registry.platform)


def test_mapper_current_to_current_instance_type(
    admin_user_token, database
) -> None:
    service = instance_service(database, admin_user_token)
    service.refresh_cache()

    current = service.get_cached_current()
    current_type = InstanceService.mapper_current_to_current_instance_type(
        current
    )
    assert current_type.schema_version == current.schema_version
    assert current_type.metrics.user_count == current.metrics.user_count
    assert (
        current_type.state.instance_datetime
        == current.state.instance_datetime
    )
    assert current_type.contacts.email == current.contacts.email
    assert current_type.settings.pu_max_pagination_size == (
        current.settings.pu_max_pagination_size
    )


def test_is_valid_trust_status() -> None:
    InstanceService.is_valid_trust_status(InstanceTrustStatus.TRUST)
    InstanceService.is_valid_trust_status(InstanceTrustStatus.BLOCKING)
    with pytest.raises(InstanceError):
        InstanceService.is_valid_trust_status(InstanceTrustStatus.PENDING)


def test_is_collection_available(crud_instance, pending_instance) -> None:
    InstanceService.is_collection_available(crud_instance)
    with pytest.raises(InstanceError):
        InstanceService.is_collection_available(pending_instance)


def test_is_valid_collection_status() -> None:
    success = Instance(
        url="https://pepeunit.test/instances/current",
        last_collection_status=InstanceCollectionStatus.SUCCESS.value,
    )
    InstanceService.is_valid_collection_status(success)

    failed = Instance(
        url="https://pepeunit.test/instances/current",
        last_collection_status=InstanceCollectionStatus.ERROR.value,
        last_collection_error="connection refused",
    )
    with pytest.raises(InstanceError) as error:
        InstanceService.is_valid_collection_status(failed)
    assert "connection refused" in error.value.message

    failed.last_collection_error = None
    with pytest.raises(InstanceError) as error:
        InstanceService.is_valid_collection_status(failed)
    assert "is failed" in error.value.message


def test_get_collection_status() -> None:
    request = httpx.Request("GET", "https://pepeunit.test")
    assert (
        InstanceService.get_collection_status(
            httpx.ConnectTimeout("timeout", request=request)
        )
        == InstanceCollectionStatus.TIMEOUT
    )
    for status_code in InstanceService.BLOCKING_STATUS_CODES:
        assert (
            InstanceService.get_collection_status(
                httpx.HTTPStatusError(
                    "blocked",
                    request=request,
                    response=httpx.Response(status_code, request=request),
                )
            )
            == InstanceCollectionStatus.BLOCKING
        )
    assert (
        InstanceService.get_collection_status(
            httpx.HTTPStatusError(
                "server error",
                request=request,
                response=httpx.Response(500, request=request),
            )
        )
        == InstanceCollectionStatus.ERROR
    )
    assert (
        InstanceService.get_collection_status(ValueError("too big"))
        == InstanceCollectionStatus.ERROR
    )


def test_get_integration_tests_summary() -> None:
    assert (
        InstanceService.get_integration_tests_summary(
            "collecting ...\n"
            "===== 1 failed, 12 passed, 3 warnings in 51.20s =====\n",
            "",
        )
        == "1 failed, 12 passed, 3 warnings"
    )
    assert (
        InstanceService.get_integration_tests_summary(
            "", "==== 13 passed in 10.00s ===="
        )
        == "13 passed"
    )
    assert InstanceService.get_integration_tests_summary("no summary", "") is None


def test_get_integration_tests_percentage() -> None:
    assert InstanceService.get_integration_tests_percentage(None) is None
    assert InstanceService.get_integration_tests_percentage("") is None
    assert (
        InstanceService.get_integration_tests_percentage("no counts here")
        is None
    )
    assert (
        InstanceService.get_integration_tests_percentage("13 passed") == 100.0
    )
    assert (
        InstanceService.get_integration_tests_percentage(
            "1 failed, 3 passed, 2 warnings"
        )
        == 75.0
    )
    assert (
        InstanceService.get_integration_tests_percentage(
            "1 failed, 12 passed, 3 warnings"
        )
        == 92.31
    )
    assert (
        InstanceService.get_integration_tests_percentage(
            "2 errors, 1 xpassed, 1 passed"
        )
        == 50.0
    )


def test_get_integration_tests_status() -> None:
    assert (
        InstanceService.get_integration_tests_status(
            OperationTaskStatus.RUNNING, None
        )
        == IntegrationTestsStatus.RUNNING
    )
    assert (
        InstanceService.get_integration_tests_status(
            OperationTaskStatus.SUCCESS, 100.0
        )
        == IntegrationTestsStatus.SUCCESS
    )
    assert (
        InstanceService.get_integration_tests_status(
            OperationTaskStatus.ERROR, 92.31
        )
        == IntegrationTestsStatus.WARNING
    )
    assert (
        InstanceService.get_integration_tests_status(
            OperationTaskStatus.ERROR, None
        )
        == IntegrationTestsStatus.ERROR
    )


@pytest.mark.parametrize(
    ("status", "result", "expected_status", "expected_percentage"),
    [
        (OperationTaskStatus.RUNNING, None, IntegrationTestsStatus.RUNNING, None),
        (
            OperationTaskStatus.SUCCESS,
            "13 passed",
            IntegrationTestsStatus.SUCCESS,
            100.0,
        ),
        (
            OperationTaskStatus.ERROR,
            "1 failed, 12 passed",
            IntegrationTestsStatus.WARNING,
            92.31,
        ),
        (OperationTaskStatus.ERROR, None, IntegrationTestsStatus.ERROR, None),
    ],
)
def test_get_integration_tests_state(
    status,
    result,
    expected_status,
    expected_percentage,
    admin_user,
    admin_user_token,
    database,
) -> None:
    service = instance_service(database, admin_user_token)
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


def test_start_integration_tests_without_admin(
    regular_user_token, database
) -> None:
    service = instance_service(database, regular_user_token)
    with pytest.raises(NoAccessError):
        service.start_integration_tests()


def test_start_integration_tests_anonymous(database) -> None:
    service = instance_service(database, None)
    with pytest.raises(NoAccessError):
        service.start_integration_tests()


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
async def test_collect_not_exist(admin_user_token, database) -> None:
    service = instance_service(database, admin_user_token)
    with pytest.raises(ValidationError):
        await service.collect(uuid_pkg.uuid4())


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
async def test_external_repository_collect(own_instance) -> None:
    collected = await InstanceExternalRepository().collect(own_instance.url)

    assert collected.state.schema_version == "v1"
    assert collected.last_ping > 0
    assert isinstance(collected.urls, list)
    assert all(
        item.platform in list(GitPlatform) for item in collected.registries
    )


@pytest.mark.federation
async def test_collect_with_delay(own_instance) -> None:
    instance = await InstanceService.collect_with_delay(own_instance.uuid, 0)
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
    # unreachable_instance входит в выборку Trust и обязан попасть в failed
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

    count, instances = service.list(InstanceFilter())
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
async def test_delete_stale_trusted_removes_unreachable(
    unreachable_instance, admin_user_token, database
) -> None:
    service = instance_service(database, admin_user_token)
    repository = InstanceRepository(db=database)

    instance = unreachable_instance
    instance.create_datetime = datetime.now(UTC) - timedelta(days=365)
    instance = repository.update(instance.uuid, instance)

    await service.delete_stale_trusted(instance, datetime.now(UTC))

    with pytest.raises(ValidationError):
        service.get(instance.uuid)


@pytest.mark.federation
async def test_delete_stale_trusted_keeps_alive(
    own_instance, admin_user_token, database
) -> None:
    service = instance_service(database, admin_user_token)

    await service.delete_stale_trusted(
        service.get_instance(own_instance.uuid),
        datetime.now(UTC),
    )
    assert service.get(own_instance.uuid)

    await service.delete_stale_trusted(
        service.get_instance(own_instance.uuid),
        datetime.now(UTC) - timedelta(days=365),
    )
    assert service.get(own_instance.uuid)


@pytest.mark.federation
async def test_delete_stale_instances(
    own_instance, crud_instance, admin_user_token, database
) -> None:
    service = instance_service(database, admin_user_token)
    original_retention = settings.pu_instance_retention_days

    settings.pu_instance_retention_days = 100_000
    try:
        await service.delete_stale_instances()
    finally:
        settings.pu_instance_retention_days = original_retention

    assert service.get(own_instance.uuid)
    assert service.get(crud_instance.uuid)


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
def test_scan_one_not_exist(admin_user_token, database) -> None:
    service = instance_service(database, admin_user_token)
    with pytest.raises(ValidationError):
        service.scan_one(uuid_pkg.uuid4())


@pytest.mark.federation
def test_scan_one_without_admin(
    own_instance, regular_user_token, database
) -> None:
    service = instance_service(database, regular_user_token)
    with pytest.raises(NoAccessError):
        service.scan_one(own_instance.uuid)


@pytest.mark.federation
def test_scan_all(own_instance, admin_user_token, database) -> None:
    service = instance_service(database, admin_user_token)
    age_tasks(database, OperationTaskType.SCAN_ALL_INSTANCES)

    task = service.scan_all()
    assert task.task_type == OperationTaskType.SCAN_ALL_INSTANCES.value
    assert task.status == OperationTaskStatus.RUNNING.value

    with pytest.raises(OperationTaskError):
        service.scan_all()


@pytest.mark.federation
def test_scan_all_without_admin(regular_user_token, database) -> None:
    service = instance_service(database, regular_user_token)
    with pytest.raises(NoAccessError):
        service.scan_all()


@pytest.mark.federation
def test_insert_discovered_registries_created(
    github_public_registry,
    admin_user_token,
    regular_user_token,
    database,
) -> None:
    """Найденный реестр заводится от имени первого администратора"""
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
