import strawberry
from strawberry.types import Info

from app.configs.gql import get_instance_service_gql
from app.schemas.gql.inputs.instance import InstanceFilterInput
from app.schemas.gql.types.instance import (
    CurrentInstanceType,
    InstancePublicRegistryType,
    InstanceRegistriesPageType,
    InstancesPageType,
    InstanceType,
    InstanceUrlsPageType,
)


@strawberry.field()
def get_current_instance(info: Info) -> CurrentInstanceType:
    instance_service = get_instance_service_gql(info)
    return instance_service.mapper_current_to_current_instance_type(
        instance_service.get_cached_current()
    )


@strawberry.field()
def get_instances(
    filters: InstanceFilterInput, info: Info
) -> InstancesPageType:
    page = get_instance_service_gql(info).get_cached_instances(filters)
    return InstancesPageType(
        total_count=page.total_count,
        instances=[
            InstanceType(**instance.dict()) for instance in page.instances
        ],
    )


@strawberry.field()
def get_instances_urls(
    filters: InstanceFilterInput, info: Info
) -> InstanceUrlsPageType:
    page = get_instance_service_gql(info).get_cached_urls(filters)
    return InstanceUrlsPageType(
        total_count=page.total_count,
        urls=page.urls,
    )


@strawberry.field()
def get_instances_registries(
    filters: InstanceFilterInput, info: Info
) -> InstanceRegistriesPageType:
    page = get_instance_service_gql(info).get_cached_registries(filters)
    return InstanceRegistriesPageType(
        total_count=page.total_count,
        registries=[
            InstancePublicRegistryType(**registry.dict())
            for registry in page.registries
        ],
    )
