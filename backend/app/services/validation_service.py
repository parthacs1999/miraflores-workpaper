import re
from functools import lru_cache

from app.services.packet_service import load_packet


def finding(code, severity, title, description, refs):
    return {
        "id": code + ":" + ":".join(refs),
        "code": code,
        "severity": severity,
        "title": title,
        "description": description,
        "refs": refs,
        "status": "open",
        "origin": "independent_check",
    }


def check_broken_references(packet, version):
    findings = []
    evidence_ids = {value["id"] for value in packet["extracted_values"]}
    line_keys = {line["key"] for line in version["lines"]}

    for line in version["lines"]:
        for source in line.get("sources", []):
            if source.startswith("ev-") and source not in evidence_ids:
                findings.append(
                    finding(
                        "MISSING_EVIDENCE",
                        "critical",
                        "Missing evidence reference",
                        f"{line['key']} references nonexistent {source}.",
                        [line["key"], source],
                    )
                )

        for input_key in line.get("inputs", []):
            if input_key not in line_keys:
                findings.append(
                    finding(
                        "MISSING_INPUT",
                        "critical",
                        "Missing calculation input",
                        f"{line['key']} depends on missing line {input_key}.",
                        [line["key"], input_key],
                    )
                )

    return findings


def check_document_usage(packet, version):
    findings = []

    used = set(version.get("documents_used", []))
    superseded = set(version.get("documents_superseded", []))
    known = {doc["id"] for doc in packet["documents"]}

    for doc_id in sorted(used & superseded):
        findings.append(
            finding(
                "USED_AND_SUPERSEDED",
                "high",
                "Document usage conflict",
                "Document is both used and superseded in this version.",
                [doc_id],
            )
        )

    for doc_id in sorted((used | superseded) - known):
        findings.append(
            finding(
                "UNKNOWN_DOCUMENT",
                "critical",
                "Unknown document reference",
                "Return version references a missing document.",
                [doc_id],
            )
        )

    return findings


def check_extraction_candidates(packet):
    findings = []

    pages = {
        (doc["id"], page["page"]): page["printed_content"]
        for doc in packet["documents"]
        for page in doc["pages"]
    }

    for value in packet["extracted_values"]:
        if value.get("value_type") not in {"money", "integer"}:
            continue

        raw = value.get("text_as_read")
        if raw is None or isinstance(raw, bool):
            continue

        raw_text = str(raw).strip()
        if not raw_text:
            continue

        page_text = pages.get((value["document_id"], value["page"]), "")

        # Only flag a candidate when the literal extraction
        # cannot be located. This is NOT proof of an error.
        if raw_text not in page_text:
            findings.append(
                finding(
                    "SOURCE_TEXT_NOT_FOUND",
                    "info",
                    "Extraction needs source verification",
                    (
                        f"Extracted text {raw_text!r} was not found "
                        "verbatim in the simulated printed page. "
                        "Formatting or rounding may explain this."
                    ),
                    [value["id"], value["document_id"]],
                )
            )

    return findings


def check_prior_year_variances(packet, version):
    findings = []

    prior = packet.get("prior_years", {}).get("return_2024", {}).get("lines", {})

    if not isinstance(prior, dict):
        return findings

    for line in version["lines"]:
        key = line["key"]

        if key not in prior:
            continue

        current = line.get("value")
        previous = prior[key]

        if (
            isinstance(current, bool)
            or isinstance(previous, bool)
            or not isinstance(current, (int, float))
            or not isinstance(previous, (int, float))
        ):
            continue

        difference = current - previous

        if abs(difference) < 10000:
            continue

        if abs(previous) < 1000:
            continue

        percentage = abs(difference / previous)

        if percentage >= 0.5:
            findings.append(
                finding(
                    "PRIOR_YEAR_VARIANCE",
                    "medium",
                    "Significant year-over-year change",
                    (
                        f"{key}: prior year {previous:,.2f}, "
                        f"current year {current:,.2f}. "
                        "CPA explanation required."
                    ),
                    [key, "py:/return_2024/lines/" + key],
                )
            )

    return findings


@lru_cache(maxsize=3)
def run_validation(version_id="v3"):
    packet = load_packet()

    version = next(
        (item for item in packet["return_versions"] if item["version"] == version_id),
        None,
    )

    if version is None:
        return None

    findings = (
        check_broken_references(packet, version)
        + check_document_usage(packet, version)
        + check_extraction_candidates(packet)
        + check_prior_year_variances(packet, version)
    )

    findings.sort(
        key=lambda item: (
            {
                "critical": 0,
                "high": 1,
                "medium": 2,
                "info": 3,
            }.get(item["severity"], 4),
            item["id"],
        )
    )

    return {
        "version": version_id,
        "total": len(findings),
        "findings": findings,
        "summary": {
            severity: sum(item["severity"] == severity for item in findings)
            for severity in ("critical", "high", "medium", "info")
        },
    }
