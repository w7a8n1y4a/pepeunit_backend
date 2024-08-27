import json
import logging
import uuid as uuid_pkg
from typing import Union

from fastapi import Depends

from app.domain.repo_model import Repo
from app.repositories.enum import UserRole, PermissionEntities
from app.repositories.git_repo_repository import GitRepoRepository
from app.repositories.repo_repository import RepoRepository
from app.repositories.unit_repository import UnitRepository
from app.schemas.gql.inputs.repo import (
    RepoUpdateInput,
    RepoFilterInput,
    RepoCreateInput,
    CredentialsInput,
    CommitFilterInput,
)
from app.schemas.pydantic.repo import (
    RepoCreate,
    RepoUpdate,
    RepoFilter,
    RepoRead,
    Credentials,
    CommitRead,
    CommitFilter,
    RepoVersionsRead,
)
from app.schemas.pydantic.unit import UnitFilter
from app.services.access_service import AccessService
from app.services.unit_service import UnitService
from app.services.utils import remove_none_value_dict, merge_two_dict_first_priority
from app.services.validators import is_valid_object, is_emtpy_sequence
from app.utils.utils import aes_encode, aes_decode


class RepoService:

    def __init__(
        self,
        repo_repository: RepoRepository = Depends(),
        unit_repository: UnitRepository = Depends(),
        unit_service: UnitService = Depends(),
        access_service: AccessService = Depends(),
    ) -> None:
        self.repo_repository = repo_repository
        self.git_repo_repository = GitRepoRepository()
        self.unit_repository = unit_repository
        self.unit_service = unit_service
        self.access_service = access_service

    def create(self, data: Union[RepoCreate, RepoCreateInput]) -> RepoRead:
        self.access_service.access_check([UserRole.USER, UserRole.ADMIN])

        self.repo_repository.is_valid_name(data.name)
        self.repo_repository.is_valid_repo_url(Repo(repo_url=data.repo_url))
        self.repo_repository.is_valid_private_repo(data)

        repo = Repo(creator_uuid=self.access_service.current_agent.uuid, **data.dict())

        if not repo.is_public_repository:
            repo.cipher_credentials_private_repository = aes_encode(json.dumps(data.credentials.dict()))

        repo = self.repo_repository.create(repo)

        self.git_repo_repository.clone_remote_repo(repo, data.credentials)

        self.access_service.create_permission(self.access_service.current_agent, repo)

        return self.mapper_repo_to_repo_read(repo)

    def get(self, uuid: uuid_pkg.UUID) -> RepoRead:
        self.access_service.access_check([UserRole.BOT, UserRole.USER, UserRole.ADMIN])
        repo = self.repo_repository.get(Repo(uuid=uuid))
        is_valid_object(repo)
        self.access_service.visibility_check(repo)
        return self.mapper_repo_to_repo_read(repo)

    def get_branch_commits(
        self, uuid: uuid_pkg.UUID, filters: Union[CommitFilter, CommitFilterInput]
    ) -> list[CommitRead]:
        self.access_service.access_check([UserRole.USER, UserRole.ADMIN])

        repo = self.repo_repository.get(Repo(uuid=uuid))
        is_valid_object(repo)
        self.access_service.visibility_check(repo)

        self.git_repo_repository.is_valid_branch(repo, filters.repo_branch)

        commits_with_tag = (
            self.git_repo_repository.get_tags(repo, filters.repo_branch)
            if filters.only_tag
            else self.git_repo_repository.get_commits_with_tag(repo, filters.repo_branch)
        )

        return [CommitRead(**item) for item in commits_with_tag][filters.offset : filters.offset + filters.limit]

    def get_versions(self, uuid: uuid_pkg.UUID) -> RepoVersionsRead:
        self.access_service.access_check([UserRole.BOT, UserRole.USER, UserRole.ADMIN])

        repo = self.repo_repository.get(Repo(uuid=uuid))
        is_valid_object(repo)
        self.access_service.visibility_check(repo)

        return self.repo_repository.get_versions(Repo(uuid=uuid))

    def update(self, uuid: uuid_pkg.UUID, data: Union[RepoUpdate, RepoUpdateInput]) -> RepoRead:
        self.access_service.access_check([UserRole.USER, UserRole.ADMIN])

        repo = self.repo_repository.get(Repo(uuid=uuid))
        is_valid_object(repo)

        self.access_service.access_creator_check(repo)

        if data.name:
            self.repo_repository.is_valid_name(data.name, uuid)

        if data.default_branch:
            self.git_repo_repository.is_valid_branch(repo, data.default_branch)

        repo_update_dict = merge_two_dict_first_priority(remove_none_value_dict(data.dict()), repo.dict())

        update_repo = Repo(**repo_update_dict)

        if data.default_commit:
            self.git_repo_repository.is_valid_commit(repo, update_repo.default_branch, data.default_commit)

        self.repo_repository.is_valid_auto_updated_repo(update_repo)
        self.repo_repository.is_valid_no_auto_updated_repo(update_repo)

        repo = self.repo_repository.update(uuid, update_repo)

        if not repo.is_auto_update_repo and repo.default_commit is not None and repo.default_branch is not None:
            self.update_units_firmware(repo.uuid, is_auto_update=True)

        return self.mapper_repo_to_repo_read(repo)

    def update_credentials(self, uuid: uuid_pkg.UUID, data: Union[Credentials, CredentialsInput]) -> RepoRead:
        self.access_service.access_check([UserRole.USER, UserRole.ADMIN])

        repo = self.repo_repository.get(Repo(uuid=uuid))
        is_valid_object(repo)

        self.access_service.access_creator_check(repo)
        self.repo_repository.is_private_repository(repo)

        repo.cipher_credentials_private_repository = aes_encode(json.dumps(data.dict()))
        repo = self.repo_repository.update(uuid, repo)

        self.git_repo_repository.update_credentials(repo, data)

        return self.mapper_repo_to_repo_read(repo)

    def update_default_branch(self, uuid: uuid_pkg.UUID, default_branch: str) -> RepoRead:
        self.access_service.access_check([UserRole.USER, UserRole.ADMIN])

        repo = self.repo_repository.get(Repo(uuid=uuid))
        is_valid_object(repo)

        self.access_service.access_creator_check(repo)
        self.git_repo_repository.is_valid_branch(repo, default_branch)

        repo.default_branch = default_branch
        repo = self.repo_repository.update(uuid, repo)

        return self.mapper_repo_to_repo_read(repo)

    def update_local_repo(self, uuid: uuid_pkg.UUID) -> None:
        self.access_service.access_check([UserRole.USER, UserRole.ADMIN])

        repo = self.repo_repository.get(Repo(uuid=uuid))
        is_valid_object(repo)

        self.access_service.access_creator_check(repo)

        data = self.repo_repository.get_credentials(repo)
        self.git_repo_repository.update_local_repo(repo, data)

        return None

    def update_units_firmware(self, uuid: uuid_pkg.UUID, is_auto_update: bool = False) -> None:

        if not is_auto_update:
            self.access_service.access_check([UserRole.USER, UserRole.ADMIN])

        repo = self.repo_repository.get(Repo(uuid=uuid))
        is_valid_object(repo)

        if not is_auto_update:
            self.access_service.access_creator_check(repo)

        target_version = self.git_repo_repository.get_target_version(repo)

        self.git_repo_repository.is_valid_schema_file(repo, target_version)
        self.git_repo_repository.get_env_dict(repo, target_version)

        units = self.unit_repository.list(UnitFilter(repo_uuid=repo.uuid, is_auto_update_from_repo_unit=True))

        logging.info(f'{len(units)} units candidates update launched')

        count_with_valid_version = 0
        count_error_update = 0
        count_success_update = 0
        for unit in units:
            if unit.current_commit_version != target_version:

                logging.info(f'Run update unit {unit.uuid}')

                try:
                    self.git_repo_repository.is_valid_env_file(
                        repo, target_version, json.loads(aes_decode(unit.cipher_env_dict))
                    )
                    self.unit_service.update_firmware(unit, target_version)
                except:
                    logging.warning(f'Failed update unit {unit.uuid}')
                    count_error_update += 1

                count_success_update += 1
                logging.info(f'Successfully update unit {unit.uuid}')

            else:
                count_with_valid_version += 1

        result = {
            'repo': repo.uuid,
            'count_with_valid_version': count_with_valid_version,
            'count_success_update': count_success_update,
            'count_error_update': count_error_update,
        }

        logging.info(result)

    def bulk_update_repositories(self, is_auto_update: bool = False) -> None:
        if not is_auto_update:
            self.access_service.access_check([UserRole.ADMIN])

        auto_update_repositories = self.repo_repository.list(RepoFilter(is_auto_update_repo=True))
        logging.info(f'{len(auto_update_repositories)} repos update launched')

        for repo in auto_update_repositories:
            logging.info(f'run update repo {repo.uuid}')

            try:
                self.update_units_firmware(repo.uuid, is_auto_update=True)
            except:
                logging.info(f'failed update repo {repo.uuid}')

        logging.info('task auto update repo successfully completed')

    def delete(self, uuid: uuid_pkg.UUID) -> None:
        self.access_service.access_check([UserRole.USER, UserRole.ADMIN])

        repo = self.repo_repository.get(Repo(uuid=uuid))
        is_valid_object(repo)

        self.access_service.access_creator_check(repo)

        unit_list = self.unit_repository.list(UnitFilter(repo_uuid=uuid))
        is_emtpy_sequence(unit_list)

        self.git_repo_repository.delete_repo(repo)
        self.repo_repository.delete(repo)

        return None

    def list(self, filters: Union[RepoFilter, RepoFilterInput]) -> list[RepoRead]:
        self.access_service.access_check([UserRole.BOT, UserRole.ADMIN, UserRole.USER])
        restriction = self.access_service.access_restriction(resource_type=PermissionEntities.REPO)

        filters.visibility_level = self.access_service.get_available_visibility_levels(
            filters.visibility_level, restriction
        )
        return [
            self.mapper_repo_to_repo_read(repo) for repo in self.repo_repository.list(filters, restriction=restriction)
        ]

    def mapper_repo_to_repo_read(self, repo: Repo) -> RepoRead:
        repo = self.repo_repository.get(repo)
        branches = self.git_repo_repository.get_branches(repo)
        return RepoRead(branches=branches, **repo.dict())
