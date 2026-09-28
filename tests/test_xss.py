"""Пользовательский HTML возвращается экранированным, а в БД лежит как есть."""

import pytest
from flask import Flask
from flask.testing import FlaskClient

from app.extensions import db
from app.models import Post
from tests.conftest import AuthUser

XSS_PAYLOADS = [
    ("<script>alert(1)</script>", "&lt;script&gt;alert(1)&lt;/script&gt;"),
    ('"><img src=x onerror=alert(1)>', "&#34;&gt;&lt;img src=x onerror=alert(1)&gt;"),
]


@pytest.mark.parametrize(("payload", "escaped"), XSS_PAYLOADS)
def test_create_post_escapes_html(
    client: FlaskClient, alice: AuthUser, payload: str, escaped: str
) -> None:
    response = client.post(
        "/api/posts", json={"title": payload, "body": payload}, headers=alice.headers
    )

    assert response.status_code == 201
    post = response.get_json()["data"]
    assert post["title"] == escaped
    assert post["body"] == escaped
    raw = response.get_data(as_text=True)
    assert "<script" not in raw
    assert "<img" not in raw


@pytest.mark.parametrize(("payload", "escaped"), XSS_PAYLOADS)
def test_data_escapes_html(
    client: FlaskClient, alice: AuthUser, payload: str, escaped: str
) -> None:
    client.post("/api/posts", json={"title": payload, "body": payload}, headers=alice.headers)

    response = client.get("/api/data", headers=alice.headers)

    post = response.get_json()["data"][0]
    assert post["title"] == escaped
    assert post["body"] == escaped
    raw = response.get_data(as_text=True)
    assert "<script" not in raw
    assert "<img" not in raw


def test_database_keeps_original_text(app: Flask, client: FlaskClient, alice: AuthUser) -> None:
    payload = XSS_PAYLOADS[0][0]
    client.post("/api/posts", json={"title": payload, "body": payload}, headers=alice.headers)

    with app.app_context():
        stored = db.session.execute(db.select(Post)).scalar_one()
        assert stored.title == payload
        assert stored.body == payload
