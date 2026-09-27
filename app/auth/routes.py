"""Эндпоинты аутентификации."""

from flask import Blueprint, Response, current_app, request
from pydantic import ValidationError

from app.auth.passwords import dummy_hash, verify_password
from app.auth.schemas import LoginRequest
from app.auth.tokens import issue_token
from app.auth.users import find_user
from app.responses import error, success

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

# Один ответ и для неверного логина, и для неверного пароля: так нельзя узнать,
# какие логины существуют
INVALID_CREDENTIALS = "Неверный логин или пароль"


@auth_bp.post("/login")
def login() -> Response:
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return error("Ожидается JSON-объект с полями username и password", 400)
    try:
        credentials = LoginRequest.model_validate(payload)
    except ValidationError:
        return error("Поля username и password обязательны и должны быть строками", 400)

    user = find_user(credentials.username)
    # Пароль проверяется и для несуществующего логина, чтобы время ответа не отличалось
    password_hash = user.password_hash if user else dummy_hash()
    password_ok = verify_password(credentials.password, password_hash)
    if user is None or not password_ok:
        return error(INVALID_CREDENTIALS, 401)

    issued = issue_token(
        user.id, current_app.config["JWT_SECRET"], current_app.config["JWT_TTL_MINUTES"]
    )
    return success(
        {"access_token": issued.token, "token_type": "Bearer", "expires_in": issued.expires_in}
    )
