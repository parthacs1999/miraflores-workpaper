from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.services import adjustment_service as service
from app.services.review_service import ReviewError

router = APIRouter(prefix='/api', tags=['Audited adjustments'])


class AdjustmentInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    actor_id: str
    target: str
    proposed_value: Annotated[Decimal, Field(max_digits=14, decimal_places=2, allow_inf_nan=False)]
    rationale: str = Field(min_length=1, max_length=4000)
    authority: str = Field(min_length=1, max_length=4000)
    refs: list[str] = Field(min_length=1, max_length=100)


class RevisionInput(AdjustmentInput):
    expected_sequence: int = Field(ge=1)


class ActionInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    actor_id: str
    expected_sequence: int = Field(ge=1)
    action: Literal['submit', 'approve', 'reject', 'reverse', 'supersede']
    note: str = Field(min_length=1, max_length=4000)


def invoke(function, *args):
    try:
        return function(*args)
    except (service.AdjustmentError, ReviewError) as error:
        raise HTTPException(error.status_code, error.message) from error


@router.get('/adjustment-metadata')
def metadata(version: str = 'v3'):
    return invoke(service.metadata, version)


@router.get('/adjustments')
def adjustments(version: str = 'v3'):
    return invoke(service.list_adjustments, version)


@router.post('/adjustments', status_code=201)
def create(payload: AdjustmentInput, version: str = 'v3'):
    return invoke(service.create_adjustment, version, payload.model_dump())


@router.get('/adjustments/{identifier}')
def detail(identifier: str):
    return invoke(service.get_adjustment, identifier)


@router.post('/adjustments/{identifier}/revisions')
def revise(identifier: str, payload: RevisionInput):
    return invoke(service.revise_adjustment, identifier, payload.model_dump())


@router.post('/adjustments/{identifier}/actions')
def action(identifier: str, payload: ActionInput):
    return invoke(service.act_on_adjustment, identifier, payload.model_dump())


@router.get('/adjustments/{identifier}/history')
def history(identifier: str):
    return invoke(service.history, identifier)


@router.get('/workpaper-summary')
def summary(version: str = 'v3'):
    return invoke(service.summary, version)
