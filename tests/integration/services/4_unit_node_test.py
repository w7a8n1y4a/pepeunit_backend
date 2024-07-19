import time

import fastapi
import pytest

from app.configs.gql import get_unit_node_service
from app.repositories.enum import VisibilityLevel, UnitNodeTypeEnum
from app.schemas.pydantic.unit_node import UnitNodeFilter, UnitNodeUpdate, UnitNodeEdgeCreate
from tests.integration.conftest import Info


@pytest.mark.run(order=0)
def test_update_unit_node(database) -> None:

    current_user = pytest.users[0]
    unit_node_service = get_unit_node_service(Info({'db': database, 'jwt_token': pytest.user_tokens_dict[current_user.uuid]}))

    target_unit = pytest.units[-2]

    input_unit_node = unit_node_service.list(
        UnitNodeFilter(
            unit_uuid=target_unit.uuid,
            type=[UnitNodeTypeEnum.INPUT]
        )
    )

    # check update visibility level
    update_unit_node = unit_node_service.update(
        input_unit_node[0].uuid,
        UnitNodeUpdate(
            visibility_level=VisibilityLevel.PUBLIC
        )
    )
    assert update_unit_node.visibility_level == VisibilityLevel.PUBLIC

    # check update is_rewritable_input fot input
    update_unit_node = unit_node_service.update(
        input_unit_node[0].uuid,
        UnitNodeUpdate(
            is_rewritable_input=True
        )
    )
    assert update_unit_node.is_rewritable_input == True

    output_unit_node = unit_node_service.list(
        UnitNodeFilter(
            unit_uuid=target_unit.uuid,
            type=[UnitNodeTypeEnum.OUTPUT]
        )
    )

    # check update is_rewritable_input for output
    with pytest.raises(fastapi.HTTPException):
        update_unit_node = unit_node_service.update(
            output_unit_node[0].uuid,
            UnitNodeUpdate(
                is_rewritable_input=True
            )
        )


@pytest.mark.run(order=1)
def test_create_unit_node_edge(database) -> None:

    current_user = pytest.users[0]
    unit_node_service = get_unit_node_service(Info({'db': database, 'jwt_token': pytest.user_tokens_dict[current_user.uuid]}))

    target_units = pytest.units[-3:]

    io_units_list = []
    for unit in target_units:
        unit_nodes = unit_node_service.list(
            UnitNodeFilter(
                unit_uuid=unit.uuid
            )
        )

        # first input, two output - [Input, Output]
        if unit_nodes[0].type == UnitNodeTypeEnum.OUTPUT:
            unit_nodes = unit_nodes[::-1]

        io_units_list.append(unit_nodes)

    for input_node, output_node in io_units_list:
        unit_node_service.create_node_edge(
            UnitNodeEdgeCreate(
                node_output_uuid=output_node.uuid,
                node_input_uuid=input_node.uuid
            )
        )

    assert False
