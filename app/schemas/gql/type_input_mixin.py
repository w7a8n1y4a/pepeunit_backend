from dataclasses import dataclass

from app import settings


class TypeInputMixin:
    def dict(self):
        return self.__dict__


@dataclass(kw_only=True)
class BasePaginationGql(TypeInputMixin):
    offset: int | None = None
    limit: int | None = None

    def __post_init__(self):
        if self.offset is not None and self.offset < 0:
            msg = "offset must be >= 0"
            raise ValueError(msg)

        if self.limit is None:
            return

        if self.limit < 0:
            msg = "limit must be >= 0"
            raise ValueError(msg)

        if self.limit > settings.backend_max_pagination_size:
            msg = f"limit must be <= {settings.backend_max_pagination_size}"
            raise ValueError(msg)
