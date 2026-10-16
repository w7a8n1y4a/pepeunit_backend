import sys
import uuid

from app.configs.db import get_hand_session
from app.configs.errors import UserError
from app.repositories.user_repository import UserRepository


def assign_owner(user_uuid: uuid.UUID):
    with get_hand_session() as session:
        return UserRepository(session).set_single_owner(user_uuid)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print(
            "Usage: uv run scripts/set_owner.py <user-uuid>",
            file=sys.stderr,
        )
        return 2

    try:
        user_uuid = uuid.UUID(args[0])
    except ValueError:
        print("User uuid is not valid", file=sys.stderr)
        return 2

    try:
        user = assign_owner(user_uuid)
    except UserError as exc:
        print(exc.raw_message, file=sys.stderr)
        return 1

    print(f"Owner set: {user.login} {user.uuid}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
