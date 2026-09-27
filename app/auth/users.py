"""Создание и поиск пользователей."""

import re

from sqlalchemy.exc import IntegrityError

from app.auth.passwords import PasswordTooLongError, hash_password
from app.extensions import db
from app.models import User

USERNAME_PATTERN = re.compile(r"[a-z0-9_.-]{3,64}")
MIN_PASSWORD_LENGTH = 12


class UserError(ValueError):
    """Нельзя создать пользователя с такими данными."""


def normalize_username(raw: str) -> str:
    """Логины регистронезависимы: Alice и alice это один пользователь."""
    return raw.strip().lower()


def create_user(username: str, password: str) -> User:
    normalized = normalize_username(username)
    if not USERNAME_PATTERN.fullmatch(normalized):
        raise UserError("Логин: 3-64 символа, латиница, цифры, точка, дефис, подчёркивание")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise UserError(f"Пароль должен быть не короче {MIN_PASSWORD_LENGTH} символов")
    try:
        password_hash = hash_password(password)
    except PasswordTooLongError as exc:
        raise UserError(str(exc)) from exc

    user = User(username=normalized, password_hash=password_hash)
    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise UserError(f"Пользователь {normalized} уже существует") from exc
    return user


def find_user(username: str) -> User | None:
    statement = db.select(User).filter_by(username=normalize_username(username))
    return db.session.execute(statement).scalar_one_or_none()
