from typing import Any

import pytest
from flask import Flask
from flask.testing import FlaskClient

from app.auth.tokens import decode_token
from app.auth.users import create_user

PASSWORD = "correct-horse-battery"


@pytest.fixture
def alice_id(app: Flask) -> int:
    with app.app_context():
        return create_user("alice", PASSWORD).id


def test_login_returns_jwt_for_valid_credentials(
    app: Flask, client: FlaskClient, alice_id: int
) -> None:
    response = client.post("/auth/login", json={"username": "alice", "password": PASSWORD})

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["token_type"] == "Bearer"
    assert data["expires_in"] == app.config["JWT_TTL_MINUTES"] * 60
    assert decode_token(data["access_token"], app.config["JWT_SECRET"]) == alice_id


@pytest.mark.usefixtures("alice_id")
def test_login_username_is_case_insensitive(client: FlaskClient) -> None:
    response = client.post("/auth/login", json={"username": "ALICE", "password": PASSWORD})

    assert response.status_code == 200


@pytest.mark.usefixtures("alice_id")
def test_wrong_password_and_unknown_user_get_same_401(client: FlaskClient) -> None:
    wrong_password = client.post("/auth/login", json={"username": "alice", "password": "nope"})
    unknown_user = client.post("/auth/login", json={"username": "bob", "password": PASSWORD})

    assert wrong_password.status_code == unknown_user.status_code == 401
    assert wrong_password.get_json() == unknown_user.get_json()
    assert wrong_password.get_json()["success"] is False
    assert wrong_password.get_json()["data"] is None


@pytest.mark.usefixtures("alice_id")
def test_login_response_does_not_leak_password_hash(client: FlaskClient) -> None:
    response = client.post("/auth/login", json={"username": "alice", "password": PASSWORD})

    assert "$2b$" not in response.get_data(as_text=True)


def test_login_rejects_non_json_body(client: FlaskClient) -> None:
    response = client.post("/auth/login", data="username=alice", content_type="text/plain")

    assert response.status_code == 400


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {},
        {"username": "alice"},
        {"username": 1, "password": PASSWORD},
        {"username": "alice", "password": PASSWORD, "role": "admin"},
        {"username": "a" * 65, "password": PASSWORD},
        {"username": "alice", "password": "p" * 129},
    ],
)
def test_login_rejects_invalid_payload(client: FlaskClient, payload: Any) -> None:
    response = client.post("/auth/login", json=payload)

    assert response.status_code == 400
    assert response.get_json()["success"] is False
