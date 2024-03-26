import json
from typing import Union

from fastapi import Depends

from app.domain.repo_model import Repo
from app.repositories.enum import UserRole
from app.repositories.git_repo_repository import GitRepoRepository
from app.repositories.repo_repository import RepoRepository
from app.repositories.user_repository import UserRepository
from app.schemas.gql.inputs.repo import RepoUpdateInput, RepoFilterInput, RepoCreateInput
from app.schemas.pydantic.repo import RepoCreate, RepoUpdate, RepoFilter
from app.services.access_service import AccessService
from app.services.utils import creator_check
from app.services.validators import is_valid_object
from app.utils.utils import aes_encode


class RepoService:

    repo_repository = RepoRepository()
    git_repo_repository = GitRepoRepository()
    access_service = AccessService()

    def __init__(
        self,
        repo_repository: UserRepository = Depends(),
        access_service: AccessService = Depends()
    ) -> None:
        self.user_repository = repo_repository
        self.access_service = access_service

    def create(self, data: Union[RepoCreate, RepoCreateInput]) -> Repo:
        self.access_service.access_check([UserRole.USER, UserRole.ADMIN])

        self.repo_repository.is_valid_name(data.name)
        self.repo_repository.is_valid_repo_url(Repo(repo_url=data.repo_url))
        self.repo_repository.is_valid_private_repo(data)

        repo = Repo(creator_uuid=self.access_service.current_user.uuid, **data.dict())

        if not repo.is_public_repository:
            repo.cipher_credentials_private_repository = aes_encode(json.dumps(data.credentials.dict()))

        self.git_repo_repository.clone_remote_repo(repo, data)

        return self.repo_repository.create(repo)

    def get(self, uuid: str) -> Repo:
        self.access_service.access_check([UserRole.BOT, UserRole.USER, UserRole.ADMIN])
        repo = self.repo_repository.get(Repo(uuid=uuid))
        is_valid_object(repo)
        return repo

    def update(self, uuid: str, data: Union[RepoUpdate, RepoUpdateInput]) -> Repo:
        self.access_service.access_check([UserRole.USER, UserRole.ADMIN])

        repo = self.repo_repository.get(Repo(uuid=uuid))

        is_valid_object(repo)
        creator_check(self.access_service.current_user, repo)
        self.repo_repository.is_valid_name(data.name, uuid)

        return self.repo_repository.update(uuid, repo)

    def delete(self, uuid: str) -> None:
        self.access_service.access_check([UserRole.User, UserRole.ADMIN])

        repo = self.repo_repository.get(Repo(uuid=uuid))
        creator_check(self.access_service.current_user, repo)

        return self.repo_repository.delete(repo)

    def list(self, filters: Union[RepoFilter, RepoFilterInput]) -> list[Repo]:
        self.access_service.access_check([UserRole.ADMIN])
        return self.repo_repository.list(filters)

