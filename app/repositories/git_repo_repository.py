import io
import json
import os
import shutil
from collections import Counter
from json import JSONDecodeError

import uuid
from fastapi import HTTPException
from fastapi import status as http_status

from git import Repo as GitRepo
from git.exc import GitCommandError

from app import settings
from app.domain.repo_model import Repo
from app.repositories.enum import SchemaStructName, ReservedEnvVariableName
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

    def update_local_repo(self, repo: Repo) -> None:
        # todo доработать для закрытых репозиториев
        git_repo = self.get_repo(repo)
        git_repo.remotes.origin.pull()

    def generate_tmp_git_repo(self, repo: Repo, commit: str, gen_uuid: str) -> str:
        tmp_git_repo = self.get_tmp_repo(repo, gen_uuid)
        tmp_git_repo.git.checkout(commit)

        tmp_git_repo_path = tmp_git_repo.working_tree_dir

        del_path_list = ['.gitignore', 'env_example.json', '.git', 'docs', 'model' 'readme.md', 'README.md']

        for path in del_path_list:
            merge_path = f'{tmp_git_repo_path}/{path}'

            if os.path.isfile(merge_path):
                os.remove(merge_path)
            else:
                shutil.rmtree(merge_path, ignore_errors=True)

        return tmp_git_repo_path

    @staticmethod
    def get_repo(repo: Repo) -> GitRepo:
        return GitRepo(f'{settings.save_repo_path}/{repo.uuid}')

    @staticmethod
    def get_tmp_repo(repo: Repo, gen_uuid: str) -> GitRepo:
        tmp_path = f'tmp/{gen_uuid}'
        current_path = f'{settings.save_repo_path}/{repo.uuid}'

        shutil.copytree(current_path, tmp_path)

        return GitRepo(tmp_path)

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

    def get_commits(self, repo: Repo, branch: str, depth: int = None) -> list[dict]:
        repo = self.get_repo(repo)
        return [
            {'commit': item.name_rev.split()[0], 'summary': item.summary}
            for item in repo.iter_commits(rev=f'remotes/origin/{branch}')
        ][:depth]

    def get_tags(self, repo: Repo) -> list[dict]:
        repo = self.get_repo(repo)
        return [
            {'commit': item.commit.name_rev.split()[0], 'summary': item.commit.summary, 'tag': item.name}
            for item in repo.tags
        ]

    def get_commits_with_tag(self, repo: Repo, branch: str) -> list[dict]:
        commits_dict = self.get_commits(repo, branch)
        tags_dict = self.get_tags(repo)

        commits_with_tag = []
        for commit in commits_dict:
            commit_dict = commit

            for tag in tags_dict:
                if commit['commit'] == tag['commit']:
                    commit_dict['tag'] = tag['tag']

            commits_with_tag.append(commit_dict)

        return commits_with_tag

    def get_file(self, repo: Repo, commit: str, path: str) -> io.BytesIO:
        repo = self.get_repo(repo)

        try:
            target_file = repo.commit(commit).tree / path
        except KeyError:
            raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=f'File not found in repo commit')

        buffer = io.BytesIO()

        target_file.stream_data(buffer)

        return buffer

    def get_schema_dict(self, repo: Repo, commit: str) -> dict:
        schema_buffer = self.get_file(repo, commit, 'schema.json')

        return json.loads(schema_buffer.getvalue().decode())

    def get_env_dict(self, repo: Repo, commit: str) -> dict:
        schema_buffer = self.get_file(repo, commit, 'env_example.json')

        try:
            env_dict = json.loads(schema_buffer.getvalue().decode())
        except JSONDecodeError:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=f'This env_example.json file is not a json serialise',
            )

        return env_dict

    def get_env_example(self, repo: Repo, commit: str) -> dict:
        env_dict = self.get_env_dict(repo, commit)

        reserved_env_names = [i.value for i in ReservedEnvVariableName]

        return {k: v for k, v in env_dict.items() if k not in reserved_env_names}

    def is_valid_schema_file(self, repo: Repo, commit: str) -> None:
        file_buffer = self.get_file(repo, commit, 'schema.json')

        try:
            schema_dict = json.loads(file_buffer.getvalue().decode())
        except JSONDecodeError:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST, detail=f'This schema file is not a json file'
            )

        binding_schema_keys = [i.value for i in SchemaStructName]

        if len(binding_schema_keys) != len(set(schema_dict.keys()) & set(binding_schema_keys)):
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=f'This schema file has unresolved IO and base IO keys',
            )

        schema_dict_values_type = [type(value) for value in schema_dict.values()]

        if Counter(schema_dict_values_type)[list] != len(schema_dict):
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=f'This schema file has not available value types, only list is available',
            )

        all_unique_chars_topic = Counter(''.join([item for value in schema_dict.values() for item in value])).keys()

        if (set(all_unique_chars_topic) - set(settings.available_topic_symbols)) != set():
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=f'Topics in the schema use characters that are not allowed',
            )

        # 100 chars is stock for system track parts
        if max([len(item) for value in schema_dict.values() for item in value]) >= 65535 - 100:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST, detail=f'The length of the topic title is too long'
            )

    def is_valid_env_file(self, repo: Repo, commit: str, env: dict) -> None:
        env_example_dict = self.get_env_dict(repo, commit)

        if env_example_dict.keys() - env.keys() != set():
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST, detail=f'This env file has unresolved variable'
            )

    def is_valid_branch(self, repo: Repo, branch: str):
        if branch not in self.get_branches(repo):
            raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=f"No valid branch")

    def is_valid_commit(self, repo: Repo, branch: str, commit: str):
        if commit not in [commit_dict['commit'] for commit_dict in self.get_commits(repo, branch)]:
            raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=f"No valid commit")
