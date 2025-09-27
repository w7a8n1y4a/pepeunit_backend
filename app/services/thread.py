import logging

from app.configs.clickhouse import get_hand_clickhouse_client
from app.configs.db import get_hand_session
from app.schemas.pydantic.repo import RepoFilter


def _process_bulk_update_units_firmware():
    from app.configs.rest import get_repo_service

    with get_hand_session() as db, get_hand_clickhouse_client() as cc:
        repo_service = get_repo_service(db, cc, None)

        count, auto_update_repositories = repo_service.repo_repository.list(
            RepoFilter(is_auto_update_repo=True)
        )
        logging.info(f"{len(auto_update_repositories)} repos update launched")

        for repo in auto_update_repositories:
            logging.info(f"run update repo {repo.uuid}")
            try:
                repo_service.update_units_firmware(
                    repo.uuid, is_auto_update=True
                )
            except Exception as e:
                logging.error(f"failed to update repo {repo.uuid}: {e}")

        logging.info("task auto update repo successfully completed")
