from dataclasses import dataclass, field
from typing import Self

from app import runtime
from app.configs.error_codes import ErrorCode
from app.configs.errors import ValidationError

# Marker for filters that must not be paginated. It is only reachable through
# BasePaginationRestMixin.unlimited, __post_init__ rejects it for any API input.
NO_PAGINATION = -1


@dataclass(kw_only=True)
class BasePaginationRestMixin:
    offset: int = 0
    limit: int = field(
        default_factory=lambda: runtime.get().pu_instance_max_pagination_size
    )

    def __post_init__(self):
        if self.offset < 0:
            msg = "offset must be >= 0"
            raise ValidationError(msg, code=ErrorCode.PAGINATION_OFFSET)

        if self.limit < 0:
            msg = "limit must be >= 0"
            raise ValidationError(
                msg, code=ErrorCode.PAGINATION_LIMIT_NEGATIVE
            )
        if self.limit > runtime.get().pu_instance_max_pagination_size:
            msg = (
                "limit must be <= "
                f"{runtime.get().pu_instance_max_pagination_size}"
            )
            raise ValidationError(
                msg, code=ErrorCode.PAGINATION_LIMIT_TOO_LARGE
            )

    @classmethod
    def unlimited(cls, **kwargs) -> Self:
        """Whole result set, for backend internals where a page would be a bug"""
        filters = cls(**kwargs)
        filters.offset = 0
        filters.limit = NO_PAGINATION
        return filters
