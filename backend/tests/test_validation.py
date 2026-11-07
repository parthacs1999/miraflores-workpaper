from fastapi.testclient import TestClient

from app.main import app
from app.services.packet_service import load_packet
from app.services.validation_service import (
    check_broken_references,
    check_document_usage,
    run_validation,
)

client = TestClient(app)


def test_validation_endpoint():
    response = client.get("/api/validation")

    assert response.status_code == 200
    data = response.json()

    assert data["version"] == "v3"
    assert data["total"] == len(data["findings"])


def test_validation_summary():
    data = run_validation("v3")

    assert sum(data["summary"].values()) == data["total"]


def test_validation_is_deterministic():
    assert run_validation("v3") == run_validation("v3")


def test_missing_version():
    response = client.get("/api/validation?version=v99")

    assert response.status_code == 404


def test_detects_missing_evidence():
    packet = {
        "extracted_values": [],
    }

    version = {
        "lines": [
            {
                "key": "TEST.1",
                "sources": ["ev-9999"],
                "inputs": [],
            }
        ]
    }

    results = check_broken_references(packet, version)

    assert any(item["code"] == "MISSING_EVIDENCE" for item in results)


def test_detects_document_conflict():
    packet = {
        "documents": [{"id": "D01"}],
    }

    version = {
        "documents_used": ["D01"],
        "documents_superseded": ["D01"],
    }

    results = check_document_usage(packet, version)

    assert any(item["code"] == "USED_AND_SUPERSEDED" for item in results)
