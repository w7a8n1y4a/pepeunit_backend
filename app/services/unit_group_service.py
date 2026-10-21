import datetime
import uuid as uuid_pkg

from fastapi import Depends

from app import runtime
from app.configs.error_codes import ErrorCode
from app.configs.errors import UnitGroupError
from app.domain.unit_group_model import UnitGroup
from app.domain.unit_group_unit_model import UnitGroupUnit
from app.domain.unit_model import Unit
from app.dto.enum import AgentType, NotFoundEntity, OwnershipType
from app.repositories.icon_repository import IconRepository
from app.repositories.unit_group_repository import UnitGroupRepository
from app.repositories.unit_group_unit_repository import UnitGroupUnitRepository
from app.repositories.unit_repository import UnitRepository
from app.schemas.pydantic.unit_group import (
    UnitGroupCreate,
    UnitGroupFilter,
    UnitGroupMemberFilter,
    UnitGroupUpdate,
)
from app.services.access_service import AccessService
from app.services.icon_image import IconImage
from app.services.utils import (
    merge_two_dict_first_priority,
    remove_none_value_dict,
)
from app.services.validators import is_valid_object


class UnitGroupService:
    def __init__(
        self,
        unit_group_repository: UnitGroupRepository = Depends(),
        unit_group_unit_repository: UnitGroupUnitRepository = Depends(),
        unit_repository: UnitRepository = Depends(),
        icon_repository: IconRepository = Depends(),
        access_service: AccessService = Depends(),
    ) -> None:
        self.unit_group_repository = unit_group_repository
        self.unit_group_unit_repository = unit_group_unit_repository
        self.unit_repository = unit_repository
        self.icon_repository = icon_repository
        self.access_service = access_service

    def create(self, data: UnitGroupCreate) -> UnitGroup:
        self.access_service.authorization.check_access([AgentType.USER])
        self.unit_group_repository.is_valid_name(data.name)
        self.is_valid_group_count()

        group = UnitGroup(
            name=data.name,
            creator_uuid=self.access_service.current_agent.uuid,
            create_datetime=datetime.datetime.now(datetime.UTC),
        )
        group.icon_uuid = self.icon_repository.stage(
            IconImage.generate(str(group.uuid))
        ).uuid
        return self.unit_group_repository.create(group)

    def get(self, uuid: uuid_pkg.UUID) -> UnitGroup:
        self.access_service.authorization.check_access([AgentType.USER])

        group = self.unit_group_repository.get(UnitGroup(uuid=uuid))
        is_valid_object(group, NotFoundEntity.UNIT_GROUP)

        self.access_service.authorization.check_ownership(
            group, [OwnershipType.CREATOR]
        )
        return group

    def update(self, uuid: uuid_pkg.UUID, data: UnitGroupUpdate) -> UnitGroup:
        self.access_service.authorization.check_access([AgentType.USER])

        group = self.unit_group_repository.get(UnitGroup(uuid=uuid))
        is_valid_object(group, NotFoundEntity.UNIT_GROUP)

        self.access_service.authorization.check_ownership(
            group, [OwnershipType.CREATOR]
        )

        if data.name:
            self.unit_group_repository.is_valid_name(data.name)

        updated = UnitGroup(
            **merge_two_dict_first_priority(
                remove_none_value_dict(data.dict()), group.dict()
            )
        )
        return self.unit_group_repository.update(uuid, updated)

    def delete(self, uuid: uuid_pkg.UUID) -> None:
        self.access_service.authorization.check_access([AgentType.USER])

        group = self.unit_group_repository.get(UnitGroup(uuid=uuid))
        is_valid_object(group, NotFoundEntity.UNIT_GROUP)

        self.access_service.authorization.check_ownership(
            group, [OwnershipType.CREATOR]
        )

        self.unit_group_repository.delete(group)

    def list(self, filters: UnitGroupFilter) -> tuple[int, list[UnitGroup]]:
        self.access_service.authorization.check_access([AgentType.USER])
        return self.unit_group_repository.list(
            filters, creator_uuid=self.access_service.current_agent.uuid
        )

    def list_units(
        self, uuid: uuid_pkg.UUID, filters: UnitGroupMemberFilter
    ) -> tuple[int, list[Unit]]:
        self.access_service.authorization.check_access([AgentType.USER])

        group = self.unit_group_repository.get(UnitGroup(uuid=uuid))
        is_valid_object(group, NotFoundEntity.UNIT_GROUP)

        self.access_service.authorization.check_ownership(
            group, [OwnershipType.CREATOR]
        )
        return self.unit_repository.list_for_group(group.uuid, filters)

    def link_unit(self, uuid: uuid_pkg.UUID, unit_uuid: uuid_pkg.UUID) -> None:
        self.access_service.authorization.check_access([AgentType.USER])

        group = self.unit_group_repository.get(UnitGroup(uuid=uuid))
        is_valid_object(group, NotFoundEntity.UNIT_GROUP)

        self.access_service.authorization.check_ownership(
            group, [OwnershipType.CREATOR]
        )

        unit = self.unit_repository.get(Unit(uuid=unit_uuid))
        is_valid_object(unit, NotFoundEntity.UNIT)
        self.access_service.authorization.check_visibility(unit)

        if self.unit_group_unit_repository.get_link(group.uuid, unit.uuid):
            msg = "Unit is already in this group"
            raise UnitGroupError(
                msg, code=ErrorCode.UNIT_GROUP_UNIT_ALREADY_IN_GROUP
            )

        self.unit_group_unit_repository.create(
            UnitGroupUnit(unit_group_uuid=group.uuid, unit_uuid=unit.uuid)
        )

    def unlink_unit(
        self, uuid: uuid_pkg.UUID, unit_uuid: uuid_pkg.UUID
    ) -> None:
        self.access_service.authorization.check_access([AgentType.USER])

        group = self.unit_group_repository.get(UnitGroup(uuid=uuid))
        is_valid_object(group, NotFoundEntity.UNIT_GROUP)

        self.access_service.authorization.check_ownership(
            group, [OwnershipType.CREATOR]
        )

        link = self.unit_group_unit_repository.get_link(group.uuid, unit_uuid)
        is_valid_object(link, NotFoundEntity.UNIT_GROUP_UNIT)
        self.unit_group_unit_repository.delete(link)

    def is_valid_group_count(self) -> None:
        limit = int(runtime.get().pu_instance_user_max_group)
        count = self.unit_group_repository.count_by_creator(
            self.access_service.current_agent.uuid
        )
        if count >= limit:
            msg = f"Group count is {count}, the limit is {limit}"
            raise UnitGroupError(msg, code=ErrorCode.UNIT_GROUP_COUNT_LIMIT)
