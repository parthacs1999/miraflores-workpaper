from typing import Literal
from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from app.adjustment_api import invoke
from app.services import evidence_service, verification_service
from app.services.adjustment_service import version_data
from app.services.document_accountability_service import accountability

router = APIRouter(prefix='/api', tags=['Evidence and document accountability'])


class Quote(BaseModel):
    model_config = ConfigDict(extra='forbid')
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    text: str = Field(min_length=1, max_length=10000)


class VerificationInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    verifier_id: str
    method: Literal['agreed_to_source_document', 'recalculated', 'confirmed_with_client', 'agreed_to_prior_year', 'agreed_to_third_party_record']
    source_ref: str = Field(min_length=1, max_length=500)
    status: Literal['confirmed', 'needs_review', 'revoked']
    notes: str = Field(min_length=1, max_length=4000)
    expected_sequence: int = Field(ge=0)
    quote: Quote | None = None


@router.get('/evidence-resolution', response_model=evidence_service.EvidenceResolution)
def resolve(ref: str, version: str = 'v3'):
    return evidence_service.resolve_reference(ref, version)


@router.get('/evidence-graph', response_model=evidence_service.EvidenceGraphResult)
def graph(ref: str, version: str = 'v3'):
    return evidence_service.evidence_graph(ref, version)


@router.get('/document-accountability')
def documents(version: str = 'v3'):
    invoke(version_data, version)
    return accountability(version)


@router.get('/verification-metadata')
def metadata():
    return verification_service.metadata()


@router.get('/field-verifications/{evidence_id}')
def history(evidence_id: str, version: str = 'v3'):
    return invoke(verification_service.history, evidence_id, version)


@router.post('/field-verifications/{evidence_id}', status_code=201)
def save(evidence_id: str, payload: VerificationInput, version: str = 'v3'):
    return invoke(verification_service.save, evidence_id, version, payload.model_dump())


@router.get('/documents/{document_id}/evidence')
def document_evidence(document_id: str):
    from app.services.packet_service import load_packet
    from fastapi import HTTPException
    packet = load_packet()
    if not any(d['id'] == document_id for d in packet['documents']):
        raise HTTPException(404, 'Document not found')
    values = [e for e in packet['extracted_values'] if e['document_id'] == document_id]
    return {'document_id': document_id, 'count': len(values), 'values': values}
