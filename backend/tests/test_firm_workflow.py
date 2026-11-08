"""Strict security and workflow acceptance, independent of legacy test profile."""
import hashlib,json,sqlite3
from concurrent.futures import ThreadPoolExecutor
import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from app.security import Settings,redact
from app.services import workflow_service as service
from app.services.packet_service import DATA_PATH
ORIGIN='http://localhost:3200'
@pytest.fixture
def clients(tmp_path,monkeypatch):
    monkeypatch.setenv('REVIEW_DB_PATH',str(tmp_path/'strict.db'))
    app=create_app(Settings('demo','test',(ORIGIN,)));result={}
    for identifier in ('st-01','st-02','st-03','st-04','st-05'):
        c=TestClient(app);csrf=c.get('/api/workflow/session').json()['csrf_token']
        r=c.post('/api/workflow/session',json={'staff_id':identifier},headers={'origin':ORIGIN,'x-csrf-token':csrf});assert r.status_code==200,r.text
        c.headers.update({'origin':ORIGIN,'x-csrf-token':r.json()['csrf_token']});result[identifier]=c
    return result

def post(c,path,body,code=200):
    r=c.post('/api/workflow/'+path,json=body);assert r.status_code==code,r.text;return r.json()
def record(c,area='business',identifier=None,revision=0,answer='Duplicate receipts compared to client books.'):
    return post(c,'records',{'id':identifier,'area':area,'record_type':'preparation','title':'Business review','applicability':'applicable','answer':answer,'authority':'Packet source comparison','refs':['D16'],'expected_revision':revision})
def sign(c,area='business',level='reviewer',code=200):
    p=c.get('/api/workflow/signoff-preview',params={'area':area,'level':level});assert p.status_code==200,p.text
    return post(c,'signoffs',{'area':area,'level':level,'expected_digest':p.json()['digest'],'note':'Independent demonstration review'},code)

def test_configuration_fail_closed(tmp_path,monkeypatch):
    monkeypatch.setenv('REVIEW_DB_PATH',str(tmp_path/'strict.db'))
    assert TestClient(create_app(Settings())).get('/api/overview').status_code==401
    for s in [Settings('demo','production'),Settings('legacy_test','production'),Settings('credential','production',('http://localhost',),{'st-01':'x'*40}),Settings('credential','production',('https://firm.example',),{'st-01':'short'})]:
        with pytest.raises(RuntimeError):create_app(s)
    monkeypatch.setenv('REVIEW_DB_PATH',str(DATA_PATH.parent/'reviews.db'))
    with pytest.raises(RuntimeError):create_app(Settings('legacy_test','test'))

@pytest.mark.parametrize('path',['/api/overview','/api/documents','/api/documents/D03','/api/evidence/ev-0005','/api/return-lines','/api/validation','/api/reviews','/api/unified-findings','/api/evidence-graph?ref=D03','/api/source-verification/ev-0005','/api/adjustments','/api/workflow/history','/docs','/openapi.json'])
def test_every_route_requires_session(clients,path):assert TestClient(clients['st-01'].app).get(path).status_code==401

def test_sessions_csrf_identity_inactive(clients):
    c=clients['st-01'];assert c.get('/api/overview').status_code==200
    assert c.post('/api/adjustments',json={'actor_id':'st-03'}).status_code==403
    assert c.post('/api/workflow/records',json={},headers={'x-csrf-token':'wrong'}).status_code==403
    assert c.post('/api/workflow/records',json={},headers={'origin':'https://evil.example'}).status_code==403
    assert c.post('/api/workflow/session',json={'staff_id':'st-06'}).status_code==403
    old=c.cookies.get('mf_session');assert c.post('/api/workflow/session',json={'staff_id':'st-02'}).status_code==200
    attacker=TestClient(c.app);attacker.cookies.set('mf_session',old);assert attacker.get('/api/overview').status_code==401
    assert c.post('/api/workflow/records',json={}).status_code==403
    assert c.get('/api/workflow/session/staff/anything').status_code==404

def test_assignment_roles_clearance_admin(clients):
    prep,partner,admin=clients['st-01'],clients['st-03'],clients['st-05'];limited=clients['st-04']
    assert limited.get('/api/overview').status_code==403
    a={'staff_id':'st-04','responsibility':'preparer','areas':['business'],'state':'active','expected_revision':0}
    post(prep,'assignments',a,403);post(partner,'assignments',a);assert limited.get('/api/overview').status_code==200
    assert limited.get('/api/overview',headers={'x-sensitive-access':'reveal','x-access-purpose':'Review identity discrepancy'}).status_code==403
    record(limited)
    assert admin.get('/api/overview').status_code==403
    assert admin.get('/api/workflow/overview').json()['records']==[]
    assert admin.get('/api/workflow/access-history').status_code==200
    post(partner,'assignments',{**a,'responsibility':'partner','expected_revision':1},403)
    post(partner,'assignments',{**a,'state':'inactive','expected_revision':1});assert limited.get('/api/overview').status_code==403

@pytest.mark.parametrize('path',['/api/overview','/api/documents/D03','/api/evidence/ev-0005','/api/evidence-resolution?ref=ev-0005','/api/evidence-graph?ref=D03','/api/source-verification/ev-0005'])
def test_nested_redaction_cache_audit(clients,path):
    c=clients['st-01'];r=c.get(path);assert r.status_code==200,r.text
    assert all(secret not in r.text for secret in ['482915','666-41-2287','4483019276','990000017']);assert 'no-store' in r.headers['cache-control']
    assert c.get(path,headers={'x-sensitive-access':'reveal','x-access-purpose':'Examine identity source field'}).status_code==200
    events=clients['st-03'].get('/api/workflow/access-history').json()['events'];assert any(e['action']=='reveal' and e['outcome']=='allowed' for e in events)
    assert all('482915' not in e['resource_json'] for e in events)

def test_validation_redaction(clients):
    v=redact({'ssn':'666-99-1234','routing':123456789,'nested':{'account':'4483019276'},'text':'666-99-1234'})
    assert v['routing'] is None and '666-99-1234' not in json.dumps(v)
    r=clients['st-01'].post('/api/workflow/records',json={'answer':'666-99-1234'});assert r.status_code==422 and '666-99-1234' not in r.text

def test_immutable_policy_and_nonwaivable_controls(clients):
    admin=clients['st-05'];p=admin.get('/api/workflow/overview').json()['policy'];body={'expected_revision':p['revision'],'changes':{'partner_threshold':'500'},'rationale':'Tighten partner review standard'}
    post(clients['st-03'],'policies',body,403);r=post(admin,'policies',body);assert r['policy']['partner_threshold']=='500';post(admin,'policies',body,409)
    for changes in [{'partner_threshold':'1001'},{'independent_review_required':False}]:post(admin,'policies',{**body,'expected_revision':r['revision'],'changes':changes},400)
    with service.connection() as db:
        with pytest.raises(sqlite3.IntegrityError):db.execute("UPDATE workflow_policies SET created_by='x'")

def test_scoped_permanent_transactional_invalidation(clients):
    prep,reviewer,partner=clients['st-01'],clients['st-02'],clients['st-03'];r=record(prep);record(prep,'payments');sign(prep,code=403)
    b=sign(reviewer);p=sign(partner,level='partner');payment=sign(reviewer,'payments')
    record(prep,identifier=r['id'],revision=1,answer='Changed business receipts conclusion.')
    states={s['id']:s['state'] for s in reviewer.get('/api/workflow/overview').json()['signoffs']}
    assert states[b['id']]=='invalidated' and states[p['id']]=='invalidated' and states[payment['id']]=='valid'
    record(prep,identifier=r['id'],revision=2);assert sign(reviewer)['id']!=b['id']
    with service.connection() as db:
        assert db.execute('SELECT state FROM workflow_signoffs WHERE id=?',(b['id'],)).fetchone()[0]=='invalidated'
        with pytest.raises(sqlite3.IntegrityError):db.execute("UPDATE workflow_signoffs SET state='valid' WHERE id=?",(b['id'],))
        assert db.execute("SELECT count(*) FROM workflow_events WHERE entity_id=? AND action='invalidated'",(b['id'],)).fetchone()[0]==1

def test_stale_preview_and_concurrent_mutations(clients):
    prep,reviewer=clients['st-01'],clients['st-02'];r=record(prep);preview=reviewer.get('/api/workflow/signoff-preview?area=business').json()
    body={'id':r['id'],'area':'business','record_type':'preparation','title':'Concurrent review','applicability':'applicable','answer':'Changed','authority':'Packet source','refs':['D16'],'expected_revision':1}
    with ThreadPoolExecutor(max_workers=2) as pool:assert sorted(pool.map(lambda i:prep.post('/api/workflow/records',json=body).status_code,[1,2]))==[200,409]
    post(reviewer,'signoffs',{'area':'business','level':'reviewer','expected_digest':preview['digest'],'note':'Stale review'},409)

def test_diligence_notes_history_and_independence(clients):
    prep,reviewer=clients['st-01'],clients['st-02']
    r=post(prep,'records',{'area':'business','record_type':'judgment','title':'Receipts overlap','applicability':'applicable','answer':'Investigate duplicate income','authority':'Packet D16','refs':['D16'],'expected_revision':0})
    path='records/'+r['id']+'/actions';post(prep,path,{'action':'submit','expected_revision':1,'note':'Submitted for review'})
    post(prep,path,{'action':'approve','expected_revision':2,'note':'Self approval'},403)
    assert post(reviewer,path,{'action':'approve','expected_revision':2,'note':'Independent source review'})['state']=='approved'
    n=post(prep,'notes',{'area':'business','action':'create','title':'Overlap','note':'Need source confirmation','owner_id':'st-01','expected_revision':0});sign(reviewer,code=409)
    for action,c in [('respond',prep),('request_resolution',prep),('resolve',reviewer)]:n=post(c,'notes',{'id':n['id'],'area':'business','action':action,'title':'Overlap','note':'Documented source response','owner_id':'st-01','expected_revision':n['revision']})
    assert n['state']=='resolved'
    events=reviewer.get('/api/workflow/history',params={'entity_id':n['id']}).json()['events'];assert [e['action'] for e in events]==['create','respond','request_resolution','resolve']
    with service.connection() as db:
        with pytest.raises(sqlite3.IntegrityError):db.execute('DELETE FROM workflow_events')

def test_real_blocked_synthetic_fixture_and_integrity(clients):
    r=clients['st-02'].get('/api/workflow/readiness');assert r.status_code==200,r.text;result=r.json();assert not result['filing_ready']
    assert {'FINAL_RETURN_AND_CLIENT_AUTHORIZATION_UNVERIFIED','UNSUPPORTED_TAX_CALCULATION','INCOMPLETE_DILIGENCE','UNRESOLVED_FINDING','MISSING_CURRENT_SIGNOFF'}<={b['code'] for b in result['blockers']}
    post(clients['st-02'],'readiness',{})
    assert service.readiness_from_facts({'assurance':'demonstration','checks':{'TEST':[]}})['filing_ready']
    assert not service.readiness_from_facts({'assurance':'demonstration','checks':{'TEST':['missing']}})['filing_ready']
    assert hashlib.sha256(DATA_PATH.read_bytes()).hexdigest()=='ee01f8508bd2fd9854754b82fd9c4a055bdc55e2778a132002a25381c412ad19'
    with service.connection() as db:assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'

def test_legacy_adjustment_api_invalidates_inside_commit(clients):
    from app.services.adjustment_service import metadata
    prep,reviewer,partner=clients['st-01'],clients['st-02'],clients['st-03'];record(prep);signed=sign(reviewer)
    r=prep.post('/api/adjustments',json={'actor_id':'st-01',**metadata('v3')['demo']});assert r.status_code==201,r.text;item=r.json()
    with service.connection() as db:assert db.execute('SELECT state FROM workflow_signoffs WHERE id=?',(signed['id'],)).fetchone()[0]=='invalidated'
    def action(c,action,code=200):
        nonlocal item
        r=c.post('/api/adjustments/'+item['id']+'/actions',json={'actor_id':('st-01' if c is prep else 'st-02' if c is reviewer else 'st-03'),'action':action,'expected_sequence':item['sequence'],'note':'Documented independent review'})
        assert r.status_code==code,r.text
        if r.status_code==200:item=r.json()
    action(prep,'submit');action(reviewer,'approve',403);action(partner,'approve')
    summary=prep.get('/api/workpaper-summary');assert summary.status_code==200
    action(partner,'reverse');assert item['state']=='reversed'
    history=prep.get('/api/adjustments/'+item['id']+'/history');assert history.status_code==200


def test_evidence_verification_api_invalidates_scoped_signoff(clients):
    from app.services.source_verification_service import get_source_verification
    prep,reviewer=clients['st-01'],clients['st-02'];record(prep,'investments');s=sign(reviewer,'investments')
    match=get_source_verification('ev-0016')['match']
    payload={'verifier_id':'st-02','method':'agreed_to_source_document','source_ref':'doc:D08#page1','status':'confirmed','notes':'Compared source field','expected_sequence':0,'quote':{'start':match['start'],'end':match['end'],'text':match['matched_text']}}
    r=reviewer.post('/api/field-verifications/ev-0016',json=payload);assert r.status_code==201,r.text
    # D08 W-2 is an indirect input to several areas; bound source graph determines invalidation.
    history=reviewer.get('/api/field-verifications/ev-0016');assert history.json()['sequence']==1
    assert prep.post('/api/field-verifications/ev-0016',json={**payload,'verifier_id':'st-01'}).status_code==403
    assert s['id']


def test_rollback_restores_changes_and_signoffs_atomically(clients,monkeypatch):
    from app.security_context import request_principal
    r=record(clients['st-01']);s=sign(clients['st-02'])
    person={**service.staff('st-01'),'profile':'strict','assurance':'demonstration'}
    original=service.invalidate
    def fail_after_invalidation(db):original(db);raise RuntimeError('Simulated transaction failure')
    monkeypatch.setattr(service,'invalidate',fail_after_invalidation)
    token=request_principal.set(person)
    try:
        with pytest.raises(RuntimeError):service.save_record(person,{'id':r['id'],'area':'business','record_type':'preparation','title':'Changed','applicability':'applicable','answer':'Changed','authority':'Source','refs':['D16'],'expected_revision':1})
    finally:request_principal.reset(token)
    monkeypatch.setattr(service,'invalidate',original)
    with service.connection() as db:
        assert service.entity(db,r['id'])['revision']==1
        assert db.execute('SELECT state FROM workflow_signoffs WHERE id=?',(s['id'],)).fetchone()[0]=='valid'


def test_concurrent_signoff_and_mutation_cannot_leave_stale_valid_approval(clients):
    prep,reviewer=clients['st-01'],clients['st-02'];r=record(prep);preview=reviewer.get('/api/workflow/signoff-preview?area=business').json()
    def approve():return reviewer.post('/api/workflow/signoffs',json={'area':'business','level':'reviewer','expected_digest':preview['digest'],'note':'Independent review'}).status_code
    def mutate():
        return prep.post('/api/workflow/records',json={'id':r['id'],'area':'business','record_type':'preparation','title':'Concurrent source change','applicability':'applicable','answer':'Changed','authority':'Source','refs':['D16'],'expected_revision':1}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        a=pool.submit(approve);m=pool.submit(mutate);assert m.result()==200;assert a.result() in {200,409}
    assert all(s['state']!='valid' for s in reviewer.get('/api/workflow/overview').json()['signoffs'])


def test_credential_mode_requires_real_configured_secret(tmp_path,monkeypatch):
    monkeypatch.setenv('REVIEW_DB_PATH',str(tmp_path/'credentials.db'))
    c=TestClient(create_app(Settings('credential','test',(ORIGIN,),{'st-01':'x'*40})))
    csrf=c.get('/api/workflow/session').json()['csrf_token'];c.headers.update({'origin':ORIGIN,'x-csrf-token':csrf})
    assert c.post('/api/workflow/session',json={'staff_id':'st-01','credential':'incorrect'}).status_code==401
    r=c.post('/api/workflow/session',json={'staff_id':'st-01','credential':'x'*40});assert r.status_code==200
    assert r.json()['staff']['assurance']=='configured_credential' and r.json()['legal_signature'] is False
    assert 'HttpOnly' in r.headers['set-cookie']


def test_policy_and_assignment_changes_invalidate_existing_approvals(clients):
    prep,reviewer,admin=clients['st-01'],clients['st-02'],clients['st-05'];record(prep);s=sign(reviewer)
    post(admin,'policies',{'expected_revision':1,'changes':{'partner_threshold':'750'},'rationale':'Tighten partner threshold'})
    assert next(x for x in reviewer.get('/api/workflow/overview').json()['signoffs'] if x['id']==s['id'])['state']=='invalidated'
    fresh=sign(reviewer)
    post(clients['st-03'],'assignments',{'staff_id':'st-01','responsibility':'preparer','areas':['business'],'state':'active','expected_revision':1})
    assert next(x for x in reviewer.get('/api/workflow/overview').json()['signoffs'] if x['id']==fresh['id'])['state']=='invalidated'

def test_strict_scope_and_self_resolution_are_enforced(clients):
    partner=clients['st-03'];limited=clients['st-04']
    post(partner,'assignments',{'staff_id':'st-04','responsibility':'preparer','areas':['business'],'state':'active','expected_revision':0})
    post(limited,'records',{'area':'credits','record_type':'preparation','title':'Out of scope','applicability':'applicable','answer':'x','authority':'Packet','refs':['D16'],'expected_revision':0},403)
    reviewer=clients['st-02']
    n=post(reviewer,'notes',{'area':'business','action':'create','title':'Source question','note':'Review requested','owner_id':'st-01','expected_revision':0})
    for action in ['respond','request_resolution']:
        n=post(reviewer,'notes',{'id':n['id'],'area':'business','action':action,'title':'Source question','note':'Reviewer prepared response','owner_id':'st-01','expected_revision':n['revision']})
    post(reviewer,'notes',{'id':n['id'],'area':'business','action':'resolve','title':'Source question','note':'Own response','owner_id':'st-01','expected_revision':n['revision']},403)
    post(partner,'notes',{'id':n['id'],'area':'business','action':'resolve','title':'Source question','note':'Independent partner review','owner_id':'st-01','expected_revision':n['revision']})


def test_session_validation_does_not_echo_credentials(clients):
    c=clients['st-01'];r=c.post('/api/workflow/session',json={'staff_id':{},'credential':['secret-should-not-be-reflected']})
    assert r.status_code==422 and 'secret-should-not-be-reflected' not in r.text and 'no-store' in r.headers['cache-control']


def test_assignments_deadlines_notifications_and_ownership(clients):
    partner=clients['st-03'];prep=clients['st-01'];overview=partner.get('/api/workflow/overview').json();t=overview['tasks'][0]
    r=post(partner,'tasks',{'id':t['id'],'state':'open','assignee':'st-01','due_date':'2027-01-15','expected_revision':t['revision']})
    assert r['data']['due_date']=='2027-01-15'
    post(prep,'tasks',{'id':t['id'],'state':'complete','assignee':'st-02','expected_revision':r['revision']},403)
    post(prep,'tasks',{'id':t['id'],'state':'complete','assignee':'st-01','expected_revision':r['revision']})
    notification=prep.get('/api/workflow/overview').json()['notifications'][0]
    post(prep,'tasks',{'id':notification['id'],'state':'read','expected_revision':notification['revision']})
    root=partner.get('/api/workflow/overview').json()['engagement']
    post(prep,'engagement',{'owner_id':'st-03','expected_revision':root['revision']},403)
    post(partner,'engagement',{'owner_id':'st-03','expected_revision':root['revision']})

def test_all_registered_nonpublic_routes_fail_closed(clients):
    import re
    c=TestClient(clients['st-01'].app)
    checked=[]
    for path,operations in c.app.openapi()['paths'].items():
        if path in {'/health','/api/workflow/session','/api/workflow/session/staff'}:continue
        path=re.sub(r'\{[^}]+\}','test',path)
        for method in operations:
            if method.upper() not in {'GET','POST','PATCH','PUT','DELETE'}:continue
            response=c.request(method,path,json={} if method.upper() in {'POST','PATCH','PUT'} else None)
            assert response.status_code==401,(method,path,response.text);checked.append(path)
    assert len(checked)>40


def test_access_logs_and_free_text_are_redacted(clients):
    reviewer=clients['st-02'];prep=clients['st-01']
    n=post(prep,'notes',{'area':'business','action':'create','title':'Sensitive note','note':'Bank account: 1234567890 and PIN: 123456','owner_id':'st-01','expected_revision':0})
    history=reviewer.get('/api/workflow/history',params={'entity_id':n['id']})
    assert '1234567890' not in history.text and '123456' not in history.text
    with service.connection() as db:
        with pytest.raises(sqlite3.IntegrityError):db.execute('DELETE FROM workflow_access_events')


def test_invalid_policy_values_rejected_without_500(clients):
    for changes in [{'partner_threshold':'not-numeric'},{'variance_review':[]},{'variance_review':{'compare_to':'prior_year','flag_if_change_over_percent':'NaN','and_over_amount':1000}}]:
        post(clients['st-05'],'policies',{'expected_revision':1,'changes':changes,'rationale':'Validate policy input'},400)

def test_tightened_policy_uses_unrounded_tax_effects():
    from decimal import Decimal
    from app.services.adjustment_service import calculate
    method={'tax_effect_rates':{'schc_profit':{'federal_per_dollar':0.1,'california_per_dollar':0}}}
    result=calculate(method,'SchC.1',Decimal('7500.04'),Decimal('750'))
    assert result['federal_tax']=='750.00' and result['requires_partner']
    assert not calculate(method,'SchC.1',Decimal('7500'),Decimal('750'))['requires_partner']


def test_identifier_redaction_preserves_opaque_dependency_digests():
    value='abc482915def990000017abc4483019276def'
    assert redact({'digest':value})['digest']==value
    assert redact({'text':'PIN 482915; routing 990000017'})['text']=='PIN ******; routing *********'

def test_professional_question_authors_cannot_sign_their_area(clients):
    reviewer=clients['st-02']
    post(reviewer,'records',{'area':'business','record_type':'question','title':'Professional tax question','applicability':'applicable','answer':'Substantive analysis authored by reviewer','authority':'Packet comparison','refs':['D16'],'expected_revision':0})
    sign(reviewer,code=403)


def test_required_checklist_labels_cannot_be_repurposed(clients):
    prep=clients['st-01'];r=next(r for r in prep.get('/api/workflow/overview').json()['records'] if r['id']=='required:0')
    post(prep,'records',{'id':r['id'],'area':r['area'],'record_type':'required_step','title':'Bypass original prerequisite','applicability':'not_applicable','answer':'Unrelated answer','authority':'Packet','refs':['D16'],'expected_revision':r['revision']},400)


def test_scoped_preparer_can_use_existing_correction_api(clients):
    post(clients['st-03'],'assignments',{'staff_id':'st-04','responsibility':'preparer','areas':['business'],'state':'active','expected_revision':0})
    r=clients['st-04'].post('/api/reconciliations/business.receipts/adjustment',json={'actor_id':'st-04','note':'Compare independent business receipts sources','authority':'Packet source comparison'})
    assert r.status_code==201,r.text
