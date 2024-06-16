import json
from typing import Optional

from fastapi import Depends
from fastapi import HTTPException
from fastapi import status as http_status
from sqlalchemy import func, desc
from sqlmodel import Session, select

from app.configs.db import get_session
from app.domain.repo_model import Repo
from app.domain.unit_model import Unit
from app.repositories.git_repo_repository import GitRepoRepository
from app.repositories.utils import apply_ilike_search_string, apply_enums, apply_offset_and_limit, apply_orders_by
from app.schemas.pydantic.repo import RepoFilter, RepoCreate, RepoUpdate, RepoVersionRead, RepoVersionsRead, Credentials
from app.utils.utils import aes_decode


class RepoRepository:
    db: Session

    def __init__(self, db: Session = Depends(get_session)) -> None:
        self.db = db
        self.git_repo_repository = GitRepoRepository()

    def create(self, repo: Repo) -> Repo:
        self.db.add(repo)
        self.db.commit()
        self.db.refresh(repo)
        return repo

    def get(self, repo: Repo) -> Repo:
        return self.db.get(Repo, repo.uuid)

    def get_credentials(self, repo: Repo) -> Optional[Credentials]:
        full_repo = self.db.get(Repo, repo.uuid)
        if not full_repo.cipher_credentials_private_repository:
            return None
        return Credentials(**json.loads(aes_decode(full_repo.cipher_credentials_private_repository)))

    def get_all_count(self) -> int:
        return self.db.query(Repo).count()

    def get_versions(self, repo: Repo) -> RepoVersionsRead:
        versions = (
            self.db.query(Unit.current_commit_version, func.count(Unit.uuid))
            .filter(Unit.current_commit_version != None, Unit.repo_uuid == repo.uuid)
            .group_by(Unit.current_commit_version)
            .order_by(desc(func.count(Unit.uuid)))
        )
        count_with_version = (
            self.db.query(Unit).filter(Unit.current_commit_version != None, Unit.repo_uuid == repo.uuid).count()
        )

        tags = self.git_repo_repository.get_tags(repo)

        versions_list = []
        for commit, count in versions:

            tag = list(filter(lambda item: item['commit'] == commit, tags))

            versions_list.append(RepoVersionRead(commit=commit, unit_count=count, tag=tag[0]['tag'] if tag else None))

        return RepoVersionsRead(unit_count=count_with_version, versions=versions_list)

    def update(self, uuid, repo: Repo) -> Repo:
        repo.uuid = uuid
        self.db.merge(repo)
        self.db.commit()
        return self.get(repo)

    def delete(self, repo: Repo) -> None:
        self.db.delete(self.get(repo))
        self.db.commit()
        self.db.flush()

    def list(self, filters: RepoFilter, restriction: list[str] = None) -> list[Repo]:
        query = self.db.query(Repo)

        if filters.creator_uuid:
            query = query.filter(Repo.creator_uuid == filters.creator_uuid)

        if filters.is_auto_update_repo is not None:
            query = query.filter(Repo.is_auto_update_repo == filters.is_auto_update_repo)

        if restriction:
            query = query.filter(Repo.uuid.in_(restriction))

        fields = [Repo.name, Repo.repo_url, Repo.default_branch]
        query = apply_ilike_search_string(query, filters, fields)

        fields = {'visibility_level': Repo.visibility_level}
        query = apply_enums(query, filters, fields)

        fields = {'order_by_create_date': Repo.create_datetime, 'order_by_last_update': Repo.last_update_datetime}
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
        if url[-4:] != '.git' or not (url.find('https://') == 0 or url.find('http://') == 0):
            raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=f"No valid repo_url")

    @staticmethod
    def is_valid_private_repo(data: RepoCreate or RepoUpdate):
        if not data.is_public_repository and (
            not data.credentials or (not data.credentials.username or not data.credentials.pat_token)
        ):
            raise HTTPException(status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"No valid credentials")

    @staticmethod
    def is_private_repository(repo: Repo):
        if repo.is_public_repository:
            raise HTTPException(status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Is public repo")

    def is_valid_auto_updated_repo(self, repo: Repo):
        if repo.is_auto_update_repo and not repo.default_branch:
            raise HTTPException(status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                                detail=f"Invalid auto updated Repo")
        if repo.is_auto_update_repo and not self.git_repo_repository.get_target_version(repo):
            raise HTTPException(status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                                detail=f"Invalid auto updated target version")
