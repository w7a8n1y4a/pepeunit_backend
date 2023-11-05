from fastapi import Depends, HTTPException
from sqlmodel import Session, select, func, or_, asc, desc

from app.core.auth.unit_auth import generate_unit_access_token
from fastapi import status as http_status
from app.core.db import get_session
from app.modules.repo.sql_models import Repo
from app.modules.unit.api_models import UnitCreate, UnitRead
from app.modules.unit.sql_models import Unit
from app.modules.unit.utils import program_link_generation
from app.modules.unit.validators import is_valid_name, is_valid_no_updated_unit
from app.modules.user.sql_models import User
from app.utils.validators import is_valid_object


def create(data: UnitCreate, user: User, db: Session = Depends(get_session)) -> UnitRead:
    """Создание репозитория"""

    is_valid_name(data.name, db)

    repo = db.get(Repo, data.repo_uuid)
    is_valid_object(repo)

    is_valid_no_updated_unit(repo, data)

    unit = Unit(creator_uuid=user.uuid,
                **data.dict())

    db.add(unit)
    db.commit()
    db.refresh(unit)

    return UnitRead(
        unit_program_url=program_link_generation(unit),
        **unit.dict()
    )


async def get_auth(unit: Unit, db):

    print(unit.dict())

    return True


async def get_auth_acl(data, unit: Unit, db):

    # todo права доступа на отдельные топики, мб стоит научиться обновлять acl лист на mosquitto

    print(await data.json())

    return True
