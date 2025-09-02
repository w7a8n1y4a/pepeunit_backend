from fastapi import Depends
from sqlmodel import Session

from app.configs.db import get_session
from app.domain.panels_unit_nodes_model import PanelsUnitNodes
from app.repositories.base_repository import BaseRepository


class PanelsUnitNodesRepository(BaseRepository):
    def __init__(self, db: Session = Depends(get_session)) -> None:
        super().__init__(PanelsUnitNodes, db)
