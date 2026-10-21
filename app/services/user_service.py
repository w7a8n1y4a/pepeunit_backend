import datetime
import uuid as uuid_pkg

from fastapi import Depends

from app import runtime
from app.configs.error_codes import ErrorCode
from app.configs.errors import FeatureFlagError, UserError
from app.configs.redis import get_redis_session
from app.domain.notification_settings_model import NotificationSettings
from app.domain.user_model import User
from app.dto.agent.abc import AgentGrafana, AgentUser
from app.dto.enum import AgentType, NotFoundEntity, UserRole, UserStatus
from app.repositories.data_pipe_repository import DataPipeRepository
from app.repositories.grafana_repository import GrafanaRepository
from app.repositories.icon_repository import IconRepository
from app.repositories.notification_settings_repository import (
    NotificationSettingsRepository,
)
from app.repositories.user_repository import UserRepository
from app.schemas.pydantic.user import (
    AuthChallengeCreate,
    AuthTokenCreate,
    UserCreate,
    UserFilter,
    UserUpdate,
)
from app.services.access_service import AccessService
from app.services.auth.challenge import ChallengeService
from app.services.icon_image import IconImage
from app.services.validators import is_valid_object
from app.utils.utils import generate_random_string


class UserService:
    def __init__(
        self,
        user_repository: UserRepository = Depends(),
        icon_repository: IconRepository = Depends(),
        data_pipe_repository: DataPipeRepository = Depends(),
        access_service: AccessService = Depends(),
        notification_settings_repository: (
            NotificationSettingsRepository
        ) = Depends(),
    ) -> None:
        self.user_repository = user_repository
        self.icon_repository = icon_repository
        self.challenge_service = ChallengeService(user_repository)
        self.data_pipe_repository = GrafanaRepository(data_pipe_repository)
        self.access_service = access_service
        self.notification_settings_repository = (
            notification_settings_repository
        )

    def create(self, data: UserCreate) -> User:
        self.access_service.authorization.check_access([AgentType.BOT])
        public_key, hash_public_key = (
            self.challenge_service.canonical_public_key(data.public_key)
        )
        self._check_user_count()

        user = User(
            public_key=public_key,
            hash_public_key=hash_public_key,
            role=UserRole.USER,
            status=UserStatus.ACTIVE,
            create_datetime=datetime.datetime.now(datetime.UTC),
        )
        user.icon_uuid = self.icon_repository.stage(
            IconImage.generate(public_key)
        ).uuid

        user = self.user_repository.create(user)
        self.notification_settings_repository.create(
            NotificationSettings.for_user(user.uuid)
        )
        self.create_org_if_not_exists(user.uuid)

        return self.user_repository.get(user)

    def get(self, uuid: uuid_pkg.UUID) -> User:
        self.access_service.authorization.check_access(
            [AgentType.USER, AgentType.GRAFANA]
        )
        user = self.user_repository.get(User(uuid=uuid))
        is_valid_object(user, NotFoundEntity.USER)
        return user

    async def create_challenge(self, data: AuthChallengeCreate) -> str:
        self.access_service.authorization.check_access([AgentType.BOT])
        digest = self.challenge_service.normalize_public_key_hash(
            data.hash_public_key
        )
        user = self.user_repository.get_user_by_hash_public_key(digest)
        is_valid_object(user, NotFoundEntity.USER)
        return await self.challenge_service.issue(user)

    async def get_token(self, data: AuthTokenCreate) -> str:
        self.access_service.authorization.check_access([AgentType.BOT])
        user = await self.challenge_service.accept(
            data.challenge, data.signature
        )
        return AgentUser(**user.dict()).generate_agent_token()

    def get_grafana_token(self) -> str:
        self.access_service.authorization.check_access([AgentType.USER])

        current_user = self.access_service.current_agent
        return AgentGrafana(
            uuid=current_user.uuid,
            name=current_user.login or str(current_user.uuid),
        ).generate_agent_token()

    def update(self, data: UserUpdate) -> User:
        self.access_service.authorization.check_access([AgentType.USER])
        user = self.user_repository.get(
            User(uuid=self.access_service.current_agent.uuid)
        )
        is_valid_object(user, NotFoundEntity.USER)
        if not data.login:
            return user

        self.user_repository.is_valid_login(data.login)
        user.login = data.login
        return self.user_repository.update(user.uuid, user)

    async def generate_verification_link(self) -> str:
        if not runtime.get().pu_ff_telegram_bot_enable:
            msg = "This feature has been disabled by the instance Owner"
            raise FeatureFlagError(msg, code=ErrorCode.FEATURE_DISABLED)

        self.access_service.authorization.check_access([AgentType.USER])
        redis = await anext(get_redis_session())

        code = generate_random_string(8)
        await redis.set(
            code, str(self.access_service.current_agent.uuid), ex=60
        )

        return f"{runtime.get().pu_telegram_bot_link}?start={code}"

    async def verification(
        self, telegram_chat_id: str, verification_code: str
    ):
        redis = await anext(get_redis_session())
        uuid = await redis.get(verification_code)
        is_valid_object(uuid, NotFoundEntity.VERIFICATION_CODE)
        await redis.delete(verification_code)

        user = self.user_repository.get(User(uuid=uuid))
        is_valid_object(user, NotFoundEntity.USER)
        self.user_repository.is_valid_telegram_chat_id(
            telegram_chat_id, user.uuid
        )

        user.telegram_chat_id = telegram_chat_id
        return self.user_repository.update(user.uuid, user)

    def grant_admin(self, uuid: uuid_pkg.UUID) -> User:
        self.access_service.authorization.check_access(
            [AgentType.USER], [UserRole.OWNER]
        )
        user = self.user_repository.get(User(uuid=uuid))
        is_valid_object(user, NotFoundEntity.USER)
        user.role = UserRole.ADMIN
        return self.user_repository.update(user.uuid, user)

    def revoke_admin(self, uuid: uuid_pkg.UUID) -> User:
        self.access_service.authorization.check_access(
            [AgentType.USER], [UserRole.OWNER]
        )
        user = self.user_repository.get(User(uuid=uuid))
        is_valid_object(user, NotFoundEntity.USER)
        user.role = UserRole.USER
        return self.user_repository.update(user.uuid, user)

    def block(self, uuid: uuid_pkg.UUID) -> None:
        self.access_service.authorization.check_access(
            [AgentType.USER], [UserRole.ADMIN]
        )
        user = self.user_repository.get(User(uuid=uuid))
        is_valid_object(user, NotFoundEntity.USER)
        user.status = UserStatus.BLOCKED
        self.user_repository.update(user.uuid, user)

    def unblock(self, uuid: uuid_pkg.UUID) -> None:
        self.access_service.authorization.check_access(
            [AgentType.USER], [UserRole.ADMIN]
        )

        user = self.user_repository.get(User(uuid=uuid))
        is_valid_object(user, NotFoundEntity.USER)

        user.status = UserStatus.ACTIVE
        self.user_repository.update(user.uuid, user)

    def list(self, filters: UserFilter) -> tuple[int, list[User]]:
        self.access_service.authorization.check_access([AgentType.USER])
        return self.user_repository.list(filters)

    def _check_user_count(self) -> None:
        limit = int(runtime.get().pu_instance_user_max_count)
        count = self.user_repository.get_all_count()
        if count < limit:
            return
        msg = f"User count is {count}, the limit is {limit}"
        raise UserError(msg, code=ErrorCode.USER_COUNT_LIMIT)

    def create_org_if_not_exists(self, uuid: uuid_pkg.UUID) -> None:
        if not runtime.get().pu_ff_grafana_integration_enable:
            return

        user = self.user_repository.get(User(uuid=uuid))
        is_valid_object(user, NotFoundEntity.USER)

        if user.grafana_org_id:
            grafana_name = self.data_pipe_repository.get_org_name(
                user.grafana_org_id
            )
            if grafana_name and grafana_name != str(user.grafana_org_name):
                try:
                    user.grafana_org_name = uuid_pkg.UUID(grafana_name)
                except ValueError:
                    return
                self.user_repository.update(user.uuid, user)
            return

        org_id = self.data_pipe_repository.create_org_if_not_exists(user)
        user.grafana_org_id = str(org_id)
        self.user_repository.update(user.uuid, user)
