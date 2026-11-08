"""Public fictional-data profile: no login, isolated state, default-deny unsafe actions."""
import asyncio
import hashlib
import sqlite3
import time
import pytest
from fastapi.testclient import TestClient
from app.public_demo import configuration,SandboxStore,create_public_app,database_scope,PACKET_SHA256


def settings():return configuration({'WORKPAPER_PROFILE':'public-demo','WORKPAPER_ORIGINS':'https://public.vercel.app'})

@pytest.fixture
def public():
    store=SandboxStore();app=create_public_app(settings(),store)
    yield app,store
    import shutil
    shutil.rmtree(store.root)


def visitor(app):return TestClient(app,base_url='https://public.vercel.app')
def bootstrap(client):
    r=client.get('/api/workflow/session');assert r.status_code==200,r.text
    data=r.json();return {'Origin':'https://public.vercel.app','X-CSRF-Token':data['csrf_token']},data

def role(client,headers,staff):
    r=client.post('/api/workflow/session',headers=headers,json={'staff_id':staff,'credential':''});assert r.status_code==200,r.text
    return {**headers,'X-CSRF-Token':r.json()['csrf_token']}

def note(client,headers,title):
    return client.post('/api/workflow/notes',headers=headers,json={'area':'business','action':'create','title':title,'note':'Private fictional investigation note for this sandbox','owner_id':'st-01','expected_revision':0})


def test_anonymous_visitor_explores_immediately_without_login(public):
    app,_=public;client=visitor(app)
    response=client.get('/api/overview');assert response.status_code==200
    for path in ('/api/documents','/api/reconciliations','/api/version-comparison','/api/workflow/overview'):
        assert client.get(path).status_code==200,path
    _,data=bootstrap(client)
    assert data['public_demo'] and data['demonstration'] and not data['legal_signature']
    assert data['staff']['id']=='st-01' and data['staff']['assurance']=='public_simulation'
    assert 'no-store' in response.headers['cache-control']
    cookies=response.headers.get_list('set-cookie');assert len(cookies)==2
    assert all(all(flag in c.lower() for flag in ('secure','httponly','samesite=strict')) for c in cookies)


def test_two_visitors_have_private_notes_audits_and_sessions(public):
    app,store=public;a,b=visitor(app),visitor(app)
    ah,_=bootstrap(a);bh,_=bootstrap(b)
    created=note(a,ah,'A sandbox only');assert created.status_code==200,created.text
    assert 'A sandbox only' in a.get('/api/workflow/overview').text
    assert 'A sandbox only' not in b.get('/api/workflow/overview').text
    assert 'A sandbox only' not in b.get('/api/workflow/history').text
    # A session cookie alone has no authority in another visitor's database.
    b.cookies.set('mf_session',a.cookies.get('mf_session'),domain='public.vercel.app',path='/')
    assert b.get('/api/overview').status_code==401
    assert len(store.slots)==2
    assert len({slot.path for slot in store.slots.values()})==2


def test_simulated_roles_preserve_approval_rules_and_reject_administrator(public):
    app,_=public;c=visitor(app);headers,data=bootstrap(c)
    roster=c.get('/api/workflow/session/staff').json()['staff'];assert {s['id'] for s in roster}=={'st-01','st-02','st-03'}
    assert c.post('/api/workflow/session',headers=headers,json={'staff_id':'st-05'}).status_code==403
    headers=role(c,headers,'st-02');assert c.get('/api/workflow/session').json()['staff']['role']=='reviewer'
    headers,_=bootstrap(c);headers=role(c,headers,'st-03')
    assert c.get('/api/workflow/session').json()['staff']['role']=='partner'
    # Mode selection cannot become authenticated identity assurance.
    assert c.post('/api/workflow/session',headers=headers,json={'staff_id':'st-01','credential':'any-password'}).status_code==403


@pytest.mark.parametrize('method,path',[
 ('post','/api/lifecycle/filings'),('post','/api/lifecycle/deliveries'),('post','/api/lifecycle/payments'),
 ('post','/api/lifecycle/authorizations'),('post','/api/lifecycle/notices'),('post','/api/workflow/policies'),
 ('post','/api/workflow/assignments'),('post','/api/workflow/engagement'),('post','/api/product/attachments'),
 ('post','/api/product/questions'),('post','/api/product/budgets'),('post','/api/future-unsafe-route'),
 ('get','/api/product/attachments/private/download'),('get','/api/lifecycle/packages/private')])
def test_unsafe_actions_and_private_files_are_blocked(public,method,path):
    app,_=public;c=visitor(app);headers,_=bootstrap(c)
    assert getattr(c,method)(path,headers=headers,**({'json':{}} if method!='get' else {})).status_code==403
    assert not c.get('/api/workflow/readiness').json()['filing_ready']


def test_csrf_masking_reset_and_session_methods(public):
    app,_=public;c=visitor(app);headers,_=bootstrap(c)
    assert note(c,{},'No CSRF').status_code==403
    assert note(c,{**headers,'Origin':'https://evil.example'},'Wrong Origin').status_code==403
    assert c.delete('/api/workflow/session').status_code==405
    assert c.get('/api/documents/D71',headers={'X-Sensitive-Access':'reveal'}).status_code==403
    assert '666-41-2287' not in c.get('/api/documents/D71').text
    assert note(c,headers,'Reset this private note').status_code==200
    assert c.post('/api/public-demo/reset',headers={}).status_code==403
    assert c.post('/api/public-demo/reset',headers=headers,json={}).status_code==200
    bootstrap(c)
    assert 'Reset this private note' not in c.get('/api/workflow/overview').text


def test_concurrent_requests_keep_database_and_policy_context_isolated(public):
    import httpx
    app,store=public
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='https://public.vercel.app') as a,httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='https://public.vercel.app') as b:
            responses=await asyncio.gather(a.get('/api/workflow/session'),b.get('/api/workflow/session'))
            def h(r):return {'Origin':'https://public.vercel.app','X-CSRF-Token':r.json()['csrf_token']}
            async def save(c,headers,title):
                return await c.post('/api/workflow/notes',headers=headers,json={'area':'business','action':'create','title':title,'note':'Concurrent synthetic note','owner_id':'st-01','expected_revision':0})
            results=await asyncio.gather(save(a,h(responses[0]),'First isolated visitor'),save(b,h(responses[1]),'Second isolated visitor'))
            assert all(r.status_code==200 for r in results)
            ar,br=await asyncio.gather(a.get('/api/workflow/overview'),b.get('/api/workflow/overview'))
            assert 'First isolated visitor' in ar.text and 'Second isolated visitor' not in ar.text
            assert 'Second isolated visitor' in br.text and 'First isolated visitor' not in br.text
    asyncio.run(run())
    assert len(store.slots)==2
    from app.services.firm_policy import current
    from app.security_context import request_principal
    from app.services.review_service import database_path
    # Exercise the formerly direct SQLite policy reader under each scoped path.
    for slot in store.slots.values():
        with database_scope(slot.path):
            assert database_path()==slot.path
            token=request_principal.set({'profile':'strict'})
            try:assert current()['partner_threshold']=='1000'
            finally:request_principal.reset(token)
    from app.security_context import request_database_path
    assert request_database_path.get() is None


def test_expiry_capacity_path_traversal_and_fresh_seed(public):
    app,store=public;store.max_visitors=1;c=visitor(app);bootstrap(c)
    other=visitor(app);assert other.get('/api/overview').status_code==503
    other.cookies.set('mf_demo','../../backend/data/reviews.db')
    assert other.get('/api/overview').status_code==503
    slot=next(iter(store.slots.values()));old=slot.path;slot.expires=time.time()-1
    assert other.get('/api/overview').status_code==200
    assert not old.exists()
    with database_scope(next(iter(store.slots.values())).path):
        from app.services.review_service import connect
        with connect() as db:
            assert db.execute('SELECT count(*) FROM product_files').fetchone()[0]==0
            with pytest.raises(sqlite3.IntegrityError):db.execute('DELETE FROM workflow_access_events')


@pytest.mark.parametrize('changes',[{'WORKPAPER_PROFILE':'assignment-demo'},{'WORKPAPER_HOSTED':'1'},{'REVIEW_DB_PATH':'/do-not-touch.db'},{'WORKPAPER_DISK_ROOT':'/var/data'},{'WORKPAPER_MODE':'demo'},{'WORKPAPER_CREDENTIALS':'{}'},{'WORKPAPER_ACCESS_ISSUER':'https://example.com'},{'WORKPAPER_ASSIGNMENT_REVIEWERS':'{}'},{'WEB_CONCURRENCY':'2'},{'WORKPAPER_ORIGINS':'http://public.vercel.app'},{'WORKPAPER_ORIGINS':'https://*.vercel.app'}])
def test_public_profile_cannot_override_secure_configuration(changes):
    with pytest.raises(ValueError):configuration({'WORKPAPER_PROFILE':'public-demo','WORKPAPER_ORIGINS':'https://public.vercel.app',**changes})


def test_packet_remains_original_fictional_and_no_real_seed_is_used(public):
    from app.services.packet_service import DATA_PATH,load_packet
    assert hashlib.sha256(DATA_PATH.read_bytes()).hexdigest()==PACKET_SHA256
    assert 'fictional' in load_packet()['readme']['all_data_is_invented']
    _,store=public
    with sqlite3.connect(store.template) as db:
        assert db.execute('SELECT count(*) FROM reviews').fetchone()[0]==0
        assert db.execute('SELECT count(*) FROM product_files').fetchone()[0]==0
        assert db.execute('SELECT count(*) FROM adjustment_events').fetchone()[0]==0


def test_receipts_adjustment_independent_partner_simulation_and_visitor_isolation(public):
    from app.services import adjustment_service as adjustments
    app,_=public;c,other=visitor(app),visitor(app);headers,_=bootstrap(c);bootstrap(other)
    before=c.get('/api/return-lines').json()
    payload={'actor_id':'st-01',**adjustments.metadata('v3')['demo']}
    r=c.post('/api/adjustments',headers=headers,json=payload);assert r.status_code==201,r.text
    item=r.json();assert item['payload']['delta']=='-12400.00'
    def action(item,which,staff,expected=200):
        r=c.post('/api/adjustments/'+item['id']+'/actions',headers=headers,json={'action':which,'actor_id':staff,'expected_sequence':item['sequence'],'note':'Simulated fictional receipts review'})
        assert r.status_code==expected,r.text
        return r.json()
    item=action(item,'submit','st-01')
    action(item,'approve','st-01',403)
    headers=role(c,headers,'st-02');action(item,'approve','st-02',403)
    headers=role(c,headers,'st-03');item=action(item,'approve','st-03')
    assert item['state']=='approved'
    assert c.get('/api/workpaper-summary').json()['approved_adjustment_ids']==[item['id']]
    assert other.get('/api/workpaper-summary').json()['approved_adjustment_ids']==[]
    assert other.get('/api/adjustments/'+item['id']).status_code==404
    assert c.get('/api/return-lines').json()==before
    assert not c.get('/api/workflow/readiness').json()['filing_ready']


def test_reviewer_decisions_and_checkpoints_are_private(public):
    app,_=public;a,b=visitor(app),visitor(app);headers,_=bootstrap(a);bootstrap(b)
    headers=role(a,headers,'st-02')
    finding=a.get('/api/reviews').json()['findings'][0]
    r=a.patch('/api/reviews/'+finding['id'],headers=headers,json={'status':'in_review','note':'Visitor-specific demonstration review','actor_role':'reviewer','actor_name':'st-02'})
    assert r.status_code==200,r.text
    assert 'Visitor-specific demonstration review' in a.get('/api/reviews').text
    assert 'Visitor-specific demonstration review' not in b.get('/api/reviews').text
    assert 'Visitor-specific demonstration review' not in b.get('/api/product/changes?wait_seconds=0').text
