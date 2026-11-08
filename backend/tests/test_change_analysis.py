"""Phase 5 acceptance: immutable snapshots, no speculative aggregation, time-safe evidence."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import hashlib,json,sqlite3
import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from app.security import Settings,redact
from app.services.packet_service import load_packet,DATA_PATH
from app.services import change_analysis_service as service,workflow_service as workflow
from app.services.timeline_service import HistoricalContext,instant
from app.security_context import request_principal

ORIGIN='http://localhost:3200'
@pytest.fixture
def clients(tmp_path,monkeypatch):
    monkeypatch.setenv('REVIEW_DB_PATH',str(tmp_path/'phase5.db'));app=create_app(Settings('demo','test',(ORIGIN,)));clients={}
    for identifier in ('st-01','st-02','st-03','st-04','st-05'):
        c=TestClient(app);token=c.get('/api/workflow/session').json()['csrf_token']
        r=c.post('/api/workflow/session',json={'staff_id':identifier},headers={'origin':ORIGIN,'x-csrf-token':token});assert r.status_code==200,r.text
        c.headers.update({'origin':ORIGIN,'x-csrf-token':r.json()['csrf_token']});clients[identifier]=c
    return clients

def get(c,path):
    r=c.get('/api/'+path);assert r.status_code==200,r.text;return r.json()
def post(c,path,data,code=200):
    r=c.post('/api/'+path,json=data);assert r.status_code==code,r.text;return r.json()
def preparation(c,area='business'):
    return post(c,'workflow/records',{'area':area,'record_type':'preparation','title':'Phase 5 source review','applicability':'applicable','answer':'Compare source evidence without overwriting stored values','authority':'Supplied packet comparison','refs':['D14'],'expected_revision':0})
def sign(c,area='business'):
    p=get(c,'workflow/signoff-preview?area='+area)
    return post(c,'workflow/signoffs',{'area':area,'level':'reviewer','expected_digest':p['digest'],'note':'Independent demonstration review'})

@pytest.mark.parametrize('before,after',[('v1','v2'),('v2','v3'),('v1','v3'),('v3','v1'),('v2','v2')])
def test_actual_version_comparison_and_matrix(clients,before,after):
    packet=deepcopy(load_packet());result=get(clients['st-01'],f'version-comparison?before={before}&after={after}')
    a={l['key']:l for l in next(v for v in packet['return_versions'] if v['version']==before)['lines']};b={l['key']:l for l in next(v for v in packet['return_versions'] if v['version']==after)['lines']}
    expected_a,expected_b=redact(a),redact(b)
    assert len(result['lines'])==len(a.keys()|b.keys())
    for line in result['lines']:
        key=line['key'];assert line['old']==expected_a.get(key) and line['new']==expected_b.get(key)
        assert line['change']==('added' if key not in a else 'removed' if key not in b else 'changed' if a[key]!=b[key] else 'unchanged')
    assert all(set(row['values'])=={'v1','v2','v3'} for row in result['version_matrix'])
    if before==after:assert result['counts']['changed']==0
    assert packet==load_packet()


def test_missing_changed_text_zero_and_sign_comparisons():
    left={'lines':[{'key':'A','label':'Tax','value':-100},{'key':'B','label':'Rate','value':0},{'key':'C','label':'Text','value':'old'},{'key':'E','label':'Removed','value':8}]}
    right={'lines':[{'key':'A','label':'Tax','value':-125},{'key':'B','label':'Rate','value':0.5},{'key':'C','label':'Text','value':'new'},{'key':'D','label':'Added','value':9}]}
    rows={r['key']:r for r in service.compare_lines(left,right)}
    assert rows['A']['numeric_difference']=='-25' and rows['A']['percent_difference']=='-25.00'
    assert rows['B']['percent_difference'] is None and rows['B']['dollar_difference'] is None
    assert rows['C']['numeric_difference'] is None and rows['E']['change']=='removed' and rows['D']['change']=='added'
    assert rows['D']['numeric_difference'] is None
    right['changes_from_previous']=[{'key':'A','change':'added','new':999}]
    assert next(r for r in service.compare_lines(left,right) if r['key']=='A')['change']=='changed'


def test_diff_uses_actual_lines_not_declared_delta(clients):
    result=get(clients['st-01'],'version-comparison?before=v1&after=v2')
    row=next(l for l in result['lines'] if l['key']=='F8949.D.M14')
    # Verify the declared addition against both stored snapshots.
    assert row['change']=='added' and row['reasons']['declared_changes'][0]['change']=='added'
    assert row['support']['v2']['document_ids']
    assert result['diagnostics'] and result['findings'] and set(result['adjustments'])=={'v1','v2'}

@pytest.mark.parametrize('identifier,fd,ca',[('equipment_section179',0,-1050),('equipment_no_bonus',10245,-260),('hvac_improvement',3633,896),('standard_deduction',12306,0),('penalty_annualized',0,0)])
def test_supplied_scenario_exact_results(clients,identifier,fd,ca):
    result=post(clients['st-01'],'what-if/compare',{'version':'v3','scenario_ids':[identifier]})
    a=result['selected'][0];assert a['compatible'] and a['federal']['total_tax_change']==fd and a['california']['total_tax_change']==ca
    assert a['classification']=='stored_engine_alternative' and not a['authoritative_calculation']
    assert result['combined_result'] is None

@pytest.mark.parametrize('version',['v1','v2'])
def test_wrong_scenario_baseline_is_explicit(clients,version):
    result=post(clients['st-01'],'what-if/compare',{'version':version,'scenario_ids':['equipment_section179']})
    assert not result['selection_valid'] and not result['selected'][0]['compatible']
    post(clients['st-01'],'what-if/analyses',{'version':version,'scenario_ids':['equipment_section179'],'note':'Unsupported baseline','expected_revision':0},409)


def test_conflicts_unknown_and_nonadditive_interactions(clients):
    c=clients['st-01']
    conflict=post(c,'what-if/compare',{'scenario_ids':['equipment_section179','equipment_no_bonus']})
    assert conflict['conflicts'][0]['choices']==['equipment'] and not conflict['selection_valid']
    supported=post(c,'what-if/compare',{'scenario_ids':['equipment_section179','standard_deduction']})
    assert supported['selection_valid'] and supported['combined_result'] is None and any('No combined' in w for w in supported['warnings'])
    unknown=post(c,'what-if/compare',{'scenario_ids':['invented_tax_result']})
    assert unknown['unknown']==['invented_tax_result'] and not unknown['selection_valid']
    post(c,'what-if/analyses',{'scenario_ids':['equipment_section179','equipment_no_bonus'],'note':'Cannot sum','expected_revision':0},409)


def test_scenario_persistence_revision_audit_and_no_tax_mutation(clients):
    c=clients['st-01'];before=get(c,'return-lines');summary=get(c,'workpaper-summary')
    body={'scenario_ids':['equipment_section179'],'note':'Considering election only','expected_revision':0}
    a=post(c,'what-if/analyses',body);assert a['state']=='hypothetical'
    history=get(clients['st-02'],'what-if/analyses');assert history['analyses'][0]['id']==a['id']
    revised=post(c,'what-if/analyses',{**body,'id':a['id'],'expected_revision':1,'note':'Revised analysis notes only'})
    assert revised['revision']==2 and len(get(c,'what-if/analyses')['events'])==2
    post(c,'what-if/analyses',{**body,'id':a['id'],'expected_revision':1},409)
    assert get(c,'return-lines')==before and get(c,'workpaper-summary')==summary
    with workflow.connection() as db:
        with pytest.raises(sqlite3.IntegrityError):db.execute("DELETE FROM workflow_events WHERE kind='scenario_analysis'")

@pytest.mark.parametrize('at,version,visible,hidden',[
 ('2026-01-12T17:03:59Z',None,[],['D01']),('2026-01-12T17:04:00Z',None,['D01'],['D06']),
 ('2026-03-04T09:11:59Z',None,['D30'],['D31','D37','D72']),
 ('2026-03-04T09:12:00Z','v1',['D30'],['D31','D37','D72']),
 ('2026-03-18T21:08:59Z','v1',['D30'],['D31']),
 ('2026-03-18T21:09:00Z','v1',['D31'],['D37']),
 ('2026-03-19T07:40:00Z','v2',['D31'],['D37','D71','D72']),
 ('2026-06-23T06:05:00Z','v3',['D37','D38'],['D71','D72']),
 ('2026-07-13T19:02:00Z','v3',['D71'],['D72']),
 ('2028-01-26T15:00:00Z','v3',['D72'],[])])
def test_timeline_exact_boundaries(clients,at,version,visible,hidden):
    result=get(clients['st-01'],'timeline-replay?at='+at)
    assert result['active_version']==version
    ids={d['id'] for d in result['documents']};assert set(visible)<=ids and not set(hidden)&ids
    assert all(instant(e['at'])<=instant(at) for e in result['events'])
    assert not result['changes_current_state']
    assert all(not e['completes_live_workflow'] for e in result['events'])

@pytest.mark.parametrize('ref',['D72','doc:D72#page1','future_extracted','agency:/notices/1','agency:/efile/2','agency:/irs_account_transcript_2025/1','timeline:tl-29','msg-10','call-01','qa-45','asset:STU-PRINTER'])
def test_historical_nested_future_evidence_not_exposed(clients,ref):
    at='2026-01-20T04:00:00Z' if ref=='future_extracted' else '2026-03-04T09:12:00Z'
    # A received document is required even when an extracted field already exists in the full packet.
    if ref=='future_extracted':
        packet=load_packet();future=next(e['id'] for e in packet['extracted_values'] if e['document_id']=='D37');ref=future
    if ref=='asset:STU-PRINTER':at='2026-01-19T00:00:00Z'
    if ref=='qa-45':at='2026-01-19T00:00:00Z'
    g=get(clients['st-01'],f'timeline-replay/evidence?at={at}&ref={ref}')
    assert g['resolution']['status']=='unresolved' and g['resolution']['value'] is None and not g['document_ids']
    assert '2028-02-19' not in json.dumps(g)


def test_agency_parent_does_not_expose_future_accepted_events(clients):
    g=get(clients['st-01'],'timeline-replay/evidence?at=2026-07-13T17:04:00Z&ref=agency:/efile')
    assert g['resolution']['status']=='resolved'
    text=json.dumps(g);assert 'accepted' not in text and '71530420261950019871' not in text
    assert 'rejected' in text


def test_historical_replay_does_not_change_live_workflow(clients):
    c=clients['st-02'];before=get(c,'workflow/overview');ready=get(c,'workflow/readiness')
    snapshot=get(c,'timeline-replay?at=2028-02-01T00:00:00Z')
    assert any(e['event']=='efile_accepted_federal' for e in snapshot['events'])
    after=get(c,'workflow/overview');assert before['signoffs']==after['signoffs'] and before['records']==after['records']
    assert not get(c,'workflow/readiness')['filing_ready'] and not ready['filing_ready']
    past=get(c,'timeline-replay?at=2026-06-23T06:05:00Z');assert past['review_activity']==[] and past['workflow_activity']==[]


def test_impact_preview_actual_invalidation_and_unrelated_area(clients):
    c=clients['st-01'];reviewer=clients['st-02'];preparation(c);preparation(c,'payments');b=sign(reviewer);p=sign(reviewer,'payments')
    preview=get(c,'change-impact?ref=SchC.1');assert 'SchC.31' in preview['affected_lines'] and 'business' in preview['areas']
    assert next(a for a in get(c,'workflow/overview')['signoffs'] if a['id']==b['id'])['state']=='valid'
    post(c,'what-if/analyses',{'scenario_ids':['equipment_section179'],'note':'Hypothetical only','expected_revision':0})
    assert next(a for a in get(c,'workflow/overview')['signoffs'] if a['id']==b['id'])['state']=='valid'
    from app.services.adjustment_service import metadata
    post(c,'adjustments',{'actor_id':'st-01',**metadata('v3')['demo']},201)
    states={a['id']:a['state'] for a in get(c,'workflow/overview')['signoffs']}
    assert states[b['id']]=='invalidated' and states[p['id']]=='valid'
    post(reviewer,'change-impact/reassess',{'version':'v3','refs':['SchC.1'],'note':'Reviewed actual source change'})
    assert any(e['kind']=='impact' for e in get(c,'change-impact?ref=SchC.1')['events'])


def test_resolved_review_reassessed_without_overwriting_history(clients):
    c=clients['st-01'];r=clients['st-02'];preparation(c)
    finding=next(f for f in get(r,'unified-findings')['findings'] if f['issue_key']=='business.receipts')
    post(r,'reconciliation-decision?finding_id='+finding['id'],{'actor_id':'st-02','status':'resolved','note':'Documented investigation; stored engine remains unchanged','authority':'Supplied business receipts source comparison','disposition':'professional_judgment','refs':['D14','D15','D21']})
    report=get(r,'change-impact?ref=SchC.1');a=next(a for a in report['assessments'] if a['data']['finding_id']==finding['id']);assert a['state']=='current'
    from app.services.adjustment_service import metadata
    post(c,'adjustments',{'actor_id':'st-01',**metadata('v3')['demo']},201)
    report=get(r,'change-impact?ref=SchC.1');a=next(a for a in report['assessments'] if a['data']['finding_id']==finding['id']);assert a['state']=='needs_reassessment'
    stored=next(f for f in get(r,'reviews')['findings'] if f['id']==finding['id']);assert stored['status']=='resolved'
    assert any(b['code']=='REVIEW_REASSESSMENT_REQUIRED' for b in get(r,'workflow/readiness')['blockers'])
    assert get(r,'review-history?finding_id='+finding['id'])['events']

@pytest.mark.parametrize('path',['version-comparison','what-if','what-if/analyses','timeline-replay?at=2026-06-23','timeline-replay/evidence?at=2026-06-23&ref=D03','change-impact'])
def test_phase5_authorization_and_redaction(clients,path):
    assert TestClient(clients['st-01'].app).get('/api/'+path).status_code==401
    assert clients['st-05'].get('/api/'+path).status_code==403
    assert clients['st-04'].get('/api/'+path).status_code==403
    r=clients['st-01'].get('/api/'+path);assert r.status_code==200,r.text
    assert 'no-store' in r.headers['cache-control']
    assert '482915' not in r.text and '666-41-2287' not in r.text


def test_missing_inputs_and_security_malformed_requests(clients):
    c=clients['st-01'];assert c.get('/api/version-comparison?before=unknown').status_code==404
    assert c.get('/api/timeline-replay?at=not-a-date').status_code==400
    assert c.get('/api/timeline-replay?at=2026-06-23T01:00:00').status_code==400
    assert c.post('/api/what-if/analyses',json={'actor_id':'st-03'}).status_code==403
    assert c.post('/api/what-if/compare',json={},headers={'x-csrf-token':'wrong'}).status_code==403
    assert get(c,'change-impact?ref=unknown')['unresolved']==['unknown']
    malformed=c.post('/api/what-if/compare',json=['666-99-1234'])
    assert malformed.status_code==422 and '666-99-1234' not in malformed.text


def test_packet_and_database_integrity(clients):
    assert hashlib.sha256(DATA_PATH.read_bytes()).hexdigest()=='ee01f8508bd2fd9854754b82fd9c4a055bdc55e2778a132002a25381c412ad19'
    with workflow.connection() as db:
        assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert not db.execute('PRAGMA foreign_key_check').fetchall()

def test_source_documents_are_inspectable_before_first_engine_run(clients):
    early=get(clients['st-01'],'timeline-replay/evidence?at=2026-01-12T17:04:00Z&ref=D01')
    assert early['resolution']['status']=='resolved' and early['resolution']['version']=='none'
    assert early['document_ids']==['D01']
    unseen=get(clients['st-01'],'timeline-replay/evidence?at=2026-01-12T17:03:59Z&ref=D01')
    assert unseen['resolution']['status']=='unresolved'


def test_historical_version_corrections_exclude_future_runs(clients):
    c=clients['st-01'];first=get(c,'timeline-replay?at=2026-03-04T09:12:00Z');assert first['corrections']==[]
    second=get(c,'timeline-replay?at=2026-03-19T07:40:00Z');assert second['corrections']
    assert all(change['after']=='v2' for change in second['corrections'])
    assert all(instant(change['at'])<=instant(second['as_of']) for change in second['corrections'])


def test_nested_future_dependencies_withhold_historical_line_value():
    packet=deepcopy(load_packet());line=next(l for l in packet['return_versions'][0]['lines'] if l['key']=='SchC.1')
    line['sources']=['msg-10'];context=HistoricalContext('2026-03-04T09:12:00Z',packet)
    result=context.resolve('SchC.1');assert result.status=='unresolved' and result.value is None
    assert 'msg-10' not in json.dumps(context.evidence('SchC.1'))

@pytest.mark.parametrize('identifier',['CL-20417','membership:st-03','required:0','membership:st-06'])
def test_hypothetical_analysis_cannot_overwrite_or_reserve_workflow_entities(clients,identifier):
    before=get(clients['st-01'],'workflow/overview')
    post(clients['st-01'],'what-if/analyses',{'id':identifier,'scenario_ids':['equipment_section179'],'note':'Attempt unsafe entity reuse','expected_revision':1},404 if identifier=='membership:st-06' else 409)
    after=get(clients['st-01'],'workflow/overview')
    assert before['engagement']==after['engagement'] and before['memberships']==after['memberships'] and before['records']==after['records']

def test_duplicate_diagnostic_identities_are_not_discarded():
    items=[{'code':'LOW','refs':['D31'],'message':'One field'},{'code':'LOW','refs':['D31'],'message':'Another field'}]
    diff=service.collection_diff(items,items[:1],lambda x:x['code']+str(x['refs']))
    assert len(diff)==2 and sum(d['change']=='removed' for d in diff)==1


def resolve_receipts(c):
    f=next(f for f in get(c,'unified-findings')['findings'] if f['issue_key']=='business.receipts')
    post(c,'reconciliation-decision?finding_id='+f['id'],{'actor_id':'st-02','status':'resolved','note':'Independent documented current source comparison','authority':'Packet source evidence','disposition':'professional_judgment','refs':['D14','D15','D21']})
    return f


def test_unrelated_adjustment_preserves_review_binding_then_fresh_resolution_is_required(clients):
    c=clients['st-01'];r=clients['st-02'];finding=resolve_receipts(r)
    from app.services.adjustment_service import metadata,version_data
    payment=next(l for l in version_data('v3')['lines'] if l['key']=='F1040.26')
    post(c,'adjustments',{**metadata('v3')['demo'],'actor_id':'st-01','target':'F1040.26','proposed_value':str(payment['value']+100),'refs':['D69']},201)
    current=next(a for a in get(r,'change-impact?ref=SchC.1')['assessments'] if a['data']['finding_id']==finding['id'])
    assert current['state']=='current'
    post(c,'adjustments',{'actor_id':'st-01',**metadata('v3')['demo']},201)
    stale=next(f for f in get(r,'unified-findings')['findings'] if f['id']==finding['id'])
    assert stale['status']=='resolved' and stale['review_validity']['state']=='needs_reassessment'
    resolve_receipts(r)
    fresh=next(f for f in get(r,'unified-findings')['findings'] if f['id']==finding['id'])
    assert fresh['review_validity']['state']=='current'
    events=get(r,'review-history?finding_id='+finding['id'])['events'];assert len(events)==2


def test_simultaneous_analysis_edits_preserve_every_revision(clients):
    c=clients['st-01'];a=post(c,'what-if/analyses',{'scenario_ids':['standard_deduction'],'note':'Initial hypothetical comparison','expected_revision':0})
    def edit(i):return c.post('/api/what-if/analyses',json={'id':a['id'],'scenario_ids':['standard_deduction'],'note':f'Concurrent review {i}','expected_revision':1}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:assert sorted(pool.map(edit,[1,2]))==[200,409]
    events=get(c,'what-if/analyses')['events'];assert len(events)==2

def test_historical_version_reference_is_typed_without_future_payload(clients):
    known=get(clients['st-01'],'timeline-replay/evidence?at=2026-03-04T09:12:00Z&ref=v1')
    assert known['resolution']['type']=='return_version' and known['resolution']['value']['version']=='v1'
    future=get(clients['st-01'],'timeline-replay/evidence?at=2026-03-04T09:12:00Z&ref=v3')
    assert future['resolution']['status']=='unresolved' and future['resolution']['value'] is None

def test_actual_verification_activity_is_replayed_only_after_it_was_recorded(clients):
    from app.services.source_verification_service import get_source_verification
    c=clients['st-02'];match=get_source_verification('ev-0016')['match']
    post(c,'field-verifications/ev-0016',{'verifier_id':'st-02','method':'agreed_to_source_document','source_ref':'doc:D08#page1','status':'confirmed','notes':'Actual review recorded now, not in scripted March season','expected_sequence':0,'quote':{'start':match['start'],'end':match['end'],'text':match['matched_text']}},201)
    assert get(c,'timeline-replay?at=2026-06-23T06:05:00Z')['verification_activity']==[]
    later=get(c,'timeline-replay?at=2028-02-01T00:00:00Z')['verification_activity']
    assert len(later)==1 and later[0]['evidence_id']=='ev-0016' and later[0]['verifier_id']=='st-02'
