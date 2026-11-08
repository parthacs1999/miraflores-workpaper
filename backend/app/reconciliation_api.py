from typing import Literal
from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field
from app.adjustment_api import invoke
from app.services import reconciliation_workflow as workflow
from app.services.reconciliation_service import run_reconciliations
from app.services.adjustment_service import version_data

router=APIRouter(prefix='/api',tags=['CPA reconciliation'])

class Decision(BaseModel):
    model_config=ConfigDict(extra='forbid')
    actor_id:str
    status:Literal['open','in_review','resolved','escalated']
    note:str=Field(min_length=1,max_length=4000)
    authority:str=Field(min_length=1,max_length=4000)
    disposition:Literal['investigating','accepted_as_reported','professional_judgment','unsupported_acknowledged','correction_linked']
    refs:list[str]=Field(default_factory=list,max_length=100)
    adjustment_id:str|None=None

class Correction(BaseModel):
    model_config=ConfigDict(extra='forbid')
    actor_id:str
    note:str=Field(min_length=1,max_length=4000)
    authority:str=Field(min_length=1,max_length=4000)

class Link(BaseModel):
    model_config=ConfigDict(extra='forbid')
    actor_id:str
    adjustment_id:str
    note:str=Field(min_length=1,max_length=4000)
    action:Literal['link','unlink']='link'

@router.get('/reconciliations')
def reconciliations(version:str='v3'):
    invoke(version_data,version)
    return run_reconciliations(version)

@router.get('/unified-findings')
def findings(version:str='v3'):
    return invoke(workflow.dashboard,version)

@router.get('/unified-findings/{identifier:path}/history')
def history(identifier:str,version:str='v3'):
    return invoke(workflow.history,version,identifier)

@router.post('/reconciliation-decision')
def decision(finding_id:str,payload:Decision,version:str='v3'):
    return invoke(workflow.decide,version,finding_id,payload.model_dump())

@router.post('/reconciliation-links')
def link(finding_id:str,payload:Link,version:str='v3'):
    return invoke(workflow.link,version,finding_id,payload.adjustment_id,payload.actor_id,payload.note,payload.action)

@router.post('/reconciliations/{check_id}/adjustment',status_code=201)
def correction(check_id:str,payload:Correction,version:str='v3'):
    return invoke(workflow.create_correction,version,check_id,payload.actor_id,payload.note,payload.authority)
