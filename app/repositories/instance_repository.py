from fastapi import Depends
from sqlmodel import Session, col, func, select

from app.configs.db import get_session
from app.domain.instance_model import Instance
from app.dto.enum import InstanceTrustStatus
from app.repositories.base_repository import BaseRepository
from app.schemas.pydantic.instance import InstanceFilter


class InstanceRepository(BaseRepository[Instance]):
    def __init__(self, db: Session = Depends(get_session)) -> None:
        super().__init__(Instance, db)

    def get_by_url(self, url: str) -> Instance | None:
        return self.db.exec(
            select(Instance).where(Instance.url == url)
        ).first()

    def get_all_sorted(self) -> list[Instance]:
        return list(
            self.db.exec(
                select(Instance).order_by(
                    col(Instance.last_success_datetime).desc().nullslast(),
                    Instance.url,
                )
            ).all()
        )

    def list_urls(
        self,
        filters: InstanceFilter,
    ) -> tuple[int, list[str]]:
        count = self.db.exec(select(func.count()).select_from(Instance)).one()
        urls = self.db.exec(
            select(Instance.url)
            .order_by(Instance.url)
            .offset(filters.offset)
            .limit(filters.limit)
        ).all()
        return count, list(urls)

    def get_all_urls(self) -> list[str]:
        return list(
            self.db.exec(select(Instance.url).order_by(Instance.url)).all()
        )

    def list_trusted(self) -> list[Instance]:
        return list(
            self.db.exec(
                select(Instance)
                .where(
                    Instance.trust_status == InstanceTrustStatus.TRUST.value
                )
                .order_by(Instance.url)
            ).all()
        )

    def list_pending(self) -> list[Instance]:
        return list(
            self.db.exec(
                select(Instance)
                .where(
                    Instance.trust_status == InstanceTrustStatus.PENDING.value
                )
                .order_by(Instance.url)
            ).all()
        )

    def list(
        self,
        filters: InstanceFilter,
    ) -> tuple[int, list[Instance]]:
        count = self.db.exec(select(func.count()).select_from(Instance)).one()
        instances = self.db.exec(
            select(Instance)
            .order_by(
                col(Instance.last_success_datetime).desc().nullslast(),
                Instance.url,
            )
            .offset(filters.offset)
            .limit(filters.limit)
        ).all()
        return count, list(instances)
