import base64
import hashlib
import os

from cryptography.hazmat.primitives.asymmetric.mldsa import (
    MLDSA87PrivateKey,
)

from app import settings


class UserKey:
    def __init__(self, private_key: MLDSA87PrivateKey):
        self.private_key = private_key
        raw = private_key.public_key().public_bytes_raw()
        self.public_key = base64.b64encode(raw).decode("ascii")
        self.hash_public_key = hashlib.sha256(raw).hexdigest()

    def sign(self, challenge: str) -> str:
        signature = self.private_key.sign(challenge.encode("utf-8"))
        return base64.b64encode(signature).decode("ascii")


def test_key(seed: str) -> UserKey:
    if settings.pu_test_integration_clear_data:
        material = os.urandom(32)
    else:
        material = hashlib.sha256(seed.encode("utf-8")).digest()
    return UserKey(MLDSA87PrivateKey.from_seed_bytes(material))


def fresh_key() -> UserKey:
    return UserKey(MLDSA87PrivateKey.generate())


REGULAR_USER_KEY = test_key("regular")
ADMIN_USER_KEY = test_key("admin")
