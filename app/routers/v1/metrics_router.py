from fastapi import APIRouter, Depends

from app.schemas.pydantic.metrics import BaseMetricsRead
from app.services.metrics_service import MetricsService

router = APIRouter()


@router.get("/", response_model=BaseMetricsRead)
def get_base_metrics(metrics_mervice: MetricsService = Depends()):
    return metrics_mervice.get_instance_metrics()
