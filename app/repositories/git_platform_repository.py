import json
from abc import ABC, abstractmethod

import httpx
from fastapi import HTTPException
from fastapi import status as http_status

from app.domain.repo_model import Repo
from app.schemas.pydantic.repo import Credentials
from app.utils.utils import aes_decode


class GitPlatformRepositoryABC(ABC):

    def __init__(self, repo: Repo):
        self.repo = repo
        self.credentials = None

        if not repo.is_public_repository:
            self.credentials = Credentials(**json.loads(aes_decode(repo.cipher_credentials_private_repository)))

    @abstractmethod
    def get_cloning_url(self) -> str:
        """Get url for cloning"""

        repo_url = self.repo.repo_url
        if not self.repo.is_public_repository:
            username = self.credentials.username
            pat_token = self.credentials.pat_token
            repo_url = repo_url.replace('https://', f"https://{username}:{pat_token}@").replace(
                'http://', f"http://{username}:{pat_token}@"
            )

        return repo_url

    @abstractmethod
    def _get_api_url(self) -> str:
        """Get url for api"""
        pass

    @abstractmethod
    def _get_repository_name(self) -> str:
        """Get repository name with group/creator"""
        _, _, _, *name = self.repo.repo_url.split('/')

        return '/'.join(name).replace('.git', '')

    @abstractmethod
    def get_releases(self) -> dict[str, list[tuple[str, str]]]:
        """Get release information -> {tag: [(name_package, download_link)]}"""
        pass


class GitlabPlatformRepository(GitPlatformRepositoryABC):
    """For Gitlab"""

    def get_cloning_url(self) -> str:
        return super().get_cloning_url()

    def _get_api_url(self) -> str:
        http_str, _, domain, *_ = self.repo.repo_url.split('/')

        return f'{http_str}//{domain}/api/v4/projects/'

    def _get_repository_name(self):
        return super()._get_repository_name()

    def _get_repository_id(self) -> int:

        headers = None
        if self.credentials:
            headers = {
                'PRIVATE-TOKEN': self.credentials.pat_token,
            }

        result_data = httpx.get(
            url=self._get_api_url() + self._get_repository_name().replace('/', '%2F'), headers=headers
        )

        try:
            target_id = result_data.json()['id']
        except KeyError:
            raise HTTPException(
                status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f'Invalid Credentials',
            )

        return target_id

    def get_releases(self) -> dict[str, list[tuple[str, str]]]:
        repository_id = self._get_repository_id()

        headers = None
        if self.credentials:
            headers = {
                'PRIVATE-TOKEN': self.credentials.pat_token,
            }

        releases_data = httpx.get(url=f'{self._get_api_url()}{repository_id}/releases', headers=headers)

        result_dict = {}
        for item in releases_data.json():

            assets_list = []
            for source in item['assets']["sources"]:
                assets_list.append((source['format'], source['url']))

            for link in item['assets']["links"]:
                assets_list.append((link['name'], link['url']))

            result_dict[item['tag_name']] = assets_list

        return result_dict


class GithubPlatformRepository(GitPlatformRepositoryABC):
    """For Github"""

    def get_cloning_url(self) -> str:
        """Get url for cloning"""
        return super().get_cloning_url()

    def _get_api_url(self) -> str:
        """Get url for api"""

        credentials = ''
        if self.credentials:
            credentials = f'{self.credentials.username}:{self.credentials.pat_token}@'

        return f'https://{credentials}api.github.com/repos/'

    def _get_repository_name(self):
        return super()._get_repository_name()

    def get_releases(self) -> dict[str, list[tuple[str, str]]]:

        headers = {"Accept": "application/vnd.github.v3+json"}

        releases_data = httpx.get(url=f'{self._get_api_url()}{self._get_repository_name()}/releases', headers=headers)

        result_dict = {}
        for item in releases_data.json():

            assets_list = []
            for asset in item['assets']:
                assets_list.append((asset['name'], asset['browser_download_url']))

            result_dict[item['tag_name']] = assets_list

        return result_dict
