import uuid as uuid_pkg
from datetime import datetime

from pydantic import BaseModel


class UnitRead(BaseModel):

    uuid: uuid_pkg.UUID
    name: str
    repository_link: str
    unit_state_variable: str
    encrypted_env_variables: str
    create_datetime: datetime
