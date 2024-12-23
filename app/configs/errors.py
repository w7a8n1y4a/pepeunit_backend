from fastapi import HTTPException, status


class Error:
    def __init__(self, status_code: int, message_template: str, error_code: int):
        self.status_code = status_code
        self.message_template = message_template
        self.error_code = error_code

    def raise_exception(self, *args):
        detail = f"{self.error_code}: {self.message_template.format(*args)}"
        raise HTTPException(status_code=self.status_code, detail=detail)


class AppErrors:
    def __init__(self):

        self.no_access = Error(status_code=status.HTTP_403_FORBIDDEN, message_template="No Access: {}", error_code=1)

        self.validation_error = Error(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, message_template="Validation Error: {}", error_code=2
        )

        self.user_error = Error(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, message_template="User Validation Error: {}", error_code=3
        )

        self.permission_error = Error(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            message_template="Permission Validation Error: {}",
            error_code=4,
        )

        self.git_repo_error = Error(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            message_template="Git Repo Validation Error: {}",
            error_code=5,
        )

        self.repo_error = Error(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, message_template="Repo Validation Error: {}", error_code=6
        )

        self.unit_error = Error(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, message_template="Unit Validation Error: {}", error_code=7
        )

        self.unit_node_error = Error(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            message_template="UnitNode Validation Error: {}",
            error_code=8,
        )

        self.json_decode_error = Error(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, message_template="JSON Decode Error: {}", error_code=9
        )

        self.mqtt_error = Error(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, message_template="MQTT Error: {}", error_code=10
        )

        self.update_error = Error(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, message_template="Update Error: {}", error_code=11
        )

        self.cipher_error = Error(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, message_template="Cipher Error: {}", error_code=12
        )


app_errors = AppErrors()


if __name__ == "__main__":

    try:
        app_errors.no_access.raise_exception("Agent not allowed")
        app_errors.validation_error.raise_exception("Validation error")
    except HTTPException as e:
        print(f"{e.status_code}: {e.detail}")
