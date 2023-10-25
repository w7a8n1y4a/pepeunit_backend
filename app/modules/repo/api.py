from fastapi import APIRouter, Depends
from fastapi_filter import FilterDepends
from starlette.status import HTTP_200_OK

from app.core.auth.user_auth import user_token_required, Context
from app.modules.repo import crud
from app.modules.repo.api_models import RepoRead, Credentials, RepoCreate, RepoUpdate, RepoFilter

router = APIRouter()


@router.post("", response_model=RepoRead, status_code=HTTP_200_OK)
def create_repo(data: RepoCreate, context: Context = Depends(user_token_required)):
    return crud.create(data, context.user, context.db)


@router.put("/credentials/{uuid}", response_model=RepoRead, status_code=HTTP_200_OK)
def update_credentials_private_repo(uuid: str, data: Credentials, context: Context = Depends(user_token_required)):
    return crud.update_credentials_private(uuid, data, context.user, context.db)


@router.put("/default_branch/{uuid}", response_model=RepoRead, status_code=HTTP_200_OK)
def set_default_branch_repo(uuid: str, default_branch: str, context: Context = Depends(user_token_required)):
    return crud.set_default_branch(uuid, default_branch, context.user, context.db)


@router.put("/{uuid}", response_model=RepoRead, status_code=HTTP_200_OK)
def update_repo(uuid: str, data: RepoUpdate, context: Context = Depends(user_token_required)):
    return crud.update(uuid, data, context.user, context.db)


@router.get("/{uuid}", response_model=RepoRead, status_code=HTTP_200_OK)
def get_repo(uuid: str, context: Context = Depends(user_token_required)):
    return crud.get(uuid, context.user, context.db)


@router.get("", response_model=list[RepoRead], status_code=HTTP_200_OK)
def get_repos(filters: RepoFilter = FilterDepends(RepoFilter), context: Context = Depends(user_token_required)):
    return crud.gets(filters, context.user, context.db)
