from fastapi import HTTPException
from fastapi import status as http_status
from sqlmodel import Session, select, func

from app.modules.repo.api_models import RepoCreate, RepoUpdate
from app.modules.repo.sql_models import Repo
from app.modules.repo.utils import get_repo, get_branches_repo


def is_valid_name(name: str, db: Session, update: bool = False, update_uuid: str = ''):
    repo = db.exec(select(Repo.uuid).where(Repo.name == name)).first()

    if (repo and not update) or (repo and update and repo.uuid != update_uuid):
        raise HTTPException(status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Name is not unique")


def is_valid_repo_url(repo_url: str):
    if repo_url[-4:] != '.git' and not (repo_url.find('https://') == 0 or repo_url.find('http://') == 0):
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=f"No valid repo_url")


def is_valid_private_repo(data: RepoCreate or RepoUpdate):
    """ Для приватных репозиториев, должны быть переданы креды доступа. Если нет имени или токена, выдаём 400"""
    if not data.is_public_repository and (not data.credentials or (not data.credentials.username or not data.credentials.pat_token)):
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=f"No valid credentials")


def is_private_repository(repo: Repo):
    if repo.is_public_repository:
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=f"Is public repo")


def is_valid_branch(repo: Repo, branch: str):
    if branch not in get_branches_repo(get_repo(repo.uuid)):
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=f"No valid branch")

