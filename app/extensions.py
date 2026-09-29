"""Расширения Flask. Создаются здесь, привязываются к приложению в create_app."""

from flask import Response
from flask_limiter import Limiter, RequestLimit
from flask_limiter.util import get_remote_address
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase

from app.responses import error

TOO_MANY_REQUESTS = 429


class Base(DeclarativeBase):
    pass


db = SQLAlchemy(model_class=Base)


def _rate_limit_exceeded(_limit: RequestLimit) -> Response:
    """Ответ при превышении лимита в общем JSON-конверте."""
    return error("Слишком много запросов, попробуйте позже", TOO_MANY_REQUESTS)


# Счётчики в памяти процесса, ключ по IP клиента. Лимиты задаются на маршрутах
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri="memory://",
    on_breach=_rate_limit_exceeded,
)
