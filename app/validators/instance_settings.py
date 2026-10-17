from pydantic import ValidationError

from app.configs.errors import InstanceError
from app.schemas.pydantic.instance_settings import InstanceSettingsData


def is_valid_instance_settings(data: dict) -> InstanceSettingsData:
    try:
        return InstanceSettingsData.model_validate(data)
    except ValidationError as err:
        raise InstanceError(err.errors()[0]["msg"]) from err
