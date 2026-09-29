"""Ограничение частоты запросов к /auth/login."""

import pytest
from flask import Flask
from flask.testing import FlaskClient

from app import create_app
from app.auth.routes import LOGIN_RATE_LIMIT
from app.config import Settings
from app.extensions import db, limiter

LOGIN_ATTEMPTS_ALLOWED = 5
WRONG_CREDENTIALS = {"username": "mallory", "password": "guess"}


@pytest.fixture
def limited_client(settings: Settings) -> FlaskClient:
    """Клиент приложения с включённым лимитом и чистым счётчиком."""
    enabled = Settings(
        database_url=settings.database_url,
        jwt_secret=settings.jwt_secret,
        rate_limit_enabled=True,
    )
    app: Flask = create_app(enabled)
    with app.app_context():
        db.create_all()
    limiter.reset()
    return app.test_client()


def test_login_limit_is_five_per_minute() -> None:
    assert LOGIN_RATE_LIMIT == "5 per minute"


def test_sixth_login_attempt_gets_429(limited_client: FlaskClient) -> None:
    for _ in range(LOGIN_ATTEMPTS_ALLOWED):
        response = limited_client.post("/auth/login", json=WRONG_CREDENTIALS)
        assert response.status_code == 401

    response = limited_client.post("/auth/login", json=WRONG_CREDENTIALS)

    assert response.status_code == 429
    body = response.get_json()
    assert body["success"] is False
    assert body["data"] is None
    assert "Слишком много" in body["error"]


def test_limit_does_not_apply_to_other_endpoints(limited_client: FlaskClient) -> None:
    for _ in range(LOGIN_ATTEMPTS_ALLOWED + 1):
        limited_client.post("/auth/login", json=WRONG_CREDENTIALS)

    assert limited_client.get("/health").status_code == 200


def test_limit_disabled_in_default_test_settings(client: FlaskClient) -> None:
    for _ in range(LOGIN_ATTEMPTS_ALLOWED + 1):
        response = client.post("/auth/login", json=WRONG_CREDENTIALS)

    assert response.status_code == 401
