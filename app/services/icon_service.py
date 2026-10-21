import uuid as uuid_pkg

from fastapi import Depends

from app.configs.error_codes import ErrorCode
from app.configs.errors import NoAccessError, ValidationError
from app.domain.icon_model import Icon
from app.domain.instance_settings_model import InstanceSettings
from app.domain.unit_group_model import UnitGroup
from app.domain.unit_model import Unit
from app.domain.user_model import User
from app.dto.enum import (
    AgentType,
    IconEntityType,
    NotFoundEntity,
    OwnershipType,
    UserRole,
)
from app.repositories.icon_repository import IconRepository
from app.repositories.instance_settings_repository import (
    InstanceSettingsRepository,
)
from app.repositories.unit_group_repository import UnitGroupRepository
from app.repositories.unit_repository import UnitRepository
from app.repositories.user_repository import UserRepository
from app.services.access_service import AccessService
from app.services.icon_image import IconImage
from app.services.validators import is_valid_object


class IconService:
    def __init__(
        self,
        icon_repository: IconRepository = Depends(),
        user_repository: UserRepository = Depends(),
        unit_repository: UnitRepository = Depends(),
        unit_group_repository: UnitGroupRepository = Depends(),
        instance_settings_repository: InstanceSettingsRepository = Depends(),
        access_service: AccessService = Depends(),
    ) -> None:
        self.icon_repository = icon_repository
        self.user_repository = user_repository
        self.unit_repository = unit_repository
        self.unit_group_repository = unit_group_repository
        self.instance_settings_repository = instance_settings_repository
        self.access_service = access_service

    def get(self, uuid: uuid_pkg.UUID) -> Icon:
        icon = self.icon_repository.get(Icon(uuid=uuid))
        is_valid_object(icon, NotFoundEntity.ICON)
        return icon

    def upload(
        self,
        entity_uuid: uuid_pkg.UUID,
        entity_type: IconEntityType,
        image: bytes,
    ) -> Icon:
        IconImage.validate(image)
        entity = self._entity(entity_uuid, entity_type)
        return self.icon_repository.replace(entity, image)

    def _entity(self, entity_uuid: uuid_pkg.UUID, entity_type: IconEntityType):
        match entity_type:
            case IconEntityType.USER:
                return self._user(entity_uuid)
            case IconEntityType.UNIT:
                return self._unit(entity_uuid)
            case IconEntityType.UNIT_GROUP:
                return self._unit_group(entity_uuid)
            case IconEntityType.INSTANCE:
                return self._instance(entity_uuid)
            case _:
                msg = "Image target is not supported"
                raise ValidationError(
                    msg, code=ErrorCode.ICON_TARGET_UNSUPPORTED
                )

    def _user(self, entity_uuid: uuid_pkg.UUID) -> User:
        self.access_service.authorization.check_access([AgentType.USER])
        if self.access_service.current_agent.uuid != entity_uuid:
            msg = "Only the user can change this icon"
            raise NoAccessError(msg, code=ErrorCode.ACCESS_ICON_OWNER_ONLY)
        user = self.user_repository.get(User(uuid=entity_uuid))
        is_valid_object(user, NotFoundEntity.USER)
        return user

    def _unit(self, entity_uuid: uuid_pkg.UUID) -> Unit:
        self.access_service.authorization.check_access([AgentType.USER])
        unit = self.unit_repository.get(Unit(uuid=entity_uuid))
        is_valid_object(unit, NotFoundEntity.UNIT)
        self.access_service.authorization.check_ownership(
            unit, [OwnershipType.CREATOR]
        )
        return unit

    def _unit_group(self, entity_uuid: uuid_pkg.UUID) -> UnitGroup:
        self.access_service.authorization.check_access([AgentType.USER])
        group = self.unit_group_repository.get(UnitGroup(uuid=entity_uuid))
        is_valid_object(group, NotFoundEntity.UNIT_GROUP)
        self.access_service.authorization.check_ownership(
            group, [OwnershipType.CREATOR]
        )
        return group

    def _instance(self, entity_uuid: uuid_pkg.UUID) -> InstanceSettings:
        self.access_service.authorization.check_access(
            [AgentType.USER], [UserRole.OWNER]
        )
        if entity_uuid != InstanceSettings.ROW_UUID:
            is_valid_object(None, NotFoundEntity.INSTANCE_SETTINGS)
        row = self.instance_settings_repository.get(
            InstanceSettings(uuid=InstanceSettings.ROW_UUID)
        )
        is_valid_object(row, NotFoundEntity.INSTANCE_SETTINGS)
        return row
