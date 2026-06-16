from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_security_headers_on_response() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert (
        response.headers["Permissions-Policy"]
        == "geolocation=(), microphone=(), camera=()"
    )
    assert "Strict-Transport-Security" not in response.headers
