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

from app import runtime, settings
from app.configs.error_codes import ErrorCode
from app.configs.errors import (
    CustomException,
    FeatureFlagError,
    InstanceError,
    PeerError,
)
from app.domain.operation_task_model import OperationTask
from app.domain.peer_model import Peer
from app.domain.repo_model import Repo
from app.dto.enum import (
    AgentType,
    GitPlatform,
    IntegrationTestsStatus,
    NotFoundEntity,
    OperationTaskStatus,
    OperationTaskType,
    OrderByText,
    PeerCollectionStatus,
    PeerTrustStatus,
    UserRole,
)
from app.dto.integration_tests import IntegrationTestsStats
from app.repositories.instance_cache_repository import (
    InstanceCacheSnapshot,
    instance_cache,
)
from app.repositories.operation_task_repository import OperationTaskRepository
from app.repositories.peer_external_repository import (
    CollectedPeer,
    PeerExternalRepository,
)
from app.repositories.peer_repository import PeerRepository
from app.repositories.repo_repository import (
    RepoRepository,
)
from app.schemas.pydantic.instance import (
    CurrentInstanceMetricsV1,
    CurrentInstanceSchemaV1,
    CurrentInstanceStateV1,
)
from app.schemas.pydantic.operation_task import OperationTaskCreate
from app.schemas.pydantic.peer import (
    PeerCreate,
    PeerFilter,
    PeerPublicRepo,
    PeerRead,
    PeerReposPage,
    PeersPage,
    PeerUpdate,
    PeerUrlsPage,
)
from app.schemas.pydantic.repo import (
    RepoCreate,
    RepoFilter,
)
from app.services.access_service import AccessService
from app.services.background import BackgroundService
from app.services.metrics_service import MetricsService
from app.services.operation_task_service import OperationTaskService
from app.services.repo_service import RepoService
from app.services.validators import is_valid_object
from app.utils.utils import ensure_timezone_aware


class PeerService:
    MAX_COLLECTION_ERROR_LENGTH = 256

    # spread of peer polling inside the data collection window
    COLLECT_ALL_MAX_DELAY = 60 * 60 - 1
    SCAN_ALL_MAX_DELAY = 10 * 60 - 1
    SCAN_ALL_COOLDOWN = timedelta(minutes=10)

    BLOCKING_STATUS_CODES = (403, 451)
    INTEGRATION_TEST_COMMAND = "uv run pytest tests -v"

    def __init__(
        self,
        peer_repository: PeerRepository = Depends(),
        peer_external_repository: PeerExternalRepository = Depends(),
        operation_task_repository: OperationTaskRepository = Depends(),
        repo_repository: RepoRepository = Depends(),
        repo_service: RepoService = Depends(),
        metrics_service: MetricsService = Depends(),
        operation_task_service: OperationTaskService = Depends(),
        access_service: AccessService = Depends(),
    ) -> None:
        self.peer_repository = peer_repository
        self.peer_external_repository = peer_external_repository
        self.operation_task_repository = operation_task_repository
        self.repo_repository = repo_repository
        self.instance_cache_repository = instance_cache
        self.repo_service = repo_service
        self.metrics_service = metrics_service
        self.operation_task_service = operation_task_service
        self.access_service = access_service

    def create(self, data: PeerCreate) -> Peer:
        self.access_service.authorization.check_access(
            [AgentType.USER],
            [UserRole.ADMIN],
        )

        url = self.is_valid_url(data.url)
        self.peer_repository.is_unique_url(url)

        peer = self.peer_repository.create(
            Peer(
                url=url,
                trust_status=PeerTrustStatus.TRUST.value,
                create_datetime=datetime.now(UTC),
            )
        )

        self.refresh_cache()
        return peer

    def get(self, uuid: uuid_pkg.UUID) -> Peer:
        self.access_service.authorization.check_access([AgentType.USER])
        return self.get_peer(uuid)

    def list(self, filters: PeerFilter) -> tuple[int, list[Peer]]:
        self.access_service.authorization.check_access(
            [AgentType.BOT, AgentType.USER]
        )
        return self.peer_repository.list(filters)

    def update(
        self,
        uuid: uuid_pkg.UUID,
        data: PeerUpdate,
    ) -> Peer:
        self.access_service.authorization.check_access(
            [AgentType.USER],
            [UserRole.ADMIN],
        )

        peer = self.get_peer(uuid)
        self.is_valid_trust_status(data.trust_status)

        peer.trust_status = data.trust_status.value

        if data.trust_status == PeerTrustStatus.BLOCKING:
            peer.last_collection_status = PeerCollectionStatus.BLOCKING.value
            peer.last_ping = None
            peer.last_collection_error = None

        peer = self.peer_repository.update(peer.uuid, peer)

        self.refresh_cache()
        return peer

    def delete(self, uuid: uuid_pkg.UUID) -> None:
        self.access_service.authorization.check_access(
            [AgentType.USER],
            [UserRole.ADMIN],
        )

        self.peer_repository.delete(self.get_peer(uuid))

        self.refresh_cache()

    def get_cached_current(self) -> CurrentInstanceSchemaV1:
        return self.instance_cache_repository.get_current()

    def get_cached_peers(self, filters: PeerFilter) -> PeersPage:
        return self.instance_cache_repository.get_peers(filters)

    def get_cached_urls(self, filters: PeerFilter) -> PeerUrlsPage:
        return self.instance_cache_repository.get_urls(filters)

    def get_cached_repos(self, filters: PeerFilter) -> PeerReposPage:
        return self.instance_cache_repository.get_repos(filters)

    def refresh_cache(self) -> None:
        count, peers = self.peer_repository.list(PeerFilter.unlimited())
        count, repos = self.repo_repository.list(
            RepoFilter.unlimited(
                is_public_repository=True,
                order_by_create_date=None,
                order_by_last_update=None,
                order_by_repository_url=OrderByText.asc,
            )
        )

        self.instance_cache_repository.update(
            InstanceCacheSnapshot(
                current=self.get_current_instance(),
                peers=tuple(
                    self.mapper_peer_to_peer_read(peer) for peer in peers
                ),
                urls=tuple(sorted(peer.url for peer in peers)),
                repos=tuple(
                    self.mapper_repo_to_public_repo(repo)
                    for repo, _child_unit_count in repos
                ),
            )
        )

    def get_current_instance(self) -> CurrentInstanceSchemaV1:
        metrics = self.metrics_service.get_instance_metrics(
            is_api=False,
            public_only=True,
        )

        state = self.get_integration_tests_state()
        reboot = self.operation_task_repository.get_latest_by_type(
            OperationTaskType.REBOOT_INSTANCE
        )
        if reboot and reboot.status == OperationTaskStatus.SUCCESS.value:
            state.last_successful_start_datetime = reboot.finish_datetime
        return CurrentInstanceSchemaV1(
            state=state,
            metrics=CurrentInstanceMetricsV1(**metrics.dict()),
        )

    def get_integration_tests_state(self) -> CurrentInstanceStateV1:
        state = CurrentInstanceStateV1(instance_datetime=datetime.now(UTC))

        latest_task = self.operation_task_repository.get_latest_by_type(
            OperationTaskType.INTEGRATION_TESTS
        )
        if not latest_task:
            return state

        success_percentage = IntegrationTestsStats.from_result(
            latest_task.result
        ).success_percentage

        state.integration_tests_datetime = (
            latest_task.start_datetime or latest_task.create_datetime
        )
        state.integration_tests_status = self.get_integration_tests_status(
            OperationTaskStatus(latest_task.status),
            success_percentage,
        )
        state.integration_tests_success_percentage = success_percentage
        return state

    def scan_all(self) -> OperationTask:
        self.access_service.authorization.check_access(
            [AgentType.USER],
            [UserRole.ADMIN],
        )
        self.is_federation_enable()
        self.operation_task_service.is_valid_cooldown(
            OperationTaskType.SCAN_ALL_PEERS,
            self.SCAN_ALL_COOLDOWN,
        )

        task = self.operation_task_service.create(
            OperationTaskCreate(
                task_type=OperationTaskType.SCAN_ALL_PEERS,
            )
        )

        async def operation(_db):
            with BackgroundService() as services:
                summary = await services.get_peer_service().collect_all(
                    PeerService.SCAN_ALL_MAX_DELAY
                )
            with BackgroundService() as services:
                services.get_peer_service().refresh_cache()
            return summary

        self.operation_task_service.schedule(task, operation)
        return task

    def scan_one(self, uuid: uuid_pkg.UUID) -> OperationTask:
        self.access_service.authorization.check_access(
            [AgentType.USER],
            [UserRole.ADMIN],
        )
        self.is_federation_enable()
        self.get_peer(uuid)

        task = self.operation_task_service.create(
            OperationTaskCreate(
                task_type=OperationTaskType.SCAN_PEER,
            )
        )

        async def operation(_db):
            with BackgroundService() as services:
                service = services.get_peer_service()
                peer = await service.collect(uuid)
                service.refresh_cache()
                service.is_valid_collection_status(peer)
                origin = PeerService.peer_origin(peer.url)
                return f"Scanned {origin}, ping {round(peer.last_ping)} ms"

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
                service = services.get_peer_service()
                log = service.run_integration_tests()
                service.refresh_cache()
                return log

        self.operation_task_service.schedule(task, operation)
        return task

    def run_integration_tests(self) -> str:
        process = subprocess.run(
            shlex.split(self.INTEGRATION_TEST_COMMAND),
            check=False,
            capture_output=True,
            text=True,
        )

        # a raw test log is stored as is, IntegrationTestsStats parses it
        log = f"{process.stdout}{process.stderr}".strip()

        if process.returncode:
            raise InstanceError(
                log or "Integration tests failed",
                code=ErrorCode.INSTANCE_INTEGRATION_TESTS_FAILED,
            )

        return log

    async def collect_all(self, max_delay: int) -> str:
        self.is_federation_enable()

        count, peers = self.peer_repository.list(
            PeerFilter.unlimited(trust_status=[PeerTrustStatus.TRUST.value])
        )

        collected = await asyncio.gather(
            *(self.collect_with_delay(peer.uuid, max_delay) for peer in peers)
        )
        failed = [
            peer
            for peer in collected
            if peer.last_collection_status
            != PeerCollectionStatus.SUCCESS.value
        ]

        return f"Scanned {len(collected)}, failed {len(failed)}"

    @staticmethod
    async def collect_with_delay(uuid: uuid_pkg.UUID, max_delay: int) -> Peer:
        await asyncio.sleep(random.randint(0, max_delay))

        with BackgroundService() as services:
            return await services.get_peer_service().collect(uuid)

    async def collect(self, uuid: uuid_pkg.UUID) -> Peer:
        self.is_federation_enable()

        peer = self.get_peer(uuid)
        self.is_collection_available(peer)

        peer.last_attempt_datetime = datetime.now(UTC)
        peer.last_collection_error = None
        peer = self.peer_repository.update(peer.uuid, peer)

        try:
            collected = await self.peer_external_repository.collect(peer.url)
        except (
            httpx.HTTPError,
            PydanticValidationError,
            ValueError,
            PeerError,
        ) as e:
            return self.set_collection_failure(peer, e)

        peer = self.set_collection_success(peer, collected)

        self.insert_discovered_urls(collected.urls)
        self.insert_discovered_repos(collected.repos)
        return peer

    def set_collection_success(
        self,
        peer: Peer,
        collected: CollectedPeer,
    ) -> Peer:
        peer.state = collected.state.model_dump(mode="json")
        peer.last_ping = collected.last_ping
        peer.last_collection_status = PeerCollectionStatus.SUCCESS.value
        peer.last_success_datetime = datetime.now(UTC)
        peer.consecutive_success_count += 1
        peer.last_collection_error = None

        return self.peer_repository.update(peer.uuid, peer)

    def set_collection_failure(
        self,
        peer: Peer,
        error: Exception,
    ) -> Peer:
        message = str(error).strip() or error.__class__.__name__

        peer.last_collection_status = self.get_collection_status(error).value
        peer.last_ping = None
        peer.consecutive_success_count = 0
        peer.last_collection_error = message[
            : self.MAX_COLLECTION_ERROR_LENGTH
        ]

        return self.peer_repository.update(peer.uuid, peer)

    async def delete_stale_peers(self) -> None:
        self.is_federation_enable()

        threshold = datetime.now(UTC) - timedelta(
            days=runtime.get().pu_instance_retention_days
        )
        # pending is a quarantine for discovered peers, it is not deleted automatically
        count, peers = self.peer_repository.list(
            PeerFilter.unlimited(trust_status=[PeerTrustStatus.TRUST.value])
        )

        for peer in peers:
            await self.delete_stale_trusted(peer, threshold)

    async def delete_stale_trusted(
        self,
        peer: Peer,
        threshold: datetime,
    ) -> None:
        last_datetime = ensure_timezone_aware(
            peer.last_success_datetime or peer.create_datetime
        )
        if last_datetime >= threshold:
            return

        # the peer is always polled before deletion
        peer = await self.collect(peer.uuid)
        if peer.last_collection_status != PeerCollectionStatus.SUCCESS.value:
            self.peer_repository.delete(peer)

    def insert_discovered_urls(self, urls: Sequence[str]) -> None:
        count, peers = self.peer_repository.list(PeerFilter.unlimited())

        known_urls = {peer.url for peer in peers}
        known_urls.add(self.get_own_url())

        for url in sorted(set(urls)):
            try:
                valid_url = self.is_valid_url(url)
            except PeerError as e:
                logging.warning(f"Skip discovered Peer {url}: {e}")
                continue

            if valid_url in known_urls:
                continue

            known_urls.add(valid_url)
            self.peer_repository.create(
                Peer(
                    url=valid_url,
                    trust_status=PeerTrustStatus.PENDING.value,
                    create_datetime=datetime.now(UTC),
                )
            )

    def insert_discovered_repos(self, repos: Sequence[PeerPublicRepo]) -> None:
        count, known_repos = self.repo_repository.list(RepoFilter.unlimited())
        known_urls = {
            repo.repository_url for repo, _child_unit_count in known_repos
        }

        for repo in repos:
            if repo.url in known_urls:
                continue

            known_urls.add(repo.url)
            try:
                self.repo_service.create(
                    RepoCreate(
                        platform=repo.platform,
                        repository_url=repo.url,
                        is_public_repository=True,
                    ),
                    is_api=True,
                )
            except CustomException as e:
                logging.warning(f"Skip discovered Repo {repo.url}: {e}")

    def get_peer(self, uuid: uuid_pkg.UUID) -> Peer:
        peer = self.peer_repository.get(Peer(uuid=uuid))
        is_valid_object(peer, NotFoundEntity.PEER)
        return peer

    @staticmethod
    def get_own_url() -> str:
        return PeerService.is_valid_url(
            f"{settings.pu_link_prefix_and_v1}/instances/current"
        )

    @staticmethod
    def get_collection_status(error: Exception) -> PeerCollectionStatus:
        if isinstance(error, httpx.TimeoutException):
            return PeerCollectionStatus.TIMEOUT

        if (
            isinstance(error, httpx.HTTPStatusError)
            and error.response.status_code in PeerService.BLOCKING_STATUS_CODES
        ):
            return PeerCollectionStatus.BLOCKING

        return PeerCollectionStatus.ERROR

    @staticmethod
    def get_integration_tests_status(
        task_status: OperationTaskStatus,
        success_percentage: float | None,
    ) -> IntegrationTestsStatus:
        if task_status == OperationTaskStatus.RUNNING:
            return IntegrationTestsStatus.RUNNING
        if task_status == OperationTaskStatus.SUCCESS:
            return IntegrationTestsStatus.SUCCESS
        if not success_percentage:
            return IntegrationTestsStatus.ERROR

        return IntegrationTestsStatus.WARNING

    @staticmethod
    def is_federation_enable() -> None:
        if not runtime.get().pu_ff_federation_enable:
            msg = "This feature has been disabled by the instance Owner"
            raise FeatureFlagError(msg, code=ErrorCode.FEATURE_DISABLED)

    @staticmethod
    def is_collection_available(peer: Peer) -> None:
        if peer.trust_status != PeerTrustStatus.TRUST.value:
            msg = f"Collection is not available, Peer trust status is {peer.trust_status}, but it should have been {PeerTrustStatus.TRUST.value}"
            raise PeerError(msg, code=ErrorCode.PEER_COLLECTION_TRUST)

    @staticmethod
    def is_valid_collection_status(peer: Peer) -> None:
        if peer.last_collection_status != PeerCollectionStatus.SUCCESS.value:
            msg = (
                peer.last_collection_error
                or f"Collection {peer.url} is failed"
            )
            raise PeerError(msg, code=ErrorCode.PEER_COLLECTION_FAILED)

    @staticmethod
    def is_valid_trust_status(trust_status: PeerTrustStatus) -> None:
        if trust_status not in (
            PeerTrustStatus.TRUST,
            PeerTrustStatus.BLOCKING,
        ):
            msg = f"Trust status can only be {PeerTrustStatus.TRUST.value} or {PeerTrustStatus.BLOCKING.value}"
            raise PeerError(msg, code=ErrorCode.PEER_TRUST_STATUS_INVALID)

    @staticmethod
    def peer_origin(url: str) -> str:
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"

    @staticmethod
    def is_valid_url(url: str) -> str:
        parsed = urlparse(url.strip())

        if parsed.scheme not in ("http", "https"):
            msg = "Peer URL scheme must be http or https"
            raise PeerError(msg, code=ErrorCode.PEER_URL_SCHEME)
        if not parsed.hostname:
            msg = "Peer URL must include a host"
            raise PeerError(msg, code=ErrorCode.PEER_URL_HOST)
        if parsed.query or parsed.fragment:
            msg = "Peer URL must not include query or fragment"
            raise PeerError(msg, code=ErrorCode.PEER_URL_QUERY)
        if parsed.username or parsed.password:
            msg = "Peer URL must not include credentials"
            raise PeerError(msg, code=ErrorCode.PEER_URL_CREDENTIALS)

        path = parsed.path.rstrip("/")
        if not path.endswith("/instances/current"):
            msg = 'Peer URL must point to the "/instances/current" endpoint'
            raise PeerError(msg, code=ErrorCode.PEER_URL_ENDPOINT)

        netloc = parsed.hostname.lower()
        if parsed.port is not None:
            netloc = f"{netloc}:{parsed.port}"

        return urlunparse((parsed.scheme.lower(), netloc, path, "", "", ""))

    @staticmethod
    def mapper_peer_to_peer_read(peer: Peer) -> PeerRead:
        return PeerRead(**peer.dict())

    @staticmethod
    def mapper_repo_to_public_repo(
        repo: Repo,
    ) -> PeerPublicRepo:
        return PeerPublicRepo(
            url=repo.repository_url,
            platform=GitPlatform(repo.platform),
        )
