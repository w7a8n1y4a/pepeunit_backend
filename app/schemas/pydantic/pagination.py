from dataclasses import dataclass
from typing import Self

from fastapi import HTTPException

from app import settings

# Marker for filters that must not be paginated. It is only reachable through
# BasePaginationRestMixin.unlimited, __post_init__ rejects it for any API input.
NO_PAGINATION = -1


@dataclass(kw_only=True)
class BasePaginationRestMixin:
    offset: int = 0
    limit: int = settings.pu_max_pagination_size

    def __post_init__(self):
        if self.offset < 0:
            raise HTTPException(status_code=422, detail="offset must be >= 0")

        if self.limit < 0:
            raise HTTPException(status_code=422, detail="limit must be >= 0")
        if self.limit > settings.pu_max_pagination_size:
            raise HTTPException(
                status_code=422,
                detail=(f"limit must be <= {settings.pu_max_pagination_size}"),
            )

    @classmethod
    def unlimited(cls, **kwargs) -> Self:
        """Whole result set, for backend internals where a page would be a bug"""
        filters = cls(**kwargs)
        filters.offset = 0
        filters.limit = NO_PAGINATION
        return filters
