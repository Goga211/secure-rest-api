"""Декоратор jwt_required: пускает к эндпоинту только с валидным JWT."""

from collections.abc import Callable
from functools import wraps

from flask import current_app, g, request
from flask.typing import ResponseReturnValue

from app.auth.tokens import TokenError, decode_token
from app.extensions import db
from app.models import User
from app.responses import error

BEARER_CHALLENGE = {"WWW-Authenticate": 'Bearer realm="api"'}
MISSING_AUTH_MESSAGE = "Требуется заголовок Authorization: Bearer <token>"
INVALID_AUTH_MESSAGE = "Недействительный или просроченный токен"


def jwt_required[**P](
    view: Callable[P, ResponseReturnValue],
) -> Callable[P, ResponseReturnValue]:
    @wraps(view)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> ResponseReturnValue:
        token = _bearer_token(request.headers.get("Authorization", ""))
        if token is None:
            return error(MISSING_AUTH_MESSAGE, 401, BEARER_CHALLENGE)
        try:
            user_id = decode_token(token, current_app.config["JWT_SECRET"])
        except TokenError:
            return error(INVALID_AUTH_MESSAGE, 401, BEARER_CHALLENGE)

        # Пользователь мог быть удалён после выдачи токена
        user = db.session.get(User, user_id)
        if user is None:
            return error(INVALID_AUTH_MESSAGE, 401, BEARER_CHALLENGE)

        g.current_user = user
        return view(*args, **kwargs)

    return wrapper


def current_user() -> User:
    """Пользователь текущего запроса. Доступен только внутри @jwt_required."""
    return g.current_user


def _bearer_token(header: str) -> str | None:
    scheme, _, token = header.partition(" ")
    token = token.strip()
    if scheme.lower() != "bearer" or not token:
        return None
    return token
