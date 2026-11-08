from copy import deepcopy
from decimal import Decimal
import pytest
from app.services.packet_service import load_packet
from app.services.reconciliation_core import compare, decimal, Rule, Context, execute, Unsupported
from app.services.reconciliation_service import run_reconciliations, rules_for, printed_lots


def checks(packet=None,version='v3'):
    return {c['id']:c for c in run_reconciliations(version,packet)['checks']}


@pytest.mark.parametrize('id,expected,reported,conclusion',[
 ('business.receipts','151300','163700','exact_mismatch'),
 ('business.software','6634','6850','judgment_required'),
 ('business.utilities','2172','3480','judgment_required'),
 ('business.meals','1980','1980','exact_match'),
 ('vehicle.miles','8100','11800','exact_mismatch'),
 ('vehicle.deduction','5670','8260','exact_mismatch'),
 ('investment.bank_sweep','1840','3680','exact_mismatch'),
 ('investment.meridian_summary','71965','71715','exact_mismatch'),
 ('investment.lot.D28.N1','140','19240','exact_mismatch'),
 ('investment.lot.D28.N2','2100','2100','exact_match'),
 ('investment.lot.D28.N3','-620','18480','exact_mismatch'),
 ('investment.lot.D28.N4','5880','15300','exact_mismatch'),
 ('california.wages','129569','218400','judgment_required'),
 ('california.depreciation','30400','30400','exact_match'),
 ('deductions.mortgage','19697','21847','exact_mismatch'),
 ('deductions.property_tax','6508','13420','judgment_required'),
 ('deductions.salt_limit','40000','40000','exact_match'),
 ('deductions.vehicle_gift','2900','6000','judgment_required'),
 ('payments.federal_estimates','12000','13000','exact_mismatch'),
 ('payments.ca_estimates','10500','14000','exact_mismatch'),
 ('payments.federal_withholding','25400','25400','exact_match'),
 ('payments.ca_withholding','13130','13130','exact_match'),
 ('carryover.capital_loss_short','-3200','-3200','exact_match'),
 ('carryover.capital_loss_long','-11000','-11000','exact_match'),
 ('k1.scorp_income','18400','18400','exact_match'),
 ('k1.partnership_income','8400','8400','exact_match'),
 ('k1.stock_basis','2300','2300','judgment_required'),
 ('rental.rent_a','37200','37200','exact_match'),
 ('rental.rent_b','20250','20250','exact_match'),
 ('rental.passive_loss','-38630','-38630','exact_match'),
 ('disposition.gain','105040','105040','rounding_difference'),
 ('disposition.unrecaptured','50340','50340','rounding_difference'),
])
def test_rule_known_source_results(id,expected,reported,conclusion):
    result=checks()[id]
    assert Decimal(result['expected_value'])==Decimal(expected)
    assert Decimal(result['reported_value'])==Decimal(reported)
    assert result['conclusion']==conclusion
    assert result['method'] and result['refs'] and result['inputs'] and result['steps']


@pytest.mark.parametrize('id',['business.books_bridge','investment.crypto_basis','depreciation.rates',
 'disposition.recapture','rental.hvac','california.amt','california.capital_sourcing',
 'deductions.cash_gift','carryover.outgoing','k1.outside_basis'])
def test_unsupported_checks_are_not_fabricated_results(id):
    result=checks()[id]
    assert result['conclusion']=='unsupported'
    assert result['expected_value'] is None and result['difference'] is None
    assert result['reason'] and result['refs']


def test_unextracted_missing_return_lot_is_not_zeroed():
    result=checks()['investment.lot.D31.M18']
    assert result['expected_value']=='-60.00' and result['reported_value'] is None
    assert result['conclusion']=='unsupported' and 'missing' in result['reason']
    assert 'doc:D31#page32' in result['refs']


def test_every_implemented_rule_has_reproducible_disposition_and_traceability():
    packet=load_packet();baseline=packet['return_versions'][-1]
    results=checks()
    for rule in rules_for(packet,baseline):
        first=execute(rule,packet,baseline);second=execute(rule,packet,baseline)
        assert first==second
        assert rule.id in results and first['method'] and first['refs']
        assert first['conclusion'] in {'exact_match','rounding_difference','exact_mismatch','judgment_required','unsupported','conflicting_sources'}
        if first['expected_value'] is not None:
            assert first['inputs'] and first['steps'] or rule.id.startswith('depreciation.opening.')
    assert len({c['id'] for c in results.values()})==len(results)


def test_all_260_brightpath_lots_use_their_own_printed_proceeds_basis_and_wash():
    p=load_packet();c=Context(p,p['return_versions'][-1]);lots=printed_lots(c,'D74')
    assert len(lots)==260
    results=checks()
    for key,lot in lots.items():
        result=results['investment.lot.D74.'+key]
        assert Decimal(result['expected_value'])==lot['proceeds']-lot['basis']+lot['wash']
        assert result['conclusion']=='exact_match'
        assert result['inputs'][-1]['raw']==lot['raw']


@pytest.mark.parametrize('asset', ['SAC-BLDG','SAC-APPL','SAC-ROOF','AUS-BLDG','AUS-FLOOR','STU-LAPTOP'])
@pytest.mark.parametrize('jurisdiction',['federal','california'])
def test_each_asset_opening_balance_is_rolled_from_prior_history(asset,jurisdiction):
    prior=next(a for a in load_packet()['prior_years']['asset_records'] if a['asset_id']==asset)
    expected=sum(Decimal(str(x)) for x in prior[jurisdiction].values())
    result=checks()['depreciation.opening.'+asset+'.'+jurisdiction]
    assert Decimal(result['expected_value'])==expected
    assert result['conclusion']=='exact_match'


@pytest.mark.parametrize('expected,reported,conclusion', [('10.49','10','rounding_difference'),('10.50','11','rounding_difference'),('-10.50','-11','rounding_difference'),('10','10','exact_match'),('10.51','10','exact_mismatch')])
def test_rounding_uses_packet_display_precision_and_sign(expected,reported,conclusion):
    assert compare(expected,reported)['conclusion']==conclusion
    assert compare(expected,reported)['tolerance']=='0'


def test_cent_precision_and_unknowns_are_not_rounded_away_or_zeroed():
    assert compare('100.01','100.00',Decimal('.01'))['conclusion']=='exact_mismatch'
    for value in [None,True,'NaN','infinity','not given']:
        with pytest.raises(Unsupported):decimal(value)


def test_missing_document_and_conflicting_printed_fields_are_explicit():
    p=deepcopy(load_packet());p['documents']=[d for d in p['documents'] if d['id']!='D14']
    assert checks(p)['business.receipts']['conclusion']=='unsupported'
    p=deepcopy(load_packet());d=next(d for d in p['documents'] if d['id']=='D14');d['pages'][0]['printed_content']+=' Total income 999,999.00.'
    assert checks(p)['business.receipts']['conclusion']=='conflicting_sources'
    p=deepcopy(load_packet());d=next(d for d in p['documents'] if d['id']=='D21');d['pages'][0]['printed_content']=d['pages'][0]['printed_content'].replace('12,400.00','12,000.00')
    assert checks(p)['business.receipts']['conclusion']=='conflicting_sources'


def test_engine_mutation_does_not_change_source_expected_value():
    p=deepcopy(load_packet());line=next(l for l in p['return_versions'][-1]['lines'] if l['key']=='SchC.1');line['value']=1
    result=checks(p)['business.receipts']
    assert result['expected_value']=='151300' and result['reported_value']=='1'
    assert Decimal(result['difference'])==-151299


def test_missing_rate_is_not_invented_and_client_estimate_remains_conditional():
    p=deepcopy(load_packet());del p['engine_reference']['parameters']['mileage_rate']
    assert checks(p)['vehicle.deduction']['conclusion']=='unsupported'
    p=deepcopy(load_packet());p['client']['call_notes'][0]['notes']=[n for n in p['client']['call_notes'][0]['notes'] if '70%' not in n]
    assert checks(p)['business.utilities']['conclusion']=='unsupported'


def test_only_available_irs_snapshot_is_used_and_scripted_payments_excluded():
    assert checks(version='v1')['payments.federal_estimates']['conclusion']=='unsupported'
    p=deepcopy(load_packet());p['tax_agency_records']['irs_account_transcript_2025'][1]['transactions'][0]['amount']=999999
    assert checks(p)['payments.federal_estimates']['expected_value']=='12000'


def test_prior_variance_uses_both_firm_thresholds_strictly_and_zero_is_explicit():
    p=deepcopy(load_packet());p['prior_years']['return_2024']['lines']['F1040.1a']=10000
    line=next(l for l in p['return_versions'][-1]['lines'] if l['key']=='F1040.1a');line['value']=11000
    assert checks(p)['variance.F1040.1a']['conclusion']=='not_flagged_by_firm_variance_standard'
    line['value']=11001
    assert checks(p)['variance.F1040.1a']['conclusion']=='material_discrepancy'
    p['prior_years']['return_2024']['lines']['F1040.1a']=0
    assert checks(p)['variance.F1040.1a']['conclusion']=='judgment_required'


def test_all_variance_check_inputs_trace_back_to_their_own_prior_line():
    for result in checks().values():
        if result['id'].startswith('variance.'):
            assert 'py:/return_2024/lines/'+result['target'] in result['refs']
            assert result['materiality']['flag_if_change_over_percent']==10
            assert result['materiality']['and_over_amount']==1000


def test_reported_broker_aggregate_preserves_each_extracted_component():
    result=checks()['investment.meridian_summary']
    components=[i for i in result['inputs'] if i['kind']=='pipeline_extracted']
    assert len(components)==17 and all(i['ref'].startswith('ev-') for i in components)
    assert sum(Decimal(i['value']) for i in components)==Decimal(result['reported_value'])


def test_later_received_source_is_identified_for_historical_engine_comparison():
    result=checks(version='v1')['k1.stock_basis']
    assert any(i['ref']=='doc:D40#page1' and i['available_after_engine'] for i in result['inputs'])


def test_conditional_books_to_tax_bridge_retains_all_assumptions_and_components():
    result=checks()['business.conditional_bridge']
    assert result['expected_value']=='73568'
    assert result['reported_value']=='81854'
    assert result['difference']=='8286'
    assert result['conclusion']=='judgment_required'
    assert result['check_type']=='professional_judgment'
    assert {'SchC.13','SchC.30','doc:D14#page1','call-01'} <= set(result['refs'])
    assert any(i['ref']=='SchC.13' and i['kind']=='engine_reported' for i in result['inputs'])
    assert checks()['business.books_bridge']['conclusion']=='unsupported'
