import contextlib
from dataclasses import dataclass

import pytest

from app import settings
from app.domain.peer_model import Peer
from app.dto.enum import PeerTrustStatus
from app.repositories.peer_repository import PeerRepository
from app.schemas.pydantic.peer import PeerCreate
from app.services.peer_service import PeerService
from tests.integration.helpers.names import (
    unique_peer_url,
    unreachable_peer_url,
)
from tests.integration.helpers.services import peer_service


def _create_peer(database, token, url: str) -> Peer:
    return peer_service(database, token).create(PeerCreate(url=url))


def _delete_peer(database, uuid) -> None:
    PeerRepository(db=database).delete(Peer(uuid=uuid))


def _drop_by_url(database, url: str) -> None:
    repository = PeerRepository(db=database)
    for peer in database.query(Peer).filter(Peer.url == url).all():
        repository.delete(Peer(uuid=peer.uuid))


def _own_peer(database, token) -> Peer:
    own_url = PeerService.get_own_url()
    existing = database.query(Peer).filter(Peer.url == own_url).first()
    if existing is not None and not settings.pu_test_integration_clear_data:
        return existing

    _drop_by_url(database, own_url)
    return _create_peer(database, token, own_url)


@dataclass
class LivePeers:
    own_peer: object
    unreachable_peer: object

    def all(self) -> list:
        return [self.own_peer, self.unreachable_peer]


@pytest.fixture(scope="session")
def trusted_peers(admin_user_token, database) -> LivePeers:
    unreachable_url = unreachable_peer_url()
    _drop_by_url(database, unreachable_url)

    peers = LivePeers(
        own_peer=_own_peer(database, admin_user_token),
        unreachable_peer=_create_peer(
            database, admin_user_token, unreachable_url
        ),
    )
    yield peers
    with contextlib.suppress(Exception):
        _delete_peer(database, peers.unreachable_peer.uuid)


@pytest.fixture(scope="session")
def own_peer(trusted_peers) -> Peer:
    return trusted_peers.own_peer


@pytest.fixture(scope="session")
def unreachable_peer(trusted_peers) -> Peer:
    return trusted_peers.unreachable_peer


@pytest.fixture
def crud_peer(admin_user_token, database) -> Peer:
    peer = _create_peer(database, admin_user_token, unique_peer_url("crud"))
    yield peer
    with contextlib.suppress(Exception):
        _delete_peer(database, peer.uuid)


@pytest.fixture
def pending_peer(admin_user_token, database) -> Peer:
    peer = _create_peer(database, admin_user_token, unique_peer_url("pending"))
    repository = PeerRepository(db=database)
    peer.trust_status = PeerTrustStatus.PENDING.value
    peer = repository.update(peer.uuid, peer)
    yield peer
    with contextlib.suppress(Exception):
        _delete_peer(database, peer.uuid)
