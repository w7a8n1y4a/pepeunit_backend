from fastapi import Depends
from sqlmodel import Session

from app.configs.db import get_session
from app.domain.dashboard_panel_model import DashboardPanel
from app.domain.panels_unit_ios_model import PanelsUnitIOs
from app.domain.unit_io_model import UnitIO
from app.repositories.base_repository import BaseRepository


class PanelsUnitIOsRepository(BaseRepository):
    def __init__(self, db: Session = Depends(get_session)) -> None:
        super().__init__(PanelsUnitIOs, db)

    def delete(self, unit_io: UnitIO, dashboard_panel: DashboardPanel) -> None:
        (
            self.db.query(PanelsUnitIOs)
            .filter(
                PanelsUnitIOs.unit_io_uuid == unit_io.uuid,
                PanelsUnitIOs.dashboard_panels_uuid == dashboard_panel.uuid,
            )
            .delete()
        )
        self.db.commit()
        self.db.flush()

    def get_by_parent(
        self, unit_io: UnitIO, dashboard_panel: DashboardPanel
    ) -> PanelsUnitIOs:
        return (
            self.db.query(PanelsUnitIOs)
            .filter(
                PanelsUnitIOs.unit_io_uuid == unit_io.uuid,
                PanelsUnitIOs.dashboard_panels_uuid == dashboard_panel.uuid,
            )
            .first()
        )
