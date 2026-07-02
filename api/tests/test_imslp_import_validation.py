from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _csrf_headers() -> dict[str, str]:
    token = client.get("/api/v1/csrf-token").json()["csrf_token"]
    return {"X-CSRF-Token": token}


def test_create_partset_from_imslp_rejects_whitespace_title() -> None:
    response = client.post(
        "/api/v1/partsets/imslp",
        headers=_csrf_headers(),
        json={
            "imslp_id": "12345",
            "title": "   ",
            "composer": "Composer",
            "publisher": "",
            "copyright": "unknown",
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Title and composer are required"


def test_create_partset_from_imslp_rejects_invalid_copyright() -> None:
    response = client.post(
        "/api/v1/partsets/imslp",
        headers=_csrf_headers(),
        json={
            "imslp_id": "12345",
            "title": "Title",
            "composer": "Composer",
            "publisher": "",
            "copyright": "invalid",
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid copyright value"
