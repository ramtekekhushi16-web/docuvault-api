from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def get_auth_headers():
    email = "share_access_test_2026@example.com"
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
                "share-access-test.txt",
                b"Secret shared document",
                "text/plain",
            )
        },
        data={
            "description": "Share access test document",
        },
    )

    assert response.status_code in (200, 201)

    return response.json()["id"]


def create_share_link(headers, document_id, **data):
    response = client.post(
        f"/api/documents/{document_id}/share-links",
        headers=headers,
        json=data,
    )

    assert response.status_code in (200, 201)

    return response.json()


def test_invalid_share_token():
    response = client.get(
        "/api/share/this-is-an-invalid-token"
    )

    assert response.status_code in (401, 403, 404)


def test_valid_share_link_access():
    headers = get_auth_headers()
    document_id = create_test_document(headers)

    share_link = create_share_link(
        headers,
        document_id,
    )

    token = share_link["token"]

    response = client.get(
        f"/api/share/{token}"
    )

    assert response.status_code == 200


def test_password_protected_share_link():
    headers = get_auth_headers()
    document_id = create_test_document(headers)

    share_link = create_share_link(
        headers,
        document_id,
        password="SharePassword123!",
    )

    token = share_link["token"]

    # Access without password should be rejected.
    response = client.get(
        f"/api/share/{token}"
    )

    assert response.status_code in (400, 401, 403)


def test_one_time_share_link():
    headers = get_auth_headers()
    document_id = create_test_document(headers)

    share_link = create_share_link(
        headers,
        document_id,
        is_one_time=True,
    )

    token = share_link["token"]

    first_response = client.get(
        f"/api/share/{token}"
    )

    assert first_response.status_code == 200

    second_response = client.get(
        f"/api/share/{token}"
    )


    assert second_response.status_code in (400, 401, 403, 404, 410)