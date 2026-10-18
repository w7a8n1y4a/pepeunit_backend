import uuid as uuid_pkg

from fastapi import APIRouter, Depends, Form, Response, status

from app.configs.rest import get_icon_service
from app.schemas.pydantic.icon import IconRead, IconUpload
from app.services.icon_image import IconImage
from app.services.icon_service import IconService

router = APIRouter()


@router.get("/{uuid}")
def get_icon(
    uuid: uuid_pkg.UUID,
    icon_service: IconService = Depends(get_icon_service),
):
    icon = icon_service.get(uuid)
    return Response(
        content=bytes(icon.image_bin),
        media_type="image/png",
        headers={
            "ETag": f'"{icon.image_hash}"',
            "Cache-Control": "public, max-age=31536000, immutable",
        },
    )


@router.post("", response_model=IconRead, status_code=status.HTTP_201_CREATED)
def upload_icon(
    data: IconUpload = Form(media_type="multipart/form-data"),
    icon_service: IconService = Depends(get_icon_service),
):
    image = data.file.file.read(IconImage.MAX_BYTES + 1)
    icon = icon_service.upload(data.entity_uuid, data.entity_type, image)
    return IconRead(**icon.dict())
