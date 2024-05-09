import json
from typing import Union

from fastapi import Depends
from sqlmodel import Session

from app.configs.db import get_session
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
)
from app.schemas.pydantic.unit import UnitFilter
from app.services.access_service import AccessService
from app.services.unit_service import UnitService
from app.services.utils import creator_check, token_depends
from app.services.validators import is_valid_object, is_emtpy_sequence
from app.utils.utils import aes_encode


class RepoService:
    def __init__(self, db: Session = Depends(get_session),
        jwt_token: str = Depends(token_depends)) -> None:
        self.repo_repository = RepoRepository(db)
        self.git_repo_repository = GitRepoRepository()
        self.unit_repository = UnitRepository(db)
        self.unit_service = UnitService(db)
        self.access_service = AccessService(db, jwt_token)

    def create(self, data: Union[RepoCreate, RepoCreateInput]) -> RepoRead:
        self.access_service.access_check([UserRole.USER, UserRole.ADMIN])

        self.repo_repository.is_valid_name(data.name)
        self.repo_repository.is_valid_repo_url(Repo(repo_url=data.repo_url))
        self.repo_repository.is_valid_private_repo(data)

        repo = Repo(creator_uuid=self.access_service.current_agent.uuid, **data.dict())

        if not repo.is_public_repository:
            repo.cipher_credentials_private_repository = aes_encode(json.dumps(data.credentials.dict()))

        repo = self.repo_repository.create(repo)

        self.git_repo_repository.clone_remote_repo(repo, data)

        return self.mapper_repo_to_repo_read(repo)

    def get(self, uuid: str) -> RepoRead:
        self.access_service.access_check([UserRole.BOT, UserRole.USER, UserRole.ADMIN])
        repo = self.repo_repository.get(Repo(uuid=uuid))
        is_valid_object(repo)
        return self.mapper_repo_to_repo_read(repo)

    def get_branch_commits(self, uuid: str, filters: Union[CommitFilter, CommitFilterInput]) -> list[CommitRead]:
        self.access_service.access_check([UserRole.BOT, UserRole.USER, UserRole.ADMIN])

        repo = self.repo_repository.get(Repo(uuid=uuid))

        self.git_repo_repository.is_valid_branch(repo, filters.repo_branch)

        commits_with_tag = self.git_repo_repository.get_commits_with_tag(repo, filters.repo_branch)

        return [CommitRead(**item) for item in commits_with_tag][filters.offset : filters.offset + filters.limit]

    def update(self, uuid: str, data: Union[RepoUpdate, RepoUpdateInput]) -> RepoRead:
        self.access_service.access_check([UserRole.USER, UserRole.ADMIN])

        repo = self.repo_repository.get(Repo(uuid=uuid))

        is_valid_object(repo)
        creator_check(self.access_service.current_agent, repo)
        self.repo_repository.is_valid_name(data.name, uuid)

        repo = self.repo_repository.update(uuid, repo)

        return self.mapper_repo_to_repo_read(repo)

    def update_credentials(self, uuid: str, data: Union[Credentials, CredentialsInput]) -> RepoRead:
        self.access_service.access_check([UserRole.BOT, UserRole.USER, UserRole.ADMIN])

        repo = self.repo_repository.get(Repo(uuid=uuid))
        is_valid_object(repo)
        creator_check(self.access_service.current_agent, repo)
        self.repo_repository.is_private_repository(repo)

        repo.cipher_credentials_private_repository = aes_encode(json.dumps(data.dict()))
        repo = self.repo_repository.update(uuid, repo)

        return self.mapper_repo_to_repo_read(repo)

    def update_default_branch(self, uuid: str, default_branch: str) -> RepoRead:
        self.access_service.access_check([UserRole.BOT, UserRole.USER, UserRole.ADMIN])

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

        self.git_repo_repository.update_local_repo(repo)

        return None

    def update_units_firmware(self, uuid: str) -> None:
        repo = self.repo_repository.get(Repo(uuid=uuid))

        is_valid_object(repo)
        creator_check(self.access_service.current_agent, repo)

        units = self.unit_repository.list(UnitFilter(repo_uuid=str(repo.uuid)))

        target_version = self.git_repo_repository.get_target_version(repo)

        self.git_repo_repository.is_valid_schema_file(repo, target_version)
        self.git_repo_repository.get_env_dict(repo, target_version)

        for unit in units:
            if unit.is_auto_update_from_repo_unit and unit.current_commit_version != target_version:
                # todo здесь должна быть очередь
                print('kek')
                self.unit_service.update_firmware(unit, target_version)

    def delete(self, uuid: str) -> None:
        self.access_service.access_check([UserRole.USER, UserRole.ADMIN])

        repo = self.repo_repository.get(Repo(uuid=uuid))

        is_valid_object(repo)
        unit_list = self.unit_repository.list(UnitFilter(repo_uuid=uuid))
        is_emtpy_sequence(unit_list)
        creator_check(self.access_service.current_agent, repo)

        return self.repo_repository.delete(repo)

    def list(self, filters: Union[RepoFilter, RepoFilterInput]) -> list[RepoRead]:
        self.access_service.access_check([UserRole.ADMIN, UserRole.USER])
        return [self.mapper_repo_to_repo_read(repo) for repo in self.repo_repository.list(filters)]

    def mapper_repo_to_repo_read(self, repo: Repo) -> RepoRead:
        repo = self.repo_repository.get(repo)
        branches = self.git_repo_repository.get_branches(repo)
        is_credentials_set = bool(repo.cipher_credentials_private_repository)
        return RepoRead(branches=branches, is_credentials_set=is_credentials_set, **repo.dict())
