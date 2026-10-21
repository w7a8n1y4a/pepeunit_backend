from fastapi import Depends
from fastapi.params import Query
from sqlmodel import Session

from app.configs.db import get_session
from app.configs.error_codes import ErrorCode
from app.configs.errors import RepoError
from app.domain.repo_model import Repo
from app.dto.enum import GitPlatform, UuidEntity
from app.repositories.base_repository import BaseRepository
from app.repositories.utils import (
    apply_ilike_search_string,
    apply_offset_and_limit,
    apply_orders_by,
)
from app.schemas.pydantic.repo import RepoFilter
from app.services.validators import is_valid_uuid


class RepoRepository(BaseRepository):
    def __init__(self, db: Session = Depends(get_session)) -> None:
        super().__init__(Repo, db)

    def get_by_url(self, repo: Repo) -> Repo | None:
        return (
            self.db.query(Repo)
            .filter(Repo.repository_url == repo.repository_url)
            .first()
        )

    def list(self, filters: RepoFilter) -> tuple[int, list[Repo]]:
        query = self.db.query(Repo)

        filters.uuids = (
            filters.uuids.default
            if isinstance(filters.uuids, Query)
            else filters.uuids
        )
        if filters.uuids:
            query = query.filter(
                Repo.uuid.in_(
                    [
                        is_valid_uuid(item, UuidEntity.REPO)
                        for item in filters.uuids
                    ]
                )
            )

        if filters.creator_uuid:
            query = query.filter(
                Repo.creator_uuid
                == is_valid_uuid(filters.creator_uuid, UuidEntity.USER)
            )

        if filters.is_public_repository is not None:
            query = query.filter(
                Repo.is_public_repository == filters.is_public_repository
            )

        fields = [Repo.repository_url]
        query = apply_ilike_search_string(query, filters, fields)

        fields = {
            "order_by_create_date": Repo.create_datetime,
            "order_by_last_update": Repo.last_update_datetime,
            "order_by_repository_url": Repo.repository_url,
        }
        query = apply_orders_by(query, filters, fields)

        count, query = apply_offset_and_limit(query, filters)
        return count, query.all()

    def is_unique_url(self, url: str) -> None:
        repo = self.db.query(Repo).filter(Repo.repository_url == url).first()

        if repo:
            msg = f'Url "{url}" is exist'
            raise RepoError(msg, code=ErrorCode.REPO_URL_EXISTS)

    @staticmethod
    def is_private_repository(repo: Repo):
        if repo.is_public_repository:
            msg = "Is public repo"
            raise RepoError(msg, code=ErrorCode.REPO_IS_PUBLIC)

    @staticmethod
    def is_valid_platform(repo: Repo):
        if repo.platform not in list(GitPlatform):
            msg = "Platform {} is not supported - available: {}".format(
                repo.platform, ", ".join(list(GitPlatform))
            )
            raise RepoError(msg, code=ErrorCode.REPO_PLATFORM_UNSUPPORTED)
