from strawberry.tools import create_type

from app.schemas.gql.queries.metrics import *
from app.schemas.gql.queries.permission import *
from app.schemas.gql.queries.repo import *
from app.schemas.gql.queries.repository_registry import *
from app.schemas.gql.queries.unit import *
from app.schemas.gql.queries.unit_node import *
from app.schemas.gql.queries.user import *

Query = create_type(
    "Query",
    [
        get_user,
        get_token,
        get_grafana_token,
        get_verification_user,
        get_users,
        get_repo,
        get_repos,
        get_repository_registry,
        get_branch_commits,
        get_credentials,
        get_repositories_registry,
        get_available_platforms,
        get_versions,
        get_unit,
        get_unit_env,
        get_target_version,
        get_unit_current_schema,
        get_state_storage,
        get_units,
        get_unit_logs,
        get_unit_node,
        get_pipe_data,
        get_unit_nodes,
        check_data_pipe_config,
        get_data_pipe_config,
        get_base_metrics,
        get_resource_agents,
    ],
)
