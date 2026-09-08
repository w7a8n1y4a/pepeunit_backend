import uuid as uuid_pkg

import strawberry
from strawberry.types import Info

from app.configs.gql import get_instance_service_gql
from app.schemas.gql.inputs.instance import (
    InstanceCreateInput,
    InstanceUpdateInput,
)
from app.schemas.gql.types.instance import InstanceType
from app.schemas.gql.types.shared import NoneType


@strawberry.mutation()
def create_instance(
    info: Info,
    instance: InstanceCreateInput,
) -> InstanceType:
    created = get_instance_service_gql(info).create(instance)
    return InstanceType(**created.dict())


@strawberry.mutation()
def update_instance(
    info: Info,
    uuid: uuid_pkg.UUID,
    instance: InstanceUpdateInput,
) -> InstanceType:
    updated = get_instance_service_gql(info).update(uuid, instance)
    return InstanceType(**updated.dict())


@strawberry.mutation()
def delete_instance(info: Info, uuid: uuid_pkg.UUID) -> NoneType:
    get_instance_service_gql(info).delete(uuid)
    return NoneType()


@strawberry.mutation()
def scan_instances(info: Info) -> NoneType:
    get_instance_service_gql(info).scan_all()
    return NoneType()


@strawberry.mutation()
def scan_instance(info: Info, uuid: uuid_pkg.UUID) -> NoneType:
    get_instance_service_gql(info).scan_one(uuid)
    return NoneType()


@strawberry.mutation()
def run_integration_tests(info: Info) -> NoneType:
    get_instance_service_gql(info).start_integration_tests()
    return NoneType()
