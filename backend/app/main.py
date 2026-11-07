from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware
from app.services.packet_service import (
    get_overview,
    get_documents,
    get_document,
    get_extracted_value,
    get_return_versions,
    get_return_lines,
)
from app.services.lineage_service import (
    trace_line,
    document_destinations,
    get_version,
)
from app.services.validation_service import run_validation
from app.services.review_service import (
    ReviewError,
    list_reviews,
    update_review,
    get_review_history,
)

app = FastAPI(title="MiraFlores Tax Workpaper API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ReviewUpdate(BaseModel):
    status: str
    note: str = Field(min_length=1, max_length=4000)
    actor_role: str
    actor_name: str = Field(min_length=1, max_length=120)


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "miraflores-workpaper",
    }


@app.get("/api/overview")
def overview():
    return get_overview()


@app.get("/api/documents")
def documents():
    return get_documents()


@app.get("/api/documents/{document_id}")
def document_detail(document_id: str):
    document = get_document(document_id)

    if document is None:
        raise HTTPException(404, "Document not found")

    return document


@app.get("/api/evidence/{value_id}")
def evidence_detail(value_id: str):
    value = get_extracted_value(value_id)

    if value is None:
        raise HTTPException(404, "Evidence not found")

    return value


@app.get("/api/return-versions")
def return_versions():
    return get_return_versions()


@app.get("/api/return-lines")
def return_lines(version: str = "v3"):
    lines = get_return_lines(version)

    if lines is None:
        raise HTTPException(404, "Return version not found")

    return {
        "version": version,
        "count": len(lines),
        "lines": lines,
    }


@app.get("/api/lineage/{line_key}")
def lineage(line_key: str, version: str = "v3"):
    if get_version(version) is None:
        raise HTTPException(404, "Return version not found")

    result = trace_line(line_key, version)

    if result is None:
        raise HTTPException(404, "Return line not found")

    return result


@app.get("/api/documents/{document_id}/destinations")
def destinations(document_id: str, version: str = "v3"):
    if get_version(version) is None:
        raise HTTPException(404, "Return version not found")

    result = document_destinations(document_id, version)

    if result is None:
        raise HTTPException(404, "Document not found")

    return result


@app.get("/api/return-versions/{version_id}/diagnostics")
def diagnostics(version_id: str):
    version = get_version(version_id)

    if version is None:
        raise HTTPException(404, "Return version not found")

    return {
        "version": version_id,
        "diagnostics": version.get("diagnostics", []),
    }


@app.get("/api/validation")
def validation(version: str = "v3"):
    result = run_validation(version)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Return version not found",
        )

    return result


@app.get("/api/reviews")
def reviews(version: str = "v3"):
    try:
        return list_reviews(version)
    except ReviewError as error:
        raise HTTPException(
            status_code=error.status_code,
            detail=error.message,
        )


@app.patch("/api/reviews/{finding_id:path}")
def save_review(
    finding_id: str,
    payload: ReviewUpdate,
    version: str = "v3",
):
    try:
        return update_review(
            version=version,
            finding_id=finding_id,
            status=payload.status,
            note=payload.note,
            actor_role=payload.actor_role,
            actor_name=payload.actor_name,
        )
    except ReviewError as error:
        raise HTTPException(
            status_code=error.status_code,
            detail=error.message,
        )


@app.get("/api/reviews/{finding_id:path}/history")
def review_history(
    finding_id: str,
    version: str = "v3",
):
    try:
        return get_review_history(version, finding_id)
    except ReviewError as error:
        raise HTTPException(
            status_code=error.status_code,
            detail=error.message,
        )
