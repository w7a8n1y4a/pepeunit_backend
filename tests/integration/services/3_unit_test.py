import fastapi
import pytest

from app.configs.gql import get_unit_service
from app.schemas.pydantic.unit import UnitCreate
from tests.integration.conftest import Info


@pytest.mark.run(order=0)
def test_create_unit(database) -> None:

    current_user = pytest.users[0]
    unit_service = get_unit_service(Info({'db': database, 'jwt_token': pytest.user_tokens_dict[current_user.uuid]}))

    # todo перенести в conftest, основные виды unit, добавить некоторым нужные версии и ветки

    # create test units
    new_units = []
    for inc, test_repo in enumerate(pytest.repos[-3:]):
        unit = unit_service.create(
            UnitCreate(
                repo_uuid=test_repo.uuid,
                visibility_level=test_repo.visibility_level,
                name=f'test_{inc}_{pytest.test_hash}',
                is_auto_update_from_repo_unit=False
            )
        )
        new_units.append(unit)

    assert False
