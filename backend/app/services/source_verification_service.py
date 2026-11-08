import json
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from pathlib import Path

from app.services.field_match_service import source_candidates

PACKET_PATH = Path(__file__).resolve().parents[2] / "data" / "Instructions.json"


@lru_cache(maxsize=1)
def load_source_packet():
    with PACKET_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def numeric_value(value):
    if isinstance(value, bool):
        return None

    if not isinstance(value, (int, float, str)):
        return None

    cleaned = str(value).strip().replace(",", "").replace("$", "")

    if not re.fullmatch(r"-?\d+(?:\.\d+)?", cleaned):
        return None

    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def equivalent_numeric_token(value, text):
    target = numeric_value(value)

    if target is None:
        return None

    pattern = r"(?<![\w.])" r"\(?-?\$?\d[\d,]*(?:\.\d+)?\)?" r"(?![\w.])"

    for match in re.finditer(pattern, text):
        token = match.group()

        negative = token.startswith("(") and token.endswith(")")
        cleaned = token.strip("()")

        candidate = numeric_value(cleaned)

        if candidate is None:
            continue

        if negative:
            candidate = -candidate

        if candidate == target:
            return match.group()

    return None


def equivalent_date_token(value, text):
    if not isinstance(value, str):
        return None

    try:
        target = datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None

    for match in re.finditer(
        r"\b\d{1,2}/\d{1,2}/\d{4}\b",
        text,
    ):
        try:
            candidate = datetime.strptime(
                match.group(),
                "%m/%d/%Y",
            ).date()

            if candidate == target:
                return match.group()
        except ValueError:
            continue

    return None


def find_supporting_text(evidence, printed_content):
    raw = str(evidence.get("text_as_read") or "").strip()
    value = evidence.get("value")
    value_type = str(evidence.get("value_type") or "").lower()

    if raw:
        index = printed_content.find(raw)

        if index >= 0:
            return {
                "method": "exact_extracted_text",
                "matched_text": raw,
                "start": index,
                "end": index + len(raw),
            }

    if value_type in {"date"}:
        candidate = equivalent_date_token(value, printed_content)

        if candidate:
            index = printed_content.find(candidate)

            return {
                "method": "normalized_date",
                "matched_text": candidate,
                "start": index,
                "end": index + len(candidate),
            }

    if value_type in {
        "number",
        "numeric",
        "money",
        "currency",
        "amount",
        "integer",
        "float",
        "decimal",
    } or isinstance(value, (int, float)):
        candidate = equivalent_numeric_token(value, printed_content)

        if candidate:
            index = printed_content.find(candidate)

            return {
                "method": "normalized_number",
                "matched_text": candidate,
                "start": index,
                "end": index + len(candidate),
            }

    if value is not None:
        candidate = str(value).strip()

        if candidate:
            index = printed_content.find(candidate)

            if index >= 0:
                return {
                    "method": "exact_value",
                    "matched_text": candidate,
                    "start": index,
                    "end": index + len(candidate),
                }

    return None


def verify_extracted_value(evidence, documents):
    document_id = evidence.get("document_id")
    document = documents.get(document_id)

    result = {
        "evidence_id": evidence.get("id"),
        "document_id": document_id,
        "page": evidence.get("page"),
        "field": evidence.get("field"),
        "label": evidence.get("label"),
        "extracted_value": evidence.get("value"),
        "text_as_read": evidence.get("text_as_read"),
        "confidence": evidence.get("confidence"),
        "position": evidence.get("position"),
        "document_title": (document.get("title") if document else None),
        "status": "unverified",
        "reason": "",
        "match": None,
        "printed_content": None,
        "assessment": "missing_source",
        "candidates": [],
        "automatic": True,
        "human_verified": False,
    }

    if document is None:
        result["status"] = "missing_source"
        result["reason"] = "Referenced source document was not found."
        return result

    page = next(
        (
            item
            for item in document.get("pages", [])
            if item.get("page") == evidence.get("page")
        ),
        None,
    )

    if page is None:
        result["status"] = "missing_source"
        result["reason"] = "Referenced source page was not found."
        return result

    printed_content = page.get("printed_content")

    if not isinstance(printed_content, str):
        result["status"] = "missing_source"
        result["reason"] = "Source page has no printed text."
        return result

    result["printed_content"] = printed_content

    analysis = source_candidates(evidence, printed_content)
    result.update(analysis)
    result['status'] = 'supported' if analysis['assessment'] == 'field_supported' else 'unverified'

    return result


def get_source_verification(evidence_id):
    packet = load_source_packet()

    evidence = next(
        (item for item in packet["extracted_values"] if item["id"] == evidence_id),
        None,
    )

    if evidence is None:
        return None

    documents = {item["id"]: item for item in packet["documents"]}

    return verify_extracted_value(evidence, documents)


def get_source_verification_summary():
    packet = load_source_packet()

    documents = {item["id"]: item for item in packet["documents"]}

    results = [
        verify_extracted_value(item, documents) for item in packet["extracted_values"]
    ]

    counts = {
        "supported": 0,
        "unverified": 0,
        "missing_source": 0,
    }

    for result in results:
        counts[result["status"]] += 1

    return {
        "total": len(results),
        "counts": counts,
        "results": results,
    }
