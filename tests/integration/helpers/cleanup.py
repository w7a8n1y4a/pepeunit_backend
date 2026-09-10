import os
import shutil
from datetime import UTC, datetime

from sqlmodel import Session

from app import settings
from app.domain.instance_model import Instance
from app.domain.repository_registry_model import RepositoryRegistry
from app.domain.user_model import User
from app.dto.enum import InstanceTrustStatus
from app.repositories.instance_repository import InstanceRepository
from app.services.instance_service import InstanceService
from tests.integration.helpers.names import TEST_HASH
from tests.integration.helpers.private_repos import all_known_repo_urls


def ensure_own_instance(database: Session) -> None:
    own_url = InstanceService.get_own_url()
    repository = InstanceRepository(db=database)
    existing = (
        database.query(Instance).filter(Instance.url == own_url).first()
    )
    if existing:
        return

    repository.create(
        Instance(
            url=own_url,
            trust_status=InstanceTrustStatus.TRUST.value,
            create_datetime=datetime.now(UTC),
        )
    )


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

    # OperationTask is deleted by cascade together with test Users
    own_url = InstanceService.get_own_url()
    database.query(Instance).where(
        Instance.url.ilike(f"%{TEST_HASH}%"),
        Instance.url != own_url,
    ).delete()

    database.query(User).where(User.login.ilike(f"%{TEST_HASH}%")).delete()
    database.commit()
    ensure_own_instance(database)
