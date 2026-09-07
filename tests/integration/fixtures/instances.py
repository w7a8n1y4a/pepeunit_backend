import pytest

from app.domain.instance_model import Instance
from app.dto.enum import InstanceTrustStatus
from app.repositories.instance_repository import InstanceRepository
from app.schemas.pydantic.instance import InstanceCreate
from app.services.instance_service import InstanceService
from tests.integration.helpers.names import (
    unique_instance_url,
    unreachable_instance_url,
)
from tests.integration.helpers.services import instance_service


def _create_instance(database, token, url: str) -> Instance:
    return instance_service(database, token).create(InstanceCreate(url=url))


def _delete_instance(database, uuid) -> None:
    InstanceRepository(db=database).delete(Instance(uuid=uuid))


def _drop_by_url(database, url: str) -> None:
    repository = InstanceRepository(db=database)
    for instance in database.query(Instance).filter(Instance.url == url).all():
        repository.delete(Instance(uuid=instance.uuid))


@pytest.fixture(scope="session")
def own_instance(admin_user_token, database) -> Instance:
    """Instance pointing at the current backend, always available for collection"""
    own_url = InstanceService.get_own_url()
    _drop_by_url(database, own_url)

    instance = _create_instance(database, admin_user_token, own_url)
    yield instance
    try:
        _delete_instance(database, instance.uuid)
    except Exception:
        pass


@pytest.fixture
def crud_instance(admin_user_token, database) -> Instance:
    instance = _create_instance(
        database, admin_user_token, unique_instance_url("crud")
    )
    yield instance
    try:
        _delete_instance(database, instance.uuid)
    except Exception:
        pass


@pytest.fixture
def unreachable_instance(admin_user_token, database) -> Instance:
    """Instance with a guaranteed unreachable address"""
    url = unreachable_instance_url()
    _drop_by_url(database, url)

    instance = _create_instance(database, admin_user_token, url)
    yield instance
    try:
        _delete_instance(database, instance.uuid)
    except Exception:
        pass


@pytest.fixture
def pending_instance(admin_user_token, database) -> Instance:
    instance = _create_instance(
        database, admin_user_token, unique_instance_url("pending")
    )
    repository = InstanceRepository(db=database)
    instance.trust_status = InstanceTrustStatus.PENDING.value
    instance = repository.update(instance.uuid, instance)
    yield instance
    try:
        _delete_instance(database, instance.uuid)
    except Exception:
        pass
