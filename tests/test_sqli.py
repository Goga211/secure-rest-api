"""Попытки SQL-инъекций через логин и создание поста.

ORM SQLAlchemy не склеивает SQL из строк: значения из запроса уходят в драйвер
как связанные параметры, отдельно от текста запроса. Поэтому кавычки и SQL-код
во входных данных остаются обычным текстом и не меняют структуру запроса.
"""

import pytest
from flask import Flask
from flask.testing import FlaskClient
from markupsafe import escape

from app.extensions import db
from app.models import Post, User
from tests.conftest import TEST_PASSWORD, AuthUser

USERNAME_INJECTIONS = [
    "' OR '1'='1' --",
    "admin'--",
    "alice'--",
    "' UNION SELECT id, username, password_hash FROM users --",
]
PASSWORD_INJECTIONS = [
    "' OR '1'='1' --",
    "' OR 1=1 --",
]
DROP_TABLE_TITLE = "'); DROP TABLE posts; --"


@pytest.mark.parametrize("username", USERNAME_INJECTIONS)
def test_login_username_injection_rejected(
    client: FlaskClient, alice: AuthUser, username: str
) -> None:
    response = client.post("/auth/login", json={"username": username, "password": TEST_PASSWORD})

    assert response.status_code == 401
    assert response.get_json()["success"] is False


@pytest.mark.parametrize("password", PASSWORD_INJECTIONS)
def test_login_password_injection_rejected(
    client: FlaskClient, alice: AuthUser, password: str
) -> None:
    response = client.post("/auth/login", json={"username": alice.username, "password": password})

    assert response.status_code == 401
    assert response.get_json()["success"] is False


def test_post_title_injection_stored_as_text(
    app: Flask, client: FlaskClient, alice: AuthUser
) -> None:
    response = client.post(
        "/api/posts",
        json={"title": DROP_TABLE_TITLE, "body": "текст"},
        headers=alice.headers,
    )
    assert response.status_code == 201

    data = client.get("/api/data", headers=alice.headers)
    assert data.status_code == 200
    posts = data.get_json()["data"]
    assert [post["title"] for post in posts] == [str(escape(DROP_TABLE_TITLE))]

    with app.app_context():
        stored = db.session.execute(db.select(Post)).scalar_one()
        assert stored.title == DROP_TABLE_TITLE
        assert db.session.execute(db.select(User)).scalar_one().username == alice.username
