import uuid as uuid_pkg

import strawberry
from strawberry.types import Info

from app.configs.gql import get_instance_cache_gql, get_instance_service_gql
from app.schemas.gql.inputs.instance import (
    InstanceCreateInput,
    InstanceUpdateInput,
)
from app.schemas.gql.types.instance import InstanceType
from app.schemas.gql.types.shared import NoneType


@strawberry.mutation()
async def create_instance(
    info: Info,
    instance: InstanceCreateInput,
) -> InstanceType:
    service = get_instance_service_gql(info)
    created = await service.create(instance)
    service.refresh_cache(get_instance_cache_gql(info))
    return InstanceType(**created.dict())


@strawberry.mutation()
async def update_instance(
    info: Info,
    uuid: uuid_pkg.UUID,
    instance: InstanceUpdateInput,
) -> InstanceType:
    service = get_instance_service_gql(info)
    updated = await service.update(uuid, instance)
    service.refresh_cache(get_instance_cache_gql(info))
    return InstanceType(**updated.dict())


@strawberry.mutation()
def delete_instance(info: Info, uuid: uuid_pkg.UUID) -> NoneType:
    service = get_instance_service_gql(info)
    service.delete(uuid)
    service.refresh_cache(get_instance_cache_gql(info))
    return NoneType()


@strawberry.mutation()
def scan_instances(info: Info) -> NoneType:
    get_instance_service_gql(info).scan_all(get_instance_cache_gql(info))
    return NoneType()


@strawberry.mutation()
def scan_instance(info: Info, uuid: uuid_pkg.UUID) -> NoneType:
    get_instance_service_gql(info).scan_one(uuid, get_instance_cache_gql(info))
    return NoneType()


@strawberry.mutation()
def run_integration_tests(info: Info) -> NoneType:
    get_instance_service_gql(info).start_integration_tests(
        get_instance_cache_gql(info)
    )
    return NoneType()
