from typing import Optional

from fastapi import Depends
from fastapi_filter.contrib.sqlalchemy import Filter
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.domain.repo_model import Repo
from app.repositories.enum import VisibilityLevel, OrderByDate
from app.repositories.utils import apply_ilike_search_string, apply_enums, apply_offset_and_limit, apply_orders_by


class RepoFilter(Filter):
    """Фильтр выборки репозиториев"""

    search_string: Optional[str] = None

    is_public_repository: Optional[bool] = None
    is_auto_update_repo: Optional[bool] = None

    visibility_level: Optional[VisibilityLevel] = None

    order_by_create_date: Optional[OrderByDate] = OrderByDate.desc
    order_by_last_update: Optional[OrderByDate] = OrderByDate.desc

    offset: Optional[int] = None
    limit: Optional[int] = None


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
        return repo

    def delete(self, repo: Repo) -> None:
        self.db.delete(repo)
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
