from dataclasses import dataclass

from fastapi import HTTPException
from pydantic import BaseModel, Field

from app import settings


@dataclass(kw_only=True)
class BasePaginationRestMixin:
    offset: int | None = None
    limit: int | None = None

    def __post_init__(self):
        if self.offset is not None and self.offset < 0:
            raise HTTPException(status_code=422, detail="offset must be >= 0")

        if self.limit is None:
            return

        if self.limit < 0:
            raise HTTPException(status_code=422, detail="limit must be >= 0")

        if self.limit > settings.backend_max_pagination_size:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"limit must be <= {settings.backend_max_pagination_size}"
                ),
            )


class BasePaginationRest(BaseModel):
    offset: int | None = Field(default=None, ge=0)
    limit: int | None = Field(
        default=None,
        ge=0,
        le=settings.backend_max_pagination_size,
    )
