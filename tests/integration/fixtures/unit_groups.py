import pytest

from app import settings
from app.schemas.pydantic.unit_group import UnitGroupCreate
from tests.integration.helpers.names import entity_name
from tests.integration.helpers.services import unit_group_service


def _delete_group(service, uuid) -> None:
    try:
        service.delete(uuid)
    except Exception:
        pass


def _create_group(service, name: str, units: list):
    group = service.create(UnitGroupCreate(name=entity_name(name)))
    for unit in units:
        service.link_unit(group.uuid, unit.uuid)
    return group


@pytest.fixture(scope="session")
def live_unit_groups(live_units, regular_user_token, database):
    """Groups of the demo units.

    Left in the database for the frontend when
    PU_TEST_INTEGRATION_CLEAR_DATA=False, same as live units and the
    grafana test0 dashboard.
    """
    service = unit_group_service(database, regular_user_token)
    groups = (
        _create_group(
            service,
            "grp_main",
            [
                live_units.universal_manual_unit,
                live_units.universal_auto_unit,
                live_units.compile_unit,
            ],
        ),
        _create_group(
            service,
            "grp_pipe",
            [
                live_units.last_value_unit,
                live_units.n_records_unit,
                live_units.time_window_unit,
            ],
        ),
        _create_group(
            service,
            "grp_chain",
            [
                live_units.chain_source_unit,
                live_units.chain_middle_unit,
                live_units.chain_sink_unit,
            ],
        ),
    )
    yield groups
    if settings.pu_test_integration_clear_data:
        for group in groups:
            _delete_group(service, group.uuid)
