from fastapi import status

from app.configs.error_codes import ErrorCode


class CustomException(Exception):
    status_code: int
    message_template: str

    def __init__(self, message: str, *, code: ErrorCode) -> None:
        self.raw_message = message
        self.error_code = int(code)
        body = self.message_template.format(message)
        self.message = f"{self.status_code}: {self.error_code}: {body}"
        super().__init__(
            f"{self.status_code}: {ErrorCode.console(code)}: {body}"
        )


class NoAccessError(CustomException):
    status_code = status.HTTP_403_FORBIDDEN
    message_template = "No Access: {}"


class ValidationError(CustomException):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    message_template = "Validation Error: {}"


class UserError(CustomException):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    message_template = "User Validation Error: {}"


class CustomPermissionError(CustomException):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    message_template = "Permission Validation Error: {}"


class GitRepoError(CustomException):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    message_template = "Git Repo Validation Error: {}"


class RepoError(CustomException):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    message_template = "Repo Validation Error: {}"


class UnitError(CustomException):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    message_template = "Unit Validation Error: {}"


class UnitIOError(CustomException):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    message_template = "UnitIO Validation Error: {}"


class DataPipeError(CustomException):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    message_template = "DataPipe Validation Error: {}"


class CustomJSONDecodeError(CustomException):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    message_template = "JSON Decode Error: {}"


class MqttError(CustomException):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    message_template = "MQTT Error: {}"


class UpdateError(CustomException):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    message_template = "Update Error: {}"


class CipherError(CustomException):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    message_template = "Cipher Error: {}"


class GitPlatformClientError(CustomException):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    message_template = "Git Platform Client Error: {}"


class GrafanaError(CustomException):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    message_template = "Grafana Error: {}"


class FeatureFlagError(CustomException):
    status_code = status.HTTP_405_METHOD_NOT_ALLOWED
    message_template = "Feature Flag Error: {}"


class ReadmeGenerationError(CustomException):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    message_template = "Readme Generation Error: {}"


class InstanceError(CustomException):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    message_template = "Instance Validation Error: {}"


class OperationTaskError(CustomException):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    message_template = "Operation Task Validation Error: {}"


class NotificationError(CustomException):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    message_template = "Notification Validation Error: {}"


class LokiError(CustomException):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    message_template = "Loki Error: {}"


class UnitGroupError(CustomException):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    message_template = "Unit Group Validation Error: {}"
