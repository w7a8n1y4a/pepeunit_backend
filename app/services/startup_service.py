import asyncio
import logging
from collections.abc import Callable
from contextlib import suppress
from datetime import UTC, datetime, timedelta

import aiogram.exceptions
import httpx
from aiogram import Bot, Dispatcher
from clickhouse_migrations.clickhouse_cluster import ClickhouseCluster
from fastapi import FastAPI
from fastapi_mqtt import FastMQTT

from app import settings
from app.configs.emqx import ControlEmqx
from app.configs.redis import get_redis_session
from app.configs.utils import acquire_file_lock, wait_for_file_unlock
from app.dto.agent.abc import AgentBackend
from app.dto.enum import FileLock, GlobalPrefixTopic
from app.repositories.grafana_repository import GrafanaRepository
from app.repositories.instance_cache_repository import InstanceCacheRepository
from app.schemas.mqtt.manager import mqtt_manager
from app.services.background import BackgroundService
from app.services.instance_service import InstanceService
from app.utils.utils import logo_to_console


class StartupService:
    def __init__(
        self,
        app: FastAPI,
        mqtt: FastMQTT,
        bot: Bot | None = None,
        dp: Dispatcher | None = None,
    ) -> None:
        self.app = app
        self.mqtt = mqtt
        self.bot = bot
        self.dp = dp
        self._init_lock = None
        self._redis = None
        self._bot_tasks: list[asyncio.Task] = []
        self._mqtt_task: asyncio.Task | None = None
        self._instance_tasks: list[asyncio.Task] = []
        self._singleton_tasks: list[asyncio.Task] = []

    async def start(self) -> None:
        self._redis = await anext(get_redis_session())
        self._init_lock = acquire_file_lock(FileLock.INIT)
        if self._init_lock:
            await self._start_once()
        wait_for_file_unlock(FileLock.MQTT_RUN)
        await self._start_every_worker()
        self._start_singleton()

    async def stop(self) -> None:
        await self._cancel_tasks(self._bot_tasks, "Telegram bot")
        if self._mqtt_task and not self._mqtt_task.done():
            logging.info("Stopping MQTT task...")
            self._mqtt_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._mqtt_task
        await self._cancel_tasks(self._instance_tasks, "instance")
        await self._cancel_tasks(self._singleton_tasks, "singleton")
        if self._init_lock:
            self._init_lock.close()
        await self.mqtt.mqtt_shutdown()

    async def _start_once(self) -> None:
        mqtt_run_lock = acquire_file_lock(FileLock.MQTT_RUN)
        await self._init_clickhouse()
        await ControlEmqx().init()
        if settings.pu_ff_grafana_integration_enable:
            asyncio.get_running_loop().run_in_executor(
                None,
                GrafanaRepository.configure_admin_dashboard_permissions,
            )
        await self._setup_backend_acl()
        self._start_telegram_bot()
        self._sync_local_repository()
        mqtt_run_lock.close()
        logo_to_console()

    async def _start_every_worker(self) -> None:
        cache = self.app.state.instance_cache
        self._mqtt_task = asyncio.create_task(
            self._run_mqtt_client(), name="run_mqtt_client"
        )
        with BackgroundService() as services:
            services.get_instance_service().refresh_cache(cache)
        self._instance_tasks.append(
            asyncio.create_task(
                self._run_instance_cache_loop(cache),
                name="run_instance_cache",
            )
        )

    def _start_singleton(self) -> None:
        if settings.pu_ff_federation_enable:
            self._singleton_tasks.append(
                asyncio.create_task(
                    self._run_instance_collection_loop(
                        self.app.state.instance_cache
                    ),
                    name="run_instance_collection",
                )
            )
        self._singleton_tasks.append(
            asyncio.create_task(
                self._run_locked_hourly(
                    FileLock.UPDATE_REPOS,
                    0,
                    self._update_repositories,
                ),
                name="automatic_update_repositories",
            )
        )
        self._singleton_tasks.append(
            asyncio.create_task(
                self._run_locked_hourly(
                    FileLock.UPDATE_REGISTRY,
                    30,
                    self._update_registry,
                ),
                name="automatic_update_registry",
            )
        )

    async def _init_clickhouse(self) -> None:
        clickhouse_cluster = ClickhouseCluster(
            settings.pu_clickhouse_connection.host,
            settings.pu_clickhouse_connection.user,
            settings.pu_clickhouse_connection.password,
        )
        clickhouse_cluster.migrate(
            settings.pu_clickhouse_connection.database,
            "./clickhouse/migrations",
            cluster_name=None,
            create_db_if_no_exists=True,
            multi_statement=True,
        )

    async def _setup_backend_acl(self) -> None:
        backend_topics = (
            f"{settings.pu_domain}/+/+/+{GlobalPrefixTopic.BACKEND_SUB_PREFIX.value}",
        )

        async def hset_emqx_auth_keys(topic: str) -> None:
            token = AgentBackend(
                name=settings.pu_domain
            ).generate_agent_token()
            await self._redis.hset(f"mqtt_acl:{token}", topic, "all")

        await asyncio.gather(
            *[hset_emqx_auth_keys(topic) for topic in backend_topics]
        )

    def _sync_local_repository(self) -> None:
        with BackgroundService(
            AgentBackend(name=settings.pu_domain).generate_agent_token()
        ) as services:
            services.get_repository_registry_service().sync_local_repository_storage()

    def _start_telegram_bot(self) -> None:
        if (
            not settings.pu_ff_telegram_bot_enable
            or not self.bot
            or not self.dp
        ):
            return
        if settings.pu_telegram_bot_mode == "pooling":
            self._bot_tasks.append(
                asyncio.create_task(
                    self._run_polling_bot(), name="run_polling_bot"
                )
            )
        elif settings.pu_telegram_bot_mode == "webhook":
            self._bot_tasks.append(
                asyncio.create_task(
                    self._run_webhook_bot(), name="run_webhook_bot"
                )
            )

    async def _run_polling_bot(self) -> None:
        logging.info("Delete webhook before run polling")
        await self.bot.delete_webhook()
        logging.info("Run polling")
        try:
            await self.dp.start_polling(
                self.bot, allowed_updates=self.dp.resolve_used_update_types()
            )
        except asyncio.CancelledError:
            logging.info("Polling bot task cancelled")
            raise
        except Exception as e:
            logging.error(f"Error in polling bot: {e}")
            raise

    async def _run_webhook_bot(self) -> None:
        webhook_url = f"{settings.pu_link_prefix_and_v1}/bot"

        if settings.pu_telegram_del_old_webhook:
            logging.info("Delete webhook before set new webhook")
            await self.bot.delete_webhook()

        inc = 0
        while True:
            result = httpx.post(
                f"{settings.pu_link_prefix_and_v1}/bot",
                headers={"Content-Type": "application/json"},
            )
            if result.status_code == 422:
                break
            await asyncio.sleep(2)
            if inc > 10:
                msg = "Webhook route not valid"
                raise Exception(msg)
            inc += 1

        try:
            await self.bot.set_webhook(
                url=webhook_url,
                drop_pending_updates=True,
                allowed_updates=self.dp.resolve_used_update_types(),
            )
            logging.info("Success set TG bot webhook url")
        except aiogram.exceptions.TelegramBadRequest:
            logging.info("Error set TG bot webhook url")

        try:
            while True:
                await asyncio.sleep(60)
                try:
                    webhook_info = await self.bot.get_webhook_info()
                    if not webhook_info.url:
                        logging.warning("Webhook was removed, re-setting...")
                        await self.bot.set_webhook(
                            url=webhook_url,
                            drop_pending_updates=False,
                            allowed_updates=self.dp.resolve_used_update_types(),
                        )
                except Exception as e:
                    logging.warning(f"Webhook check failed: {e}")
        except asyncio.CancelledError:
            logging.info("Webhook bot task cancelled")
            raise

    async def _run_mqtt_client(self) -> None:
        logging.info(
            f"Connect to mqtt server: {settings.pu_mqtt_host}:{settings.pu_mqtt_port}"
        )
        mqtt_manager.attach_loop(asyncio.get_running_loop())
        await self.mqtt.mqtt_startup()
        token = AgentBackend(name=settings.pu_domain).generate_agent_token()
        access = await self._redis.hgetall(token)
        for k, v in access.items():
            logging.info(f"Redis set {k} access {v}")

    async def _run_instance_cache_loop(
        self, cache: InstanceCacheRepository
    ) -> None:
        while True:
            await asyncio.sleep(60)
            with BackgroundService() as services:
                services.get_instance_service().refresh_cache(cache)

    async def _run_instance_collection_loop(
        self, cache: InstanceCacheRepository
    ) -> None:
        while True:
            await asyncio.sleep(self._seconds_until(minute=0))
            lock = acquire_file_lock(FileLock.COLLECT_INSTANCES)
            if lock is None:
                continue
            try:
                with BackgroundService() as services:
                    instance_uuids = (
                        services.get_instance_service().get_pollable_uuids()
                    )
                await InstanceService.collect_instances(instance_uuids, 3599)
                with BackgroundService() as services:
                    service = services.get_instance_service()
                    await service.delete_stale_instances()
                    service.refresh_cache(cache)
            finally:
                lock.close()

    async def _run_locked_hourly(
        self, lock: FileLock, minute: int, work: Callable[[], None]
    ) -> None:
        while True:
            await asyncio.sleep(self._seconds_until(minute=minute))
            lock_fd = acquire_file_lock(lock)
            await asyncio.sleep(10)
            if lock_fd:
                logging.info("Run update with lock")
                try:
                    work()
                finally:
                    lock_fd.close()
            else:
                logging.info("Skip update without lock")

    def _update_repositories(self) -> None:
        with BackgroundService() as services:
            services.get_repo_service().bulk_update_units_firmware()

    def _update_registry(self) -> None:
        with BackgroundService() as services:
            services.get_repository_registry_service().sync_local_repository_storage(
                True
            )

    def _seconds_until(self, *, minute: int) -> float:
        now = datetime.now(UTC)
        next_run = now.replace(minute=minute, second=0, microsecond=0)
        if next_run <= now:
            next_run += timedelta(hours=1)
        return (next_run - now).total_seconds()

    async def _cancel_tasks(
        self, tasks: list[asyncio.Task], label: str
    ) -> None:
        if tasks:
            logging.info(f"Stopping {label} tasks...")
        for task in tasks:
            if not task.done():
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
        tasks.clear()
