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
    RepoError,
)
from app.domain.operation_task_model import OperationTask
from app.domain.repo_model import Repo
from app.dto.enum import (
    AgentType,
    CredentialStatus,
    GitPlatform,
    JsonPayload,
    NotFoundEntity,
    OperationTaskType,
    OwnershipType,
    RepoStatus,
    UserRole,
)
from app.repositories.git_platform_repository import (
    GithubPlatformClient,
    GitlabPlatformClient,
    GitPlatformClientABC,
)
from app.repositories.git_repo_repository import GitRepoRepository
from app.repositories.icon_repository import IconRepository
from app.repositories.repo_repository import (
    RepoRepository,
)
from app.repositories.unit_repository import UnitRepository
from app.repositories.user_repository import UserRepository
from app.schemas.pydantic.operation_task import OperationTaskCreate
from app.schemas.pydantic.repo import (
    CommitFilter,
    CommitRead,
    Credentials,
    OneRepoCredentials,
    RepoCreate,
    RepoFilter,
    RepoRead,
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


class RepoService:
    def __init__(
        self,
        repo_repository: RepoRepository = Depends(),
        icon_repository: IconRepository = Depends(),
        unit_repository: UnitRepository = Depends(),
        user_repository: UserRepository = Depends(),
        operation_task_service: OperationTaskService = Depends(),
        permission_service: PermissionService = Depends(),
        access_service: AccessService = Depends(),
    ) -> None:
        self.repo_repository = repo_repository
        self.icon_repository = icon_repository
        self.unit_repository = unit_repository
        self.user_repository = user_repository
        self.operation_task_service = operation_task_service
        self.git_repo_repository = GitRepoRepository()
        self.permission_service = permission_service
        self.access_service = access_service

    def get_platform(
        self,
        repo: Repo,
        skip_check_credentials: bool = False,
    ) -> GitPlatformClientABC:
        platforms_dict = {
            GitPlatform.GITLAB: GitlabPlatformClient,
            GitPlatform.GITHUB: GithubPlatformClient,
        }

        if not skip_check_credentials:
            self.is_valid_private_repository(repo)

        credentials = None
        if not repo.is_public_repository:
            all_repository_credentials = repo.get_credentials()

            if self.access_service.current_agent.type == AgentType.USER:
                credentials_with_status = repo.get_credentials_by_user(
                    all_repository_credentials,
                    str(self.access_service.current_agent.uuid),
                )

                if not credentials_with_status:
                    msg = "This User has no Credentials"
                    raise RepoError(
                        msg,
                        code=ErrorCode.REPO_USER_NO_CREDENTIALS,
                    )

                if credentials_with_status.status == CredentialStatus.ERROR:
                    msg = "Credentials has no permission, status: Error"
                    raise RepoError(
                        msg,
                        code=ErrorCode.REPO_CREDENTIALS_ERROR,
                    )

                if (
                    not skip_check_credentials
                    and credentials_with_status.status
                    == CredentialStatus.NOT_VERIFIED
                ):
                    msg = "Credentials has no permission, status: NotVerified"
                    raise RepoError(
                        msg,
                        code=ErrorCode.REPO_CREDENTIALS_NOT_VERIFIED,
                    )

                credentials = credentials_with_status.credentials

            elif self.access_service.current_agent.type == AgentType.BACKEND:
                credentials = repo.get_first_valid_credentials(
                    all_repository_credentials
                )

        return platforms_dict[GitPlatform(repo.platform)](repo, credentials)

    def create(
        self,
        data: RepoCreate,
        is_api: bool = False,
    ) -> Repo:
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
        self.repo_repository.is_unique_url(data.repository_url)

        repo = Repo(creator_uuid=creator_uuid, **data.dict())

        if not data.is_public_repository:
            repo.set_credentials(
                self.access_service.current_agent.uuid,
                OneRepoCredentials(
                    status=CredentialStatus.NOT_VERIFIED,
                    credentials=Credentials(**data.credentials.dict()),
                ),
            )

            if self.get_platform(repo, True).is_valid_token():
                status = CredentialStatus.VALID
            else:
                status = CredentialStatus.ERROR

            repo.set_credentials(
                self.access_service.current_agent.uuid,
                OneRepoCredentials(
                    status=status,
                    credentials=Credentials(**data.credentials.dict()),
                ),
            )

        repo.create_datetime = datetime.datetime.now(datetime.UTC)
        repo.last_update_datetime = repo.create_datetime
        repo.icon_uuid = self.icon_repository.stage(
            IconImage.generate(repo.repository_url)
        ).uuid

        repo = self.repo_repository.create(repo)
        if is_api:
            return self.sync_external_repository(repo)

        self.schedule_update(repo.uuid)
        return repo

    def get(self, uuid: uuid_pkg.UUID) -> Repo:
        self.access_service.authorization.check_access(
            [AgentType.BOT, AgentType.USER]
        )
        repo = self.repo_repository.get(Repo(uuid=uuid))
        is_valid_object(repo, NotFoundEntity.REPO)
        self.access_service.authorization.check_visibility(repo)
        return repo

    def read(self, uuid: uuid_pkg.UUID) -> RepoRead:
        self.access_service.authorization.check_access(
            [AgentType.BOT, AgentType.USER]
        )
        row = self.repo_repository.get_with_child_unit_count(uuid)
        is_valid_object(row, NotFoundEntity.REPO)
        repo, child_unit_count = row
        self.access_service.authorization.check_visibility(repo)
        return self.mapper_repo_to_repo_read(repo, int(child_unit_count))

    def get_branch_commits(
        self, uuid: uuid_pkg.UUID, filters: CommitFilter
    ) -> list[CommitRead]:
        self.access_service.authorization.check_access([AgentType.USER])

        repo = self.repo_repository.get(Repo(uuid=uuid))
        is_valid_object(repo, NotFoundEntity.REPO)
        self.access_service.authorization.check_visibility(repo)

        page = (
            self.git_repo_repository.get_branch_tagged_commits_page(
                repo,
                filters.repo_branch,
                filters.offset,
                filters.limit,
            )
            if filters.only_tag
            else self.git_repo_repository.get_branch_commits_page(
                repo,
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

        repo = self.repo_repository.get(Repo(uuid=uuid))
        is_valid_object(repo, NotFoundEntity.REPO)
        self.access_service.authorization.check_visibility(repo)

        platforms = []
        if repo.releases_data:
            releases = is_valid_json(
                repo.releases_data,
                JsonPayload.RELEASES_FOR_COMPILE_REPO,
            )

            if target_tag:
                with contextlib.suppress(KeyError):
                    platforms = releases[target_tag]
            elif target_commit:
                commit = self.git_repo_repository.get_commit_with_tag(
                    repo, branch, target_commit
                )
                if commit and commit.get("tag"):
                    platforms = releases[commit["tag"]]
            else:
                page = self.git_repo_repository.get_branch_tagged_commits_page(
                    repo, branch, 0, 1
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
    ) -> OneRepoCredentials | None:
        self.access_service.authorization.check_access([AgentType.USER])

        repo = self.repo_repository.get(Repo(uuid=uuid))
        is_valid_object(repo, NotFoundEntity.REPO)

        self.is_private_repository(repo)

        all_repository_credentials = repo.get_credentials()

        user_credentials = None
        if all_repository_credentials:
            user_credentials = repo.get_credentials_by_user(
                all_repository_credentials,
                str(self.access_service.current_agent.uuid),
            )

        return user_credentials

    def set_credentials(self, uuid: uuid_pkg.UUID, data: Credentials) -> None:
        self.access_service.authorization.check_access([AgentType.USER])

        repo = self.repo_repository.get(Repo(uuid=uuid))
        is_valid_object(repo, NotFoundEntity.REPO)

        self.is_private_repository(repo)

        repo.set_credentials(
            self.access_service.current_agent.uuid,
            OneRepoCredentials(
                status=CredentialStatus.NOT_VERIFIED,
                credentials=Credentials(**data.dict()),
            ),
        )

        if self.get_platform(repo, True).is_valid_token():
            status = CredentialStatus.VALID
        else:
            status = CredentialStatus.ERROR

        repo.set_credentials(
            self.access_service.current_agent.uuid,
            OneRepoCredentials(
                status=status,
                credentials=Credentials(**data.dict()),
            ),
        )

        self.repo_repository.update(repo.uuid, repo)

    def list(self, filters: RepoFilter) -> tuple[int, list[tuple[Repo, int]]]:
        self.access_service.authorization.check_access(
            [AgentType.BOT, AgentType.USER]
        )

        if self.access_service.current_agent.type == AgentType.BOT:
            filters.is_public_repository = True

        return self.repo_repository.list(filters)

    def delete(self, uuid: uuid_pkg.UUID) -> None:
        self.access_service.authorization.check_access([AgentType.USER])

        repo = self.repo_repository.get(Repo(uuid=uuid))
        is_valid_object(repo, NotFoundEntity.REPO)

        self.access_service.authorization.check_ownership(
            repo, [OwnershipType.CREATOR]
        )

        _count, units = self.unit_repository.list(
            UnitFilter(repo_uuid=uuid, limit=1)
        )
        if units:
            msg = "Repo still has units"
            raise RepoError(
                msg,
                code=ErrorCode.REPO_HAS_UNITS,
            )

        self.git_repo_repository.delete_repo(repo)
        self.repo_repository.delete(repo)

    def sync_external_repository(self, repo: Repo) -> Repo:
        self.is_sync_available(repo)

        repo.sync_status = RepoStatus.PROCESSING
        repo.sync_error = None
        repo.sync_last_datetime = datetime.datetime.now(datetime.UTC)

        repo = self.repo_repository.update(repo.uuid, repo)

        try:
            # get size repository on external platform
            repository_size = self.get_platform(repo).get_repo_size()
            self.is_valid_repo_size(repository_size)

            # load Repository to local
            url = self.get_platform(repo).get_cloning_url()
            repo_save_path = (
                self.git_repo_repository.get_path_physic_repository(repo)
            )
            self.git_repo_repository.clone(url, repo_save_path)

            # get releases assets
            releases = self.get_platform(repo).get_releases()
            repo.releases_data = json.dumps(releases) if releases else None

            # check real on disk size, delete repo if not valid
            repository_size = self.git_repo_repository.local_repository_size(
                repo
            )
            self.is_valid_repo_size(
                repo_size=repository_size,
                delete_path=repo_save_path,
            )
            repo.local_repository_size = repository_size

            repo.sync_status = RepoStatus.UPDATED
            repo.sync_error = None
        except CustomException as e:
            repo.sync_status = RepoStatus.ERROR
            repo.sync_error = e.message

        return self.repo_repository.update(repo.uuid, repo)

    def update_local_repository(self, uuid: uuid_pkg.UUID) -> str:
        repo = self.repo_repository.get(Repo(uuid=uuid))
        is_valid_object(repo, NotFoundEntity.REPO)

        repo = self.sync_external_repository(repo)
        if repo.sync_status == RepoStatus.ERROR:
            msg = repo.sync_error or "Repo sync failed"
            raise RepoError(msg, code=ErrorCode.REPO_SYNC_FAILED)
        return "Repo updated"

    def schedule_update(
        self,
        uuid: uuid_pkg.UUID,
    ) -> OperationTask:
        repo = self.get(uuid)
        self.access_service.authorization.check_repo_access(repo)
        jwt_token = self.access_service.current_agent.generate_agent_token()
        task = self.operation_task_service.create(
            OperationTaskCreate(
                task_type=OperationTaskType.UPDATE_REPO,
            )
        )

        def operation(_db):
            with BackgroundService(jwt_token) as services:
                return services.get_repo_service().update_local_repository(
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
                task_type=OperationTaskType.UPDATE_ALL_REPOS,
            )
        )

        def operation(_db):
            with BackgroundService() as services:
                return (
                    services.get_repo_service().sync_local_repository_storage(
                        force=True
                    )
                )

        self.operation_task_service.schedule(task, operation)
        return task

    def sync_local_repository_storage(
        self,
        force: bool = False,
    ) -> str:
        logging.info("Run sync of all repos")

        local_physic_repository = self.git_repo_repository.get_local_repo()
        local_repo = self.repo_repository.get_all()

        synced = 0
        for repo in local_repo:
            if force or (str(repo.uuid) not in local_physic_repository):
                logging.info(f"Run sync repo: {repo.repository_url}")
                self.sync_external_repository(repo)
                synced += 1

        logging.info("End sync of all repos")
        return f"Synced {synced} of {len(local_repo)} repos"

    def backend_force_sync_local_repository_storage(self) -> None:
        self.access_service.authorization.check_access([AgentType.BACKEND])

        self.sync_local_repository_storage()

    @staticmethod
    def is_valid_repo_url(
        repo: RepoCreate | Repo,
    ):
        url = repo.repository_url
        if url[-4:] != ".git" or not (
            url.find("https://") == 0 or url.find("http://") == 0
        ):
            msg = "Repo URL is not correct check the .git at the end of the link and the correctness of https / http"
            raise RepoError(msg, code=ErrorCode.REPO_URL_INVALID)

    @staticmethod
    def is_valid_private_repository(
        data: RepoCreate | Repo,
    ):
        if (
            isinstance(data, RepoCreate)
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
            raise RepoError(msg, code=ErrorCode.REPO_CREDENTIALS_INVALID)

        if isinstance(data, Repo) and not data.is_public_repository:
            all_repository_credentials = data.get_credentials()

            if not all_repository_credentials:
                msg = "Credentials not Exist"
                raise RepoError(msg, code=ErrorCode.REPO_CREDENTIALS_MISSING)

            if not data.get_first_valid_credentials(
                all_repository_credentials
            ):
                msg = "No valid credentials in credential list"
                raise RepoError(
                    msg,
                    code=ErrorCode.REPO_NO_VALID_CREDENTIALS,
                )

    @staticmethod
    def is_private_repository(
        data: RepoCreate | Repo,
    ):
        if data.is_public_repository:
            msg = "This Repository is Public"
            raise RepoError(msg, code=ErrorCode.REPO_PUBLIC)

    @staticmethod
    def is_valid_platform(
        repo: RepoCreate | Repo,
    ):
        if repo.platform not in list(GitPlatform):
            msg = "Platform {} is not supported - available: {}".format(
                repo.platform, ", ".join(list(GitPlatform))
            )
            raise RepoError(msg, code=ErrorCode.REPO_PLATFORM_UNSUPPORTED)

    @staticmethod
    def is_sync_available(repo: Repo):
        if (
            repo.sync_status == RepoStatus.PROCESSING
            and repo.sync_last_datetime
        ):
            last_update_datetime = ensure_timezone_aware(
                repo.last_update_datetime
            )

            delta = (
                datetime.datetime.now(datetime.UTC) - last_update_datetime
            ).total_seconds()
            if delta <= runtime.get().pu_instance_repo_min_interval_sync:
                msg = f"Sync is not available, last sync was {delta} s ago, but it should have taken at least {runtime.get().pu_instance_repo_min_interval_sync} s"
                raise RepoError(msg, code=ErrorCode.REPO_SYNC_TOO_SOON)

    @staticmethod
    def is_valid_repo_size(
        repo_size: int, delete_path: str | None = None
    ) -> None:
        if (
            repo_size < 0
            or repo_size > runtime.get().pu_instance_repo_max_size * 2**20
        ):
            if delete_path:
                shutil.rmtree(delete_path, ignore_errors=True)

            msg = f"No valid external repo size {round(repo_size / 2**20, 2)} MB, max {runtime.get().pu_instance_repo_max_size} MB"
            raise GitRepoError(msg, code=ErrorCode.GIT_REPO_TOO_LARGE)

    def mapper_repo_to_repo_read(
        self, repo: Repo, child_unit_count: int
    ) -> RepoRead:
        try:
            branches = self.git_repo_repository.get_branches(repo)
        except Exception:
            branches = []

        return RepoRead(
            branches=branches,
            child_unit_count=child_unit_count,
            **repo.dict(),
        )
