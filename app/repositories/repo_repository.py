
from fastapi import Depends
from fastapi import HTTPException
from fastapi import status as http_status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.domain.repo_model import Repo
from app.repositories.utils import apply_ilike_search_string, apply_enums, apply_offset_and_limit, apply_orders_by
from app.schemas.pydantic.repo import RepoFilter, RepoCreate, RepoUpdate


class RepoRepository:
    db: Session

    def __init__(
        self, db: Session = Depends(get_session)
    ) -> None:
        self.db = db

    def create(self, repo: Repo) -> Repo:
        self.db.add(repo)
        self.db.commit()
        self.db.refresh(repo)
        return repo

    def get(self, repo: Repo) -> Repo:
        return self.db.get(Repo, repo.uuid)

    def update(self, uuid, repo: Repo) -> Repo:
        repo.uuid = uuid
        self.db.merge(repo)
        self.db.commit()
        return self.get(repo)

    def delete(self, repo: Repo) -> None:
        self.db.delete(self.get(repo))
        self.db.commit()
        self.db.flush()

    def list(self, filters: RepoFilter) -> list[Repo]:
        query = self.db.query(Repo)

        fields = [Repo.name, Repo.repo_url, Repo.default_branch]
        query = apply_ilike_search_string(query, filters, fields)

        fields = {'visibility_level': Repo.visibility_level}
        query = apply_enums(query, filters, fields)

        fields = {
            'order_by_create_date': Repo.create_datetime,
            'order_by_last_update': Repo.last_update_datetime
        }
        query = apply_orders_by(query, filters, fields)

        query = apply_offset_and_limit(query, filters)
        return query.all()

    def is_valid_name(self, name: str, uuid: str = None):
        repo_uuid = self.db.exec(select(Repo.uuid).where(Repo.name == name)).first()
        repo_uuid = str(repo_uuid) if repo_uuid else repo_uuid

        if (uuid is None and repo_uuid) or (uuid and repo_uuid != uuid and repo_uuid is not None):
            raise HTTPException(status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Name is not unique")

    @staticmethod
    def is_valid_repo_url(repo: Repo):
        url = repo.repo_url
        if url[-4:] != '.git' and not (url.find('https://') == 0 or url.find('http://') == 0):
            raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=f"No valid repo_url")

    @staticmethod
    def is_valid_private_repo(data: RepoCreate or RepoUpdate):
        if not data.is_public_repository and (
                not data.credentials or (not data.credentials.username or not data.credentials.pat_token)):
            raise HTTPException(status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"No valid credentials")

    @staticmethod
    def is_private_repository(repo: Repo):
        if repo.is_public_repository:
            raise HTTPException(status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Is public repo")
