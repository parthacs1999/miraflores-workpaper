
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_overview():
    response = client.get("/api/overview")
    assert response.status_code == 200

    data = response.json()
    assert data["stats"]["documents"] == 74
    assert data["stats"]["extracted_values"] == 3012
    assert data["current_version"] == "v3"


def test_documents():
    response = client.get("/api/documents")
    assert response.status_code == 200
    assert len(response.json()) == 74


def test_document_detail():
    response = client.get("/api/documents/D01")
    assert response.status_code == 200
    assert response.json()["id"] == "D01"
    assert "pages" in response.json()


def test_evidence():
    response = client.get("/api/evidence/ev-0001")
    assert response.status_code == 200
    assert response.json()["document_id"] == "D01"


def test_return_lines():
    response = client.get("/api/return-lines?version=v3")
    assert response.status_code == 200
    assert response.json()["count"] > 0


def test_missing_document():
    response = client.get("/api/documents/INVALID")
    assert response.status_code == 404


def test_missing_version():
    response = client.get("/api/return-lines?version=v99")
    assert response.status_code == 404
