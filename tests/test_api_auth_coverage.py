"""Каждый маршрут /api/* закрыт JWT.

Защита ставится декоратором jwt_required на каждый эндпоинт отдельно. Тест проходит по всем
зарегистрированным маршрутам /api/*, поэтому новый эндпоинт без декоратора уронит CI, а не
станет публичным незаметно.
"""

import re

from flask import Flask, Response
from flask.testing import FlaskClient

from app.responses import success

API_PREFIX = "/api/"
SKIPPED_METHODS = frozenset({"HEAD", "OPTIONS"})
# Переменные части пути (<int:post_id>) заменяются любым допустимым значением
PATH_VARIABLE = re.compile(r"<[^>]+>")
PATH_VARIABLE_VALUE = "1"
UNPROTECTED_URL = "/api/_test/forgot-decorator"


def _api_endpoints(app: Flask) -> list[tuple[str, str]]:
    return sorted(
        (PATH_VARIABLE.sub(PATH_VARIABLE_VALUE, rule.rule), method)
        for rule in app.url_map.iter_rules()
        if rule.rule.startswith(API_PREFIX)
        for method in (rule.methods or set()) - SKIPPED_METHODS
    )


def _unprotected_endpoints(app: Flask, client: FlaskClient) -> list[str]:
    """Маршруты /api/*, которые без токена отвечают не 401."""
    return [
        f"{method} {path}"
        for path, method in _api_endpoints(app)
        if client.open(path, method=method).status_code != 401
    ]


def test_every_api_endpoint_requires_token(app: Flask, client: FlaskClient) -> None:
    assert _api_endpoints(app), "в приложении нет маршрутов /api/*, проверять нечего"
    assert _unprotected_endpoints(app, client) == []


def test_endpoint_without_decorator_is_detected(app: Flask, client: FlaskClient) -> None:
    def forgot_decorator() -> Response:
        return success({"secret": "data"})

    app.add_url_rule(UNPROTECTED_URL, view_func=forgot_decorator)

    assert _unprotected_endpoints(app, client) == [f"GET {UNPROTECTED_URL}"]
