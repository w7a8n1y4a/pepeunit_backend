import base64
import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric.mldsa import (
    MLDSA87PrivateKey,
)

from app import settings
from app.configs.errors import NoAccessError, UserError
from app.domain.user_model import User
from app.services.auth.challenge import ChallengeService


def _key():
    private_key = MLDSA87PrivateKey.generate()
    raw = private_key.public_key().public_bytes_raw()
    return (
        private_key,
        base64.b64encode(raw).decode("ascii"),
        hashlib.sha256(raw).hexdigest(),
    )


class FakeRedis:
    def __init__(self):
        self.data: dict[str, str] = {}
        self.ttl: dict[str, int | None] = {}

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.data[key] = value
        self.ttl[key] = ex

    async def getdel(self, key: str) -> str | None:
        self.ttl.pop(key, None)
        return self.data.pop(key, None)

    async def close(self) -> None:
        return None


@pytest.fixture
def redis_store(monkeypatch):
    store = FakeRedis()

    async def session():
        yield store

    monkeypatch.setattr(
        "app.services.auth.challenge.get_redis_session",
        session,
    )
    return store


def _user_for(public_key: str, hash_public_key: str):
    user = User(
        uuid=uuid.uuid4(),
        login="tester",
        role="User",
        status="Active",
        public_key=public_key,
        hash_public_key=hash_public_key,
        create_datetime=datetime.now(UTC),
    )
    repository = Mock()
    repository.get.return_value = user
    return user, repository


def _sign(private_key, challenge: str) -> str:
    signature = private_key.sign(challenge.encode("utf-8"))
    return base64.b64encode(signature).decode("ascii")


def test_canonical_public_key_round_trip() -> None:
    _private_key, public_key, digest = _key()
    service = ChallengeService(Mock())
    canonical, hashed = service.canonical_public_key(public_key)
    assert canonical == public_key
    assert hashed == digest


def test_canonical_public_key_rejects_garbage() -> None:
    service = ChallengeService(Mock())
    with pytest.raises(UserError):
        service.canonical_public_key("not-a-key")


async def test_challenge_is_single_use(redis_store) -> None:
    private_key, public_key, digest = _key()
    user, repository = _user_for(public_key, digest)
    service = ChallengeService(repository)
    challenge = await service.issue(user)
    signature = _sign(private_key, challenge)

    accepted = await service.accept(challenge, signature)
    assert accepted.uuid == user.uuid
    assert redis_store.data == {}

    with pytest.raises(NoAccessError, match="used or expired"):
        await service.accept(challenge, signature)


@pytest.mark.usefixtures("redis_store")
async def test_bad_signature_leaves_challenge_usable() -> None:
    private_key, public_key, digest = _key()
    user, repository = _user_for(public_key, digest)
    service = ChallengeService(repository)
    challenge = await service.issue(user)
    other_key, _public_key, _digest = _key()

    with pytest.raises(NoAccessError, match="Signature mismatched"):
        await service.accept(challenge, _sign(other_key, challenge))

    accepted = await service.accept(challenge, _sign(private_key, challenge))
    assert accepted.uuid == user.uuid


@pytest.mark.usefixtures("redis_store")
async def test_challenge_domain_must_match() -> None:
    private_key, public_key, digest = _key()
    user, repository = _user_for(public_key, digest)
    service = ChallengeService(repository)
    token = jwt.encode(
        {
            "type": ChallengeService.TYPE,
            "uuid": str(user.uuid),
            "hash_public_key": user.hash_public_key,
            "domain": "other.example",
            "jti": "foreign",
            "exp": datetime.now(UTC) + timedelta(seconds=60),
        },
        settings.pu_secret_key,
        algorithm="HS256",
    )

    with pytest.raises(NoAccessError, match="domain mismatched"):
        await service.accept(token, _sign(private_key, token))


@pytest.mark.usefixtures("redis_store")
async def test_challenge_expiry() -> None:
    private_key, public_key, digest = _key()
    user, repository = _user_for(public_key, digest)
    service = ChallengeService(repository)
    token = jwt.encode(
        {
            "type": ChallengeService.TYPE,
            "uuid": str(user.uuid),
            "hash_public_key": user.hash_public_key,
            "domain": settings.pu_domain,
            "jti": "stale",
            "exp": datetime.now(UTC) - timedelta(seconds=5),
        },
        settings.pu_secret_key,
        algorithm="HS256",
    )

    with pytest.raises(NoAccessError, match="Challenge expired"):
        await service.accept(token, _sign(private_key, token))
