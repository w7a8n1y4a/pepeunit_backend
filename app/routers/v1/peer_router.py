import uuid as uuid_pkg

from fastapi import APIRouter, Depends, status

from app.configs.rest import get_peer_service
from app.schemas.pydantic.peer import (
    PeerCreate,
    PeerFilter,
    PeerRead,
    PeerReposPage,
    PeersPage,
    PeerUpdate,
    PeerUrlsPage,
)
from app.services.peer_service import PeerService

router = APIRouter()


@router.get("", response_model=PeersPage)
def get_peers(
    filters: PeerFilter = Depends(PeerFilter),
    peer_service: PeerService = Depends(get_peer_service),
):
    return peer_service.get_cached_peers(filters)


@router.get("/urls", response_model=PeerUrlsPage)
def get_peer_urls(
    filters: PeerFilter = Depends(PeerFilter),
    peer_service: PeerService = Depends(get_peer_service),
):
    return peer_service.get_cached_urls(filters)


@router.get("/repos", response_model=PeerReposPage)
def get_peer_repos(
    filters: PeerFilter = Depends(PeerFilter),
    peer_service: PeerService = Depends(get_peer_service),
):
    return peer_service.get_cached_repos(filters)


@router.post(
    "",
    response_model=PeerRead,
    status_code=status.HTTP_201_CREATED,
)
def create_peer(
    data: PeerCreate,
    peer_service: PeerService = Depends(get_peer_service),
):
    return peer_service.mapper_peer_to_peer_read(peer_service.create(data))


@router.post("/scan_all", status_code=status.HTTP_204_NO_CONTENT)
def scan_peers(
    peer_service: PeerService = Depends(get_peer_service),
):
    peer_service.scan_all()


@router.post("/scan/{uuid}", status_code=status.HTTP_204_NO_CONTENT)
def scan_peer(
    uuid: uuid_pkg.UUID,
    peer_service: PeerService = Depends(get_peer_service),
):
    peer_service.scan_one(uuid)


@router.patch("/{uuid}", response_model=PeerRead)
def update_peer(
    uuid: uuid_pkg.UUID,
    data: PeerUpdate,
    peer_service: PeerService = Depends(get_peer_service),
):
    return peer_service.mapper_peer_to_peer_read(
        peer_service.update(uuid, data)
    )


@router.delete("/{uuid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_peer(
    uuid: uuid_pkg.UUID,
    peer_service: PeerService = Depends(get_peer_service),
):
    peer_service.delete(uuid)
