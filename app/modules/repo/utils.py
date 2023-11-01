from git import Repo as GitRepo
from git.exc import GitCommandError
from fastapi import HTTPException
from fastapi import status as http_status

from app.modules.repo.api_models import RepoCreate
from app.modules.repo.sql_models import Repo


def clone_remote_repo(repo: Repo, repo_url: str) -> GitRepo:
    """ Клонирует репозиторий в директорию, определяемую через uuid """

    try:
        # клонирование
        git_repo = GitRepo.clone_from(repo_url, f'repositories/{repo.uuid}')
    except GitCommandError:
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=f"No valid repo_url or credentials")

    # получает все удалённые ветки
    for remote in git_repo.remotes:
        remote.fetch()

    return git_repo


def get_url_for_clone(data: RepoCreate):
    """ Генерирует ссылку с токенами, для скачивания """
    repo_url = data.repo_url
    if not data.is_public_repository:
        repo_url = repo_url.replace(
            'https://',
            f"https://{data.credentials.username}:{data.credentials.pat_token}@"
        ).replace(
            'http://',
            f"http://{data.credentials.username}:{data.credentials.pat_token}@"
        )

    return repo_url


def get_repo(uuid: str) -> GitRepo:
    return GitRepo(f'repositories/{uuid}')


def get_branches_repo(repo: GitRepo) -> list[str]:
    return [r.remote_head for r in repo.remote().refs][1:]


def get_commits_repo(repo: GitRepo, branch: str, depth: int = None) -> list[tuple[str, str]]:
    return [
               (item.name_rev.split()[0], item.summary) for item in repo.iter_commits(rev=f'remotes/origin/{branch}')
           ][:depth]


def get_tags_repo(repo: GitRepo) -> list[tuple]:
    return [(item.name, (item.commit.name_rev.split()[0], item.commit.summary)) for item in repo.tags]

