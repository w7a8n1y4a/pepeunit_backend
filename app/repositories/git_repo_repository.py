import io
import json
import shutil
from collections import Counter
from json import JSONDecodeError
from typing import Sequence

from fastapi import HTTPException
from fastapi import status as http_status

from git import Repo as GitRepo
from git.exc import GitCommandError

from app import settings
from app.domain.repo_model import Repo
from app.schemas.pydantic.repo import RepoCreate


class GitRepoRepository:
    def clone_remote_repo(self, repo: Repo, data: RepoCreate) -> None:
        repo_save_path = f'{settings.save_repo_path}/{repo.uuid}'
        try:
            shutil.rmtree(repo_save_path)
        except FileNotFoundError:
            pass

        try:
            # клонирование
            git_repo = GitRepo.clone_from(self.get_url(data), repo_save_path)
        except GitCommandError:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST, detail=f"No valid repo_url or credentials"
            )

        # получает все удалённые ветки
        for remote in git_repo.remotes:
            remote.fetch()

    @staticmethod
    def get_repo(repo: Repo) -> GitRepo:
        return GitRepo(f'{settings.save_repo_path}/{repo.uuid}')

    @staticmethod
    def get_url(data: RepoCreate):
        repo_url = data.repo_url
        if not data.is_public_repository:
            repo_url = repo_url.replace(
                'https://', f"https://{data.credentials.username}:{data.credentials.pat_token}@"
            ).replace('http://', f"http://{data.credentials.username}:{data.credentials.pat_token}@")

        return repo_url

    def get_branches(self, repo: Repo) -> list[str]:
        repo = self.get_repo(repo)
        return [r.remote_head for r in repo.remote().refs][1:]

    def get_commits(self, repo: Repo, branch: str, depth: int = None) -> list[tuple[str, str]]:
        repo = self.get_repo(repo)
        return [(item.name_rev.split()[0], item.summary) for item in repo.iter_commits(rev=f'remotes/origin/{branch}')][
            :depth
        ]

    def get_tags(self, repo: Repo) -> list[tuple[str, tuple[str, str]]]:
        repo = self.get_repo(repo)
        return [(item.name, (item.commit.name_rev.split()[0], item.commit.summary)) for item in repo.tags]

    def get_file(self, repo: Repo, commit: str, path: str) -> io.BytesIO:

        repo = self.get_repo(repo)

        try:
            target_file = repo.commit(commit).tree / path
        except KeyError:
            raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=f'File not found in repo commit')

        buffer = io.BytesIO()

        target_file.stream_data(buffer)

        return buffer

    def is_valid_schema_file(self, repo: Repo, commit: str) -> bool:

        file_buffer = self.get_file(repo, commit, 'schema.json')

        try:
            schema_dict = json.loads(file_buffer.getvalue().decode())
        except JSONDecodeError:
            raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST,
                                detail=f'This schema file is not a json file')

        if len(settings.binding_schema_keys) != len(set(schema_dict.keys()) & set(settings.binding_schema_keys)):
            raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST,
                                detail=f'This schema file has unresolved IO and base IO keys')

        schema_dict_values_type = [type(value) for value in schema_dict.values()]

        if Counter(schema_dict_values_type)[list] != len(schema_dict):
            raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST,
                                detail=f'This schema file has not available value types, only list is available')

        all_unique_chars_topic = Counter(''.join([item for value in schema_dict.values() for item in value])).keys()

        if (set(all_unique_chars_topic) - set(settings.available_topic_symbols)) != set():
            raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST,
                                detail=f'Topics in the schema use characters that are not allowed')

        # 100 chars is stock for system track parts
        if max([len(item) for value in schema_dict.values() for item in value]) >= 65535 - 100:
            raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST,
                                detail=f'The length of the topic title is too long')



    def is_valid_branch(self, repo: Repo, branch: str):
        if branch not in self.get_branches(repo):
            raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=f"No valid branch")

    def is_valid_commit(self, repo: Repo, branch: str, commit: str):
        if commit not in [hash_commit for hash_commit, name in self.get_commits(repo, branch)]:
            raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=f"No valid commit")
