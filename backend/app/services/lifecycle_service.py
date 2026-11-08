"""Auditable simulator. No agency transport, authenticated client, or legal signature adapter."""
from copy import deepcopy
from datetime import datetime,timedelta,timezone,date
from decimal import Decimal,ROUND_CEILING
from uuid import uuid4
import hashlib,json

from app.services import workflow_service as w
from app.services.adjustment_service import fail,AdjustmentError,read_one,version_data,packet_hash,summary_from_items,money
from app.services.packet_service import load_packet
from app.services.evidence_service import resolve_reference

DISCLAIMER='DEMONSTRATION ONLY — no agency submission, payment transfer, authenticated client identity or legally valid electronic signature.'
KINDS={'lc_snapshot_validity','lc_filing','lc_authorization','lc_extension','lc_payment','lc_amendment','lc_notice','lc_carryover','lc_handoff','lc_delivery'}


def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True)
def digest(value):return hashlib.sha256(canonical(value).encode()).hexdigest()
def when(value):
    try:
        result=datetime.fromisoformat(value.replace('Z','+00:00'))
        if result.tzinfo is None:raise ValueError()
        return result.astimezone(timezone.utc)
    except (ValueError,TypeError):fail('Timestamp must be ISO-8601 with a timezone')
def valid_date(value):
    try:return date.fromisoformat(value).isoformat()
    except (ValueError,TypeError):fail('An ISO calendar date is required')
def access(db,actor):
    w.require_access(db,actor,'engagement')
    if actor['role'] not in w.PRACTICE_ROLES:fail('Assigned tax-practice staff required',403)
def peer(db,actor,authors,partner=False):
    access(db,actor)
    if actor['role'] not in ({'partner'} if partner else {'reviewer','partner'}):fail('Independent partner required' if partner else 'Independent reviewer required',403)
    if actor['id'] in authors:fail('A preparer cannot approve their own lifecycle work',403)
def record(db,identifier,kind):
    item=w.entity(db,identifier)
    if not item or item['kind']!=kind:fail('Lifecycle record not found',404)
    return item
def save(db,actor,item,state,data,action,expected):
    return w.put(db,item['id'],item['kind'],item['area'],state,data,item['authors'],actor['id'],action,expected)
def create(db,actor,kind,data,state='draft',authors=None):
    return w.put(db,kind+':'+uuid4().hex,kind,'engagement',state,{**data,'simulation_only':True,'legal_signature':False},authors or [actor['id']],actor['id'],'created',0)
def check_revision(item,expected):
    if item['revision']!=expected:fail('Lifecycle record changed; reload before acting',409)
def refs_valid(refs,version='v3'):
    if not refs or any(resolve_reference(r,version).status!='resolved' for r in refs):fail('Resolved supporting evidence is required')
def assignments(db):return [e for e in w.entities(db,'membership') if e['state']=='active']
def version_items(db,version):return [read_one(db,r[0]) for r in db.execute('SELECT id FROM adjustments WHERE version=? ORDER BY id',(version,))]


def dependencies(db,version):
    return {'workpaper':w.manifest(db,'engagement'),'version':version,'packet_sha256':packet_hash(),
            'adjustments':version_items(db,version),
            'reviews':[dict(r) for r in db.execute('SELECT * FROM reviews WHERE version=? ORDER BY finding_id',(version,))],
            'decisions':[dict(r) for r in db.execute('SELECT * FROM reconciliation_decisions WHERE version=? ORDER BY id',(version,))],
            'verifications':[dict(r) for r in db.execute('SELECT * FROM field_verification_events WHERE version=? ORDER BY id',(version,))],
            'links':[dict(r) for r in db.execute('SELECT * FROM finding_adjustment_events WHERE version=? ORDER BY id',(version,))],
            'financial_evidence':[e for e in w.entities(db) if e['kind']=='lc_payment' or e['kind']=='lc_carryover' and e['data']['version']==version]}


def snapshot(db,identifier):
    row=db.execute('SELECT * FROM lifecycle_snapshots WHERE id=?',(identifier,)).fetchone()
    if not row:fail('Frozen snapshot not found',404)
    result=dict(row);result['content']=json.loads(result.pop('content_json'));result['dependencies']=json.loads(result.pop('dependency_json'))
    return result


def current(db,s):
    state=w.entity(db,'validity:'+s['id'])
    return bool(state and state['state']=='current' and digest(dependencies(db,s['version']))==digest(s['dependencies']))
def require_current(db,s):
    if not current(db,s):fail('Snapshot dependencies changed or it was superseded; freeze and authorize a fresh snapshot',409)
def snapshot_public(db,s,include=False):
    result={k:s[k] for k in ('id','content_hash','version','purpose','mode','parent_id','created_by','created_at')}
    state=w.entity(db,'validity:'+s['id']);result.update(display_name=s['content']['note'][:120],validity=state['state'] if state else 'unbound',simulation_only=s['mode']=='demonstration',legal_signature=False)
    if include:result.update(content=s['content'],dependencies=s['dependencies'])
    return result


def freeze(db,actor,data,readiness,purpose='return',parent=None):
    access(db,actor);version=data['version'];base=deepcopy(version_data(version))
    mode=data['mode']
    if mode=='authoritative' and (not readiness['filing_ready'] or actor['assurance']=='demonstration'):
        fail('Authoritative finalization is blocked: actual final-return and client-authorization prerequisites are not satisfied',409)
    if mode!='demonstration':fail('No authoritative return/signature adapter is configured',409)
    if readiness['digest']!=w.digest(w.manifest(db,'engagement')):fail('Readiness dependencies changed during finalization; reload',409)
    refs_valid(data['refs'],version)
    if not data['note'].strip():fail('Finalization rationale is required')
    deps=dependencies(db,version);items=version_items(db,version)
    approved=[a for a in items if a['state']=='approved' and not a['stale']]
    content={'classification':'demonstration_frozen_workpaper_not_authoritative_return','disclaimer':DISCLAIMER,
             'packet_sha256':packet_hash(),'tax_year':load_packet()['household']['tax_year'],'version':version,'purpose':purpose,'parent_id':parent,
             'engine_baseline':base,'approved_adjustments':approved,'estimated_summary':summary_from_items(version,items),
             'evidence_refs':sorted({r for l in base['lines'] for r in l.get('sources',[])}|set(data['refs'])),
             'evidence_bundle':deepcopy(load_packet()),
             'evidence_classification':'Invented case-study packet; later filing/notice records are scripted, not live confirmations.',
             'firm_policy_history':[dict(r) for r in db.execute('SELECT * FROM workflow_policies ORDER BY revision')],
             'reconciliation_decisions':deps['decisions'],'review_history':[dict(r) for r in db.execute('SELECT * FROM review_events WHERE version=? ORDER BY id',(version,))],
             'workflow_approvals':deps['workpaper'],'financial_evidence':deps['financial_evidence'],
             'readiness':{k:readiness[k] for k in ('filing_ready','blockers','legal_signature','assurance','label')},
             'note':data['note'],'correction_refs':data['refs'],'contributors':sorted(w.contributors(db,'engagement')|{actor['id']})}
    from app.services.product_service import snapshot_evidence,evidence_dependencies
    if evidence_dependencies(db,'engagement'):content['supplemental_evidence']=snapshot_evidence(db)
    fingerprint=digest({'content':content,'dependencies':deps})
    for existing in db.execute('SELECT id FROM lifecycle_snapshots WHERE content_hash=? ORDER BY created_at DESC,id',(fingerprint,)):
        validity=w.entity(db,'validity:'+existing[0])
        if validity and validity['state']=='current':return snapshot(db,existing[0])
    identifier='snapshot:'+uuid4().hex
    db.execute('INSERT INTO lifecycle_snapshots VALUES(?,?,?,?,?,?,?,?,?,?)',(identifier,fingerprint,version,purpose,mode,parent,canonical(content),canonical(deps),actor['id'],w.now()))
    w.put(db,'validity:'+identifier,'lc_snapshot_validity','engagement','current',{'snapshot_id':identifier,'reason':'Dependencies bound at freeze.'},[],actor['id'],'frozen',0)
    w.event(db,identifier,'snapshot','frozen',actor['id'],{'content_hash':fingerprint,'mode':mode,'purpose':purpose,'parent_id':parent,'legal_signature':False})
    return snapshot(db,identifier)


def finalize(actor,data):
    readiness=stabilized_readiness(actor)
    with w.connection() as db:
        if data.get('supersedes_id'):
            old=snapshot(db,data['supersedes_id'])
            if any(e['state']=='accepted' and e['data']['snapshot_id']==old['id'] for e in w.entities(db,'lc_filing')):fail('Preserve the accepted original; create an amendment instead',409)
        s=freeze(db,actor,data,readiness)
        if data.get('supersedes_id') and data['supersedes_id']!=s['id']:
            validity=record(db,'validity:'+data['supersedes_id'],'lc_snapshot_validity')
            if validity['state']=='current':save(db,actor,validity,'superseded',{**validity['data'],'successor_id':s['id']},'superseded',validity['revision'])
        return snapshot_public(db,s,True)


def bound_control(db,kind,data):
    if kind=='lc_extension':return digest({'packet':packet_hash(),'version':data['version'],'adjustments':version_items(db,data['version']),'payment_evidence':[p for p in w.entities(db,'lc_payment') if p['data']['jurisdiction']==data['jurisdiction'] and p['data']['tax_year']==2025],'policy':w.active_policy(db),'assignments':assignments(db)})
    if kind=='lc_notice':return digest({'snapshot':snapshot(db,data['snapshot_id'])['content_hash'],'response':data.get('response'),'refs':data['refs'],'packet':packet_hash(),'policy':w.active_policy(db),'assignments':assignments(db)})
    if kind=='lc_amendment':return digest({'snapshot':snapshot(db,data['snapshot_id'])['content_hash'],'policy':w.active_policy(db),'assignments':assignments(db)})
    if kind=='lc_handoff':return digest({'snapshot':data['snapshot_id'],'carryovers':[c for c in w.entities(db,'lc_carryover') if c['data']['snapshot_id']==data['snapshot_id']],'notes':data['notes'],'owner_id':data['owner_id'],'policy':w.active_policy(db),'assignments':assignments(db)})
    return None


def invalidate(db,actor):
    """Part of the originating write transaction; frozen content is never edited."""
    rows=db.execute('SELECT id,version,dependency_json FROM lifecycle_snapshots').fetchall()
    current_deps={}
    for row in rows:
        validity=w.entity(db,'validity:'+row['id'])
        if not validity or validity['state']!='current':continue
        if row['version'] not in current_deps:current_deps[row['version']]=digest(dependencies(db,row['version']))
        if current_deps[row['version']]!=digest(json.loads(row['dependency_json'])):
            save(db,actor,validity,'invalidated',{**validity['data'],'reason':'Bound workpaper dependencies changed. Historical content is preserved.'},'invalidated',validity['revision'])
    for item in w.entities(db):
        if item['kind']=='lc_authorization' and item['state'] in {'requested','partially_approved','approved'}:
            s=snapshot(db,item['data']['snapshot_id']);reason='expired' if when(item['data']['expires_at'])<=datetime.now(timezone.utc) else 'snapshot_changed' if not current(db,s) else None
            if reason:save(db,actor,item,'invalidated',{**item['data'],'invalidation_reason':reason},'invalidated',item['revision'])
        elif item['kind']=='lc_filing' and item['state']=='ready_for_submission':
            try:filing_controls(db,item)
            except AdjustmentError:
                save(db,actor,item,'draft',{**item['data'],'approval_valid':False,'invalidation_reason':'Snapshot, authorization or required amendment approval changed.'},'approval_invalidated',item['revision'])
        elif item['kind']=='lc_handoff' and item['state']=='handed_off' and item['data'].get('approval_valid') and bound_control(db,item['kind'],item['data'])!=item['data'].get('approval_digest'):
            save(db,actor,item,'handed_off',{**item['data'],'approval_valid':False,'needs_successor_handoff':True},'published_handoff_stale',item['revision'])
            w.notify(db,item['data']['owner_id'],'Published handoff requires a fresh review after carryover changes',item['id'],'stale-handoff:'+item['id'])
        elif item['kind'] in {'lc_extension','lc_notice','lc_amendment','lc_handoff'} and item['data'].get('approval_digest') and item['state'] in {'approved','reviewed'}:
            stale=bound_control(db,item['kind'],item['data'])!=item['data']['approval_digest']
            if item['kind']=='lc_amendment':stale=stale or not current(db,snapshot(db,item['data']['snapshot_id']))
            if stale:save(db,actor,item,'needs_review',{**item['data'],'approval_valid':False},'approval_invalidated',item['revision'])


def authorize_request(actor,data):
    with w.connection() as db:
        access(db,actor);s=snapshot(db,data['snapshot_id']);require_current(db,s)
        expiry=when(data['expires_at'])
        if expiry<=datetime.now(timezone.utc):fail('Authorization expiry must be in the future')
        previous=[a for a in w.entities(db,'lc_authorization') if a['data']['snapshot_id']==s['id'] and a['state'] in {'requested','partially_approved','approved'}]
        result=create(db,actor,'lc_authorization',{'snapshot_id':s['id'],'content_hash':s['content_hash'],'version':s['version'],
            'client_ids':[c['id'] for c in load_packet()['firm']['client_users']],'responses':{},'expires_at':expiry.isoformat(),'note':data['note'],
            'client_identity_assurance':'declared_client_demonstration_only','real_external_authorization':False},'requested')
        for old in previous:save(db,actor,old,'invalidated',{**old['data'],'invalidation_reason':'superseded_by_new_request','successor_id':result['id']},'superseded',old['revision'])
        return result


def client_review(actor,identifier):
    with w.connection() as db:
        access(db,actor);a=record(db,identifier,'lc_authorization');s=snapshot(db,a['data']['snapshot_id'])
        return {'request':a,'snapshot':{k:s[k] for k in ('id','content_hash','version','mode')},'summary':s['content']['estimated_summary'],
                'return_review':{'engine_original_lines':s['content']['engine_baseline']['lines'],'approved_estimated_adjustments':s['content']['approved_adjustments'],'warning':'Original engine lines and approved estimates are separate; no authoritative corrected forms are generated.'},
                'clients':load_packet()['firm']['client_users'],'disclaimer':DISCLAIMER,'legal_signature':False,'client_authenticated':False,
                'currently_eligible':current(db,s) and when(a['data']['expires_at'])>datetime.now(timezone.utc) and a['state']!='invalidated'}


def client_respond(actor,identifier,data):
    with w.connection() as db:
        access(db,actor);a=record(db,identifier,'lc_authorization');check_revision(a,data['expected_revision'])
        require_current(db,snapshot(db,a['data']['snapshot_id']))
        if a['state'] not in {'requested','partially_approved'} or when(a['data']['expires_at'])<=datetime.now(timezone.utc):fail('Authorization is expired, invalidated or complete',409)
        if data['client_id'] not in a['data']['client_ids']:fail('Client ID is not part of this joint return',403)
        if data['client_id'] in a['data']['responses']:fail('Response is immutable; issue a new request to change it',409)
        refs_valid(data['refs'],a['data']['version'])
        responses={**a['data']['responses'],data['client_id']:{'decision':data['decision'],'note':data['note'],'refs':data['refs'],'recorded_by':actor['id'],'recorded_at':w.now(),'assurance':'declared_client_demo','legal_signature':False}}
        state='declined' if data['decision']=='decline' else 'approved' if all(responses.get(c,{}).get('decision')=='approve' for c in a['data']['client_ids']) else 'partially_approved'
        return save(db,actor,a,state,{**a['data'],'responses':responses},'demo_client_response',a['revision'])


def valid_authorization(db,snapshot_id):
    requests=[a for a in w.entities(db,'lc_authorization') if a['data']['snapshot_id']==snapshot_id and a['state']=='approved' and when(a['data']['expires_at'])>datetime.now(timezone.utc)]
    if not requests:fail('Current snapshot-bound demonstration approval from both packet clients is required',409)
    return sorted(requests,key=lambda a:(a['updated_at'],a['id']))[-1]


def filing_controls(db,item):
    s=snapshot(db,item['data']['snapshot_id']);require_current(db,s);authorization=valid_authorization(db,s['id'])
    if item['data'].get('amendment_id'):
        amendment=record(db,item['data']['amendment_id'],'lc_amendment')
        if amendment['state']!='approved' or amendment['data']['snapshot_id']!=s['id'] or amendment['data']['approval_digest']!=bound_control(db,'lc_amendment',amendment['data']):fail('A current independently reviewed and approved amendment is required',409)
    return s,authorization


def new_filing(actor,data):
    with w.connection() as db:
        access(db,actor);s=snapshot(db,data['snapshot_id']);require_current(db,s)
        amendment=data.get('amendment_id')
        if (s['purpose']=='amendment')!=bool(amendment):fail('Amended snapshots require their separate amendment record')
        if amendment and record(db,amendment,'lc_amendment')['data']['snapshot_id']!=s['id']:fail('Amendment/snapshot mismatch',409)
        if any((f['data']['snapshot_id']==s['id'] or any(a['snapshot_id']==s['id'] for a in f['data'].get('attempts',[]))) and f['data']['jurisdiction']==data['jurisdiction']  for f in w.entities(db,'lc_filing')):fail('A filing record already exists for this snapshot and jurisdiction',409)
        run_id=s['id']
        if amendment:
            parent=record(db,amendment,'lc_amendment')['data']['parent_snapshot_id']
            run_id=next(f['data'].get('simulation_run_id',parent) for f in w.entities(db,'lc_filing') if f['state']=='accepted' and f['data']['snapshot_id']==parent)
        return create(db,actor,'lc_filing',{'simulation_run_id':run_id,'snapshot_id':s['id'],'jurisdiction':data['jurisdiction'],'amendment_id':amendment,'attempts':[],'corrections':[],'approval_valid':False,'note':data['note'],'provider':'local_simulator','real_agency_submission':False})


def filing_action(actor,identifier,data):
    with w.connection() as db:
        access(db,actor);f=record(db,identifier,'lc_filing');check_revision(f,data['expected_revision']);d=deepcopy(f['data']);action=data['action']
        if action=='ready':
            if f['state']!='draft':fail('Only draft filings can be approved for simulated submission',409)
            s,a=filing_controls(db,f);authors=set(s['content']['contributors'])|set(f['authors'])|{r['recorded_by'] for r in a['data']['responses'].values()}
            peer(db,actor,authors,True)
            d.update(approved_by=actor['id'],authorization_id=a['id'],approval_valid=True,approved_at=w.now());state='ready_for_submission'
        elif action=='submit':
            if f['state']!='ready_for_submission' or not d.get('approval_valid'):fail('A current partner-approved ready state is required',409)
            s,a=filing_controls(db,f);approver=w.staff(d['approved_by']);peer(db,approver,set(s['content']['contributors'])|set(f['authors']),True)
            if a['id']!=d['authorization_id']:fail('Authorization changed; fresh partner approval required',409)
            amendment_certificate=deepcopy(record(db,d['amendment_id'],'lc_amendment')) if d.get('amendment_id') else None
            d['attempts'].append({'amendment_approval_snapshot':amendment_certificate,'id':'SIM-'+uuid4().hex,'snapshot_id':s['id'],'content_hash':s['content_hash'],'submitted_at':w.now(),'submitted_by':actor['id'],'status':'submitted','provider':'local_simulator','real_submission':False,'authorization_id':a['id'],'authorization_snapshot':deepcopy(a),'partner_approval':{'staff_id':d['approved_by'],'approved_at':d['approved_at'],'simulation_only':True}});state='submitted'
        elif action in {'simulate_reject','simulate_accept'}:
            peer(db,actor,f['authors'])
            if f['state']!='submitted':fail('Provider outcome must refer to a pending simulated attempt',409)
            attempt=d['attempts'][-1];state='rejected' if action=='simulate_reject' else 'accepted'
            attempt.update(status=state,outcome_at=w.now(),outcome_recorded_by=actor['id'],real_agency_confirmation=False)
            if state=='rejected':
                jurisdiction=d['jurisdiction'];source=next(x for x in load_packet()['tax_agency_records']['efile'] if x['jurisdiction']==jurisdiction and x.get('errors'))
                attempt['errors']=deepcopy(source['errors']);attempt['response_origin']='Local simulated response using packet rejection vocabulary; not a replayed confirmation.'
            else:d['accepted_at']=attempt['outcome_at']
        elif action=='correct':
            if f['state']!='rejected':fail('Corrections require a rejected attempt',409)
            if not data.get('replacement_snapshot_id') or data['replacement_snapshot_id']==d['snapshot_id']:fail('Freeze a distinct corrected snapshot and obtain new client approval before resubmission',409)
            s=snapshot(db,data['replacement_snapshot_id']);require_current(db,s);refs_valid(data['refs'],s['version'])
            if s['purpose']!=snapshot(db,d['snapshot_id'])['purpose']:fail('Cannot change filing type through correction')
            if any(other['id']!=f['id'] and other['data']['snapshot_id']==s['id'] and other['data']['jurisdiction']==d['jurisdiction'] for other in w.entities(db,'lc_filing')):fail('Replacement snapshot already has a filing record',409)
            if d.get('amendment_id'):
                replacement=record(db,data.get('replacement_amendment_id'),'lc_amendment')
                if replacement['state']!='approved' or replacement['data']['snapshot_id']!=s['id'] or replacement['data']['parent_snapshot_id']!=snapshot(db,d['snapshot_id'])['parent_id']:fail('A newly reviewed amendment bound to the same original is required',409)
                d['amendment_id']=replacement['id']
            d['corrections'].append({'previous_snapshot_id':d['snapshot_id'],'replacement_snapshot_id':s['id'],'note':data['note'],'refs':data['refs'],'recorded_by':actor['id'],'at':w.now()})
            d.update(snapshot_id=s['id'],approval_valid=False);state='draft'
        else:fail('Unsupported filing transition')
        d['last_note']=data['note'];return save(db,actor,f,state,d,action,f['revision'])


def extension_prepare(actor,data):
    if data['version']!=load_packet()['what_if']['extension']['based_on_version']:fail('Only the supplied v2 extension estimate is supported',409)
    with w.connection() as db:
        access(db,actor);source=deepcopy(load_packet()['what_if']['extension'][data['jurisdiction']]);balance=Decimal(str(source['estimated_total_tax']))-Decimal(str(source['payments']))
        rounded=(max(balance,Decimal(0))/Decimal(500)).to_integral_value(rounding=ROUND_CEILING)*500
        supplied=source['paid_with_form_4868'] if data['jurisdiction']=='federal' else source['paid_with_ftb_3519']
        if rounded!=Decimal(str(supplied)):fail('Supplied extension result conflicts with its stated method; manual review required',409)
        return create(db,actor,'lc_extension',{'version':data['version'],'jurisdiction':data['jurisdiction'],'estimate':source,'proposed_payment':money(rounded),'method':'max(estimated tax - payments, 0), rounded up to next 500 as supplied by the packet',
            'refs':['timeline:extension-2026-04-14'],'note':data['note'],'approval_valid':False,'real_submission':False},'prepared')


def extension_action(actor,identifier,data):
    with w.connection() as db:
        access(db,actor);e=record(db,identifier,'lc_extension');check_revision(e,data['expected_revision']);d=deepcopy(e['data']);action=data['action']
        if action=='approve':
            if e['state'] not in {'prepared','needs_review'}:fail('Extension is not awaiting approval',409)
            peer(db,actor,e['authors'],True);d.update(approved_by=actor['id'],approval_digest=bound_control(db,e['kind'],d),approval_valid=True);state='approved'
        elif action=='simulate_submit':
            if e['state']!='approved' or d['approval_digest']!=bound_control(db,e['kind'],d):fail('Current independent extension approval required',409)
            d.update(simulated_submission_id='SIM-EXT-'+uuid4().hex,simulated_submitted_at=w.now(),real_submission=False);state='simulated_submitted'
        elif action=='record_packet_event':
            if e['state']!='simulated_submitted':fail('Record packet evidence only after the simulated submission step',409)
            peer(db,actor,e['authors']);refs_valid(data['refs'],e['data']['version'])
            def supports(ref):
                if ref=='timeline:extension-2026-04-14':return True
                if d['jurisdiction']!='federal' or not ref.startswith('agency:/irs_account_transcript_2025/1'):return False
                def payments(value):
                    if isinstance(value,dict):return ([value] if value.get('code')=='670' else [])+[p for child in value.values() for p in payments(child)]
                    if isinstance(value,list):return [p for child in value for p in payments(child)]
                    return []
                return any(p.get('date')=='2026-04-14' and isinstance(p.get('amount'),(int,float)) and Decimal(str(p['amount']))==Decimal(d['proposed_payment']) for p in payments(resolve_reference(ref,d['version']).value))
            if not any(supports(r) for r in data['refs']):fail('Evidence must identify this jurisdiction and the supplied extension payment; another estimated payment is insufficient')
            d.update(external_evidence_refs=data['refs'],evidence_classification='scripted_packet_history',real_external_confirmation=False);state='external_evidence_recorded'
        else:fail('No real external confirmation/transport adapter is configured',409)
        d['last_note']=data['note'];return save(db,actor,e,state,d,action,e['revision'])


def payment_catalog():
    packet=load_packet();result=[]
    for i,source in enumerate(packet['tax_agency_records']['irs_account_transcript_2025']):
        for j,txn in enumerate(source['transactions']):
            if txn['code']!='670' or not isinstance(txn['amount'],(int,float)):continue
            result.append({'source_ref':f'agency:/irs_account_transcript_2025/{i}/transactions/{j}','jurisdiction':'federal','tax_year':2025,'date':txn['date'],'amount':money(txn['amount']),'classification':'scripted_packet_history' if i>0 else 'provided_packet_record','description':txn['description']})
    ftb=packet['tax_agency_records']['ftb_account']
    for collection,year in [('tax_year_2025_payments',2025),('tax_year_2024_payments_after_filing',2024)]:
        for i,p in enumerate(ftb[collection]):result.append({'source_ref':f'agency:/ftb_account/{collection}/{i}','jurisdiction':'california','tax_year':year,'date':p['date'],'amount':money(p['amount']),'classification':'provided_packet_record','description':p.get('note','Estimated payment')})
    return result


def payment_record(actor,data):
    source=next((p for p in payment_catalog() if p['source_ref']==data['source_ref']),None)
    if not source:fail('Only an attributable numeric payment in the supplied agency records is supported')
    key=digest({k:source[k] for k in ('jurisdiction','tax_year','date','amount')})
    with w.connection() as db:
        access(db,actor)
        if any(p['data']['payment_identity']==key for p in w.entities(db,'lc_payment')):fail('Duplicate payment evidence; the same payment cannot be counted through another transcript snapshot',409)
        return create(db,actor,'lc_payment',{**source,'payment_identity':key,'note':data['note'],'real_world_confirmation':False,'reviewed_value':None},'evidence_recorded')


def payment_review(actor,identifier,data):
    with w.connection() as db:
        access(db,actor);p=record(db,identifier,'lc_payment');check_revision(p,data['expected_revision']);peer(db,actor,p['authors'])
        if p['state']!='evidence_recorded':fail('Payment evidence already reviewed',409)
        return save(db,actor,p,'reviewed',{**p['data'],'reviewed_by':actor['id'],'review_note':data['note'],'reviewed_value':p['data']['amount'],'confirmation_level':'packet record reviewed; not a live payment confirmation'},'reviewed',p['revision'])


def create_package(db,actor,kind,snapshot_id,resource_id,content):
    identifier='package:'+uuid4().hex
    body={**content,'classification':'simulated_'+kind,'disclaimer':DISCLAIMER,'real_delivery_or_submission':False,'legal_signature':False}
    db.execute('INSERT INTO lifecycle_packages VALUES(?,?,?,?,?,?,?,?)',(identifier,kind,snapshot_id,resource_id,digest(body),canonical(body),actor['id'],w.now()))
    w.event(db,identifier,'package','generated',actor['id'],{'kind':kind,'resource_id':resource_id,'snapshot_id':snapshot_id,'content_hash':digest(body)})
    return {'id':identifier,'kind':kind,'snapshot_id':snapshot_id,'content_hash':digest(body),'simulation_only':True}


def package_view(actor,identifier,reveal=False):
    with w.connection() as db:
        access(db,actor);row=db.execute('SELECT * FROM lifecycle_packages WHERE id=?',(identifier,)).fetchone()
        if not row:fail('Generated package not found',404)
        content=json.loads(row['content_json'])
        # The shared middleware independently validates and audits any requested reveal.
        if not reveal:
            from app.security import redact
            content=redact(content)
        return {'id':row['id'],'kind':row['kind'],'snapshot_id':row['snapshot_id'],'canonical_content_hash':row['content_hash'],
                'delivered_content_hash':digest(content),'content':content,'download_json':canonical(content),'encoding':'canonical sorted ASCII JSON for hash verification','simulation_only':True}


def client_copy(actor,filing_id):
    with w.connection() as db:
        access(db,actor);f=record(db,filing_id,'lc_filing')
        if f['state']!='accepted':fail('Client copy requires an accepted simulated filing',409)
        s=snapshot(db,f['data']['snapshot_id'])
        return create_package(db,actor,'client_copy',s['id'],f['id'],{'snapshot_id':s['id'],'snapshot_content_hash':s['content_hash'],
            'household':s['content']['evidence_bundle']['household'],'engine_baseline':s['content']['engine_baseline'],'approved_adjustments':s['content']['approved_adjustments'],'estimated_summary':s['content']['estimated_summary'],
            'filing':f,'retention':retention(),'warning':'JSON workpaper copy, not official tax forms or an actual agency acceptance.'})


def delivery(actor,data):
    with w.connection() as db:
        access(db,actor);package=db.execute('SELECT * FROM lifecycle_packages WHERE id=?',(data['package_id'],)).fetchone()
        if not package or package['kind']!='client_copy':fail('An immutable client-copy package is required',409)
        if data['client_id'] not in {c['id'] for c in load_packet()['firm']['client_users']}:fail('Unknown packet client ID')
        return create(db,actor,'lc_delivery',{'package_id':package['id'],'client_id':data['client_id'],'method':'simulated_portal','note':data['note'],'simulated_delivered_at':w.now(),'real_delivery_confirmation':False},'simulated_delivered')


def snapshot_compare(db,original_id,amended_id):
    from app.services.change_analysis_service import compare_lines,differences
    original=snapshot(db,original_id);amended=snapshot(db,amended_id)
    def leaves(s):
        values={l['key']:l['value'] for l in s['content']['engine_baseline']['lines']}
        for a in s['content']['approved_adjustments']:values[a['payload']['target']]=a['payload']['proposed_value']
        return values
    a,b=leaves(original),leaves(amended);changes=[]
    for key in sorted(a.keys()|b.keys()):
        if str(a.get(key))!=str(b.get(key)):
            diff=differences(Decimal(str(a[key])) if key in a and isinstance(a[key],(int,float,str)) and str(a[key]).replace('.','',1).replace('-','',1).isdigit() else a.get(key),Decimal(str(b[key])) if key in b and isinstance(b[key],(int,float,str)) and str(b[key]).replace('.','',1).replace('-','',1).isdigit() else b.get(key))
            # Normalize equal decimal representations; zero is not a substantive change.
            if diff['numeric_difference'] is not None and Decimal(diff['numeric_difference'])==0:continue
            changes.append({'key':key,'original':a.get(key),'amended':b.get(key),**diff})
    return {'original_snapshot_id':original_id,'amended_snapshot_id':amended_id,'engine_changes':[c for c in compare_lines(original['content']['engine_baseline'],amended['content']['engine_baseline']) if c['change']!='unchanged'],
            'approved_workpaper_leaf_changes':changes,'estimated_summaries':{'original':original['content']['estimated_summary'],'amended':amended['content']['estimated_summary']},
            'warning':'Only approved leaf proposals and estimated effects are compared. No official amended-return tax computation is invented.'}


def stabilized_readiness(actor):
    with w.connection() as db:
        access(db,actor)
        from app.services.change_analysis_service import reassess
        reassess(db,actor,{'workflow_entities'})
        w.invalidate(db)
    return w.readiness(actor)


def amendment_create(actor,data):
    ready=stabilized_readiness(actor)
    with w.connection() as db:
        access(db,actor);parent=snapshot(db,data['parent_snapshot_id'])
        if not any(f['state']=='accepted' and f['data']['snapshot_id']==parent['id'] for f in w.entities(db,'lc_filing')):fail('An accepted original simulated filing is required for an amendment',409)
        s=freeze(db,actor,{'version':data['version'],'mode':'demonstration','note':data['reason'],'refs':data['refs']},ready,'amendment',parent['id'])
        result=create(db,actor,'lc_amendment',{'parent_snapshot_id':parent['id'],'snapshot_id':s['id'],'reason':data['reason'],'refs':data['refs'],'approval_valid':False},'prepared')
        return {**result,'comparison':snapshot_compare(db,parent['id'],s['id'])}


def amendment_action(actor,identifier,data):
    with w.connection() as db:
        access(db,actor);a=record(db,identifier,'lc_amendment');check_revision(a,data['expected_revision']);require_current(db,snapshot(db,a['data']['snapshot_id']));d=deepcopy(a['data'])
        if data['action']=='review':
            if a['state'] not in {'prepared','needs_review'}:fail('Amendment is not awaiting independent review',409)
            peer(db,actor,set(a['authors'])|set(snapshot(db,d['snapshot_id'])['content']['contributors']));d.update(reviewed_by=actor['id'],review_note=data['note']);state='reviewed'
        elif data['action']=='approve':
            if a['state']!='reviewed':fail('Distinct independent review is required before amendment approval',409)
            peer(db,actor,set(a['authors'])|{d['reviewed_by']}|set(snapshot(db,d['snapshot_id'])['content']['contributors']),True)
            d.update(approved_by=actor['id'],approval_digest=bound_control(db,a['kind'],d),approval_valid=True);state='approved'
        else:fail('Unsupported amendment transition')
        return save(db,actor,a,state,d,data['action'],a['revision'])


def retention(anchor=None):
    today=datetime.now(timezone.utc).date()
    start=max(today,date.fromisoformat(anchor)) if anchor else today
    try:until=start.replace(year=start.year+7)
    except ValueError:until=start.replace(month=2,day=28,year=start.year+7)
    return {'years':7,'anchor':start.isoformat(),'retain_until_at_least':until.isoformat(),'source_ref':'doc:D01#page2','basis':'Engagement letter client-retention statement, used as a demonstration minimum; no automated deletion.','legal_hold':True}


def notice_create(actor,data):
    with w.connection() as db:
        access(db,actor)
        if data.get('packet_notice_id'):
            source=next((n for n in load_packet()['tax_agency_records']['notices'] if n['id']==data['packet_notice_id']),None)
            if not source:fail('Supplied notice not found',404)
            jurisdiction='federal' if source['agency']=='IRS' else 'california';title=source['type'];source_date=source['dated'];deadline=source.get('response_due');refs=[source['document']]
            classification='packet_scripted_examination' if source['id']=='N-2025-L566' else 'packet_prior_year_history';year=source['tax_year']
        else:
            source=None;jurisdiction=data['jurisdiction'];title=data['title'];source_date=valid_date(data['source_date']);deadline=valid_date(data['response_due']) if data.get('response_due') else None;refs=data['refs'];classification='staff_entered_demonstration_notice';year=2025
        refs_valid(refs)
        if deadline and deadline<source_date:fail('Response deadline cannot precede notice date')
        owner=w.staff(data['owner_id'])
        if not w.membership(db,owner) or owner['role'] not in w.PRACTICE_ROLES:fail('Notice owner must be active assigned practice staff',403)
        result=create(db,actor,'lc_notice',{'jurisdiction':jurisdiction,'tax_year':year,'title':title,'source_date':source_date,'response_due':deadline,'deadline_source':'supplied_packet' if source else 'staff_entered_demo' if deadline else 'not_supplied_manual_review',
            'owner_id':owner['id'],'refs':refs,'classification':classification,'source':source,'real_received_at':None,'intake_recorded_at':w.now(),'note':data['note'],'response':'','snapshot_id':None,'approval_valid':False,'retention':retention(source_date)},'intake')
        w.notify(db,owner['id'],'Demonstration notice response assigned',result['id'],'notice:'+result['id']);return result


def notice_action(actor,identifier,data):
    with w.connection() as db:
        access(db,actor);n=record(db,identifier,'lc_notice');check_revision(n,data['expected_revision']);d=deepcopy(n['data']);action=data['action']
        if action=='prepare':
            if n['state'] not in {'intake','preparing','needs_review'}:fail('Response cannot be changed in this state',409)
            if actor['id']!=d['owner_id'] and actor['role']!='partner':fail('Assigned response preparer or partner required',403)
            s=snapshot(db,data['snapshot_id'])
            if s['content']['tax_year']!=d['tax_year']:fail('Snapshot tax year does not match the notice; missing prior-year filing snapshot',409)
            if not any(f['state']=='accepted' and f['data']['snapshot_id']==s['id'] and f['data']['jurisdiction']==d['jurisdiction'] for f in w.entities(db,'lc_filing')):fail('Select an accepted simulated filing in the notice jurisdiction',409)
            refs_valid(data['refs'],s['version']);d.update(snapshot_id=s['id'],response=data['note'],refs=sorted(set(d['refs']+data['refs'])),approval_valid=False)
            authors=sorted(set(n['authors']+[actor['id']]))
            return w.put(db,n['id'],n['kind'],n['area'],'preparing',d,authors,actor['id'],'response_prepared',n['revision'])
        elif action=='submit_review':
            if n['state']!='preparing' or not d['response']:fail('A documented response must be prepared first',409)
            state='in_review'
        elif action=='approve':
            if n['state']!='in_review':fail('Response is not awaiting independent review',409)
            peer(db,actor,n['authors']);d.update(approved_by=actor['id'],approval_digest=bound_control(db,n['kind'],d),approval_valid=True,review_note=data['note']);state='approved'
        elif action=='simulate_dispatch':
            if n['state']!='approved' or d['approval_digest']!=bound_control(db,n['kind'],d):fail('Current response approval required',409)
            if not db.execute("SELECT 1 FROM lifecycle_packages WHERE kind='examination_response' AND resource_id=?",(n['id'],)).fetchone():fail('Generate an immutable examination package first',409)
            d.update(simulated_dispatched_at=w.now(),real_dispatch=False);state='simulated_sent'
        elif action=='close_demo':
            if n['state']!='simulated_sent':fail('Only a simulated sent response can be closed',409)
            peer(db,actor,n['authors']);d['closing_note']=data['note'];state='simulated_closed'
        else:fail('Unsupported notice transition')
        return save(db,actor,n,state,d,action,n['revision'])


def examination_package(actor,identifier):
    with w.connection() as db:
        access(db,actor);n=record(db,identifier,'lc_notice')
        if n['state']!='approved' or n['data']['approval_digest']!=bound_control(db,n['kind'],n['data']):fail('A current independently approved notice response is required',409)
        s=snapshot(db,n['data']['snapshot_id']);evidence=[resolve_reference(r,s['version']).model_dump() for r in n['data']['refs']]
        events=[dict(r) for r in db.execute('SELECT * FROM workflow_events WHERE entity_id=? ORDER BY id',(n['id'],))]
        return create_package(db,actor,'examination_response',s['id'],n['id'],{'notice':n,'frozen_workpaper':s['content'],'snapshot_content_hash':s['content_hash'],'dependency_manifest':s['dependencies'],
            'response_evidence':evidence,'notice_audit_history':events,'accepted_filing_history':[f for f in w.entities(db,'lc_filing') if f['state']=='accepted' and f['data']['snapshot_id']==s['id'] and f['data']['jurisdiction']==n['data']['jurisdiction']],
            'snapshot_history':[dict(r) for r in db.execute('SELECT * FROM workflow_events WHERE entity_id IN (?,?) ORDER BY id',(s['id'],'validity:'+s['id']))],'retention':n['data']['retention'],'completeness':'Self-contained supplied packet, frozen baseline/approved overlay, review provenance and response evidence; unsupported tax calculations remain explicit.'})


def flattened(value,prefix=''):
    result=[]
    for key,item in value.items():
        path=prefix+'/'+key
        if isinstance(item,dict):result.extend(flattened(item,path))
        else:result.append((path,item))
    return result


def carryover_import(actor,data):
    with w.connection() as db:
        access(db,actor);s=snapshot(db,data['snapshot_id']);result=[]
        for path,value in flattened(s['content']['engine_baseline']['carryovers_out']):
            identifier='carryover:'+digest({'snapshot_id':s['id'],'path':path})[:32]
            existing=w.entity(db,identifier)
            if existing:result.append(existing);continue
            result.append(w.put(db,identifier,'lc_carryover','carryovers','prepared',{'snapshot_id':s['id'],'version':s['version'],'source_path':'return_versions/'+s['version']+'/carryovers_out'+path,'key':path,'original_value':value,
                'adjusted_value':None,'reviewed_value':None,'notes':data['note'],'refs':[],'authority':'','from_year':2025,'to_year':2026,'simulation_only':True,'calculation_status':'stored_engine_unverified; corrected outgoing rollforward unsupported','authoritative_rollforward':False},[actor['id']],actor['id'],'imported_original',0))
        return {'records':result,'new_year_tax_computed':False}


def carryover_action(actor,identifier,data):
    with w.connection() as db:
        access(db,actor);c=record(db,identifier,'lc_carryover');check_revision(c,data['expected_revision']);d=deepcopy(c['data'])
        if data['action']=='revise':
            refs_valid(data['refs'],d['version'])
            if not data['authority'].strip():fail('Documented method/authority is required for a manual proposal')
            if data['adjusted_value'] is not None:
                value=Decimal(str(data['adjusted_value']))
                if not value.is_finite():fail('A finite manual workpaper value is required')
                d['adjusted_value']=format(value,'f')
            else:d['adjusted_value']=None
            d.update(notes=data['note'],refs=data['refs'],authority=data['authority'],reviewed_value=None)
            return w.put(db,c['id'],c['kind'],c['area'],'prepared',d,sorted(set(c['authors']+[actor['id']])),actor['id'],'manual_value_proposed',c['revision'])
        if data['action']!='review' or c['state']!='prepared':fail('Carryover is not awaiting review',409)
        peer(db,actor,c['authors']);refs_valid(data['refs'],d['version'])
        if not data['authority'].strip():fail('Review method/authority is required')
        d.update(reviewed_value=d['adjusted_value'] if d['adjusted_value'] is not None else d['original_value'],reviewed_by=actor['id'],review_note=data['note'],refs=data['refs'],authority=data['authority'],calculation_status='CPA-reviewed workpaper proposal; no authoritative 2026 calculation')
        return save(db,actor,c,'reviewed',d,'reviewed',c['revision'])


def handoff_prepare(actor,data):
    with w.connection() as db:
        access(db,actor);s=snapshot(db,data['snapshot_id']);owner=w.staff(data['owner_id'])
        if not w.membership(db,owner) or owner['role'] not in w.PRACTICE_ROLES:fail('Active assigned handoff owner required',403)
        return create(db,actor,'lc_handoff',{'snapshot_id':s['id'],'from_year':2025,'to_year':2026,'owner_id':owner['id'],'notes':data['note'],'planning_reference':deepcopy(load_packet()['planning_reference_2026']),
            'unsupported_calculations':['2026 taxable income and tax','corrected outgoing carryovers without a rerunnable engine','actual safe-harbor installments from an authoritative filed 2025 return'],'approval_valid':False},'prepared')


def handoff_action(actor,identifier,data):
    with w.connection() as db:
        access(db,actor);h=record(db,identifier,'lc_handoff');check_revision(h,data['expected_revision']);d=deepcopy(h['data'])
        carries=[c for c in w.entities(db,'lc_carryover') if c['data']['snapshot_id']==d['snapshot_id']]
        needed=len(flattened(snapshot(db,d['snapshot_id'])['content']['engine_baseline']['carryovers_out']))
        if len(carries)!=needed or any(c['state']!='reviewed' for c in carries):fail('Every supplied carryover requires a documented independent review before handoff',409)
        if data['action']=='review':
            if h['state'] not in {'prepared','needs_review'}:fail('Handoff is not awaiting review',409)
            peer(db,actor,set(h['authors'])|{author for c in carries for author in c['authors']});d.update(reviewed_by=actor['id'],approval_digest=bound_control(db,h['kind'],d),approval_valid=True,review_note=data['note']);state='reviewed'
        elif data['action']=='handoff':
            if h['state']!='reviewed' or d['approval_digest']!=bound_control(db,h['kind'],d):fail('Current independently reviewed handoff required',409)
            if not any(f['state']=='accepted' and f['data']['snapshot_id']==d['snapshot_id'] for f in w.entities(db,'lc_filing')):fail('A source accepted simulated filing is required for completed handoff',409)
            d['handed_off_at']=w.now();state='handed_off';w.notify(db,d['owner_id'],'Demonstration next-year handoff available',h['id'],'handoff:'+h['id'])
        else:fail('Unsupported handoff transition')
        result=save(db,actor,h,state,d,data['action'],h['revision'])
        if state=='handed_off':
            package=create_package(db,actor,'handoff',d['snapshot_id'],h['id'],{'handoff':result,'carryovers':carries,'source_snapshot_hash':snapshot(db,d['snapshot_id'])['content_hash'],'planning_reference':d['planning_reference'],'retention':retention()})
            return {**result,'package':package}
        return result


def overview(actor):
    from app.services.reconciliation_service import run_reconciliations
    with w.connection() as db:
        access(db,actor);invalidate(db,actor)
        snapshots=[snapshot_public(db,snapshot(db,r[0])) for r in db.execute('SELECT id FROM lifecycle_snapshots ORDER BY created_at,id')]
        packages=[{k:r[k] for k in ('id','kind','snapshot_id','resource_id','content_hash','created_by','created_at')} for r in db.execute('SELECT * FROM lifecycle_packages ORDER BY created_at')]
        return {'disclaimer':DISCLAIMER,'simulation_only':True,'real_filing_ready':False,'legal_signature':False,'snapshots':snapshots,
            'records':[e for e in w.entities(db) if e['kind'] in KINDS],'packages':packages,'clients':load_packet()['firm']['client_users'],'staff':load_packet()['firm']['staff'],
            'payment_catalog':payment_catalog(),'payment_reconciliations':[c for c in run_reconciliations()['checks'] if c['id'] in {'payments.federal_estimates','payments.ca_estimates'}],
            'packet_notices':load_packet()['tax_agency_records']['notices'],'planning_reference':load_packet()['planning_reference_2026'],
            'external_confirmation_support':'Not configured. Packet filing/payment events are invented case evidence; no endpoint creates real-world confirmations.'}


def history(actor,identifier=None):
    with w.connection() as db:
        access(db,actor)
        clauses="(kind LIKE 'lc_%' OR kind IN ('snapshot','package'))";params=()
        if identifier:clauses+=' AND entity_id=?';params=(identifier,)
        return {'events':[{**dict(r),'payload':json.loads(r['payload_json'])} for r in db.execute('SELECT * FROM workflow_events WHERE '+clauses+' ORDER BY id',params)],'append_only':True,'disclaimer':DISCLAIMER}
