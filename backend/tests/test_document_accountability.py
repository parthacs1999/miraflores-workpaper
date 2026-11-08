from fastapi.testclient import TestClient
from app.main import app
from app.services.document_accountability_service import accountability, document_destinations
from app.services.packet_service import load_packet

client = TestClient(app)


def test_accountability_covers_every_document_with_nonexclusive_reasons():
    data = client.get('/api/document-accountability').json()
    assert data['total'] == 74
    assert {d['id'] for d in data['documents']} == {d['id'] for d in load_packet()['documents']}
    for document in data['documents']:
        assert document['dispositions'] and document['reasons']
        assert {r['disposition'] for r in document['reasons']} == set(document['dispositions'])
        assert all(r['reason'] and r['refs'] for r in document['reasons'])
    for state, count in data['counts'].items():
        assert count == sum(state in d['dispositions'] for d in data['documents'])


def test_dispositions_preserve_supersession_extraction_and_usage():
    docs = {d['id']: d for d in accountability()['documents']}
    assert 'used' in docs['D09']['dispositions']
    assert 'duplicate' in docs['D10']['dispositions']
    assert docs['D10']['duplicate_of']['document_id'] == 'D09'
    assert {'superseded', 'unextracted', 'requires_review'} <= set(docs['D30']['dispositions'])
    assert 'used' not in docs['D30']['dispositions']
    assert {'used', 'unextracted', 'requires_review'} <= set(docs['D31']['dispositions'])
    assert 32 in docs['D31']['pages_without_extracted_values']
    assert {'unextracted', 'unused', 'requires_review'} <= set(docs['D72']['dispositions'])
    assert {'used', 'unextracted'} <= set(docs['D07']['dispositions'])


def test_duplicate_page_is_not_whole_document_duplicate():
    doc = next(d for d in accountability()['documents'] if d['id'] == 'D23')
    assert 'used' in doc['dispositions'] and 'requires_review' in doc['dispositions']
    assert 'duplicate' not in doc['dispositions']
    assert doc['duplicate_pages'][0]['page'] == 3
    assert doc['duplicate_pages'][0]['duplicate_of_page'] == 2


def test_dispositions_change_with_engine_version():
    first = next(d for d in accountability('v1')['documents'] if d['id'] == 'D30')
    current = next(d for d in accountability('v3')['documents'] if d['id'] == 'D30')
    assert 'used' in first['dispositions'] and 'superseded' not in first['dispositions']
    assert 'superseded' in current['dispositions']


def test_reverse_tracing_includes_direct_indirect_and_findings():
    response = client.get('/api/documents/D09/destinations')
    assert response.status_code == 200
    trace = response.json()
    assert 'F1040.1a' in {l['key'] for l in trace['direct_lines']}
    assert 'F1040.24' in {l['key'] for l in trace['downstream_lines']}
    assert trace['associated_findings']
    assert any('F1040.11' in f['refs'] for f in trace['associated_findings'])
    assert not {l['key'] for l in trace['direct_lines']}.intersection(l['key'] for l in trace['downstream_lines'])


def test_unextracted_prior_workpaper_is_traceable_through_asset_provenance():
    trace = document_destinations('D07')
    assert trace['direct_lines'] and trace['downstream_lines']
    assert any('F4562' in line['key'] or 'FTB3885A' in line['key'] for line in trace['direct_lines'])
    assert trace['associated_findings']


def test_every_reverse_link_is_supported_by_calculation_inputs():
    baseline = load_packet()['return_versions'][-1]
    for identifier in ('D08', 'D07', 'D31', 'D74'):
        trace = document_destinations(identifier)
        direct = {l['key'] for l in trace['direct_lines']}
        reached = set(direct)
        while True:
            more = reached | {l['key'] for l in baseline['lines'] if reached.intersection(l['inputs'])}
            if more == reached:
                break
            reached = more
        assert {l['key'] for l in trace['downstream_lines']} == reached-direct


def test_documents_with_no_links_are_explicit_and_evidence_inventory_complete():
    trace = document_destinations('D72')
    assert trace['direct_lines'] == [] and trace['downstream_lines'] == []
    assert trace['associated_findings'] == []
    inventory = client.get('/api/documents/D08/evidence').json()
    assert inventory['count'] == len(inventory['values'])
    assert all(v['document_id'] == 'D08' for v in inventory['values'])
    assert 'ev-0016' in {v['id'] for v in inventory['values']}
    assert client.get('/api/documents/D99/evidence').status_code == 404
    assert client.get('/api/document-accountability?version=v99').status_code == 404


def test_unresolved_provenance_is_exposed_without_split_character_refs():
    refs = [r['ref'] for r in accountability()['unresolved_provenance']]
    assert 'prior_preparer_depreciation_schedule' in refs
    assert not any(len(ref) == 1 for ref in refs)
