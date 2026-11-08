"""Separate disposable assignment profile. Never used by the secure hosted launcher."""
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import asyncio
import json
import os
from pathlib import Path
import re
import tempfile
import time
from urllib.parse import urlsplit

from starlette.requests import Request
from starlette.responses import JSONResponse
from app.security import Settings, get_session, access, principal

BASE = Path(__file__).resolve().parents[1]
WARNING = 'NON-PRODUCTION ASSIGNMENT DEMO — review changes and audit history disappear on server restart. Use synthetic evidence only. FILING BLOCKED.'

@dataclass(frozen=True)
class AssignmentProfile:
    settings: Settings
    expires_at: datetime
    seed_digest: str


def configure(env=None):
    env = os.environ if env is None else env
    if env.get('WORKPAPER_PROFILE') != 'assignment-demo' or env.get('WORKPAPER_ENV') != 'production':
        raise ValueError('Explicit non-production assignment profile is required')
    if env.get('WORKPAPER_HOSTED') or env.get('WORKPAPER_MODE') not in {None, 'credential'} or env.get('WORKPAPER_CREDENTIALS') or env.get('WEB_CONCURRENCY', '1') != '1':
        raise ValueError('Assignment configuration cannot override another security profile')
    if env.get('REVIEW_DB_PATH') or env.get('WORKPAPER_DISK_ROOT'):
        raise ValueError('Assignment must create its own disposable database; existing database paths are forbidden')
    expires = datetime.fromisoformat(env.get('WORKPAPER_ASSIGNMENT_EXPIRES_AT', '').replace('Z', '+00:00'))
    if expires.tzinfo is None or not 0 < (expires-datetime.now(timezone.utc)).total_seconds() <= 7*86400:
        raise ValueError('Assignment expiry must be in the next seven days')
    seed = BASE/'assignment_demo'/'seed.json'
    packet = BASE/'data'/'Instructions.json'
    digest = hashlib.sha256(seed.read_bytes()).hexdigest()
    if env.get('WORKPAPER_ASSIGNMENT_SEED_SHA256') != digest or env.get('WORKPAPER_ASSIGNMENT_PACKET_SHA256') != hashlib.sha256(packet.read_bytes()).hexdigest() or env.get('WORKPAPER_ASSIGNMENT_DATA_APPROVAL') != 'reviewed-sanitized-assignment-only':
        raise ValueError('Owner must review and explicitly approve the exact seed and packet before sharing')
    if json.loads(seed.read_text()) != {'format':'miraflores-empty-assignment-seed-v1','description':'NON-PRODUCTION. Empty workflow database created by existing migrations. No historical reviews, uploaded attachments, sessions, approvals or filing snapshots are imported.','import_records':False}:
        raise ValueError('Only the reviewed empty seed format is supported')
    credentials = json.loads(env.get('WORKPAPER_ASSIGNMENT_REVIEWERS', '{}'))
    if not isinstance(credentials, dict) or not credentials or len(credentials)>6 or any(not isinstance(v,str) or not re.fullmatch('[a-f0-9]{64}',v) for v in credentials.values()) or len(set(credentials.values())) != len(credentials):
        raise ValueError('Distinct SHA256 digests of high-entropy per-reviewer tokens are required')
    origin=env.get('WORKPAPER_ORIGINS','')
    u=urlsplit(origin)
    if u.scheme!='https' or not u.hostname or u.username or u.password or u.path or u.query or u.fragment or ',' in origin or '*' in origin:
        raise ValueError('One exact HTTPS frontend origin is required')
    from app.services.packet_service import load_packet
    if not set(credentials).issubset({s['id'] for s in load_packet()['firm']['staff']}):
        raise ValueError('Unknown packet staff ID')
    settings=Settings(mode='credential',environment='production',origins=(origin,),credentials=credentials)
    settings.validate()
    return AssignmentProfile(settings,expires,digest)


def initialize_disposable_database(profile):
    """Every process start gets a new directory; never opens or removes an old database."""
    os.umask(0o077)
    root=Path(tempfile.mkdtemp(prefix='miraflores-assignment-'))
    os.environ['REVIEW_DB_PATH']=str(root/'workpaper.db')
    from app.services.review_service import initialize_database,connect
    initialize_database()
    with connect() as db:
        db.execute('PRAGMA journal_mode=WAL')
        if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or db.execute('PRAGMA foreign_key_check').fetchone():
            raise RuntimeError('Assignment database initialization failed')
    (root/'workpaper.db').chmod(0o600)
    return root


class AssignmentBoundary:
    def __init__(self,app,profile):
        self.app,self.profile=app,profile
        self.attempts=[]
        self.upload_lock=asyncio.Lock()

    async def __call__(self,scope,receive,send):
        if scope['type']=='http' and scope.get('path')=='/api/product/attachments' and scope.get('method')=='POST':
            if self.upload_lock.locked():
                return await JSONResponse({'detail':'Another evidence upload is in progress; retry after it finishes'},status_code=429)(scope,receive,send)
            async with self.upload_lock:return await self.handle(scope,receive,send)
        return await self.handle(scope,receive,send)

    async def handle(self,scope,receive,send):
        if scope['type']!='http':return await self.app(scope,receive,send)
        request=Request(scope,receive); path=request.url.path; settings=self.profile.settings
        async def error(code,message):
            await JSONResponse({'detail':message},status_code=code)(scope,receive,send)
        if path!='/health' and datetime.now(timezone.utc)>=self.profile.expires_at:
            return await error(401,'Temporary assignment access expired; ask the owner for a scheduled review')
        row=get_session(request.cookies.get('mf_session'),settings) if request.cookies.get('mf_session') else None
        if request.headers.get('x-sensitive-access')=='reveal' or (path.startswith('/api/product/attachments/') and path.endswith('/download')):
            person=principal(row) if row else None
            if person:access(person,'assignment_protected_original',{'path':path},'Original access excluded from disposable assignment profile','denied')
            return await error(403 if person else 401,'Protected originals and sensitive reveals are excluded from this assignment profile')
        if path=='/api/workflow/session/staff' and request.method=='GET':
            from app.services.packet_service import load_packet
            # No public packet roster: only configured role aliases needed to enter a token.
            staff=[{'id':s['id'],'name':'Temporary '+s['role'].replace('_',' ')+' profile','role':s['role']} for s in load_packet()['firm']['staff'] if s['id'] in settings.credentials]
            return await JSONResponse({'staff':staff})(scope,receive,send)
        if path=='/api/workflow/session' and request.method=='POST':
            now=time.monotonic();self.attempts=[t for t in self.attempts if t>now-60]
            if len(self.attempts)>=30:return await error(429,'Too many session attempts; wait one minute')
            self.attempts.append(now)
            body=bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body)>16384:return await error(413,'Session request too large')
            try:
                data=json.loads(body)
                if not isinstance(data,dict):raise ValueError()
                if row and row['staff_id'] and data.get('staff_id') not in {None,row['staff_id']}:
                    person=principal(row)
                    access(person,'assignment_identity_switch',{},'','denied')
                    return await error(403,'End this session before using a separately authorized reviewer profile')
                token=data.get('credential','')
                if not isinstance(token,str) or len(token)>256:raise ValueError()
                # Existing constant-time credential checks compare a digest; raw tokens are never persisted.
                data['credential']=hashlib.sha256(token.encode()).hexdigest() if re.fullmatch(r'[A-Za-z0-9_-]{43,128}',token) else 'invalid'
                body=json.dumps(data).encode()
            except (ValueError,TypeError):return await error(422,'Invalid temporary session request')
            original=receive;sent=False
            async def replay():
                nonlocal sent
                if not sent:sent=True;return {'type':'http.request','body':body,'more_body':False}
                return await original()
            receive=replay
        if path=='/api/workflow/session':
            messages=[]
            async def capture(message):messages.append(message)
            await self.app(scope,receive,capture)
            start=next((m for m in messages if m['type']=='http.response.start'),None)
            if start and start['status']==200:
                body=json.loads(b''.join(m.get('body',b'') for m in messages if m['type']=='http.response.body'))
                expiry=min(datetime.fromisoformat(body['expires_at']),self.profile.expires_at)
                body.update(assignment_demo=True,demonstration=True,state_warning=WARNING,expires_at=expiry.isoformat(),identity_assurance='Restricted temporary bearer-token access; recipient identity is not independently authenticated; no legal signatures')
                raw=json.dumps(body).encode()
                headers=[(k,v) for k,v in start['headers'] if k.lower()!=b'content-length']
                # Cookie lifetime cannot exceed the assignment deadline; DB expiry is also enforced at the boundary.
                max_age=max(0,int((expiry-datetime.now(timezone.utc)).total_seconds()))
                headers=[(k,re.sub(rb'Max-Age=\d+',b'Max-Age='+str(max_age).encode(),v) if k.lower()==b'set-cookie' else v) for k,v in headers]
                await send({**start,'headers':headers+[(b'content-length',str(len(raw)).encode())]})
                return await send({'type':'http.response.body','body':raw})
            for message in messages:await send(message)
            return
        return await self.app(scope,receive,send)


def create_assignment_app(profile):
    from app.main import create_app
    from app.hosting_headers import HostedSecurityHeaders
    return HostedSecurityHeaders(AssignmentBoundary(create_app(profile.settings),profile))
