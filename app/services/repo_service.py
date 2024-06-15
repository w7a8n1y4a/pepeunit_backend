import json
import logging
from typing import Union

from fastapi import Depends

from app.domain.repo_model import Repo
from app.repositories.enum import UserRole
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
from app.services.utils import creator_check, token_depends, remove_none_value_dict, merge_two_dict_first_priority
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

        return self.mapper_repo_to_repo_read(repo)

    def get(self, uuid: str) -> RepoRead:
        self.access_service.access_check([UserRole.BOT, UserRole.USER, UserRole.ADMIN])
        repo = self.repo_repository.get(Repo(uuid=uuid))
        is_valid_object(repo)
        self.access_service.visibility_check(repo)
        return self.mapper_repo_to_repo_read(repo)

    def get_branch_commits(self, uuid: str, filters: Union[CommitFilter, CommitFilterInput]) -> list[CommitRead]:
        self.access_service.access_check([UserRole.BOT, UserRole.USER, UserRole.ADMIN])

        repo = self.repo_repository.get(Repo(uuid=uuid))
        self.access_service.visibility_check(repo)

        self.git_repo_repository.is_valid_branch(repo, filters.repo_branch)

        commits_with_tag = self.git_repo_repository.get_commits_with_tag(repo, filters.repo_branch)

        return [CommitRead(**item) for item in commits_with_tag][filters.offset : filters.offset + filters.limit]

    def get_versions(self, uuid: str) -> RepoVersionsRead:
        self.access_service.access_check([UserRole.USER, UserRole.ADMIN])

        return self.repo_repository.get_versions(Repo(uuid=uuid))

    def update(self, uuid: str, data: Union[RepoUpdate, RepoUpdateInput]) -> RepoRead:
        self.access_service.access_check([UserRole.USER, UserRole.ADMIN])

        repo = self.repo_repository.get(Repo(uuid=uuid))

        is_valid_object(repo)
        creator_check(self.access_service.current_agent, repo)

        if data.name:
            self.repo_repository.is_valid_name(data.name, uuid)

        repo_update_dict = merge_two_dict_first_priority(remove_none_value_dict(data.dict()), repo.dict())
        repo = self.repo_repository.update(uuid, Repo(**repo_update_dict))

        return self.mapper_repo_to_repo_read(repo)

    def update_credentials(self, uuid: str, data: Union[Credentials, CredentialsInput]) -> RepoRead:
        self.access_service.access_check([UserRole.USER, UserRole.ADMIN])

        repo = self.repo_repository.get(Repo(uuid=uuid))
        is_valid_object(repo)
        creator_check(self.access_service.current_agent, repo)
        self.repo_repository.is_private_repository(repo)

        repo.cipher_credentials_private_repository = aes_encode(json.dumps(data.dict()))
        repo = self.repo_repository.update(uuid, repo)

        self.git_repo_repository.update_credentials(repo, data)

        return self.mapper_repo_to_repo_read(repo)

    def update_default_branch(self, uuid: str, default_branch: str) -> RepoRead:
        self.access_service.access_check([UserRole.USER, UserRole.ADMIN])

        repo = self.repo_repository.get(Repo(uuid=uuid))
        is_valid_object(repo)
        creator_check(self.access_service.current_agent, repo)
        self.git_repo_repository.is_valid_branch(repo, default_branch)

        repo.default_branch = default_branch
        repo = self.repo_repository.update(uuid, repo)

        return self.mapper_repo_to_repo_read(repo)

    def update_local_repo(self, uuid: str) -> None:
        self.access_service.access_check([UserRole.USER, UserRole.ADMIN])

        repo = self.repo_repository.get(Repo(uuid=uuid))

        is_valid_object(repo)
        creator_check(self.access_service.current_agent, repo)

        data = self.repo_repository.get_credentials(repo)
        self.git_repo_repository.update_local_repo(repo, data)

        return None

    def update_units_firmware(self, uuid: str, is_auto_update: bool = False) -> None:

        if not is_auto_update:
            self.access_service.access_check([UserRole.USER, UserRole.ADMIN])

        repo = self.repo_repository.get(Repo(uuid=uuid))

        is_valid_object(repo)
        if not is_auto_update:
            creator_check(self.access_service.current_agent, repo)

        target_version = self.git_repo_repository.get_target_version(repo)

        self.git_repo_repository.is_valid_schema_file(repo, target_version)
        self.git_repo_repository.get_env_dict(repo, target_version)

        units = self.unit_repository.list(UnitFilter(repo_uuid=str(repo.uuid), is_auto_update_from_repo_unit=True))

        logging.info(f'{len(units)} nodes candidates update launched')

        count_with_valid_version = 0
        count_error_update = 0
        count_success_update = 0
        for unit in units:
            if unit.current_commit_version != target_version:

                logging.info(f'run update unit {unit.uuid}')

                try:
                    self.git_repo_repository.is_valid_env_file(
                        repo, target_version, json.loads(aes_decode(unit.cipher_env_dict))
                    )
                    self.unit_service.update_firmware(unit, target_version)
                except:
                    logging.info(f'failed update unit {unit.uuid}')
                    count_error_update += 1

                count_success_update += 1
                logging.info(f'successfully update unit {unit.uuid}')

            else:
                count_with_valid_version += 1

        result = {
            'repo': repo.uuid,
            'count_with_valid_version': count_with_valid_version,
            'count_success_update': count_success_update,
            'count_error_update': count_error_update,
        }

        logging.info(result)

    def delete(self, uuid: str) -> None:
        self.access_service.access_check([UserRole.USER, UserRole.ADMIN])

        repo = self.repo_repository.get(Repo(uuid=uuid))

        is_valid_object(repo)
        creator_check(self.access_service.current_agent, repo)

        unit_list = self.unit_repository.list(UnitFilter(repo_uuid=uuid))
        is_emtpy_sequence(unit_list)

        return self.repo_repository.delete(repo)

    def list(self, filters: Union[RepoFilter, RepoFilterInput]) -> list[RepoRead]:
        self.access_service.access_check([UserRole.BOT, UserRole.ADMIN, UserRole.USER])
        restriction = self.access_service.access_restriction()

        filters.visibility_level = self.access_service.get_available_visibility_levels(
            filters.visibility_level, restriction
        )
        return [
            self.mapper_repo_to_repo_read(repo) for repo in self.repo_repository.list(filters, restriction=restriction)
        ]

    def mapper_repo_to_repo_read(self, repo: Repo) -> RepoRead:
        repo = self.repo_repository.get(repo)
        branches = self.git_repo_repository.get_branches(repo)
        is_credentials_set = bool(repo.cipher_credentials_private_repository)
        return RepoRead(branches=branches, is_credentials_set=is_credentials_set, **repo.dict())
