from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def get_auth_headers():
    email = "share_links_test_2026@example.com"
    password = "TestPassword123!"

    register_response = client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": password,
        },
    )

    assert register_response.status_code in (200, 201, 400, 409)

    login_response = client.post(
        "/api/auth/login",
        json={
            "email": email,
            "password": password,
        },
    )

    assert login_response.status_code == 200

    return {
        "Authorization": f"Bearer {login_response.json()['access_token']}"
    }


def create_test_document(headers):
    response = client.post(
        "/api/documents/upload",
        headers=headers,
        files={
            "file": (
                "share-link-test.txt",
                b"Share link test document",
                "text/plain",
            )
        },
        data={
            "description": "Document for share link tests",
        },
    )

    assert response.status_code in (200, 201)

    return response.json()["id"]


def test_create_share_link():
    headers = get_auth_headers()
    document_id = create_test_document(headers)

    response = client.post(
        f"/api/documents/{document_id}/share-links",
        headers=headers,
        json={},
    )

    assert response.status_code in (200, 201)

    data = response.json()

    assert "token" in data
    assert data["document_id"] == document_id


def test_create_password_protected_share_link():
    headers = get_auth_headers()
    document_id = create_test_document(headers)

    response = client.post(
        f"/api/documents/{document_id}/share-links",
        headers=headers,
        json={
            "password": "SharePassword123!",
        },
    )

    assert response.status_code in (200, 201)

    data = response.json()

    assert "token" in data
    assert data["document_id"] == document_id


def test_create_one_time_share_link():
    headers = get_auth_headers()
    document_id = create_test_document(headers)

    response = client.post(
        f"/api/documents/{document_id}/share-links",
        headers=headers,
        json={
            "is_one_time": True,
        },
    )

    assert response.status_code in (200, 201)

    data = response.json()

    assert data["is_one_time"] is True


def test_create_expiring_share_link():
    headers = get_auth_headers()
    document_id = create_test_document(headers)

    expires_at = (
        datetime.now(timezone.utc) + timedelta(hours=1)
    ).isoformat()

    response = client.post(
        f"/api/documents/{document_id}/share-links",
        headers=headers,
        json={
            "expires_at": expires_at,
        },
    )

    assert response.status_code in (200, 201)

    data = response.json()

    assert data["expires_at"] is not None


def test_invalid_share_link_expiry():
    headers = get_auth_headers()
    document_id = create_test_document(headers)

    expires_at = (
        datetime.now(timezone.utc) - timedelta(hours=1)
    ).isoformat()

    response = client.post(
        f"/api/documents/{document_id}/share-links",
        headers=headers,
        json={
            "expires_at": expires_at,
        },
    )

    assert response.status_code in (400, 422)


def test_nonexistent_document_share_link():
    headers = get_auth_headers()

    response = client.post(
        "/api/documents/999999/share-links",
        headers=headers,
        json={},
    )

    assert response.status_code in (403, 404)