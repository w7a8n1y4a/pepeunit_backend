from contextlib import contextmanager

from sqlalchemy import update
from sqlmodel import Session

from app.domain.user_model import User
from app.dto.enum import UserRole
from app.repositories.user_repository import UserRepository


def _role_value(role: str | UserRole) -> str:
    return role.value if isinstance(role, UserRole) else role


def _set_role(database: Session, user: User, role: str | UserRole) -> None:
    value = _role_value(role)
    database.expire(user)
    if user.role == value:
        return
    database.execute(
        update(User).where(User.uuid == user.uuid).values(role=value)
    )
    database.commit()
    database.expire_all()


@contextmanager
def as_owner(database: Session, user: User):
    """Give this user Owner, then restore their own previous role.

    Owner checks read the acting user's role. Promoting them directly leaves
    the instance owner in place. set_single_owner would demote that account,
    and only that account can run these tests.
    """
    database.expire(user)
    previous = user.role
    _set_role(database, user, UserRole.OWNER)
    try:
        yield
    finally:
        _set_role(database, user, previous)


@contextmanager
def preserve_instance_owner(database: Session):
    """Put the instance owner back after set_single_owner demotes them."""
    repository = UserRepository(db=database)
    database.expire_all()
    current = repository.get_owner()
    owner_uuid = current.uuid if current is not None else None
    try:
        yield
    finally:
        if owner_uuid is not None:
            database.expire_all()
            restored = repository.get(User(uuid=owner_uuid))
            if restored is not None and restored.role != UserRole.OWNER:
                repository.set_single_owner(owner_uuid)
