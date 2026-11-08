from copy import deepcopy
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.evidence_service import resolve_reference, json_pointer, evidence_graph
from app.services.packet_service import load_packet

client = TestClient(app)


@pytest.mark.parametrize('ref,kind', [
    ('ev-0016', 'extracted_value'), ('D07', 'document'), ('doc:D31#page32', 'document_page'),
    ('py:/carryovers_into_2025/capital_loss_short', 'prior_year'),
    ('agency:/irs_account_transcript_2025/0', 'agency'), ('qa-14', 'questionnaire'),
    ('msg-07', 'message'), ('call-01', 'call_note'), ('asset:SAC-BLDG', 'asset'),
    ('asset:STU-LAPTOP', 'asset'), ('household:theo', 'household_member'),
    ('ref:param.std_deduction_mfj', 'engine_parameter'), ('ref:param.fx.SEK.2025_average', 'engine_parameter'),
    ('ref:fx.SEK.2025_year_end', 'fx_rate'), ('timeline:extension-2026-04-14', 'timeline_event'),
    ('timeline:tl-01', 'timeline_event'), ('F1040.11', 'return_line'),
])
def test_every_reference_format(ref, kind):
    response = client.get('/api/evidence-resolution', params={'ref': ref, 'version': 'v3'})
    assert response.status_code == 200
    result = response.json()
    assert result['type'] == kind and result['status'] == 'resolved'
    assert result['location'] and result['reason_code'] is None
    assert 'value' in result and 'related_refs' in result


@pytest.mark.parametrize('ref', ['ev-9999', 'D99', 'doc:D08#page99', 'py:/nope', 'agency:/nope',
                                'qa-99', 'msg-99', 'call-99', 'asset:missing', 'household:missing',
                                'ref:param.missing', 'ref:fx.SEK.missing', 'timeline:missing', 'F1040.nope'])
def test_missing_references_are_explicit_typed_results(ref):
    result = client.get('/api/evidence-resolution', params={'ref': ref}).json()
    assert result['status'] == 'unresolved'
    assert result['reason_code'] == 'missing_reference'
    assert result['reason'] and result['ref'] == ref and result['type'] != 'unknown'


@pytest.mark.parametrize('ref', ['doc:D08#page0', 'doc:D08', 'py:not-a-pointer', 'py:/bad~escape',
                                'agency:/irs_account_transcript_2025/00', 'ref:param..rate'])
def test_invalid_references_are_not_silently_coerced(ref):
    result = resolve_reference(ref)
    assert result.status == 'unresolved' and result.reason_code == 'invalid_reference'


def test_unknown_format_and_version():
    assert resolve_reference('not-a-reference').reason_code == 'unknown_format'
    assert resolve_reference('F1040.11', 'v99').reason_code == 'unknown_version'
    assert client.get('/api/evidence-graph', params={'ref': 'unknown'}).json()['unresolved'][0]['ref'] == 'unknown'


def test_rfc6901_arrays_escapes_empty_keys_and_null():
    root = {'a/b': {'m~n': [None, {'': False}]}, '': 0}
    assert json_pointer(root, '') == root
    assert json_pointer(root, '/a~1b/m~0n/0') is None
    assert json_pointer(root, '/a~1b/m~0n/1/') is False
    assert json_pointer(root, '/') == 0
    for pointer in ['/a~2b', '/a~1b/m~0n/-', '/a~1b/m~0n/01']:
        with pytest.raises(ValueError):
            json_pointer(root, pointer)
    with pytest.raises(IndexError):
        json_pointer(root, '/a~1b/m~0n/9')


def test_pointer_to_null_is_resolved_not_missing():
    result = resolve_reference('py:/basis_records/scorp_lindqvist_family_woodworks/1/ending_stock_basis')
    assert result.status == 'resolved' and result.value is None


def test_all_engine_source_refs_resolve_in_their_own_versions():
    for version in load_packet()['return_versions']:
        for ref in {r for line in version['lines'] for r in line['sources']}:
            result = resolve_reference(ref, version['version'])
            assert result.status == 'resolved', (version['version'], ref, result.reason)


def test_version_specific_asset_and_line_values():
    for version in ('v1', 'v2', 'v3'):
        baseline = next(v for v in load_packet()['return_versions'] if v['version'] == version)
        result = resolve_reference('asset:STU-PRINTER', version)
        assert result.value == next(a for a in baseline['assets'] if a['asset_id'] == 'STU-PRINTER')
        result = resolve_reference('F1040.11', version)
        assert result.value['value'] == baseline['summary']['federal']['agi']


def test_transitive_provenance_and_no_character_splitting():
    graph = evidence_graph('py:/return_2024/lines/F1040.24')
    assert graph['document_ids'] == ['D06']
    assert 'ev-0011' in {n['ref'] for n in graph['nodes']}
    assert not graph['unresolved']
    assert 'D07' in evidence_graph('asset:SAC-BLDG')['document_ids']
    assert 'D69' in evidence_graph('agency:/irs_account_transcript_2025/0')['document_ids']


def test_graph_preserves_unknown_provenance_and_handles_cycles():
    packet = deepcopy(load_packet())
    asset = packet['return_versions'][-1]['assets'][0]
    asset['sources'] = ['asset:SAC-BLDG', 'unknown-source']
    graph = evidence_graph('asset:SAC-BLDG', packet=packet)
    assert graph['cycles'] == [{'from': 'asset:SAC-BLDG', 'to': 'asset:SAC-BLDG'}]
    assert graph['unresolved'][0]['ref'] == 'unknown-source'


def test_legacy_lineage_contract_is_extended_without_removing_fields():
    result = client.get('/api/lineage/F1040.1a').json()['lineage']
    source = result['sources'][0]
    assert source['type'] == 'extracted_value' and source['evidence']['id'] == 'ev-0016'
    assert source['document']['pages'] and source['resolution']['status'] == 'resolved'
    result = client.get('/api/lineage/F1040.12').json()['lineage']
    def walk(node):
        yield from node.get('sources', [])
        for child in node.get('inputs', []):
            yield from walk(child)
    assert all(s['resolution']['status'] == 'resolved' for s in walk(result))


def test_resolver_applies_pointer_escapes_and_arrays_to_packet_data():
    packet = deepcopy(load_packet())
    packet['prior_years']['a/b'] = {'m~n': [0, None, {'': 'evidence'}]}
    result = resolve_reference('py:/a~1b/m~0n/2/', packet=packet)
    assert result.status == 'resolved' and result.value == 'evidence'
    assert resolve_reference('py:/a~1b/m~0n/1', packet=packet).value is None


def test_phase1_adjustments_accept_new_resolvable_source_types(tmp_path, monkeypatch):
    monkeypatch.setenv('REVIEW_DB_PATH', str(tmp_path/'ledger.db'))
    from app.services.adjustment_service import metadata
    response = client.post('/api/adjustments', json={'actor_id': 'st-01', **metadata('v3')['demo'],
        'refs': ['py:/carryovers_into_2025/capital_loss_short', 'agency:/irs_account_transcript_2025/0', 'ref:param.mileage_rate']})
    assert response.status_code == 201
    assert response.json()['state'] == 'draft'


def test_nested_notice_fields_inherit_only_their_own_document():
    graph = evidence_graph('agency:/notices/0/summary')
    assert graph['document_ids'] == ['D70']
    graph = evidence_graph('agency:/notices/1/items_under_examination/0')
    assert graph['document_ids'] == ['D72']
