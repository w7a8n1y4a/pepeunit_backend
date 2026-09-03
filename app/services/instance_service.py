import asyncio
import logging
import random
import shlex
import subprocess
import uuid as uuid_pkg
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse, urlunparse

import httpx
from fastapi import Depends
from fastapi.encoders import jsonable_encoder
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
    InstanceCacheRepository,
    InstanceCacheSnapshot,
)
from app.repositories.instance_external_repository import (
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
    CurrentInstanceFeatureFlagsType,
    CurrentInstanceMetricsType,
    CurrentInstanceSettingsType,
    CurrentInstanceStateType,
    CurrentInstanceType,
)
from app.schemas.pydantic.instance import (
    CurrentInstanceContactsV1,
    CurrentInstanceFeatureFlags,
    CurrentInstanceMetricsV1,
    CurrentInstanceSchemaV1,
    CurrentInstanceSettingsV1,
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
    _MAX_COLLECTION_ERROR_LENGTH = 256
    _SCAN_ALL_MAX_DELAY_SECONDS = 10 * 60 - 1

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
        self.repository_registry_service = repository_registry_service
        self.metrics_service = metrics_service
        self.operation_task_service = operation_task_service
        self.access_service = access_service

    async def create(
        self,
        data: InstanceCreate | InstanceCreateInput,
    ) -> Instance:
        self.access_service.authorization.check_access(
            [AgentType.USER],
            [UserRole.ADMIN],
        )
        url = self.is_valid_url(data.url)

        return self.instance_repository.create(
            Instance(
                url=url,
                trust_status=InstanceTrustStatus.TRUST.value,
                create_datetime=datetime.now(UTC),
            )
        )

    def get(self, instance_uuid: uuid_pkg.UUID) -> Instance:
        self.access_service.authorization.check_access([AgentType.USER])
        return self._get_instance(instance_uuid)

    def list_urls(
        self,
        filters: InstanceFilter,
    ) -> tuple[int, list[str]]:
        return self.instance_repository.list_urls(filters)

    def list_registries(
        self,
        filters: InstanceFilter,
    ) -> tuple[int, list[InstancePublicRegistry]]:
        count, registries = self.repository_registry_repository.list(
            self._public_registry_filter(
                offset=filters.offset,
                limit=filters.limit,
            )
        )
        return count, [
            self._public_registry(registry) for registry in registries
        ]

    async def update(
        self,
        instance_uuid: uuid_pkg.UUID,
        data: InstanceUpdate | InstanceUpdateInput,
    ) -> Instance:
        self.access_service.authorization.check_access(
            [AgentType.USER],
            [UserRole.ADMIN],
        )
        instance = self._get_instance(instance_uuid)
        self.is_valid_trust_status(data.trust_status)
        self._set_trust_status(instance, data.trust_status)

        return self.instance_repository.update(instance.uuid, instance)

    def delete(self, instance_uuid: uuid_pkg.UUID) -> None:
        self.access_service.authorization.check_access(
            [AgentType.USER],
            [UserRole.ADMIN],
        )
        self.instance_repository.delete(self._get_instance(instance_uuid))

    def get_cached_current(
        self,
        cache: InstanceCacheRepository,
    ) -> CurrentInstanceSchemaV1:
        return cache.get_current()

    def get_cached_instances(
        self,
        cache: InstanceCacheRepository,
        filters: InstanceFilter | InstanceFilterInput,
    ) -> InstancesPage:
        return cache.get_instances(filters)

    def get_cached_urls(
        self,
        cache: InstanceCacheRepository,
        filters: InstanceFilter | InstanceFilterInput,
    ) -> InstanceUrlsPage:
        return cache.get_urls(filters)

    def get_cached_registries(
        self,
        cache: InstanceCacheRepository,
        filters: InstanceFilter | InstanceFilterInput,
    ) -> InstanceRegistriesPage:
        return cache.get_registries(filters)

    def refresh_cache(self, cache: InstanceCacheRepository) -> None:
        instances = self.instance_repository.get_all_sorted()
        cache.update(
            InstanceCacheSnapshot(
                current=self.build_current_instance_response(),
                instances=tuple(
                    self.mapper_instance_to_instance_read(instance)
                    for instance in instances
                ),
                urls=tuple(self.instance_repository.get_all_urls()),
                registries=tuple(
                    self._public_registry(registry)
                    for registry in self.repository_registry_repository.list(
                        self._public_registry_filter()
                    )[1]
                ),
            )
        )

    def build_current_instance_response(self) -> CurrentInstanceSchemaV1:
        latest_tests = self.operation_task_repository.get_latest_by_type(
            OperationTaskType.INTEGRATION_TESTS,
        )
        tests_datetime = None
        tests_status = None
        tests_success_percentage = None
        if latest_tests is not None:
            tests_datetime = (
                latest_tests.start_datetime or latest_tests.create_datetime
            )
            if latest_tests.status == OperationTaskStatus.RUNNING.value:
                tests_status = IntegrationTestsStatus.RUNNING.value
            elif latest_tests.status == OperationTaskStatus.SUCCESS.value:
                tests_status = IntegrationTestsStatus.SUCCESS.value
                tests_success_percentage = 100.0
            elif latest_tests.status == OperationTaskStatus.ERROR.value:
                tests_status = IntegrationTestsStatus.ERROR.value
                tests_success_percentage = 0.0

        metrics = self.metrics_service.get_instance_metrics(
            is_api=False,
            public_only=True,
        )
        return CurrentInstanceSchemaV1(
            name=settings.project_name,
            version=settings.version,
            description=settings.description,
            license=settings.license,
            swagger=f"{settings.pu_link_prefix}/docs",
            graphql=f"{settings.pu_link_prefix}/graphql",
            grafana=f"{settings.pu_link}/grafana/",
            telegram_bot=settings.pu_telegram_bot_link,
            feature_flags=CurrentInstanceFeatureFlags(
                pu_ff_telegram_bot_enable=settings.pu_ff_telegram_bot_enable,
                pu_ff_grafana_integration_enable=(
                    settings.pu_ff_grafana_integration_enable
                ),
                pu_ff_datapipe_enable=settings.pu_ff_datapipe_enable,
                pu_ff_datapipe_default_last_value_enable=(
                    settings.pu_ff_datapipe_default_last_value_enable
                ),
                pu_ff_prometheus_enable=settings.pu_ff_prometheus_enable,
                pu_ff_federation_enable=settings.pu_ff_federation_enable,
            ),
            settings=CurrentInstanceSettingsV1(
                pu_state_send_interval=settings.pu_state_send_interval,
                pu_max_external_repo_size=settings.pu_max_external_repo_size,
                pu_max_cipher_length=settings.pu_max_cipher_length,
                pu_unit_log_expiration=settings.pu_unit_log_expiration,
                pu_max_pagination_size=settings.pu_max_pagination_size,
                pu_mqtt_max_clients=settings.pu_mqtt_max_clients,
                pu_mqtt_max_client_connection_rate=(
                    settings.pu_mqtt_max_client_connection_rate
                ),
                pu_mqtt_max_client_id_len=settings.pu_mqtt_max_client_id_len,
                pu_mqtt_client_max_messages_rate=(
                    settings.pu_mqtt_client_max_messages_rate
                ),
                pu_mqtt_client_max_bytes_rate=(
                    settings.pu_mqtt_client_max_bytes_rate
                ),
                pu_mqtt_max_payload_size=settings.pu_mqtt_max_payload_size,
                pu_mqtt_max_qos=settings.pu_mqtt_max_qos,
                pu_mqtt_max_topic_levels=settings.pu_mqtt_max_topic_levels,
                pu_mqtt_max_len_message_queue=(
                    settings.pu_mqtt_max_len_message_queue
                ),
                pu_mqtt_max_topic_alias=settings.pu_mqtt_max_topic_alias,
            ),
            state=CurrentInstanceStateV1(
                instance_datetime=datetime.now(UTC),
                integration_tests_datetime=tests_datetime,
                integration_tests_status=tests_status,
                integration_tests_success_percentage=(
                    tests_success_percentage
                ),
            ),
            metrics=CurrentInstanceMetricsV1(**metrics.dict()),
            contacts=CurrentInstanceContactsV1(
                email=settings.pu_admin_email,
                telegram=settings.pu_admin_tg,
            ),
        )

    def scan_all(
        self,
        cache: InstanceCacheRepository,
    ) -> OperationTask:
        self.access_service.authorization.check_access(
            [AgentType.USER],
            [UserRole.ADMIN],
        )
        cooldown_error = self.operation_task_service.ensure_cooldown(
            OperationTaskType.SCAN_ALL_INSTANCES,
            timedelta(minutes=10),
        )
        task = self.operation_task_service.create(
            OperationTaskCreate(
                task_type=OperationTaskType.SCAN_ALL_INSTANCES,
            )
        )
        if cooldown_error:

            def operation(_db):
                raise RuntimeError(cooldown_error)

            self.operation_task_service.schedule(task.uuid, operation)
            return task

        instance_uuids = self.get_pollable_uuids()

        async def operation(_db):
            summary = await InstanceService.collect_instances(
                instance_uuids,
                self._SCAN_ALL_MAX_DELAY_SECONDS,
                fail_on_collection_error=True,
            )
            with BackgroundService() as services:
                services.get_instance_service().refresh_cache(cache)
            return summary

        self.operation_task_service.schedule(task.uuid, operation)
        return task

    def scan_one(
        self,
        instance_uuid: uuid_pkg.UUID,
        cache: InstanceCacheRepository,
    ) -> OperationTask:
        self.access_service.authorization.check_access(
            [AgentType.USER],
            [UserRole.ADMIN],
        )
        self._get_instance(instance_uuid)
        task = self.operation_task_service.create(
            OperationTaskCreate(
                task_type=OperationTaskType.SCAN_INSTANCE,
            )
        )

        async def operation(_db):
            with BackgroundService() as services:
                service = services.get_instance_service()
                result = await service.collect(instance_uuid)
                service.refresh_cache(cache)
            if (
                result.last_collection_status
                != InstanceCollectionStatus.SUCCESS.value
            ):
                msg = result.last_collection_error or "Instance scan failed"
                raise RuntimeError(msg)
            return f"Scanned 1 instance, ping {result.last_ping} ms"

        self.operation_task_service.schedule(task.uuid, operation)
        return task

    def start_integration_tests(
        self,
        cache: InstanceCacheRepository,
    ) -> OperationTask:
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
                service.refresh_cache(cache)
            return summary

        self.operation_task_service.schedule(task.uuid, operation)
        return task

    def run_integration_tests(self) -> str:
        result = subprocess.run(
            shlex.split(settings.pu_test_integration_command),
            check=False,
            capture_output=True,
            text=True,
        )
        summary = self._integration_tests_summary(
            result.stdout,
            result.stderr,
        )
        if result.returncode:
            raise RuntimeError(
                summary
                or (result.stderr.strip() or result.stdout.strip())[-4096:]
            )
        return summary or "Integration tests completed"

    @staticmethod
    def _integration_tests_summary(stdout: str, stderr: str) -> str | None:
        for line in reversed(f"{stdout}\n{stderr}".splitlines()):
            stripped = line.strip()
            if stripped.startswith("=") and " in " in stripped:
                return stripped.strip("=").strip().rsplit(" in ", 1)[0]
        return None

    @staticmethod
    async def collect_instances(
        instance_uuids: list[uuid_pkg.UUID],
        max_delay: int,
        fail_on_collection_error: bool = False,
    ) -> str:
        if not settings.pu_ff_federation_enable:
            raise FeatureFlagError()

        async def collect_one(instance_uuid: uuid_pkg.UUID):
            await asyncio.sleep(random.randint(0, max_delay))
            with BackgroundService() as services:
                return await services.get_instance_service().collect(
                    instance_uuid
                )

        results = await asyncio.gather(
            *(collect_one(instance_uuid) for instance_uuid in instance_uuids)
        )
        failed = [
            result
            for result in results
            if result.last_collection_status
            != InstanceCollectionStatus.SUCCESS.value
        ]
        summary = f"Scanned {len(results)}, failed {len(failed)}"
        if fail_on_collection_error and failed:
            raise RuntimeError(summary)
        return summary

    async def collect(self, instance_uuid: uuid_pkg.UUID) -> Instance:
        if not settings.pu_ff_federation_enable:
            raise FeatureFlagError()

        instance = self._get_instance(instance_uuid)
        if instance.trust_status != InstanceTrustStatus.TRUST.value:
            msg = "Only trusted instances can be polled"
            raise InstanceError(msg)

        instance.last_attempt_datetime = datetime.now(UTC)
        instance.last_collection_error = None
        instance = self.instance_repository.update(instance.uuid, instance)
        try:
            collected = await self.instance_external_repository.collect(
                instance.url
            )
            instance.state = collected.state.model_dump(mode="json")
            instance.last_ping = collected.last_ping
            instance.last_collection_status = (
                InstanceCollectionStatus.SUCCESS.value
            )
            instance.last_success_datetime = datetime.now(UTC)
            instance.consecutive_success_count += 1
            instance.last_collection_error = None
            instance = self.instance_repository.update(instance.uuid, instance)
        except httpx.TimeoutException as exc:
            return self._record_collection_failure(
                instance,
                InstanceCollectionStatus.TIMEOUT,
                exc,
            )
        except httpx.HTTPStatusError as exc:
            collection_status = (
                InstanceCollectionStatus.BLOCKING
                if exc.response.status_code in {403, 451}
                else InstanceCollectionStatus.ERROR
            )
            return self._record_collection_failure(
                instance,
                collection_status,
                exc,
            )
        except (httpx.HTTPError, PydanticValidationError, ValueError) as exc:
            return self._record_collection_failure(
                instance,
                InstanceCollectionStatus.ERROR,
                exc,
            )

        self._insert_discovered_urls(collected.urls.urls)
        self._insert_discovered_registries(collected.registries.registries)
        return instance

    def get_pollable_uuids(self) -> list[uuid_pkg.UUID]:
        return [
            instance.uuid
            for instance in self.instance_repository.list_trusted()
        ]

    async def delete_stale_instances(self) -> None:
        threshold = datetime.now(UTC) - timedelta(
            days=settings.pu_instance_retention_days
        )
        for instance in self.instance_repository.list_trusted():
            reference_datetime = ensure_timezone_aware(
                instance.last_success_datetime or instance.create_datetime
            )
            if reference_datetime >= threshold:
                continue
            result = await self.collect(instance.uuid)
            if (
                result.last_collection_status
                != InstanceCollectionStatus.SUCCESS.value
            ):
                self.instance_repository.delete(instance)

        for instance in self.instance_repository.list_pending():
            if ensure_timezone_aware(instance.create_datetime) >= threshold:
                continue
            self.instance_repository.delete(instance)

    def _insert_discovered_urls(
        self,
        urls: list[str],
    ) -> None:
        own_url = self.is_valid_url(
            f"{settings.pu_link_prefix_and_v1}/instances/current"
        )
        discovered_urls = set()
        for url in urls:
            try:
                discovered_urls.add(self.is_valid_url(url))
            except InstanceError:
                logging.exception(
                    "Skip invalid discovered instance URL: %s",
                    url,
                )

        for url in sorted(discovered_urls - {own_url}):
            if self.instance_repository.get_by_url(url) is not None:
                continue
            self.instance_repository.create(
                Instance(
                    url=url,
                    trust_status=InstanceTrustStatus.PENDING.value,
                    create_datetime=datetime.now(UTC),
                )
            )

    def _insert_discovered_registries(
        self,
        registries: list[InstancePublicRegistry],
    ) -> None:
        for registry in registries:
            if (
                self.repository_registry_repository.get_by_url(
                    RepositoryRegistry(repository_url=registry.url)
                )
                is not None
            ):
                continue
            try:
                self.repository_registry_service.create(
                    RepositoryRegistryCreate(
                        platform=registry.platform,
                        repository_url=registry.url,
                        is_public_repository=True,
                    ),
                    is_api=True,
                )
            except CustomException:
                logging.exception(
                    "Failed to create discovered public registry: %s",
                    registry.url,
                )

    def list(
        self,
        filters: InstanceFilter,
    ) -> tuple[int, list[Instance]]:
        return self.instance_repository.list(filters)

    @staticmethod
    def _public_registry(
        registry: RepositoryRegistry,
    ) -> InstancePublicRegistry:
        return InstancePublicRegistry(
            url=registry.repository_url,
            platform=GitPlatform(registry.platform),
        )

    def _record_collection_failure(
        self,
        instance: Instance,
        collection_status: InstanceCollectionStatus,
        exc: Exception,
    ) -> Instance:
        error = str(exc).strip() or exc.__class__.__name__
        instance.last_collection_status = collection_status.value
        instance.last_ping = None
        instance.consecutive_success_count = 0
        instance.last_collection_error = error[
            : self._MAX_COLLECTION_ERROR_LENGTH
        ]
        return self.instance_repository.update(instance.uuid, instance)

    def _get_instance(self, instance_uuid: uuid_pkg.UUID) -> Instance:
        instance = self.instance_repository.get(Instance(uuid=instance_uuid))
        is_valid_object(instance)
        return instance

    def mapper_instance_to_instance_read(
        self,
        instance: Instance,
    ) -> InstanceRead:
        return InstanceRead(**jsonable_encoder(instance.dict()))

    @staticmethod
    def mapper_current_to_current_type(
        current: CurrentInstanceSchemaV1,
    ) -> CurrentInstanceType:
        current_dict = current.dict()
        return CurrentInstanceType(
            feature_flags=CurrentInstanceFeatureFlagsType(
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

    @staticmethod
    def _public_registry_filter(
        offset: int | None = None,
        limit: int | None = None,
    ) -> RepositoryRegistryFilter:
        return RepositoryRegistryFilter(
            is_public_repository=True,
            offset=offset,
            limit=limit,
            order_by_create_date=None,
            order_by_last_update=None,
            order_by_repository_url=OrderByText.asc,
        )

    @staticmethod
    def is_valid_url(url: str) -> str:
        raw = url.strip()
        if not raw:
            msg = "Instance URL must not be empty"
            raise InstanceError(msg)

        parsed = urlparse(raw)
        if parsed.scheme not in {"http", "https"}:
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

        hostname = parsed.hostname.lower()
        netloc = hostname
        if parsed.port is not None:
            netloc = f"{hostname}:{parsed.port}"

        return urlunparse((parsed.scheme.lower(), netloc, path, "", "", ""))

    @staticmethod
    def is_valid_trust_status(trust_status: InstanceTrustStatus) -> None:
        if trust_status not in (
            InstanceTrustStatus.TRUST,
            InstanceTrustStatus.BLOCKING,
        ):
            msg = "Trust status can only be Trust or Blocking"
            raise InstanceError(msg)

    @staticmethod
    def _set_trust_status(
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
