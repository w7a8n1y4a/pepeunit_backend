from abc import ABC, abstractmethod

import httpx

from app import settings
from app.configs.errors import GitPlatformClientError
from app.domain.repository_registry_model import RepositoryRegistry
from app.schemas.pydantic.repository_registry import Credentials


class GitPlatformClientABC(ABC):
    def __init__(
        self,
        repository_registry: RepositoryRegistry,
        credentials: Credentials | None = None,
    ):
        self.repository_registry = repository_registry
        self.credentials = credentials

    @abstractmethod
    def get_cloning_url(self) -> str:
        """Get url for cloning"""

        repo_url = self.repository_registry.repository_url
        if not self.repository_registry.is_public_repository:
            username = self.credentials.username
            pat_token = self.credentials.pat_token
            repo_url = repo_url.replace(
                "https://", f"https://{username}:{pat_token}@"
            ).replace("http://", f"http://{username}:{pat_token}@")

        return repo_url

    @abstractmethod
    def _get_api_url(self) -> str:
        """Get url for api"""

    @abstractmethod
    def _get_repository_name(self) -> str:
        """Get repository name with group/creator"""
        _, _, _, *name = self.repository_registry.repository_url.split("/")

        return "/".join(name).replace(".git", "")

    @abstractmethod
    def get_releases(self) -> dict[str, list[tuple[str, str]]]:
        """Get release information -> {tag: [(name_package, download_link)]}"""

    @abstractmethod
    def get_repo_size(self) -> int:
        """Get release information -> {tag: [(name_package, download_link)]}"""

    @abstractmethod
    def is_valid_token(self) -> bool:
        """Check valid pat token"""


class GitlabPlatformClient(GitPlatformClientABC):
    """For Gitlab"""

    def get_cloning_url(self) -> str:
        return super().get_cloning_url()

    def _get_api_url(self) -> str:
        http_str, _, domain, *_ = (
            self.repository_registry.repository_url.split("/")
        )

        return f"{http_str}//{domain}/api/v4/projects/"

    def _get_repository_name(self):
        return super()._get_repository_name()

    def _get_repository_id(self) -> int:
        headers = None
        if self.credentials:
            headers = {
                "PRIVATE-TOKEN": self.credentials.pat_token,
            }

        result_data = httpx.get(
            url=self._get_api_url()
            + self._get_repository_name().replace("/", "%2F"),
            headers=headers,
        )

        try:
            target_id = result_data.json()["id"]
        except KeyError as err:
            msg = "Invalid Credentials"
            raise GitPlatformClientError(msg) from err

        return target_id

    def get_releases(self) -> dict[str, list[tuple[str, str]]]:
        repository_id = self._get_repository_id()

        headers = None
        if self.credentials:
            headers = {"PRIVATE-TOKEN": self.credentials.pat_token}

        all_releases: list[dict] = []
        page = 1
        per_page = 100

        while True:
            releases_data = httpx.get(
                url=f"{self._get_api_url()}{repository_id}/releases",
                headers=headers,
                params={"page": page, "per_page": per_page},
            )
            page_items = releases_data.json()

            if not page_items:
                break

            all_releases.extend(page_items)

            if len(page_items) < per_page:
                break

            page += 1

        result_dict: dict[str, list[tuple[str, str]]] = {}
        for item in all_releases:
            assets_list = [
                (source["format"], source["url"])
                for source in item["assets"]["sources"]
            ]
            assets_list.extend(
                [
                    (link["name"], link["url"])
                    for link in item["assets"]["links"]
                ]
            )

            result_dict[item["tag_name"]] = assets_list

        return result_dict

    def get_repo_size(self) -> int:
        repository_id = self._get_repository_id()

        if self.credentials:
            headers = {
                "PRIVATE-TOKEN": self.credentials.pat_token,
            }
        else:
            # BUG: gitlab (< 17.9) has no repository_size for user without role < REPORTER.
            return 0

        repo_data = httpx.get(
            url=f"{self._get_api_url()}{repository_id}?statistics=true",
            headers=headers,
        )

        try:
            repo_size = repo_data.json()["statistics"]["repository_size"]
        except KeyError as err:
            msg = "Invalid Credentials"
            raise GitPlatformClientError(msg) from err

        return repo_size

    def is_valid_token(self) -> bool:
        headers = None
        if self.credentials:
            headers = {
                "PRIVATE-TOKEN": self.credentials.pat_token,
            }

        result_data = httpx.get(
            url=self._get_api_url()
            + self._get_repository_name().replace("/", "%2F"),
            headers=headers,
        )

        try:
            result_data.json()["id"]
        except KeyError:
            return False

        return True


class GithubPlatformClient(GitPlatformClientABC):
    """For Github"""

    def get_cloning_url(self) -> str:
        """Get url for cloning"""
        return super().get_cloning_url()

    def _get_api_url(self) -> str:
        """Get url for api"""

        credentials = ""
        if self.credentials:
            credentials = (
                f"{self.credentials.username}:{self.credentials.pat_token}@"
            )
        elif (
            len(settings.pu_github_token_name) > 0
            and len(settings.pu_github_token_pat) > 0
        ):
            credentials = f"{settings.pu_github_token_name}:{settings.pu_github_token_pat}@"

        return f"https://{credentials}api.github.com/repos/"

    def _get_repository_name(self):
        return super()._get_repository_name()

    def get_releases(self) -> dict[str, list[tuple[str, str]]]:
        headers = {"Accept": "application/vnd.github.v3+json"}

        releases_data = httpx.get(
            url=f"{self._get_api_url()}{self._get_repository_name()}/releases",
            headers=headers,
        )

        result_dict = {}
        for item in releases_data.json():
            result_dict[item["tag_name"]] = [
                (asset["name"], asset["browser_download_url"])
                for asset in item["assets"]
            ]

        return result_dict

    def get_repo_size(self) -> int:
        headers = {"Accept": "application/vnd.github.v3+json"}

        repo_data = httpx.get(
            url=f"{self._get_api_url()}{self._get_repository_name()}",
            headers=headers,
        )

        try:
            repo_size = repo_data.json()["size"]
        except KeyError as err:
            if repo_data.status_code == 403:
                msg = "Rate limit external API"
                raise GitPlatformClientError(msg) from err
            msg = "Invalid Credentials"
            raise GitPlatformClientError(msg) from err

        return repo_size * 1024

    def is_valid_token(self) -> bool:
        headers = {"Accept": "application/vnd.github.v3+json"}

        repo_data = httpx.get(
            url=f"{self._get_api_url()}{self._get_repository_name()}",
            headers=headers,
        )

        try:
            repo_data.json()["id"]
        except KeyError:
            return False

        return True
