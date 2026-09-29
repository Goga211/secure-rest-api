"""Расширения Flask. Создаются здесь, привязываются к приложению в create_app."""

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


db = SQLAlchemy(model_class=Base)


# Счётчики в памяти процесса, ключ по IP клиента. Лимиты задаются на маршрутах.
# Ответ 429 формирует общий обработчик ошибок в app/errors.py
limiter = Limiter(key_func=get_remote_address, storage_uri="memory://")
