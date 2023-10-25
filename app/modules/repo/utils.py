from git import Repo


def clone_repo(uuid: str, repo_url: str) -> Repo:

    # клонирует репозиторий в определённую директорию
    repo = Repo.clone_from(repo_url, f'repositories/{uuid}')

    # получает все удалённые ветки
    for remote in repo.remotes:
        remote.fetch()

    return repo


def get_repo(uuid: str) -> Repo:
    return Repo(f'repositories/{uuid}')


def get_branches_repo(repo: Repo) -> list[str]:
    return [r.remote_head for r in repo.remote().refs]


def get_commits_repo(repo: Repo, branch: str, depth: int) -> list[tuple]:
    return [(item.name_rev.split()[0], item.summary) for item in repo.iter_commits(rev=f'remotes/origin/{branch}')][:depth]


def get_tags_repo(repo: Repo) -> list[tuple]:
    return [(item.name, (item.commit.name_rev.split()[0], item.commit.summary)) for item in repo.tags]

