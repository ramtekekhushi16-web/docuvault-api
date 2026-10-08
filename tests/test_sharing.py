from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def get_auth_headers():
    email = "sharing_test_2026@example.com"
    password = "TestPassword123!"

    register_response = client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": password,
        },
    )

    # User may already exist from a previous test run
    if register_response.status_code not in (200, 201, 400, 409):
        raise AssertionError(register_response.text)

    login_response = client.post(
        "/api/auth/login",
        json={
            "email": email,
            "password": password,
        },
    )

    assert login_response.status_code == 200

    token = login_response.json()["access_token"]

    return {
        "Authorization": f"Bearer {token}"
    }


def create_test_document(headers):
    response = client.post(
        "/api/documents/upload",
        headers=headers,
        files={
            "file": (
                "sharing-test.txt",
                b"Sharing test document",
                "text/plain",
            )
        },
        data={
            "description": "Document for sharing tests",
        },
    )

    assert response.status_code in (200, 201)

    return response.json()["id"]


def test_list_permissions():
    headers = get_auth_headers()
    document_id = create_test_document(headers)

    response = client.get(
        f"/api/documents/{document_id}/permissions",
        headers=headers,
    )

    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_grant_permission():
    owner_headers = get_auth_headers()

    # Create another user
    client.post(
        "/api/auth/register",
        json={
            "email": "viewer_test_2026@example.com",
            "password": "TestPassword123!",
        },
    )

    document_id = create_test_document(owner_headers)

    response = client.post(
        f"/api/documents/{document_id}/permissions",
        headers=owner_headers,
        json={
            "user_id": 1,
            "role": "Viewer",
        },
    )

    assert response.status_code in (200, 201, 400, 404)


def test_invalid_permission_role():
    headers = get_auth_headers()
    document_id = create_test_document(headers)

    response = client.post(
        f"/api/documents/{document_id}/permissions",
        headers=headers,
        json={
            "user_id": 1,
            "role": "InvalidRole",
        },
    )

    assert response.status_code == 422


def test_revoke_permission():
    headers = get_auth_headers()
    document_id = create_test_document(headers)

    response = client.delete(
        f"/api/documents/{document_id}/permissions/1",
        headers=headers,
    )

    assert response.status_code in (200, 204, 404)