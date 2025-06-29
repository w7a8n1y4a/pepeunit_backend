from fastapi import status


class CustomException(Exception):
    def __init__(self, message: str, status_code: int, message_template: str, error_code: int):
        self.message = '{}: {}: {}'.format(status_code, error_code, message_template.format(message))
        self.status_code = status_code
        self.message_template = message_template
        self.error_code = error_code
        super().__init__(self.message)


class NoAccessError(CustomException):
    def __init__(self, message):
        super().__init__(message, status_code=status.HTTP_403_FORBIDDEN, message_template="No Access: {}", error_code=1)


class ValidationError(CustomException):
    def __init__(self, message):
        super().__init__(
            message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            message_template="Validation Error: {}",
            error_code=2,
        )


class UserError(CustomException):
    def __init__(self, message):
        super().__init__(
            message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            message_template="User Validation Error: {}",
            error_code=3,
        )


class CustomPermissionError(CustomException):
    def __init__(self, message):
        super().__init__(
            message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            message_template="Permission Validation Error: {}",
            error_code=4,
        )


class GitRepoError(CustomException):
    def __init__(self, message):
        super().__init__(
            message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            message_template="Git Repo Validation Error: {}",
            error_code=5,
        )


class RepoError(CustomException):
    def __init__(self, message):
        super().__init__(
            message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            message_template="Repo Validation Error: {}",
            error_code=6,
        )


class UnitError(CustomException):
    def __init__(self, message):
        super().__init__(
            message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            message_template="Unit Validation Error: {}",
            error_code=7,
        )


class UnitNodeError(CustomException):
    def __init__(self, message):
        super().__init__(
            message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            message_template="UnitNode Validation Error: {}",
            error_code=8,
        )


class DataPipeError(CustomException):
    def __init__(self, message):
        super().__init__(
            message=message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            message_template="DataPipe Validation Error: {}",
            error_code=8,
        )


class CustomJSONDecodeError(CustomException):
    def __init__(self, message):
        super().__init__(
            message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            message_template="JSON Decode Error: {}",
            error_code=9,
        )


class MqttError(CustomException):
    def __init__(self, message):
        super().__init__(
            message, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, message_template="MQTT Error: {}", error_code=10
        )


class UpdateError(CustomException):
    def __init__(self, message):
        super().__init__(
            message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            message_template="Update Error: {}",
            error_code=11,
        )


class CipherError(CustomException):
    def __init__(self, message):
        super().__init__(
            message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            message_template="Cipher Error: {}",
            error_code=12,
        )


class RepositoryRegistryError(CustomException):
    def __init__(self, message):
        super().__init__(
            message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            message_template="RepositoryRegistry Validation Error: {}",
            error_code=13,
        )
