from strawberry.tools import create_type

from app.schemas.gql.mutations.grafana import (
    create_dashboard,
    create_dashboard_panel,
    delete_dashboard,
    delete_link,
    delete_panel,
    link_unit_node_to_panel,
    sync_dashboard,
)
from app.schemas.gql.mutations.permission import (
    create_permission,
    delete_permission,
)
from app.schemas.gql.mutations.repo import (
    bulk_update,
    create_repo,
    delete_repo,
    update_repo,
    update_units_firmware,
)
from app.schemas.gql.mutations.repository_registry import (
    create_repository_registry,
    delete_repository_registry,
    set_credentials,
    update_local_repository,
)
from app.schemas.gql.mutations.unit import (
    create_unit,
    delete_unit,
    send_command_to_input_base_topic,
    set_state_storage,
    update_unit,
    update_unit_env,
)
from app.schemas.gql.mutations.unit_node import (
    create_unit_node_edge,
    delete_data_pipe_data,
    delete_unit_node_edge,
    set_data_pipe_config,
    set_data_pipe_data_csv,
    set_state_unit_node_input,
    update_unit_node,
)
from app.schemas.gql.mutations.user import (
    block_user,
    create_user,
    delete_user_cookies,
    set_grafana_cookies,
    unblock_user,
    update_user,
)

Mutation = create_type(
    "Mutation",
    [
        create_user,
        update_user,
        set_grafana_cookies,
        block_user,
        unblock_user,
        delete_user_cookies,
        create_repo,
        update_repo,
        delete_repo,
        create_repository_registry,
        set_credentials,
        update_local_repository,
        delete_repository_registry,
        update_units_firmware,
        bulk_update,
        create_unit,
        update_unit,
        update_unit_env,
        set_state_storage,
        send_command_to_input_base_topic,
        delete_unit,
        update_unit_node,
        set_state_unit_node_input,
        create_permission,
        delete_permission,
        create_unit_node_edge,
        delete_unit_node_edge,
        set_data_pipe_config,
        set_data_pipe_data_csv,
        delete_data_pipe_data,
        create_dashboard,
        create_dashboard_panel,
        link_unit_node_to_panel,
        sync_dashboard,
        delete_dashboard,
        delete_panel,
        delete_link,
    ],
)
