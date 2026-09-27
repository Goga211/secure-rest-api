import secrets

import pytest
from flask import Flask
from flask.testing import FlaskClient

from app import create_app
from app.config import Settings
from app.extensions import db


@pytest.fixture
def settings() -> Settings:
    return Settings(
        database_url="sqlite:///:memory:",
        jwt_secret=secrets.token_urlsafe(48),
    )


@pytest.fixture
def app(settings: Settings) -> Flask:
    app = create_app(settings)
    with app.app_context():
        db.create_all()
    return app


@pytest.fixture
def client(app: Flask) -> FlaskClient:
    return app.test_client()
