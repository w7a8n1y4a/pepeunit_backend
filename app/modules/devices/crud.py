import datetime
import uuid

from app.modules.devices.models import UnitRead
from app.modules.devices.nodes import Unit


def create(name: str, repository_link: str) -> UnitRead:

    unit = Unit(uuid=uuid.uuid4(),
                name=name,
                repository_link=repository_link,
                unit_state_variable='',
                encrypted_env_variables='',
                create_datetime=datetime.datetime.utcnow()).save()

    return UnitRead(
            uuid=unit.uuid,
            name=unit.name,
            repository_link=unit.repository_link,
            unit_state_variable=unit.unit_state_variable,
            encrypted_env_variables=unit.encrypted_env_variables,
            create_datetime=unit.create_datetime
        )


def get_all() -> list[UnitRead]:

    units = Unit.nodes.all()

    return [
        UnitRead(
            uuid=unit.uuid,
            name=unit.name,
            repository_link=unit.repository_link,
            unit_state_variable=unit.unit_state_variable,
            encrypted_env_variables=unit.encrypted_env_variables,
            create_datetime=unit.create_datetime
        )
        for unit in units
    ]
