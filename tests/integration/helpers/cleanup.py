import shutil
from datetime import UTC, datetime

from sqlmodel import Session

from app.domain.instance_model import Instance
from app.domain.repository_registry_model import RepositoryRegistry
from app.domain.user_model import User
from app.dto.enum import InstanceTrustStatus
from app.repositories.git_repo_repository import GitRepoRepository
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


def _drop_test_registries(database: Session) -> None:
    urls = all_known_repo_urls()
    if not urls:
        return

    git_repo_repository = GitRepoRepository()
    registries = (
        database.query(RepositoryRegistry)
        .where(RepositoryRegistry.repository_url.in_(urls))
        .all()
    )
    for registry in registries:
        git_repo_repository.delete_repo(registry)

    database.query(RepositoryRegistry).where(
        RepositoryRegistry.repository_url.in_(urls)
    ).delete()


def clear_integration_data(database: Session) -> None:
    shutil.rmtree("tmp/test_units", ignore_errors=True)
    shutil.rmtree("tmp/test_units_tar_tgz", ignore_errors=True)
    _drop_test_registries(database)

    # OperationTask is deleted by cascade together with test Users
    own_url = InstanceService.get_own_url()
    database.query(Instance).where(
        Instance.url.ilike(f"%{TEST_HASH}%"),
        Instance.url != own_url,
    ).delete()

    database.query(User).where(User.login.ilike(f"%{TEST_HASH}%")).delete()
    database.commit()
    ensure_own_instance(database)
