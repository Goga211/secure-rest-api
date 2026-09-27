import secrets
from datetime import UTC, datetime, timedelta

import pytest
from flask import Flask, Response
from flask.testing import FlaskClient

from app.auth.decorators import current_user, jwt_required
from app.auth.tokens import issue_token
from app.auth.users import create_user
from app.responses import success

PROTECTED_URL = "/_test/whoami"


@pytest.fixture
def protected_client(app: Flask) -> FlaskClient:
    @jwt_required
    def whoami() -> Response:
        return success({"username": current_user().username})

    app.add_url_rule(PROTECTED_URL, view_func=whoami)
    return app.test_client()


@pytest.fixture
def alice_id(app: Flask) -> int:
    with app.app_context():
        return create_user("alice", "correct-horse-battery").id


def _token(
    app: Flask, user_id: int, *, secret: str | None = None, now: datetime | None = None
) -> str:
    signing_secret = secret or app.config["JWT_SECRET"]
    return issue_token(user_id, signing_secret, ttl_minutes=15, now=now).token


def _get(client: FlaskClient, authorization: str | None) -> Response:
    headers = {} if authorization is None else {"Authorization": authorization}
    return client.get(PROTECTED_URL, headers=headers)


def _assert_unauthorized(response: Response) -> None:
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"].startswith("Bearer")
    assert response.get_json()["success"] is False


def test_valid_token_grants_access(
    app: Flask, protected_client: FlaskClient, alice_id: int
) -> None:
    response = _get(protected_client, f"Bearer {_token(app, alice_id)}")

    assert response.status_code == 200
    assert response.get_json()["data"] == {"username": "alice"}


def test_scheme_is_case_insensitive(
    app: Flask, protected_client: FlaskClient, alice_id: int
) -> None:
    response = _get(protected_client, f"bearer {_token(app, alice_id)}")

    assert response.status_code == 200


@pytest.mark.parametrize("authorization", [None, "", "Bearer", "Bearer   ", "Basic YWxpY2U6cHc="])
def test_missing_or_malformed_header_is_rejected(
    protected_client: FlaskClient, authorization: str | None
) -> None:
    _assert_unauthorized(_get(protected_client, authorization))


def test_garbage_token_is_rejected(protected_client: FlaskClient) -> None:
    _assert_unauthorized(_get(protected_client, "Bearer not.a.jwt"))


def test_token_signed_with_other_secret_is_rejected(
    app: Flask, protected_client: FlaskClient, alice_id: int
) -> None:
    forged = _token(app, alice_id, secret=secrets.token_urlsafe(48))

    _assert_unauthorized(_get(protected_client, f"Bearer {forged}"))


def test_expired_token_is_rejected(
    app: Flask, protected_client: FlaskClient, alice_id: int
) -> None:
    expired = _token(app, alice_id, now=datetime.now(UTC) - timedelta(hours=1))

    _assert_unauthorized(_get(protected_client, f"Bearer {expired}"))


def test_token_of_missing_user_is_rejected(app: Flask, protected_client: FlaskClient) -> None:
    _assert_unauthorized(_get(protected_client, f"Bearer {_token(app, 999)}"))
