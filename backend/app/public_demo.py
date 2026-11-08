"""Explicit public fictional-data sandbox. Does not enable anonymous secure-mode access."""
import asyncio
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import sqlite3
import tempfile
import time
from urllib.parse import urlsplit

from starlette.requests import Request
from starlette.responses import JSONResponse
from app.security import Settings, sha, get_session, principal, access, redact
from app.security_context import request_database_path

PACKET_SHA256='ee01f8508bd2fd9854754b82fd9c4a055bdc55e2778a132002a25381c412ad19'
STAFF=('st-01','st-02','st-03')
NOTICE='PUBLIC DEMO — fictional packet, simulated roles and approvals; private temporary sandbox. Changes disappear on expiry or server restart. FILING BLOCKED.'
WRITE_PATHS=(r'/api/adjustments(?:/[^/]+/(?:revisions|actions))?',r'/api/reviews(?:/.+)?',r'/api/field-verifications/[^/]+',r'/api/reconciliation-(?:decision|links)',r'/api/reconciliations/[^/]+/adjustment',r'/api/workflow/(?:records(?:/[^/]+/actions)?|notes|signoffs(?:/[^/]+/revoke)?|tasks)',r'/api/(?:what-if/(?:compare|analyses)|change-impact)',r'/api/product/checkpoint')


def configuration(env=None):
    env=os.environ if env is None else env
    if env.get('WORKPAPER_PROFILE')!='public-demo':raise ValueError('Explicit public-demo profile required')
    if any(env.get(k) for k in ('WORKPAPER_HOSTED','REVIEW_DB_PATH','WORKPAPER_DISK_ROOT','WORKPAPER_CREDENTIALS','WORKPAPER_ACCESS_ISSUER','WORKPAPER_ASSIGNMENT_REVIEWERS')) or env.get('WORKPAPER_MODE') not in {None,'locked'} or env.get('WEB_CONCURRENCY','1')!='1':
        raise ValueError('Public demo cannot inherit secure storage or identity settings')
    origin=env.get('WORKPAPER_ORIGINS','');u=urlsplit(origin)
    if u.scheme!='https' or not u.hostname or u.username or u.password or u.path or u.query or u.fragment or ',' in origin or '*' in origin:raise ValueError('One exact HTTPS frontend origin required')
    packet=Path(__file__).resolve().parents[1]/'data'/'Instructions.json'
    if hashlib.sha256(packet.read_bytes()).hexdigest()!=PACKET_SHA256:raise ValueError('Only the original verified fictional packet is permitted')
    # Internal, unexposed guard configuration. Visitor roles are created by this boundary,
    # never by the secure credential-selection endpoint or an external credential fallback.
    return Settings(mode='credential',environment='production',origins=(origin,),credentials={s:secrets.token_urlsafe(48) for s in STAFF})


@contextmanager
def database_scope(path):
    token=request_database_path.set(path)
    try:yield
    finally:request_database_path.reset(token)


@dataclass
class Sandbox:
    directory: Path
    expires: float
    active: int=0
    requests: list=field(default_factory=list)
    mutations: int=0
    lock: asyncio.Lock=field(default_factory=asyncio.Lock)

    @property
    def path(self):return self.directory/'workpaper.db'


class SandboxStore:
    def __init__(self,max_visitors=24,lifetime=3600):
        self.root=Path(tempfile.mkdtemp(prefix='miraflores-public-'))
        self.root.chmod(0o700)
        self.slots={};self.max_visitors=max_visitors;self.lifetime=lifetime
        self.template=self.root/'fictional-baseline.db'
        with database_scope(self.template):
            from app.services.review_service import initialize_database
            from app.services.workflow_service import connection
            initialize_database()
            with connection():pass
        self.template.chmod(0o600)

    def acquire(self,cookie):
        now=time.time()
        for key,slot in list(self.slots.items()):
            if slot.expires<=now and not slot.active:
                shutil.rmtree(slot.directory);del self.slots[key]
        key=sha(cookie) if cookie and re.fullmatch(r'[A-Za-z0-9_-]{43}',cookie) else None
        slot=self.slots.get(key)
        if slot and slot.expires<=now:return None,None
        if slot:return slot,None
        if len(self.slots)>=self.max_visitors:return None,None
        token=secrets.token_urlsafe(32);directory=self.root/secrets.token_hex(16);directory.mkdir(mode=0o700)
        path=directory/'workpaper.db'
        # Copy only a baseline created by this process, never a historical review database.
        with sqlite3.connect(self.template) as source,sqlite3.connect(path) as target:source.backup(target)
        path.chmod(0o600);slot=Sandbox(directory,now+self.lifetime)
        self.slots[sha(token)]=slot
        return slot,token


def response_session(settings,slot,staff_id,old=None):
    token=secrets.token_urlsafe(36);csrf=secrets.token_urlsafe(32)
    expiry=datetime.fromtimestamp(slot.expires,timezone.utc)
    from app.security import session_db
    from app.access_identity import configuration_epoch
    with session_db() as db:
        db.execute('BEGIN IMMEDIATE')
        if old:db.execute('UPDATE workflow_sessions SET revoked=1 WHERE token_hash=?',(sha(old),))
        db.execute('INSERT INTO workflow_sessions VALUES(?,?,?,?,?,?,?)',(sha(token),staff_id,sha(csrf),'public_simulation',expiry.isoformat(),0,configuration_epoch(settings)))
        db.commit()
    row=get_session(token,settings)
    return token,csrf,principal(row)


class PublicDemoBoundary:
    def __init__(self,app,settings,store):self.app,self.settings,self.store=app,settings,store

    async def __call__(self,scope,receive,send):
        if scope['type']!='http':return await self.app(scope,receive,send)
        request=Request(scope,receive);path=request.url.path;method=request.method
        if path=='/health':return await self.app(scope,receive,send)
        if method=='OPTIONS':return await self.app(scope,receive,send)
        async def error(code,detail):await JSONResponse({'detail':detail,'public_demo':True},status_code=code)(scope,receive,send)
        if path=='/api/workflow/session' and method not in {'GET','POST'}:return await error(405,'Use GET to explore or POST to switch a simulated role')
        if path=='/api/workflow/session/staff' and method!='GET':return await error(405,'Demo role list is read-only')
        # Default-deny mutations, including future APIs. No originals or intake of private files.
        if request.headers.get('x-sensitive-access')=='reveal' or path.startswith('/api/product/attachments') or path.startswith('/api/lifecycle/packages/'):
            return await error(403,'Public demo: uploads, protected originals and sensitive reveals are unavailable')
        if method not in {'GET','HEAD'} and path not in {'/api/workflow/session','/api/public-demo/reset'} and not (method in {'POST','PATCH'} and any(re.fullmatch(p,path) for p in WRITE_PATHS)):
            return await error(403,'Public demo: filing, communications, administrative changes and unsupported writes are disabled')
        if path in {'/docs','/redoc','/openapi.json'}:return await error(404,'Not available in public demo')
        # Unknown/expired capabilities never select a caller-supplied database path.
        slot,visitor_cookie=self.store.acquire(request.cookies.get('mf_demo'))
        if not slot:return await error(503,'Public demo is at temporary capacity; retry later')
        slot.active+=1
        try:
            with database_scope(slot.path):
                size=sum(p.stat().st_size for p in slot.directory.iterdir() if p.is_file())
                if size>8*1024*1024:return await error(507,'Demo sandbox limit reached; clear site cookies to start a new sandbox after capacity becomes available')
                now=time.monotonic();slot.requests[:]=[t for t in slot.requests if t>now-60]
                if len(slot.requests)>=180:return await error(429,'Demo request limit reached; wait one minute')
                slot.requests.append(now)
                if method not in {'GET','HEAD'}:
                    slot.mutations+=1
                    if slot.mutations>150:return await error(429,'Demo action limit reached for this sandbox')
                cookie=request.cookies.get('mf_session');row=get_session(cookie,self.settings)
                new_cookie=None
                if path=='/api/public-demo/reset':
                    if method!='POST' or not row or request.headers.get('origin') not in self.settings.origins or not secrets.compare_digest(sha(request.headers.get('x-csrf-token','')),row['csrf_hash']):return await error(403,'Origin and CSRF validation required')
                    slot.expires=time.time()
                    response=JSONResponse({'reset':True,'public_demo':True})
                    response.delete_cookie('mf_demo',secure=True,httponly=True,samesite='strict')
                    response.delete_cookie('mf_session',secure=True,httponly=True,samesite='strict')
                    return await response(scope,receive,send)
                if method=='POST' and path=='/api/workflow/session':
                    chunks=[];size=0
                    async for chunk in request.stream():
                        size+=len(chunk)
                        if size>16384:return await error(413,'Demo role request too large')
                        chunks.append(chunk)
                    if not row or request.headers.get('origin') not in self.settings.origins or not secrets.compare_digest(sha(request.headers.get('x-csrf-token','')),row['csrf_hash']):return await error(403,'Origin and CSRF validation required')
                    try:
                        data=json.loads(b''.join(chunks))
                        if not isinstance(data,dict) or set(data)-{'staff_id','credential'} or data.get('credential'):raise ValueError()
                        selected=data.get('staff_id')
                        if selected not in (*STAFF,None):raise ValueError()
                    except (ValueError,TypeError):return await error(403,'Only the three simulated tax-practice roles are available')
                else:selected=row['staff_id'] if row else 'st-01'
                if path=='/api/workflow/session' or (not row and not cookie and method in {'GET','HEAD'}):
                    async with slot.lock:
                        new_cookie,csrf,person=response_session(self.settings,slot,selected,cookie)
                    cookie=new_cookie
                elif not row:return await error(401,'Demo sandbox or session expired; reload to start a new simulation')
                async def out(message):
                    if message['type']=='http.response.start':
                        # Each capability is host-only and never exposed to application JavaScript.
                        headers=list(message['headers']);age=max(0,int(slot.expires-time.time()))
                        for name,value in (('mf_demo',visitor_cookie),('mf_session',new_cookie)):
                            if value:headers.append((b'set-cookie',f'{name}={value}; HttpOnly; Secure; SameSite=Strict; Path=/; Max-Age={age}'.encode()))
                        message={**message,'headers':headers}
                    await send(message)
                if path=='/api/workflow/session':
                    access(person,'public_role_simulation',{'staff_id':selected},'Simulated visitor role; no authenticated identity or legal approval','allowed')
                    return await JSONResponse({'mode':'public_demo','public_demo':True,'staff':redact(person),'csrf_token':csrf,'expires_at':datetime.fromtimestamp(slot.expires,timezone.utc).isoformat(),'legacy_profile':False,'demonstration':True,'legal_signature':False,'identity_assurance':'Simulated role, not authenticated identity','state_warning':NOTICE})(scope,receive,out)
                if path=='/api/workflow/session/staff':
                    from app.services.packet_service import load_packet
                    return await JSONResponse({'staff':[{k:s[k] for k in ('id','name','role')} for s in load_packet()['firm']['staff'] if s['id'] in STAFF]})(scope,receive,out)
                # Inject the newly bootstrapped session only into this request, not shared process state.
                headers=[(k,v) for k,v in scope['headers'] if k.lower()!=b'cookie']
                cookies={**request.cookies,'mf_session':cookie}
                headers.append((b'cookie','; '.join(k+'='+v for k,v in cookies.items()).encode()))
                await self.app({**scope,'headers':headers},receive,out)
        except (sqlite3.Error,OSError):return await error(503,'Demo storage is temporarily unavailable; retry or reload')
        finally:slot.active-=1


def create_public_app(settings,store):
    from app.main import create_app
    from app.hosting_headers import HostedSecurityHeaders
    return HostedSecurityHeaders(PublicDemoBoundary(create_app(settings),settings,store))
