"""Fail-closed request boundary shared by every legacy and workflow route."""
import hashlib
import json
import os
import re
import secrets
import tempfile
from functools import lru_cache
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from starlette.responses import JSONResponse
from app.security_context import request_principal
from app.services.packet_service import load_packet

@dataclass
class Settings:
    mode: str='locked'
    environment: str='production'
    origins: tuple=('http://localhost:3000',)
    credentials: dict=field(default_factory=dict)

    @classmethod
    def from_env(cls):
        return cls(os.getenv('WORKPAPER_MODE','locked'),os.getenv('WORKPAPER_ENV','production'),tuple(o for o in os.getenv('WORKPAPER_ORIGINS','http://localhost:3000').split(',') if o),json.loads(os.getenv('WORKPAPER_CREDENTIALS','{}')))

    def validate(self):
        if self.environment not in {'production','development','test'}:raise RuntimeError('Unknown application environment')
        if self.mode not in {'locked','legacy_test','demo','credential'}:raise RuntimeError('Unknown security mode')
        if self.mode=='legacy_test':
            path=Path(os.environ.get('REVIEW_DB_PATH','')).resolve()
            roots=(Path(tempfile.gettempdir()).resolve(),Path('/private/tmp').resolve())
            if self.environment!='test' or not any(path.is_relative_to(root) for root in roots):raise RuntimeError('Legacy profile requires an isolated temporary test database')
        if self.mode=='demo' and self.environment not in {'test','development'}:raise RuntimeError('Demonstration mode is forbidden in production')
        if self.mode=='credential' and (not self.credentials or any(not isinstance(v,str) or len(v)<32 for v in self.credentials.values())):raise RuntimeError('Configured credentials must have at least 32 characters')
        if self.environment=='production' and self.mode!='locked' and (self.mode!='credential' or any(not o.startswith('https://') for o in self.origins)):raise RuntimeError('Production requires credential mode and HTTPS origins')


def sha(value):return hashlib.sha256(value.encode()).hexdigest()

def session_db():
    from app.services.review_service import connect,initialize_database
    initialize_database()
    return connect()


def access(actor,action,resource,purpose,outcome):
    with session_db() as db:
        db.execute('INSERT INTO workflow_access_events(staff_id,action,resource_json,purpose,outcome,request_id,created_at) VALUES(?,?,?,?,?,?,?)',
                   (actor.get('id') if actor else None,action,json.dumps(resource),purpose,outcome,secrets.token_hex(12),datetime.now(timezone.utc).isoformat()))


def new_session(settings,staff_id=None,old=None):
    token=secrets.token_urlsafe(36);csrf=secrets.token_urlsafe(32)
    assurance='demonstration' if settings.mode=='demo' else 'configured_credential'
    with session_db() as db:
        if old:db.execute('UPDATE workflow_sessions SET revoked=1 WHERE token_hash=?',(sha(old),))
        db.execute('INSERT INTO workflow_sessions VALUES(?,?,?,?,?,?,?)',(sha(token),staff_id,sha(csrf),assurance,(datetime.now(timezone.utc)+timedelta(hours=2)).isoformat(),0,sha(json.dumps(settings.credentials,sort_keys=True))))
    return token,csrf


def get_session(token,settings):
    if not token:return None
    with session_db() as db:row=db.execute('SELECT * FROM workflow_sessions WHERE token_hash=?',(sha(token),)).fetchone()
    if not row or row['revoked'] or row['expires_at']<datetime.now(timezone.utc).isoformat() or row['credential_epoch']!=sha(json.dumps(settings.credentials,sort_keys=True)):return None
    return dict(row)


def principal(row):
    if not row or not row['staff_id']:return None
    from app.services.workflow_service import staff
    person=staff(row['staff_id'])
    return {**person,'assurance':row['assurance'],'profile':'strict'}


def secrets_registry():
    values=set();sensitive=re.compile(r'ssn|taxpayer_identification|routing|bank_account|account_number|(?:^|_)pin(?:_|$)|^pin$|^account$|account_(?:id|no)$|efin|ptin|driver.*license|iban',re.I)
    def walk(value,key=''):
        if isinstance(value,dict):
            for k,v in value.items():walk(v,key if 'ptin' in key.lower() else k)
        elif isinstance(value,list):
            for v in value:walk(v,key)
        elif value is not None and sensitive.search(key) and len(str(value))>=4 and any(c.isdigit() for c in str(value)):values.add(str(value))
        elif isinstance(value,str):
            values.update(re.findall(r'\b\d{3}-\d{2}-\d{4}\b',value))
            for match in re.finditer(r'(?:PIN|routing|account(?: number)?|EFIN|PTIN|license|IBAN)\s*[:#=]\s*([A-Z0-9][A-Z0-9 -]{3,30})',value,re.I):
                if any(c.isdigit() for c in match.group(1)):values.add(match.group(1).strip())
    packet=load_packet()
    walk(packet)
    for evidence in packet['extracted_values']:
        if evidence['value_type'] in {'ssn','account_number'} or sensitive.search(evidence['field']):
            for key in ('value','text_as_read'):
                if evidence.get(key) is not None and len(str(evidence[key]))>=4:values.add(str(evidence[key]))
    return sorted(values,key=len,reverse=True),sensitive

_REGISTRY=None

def redact(payload):
    global _REGISTRY
    if _REGISTRY is None:_REGISTRY=secrets_registry()
    values,sensitive=_REGISTRY
    identifiers=re.compile(r'(?<![A-Z0-9])(?:'+'|'.join(re.escape(v) for v in values)+r')(?![A-Z0-9])',re.I)
    @lru_cache(maxsize=32000)
    def text(value):
        value=re.sub(r'\b\d{3}-\d{2}-\d{4}\b',lambda m:re.sub(r'\w','*',m[0]),value)
        value=re.sub(r'(\b(?:IP[ _-]?PIN|PIN|routing|account(?: number)?|EFIN|PTIN|license|IBAN)\b\s*[:#=]?\s*)([A-Z0-9][A-Z0-9-]{3,30})',lambda m:m[1]+re.sub(r'\w','*',m[2]) if any(c.isdigit() for c in m[2]) else m[0],value,flags=re.I)
        value=identifiers.sub(lambda m:re.sub(r'\w','*',m[0]),value)
        return value
    def visit(value,key=''):
        if key=='unprocessed_file_content_base64':return None
        if isinstance(value,dict):
            result={k:visit(v,k) for k,v in value.items()}
            # A masked excerpt is never proof of an exact source-field match.
            if any(isinstance(v,str) and '*' in v for v in result.values()) and any(k in result for k in ('matched_text','field_supported')):
                result['field_supported']=False;result['redacted']=True
            return result
        if isinstance(value,list):return [visit(v,key) for v in value]
        if sensitive.search(key) and value is not None:return text(str(value)) if isinstance(value,str) else None
        if isinstance(value,str):return text(value)
        return value
    return visit(payload)


class SecurityBoundary:
    def __init__(self,app,settings=None):self.app=app;self.settings=settings or Settings.from_env();self.settings.validate()

    async def __call__(self,scope,receive,send):
        if scope['type']!='http':return await self.app(scope,receive,send)
        from starlette.requests import Request
        from app.services.adjustment_service import AdjustmentError
        from app.services.workflow_service import connection,require_access
        settings=self.settings;request=Request(scope,receive);path=request.url.path;actor=None
        async def error(code,message):
            if actor and code in {401,403}:access(actor,'access',{'path':path},'','denied')
            headers={'Cache-Control':'no-store','Pragma':'no-cache','Vary':'Cookie, Origin'}
            if request.headers.get('origin') in settings.origins:headers.update({'Access-Control-Allow-Origin':request.headers['origin'],'Access-Control-Allow-Credentials':'true'})
            await JSONResponse({'detail':message},status_code=code,headers=headers)(scope,receive,send)
        if settings.mode=='legacy_test':
            if (scope.get('client') or ('testclient',))[0] not in {'127.0.0.1','::1','localhost','testclient'}:return await error(403,'Isolated regression profile is local only')
            return await self.app(scope,receive,send)
        if settings.mode=='demo' and (scope.get('client') or ('testclient',))[0] not in {'127.0.0.1','::1','localhost','testclient'}:return await error(403,'Demonstration sessions are local only')
        if path=='/health' or request.method=='OPTIONS':return await self.app(scope,receive,send)
        if path in {'/api/workflow/session','/api/workflow/session/staff'}:
            scope['workflow_settings']=settings
            session_messages=[]
            async def session_send(message):session_messages.append(message)
            await self.app(scope,receive,session_send)
            start=next(m for m in session_messages if m['type']=='http.response.start')
            if start['status']>=400:return await error(start['status'],'Session request rejected; check identity, credential, origin and CSRF token')
            for message in session_messages:
                if message['type']=='http.response.start':
                    message={**message,'headers':[(k,v) for k,v in message['headers'] if k.lower() not in {b'cache-control',b'pragma'}]+[(b'cache-control',b'no-store'),(b'pragma',b'no-cache')]}
                await send(message)
            return
        if settings.mode=='locked':return await error(401,'Access is locked; configure a secure session provider')
        row=get_session(request.cookies.get('mf_session'),settings)
        try:actor=principal(row)
        except AdjustmentError:return await error(401,'Session identity is inactive')
        if not actor:return await error(401,'A workpaper session is required')
        body=b''
        if request.method not in {'GET','HEAD'}:
            if request.headers.get('origin') not in settings.origins or not secrets.compare_digest(sha(request.headers.get('x-csrf-token','')),row['csrf_hash']):return await error(403,'Origin and CSRF validation required')
            # Bound memory before parsing JSON/base64; never trust Content-Length alone.
            body_parts=[];size=0
            async for part in request.stream():
                size+=len(part)
                if size>8*1024*1024:return await error(413,'Request exceeds the 8 MiB intake limit')
                body_parts.append(part)
            body=b''.join(body_parts)
            try:data=json.loads(body) if body else {}
            except ValueError:return await error(400,'Invalid JSON request')
            if not isinstance(data,dict):return await error(422,'A JSON object request is required')
            for key in ('actor_id','verifier_id'):
                if key in data and data[key]!=actor['id']:return await error(403,'Request identity does not match the server session')
            if data.get('actor_role',actor['role'])!=actor['role'] or data.get('actor_name',actor['name']) not in {actor['id'],actor['name']}:return await error(403,'Review identity does not match the server session')
            if actor['role'] not in {'preparer','reviewer','partner','firm_administrator'}:return await error(403,'Read-only staff cannot mutate the workpaper')
        else:data={}
        admin_product=path in {'/api/product/operations','/api/product/budgets','/api/product/bulk/history'} or path=='/api/product/bulk/catalog' and request.query_params.get('operation')=='assign_tasks' or path=='/api/product/bulk' and data.get('operation')=='assign_tasks' or path.startswith('/api/product/bulk/') and path.endswith('/undo')
        if actor['role']=='firm_administrator' and not (admin_product or path.startswith('/api/workflow/') and (path=='/api/workflow/access-history' or not any(x in path for x in ('history','signoff','record','note','sensitive')))):return await error(403,'Administrator has no tax-evidence access')
        limited=False;membership_revision=None
        try:
            with connection() as db:
                require_access(db,actor,manage=actor['role']=='firm_administrator')
                if actor['role']!='firm_administrator':
                    from app.services.workflow_service import membership
                    current_member=membership(db,actor);membership_revision=current_member['revision']
                    limited='*' not in current_member['data']['areas']
                    # Legacy aggregate APIs were designed for an entire engagement.
                    # Do not expose their nested evidence to an area-restricted member.
                    if limited and not path.startswith('/api/product/'):
                        permitted=path in {'/api/overview','/api/workflow/overview','/api/timeline-replay/evidence'} or path.startswith(('/api/workflow/records','/api/workflow/notes')) or path=='/api/workflow/signoff-preview' and request.query_params.get('area')!='engagement' or path=='/api/workflow/signoffs' and data.get('area')!='engagement'
                        if request.method in {'GET','HEAD'} and not permitted:raise AdjustmentError('This aggregate API requires assignment to all engagement areas; use the scoped collaboration workspace',403)
                        if path.startswith(('/api/lifecycle/','/api/change-analysis/')):raise AdjustmentError('An entire-engagement assignment is required',403)
                if not path.startswith(('/api/workflow/','/api/lifecycle/','/api/product/')) and request.method not in {'GET','HEAD'}:
                    from app.services.finding_service import area_for,build_catalog
                    from app.services.workflow_service import independent,entity
                    area=area_for(data.get('target',''))
                    if '/adjustments/' in path:
                        from app.services.adjustment_service import read_one
                        item=read_one(db,path.split('/adjustments/')[1].split('/')[0]);area=area_for(item['payload']['target'])
                    elif path.startswith('/api/reconciliations/') and path.endswith('/adjustment'):
                        from app.services.reconciliation_service import run_reconciliations
                        check_id=path.split('/api/reconciliations/')[1].rsplit('/adjustment',1)[0]
                        check=next((c for c in run_reconciliations()['checks'] if c['id']==check_id),None)
                        area=check['area'] if check else 'engagement'
                    elif 'review' in path or 'reconciliation' in path:
                        identifier=data.get('finding_id') or request.query_params.get('finding_id') or path.split('/reviews/')[-1]
                        finding=next((f for f in build_catalog()['findings'] if f['id']==identifier),None)
                        area=finding['area'] if finding else 'engagement'
                    if area=='other':area='engagement'
                    require_access(db,actor,area)
                    actor['_write_area']=area
                    actor['_independent']=data.get('status')=='resolved' or data.get('action') in {'approve','reject','reverse'}
                    if data.get('status')=='resolved' or data.get('action') in {'approve','reject','reverse'}:independent(db,actor,area)
                    if 'field-verifications' in path and actor['role'] not in {'reviewer','partner'}:raise AdjustmentError('CPA reviewer permission required',403)
        except AdjustmentError as exc:return await error(exc.status_code,exc.message)
        reveal=request.headers.get('x-sensitive-access')=='reveal'
        if reveal:
            if not actor.get('sensitive_data_clearance') or actor['role'] not in {'preparer','reviewer','partner'}:
                access(actor,'reveal',{'path':path},'','denied');return await error(403,'Sensitive-data clearance required')
            purpose=request.headers.get('x-access-purpose','').strip()
            if len(purpose)<8:return await error(400,'A meaningful sensitive-access purpose is required')
            access(actor,'reveal',{'path':path},purpose,'allowed')
        else:access(actor,'masked_read' if request.method=='GET' else 'mutation',{'path':path},'','allowed')
        sent=False
        async def replay():
            nonlocal sent
            if not sent:sent=True;return {'type':'http.request','body':body,'more_body':False}
            return await receive()
        messages=[]
        async def capture(message):messages.append(message)
        context=request_principal.set(actor)
        try:
            try:await self.app(scope,replay if body else receive,capture)
            except Exception:
                return await error(500,'Workpaper request failed; no sensitive request details are logged')
        finally:request_principal.reset(context)
        # An identity switch revokes in-flight responses before delivery.
        if not get_session(request.cookies.get('mf_session'),settings):return await error(401,'Session changed; discard this response')
        if membership_revision is not None:
            try:
                with connection() as db:
                    require_access(db,actor)
                    delivery_member=membership(db,actor)
                    if delivery_member['revision']!=membership_revision:raise AdjustmentError('Assignment changed; discard this response and reload',403)
            except AdjustmentError as exc:return await error(exc.status_code,exc.message)
        start=next((m for m in messages if m['type']=='http.response.start'),None)
        raw=b''.join(m.get('body',b'') for m in messages if m['type']=='http.response.body')
        if not start:return await error(500,'No response')
        if start['status']>=400:access(actor,'request_outcome',{'path':path,'status':start['status']},'','denied' if start['status'] in {401,403} else 'rejected')
        try:
            payload=json.loads(raw)
            if start['status']==422:payload={'detail':'Request validation failed'}
            if limited and path=='/api/overview' and start['status']==200:
                payload={**payload,'household':{'people':[],'limited_scope':True},'scope_notice':'Tax details require an entire-engagement assignment; use scoped workpaper collaboration.'}
            if not reveal:payload=redact(payload)
            raw=json.dumps(payload,separators=(',',':')).encode()
        except (ValueError,TypeError):
            if not reveal:raw=b''
        headers=[(k,v) for k,v in start['headers'] if k.lower() not in {b'content-length',b'cache-control',b'pragma',b'vary'}]
        headers.extend([(b'content-length',str(len(raw)).encode()),(b'cache-control',b'no-store, private'),(b'pragma',b'no-cache'),(b'vary',b'Cookie, Origin'),(b'x-content-type-options',b'nosniff')])
        await send({**start,'headers':headers});await send({'type':'http.response.body','body':raw})
