"""Единый JSON-конверт для ошибок: 400, 404, 405, 413, 429, 500."""

import logging

import pytest
from flask import Flask, abort
from flask.testing import FlaskClient

from app import MAX_CONTENT_LENGTH
from tests.conftest import AuthUser

INTERNAL_DETAIL = "секретная-деталь-исключения"


def assert_error_envelope(body: dict, text: str) -> None:
    assert body == {"success": False, "data": None, "error": body["error"]}
    assert text in body["error"]


def test_unknown_path_returns_404_envelope(client: FlaskClient) -> None:
    response = client.get("/no-such-path")

    assert response.status_code == 404
    assert response.is_json
    assert_error_envelope(response.get_json(), "не найден")


def test_wrong_method_returns_405_envelope(client: FlaskClient) -> None:
    response = client.get("/auth/login")

    assert response.status_code == 405
    assert response.is_json
    assert_error_envelope(response.get_json(), "не поддерживается")
    assert "POST" in response.headers["Allow"]


def test_too_large_body_returns_413_envelope(client: FlaskClient, alice: AuthUser) -> None:
    payload = {"title": "заголовок", "body": "b" * (MAX_CONTENT_LENGTH + 1)}

    response = client.post("/api/posts", json=payload, headers=alice.headers)

    assert response.status_code == 413
    assert response.is_json
    assert_error_envelope(response.get_json(), "слишком большое")


def test_malformed_request_returns_400_envelope(app: Flask) -> None:
    @app.post("/test-bad-request")
    def bad_request() -> None:
        abort(400)

    response = app.test_client().post("/test-bad-request")

    assert response.status_code == 400
    assert response.is_json
    assert_error_envelope(response.get_json(), "Некорректный запрос")


@pytest.fixture
def failing_client(app: Flask) -> FlaskClient:
    """Клиент с маршрутом, который падает с необработанным исключением."""
    app.config["PROPAGATE_EXCEPTIONS"] = False

    @app.get("/test-crash")
    def crash() -> None:
        raise RuntimeError(INTERNAL_DETAIL)

    return app.test_client()


def test_unhandled_exception_returns_500_without_details(
    failing_client: FlaskClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.ERROR):
        response = failing_client.get("/test-crash")

    assert response.status_code == 500
    assert response.is_json
    assert_error_envelope(response.get_json(), "Внутренняя ошибка")
    text = response.get_data(as_text=True)
    assert INTERNAL_DETAIL not in text
    assert "Traceback" not in text
    # Детали остаются только в логе сервера
    assert INTERNAL_DETAIL in caplog.text


def test_error_responses_keep_security_headers(client: FlaskClient) -> None:
    response = client.get("/no-such-path")

    assert response.headers["X-Content-Type-Options"] == "nosniff"


def test_explicit_abort_500_returns_envelope(app: Flask) -> None:
    @app.get("/test-abort-500")
    def abort_500() -> None:
        abort(500)

    response = app.test_client().get("/test-abort-500")

    assert response.status_code == 500
    assert_error_envelope(response.get_json(), "Внутренняя ошибка")


def test_other_http_errors_keep_their_status(app: Flask) -> None:
    @app.get("/test-forbidden")
    def forbidden() -> None:
        abort(403)

    response = app.test_client().get("/test-forbidden")

    assert response.status_code == 403
