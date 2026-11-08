from typing import Literal,Annotated
from decimal import Decimal
from fastapi import APIRouter,Request
from pydantic import BaseModel,ConfigDict,Field,field_validator
from app.adjustment_api import invoke
from app.workflow_api import actor
from app.services import lifecycle_service as s
router=APIRouter(prefix='/api/lifecycle',tags=['Simulated filing and post-filing'])
class Note(BaseModel):
    model_config=ConfigDict(extra='forbid')
    note:str=Field(min_length=1,max_length=4000)
    @field_validator('note')
    @classmethod
    def nonblank(cls,value):
        if not value.strip():raise ValueError('A documented rationale is required')
        return value.strip()
class Snapshot(Note):
    version:Literal['v1','v2','v3']='v3'
    mode:Literal['demonstration','authoritative']='demonstration'
    refs:list[str]=Field(min_length=1,max_length=100)
    supersedes_id:str|None=None
class Authorization(Note):snapshot_id:str;expires_at:str
class ClientResponse(Note):
    client_id:str;decision:Literal['approve','decline'];refs:list[str]=Field(min_length=1,max_length=100);expected_revision:int=Field(ge=1)
class Filing(Note):snapshot_id:str;jurisdiction:Literal['federal','california'];amendment_id:str|None=None
class FilingAction(Note):
    action:Literal['ready','submit','simulate_reject','simulate_accept','correct']
    expected_revision:int=Field(ge=1)
    replacement_snapshot_id:str|None=None
    replacement_amendment_id:str|None=None
    refs:list[str]=Field(default_factory=list,max_length=100)
class Extension(Note):jurisdiction:Literal['federal','california'];version:Literal['v1','v2','v3']='v2'
class ExtensionAction(Note):action:Literal['approve','simulate_submit','record_packet_event','confirm_external'];expected_revision:int=Field(ge=1);refs:list[str]=Field(default_factory=list,max_length=100)
class Payment(Note):source_ref:str
class Revision(Note):expected_revision:int=Field(ge=1)
class Delivery(Note):package_id:str;client_id:str
class Amendment(Note):
    parent_snapshot_id:str;version:Literal['v1','v2','v3']='v3';refs:list[str]=Field(min_length=1,max_length=100)
class AmendmentAction(Revision):action:Literal['review','approve']
class Notice(Note):
    packet_notice_id:str|None=None;jurisdiction:Literal['federal','california']='federal';title:str='Demonstration notice';source_date:str|None=None;response_due:str|None=None;refs:list[str]=Field(default_factory=list,max_length=100);owner_id:str
class NoticeAction(Revision):
    action:Literal['prepare','submit_review','approve','simulate_dispatch','close_demo'];snapshot_id:str|None=None;refs:list[str]=Field(default_factory=list,max_length=100)
class ImportCarryovers(Note):snapshot_id:str
class CarryoverAction(Revision):
    action:Literal['revise','review'];adjusted_value:Annotated[Decimal,Field(max_digits=16,decimal_places=2,allow_inf_nan=False)]|None=None;refs:list[str]=Field(min_length=1,max_length=100);authority:str=Field(min_length=1,max_length=4000)
class Handoff(Note):snapshot_id:str;owner_id:str
class HandoffAction(Revision):action:Literal['review','handoff']

@router.get('/overview')
def overview():return invoke(s.overview,actor())
@router.post('/snapshots')
def freeze(payload:Snapshot):return invoke(s.finalize,actor(),payload.model_dump())
@router.get('/snapshots/{identifier}')
def snapshot(identifier:str):
    person=actor()
    with s.w.connection() as db:
        invoke(s.access,db,person);return invoke(s.snapshot_public,db,invoke(s.snapshot,db,identifier),True)
@router.get('/snapshots/{original}/compare/{amended}')
def compare(original:str,amended:str):
    person=actor()
    with s.w.connection() as db:invoke(s.access,db,person);return invoke(s.snapshot_compare,db,original,amended)
@router.post('/authorizations')
def authorization(payload:Authorization):return invoke(s.authorize_request,actor(),payload.model_dump())
@router.get('/authorizations/{identifier}/client-review')
def client_review(identifier:str):return invoke(s.client_review,actor(),identifier)
@router.post('/authorizations/{identifier}/responses')
def response(identifier:str,payload:ClientResponse):return invoke(s.client_respond,actor(),identifier,payload.model_dump())
@router.post('/filings')
def filing(payload:Filing):return invoke(s.new_filing,actor(),payload.model_dump())
@router.post('/filings/{identifier}/actions')
def filing_action(identifier:str,payload:FilingAction):return invoke(s.filing_action,actor(),identifier,payload.model_dump())
@router.post('/filings/{identifier}/client-copy')
def client_copy(identifier:str):return invoke(s.client_copy,actor(),identifier)
@router.post('/deliveries')
def delivery(payload:Delivery):return invoke(s.delivery,actor(),payload.model_dump())
@router.get('/packages/{identifier}')
def package(identifier:str,request:Request):return invoke(s.package_view,actor(),identifier,request.headers.get('x-sensitive-access')=='reveal')
@router.post('/extensions')
def extension(payload:Extension):return invoke(s.extension_prepare,actor(),payload.model_dump())
@router.post('/extensions/{identifier}/actions')
def extension_action(identifier:str,payload:ExtensionAction):return invoke(s.extension_action,actor(),identifier,payload.model_dump())
@router.post('/payments')
def payment(payload:Payment):return invoke(s.payment_record,actor(),payload.model_dump())
@router.post('/payments/{identifier}/review')
def payment_review(identifier:str,payload:Revision):return invoke(s.payment_review,actor(),identifier,payload.model_dump())
@router.post('/amendments')
def amendment(payload:Amendment):
    data=payload.model_dump();data['reason']=data.pop('note');return invoke(s.amendment_create,actor(),data)
@router.post('/amendments/{identifier}/actions')
def amendment_action(identifier:str,payload:AmendmentAction):return invoke(s.amendment_action,actor(),identifier,payload.model_dump())
@router.post('/notices')
def notice(payload:Notice):return invoke(s.notice_create,actor(),payload.model_dump())
@router.post('/notices/{identifier}/actions')
def notice_action(identifier:str,payload:NoticeAction):return invoke(s.notice_action,actor(),identifier,payload.model_dump())
@router.post('/notices/{identifier}/package')
def examination(identifier:str):return invoke(s.examination_package,actor(),identifier)
@router.post('/carryovers/import')
def carryover(payload:ImportCarryovers):return invoke(s.carryover_import,actor(),payload.model_dump())
@router.post('/carryovers/{identifier}/actions')
def carryover_action(identifier:str,payload:CarryoverAction):return invoke(s.carryover_action,actor(),identifier,payload.model_dump())
@router.post('/handoffs')
def handoff(payload:Handoff):return invoke(s.handoff_prepare,actor(),payload.model_dump())
@router.post('/handoffs/{identifier}/actions')
def handoff_action(identifier:str,payload:HandoffAction):return invoke(s.handoff_action,actor(),identifier,payload.model_dump())
@router.get('/history')
def history(entity_id:str|None=None):return invoke(s.history,actor(),entity_id)
