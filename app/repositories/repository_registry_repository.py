from typing import Optional

from fastapi import Depends
from fastapi.params import Query
from sqlmodel import Session

from app.configs.db import get_session
from app.configs.errors import RepositoryRegistryError
from app.domain.repository_registry_model import RepositoryRegistry
from app.dto.enum import GitPlatform
from app.repositories.base_repository import BaseRepository
from app.repositories.utils import apply_ilike_search_string, apply_offset_and_limit, apply_orders_by
from app.schemas.pydantic.repository_registry import RepositoryRegistryFilter
from app.services.validators import is_valid_uuid


class RepositoryRegistryRepository(BaseRepository):
    def __init__(self, db: Session = Depends(get_session)) -> None:
        super().__init__(RepositoryRegistry, db)

    def get_by_url(self, repository_registry: RepositoryRegistry) -> Optional[RepositoryRegistry]:
        return (
            self.db.query(RepositoryRegistry)
            .filter(RepositoryRegistry.repository_url == repository_registry.repository_url)
            .first()
        )

    def list(
        self, filters: RepositoryRegistryFilter, restriction: list[str] = None
    ) -> tuple[int, list[RepositoryRegistry]]:
        query = self.db.query(RepositoryRegistry)

        filters.uuids = filters.uuids.default if isinstance(filters.uuids, Query) else filters.uuids
        if filters.uuids:
            query = query.filter(RepositoryRegistry.uuid.in_([is_valid_uuid(item) for item in filters.uuids]))

        if filters.creator_uuid:
            query = query.filter(RepositoryRegistry.creator_uuid == is_valid_uuid(filters.creator_uuid))

        if filters.is_public_repository is not None:
            query = query.filter(RepositoryRegistry.is_public_repository == filters.is_public_repository)

        fields = [RepositoryRegistry.repository_url]
        query = apply_ilike_search_string(query, filters, fields)

        fields = {
            'order_by_create_date': RepositoryRegistry.create_datetime,
            'order_by_last_update': RepositoryRegistry.last_update_datetime,
        }
        query = apply_orders_by(query, filters, fields)

        count, query = apply_offset_and_limit(query, filters)
        return count, query.all()

    def is_unique_url(self, url: str) -> None:
        repository_registry = self.db.query(RepositoryRegistry).filter(RepositoryRegistry.repository_url == url).first()

        if repository_registry:
            raise RepositoryRegistryError('Url "{}" is exist'.format(url))

    @staticmethod
    def is_private_repository(repository_registry: RepositoryRegistry):
        if repository_registry.is_public_repository:
            raise RepositoryRegistryError('Is public repo')

    @staticmethod
    def is_valid_platform(repository_registry: RepositoryRegistry):
        if repository_registry.platform not in list(GitPlatform):
            raise RepositoryRegistryError(
                'Platform {} is not supported - available: {}'.format(
                    repository_registry.platform, ", ".join(list(GitPlatform))
                )
            )
