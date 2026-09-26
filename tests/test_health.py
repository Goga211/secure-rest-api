from flask.testing import FlaskClient


def test_health_returns_ok_envelope(client: FlaskClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.get_json() == {"success": True, "data": {"status": "ok"}, "error": None}
