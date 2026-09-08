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


def instance_url(role: str) -> str:
    return (
        f"https://{role}-{TEST_HASH}.pepeunit.test"
        f"{settings.pu_app_prefix}{settings.pu_api_v1_prefix}"
        "/instances/current"
    )


def unique_instance_url(role: str) -> str:
    return instance_url(f"{role}-{uuid_pkg.uuid4().hex[:6]}")


def unreachable_instance_url() -> str:
    return f"http://127.0.0.1:1/{TEST_HASH}/instances/current"
