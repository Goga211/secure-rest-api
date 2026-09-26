import secrets

import pytest
from flask import Flask
from flask.testing import FlaskClient

from app import create_app
from app.config import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings(
        database_url="sqlite:///:memory:",
        jwt_secret=secrets.token_urlsafe(48),
    )


@pytest.fixture
def app(settings: Settings) -> Flask:
    return create_app(settings)


@pytest.fixture
def client(app: Flask) -> FlaskClient:
    return app.test_client()
