from typing import Union

from fastapi import params
from sqlalchemy import desc, asc
from sqlmodel import or_

from app.domain.permission_model import Permission
from app.domain.repo_model import Repo
from app.domain.unit_model import Unit
from app.domain.unit_node_model import UnitNode
from app.domain.user_model import User
from app.repositories.enum import OrderByDate


def apply_ilike_search_string(query, filters, fields: list):
    if filters.dict()['search_string'] and len(filters.dict()['search_string']) > 0:
        for word in filters.search_string.split():
            query = query.where(or_(*[field.ilike(f'%{word}%') for field in fields]))

    return query


def apply_enums(query, filters, fields: dict):
    for filter_name, field in fields.items():
        if filter_name in filters.dict() and filters.dict()[filter_name]:
            value = filters.dict()[filter_name]

            if isinstance(value, params.Query):
                value = value.default

            query = query.where(field.in_(value))
    return query


def apply_offset_and_limit(query, filters):
    return query.offset(filters.offset if filters.offset else None).limit(filters.limit if filters.limit else None)


def apply_orders_by(query, filters, fields: dict):
    for filter_name, value in fields.items():
        if filter_name in filters.dict() and filters.dict()[filter_name]:
            query = query.order_by(
                asc(fields[filter_name])
                if filters.dict()[filter_name] == OrderByDate.asc
                else desc(fields[filter_name])
            )
    return query


def make_permission(
    agent: Union[User, Unit, UnitNode],
    resource: Union[Repo, Unit, UnitNode]
) -> Permission:
    return Permission(
        agent_uuid=agent.uuid,
        agent_type=agent.__class__.__name__,
        resource_uuid=resource.uuid,
        resource_type=resource.__class__.__name__
    )
