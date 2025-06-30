from typing import Optional

from fastapi import Depends
from sqlmodel import Session

from app.configs.db import get_session
from app.configs.errors import RepositoryRegistryError
from app.domain.repository_registry_model import RepositoryRegistry
from app.dto.enum import GitPlatform


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

    def is_valid_url(self, repository_registry: RepositoryRegistry) -> Optional[RepositoryRegistry]:
        url = repository_registry.repository_url
        if url[-4:] != '.git' or not (url.find('https://') == 0 or url.find('http://') == 0):
            raise RepositoryRegistryError(
                "RepositoryRegistry URL is not correct check the .git at the end of the link and the correctness of https / http"
            )

        return (
            self.db.query(RepositoryRegistry)
            .filter(RepositoryRegistry.repository_url == repository_registry.repository_url)
            .first()
        )

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
