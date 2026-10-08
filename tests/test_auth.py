from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_register_validation():
    response = client.post(
        "/api/auth/register",
        json={
            "email": "invalid-email",
            "password": "short",
        },
    )

    assert response.status_code == 422


def test_login_without_credentials():
    response = client.post(
        "/api/auth/login",
        json={
            "email": "doesnotexist@example.com",
            "password": "WrongPassword123!",
        },
    )

    assert response.status_code in (401, 404)