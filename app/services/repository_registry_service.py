import datetime

from fastapi import Depends

from app.configs.errors import RepositoryRegistryError
from app.domain.repository_registry_model import RepositoryRegistry
from app.dto.enum import AgentType, GitPlatform
from app.dto.repository_registry import Credentials, RepositoryRegistryCreate
from app.repositories.git_repo_repository import GitRepoRepository
from app.repositories.repository_registry_repository import RepositoryRegistryRepository
from app.services.access_service import AccessService
from app.services.permission_service import PermissionService


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

    def sync_external_repository(
        self, repository_registry: RepositoryRegistry, credentials: Credentials | None = None
    ) -> None:

        self.repository_registry_repository.update()

    def create(self, data: RepositoryRegistryCreate) -> RepositoryRegistry:
        self.access_service.authorization.check_access([AgentType.USER])

        self.is_valid_repo_url(data)
        self.is_valid_platform(data)
        self.is_valid_private_repo(data)

        repository_registry = self.repository_registry_repository.get_by_url(RepositoryRegistry(**data.dict()))

        if not repository_registry:
            repository_registry = RepositoryRegistry(creator_uuid=self.access_service.current_agent.uuid, **data.dict())
            repository_registry.create_datetime = datetime.datetime.utcnow()
            repository_registry.last_update_datetime = repository_registry.create_datetime
            repository_registry = self.repository_registry_repository.create(repository_registry)

        self.sync_external_repository(repository_registry, data.credentials)

        return repository_registry

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
