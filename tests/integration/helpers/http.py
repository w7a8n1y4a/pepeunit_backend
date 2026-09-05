import logging
import uuid as uuid_pkg

import httpx

from app import settings
from app.dto.enum import BackendTopicCommand
from app.schemas.pydantic.repo import RepoUpdate
from app.schemas.pydantic.unit import UnitUpdate
from app.schemas.pydantic.unit_node import UnitNodeSetState


def _headers(token: str) -> dict[str, str]:
    return {"accept": "application/json", "x-auth-token": token}


def _status(response: httpx.Response) -> int:
    if response.status_code >= 400:
        logging.error(
            f"{response.request.method} {response.request.url}"
            f" -> {response.status_code}: {response.text}"
        )

    return response.status_code


def patch_unit_commit(token: str, unit, target_version: str) -> int:
    url = f"{settings.pu_link_prefix_and_v1}/units/{unit.uuid}"
    response = httpx.patch(
        url=url,
        json=UnitUpdate(repo_commit=target_version).dict(),
        headers=_headers(token),
        timeout=60,
    )
    return _status(response)


def patch_repo(token: str, repo, repo_update: RepoUpdate) -> int:
    url = f"{settings.pu_link_prefix_and_v1}/repos/{repo.uuid}"
    response = httpx.patch(
        url=url,
        json=repo_update.dict(),
        headers=_headers(token),
        timeout=60,
    )
    return _status(response)


def post_bulk_update_repo(token: str) -> int:
    url = f"{settings.pu_link_prefix_and_v1}/repos/bulk_update"
    response = httpx.post(url=url, headers=_headers(token), timeout=60)
    return _status(response)


def patch_update_units_firmware(token: str, repo) -> int:
    url = (
        f"{settings.pu_link_prefix_and_v1}/repos/update_units_firmware/{repo.uuid}"
    )
    response = httpx.patch(url=url, headers=_headers(token), timeout=60)
    return _status(response)


def post_unit_command(token: str, unit, command: BackendTopicCommand) -> int:
    url = (
        f"{settings.pu_link_prefix_and_v1}/units/"
        f"send_command_to_input_base_topic/{unit.uuid}?command={command.value}"
    )
    response = httpx.post(url=url, headers=_headers(token), timeout=60)
    return _status(response)


def post_schema_update(token: str, unit_uuid: uuid_pkg.UUID) -> int:
    url = (
        f"{settings.pu_link_prefix_and_v1}/units/"
        f"send_command_to_input_base_topic/{unit_uuid}?command=SchemaUpdate"
    )
    response = httpx.post(url=url, headers=_headers(token), timeout=60)
    return _status(response)


def patch_input_state(token: str, unit_node_uuid: uuid_pkg.UUID, state: str) -> int:
    url = f"{settings.pu_link_prefix_and_v1}/unit_nodes/set_state_input/{unit_node_uuid}"
    response = httpx.patch(
        url=url,
        json=UnitNodeSetState(state=state).dict(),
        headers=_headers(token),
        timeout=60,
    )
    return _status(response)


def patch_backend_sync_registry(token: str) -> int:
    url = f"{settings.pu_link_prefix_and_v1}/repository_registry/backend_sync_registry"
    response = httpx.patch(url=url, headers=_headers(token), timeout=60)
    return _status(response)
