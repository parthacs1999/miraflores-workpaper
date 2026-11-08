import os

from app.security import Settings
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
from app.services.source_verification_service import (
    get_source_verification,
    get_source_verification_summary,
)
from app.adjustment_api import router as adjustment_router
from app.evidence_api import router as evidence_router
from app.reconciliation_api import router as reconciliation_router

app = FastAPI(title="MiraFlores Tax Workpaper API")
app.include_router(adjustment_router)
app.include_router(evidence_router)
app.include_router(reconciliation_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(Settings.from_env().origins) if Settings.from_env().mode != "legacy_test" else ["http://localhost:3000"] + [
        origin.strip() for origin in os.environ.get("EXTRA_CORS_ORIGINS", "").split(",") if origin.strip()
    ],
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


@app.patch("/api/review-decision")
def save_review_decision(
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


@app.get("/api/review-history")
def read_review_history(
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


@app.get("/api/source-verification")
def source_verification_summary():
    return get_source_verification_summary()


@app.get("/api/source-verification/{evidence_id}")
def source_verification_detail(evidence_id: str):
    result = get_source_verification(evidence_id)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Extracted value not found",
        )

    return result


# One boundary covers every existing and future API, including documentation routes.
from app.workflow_api import router as workflow_router
from app.security import SecurityBoundary, Settings
app.include_router(workflow_router)
from app.change_analysis_api import router as change_router
app.include_router(change_router)
from app.lifecycle_api import router as lifecycle_router
app.include_router(lifecycle_router)
from app.product_api import router as product_router
app.include_router(product_router)
Settings.from_env().validate()
app.add_middleware(SecurityBoundary)
if Settings.from_env().mode=="access":
    from app.hosting_headers import HostedSecurityHeaders
    app.add_middleware(HostedSecurityHeaders)

def create_app(settings):
    """Explicit settings for isolated strict-mode tests; route contracts are shared."""
    settings.validate()
    instance=FastAPI(title="MiraFlores Tax Workpaper API")
    instance.router.routes.extend(app.router.routes)
    instance.add_middleware(SecurityBoundary,settings=settings)
    instance.add_middleware(CORSMiddleware,allow_origins=list(settings.origins),allow_credentials=True,allow_methods=["GET","POST","PATCH","OPTIONS"],allow_headers=["Content-Type","X-CSRF-Token","X-Sensitive-Access","X-Access-Purpose"])
    if settings.mode=="access":
        from app.hosting_headers import HostedSecurityHeaders
        instance.add_middleware(HostedSecurityHeaders)
    return instance
