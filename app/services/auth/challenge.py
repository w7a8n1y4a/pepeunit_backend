import base64
import binascii
import hashlib
import secrets
from datetime import UTC, datetime, timedelta

import jwt
from cryptography.exceptions import InvalidSignature, UnsupportedAlgorithm
from cryptography.hazmat.primitives.asymmetric.mldsa import MLDSA87PublicKey

from app import settings
from app.configs.errors import NoAccessError, UserError
from app.configs.redis import get_redis_session
from app.domain.user_model import User
from app.repositories.user_repository import UserRepository
from app.services.validators import is_valid_uuid


class ChallengeService:
    # ML-DSA-87 raw public key size, FIPS 204.
    PUBLIC_KEY_BYTES = 2592
    # One-time pass for this instance. The client has one to two minutes to sign it.
    TTL_SECONDS = 120
    TYPE = "challenge"
    _KEY = "user_auth_challenge:{jti}"
    _HASH_LENGTH = 64

    def __init__(self, user_repository: UserRepository) -> None:
        self.user_repository = user_repository

    def canonical_public_key(self, public_key: str) -> tuple[str, str]:
        try:
            raw = base64.b64decode(public_key.strip(), validate=True)
        except (binascii.Error, ValueError) as err:
            msg = "Public key is not correct"
            raise UserError(msg) from err

        if len(raw) != self.PUBLIC_KEY_BYTES:
            msg = "Public key is not correct"
            raise UserError(msg)

        try:
            MLDSA87PublicKey.from_public_bytes(raw)
        except (ValueError, UnsupportedAlgorithm) as err:
            msg = "Public key is not correct"
            raise UserError(msg) from err

        canonical = base64.b64encode(raw).decode("ascii")
        digest = hashlib.sha256(raw).hexdigest()
        return canonical, digest

    def normalize_public_key_hash(self, hash_public_key: str) -> str:
        digest = hash_public_key.strip().lower()
        if len(digest) != self._HASH_LENGTH or any(
            char not in "0123456789abcdef" for char in digest
        ):
            msg = "Public key hash is not correct"
            raise UserError(msg)
        return digest

    async def issue(self, user: User) -> str:
        jti = secrets.token_urlsafe(32)
        token = jwt.encode(
            {
                "type": self.TYPE,
                "uuid": str(user.uuid),
                "hash_public_key": user.hash_public_key,
                "domain": settings.pu_domain,
                "jti": jti,
                "exp": datetime.now(UTC) + timedelta(seconds=self.TTL_SECONDS),
            },
            settings.pu_secret_key,
            algorithm="HS256",
        )
        redis = await anext(get_redis_session())
        try:
            await redis.set(
                self._KEY.format(jti=jti),
                str(user.uuid),
                ex=self.TTL_SECONDS,
            )
        finally:
            await redis.close()
        return token

    async def accept(self, challenge: str, signature: str) -> User:
        data = self._decode(challenge)
        user_uuid = is_valid_uuid(str(data["uuid"]))
        user = self.user_repository.get(User(uuid=user_uuid))
        if not user or user.hash_public_key != data["hash_public_key"]:
            msg = "Challenge is invalid"
            raise NoAccessError(msg)

        self._verify_signature(user.public_key, challenge, signature)
        await self._consume(data["jti"], str(user.uuid))
        return user

    def _decode(self, challenge: str) -> dict:
        try:
            data = jwt.decode(
                challenge,
                settings.pu_secret_key,
                algorithms=["HS256"],
                options={
                    "require": ["exp", "jti", "domain", "uuid", "type"],
                },
            )
        except jwt.ExpiredSignatureError as err:
            msg = "Challenge expired"
            raise NoAccessError(msg) from err
        except jwt.InvalidTokenError as err:
            msg = "Challenge is invalid"
            raise NoAccessError(msg) from err

        if data.get("type") != self.TYPE:
            msg = "Challenge is invalid"
            raise NoAccessError(msg)
        if data.get("domain") != settings.pu_domain:
            msg = "Challenge domain mismatched"
            raise NoAccessError(msg)
        return data

    def _verify_signature(
        self, public_key: str, challenge: str, signature: str
    ) -> None:
        try:
            raw_key = base64.b64decode(public_key, validate=True)
            raw_signature = base64.b64decode(signature, validate=True)
            key = MLDSA87PublicKey.from_public_bytes(raw_key)
            # Empty ML-DSA context. The client signs the challenge JWT bytes.
            key.verify(raw_signature, challenge.encode("utf-8"))
        except (
            InvalidSignature,
            ValueError,
            binascii.Error,
            UnsupportedAlgorithm,
        ) as err:
            msg = "Signature mismatched"
            raise NoAccessError(msg) from err

    async def _consume(self, jti: str, user_uuid: str) -> None:
        redis = await anext(get_redis_session())
        try:
            stored = await redis.getdel(self._KEY.format(jti=jti))
        finally:
            await redis.close()
        if stored != user_uuid:
            msg = "Challenge is used or expired"
            raise NoAccessError(msg)
