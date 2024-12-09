import io
import json
import os
import shutil
import uuid as uuid_pkg
from collections import Counter
from json import JSONDecodeError
from typing import Optional

import git
from fastapi import HTTPException
from fastapi import status as http_status
from git import Repo as GitRepo
from git.exc import GitCommandError

from app import settings
from app.domain.repo_model import Repo
from app.repositories.enum import DestinationTopicType, GitPlatform, ReservedEnvVariableName
from app.repositories.git_platform_repository import (
    GithubPlatformRepository,
    GitlabPlatformRepository,
    GitPlatformRepositoryABC,
)
from app.schemas.pydantic.repo import Credentials


class GitRepoRepository:

    @staticmethod
    def get_platform(repo: Repo) -> GitPlatformRepositoryABC:
        platforms_dict = {GitPlatform.GITLAB: GitlabPlatformRepository, GitPlatform.GITHUB: GithubPlatformRepository}

        return platforms_dict[GitPlatform(repo.platform)](repo)

    def clone_remote_repo(self, repo: Repo) -> None:
        repo_save_path = f'{settings.save_repo_path}/{repo.uuid}'
        try:
            shutil.rmtree(repo_save_path)
        except FileNotFoundError:
            pass

        try:
            # cloning repo by url
            git_repo = GitRepo.clone_from(
                self.get_platform(repo).get_cloning_url(), repo_save_path, env={"GIT_TERMINAL_PROMPT": "0"}
            )
        except GitCommandError:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST, detail=f"No valid repo_url or credentials"
            )

        # get all remotes branches to local repo
        for remote in git_repo.remotes:
            remote.fetch()

    def get_releases(self, repo: Repo) -> dict[str, list[tuple[str, str]]]:
        return self.get_platform(repo).get_releases()

    def generate_tmp_git_repo(self, repo: Repo, commit: str, gen_uuid: uuid_pkg.UUID) -> str:
        tmp_git_repo = self.get_tmp_repo(repo, gen_uuid)
        tmp_git_repo.git.checkout(commit)

        tmp_git_repo_path = tmp_git_repo.working_tree_dir

        del_path_list = ['.gitignore', 'env_example.json', '.git', 'docs', 'model' 'readme.md', 'README.md', 'LICENSE']

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
    def get_tmp_repo(repo: Repo, gen_uuid: uuid_pkg.UUID) -> GitRepo:
        tmp_path = f'tmp/{gen_uuid}'
        current_path = f'{settings.save_repo_path}/{repo.uuid}'

        shutil.copytree(current_path, tmp_path)

        return GitRepo(tmp_path)

    @staticmethod
    def get_url(repo: Repo, data: Optional[Credentials]):
        repo_url = repo.repo_url
        if not repo.is_public_repository:
            repo_url = repo_url.replace('https://', f"https://{data.username}:{data.pat_token}@").replace(
                'http://', f"http://{data.username}:{data.pat_token}@"
            )

        return repo_url

    def update_credentials(self, repo: Repo):
        try:
            git_repo = self.get_repo(repo)
        except git.NoSuchPathError:
            self.clone_remote_repo(repo)
            git_repo = self.get_repo(repo)

        for remote in git_repo.remotes:
            remote.set_url(self.get_platform(repo).get_cloning_url())

    def get_branches(self, repo: Repo) -> list[str]:
        repo = self.get_repo(repo)
        return [r.remote_head for r in repo.remote().refs][1:]

    def get_commits(self, repo: Repo, branch: str, depth: int = None) -> list[dict]:
        repo = self.get_repo(repo)
        return [
            {'commit': item.name_rev.split()[0], 'summary': item.summary}
            for item in repo.iter_commits(rev=f'remotes/origin/{branch}')
        ][:depth]

    def get_tags(self, repo: Repo, branch: str) -> list[dict]:
        self.is_valid_branch(repo, repo.default_branch)
        branch_commits_set = {item['commit'] for item in self.get_commits(repo, branch)}
        repo = self.get_repo(repo)

        return [
            {'commit': item.commit.name_rev.split()[0], 'summary': item.commit.summary, 'tag': item.name}
            for item in repo.tags
            if item.commit.name_rev.split()[0] in branch_commits_set
        ][::-1]

    def get_commits_with_tag(self, repo: Repo, branch: str) -> list[dict]:
        commits_dict = self.get_commits(repo, branch)

        tags_dict = self.get_tags(repo, branch)

        commits_with_tag = []
        for commit in commits_dict:
            commit_dict = commit

            for tag in tags_dict:
                if commit['commit'] == tag['commit']:
                    commit_dict['tag'] = tag['tag']

            commits_with_tag.append(commit_dict)

        return commits_with_tag

    def get_target_version(self, repo: Repo) -> str:

        self.is_valid_branch(repo, repo.default_branch)

        all_versions = self.get_commits_with_tag(repo, repo.default_branch)
        versions_tag_only = [version for version in all_versions if 'tag' in version and version['tag']]

        if len(all_versions) == 0:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=f'Commits are missing',
            )

        if repo.is_only_tag_update and len(versions_tag_only) == 0:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=f'Tags are missing',
            )

        return versions_tag_only[0]['commit'] if repo.is_only_tag_update else all_versions[0]['commit']

    def get_file(self, repo: Repo, commit: str, path: str) -> io.BytesIO:
        repo = self.get_repo(repo)

        if commit is None:
            raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=f'Commit not found')

        try:
            target_file = repo.commit(commit).tree / path
        except KeyError:
            raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=f'File not found in repo commit')

        buffer = io.BytesIO()

        target_file.stream_data(buffer)

        return buffer

    def get_schema_dict(self, repo: Repo, commit: str) -> dict:
        schema_buffer = self.get_file(repo, commit, 'schema_example.json')

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

        if commit is None:
            raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=f'Commit not found')

        env_dict = self.get_env_dict(repo, commit)

        reserved_env_names = [i.value for i in ReservedEnvVariableName]

        return {k: v for k, v in env_dict.items() if k not in reserved_env_names}

    @staticmethod
    def get_current_repos() -> list[str]:
        path = settings.save_repo_path
        return [name for name in os.listdir(path) if os.path.isdir(os.path.join(path, name))]

    @staticmethod
    def delete_repo(repo: Repo) -> None:
        shutil.rmtree(f'{settings.save_repo_path}/{repo.uuid}', ignore_errors=True)
        return None

    def is_valid_schema_file(self, repo: Repo, commit: str) -> None:
        file_buffer = self.get_file(repo, commit, 'schema_example.json')

        # check - json loads
        try:
            schema_dict = json.loads(file_buffer.getvalue().decode())
        except JSONDecodeError:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST, detail=f'This schema file is not a json file'
            )

        binding_schema_keys = [i.value for i in DestinationTopicType]

        # check - all 4 topic destination, is in schema
        if len(binding_schema_keys) != len(set(schema_dict.keys()) & set(binding_schema_keys)):
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=f'This schema file has unresolved IO and base IO keys',
            )

        schema_dict_values_type = [type(value) for value in schema_dict.values()]

        # check - all values first layer schema is list
        if Counter(schema_dict_values_type)[list] != len(schema_dict):
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=f'This schema file has not available value types, only list is available',
            )

        all_unique_chars_topic = Counter(''.join([item for value in schema_dict.values() for item in value])).keys()

        # check - all chars in topics is valid
        if (set(all_unique_chars_topic) - set(settings.available_topic_symbols)) != set():
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=f'Topics in the schema use characters that are not allowed',
            )

        # check - length topics. 100 chars is stock for system track parts
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
        if not branch or branch not in self.get_branches(repo):
            raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=f"No valid branch")

    def is_valid_commit(self, repo: Repo, branch: str, commit: str):
        if commit not in [commit_dict['commit'] for commit_dict in self.get_commits(repo, branch)]:
            raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=f"No valid commit")
