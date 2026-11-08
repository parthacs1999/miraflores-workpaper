"""Phase 7 uses private SQLite databases and strict sessions, never the legacy profile."""
import base64
import hashlib
import json
import sqlite3
import time
import struct
import zlib
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from app.security import Settings
from app.services import workflow_service as w,product_service as s
from app.services.packet_service import DATA_PATH

ORIGIN='http://localhost:3200'


@pytest.fixture
def clients(tmp_path,monkeypatch):
    monkeypatch.setenv('REVIEW_DB_PATH',str(tmp_path/'product.db'))
    app=create_app(Settings('demo','test',(ORIGIN,)));result={}
    for sid in ('st-01','st-02','st-03','st-04','st-05'):
        c=TestClient(app);csrf=c.get('/api/workflow/session').json()['csrf_token']
        r=c.post('/api/workflow/session',json={'staff_id':sid},headers={'origin':ORIGIN,'x-csrf-token':csrf});assert r.status_code==200
        c.headers.update({'origin':ORIGIN,'x-csrf-token':r.json()['csrf_token']});result[sid]=c
    return result


def post(c,path,body,code=200):
    r=c.post('/api/product'+path,json=body);assert r.status_code==code,r.text;return r.json()
def get(c,path,code=200):
    r=c.get('/api/product'+path);assert r.status_code==code,r.text;return r.json()
def wf(c,path,body,code=200):
    r=c.post('/api/workflow/'+path,json=body);assert r.status_code==code,r.text;return r.json()
def assign(clients,staff='st-04',areas=None,revision=0,state='active'):
    return wf(clients['st-03'],'assignments',{'staff_id':staff,'responsibility':'preparer','areas':areas or ['business'],'state':state,'expected_revision':revision})
def attachment(c,**extra):
    return post(c,'/attachments',{'area':'business','title':'Original supporting source','note':'Client-provided supporting evidence, not extracted','filename':'support.txt','media_type':'text/plain','content_base64':base64.b64encode(b'Business receipts source: 151300\n').decode(),'links':[{'kind':'document','id':'D14'}],**extra})
def question(c,**extra):
    return post(c,'/questions',{'area':'business','title':'Confirm duplicated receipts','note':'Explain overlap before filing','owner_id':'st-01','participants':['st-01','st-02','st-03'],'due_date':'2026-12-01','blocking':True,'refs':['D14'],**extra})
def record(c,title='Workpaper test',answer='Compared business receipts',refs=None,authority='Packet supporting sources'):
    return wf(c,'records',{'area':'business','record_type':'preparation','title':title,'applicability':'applicable','answer':answer,'authority':authority,'refs':refs or ['D14'],'expected_revision':0})
def sign(c,area='business'):
    p=c.get('/api/workflow/signoff-preview',params={'area':area,'level':'reviewer'}).json()
    return wf(c,'signoffs',{'area':area,'level':'reviewer','expected_digest':p['digest'],'note':'Independent scoped review'})
def payment_preparation(c):
    return wf(c,'records',{'area':'payments','record_type':'preparation','title':'Payment source review','applicability':'applicable','answer':'Compared agency payment evidence','authority':'Supplied agency records','refs':['D53'],'expected_revision':0})
def batch(c,operation,items,**extra):
    return post(c,'/bulk',{'operation':operation,'command_key':uuid4().hex,'items':items,'note':'Documented atomic multi-item operation',**extra})
def changes(c,after=0,**extra):
    r=c.get('/api/product/changes',params={'after':after,**extra});assert r.status_code==200,r.text;return r.json()
def download(c,identifier,code=200):
    r=c.get('/api/product/attachments/'+identifier+'/download',headers={'x-sensitive-access':'reveal','x-access-purpose':'Inspect original supporting evidence'});assert r.status_code==code,r.text;return r


def test_change_feed_indexes_old_and_new_reviews_adjustments_and_verifications(clients):
    c=clients['st-01'];head=changes(c)['cursor'];a=attachment(c);q=question(c)
    record(c)
    f=get(c,'/bulk/catalog?operation=acknowledge_findings')['items'][0]
    batch(c,'acknowledge_findings',[{'id':f['id'],'expected_revision':f['expected_revision']}])
    result=changes(c,head)
    assert {a['id'],q['id']}<={e['resource_id'] for e in result['events']}
    assert {'p_attachment','p_question','review','record'}<={e['category'] for e in result['events']}
    assert result['summary']['by_area']['business']>=3
    assert result['summary']['by_document']['D14']>=1 and result['summary']['by_finding'][f['id']]>=1
    assert result['summary']['by_review_status']['in_review']==1
    assert all('payload' not in e and 'note' not in e for e in result['events'])
    # Legacy mutation paths participate through the same SQL outbox triggers.
    with w.connection() as db:
        db.execute("INSERT INTO field_verification_events(version,evidence_id,sequence,verifier_id,verifier_name,verifier_role,credential,assurance,method,source_ref,status,notes,created_at,packet_hash,snapshot_json) VALUES('v3','ev-0001',1,'st-02','Daniel','reviewer','CPA','cpa_attestation','agreed_to_source_document','D01','confirmed','Review',?,'packet','{}')",(w.now(),))
    assert any(e['category']=='verification' for e in changes(c,result['cursor'])['events'])


def test_personal_checkpoints_persist_and_never_mark_another_reviewer_seen(clients):
    a,b=clients['st-01'],clients['st-02'];question(a)
    result=changes(a);cp=post(a,'/checkpoint',{'cursor':result['cursor'],'expected_revision':0})
    assert cp['revision']==1
    assert get(a,'/changes')['events']==[]
    assert get(b,'/changes')['events']
    post(a,'/checkpoint',{'cursor':result['cursor'],'expected_revision':0},409)
    post(a,'/checkpoint',{'cursor':0,'expected_revision':1},409)
    post(a,'/checkpoint',{'cursor':10**12,'expected_revision':1},409)


def test_reconnect_recovers_every_missed_page_without_duplicates(clients):
    c=clients['st-01'];head=changes(c)['cursor']
    expected=[question(c,title=f'Question {i}')['id'] for i in range(5)]
    found=[];cursor=head
    while True:
        page=changes(c,cursor,limit=2);found.extend(e['resource_id'] for e in page['events']);assert page['cursor']>=cursor;cursor=page['cursor']
        if not page['has_more']:break
    assert found==expected and len(set(found))==5
    assert changes(c,cursor)['events']==[]
    assert [e['resource_id'] for e in changes(c,head)['events']]==expected


def test_long_poll_releases_write_lock_and_wakes_on_committed_change(clients):
    c=clients['st-01'];head=changes(c)['cursor']
    with ThreadPoolExecutor(max_workers=2) as pool:
        pending=pool.submit(changes,c,head,wait_seconds=3)
        time.sleep(.15);q=question(clients['st-02'])
        result=pending.result(timeout=5)
    assert any(e['resource_id']==q['id'] for e in result['events'])


def test_scope_filtering_other_engagement_and_area_never_leak(clients):
    assign(clients);limited=clients['st-04'];head=changes(limited)['cursor']
    business=question(clients['st-01'])
    hidden=question(clients['st-01'],area='credits',title='PRIVATE CREDIT QUESTION',refs=['D62'])
    with w.connection() as db:
        db.execute("INSERT INTO product_changes(engagement_id,area,category,resource_id,action,actor_id,created_at,source_table,source_id) VALUES('OTHER','business','p_question','OTHER-PRIVATE','new','st-01',?,'test',98765)",(w.now(),))
        db.execute("INSERT INTO workflow_entities VALUES('OTHER-RECORD','record','OTHER','business',1,'draft','{}','[]','st-01',?)",(w.now(),))
        w.event(db,'OTHER-RECORD','record','changed','st-01',{'area':'business','note':'PRIVATE FOREIGN HISTORY'})
        assert db.execute("SELECT engagement_id FROM product_changes WHERE resource_id='OTHER-RECORD'").fetchone()[0]=='OTHER'
    result=changes(limited,head)
    assert business['id'] in json.dumps(result) and hidden['id'] not in json.dumps(result) and 'OTHER-PRIVATE' not in json.dumps(result) and 'OTHER-RECORD' not in json.dumps(result)
    assert hidden['id'] not in json.dumps(get(limited,'/overview'))
    get(limited,'/history/'+hidden['id'],403)
    for path in ['/api/return-lines','/api/evidence-resolution?ref=D62','/api/workflow/history','/api/lifecycle/overview']:
        assert limited.get(path).status_code==403
    assert limited.get('/api/overview').json()['household']=={'people':[],'limited_scope':True}


def test_scope_change_restarts_checkpoint_and_revocation_blocks_reconnect(clients):
    assign(clients);c=clients['st-04'];p=changes(c);post(c,'/checkpoint',{'cursor':p['cursor'],'expected_revision':0})
    assign(clients,areas=['business','credits'],revision=1)
    assert get(c,'/changes')['checkpoint']['cursor']==0
    assign(clients,revision=2,state='inactive')
    get(c,'/changes',403)


def test_long_poll_revocation_and_identity_switch_fail_before_delivery(clients):
    assign(clients);c=clients['st-04'];head=changes(c)['cursor']
    with ThreadPoolExecutor(max_workers=2) as pool:
        pending=pool.submit(c.get,'/api/product/changes',params={'after':head,'wait_seconds':2})
        time.sleep(.1);assign(clients,revision=1,state='inactive')
        assert pending.result(timeout=4).status_code==403
    c=clients['st-01'];head=changes(c)['cursor']
    # Revoke the exact in-flight cookie from a separate client, retaining its old cookie.
    other=TestClient(c.app);other.cookies.update(c.cookies)
    with ThreadPoolExecutor(max_workers=2) as pool:
        pending=pool.submit(c.get,'/api/product/changes',params={'after':head,'wait_seconds':.5})
        time.sleep(.1)
        r=other.post('/api/workflow/session',json={'staff_id':'st-03'},headers=c.headers);assert r.status_code==200
        assert pending.result(timeout=3).status_code==401


def test_bulk_findings_idempotency_audited_undo_and_no_resolution(clients):
    c=clients['st-01'];available=get(c,'/bulk/catalog?operation=acknowledge_findings')['items'][:2]
    data={'operation':'acknowledge_findings','command_key':uuid4().hex,'items':[{'id':i['id'],'expected_revision':i['expected_revision']} for i in available],'note':'Seen both issues; not resolved'}
    a=post(c,'/bulk',data);b=post(c,'/bulk',data);assert a==b
    for i in available:
        assert c.get('/api/reviews').json()['findings'][0] # original contract still available
        with w.connection() as db:assert db.execute('SELECT status FROM reviews WHERE finding_id=?',(i['id'],)).fetchone()[0]=='in_review'
    post(c,'/bulk',{**data,'note':'Changed content'},409)
    undone=post(c,'/bulk/'+a['id']+'/undo',{'expected_revision':1,'note':'Compensate accidental acknowledgment'})
    assert undone['state']=='undone'
    events=get(c,'/history/'+a['id'])['events'];assert len(events)==2
    with w.connection() as db:
        for i in available:
            assert db.execute('SELECT status FROM reviews WHERE finding_id=?',(i['id'],)).fetchone()[0]=='open'
            assert db.execute('SELECT COUNT(*) FROM review_events WHERE finding_id=?',(i['id'],)).fetchone()[0]==2


def test_bulk_partial_validation_rolls_back_every_item_and_idempotency_record(clients):
    c=clients['st-01'];a=record(c);b=record(c,authority='')
    data={'operation':'submit_records','command_key':uuid4().hex,'items':[{'id':i['id'],'expected_revision':1} for i in [a,b]],'note':'Atomic submission'}
    post(c,'/bulk',data,409)
    with w.connection() as db:
        assert w.entity(db,a['id'])['state']=='draft'
        assert not db.execute('SELECT 1 FROM product_commands WHERE command_key=?',(data['command_key'],)).fetchone()
        assert len(db.execute('SELECT id FROM workflow_events WHERE entity_id=?',(a['id'],)).fetchall())==1


def test_bulk_record_undo_invalidates_signoffs_permanently(clients):
    c=clients['st-01'];a=record(c);signed=sign(clients['st-02'])
    b=batch(c,'submit_records',[{'id':a['id'],'expected_revision':1}])
    post(c,'/bulk/'+b['id']+'/undo',{'expected_revision':1,'note':'Return to preparation for more evidence'})
    with w.connection() as db:
        assert w.entity(db,a['id'])['state']=='draft'
        assert db.execute('SELECT state FROM workflow_signoffs WHERE id=?',(signed['id'],)).fetchone()[0]=='invalidated'
        assert len(db.execute('SELECT id FROM workflow_events WHERE entity_id=?',(a['id'],)).fetchall())==3


def test_bulk_documents_acknowledgment_never_changes_accountability(clients):
    c=clients['st-01'];before=c.get('/api/document-accountability').json()
    b=batch(c,'acknowledge_documents',[{'id':'D14','expected_revision':0},{'id':'D15','expected_revision':0}])
    assert c.get('/api/document-accountability').json()==before
    post(c,'/bulk/'+b['id']+'/undo',{'expected_revision':1,'note':'Compensate seen markers'})
    with w.connection() as db:assert w.entity(db,'ack:st-01:D14')['state']=='unacknowledged'


def test_bulk_assignment_permissions_notifications_and_compensation(clients):
    c=clients['st-05'];items=get(c,'/bulk/catalog?operation=assign_tasks')['items'][:2]
    b=batch(c,'assign_tasks',[{'id':i['id'],'expected_revision':i['expected_revision']} for i in items],assignee='st-01')
    with w.connection() as db:assert all(w.entity(db,i['id'])['data']['assignee']=='st-01' for i in items)
    assert any('bulk' in n['data']['title'].lower() or 'Task assigned' in n['data']['title'] for n in clients['st-01'].get('/api/workflow/overview').json()['notifications'])
    post(c,'/bulk/'+b['id']+'/undo',{'expected_revision':1,'note':'Restore prior task ownership'})
    with w.connection() as db:assert all(w.entity(db,i['id'])['data']['assignee'] is None for i in items)
    get(c,'/bulk/catalog?operation=acknowledge_findings',403)


def test_bulk_concurrency_and_intervening_mutation_prevent_unsafe_undo(clients):
    c=clients['st-01'];a=record(c)
    data={'operation':'submit_records','command_key':uuid4().hex,'items':[{'id':a['id'],'expected_revision':1}],'note':'Concurrent exact same operation'}
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _:post(c,'/bulk',data),[1,2]))
    assert results[0]['id']==results[1]['id']
    wf(clients['st-02'],'records/'+a['id']+'/actions',{'action':'approve','expected_revision':2,'note':'Independent review'})
    post(c,'/bulk/'+results[0]['id']+'/undo',{'expected_revision':1,'note':'Must not restore or erase approval'},409)


@pytest.mark.parametrize('filename',['../secret.txt','/tmp/secret.txt','a\\b.txt','..txt','x\n.txt','a.txt.','a\x00.txt'])
def test_attachment_path_and_filename_attacks_are_rejected(clients,filename):
    c=clients['st-01'];payload={'area':'business','title':'Unsafe upload','note':'Rejected input','filename':filename,'media_type':'text/plain','content_base64':base64.b64encode(b'plain').decode(),'links':[{'kind':'document','id':'D14'}]}
    post(c,'/attachments',payload,400)
    assert not get(c,'/overview')['items']


@pytest.mark.parametrize(('filename','media','content'),[
    ('fake.pdf','application/pdf',b'not a pdf'),('active.pdf','application/pdf',b'%PDF-1.7\n/JavaScript (alert)\n%%EOF'),
    ('encrypted.pdf','application/pdf',b'%PDF-1.7\n/Encrypt 1 0 R\n%%EOF'),('evil.txt','text/plain',b'<script>evil</script>'),
    ('binary.txt','text/plain',b'\x00binary'),('fake.png','image/png',b'notpng'),('fake.jpg','image/jpeg',b'notjpeg'),
    ('exe.txt','text/plain',b'MZ\x00'),('fake.txt','application/pdf',b'%PDF-1.7\n%%EOF'),('nonutf8.txt','text/plain',b'\xff\xfe')])
def test_attachment_type_signature_and_active_content_validation(clients,filename,media,content):
    post(clients['st-01'],'/attachments',{'area':'business','title':'File validation','note':'Rejected upload','filename':filename,'media_type':media,'content_base64':base64.b64encode(content).decode(),'links':[{'kind':'document','id':'D14'}]},400)


def test_attachment_invalid_base64_empty_and_size_limits(clients):
    body={'area':'business','title':'File validation','note':'Rejected upload','filename':'test.txt','media_type':'text/plain','content_base64':'!!!','links':[{'kind':'document','id':'D14'}]}
    post(clients['st-01'],'/attachments',body,400)
    post(clients['st-01'],'/attachments',{**body,'content_base64':''},413)
    post(clients['st-01'],'/attachments',{**body,'content_base64':base64.b64encode(b'x'*(s.MAX_FILE+1)).decode()},413)
    r=clients['st-01'].post('/api/product/attachments',content=b'x'*(8*1024*1024+1),headers={'content-type':'application/json'})
    assert r.status_code==413


def test_attachment_immutable_hash_download_and_independent_manual_review(clients):
    c=clients['st-01'];a=attachment(c);assert a['data']['processing']=='not_extracted' and a['state']=='unreviewed'
    get(c,'/attachments/'+a['id']+'/download',403)
    raw=download(clients['st-02'],a['id']);data=raw.json()
    assert hashlib.sha256(base64.b64decode(data['content_base64'])).hexdigest()==a['data']['sha256']
    assert raw.headers['cache-control'].startswith('no-store') and raw.headers['x-content-type-options']=='nosniff'
    post(c,'/attachments/'+a['id']+'/actions',{'action':'review','note':'Self-review forbidden','expected_revision':1},403)
    reviewed=post(clients['st-02'],'/attachments/'+a['id']+'/actions',{'action':'review','note':'Read original and reviewed as support, not extracted','expected_revision':1})
    assert reviewed['state']=='reviewed' and reviewed['data']['processing']=='not_extracted'
    assert 'manual_support_review' in reviewed['data']['verification']
    with w.connection() as db:
        for sql in ['UPDATE product_files SET content=X\'00\'','DELETE FROM product_files']:
            with pytest.raises(sqlite3.IntegrityError):db.execute(sql)
    assert len(get(c,'/history/'+a['id'])['events'])==2


def test_attachment_requires_view_before_review_and_clearance_for_original(clients):
    a=attachment(clients['st-01']);assign(clients,areas=['*'])
    post(clients['st-02'],'/attachments/'+a['id']+'/actions',{'action':'review','note':'No inspection yet','expected_revision':1},409)
    get(clients['st-04'],'/attachments/'+a['id']+'/download',403)
    download(clients['st-04'],a['id'],403)
    get(clients['st-05'],'/overview',403)
    download(clients['st-05'],a['id'],403)
    assert clients['st-02'].get('/api/product/attachments/'+a['id']+'/download',headers={'x-sensitive-access':'reveal','x-access-purpose':'tiny'}).status_code==400


def test_attachment_metadata_versions_scope_and_signoff_invalidation(clients):
    c=clients['st-01'];record(c);payment_preparation(c);a=attachment(c);signed=sign(clients['st-02'],'payments')
    # The attachment is business scoped; it does not stale an unrelated payments review.
    with w.connection() as db:assert db.execute('SELECT state FROM workflow_signoffs WHERE id=?',(signed['id'],)).fetchone()[0]=='valid'
    download(clients['st-03'],a['id'])
    post(clients['st-03'],'/attachments/'+a['id']+'/actions',{'action':'review','expected_revision':1,'note':'Independent supporting file review'})
    business=sign(clients['st-02'])
    updated=post(c,'/attachments/'+a['id']+'/actions',{'action':'metadata','expected_revision':2,'title':'Revised description','links':[{'kind':'document','id':'D14'}],'note':'New evidence context'})
    assert updated['revision']==3 and updated['data']['sha256']==a['data']['sha256']
    with w.connection() as db:
        assert db.execute('SELECT state FROM workflow_signoffs WHERE id=?',(business['id'],)).fetchone()[0]=='invalidated'
        assert db.execute('SELECT state FROM workflow_signoffs WHERE id=?',(signed['id'],)).fetchone()[0]=='valid'
    post(c,'/attachments/'+a['id']+'/actions',{'action':'metadata','expected_revision':1,'title':'Stale','links':[{'kind':'document','id':'D14'}],'note':'Stale revision'},409)


def test_uploaded_evidence_resolves_and_enters_frozen_packages_without_encoded_leak(clients):
    c=clients['st-01'];a=attachment(c,content_base64=base64.b64encode(b'Unknown sensitive bank account 123456789101').decode())
    resolved=c.get('/api/evidence-resolution',params={'ref':a['id']}).json();assert resolved['type']=='attachment' and resolved['status']=='resolved'
    q=question(c,refs=[a['id']]);assert c.get('/api/evidence-resolution',params={'ref':q['id']}).json()['type']=='collaboration_question'
    frozen=c.post('/api/lifecycle/snapshots',json={'version':'v3','mode':'demonstration','note':'Freeze new evidence manifest','refs':[a['id']]}).json()
    assert frozen['content']['supplemental_evidence']['originals'][0]['unprocessed_file_content_base64'] is None
    assert a['id'] in json.dumps(frozen['dependencies'])
    from app.services.evidence_service import resolve_reference
    from app.services.packet_service import load_packet
    assert resolve_reference(a['id'],packet=load_packet()).status=='unresolved' # never injected into past replay
    assert c.get('/api/workflow/readiness').json()['filing_ready'] is False


def test_questions_threading_client_assurance_persistence_independent_resolution(clients):
    c=clients['st-01'];q=question(c)
    m=post(c,'/questions/'+q['id']+'/messages',{'expected_revision':1,'note':'Client said receipts include duplicate image','declared_client_id':'cu-01','refs':['D14']})
    assert not m['data']['client_authenticated'] and m['data']['recorded_by']=='st-01' and 'staff_mediated' in m['data']['assurance']
    post(clients['st-02'],'/questions/'+q['id']+'/messages',{'expected_revision':2,'parent_id':m['id'],'note':'Colleague follow-up retained as evidence','refs':['D14']})
    q=post(c,'/questions/'+q['id']+'/actions',{'action':'request_resolution','expected_revision':3,'note':'Response ready for independent clearance'})
    post(c,'/questions/'+q['id']+'/actions',{'action':'resolve','expected_revision':4,'note':'Self-resolution forbidden'},403)
    post(clients['st-02'],'/questions/'+q['id']+'/actions',{'action':'resolve','expected_revision':4,'note':'Responder cannot close own work'},403)
    q=post(clients['st-03'],'/questions/'+q['id']+'/actions',{'action':'resolve','expected_revision':4,'note':'Independent source review resolved the question'})
    assert q['state']=='resolved'
    assert q['id'] not in [r for b in c.get('/api/workflow/readiness').json()['blockers'] if b['code']=='OPEN_BLOCKING_QUESTION' for r in b['resources']]
    assert len([e for e in get(c,'/overview')['items'] if e['kind']=='p_message'])==2
    assert len(get(c,'/history/'+q['id'])['events'])==5
    assert any(n['data']['resource']==q['id'] for n in c.get('/api/workflow/overview').json()['notifications'])


def test_question_invalid_parent_participant_date_and_stale_revision(clients):
    c=clients['st-01'];q=question(c);other=question(c)
    m=post(c,'/questions/'+other['id']+'/messages',{'expected_revision':1,'note':'Other question response','refs':[]})
    post(c,'/questions/'+q['id']+'/messages',{'expected_revision':1,'parent_id':m['id'],'note':'Cross-thread reply','refs':[]},409)
    post(c,'/questions/'+q['id']+'/messages',{'expected_revision':8,'note':'Stale response','refs':[]},409)
    post(c,'/questions',{k:v for k,v in {**q['data'],'due_date':'not-a-date'}.items() if k in {'area','title','note','owner_id','participants','due_date','blocking','refs'}},400)
    assign(clients,areas=['*'])
    post(clients['st-04'],'/questions/'+q['id']+'/messages',{'expected_revision':1,'note':'Not a participant','refs':[]},403)
    post(c,'/questions/'+q['id']+'/messages',{'expected_revision':1,'note':'Forged client','declared_client_id':'cu-fake','refs':[]},403)


def test_question_changes_invalidate_related_signoffs_and_readiness_blocks(clients):
    c=clients['st-01'];record(c);payment_preparation(c);b=sign(clients['st-02']);p=sign(clients['st-02'],'payments')
    q=question(c)
    with w.connection() as db:
        assert db.execute('SELECT state FROM workflow_signoffs WHERE id=?',(b['id'],)).fetchone()[0]=='invalidated'
        assert db.execute('SELECT state FROM workflow_signoffs WHERE id=?',(p['id'],)).fetchone()[0]=='valid'
    assert any(q['id'] in b['resources'] for b in c.get('/api/workflow/readiness').json()['blockers'] if b['code']=='OPEN_BLOCKING_QUESTION')


def test_time_budget_decimal_totals_voids_and_original_packet_provenance(clients):
    c=clients['st-01'];original=get(c,'/operations');assert len(original['engagements'])==1 and original['total_actual_minutes']==0
    body={'area':'business','bucket':'business','minutes':95,'work_date':date.today().isoformat(),'note':'Compared receipts and source book totals','expected_revision':0}
    entry=post(c,'/time',body)
    data=get(c,'/operations');b=next(b for b in data['budgets'] if b['bucket']=='business')
    assert b['actual_minutes']==95 and b['actual_hours']=='1.58' and b['remaining_hours']=='1.92'
    changed=post(clients['st-05'],'/budgets',{'bucket':'business','hours':'1.25','note':'Revised engagement budget, original preserved','expected_revision':0})
    b=next(b for b in get(c,'/operations')['budgets'] if b['bucket']=='business')
    assert b['original_packet_hours']=='3.5' and b['over_budget'] and b['remaining_hours']=='-0.33'
    post(c,'/time',{**body,'id':entry['id'],'expected_revision':1,'state':'voided','note':'Compensate duplicate time'})
    assert get(c,'/operations')['total_actual_minutes']==0
    assert len(get(c,'/history/'+entry['id'])['events'])==2
    assert changed['data']['original_packet_hours']==3.5
    assert get(c,'/operations?q=not-a-real-client')['engagements']==[]


def test_time_permissions_limits_and_admin_operational_redaction(clients):
    c=clients['st-01'];body={'area':'business','bucket':'business','minutes':1000,'work_date':date.today().isoformat(),'note':'Sensitive workpaper note about bank account: 876543219','expected_revision':0}
    entry=post(c,'/time',body)
    post(c,'/time',body,409)
    post(c,'/time',{**body,'work_date':'2099-01-01'},400)
    post(c,'/time',{**body,'bucket':'california'},400)
    post(clients['st-02'],'/time',{**body,'id':entry['id'],'expected_revision':1},403)
    post(c,'/budgets',{'bucket':'business','hours':'2','note':'Unauthorized budget revision','expected_revision':0},403)
    admin=get(clients['st-05'],'/operations');assert 'Sensitive workpaper note' not in json.dumps(admin)
    assert admin['time_entries'][0]['data'].get('note') is None
    assign(clients)
    limited=get(clients['st-04'],'/operations');assert all(b['bucket']=='business' for b in limited['budgets'])


@pytest.mark.parametrize('path',['/overview','/changes','/bulk/catalog?operation=acknowledge_findings','/operations','/history/missing','/attachments/missing/download'])
def test_every_new_read_path_requires_strict_session(clients,path):
    c=TestClient(clients['st-01'].app);assert c.get('/api/product'+path).status_code==401


def test_new_mutations_require_csrf_origin_and_session_identity(clients):
    c=clients['st-01'];body={'cursor':0,'expected_revision':0}
    assert c.post('/api/product/checkpoint',json=body,headers={'x-csrf-token':'wrong'}).status_code==403
    assert c.post('/api/product/checkpoint',json=body,headers={'origin':'https://evil.example'}).status_code==403
    assert c.post('/api/product/checkpoint',json={**body,'actor_id':'st-03'}).status_code==403
    result=get(c,'/changes');assert '666-41-2287' not in json.dumps(result)


def test_phase7_migration_idempotence_append_only_and_packet_integrity(clients,tmp_path):
    from app.migrate import migrate
    path=tmp_path/'migrate.db'
    with sqlite3.connect(path) as db:
        migrate(db);before=db.execute('SELECT * FROM product_changes').fetchall();migrate(db)
        assert before==db.execute('SELECT * FROM product_changes').fetchall()
        assert db.execute('SELECT COUNT(*) FROM product_schema_migrations').fetchone()[0]==1
        assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok' and not db.execute('PRAGMA foreign_key_check').fetchall()
    assert hashlib.sha256(DATA_PATH.read_bytes()).hexdigest()=='ee01f8508bd2fd9854754b82fd9c4a055bdc55e2778a132002a25381c412ad19'


def test_bulk_undo_is_atomic_when_a_later_item_changed(clients):
    c=clients['st-01'];a=record(c);b=record(c)
    bulk=batch(c,'submit_records',[{'id':r['id'],'expected_revision':1} for r in [a,b]])
    wf(clients['st-02'],'records/'+b['id']+'/actions',{'action':'approve','expected_revision':2,'note':'Reviewed separately after submission'})
    post(c,'/bulk/'+bulk['id']+'/undo',{'expected_revision':1,'note':'Entire compensation must roll back'},409)
    with w.connection() as db:
        assert w.entity(db,a['id'])['state']=='submitted'
        assert w.entity(db,bulk['id'])['state']=='applied'
        assert not db.execute("SELECT 1 FROM workflow_events WHERE entity_id=? AND action='compensating_undo'",(a['id'],)).fetchone()


def test_undo_cannot_change_work_bound_to_submitted_simulated_filing(clients):
    from test_lifecycle import accepted
    c=clients['st-01'];r=record(c);b=batch(c,'submit_records',[{'id':r['id'],'expected_revision':1}])
    _,filing=accepted(clients)
    post(c,'/bulk/'+b['id']+'/undo',{'expected_revision':1,'note':'No reversal of already accepted payload'},409)
    with w.connection() as db:assert w.entity(db,filing['id'])['state']=='accepted'


def test_attachment_links_all_supported_workpaper_targets(clients):
    c=clients['st-01'];r=record(c);q=question(c)
    n=wf(c,'notes',{'area':'business','action':'create','title':'Source note','note':'Question about receipts','owner_id':'st-01','expected_revision':0})
    f=get(c,'/bulk/catalog?operation=acknowledge_findings')['items'][0]
    response=c.post('/api/adjustments',json={'actor_id':'st-01','target':'SchC.1','proposed_value':'151300','rationale':'Duplicate business receipts discrepancy','authority':'Source comparison','refs':['D14','D15']});assert response.status_code==201,response.text
    adjustment=response.json()
    links=[{'kind':'finding','id':f['id']},{'kind':'document','id':'D14'},{'kind':'adjustment','id':adjustment['id']},{'kind':'note','id':n['id']},{'kind':'workflow','id':r['id']},{'kind':'question','id':q['id']}]
    a=attachment(c,links=links);assert a['data']['links']==links


def test_attachment_metadata_history_does_not_leak_previous_unauthorized_scope(clients):
    c=clients['st-01'];q=question(c)
    credit=wf(c,'records',{'area':'credits','record_type':'preparation','title':'PRIVATE CREDIT CONTEXT','applicability':'applicable','answer':'Credit source comparison','authority':'Packet','refs':['D62'],'expected_revision':0})
    a=attachment(c,links=[{'kind':'workflow','id':credit['id']}],title='PRIVATE CREDIT ATTACHMENT')
    post(c,'/attachments/'+a['id']+'/actions',{'action':'metadata','expected_revision':1,'title':'Current business source','links':[{'kind':'question','id':q['id']}],'note':'Current business-only context'})
    assign(clients);limited=clients['st-04']
    assert 'PRIVATE CREDIT' not in json.dumps(get(limited,'/overview'))
    assert 'PRIVATE CREDIT' not in json.dumps(get(limited,'/history/'+a['id']))


def test_attachment_valid_png_pdf_and_storage_quota(clients,monkeypatch):
    def chunk(kind,content):return struct.pack('>I',len(content))+kind+content+struct.pack('>I',zlib.crc32(kind+content)&0xffffffff)
    png=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',1,1,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(b'\x00\xff\x00\x00'))+chunk(b'IEND',b'')
    a=attachment(clients['st-01'],filename='pixel.png',media_type='image/png',content_base64=base64.b64encode(png).decode())
    assert a['data']['sha256']==hashlib.sha256(png).hexdigest()
    pdf=b'%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n'
    attachment(clients['st-01'],filename='support.pdf',media_type='application/pdf',content_base64=base64.b64encode(pdf).decode())
    monkeypatch.setattr(s,'MAX_TOTAL_FILES',len(png)+len(pdf))
    body={'area':'business','title':'Quota','note':'Storage policy test','filename':'quota.txt','media_type':'text/plain','content_base64':base64.b64encode(b'x').decode(),'links':[{'kind':'document','id':'D14'}]}
    post(clients['st-01'],'/attachments',body,413)


def test_resolved_question_reopens_on_supporting_change_and_never_auto_revives(clients):
    c=clients['st-01'];a=attachment(c);q=question(c,refs=[a['id']])
    post(c,'/questions/'+q['id']+'/messages',{'expected_revision':1,'note':'Source explanation','refs':[a['id']]})
    post(c,'/questions/'+q['id']+'/actions',{'expected_revision':2,'action':'request_resolution','note':'Independent review requested'})
    resolved=post(clients['st-03'],'/questions/'+q['id']+'/actions',{'expected_revision':3,'action':'resolve','note':'Independent source assessment'})
    assert resolved['state']=='resolved'
    post(c,'/attachments/'+a['id']+'/actions',{'action':'metadata','expected_revision':1,'title':'Changed support','links':[{'kind':'document','id':'D14'}],'note':'New source context'})
    current=next(e for e in get(c,'/overview')['items'] if e['id']==resolved['id'])
    assert current['state']=='awaiting_review' and not current['data']['resolution_valid']
    post(c,'/attachments/'+a['id']+'/actions',{'action':'metadata','expected_revision':2,'title':a['data']['title'],'links':a['data']['links'],'note':a['data']['note']})
    with w.connection() as db:assert w.entity(db,resolved['id'])['state']=='awaiting_review'


def test_time_ids_cannot_reserve_other_namespaces_and_concurrent_daily_limit(clients):
    c=clients['st-01'];body={'area':'business','bucket':'business','minutes':800,'work_date':date.today().isoformat(),'note':'Actual recorded source-review time','expected_revision':0}
    post(c,'/time',{**body,'id':'budget:business'},404)
    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses=list(pool.map(lambda _:c.post('/api/product/time',json=body).status_code,[1,2]))
    assert sorted(statuses)==[200,409]
    with w.connection() as db:assert len(w.entities(db,'p_time'))==1


def test_product_history_and_command_tables_remain_append_only(clients):
    c=clients['st-01'];batch(c,'acknowledge_documents',[{'id':'D14','expected_revision':0}])
    with w.connection() as db:
        for table in ['product_changes','product_commands']:
            with pytest.raises(sqlite3.IntegrityError):db.execute('DELETE FROM '+table)
    assert len(get(c,'/bulk/history')['items'])==1


def test_new_evidence_invalidation_rolls_back_if_commit_hook_fails(clients,monkeypatch):
    c=clients['st-01'];before=get(c,'/overview')['items']
    def fail_hook(*args):raise RuntimeError('Simulated transactional invalidation failure')
    monkeypatch.setattr(w,'invalidate',fail_hook)
    r=c.post('/api/product/attachments',json={'area':'business','title':'Atomic evidence','note':'Must roll back original and metadata','filename':'test.txt','media_type':'text/plain','content_base64':base64.b64encode(b'support').decode(),'links':[{'kind':'document','id':'D14'}]})
    assert r.status_code==500
    with w.connection() as db:
        assert db.execute('SELECT COUNT(*) FROM product_files').fetchone()[0]==0
        assert [e for e in w.entities(db) if e['kind']=='p_attachment']==before


def test_question_metadata_reassignment_is_versioned_and_cannot_remove_blocker(clients):
    c=clients['st-01'];q=question(c)
    data={'expected_revision':1,'title':'Revised source question','note':'New owner and explicit response date','owner_id':'st-02','participants':['st-01','st-02','st-03'],'due_date':'2026-12-15','blocking':True,'refs':['D14']}
    post(c,'/questions/'+q['id']+'/metadata',{**data,'blocking':False},409)
    changed=post(c,'/questions/'+q['id']+'/metadata',data)
    assert changed['data']['owner_id']=='st-02' and changed['revision']==2
    post(c,'/questions/'+q['id']+'/metadata',{**data,'expected_revision':2},403)
    assert len(get(clients['st-02'],'/history/'+q['id'])['events'])==2


def test_open_questions_and_unreviewed_uploads_block_fresh_signoff(clients):
    c=clients['st-01'];record(c);a=attachment(c)
    preview=clients['st-02'].get('/api/workflow/signoff-preview?area=business').json()
    wf(clients['st-02'],'signoffs',{'area':'business','level':'reviewer','expected_digest':preview['digest'],'note':'Unreviewed files prevent approval'},409)
    download(clients['st-02'],a['id']);post(clients['st-02'],'/attachments/'+a['id']+'/actions',{'action':'review','expected_revision':1,'note':'Independently reviewed original'})
    question(c)
    preview=clients['st-02'].get('/api/workflow/signoff-preview?area=business').json()
    wf(clients['st-02'],'signoffs',{'area':'business','level':'reviewer','expected_digest':preview['digest'],'note':'Unresolved question prevents approval'},409)
