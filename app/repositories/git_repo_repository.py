import contextlib
import io
import os
import shutil
import uuid as uuid_pkg
from collections import Counter

from git import Repo as GitRepo
from git.exc import GitCommandError

from app import settings
from app.configs.errors import GitRepoError
from app.configs.utils import get_directory_size
from app.domain.repo_model import Repo
from app.domain.repository_registry_model import RepositoryRegistry
from app.domain.unit_model import Unit
from app.dto.enum import (
    DestinationTopicType,
    ReservedEnvVariableName,
    StaticRepoFileName,
)
from app.services.validators import is_valid_json, is_valid_object
from app.utils.utils import clean_files_with_pepeignore


class GitRepoRepository:
    COMMIT_FORMAT = "%H%x00%s"

    @staticmethod
    def get_path_physic_repository(repository_registry: RepositoryRegistry):
        return f"{settings.pu_save_repo_path}/{repository_registry.uuid}"

    @staticmethod
    def _origin(branch: str) -> str:
        return f"remotes/origin/{branch}"

    @staticmethod
    def _parse_commits(rev_list: str) -> list[dict]:
        commits = []
        for line in rev_list.strip().split("\n"):
            commit, separator, summary = line.partition("\0")
            if separator:
                commits.append({"commit": commit, "summary": summary})
        return commits

    @staticmethod
    def _open(path: str) -> GitRepo:
        try:
            return GitRepo(path)
        except Exception as err:
            msg = "Physic repository not exist"
            raise GitRepoError(msg) from err

    @staticmethod
    def clone(url: str, repo_save_path: str):
        shutil.rmtree(repo_save_path, ignore_errors=True)

        git_env = settings.git_http_env()

        try:
            git_repo = GitRepo.clone_from(
                url,
                repo_save_path,
                env=git_env,
            )
        except GitCommandError as err:
            msg = "No valid repo_url or credentials"
            raise GitRepoError(msg) from err

        git_repo.git.update_environment(**git_env)
        for remote in git_repo.remotes:
            remote.fetch()

    def local_repository_size(
        self, repository_registry: RepositoryRegistry
    ) -> int:
        return get_directory_size(
            self.get_path_physic_repository(repository_registry)
        )

    @staticmethod
    def get_local_registry() -> list[str]:
        path = settings.pu_save_repo_path
        return [
            name
            for name in os.listdir(path)
            if os.path.isdir(os.path.join(path, name))
        ]

    def generate_tmp_git_repo(
        self,
        repository_registry: RepositoryRegistry,
        commit: str,
        gen_uuid: uuid_pkg.UUID,
    ) -> str:
        tmp_git_repo = self.get_tmp_repo(repository_registry, gen_uuid)
        tmp_git_repo.git.checkout(commit)

        tmp_git_repo_path = tmp_git_repo.working_tree_dir
        clean_files_with_pepeignore(
            tmp_git_repo_path, f"{tmp_git_repo_path}/.pepeignore"
        )

        return tmp_git_repo_path

    def get_repo(self, repository_registry: RepositoryRegistry) -> GitRepo:
        return self._open(self.get_path_physic_repository(repository_registry))

    @staticmethod
    def get_tmp_path(gen_uuid: uuid_pkg.UUID) -> str:
        return f"tmp/{gen_uuid}"

    def get_tmp_repo(
        self, repository_registry: RepositoryRegistry, gen_uuid: uuid_pkg.UUID
    ) -> GitRepo:
        tmp_path = self.get_tmp_path(gen_uuid)
        shutil.copytree(
            self.get_path_physic_repository(repository_registry), tmp_path
        )
        return self._open(tmp_path)

    def get_branches(
        self, repository_registry: RepositoryRegistry
    ) -> list[str]:
        return [
            r.remote_head
            for r in self.get_repo(repository_registry).remote().refs
        ][1:]

    def _rev_list(
        self, repository_registry: RepositoryRegistry, *revs, **kwargs
    ) -> list[dict]:
        kwargs.setdefault("pretty", self.COMMIT_FORMAT)
        return self._parse_commits(
            self.get_repo(repository_registry).git.rev_list(*revs, **kwargs)
        )

    def _tag_map(
        self,
        repository_registry: RepositoryRegistry,
        commits: set | None = None,
    ) -> dict[str, str]:
        if commits is not None and not commits:
            return {}

        raw = self.get_repo(repository_registry).git.for_each_ref(
            "refs/tags",
            format="%(objectname)\t%(*objectname)\t%(refname:short)",
            sort="refname",
        )

        tag_by_commit = {}
        for line in raw.split("\n"):
            if not line:
                continue
            objectname, peeled, name = line.split("\t", 2)
            commit_hash = peeled or objectname
            if commits is None or commit_hash in commits:
                tag_by_commit.setdefault(commit_hash, name)

        return tag_by_commit

    def _with_tags(
        self, repository_registry: RepositoryRegistry, commits: list[dict]
    ) -> list[dict]:
        tag_by_commit = self._tag_map(
            repository_registry, {item["commit"] for item in commits}
        )
        for item in commits:
            item["tag"] = tag_by_commit.get(item["commit"])
        return commits

    def _commit(
        self, repository_registry: RepositoryRegistry, sha: str
    ) -> dict | None:
        commits = self._rev_list(repository_registry, sha, max_count=1)
        if commits:
            commits[0]["tag"] = self._tag_map(repository_registry, {sha}).get(
                sha
            )
        return commits[0] if commits else None

    def _tagged_shas(
        self,
        repository_registry: RepositoryRegistry,
        branch: str,
        limit: int,
    ) -> list[tuple[str, str]]:
        tag_by_commit = self._tag_map(repository_registry)
        if not tag_by_commit or limit <= 0:
            return []

        tagged = []
        proc = self.get_repo(repository_registry).git.rev_list(
            self._origin(branch), as_process=True
        )
        try:
            for raw in proc.stdout:
                sha = (raw.decode() if isinstance(raw, bytes) else raw).strip()
                tag = tag_by_commit.get(sha)
                if tag:
                    tagged.append((sha, tag))
                    if len(tagged) >= limit:
                        break
        finally:
            if proc.poll() is None:
                proc.kill()
            with contextlib.suppress(GitCommandError):
                proc.wait()

        return tagged

    def get_branch_commits(
        self,
        repository_registry: RepositoryRegistry,
        branch: str,
        depth: int = None,
        skip: int = None,
    ) -> list[dict]:
        self.is_valid_branch(repository_registry, branch)
        return self._rev_list(
            repository_registry,
            self._origin(branch),
            max_count=depth,
            skip=skip,
        )

    def get_branch_commits_with_tag(
        self, repository_registry: RepositoryRegistry, branch: str
    ) -> list[dict]:
        return self._with_tags(
            repository_registry,
            self.get_branch_commits(repository_registry, branch),
        )

    def get_branch_commits_page(
        self,
        repository_registry: RepositoryRegistry,
        branch: str,
        offset: int,
        limit: int,
    ) -> list[dict]:
        return self._with_tags(
            repository_registry,
            self.get_branch_commits(
                repository_registry, branch, depth=limit, skip=offset
            ),
        )

    def get_branch_tagged_commits_page(
        self,
        repository_registry: RepositoryRegistry,
        branch: str,
        offset: int,
        limit: int,
    ) -> list[dict]:
        self.is_valid_branch(repository_registry, branch)

        page = self._tagged_shas(repository_registry, branch, offset + limit)[
            offset : offset + limit
        ]
        summaries = (
            {
                item["commit"]: item["summary"]
                for item in self._rev_list(
                    repository_registry,
                    *[sha for sha, _ in page],
                    no_walk="unsorted",
                )
            }
            if page
            else {}
        )

        return [
            {"commit": sha, "summary": summaries[sha], "tag": tag}
            for sha, tag in page
        ]

    @staticmethod
    def get_tags_from_all_commits(commits: list[dict]) -> list[dict]:
        return [commit for commit in commits if commit["tag"]]

    def get_commit_with_tag(
        self, repository_registry: RepositoryRegistry, branch: str, commit: str
    ) -> dict | None:
        return (
            self._commit(repository_registry, commit)
            if self.is_commit_in_branch(repository_registry, branch, commit)
            else None
        )

    def get_target_repo_version(
        self, repository_registry: RepositoryRegistry, repo: Repo
    ) -> tuple[str, str | None]:
        branch = repo.default_branch
        self.is_valid_branch(repository_registry, branch)

        if repo.is_auto_update_repo:
            if repo.is_compilable_repo or repo.is_only_tag_update:
                page = self.get_branch_tagged_commits_page(
                    repository_registry, branch, 0, 1
                )
                target = page[0] if page else None
            else:
                sha = self.get_repo(repository_registry).git.rev_parse(
                    self._origin(branch)
                )
                target = self._commit(repository_registry, sha)
        else:
            self.is_valid_commit(
                repository_registry, branch, repo.default_commit
            )
            target = self.get_commit_with_tag(
                repository_registry, branch, repo.default_commit
            )
            self._raise_if_compilable_untagged(repo, target)

        if not target:
            msg = "Version is missing: The tags are not in the repository"
            raise GitRepoError(msg)

        return target["commit"], target["tag"]

    def get_target_unit_version(
        self, repo: Repo, repository_registry: RepositoryRegistry, unit: Unit
    ) -> tuple[str, str | None]:
        if unit.is_auto_update_from_repo_unit:
            return self.get_target_repo_version(repository_registry, repo)

        self.is_valid_branch(repository_registry, unit.repo_branch)
        target = self.get_commit_with_tag(
            repository_registry, unit.repo_branch, unit.repo_commit
        )
        self._raise_if_compilable_untagged(repo, target)

        if not target:
            msg = "Version is missing"
            raise GitRepoError(msg)

        return target["commit"], target["tag"]

    @staticmethod
    def _raise_if_compilable_untagged(repo: Repo, target: dict | None) -> None:
        if target and repo.is_compilable_repo and target["tag"] is None:
            msg = "Commit {} without Tag".format(target["commit"])
            raise GitRepoError(msg)

    def get_file(
        self, repository_registry: RepositoryRegistry, commit: str, path: str
    ) -> io.BytesIO:
        repo = self.get_repo(repository_registry)

        if commit is None:
            msg = "Commit not found"
            raise GitRepoError(msg)

        try:
            target_file = repo.commit(commit).tree / path
        except KeyError as err:
            msg = f"File {path} not found in repo commit {commit}"
            raise GitRepoError(msg) from err

        buffer = io.BytesIO()
        target_file.stream_data(buffer)
        return buffer

    def get_schema_dict(
        self, repository_registry: RepositoryRegistry, commit: str
    ) -> dict:
        target_file = StaticRepoFileName.SCHEMA_EXAMPLE.value
        schema_buffer = self.get_file(repository_registry, commit, target_file)
        return is_valid_json(schema_buffer.getvalue().decode(), target_file)

    def get_env_dict(
        self, repository_registry: RepositoryRegistry, commit: str
    ) -> dict:
        target_file = StaticRepoFileName.ENV_EXAMPLE.value
        schema_buffer = self.get_file(repository_registry, commit, target_file)
        return is_valid_json(schema_buffer.getvalue().decode(), target_file)

    def get_env_example(
        self, repository_registry: RepositoryRegistry, commit: str
    ) -> dict:
        is_valid_object(commit)

        env_dict = self.get_env_dict(repository_registry, commit)
        reserved_env_names = [i.value for i in ReservedEnvVariableName]

        return {
            k: v for k, v in env_dict.items() if k not in reserved_env_names
        }

    def delete_repo(self, repository_registry: RepositoryRegistry) -> None:
        shutil.rmtree(
            self.get_path_physic_repository(repository_registry),
            ignore_errors=True,
        )

    def is_valid_schema_file(
        self, repository_registry: RepositoryRegistry, commit: str
    ) -> None:
        schema_dict = self.get_schema_dict(repository_registry, commit)

        binding_schema_keys = [i.value for i in DestinationTopicType]

        if len(binding_schema_keys) != len(
            set(schema_dict.keys()) & set(binding_schema_keys)
        ):
            msg = "This schema file has unresolved IO and base IO keys"
            raise GitRepoError(msg)

        schema_dict_values_type = [
            type(value) for value in schema_dict.values()
        ]

        if Counter(schema_dict_values_type)[list] != len(schema_dict):
            msg = "This schema file has not available value types, only list is available"
            raise GitRepoError(msg)

        all_unique_chars_topic = Counter(
            "".join([item for value in schema_dict.values() for item in value])
        ).keys()

        if (
            set(all_unique_chars_topic)
            - set(settings.pu_available_topic_symbols)
        ) != set():
            msg = f"Topics in the schema use characters that are not allowed, allowed: {settings.pu_available_topic_symbols}"
            raise GitRepoError(msg)

        current_len = max(
            [len(item) for value in schema_dict.values() for item in value]
        )
        max_value = 65535 - 100
        if current_len >= max_value:
            msg = f"The length {current_len} of the topic title is too long, max: {max_value}"
            raise GitRepoError(msg)

    def is_valid_env_file(
        self, repository_registry: RepositoryRegistry, commit: str, env: dict
    ) -> None:
        env_example_dict = self.get_env_dict(repository_registry, commit)

        unresolved_set = env_example_dict.keys() - env.keys()
        if unresolved_set != set():
            msg = f"This env file has {unresolved_set} unresolved variable"
            raise GitRepoError(msg)

    def is_valid_branch(
        self, repository_registry: RepositoryRegistry, branch: str
    ):
        available_branches = self.get_branches(repository_registry)
        if not branch or branch not in available_branches:
            msg = f"Branch {branch} not found, available: {available_branches}"
            raise GitRepoError(msg)

    def is_commit_in_branch(
        self, repository_registry: RepositoryRegistry, branch: str, commit: str
    ) -> bool:
        in_branch = False
        if commit:
            try:
                repo = self.get_repo(repository_registry)
                if repo.git.rev_parse(f"{commit}^{{commit}}") == commit:
                    repo.git.merge_base(
                        commit, self._origin(branch), is_ancestor=True
                    )
                    in_branch = True
            except GitCommandError:
                pass
        return in_branch

    def is_valid_commit(
        self, repository_registry: RepositoryRegistry, branch: str, commit: str
    ):
        self.is_valid_branch(repository_registry, branch)

        if not self.is_commit_in_branch(repository_registry, branch, commit):
            msg = f"Commit {commit} not in branch {branch}"
            raise GitRepoError(msg)

    @staticmethod
    def find_by_platform(
        data: list[tuple[str, str]], platform: str
    ) -> tuple[str, str] | None:
        return next((item for item in data if item[0] == platform), None)

    def is_valid_firmware_platform(
        self,
        repo: Repo,
        repository_registry: RepositoryRegistry,
        unit: Unit,
        firmware_platform: str,
        target_version_with_tag: tuple[str, str | None] | None = None,
    ):
        if not repo.is_compilable_repo:
            return

        is_valid_object(repository_registry.releases_data)
        releases = is_valid_json(
            repository_registry.releases_data, "Releases for compile repo"
        )
        _, target_tag = (
            target_version_with_tag
            or self.get_target_unit_version(repo, repository_registry, unit)
        )
        target_platforms = releases.get(target_tag)

        if not target_platforms:
            msg = "Target Tag has no platforms"
            raise GitRepoError(msg)

        if self.find_by_platform(target_platforms, firmware_platform) is None:
            msg = f"Not find platform {firmware_platform}, available: {[item[0] for item in target_platforms]}"
            raise GitRepoError(msg)
