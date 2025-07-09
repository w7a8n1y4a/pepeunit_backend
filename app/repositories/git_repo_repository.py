import io
import os
import shutil
import uuid as uuid_pkg
from collections import Counter
from typing import Optional

from git import Repo as GitRepo
from git.exc import GitCommandError

from app import settings
from app.configs.errors import GitRepoError
from app.configs.utils import get_directory_size
from app.domain.repo_model import Repo
from app.domain.repository_registry_model import RepositoryRegistry
from app.domain.unit_model import Unit
from app.dto.enum import DestinationTopicType, ReservedEnvVariableName, StaticRepoFileName
from app.services.validators import is_valid_json, is_valid_object
from app.utils.utils import clean_files_with_pepeignore


class GitRepoRepository:

    @staticmethod
    def get_path_physic_repository(repository_registry: RepositoryRegistry):
        return f'{settings.backend_save_repo_path}/{repository_registry.uuid}'

    @staticmethod
    def clone(url: str, repo_save_path: str):
        shutil.rmtree(repo_save_path, ignore_errors=True)

        try:
            # cloning repo by url
            git_repo = GitRepo.clone_from(
                url,
                repo_save_path,
                env={"GIT_TERMINAL_PROMPT": "0"},
            )
        except GitCommandError:
            raise GitRepoError('No valid repo_url or credentials')

        # get all remotes branches to local repo
        for remote in git_repo.remotes:
            remote.fetch()

    def local_repository_size(self, repository_registry: RepositoryRegistry) -> int:
        return get_directory_size(self.get_path_physic_repository(repository_registry))

    @staticmethod
    def get_local_registry() -> list[str]:
        path = settings.backend_save_repo_path
        return [name for name in os.listdir(path) if os.path.isdir(os.path.join(path, name))]

    def generate_tmp_git_repo(
        self, repository_registry: RepositoryRegistry, commit: str, gen_uuid: uuid_pkg.UUID
    ) -> str:
        tmp_git_repo = self.get_tmp_repo(repository_registry, gen_uuid)
        tmp_git_repo.git.checkout(commit)

        tmp_git_repo_path = tmp_git_repo.working_tree_dir
        clean_files_with_pepeignore(tmp_git_repo_path, f'{tmp_git_repo_path}/.pepeignore')

        return tmp_git_repo_path

    def get_repo(self, repository_registry: RepositoryRegistry) -> GitRepo:
        repo_save_path = self.get_path_physic_repository(repository_registry)
        try:
            repo = GitRepo(repo_save_path)
        except:
            raise GitRepoError('Physic repository not exist')

        return repo

    @staticmethod
    def get_tmp_path(gen_uuid: uuid_pkg.UUID) -> str:
        return f'tmp/{gen_uuid}'

    def get_tmp_repo(self, repository_registry: RepositoryRegistry, gen_uuid: uuid_pkg.UUID) -> GitRepo:
        tmp_path = self.get_tmp_path(gen_uuid)
        current_path = self.get_path_physic_repository(repository_registry)

        shutil.copytree(current_path, tmp_path)

        try:
            repo = GitRepo(tmp_path)
        except:
            raise GitRepoError('Physic repository not exist')

        return repo

    def update_credentials(self, repository_registry: RepositoryRegistry):
        git_repo = self.get_repo(repository_registry)

        for remote in git_repo.remotes:
            remote.set_url(self.get_platform(repository_registry).get_cloning_url())

    def get_branches(self, repository_registry: RepositoryRegistry) -> list[str]:

        repo = self.get_repo(repository_registry)

        return [r.remote_head for r in repo.remote().refs][1:]

    def get_branch_commits(self, repository_registry: RepositoryRegistry, branch: str, depth: int = None) -> list[dict]:
        """
        Get all commits for branch with depth
        """

        self.is_valid_branch(repository_registry, branch)

        repo = self.get_repo(repository_registry)
        rev_list = repo.git.rev_list(f'remotes/origin/{branch}', max_count=depth, pretty='%H|%s')
        commits = rev_list.strip().split("\n")
        return [{'commit': line.split('|')[0], 'summary': line.split('|')[1]} for line in commits if '|' in line]

    def get_branch_tags(self, repository_registry: RepositoryRegistry, commits: set) -> list[dict]:
        """
        Get all commits with tags for branch
        """

        repo = self.get_repo(repository_registry)
        tags = []
        for tag in repo.tags:
            commit_hash = tag.commit.hexsha
            if commit_hash in commits:
                tags.append({'commit': commit_hash, 'summary': tag.commit.summary, 'tag': tag.name})
        return tags[::-1]

    def get_branch_commits_with_tag(self, repository_registry: RepositoryRegistry, branch: str) -> list[dict]:
        """
        Get all commits for branch, with tags
        """

        commits = self.get_branch_commits(repository_registry, branch)
        tags = self.get_branch_tags(repository_registry, {item['commit'] for item in commits})

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
    def get_tags_from_all_commits(commits: list[dict]) -> list[dict]:
        return [commit for commit in commits if commit['tag']]

    @staticmethod
    def find_by_commit(data: list[dict], commit: str) -> Optional[dict]:
        for item in data:
            if item["commit"] == commit:
                return item
        return None

    def get_target_repo_version(self, repository_registry: RepositoryRegistry, repo: Repo) -> tuple[str, Optional[str]]:
        self.is_valid_branch(repository_registry, repo.default_branch)

        all_commits = self.get_branch_commits_with_tag(repository_registry, repo.default_branch)
        tags = self.get_tags_from_all_commits(all_commits)

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
            self.is_valid_commit(repository_registry, repo.default_branch, repo.default_commit)

            target_commit = self.find_by_commit(all_commits, repo.default_commit)

            if repo.is_compilable_repo and target_commit['tag'] is None:
                raise GitRepoError('Commit {} without Tag'.format(target_commit['commit']))

        if not target_commit:
            raise GitRepoError('Version is missing: The tags are not in the repository')

        return target_commit['commit'], target_commit['tag']

    def get_target_unit_version(
        self, repo: Repo, repository_registry: RepositoryRegistry, unit: Unit
    ) -> tuple[str, Optional[str]]:

        target_commit = None
        if unit.is_auto_update_from_repo_unit:
            repo_target = self.get_target_repo_version(repository_registry, repo)
            target_commit = {'commit': repo_target[0], 'tag': repo_target[1]}
        else:
            self.is_valid_branch(repository_registry, unit.repo_branch)
            all_commits = self.get_branch_commits_with_tag(repository_registry, unit.repo_branch)
            target_commit = self.find_by_commit(all_commits, unit.repo_commit)

            if target_commit:
                if repo.is_compilable_repo and target_commit['tag'] is None:
                    raise GitRepoError('Commit {} without Tag'.format(target_commit['commit']))

        if not target_commit:
            raise GitRepoError('Version is missing')

        return target_commit['commit'], target_commit['tag']

    def get_file(self, repository_registry: RepositoryRegistry, commit: str, path: str) -> io.BytesIO:
        repo = self.get_repo(repository_registry)

        if commit is None:
            raise GitRepoError('Commit not found')

        try:
            target_file = repo.commit(commit).tree / path
        except KeyError:
            raise GitRepoError('File {} not found in repo commit {}'.format(path, commit))

        buffer = io.BytesIO()

        target_file.stream_data(buffer)

        return buffer

    def get_schema_dict(self, repository_registry: RepositoryRegistry, commit: str) -> dict:
        target_file = StaticRepoFileName.SCHEMA_EXAMPLE
        schema_buffer = self.get_file(repository_registry, commit, target_file)
        return is_valid_json(schema_buffer.getvalue().decode(), target_file)

    def get_env_dict(self, repository_registry: RepositoryRegistry, commit: str) -> dict:
        target_file = StaticRepoFileName.ENV_EXAMPLE
        schema_buffer = self.get_file(repository_registry, commit, target_file)
        return is_valid_json(schema_buffer.getvalue().decode(), target_file)

    def get_env_example(self, repository_registry: RepositoryRegistry, commit: str) -> dict:
        is_valid_object(commit)

        env_dict = self.get_env_dict(repository_registry, commit)

        reserved_env_names = [i.value for i in ReservedEnvVariableName]

        return {k: v for k, v in env_dict.items() if k not in reserved_env_names}

    def delete_repo(self, repository_registry: RepositoryRegistry) -> None:
        shutil.rmtree(self.get_path_physic_repository(repository_registry), ignore_errors=True)
        return None

    def is_valid_schema_file(self, repository_registry: RepositoryRegistry, commit: str) -> None:
        schema_dict = self.get_schema_dict(repository_registry, commit)

        binding_schema_keys = [i.value for i in DestinationTopicType]

        # check - all 4 topic destination, is in schema
        if len(binding_schema_keys) != len(set(schema_dict.keys()) & set(binding_schema_keys)):
            raise GitRepoError('This schema file has unresolved IO and base IO keys')

        schema_dict_values_type = [type(value) for value in schema_dict.values()]

        # check - all values first layer schema is list
        if Counter(schema_dict_values_type)[list] != len(schema_dict):
            raise GitRepoError('This schema file has not available value types, only list is available')

        all_unique_chars_topic = Counter(''.join([item for value in schema_dict.values() for item in value])).keys()

        # check - all chars in topics is valid
        if (set(all_unique_chars_topic) - set(settings.available_topic_symbols)) != set():
            raise GitRepoError(
                'Topics in the schema use characters that are not allowed, allowed: {}'.format(
                    settings.available_topic_symbols
                )
            )

        # check - length topics. 100 chars is stock for system track parts
        current_len = max([len(item) for value in schema_dict.values() for item in value])
        max_value = 65535 - 100
        if current_len >= max_value:
            raise GitRepoError('The length {} of the topic title is too long, max: {}'.format(current_len, max_value))

    def is_valid_env_file(self, repository_registry: RepositoryRegistry, commit: str, env: dict) -> None:
        env_example_dict = self.get_env_dict(repository_registry, commit)

        unresolved_set = env_example_dict.keys() - env.keys()
        if unresolved_set != set():
            raise GitRepoError('This env file has {} unresolved variable'.format(unresolved_set))

    def is_valid_branch(self, repository_registry: RepositoryRegistry, branch: str):
        available_branches = self.get_branches(repository_registry)
        if not branch or branch not in available_branches:
            raise GitRepoError('Branch {} not found, available: {}'.format(branch, available_branches))

    def is_valid_commit(self, repository_registry: RepositoryRegistry, branch: str, commit: str):
        if commit not in [
            commit_dict['commit'] for commit_dict in self.get_branch_commits(repository_registry, branch)
        ]:
            raise GitRepoError('Commit {} not in branch {}'.format(commit, branch))

    @staticmethod
    def find_by_platform(data: list[tuple[str, str]], platform: str) -> Optional[tuple[str, str]]:
        for item in data:
            if item[0] == platform:
                return item
        return None

    def is_valid_firmware_platform(
        self, repo: Repo, repository_registry: RepositoryRegistry, unit: Unit, firmware_platform: str
    ):

        if repo.is_compilable_repo:
            is_valid_object(repository_registry.releases_data)

            releases = is_valid_json(repository_registry.releases_data, "Releases for compile repo")
            target_commit, target_tag = self.get_target_unit_version(repo, repository_registry, unit)

            target_platforms = releases.get(target_tag)

            if target_platforms:
                if self.find_by_platform(target_platforms, firmware_platform) is None:
                    raise GitRepoError(
                        'Not find platform {}, available: {}'.format(
                            firmware_platform, [item[0] for item in target_platforms]
                        )
                    )

            else:
                raise GitRepoError('Target Tag has no platforms')
