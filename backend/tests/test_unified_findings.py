from app.services.finding_service import build_catalog
from app.services.validation_service import run_validation


def test_legacy_identities_and_metadata_are_preserved():
    for version in ('v1','v2','v3'):
        unified=build_catalog(version)
        index={f['id']:f for f in unified['findings']}
        for legacy in run_validation(version)['findings']:
            assert legacy['id'] in index
            for key in ('id','origin','severity','status','title'):
                assert index[legacy['id']][key]==legacy[key]
        assert all(f['tax_year']==2025 and f['jurisdiction'] and f['area'] and f['supporting_evidence'] for f in unified['findings'])
        assert len(index)==unified['total']


def test_underlying_issues_are_deduplicated_without_losing_check_details():
    result=build_catalog()
    def issue(key):return next(f for f in result['findings'] if f['issue_key']==key)
    mileage=issue('vehicle.miles')
    assert set(mileage['reconciliations'])=={'vehicle.miles','vehicle.deduction'}
    crypto=issue('investment.crypto_basis')
    assert crypto['origin']=='engine_diagnostic'
    assert set(crypto['origins'])=={'engine_diagnostic','independent_reconciliation'}
    meridian=issue('investment.meridian_summary')
    assert set(meridian['reconciliations'])=={'investment.meridian_summary','investment.lot.D31.M18'}
    stock=issue('investment.stock_comp_basis')
    assert len(stock['reconciliations'])==3
    assert len({f['issue_key'] for f in result['findings']})==len(result['findings'])


def test_prior_variances_reuse_original_ids_where_they_exist():
    result=build_catalog()
    for legacy in run_validation()['findings']:
        if legacy['code']=='PRIOR_YEAR_VARIANCE':
            item=next(f for f in result['findings'] if f['id']==legacy['id'])
            assert item['reconciliations']==['variance.'+legacy['refs'][0]]


def test_identity_is_deterministic_and_unknown_version_is_explicit():
    assert build_catalog()==build_catalog()
    assert build_catalog('v99') is None


def test_california_amt_issue_is_classified_by_affected_jurisdiction_not_federal_iso_reference():
    item=next(f for f in build_catalog()['findings'] if f['issue_key']=='california.amt')
    assert item['jurisdiction']=='california'
    assert 'F6251.2i' in item['refs'] and 'F540NR.61' in item['refs']
