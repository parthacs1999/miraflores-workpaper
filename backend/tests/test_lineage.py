from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_trace_wages():
    response = client.get("/api/lineage/F1040.1a")

    assert response.status_code == 200

    data = response.json()
    assert data["version"] == "v3"
    assert data["lineage"]["key"] == "F1040.1a"


def test_document_destinations():
    response = client.get("/api/documents/D09/destinations")

    assert response.status_code == 200

    data = response.json()
    assert data["document_id"] == "D09"
    assert "direct_lines" in data
    assert "downstream_lines" in data


def test_diagnostics():
    response = client.get("/api/return-versions/v3/diagnostics")

    assert response.status_code == 200
    assert isinstance(response.json()["diagnostics"], list)


def test_missing_line():
    response = client.get("/api/lineage/INVALID")

    assert response.status_code == 404


def test_missing_version():
    response = client.get("/api/lineage/F1040.1a?version=v99")

    assert response.status_code == 404
