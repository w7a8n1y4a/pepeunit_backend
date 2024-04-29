from strawberry.tools import create_type

from app.schemas.gql.mutations.user import *
from app.schemas.gql.mutations.repo import *
from app.schemas.gql.mutations.unit import *

Mutation = create_type(
    "Mutation",
    [
        create_user,
        update_user,
        delete_user,
        create_repo,
        update_repo,
        delete_repo,
        update_repo_credentials,
        update_repo_default_branch,
        update_local_repo,
        create_unit,
        update_unit,
        update_unit_env,
        delete_unit,
    ],
)
