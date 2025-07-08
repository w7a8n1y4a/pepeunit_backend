from typing import Optional

from fastapi import Depends
from fastapi.params import Query
from sqlmodel import Session

from app.configs.db import get_session
from app.configs.errors import RepositoryRegistryError
from app.domain.repository_registry_model import RepositoryRegistry
from app.dto.enum import GitPlatform
from app.repositories.utils import apply_ilike_search_string, apply_offset_and_limit, apply_orders_by
from app.schemas.pydantic.repository_registry import RepositoryRegistryFilter
from app.services.validators import is_valid_uuid


class RepositoryRegistryRepository:
    db: Session

    def __init__(self, db: Session = Depends(get_session)) -> None:
        self.db = db

    def create(self, repository_registry: RepositoryRegistry) -> RepositoryRegistry:
        self.db.add(repository_registry)
        self.db.commit()
        self.db.refresh(repository_registry)
        return repository_registry

    def get(self, repository_registry: RepositoryRegistry) -> Optional[RepositoryRegistry]:
        return self.db.get(RepositoryRegistry, repository_registry.uuid)

    def get_all_count(self) -> int:
        return self.db.query(RepositoryRegistry).count()

    def update(self, uuid, repository_registry: RepositoryRegistry) -> RepositoryRegistry:
        repository_registry.uuid = uuid
        self.db.merge(repository_registry)
        self.db.commit()
        return self.get(repository_registry)

    def delete(self, repository_registry: RepositoryRegistry) -> None:
        self.db.delete(self.get(repository_registry))
        self.db.commit()
        self.db.flush()

    def get_all(self) -> list[RepositoryRegistry]:
        return self.db.query(RepositoryRegistry).all()

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
