from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def get_auth_headers():
    email = "documents_authenticated_2026@example.com"
    password = "TestPassword123!"

    register_response = client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": password,
        },
    )

    assert register_response.status_code in (201, 400, 409)

    login_response = client.post(
        "/api/auth/login",
        json={
            "email": email,
            "password": password,
        },
    )

    assert login_response.status_code == 200

    data = login_response.json()

    assert "access_token" in data

    return {
        "Authorization": f"Bearer {data['access_token']}"
    }


def test_get_document():
    headers = get_auth_headers()

    upload_response = client.post(
        "/api/documents/upload",
        headers=headers,
        files={
            "file": (
                "auth_flow_get.txt",
                b"Document retrieval test",
                "text/plain",
            )
        },
        data={
            "description": "Auth flow get test",
        },
    )

    assert upload_response.status_code in (200, 201)

    document_id = upload_response.json()["id"]

    response = client.get(
        f"/api/documents/{document_id}",
        headers=headers,
    )

    assert response.status_code == 200


def test_update_document():
    headers = get_auth_headers()

    upload_response = client.post(
        "/api/documents/upload",
        headers=headers,
        files={
            "file": (
                "auth_flow_update.txt",
                b"Document update test",
                "text/plain",
            )
        },
        data={
            "description": "Original description",
        },
    )

    assert upload_response.status_code in (200, 201)

    document_id = upload_response.json()["id"]

    response = client.put(
        f"/api/documents/{document_id}",
        headers=headers,
        json={
            "description": "Updated description",
        },
    )

    assert response.status_code == 200


def test_list_versions():
    headers = get_auth_headers()

    upload_response = client.post(
        "/api/documents/upload",
        headers=headers,
        files={
            "file": (
                "auth_flow_versions.txt",
                b"Version test",
                "text/plain",
            )
        },
        data={
            "description": "Version test",
        },
    )

    assert upload_response.status_code in (200, 201)

    document_id = upload_response.json()["id"]

    response = client.get(
        f"/api/documents/{document_id}/versions",
        headers=headers,
    )

    assert response.status_code == 200