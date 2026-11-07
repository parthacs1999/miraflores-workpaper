import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import review_service

client = TestClient(app)


@pytest.fixture
def review_environment(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "REVIEW_DB_PATH",
        str(tmp_path / "reviews.db"),
    )

    sample = {
        "version": "v3",
        "total": 1,
        "findings": [
            {
                "id": "TEST:ev-0016",
                "code": "TEST",
                "severity": "high",
                "title": "Test finding",
                "description": "Test discrepancy",
                "refs": ["ev-0016"],
                "status": "open",
                "origin": "independent_check",
            }
        ],
    }

    monkeypatch.setattr(
        review_service,
        "run_validation",
        lambda version="v3": (sample if version == "v3" else None),
    )

    return sample["findings"][0]["id"]


def test_reviews_initially_open(review_environment):
    response = client.get("/api/reviews")

    assert response.status_code == 200
    assert response.json()["findings"][0]["status"] == "open"


def test_review_update_persists(review_environment):
    finding_id = review_environment

    response = client.patch(
        f"/api/reviews/{finding_id}",
        json={
            "status": "in_review",
            "note": "Checking source document.",
            "actor_role": "preparer",
            "actor_name": "Demo Preparer",
        },
    )

    assert response.status_code == 200

    result = client.get("/api/reviews").json()

    assert result["findings"][0]["status"] == "in_review"
    assert result["findings"][0]["review_note"] == ("Checking source document.")


def test_preparer_cannot_resolve(review_environment):
    response = client.patch(
        f"/api/reviews/{review_environment}",
        json={
            "status": "resolved",
            "note": "Reviewed.",
            "actor_role": "preparer",
            "actor_name": "Demo Preparer",
        },
    )

    assert response.status_code == 403


def test_reviewer_can_resolve(review_environment):
    response = client.patch(
        f"/api/reviews/{review_environment}",
        json={
            "status": "resolved",
            "note": "Verified against source.",
            "actor_role": "reviewer",
            "actor_name": "Demo Reviewer",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "resolved"


def test_history_preserved(review_environment):
    finding_id = review_environment

    for status in ["in_review", "resolved"]:
        response = client.patch(
            f"/api/reviews/{finding_id}",
            json={
                "status": status,
                "note": f"Moved to {status}",
                "actor_role": "reviewer",
                "actor_name": "Demo Reviewer",
            },
        )
        assert response.status_code == 200

    response = client.get(f"/api/reviews/{finding_id}/history")

    assert response.status_code == 200

    events = response.json()["events"]

    assert len(events) == 2
    assert events[0]["new_status"] == "in_review"
    assert events[1]["previous_status"] == "in_review"
    assert events[1]["new_status"] == "resolved"


def test_unknown_finding_rejected(review_environment):
    response = client.patch(
        "/api/reviews/NOT_REAL",
        json={
            "status": "resolved",
            "note": "Invalid finding.",
            "actor_role": "reviewer",
            "actor_name": "Demo Reviewer",
        },
    )

    assert response.status_code == 404


def test_missing_note_rejected(review_environment):
    response = client.patch(
        f"/api/reviews/{review_environment}",
        json={
            "status": "in_review",
            "note": "",
            "actor_role": "reviewer",
            "actor_name": "Demo Reviewer",
        },
    )

    assert response.status_code == 422
