"""Обработчики ошибок: любой сбой отдаётся в общем JSON-конверте по-русски."""

from flask import Flask, Response, current_app
from werkzeug.exceptions import HTTPException

from app.responses import error

INTERNAL_SERVER_ERROR = 500
INTERNAL_ERROR_MESSAGE = "Внутренняя ошибка сервера"

# Сообщения для HTTP-ошибок, которые может вернуть API
HTTP_ERROR_MESSAGES: dict[int, str] = {
    400: "Некорректный запрос",
    404: "Ресурс не найден",
    405: "Метод не поддерживается для этого ресурса",
    413: "Тело запроса слишком большое",
    429: "Слишком много запросов, попробуйте позже",
}

# Заголовки исключения, которые нужно сохранить (например, Allow для 405)
PASSTHROUGH_HEADERS = frozenset({"allow", "retry-after"})


def handle_http_error(exc: HTTPException) -> Response:
    status = exc.code or INTERNAL_SERVER_ERROR
    headers = {
        name: value for name, value in exc.get_headers() if name.lower() in PASSTHROUGH_HEADERS
    }
    return error(HTTP_ERROR_MESSAGES[status], status, headers)


def handle_internal_error(_exc: HTTPException) -> Response:
    return error(INTERNAL_ERROR_MESSAGE, INTERNAL_SERVER_ERROR)


def handle_unexpected_error(exc: Exception) -> Response | HTTPException:
    """Необработанное исключение: подробности только в лог, клиенту общий текст."""
    if isinstance(exc, HTTPException):
        # Коды без своего обработчика (например, 403 из abort) Flask отдаст сам
        return exc
    current_app.logger.exception("Необработанное исключение")
    return error(INTERNAL_ERROR_MESSAGE, INTERNAL_SERVER_ERROR)


def register_error_handlers(app: Flask) -> None:
    for status in HTTP_ERROR_MESSAGES:
        app.register_error_handler(status, handle_http_error)
    app.register_error_handler(INTERNAL_SERVER_ERROR, handle_internal_error)
    app.register_error_handler(Exception, handle_unexpected_error)
