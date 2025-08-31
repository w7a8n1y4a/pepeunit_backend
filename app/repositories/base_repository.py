from typing import Generic, Optional, Type, TypeVar

from fastapi import Depends
from sqlmodel import Session, SQLModel

from app.configs.db import get_session

T = TypeVar("T", bound=SQLModel)


class BaseRepository(Generic[T]):
    db: Session
    model: Type[T]

    def __init__(self, model: Type[T], db: Session = Depends(get_session)) -> None:
        self.model = model
        self.db = db

    def create(self, obj: T) -> T:
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def get(self, obj: T) -> Optional[T]:
        return self.db.get(self.model, obj.uuid)

    def get_all_count(self) -> int:
        return self.db.query(self.model).count()

    def update(self, uuid, obj: T) -> T:
        obj.uuid = uuid
        self.db.merge(obj)
        self.db.commit()
        return self.get(obj)

    def delete(self, obj: T) -> None:
        self.db.delete(self.get(obj))
        self.db.commit()
        self.db.flush()

    def get_all(self) -> list[T]:
        return self.db.query(self.model).all()
