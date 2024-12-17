import io
import json
import os
import shutil
import uuid as uuid_pkg
from collections import Counter
from json import JSONDecodeError
from typing import Optional
from zoneinfo import available_timezones

import git
from git import Repo as GitRepo
from git.exc import GitCommandError

from app import settings
from app.configs.errors import app_errors
from app.domain.repo_model import Repo
from app.domain.unit_model import Unit
from app.repositories.enum import DestinationTopicType, GitPlatform, ReservedEnvVariableName
from app.repositories.git_platform_repository import (
    GithubPlatformRepository,
    GitlabPlatformRepository,
    GitPlatformRepositoryABC,
)
from app.schemas.pydantic.repo import Credentials
from app.services.validators import is_valid_json, is_valid_object


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
            app_errors.validation_error.raise_exception('No valid repo_url or credentials')

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
    def get_tmp_path(gen_uuid: uuid_pkg.UUID) -> str:
        return f'tmp/{gen_uuid}'

    def get_tmp_repo(self, repo: Repo, gen_uuid: uuid_pkg.UUID) -> GitRepo:
        tmp_path = self.get_tmp_path(gen_uuid)
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

    def get_branch_commits(self, repo: Repo, branch: str, depth: int = None) -> list[dict]:
        """
        Get all commits for branch with depth
        """

        self.is_valid_branch(repo, branch)

        repo = self.get_repo(repo)
        return [
            {'commit': item.name_rev.split()[0], 'summary': item.summary}
            for item in repo.iter_commits(rev=f'remotes/origin/{branch}')
        ][:depth]

    def get_branch_tags(self, repo: Repo, branch: str) -> list[dict]:
        """
        Get all commits with tags for branch
        """

        self.is_valid_branch(repo, repo.default_branch)
        branch_commits_set = {item['commit'] for item in self.get_branch_commits(repo, branch)}
        repo = self.get_repo(repo)

        return [
            {'commit': item.commit.name_rev.split()[0], 'summary': item.commit.summary, 'tag': item.name}
            for item in repo.tags
            if item.commit.name_rev.split()[0] in branch_commits_set
        ][::-1]

    def get_branch_commits_with_tag(self, repo: Repo, branch: str) -> list[dict]:
        """
        Get all commits for branch, with tags
        """

        commits = self.get_branch_commits(repo, branch)
        tags = self.get_branch_tags(repo, branch)

        commits_with_tag = []
        for commit in commits:
            commit_dict = commit
            commit_dict['tag'] = None

            for tag in tags:
                if commit['commit'] == tag['commit']:
                    commit_dict['tag'] = tag['tag']

            commits_with_tag.append(commit_dict)

        return commits_with_tag

    @staticmethod
    def find_by_commit(data: list[dict], commit: str) -> Optional[dict]:
        for item in data:
            if item["commit"] == commit:
                return item
        return None

    def get_target_repo_version(self, repo: Repo) -> tuple[str, Optional[str]]:
        self.is_valid_branch(repo, repo.default_branch)

        all_commits = self.get_branch_commits_with_tag(repo, repo.default_branch)
        tags = self.get_branch_tags(repo, repo.default_branch)

        target_commit = None
        if repo.is_auto_update_repo:
            if repo.is_compilable_repo:
                if len(tags) != 0:
                    target_commit = tags[0]
            else:
                if repo.is_only_tag_update:
                    if len(tags) != 0:
                        target_commit = tags[0]
                else:
                    target_commit = all_commits[0]

        else:
            self.is_valid_commit(repo, repo.default_branch, repo.default_commit)

            target_commit = self.find_by_commit(all_commits, repo.default_commit)

            if repo.is_compilable_repo and target_commit['tag'] is None:
                app_errors.validation_error.raise_exception('Commit {} without Tag'.format(target_commit['commit']))

        if not target_commit:
            app_errors.validation_error.raise_exception('Version is missing: The tags are not in the repository')

        return target_commit['commit'], target_commit['tag']

    def get_target_unit_version(self, repo: Repo, unit: Unit) -> tuple[str, Optional[str]]:

        target_commit = None
        if unit.is_auto_update_from_repo_unit:
            repo_target = self.get_target_repo_version(repo)
            target_commit = {'commit': repo_target[0], 'tag': repo_target[1]}
        else:
            self.is_valid_branch(repo, unit.repo_branch)
            all_commits = self.get_branch_commits_with_tag(repo, unit.repo_branch)
            target_commit = self.find_by_commit(all_commits, unit.repo_commit)

            if target_commit:
                if repo.is_compilable_repo and target_commit['tag'] is None:
                    app_errors.validation_error.raise_exception('Commit {} without Tag'.format(target_commit['commit']))

        if not target_commit:
            app_errors.validation_error.raise_exception('Version is missing')

        return target_commit['commit'], target_commit['tag']

    def get_file(self, repo: Repo, commit: str, path: str) -> io.BytesIO:
        repo = self.get_repo(repo)

        if commit is None:
            app_errors.validation_error.raise_exception('Commit not found')

        try:
            target_file = repo.commit(commit).tree / path
        except KeyError:
            app_errors.validation_error.raise_exception('File {} not found in repo commit {}'.format(path, commit))

        buffer = io.BytesIO()

        target_file.stream_data(buffer)

        return buffer

    def get_schema_dict(self, repo: Repo, commit: str) -> dict:
        # TODO: hardcode - подумать как избавиться
        target_file = 'schema_example.json'
        schema_buffer = self.get_file(repo, commit, target_file)
        return is_valid_json(schema_buffer.getvalue().decode(), target_file)

    def get_env_dict(self, repo: Repo, commit: str) -> dict:
        # TODO: hardcode - подумать как избавиться
        target_file = 'env_example.json'
        schema_buffer = self.get_file(repo, commit, target_file)
        return is_valid_json(schema_buffer.getvalue().decode(), target_file)

    def get_env_example(self, repo: Repo, commit: str) -> dict:
        is_valid_object(commit)

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
        schema_dict = self.get_schema_dict(repo, commit)

        binding_schema_keys = [i.value for i in DestinationTopicType]

        # check - all 4 topic destination, is in schema
        if len(binding_schema_keys) != len(set(schema_dict.keys()) & set(binding_schema_keys)):
            app_errors.validation_error.raise_exception('This schema file has unresolved IO and base IO keys')

        schema_dict_values_type = [type(value) for value in schema_dict.values()]

        # check - all values first layer schema is list
        if Counter(schema_dict_values_type)[list] != len(schema_dict):
            app_errors.validation_error.raise_exception(
                'This schema file has not available value types, only list is available'
            )

        all_unique_chars_topic = Counter(''.join([item for value in schema_dict.values() for item in value])).keys()

        # check - all chars in topics is valid
        if (set(all_unique_chars_topic) - set(settings.available_topic_symbols)) != set():
            app_errors.validation_error.raise_exception(
                'Topics in the schema use characters that are not allowed, allowed: {}'.format(
                    settings.available_topic_symbols
                )
            )

        # check - length topics. 100 chars is stock for system track parts
        current_len = max([len(item) for value in schema_dict.values() for item in value])
        max_value = 65535 - 100
        if current_len >= max_value:
            app_errors.validation_error.raise_exception(
                'The length {} of the topic title is too long, max: {}'.format(current_len, max_value)
            )

    def is_valid_env_file(self, repo: Repo, commit: str, env: dict) -> None:
        env_example_dict = self.get_env_dict(repo, commit)

        unresolved_set = env_example_dict.keys() - env.keys()
        if unresolved_set != set():
            app_errors.validation_error.raise_exception(
                'This env file has {} unresolved variable'.format(unresolved_set)
            )

    def is_valid_branch(self, repo: Repo, branch: str):
        available_branches = self.get_branches(repo)
        if not branch or branch not in available_branches:
            app_errors.validation_error.raise_exception(
                'Branch {} not found, available: {}'.format(branch, available_branches)
            )

    def is_valid_commit(self, repo: Repo, branch: str, commit: str):
        if commit not in [commit_dict['commit'] for commit_dict in self.get_branch_commits(repo, branch)]:
            app_errors.validation_error.raise_exception('Commit {} not in branch {}'.format(commit, branch))

    @staticmethod
    def find_by_platform(data: list[tuple[str, str]], platform: str) -> Optional[tuple[str, str]]:
        for item in data:
            if item[0] == platform:
                return item
        return None

    def is_valid_firmware_platform(self, repo: Repo, unit: Unit, firmware_platform: str):

        if repo.is_compilable_repo:
            is_valid_object(repo.releases_data)

            releases = json.loads(repo.releases_data)
            target_commit, target_tag = self.get_target_unit_version(repo, unit)

            target_platforms = releases.get(target_tag)

            if target_platforms:
                if self.find_by_platform(target_platforms, firmware_platform) is None:
                    app_errors.validation_error.raise_exception(
                        'Not find platform {}, available: {}'.format(
                            firmware_platform, [item[0] for item in target_platforms]
                        )
                    )

            else:
                app_errors.validation_error.raise_exception('Target Tag has no platforms')
