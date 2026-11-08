"""Time-bounded packet views. Scripted replay never mutates live workpaper state."""
from copy import deepcopy
from datetime import datetime,timezone
from functools import lru_cache
import json,re
from app.services.packet_service import load_packet
from app.services.evidence_service import resolve_reference,EvidenceResolution,reference_strings
from app.services.adjustment_service import fail
from app.services import workflow_service as workflow


def instant(value):
    try:
        if len(value)==10:value+='T23:59:59.999999+00:00'  # date-only availability is conservative
        result=datetime.fromisoformat(value.replace('Z','+00:00'))
        if result.tzinfo is None:raise ValueError()
        return result.astimezone(timezone.utc)
    except (ValueError,TypeError):fail('An ISO date or timestamp with timezone is required')


class HistoricalContext:
    def __init__(self,at,packet=None):
        self.at=instant(at);self.original=packet or load_packet();self.packet=deepcopy(self.original);self.blocked=set();self.cache={}
        self.document_dates={d['id']:instant(d['received_at']) for d in self.original['documents']}
        self.packet['documents']=[d for d in self.packet['documents'] if self.document_dates[d['id']]<=self.at]
        available={d['id'] for d in self.packet['documents']}
        self.packet['extracted_values']=[e for e in self.packet['extracted_values'] if e['document_id'] in available]
        for name,key in [('questionnaire','answered_at'),('messages','sent_at'),('call_notes','date')]:
            self.packet['client'][name]=[c for c in self.packet['client'][name] if instant(c[key])<=self.at]
        self.packet['timeline']=[e for e in self.packet['timeline'] if instant(e['at'])<=self.at]
        self.packet['return_versions']=[v for v in self.packet['return_versions'] if instant(v['computed_at'])<=self.at]
        # No dated knowledge contract exists for the full raw packet/household before organizer delivery.
        if self.at<instant('2026-01-20T04:00:00Z'):self.packet['household']={'people':[]}
        if not {'D06','D07'}<=available:
            self.packet['prior_years']={};self.blocked.add('py:')
        self.packet['tax_agency_records']=self.filter_dated(self.packet['tax_agency_records'],'agency:')
        # Never expose future snapshots by changing their JSON Pointer indices.
        self.version=self.packet['return_versions'][-1]['version'] if self.packet['return_versions'] else None

    def filter_dated(self,value,path):
        if isinstance(value,dict):
            dates=[value[k] for k in ('as_of','dated','date') if isinstance(value.get(k),str)]
            doc=value.get('document')
            future=any(instant(d)>self.at for d in dates) or (doc in self.document_dates and self.document_dates[doc]>self.at)
            if path.startswith('agency:/irs_account_transcript_2025') and self.document_dates['D69']>self.at:future=True
            if path.startswith('agency:/ftb_account') and self.document_dates['D69']>self.at:future=True
            if future:self.blocked.add(path);return None
            return {k:self.filter_dated(v,path+'/'+k.replace('~','~0').replace('/','~1')) for k,v in value.items()}
        if isinstance(value,list):return [self.filter_dated(v,path+'/'+str(i)) for i,v in enumerate(value)]
        return value

    def unavailable(self,ref,version,reason='not_available_at_selected_time'):
        return EvidenceResolution(ref=ref,version=version or 'none',type='unknown',status='unresolved',reason_code=reason,
                                  reason='Reference or a required dependency is not available in this historical context. No future value is supplied.')

    def resolve(self,ref,version=None,path=()):
        version=version or self.version
        key=(ref,version)
        if key in self.cache:return self.cache[key]
        if version and not any(v['version']==version for v in self.packet['return_versions']):return self.unavailable(ref,version,'version_not_available_at_selected_time')
        if not version and ref.startswith(('ref:param.','ref:fx.')):return self.unavailable(ref,version,'parameter_availability_not_established')
        if ref in path:return self.unavailable(ref,version,'cyclic_historical_dependency')
        if any(ref==b or ref.startswith(b+'/') or b=='py:' and ref.startswith(b) for b in self.blocked):return self.unavailable(ref,version)
        if ref in {v['version'] for v in self.original['return_versions']}:
            v=next((v for v in self.packet['return_versions'] if v['version']==ref),None)
            return EvidenceResolution(ref=ref,version=version,type='return_version',status='resolved',reason='Stored version existed at this time.',value={'version':ref,'computed_at':v['computed_at']} if v else None) if v else self.unavailable(ref,version)
        source_packet=self.packet if version else {**self.packet,'return_versions':[{'version':'source-only','lines':[],'assets':[]}]}
        result=resolve_reference(ref,version or 'source-only',source_packet)
        if not version:result=result.model_copy(update={'version':'none'})
        if result.status!='resolved':return self.unavailable(ref,version,'unknown_or_unavailable_reference')
        # Container records may have a later dated, source-linked child; withhold it rather than speculate.
        for related in result.related_refs:
            if self.resolve(related,version,path+(ref,)).status!='resolved':
                result=self.unavailable(ref,version);break
        self.cache[key]=result
        return result

    def evidence(self,ref,version=None):
        version=version or self.version;nodes={};cycles=[]
        def visit(current,path):
            if current in path:cycles.append({'from':path[-1],'to':current});return
            if current in nodes:return
            node=self.resolve(current,version);nodes[current]=node.model_dump()
            for related in node.related_refs:visit(related,path+[current])
        visit(ref,[])
        return {'mode':'historical','as_of':self.at.isoformat(),'version':version,'reference':ref,'resolution':nodes[ref],
                'nodes':list(nodes.values()),'unresolved':[n for n in nodes.values() if n['status']=='unresolved'],
                'document_ids':sorted({d for n in nodes.values() for d in n['document_ids']}),'cycles':cycles,'changes_current_state':False}

    def snapshot(self):
        baseline=next((v for v in self.packet['return_versions'] if v['version']==self.version),None)
        lines=[];withheld=[]
        if baseline:
            for line in baseline['lines']:
                result=self.resolve(line['key'])
                if result.status=='resolved':lines.append(line)
                else:withheld.append({'key':line['key'],'reason':'Supporting dependencies unavailable or unresolved; value withheld.'})
        corrections=[]
        from app.services.change_analysis_service import compare_lines
        for before,after in zip(self.packet['return_versions'],self.packet['return_versions'][1:]):
            for change in compare_lines(before,after):
                if change['change']=='unchanged':continue
                if any(line is not None and self.resolve(change['key'],v['version']).status!='resolved' for v,line in ((before,change['old']),(after,change['new']))):continue
                corrections.append({'key':change['key'],'before':before['version'],'after':after['version'],'at':after['computed_at'],'change':change['change'],'old':change['old']['value'] if change['old'] else None,'new':change['new']['value'] if change['new'] else None,'difference':change['numeric_difference'],'reason':after['trigger'],'origin':'stored_engine_version_change'})
        findings=[]
        if baseline:
            for index,d in enumerate(baseline.get('diagnostics',[])):
                if all(self.resolve(r).status=='resolved' for r in d.get('refs',[])):
                    findings.append({'id':f"engine:{self.version}:{d['code']}:{index}",'origin':'stored_engine_diagnostic','status':'as_reported_not_reviewed',**d})
        events=[]
        for e in self.packet['timeline']:
            known=[r for r in e.get('refs',[]) if self.resolve(r).status=='resolved']
            events.append({**e,'refs':known,'origin':'scripted_packet_history','completes_live_workflow':False})
        # Include each arrival, not merely the subset represented by scripted timeline events.
        events.extend({'id':'arrival:'+d['id'],'at':d['received_at'],'event':'document_arrival','actor':None,'detail':d['title'],'refs':[d['id']],'origin':'packet_received_at','completes_live_workflow':False} for d in self.packet['documents'])
        events.sort(key=lambda e:(instant(e['at']),e['id']))
        with workflow.connection() as db:
            activity=[]
            for row in db.execute('SELECT * FROM review_events ORDER BY id'):
                if instant(row['created_at'])<=self.at and any(v['version']==row['version'] for v in self.packet['return_versions']):
                    # Current catalog/narratives can contain later knowledge; only actual audit metadata is replayed.
                    activity.append({'id':row['id'],'at':row['created_at'],'event':'documented_review_'+row['new_status'],'actor':row['actor_name'],'origin':'actual_workpaper_audit','version':row['version']})
            adjustments={}
            for row in db.execute('SELECT * FROM adjustment_events ORDER BY id'):
                if instant(row['created_at'])>self.at:continue
                snapshot=json.loads(row['snapshot_json'])
                if not any(v['version']==snapshot['version'] for v in self.packet['return_versions']) or any(self.resolve(r,snapshot['version']).status!='resolved' for r in snapshot['payload']['refs']) or self.resolve(snapshot['payload']['target'],snapshot['version']).status!='resolved':continue
                adjustments[row['adjustment_id']]={'id':row['adjustment_id'],'state':row['new_state'],'sequence':snapshot['sequence'],'revision':snapshot['revision'],'at':row['created_at'],'target':snapshot['payload']['target'],'version':snapshot['version'],'payload':snapshot['payload'],'origin':'actual_workpaper_audit'}
            verification_activity=[{k:r[k] for k in ('id','version','evidence_id','verifier_id','method','status','created_at')} for r in db.execute('SELECT * FROM field_verification_events ORDER BY id') if instant(r['created_at'])<=self.at and self.resolve(r['evidence_id'],r['version']).status=='resolved' and self.resolve(r['source_ref'],r['version']).status=='resolved']
            workflow_activity=[{'id':r['id'],'at':r['created_at'],'event':r['kind']+':'+r['action'],'actor':r['actor_id'],'origin':'actual_workpaper_audit'} for r in db.execute('SELECT * FROM workflow_events ORDER BY id') if instant(r['created_at'])<=self.at]
        return {'mode':'historical','as_of':self.at.isoformat(),'active_version':self.version,
                'versions':[{'version':v['version'],'computed_at':v['computed_at']} for v in self.packet['return_versions']],
                'documents':[{'id':d['id'],'title':d['title'],'received_at':d['received_at'],'extraction':d['extraction']} for d in self.packet['documents']],
                'communications':self.packet['client'],'events':events,'lines':lines,'withheld_lines':withheld,'findings':findings,
                'corrections':corrections,'verification_activity':verification_activity,'review_activity':activity,'workflow_activity':workflow_activity,'adjustments':list(adjustments.values()),
                'independent_findings':'Not reconstructed: current reconciliation catalogs may incorporate later evidence. Only time-eligible stored diagnostics appear.',
                'summary':{'classification':'stored_engine_snapshot_not_verified','values':baseline['summary']} if baseline else None,
                'changes_current_state':False,'warning':'Read-only historical snapshot. Filing events are scripted; they do not sign, approve, file, pay, resolve notes or clear current readiness.'}


def replay(at):return HistoricalContext(at).snapshot()
def replay_evidence(at,ref,version=None):return HistoricalContext(at).evidence(ref,version)
