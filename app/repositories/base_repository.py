from collections.abc import Callable

from fastapi import Depends
from sqlalchemy import UniqueConstraint
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel

from app.configs.db import get_session
from app.configs.errors import (
    CustomException,
    GrafanaError,
    RepoError,
    UnitError,
    UnitGroupError,
)
from app.domain.dashboard_model import Dashboard
from app.domain.dashboard_panel_model import DashboardPanel
from app.domain.repo_model import Repo
from app.domain.unit_group_model import UnitGroup
from app.domain.unit_model import Unit


class BaseRepository[T: SQLModel]:
    db: Session
    model: type[T]

    def __init__(
        self, model: type[T], db: Session = Depends(get_session)
    ) -> None:
        self.model = model
        self.db = db

    def create(self, obj: T) -> T:
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def get(self, obj: T) -> T | None:
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


class UniqueNameMixin[T: SQLModel]:
    """Map a creator name conflict on the model to a domain error.

    List this mixin before BaseRepository so create and update run first.
    """

    db: Session
    model: type[T]
    _name_errors: dict[type[SQLModel], type[CustomException]] = {
        Unit: UnitError,
        UnitGroup: UnitGroupError,
        Repo: RepoError,
        Dashboard: GrafanaError,
        DashboardPanel: GrafanaError,
    }

    def create(self, obj: T) -> T:
        return self._save_unique(super().create, obj)

    def update(self, uuid, obj: T) -> T:
        return self._save_unique(super().update, uuid, obj)

    @staticmethod
    def _creator_name_constraint(model: type[SQLModel]) -> tuple[str, str]:
        found: list[tuple[str, str]] = []
        for constraint in model.__table__.constraints:
            if (
                not isinstance(constraint, UniqueConstraint)
                or not constraint.name
            ):
                continue
            column_names = [column.name for column in constraint.columns]
            if "creator_uuid" not in column_names:
                continue
            fields = [name for name in column_names if name != "creator_uuid"]
            if len(fields) == 1:
                found.append((constraint.name, fields[0]))

        if len(found) != 1:
            msg = f"{model.__name__} creator name constraint is not defined"
            raise RuntimeError(msg)
        return found[0]

    def _save_unique(self, method: Callable[..., T], *args) -> T:
        try:
            return method(*args)
        except IntegrityError as err:
            self.db.rollback()
            constraint_name, field_name = self._creator_name_constraint(
                self.model
            )
            current_name = getattr(
                getattr(err.orig, "diag", None), "constraint_name", None
            )
            if current_name != constraint_name:
                raise
            error_cls = self._name_errors.get(self.model)
            if error_cls is None:
                msg = f"No name error for {self.model.__name__}"
                raise RuntimeError(msg) from err
            message = f"{field_name.capitalize()} is not unique"
            raise error_cls(message) from err
