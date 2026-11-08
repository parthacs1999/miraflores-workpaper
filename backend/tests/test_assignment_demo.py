"""Isolated disposable assignment security and restart regressions."""
from datetime import datetime,timezone,timedelta
from dataclasses import replace
import hashlib,json,os,secrets,sqlite3
import pytest
from fastapi.testclient import TestClient
from app.assignment_demo import BASE,configure,initialize_disposable_database,create_assignment_app

def configuration():
    tokens={s:secrets.token_urlsafe(32) for s in ('st-01','st-02','st-03','st-05')}
    env={'WORKPAPER_PROFILE':'assignment-demo','WORKPAPER_ENV':'production','WORKPAPER_ORIGINS':'https://assignment.vercel.app','WORKPAPER_ASSIGNMENT_EXPIRES_AT':(datetime.now(timezone.utc)+timedelta(hours=4)).isoformat(),'WORKPAPER_ASSIGNMENT_REVIEWERS':json.dumps({s:hashlib.sha256(t.encode()).hexdigest() for s,t in tokens.items()}),'WORKPAPER_ASSIGNMENT_SEED_SHA256':hashlib.sha256((BASE/'assignment_demo/seed.json').read_bytes()).hexdigest(),'WORKPAPER_ASSIGNMENT_PACKET_SHA256':hashlib.sha256((BASE/'data/Instructions.json').read_bytes()).hexdigest(),'WORKPAPER_ASSIGNMENT_DATA_APPROVAL':'reviewed-sanitized-assignment-only'}
    return env,tokens

@pytest.fixture
def assignment(monkeypatch):
    env,tokens=configuration();profile=configure(env)
    old=os.environ.get('REVIEW_DB_PATH');monkeypatch.setenv('REVIEW_DB_PATH',old or '')
    root=initialize_disposable_database(profile)
    monkeypatch.setenv('REVIEW_DB_PATH',str(root/'workpaper.db'))
    client=TestClient(create_assignment_app(profile),base_url='https://assignment.vercel.app')
    yield client,profile,tokens,root
    client.close()

def login(client,tokens,staff='st-01'):
    bootstrap=client.get('/api/workflow/session').json()
    headers={'Origin':'https://assignment.vercel.app','X-CSRF-Token':bootstrap['csrf_token']}
    response=client.post('/api/workflow/session',headers=headers,json={'staff_id':staff,'credential':tokens[staff]})
    assert response.status_code==200,response.text
    return {'Origin':headers['Origin'],'X-CSRF-Token':response.json()['csrf_token']}

@pytest.mark.parametrize('change',[{'WORKPAPER_PROFILE':'hosted'},{'WORKPAPER_HOSTED':'1'},{'WORKPAPER_ENV':'development'},{'WORKPAPER_MODE':'demo'},{'WORKPAPER_CREDENTIALS':'{}'},{'WEB_CONCURRENCY':'2'},{'REVIEW_DB_PATH':'/do-not-touch/history.db'},{'WORKPAPER_DISK_ROOT':'/var/data'},{'WORKPAPER_ASSIGNMENT_DATA_APPROVAL':'pending'},{'WORKPAPER_ASSIGNMENT_SEED_SHA256':'0'*64},{'WORKPAPER_ASSIGNMENT_PACKET_SHA256':'0'*64},{'WORKPAPER_ASSIGNMENT_EXPIRES_AT':'2000-01-01T00:00:00Z'},{'WORKPAPER_ASSIGNMENT_EXPIRES_AT':(datetime.now(timezone.utc)+timedelta(days=8)).isoformat()},{'WORKPAPER_ASSIGNMENT_REVIEWERS':'{}'},{'WORKPAPER_ASSIGNMENT_REVIEWERS':json.dumps({'st-01':'weak'})},{'WORKPAPER_ASSIGNMENT_REVIEWERS':json.dumps({'not-staff':'a'*64})},{'WORKPAPER_ORIGINS':'http://localhost:3000'},{'WORKPAPER_ORIGINS':'https://*.vercel.app'},{'WORKPAPER_ORIGINS':'https://assignment.vercel.app/'}])
def test_preflight_fails_closed(change):
    env,_=configuration();env.update(change)
    with pytest.raises((ValueError,RuntimeError)):configure(env)

def test_anonymous_and_invalid_sessions_cannot_read_packet(assignment):
    client,_,_,_=assignment
    for path in ('/api/overview','/api/documents','/api/workflow/history','/api/product/attachments','/docs'):assert client.get(path).status_code==401
    assert client.get('/health').status_code==200
    staff=client.get('/api/workflow/session/staff').json()['staff']
    assert all(s['name'].startswith('Temporary') for s in staff)
    assert {s['id'] for s in staff}=={'st-01','st-02','st-03','st-05'}
    client.cookies.set('mf_session','invalid');assert client.get('/api/overview').status_code==401

def test_token_login_secure_cookie_expiry_and_no_hash_bypass(assignment):
    client,profile,tokens,root=assignment
    initial=client.get('/api/workflow/session').json();headers={'Origin':'https://assignment.vercel.app','X-CSRF-Token':initial['csrf_token']}
    for value in ('forged',profile.settings.credentials['st-01']):assert client.post('/api/workflow/session',headers=headers,json={'staff_id':'st-01','credential':value}).status_code==401
    response=client.post('/api/workflow/session',headers=headers,json={'staff_id':'st-01','credential':tokens['st-01']});assert response.status_code==200
    assert all(s in response.headers['set-cookie'].lower() for s in ('secure','httponly','samesite=strict'))
    data=response.json();assert data['assignment_demo'] and not data['legal_signature']
    assert datetime.fromisoformat(data['expires_at'])<=profile.expires_at
    assert tokens['st-01'].encode() not in (root/'workpaper.db').read_bytes()
    assert client.get('/api/overview').status_code==200
    assert client.post('/api/workflow/session',headers={'Origin':headers['Origin'],'X-CSRF-Token':data['csrf_token']},json={'staff_id':'st-03','credential':tokens['st-03']}).status_code==403

def test_csrf_roles_masking_private_originals_and_filing_blockers(assignment):
    client,_,tokens,_=assignment;headers=login(client,tokens)
    assert client.post('/api/workflow/notes',json={}).status_code==403
    assert client.post('/api/workflow/notes',headers={**headers,'Origin':'https://evil.example'},json={}).status_code==403
    assert client.post('/api/workflow/assignments',headers=headers,json={'staff_id':'st-01','responsibility':'preparation','areas':['*'],'state':'active','expected_revision':1}).status_code==403
    document=client.get('/api/documents/D71');assert document.status_code==200 and '666-41-2287' not in document.text
    assert client.get('/api/documents/D71',headers={'X-Sensitive-Access':'reveal','X-Access-Purpose':'Try protected source original'}).status_code==403
    assert client.get('/api/product/attachments/missing/download').status_code==403
    assert not client.get('/api/workflow/readiness').json()['filing_ready']
    assert 'no-store' in document.headers['cache-control']

def test_profile_expiry_rejects_valid_cookie_and_new_logins(assignment):
    client,profile,tokens,_=assignment;login(client,tokens)
    expired=TestClient(create_assignment_app(replace(profile,expires_at=datetime.now(timezone.utc)-timedelta(seconds=1))),base_url='https://assignment.vercel.app');expired.cookies.update(client.cookies)
    for path in ('/api/overview','/api/workflow/session','/api/workflow/session/staff'):assert expired.get(path).status_code==401
    assert expired.get('/health').status_code==200

def test_audit_is_append_only_and_restart_never_imports_history(assignment,monkeypatch):
    client,profile,tokens,old_root=assignment;login(client,tokens)
    with sqlite3.connect(old_root/'workpaper.db') as db:
        assert db.execute('SELECT count(*) FROM workflow_access_events').fetchone()[0]>0
        with pytest.raises(sqlite3.IntegrityError):db.execute('DELETE FROM workflow_access_events')
    old_cookie=client.cookies.get('mf_session');new_root=initialize_disposable_database(profile)
    monkeypatch.setenv('REVIEW_DB_PATH',str(new_root/'workpaper.db'))
    assert new_root!=old_root and (old_root/'workpaper.db').is_file()
    with sqlite3.connect(new_root/'workpaper.db') as db:
        assert db.execute('SELECT count(*) FROM workflow_sessions').fetchone()[0]==0
        assert db.execute('SELECT count(*) FROM product_files').fetchone()[0]==0
    fresh=TestClient(create_assignment_app(profile),base_url='https://assignment.vercel.app');fresh.cookies.set('mf_session',old_cookie)
    assert fresh.get('/api/overview').status_code==401

def test_login_body_limit_and_rate_limit(assignment):
    client,_,_,_=assignment
    assert client.post('/api/workflow/session',content='x'*16385).status_code==413
    for _ in range(29):client.post('/api/workflow/session',json={})
    assert client.post('/api/workflow/session',json={}).status_code==429

def test_concurrent_uploads_fail_fast_without_blocking_long_poll_or_health(assignment):
    import asyncio,httpx
    from app.assignment_demo import AssignmentBoundary
    _,profile,_,_=assignment
    async def exercise():
        entered=asyncio.Event();release=asyncio.Event()
        async def upstream(scope,receive,send):
            if scope['path']=='/api/product/attachments':entered.set();await release.wait()
            from starlette.responses import JSONResponse
            await JSONResponse({'ok':True})(scope,receive,send)
        boundary=AssignmentBoundary(upstream,profile)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=boundary),base_url='https://assignment.vercel.app') as client:
            first=asyncio.create_task(client.post('/api/product/attachments',json={}))
            await entered.wait()
            assert (await client.post('/api/product/attachments',json={})).status_code==429
            assert (await client.get('/health')).status_code==200
            release.set();assert (await first).status_code==200
    asyncio.run(exercise())
