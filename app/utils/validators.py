from fastapi import HTTPException
from fastapi import status as http_status


def is_valid_object(obj: any):
    if not obj:
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=f"No valid request")
