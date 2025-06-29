import datetime
import json
import logging
import threading
import uuid as uuid_pkg
from typing import Optional, Union

from fastapi import Depends, HTTPException

from app.domain.repo_model import Repo
from app.domain.repository_registry_model import RepositoryRegistry
from app.domain.user_model import User
from app.dto.enum import AgentType, BackendTopicCommand, OwnershipType, PermissionEntities, UserRole
from app.repositories.git_local_repository import GitLocalRepository
from app.repositories.repo_repository import RepoRepository
from app.repositories.repository_registry_repository import RepositoryRegistryRepository
from app.repositories.unit_repository import UnitRepository
from app.schemas.gql.inputs.repo import (
    CommitFilterInput,
    CredentialsInput,
    RepoCreateInput,
    RepoFilterInput,
    RepoUpdateInput,
)
from app.schemas.pydantic.repo import (
    CommitFilter,
    CommitRead,
    Credentials,
    RepoCreate,
    RepoFilter,
    RepoRead,
    RepoUpdate,
    RepoVersionsRead,
)
from app.schemas.pydantic.unit import UnitFilter
from app.services.access_service import AccessService
from app.services.permission_service import PermissionService
from app.services.thread import _process_bulk_update_repositories
from app.services.unit_service import UnitService
from app.services.utils import merge_two_dict_first_priority, remove_none_value_dict, token_depends
from app.services.validators import is_emtpy_sequence, is_valid_json, is_valid_object, is_valid_visibility_level
from app.utils.utils import aes_gcm_encode


class RepoService:

    def __init__(
        self,
        repo_repository: RepoRepository = Depends(),
        repository_registry_repository: RepositoryRegistryRepository = Depends(),
        unit_repository: UnitRepository = Depends(),
        unit_service: UnitService = Depends(),
        permission_service: PermissionService = Depends(),
        access_service: AccessService = Depends(),
    ) -> None:
        self.repo_repository = repo_repository
        self.repository_registry_repository = repository_registry_repository
        self.git_local_repository = GitLocalRepository()
        self.unit_repository = unit_repository
        self.unit_service = unit_service
        self.permission_service = permission_service
        self.access_service = access_service

    def create(self, data: Union[RepoCreate, RepoCreateInput]) -> RepoRead:
        self.access_service.authorization.check_access([AgentType.USER])

        # check repository registry
        self.repository_registry_repository.is_valid_platform(RepositoryRegistry(platform=data.platform))
        exist_repository = self.repository_registry_repository.is_valid_url(
            RepositoryRegistry(repository_url=data.repository_url)
        )

        # get valid repository registry
        if exist_repository:
            repository_registry = exist_repository
        else:
            repository_registry = RepositoryRegistry(creator_uuid=self.access_service.current_agent.uuid, **data.dict())
            repository_registry.create_datetime = datetime.datetime.utcnow()
            repository_registry.last_update_datetime = repository_registry.create_datetime
            repository_registry = self.repository_registry_repository.create(repository_registry)

        # check repo
        self.repo_repository.is_valid_name(data.name)
        self.repo_repository.is_valid_private_repo(data)

        repo = Repo(
            creator_uuid=self.access_service.current_agent.uuid,
            repository_registry_uuid=repository_registry.uuid,
            **data.dict(),
        )

        if not repository_registry.is_public_repository:
            repo.cipher_credentials_private_repository = aes_gcm_encode(json.dumps(data.credentials.dict()))

        if repo.is_compilable_repo:
            repo.is_auto_update_repo = True
            repo.is_only_tag_update = True

        repo.create_datetime = datetime.datetime.utcnow()
        repo.last_update_datetime = repo.create_datetime
        repo = self.repo_repository.create(repo)
        self.permission_service.create_by_domains(User(uuid=self.access_service.current_agent.uuid), repo)

        self.git_local_repository.clone_remote_repo(repository_registry, repo)

        # set releases data for any repository
        repository_registry.releases_data = json.dumps(
            self.git_local_repository.get_releases(repository_registry, repo)
        )
        self.repository_registry_repository.update(repository_registry.uuid, repository_registry)

        return self.mapper_repo_to_repo_read(repo)

    def get(self, uuid: uuid_pkg.UUID) -> RepoRead:
        self.access_service.authorization.check_access([AgentType.BOT, AgentType.USER])
        repo = self.repo_repository.get(Repo(uuid=uuid))
        is_valid_object(repo)
        self.access_service.authorization.check_visibility(repo)
        return self.mapper_repo_to_repo_read(repo)

    def get_branch_commits(
        self, uuid: uuid_pkg.UUID, filters: Union[CommitFilter, CommitFilterInput]
    ) -> list[CommitRead]:
        self.access_service.authorization.check_access([AgentType.USER])

        repo = self.repo_repository.get(Repo(uuid=uuid))
        is_valid_object(repo)
        self.access_service.authorization.check_visibility(repo)

        self.git_local_repository.is_valid_branch(repo, filters.repo_branch)

        commits = self.git_local_repository.get_branch_commits_with_tag(repo, filters.repo_branch)

        commits_with_tag = self.git_local_repository.get_tags_from_all_commits(commits) if filters.only_tag else commits

        return [CommitRead(**item) for item in commits_with_tag][filters.offset : filters.offset + filters.limit]

    def get_available_platforms(
        self, uuid: uuid_pkg.UUID, target_commit: Optional[str] = None, target_tag: Optional[str] = None
    ) -> list[tuple[str, str]]:

        self.access_service.authorization.check_access([AgentType.USER])

        repo = self.repo_repository.get(Repo(uuid=uuid))
        is_valid_object(repo)
        self.access_service.authorization.check_visibility(repo)

        platforms = []
        if repo.is_compilable_repo and repo.releases_data:
            releases = is_valid_json(repo.releases_data, "releases for compile repo")

            if target_tag:
                try:
                    platforms = releases[target_tag]
                except KeyError:
                    pass
            elif target_commit:
                commits = self.git_local_repository.get_branch_commits_with_tag(repo, repo.default_branch)
                commit = self.git_local_repository.find_by_commit(commits, target_commit)
                if commit and commit.get('tag'):
                    platforms = releases[commit['tag']]
            else:
                target_commit, target_tag = self.git_local_repository.get_target_repo_version(repo)
                platforms = releases[target_tag]

        return platforms

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
            self.git_local_repository.is_valid_branch(repo, data.default_branch)

        repo_update_dict = merge_two_dict_first_priority(remove_none_value_dict(data.dict()), repo.dict())

        update_repo = Repo(**repo_update_dict)
        update_repo.last_update_datetime = datetime.datetime.utcnow()

        count, child_units = self.unit_repository.list(filters=UnitFilter(repo_uuid=update_repo.uuid))
        is_valid_visibility_level(update_repo, [unit[0] for unit in child_units])

        if data.default_commit:
            self.git_local_repository.is_valid_commit(repo, update_repo.default_branch, data.default_commit)

        self.repo_repository.is_valid_auto_updated_repo(update_repo)
        self.repo_repository.is_valid_no_auto_updated_repo(update_repo)
        self.repo_repository.is_valid_compilable_repo(update_repo)

        if update_repo.is_compilable_repo:
            update_repo.releases_data = json.dumps(self.git_local_repository.get_releases(update_repo))

        repo = self.repo_repository.update(uuid, update_repo)

        if not repo.is_auto_update_repo and repo.default_commit is not None and repo.default_branch is not None:
            self.update_units_firmware(repo.uuid, is_auto_update=True)

        return self.mapper_repo_to_repo_read(repo)

    def update_credentials(self, uuid: uuid_pkg.UUID, data: Union[Credentials, CredentialsInput]) -> RepoRead:
        self.access_service.authorization.check_access([AgentType.USER])

        repo = self.repo_repository.get(Repo(uuid=uuid))
        is_valid_object(repo)

        self.access_service.authorization.check_ownership(repo, [OwnershipType.CREATOR])
        self.repo_repository.is_private_repository(repo)

        repo.cipher_credentials_private_repository = aes_gcm_encode(json.dumps(data.dict()))

        if repo.is_compilable_repo:
            repo.releases_data = json.dumps(self.git_local_repository.get_releases(repo))

        repo.last_update_datetime = datetime.datetime.utcnow()
        repo = self.repo_repository.update(uuid, repo)

        self.git_local_repository.update_credentials(repo)

        return self.mapper_repo_to_repo_read(repo)

    def update_default_branch(self, uuid: uuid_pkg.UUID, default_branch: str) -> RepoRead:
        self.access_service.authorization.check_access([AgentType.USER])

        repo = self.repo_repository.get(Repo(uuid=uuid))
        is_valid_object(repo)

        self.access_service.authorization.check_ownership(repo, [OwnershipType.CREATOR])
        self.git_local_repository.is_valid_branch(repo, default_branch)

        repo.default_branch = default_branch
        repo.last_update_datetime = datetime.datetime.utcnow()
        repo = self.repo_repository.update(uuid, repo)

        return self.mapper_repo_to_repo_read(repo)

    def update_local_repo(self, uuid: uuid_pkg.UUID) -> None:
        self.access_service.authorization.check_access([AgentType.USER])

        repo = self.repo_repository.get(Repo(uuid=uuid))
        is_valid_object(repo)

        self.access_service.authorization.check_ownership(repo, [OwnershipType.CREATOR])

        if repo.is_compilable_repo:
            repo.releases_data = json.dumps(self.git_local_repository.get_releases(repo))

            repo = self.repo_repository.update(uuid, repo)

        self.git_local_repository.clone_remote_repo(repo)

        return None

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

    def bulk_update_repositories(self, is_auto_update: bool = False) -> None:
        if not is_auto_update:
            self.access_service.authorization.check_access([AgentType.USER], [UserRole.ADMIN])

        threading.Thread(target=_process_bulk_update_repositories, daemon=True).start()

        return None

    def sync_local_repo_storage(self) -> None:

        logging.info('run sync local repo storage')

        physic_repositories_registry = self.git_local_repository.get_current_repos()
        db_repositories_registry = self.repository_registry_repository.get_all()

        for repository_registry in db_repositories_registry:
            if str(repository_registry.uuid) not in physic_repositories_registry:
                try:

                    if repository_registry.is_public_repository:
                        repository_registry.releases_data = json.dumps(
                            self.git_local_repository.get_releases(repository_registry)
                        )

                        repository_registry = self.repository_registry_repository.update(
                            repository_registry.uuid, repository_registry
                        )

                        self.git_local_repository.clone_remote_repo(repository_registry)

                        logging.info(f'success load: {repository_registry.repository_url}')

                except HTTPException as e:
                    logging.warning(f'corrupt load: {repository_registry.repository_url} {e.detail}')

        logging.info('end sync local repo storage')

    def delete(self, uuid: uuid_pkg.UUID) -> None:
        self.access_service.authorization.check_access([AgentType.USER])

        repo = self.repo_repository.get(Repo(uuid=uuid))
        is_valid_object(repo)

        self.access_service.authorization.check_ownership(repo, [OwnershipType.CREATOR])

        count, unit_list = self.unit_repository.list(UnitFilter(repo_uuid=uuid))
        is_emtpy_sequence(unit_list)

        self.git_local_repository.delete_repo(repo)
        self.repo_repository.delete(repo)

        return None

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
            branches = self.git_local_repository.get_branches(repo)
        except:
            branches = []

        return RepoRead(branches=branches, **repo.dict())
