from functools import lru_cache

from app.services.packet_service import load_packet
from app.services.evidence_service import resolve_reference


@lru_cache(maxsize=1)
def indexes():
    packet = load_packet()

    return {
        "documents": {d["id"]: d for d in packet["documents"]},
        "evidence": {e["id"]: e for e in packet["extracted_values"]},
        "versions": {v["version"]: v for v in packet["return_versions"]},
    }


def get_version(version_id):
    return indexes()["versions"].get(version_id)


def resolve_source(source_id, version_id="v3"):
    resolution = resolve_reference(source_id, version_id).model_dump()
    idx = indexes()

    if source_id.startswith("ev-"):
        evidence = idx["evidence"].get(source_id)

        if evidence is None:
            return {
                "ref": source_id,
                "type": "missing_evidence",
                "resolution": resolution,
            }

        document = idx["documents"].get(evidence["document_id"])

        return {
            "ref": source_id,
            "type": "extracted_value",
            "resolution": resolution,
            "evidence": evidence,
            "document": (
                {
                    "id": document["id"],
                    "title": document["title"],
                    "pages": [
                        p for p in document["pages"] if p["page"] == evidence["page"]
                    ],
                }
                if document
                else None
            ),
        }

    return {
        "ref": source_id,
        "type": "external_reference",
        "status": resolution["status"],
        "resolution": resolution,
    }


def trace_line(line_key, version_id="v3"):
    version = get_version(version_id)

    if version is None:
        return None

    line_index = {line["key"]: line for line in version["lines"]}

    if line_key not in line_index:
        return None

    def visit(key, visited):
        if key in visited:
            return {
                "key": key,
                "cycle": True,
            }

        line = line_index.get(key)

        if line is None:
            return {
                "key": key,
                "missing": True,
            }

        next_visited = visited | {key}

        return {
            "key": key,
            "label": line["label"],
            "value": line["value"],
            "rule": line.get("rule"),
            "note": line.get("note"),
            "sources": [resolve_source(source, version_id) for source in line.get("sources", [])],
            "inputs": [
                visit(input_key, next_visited) for input_key in line.get("inputs", [])
            ],
        }

    return {
        "version": version_id,
        "lineage": visit(line_key, set()),
    }


def document_destinations(document_id, version_id="v3"):
    from app.services.document_accountability_service import document_destinations as trace_document
    return trace_document(document_id, version_id)
