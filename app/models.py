"""Модели данных. Работа с БД идёт только через ORM, SQL из строк не собирается."""

from datetime import UTC, datetime

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

USERNAME_MAX_LENGTH = 64
PASSWORD_HASH_MAX_LENGTH = 128
POST_TITLE_MAX_LENGTH = 120


def _utcnow() -> datetime:
    return datetime.now(UTC)


class User(db.Model):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(USERNAME_MAX_LENGTH), unique=True)
    # Только хэш: открытый пароль в БД не хранится
    password_hash: Mapped[str] = mapped_column(String(PASSWORD_HASH_MAX_LENGTH))
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)

    posts: Mapped[list["Post"]] = relationship(back_populates="author")


class Post(db.Model):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(POST_TITLE_MAX_LENGTH))
    body: Mapped[str] = mapped_column(Text)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)

    author: Mapped[User] = relationship(back_populates="posts")
