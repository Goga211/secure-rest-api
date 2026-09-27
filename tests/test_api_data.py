from flask import Flask
from flask.testing import FlaskClient

from app.api.routes import MAX_POSTS
from app.extensions import db
from app.models import Post
from tests.conftest import AuthUser


def _add_posts(app: Flask, author_id: int, count: int) -> None:
    with app.app_context():
        db.session.add_all(
            Post(title=f"Post {n}", body=f"Body {n}", author_id=author_id) for n in range(count)
        )
        db.session.commit()


def test_data_requires_token(client: FlaskClient) -> None:
    response = client.get("/api/data")

    assert response.status_code == 401


def test_data_returns_empty_list_without_posts(client: FlaskClient, alice: AuthUser) -> None:
    response = client.get("/api/data", headers=alice.headers)

    assert response.status_code == 200
    assert response.get_json() == {"success": True, "data": [], "error": None}


def test_data_returns_posts_newest_first(app: Flask, client: FlaskClient, alice: AuthUser) -> None:
    _add_posts(app, alice.id, 3)

    response = client.get("/api/data", headers=alice.headers)

    posts = response.get_json()["data"]
    assert [p["title"] for p in posts] == ["Post 2", "Post 1", "Post 0"]
    assert set(posts[0]) == {"id", "title", "body", "author", "created_at"}
    assert posts[0]["author"] == "alice"
    assert posts[0]["created_at"].endswith("+00:00")


def test_data_is_limited(app: Flask, client: FlaskClient, alice: AuthUser) -> None:
    _add_posts(app, alice.id, MAX_POSTS + 5)

    response = client.get("/api/data", headers=alice.headers)

    assert len(response.get_json()["data"]) == MAX_POSTS
