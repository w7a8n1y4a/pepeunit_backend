import contextlib
import datetime
import json
import logging
import shutil
import uuid as uuid_pkg

from fastapi import Depends

from app import runtime
from app.configs.error_codes import ErrorCode
from app.configs.errors import (
    CustomException,
    GitRepoError,
    RepositoryRegistryError,
)
from app.domain.operation_task_model import OperationTask
from app.domain.repository_registry_model import RepositoryRegistry
from app.dto.enum import (
    AgentType,
    CredentialStatus,
    GitPlatform,
    JsonPayload,
    NotFoundEntity,
    OperationTaskType,
    OwnershipType,
    RepositoryRegistryStatus,
    UserRole,
)
from app.repositories.git_platform_repository import (
    GithubPlatformClient,
    GitlabPlatformClient,
    GitPlatformClientABC,
)
from app.repositories.git_repo_repository import GitRepoRepository
from app.repositories.icon_repository import IconRepository
from app.repositories.repository_registry_repository import (
    RepositoryRegistryRepository,
)
from app.repositories.unit_repository import UnitRepository
from app.repositories.user_repository import UserRepository
from app.schemas.pydantic.operation_task import OperationTaskCreate
from app.schemas.pydantic.repository_registry import (
    CommitFilter,
    CommitRead,
    Credentials,
    OneRepositoryRegistryCredentials,
    RepositoryRegistryCreate,
    RepositoryRegistryFilter,
    RepositoryRegistryRead,
)
from app.schemas.pydantic.unit import UnitFilter
from app.services.access_service import AccessService
from app.services.background import BackgroundService
from app.services.icon_image import IconImage
from app.services.operation_task_service import OperationTaskService
from app.services.permission_service import PermissionService
from app.services.validators import (
    is_valid_json,
    is_valid_object,
)
from app.utils.utils import ensure_timezone_aware


class RepositoryRegistryService:
    def __init__(
        self,
        repository_registry_repository: RepositoryRegistryRepository = Depends(),
        icon_repository: IconRepository = Depends(),
        unit_repository: UnitRepository = Depends(),
        user_repository: UserRepository = Depends(),
        operation_task_service: OperationTaskService = Depends(),
        permission_service: PermissionService = Depends(),
        access_service: AccessService = Depends(),
    ) -> None:
        self.repository_registry_repository = repository_registry_repository
        self.icon_repository = icon_repository
        self.unit_repository = unit_repository
        self.user_repository = user_repository
        self.operation_task_service = operation_task_service
        self.git_repo_repository = GitRepoRepository()
        self.permission_service = permission_service
        self.access_service = access_service

    def get_platform(
        self,
        repository_registry: RepositoryRegistry,
        skip_check_credentials: bool = False,
    ) -> GitPlatformClientABC:
        platforms_dict = {
            GitPlatform.GITLAB: GitlabPlatformClient,
            GitPlatform.GITHUB: GithubPlatformClient,
        }

        if not skip_check_credentials:
            self.is_valid_private_repository(repository_registry)

        credentials = None
        if not repository_registry.is_public_repository:
            all_repository_credentials = repository_registry.get_credentials()

            if self.access_service.current_agent.type == AgentType.USER:
                credentials_with_status = (
                    repository_registry.get_credentials_by_user(
                        all_repository_credentials,
                        str(self.access_service.current_agent.uuid),
                    )
                )

                if not credentials_with_status:
                    msg = "This User has no Credentials"
                    raise RepositoryRegistryError(
                        msg,
                        code=ErrorCode.REPOSITORY_REGISTRY_USER_NO_CREDENTIALS,
                    )

                if credentials_with_status.status == CredentialStatus.ERROR:
                    msg = "Credentials has no permission, status: Error"
                    raise RepositoryRegistryError(
                        msg,
                        code=ErrorCode.REPOSITORY_REGISTRY_CREDENTIALS_ERROR,
                    )

                if (
                    not skip_check_credentials
                    and credentials_with_status.status
                    == CredentialStatus.NOT_VERIFIED
                ):
                    msg = "Credentials has no permission, status: NotVerified"
                    raise RepositoryRegistryError(
                        msg,
                        code=ErrorCode.REPOSITORY_REGISTRY_CREDENTIALS_NOT_VERIFIED,
                    )

                credentials = credentials_with_status.credentials

            elif self.access_service.current_agent.type == AgentType.BACKEND:
                credentials = repository_registry.get_first_valid_credentials(
                    all_repository_credentials
                )

        return platforms_dict[GitPlatform(repository_registry.platform)](
            repository_registry, credentials
        )

    def create(
        self,
        data: RepositoryRegistryCreate,
        is_api: bool = False,
    ) -> RepositoryRegistry:
        if is_api:
            owner = self.user_repository.get_owner()
            is_valid_object(owner, NotFoundEntity.USER)
            creator_uuid = owner.uuid
        else:
            self.access_service.authorization.check_access([AgentType.USER])
            creator_uuid = self.access_service.current_agent.uuid

        self.is_valid_repo_url(data)
        self.is_valid_platform(data)
        self.is_valid_private_repository(data)
        self.repository_registry_repository.is_unique_url(data.repository_url)

        repository_registry = RepositoryRegistry(
            creator_uuid=creator_uuid, **data.dict()
        )

        if not data.is_public_repository:
            repository_registry.set_credentials(
                self.access_service.current_agent.uuid,
                OneRepositoryRegistryCredentials(
                    status=CredentialStatus.NOT_VERIFIED,
                    credentials=Credentials(**data.credentials.dict()),
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
                    credentials=Credentials(**data.credentials.dict()),
                ),
            )

        repository_registry.create_datetime = datetime.datetime.now(
            datetime.UTC
        )
        repository_registry.last_update_datetime = (
            repository_registry.create_datetime
        )
        repository_registry.icon_uuid = self.icon_repository.stage(
            IconImage.generate(repository_registry.repository_url)
        ).uuid

        repository_registry = self.repository_registry_repository.create(
            repository_registry
        )
        if is_api:
            return self.sync_external_repository(repository_registry)

        self.schedule_update(repository_registry.uuid)
        return repository_registry

    def get(self, uuid: uuid_pkg.UUID) -> RepositoryRegistry:
        self.access_service.authorization.check_access(
            [AgentType.BOT, AgentType.USER]
        )
        repository_registry = self.repository_registry_repository.get(
            RepositoryRegistry(uuid=uuid)
        )
        is_valid_object(
            repository_registry, NotFoundEntity.REPOSITORY_REGISTRY
        )
        self.access_service.authorization.check_visibility(repository_registry)
        return repository_registry

    def get_branch_commits(
        self, uuid: uuid_pkg.UUID, filters: CommitFilter
    ) -> list[CommitRead]:
        self.access_service.authorization.check_access([AgentType.USER])

        repository_registry = self.repository_registry_repository.get(
            RepositoryRegistry(uuid=uuid)
        )
        is_valid_object(
            repository_registry, NotFoundEntity.REPOSITORY_REGISTRY
        )
        self.access_service.authorization.check_visibility(repository_registry)

        page = (
            self.git_repo_repository.get_branch_tagged_commits_page(
                repository_registry,
                filters.repo_branch,
                filters.offset,
                filters.limit,
            )
            if filters.only_tag
            else self.git_repo_repository.get_branch_commits_page(
                repository_registry,
                filters.repo_branch,
                filters.offset,
                filters.limit,
            )
        )

        return [CommitRead(**item) for item in page]

    def get_available_platforms(
        self,
        uuid: uuid_pkg.UUID,
        target_commit: str | None = None,
        target_tag: str | None = None,
        branch: str | None = None,
    ) -> list[tuple[str, str]]:
        self.access_service.authorization.check_access([AgentType.USER])

        repository_registry = self.repository_registry_repository.get(
            RepositoryRegistry(uuid=uuid)
        )
        is_valid_object(
            repository_registry, NotFoundEntity.REPOSITORY_REGISTRY
        )
        self.access_service.authorization.check_visibility(repository_registry)

        platforms = []
        if repository_registry.releases_data:
            releases = is_valid_json(
                repository_registry.releases_data,
                JsonPayload.RELEASES_FOR_COMPILE_REPO,
            )

            if target_tag:
                with contextlib.suppress(KeyError):
                    platforms = releases[target_tag]
            elif target_commit:
                commit = self.git_repo_repository.get_commit_with_tag(
                    repository_registry, branch, target_commit
                )
                if commit and commit.get("tag"):
                    platforms = releases[commit["tag"]]
            else:
                page = self.git_repo_repository.get_branch_tagged_commits_page(
                    repository_registry, branch, 0, 1
                )
                target = page[0] if page else None
                if not target:
                    msg = "Version is missing: The tags are not in the repository"
                    raise GitRepoError(
                        msg, code=ErrorCode.GIT_REPO_VERSION_MISSING
                    )
                platforms = releases[target["tag"]]

        return platforms

    def get_credentials(
        self, uuid: uuid_pkg.UUID
    ) -> OneRepositoryRegistryCredentials | None:
        self.access_service.authorization.check_access([AgentType.USER])

        repository_registry = self.repository_registry_repository.get(
            RepositoryRegistry(uuid=uuid)
        )
        is_valid_object(
            repository_registry, NotFoundEntity.REPOSITORY_REGISTRY
        )

        self.is_private_repository(repository_registry)

        all_repository_credentials = repository_registry.get_credentials()

        user_credentials = None
        if all_repository_credentials:
            user_credentials = repository_registry.get_credentials_by_user(
                all_repository_credentials,
                str(self.access_service.current_agent.uuid),
            )

        return user_credentials

    def set_credentials(self, uuid: uuid_pkg.UUID, data: Credentials) -> None:
        self.access_service.authorization.check_access([AgentType.USER])

        repository_registry = self.repository_registry_repository.get(
            RepositoryRegistry(uuid=uuid)
        )
        is_valid_object(
            repository_registry, NotFoundEntity.REPOSITORY_REGISTRY
        )

        self.is_private_repository(repository_registry)

        repository_registry.set_credentials(
            self.access_service.current_agent.uuid,
            OneRepositoryRegistryCredentials(
                status=CredentialStatus.NOT_VERIFIED,
                credentials=Credentials(**data.dict()),
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
                credentials=Credentials(**data.dict()),
            ),
        )

        self.repository_registry_repository.update(
            repository_registry.uuid, repository_registry
        )

    def list(
        self, filters: RepositoryRegistryFilter
    ) -> tuple[int, list[RepositoryRegistry]]:
        self.access_service.authorization.check_access(
            [AgentType.BOT, AgentType.USER]
        )

        if self.access_service.current_agent.type == AgentType.BOT:
            filters.is_public_repository = True

        return self.repository_registry_repository.list(filters)

    def delete(self, uuid: uuid_pkg.UUID) -> None:
        self.access_service.authorization.check_access([AgentType.USER])

        repository_registry = self.repository_registry_repository.get(
            RepositoryRegistry(uuid=uuid)
        )
        is_valid_object(
            repository_registry, NotFoundEntity.REPOSITORY_REGISTRY
        )

        self.access_service.authorization.check_ownership(
            repository_registry, [OwnershipType.CREATOR]
        )

        _count, units = self.unit_repository.list(
            UnitFilter(repository_registry_uuid=uuid, limit=1)
        )
        if units:
            msg = "Repository registry still has units"
            raise RepositoryRegistryError(
                msg,
                code=ErrorCode.REPOSITORY_REGISTRY_HAS_UNITS,
            )

        self.git_repo_repository.delete_repo(repository_registry)
        self.repository_registry_repository.delete(repository_registry)

    def sync_external_repository(
        self, repository_registry: RepositoryRegistry
    ) -> RepositoryRegistry:
        self.is_sync_available(repository_registry)

        repository_registry.sync_status = RepositoryRegistryStatus.PROCESSING
        repository_registry.sync_error = None
        repository_registry.sync_last_datetime = datetime.datetime.now(
            datetime.UTC
        )

        repository_registry = self.repository_registry_repository.update(
            repository_registry.uuid, repository_registry
        )

        try:
            # get size repository on external platform
            repository_size = self.get_platform(
                repository_registry
            ).get_repo_size()
            self.is_valid_repo_size(repository_size)

            # load Repository to local
            url = self.get_platform(repository_registry).get_cloning_url()
            repo_save_path = (
                self.git_repo_repository.get_path_physic_repository(
                    repository_registry
                )
            )
            self.git_repo_repository.clone(url, repo_save_path)

            # get releases assets
            releases = self.get_platform(repository_registry).get_releases()
            repository_registry.releases_data = (
                json.dumps(releases) if releases else None
            )

            # check real on disk size, delete repo if not valid
            repository_size = self.git_repo_repository.local_repository_size(
                repository_registry
            )
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

        return self.repository_registry_repository.update(
            repository_registry.uuid, repository_registry
        )

    def update_local_repository(self, uuid: uuid_pkg.UUID) -> str:
        repository_registry = self.repository_registry_repository.get(
            RepositoryRegistry(uuid=uuid)
        )
        is_valid_object(
            repository_registry, NotFoundEntity.REPOSITORY_REGISTRY
        )

        repository_registry = self.sync_external_repository(
            repository_registry
        )
        if repository_registry.sync_status == RepositoryRegistryStatus.ERROR:
            msg = (
                repository_registry.sync_error
                or "Repository registry sync failed"
            )
            raise RepositoryRegistryError(
                msg, code=ErrorCode.REPOSITORY_REGISTRY_SYNC_FAILED
            )
        return "Registry updated"

    def schedule_update(
        self,
        uuid: uuid_pkg.UUID,
    ) -> OperationTask:
        repository_registry = self.get(uuid)
        self.access_service.authorization.check_repository_registry_access(
            repository_registry
        )
        jwt_token = self.access_service.current_agent.generate_agent_token()
        task = self.operation_task_service.create(
            OperationTaskCreate(
                task_type=OperationTaskType.UPDATE_REGISTRY,
            )
        )

        def operation(_db):
            with BackgroundService(jwt_token) as services:
                return services.get_repository_registry_service().update_local_repository(
                    uuid
                )

        self.operation_task_service.schedule(task, operation)
        return task

    def schedule_update_all(self) -> OperationTask:
        self.access_service.authorization.check_access(
            [AgentType.USER],
            [UserRole.ADMIN],
        )
        task = self.operation_task_service.create(
            OperationTaskCreate(
                task_type=OperationTaskType.UPDATE_ALL_REGISTRIES,
            )
        )

        def operation(_db):
            with BackgroundService() as services:
                return services.get_repository_registry_service().sync_local_repository_storage(
                    force=True
                )

        self.operation_task_service.schedule(task, operation)
        return task

    def sync_local_repository_storage(
        self,
        force: bool = False,
    ) -> str:
        logging.info("Run sync all repository in RepositoryRegistry")

        local_physic_repository = self.git_repo_repository.get_local_registry()
        local_repository_registry = (
            self.repository_registry_repository.get_all()
        )

        synced = 0
        for repository_registry in local_repository_registry:
            if force or (
                str(repository_registry.uuid) not in local_physic_repository
            ):
                logging.info(
                    f"Run sync RepositoryRegistry: {repository_registry.repository_url}"
                )
                self.sync_external_repository(repository_registry)
                synced += 1

        logging.info("End sync all repository in RepositoryRegistry")
        return (
            f"Synced {synced} of {len(local_repository_registry)} registries"
        )

    def backend_force_sync_local_repository_storage(self) -> None:
        self.access_service.authorization.check_access([AgentType.BACKEND])

        self.sync_local_repository_storage()

    @staticmethod
    def is_valid_repo_url(
        repository_registry: RepositoryRegistryCreate | RepositoryRegistry,
    ):
        url = repository_registry.repository_url
        if url[-4:] != ".git" or not (
            url.find("https://") == 0 or url.find("http://") == 0
        ):
            msg = "Repo URL is not correct check the .git at the end of the link and the correctness of https / http"
            raise RepositoryRegistryError(
                msg, code=ErrorCode.REPOSITORY_REGISTRY_URL_INVALID
            )

    @staticmethod
    def is_valid_private_repository(
        data: RepositoryRegistryCreate | RepositoryRegistry,
    ):
        if (
            isinstance(data, RepositoryRegistryCreate)
            and not data.is_public_repository
            and (
                not data.credentials
                or (
                    not data.credentials.username
                    or not data.credentials.pat_token
                )
            )
        ):
            msg = "Credentials is not valid"
            raise RepositoryRegistryError(
                msg, code=ErrorCode.REPOSITORY_REGISTRY_CREDENTIALS_INVALID
            )

        if (
            isinstance(data, RepositoryRegistry)
            and not data.is_public_repository
        ):
            all_repository_credentials = data.get_credentials()

            if not all_repository_credentials:
                msg = "Credentials not Exist"
                raise RepositoryRegistryError(
                    msg, code=ErrorCode.REPOSITORY_REGISTRY_CREDENTIALS_MISSING
                )

            if not data.get_first_valid_credentials(
                all_repository_credentials
            ):
                msg = "No valid credentials in credential list"
                raise RepositoryRegistryError(
                    msg,
                    code=ErrorCode.REPOSITORY_REGISTRY_NO_VALID_CREDENTIALS,
                )

    @staticmethod
    def is_private_repository(
        data: RepositoryRegistryCreate | RepositoryRegistry,
    ):
        if data.is_public_repository:
            msg = "This Repository is Public"
            raise RepositoryRegistryError(
                msg, code=ErrorCode.REPOSITORY_REGISTRY_PUBLIC
            )

    @staticmethod
    def is_valid_platform(
        repository_registry: RepositoryRegistryCreate | RepositoryRegistry,
    ):
        if repository_registry.platform not in list(GitPlatform):
            msg = "Platform {} is not supported - available: {}".format(
                repository_registry.platform, ", ".join(list(GitPlatform))
            )
            raise RepositoryRegistryError(
                msg, code=ErrorCode.REPOSITORY_REGISTRY_PLATFORM_UNSUPPORTED
            )

    @staticmethod
    def is_sync_available(repository_registry: RepositoryRegistry):
        if (
            repository_registry.sync_status
            == RepositoryRegistryStatus.PROCESSING
            and repository_registry.sync_last_datetime
        ):
            last_update_datetime = ensure_timezone_aware(
                repository_registry.last_update_datetime
            )

            delta = (
                datetime.datetime.now(datetime.UTC) - last_update_datetime
            ).total_seconds()
            if delta <= runtime.get().pu_instance_registry_min_interval_sync:
                msg = f"Sync is not available, last sync was {delta} s ago, but it should have taken at least {runtime.get().pu_instance_registry_min_interval_sync} s"
                raise RepositoryRegistryError(
                    msg, code=ErrorCode.REPOSITORY_REGISTRY_SYNC_TOO_SOON
                )

    @staticmethod
    def is_valid_repo_size(
        repo_size: int, delete_path: str | None = None
    ) -> None:
        if (
            repo_size < 0
            or repo_size > runtime.get().pu_instance_registry_max_size * 2**20
        ):
            if delete_path:
                shutil.rmtree(delete_path, ignore_errors=True)

            msg = f"No valid external repo size {round(repo_size / 2**20, 2)} MB, max {runtime.get().pu_instance_registry_max_size} MB"
            raise GitRepoError(msg, code=ErrorCode.GIT_REPO_TOO_LARGE)

    def mapper_registry_to_registry_read(
        self, repository_registry: RepositoryRegistry
    ) -> RepositoryRegistryRead:
        try:
            branches = self.git_repo_repository.get_branches(
                repository_registry
            )
        except Exception:
            branches = []

        return RepositoryRegistryRead(
            branches=branches, **repository_registry.dict()
        )
