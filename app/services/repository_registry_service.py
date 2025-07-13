import datetime
import json
import logging
import shutil
import uuid as uuid_pkg
from typing import Optional, Union

from fastapi import Depends

from app import settings
from app.configs.errors import CustomException, GitRepoError, RepositoryRegistryError
from app.domain.repository_registry_model import RepositoryRegistry
from app.dto.enum import AgentType, CredentialStatus, GitPlatform, OwnershipType, RepositoryRegistryStatus
from app.repositories.git_platform_repository import GithubPlatformClient, GitlabPlatformClient, GitPlatformClientABC
from app.repositories.git_repo_repository import GitRepoRepository
from app.repositories.repo_repository import RepoRepository
from app.repositories.repository_registry_repository import RepositoryRegistryRepository
from app.schemas.pydantic.repo import RepoFilter
from app.schemas.pydantic.repository_registry import (
    CommitFilter,
    CommitRead,
    Credentials,
    OneRepositoryRegistryCredentials,
    RepositoryRegistryCreate,
    RepositoryRegistryFilter,
    RepositoryRegistryRead,
)
from app.services.access_service import AccessService
from app.services.permission_service import PermissionService
from app.services.validators import is_emtpy_sequence, is_valid_json, is_valid_object


class RepositoryRegistryService:

    def __init__(
        self,
        repository_registry_repository: RepositoryRegistryRepository = Depends(),
        repo_repository: RepoRepository = Depends(),
        permission_service: PermissionService = Depends(),
        access_service: AccessService = Depends(),
    ) -> None:
        self.repository_registry_repository = repository_registry_repository
        self.repo_repository = repo_repository
        self.git_repo_repository = GitRepoRepository()
        self.permission_service = permission_service
        self.access_service = access_service

    def get_platform(
        self, repository_registry: RepositoryRegistry, skip_check_credentials: bool = False
    ) -> GitPlatformClientABC:
        platforms_dict = {GitPlatform.GITLAB: GitlabPlatformClient, GitPlatform.GITHUB: GithubPlatformClient}

        if not skip_check_credentials:
            self.is_valid_private_repository(repository_registry)

        credentials = None
        if not repository_registry.is_public_repository:
            all_repository_credentials = repository_registry.get_credentials()

            if self.access_service.current_agent.type == AgentType.USER:
                credentials_with_status = repository_registry.get_credentials_by_user(
                    all_repository_credentials, str(self.access_service.current_agent.uuid)
                )

                if not credentials_with_status:
                    raise RepositoryRegistryError('This User has no Credentials')

                if credentials_with_status.status == CredentialStatus.ERROR:
                    raise RepositoryRegistryError('Credentials has no permission, status: Error')

                if not skip_check_credentials and credentials_with_status.status == CredentialStatus.NOT_VERIFIED:
                    raise RepositoryRegistryError('Credentials has no permission, status: NotVerified')

                credentials = credentials_with_status.credentials

            elif self.access_service.current_agent.type == AgentType.BACKEND:
                credentials = repository_registry.get_first_valid_credentials(all_repository_credentials)

        return platforms_dict[GitPlatform(repository_registry.platform)](repository_registry, credentials)

    def create(self, data: RepositoryRegistryCreate) -> RepositoryRegistry:
        self.access_service.authorization.check_access([AgentType.USER])

        self.is_valid_repo_url(data)
        self.is_valid_platform(data)
        self.is_valid_private_repository(data)
        self.repository_registry_repository.is_unique_url(data.repository_url)

        repository_registry = RepositoryRegistry(creator_uuid=self.access_service.current_agent.uuid, **data.dict())

        if not data.is_public_repository:
            repository_registry.set_credentials(
                self.access_service.current_agent.uuid,
                OneRepositoryRegistryCredentials(
                    status=CredentialStatus.NOT_VERIFIED,
                    credentials=data.credentials,
                ),
            )

            if self.get_platform(repository_registry, True).is_valid_token():
                status = CredentialStatus.VALID
            else:
                status = CredentialStatus.ERROR

            repository_registry.set_credentials(
                self.access_service.current_agent.uuid,
                OneRepositoryRegistryCredentials(
                    status=status,
                    credentials=data.credentials,
                ),
            )

        repository_registry.create_datetime = datetime.datetime.utcnow()
        repository_registry.last_update_datetime = repository_registry.create_datetime

        repository_registry = self.repository_registry_repository.create(repository_registry)

        return self.sync_external_repository(repository_registry)

    def get(self, uuid: uuid_pkg.UUID) -> RepositoryRegistry:
        self.access_service.authorization.check_access([AgentType.BOT, AgentType.USER])
        repository_registry = self.repository_registry_repository.get(RepositoryRegistry(uuid=uuid))
        is_valid_object(repository_registry)
        self.access_service.authorization.check_visibility(repository_registry)
        return repository_registry

    def get_branch_commits(self, uuid: uuid_pkg.UUID, filters: Union[CommitFilter]) -> list[CommitRead]:
        self.access_service.authorization.check_access([AgentType.USER])

        repository_registry = self.repository_registry_repository.get(RepositoryRegistry(uuid=uuid))
        is_valid_object(repository_registry)
        self.access_service.authorization.check_visibility(repository_registry)

        self.git_repo_repository.is_valid_branch(repository_registry, filters.repo_branch)

        commits = self.git_repo_repository.get_branch_commits_with_tag(repository_registry, filters.repo_branch)

        commits_with_tag = self.git_repo_repository.get_tags_from_all_commits(commits) if filters.only_tag else commits

        return [CommitRead(**item) for item in commits_with_tag][filters.offset : filters.offset + filters.limit]

    def get_credentials(self, uuid: uuid_pkg.UUID) -> Optional[OneRepositoryRegistryCredentials]:
        self.access_service.authorization.check_access([AgentType.USER])

        repository_registry = self.repository_registry_repository.get(RepositoryRegistry(uuid=uuid))
        is_valid_object(repository_registry)

        self.is_private_repository(repository_registry)

        all_repository_credentials = repository_registry.get_credentials()

        user_credentials = None
        if all_repository_credentials:
            user_credentials = repository_registry.get_credentials_by_user(
                all_repository_credentials, str(self.access_service.current_agent.uuid)
            )

        return user_credentials

    def set_credentials(self, uuid: uuid_pkg.UUID, data: Union[Credentials]) -> None:
        self.access_service.authorization.check_access([AgentType.USER])

        repository_registry = self.repository_registry_repository.get(RepositoryRegistry(uuid=uuid))
        is_valid_object(repository_registry)

        self.is_private_repository(repository_registry)

        repository_registry.set_credentials(
            self.access_service.current_agent.uuid,
            OneRepositoryRegistryCredentials(
                status=CredentialStatus.NOT_VERIFIED,
                credentials=data,
            ),
        )

        if self.get_platform(repository_registry, True).is_valid_token():
            status = CredentialStatus.VALID
        else:
            status = CredentialStatus.ERROR

        repository_registry.set_credentials(
            self.access_service.current_agent.uuid,
            OneRepositoryRegistryCredentials(
                status=status,
                credentials=data,
            ),
        )

        self.repository_registry_repository.update(repository_registry.uuid, repository_registry)

    def list(self, filters: Union[RepositoryRegistryFilter]) -> tuple[int, list[RepositoryRegistry]]:
        self.access_service.authorization.check_access([AgentType.BOT, AgentType.USER])

        if self.access_service.current_agent.type == AgentType.BOT:
            filters.is_public_repository = True

        return self.repository_registry_repository.list(filters)

    def delete(self, uuid: uuid_pkg.UUID) -> None:
        self.access_service.authorization.check_access([AgentType.USER])

        repository_registry = self.repository_registry_repository.get(RepositoryRegistry(uuid=uuid))
        is_valid_object(repository_registry)

        self.access_service.authorization.check_ownership(repository_registry, [OwnershipType.CREATOR])

        count, repo_list = self.repo_repository.list(RepoFilter(repository_registry_uuid=uuid))
        print(repo_list)
        is_emtpy_sequence(repo_list)

        self.git_repo_repository.delete_repo(repository_registry)
        self.repository_registry_repository.delete(repository_registry)

    def sync_external_repository(self, repository_registry: RepositoryRegistry) -> RepositoryRegistry:

        self.is_sync_available(repository_registry)

        repository_registry.sync_status = RepositoryRegistryStatus.PROCESSING
        repository_registry.sync_error = None
        repository_registry.sync_last_datetime = datetime.datetime.utcnow()

        repository_registry = self.repository_registry_repository.update(repository_registry.uuid, repository_registry)

        try:
            # get size repository on external platform
            repository_size = self.get_platform(repository_registry).get_repo_size()
            self.is_valid_repo_size(repository_size)

            # load Repository to local
            url = self.get_platform(repository_registry).get_cloning_url()
            repo_save_path = self.git_repo_repository.get_path_physic_repository(repository_registry)
            self.git_repo_repository.clone(url, repo_save_path)

            # get releases assets
            releases = self.get_platform(repository_registry).get_releases()
            repository_registry.releases_data = json.dumps(releases) if releases else None

            # check real on disk size, delete repo if not valid
            repository_size = self.git_repo_repository.local_repository_size(repository_registry)
            self.is_valid_repo_size(
                repo_size=repository_size,
                delete_path=repo_save_path,
            )
            repository_registry.local_repository_size = repository_size

            repository_registry.sync_status = RepositoryRegistryStatus.UPDATED
            repository_registry.sync_error = None
        except CustomException as e:
            repository_registry.sync_status = RepositoryRegistryStatus.ERROR
            repository_registry.sync_error = e.message

        return self.repository_registry_repository.update(repository_registry.uuid, repository_registry)

    def update_local_repository(self, uuid: uuid_pkg.UUID) -> None:
        self.access_service.authorization.check_access([AgentType.USER])

        repository_registry = self.repository_registry_repository.get(RepositoryRegistry(uuid=uuid))
        is_valid_object(repository_registry)

        self.access_service.authorization.check_repository_registry_access(repository_registry)

        self.sync_external_repository(repository_registry)

    def sync_local_repository_storage(self) -> None:

        logging.info('Run sync all repository in RepositoryRegistry')

        local_physic_repository = self.git_repo_repository.get_local_registry()
        local_repository_registry = self.repository_registry_repository.get_all()

        for repository_registry in local_repository_registry:
            if str(repository_registry.uuid) not in local_physic_repository:
                logging.info(f'Run sync RepositoryRegistry: {repository_registry.repository_url}')
                self.sync_external_repository(repository_registry)

        logging.info('End sync all repository in RepositoryRegistry')

    def backend_force_sync_local_repository_storage(self) -> None:
        self.access_service.authorization.check_access([AgentType.BACKEND])

        self.sync_local_repository_storage()

    @staticmethod
    def is_valid_repo_url(repository_registry: RepositoryRegistryCreate | RepositoryRegistry):
        url = repository_registry.repository_url
        if url[-4:] != '.git' or not (url.find('https://') == 0 or url.find('http://') == 0):
            raise RepositoryRegistryError(
                "Repo URL is not correct check the .git at the end of the link and the correctness of https / http"
            )

    @staticmethod
    def is_valid_private_repository(data: RepositoryRegistryCreate | RepositoryRegistry):
        if (
            isinstance(data, RepositoryRegistryCreate)
            and not data.is_public_repository
            and (not data.credentials or (not data.credentials.username or not data.credentials.pat_token))
        ):
            raise RepositoryRegistryError('Credentials is not valid')

        if isinstance(data, RepositoryRegistry) and not data.is_public_repository:
            all_repository_credentials = data.get_credentials()

            if not all_repository_credentials:
                raise RepositoryRegistryError('Credentials not Exist')

            if not data.get_first_valid_credentials(all_repository_credentials):
                raise RepositoryRegistryError('No valid credentials in credential list')

    @staticmethod
    def is_private_repository(data: RepositoryRegistryCreate | RepositoryRegistry):
        if data.is_public_repository:
            raise RepositoryRegistryError('This Repository is Public')

    @staticmethod
    def is_valid_platform(repository_registry: RepositoryRegistryCreate | RepositoryRegistry):
        if repository_registry.platform not in list(GitPlatform):
            raise RepositoryRegistryError(
                'Platform {} is not supported - available: {}'.format(
                    repository_registry.platform, ", ".join(list(GitPlatform))
                )
            )

    @staticmethod
    def is_sync_available(repository_registry: RepositoryRegistry):
        if (
            repository_registry.sync_status == RepositoryRegistryStatus.PROCESSING
            and repository_registry.sync_last_datetime
        ):
            delta = (datetime.datetime.utcnow() - repository_registry.last_update_datetime).total_seconds()
            if delta <= settings.backend_min_interval_sync_repository:
                raise RepositoryRegistryError(
                    'Sync is not available, last sync was {} s ago, but it should have taken at least {} s'.format(
                        delta, settings.backend_min_interval_sync_repository
                    )
                )

    @staticmethod
    def is_valid_repo_size(repo_size: int, delete_path: str | None = None) -> None:
        if repo_size < 0 or repo_size > settings.backend_max_external_repo_size * 2**20:
            if delete_path:
                shutil.rmtree(delete_path, ignore_errors=True)

            raise GitRepoError(
                'No valid external repo size {} MB, max {} MB'.format(
                    round(repo_size / 2**20, 2), settings.physic_repo_size
                )
            )

    def mapper_registry_to_registry_read(self, repository_registry: RepositoryRegistry) -> RepositoryRegistryRead:
        try:
            branches = self.git_repo_repository.get_branches(repository_registry)
        except:
            branches = []

        return RepositoryRegistryRead(branches=branches, **repository_registry.dict())
