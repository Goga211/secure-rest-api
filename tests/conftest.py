import secrets
from dataclasses import dataclass

import pytest
from flask import Flask
from flask.testing import FlaskClient

from app import create_app
from app.auth.tokens import issue_token
from app.auth.users import create_user
from app.config import Settings
from app.extensions import db

TEST_PASSWORD = "correct-horse-battery"


@dataclass(frozen=True)
class AuthUser:
    id: int
    username: str
    headers: dict[str, str]


@pytest.fixture
def settings() -> Settings:
    return Settings(
        database_url="sqlite:///:memory:",
        jwt_secret=secrets.token_urlsafe(48),
        # Лимит проверяется отдельно в test_rate_limit.py
        rate_limit_enabled=False,
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


@pytest.fixture
def alice(app: Flask) -> AuthUser:
    """Зарегистрированный пользователь с готовым заголовком Authorization."""
    with app.app_context():
        user = create_user("alice", TEST_PASSWORD)
        issued = issue_token(user.id, app.config["JWT_SECRET"], app.config["JWT_TTL_MINUTES"])
        return AuthUser(
            id=user.id,
            username=user.username,
            headers={"Authorization": f"Bearer {issued.token}"},
        )
