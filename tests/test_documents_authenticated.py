import io

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def get_auth_headers():
    email = "coverage_user_2026@example.com"
    password = "TestPassword123!"

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


def test_authenticated_list_documents():
    headers = get_auth_headers()

    response = client.get(
        "/api/documents",
        headers=headers,
    )

    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_authenticated_search_documents():
    headers = get_auth_headers()

    response = client.get(
        "/api/documents/search?q=rose",
        headers=headers,
    )

    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_upload_document():
    headers = get_auth_headers()

    response = client.post(
        "/api/documents/upload",
        headers=headers,
        files={
            "file": (
                "coverage_test_unique.txt",
                io.BytesIO(b"DocuVault coverage test content"),
                "text/plain",
            )
        },
        data={
            "description": "Coverage test document",
        },
    )

    assert response.status_code in (200, 201)

    data = response.json()

    assert "id" in data
    assert data["original_filename"] == "coverage_test_unique.txt"
    assert data["current_version"] == 1


def test_get_document():
    headers = get_auth_headers()

    upload_response = client.post(
        "/api/documents/upload",
        headers=headers,
        files={
            "file": (
                "get_test.txt",
                io.BytesIO(b"Document retrieval test"),
                "text/plain",
            )
        },
        data={
            "description": "Document retrieval test",
        },
    )

    assert upload_response.status_code in (200, 201)

    document_id = upload_response.json()["id"]

    response = client.get(
        f"/api/documents/{document_id}",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["id"] == document_id


def test_update_document():
    headers = get_auth_headers()

    upload_response = client.post(
        "/api/documents/upload",
        headers=headers,
        files={
            "file": (
                "update_test.txt",
                io.BytesIO(b"Document update test"),
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
    assert response.json()["description"] == "Updated description"


def test_list_versions():
    headers = get_auth_headers()

    upload_response = client.post(
        "/api/documents/upload",
        headers=headers,
        files={
            "file": (
                "version_test.txt",
                io.BytesIO(b"Version one"),
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
    assert isinstance(response.json(), list)


def test_download_document():
    headers = get_auth_headers()

    upload_response = client.post(
        "/api/documents/upload",
        headers=headers,
        files={
            "file": (
                "download_test.txt",
                io.BytesIO(b"Download test content"),
                "text/plain",
            )
        },
        data={
            "description": "Download test",
        },
    )

    assert upload_response.status_code in (200, 201)

    document_id = upload_response.json()["id"]

    response = client.get(
        f"/api/documents/{document_id}/download",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.content == b"Download test content"


def test_create_new_version():
    headers = get_auth_headers()

    upload_response = client.post(
        "/api/documents/upload",
        headers=headers,
        files={
            "file": (
                "version_flow.txt",
                io.BytesIO(b"Version 1 content"),
                "text/plain",
            )
        },
        data={
            "description": "Version flow test",
        },
    )

    assert upload_response.status_code in (200, 201)

    document_id = upload_response.json()["id"]

    version_response = client.post(
        f"/api/documents/{document_id}/versions",
        headers=headers,
        files={
            "file": (
                "version_flow.txt",
                io.BytesIO(b"Version 2 content"),
                "text/plain",
            )
        },
    )

    assert version_response.status_code in (200, 201)


def test_delete_document():
    headers = get_auth_headers()

    upload_response = client.post(
        "/api/documents/upload",
        headers=headers,
        files={
            "file": (
                "delete_test.txt",
                io.BytesIO(b"Delete test content"),
                "text/plain",
            )
        },
        data={
            "description": "Delete test",
        },
    )

    assert upload_response.status_code in (200, 201)

    document_id = upload_response.json()["id"]

    delete_response = client.delete(
        f"/api/documents/{document_id}",
        headers=headers,
    )

    assert delete_response.status_code in (200, 204)

    get_response = client.get(
        f"/api/documents/{document_id}",
        headers=headers,
    )

    assert get_response.status_code == 404


def test_restore_document_version():
    headers = get_auth_headers()

    upload_response = client.post(
        "/api/documents/upload",
        headers=headers,
        files={
            "file": (
                "restore_test.txt",
                io.BytesIO(b"Original content"),
                "text/plain",
            )
        },
        data={
            "description": "Restore test",
        },
    )

    assert upload_response.status_code in (200, 201)

    document_id = upload_response.json()["id"]

    version_response = client.post(
        f"/api/documents/{document_id}/versions",
        headers=headers,
        files={
            "file": (
                "restore_test.txt",
                io.BytesIO(b"Second version content"),
                "text/plain",
            )
        },
    )

    assert version_response.status_code in (200, 201)

    restore_response = client.post(
        f"/api/documents/{document_id}/versions/1/restore",
        headers=headers,
    )

    assert restore_response.status_code in (200, 201)


def test_download_after_version_creation():
    headers = get_auth_headers()

    upload_response = client.post(
        "/api/documents/upload",
        headers=headers,
        files={
            "file": (
                "version_download_test.txt",
                io.BytesIO(b"First version"),
                "text/plain",
            )
        },
        data={
            "description": "Version download test",
        },
    )

    assert upload_response.status_code in (200, 201)

    document_id = upload_response.json()["id"]

    version_response = client.post(
        f"/api/documents/{document_id}/versions",
        headers=headers,
        files={
            "file": (
                "version_download_test.txt",
                io.BytesIO(b"Second version"),
                "text/plain",
            )
        },
    )

    assert version_response.status_code in (200, 201)

    download_response = client.get(
        f"/api/documents/{document_id}/download",
        headers=headers,
    )

    assert download_response.status_code == 200
    assert download_response.content == b"Second version"
    