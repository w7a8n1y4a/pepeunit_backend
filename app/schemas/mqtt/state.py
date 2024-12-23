from typing import Optional

from pydantic import BaseModel, root_validator


class StateUnitModel(BaseModel):
    ifconfig: Optional[list] = None
    millis: Optional[int] = None
    mem_free: Optional[int] = None
    mem_alloc: Optional[int] = None
    freq: Optional[float] = None
    statvfs: Optional[list] = None
    commit_version: Optional[str] = None

    @root_validator(pre=True)
    def check_types(cls, values):
        annotations = cls.__annotations__
        for field, expected_type in annotations.items():
            value = values.get(field, None)
            if value is not None and not isinstance(value, expected_type):
                values[field] = None
        return values
