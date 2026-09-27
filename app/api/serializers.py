"""Преобразование моделей в JSON-ответы."""

from datetime import UTC, datetime
from typing import Any

from app.models import Post


def post_to_dict(post: Post) -> dict[str, Any]:
    return {
        "id": post.id,
        "title": post.title,
        "body": post.body,
        "author": post.author.username,
        "created_at": _iso_utc(post.created_at),
    }


def _iso_utc(moment: datetime) -> str:
    # SQLite не хранит часовой пояс, а время в БД всегда пишется в UTC
    aware = moment if moment.tzinfo else moment.replace(tzinfo=UTC)
    return aware.isoformat()
