from strawberry.tools import create_type

from app.schemas.gql.queries.repo import *
from app.schemas.gql.queries.user import *
from app.schemas.gql.queries.unit import *


Query = create_type("Query", [get_user, get_token, get_users, get_repo, get_repos, get_unit, get_unit_env, get_units])
