"""Схемы входных данных API."""

from pydantic import BaseModel, ConfigDict, Field

from app.models import POST_BODY_MAX_LENGTH, POST_TITLE_MAX_LENGTH


class CreatePostRequest(BaseModel):
    # strict: без неявных приведений типов; forbid: автора и прочие поля задать нельзя
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    title: str = Field(min_length=1, max_length=POST_TITLE_MAX_LENGTH)
    body: str = Field(min_length=1, max_length=POST_BODY_MAX_LENGTH)
