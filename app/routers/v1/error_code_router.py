from fastapi import APIRouter

from app.configs.error_codes import ErrorCode

router = APIRouter()
router.add_api_route(
    "",
    ErrorCode.catalog,
    methods=["GET"],
    response_model=dict[str, int],
)
