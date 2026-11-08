"""Stored-version comparisons and supported alternatives; never a tax-engine rerun."""
from copy import deepcopy
from decimal import Decimal,InvalidOperation
from functools import lru_cache
from itertools import combinations
from uuid import uuid4
import json

from app.services.packet_service import load_packet
from app.services.adjustment_service import fail,version_data,read_one
from app.services.evidence_service import evidence_graph,resolve_reference
from app.services.finding_service import build_catalog,area_for
from app.services import workflow_service as workflow


def number(value):
    if isinstance(value,bool) or not isinstance(value,(int,float,Decimal)):return None
    try:
        result=Decimal(str(value))
        return result if result.is_finite() else None
    except InvalidOperation:return None


def differences(old,new):
    a,b=number(old),number(new)
    if a is None or b is None:return {'numeric_difference':None,'percent_difference':None,'percentage_reason':'Values are missing or nonnumeric.'}
    return {'numeric_difference':format(b-a,'f'),'percent_difference':format((b-a)/abs(a)*100,'f') if a else None,
            'percentage_reason':None if a else 'Zero baseline; percentage change is undefined.'}


def compare_lines(left,right):
    a={l['key']:l for l in left['lines']};b={l['key']:l for l in right['lines']};result=[]
    for key in sorted(a.keys()|b.keys()):
        old,new=a.get(key),b.get(key)
        change='added' if old is None else 'removed' if new is None else 'changed' if old!=new else 'unchanged'
        line=new or old
        diff=differences(old['value'] if old else None,new['value'] if new else None)
        monetary=number(line['value']) is not None and not (isinstance(line['value'],bool) or any(word in line.get('label','').lower() for word in ('ratio','percent','rate','days','miles','units','shares','year','number of','quantity')) or key in {'F540NR.34','F540NR.36'})
        result.append({'key':key,'change':change,'value_changed':old is None or new is None or old['value']!=new['value'],
                       'old':old,'new':new,**diff,'dollar_difference':diff['numeric_difference'] if monetary else None,
                       'unit':'dollars' if monetary else 'nonmonetary_or_unspecified','metadata_changed':old is not None and new is not None and {k:v for k,v in old.items() if k!='value'}!={k:v for k,v in new.items() if k!='value'}})
    return result


@lru_cache(maxsize=16000)
def packet_resolution(ref,version):return resolve_reference(ref,version).model_dump()

def resolution(ref,version):
    if ref.startswith(('attachment:','question:','discussion:')):return resolve_reference(ref,version).model_dump()
    return packet_resolution(ref,version)

@lru_cache(maxsize=4096)
def packet_graph(ref,version):return uncached_graph(ref,version)

def graph(ref,version):
    if ref.startswith(('attachment:','question:','discussion:')):return uncached_graph(ref,version)
    return packet_graph(ref,version)

def uncached_graph(ref,version):
    nodes={};cycles=[]
    def visit(current,path):
        if current in path:cycles.append({'from':path[-1],'to':current});return
        if current in nodes:return
        node=resolution(current,version);nodes[current]=node
        for related in node['related_refs']:visit(related,path+[current])
    visit(ref,[])
    return {'resolution':nodes[ref],'nodes':list(nodes.values()),'document_ids':sorted({d for n in nodes.values() for d in n['document_ids']}),
            'unresolved':[n for n in nodes.values() if n['status']=='unresolved'],'cycles':cycles}



def source_summary(ref,version):
    g=graph(ref,version)
    return {'refs':[n['ref'] for n in g['nodes']], 'document_ids':g['document_ids'],
            'unresolved':[{'ref':n['ref'],'reason_code':n['reason_code'],'reason':n['reason']} for n in g['unresolved']]}


def support_link(ref,version):
    summary=source_summary(ref,version)
    return {'document_ids':summary['document_ids'],'refs':resolution(ref,version)['related_refs'],
            'unresolved':summary['unresolved'],'graph_reference':ref,'version':version}


def catalog_map(version):return {f['issue_key']:f for f in build_catalog(version)['findings']}


def collection_diff(left,right,key):
    def indexed(items):
        result={};seen={}
        for item in items:
            identity=key(item);ordinal=seen.get(identity,0);seen[identity]=ordinal+1
            result[identity+'#'+str(ordinal)]=item
        return result
    a=indexed(left);b=indexed(right)
    return [{'identity':k,'change':'added' if k not in a else 'removed' if k not in b else 'changed' if a[k]!=b[k] else 'unchanged','old':a.get(k),'new':b.get(k)} for k in sorted(a.keys()|b.keys())]


def comparison(before='v1',after='v3'):
    left,right=version_data(before),version_data(after)
    lines=compare_lines(left,right)
    for item in lines:
        if item['change']=='unchanged':continue
        key=item['key'];item['support']={v:support_link(key,v) for v,line in ((before,item['old']),(after,item['new'])) if line is not None}
        item['reasons']={'engine_trigger':right['trigger'],'line_notes':{v:l.get('note') for v,l in ((before,item['old']),(after,item['new'])) if l and l.get('note')},
                        'declared_changes':[{'version':v['version'],**c} for v in load_packet()['return_versions'] if min(left['computed_at'],right['computed_at'])<v['computed_at']<=max(left['computed_at'],right['computed_at']) for c in v.get('changes_from_previous',[]) if c['key']==key],
                        'attribution':'Triggers and notes are packet explanations, not proof of causality. Actual diff is computed from stored lines.'}
    with workflow.connection() as db:
        def review_findings(v):
            states={r['finding_id']:dict(r) for r in db.execute('SELECT * FROM reviews WHERE version=?',(v,))}
            return [{**f,'current_review':states.get(f['id']), 'review_validity':workflow.entity(db,'assessment:'+v+':'+f['id'])} for f in catalog_map(v).values()]
        adjustments={v:[read_one(db,r[0]) for r in db.execute('SELECT id FROM adjustments WHERE version=?',(v,))] for v in dict.fromkeys((before,after))}
        findings=collection_diff(review_findings(before),review_findings(after),lambda f:f['issue_key'])
    return {'mode':'stored_engine_comparison','before':before,'after':after,'versions':[{'version':v['version'],'computed_at':v['computed_at'],'trigger':v['trigger'],'summary':v['summary']} for v in load_packet()['return_versions']],
            'version_matrix':[{'key':k,'values':{v['version']:next(({'present':True,'value':l['value'],'label':l['label']} for l in v['lines'] if l['key']==k),{'present':False,'value':None}) for v in load_packet()['return_versions']}} for k in sorted({l['key'] for v in load_packet()['return_versions'] for l in v['lines']})],
            'lines':lines,'counts':{s:sum(l['change']==s for l in lines) for s in ('added','removed','changed','unchanged')},
            'diagnostics':collection_diff(left.get('diagnostics',[]),right.get('diagnostics',[]),lambda x:x['code']+':'+','.join(x.get('refs',[]))),
            'findings':findings,'adjustments':adjustments,'review_scope':'Current persistent reviews and adjustments for each engine baseline; not historical workflow snapshots.',
            'warning':'Stored engine results may contain mistakes. Comparison does not approve corrections or recompute taxes.'}


def alternatives(version='v3',ids=None):
    baseline=version_data(version);items=deepcopy(load_packet()['what_if']['alternatives'])
    for item in items:
        item['compatible']=item['base_version']==version
        item['classification']='stored_engine_alternative';item['authoritative_calculation']=False
        item['support']={c['key']:support_link(c['key'],item['base_version']) for c in item['changed_lines']}
        source=version_data(item['base_version']);index={l['key']:l for l in source['lines']}
        item['baseline_checks']=[{'key':c['key'],'status':'matches' if c['key'] in index and index[c['key']]['value']==c.get('old') else 'missing' if c['key'] not in index else 'mismatch','reported_old':c.get('old'),'stored_baseline':index.get(c['key'],{}).get('value')} for c in item['changed_lines']]
        summary_checks=[]
        for jurisdiction in ('federal','california'):
            for key,value in item[jurisdiction]['base'].items():
                if source['summary'][jurisdiction].get(key)!=value:summary_checks.append(jurisdiction+'.'+key)
        item['baseline_summary_mismatches']=summary_checks
        item['compatible']=item['compatible'] and not summary_checks and all(c['status']=='matches' for c in item['baseline_checks'])
        item['compatibility_reason']='Compatible with the original stored baseline only.' if item['compatible'] else 'Wrong baseline or supplied alternative does not agree with its stored baseline; do not apply.'
        item['effect_checks']={j:{k:('not_supplied' if k not in item[j] else 'matches' if number(item[j]['alternative'][field])-number(item[j]['base'][field])==number(item[j][k]) else 'mismatch') for k,field in (('total_tax_change','total_tax'),('penalty_change','penalty'))} for j in ('federal','california')}
    selected=[];unknown=[]
    for identifier in ids or []:
        candidate=next((i for i in items if i['id']==identifier),None)
        if candidate is None:unknown.append(identifier)
        elif not any(i['id']==identifier for i in selected):selected.append(candidate)
    conflicts=[]
    for a,b in combinations(selected,2):
        choices=[k for k in a['choices'] if k in b['choices'] and a['choices'][k]!=b['choices'][k]]
        if choices:conflicts.append({'alternatives':[a['id'],b['id']],'choices':choices,'reason':'Mutually exclusive treatments for the same election or asset.'})
    unsupported=[]
    if len(selected)>1:unsupported.append('No combined engine result is supplied. Effects are shown separately; never add savings, even when choices are not mutually exclusive.')
    if unknown:unsupported.append('No computation result is supplied for unknown scenario IDs.')
    if any(not i['compatible'] for i in selected):unsupported.append('Selected alternatives are incompatible with the requested baseline.')
    with workflow.connection() as db:
        active_adjustments=[r[0] for r in db.execute("SELECT id FROM adjustments WHERE version=? AND state IN ('submitted','approved')",(version,))]
    if active_adjustments:unsupported.append('Existing submitted/approved adjustments are not reflected in stored alternatives; their interactions are unsupported.')
    return {'mode':'hypothetical','baseline':version,'alternatives':items,'selected':selected,'unknown':unknown,'conflicts':conflicts,
            'selection_valid':not unknown and not conflicts and all(i['compatible'] for i in selected),'combined_result':None,
            'warnings':['Alternatives always use the original unadjusted engine baseline; current ledger changes are never incorporated.','Stored alternatives are simplified engine results, not authoritative calculations. California AMT is not computed. No result is an approved adjustment.',*unsupported],
            'active_adjustment_ids':active_adjustments,'extension':deepcopy(load_packet()['what_if']['extension']),
            'extension_compatible':load_packet()['what_if']['extension']['based_on_version']==baseline['version']}


def save_analysis(actor,data):
    result=alternatives(data['version'],data['scenario_ids'])
    if not result['selection_valid']:fail('Incompatible, conflicting or unsupported scenario selection',409)
    if not result['selected']:fail('Select at least one supplied alternative')
    with workflow.connection() as db:
        workflow.require_access(db,actor,'engagement')
        if actor['role'] not in workflow.PRACTICE_ROLES:fail('Tax-practice analysis permission required',403)
        identifier=data.get('id') or 'analysis:'+uuid4().hex
        previous=workflow.entity(db,identifier)
        if data.get('id') and not previous:fail('Saved analysis not found',404)
        if previous and previous['kind']!='scenario_analysis':fail('Only a saved hypothetical analysis may be revised through this endpoint',409)
        if not data['note'].strip():fail('An analysis rationale is required')
        authors=(previous['authors'] if previous else [])+[actor['id']]
        return workflow.put(db,identifier,'scenario_analysis','engagement','hypothetical',
                            {'version':data['version'],'scenario_ids':data['scenario_ids'],'note':data['note'],'packet_hash':workflow.digest(load_packet()),'result':result},authors,actor['id'],'scenario_saved',data['expected_revision'])


def analysis_history(actor):
    with workflow.connection() as db:
        workflow.require_access(db,actor)
        return {'analyses':workflow.entities(db,'scenario_analysis'),'events':[{**dict(r),'payload':json.loads(r['payload_json'])} for r in db.execute("SELECT * FROM workflow_events WHERE kind='scenario_analysis' ORDER BY id")], 'mode':'hypothetical','changes_current_tax':False}


def impacted(refs,version='v3'):
    baseline=version_data(version);seeds=set(refs);affected=[];all_refs=set(seeds)
    policy_change='policy:current' in seeds
    for line in baseline['lines']:
        support=source_summary(line['key'],version)
        if policy_change or seeds.intersection(support['refs']) or seeds.intersection(support['document_ids']):affected.append(line['key']);all_refs.update(support['refs'])
    findings=[{'id':f['id'],'area':f['area'],'refs':f['refs']} for f in build_catalog(version)['findings'] if policy_change or set(f['refs']).intersection(set(affected)|seeds) or any(seeds.intersection(source_summary(r,version)['refs']) or seeds.intersection(source_summary(r,version)['document_ids']) for r in f['refs'])]
    areas={area_for(k) for k in affected}|{f['area'] for f in findings}
    if policy_change:areas.update(workflow.AREAS)
    return {'refs':sorted(seeds),'version':version,'affected_lines':affected,'areas':sorted(areas-{'other'}),'findings':findings,
            'unresolved':[r for r in refs if r!='policy:current' and graph(r,version)['resolution']['status']!='resolved'],'mode':'current_impact_preview','mutates_approvals':False}


def fingerprint(db,version,finding):
    refs=set(finding['refs']);nodes={};docs=set()
    for ref in refs:
        g=graph(ref,version);docs.update(g['document_ids'])
        nodes.update({n['ref']:n for n in g['nodes']})
    adjustments=[]
    for row in db.execute('SELECT id FROM adjustments WHERE version=?',(version,)):
        a=read_one(db,row[0])
        if a['payload']['target'] in nodes or refs.intersection(a['payload']['refs']):adjustments.append(a)
    evidence_ids={e['id'] for e in load_packet()['extracted_values'] if e['document_id'] in docs}
    verifications=[dict(r) for r in db.execute('SELECT id,evidence_id,sequence,status,packet_hash FROM field_verification_events WHERE version=?',(version,)) if r['evidence_id'] in evidence_ids]
    links=[dict(r) for r in db.execute('SELECT * FROM finding_adjustment_events WHERE version=? AND finding_id=?',(version,finding['id']))]
    records=[r for r in workflow.entities(db) if (r['kind'] in {'record','note'} and r['area'] in {finding['area'],'engagement'} or r['kind']=='lc_payment' and finding['area']=='payments' or r['kind']=='lc_carryover' and finding['area']=='carryovers' and r['data']['version']==version)]
    from app.services.product_service import evidence_dependencies
    supplemental=evidence_dependencies(db,finding['area'] if finding['area'] in workflow.AREAS else 'engagement')
    return workflow.digest({**({'supplemental_evidence':supplemental} if supplemental else {}),'records':records,'nodes':nodes,'adjustments':adjustments,'verifications':verifications,'policy':workflow.active_policy(db),'links':links})


def reassess(db,principal,tables,review_event_ids=()):
    """Called inside the original mutation's transaction, before signature invalidation."""
    relevant={'adjustments','adjustment_revisions','review_events','field_verification_events','finding_adjustment_events','reconciliation_decisions','workflow_policies','workflow_entities'}
    if not tables.intersection(relevant):return
    for version in ('v1','v2','v3'):
        resolved=db.execute("SELECT * FROM reviews WHERE version=? AND status='resolved'",(version,)).fetchall()
        if not resolved:continue
        catalog={f['id']:f for f in build_catalog(version)['findings']}
        for review in resolved:
            finding=catalog.get(review['finding_id'])
            if finding is None:continue
            identifier='assessment:'+version+':'+finding['id'];previous=workflow.entity(db,identifier)
            latest=db.execute('SELECT id FROM review_events WHERE version=? AND finding_id=? ORDER BY id DESC LIMIT 1',(version,finding['id'])).fetchone()
            event_id=latest[0] if latest else None;current=fingerprint(db,version,finding)
            new_decision=event_id in review_event_ids
            state='current' if new_decision else 'needs_reassessment' if not previous or previous['data']['fingerprint']!=current else previous['state']
            if previous and state==previous['state'] and not new_decision:continue
            data={'version':version,'finding_id':finding['id'],'review_event_id':event_id,'fingerprint':current if state=='current' else previous['data']['fingerprint'] if previous else current,
                  'reason':'New documented resolution bound to current dependencies.' if state=='current' else 'Relevant dependencies changed or a legacy resolution has no dependency binding. Original review history is preserved.'}
            workflow.put(db,identifier,'review_assessment',finding['area'],state,data,[],principal['id'],'review_reassessed')


def impact_report(refs,version='v3'):
    result=impacted(refs,version)
    with workflow.connection() as db:
        result['assessments']=workflow.entities(db,'review_assessment')
        relevant_areas=set(result['areas']);relevant_refs=set(refs)
        result['approvals']=[]
        for row in db.execute('SELECT * FROM workflow_signoffs ORDER BY created_at'):
            manifest=json.loads(row['manifest_json'])
            _,nodes,docs=workflow.scope_resources(row['area'])
            if row['area']=='engagement' or row['area'] in relevant_areas or relevant_refs.intersection(nodes) or relevant_refs.intersection(docs):
                result['approvals'].append({k:row[k] for k in ('id','area','level','state','reason','staff_id')})
        result['events']=[{**dict(r),'payload':json.loads(r['payload_json'])} for r in db.execute("SELECT * FROM workflow_events WHERE kind IN ('impact','review_assessment','signoff','legacy_mutation','policy') ORDER BY id")]
    result['warning']='Preview does not apply a change. Actual supported mutations reassess decisions and invalidate dependent approvals transactionally. Hypothetical selections and replay do not.'
    return result


def record_impact(actor,data):
    report=impact_report(data['refs'],data['version'])
    if report['unresolved']:fail('Resolve unsupported references before recording an impact assessment')
    with workflow.connection() as db:
        workflow.require_access(db,actor,'engagement')
        if actor['role'] not in {'reviewer','partner'}:fail('Independent reviewer or partner required',403)
        reassess(db,actor,{'adjustments'})
        workflow.invalidate(db)
        workflow.event(db,'impact:'+uuid4().hex,'impact','assessed',actor['id'],{'note':data['note'],'version':data['version'],'refs':data['refs'],'affected_lines':report['affected_lines'],'areas':report['areas']})
    return impact_report(data['refs'],data['version'])
