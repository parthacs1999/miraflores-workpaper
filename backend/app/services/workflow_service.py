"""Firm workflow projections + append-only events. No filing or legal e-signature service."""
import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from uuid import uuid4
from functools import lru_cache

from app.services.packet_service import load_packet
from app.services.adjustment_service import fail

ENGAGEMENT = 'CL-20417'
AREAS = ('intake','business','vehicle','investments','depreciation','rentals','california','itemized','credits','payments','carryovers','pass_throughs','prior_year','engagement')
PRACTICE_ROLES = {'preparer','reviewer','partner'}
RECORD_TYPES = {'preparation','required_step','diligence','election','judgment','question','document_disposition','outside_filing'}


def now():return datetime.now(timezone.utc).isoformat()
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,default=str,separators=(',',':')).encode()).hexdigest()
def staff(identifier):
    value=next((s for s in load_packet()['firm']['staff'] if s['id']==identifier),None)
    if not value or value['active_from']>now()[:10]:fail('Staff identity is unknown or inactive',403)
    return value


def decode(row):
    if row is None:return None
    item=dict(row)
    item['data']=json.loads(item.pop('data_json'))
    item['authors']=json.loads(item.pop('authors_json'))
    return item


def entity(db,identifier):return decode(db.execute('SELECT * FROM workflow_entities WHERE id=?',(identifier,)).fetchone())
def entities(db,kind=None):
    rows=db.execute('SELECT * FROM workflow_entities WHERE engagement_id=?'+(' AND kind=?' if kind else '')+' ORDER BY id',(ENGAGEMENT,kind) if kind else (ENGAGEMENT,))
    return [decode(r) for r in rows]


def event(db,identifier,kind,action,actor,payload,key=None):
    db.execute('INSERT OR IGNORE INTO workflow_events(entity_id,kind,action,actor_id,payload_json,created_at,event_key) VALUES (?,?,?,?,?,?,?)',
               (identifier,kind,action,actor,json.dumps(payload,sort_keys=True,default=str),now(),key))


def put(db,identifier,kind,area,state,data,authors,actor,action,expected=None):
    previous=entity(db,identifier)
    if previous and (previous['engagement_id'] != ENGAGEMENT or previous['kind'] != kind or previous['area'] != area):
        fail('Workflow identity, kind and engagement scope are immutable',409)
    if expected is not None and (previous['revision'] if previous else 0)!=expected:fail('Workflow item changed; reload before acting',409)
    revision=(previous['revision'] if previous else 0)+1
    db.execute('''INSERT INTO workflow_entities VALUES (?,?,?,?,?,?,?,?,?,?)
      ON CONFLICT(id) DO UPDATE SET revision=excluded.revision,state=excluded.state,data_json=excluded.data_json,authors_json=excluded.authors_json,updated_at=excluded.updated_at''',
      (identifier,kind,ENGAGEMENT,area,revision,state,json.dumps(data,sort_keys=True),json.dumps(sorted(set(authors))),previous['created_by'] if previous else actor,now()))
    result=entity(db,identifier)
    event(db,identifier,kind,action,actor,{'before':previous,'after':result})
    return result


def seed(db):
    if entity(db,ENGAGEMENT):return
    packet=load_packet();firm=packet['firm']
    policy={'partner_threshold':'1000','variance_review':firm['starter_standards']['variance_review'],
            'verification_methods':firm['starter_standards']['verification_types'],
            'required_steps':firm['starter_standards']['required_steps'],
            'required_areas':list(AREAS[:-1]),'independent_review_required':True,'blocking_notes_required':True}
    db.execute('INSERT OR IGNORE INTO workflow_policies VALUES (?,?,?,?,?)',('packet-v1',1,json.dumps(policy,sort_keys=True),'system',now()))
    put(db,ENGAGEMENT,'engagement','engagement','active',{'owner_id':'st-03','baseline':'v3','tax_year':2025,'policy_id':'packet-v1','packet_hash':digest(packet)},[],'system','seeded')
    for role,identifier in firm['assignment_at_start'].items():
        put(db,'membership:'+identifier,'membership','engagement','active',{'staff_id':identifier,'responsibility':role,'areas':['*']},[],'system','seeded')
    for i,title in enumerate(policy['required_steps']):
        put(db,f'required:{i}','record','intake','open',{'record_type':'required_step','title':title,'applicability':'unknown','refs':[],'authority':'','answer':'','source':'firm.starter_standards.required_steps'},[],'system','seeded')
    for topic in ('child_tax_credit','other_dependent_credit','aotc','eic','head_of_household'):
        put(db,'diligence:'+topic,'record','credits','open',{'record_type':'diligence','title':topic,'applicability':'unknown','refs':[],'authority':'','answer':''},[],'system','seeded')
    for i,deadline in enumerate(firm['deadlines']):
        put(db,f'deadline:{i}','task','engagement','open',{'title':deadline['what'],'due_date':deadline['date'],'assignee':None,'source':'firm.deadlines','outside_scope':'outside engagement' in deadline['what']},[],'system','seeded')


@contextmanager
def connection(write=True):
    from app.services.review_service import connect
    from app.migrate import migrate
    db=connect()
    from app.security_context import request_database
    token=request_database.set(db)
    try:
        migrate(db);db.execute('BEGIN IMMEDIATE')
        seed(db)
        yield db
        db.commit()
    except Exception:
        db.rollback();raise
    finally:
        request_database.reset(token)
        db.close()


def active_policy(db):
    root=entity(db,ENGAGEMENT)
    row=db.execute('SELECT * FROM workflow_policies WHERE id=?',(root['data']['policy_id'],)).fetchone()
    return {'id':row['id'],'revision':row['revision'],'policy':json.loads(row['policy_json'])}


def membership(db,actor):
    row=entity(db,'membership:'+actor['id'])
    if row and row['engagement_id']==ENGAGEMENT and row['state']=='active':return row
    return None


def require_access(db,actor,area=None,manage=False):
    current=staff(actor['id'])
    if current['role']!=actor['role']:fail('Principal role is no longer valid',403)
    if manage:
        if current['role'] not in {'firm_administrator','partner'}:fail('Engagement administration permission required',403)
        if current['role']=='partner' and not membership(db,actor):fail('No engagement assignment',403)
        return
    member=membership(db,actor)
    if not member:fail('No engagement assignment',403)
    if area and '*' not in member['data']['areas'] and area not in member['data']['areas']:fail('Work is outside the assigned area',403)


def contributors(db,area):
    result=set()
    for record in entities(db,'record'):
        if record['area'] in {area,'engagement'} and record['data'].get('record_type') in RECORD_TYPES:
            result.update(record['authors'])
    for row in db.execute('SELECT * FROM adjustments'):
        payload=db.execute('SELECT payload_json FROM adjustment_revisions WHERE adjustment_id=? AND revision=?',(row['id'],row['revision'])).fetchone()
        if payload:
            from app.services.finding_service import area_for
            target=json.loads(payload[0])['target']
            if area=='engagement' or area_for(target)==area:result.update(json.loads(row['prepared_by']))
    if area=='engagement':
        for record in entities(db,'record'):result.update(record['authors'])
    from app.services.product_service import evidence_dependencies
    for record in evidence_dependencies(db,area):result.update(record['authors'])
    return result


def independent(db,actor,area):
    require_access(db,actor,area)
    if actor['role'] not in {'reviewer','partner'}:fail('Independent tax reviewer or partner required',403)
    if actor['id'] in contributors(db,area):fail('A substantive author cannot review or sign off their own work',403)


def scope_resources(area):
    from app.services.firm_policy import current
    return _scope_resources(area,digest(current()))

@lru_cache(maxsize=64)
def _scope_resources(area,policy_key):
    from app.services.reconciliation_service import run_reconciliations
    from app.services.evidence_service import evidence_graph
    packet=load_packet();checks=run_reconciliations()['checks']
    selected=checks if area=='engagement' else [c for c in checks if c['area']==area]
    refs={r for c in selected for r in c['refs']}
    if area in {'intake','engagement'}:refs.update(['D01','D02','D03','D04','D05','D06','D07'])
    if area in {'credits','engagement'}:
        refs.update(l['key'] for l in packet['return_versions'][-1]['lines'] if l['key'].startswith(('F8812.','F8863.','F8867.','F2441.')))
    documents=set();nodes={}
    for ref in sorted(refs):
        graph=evidence_graph(ref)
        documents.update(graph['document_ids'])
        for node in graph['nodes']:nodes[node['ref']]=node
    return selected,nodes,documents


def manifest(db,area,level="reviewer"):
    from app.services.product_service import evidence_dependencies
    supplemental=evidence_dependencies(db,area)
    from app.services.finding_service import build_catalog
    checks,base_nodes,base_documents=scope_resources(area)
    nodes=dict(base_nodes);documents=set(base_documents)
    root=entity(db,ENGAGEMENT)
    members=[e for e in entities(db,'membership') if area=='engagement' or '*' in e['data']['areas'] or area in e['data']['areas']]
    records=[e for e in entities(db) if e['kind'] in {'record','note'} and (area=='engagement' or e['area'] in {area,'engagement'})]
    from app.services.evidence_service import evidence_graph
    for record in records:
        for ref in record["data"].get("refs",[]):
            graph=evidence_graph(ref);documents.update(graph["document_ids"])
            for node in graph["nodes"]:nodes[node["ref"]]=node
    adjustments=[]
    for row in db.execute('SELECT * FROM adjustments WHERE version=?',(root['data']['baseline'],)):
        payload=db.execute('SELECT payload_json FROM adjustment_revisions WHERE adjustment_id=? AND revision=?',(row['id'],row['revision'])).fetchone()
        if payload and (area=='engagement' or json.loads(payload[0])['target'] in nodes):
            adjustments.append({**dict(row),'payload':payload[0]})
    evidence_ids={e['id'] for e in load_packet()['extracted_values'] if e['document_id'] in documents}
    verifications=[dict(r) for r in db.execute('SELECT id,version,evidence_id,sequence,status,packet_hash FROM field_verification_events') if r['evidence_id'] in evidence_ids]
    relevant_findings={f['id'] for f in build_catalog()['findings'] if area=='engagement' or f['area']==area or set(f['refs']).intersection(nodes)}
    reviews=[dict(r) for r in db.execute('SELECT * FROM reviews') if r['finding_id'] in relevant_findings]
    links=[dict(r) for r in db.execute('SELECT * FROM finding_adjustment_events') if r['finding_id'] in relevant_findings]
    decisions=[dict(r) for r in db.execute('SELECT * FROM reconciliation_decisions') if r['finding_id'] in relevant_findings]
    required_signoffs=[]
    if area=='engagement':
        required_signoffs=[dict(r) for r in db.execute("SELECT id,area,level,state,staff_id FROM workflow_signoffs WHERE area!='engagement'")]
    if level=='partner':
        required_signoffs.extend(dict(r) for r in db.execute("SELECT id,area,level,state,staff_id FROM workflow_signoffs WHERE area=? AND level='reviewer'",(area,)))
    return {**({'supplemental_evidence':supplemental} if supplemental else {}),'level':level,'policy':active_policy(db),'baseline':root['data']['baseline'],'area':area,
            'owner_id':root['data']['owner_id'],'source_digest':digest(nodes),'check_digest':digest(checks),'members':members,'records':records,
            'adjustments':adjustments,'verifications':verifications,'reviews':reviews,'links':links,'decisions':decisions,
            'contributors':sorted(contributors(db,area)),'required_signoffs':required_signoffs,
            **({'lifecycle_financial_evidence':[e for e in entities(db) if e['kind']=='lc_payment' and area in {'payments','engagement'} or e['kind']=='lc_carryover' and area in {'carryovers','engagement'}]} if any(e['kind']=='lc_payment' and area in {'payments','engagement'} or e['kind']=='lc_carryover' and area in {'carryovers','engagement'} for e in entities(db)) else {}),
            **({'review_assessments':[e for e in entities(db,'review_assessment') if area=='engagement' or e['area'] in {area,'engagement'}]} if any(area=='engagement' or e['area'] in {area,'engagement'} for e in entities(db,'review_assessment')) else {})}


def invalidate(db):
    # Area approvals first; engagement approvals then see the changed child state.
    rows=db.execute("SELECT * FROM workflow_signoffs WHERE state='valid' ORDER BY CASE WHEN area='engagement' THEN 1 ELSE 0 END,created_at").fetchall()
    for row in rows:
        current=manifest(db,row['area'],row['level'])
        if digest(current)!=digest(json.loads(row['manifest_json'])):
            db.execute("UPDATE workflow_signoffs SET state='invalidated',reason=? WHERE id=?",('Underlying scoped dependencies changed; a fresh demonstration approval is required.',row['id']))
            event(db,row['id'],'signoff','invalidated','system',{'area':row['area'],'reason':'dependency_changed'})
            notify(db,row['staff_id'],'Sign-off invalidated',row['id'],'signoff-invalidated:'+row['id'])


def notify(db,recipient,title,resource,key):
    identifier='notification:'+digest(key)[:24]
    if entity(db,identifier):return
    put(db,identifier,'notification','engagement','unread',{'recipient':recipient,'title':title,'resource':resource},[],'system','created')


def after_write(db,principal,tables,legacy_events):
    if not principal or principal.get('profile')=='legacy_test':return
    if not tables.intersection({'workflow_entities','workflow_signoffs','workflow_policies','adjustments','adjustment_revisions','review_events','field_verification_events','finding_adjustment_events','reconciliation_decisions'}):return
    if principal.get('_write_area'):
        require_access(db,principal,principal['_write_area'])
        if principal.get('_independent'):independent(db,principal,principal['_write_area'])
    if tables.intersection({'adjustments','adjustment_revisions','review_events','field_verification_events','finding_adjustment_events','reconciliation_decisions'}):
        event(db,'legacy:'+uuid4().hex,'legacy_mutation','changed',principal['id'],{'tables':sorted(tables),'review_events':legacy_events})
    from app.services.product_service import invalidate_questions
    invalidate_questions(db,principal)
    from app.services.change_analysis_service import reassess
    reassess(db,principal,tables,legacy_events)
    invalidate(db)
    from app.services.lifecycle_service import invalidate as invalidate_lifecycle
    invalidate_lifecycle(db,principal)


def overview(actor):
    with connection() as db:
        require_access(db,actor,manage=actor['role']=='firm_administrator')
        tasks=entities(db,'task')
        for task in tasks:
            if task['state']!='complete' and task['data'].get('due_date','9999')<now()[:10] and task['data'].get('assignee'):
                notify(db,task['data']['assignee'],'Task overdue',task['id'],'overdue:'+task['id']+':'+str(task['revision']))
        from app.services.product_service import visible
        admin=actor['role']=='firm_administrator'
        allowed=lambda area:admin or visible(db,actor,area)
        return {'engagement':entity(db,ENGAGEMENT),'memberships':entities(db,'membership'),'staff':load_packet()['firm']['staff'],
                'policy':active_policy(db),'records':[] if admin else [e for e in entities(db,'record') if allowed(e['area'])],
                'notes':[] if admin else [e for e in entities(db,'note') if allowed(e['area'])],'tasks':[e for e in tasks if allowed(e['area'])],
                'notifications':[n for n in entities(db,'notification') if n['data']['recipient']==actor['id'] and (admin or allowed((entity(db,n['data']['resource']) or {}).get('area','engagement')))],
                'signoffs':[s for s in public_signoffs(db) if allowed(s['area'])],'areas':[a for a in AREAS if allowed(a)],'record_types':sorted(RECORD_TYPES),'available_verification_methods':load_packet()['firm']['starter_standards']['verification_types'],
                'demonstration':actor['assurance']=='demonstration','legal_signature':False}


def public_signoffs(db):
    return [{k:r[k] for k in ('id','area','level','staff_id','assurance','legal_signature','state','reason','created_at')} for r in db.execute('SELECT * FROM workflow_signoffs ORDER BY created_at')]


def assign(actor,data):
    with connection() as db:
        require_access(db,actor,manage=True)
        person=staff(data['staff_id'])
        responsibility=data['responsibility']
        if responsibility!=person['role']:fail('Assignments cannot promote staff into a different practice role',403)
        if responsibility=='firm_administrator':fail('Administrator does not receive tax preparation privileges through assignment',403)
        if not data['areas'] or any(a not in AREAS and a!='*' for a in data['areas']):fail('Invalid assignment scope')
        if responsibility in {'reviewer','partner'}:
            for member in entities(db,'membership'):
                if member['state']=='active' and member['data']['staff_id']==person['id'] and member['data']['responsibility']!=responsibility:
                    fail('Reviewer and partner responsibilities must be separated',409)
        result=put(db,'membership:'+person['id'],'membership','engagement',data['state'],{'staff_id':person['id'],'responsibility':responsibility,'areas':data['areas']},[],actor['id'],'assigned',data['expected_revision'])
        notify(db,person['id'],'Assignment updated',result['id'],'assignment:'+result['id']+':'+str(result['revision']))
        return result


def publish_policy(actor,data):
    with connection() as db:
        if actor['role']!='firm_administrator':fail('Firm administrator permission required',403)
        current=active_policy(db)
        if data['expected_revision']!=current['revision']:fail('Policy changed; reload',409)
        policy={**current['policy'],**data['changes']}
        if set(data['changes'])-{'partner_threshold','variance_review','verification_methods','required_areas'}:fail('Unsupported or non-waivable policy control')
        try:threshold=Decimal(str(policy['partner_threshold']))
        except (InvalidOperation,ValueError,TypeError):fail('Invalid partner approval threshold')
        if not threshold.is_finite() or threshold<0 or threshold>1000:fail('Partner threshold may only tighten the existing $1,000 ceiling')
        variance=policy['variance_review']
        if not isinstance(variance,dict):fail('Invalid variance policy')
        if set(variance)!={'compare_to','flag_if_change_over_percent','and_over_amount'} or variance['compare_to']!='prior_year':fail('Invalid variance policy')
        for key in ('flag_if_change_over_percent','and_over_amount'):
            try:val=Decimal(str(variance[key]))
            except (InvalidOperation,ValueError,TypeError):fail('Invalid variance threshold')
            if not val.is_finite() or val<0:fail('Variance thresholds must be finite and non-negative')
        allowed=load_packet()['firm']['starter_standards']['verification_types']
        if not policy['verification_methods'] or any(m not in allowed for m in policy['verification_methods']):fail('Invalid verification methods')
        # Additional areas may be required; existing mandatory areas cannot be removed.
        if set(AREAS[:-1])-set(policy['required_areas']) or any(a not in AREAS[:-1] for a in policy['required_areas']):fail('Mandatory review areas cannot be removed')
        identifier=uuid4().hex
        db.execute('INSERT INTO workflow_policies VALUES (?,?,?,?,?)',(identifier,current['revision']+1,json.dumps(policy,sort_keys=True),actor['id'],now()))
        root=entity(db,ENGAGEMENT);root['data']['policy_id']=identifier
        put(db,ENGAGEMENT,'engagement','engagement','active',root['data'],[],actor['id'],'policy_activated',root['revision'])
        event(db,identifier,'policy','activated',actor['id'],{'revision':current['revision']+1,'rationale':data['rationale']})
        return {'id':identifier,'revision':current['revision']+1,'policy':policy}


def validate_refs(refs):
    from app.services.evidence_service import resolve_reference
    if any(resolve_reference(r).status!='resolved' for r in refs):fail('Evidence reference is unresolved')


def save_record(actor,data):
    area=data['area']
    if area not in AREAS:fail('Unknown tax area')
    with connection() as db:
        require_access(db,actor,area)
        if actor['role'] not in PRACTICE_ROLES:fail('Tax-practice preparation permission required',403)
        if data['record_type'] not in RECORD_TYPES:fail('Unknown record type')
        validate_refs(data['refs'])
        identifier=data.get('id') or 'record:'+uuid4().hex
        previous=entity(db,identifier)
        if previous and (previous['kind']!='record' or previous['area']!=area):fail('Record kind and scope cannot be changed',409)
        if previous and identifier.startswith(('required:','diligence:')) and data['title']!=previous['data']['title']:fail('Required checklist identities and labels cannot be changed')
        content={k:data[k] for k in ('record_type','title','applicability','answer','authority','refs')}
        if previous and previous['data'].get('record_type')!=data['record_type']:fail('Record type cannot be changed',409)
        if data['record_type']=='document_disposition':
            if not any(r.startswith(('D','doc:')) for r in data['refs']):fail('Document disposition needs its source document')
        if data['record_type']=='preparation' and not data['answer'].strip():fail('Preparation attribution requires a statement')
        authors=(previous['authors'] if previous else [])+[actor['id']]
        return put(db,identifier,'record',area,'draft',content,authors,actor['id'],'revised',data['expected_revision'])


def record_action(actor,identifier,data):
    with connection() as db:
        record=entity(db,identifier)
        if not record or record['kind']!='record':fail('Workflow record not found',404)
        require_access(db,actor,record['area'])
        action=data['action']
        if action=='submit':
            if actor['role'] not in PRACTICE_ROLES or record['state'] not in {'draft','open'}:fail('Record cannot be submitted',409)
            content=record['data']
            if not content.get('answer','').strip() or not content.get('authority','').strip() or not content.get('refs'):fail('Answers, authority and evidence are required')
            if content.get('applicability')=='unknown':fail('Applicability assessment is required')
            state='submitted'
        elif action=='approve':
            independent(db,actor,record['area'])
            if actor['id'] in record['authors']:fail('Cannot approve an authored record',403)
            if record['state']!='submitted':fail('Only submitted records can be independently approved',409)
            state='approved'
        elif action=='reopen':
            if actor['role'] not in {'reviewer','partner'}:fail('Reviewer permission required',403)
            state='open'
        else:fail('Unknown workflow action')
        content={**record['data'],'last_action_note':data['note']}
        return put(db,identifier,'record',record['area'],state,content,record['authors'],actor['id'],action,data['expected_revision'])


def note_action(actor,data):
    with connection() as db:
        identifier=data.get('id') or 'note:'+uuid4().hex
        previous=entity(db,identifier)
        if previous and previous['kind']!='note':fail('Not a review note',404)
        area=previous['area'] if previous else data['area']
        require_access(db,actor,area)
        if actor['role'] not in PRACTICE_ROLES:fail('Tax-practice note permission required',403)
        action=data['action']
        transitions={'create':{'new'},'respond':{'open','reopened'},'request_resolution':{'responded'},'resolve':{'resolution_requested'},'reopen':{'resolved'}}
        old=previous['state'] if previous else 'new'
        if action not in transitions or old not in transitions[action]:fail('Invalid blocking-note transition',409)
        if action in {'resolve','reopen'}:
            independent(db,actor,area)
            if previous and previous['data'].get('responded_by')==actor['id']:fail('Resolution requires a different reviewer from the responder',403)
        state={'create':'open','respond':'responded','request_resolution':'resolution_requested','resolve':'resolved','reopen':'reopened'}[action]
        content={**(previous['data'] if previous else {}),'title':data['title'],'note':data['note'],'blocking':True,'owner_id':data['owner_id']}
        if action=='respond':content['responded_by']=actor['id']
        owner=staff(data['owner_id'])
        if not membership(db,owner):fail('Note owner must have an active engagement assignment',403)
        result=put(db,identifier,'note',area,state,content,[],actor['id'],action,data['expected_revision'])
        notify(db,data['owner_id'],'Blocking review note updated',identifier,'note:'+identifier+':'+str(result['revision']))
        return result


def sign(actor,data):
    with connection() as db:
        area=data['area'];level=data['level']
        if area not in AREAS:fail('Invalid sign-off scope')
        independent(db,actor,area)
        member=membership(db,actor)
        if member['data']['responsibility']!=level:fail('Assigned review responsibility does not match sign-off level',403)
        if level=='partner' and actor['role']!='partner':fail('Partner required',403)
        authors=contributors(db,area)
        if not authors:fail('Preparation attribution is missing; legacy free-text identities are not formal sign-offs',409)
        if any(n['state']!='resolved' and n['data'].get('blocking') for n in entities(db,'note') if area=='engagement' or n['area'] in {area,'engagement'}):fail('Open review notes block sign-off',409)
        if any(q['state']!='resolved' and q['data']['blocking'] for q in entities(db,'p_question') if area=='engagement' or q['area'] in {area,'engagement'}):fail('Open collaboration questions block sign-off',409)
        if any(a['state']!='reviewed' for a in entities(db,'p_attachment') if area=='engagement' or area in a['data']['areas']):fail('Uploaded supporting evidence requires independent support review before sign-off',409)
        if any(r['state']!='approved' for r in entities(db,'record') if r['area']==area and r['data'].get('record_type')!='preparation'):
            fail('Required scoped workflow records are incomplete',409)
        if level=='partner':
            reviewers=[r for r in db.execute("SELECT * FROM workflow_signoffs WHERE area=? AND level='reviewer' AND state='valid'",(area,))]
            if not reviewers or all(r['staff_id']==actor['id'] for r in reviewers):fail('A distinct current reviewer sign-off is required',409)
        current=manifest(db,area,level)
        if data['expected_digest']!=digest(current):fail('Dependencies changed; refresh before signing',409)
        identifier=uuid4().hex
        db.execute('INSERT INTO workflow_signoffs VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                   (identifier,ENGAGEMENT,area,level,actor['id'],actor['assurance'],0,json.dumps(current,sort_keys=True),'valid','Demonstration workpaper approval; never a legal electronic signature.',now()))
        event(db,identifier,'signoff','signed',actor['id'],{'area':area,'level':level,'assurance':actor['assurance'],'legal_signature':False,'note':data['note']})
        # A sign-off does not invalidate itself; children are dependencies only for engagement approvals.
        return {'id':identifier,'state':'valid','demonstration':actor['assurance']=='demonstration','legal_signature':False}


def signoff_preview(actor,area,level="reviewer"):
    with connection() as db:
        require_access(db,actor,area)
        return {'area':area,'digest':digest(manifest(db,area,level)),'contributors':sorted(contributors(db,area)),'legal_signature':False}


def revoke(actor,identifier,note):
    with connection() as db:
        row=db.execute('SELECT * FROM workflow_signoffs WHERE id=?',(identifier,)).fetchone()
        if not row:fail('Sign-off not found',404)
        independent(db,actor,row['area'])
        if row['state']!='valid':fail('This approval is already permanently invalid',409)
        db.execute("UPDATE workflow_signoffs SET state='revoked',reason=? WHERE id=?",(note,identifier))
        event(db,identifier,'signoff','revoked',actor['id'],{'note':note})
        return {'id':identifier,'state':'revoked','legal_signature':False}


def task_action(actor,data):
    with connection() as db:
        previous=entity(db,data['id'])
        if not previous or previous['kind'] not in {'task','notification'}:fail('Task or notification not found',404)
        if previous['kind']=='notification':
            if previous['data']['recipient']!=actor['id']:fail('Notification belongs to another staff member',403)
            if data['state']!='read':fail('Notifications can only be acknowledged')
            return put(db,previous['id'],'notification','engagement','read',previous['data'],[],actor['id'],'read',data['expected_revision'])
        require_access(db,actor,manage=actor['role']=='firm_administrator')
        if data.get('due_date'):
            from datetime import date
            try:date.fromisoformat(data['due_date'])
            except ValueError:fail('Invalid task deadline')
        if actor['role'] not in {'firm_administrator','partner'} and previous['data'].get('assignee')!=actor['id']:fail('Task assignment permission required',403)
        content={**previous['data'],'assignee':data['assignee'],'due_date':data['due_date'] or previous['data'].get('due_date')}
        if data['assignee']:staff(data['assignee'])
        if actor['role'] not in {'firm_administrator','partner'} and content['assignee']!=previous['data'].get('assignee'):fail('Cannot reassign this task',403)
        if data['state'] not in {'open','complete'}:fail('Invalid task state')
        result=put(db,previous['id'],'task',previous['area'],data['state'],content,[],actor['id'],'updated',data['expected_revision'])
        if content['assignee']:notify(db,content['assignee'],'Task assigned',result['id'],'task:'+result['id']+':'+str(result['revision']))
        return result


def readiness_from_facts(facts):
    blockers=[]
    for code,items in facts['checks'].items():
        if items:blockers.append({'code':code,'resources':items})
    return {'filing_ready':not blockers,'blockers':blockers,'legal_signature':False,
            'assurance':facts['assurance'],'label':'Demonstration readiness assessment' if facts['assurance']=='demonstration' else 'Workpaper readiness assessment; not filing authorization'}


def readiness(actor,record=False):
    from app.services.document_accountability_service import accountability
    from app.services import review_service
    from app.services.adjustment_service import read_one
    with connection() as db:
        require_access(db,actor,manage=actor['role']=='firm_administrator')
        invalidate(db)
        members=entities(db,'membership');records=entities(db,'record')
        approved=[r for r in records if r['state']=='approved']
        roles={m['data']['responsibility']:m['data']['staff_id'] for m in members if m['state']=='active'}
        checks={
          'MISSING_ASSIGNMENT':[r for r in ('preparer','reviewer','partner') if r not in roles],
          'INCOMPLETE_REQUIRED_STEP':[r['id'] for r in records if r['data'].get('record_type')=='required_step' and r['state']!='approved'],
          'INCOMPLETE_DILIGENCE':[r['id'] for r in records if r['data'].get('record_type')=='diligence' and r['state']!='approved'],
          'UNRESOLVED_PROFESSIONAL_QUESTION':[r['id'] for r in records if r['data'].get('record_type') in {'question','election','judgment'} and r['state']!='approved'],
          'REVIEW_REASSESSMENT_REQUIRED':[a['id'] for a in entities(db,'review_assessment') if a['state']=='needs_reassessment'],
          'OPEN_BLOCKING_NOTE':[n['id'] for n in entities(db,'note') if n['state']!='resolved'],
          'OPEN_BLOCKING_QUESTION':[q['id'] for q in entities(db,'p_question') if q['data']['blocking'] and q['state']!='resolved'],
          'UPLOADED_EVIDENCE_REVIEW_REQUIRED':[a['id'] for a in entities(db,'p_attachment') if a['state']!='reviewed'],
        }
        for role,identifier in roles.items():
            try:staff(identifier)
            except Exception:checks.setdefault('INACTIVE_ASSIGNMENT',[]).append(identifier)
        dispositions={ref[4:].split('#')[0] if ref.startswith('doc:') else ref for r in approved if r['data'].get('record_type')=='document_disposition' for ref in r['data'].get('refs',[])}
        checks['DOCUMENT_REVIEW_REQUIRED']=[d['id'] for d in accountability()['documents'] if set(d['dispositions']).intersection({'requires_review','unused','unextracted'}) and d['id'] not in dispositions]
        from app.services.finding_service import build_catalog
        states={r['finding_id']:r['status'] for r in db.execute('SELECT * FROM reviews WHERE version="v3"')}
        reviews=[{**f,'status':states.get(f['id'],f.get('status','open'))} for f in build_catalog()['findings']]
        checks['UNRESOLVED_FINDING']=[f['id'] for f in reviews if f['status']!='resolved']
        from app.services.reconciliation_service import run_reconciliations
        checks['UNSUPPORTED_TAX_CALCULATION']=[c['id'] for c in run_reconciliations()['checks'] if c['conclusion']=='unsupported']
        adjustments=[read_one(db,r[0]) for r in db.execute('SELECT id FROM adjustments WHERE version="v3"')];threshold=Decimal(str(active_policy(db)['policy']['partner_threshold']))
        checks['UNAPPROVED_OR_STALE_ADJUSTMENT']=[a['id'] for a in adjustments if a['stale'] or a['state'] in {'draft','submitted','rejected'}]
        from app.services.adjustment_service import packet_hash
        latest={}
        for v in db.execute('SELECT * FROM field_verification_events WHERE version="v3" ORDER BY id'):latest[v['evidence_id']]=dict(v)
        checks['EVIDENCE_VERIFICATION_REQUIRED']=[e['id'] for e in load_packet()['extracted_values'] if e.get('confidence',1)<0.9 and not (e['id'] in latest and latest[e['id']]['status']=='confirmed' and latest[e['id']]['packet_hash']==packet_hash())]
        checks['STALE_OR_UNRESOLVED_VERIFICATION']=[e['evidence_id'] for e in latest.values() if e['status']!='confirmed' or e['packet_hash']!=packet_hash()]
        checks['CURRENT_POLICY_APPROVAL_REQUIRED']=[]
        for a in adjustments:
            if a['state']=='approved':
                from app.services.adjustment_service import calculate,version_data
                requires=calculate(version_data(a['version']),a['payload']['target'],Decimal(a['payload']['delta']),threshold)['requires_partner']
                approval=db.execute("SELECT actor_role FROM adjustment_events WHERE adjustment_id=? AND action='approve' ORDER BY id DESC LIMIT 1",(a['id'],)).fetchone()
                if requires and (not approval or approval[0]!='partner'):checks['CURRENT_POLICY_APPROVAL_REQUIRED'].append(a['id'])
        current_signoffs=[dict(r) for r in db.execute("SELECT * FROM workflow_signoffs WHERE state='valid'")]
        checks['MISSING_CURRENT_SIGNOFF']=[area+':'+level for area in active_policy(db)['policy']['required_areas']+['engagement'] for level in ('reviewer','partner') if not any(s['area']==area and s['level']==level for s in current_signoffs)]
        # The supplied engine cannot be rerun and the packet's later filing/signature events
        # are scripted. There is deliberately no API knob that manufactures this evidence.
        checks['FINAL_RETURN_AND_CLIENT_AUTHORIZATION_UNVERIFIED']=['authoritative final return','actual return-bound client authorization']
        result=readiness_from_facts({'checks':checks,'assurance':actor['assurance']})
        result.update(engagement_id=ENGAGEMENT,policy_id=active_policy(db)['id'],evaluated_at=now(),digest=digest(manifest(db,'engagement')))
        if record:
            identifier=uuid4().hex
            db.execute('INSERT INTO workflow_readiness_evaluations VALUES (?,?,?,?,?)',(identifier,ENGAGEMENT,actor['id'],json.dumps(result,sort_keys=True),now()))
            result['evaluation_id']=identifier
        return result


def transfer_ownership(actor,data):
    with connection() as db:
        require_access(db,actor,manage=True)
        person=staff(data['owner_id'])
        if person['role']!='partner' or not membership(db,person):fail('Engagement owner must be an assigned active partner',403)
        root=entity(db,ENGAGEMENT)
        return put(db,ENGAGEMENT,'engagement','engagement','active',{**root['data'],'owner_id':person['id']},[],actor['id'],'ownership_transferred',data['expected_revision'])
