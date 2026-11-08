"""Review decisions and explicit links to the immutable-baseline adjustment ledger."""
import json
from datetime import datetime, timezone

from app.services import review_service
from app.services.adjustment_service import database, packet_hash, staff_member, get_adjustment, create_adjustment, list_adjustments, fail
from app.services.finding_service import build_catalog
from app.services.reconciliation_service import run_reconciliations
from app.services.evidence_service import resolve_reference


def catalog(version):
    result = build_catalog(version)
    if result is None:fail('Return version not found',404)
    return result


def finding(version, identifier):
    return review_service.get_valid_finding(version,identifier)


def link_events(version, identifier):
    item = finding(version,identifier)
    with database() as db:
        events = [dict(r) for r in db.execute('SELECT * FROM finding_adjustment_events WHERE version=? AND finding_id=? ORDER BY id',(version,item['id']))]
    latest = {}
    for event in events:latest[event['adjustment_id']]=event
    linked=[]
    for identifier,event in latest.items():
        if event['action']=='link':linked.append(get_adjustment(identifier))
    return {'events':events,'adjustments':linked}


def link(version, identifier, adjustment_id, actor_id, note, action='link'):
    actor=staff_member(actor_id)
    item=finding(version,identifier)
    adjustment=get_adjustment(adjustment_id)
    if adjustment['version']!=version:fail('Adjustment belongs to a different baseline version',409)
    checks=[c for c in run_reconciliations(version)['checks'] if c['id'] in item['reconciliations']]
    targets={c['target'] for c in checks if c['target']}
    if adjustment['payload']['target'] not in targets:fail('Adjustment target is not an affected line for this finding',409)
    if not note.strip():fail('A link rationale is required')
    with database(write=True) as db:
        previous=db.execute('SELECT action FROM finding_adjustment_events WHERE version=? AND finding_id=? AND adjustment_id=? ORDER BY id DESC LIMIT 1',(version,item['id'],adjustment_id)).fetchone()
        if (previous and previous['action']==action) or (not previous and action=='unlink'):fail('Link state already matches requested action',409)
        db.execute('INSERT INTO finding_adjustment_events(version,finding_id,adjustment_id,action,actor_id,note,packet_hash,created_at) VALUES (?,?,?,?,?,?,?,?)',
                   (version,item['id'],adjustment_id,action,actor['id'],note.strip(),packet_hash(),datetime.now(timezone.utc).isoformat()))
    return link_events(version,item['id'])


def create_correction(version,check_id,actor_id,note,authority):
    catalog(version)
    check=next((c for c in run_reconciliations(version)['checks'] if c['id']==check_id),None)
    if check is None:fail('Reconciliation not found',404)
    if not check['target'] or check['expected_value'] is None or check['conclusion'] not in {'exact_mismatch','judgment_required'}:
        fail('No supported leaf-line correction proposal exists for this check',409)
    item=next((f for f in catalog(version)['findings'] if check_id in f['reconciliations']),None)
    if item is None:fail('No finding requires this correction',409)
    if not note.strip() or not authority.strip():fail('Rationale and authority are required')
    from app.services.adjustment_service import insert_draft, build_payload, read_one, version_data
    actor=staff_member(actor_id)
    payload=build_payload(version_data(version),{'actor_id':actor_id,'target':check['target'],'proposed_value':check['expected_value'],
                                                'rationale':note,'authority':authority,
                                                'refs':[r for r in check['refs'] if resolve_reference(r,version).status=='resolved']})
    with database(write=True) as db:
        rows=db.execute('SELECT adjustment_id,action FROM finding_adjustment_events WHERE version=? AND finding_id=? ORDER BY id',(version,item['id'])).fetchall()
        latest={row['adjustment_id']:row['action'] for row in rows}
        for identifier,action in latest.items():
            if action=='link' and read_one(db,identifier)['state'] not in {'reversed','superseded','rejected'}:
                fail('A linked correction already exists; open or revise it',409)
        adjustment=insert_draft(db,version,payload,actor)
        db.execute('INSERT INTO finding_adjustment_events(version,finding_id,adjustment_id,action,actor_id,note,packet_hash,created_at) VALUES (?,?,?,?,?,?,?,?)',
                   (version,item['id'],adjustment['id'],'link',actor_id,note.strip(),packet_hash(),datetime.now(timezone.utc).isoformat()))
    return adjustment


def append_decision(db,version,finding_id,event_id,details,timestamp):
    """Called inside legacy review transaction; failure rolls back status and history."""
    adjustment_id=details.get('adjustment_id')
    if details['disposition']=='correction_linked':
        if not adjustment_id:fail('A correction resolution requires a linked approved adjustment',409)
        from app.services.adjustment_service import read_one
        adjustment=read_one(db,adjustment_id)
        active_link=db.execute('SELECT action FROM finding_adjustment_events WHERE version=? AND finding_id=? AND adjustment_id=? ORDER BY id DESC LIMIT 1',(version,finding_id,adjustment_id)).fetchone()
        if adjustment['version']!=version or adjustment['state']!='approved' or adjustment['stale'] or not active_link or active_link['action']!='link':
            fail('A current approved same-version linked adjustment is required; review resolution does not approve corrections',409)
    db.execute('''INSERT INTO reconciliation_decisions(version,finding_id,review_event_id,actor_id,disposition,authority,evidence_refs_json,adjustment_id,packet_hash,snapshot_json,created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
               (version,finding_id,event_id,details['actor_id'],details['disposition'],details['authority'],json.dumps(details['refs']),adjustment_id,
                packet_hash(),json.dumps(details['snapshot'],sort_keys=True),timestamp))


def decide(version,identifier,data):
    actor=staff_member(data['actor_id'])
    item=finding(version,identifier)
    if data['status']=='resolved' and data['disposition']=='investigating':fail('A resolved issue requires an explicit resolution disposition')
    if not data['authority'].strip() or not data['note'].strip():fail('Documented rationale and authority are required')
    for ref in data['refs']:
        if resolve_reference(ref,version).status!='resolved':fail('Unresolved decision evidence: '+ref)
    details={'actor_id':actor['id'],'authority':data['authority'].strip(),'disposition':data['disposition'],
             'refs':data['refs'],'adjustment_id':data.get('adjustment_id'),
             'snapshot':{'finding':item,'checks':[c for c in run_reconciliations(version)['checks'] if c['id'] in item['reconciliations']]}}
    return review_service.update_review(version,item['id'],data['status'],data['note'],actor['role'],actor['name'],audit_details=details)


def history(version,identifier):
    item=finding(version,identifier)
    old=review_service.get_review_history(version,item['id'])
    with database() as db:
        decisions=[]
        for row in db.execute('SELECT * FROM reconciliation_decisions WHERE version=? AND finding_id=? ORDER BY id',(version,item['id'])):
            d=dict(row);d['snapshot']=json.loads(d.pop('snapshot_json'));d['refs']=json.loads(d.pop('evidence_refs_json'));decisions.append(d)
    return {**old,'decisions':decisions,'links':link_events(version,item['id'])}


def dashboard(version):
    data=catalog(version)
    reviews=review_service.list_reviews(version)
    saved={f['id']:f for f in reviews['findings']}
    adjustments={a['id']:a for a in list_adjustments(version)['adjustments']}
    with database() as db:
        rows=db.execute('SELECT * FROM finding_adjustment_events WHERE version=? ORDER BY id',(version,)).fetchall()
        from app.services.workflow_service import entities
        assessments={a['data']['finding_id']:a for a in entities(db,'review_assessment') if a['data']['version']==version}
    latest={}
    for row in rows:latest[(row['finding_id'],row['adjustment_id'])]=dict(row)
    for item in data['findings']:
        state=saved[item['id']]
        for key in ('status','review_note','updated_by','updated_at'):item[key]=state[key]
        if item['id'] in assessments:item['review_validity']=assessments[item['id']]
        item['adjustment_links']=[adjustments[aid] for (fid,aid),event in latest.items() if fid==item['id'] and event['action']=='link' and aid in adjustments]
    return {**data,'standards':run_reconciliations(version)['standards'],
            'note':'Reported values remain engine originals. Conditional comparisons and unsupported tax calculations are not completed tax results.'}
