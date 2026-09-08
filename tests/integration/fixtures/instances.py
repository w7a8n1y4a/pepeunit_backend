from dataclasses import dataclass

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


@dataclass
class LiveInstances:
    own_instance: object
    unreachable_instance: object

    def all(self) -> list:
        return [self.own_instance, self.unreachable_instance]


@pytest.fixture(scope="session")
def trusted_instances(admin_user_token, database) -> LiveInstances:
    own_url = InstanceService.get_own_url()
    unreachable_url = unreachable_instance_url()
    _drop_by_url(database, own_url)
    _drop_by_url(database, unreachable_url)

    instances = LiveInstances(
        own_instance=_create_instance(database, admin_user_token, own_url),
        unreachable_instance=_create_instance(
            database, admin_user_token, unreachable_url
        ),
    )
    yield instances
    for instance in instances.all():
        try:
            _delete_instance(database, instance.uuid)
        except Exception:
            pass


@pytest.fixture(scope="session")
def own_instance(trusted_instances) -> Instance:
    return trusted_instances.own_instance


@pytest.fixture(scope="session")
def unreachable_instance(trusted_instances) -> Instance:
    return trusted_instances.unreachable_instance


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
