import json

from fastapi import Depends, HTTPException
from fastapi import status as http_status
from sqlmodel import Session, select, func, or_, asc, desc

from app.core.db import get_session
from app.modules.repo.api_models import RepoCreate, RepoRead, Credentials
from app.modules.repo.sql_models import Repo
from app.modules.repo.utils import clone_remote_repo, get_branches_repo, get_url_for_clone, get_repo
from app.modules.repo.validators import is_valid_name, is_valid_private_repo, is_valid_repo_url, is_private_repository, \
    is_valid_branch
from app.modules.user.sql_models import User
from app.utils.access import creator_check
from app.utils.utils import aes_encode
from app.utils.validators import is_valid_object


def create(data: RepoCreate, user: User, db: Session = Depends(get_session)) -> RepoRead:
    """Создание репозитория"""

    is_valid_name(data.name, db)
    is_valid_repo_url(data.repo_url)
    is_valid_private_repo(data)

    repo = Repo(creator_uuid=user.uuid, **data.dict())

    if not repo.is_public_repository:
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


def update_credentials_private(uuid: str, data: Credentials, user: User, db: Session = Depends(get_session)) -> RepoRead:

    repo = db.get(Repo, uuid)
    is_valid_object(repo)
    creator_check(user, repo)
    is_private_repository(repo)

    repo.cipher_credentials_private_repository = aes_encode(json.dumps(data.dict()))

    print(repo.cipher_credentials_private_repository)

    db.add(repo)
    db.commit()
    db.refresh(repo)

    git_repo = get_repo(repo.uuid)

    return RepoRead(
        is_credentials_set=bool(repo.cipher_credentials_private_repository),
        branches=get_branches_repo(git_repo),
        **repo.dict()
    )


def set_default_branch(uuid: str, default_branch: str, user: User, db: Session = Depends(get_session)) -> RepoRead:

    repo = db.get(Repo, uuid)
    is_valid_object(repo)
    creator_check(user, repo)
    is_private_repository(repo)
    is_valid_branch(repo, default_branch)

    repo.default_branch = default_branch

    db.add(repo)
    db.commit()
    db.refresh(repo)

    git_repo = get_repo(repo.uuid)

    return RepoRead(
        is_credentials_set=bool(repo.cipher_credentials_private_repository),
        branches=get_branches_repo(git_repo),
        **repo.dict()
    )
