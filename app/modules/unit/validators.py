from fastapi import HTTPException
from fastapi import status as http_status
from sqlmodel import Session, select, func

from app.modules.repo.sql_models import Repo
from app.modules.repo.validators import is_valid_branch, is_valid_commit
from app.modules.unit.api_models import UnitCreate
from app.modules.unit.sql_models import Unit


def is_valid_name(name: str, db: Session, update: bool = False, update_uuid: str = ''):
    unit = db.exec(select(Unit.uuid).where(Unit.name == name)).first()

    if (unit and not update) or (unit and update and unit.uuid != update_uuid):
        raise HTTPException(status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Name is not unique")


def is_valid_no_updated_unit(repo: Repo, data: UnitCreate):
    """ Для unit которые не обновляются автоматически, ветка и коммит должны быть указаны и при этом не None """
    if not data.is_auto_update_from_repo_unit and (not data.repo_branch or not data.repo_commit):
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=f"No valid no auto updated unit")

    # проверка чтобы ветка и коммит существовали у репозитория
    if not data.is_auto_update_from_repo_unit:
        is_valid_branch(repo, data.repo_branch)
        is_valid_commit(repo, data.repo_branch, data.repo_commit)
