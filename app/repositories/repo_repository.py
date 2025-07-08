import uuid as uuid_pkg
from typing import Optional

from fastapi import Depends
from fastapi.params import Query
from sqlalchemy import desc, func
from sqlmodel import Session, select

from app.configs.db import get_session
from app.configs.errors import RepoError
from app.domain.repo_model import Repo
from app.domain.repository_registry_model import RepositoryRegistry
from app.domain.unit_model import Unit
from app.dto.enum import GitPlatform
from app.repositories.git_repo_repository import GitRepoRepository
from app.repositories.utils import (
    apply_enums,
    apply_ilike_search_string,
    apply_offset_and_limit,
    apply_orders_by,
    apply_restriction,
)
from app.schemas.pydantic.repo import RepoCreate, RepoFilter, RepoUpdate, RepoVersionRead, RepoVersionsRead
from app.services.validators import is_valid_string_with_rules, is_valid_uuid


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

    def get(self, repo: Repo) -> Optional[Repo]:
        return self.db.get(Repo, repo.uuid)

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

        commits = self.git_repo_repository.get_branch_commits_with_tag(repo, repo.default_branch)
        tags = self.git_repo_repository.get_tags_from_all_commits(commits)

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

    def get_all_repo(self) -> list[Repo]:
        return self.db.query(Repo).all()

    def list(self, filters: RepoFilter, restriction: list[str] = None) -> tuple[int, list[Repo]]:
        query = self.db.query(Repo, RepositoryRegistry).join(
            RepositoryRegistry, Repo.repository_registry_uuid == RepositoryRegistry.uuid
        )

        if filters.repository_registry_uuid:
            query = query.filter(Repo.repository_registry_uuid == is_valid_uuid(filters.repository_registry_uuid))

        filters.uuids = filters.uuids.default if isinstance(filters.uuids, Query) else filters.uuids
        if filters.uuids:
            query = query.filter(Repo.uuid.in_([is_valid_uuid(item) for item in filters.uuids]))

        filters.creators_uuids = (
            filters.creators_uuids.default if isinstance(filters.creators_uuids, Query) else filters.creators_uuids
        )
        if filters.creators_uuids:
            query = query.filter(Repo.creator_uuid.in_([is_valid_uuid(item) for item in filters.creators_uuids]))

        if filters.creator_uuid:
            query = query.filter(Repo.creator_uuid == is_valid_uuid(filters.creator_uuid))

        if filters.is_auto_update_repo is not None:
            query = query.filter(Repo.is_auto_update_repo == filters.is_auto_update_repo)

        fields = [Repo.name, RepositoryRegistry.repository_url, Repo.default_branch]
        query = apply_ilike_search_string(query, filters, fields)

        fields = {'visibility_level': Repo.visibility_level}
        query = apply_enums(query, filters, fields)

        query = apply_restriction(query, filters, Repo, restriction)

        fields = {'order_by_create_date': Repo.create_datetime, 'order_by_last_update': Repo.last_update_datetime}
        query = apply_orders_by(query, filters, fields)

        count, query = apply_offset_and_limit(query, filters)
        return count, query.all()

    def is_valid_name(self, name: str, uuid: Optional[uuid_pkg.UUID] = None):

        if not is_valid_string_with_rules(name):
            raise RepoError("Name is not correct")

        uuid = str(uuid)
        repo_uuid = self.db.exec(select(Repo.uuid).where(Repo.name == name)).first()
        repo_uuid = str(repo_uuid) if repo_uuid else repo_uuid

        if (uuid is None and repo_uuid) or (uuid and repo_uuid != uuid and repo_uuid is not None):
            raise RepoError("Name is not unique")

    @staticmethod
    def is_valid_compilable_repo(repo: RepoUpdate):
        if repo.is_compilable_repo and repo.is_auto_update_repo and not repo.is_only_tag_update:
            raise RepoError('Compiled repositories use only tags when updating automatically')

    def is_valid_auto_updated_repo(self, repo: Repo):
        # not commit for last commit or not tags for last tags auto update
        if repo.is_auto_update_repo and not self.git_repo_repository.get_target_repo_version(repo):
            raise RepoError('Invalid auto updated target version')

    def is_valid_no_auto_updated_repo(self, repo: Repo):
        if not repo.is_auto_update_repo and (not repo.default_branch or not repo.default_commit):
            raise RepoError('Repo updated manually requires branch and commit to be filled out')

        # check commit and branch for not auto updated repo
        if not repo.is_auto_update_repo:
            self.git_repo_repository.is_valid_branch(repo, repo.default_branch)
            self.git_repo_repository.is_valid_commit(repo, repo.default_branch, repo.default_commit)
