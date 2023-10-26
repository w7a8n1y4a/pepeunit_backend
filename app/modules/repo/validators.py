import uuid

from fastapi import HTTPException
from fastapi import status as http_status
from sqlmodel import Session, select, func

from app.modules.repo.api_models import RepoCreate
from app.modules.repo.sql_models import Repo


def is_valid_name(name: str, db: Session):
    if db.exec(select(func.count(Repo.uuid)).where(Repo.name == name)).first():
        raise HTTPException(status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Name is not unique")


def is_valid_repo_url(repo_url: str):
    if repo_url[-4:] != '.git' and not (repo_url.find('https://') == 0 or repo_url.find('http://') == 0):
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=f"No valid repo_url")


def is_valid_private_repo(data: RepoCreate):
    """ Для приватных репозиториев, должны быть переданы креды доступа. Если нет имени или токена, выдаём 400"""
    if not data.is_public_repository and (not data.credentials or (not data.credentials.username or not data.credentials.pat_token)):
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=f"No valid credentials")

