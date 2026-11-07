from app.services.source_verification_service import (
    equivalent_numeric_token,
    equivalent_date_token,
    find_supporting_text,
    get_source_verification,
    get_source_verification_summary,
    verify_extracted_value,
)


def test_numeric_formatting():
    assert (
        equivalent_numeric_token(
            104600,
            "Box 1 $104,600.00",
        )
        == "$104,600.00"
    )


def test_numeric_value_not_found():
    assert (
        equivalent_numeric_token(
            104600,
            "Box 1 $105,600.00",
        )
        is None
    )


def test_date_formatting():
    assert (
        equivalent_date_token(
            "2026-01-12",
            "Signed 01/12/2026",
        )
        == "01/12/2026"
    )


def test_exact_text_match():
    evidence = {
        "text_as_read": "104,600.00",
        "value": 104600,
        "value_type": "money",
    }

    match = find_supporting_text(
        evidence,
        "Box 1 104,600.00",
    )

    assert match is not None
    assert match["method"] == "exact_extracted_text"


def test_unverified_not_false_mismatch():
    evidence = {
        "id": "test-value",
        "document_id": "TEST",
        "page": 1,
        "field": "box1",
        "label": "Wages",
        "value": 104600,
        "value_type": "money",
        "text_as_read": "104,600.00",
    }

    documents = {
        "TEST": {
            "title": "Test W-2",
            "pages": [
                {
                    "page": 1,
                    "printed_content": "Box 1 105,600.00",
                }
            ],
        }
    }

    result = verify_extracted_value(evidence, documents)

    assert result["status"] == "unverified"


def test_missing_source():
    evidence = {
        "id": "test-value",
        "document_id": "NOT_FOUND",
        "page": 1,
        "value": 100,
    }

    result = verify_extracted_value(evidence, {})

    assert result["status"] == "missing_source"


def test_real_w2_evidence():
    result = get_source_verification("ev-0016")

    assert result is not None
    assert result["document_id"] is not None
    assert result["printed_content"] is not None
    assert result["status"] == "supported"


def test_summary_covers_all_values():
    summary = get_source_verification_summary()

    assert summary["total"] == 3012

    assert sum(summary["counts"].values()) == 3012
