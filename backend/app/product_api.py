"""Strict-session product routes. Long polling preserves the shared JSON security boundary."""
import asyncio
import time
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Request, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
from starlette.concurrency import run_in_threadpool

from app.adjustment_api import invoke
from app.workflow_api import actor
from app.services import product_service as s

router = APIRouter(prefix='/api/product', tags=['Collaboration and firm operations'])


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Note(Input):
    note: str = Field(min_length=1, max_length=4000)

    @field_validator('note')
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError('Documented rationale required')
        return value.strip()


class Link(Input):
    kind: Literal['finding', 'document', 'adjustment', 'note', 'workflow', 'question']
    id: str = Field(min_length=1, max_length=300)


class Attachment(Note):
    area: str
    title: str = Field(min_length=1, max_length=300)
    filename: str = Field(min_length=1, max_length=120)
    media_type: Literal['application/pdf', 'image/png', 'image/jpeg', 'text/plain']
    content_base64: str = Field(max_length=6990508)
    links: list[Link] = Field(min_length=1, max_length=30)


class AttachmentAction(Note):
    action: Literal['metadata', 'review']
    expected_revision: int = Field(ge=1)
    title: str = Field(default='', max_length=300)
    links: list[Link] = Field(default_factory=list, max_length=30)


class Question(Note):
    area: str
    title: str = Field(min_length=1, max_length=300)
    owner_id: str
    participants: list[str] = Field(min_length=1, max_length=20)
    due_date: str | None = None
    blocking: bool = True
    refs: list[str] = Field(default_factory=list, max_length=50)


class QuestionAction(Note):
    action: Literal['request_resolution', 'resolve', 'reopen']
    expected_revision: int = Field(ge=1)


class QuestionUpdate(Note):
    expected_revision: int = Field(ge=1)
    title: str = Field(min_length=1,max_length=300)
    owner_id: str
    participants: list[str] = Field(min_length=1,max_length=20)
    due_date: str|None = None
    blocking: bool
    refs: list[str] = Field(default_factory=list,max_length=50)


class Message(Note):
    expected_revision: int = Field(ge=1)
    parent_id: str | None = None
    declared_client_id: str | None = None
    refs: list[str] = Field(default_factory=list, max_length=50)


class Selection(Input):
    id: str = Field(min_length=1, max_length=300)
    expected_revision: int = Field(ge=0)


Operation = Literal['acknowledge_findings', 'acknowledge_documents', 'submit_records', 'assign_tasks']


class Bulk(Note):
    operation: Operation
    command_key: str = Field(pattern=r'^[A-Za-z0-9_-]{8,100}$')
    items: list[Selection] = Field(min_length=1, max_length=50)
    assignee: str | None = None


class Undo(Note):
    expected_revision: int = Field(ge=1)


class Checkpoint(Input):
    cursor: int = Field(ge=0)
    expected_revision: int = Field(ge=0)


class TimeEntry(Note):
    id: str | None = None
    area: str
    bucket: str
    minutes: int = Field(ge=1, le=1440)
    work_date: str
    state: Literal['recorded', 'voided'] = 'recorded'
    expected_revision: int = Field(ge=0)


class Budget(Note):
    bucket: str
    hours: Annotated[Decimal, Field(ge=0, le=100000, max_digits=8, decimal_places=2, allow_inf_nan=False)]
    expected_revision: int = Field(ge=0)


@router.get('/overview')
def overview(): return invoke(s.overview, actor())


@router.get('/changes')
async def changes(after: int | None = Query(default=None, ge=0), wait_seconds: float = Query(default=0, ge=0, le=20), limit: int = Query(default=100, ge=1, le=200)):
    person = actor(); deadline = time.monotonic() + wait_seconds
    while True:
        batch = await run_in_threadpool(invoke, s.change_batch, person, after, limit)
        if batch['events'] or batch['has_more'] or time.monotonic() >= deadline:
            return batch
        # No database transaction or lock is held while waiting. Authorization is
        # checked again on every pass and by the outer session boundary at delivery.
        await asyncio.sleep(min(.5, max(0, deadline - time.monotonic())))


@router.post('/checkpoint')
def checkpoint(payload: Checkpoint): return invoke(s.checkpoint_save, actor(), payload.model_dump())


@router.get('/bulk/catalog')
def catalog(operation: Operation): return invoke(s.bulk_catalog, actor(), operation)


@router.post('/bulk')
def bulk(payload: Bulk): return invoke(s.bulk, actor(), payload.model_dump())


@router.get('/bulk/history')
def bulk_history(): return invoke(s.bulk_history, actor())


@router.post('/bulk/{identifier}/undo')
def undo(identifier: str, payload: Undo): return invoke(s.undo, actor(), identifier, payload.model_dump())


@router.post('/attachments')
def upload(payload: Attachment): return invoke(s.upload, actor(), payload.model_dump())


@router.post('/attachments/{identifier}/actions')
def attachment_action(identifier: str, payload: AttachmentAction): return invoke(s.attachment_action, actor(), identifier, payload.model_dump())


@router.get('/attachments/{identifier}/download')
def download(identifier: str, request: Request): return invoke(s.download, actor(), identifier, request.headers.get('x-sensitive-access') == 'reveal', request.headers.get('x-access-purpose', ''))


@router.post('/questions')
def question(payload: Question): return invoke(s.question_create, actor(), payload.model_dump())


@router.post('/questions/{identifier}/messages')
def message(identifier: str, payload: Message): return invoke(s.message, actor(), identifier, payload.model_dump())


@router.post('/questions/{identifier}/metadata')
def question_metadata(identifier:str,payload:QuestionUpdate):return invoke(s.question_update,actor(),identifier,payload.model_dump())


@router.post('/questions/{identifier}/actions')
def question_action(identifier: str, payload: QuestionAction): return invoke(s.question_action, actor(), identifier, payload.model_dump())


@router.get('/history/{identifier}')
def history(identifier: str): return invoke(s.history, actor(), identifier)


@router.get('/operations')
def operations(q: str = Query(default='', max_length=200)): return invoke(s.operations, actor(), q)


@router.post('/time')
def time_entry(payload: TimeEntry): return invoke(s.time_save, actor(), payload.model_dump())


@router.post('/budgets')
def budget(payload: Budget): return invoke(s.budget_save, actor(), payload.model_dump())
