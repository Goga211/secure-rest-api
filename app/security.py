"""Security-заголовки, которые добавляются к каждому ответу."""

from flask import Flask, Response

# API отдаёт только JSON: запрещаем любые ресурсы, фреймы, кэш и утечку Referer
SECURITY_HEADERS: dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
}


def add_security_headers(response: Response) -> Response:
    response.headers.update(SECURITY_HEADERS)
    return response


def register_security_headers(app: Flask) -> None:
    """Подключает заголовки ко всем ответам приложения, включая ошибки."""
    app.after_request(add_security_headers)
