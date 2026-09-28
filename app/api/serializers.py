"""Преобразование моделей в JSON-ответы."""

from datetime import UTC, datetime
from typing import Any

from markupsafe import escape

from app.models import Post


def post_to_dict(post: Post) -> dict[str, Any]:
    # Экранируем на выходе, а не на входе: в БД лежит исходный текст,
    # поэтому его можно безопасно отдать в любом другом формате.
    # HTML из пользовательского ввода не выполнится, если ответ вставят в страницу.
    return {
        "id": post.id,
        "title": _escape_html(post.title),
        "body": _escape_html(post.body),
        "author": _escape_html(post.author.username),
        "created_at": _iso_utc(post.created_at),
    }


def _escape_html(text: str) -> str:
    return str(escape(text))


def _iso_utc(moment: datetime) -> str:
    # SQLite не хранит часовой пояс, а время в БД всегда пишется в UTC
    aware = moment if moment.tzinfo else moment.replace(tzinfo=UTC)
    return aware.isoformat()
