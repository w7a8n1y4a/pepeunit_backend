import datetime
import json
import uuid as uuid_pkg

from fastapi import Depends

from app.configs.errors import GitRepoError, RepositoryRegistryError
from app.domain.repository_registry_model import RepositoryRegistry
from app.dto.enum import AgentType, CredentialStatus, GitPlatform, RepositoryRegistryStatus
from app.repositories.git_repo_repository import GitRepoRepository
from app.repositories.repository_registry_repository import RepositoryRegistryRepository
from app.schemas.pydantic.repository_registry import RepositoryRegistryCreate, RepositoryRegistryRead
from app.services.access_service import AccessService
from app.services.permission_service import PermissionService
from app.services.validators import is_valid_object
from app.utils.utils import aes_gcm_encode


class RepositoryRegistryService:

    def __init__(
        self,
        repository_registry_repository: RepositoryRegistryRepository = Depends(),
        permission_service: PermissionService = Depends(),
        access_service: AccessService = Depends(),
    ) -> None:
        self.repository_registry_repository = repository_registry_repository
        self.git_repo_repository = GitRepoRepository()
        self.permission_service = permission_service
        self.access_service = access_service

    def create(self, data: RepositoryRegistryCreate) -> RepositoryRegistry:
        self.access_service.authorization.check_access([AgentType.USER])

        self.is_valid_repo_url(data)
        self.is_valid_platform(data)
        self.is_valid_private_repo(data)
        self.repository_registry_repository.is_unique_url(data.repository_url)

        repository_registry = RepositoryRegistry(creator_uuid=self.access_service.current_agent.uuid, **data.dict())

        if not data.is_public_repository:
            repository_registry.cipher_credentials_private_repository = aes_gcm_encode(
                json.dumps(
                    {
                        str(self.access_service.current_agent.uuid): {
                            "credentials": data.credentials.dict(),
                            "status": CredentialStatus.NOT_VERIFIED,
                        }
                    }
                )
            )

        repository_registry.create_datetime = datetime.datetime.utcnow()
        repository_registry.last_update_datetime = repository_registry.create_datetime

        repository_registry = self.repository_registry_repository.create(repository_registry)

        self.sync_external_repository(repository_registry)

        return repository_registry

    def get(self, uuid: uuid_pkg.UUID) -> RepositoryRegistryRead:
        self.access_service.authorization.check_access([AgentType.BOT, AgentType.USER])
        repository_registry = self.repository_registry_repository.get(RepositoryRegistry(uuid=uuid))
        is_valid_object(repository_registry)
        self.access_service.authorization.check_visibility(repository_registry)
        return RepositoryRegistryRead(**repository_registry.dict())

    def sync_external_repository(self, repository_registry: RepositoryRegistry) -> None:

        # TODO: здесь надо делать проверку по времени
        # TODO: здесь надо придумать механизм отмены статуса PROCESSING
        if repository_registry.sync_status == RepositoryRegistryStatus.PROCESSING:
            raise RepositoryRegistryError('Sync is not available, current state is update Processing')
        else:
            repository_registry.sync_status = RepositoryRegistryStatus.PROCESSING
            repository_registry.sync_error = None

            repository_registry = self.repository_registry_repository.update(
                repository_registry.uuid, repository_registry
            )

        try:
            self.git_repo_repository.clone_remote_repo(repository_registry)
            repository_registry.sync_status = RepositoryRegistryStatus.UPDATED
            repository_registry.sync_error = None
            repository_registry.sync_last_datetime = datetime.datetime.utcnow()
        except GitRepoError as e:
            repository_registry.sync_status = RepositoryRegistryStatus.ERROR
            repository_registry.sync_error = e.message

        releases = self.git_repo_repository.get_releases(repo_dto)
        repository_registry.releases_data = json.dumps(releases) if releases else None

        repository_registry.local_repository_size = self.git_repo_repository.local_repository_size(repo_dto)

        self.repository_registry_repository.update(repository_registry.uuid, repository_registry)

    @staticmethod
    def is_valid_repo_url(repository_registry: RepositoryRegistryCreate | RepositoryRegistry):
        url = repository_registry.repository_url
        if url[-4:] != '.git' or not (url.find('https://') == 0 or url.find('http://') == 0):
            raise RepositoryRegistryError(
                "Repo URL is not correct check the .git at the end of the link and the correctness of https / http"
            )

    @staticmethod
    def is_valid_private_repo(data: RepositoryRegistryCreate | RepositoryRegistryCreate):
        if not data.is_public_repository and (
            not data.credentials or (not data.credentials.username or not data.credentials.pat_token)
        ):
            raise RepositoryRegistryError('Credentials is not valid')

    @staticmethod
    def is_valid_platform(repository_registry: RepositoryRegistryCreate | RepositoryRegistry):
        if repository_registry.platform not in list(GitPlatform):
            raise RepositoryRegistryError(
                'Platform {} is not supported - available: {}'.format(
                    repository_registry.platform, ", ".join(list(GitPlatform))
                )
            )
