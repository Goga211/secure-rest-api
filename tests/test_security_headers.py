"""Security-заголовки добавляются к каждому ответу, включая ошибки."""

import pytest
from flask.testing import FlaskClient
from werkzeug.test import TestResponse

from tests.conftest import TEST_PASSWORD, AuthUser

EXPECTED_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
}


def assert_security_headers(response: TestResponse) -> None:
    for name, value in EXPECTED_HEADERS.items():
        assert response.headers.get(name) == value, name


def test_headers_on_health(client: FlaskClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert_security_headers(response)


@pytest.mark.parametrize(
    ("username", "status"),
    [("alice", 200), ("mallory", 401)],
)
def test_headers_on_login(client: FlaskClient, alice: AuthUser, username: str, status: int) -> None:
    response = client.post("/auth/login", json={"username": username, "password": TEST_PASSWORD})

    assert response.status_code == status
    assert_security_headers(response)


def test_headers_on_api_data(client: FlaskClient, alice: AuthUser) -> None:
    response = client.get("/api/data", headers=alice.headers)

    assert response.status_code == 200
    assert_security_headers(response)


def test_headers_on_unauthorized_api_data(client: FlaskClient) -> None:
    response = client.get("/api/data")

    assert response.status_code == 401
    assert_security_headers(response)
