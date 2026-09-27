"""Схемы входных данных аутентификации."""

from pydantic import BaseModel, ConfigDict, Field

from app.models import USERNAME_MAX_LENGTH

PASSWORD_MAX_LENGTH = 128


class LoginRequest(BaseModel):
    # strict: без неявных приведений типов; forbid: лишние поля (например, role) запрещены
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    username: str = Field(min_length=1, max_length=USERNAME_MAX_LENGTH)
    password: str = Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)
