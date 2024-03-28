from typing import Union

from fastapi import Depends
from fastapi import HTTPException
from fastapi import status as http_status

from app.domain.repo_model import Repo
from app.domain.unit_model import Unit
from app.repositories.enum import UserRole
from app.repositories.git_repo_repository import GitRepoRepository
from app.repositories.repo_repository import RepoRepository
from app.repositories.unit_repository import UnitRepository
from app.schemas.gql.inputs.unit import UnitCreateInput, UnitUpdateInput, UnitFilterInput
from app.schemas.pydantic.unit import UnitCreate, UnitUpdate, UnitFilter
from app.services.access_service import AccessService
from app.services.utils import creator_check
from app.services.validators import is_valid_object


class UnitService:
    unit_repository = UnitRepository()
    repo_repository = RepoRepository()
    git_repo_repository = GitRepoRepository()
    access_service = AccessService()

    def __init__(
        self,
        unit_repository: UnitRepository = Depends(),
        repo_repository: RepoRepository = Depends(),
        access_service: AccessService = Depends(),
    ) -> None:
        self.unit_repository = unit_repository
        self.repo_repository = repo_repository
        self.access_service = access_service

    def create(self, data: Union[UnitCreate, UnitCreateInput]) -> Unit:
        self.access_service.access_check([UserRole.USER, UserRole.ADMIN])

        self.unit_repository.is_valid_name(data.name)

        repo = self.repo_repository.get(Repo(uuid=data.repo_uuid))

        is_valid_object(repo)

        # todo проверка, что репозиторий готов отстыковать от себя unit, мб флажок в RepoRead и RepoType

        self.is_valid_no_updated_unit(repo, data)

        unit = Unit(creator_uuid=self.access_service.current_agent.uuid, **data.dict())

        return self.unit_repository.create(unit)

    def get(self, uuid: str) -> Unit:
        self.access_service.access_check([UserRole.BOT, UserRole.USER, UserRole.ADMIN])
        unit = self.unit_repository.get(Unit(uuid=uuid))
        is_valid_object(unit)
        return unit

    def generate_token(self, uuid: str) -> str:
        unit = self.unit_repository.get(Unit(uuid=uuid))
        is_valid_object(unit)

        return self.access_service.generate_unit_token(unit)

    def update(self, uuid: str, data: Union[UnitUpdate, UnitUpdateInput]) -> Unit:
        self.access_service.access_check([UserRole.USER, UserRole.ADMIN])

        unit = self.unit_repository.get(Unit(uuid=uuid))

        is_valid_object(unit)
        creator_check(self.access_service.current_agent, unit)

        repo = self.repo_repository.get(Repo(uuid=unit.repo_uuid))
        self.is_valid_no_updated_unit(repo, data)

        self.unit_repository.is_valid_name(data.name, uuid)

        return self.unit_repository.update(uuid, unit)

    # todo update_cipher_env - часть заполнится руками, часть автоматически - принимает json

    # todo set_unit_state - чтобы юниты у которых нет mqtt могли по http всё сделать
    """
    todo get_generate_programm - zip с прошивкой готовой к установке на устройство. Удаляет из репозитория всё лишнее
    сначала копирует репозиторий в tmp, и только потом производит действия
    """

    def delete(self, uuid: str) -> None:
        self.access_service.access_check([UserRole.USER, UserRole.ADMIN])

        unit = self.unit_repository.get(Unit(uuid=uuid))
        creator_check(self.access_service.current_agent, unit)

        return self.unit_repository.delete(unit)

    def list(self, filters: Union[UnitFilter, UnitFilterInput]) -> list[Unit]:
        self.access_service.access_check([UserRole.ADMIN])
        return self.unit_repository.list(filters)

    def is_valid_no_updated_unit(self, repo: Repo, data: UnitCreate):
        if not data.is_auto_update_from_repo_unit and (not data.repo_branch or not data.repo_commit):
            raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=f"No valid no auto updated unit")

        # проверка чтобы ветка и коммит существовали у репозитория
        if not data.is_auto_update_from_repo_unit:
            self.git_repo_repository.is_valid_branch(repo, data.repo_branch)
            self.git_repo_repository.is_valid_commit(repo, data.repo_branch, data.repo_commit)
