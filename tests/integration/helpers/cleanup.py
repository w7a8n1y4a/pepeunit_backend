import os
import shutil

from sqlmodel import Session

from app import settings
from app.domain.repository_registry_model import RepositoryRegistry
from app.domain.user_model import User
from tests.integration.helpers.names import TEST_HASH
from tests.integration.helpers.private_repos import all_known_repo_urls


def clear_integration_data(database: Session) -> None:
    shutil.rmtree("tmp/test_units", ignore_errors=True)
    shutil.rmtree("tmp/test_units_tar_tgz", ignore_errors=True)

    if os.path.isdir(settings.pu_save_repo_path):
        for item in os.listdir(settings.pu_save_repo_path):
            item_path = os.path.join(settings.pu_save_repo_path, item)
            if os.path.isdir(item_path):
                shutil.rmtree(item_path, ignore_errors=True)

    urls = all_known_repo_urls()
    if urls:
        database.query(RepositoryRegistry).where(
            RepositoryRegistry.repository_url.in_(urls)
        ).delete()

    database.query(User).where(User.login.ilike(f"%{TEST_HASH}%")).delete()
    database.commit()
