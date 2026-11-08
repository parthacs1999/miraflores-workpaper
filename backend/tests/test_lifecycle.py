"""Phase 6 simulator acceptance. Real readiness is never waived by synthetic success paths."""
import hashlib,json,sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta,timezone
from copy import deepcopy
import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from app.security import Settings
from app.services import lifecycle_service as s,workflow_service as w
from app.services.packet_service import DATA_PATH,load_packet
ORIGIN='http://localhost:3200'

@pytest.fixture
def clients(tmp_path,monkeypatch):
    monkeypatch.setenv('REVIEW_DB_PATH',str(tmp_path/'lifecycle.db'));app=create_app(Settings('demo','test',(ORIGIN,)));result={}
    for sid in ('st-01','st-02','st-03','st-04','st-05'):
        c=TestClient(app);csrf=c.get('/api/workflow/session').json()['csrf_token']
        r=c.post('/api/workflow/session',json={'staff_id':sid},headers={'origin':ORIGIN,'x-csrf-token':csrf});assert r.status_code==200,r.text
        c.headers.update({'origin':ORIGIN,'x-csrf-token':r.json()['csrf_token']});result[sid]=c
    return result

def post(c,path,body,code=200):
    r=c.post('/api/lifecycle'+path,json=body);assert r.status_code==code,r.text;return r.json()
def get(c,path):
    r=c.get('/api/lifecycle'+path);assert r.status_code==200,r.text;return r.json()
def freeze(c,note='Original demonstration return',**extra):return post(c,'/snapshots',{'version':'v3','mode':'demonstration','note':note,'refs':['D01'],**extra})
def authorize(c,snapshot_id):
    a=post(c,'/authorizations',{'snapshot_id':snapshot_id,'expires_at':(datetime.now(timezone.utc)+timedelta(days=1)).isoformat(),'note':'Joint-client snapshot review request'})
    for cu in ('cu-01','cu-02'):a=post(c,'/authorizations/'+a['id']+'/responses',{'client_id':cu,'decision':'approve','refs':['msg-09'],'note':'Declared demo client approval, never legal e-signature','expected_revision':a['revision']})
    return a
def action(c,f,act,**extra):return post(c,'/filings/'+f['id']+'/actions',{'action':act,'expected_revision':f['revision'],'note':'Documented simulated lifecycle action',**extra})
def draft(c,sid,j='federal',**extra):return post(c,'/filings',{'snapshot_id':sid,'jurisdiction':j,'note':'Prepared demonstration transmission',**extra})
def accepted(clients,j='federal'):
    frozen=freeze(clients['st-01']);authorize(clients['st-01'],frozen['id']);f=draft(clients['st-01'],frozen['id'],j)
    f=action(clients['st-03'],f,'ready');f=action(clients['st-01'],f,'submit');f=action(clients['st-02'],f,'simulate_accept');return frozen,f


def test_snapshot_reproducibility_immutability_and_originals(clients):
    c=clients['st-01'];before=deepcopy(load_packet());a=freeze(c);b=freeze(c)
    assert a['id']==b['id'] and a['content_hash']==b['content_hash'] and a['validity']=='current'
    assert not a['content']['readiness']['filing_ready'] and a['content']['approved_adjustments']==[]
    assert a['content']['engine_baseline']==before['return_versions'][-1]
    with w.connection() as db:
        raw=s.snapshot(db,a['id']);assert raw['content_hash']==s.digest({'content':raw['content'],'dependencies':raw['dependencies']})
        assert raw['content']['evidence_bundle']==before  # Includes FX, timelines, methods and other-version references offline.
        for statement in ["UPDATE lifecycle_snapshots SET content_hash='x'","DELETE FROM lifecycle_snapshots"]:
            with pytest.raises(sqlite3.IntegrityError):db.execute(statement)
    assert before==load_packet() and hashlib.sha256(DATA_PATH.read_bytes()).hexdigest()=='ee01f8508bd2fd9854754b82fd9c4a055bdc55e2778a132002a25381c412ad19'

@pytest.mark.parametrize('version',['v1','v2','v3'])
def test_authoritative_finalization_is_blocked(clients,version):
    post(clients['st-01'],'/snapshots',{'version':version,'mode':'authoritative','note':'Cannot waive actual requirements','refs':['D01']},409)
    assert get(clients['st-01'],'/overview')['snapshots']==[]
    assert not clients['st-01'].get('/api/workflow/readiness').json()['filing_ready']


def test_concurrent_identical_freezes_are_idempotent(clients):
    c=clients['st-01']
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:freeze(c),range(2)))
    assert results[0]['id']==results[1]['id'] and len(get(c,'/overview')['snapshots'])==1


def test_authorization_binding_joint_responses_independence_and_namespace(clients):
    c=clients['st-01'];frozen=freeze(c);f=draft(c,frozen['id'])
    post(clients['st-03'],'/filings/'+f['id']+'/actions',{'action':'ready','expected_revision':1,'note':'No client approval yet'},409)
    a=post(c,'/authorizations',{'snapshot_id':frozen['id'],'expires_at':(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat(),'note':'Bound demo client request'})
    body={'client_id':'cu-01','decision':'approve','refs':['D01'],'note':'Declared client response','expected_revision':a['revision']}
    post(c,'/authorizations/'+a['id']+'/responses',{**body,'client_id':'st-03'},403)
    a=post(c,'/authorizations/'+a['id']+'/responses',body);assert a['state']=='partially_approved'
    post(clients['st-03'],'/filings/'+f['id']+'/actions',{'action':'ready','expected_revision':1,'note':'Both clients required'},409)
    post(c,'/authorizations/'+a['id']+'/responses',{**body,'expected_revision':a['revision']},409)
    a=post(c,'/authorizations/'+a['id']+'/responses',{**body,'client_id':'cu-02','expected_revision':a['revision']});assert a['state']=='approved'
    assert not get(c,'/authorizations/'+a['id']+'/client-review')['client_authenticated']
    post(c,'/filings/'+f['id']+'/actions',{'action':'ready','expected_revision':1,'note':'Self-approval blocked'},403)
    ready=action(clients['st-03'],f,'ready');assert ready['state']=='ready_for_submission'
    assert all(not r['legal_signature'] for r in a['data']['responses'].values())
    post(c,'/filings/membership:st-03/actions',{'action':'submit','expected_revision':1,'note':'Cannot clobber another entity'},404)


def test_client_decline_and_expiry_never_authorize_filing(clients,monkeypatch):
    c=clients['st-01'];frozen=freeze(c);a=authorize(c,frozen['id']);f=draft(c,frozen['id']);f=action(clients['st-03'],f,'ready')
    original=datetime
    class FutureClock(datetime):
        @classmethod
        def now(cls,tz=None):return original.now(tz)+timedelta(days=2)
    monkeypatch.setattr(s,'datetime',FutureClock)
    overview=get(c,'/overview');assert next(r for r in overview['records'] if r['id']==a['id'])['state']=='invalidated'
    assert next(r for r in overview['records'] if r['id']==f['id'])['state']=='draft'
    post(c,'/filings/'+f['id']+'/actions',{'action':'submit','expected_revision':f['revision'],'note':'Expired consent'},409)


def test_declined_response_is_not_complete_authorization(clients):
    c=clients['st-01'];frozen=freeze(c);a=post(c,'/authorizations',{'snapshot_id':frozen['id'],'expires_at':(datetime.now(timezone.utc)+timedelta(days=1)).isoformat(),'note':'Client review request'})
    a=post(c,'/authorizations/'+a['id']+'/responses',{'client_id':'cu-01','decision':'decline','refs':['msg-09'],'note':'Client declines demonstration','expected_revision':a['revision']});assert a['state']=='declined'
    f=draft(c,frozen['id']);post(clients['st-03'],'/filings/'+f['id']+'/actions',{'action':'ready','expected_revision':f['revision'],'note':'Decline cannot authorize'},409)

@pytest.mark.parametrize('jurisdiction,code',[('federal','R0000-504-02'),('california','STATE-HOLD')])
def test_rejection_correction_and_resubmission_preserve_attempts(clients,jurisdiction,code):
    c=clients['st-01'];frozen=freeze(c);authorize(c,frozen['id']);f=draft(c,frozen['id'],jurisdiction)
    f=action(clients['st-03'],f,'ready');f=action(c,f,'submit');f=action(clients['st-02'],f,'simulate_reject')
    assert f['data']['attempts'][0]['errors'][0]['code']==code
    post(c,'/filings',{'snapshot_id':frozen['id'],'jurisdiction':jurisdiction,'note':'Cannot bypass rejected attempt'},409)
    post(c,'/filings/'+f['id']+'/actions',{'action':'correct','expected_revision':f['revision'],'note':'Same payload cannot be silently changed','replacement_snapshot_id':frozen['id'],'refs':['D71']},409)
    corrected=freeze(c,'Identity evidence corrected in the transmittal narrative',refs=['D71'],supersedes_id=frozen['id'])
    f=action(c,f,'correct',replacement_snapshot_id=corrected['id'],refs=['D71'])
    post(clients['st-03'],'/filings/'+f['id']+'/actions',{'action':'ready','expected_revision':f['revision'],'note':'New authorization required'},409)
    authorize(c,corrected['id']);f=action(clients['st-03'],f,'ready');f=action(c,f,'submit');f=action(clients['st-02'],f,'simulate_accept')
    assert f['state']=='accepted' and len(f['data']['attempts'])==2 and len(f['data']['corrections'])==1
    assert f['data']['attempts'][0]['snapshot_id']==frozen['id'] and f['data']['attempts'][1]['snapshot_id']==corrected['id']
    assert all(not a['real_submission'] for a in f['data']['attempts'])
    assert 'authorization_snapshot' in f['data']['attempts'][1]
    assert get(c,'/snapshots/'+frozen['id'])['content_hash']==frozen['content_hash']


def test_changes_invalidate_pending_approvals_but_preserve_accepted_history(clients):
    c=clients['st-01'];frozen,f=accepted(clients)
    original=get(c,'/snapshots/'+frozen['id']);copy=post(c,'/filings/'+f['id']+'/client-copy',{})
    other=draft(c,frozen['id'],'california');other=action(clients['st-03'],other,'ready')
    from app.services.adjustment_service import metadata
    r=c.post('/api/adjustments',json={'actor_id':'st-01',**metadata('v3')['demo']});assert r.status_code==201,r.text
    view=get(c,'/overview');states={r['id']:r['state'] for r in view['records']}
    assert states[f['id']]=='accepted' and states[other['id']]=='draft'
    assert next(s for s in view['snapshots'] if s['id']==frozen['id'])['validity']=='invalidated'
    assert get(c,'/snapshots/'+frozen['id'])['content']==original['content']
    assert get(c,'/packages/'+copy['id'])['canonical_content_hash']==copy['content_hash']
    post(c,'/filings/'+other['id']+'/actions',{'action':'submit','expected_revision':other['revision'],'note':'Stale approval cannot be submitted'},409)


def test_supersession_cannot_replace_an_accepted_original(clients):
    frozen,_=accepted(clients)
    post(clients['st-01'],'/snapshots',{'version':'v3','mode':'demonstration','note':'Use an amendment','refs':['D01'],'supersedes_id':frozen['id']},409)


def test_client_copy_package_redaction_hash_delivery_and_immutability(clients):
    frozen,f=accepted(clients);c=clients['st-01'];package=post(c,'/filings/'+f['id']+'/client-copy',{})
    view=get(c,'/packages/'+package['id']);assert '666-41-2287' not in json.dumps(view) and '482915' not in json.dumps(view)
    assert hashlib.sha256(view['download_json'].encode()).hexdigest()==view['delivered_content_hash']
    assert json.loads(view['download_json'])==view['content']
    delivery=post(c,'/deliveries',{'package_id':package['id'],'client_id':'cu-01','note':'Record simulated portal delivery only'})
    assert delivery['state']=='simulated_delivered' and not delivery['data']['real_delivery_confirmation']
    with w.connection() as db:
        for statement in ["UPDATE lifecycle_packages SET content_hash='bad'","DELETE FROM lifecycle_packages"]:
            with pytest.raises(sqlite3.IntegrityError):db.execute(statement)
    assert get(c,'/packages/'+package['id'])['snapshot_id']==frozen['id']

@pytest.mark.parametrize('j,amount,balance',[('federal','36000.00',35728),('california','0.00',-9131)])
def test_packet_extension_calculation_independent_approval_and_explicit_events(clients,j,amount,balance):
    c=clients['st-01'];e=post(c,'/extensions',{'jurisdiction':j,'version':'v2','note':'Use supplied April estimate'})
    assert e['data']['proposed_payment']==amount and e['data']['estimate']['estimated_balance']==balance
    body={'action':'approve','expected_revision':e['revision'],'note':'Independent extension review'}
    post(c,'/extensions/'+e['id']+'/actions',body,403)
    e=post(clients['st-03'],'/extensions/'+e['id']+'/actions',body)
    e=post(c,'/extensions/'+e['id']+'/actions',{'action':'simulate_submit','expected_revision':e['revision'],'note':'Simulated extension only'})
    assert e['state']=='simulated_submitted' and not e['data']['real_submission']
    e=post(clients['st-02'],'/extensions/'+e['id']+'/actions',{'action':'record_packet_event','refs':['timeline:extension-2026-04-14'],'expected_revision':e['revision'],'note':'Link scripted extension record'})
    assert e['state']=='external_evidence_recorded' and not e['data']['real_external_confirmation']
    post(clients['st-02'],'/extensions/'+e['id']+'/actions',{'action':'confirm_external','expected_revision':e['revision'],'note':'No external channel configured'},409)


def test_extension_wrong_baseline_and_policy_invalidation(clients):
    c=clients['st-01'];post(c,'/extensions',{'jurisdiction':'federal','version':'v3','note':'Missing extension method'},409)
    e=post(c,'/extensions',{'jurisdiction':'federal','version':'v2','note':'Packet estimate'})
    e=post(clients['st-03'],'/extensions/'+e['id']+'/actions',{'action':'approve','expected_revision':e['revision'],'note':'Independent partner review'})
    r=clients['st-05'].post('/api/workflow/policies',json={'expected_revision':1,'changes':{'partner_threshold':'900'},'rationale':'Change firm approval standard'});assert r.status_code==200,r.text
    assert next(x for x in get(c,'/overview')['records'] if x['id']==e['id'])['state']=='needs_review'


def test_payment_identity_tax_year_reconciliation_and_no_fabricated_amount(clients):
    c=clients['st-01'];p=post(c,'/payments',{'source_ref':'agency:/irs_account_transcript_2025/0/transactions/0','note':'Attributable packet payment'})
    assert p['data']['amount']=='3000.00' and not p['data']['real_world_confirmation']
    post(c,'/payments',{'source_ref':'agency:/irs_account_transcript_2025/1/transactions/0','note':'Duplicate transcript snapshot'},409)
    post(c,'/payments/'+p['id']+'/review',{'expected_revision':p['revision'],'note':'Self review'},403)
    p=post(clients['st-02'],'/payments/'+p['id']+'/review',{'expected_revision':p['revision'],'note':'Independent packet-record review'})
    assert p['data']['reviewed_value']=='3000.00'
    prior=post(c,'/payments',{'source_ref':'agency:/ftb_account/tax_year_2024_payments_after_filing/0','note':'Do not transfer this prior-year credit'})
    assert prior['data']['tax_year']==2024
    post(c,'/payments',{'source_ref':'made-up-payment','note':'No fabricated evidence'},400)
    post(c,'/payments',{'source_ref':'agency:/irs_account_transcript_2025/0/transactions/1','amount':'9999','note':'Server derives amount'},422)
    assert len(get(c,'/overview')['payment_reconciliations'])==2


def test_payment_evidence_invalidates_only_related_workpaper_signoffs(clients):
    c=clients['st-01'];r=clients['st-02'];ids={}
    for area in ['business','payments']:
        assert c.post('/api/workflow/records',json={'area':area,'record_type':'preparation','title':area,'applicability':'applicable','answer':'Source preparation','authority':'Packet','refs':['D01'],'expected_revision':0}).status_code==200
        preview=r.get('/api/workflow/signoff-preview',params={'area':area}).json()
        response=r.post('/api/workflow/signoffs',json={'area':area,'level':'reviewer','expected_digest':preview['digest'],'note':'Independent review'});assert response.status_code==200,response.text;ids[area]=response.json()['id']
    post(c,'/payments',{'source_ref':'agency:/irs_account_transcript_2025/0/transactions/0','note':'New payment evidence'})
    states={s['id']:s['state'] for s in c.get('/api/workflow/overview').json()['signoffs']}
    assert states[ids['payments']]=='invalidated' and states[ids['business']]=='valid'


def test_amendment_keeps_original_and_requires_distinct_review_and_approval(clients):
    original,f=accepted(clients);c=clients['st-01']
    from app.services.adjustment_service import metadata
    adj=c.post('/api/adjustments',json={'actor_id':'st-01',**metadata('v3')['demo']}).json()
    for actor,act in [('st-01','submit'),('st-03','approve')]:
        r=clients[actor].post('/api/adjustments/'+adj['id']+'/actions',json={'actor_id':actor,'action':act,'expected_sequence':adj['sequence'],'note':'Approved receipts correction'});assert r.status_code==200,r.text;adj=r.json()
    a=post(c,'/amendments',{'parent_snapshot_id':original['id'],'version':'v3','note':'Amend duplicated business receipts after independent approval','refs':['D14','D15','D21']})
    assert any(x['key']=='SchC.1' and x['numeric_difference']=='-12400.00' for x in a['comparison']['approved_workpaper_leaf_changes'])
    post(c,'/amendments/'+a['id']+'/actions',{'action':'review','expected_revision':a['revision'],'note':'Cannot review own amendment'},403)
    a=post(clients['st-02'],'/amendments/'+a['id']+'/actions',{'action':'review','expected_revision':a['revision'],'note':'Independent amendment review'})
    post(clients['st-02'],'/amendments/'+a['id']+'/actions',{'action':'approve','expected_revision':a['revision'],'note':'Distinct partner required'},403)
    a=post(clients['st-03'],'/amendments/'+a['id']+'/actions',{'action':'approve','expected_revision':a['revision'],'note':'Independent partner approval'})
    authorize(c,a['data']['snapshot_id']);amended=draft(c,a['data']['snapshot_id'],amendment_id=a['id']);amended=action(clients['st-03'],amended,'ready');amended=action(c,amended,'submit');amended=action(clients['st-02'],amended,'simulate_accept')
    assert amended['state']=='accepted' and get(c,'/snapshots/'+original['id'])['content_hash']==original['content_hash']
    assert next(x for x in get(c,'/overview')['records'] if x['id']==f['id'])['state']=='accepted'


def test_amendment_requires_an_accepted_original(clients):
    original=freeze(clients['st-01']);post(clients['st-01'],'/amendments',{'parent_snapshot_id':original['id'],'version':'v3','note':'Not filed yet','refs':['D01']},409)


def test_notice_packet_deadline_review_examination_package_and_retention(clients):
    frozen,_=accepted(clients);c=clients['st-01'];n=post(c,'/notices',{'packet_notice_id':'N-2025-L566','owner_id':'st-01','note':'Scripted 2028 examination, not real receipt'})
    assert n['data']['response_due']=='2028-02-19' and n['data']['real_received_at'] is None and n['data']['classification']=='packet_scripted_examination'
    post(c,'/notices/'+n['id']+'/package',{},409)
    for actor,act,extra in [('st-01','prepare',{'snapshot_id':frozen['id'],'refs':['D72','D14','D53']}),('st-01','submit_review',{})]:
        n=post(clients[actor],'/notices/'+n['id']+'/actions',{'action':act,'expected_revision':n['revision'],'note':'Documented response and valuation evidence review',**extra})
    post(c,'/notices/'+n['id']+'/actions',{'action':'approve','expected_revision':n['revision'],'note':'Self approval blocked'},403)
    n=post(clients['st-02'],'/notices/'+n['id']+'/actions',{'action':'approve','expected_revision':n['revision'],'note':'Independent evidence and response review'})
    package=post(c,'/notices/'+n['id']+'/package',{});view=get(c,'/packages/'+package['id'])
    assert view['kind']=='examination_response' and view['content']['frozen_workpaper']['engine_baseline']
    assert view['content']['response_evidence'] and view['content']['notice_audit_history']
    assert view['content']['retention']['years']==7 and view['content']['retention']['legal_hold']
    assert '666-41-2287' not in json.dumps(view) and '482915' not in json.dumps(view)
    assert hashlib.sha256(view['download_json'].encode()).hexdigest()==view['delivered_content_hash']
    for actor,act in [('st-01','simulate_dispatch'),('st-02','close_demo')]:n=post(clients[actor],'/notices/'+n['id']+'/actions',{'action':act,'expected_revision':n['revision'],'note':'Simulated response workflow only'})
    assert n['state']=='simulated_closed' and not n['data']['real_dispatch']


def test_california_manual_notice_and_deadline_validation(clients):
    c=clients['st-01'];body={'jurisdiction':'california','title':'Staff-entered California demonstration notice','source_date':'2026-10-10','response_due':'2026-11-10','refs':['D74'],'owner_id':'st-01','note':'Not a live FTB notice'}
    n=post(c,'/notices',body);assert n['data']['jurisdiction']=='california' and n['data']['deadline_source']=='staff_entered_demo'
    post(c,'/notices',{**body,'response_due':'2026-09-01'},400)
    post(c,'/notices',{**body,'owner_id':'st-06'},403)


def test_carryover_original_manual_reviewed_provenance_and_handoff(clients):
    frozen,_=accepted(clients);c=clients['st-01'];r=clients['st-02']
    records=post(c,'/carryovers/import',{'snapshot_id':frozen['id'],'note':'Unverified stored carryovers for handoff'})['records']
    assert len(records)==len(s.flattened(load_packet()['return_versions'][-1]['carryovers_out']))
    a=next(x for x in records if x['data']['key']=='/federal/minimum_tax_credit_from_2025_amt')
    a=post(c,'/carryovers/'+a['id']+'/actions',{'action':'revise','expected_revision':a['revision'],'note':'Documented manual estimate, not a new tax result','adjusted_value':'3800.00','refs':['F6251.11'],'authority':'Manual planning proposal; full corrected rollforward unsupported'})
    assert a['data']['original_value']==3871 and a['data']['adjusted_value']=='3800.00' and a['data']['reviewed_value'] is None
    handoff=post(c,'/handoffs',{'snapshot_id':frozen['id'],'owner_id':'st-01','note':'Next-year planning handoff'})
    post(r,'/handoffs/'+handoff['id']+'/actions',{'action':'review','expected_revision':handoff['revision'],'note':'Incomplete carryover review'},409)
    for record in records:
        record=a if record['id']==a['id'] else record
        reviewed=post(r,'/carryovers/'+record['id']+'/actions',{'action':'review','expected_revision':record['revision'],'note':'Reviewed workpaper provenance, not authoritative 2026 tax','refs':['D06'],'authority':'Stored outgoing engine amounts; unresolved correction limitations retained'})
        assert not reviewed['data']['authoritative_rollforward'] and reviewed['data']['source_path']
    handoff=post(r,'/handoffs/'+handoff['id']+'/actions',{'action':'review','expected_revision':handoff['revision'],'note':'Independent handoff review'})
    handoff=post(c,'/handoffs/'+handoff['id']+'/actions',{'action':'handoff','expected_revision':handoff['revision'],'note':'Transfer proposed next-year ownership'})
    assert handoff['state']=='handed_off' and handoff['package']['kind']=='handoff'
    assert handoff['data']['planning_reference']==load_packet()['planning_reference_2026']
    assert handoff['data']['unsupported_calculations'] and 'projected_tax' not in handoff['data']
    current_c=next(x for x in get(c,'/overview')['records'] if x['id']==a['id'])
    post(c,'/carryovers/'+current_c['id']+'/actions',{'action':'revise','expected_revision':current_c['revision'],'note':'New manual planning proposal after publication','adjusted_value':'3700.00','refs':['F6251.11'],'authority':'Manual proposal remains unsupported as authoritative tax'})
    stale=next(x for x in get(c,'/overview')['records'] if x['id']==handoff['id'])
    assert stale['state']=='handed_off' and not stale['data']['approval_valid'] and stale['data']['needs_successor_handoff']

@pytest.mark.parametrize('path',['/overview','/history','/snapshots/nonexistent','/packages/nonexistent','/authorizations/nonexistent/client-review'])
def test_all_lifecycle_data_is_protected(clients,path):
    assert TestClient(clients['st-01'].app).get('/api/lifecycle'+path).status_code==401
    assert clients['st-05'].get('/api/lifecycle'+path).status_code==403
    assert clients['st-04'].get('/api/lifecycle'+path).status_code==403


def test_sensitive_packages_access_clearance_and_no_cache(clients):
    _,f=accepted(clients);c=clients['st-01'];package=post(c,'/filings/'+f['id']+'/client-copy',{})
    assignment=clients['st-03'].post('/api/workflow/assignments',json={'staff_id':'st-04','responsibility':'preparer','areas':['*'],'state':'active','expected_revision':0});assert assignment.status_code==200
    denied=clients['st-04'].get('/api/lifecycle/packages/'+package['id'],headers={'x-sensitive-access':'reveal','x-access-purpose':'Inspect protected tax identity'});assert denied.status_code==403
    masked=clients['st-04'].get('/api/lifecycle/packages/'+package['id']);assert masked.status_code==200 and 'no-store' in masked.headers['cache-control']
    assert '666-41-2287' not in masked.text
    # Full frozen snapshot contains source identifiers; explicit cleared reveal is audited.
    sid=f['data']['snapshot_id'];revealed=c.get('/api/lifecycle/snapshots/'+sid,headers={'x-sensitive-access':'reveal','x-access-purpose':'Inspect specific source identity fields'});assert revealed.status_code==200 and '666-41-2287' in revealed.text
    events=clients['st-03'].get('/api/workflow/access-history').json()['events'];assert any(e['action']=='reveal' and e['outcome']=='allowed' for e in events)


def test_invalid_transitions_forged_identity_and_concurrent_filing_approval(clients):
    c=clients['st-01'];frozen=freeze(c);authorize(c,frozen['id']);f=draft(c,frozen['id'])
    post(c,'/filings/'+f['id']+'/actions',{'action':'submit','expected_revision':1,'note':'No readiness approval'},409)
    post(c,'/filings/'+f['id']+'/actions',{'action':'ready','expected_revision':1,'note':'Unauthorized self-approval must be audited'},403)
    outcomes=clients['st-03'].get('/api/workflow/access-history').json()['events']
    assert any(e['action']=='request_outcome' and e['outcome']=='denied' for e in outcomes)
    forged=c.post('/api/lifecycle/filings/'+f['id']+'/actions',json={'action':'ready','expected_revision':1,'note':'Forged partner','actor_id':'st-03'});assert forged.status_code==403
    def approve(_):return clients['st-03'].post('/api/lifecycle/filings/'+f['id']+'/actions',json={'action':'ready','expected_revision':1,'note':'Concurrent partner approval'}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:assert sorted(pool.map(approve,[1,2]))==[200,409]


def test_migration_preserves_rows_and_integrity(clients,tmp_path):
    from app.migrate import migrate
    path=tmp_path/'preserve.db'
    with sqlite3.connect(path) as db:
        db.executescript("CREATE TABLE reviews(version TEXT,finding_id TEXT,note TEXT);INSERT INTO reviews VALUES('v3','legacy','keep original');")
        before=list(db.execute('SELECT * FROM reviews'));migrate(db);migrate(db)
        assert list(db.execute('SELECT * FROM reviews'))==before and db.execute('SELECT count(*) FROM lifecycle_schema_migrations').fetchone()[0]==1
        assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok' and not db.execute('PRAGMA foreign_key_check').fetchall()

def test_redaction_preserves_tax_capital_account_balances_while_hiding_identifiers():
    from app.security import redact
    value=redact({'ridgeline_capital_account_end':63660.0,'capital_account_balance':5000,'account':'4483019276','routing':990000017,'ip_pin':'482915'})
    assert value['ridgeline_capital_account_end']==63660.0 and value['capital_account_balance']==5000
    assert '4483019276' not in json.dumps(value) and value['routing'] is None and '482915' not in json.dumps(value)

def test_new_client_request_supersedes_old_consent_and_decline_blocks_submission(clients):
    c=clients['st-01'];frozen=freeze(c);old=authorize(c,frozen['id']);f=draft(c,frozen['id']);action(clients['st-03'],f,'ready')
    new=post(c,'/authorizations',{'snapshot_id':frozen['id'],'expires_at':(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat(),'note':'Fresh request supersedes old demo consent'})
    new=post(c,'/authorizations/'+new['id']+'/responses',{'client_id':'cu-01','decision':'decline','refs':['msg-09'],'note':'New declared-client decision','expected_revision':new['revision']})
    view=get(c,'/overview');assert next(r for r in view['records'] if r['id']==old['id'])['state']=='invalidated'
    current_f=next(r for r in view['records'] if r['id']==f['id']);assert current_f['state']=='draft'
    post(clients['st-03'],'/filings/'+f['id']+'/actions',{'action':'ready','expected_revision':current_f['revision'],'note':'Old consent must not override new decline'},409)

def test_fresh_freeze_after_supersession_keeps_old_snapshot_permanently_retired(clients):
    c=clients['st-01'];old=freeze(c,'Original content to reproduce')
    freeze(c,'Successor with a different rationale',supersedes_id=old['id'])
    fresh=freeze(c,'Original content to reproduce')
    assert fresh['id']!=old['id'] and fresh['content_hash']==old['content_hash'] and fresh['validity']=='current'
    assert get(c,'/snapshots/'+old['id'])['validity']=='superseded'


def test_extension_evidence_cannot_substitute_an_unrelated_payment(clients):
    c=clients['st-01'];e=post(c,'/extensions',{'jurisdiction':'federal','version':'v2','note':'Supplied extension'})
    e=post(clients['st-03'],'/extensions/'+e['id']+'/actions',{'action':'approve','expected_revision':e['revision'],'note':'Independent approval'})
    e=post(c,'/extensions/'+e['id']+'/actions',{'action':'simulate_submit','expected_revision':e['revision'],'note':'No real submission'})
    post(clients['st-02'],'/extensions/'+e['id']+'/actions',{'action':'record_packet_event','refs':['agency:/irs_account_transcript_2025/1/transactions/0'],'expected_revision':e['revision'],'note':'This 3000 estimate does not establish the 36000 extension payment'},400)
    linked=post(clients['st-02'],'/extensions/'+e['id']+'/actions',{'action':'record_packet_event','refs':['agency:/irs_account_transcript_2025/1/transactions/4'],'expected_revision':e['revision'],'note':'Correct scripted extension transaction'})
    assert linked['state']=='external_evidence_recorded' and not linked['data']['real_external_confirmation']


def test_late_simulated_outcome_binds_the_submitted_payload_not_current_workpaper(clients):
    c=clients['st-01'];frozen=freeze(c);authorize(c,frozen['id']);f=draft(c,frozen['id']);f=action(clients['st-03'],f,'ready');f=action(c,f,'submit')
    post(c,'/payments',{'source_ref':'agency:/irs_account_transcript_2025/0/transactions/0','note':'New workpaper evidence after submission'})
    f=action(clients['st-02'],f,'simulate_accept')
    assert f['data']['attempts'][0]['content_hash']==frozen['content_hash']
    assert next(x for x in get(c,'/overview')['snapshots'] if x['id']==frozen['id'])['validity']=='invalidated'
    assert not clients['st-01'].get('/api/workflow/readiness').json()['filing_ready']

def test_amended_rejection_can_be_resubmitted_only_with_new_approved_amendment(clients):
    original,_=accepted(clients);c=clients['st-01']
    def amendment(reason):
        a=post(c,'/amendments',{'parent_snapshot_id':original['id'],'version':'v3','note':reason,'refs':['D71']})
        for role,act in [('st-02','review'),('st-03','approve')]:a=post(clients[role],'/amendments/'+a['id']+'/actions',{'action':act,'expected_revision':a['revision'],'note':'Independent amended workpaper step'})
        return a
    a=amendment('First amended demonstration payload');authorize(c,a['data']['snapshot_id']);f=draft(c,a['data']['snapshot_id'],amendment_id=a['id']);f=action(clients['st-03'],f,'ready');f=action(c,f,'submit');f=action(clients['st-02'],f,'simulate_reject')
    replacement=amendment('Corrected amended demonstration payload')
    f=action(c,f,'correct',replacement_snapshot_id=replacement['data']['snapshot_id'],replacement_amendment_id=replacement['id'],refs=['D71'])
    authorize(c,replacement['data']['snapshot_id']);f=action(clients['st-03'],f,'ready');f=action(c,f,'submit');f=action(clients['st-02'],f,'simulate_accept')
    assert f['state']=='accepted' and len(f['data']['attempts'])==2 and f['data']['amendment_id']==replacement['id']
    assert get(c,'/snapshots/'+original['id'])['content_hash']==original['content_hash']


def test_original_mutation_and_lifecycle_invalidation_roll_back_together(clients,monkeypatch):
    c=clients['st-01'];frozen=freeze(c);a=authorize(c,frozen['id']);f=draft(c,frozen['id']);f=action(clients['st-03'],f,'ready')
    original=s.invalidate
    def fail_after_invalidation(db,actor):original(db,actor);raise RuntimeError('Injected commit failure')
    monkeypatch.setattr(s,'invalidate',fail_after_invalidation)
    response=c.post('/api/lifecycle/payments',json={'source_ref':'agency:/irs_account_transcript_2025/0/transactions/0','note':'Must roll back the whole mutation'})
    assert response.status_code==500
    monkeypatch.setattr(s,'invalidate',original)
    view=get(c,'/overview');assert not any(r['kind']=='lc_payment' for r in view['records'])
    assert next(x for x in view['snapshots'] if x['id']==frozen['id'])['validity']=='current'
    states={r['id']:r['state'] for r in view['records']};assert states[a['id']]=='approved' and states[f['id']]=='ready_for_submission'
