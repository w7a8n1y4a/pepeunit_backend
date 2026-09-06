from dataclasses import dataclass

from fastapi import HTTPException

from app import settings


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
