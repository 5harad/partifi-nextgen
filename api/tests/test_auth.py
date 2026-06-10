from fastapi.testclient import TestClient

from app.main import app
from app.services.auth import create_session_token, parse_session_token


client = TestClient(app)


def test_auth_me_anonymous() -> None:
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 200
    assert response.json()["user"] is None


def test_session_token_roundtrip() -> None:
    token = create_session_token("user-123")
    assert parse_session_token(token) == "user-123"


def test_dev_login_sets_session() -> None:
    response = client.post("/api/v1/auth/dev-login", json={"user_id": "test-user", "name": "Test User"})
    assert response.status_code == 200
    body = response.json()
    assert body["user"]["id"] == "test-user"
    assert body["user"]["name"] == "Test User"

    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["user"]["id"] == "test-user"


def test_library_requires_login() -> None:
    anonymous = TestClient(app)
    response = anonymous.get("/api/v1/library")
    assert response.status_code == 401


def test_library_empty_for_new_user() -> None:
    client.post("/api/v1/auth/dev-login", json={"user_id": "library-user", "name": "Library User"})
    response = client.get("/api/v1/library")
    assert response.status_code == 200
    assert response.json()["items"] == []


def test_google_login_not_configured() -> None:
    response = client.post("/api/v1/auth/google", json={"id_token": "invalid"})
    assert response.status_code == 503


def test_logout_clears_session() -> None:
    client.post("/api/v1/auth/dev-login", json={})
    response = client.post("/api/v1/auth/logout")
    assert response.status_code == 200
    me = client.get("/api/v1/auth/me")
    assert me.json()["user"] is None
