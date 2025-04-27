import logging

from app.configs.db import get_hand_session
from app.schemas.pydantic.repo import RepoFilter


def _process_bulk_update_repositories():
    from app.services.repo_service import RepoService

    with get_hand_session() as db:

        repo_service = RepoService(db)

        count, auto_update_repositories = repo_service.repo_repository.list(RepoFilter(is_auto_update_repo=True))
        logging.info(f'{len(auto_update_repositories)} repos update launched')

        for repo in auto_update_repositories:
            logging.info(f'run update repo {repo.uuid}')
            try:
                repo_service.update_units_firmware(repo.uuid, is_auto_update=True)
            except Exception as e:
                logging.error(f'failed to update repo {repo.uuid}: {e}')

        logging.info('task auto update repo successfully completed')
