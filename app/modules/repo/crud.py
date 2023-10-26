import json

from fastapi import Depends, HTTPException
from fastapi import status as http_status
from sqlmodel import Session, select, func, or_, asc, desc

from app.core.db import get_session
from app.modules.repo.api_models import RepoCreate, RepoRead
from app.modules.repo.sql_models import Repo
from app.modules.repo.utils import clone_remote_repo, get_branches_repo, get_url_for_clone
from app.modules.repo.validators import is_valid_name, is_valid_private_repo, is_valid_repo_url
from app.modules.user.sql_models import User
from app.utils.utils import aes_encode


def create(data: RepoCreate, user: User, db: Session = Depends(get_session)) -> RepoRead:
    """Создание репозитория"""

    is_valid_name(data.name, db)
    is_valid_repo_url(data.repo_url)
    is_valid_private_repo(data)

    repo = Repo(creator_uuid=user.uuid, **data.dict())

    if not repo.is_public_repository:
        print(data.credentials.dict())
        repo.cipher_credentials_private_repository = aes_encode(json.dumps(data.credentials.dict()))

    git_repo = clone_remote_repo(repo, get_url_for_clone(data))

    db.add(repo)
    db.commit()
    db.refresh(repo)

    return RepoRead(
        is_credentials_set=bool(repo.cipher_credentials_private_repository),
        branches=get_branches_repo(git_repo),
        **repo.dict()
    )
