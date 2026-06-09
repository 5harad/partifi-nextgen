from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_liveness() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_csrf_token() -> None:
    response = client.get("/api/v1/csrf-token")
    assert response.status_code == 200
    body = response.json()
    assert "csrf_token" in body
    assert body["csrf_token"]
