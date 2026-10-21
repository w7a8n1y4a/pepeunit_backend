from pydantic import ValidationError

from app.configs.error_codes import ErrorCode
from app.configs.errors import InstanceError
from app.schemas.pydantic.instance_settings import InstanceSettingsData


def is_valid_instance_settings(data: dict) -> InstanceSettingsData:
    try:
        return InstanceSettingsData.model_validate(data)
    except ValidationError as err:
        first = err.errors()[0]
        raise InstanceError(
            first["msg"],
            code=ErrorCode.code_from_validation(
                first, ErrorCode.INSTANCE_SETTINGS_INVALID
            ),
        ) from err
