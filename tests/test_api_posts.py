from typing import Any

import pytest
from flask.testing import FlaskClient

from app import MAX_CONTENT_LENGTH
from app.models import POST_BODY_MAX_LENGTH, POST_TITLE_MAX_LENGTH
from tests.conftest import AuthUser

VALID_POST = {"title": "Привет", "body": "Первый пост"}


def test_create_post_requires_token(client: FlaskClient) -> None:
    response = client.post("/api/posts", json=VALID_POST)

    assert response.status_code == 401


def test_create_post_returns_201_and_post(client: FlaskClient, alice: AuthUser) -> None:
    response = client.post("/api/posts", json=VALID_POST, headers=alice.headers)

    assert response.status_code == 201
    body = response.get_json()
    assert body["success"] is True
    assert body["error"] is None
    post = body["data"]
    assert post["title"] == VALID_POST["title"]
    assert post["body"] == VALID_POST["body"]
    assert post["author"] == alice.username
    assert set(post) == {"id", "title", "body", "author", "created_at"}


def test_created_post_appears_in_data(client: FlaskClient, alice: AuthUser) -> None:
    created = client.post("/api/posts", json=VALID_POST, headers=alice.headers).get_json()

    posts = client.get("/api/data", headers=alice.headers).get_json()["data"]

    assert posts == [created["data"]]


def test_create_post_accepts_max_lengths(client: FlaskClient, alice: AuthUser) -> None:
    payload = {"title": "t" * POST_TITLE_MAX_LENGTH, "body": "b" * POST_BODY_MAX_LENGTH}

    response = client.post("/api/posts", json=payload, headers=alice.headers)

    assert response.status_code == 201


@pytest.mark.parametrize(
    "payload",
    [
        ["title", "body"],
        "строка",
        None,
        {},
        {"title": "Только заголовок"},
        {"body": "Только текст"},
        {"title": 1, "body": "текст"},
        {"title": "заголовок", "body": ["текст"]},
        {**VALID_POST, "author_id": 1},
        {"title": "", "body": "текст"},
        {"title": "заголовок", "body": ""},
        {"title": "t" * (POST_TITLE_MAX_LENGTH + 1), "body": "текст"},
        {"title": "заголовок", "body": "b" * (POST_BODY_MAX_LENGTH + 1)},
    ],
)
def test_create_post_rejects_invalid_payload(
    client: FlaskClient, alice: AuthUser, payload: Any
) -> None:
    response = client.post("/api/posts", json=payload, headers=alice.headers)

    assert response.status_code == 400
    body = response.get_json()
    assert body["success"] is False
    assert body["data"] is None
    assert body["error"]


def test_create_post_rejects_non_json_body(client: FlaskClient, alice: AuthUser) -> None:
    response = client.post(
        "/api/posts", data="title=x&body=y", content_type="text/plain", headers=alice.headers
    )

    assert response.status_code == 400
    assert response.get_json()["success"] is False


def test_create_post_rejects_too_large_body(client: FlaskClient, alice: AuthUser) -> None:
    payload = {"title": "заголовок", "body": "b" * (MAX_CONTENT_LENGTH + 1)}

    response = client.post("/api/posts", json=payload, headers=alice.headers)

    assert response.status_code == 413
