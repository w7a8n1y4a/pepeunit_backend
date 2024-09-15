from fastapi import params
from sqlalchemy import asc, desc
from sqlmodel import or_

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
