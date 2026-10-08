from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_list_documents_requires_authentication():
    response = client.get("/api/documents")
    assert response.status_code in (401, 403)


def test_search_documents_requires_authentication():
    response = client.get("/api/documents/search?q=rose")
    assert response.status_code in (401, 403)


def test_get_document_requires_authentication():
    response = client.get("/api/documents/999999")
    assert response.status_code in (401, 403)


def test_update_document_requires_authentication():
    response = client.put(
        "/api/documents/999999",
        json={"description": "Updated description"},
    )
    assert response.status_code in (401, 403)


def test_delete_document_requires_authentication():
    response = client.delete("/api/documents/999999")
    assert response.status_code in (401, 403)


def test_download_document_requires_authentication():
    response = client.get("/api/documents/999999/download")
    assert response.status_code in (401, 403)


def test_list_versions_requires_authentication():
    response = client.get("/api/documents/999999/versions")
    assert response.status_code in (401, 403)