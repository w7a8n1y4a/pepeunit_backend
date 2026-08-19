import hashlib
import uuid as uuid_pkg

from app import settings

TEST_HASH = hashlib.md5(settings.pu_domain.encode("utf-8")).hexdigest()[:5]

UNIVERSAL_FIRST_COMMIT = "7b5804d4e945f87d0925c0480706a2c88320fce2"

REGULAR_USER_PASSWORD = "testtest0"
ADMIN_USER_PASSWORD = "testtest1"


def entity_name(role: str) -> str:
    return f"{role}_{TEST_HASH}"


def unique_name(role: str) -> str:
    return f"{role}_{TEST_HASH}_{uuid_pkg.uuid4().hex[:6]}"
