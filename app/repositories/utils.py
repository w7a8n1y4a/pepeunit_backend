from typing import Any

from fastapi import params
from sqlalchemy import asc, desc
from sqlmodel import and_, or_

from app.dto.enum import OrderByDate, VisibilityLevel


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


def apply_restriction(query, filters, entity_type: any, restriction: list):

    visibility_levels = (
        filters.visibility_level.default
        if isinstance(filters.visibility_level, params.Query)
        else filters.visibility_level
    )

    if restriction and VisibilityLevel.PRIVATE in visibility_levels:
        query = query.filter(
            or_(
                entity_type.visibility_level.in_([VisibilityLevel.PUBLIC, VisibilityLevel.INTERNAL]),
                and_(entity_type.visibility_level == VisibilityLevel.PRIVATE, entity_type.uuid.in_(restriction)),
            )
        )

    return query


def apply_offset_and_limit(query, filters) -> tuple[int, Any]:
    return query.count(), query.offset(filters.offset if filters.offset else None).limit(
        filters.limit if filters.limit else None
    )


def apply_orders_by(query, filters, fields: dict):
    for filter_name, value in fields.items():
        if filter_name in filters.dict() and filters.dict()[filter_name]:
            query = query.order_by(
                asc(fields[filter_name])
                if filters.dict()[filter_name] == OrderByDate.asc
                else desc(fields[filter_name])
            )
    return query
