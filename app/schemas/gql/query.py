from strawberry.tools import create_type

from app.schemas.gql.queries.grafana import (
    get_dashboard,
    get_dashboards,
    get_dashboard_panels,
)
from app.schemas.gql.queries.metrics import get_base_metrics
from app.schemas.gql.queries.permission import get_resource_agents
from app.schemas.gql.queries.repo import (
    get_repo,
    get_repos,
    get_available_platforms,
    get_versions,
)
from app.schemas.gql.queries.repository_registry import (
    get_repository_registry,
    get_branch_commits,
    get_credentials,
    get_repositories_registry,
)
from app.schemas.gql.queries.unit import (
    get_unit,
    get_unit_env,
    get_target_version,
    get_unit_current_schema,
    get_state_storage,
    get_units,
    get_unit_logs,
)
from app.schemas.gql.queries.unit_node import (
    get_unit_node,
    get_pipe_data,
    get_unit_nodes,
    get_data_pipe_config,
    check_data_pipe_config,
)
from app.schemas.gql.queries.user import (
    get_user,
    get_token,
    get_verification_user,
    get_users,
)

Query = create_type(
    "Query",
    [
        get_user,
        get_token,
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
        get_dashboard,
        get_dashboards,
        get_dashboard_panels,
    ],
)
