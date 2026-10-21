from fastapi import Depends
from sqlmodel import Session, col

from app.configs.db import get_session
from app.configs.error_codes import ErrorCode
from app.configs.errors import PeerError
from app.domain.peer_model import Peer
from app.repositories.base_repository import BaseRepository
from app.repositories.utils import apply_enums, apply_offset_and_limit
from app.schemas.pydantic.peer import PeerFilter


class PeerRepository(BaseRepository[Peer]):
    def __init__(self, db: Session = Depends(get_session)) -> None:
        super().__init__(Peer, db)

    def list(self, filters: PeerFilter) -> tuple[int, list[Peer]]:
        query = self.db.query(Peer)

        fields = {"trust_status": Peer.trust_status}
        query = apply_enums(query, filters, fields)

        query = query.order_by(
            col(Peer.last_success_datetime).desc().nullslast(),
            col(Peer.url).asc(),
        )

        count, query = apply_offset_and_limit(query, filters)
        return count, query.all()

    def is_unique_url(self, url: str) -> None:
        peer = self.db.query(Peer).filter(Peer.url == url).first()

        if peer:
            msg = f'Url "{url}" is exist'
            raise PeerError(msg, code=ErrorCode.PEER_URL_EXISTS)
