import hashlib
import json
import sqlite3
from copy import deepcopy
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.packet_service import DATA_PATH, load_packet
from app.services import review_service

client=TestClient(app)


@pytest.fixture(autouse=True)
def isolated(tmp_path,monkeypatch):
    path=tmp_path/'reconciliation.db';monkeypatch.setenv('REVIEW_DB_PATH',str(path));return path


def dashboard(version='v3'):
    response=client.get('/api/unified-findings',params={'version':version})
    assert response.status_code==200,response.text
    return response.json()


def finding(issue):return next(f for f in dashboard()['findings'] if f['issue_key']==issue)


def decision(identifier,**overrides):
    return client.post('/api/reconciliation-decision',params={'finding_id':identifier},json={
        'actor_id':'st-02','status':'in_review','disposition':'investigating','note':'Compared independently sourced inputs.',
        'authority':'Packet D14/D15/D21 receipt reconciliation.','refs':['doc:D14#page1'],**overrides})


def history(identifier):
    return client.get(f'/api/unified-findings/{identifier}/history').json()


def create_correction():
    response=client.post('/api/reconciliations/business.receipts/adjustment',json={'actor_id':'st-01','note':'Remove card receipts already in books.','authority':'D14 total and D15 page 3 deposit reconciliation, corroborated by D21.'})
    assert response.status_code==201,response.text
    return response.json()


def act(item,action,actor='st-01'):
    return client.post(f'/api/adjustments/{item["id"]}/actions',json={'actor_id':actor,'action':action,'expected_sequence':item['sequence'],'note':'Independent ledger review.'})


def test_api_comparisons_and_existing_review_workflow_share_canonical_state():
    item=finding('business.receipts')
    assert decision(item['id']).status_code==200
    saved=next(f for f in client.get('/api/reviews').json()['findings'] if f['id']==item['id'])
    assert saved['status']=='in_review'
    audit=history(item['id']);assert len(audit['events'])==len(audit['decisions'])==1
    assert audit['decisions'][0]['snapshot']['checks'][0]['expected_value']=='151300'
    assert audit['decisions'][0]['actor_id']=='st-02'
    assert decision(item['id'],status='resolved',disposition='professional_judgment',note='Reviewed and documented a conditional treatment.').status_code==200
    assert history(item['id'])['events'][0]['new_status']=='in_review'
    assert len(history(item['id'])['events'])==2
    assert finding('business.receipts')['status']=='resolved'


def test_primary_receipts_correction_requires_independent_partner_approval_and_never_overwrites_engine():
    before=deepcopy(load_packet());digest=hashlib.sha256(DATA_PATH.read_bytes()).hexdigest()
    item=finding('business.receipts');adjustment=create_correction()
    assert adjustment['state']=='draft'
    assert finding('business.receipts')['adjustment_links'][0]['id']==adjustment['id']
    denied=decision(item['id'],status='resolved',disposition='correction_linked',adjustment_id=adjustment['id'])
    assert denied.status_code==409,denied.text
    assert history(item['id'])['events']==[]
    adjustment=act(adjustment,'submit').json()
    assert act(adjustment,'approve','st-01').status_code==403
    assert act(adjustment,'approve','st-02').status_code==403
    response=act(adjustment,'approve','st-03');assert response.status_code==200
    adjustment=response.json()
    assert decision(item['id'],status='resolved',disposition='correction_linked',adjustment_id=adjustment['id']).status_code==200
    check=next(c for c in dashboard()['checks'] if c['id']=='business.receipts')
    assert check['reported_value']=='163700' and check['expected_value']=='151300'
    assert client.get('/api/workpaper-summary').json()['jurisdictions']['federal']['tax_effect']=='-4402.00'
    assert act(adjustment,'reverse','st-03').status_code==200
    assert client.get('/api/workpaper-summary').json()['approved_adjustment_ids']==[]
    assert decision(item['id'],status='resolved',disposition='correction_linked',adjustment_id=adjustment['id']).status_code==409
    assert load_packet()==before and hashlib.sha256(DATA_PATH.read_bytes()).hexdigest()==digest


def test_alias_identity_uses_one_review_history():
    item=finding('vehicle.miles')
    assert 'recon:vehicle.deduction' in item['aliases']
    assert decision('recon:vehicle.deduction').status_code==200
    assert finding('vehicle.miles')['status']=='in_review'
    assert history('recon:vehicle.deduction')['events']==history(item['id'])['events']
    assert history(item['id'])['events'][0]['finding_id']==item['id']


def test_legacy_history_and_id_stay_accessible_after_unification():
    legacy=client.get('/api/validation').json()['findings'][0]
    response=client.patch('/api/review-decision',params={'finding_id':legacy['id']},json={'actor_role':'reviewer','actor_name':'Original Reviewer','status':'resolved','note':'Original evidence review.'})
    assert response.status_code==200
    item=next(f for f in dashboard()['findings'] if f['id']==legacy['id'])
    assert item['status']=='resolved' and item['review_note']=='Original evidence review.'
    assert history(legacy['id'])['events'][0]['actor_name']=='Original Reviewer'


def test_link_unlink_history_and_duplicate_creation_are_explicit():
    adjustment=create_correction();item=finding('business.receipts')
    response=client.post('/api/reconciliations/business.receipts/adjustment',json={'actor_id':'st-01','note':'duplicate','authority':'D14'})
    assert response.status_code==409
    payload={'actor_id':'st-02','adjustment_id':adjustment['id'],'note':'Retain linkage history.','action':'unlink'}
    response=client.post('/api/reconciliation-links',params={'finding_id':item['id']},json=payload)
    assert response.status_code==200
    assert response.json()['adjustments']==[] and len(response.json()['events'])==2
    payload['action']='link'
    assert client.post('/api/reconciliation-links',params={'finding_id':item['id']},json=payload).status_code==200
    assert len(history(item['id'])['links']['events'])==3


def test_wrong_target_and_version_corrections_cannot_be_linked():
    adjustment=create_correction();other=finding('deductions.mortgage')
    body={'actor_id':'st-02','adjustment_id':adjustment['id'],'note':'Wrong target.'}
    assert client.post('/api/reconciliation-links',params={'finding_id':other['id']},json=body).status_code==409
    assert client.post('/api/reconciliation-links',params={'finding_id':other['id'],'version':'v2'},json=body).status_code==409


@pytest.mark.parametrize('overrides,code',[({'actor_id':'st-05'},403),({'actor_id':'unknown'},403),({'authority':' '},400),({'note':' '},400),({'refs':['ev-9999']},400),({'actor_role':'partner'},422),({'actor_id':'st-01','status':'resolved','disposition':'professional_judgment'},403)])
def test_invalid_decisions_have_no_partial_audit(overrides,code):
    item=finding('business.receipts');response=decision(item['id'],**overrides)
    assert response.status_code==code,response.text
    assert history(item['id'])['events']==[]


def test_unsupported_checks_stay_visible_and_cannot_create_fake_adjustments():
    assert any(c['id']=='california.amt' and c['conclusion']=='unsupported' for c in dashboard()['checks'])
    response=client.post('/api/reconciliations/california.amt/adjustment',json={'actor_id':'st-01','note':'Cannot compute','authority':'Packet explicitly excludes CA AMT'})
    assert response.status_code==409
    assert client.get('/api/adjustments').json()['adjustments']==[]


def test_unknown_api_versions_and_ids_are_404():
    assert client.get('/api/unified-findings?version=nope').status_code==404
    assert client.get('/api/reconciliations?version=nope').status_code==404
    assert client.get('/api/unified-findings/missing/history').status_code==404
    assert client.get('/api/reconciliations').json()['total']>300


def test_append_only_and_additive_migration_keep_existing_records(isolated):
    item=finding('business.receipts');assert decision(item['id']).status_code==200
    create_correction()
    from app.migrate import migrate
    with sqlite3.connect(isolated) as db:
        tables=['reviews','review_events','reconciliation_decisions','adjustments','adjustment_revisions','adjustment_events','field_verification_events','finding_adjustment_events']
        before={t:list(db.execute('SELECT * FROM '+t)) for t in tables}
        migrate(db)
        assert before=={t:list(db.execute('SELECT * FROM '+t)) for t in tables}
        for table in ['review_events','reconciliation_decisions','finding_adjustment_events']:
            for sql in [f'DELETE FROM {table}',f'UPDATE {table} SET id=id']:
                with pytest.raises(sqlite3.IntegrityError,match='append-only'):db.execute(sql)
        assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'


def test_concurrent_correction_creation_is_atomic():
    from concurrent.futures import ThreadPoolExecutor
    body={'actor_id':'st-01','note':'Receipt reconciliation','authority':'D14/D15/D21'}
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses=list(pool.map(lambda _:client.post('/api/reconciliations/business.receipts/adjustment',json=body),range(2)))
    assert sorted(r.status_code for r in responses)==[201,409]
    assert len(client.get('/api/adjustments').json()['adjustments'])==1
    assert len(finding('business.receipts')['adjustment_links'])==1


def test_resolved_review_requires_an_actual_resolution_disposition():
    item=finding('business.receipts')
    response=decision(item['id'],status='resolved',disposition='investigating')
    assert response.status_code==400
    assert history(item['id'])['events']==[]


def test_california_payment_correction_uses_packet_one_to_one_rule():
    response=client.post('/api/reconciliations/payments.ca_estimates/adjustment',json={'actor_id':'st-01','note':'Exclude payment designated to 2024.','authority':'FTB 2025 account postings.'})
    assert response.status_code==201,response.text
    adjustment=response.json()
    assert adjustment['payload']['proposed_value']=='10500.00'
    assert adjustment['payload']['effect']['method']=='packet_one_to_one'
    assert adjustment['payload']['effect']['california_payment']=='-3500.00'
    assert adjustment['payload']['effect']['california_tax']=='0.00'
    assert adjustment['payload']['effect']['federal_tax']=='0.00'


def test_unknown_version_correction_is_404_without_partial_draft():
    response=client.post('/api/reconciliations/business.receipts/adjustment?version=nope',json={'actor_id':'st-01','note':'No valid baseline','authority':'No baseline'})
    assert response.status_code==404
    assert client.get('/api/adjustments').json()['adjustments']==[]
