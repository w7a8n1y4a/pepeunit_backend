import time
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from starlette.responses import JSONResponse

from app import settings
from app.configs.errors import NoAccessError
from app.configs.rest import get_user_service
from app.services.user_service import UserService

router = APIRouter()
auth_codes = {}
access_tokens = {}

"""
[server]
root_url = http://localhost:3000/pepeunit/grafana/
serve_from_sub_path = true

[auth]
disable_login_form = true

[auth.generic_oauth]
enabled = true
name = Pepeunit
allow_sign_up = true
client_id = grafana-client
client_secret = dummy
scopes = openid profile email
auth_url = http://192.168.0.22:8555/pepeunit/api/v1/grafana/oidc/authorize
token_url = http://192.168.0.22:8555/pepeunit/api/v1/grafana/oidc/token
api_url = http://192.168.0.22:8555/pepeunit/api/v1/grafana/oidc/userinfo
email_attribute_path = email
login_attribute_path = name
role_attribute_path = role
role_attribute_strict = true


"""


@router.get("/oidc/authorize")
def authorize(
    response_type: str, client_id: str, redirect_uri: str, scope: str, state: str, nonce: Optional[str] = None
):
    """
    Простая авторизация: возвращает редирект с "кодом" обратно в Grafana.
    """
    code = str(uuid.uuid4())
    auth_codes[code] = {
        "client_id": client_id,
        "scope": scope,
        "nonce": nonce,
        "issued_at": time.time(),
        "user": {"sub": "1234", "name": "Grafana User", "email": "grafana@example.com", "role": "Viewer"},
    }

    redirect_url = f"{redirect_uri}?code={code}&state={state}"
    return RedirectResponse(url=redirect_url)


@router.post("/oidc/token")
def token(
    grant_type: str = Form(...),
    code: str = Form(...),
    redirect_uri: str = Form(...),
    client_id: str = Form(...),
    client_secret: str = Form(...),
):

    if code not in auth_codes:
        return JSONResponse(status_code=400, content={"error": "invalid_grant"})

    # Выдать "токен"
    access_token = str(uuid.uuid4())
    id_token = str(uuid.uuid4())
    access_tokens[access_token] = auth_codes.pop(code)

    return {
        "access_token": access_token,
        "token_type": "Bearer",
        "expires_in": 3600,
        "id_token": id_token,
    }


@router.get("/oidc/userinfo")
def userinfo(request: Request):
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        return JSONResponse(status_code=401, content={"error": "invalid_token"})

    token = auth.split(" ")[1]
    if token not in access_tokens:
        return JSONResponse(status_code=401, content={"error": "invalid_token"})

    user = access_tokens[token]["user"]
    return {"sub": user["sub"], "name": user["name"], "email": user["email"], "role": user["role"]}
