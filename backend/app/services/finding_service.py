"""Unified issue catalog. Legacy finding identities are never reassigned."""
from copy import deepcopy
from app.services.packet_service import load_packet
from app.services.validation_service import run_validation
from app.services.reconciliation_service import run_reconciliations

ENGINE_ISSUES = {'DIGITAL_ASSET_BASIS_MISSING':'investment.crypto_basis',
                 'BROKER_SUMMARY_DETAIL_MISMATCH':'investment.meridian_summary',
                 'CA_AMT_NOT_COMPUTED':'california.amt',
                 'SCORP_BASIS_INCOMPLETE':'k1.stock_basis',
                 'LOW_CONFIDENCE_READ':'deductions.cash_gift'}
CHECK_ISSUES = {'business.conditional_bridge':'business.books_bridge','vehicle.deduction':'vehicle.miles',
                'investment.lot.D31.M18':'investment.meridian_summary',
                'investment.lot.D30.M18':'investment.meridian_summary',
                **{'investment.lot.D28.'+k:'investment.stock_comp_basis' for k in ('N1','N3','N4')}}
ISSUE_CONCLUSIONS = {'exact_mismatch','material_discrepancy','unsupported','conflicting_sources','judgment_required'}


def area_for(key):
    for prefix,area in [('SchC','business'),('SchSE','business'),('F8949','investments'),('SchD','investments'),
                        ('SchB','investments'),('F4797','depreciation'),('F4562','depreciation'),('asset:','depreciation'),
                        ('SchA','itemized'),('F8283','itemized'),('F8582','rentals'),('SchE','rentals'),
                        ('F7203','pass_throughs'),('F540','california'),('SchCA','california')]:
        if key.startswith(prefix):return area
    return 'other'


def build_catalog(version='v3', legacy=None):
    packet = load_packet()
    base = legacy if legacy is not None else run_validation(version)
    if base is None:return None
    baseline = next((v for v in packet['return_versions'] if v['version']==version),None)
    if baseline is None:return None
    checks = run_reconciliations(version)['checks']
    findings = []
    by_issue = {}
    by_id = {}
    line_index = {l['key']:l for l in baseline['lines']}
    def decorate(item,issue,area=None):
        refs = item.get('refs',[])
        jurisdictions = {line_index[r]['jurisdiction'] for r in refs if r in line_index}
        item.update(issue_key=issue, aliases=[], origins=[item['origin']],
                    tax_year=packet['household']['tax_year'],
                    jurisdiction=next(iter(jurisdictions)) if len(jurisdictions)==1 else 'both',
                    area=area or next((area_for(r) for r in refs if area_for(r)!='other'),'other'),
                    reconciliations=[],supporting_evidence=list(refs))
        findings.append(item);by_issue[issue]=item;by_id[item['id']]=item
        return item
    for original in base['findings']:
        item = deepcopy(original)
        issue = 'variance.'+item['refs'][0] if item['code']=='PRIOR_YEAR_VARIANCE' else 'legacy:'+item['id']
        decorate(item,issue)
    for index,diagnostic in enumerate(baseline.get('diagnostics',[])):
        identifier = f"engine:{version}:{diagnostic['code']}:{index}"  # preserved Phase 2 destination identity
        issue = ENGINE_ISSUES.get(diagnostic['code'],'engine:'+diagnostic['code'])
        item = {'id':identifier,'code':diagnostic['code'],'severity':'medium' if diagnostic['severity']=='warning' else 'info',
                'title':diagnostic['code'].replace('_',' ').title(),'description':diagnostic['message'],
                'refs':list(diagnostic['refs']),'status':'open','origin':'engine_diagnostic'}
        decorate(item,issue)
    for check in checks:
        issue = CHECK_ISSUES.get(check['id'],check['id'])
        item = by_issue.get(issue)
        if not item and check['conclusion'] not in ISSUE_CONCLUSIONS:continue
        identifier = 'recon:'+check['id']
        if not item:
            item = decorate({'id':'recon:'+issue,'code':'RECONCILIATION','severity':'high' if check['conclusion'] in {'exact_mismatch','material_discrepancy'} else 'medium',
                             'title':check['title'],'description':check['reason'],'refs':list(check['refs']),
                             'status':'open','origin':'independent_reconciliation'},issue,check['area'])
            item['jurisdiction']=check['jurisdiction']
        else:
            if identifier != item['id']:item['aliases'].append(identifier)
            item['refs']=list(dict.fromkeys(item['refs']+check['refs']))
            item['supporting_evidence']=list(item['refs'])
            item['origins']=list(dict.fromkeys(item['origins']+['independent_reconciliation']))
            item['area']=check['area']
            item['jurisdiction']=check['jurisdiction']
        if identifier != item['id'] and identifier not in item['aliases']:item['aliases'].append(identifier)
        item['reconciliations'].append(check['id'])
        by_id[identifier]=item
    for item in findings:
        if item['issue_key']=='investment.stock_comp_basis':item['title']='Stock-compensation supplemental basis (N1, N3, N4)'
        if item['issue_key']=='business.books_bridge':item['title']='Books-to-tax bridge and unresolved assumptions'
    return {'version':version,'findings':findings,'checks':checks,'total':len(findings)}
