import json
from functools import lru_cache
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "Instructions.json"


@lru_cache(maxsize=1)
def load_packet():
    if not DATA_PATH.is_file():
        raise FileNotFoundError(f"Missing dataset: {DATA_PATH}")

    with DATA_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def get_overview():
    packet = load_packet()

    return {
        "packet": packet["packet"],
        "household": packet["household"],
        "stats": {
            "documents": len(packet["documents"]),
            "extracted_values": len(packet["extracted_values"]),
            "return_versions": len(packet["return_versions"]),
            "timeline_events": len(packet["timeline"]),
        },
        "current_version": packet["return_versions"][-1]["version"],
    }


def get_documents():
    packet = load_packet()

    return [
        {
            "id": document["id"],
            "title": document["title"],
            "document_type": document["document_type"],
            "issuer": document.get("issuer"),
            "tax_year": document.get("tax_year"),
            "page_count": document["page_count"],
        }
        for document in packet["documents"]
    ]


def get_document(document_id):
    packet = load_packet()

    return next(
        (document for document in packet["documents"] if document["id"] == document_id),
        None,
    )


def get_extracted_value(value_id):
    packet = load_packet()

    return next(
        (value for value in packet["extracted_values"] if value["id"] == value_id),
        None,
    )


def get_return_versions():
    packet = load_packet()

    return [
        {
            "version": version["version"],
            "computed_at": version["computed_at"],
            "trigger": version["trigger"],
            "summary": version["summary"],
        }
        for version in packet["return_versions"]
    ]


def get_return_lines(version_id="v3"):
    packet = load_packet()

    version = next(
        (
            version
            for version in packet["return_versions"]
            if version["version"] == version_id
        ),
        None,
    )

    return version["lines"] if version else None
