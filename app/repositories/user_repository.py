from typing import Union

from fastapi import Depends
from fastapi import HTTPException
from fastapi import status as http_status
from sqlalchemy import or_
from sqlmodel import Session, select

from app.configs.db import get_session
from app.domain.user_model import User
from app.repositories.utils import apply_ilike_search_string, apply_enums, apply_offset_and_limit, apply_orders_by
from app.schemas.gql.inputs.user import UserFilterInput
from app.schemas.pydantic.user import UserFilter


class UserRepository:
    db: Session

    def __init__(self, db: Session = Depends(get_session)) -> None:
        self.db = db

    def create(self, user: User) -> User:
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def get(self, user: User) -> User:
        return self.db.get(User, user.uuid)

    def get_all_count(self) -> int:
        return self.db.query(User.uuid).count()

    def get_user_by_credentials(self, credentials: str) -> User:
        return self.db.exec(select(User).where(or_(User.login == credentials, User.telegram_chat_id == credentials))).first()

    def update(self, uuid, user: User) -> User:
        user.uuid = uuid
        self.db.merge(user)
        self.db.commit()
        return self.get(user)

    def delete(self, user: User) -> None:
        self.db.delete(self.get(user))
        self.db.commit()
        self.db.flush()

    def list(self, filters: Union[UserFilter, UserFilterInput]) -> list[User]:
        query = self.db.query(User)

        fields = [User.login]
        query = apply_ilike_search_string(query, filters, fields)

        fields = {'role': User.role, 'status': User.status}
        query = apply_enums(query, filters, fields)

        fields = {'order_by_create_date': User.create_datetime}
        query = apply_orders_by(query, filters, fields)

        query = apply_offset_and_limit(query, filters)
        return query.all()

    def is_valid_login(self, login: str, uuid: str = None):
        user_uuid = self.db.exec(select(User.uuid).where(User.login == login)).first()
        user_uuid = str(user_uuid) if user_uuid else user_uuid

        if (uuid is None and user_uuid) or (uuid and user_uuid != uuid and user_uuid is not None):
            raise HTTPException(status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Login is not unique")

    def is_valid_telegram_chat_id(self, telegram_chat_id: str, uuid: str = None):
        user_uuid = self.db.exec(select(User.uuid).where(User.telegram_chat_id == telegram_chat_id)).first()
        user_uuid = str(user_uuid) if user_uuid else user_uuid

        if (uuid is None and user_uuid) or (uuid and user_uuid != uuid and user_uuid is not None):
            raise HTTPException(status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"This Telegram user is already verified")