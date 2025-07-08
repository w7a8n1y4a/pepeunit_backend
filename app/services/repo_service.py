import datetime
import json
import logging
import threading
import uuid as uuid_pkg
from typing import Union

from fastapi import Depends

from app.domain.repo_model import Repo
from app.domain.user_model import User
from app.dto.enum import AgentType, BackendTopicCommand, OwnershipType, PermissionEntities, UserRole
from app.repositories.git_repo_repository import GitRepoRepository
from app.repositories.repo_repository import RepoRepository
from app.repositories.unit_repository import UnitRepository
from app.schemas.gql.inputs.repo import (
    RepoCreateInput,
    RepoFilterInput,
    RepoUpdateInput,
)
from app.schemas.pydantic.repo import (
    RepoCreate,
    RepoFilter,
    RepoRead,
    RepoUpdate,
    RepoVersionsRead,
)
from app.schemas.pydantic.unit import UnitFilter
from app.services.access_service import AccessService
from app.services.permission_service import PermissionService
from app.services.thread import _process_bulk_update_units_firmware
from app.services.unit_service import UnitService
from app.services.utils import merge_two_dict_first_priority, remove_none_value_dict
from app.services.validators import is_emtpy_sequence, is_valid_object, is_valid_visibility_level
from app.utils.utils import aes_gcm_encode


class RepoService:

    def __init__(
        self,
        repo_repository: RepoRepository = Depends(),
        unit_repository: UnitRepository = Depends(),
        unit_service: UnitService = Depends(),
        permission_service: PermissionService = Depends(),
        access_service: AccessService = Depends(),
    ) -> None:
        self.repo_repository = repo_repository
        self.git_repo_repository = GitRepoRepository()
        self.unit_repository = unit_repository
        self.unit_service = unit_service
        self.permission_service = permission_service
        self.access_service = access_service

    def create(self, data: Union[RepoCreate, RepoCreateInput]) -> RepoRead:
        self.access_service.authorization.check_access([AgentType.USER])

        self.repo_repository.is_valid_name(data.name)

        repo = Repo(creator_uuid=self.access_service.current_agent.uuid, **data.dict())

        if not repo.is_public_repository:
            repo.cipher_credentials_private_repository = aes_gcm_encode(json.dumps(data.credentials.dict()))

        if repo.is_compilable_repo:
            repo.is_auto_update_repo = True
            repo.is_only_tag_update = True

        repo.create_datetime = datetime.datetime.utcnow()
        repo.last_update_datetime = repo.create_datetime
        repo = self.repo_repository.create(repo)

        self.permission_service.create_by_domains(User(uuid=self.access_service.current_agent.uuid), repo)

        return self.mapper_repo_to_repo_read(repo)

    def get(self, uuid: uuid_pkg.UUID) -> RepoRead:
        self.access_service.authorization.check_access([AgentType.BOT, AgentType.USER])
        repo = self.repo_repository.get(Repo(uuid=uuid))
        is_valid_object(repo)
        self.access_service.authorization.check_visibility(repo)
        return self.mapper_repo_to_repo_read(repo)

    def get_versions(self, uuid: uuid_pkg.UUID) -> RepoVersionsRead:
        self.access_service.authorization.check_access([AgentType.BOT, AgentType.USER])

        repo = self.repo_repository.get(Repo(uuid=uuid))
        is_valid_object(repo)
        self.access_service.authorization.check_visibility(repo)

        return self.repo_repository.get_versions(repo)

    def update(self, uuid: uuid_pkg.UUID, data: Union[RepoUpdate, RepoUpdateInput]) -> RepoRead:
        self.access_service.authorization.check_access([AgentType.USER])

        repo = self.repo_repository.get(Repo(uuid=uuid))
        is_valid_object(repo)

        self.access_service.authorization.check_ownership(repo, [OwnershipType.CREATOR])

        if data.name:
            self.repo_repository.is_valid_name(data.name, uuid)

        if data.default_branch:
            self.git_repo_repository.is_valid_branch(repo, data.default_branch)

        repo_update_dict = merge_two_dict_first_priority(remove_none_value_dict(data.dict()), repo.dict())

        update_repo = Repo(**repo_update_dict)
        update_repo.last_update_datetime = datetime.datetime.utcnow()

        count, child_units = self.unit_repository.list(filters=UnitFilter(repo_uuid=update_repo.uuid))
        is_valid_visibility_level(update_repo, [unit[0] for unit in child_units])

        if data.default_commit:
            self.git_repo_repository.is_valid_commit(repo, update_repo.default_branch, data.default_commit)

        self.repo_repository.is_valid_auto_updated_repo(update_repo)
        self.repo_repository.is_valid_no_auto_updated_repo(update_repo)
        self.repo_repository.is_valid_compilable_repo(update_repo)

        if update_repo.is_compilable_repo:
            update_repo.releases_data = json.dumps(self.git_repo_repository.get_releases(update_repo))

        repo = self.repo_repository.update(uuid, update_repo)

        if not repo.is_auto_update_repo and repo.default_commit is not None and repo.default_branch is not None:
            self.update_units_firmware(repo.uuid, is_auto_update=True)

        return self.mapper_repo_to_repo_read(repo)

    def update_default_branch(self, uuid: uuid_pkg.UUID, default_branch: str) -> RepoRead:
        self.access_service.authorization.check_access([AgentType.USER])

        repo = self.repo_repository.get(Repo(uuid=uuid))
        is_valid_object(repo)

        self.access_service.authorization.check_ownership(repo, [OwnershipType.CREATOR])
        self.git_repo_repository.is_valid_branch(repo, default_branch)

        repo.default_branch = default_branch
        repo.last_update_datetime = datetime.datetime.utcnow()
        repo = self.repo_repository.update(uuid, repo)

        return self.mapper_repo_to_repo_read(repo)

    def update_units_firmware(self, uuid: uuid_pkg.UUID, is_auto_update: bool = False) -> None:

        if not is_auto_update:
            self.access_service.authorization.check_access([AgentType.USER])

        repo = self.repo_repository.get(Repo(uuid=uuid))
        is_valid_object(repo)

        if not is_auto_update:
            self.access_service.authorization.check_ownership(repo, [OwnershipType.CREATOR])

        count, units = self.unit_repository.list(UnitFilter(repo_uuid=repo.uuid, is_auto_update_from_repo_unit=True))

        logging.info(f'{len(units)} units candidates update launched')

        count_error_update = 0
        count_success_update = 0
        for unit in [unit[0] for unit in units]:

            logging.info(f'Run update unit {unit.uuid}')

            try:
                unit = self.unit_service.sync_state_unit_nodes_for_version(unit, repo)
                self.unit_service.unit_node_service.command_to_input_base_topic(
                    uuid=unit.uuid, command=BackendTopicCommand.UPDATE, is_auto_update=True
                )
                logging.info(f'Successfully update unit {unit.uuid}')
                count_success_update += 1
            except Exception as e:
                logging.warning(f'Failed update unit {unit.uuid} {e}')
                count_error_update += 1

        result = {
            'repo': repo.uuid,
            'count_success_update': count_success_update,
            'count_error_update': count_error_update,
        }

        logging.info(result)

    def bulk_update_units_firmware(self, is_auto_update: bool = False) -> None:
        if not is_auto_update:
            self.access_service.authorization.check_access([AgentType.USER], [UserRole.ADMIN])

        threading.Thread(target=_process_bulk_update_units_firmware, daemon=True).start()

    def delete(self, uuid: uuid_pkg.UUID) -> None:
        self.access_service.authorization.check_access([AgentType.USER])

        repo = self.repo_repository.get(Repo(uuid=uuid))
        is_valid_object(repo)

        self.access_service.authorization.check_ownership(repo, [OwnershipType.CREATOR])

        count, unit_list = self.unit_repository.list(UnitFilter(repo_uuid=uuid))
        is_emtpy_sequence(unit_list)

        self.git_repo_repository.delete_repo(repo)
        self.repo_repository.delete(repo)

    def list(self, filters: Union[RepoFilter, RepoFilterInput]) -> tuple[int, list[RepoRead]]:
        self.access_service.authorization.check_access([AgentType.BOT, AgentType.USER])
        restriction = self.access_service.authorization.access_restriction(resource_type=PermissionEntities.REPO)

        filters.visibility_level = self.access_service.authorization.get_available_visibility_levels(
            filters.visibility_level, restriction
        )

        count, repos = self.repo_repository.list(filters, restriction=restriction)
        return count, [self.mapper_repo_to_repo_read(repo) for repo in repos]

    def mapper_repo_to_repo_read(self, repo: Repo) -> RepoRead:
        repo = self.repo_repository.get(repo)
        try:
            branches = self.git_repo_repository.get_branches(repo)
        except:
            branches = []

        return RepoRead(branches=branches, **repo.dict())
