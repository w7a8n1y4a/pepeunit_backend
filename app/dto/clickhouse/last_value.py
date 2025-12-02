import uuid as uuid_pkg
from datetime import datetime

from pydantic import BaseModel


class LastValue(BaseModel):
    unit_node_uuid: uuid_pkg.UUID
    state: str
    last_update_datetime: datetime
