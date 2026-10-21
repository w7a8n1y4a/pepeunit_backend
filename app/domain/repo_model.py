import json
import uuid as uuid_pkg
from datetime import datetime

from sqlalchemy import Column, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import Field, SQLModel

from app.domain.icon_model import Icon
from app.dto.enum import CredentialStatus, JsonPayload
from app.schemas.pydantic.repo import (
    Credentials,
    OneRepoCredentials,
)
from app.services.validators import is_valid_json
from app.utils.utils import aes_gcm_decode, aes_gcm_encode


class Repo(SQLModel, table=True):
    """Repo"""

    __tablename__ = "repo"

    uuid: uuid_pkg.UUID = Field(
        primary_key=True,
        nullable=False,
        index=True,
        default_factory=uuid_pkg.uuid4,
    )

    # Picture is generated from repository_url and cannot be replaced.
    icon_uuid: uuid_pkg.UUID = Field(
        sa_column=Column(
            UUID(as_uuid=True),
            ForeignKey(
                Icon.__table__.c.uuid,
                name="repo_icon_uuid_fkey",
                ondelete="RESTRICT",
            ),
            nullable=False,
            index=True,
        )
    )

    # type of remote hosting
    platform: str = Field(nullable=False)
    # link to remote repository
    repository_url: str = Field(nullable=False, unique=True)
    # this remote repository is Public ?
    is_public_repository: bool = Field(nullable=False, default=True)
    # if is_public_repository=False - cipher creds to load remote repository. Struct after decipher
    # {"<creator_uuid>": {"credentials": {"username": "", "pat_token": ""}, "status": ""}}
    cipher_credentials_private_repository: str = Field(nullable=True)
    # assets links by tags
    releases_data: str = Field(nullable=True, default=None)
    # size on disk in bytes, for git repository
    local_repository_size: int = Field(nullable=False, default=0)

    # last sync status
    sync_status: str = Field(nullable=True)
    # error last sync
    sync_error: str = Field(nullable=True)
    # time last sync
    sync_last_datetime: datetime = Field(nullable=True)

    create_datetime: datetime = Field(nullable=False)
    last_update_datetime: datetime = Field(nullable=False)

    # to User link
    creator_uuid: uuid_pkg.UUID = Field(
        sa_column=Column(
            UUID(as_uuid=True),
            ForeignKey("users.uuid", ondelete="SET NULL"),
            nullable=True,
        )
    )

    def set_credentials(
        self,
        creator_uuid: uuid_pkg.UUID,
        data: OneRepoCredentials,
    ) -> None:
        all_repository_credentials = self.get_credentials()

        if not all_repository_credentials:
            all_repository_credentials = {}

        all_repository_credentials[str(creator_uuid)] = data

        self.cipher_credentials_private_repository = aes_gcm_encode(
            json.dumps(
                {
                    key: value.dict()
                    for key, value in all_repository_credentials.items()
                }
            )
        )

    def get_credentials(
        self,
    ) -> dict[str, OneRepoCredentials] | None:
        if self.cipher_credentials_private_repository:
            return {
                creator_uuid: OneRepoCredentials(**credentials)
                for creator_uuid, credentials in is_valid_json(
                    aes_gcm_decode(self.cipher_credentials_private_repository),
                    JsonPayload.CIPHER_CREDENTIALS_PRIVATE_REPOSITORY,
                ).items()
            }
        return None

    @staticmethod
    def get_first_valid_credentials(
        data: dict[str, OneRepoCredentials],
    ) -> Credentials | None:
        for credentials in data.values():
            if credentials.status == CredentialStatus.VALID:
                return credentials.credentials
        return None

    @staticmethod
    def get_credentials_by_user(
        data: dict[str, OneRepoCredentials],
        target_user_uuid: str,
    ) -> OneRepoCredentials | None:
        for user_uuid, credentials in data.items():
            if user_uuid == target_user_uuid:
                return credentials
        return None
