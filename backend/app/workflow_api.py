from typing import Literal
from fastapi import APIRouter,Request,HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel,ConfigDict,Field
from app.security_context import request_principal
from app.security import new_session,get_session,principal,sha,access
from app.services import workflow_service as service
from app.adjustment_api import invoke
import secrets
from datetime import datetime,timezone

router=APIRouter(prefix='/api/workflow',tags=['Firm workflow'])

class Input(BaseModel):model_config=ConfigDict(extra='forbid')
class SessionInput(Input):staff_id:str|None=None;credential:str=''
class Ownership(Input):owner_id:str;expected_revision:int=Field(ge=1)
class Assignment(Input):
    staff_id:str;responsibility:str;areas:list[str];state:Literal['active','inactive']='active';expected_revision:int=Field(ge=0)
class Policy(Input):expected_revision:int=Field(ge=1);changes:dict;rationale:str=Field(min_length=8,max_length=4000)
class Record(Input):
    id:str|None=None;area:str;record_type:str;title:str=Field(min_length=1,max_length=500);applicability:Literal['unknown','applicable','not_applicable'];answer:str=Field(max_length=8000);authority:str=Field(max_length=4000);refs:list[str]=Field(max_length=100);expected_revision:int=Field(ge=0)
class Action(Input):action:Literal['submit','approve','reopen'];expected_revision:int=Field(ge=1);note:str=Field(min_length=1,max_length=4000)
class Note(Input):
    id:str|None=None;area:str;action:Literal['create','respond','request_resolution','resolve','reopen'];title:str=Field(min_length=1,max_length=500);note:str=Field(min_length=1,max_length=4000);owner_id:str;expected_revision:int=Field(ge=0)
class Signoff(Input):area:str;level:Literal['reviewer','partner'];expected_digest:str;note:str=Field(min_length=1,max_length=4000)
class Revoke(Input):note:str=Field(min_length=1,max_length=4000)
class Task(Input):id:str;state:Literal['open','complete','read'];assignee:str|None=None;due_date:str|None=None;expected_revision:int=Field(ge=1)

def actor():
    value=request_principal.get()
    if not value:raise HTTPException(401,'A strict workpaper session is required')
    return value

def session_response(request,token,csrf):
    settings=request.scope['workflow_settings'];row=get_session(token,settings)
    person=invoke(principal,row)
    response=JSONResponse({'mode':settings.mode,'legacy_profile':False,'staff':person,'csrf_token':csrf,'expires_at':row['expires_at'],'demonstration':settings.mode in {'demo','access'},'legal_signature':False,'identity_assurance':'Verified gateway identity mapped to a demonstration packet staff profile; not legal signature assurance' if settings.mode=='access' else 'Selected demonstration identity; not authenticated identity assurance' if settings.mode=='demo' else 'Possession of configured credential; not legal signature assurance'},headers={'Cache-Control':'no-store','Pragma':'no-cache'})
    response.set_cookie('mf_session',token,httponly=True,secure=settings.environment=='production' or settings.mode=='access',samesite='strict',max_age=max(0,min(1800,int((datetime.fromisoformat(row['expires_at'])-datetime.now(timezone.utc)).total_seconds()))) if settings.mode=='access' else 7200)
    return response

@router.get('/session')
def session(request:Request):
    settings=request.scope.get('workflow_settings')
    if settings is None:return {'legacy_profile':True,'mode':'legacy_test','staff':None}
    if settings.mode=='locked':return JSONResponse({'mode':'locked','staff':None,'detail':'Access is locked; configure WORKPAPER_MODE securely'},headers={'Cache-Control':'no-store'})
    old=request.cookies.get('mf_session');row=get_session(old,settings)
    # Rotate CSRF/session on bootstrap so the CSRF secret is never stored in plaintext.
    identity=request.scope.get('verified_identity')
    token,csrf=new_session(settings,identity['staff_id'] if settings.mode=='access' else (row['staff_id'] if row else None),old,identity)
    if settings.mode=='access':access(principal(get_session(token,settings)),'identity_login',{'subject_hash':identity['subject_hash']},'','allowed')
    return session_response(request,token,csrf)

@router.post('/session')
def select(request:Request,payload:SessionInput):
    settings=request.scope['workflow_settings']
    if settings.mode not in {'demo','credential','access'}:raise HTTPException(403,'Session selection is disabled')
    old=request.cookies.get('mf_session');row=get_session(old,settings)
    if not row or request.headers.get('origin') not in settings.origins or not secrets.compare_digest(sha(request.headers.get('x-csrf-token','')),row['csrf_hash']):raise HTTPException(403,'Origin and CSRF validation required')
    identity=request.scope.get('verified_identity')
    if settings.mode=='access' and (payload.staff_id not in {None,identity['staff_id']} or payload.credential):raise HTTPException(403,'Staff switching is forbidden for this identity')
    person=invoke(service.staff,payload.staff_id) if payload.staff_id else None
    if person and settings.mode=='credential' and not secrets.compare_digest(payload.credential,settings.credentials.get(person['id'],secrets.token_hex(32))):
        access(None,'session',{},'','denied');raise HTTPException(401,'Invalid configured credential')
    token,csrf=new_session(settings,payload.staff_id,old,identity)
    access(person,'session',{'assurance':'verified_access_profile' if settings.mode=='access' else ('demonstration' if settings.mode=='demo' else 'configured_credential')},'','allowed')
    return session_response(request,token,csrf)

@router.get('/session/staff')
def staff_options(request:Request):
    settings=request.scope.get('workflow_settings')
    if not settings or settings.mode not in {'demo','credential','access'}:raise HTTPException(403,'Session selection is disabled')
    return {'staff':[{k:s[k] for k in ('id','name','role','active_from')} for s in service.load_packet()['firm']['staff'] if settings.mode!='access' or s['id']==request.scope['verified_identity']['staff_id']]}

@router.get('/overview')
def overview():return invoke(service.overview,actor())
@router.post('/assignments')
def assign(payload:Assignment):return invoke(service.assign,actor(),payload.model_dump())
@router.post('/policies')
def policy(payload:Policy):return invoke(service.publish_policy,actor(),payload.model_dump())
@router.post('/records')
def record(payload:Record):return invoke(service.save_record,actor(),payload.model_dump())
@router.post('/records/{identifier}/actions')
def record_action(identifier:str,payload:Action):return invoke(service.record_action,actor(),identifier,payload.model_dump())
@router.post('/notes')
def note(payload:Note):return invoke(service.note_action,actor(),payload.model_dump())
@router.get('/signoff-preview')
def preview(area:str,level:Literal['reviewer','partner']='reviewer'):return invoke(service.signoff_preview,actor(),area,level)
@router.post('/signoffs')
def sign(payload:Signoff):return invoke(service.sign,actor(),payload.model_dump())
@router.post('/signoffs/{identifier}/revoke')
def revoke(identifier:str,payload:Revoke):return invoke(service.revoke,actor(),identifier,payload.note)
@router.post('/tasks')
def task(payload:Task):return invoke(service.task_action,actor(),payload.model_dump())
@router.get('/readiness')
def readiness():return invoke(service.readiness,actor())
@router.post('/readiness')
def readiness_record():return invoke(service.readiness,actor(),True)
@router.get('/history')
def history(entity_id:str|None=None):
    person=actor()
    with service.connection() as db:
        service.require_access(db,person)
        import json
        rows=db.execute('SELECT * FROM workflow_events'+(' WHERE entity_id=?' if entity_id else '')+' ORDER BY id',(entity_id,) if entity_id else ())
        return {'events':[{**dict(r),'payload':json.loads(r['payload_json'])} for r in rows]}
@router.get('/access-history')
def access_history():
    person=actor()
    if person['role'] not in {'partner','firm_administrator'}:raise HTTPException(403,'Access audit permission required')
    with service.connection() as db:return {'events':[dict(r) for r in db.execute('SELECT * FROM workflow_access_events ORDER BY id')]}

@router.post("/engagement")
def ownership(payload:Ownership):return invoke(service.transfer_ownership,actor(),payload.model_dump())
