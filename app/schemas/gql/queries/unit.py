import strawberry
from strawberry.types import Info

from app.configs.gql import get_unit_service
from app.schemas.gql.inputs.unit import UnitFilterInput
from app.schemas.gql.types.unit import UnitType


@strawberry.field()
def get_unit(uuid: str, info: Info) -> UnitType:
    unit_service = get_unit_service(info)
    return UnitType(**unit_service.get(uuid).dict())


@strawberry.field()
def get_units(filters: UnitFilterInput, info: Info) -> list[UnitType]:
    unit_service = get_unit_service(info)
    return [UnitType(**unit.dict()) for unit in unit_service.list(filters)]
