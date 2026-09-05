from fastapi import Depends
from sqlmodel import Session, col

from app.configs.db import get_session
from app.configs.errors import InstanceError
from app.domain.instance_model import Instance
from app.repositories.base_repository import BaseRepository
from app.repositories.utils import apply_enums, apply_offset_and_limit
from app.schemas.gql.inputs.instance import InstanceFilterInput
from app.schemas.pydantic.instance import InstanceFilter


class InstanceRepository(BaseRepository[Instance]):
    def __init__(self, db: Session = Depends(get_session)) -> None:
        super().__init__(Instance, db)

    def list(
        self, filters: InstanceFilter | InstanceFilterInput
    ) -> tuple[int, list[Instance]]:
        query = self.db.query(Instance)

        fields = {"trust_status": Instance.trust_status}
        query = apply_enums(query, filters, fields)

        query = query.order_by(
            col(Instance.last_success_datetime).desc().nullslast(),
            col(Instance.url).asc(),
        )

        count, query = apply_offset_and_limit(query, filters)
        return count, query.all()

    def is_unique_url(self, url: str) -> None:
        instance = self.db.query(Instance).filter(Instance.url == url).first()

        if instance:
            msg = f'Url "{url}" is exist'
            raise InstanceError(msg)
