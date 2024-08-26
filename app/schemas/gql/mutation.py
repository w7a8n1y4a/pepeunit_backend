from strawberry.tools import create_type

from app.schemas.gql.mutations.user import *
from app.schemas.gql.mutations.repo import *
from app.schemas.gql.mutations.unit import *
from app.schemas.gql.mutations.unit_node import *
from app.schemas.gql.mutations.permission import *

Mutation = create_type(
    "Mutation",
    [
        create_user,
        update_user,
        block_user,
        unblock_user,
        create_repo,
        update_repo,
        delete_repo,
        update_repo_credentials,
        update_local_repo,
        update_units_firmware,
        create_unit,
        update_unit,
        update_unit_env,
        update_unit_schema,
        delete_unit,
        update_unit_node,
        set_state_unit_node_input,
        create_permission,
        delete_permission,
        create_unit_node_edge,
        delete_unit_node_edge,
    ],
)
