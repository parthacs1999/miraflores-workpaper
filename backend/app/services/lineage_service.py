from functools import lru_cache

from app.services.packet_service import load_packet


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


def resolve_source(source_id):
    idx = indexes()

    if source_id.startswith("ev-"):
        evidence = idx["evidence"].get(source_id)

        if evidence is None:
            return {
                "ref": source_id,
                "type": "missing_evidence",
            }

        document = idx["documents"].get(evidence["document_id"])

        return {
            "ref": source_id,
            "type": "extracted_value",
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
        "status": "unresolved",
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
            "sources": [resolve_source(source) for source in line.get("sources", [])],
            "inputs": [
                visit(input_key, next_visited) for input_key in line.get("inputs", [])
            ],
        }

    return {
        "version": version_id,
        "lineage": visit(line_key, set()),
    }


def document_destinations(document_id, version_id="v3"):
    idx = indexes()

    if document_id not in idx["documents"]:
        return None

    version = get_version(version_id)

    if version is None:
        return None

    evidence_ids = {
        e["id"] for e in idx["evidence"].values() if e["document_id"] == document_id
    }

    line_index = {line["key"]: line for line in version["lines"]}

    direct = [
        line
        for line in version["lines"]
        if evidence_ids.intersection(line.get("sources", []))
    ]

    direct_keys = {line["key"] for line in direct}

    downstream = set(direct_keys)

    changed = True

    while changed:
        changed = False

        for line in version["lines"]:
            if line["key"] in downstream:
                continue

            if downstream.intersection(line.get("inputs", [])):
                downstream.add(line["key"])
                changed = True

    return {
        "document_id": document_id,
        "version": version_id,
        "direct_lines": direct,
        "downstream_lines": [
            line_index[key] for key in sorted(downstream - direct_keys)
        ],
        "unused_evidence_ids": sorted(
            evidence_ids
            - {source for line in direct for source in line.get("sources", [])}
        ),
        "document_used_by_engine": document_id in version.get("documents_used", []),
        "document_superseded_by_engine": document_id
        in version.get("documents_superseded", []),
    }
