import uuid as uuid_pkg

from fastapi import Depends
from fastapi.params import Query
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.configs.db import get_session
from app.configs.errors import UserError
from app.domain.user_model import User
from app.dto.enum import UserRole
from app.repositories.base_repository import BaseRepository
from app.repositories.utils import (
    apply_enums,
    apply_ilike_search_string,
    apply_offset_and_limit,
    apply_orders_by,
)
from app.schemas.pydantic.user import UserFilter
from app.services.validators import is_valid_string_with_rules, is_valid_uuid


class UserRepository(BaseRepository):
    def __init__(self, db: Session = Depends(get_session)) -> None:
        super().__init__(User, db)

    def create(self, obj: User) -> User:
        try:
            return super().create(obj)
        except IntegrityError as err:
            self.db.rollback()
            if err.orig.diag.constraint_name in {
                "users_public_key_key",
                "users_hash_public_key_key",
            }:
                msg = "Public key is not unique"
                raise UserError(msg) from err
            raise

    def get_user_by_hash_public_key(self, hash_public_key: str) -> User | None:
        return self.db.exec(
            select(User).where(User.hash_public_key == hash_public_key)
        ).first()

    def get_user_by_telegram_id(self, telegram_chat_id: str):
        return self.db.exec(
            select(User).where(User.telegram_chat_id == telegram_chat_id)
        ).first()

    def get_owner(self) -> User | None:
        return self.db.exec(
            select(User).where(User.role == UserRole.OWNER.value)
        ).first()

    def set_single_owner(self, user_uuid: uuid_pkg.UUID) -> User:
        self.db.execute(
            update(User)
            .where(
                User.role == UserRole.OWNER.value,
                User.uuid != user_uuid,
            )
            .values(role=UserRole.USER.value)
        )
        result = self.db.execute(
            update(User)
            .where(User.uuid == user_uuid)
            .values(role=UserRole.OWNER.value)
        )
        if not result.rowcount:
            self.db.rollback()
            msg = "User does not exist"
            raise UserError(msg)

        self.db.commit()
        self.db.expire_all()
        return self.get(User(uuid=user_uuid))

    def list(self, filters: UserFilter) -> tuple[int, list[User]]:
        query = self.db.query(User)

        filters.uuids = (
            filters.uuids.default
            if isinstance(filters.uuids, Query)
            else filters.uuids
        )
        if filters.uuids:
            query = query.filter(
                User.uuid.in_([is_valid_uuid(item) for item in filters.uuids])
            )

        fields = [User.login]
        query = apply_ilike_search_string(query, filters, fields)

        fields = {"role": User.role, "status": User.status}
        query = apply_enums(query, filters, fields)

        fields = {"order_by_create_date": User.create_datetime}
        query = apply_orders_by(query, filters, fields)

        count, query = apply_offset_and_limit(query, filters)
        return count, query.all()

    def is_valid_login(self, login: str) -> None:
        if not is_valid_string_with_rules(login):
            msg = "Login is not correct"
            raise UserError(msg)

    def is_valid_telegram_chat_id(
        self, telegram_chat_id: str, uuid: uuid_pkg.UUID | None = None
    ):
        uuid = str(uuid)
        user_uuid = self.db.exec(
            select(User.uuid).where(User.telegram_chat_id == telegram_chat_id)
        ).first()
        user_uuid = str(user_uuid) if user_uuid else user_uuid

        if (uuid is None and user_uuid) or (
            uuid and user_uuid != uuid and user_uuid is not None
        ):
            msg = "This Telegram account is already linked"
            raise UserError(msg)
