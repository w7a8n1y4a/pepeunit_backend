import asyncio
import logging
import random
import shlex
import subprocess
import uuid as uuid_pkg
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse, urlunparse

import httpx
from fastapi import Depends
from pydantic import ValidationError as PydanticValidationError

from app import settings
from app.configs.errors import (
    CustomException,
    FeatureFlagError,
    InstanceError,
)
from app.domain.instance_model import Instance
from app.domain.operation_task_model import OperationTask
from app.domain.repository_registry_model import RepositoryRegistry
from app.dto.enum import (
    AgentType,
    GitPlatform,
    InstanceCollectionStatus,
    InstanceTrustStatus,
    IntegrationTestsStatus,
    OperationTaskStatus,
    OperationTaskType,
    OrderByText,
    UserRole,
)
from app.repositories.instance_cache_repository import (
    InstanceCacheSnapshot,
    instance_cache,
)
from app.repositories.instance_external_repository import (
    CollectedInstance,
    InstanceExternalRepository,
)
from app.repositories.instance_repository import InstanceRepository
from app.repositories.operation_task_repository import OperationTaskRepository
from app.repositories.repository_registry_repository import (
    RepositoryRegistryRepository,
)
from app.schemas.gql.inputs.instance import (
    InstanceCreateInput,
    InstanceFilterInput,
    InstanceUpdateInput,
)
from app.schemas.gql.types.instance import (
    CurrentInstanceContactsType,
    CurrentInstanceMetricsType,
    CurrentInstanceSettingsType,
    CurrentInstanceStateType,
    CurrentInstanceType,
    FeatureFlagsType,
)
from app.schemas.pydantic.instance import (
    CurrentInstanceMetricsV1,
    CurrentInstanceSchemaV1,
    CurrentInstanceStateV1,
    InstanceCreate,
    InstanceFilter,
    InstancePublicRegistry,
    InstanceRead,
    InstanceRegistriesPage,
    InstancesPage,
    InstanceUpdate,
    InstanceUrlsPage,
)
from app.schemas.pydantic.operation_task import OperationTaskCreate
from app.schemas.pydantic.repository_registry import (
    RepositoryRegistryCreate,
    RepositoryRegistryFilter,
)
from app.services.access_service import AccessService
from app.services.background import BackgroundService
from app.services.metrics_service import MetricsService
from app.services.operation_task_service import OperationTaskService
from app.services.repository_registry_service import RepositoryRegistryService
from app.services.validators import is_valid_object
from app.utils.utils import ensure_timezone_aware


class InstanceService:
    MAX_COLLECTION_ERROR_LENGTH = 256

    # разброс опроса внешних инстансов внутри окна сбора данных
    COLLECT_ALL_MAX_DELAY = 60 * 60 - 1
    SCAN_ALL_MAX_DELAY = 10 * 60 - 1
    SCAN_ALL_COOLDOWN = timedelta(minutes=10)

    BLOCKING_STATUS_CODES = (403, 451)

    def __init__(
        self,
        instance_repository: InstanceRepository = Depends(),
        instance_external_repository: InstanceExternalRepository = Depends(),
        operation_task_repository: OperationTaskRepository = Depends(),
        repository_registry_repository: RepositoryRegistryRepository = Depends(),
        repository_registry_service: RepositoryRegistryService = Depends(),
        metrics_service: MetricsService = Depends(),
        operation_task_service: OperationTaskService = Depends(),
        access_service: AccessService = Depends(),
    ) -> None:
        self.instance_repository = instance_repository
        self.instance_external_repository = instance_external_repository
        self.operation_task_repository = operation_task_repository
        self.repository_registry_repository = repository_registry_repository
        self.instance_cache_repository = instance_cache
        self.repository_registry_service = repository_registry_service
        self.metrics_service = metrics_service
        self.operation_task_service = operation_task_service
        self.access_service = access_service

    def create(self, data: InstanceCreate | InstanceCreateInput) -> Instance:
        self.access_service.authorization.check_access(
            [AgentType.USER],
            [UserRole.ADMIN],
        )

        url = self.is_valid_url(data.url)
        self.instance_repository.is_unique_url(url)

        instance = self.instance_repository.create(
            Instance(
                url=url,
                trust_status=InstanceTrustStatus.TRUST.value,
                create_datetime=datetime.now(UTC),
            )
        )

        self.refresh_cache()
        return instance

    def get(self, uuid: uuid_pkg.UUID) -> Instance:
        self.access_service.authorization.check_access(
            [AgentType.BOT, AgentType.USER]
        )
        return self.get_instance(uuid)

    def list(
        self, filters: InstanceFilter | InstanceFilterInput
    ) -> tuple[int, list[Instance]]:
        self.access_service.authorization.check_access(
            [AgentType.BOT, AgentType.USER]
        )
        return self.instance_repository.list(filters)

    def update(
        self,
        uuid: uuid_pkg.UUID,
        data: InstanceUpdate | InstanceUpdateInput,
    ) -> Instance:
        self.access_service.authorization.check_access(
            [AgentType.USER],
            [UserRole.ADMIN],
        )

        instance = self.get_instance(uuid)
        self.is_valid_trust_status(data.trust_status)
        self.set_trust_status(instance, data.trust_status)

        instance = self.instance_repository.update(instance.uuid, instance)

        self.refresh_cache()
        return instance

    def delete(self, uuid: uuid_pkg.UUID) -> None:
        self.access_service.authorization.check_access(
            [AgentType.USER],
            [UserRole.ADMIN],
        )

        self.instance_repository.delete(self.get_instance(uuid))

        self.refresh_cache()

    def get_cached_current(self) -> CurrentInstanceSchemaV1:
        return self.instance_cache_repository.get_current()

    def get_cached_instances(
        self, filters: InstanceFilter | InstanceFilterInput
    ) -> InstancesPage:
        return self.instance_cache_repository.get_instances(filters)

    def get_cached_urls(
        self, filters: InstanceFilter | InstanceFilterInput
    ) -> InstanceUrlsPage:
        return self.instance_cache_repository.get_urls(filters)

    def get_cached_registries(
        self, filters: InstanceFilter | InstanceFilterInput
    ) -> InstanceRegistriesPage:
        return self.instance_cache_repository.get_registries(filters)

    def refresh_cache(self) -> None:
        count, instances = self.instance_repository.list(InstanceFilter())
        count, registries = self.repository_registry_repository.list(
            self.get_public_registry_filter()
        )

        self.instance_cache_repository.update(
            InstanceCacheSnapshot(
                current=self.get_current_instance(),
                instances=tuple(
                    self.mapper_instance_to_instance_read(instance)
                    for instance in instances
                ),
                urls=tuple(sorted(instance.url for instance in instances)),
                registries=tuple(
                    self.mapper_registry_to_public_registry(registry)
                    for registry in registries
                ),
            )
        )

    def get_current_instance(self) -> CurrentInstanceSchemaV1:
        metrics = self.metrics_service.get_instance_metrics(
            is_api=False,
            public_only=True,
        )

        return CurrentInstanceSchemaV1(
            state=self.get_integration_tests_state(),
            metrics=CurrentInstanceMetricsV1(**metrics.dict()),
        )

    def get_integration_tests_state(self) -> CurrentInstanceStateV1:
        state = CurrentInstanceStateV1(instance_datetime=datetime.now(UTC))

        latest_task = self.operation_task_repository.get_latest_by_type(
            OperationTaskType.INTEGRATION_TESTS
        )
        if not latest_task:
            return state

        # процент успешности пока бинарный, до разбора отчёта pytest
        statuses_dict = {
            OperationTaskStatus.RUNNING: (
                IntegrationTestsStatus.RUNNING,
                None,
            ),
            OperationTaskStatus.SUCCESS: (
                IntegrationTestsStatus.SUCCESS,
                100.0,
            ),
            OperationTaskStatus.ERROR: (IntegrationTestsStatus.ERROR, 0.0),
        }
        status, success_percentage = statuses_dict[
            OperationTaskStatus(latest_task.status)
        ]

        state.integration_tests_datetime = (
            latest_task.start_datetime or latest_task.create_datetime
        )
        state.integration_tests_status = status
        state.integration_tests_success_percentage = success_percentage
        return state

    def scan_all(self) -> OperationTask:
        self.access_service.authorization.check_access(
            [AgentType.USER],
            [UserRole.ADMIN],
        )
        self.is_federation_enable()
        self.operation_task_service.is_valid_cooldown(
            OperationTaskType.SCAN_ALL_INSTANCES,
            self.SCAN_ALL_COOLDOWN,
        )

        task = self.operation_task_service.create(
            OperationTaskCreate(
                task_type=OperationTaskType.SCAN_ALL_INSTANCES,
            )
        )

        async def operation(_db):
            with BackgroundService() as services:
                summary = await services.get_instance_service().collect_all(
                    InstanceService.SCAN_ALL_MAX_DELAY
                )
            with BackgroundService() as services:
                services.get_instance_service().refresh_cache()
            return summary

        self.operation_task_service.schedule(task, operation)
        return task

    def scan_one(self, uuid: uuid_pkg.UUID) -> OperationTask:
        self.access_service.authorization.check_access(
            [AgentType.USER],
            [UserRole.ADMIN],
        )
        self.is_federation_enable()
        self.get_instance(uuid)

        task = self.operation_task_service.create(
            OperationTaskCreate(
                task_type=OperationTaskType.SCAN_INSTANCE,
            )
        )

        async def operation(_db):
            with BackgroundService() as services:
                service = services.get_instance_service()
                instance = await service.collect(uuid)
                service.refresh_cache()
                service.is_valid_collection_status(instance)
                return f"Scanned {instance.url}, ping {instance.last_ping} ms"

        self.operation_task_service.schedule(task, operation)
        return task

    def start_integration_tests(self) -> OperationTask:
        self.access_service.authorization.check_access(
            [AgentType.USER],
            [UserRole.ADMIN],
        )

        task = self.operation_task_service.create(
            OperationTaskCreate(
                task_type=OperationTaskType.INTEGRATION_TESTS,
            )
        )

        def operation(_db):
            with BackgroundService() as services:
                service = services.get_instance_service()
                summary = service.run_integration_tests()
                service.refresh_cache()
                return summary

        self.operation_task_service.schedule(task, operation)
        return task

    def run_integration_tests(self) -> str:
        result = subprocess.run(
            shlex.split(settings.pu_test_integration_command),
            check=False,
            capture_output=True,
            text=True,
        )

        summary = self.get_integration_tests_summary(
            result.stdout, result.stderr
        )
        if result.returncode:
            msg = summary or (result.stderr.strip() or result.stdout.strip())
            raise InstanceError(msg)

        return summary or "Integration tests completed"

    async def collect_all(self, max_delay: int) -> str:
        self.is_federation_enable()

        count, instances = self.instance_repository.list(
            InstanceFilter(trust_status=[InstanceTrustStatus.TRUST.value])
        )

        collected = await asyncio.gather(
            *(
                self.collect_with_delay(instance.uuid, max_delay)
                for instance in instances
            )
        )
        failed = [
            instance
            for instance in collected
            if instance.last_collection_status
            != InstanceCollectionStatus.SUCCESS.value
        ]

        return f"Scanned {len(collected)}, failed {len(failed)}"

    @staticmethod
    async def collect_with_delay(
        uuid: uuid_pkg.UUID, max_delay: int
    ) -> Instance:
        await asyncio.sleep(random.randint(0, max_delay))

        with BackgroundService() as services:
            return await services.get_instance_service().collect(uuid)

    async def collect(self, uuid: uuid_pkg.UUID) -> Instance:
        self.is_federation_enable()

        instance = self.get_instance(uuid)
        self.is_collection_available(instance)

        instance.last_attempt_datetime = datetime.now(UTC)
        instance.last_collection_error = None
        instance = self.instance_repository.update(instance.uuid, instance)

        try:
            collected = await self.instance_external_repository.collect(
                instance.url
            )
        except (httpx.HTTPError, PydanticValidationError, ValueError) as e:
            return self.set_collection_failure(instance, e)

        instance = self.set_collection_success(instance, collected)

        self.insert_discovered_urls(collected.urls)
        self.insert_discovered_registries(collected.registries)
        return instance

    def set_collection_success(
        self,
        instance: Instance,
        collected: CollectedInstance,
    ) -> Instance:
        instance.state = collected.state.model_dump(mode="json")
        instance.last_ping = collected.last_ping
        instance.last_collection_status = (
            InstanceCollectionStatus.SUCCESS.value
        )
        instance.last_success_datetime = datetime.now(UTC)
        instance.consecutive_success_count += 1
        instance.last_collection_error = None

        return self.instance_repository.update(instance.uuid, instance)

    def set_collection_failure(
        self,
        instance: Instance,
        error: Exception,
    ) -> Instance:
        message = str(error).strip() or error.__class__.__name__

        instance.last_collection_status = self.get_collection_status(
            error
        ).value
        instance.last_ping = None
        instance.consecutive_success_count = 0
        instance.last_collection_error = message[
            : self.MAX_COLLECTION_ERROR_LENGTH
        ]

        return self.instance_repository.update(instance.uuid, instance)

    async def delete_stale_instances(self) -> None:
        self.is_federation_enable()

        threshold = datetime.now(UTC) - timedelta(
            days=settings.pu_instance_retention_days
        )
        count, instances = self.instance_repository.list(InstanceFilter())

        for instance in instances:
            match instance.trust_status:
                case InstanceTrustStatus.PENDING:
                    self.delete_stale_pending(instance, threshold)
                case InstanceTrustStatus.TRUST:
                    await self.delete_stale_trusted(instance, threshold)

    def delete_stale_pending(
        self,
        instance: Instance,
        threshold: datetime,
    ) -> None:
        if ensure_timezone_aware(instance.create_datetime) < threshold:
            self.instance_repository.delete(instance)

    async def delete_stale_trusted(
        self,
        instance: Instance,
        threshold: datetime,
    ) -> None:
        last_datetime = ensure_timezone_aware(
            instance.last_success_datetime or instance.create_datetime
        )
        if last_datetime >= threshold:
            return

        # перед удалением инстанс опрашивается обязательно
        instance = await self.collect(instance.uuid)
        if (
            instance.last_collection_status
            != InstanceCollectionStatus.SUCCESS.value
        ):
            self.instance_repository.delete(instance)

    def insert_discovered_urls(self, urls: Sequence[str]) -> None:
        count, instances = self.instance_repository.list(InstanceFilter())

        known_urls = {instance.url for instance in instances}
        known_urls.add(self.get_own_url())

        for url in sorted(set(urls)):
            try:
                valid_url = self.is_valid_url(url)
            except InstanceError as e:
                logging.warning(f"Skip discovered Instance {url}: {e.message}")
                continue

            if valid_url in known_urls:
                continue

            known_urls.add(valid_url)
            self.instance_repository.create(
                Instance(
                    url=valid_url,
                    trust_status=InstanceTrustStatus.PENDING.value,
                    create_datetime=datetime.now(UTC),
                )
            )

    def insert_discovered_registries(
        self, registries: Sequence[InstancePublicRegistry]
    ) -> None:
        count, known_registries = self.repository_registry_repository.list(
            RepositoryRegistryFilter()
        )
        known_urls = {item.repository_url for item in known_registries}

        for registry in registries:
            if registry.url in known_urls:
                continue

            known_urls.add(registry.url)
            try:
                self.repository_registry_service.create(
                    RepositoryRegistryCreate(
                        platform=registry.platform,
                        repository_url=registry.url,
                        is_public_repository=True,
                    ),
                    is_api=True,
                )
            except CustomException as e:
                logging.warning(
                    f"Skip discovered RepositoryRegistry {registry.url}: {e.message}"
                )

    def get_instance(self, uuid: uuid_pkg.UUID) -> Instance:
        instance = self.instance_repository.get(Instance(uuid=uuid))
        is_valid_object(instance)
        return instance

    @staticmethod
    def get_own_url() -> str:
        return InstanceService.is_valid_url(
            f"{settings.pu_link_prefix_and_v1}/instances/current"
        )

    @staticmethod
    def get_public_registry_filter() -> RepositoryRegistryFilter:
        return RepositoryRegistryFilter(
            is_public_repository=True,
            order_by_create_date=None,
            order_by_last_update=None,
            order_by_repository_url=OrderByText.asc,
        )

    @staticmethod
    def get_collection_status(error: Exception) -> InstanceCollectionStatus:
        if isinstance(error, httpx.TimeoutException):
            return InstanceCollectionStatus.TIMEOUT

        if (
            isinstance(error, httpx.HTTPStatusError)
            and error.response.status_code
            in InstanceService.BLOCKING_STATUS_CODES
        ):
            return InstanceCollectionStatus.BLOCKING

        return InstanceCollectionStatus.ERROR

    @staticmethod
    def get_integration_tests_summary(stdout: str, stderr: str) -> str | None:
        for line in reversed(f"{stdout}\n{stderr}".splitlines()):
            stripped = line.strip()
            if stripped.startswith("=") and " in " in stripped:
                return stripped.strip("=").strip().rsplit(" in ", 1)[0]
        return None

    @staticmethod
    def set_trust_status(
        instance: Instance,
        trust_status: InstanceTrustStatus,
    ) -> None:
        instance.trust_status = trust_status.value

        if trust_status == InstanceTrustStatus.BLOCKING:
            instance.last_collection_status = (
                InstanceCollectionStatus.BLOCKING.value
            )
            instance.last_ping = None
            instance.last_collection_error = None

    @staticmethod
    def is_federation_enable() -> None:
        if not settings.pu_ff_federation_enable:
            raise FeatureFlagError()

    @staticmethod
    def is_collection_available(instance: Instance) -> None:
        if instance.trust_status != InstanceTrustStatus.TRUST.value:
            msg = f"Collection is not available, Instance trust status is {instance.trust_status}, but it should have been {InstanceTrustStatus.TRUST.value}"
            raise InstanceError(msg)

    @staticmethod
    def is_valid_collection_status(instance: Instance) -> None:
        if (
            instance.last_collection_status
            != InstanceCollectionStatus.SUCCESS.value
        ):
            msg = (
                instance.last_collection_error
                or f"Collection {instance.url} is failed"
            )
            raise InstanceError(msg)

    @staticmethod
    def is_valid_trust_status(trust_status: InstanceTrustStatus) -> None:
        if trust_status not in (
            InstanceTrustStatus.TRUST,
            InstanceTrustStatus.BLOCKING,
        ):
            msg = f"Trust status can only be {InstanceTrustStatus.TRUST.value} or {InstanceTrustStatus.BLOCKING.value}"
            raise InstanceError(msg)

    @staticmethod
    def is_valid_url(url: str) -> str:
        parsed = urlparse(url.strip())

        if parsed.scheme not in ("http", "https"):
            msg = "Instance URL scheme must be http or https"
            raise InstanceError(msg)
        if not parsed.hostname:
            msg = "Instance URL must include a host"
            raise InstanceError(msg)
        if parsed.query or parsed.fragment:
            msg = "Instance URL must not include query or fragment"
            raise InstanceError(msg)
        if parsed.username or parsed.password:
            msg = "Instance URL must not include credentials"
            raise InstanceError(msg)

        path = parsed.path.rstrip("/")
        if not path.endswith("/instances/current"):
            msg = (
                'Instance URL must point to the "/instances/current" endpoint'
            )
            raise InstanceError(msg)

        netloc = parsed.hostname.lower()
        if parsed.port is not None:
            netloc = f"{netloc}:{parsed.port}"

        return urlunparse((parsed.scheme.lower(), netloc, path, "", "", ""))

    @staticmethod
    def mapper_instance_to_instance_read(instance: Instance) -> InstanceRead:
        return InstanceRead(**instance.dict())

    @staticmethod
    def mapper_registry_to_public_registry(
        registry: RepositoryRegistry,
    ) -> InstancePublicRegistry:
        return InstancePublicRegistry(
            url=registry.repository_url,
            platform=GitPlatform(registry.platform),
        )

    @staticmethod
    def mapper_current_to_current_instance_type(
        current: CurrentInstanceSchemaV1,
    ) -> CurrentInstanceType:
        current_dict = current.dict()

        return CurrentInstanceType(
            feature_flags=FeatureFlagsType(
                **current_dict.pop("feature_flags")
            ),
            settings=CurrentInstanceSettingsType(
                **current_dict.pop("settings")
            ),
            state=CurrentInstanceStateType(**current_dict.pop("state")),
            metrics=CurrentInstanceMetricsType(**current_dict.pop("metrics")),
            contacts=CurrentInstanceContactsType(
                **current_dict.pop("contacts")
            ),
            **current_dict,
        )
