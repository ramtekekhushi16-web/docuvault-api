from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def unique_email(prefix="auth_extra"):
    import uuid
    return f"{prefix}_{uuid.uuid4().hex[:8]}@example.com"


def register_user(email=None, password="TestPassword123!"):
    if email is None:
        email = unique_email()

    response = client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": password,
        },
    )

    return response, email


def login_user(email, password="TestPassword123!"):
    return client.post(
        "/api/auth/login",
        json={
            "email": email,
            "password": password,
        },
    )


def test_duplicate_registration():
    response, email = register_user()

    assert response.status_code in (200, 201)

    duplicate_response, _ = register_user(
        email=email
    )

    assert duplicate_response.status_code in (400, 409)


def test_invalid_login_password():
    response, email = register_user()

    assert response.status_code in (200, 201)

    login_response = login_user(
        email,
        "WrongPassword123!",
    )

    assert login_response.status_code == 401


def test_invalid_login_email():
    login_response = login_user(
        unique_email("nonexistent"),
        "WrongPassword123!",
    )

    assert login_response.status_code in (401, 404)


def test_auth_me():
    response, email = register_user()

    assert response.status_code in (200, 201)

    login_response = login_user(email)

    assert login_response.status_code == 200

    access_token = login_response.json()["access_token"]

    me_response = client.get(
        "/api/auth/me",
        headers={
            "Authorization": f"Bearer {access_token}"
        },
    )

    assert me_response.status_code == 200

    data = me_response.json()

    assert data["email"] == email


def test_auth_me_without_token():
    response = client.get("/api/auth/me")

    assert response.status_code in (401, 403)


def test_auth_me_invalid_token():
    response = client.get(
        "/api/auth/me",
        headers={
            "Authorization": "Bearer invalid-token"
        },
    )

    assert response.status_code == 401


def test_refresh_token_flow():
    response, email = register_user()

    assert response.status_code in (200, 201)

    login_response = login_user(email)

    assert login_response.status_code == 200

    refresh_token = login_response.json()["refresh_token"]

    refresh_response = client.post(
        "/api/auth/refresh",
        json={
            "refresh_token": refresh_token
        },
    )

    assert refresh_response.status_code == 200

    data = refresh_response.json()

    assert "access_token" in data
    assert "refresh_token" in data


def test_invalid_refresh_token():
    response = client.post(
        "/api/auth/refresh",
        json={
            "refresh_token": "invalid-refresh-token"
        },
    )

    assert response.status_code == 401


def test_logout_invalid_refresh_token():
    response = client.post(
        "/api/auth/logout",
        json={
            "refresh_token": "invalid-refresh-token"
        },
    )

    assert response.status_code == 401