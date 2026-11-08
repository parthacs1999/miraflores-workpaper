import hashlib
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.migrate import migrate
from app.services import adjustment_service as service
from app.services.packet_service import DATA_PATH, load_packet

client = TestClient(app)


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    path = tmp_path / 'adjustments.db'
    monkeypatch.setenv('REVIEW_DB_PATH', str(path))
    return path


def draft(**overrides):
    return {'actor_id': 'st-01', **service.metadata('v3')['demo'], **overrides}


def create(version='v3', **overrides):
    response = client.post('/api/adjustments', params={'version': version}, json=draft(**overrides))
    assert response.status_code == 201, response.text
    return response.json()


def act(item, action, actor='st-01', expected=200):
    response = client.post(f'/api/adjustments/{item["id"]}/actions', json={
        'action': action, 'actor_id': actor, 'expected_sequence': item['sequence'], 'note': f'{action} substantiated'})
    assert response.status_code == expected, response.text
    return response.json()


def totals(version='v3'):
    response = client.get('/api/workpaper-summary', params={'version': version})
    assert response.status_code == 200
    return response.json()


def test_additive_migration_preserves_legacy_schema_and_data(isolated_database):
    with sqlite3.connect(isolated_database) as db:
        db.executescript('CREATE TABLE reviews (version TEXT, finding_id TEXT, note TEXT);'
                         "INSERT INTO reviews VALUES ('v3','existing','keep me');"
                         'CREATE TABLE review_events (id INTEGER, note TEXT);'
                         "INSERT INTO review_events VALUES (1,'original history');")
        before = list(db.execute("SELECT name,sql FROM sqlite_master WHERE name IN ('reviews','review_events')"))
        migrate(db)
        migrate(db)
        assert before == list(db.execute("SELECT name,sql FROM sqlite_master WHERE name IN ('reviews','review_events')"))
        assert db.execute('SELECT note FROM reviews').fetchone()[0] == 'keep me'
        assert db.execute('SELECT note FROM review_events').fetchone()[0] == 'original history'
        assert db.execute('SELECT count(*) FROM adjustment_schema_migrations').fetchone()[0] == 1
        assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'


def test_business_receipts_approval_reversal_and_immutable_engine():
    fingerprint = hashlib.sha256(DATA_PATH.read_bytes()).hexdigest()
    packet_before = deepcopy(load_packet())
    lines_before = client.get('/api/return-lines').json()
    item = create()
    effect = item['payload']['effect']
    assert item['state'] == 'draft'
    assert item['payload']['engine_value'] == '163700.00'
    assert item['payload']['delta'] == '-12400.00'
    assert effect['federal_tax'] == '-4402.00'
    assert effect['california_tax'] == '-384.40'
    assert effect['requires_partner'] is True
    assert totals()['approved_adjustment_ids'] == []
    item = act(item, 'submit')
    assert totals()['approved_adjustment_ids'] == []
    act(item, 'approve', 'st-01', 403)
    act(item, 'approve', 'st-02', 403)
    item = act(item, 'approve', 'st-03')
    summary = totals()
    assert summary['approved_adjustment_ids'] == [item['id']]
    assert summary['jurisdictions']['federal']['estimated_total_tax'] == '77560.00'
    assert summary['jurisdictions']['federal']['estimated_balance_due'] == '-182.00'
    assert summary['jurisdictions']['california']['estimated_total_tax'] == '18489.60'
    assert summary['jurisdictions']['california']['estimated_balance_due'] == '-8640.40'
    act(item, 'reverse', 'st-02', 403)
    item = act(item, 'reverse', 'st-03')
    assert item['state'] == 'reversed'
    assert totals()['approved_adjustment_ids'] == []
    assert totals()['jurisdictions']['federal']['tax_effect'] == '0.00'
    assert client.get('/api/return-lines').json() == lines_before
    assert load_packet() == packet_before
    assert hashlib.sha256(DATA_PATH.read_bytes()).hexdigest() == fingerprint
    events = client.get(f'/api/adjustments/{item["id"]}/history').json()['events']
    assert [e['action'] for e in events] == ['created', 'submit', 'approve', 'reverse']
    assert [e['sequence'] for e in events] == [1, 2, 3, 4]
    assert events[2]['actor_id'] == 'st-03'
    assert events[0]['snapshot']['state'] == 'draft'
    assert events[2]['snapshot']['payload']['proposed_value'] == '151300.00'


def test_small_effect_independent_reviewer_can_approve():
    item = act(create(proposed_value='163600'), 'submit')
    item = act(item, 'approve', 'st-02')
    assert item['state'] == 'approved'
    assert totals()['jurisdictions']['federal']['tax_effect'] == '-35.50'


def test_stable_identity_cannot_approve_own_work_even_partner():
    item = act(create(actor_id='st-03'), 'submit', 'st-03')
    act(item, 'approve', 'st-03', 403)
    assert totals()['approved_adjustment_ids'] == []


def test_rejection_revision_preserves_old_content_and_all_authors():
    item = act(create(proposed_value='163600'), 'submit')
    item = act(item, 'reject', 'st-02')
    assert item['state'] == 'rejected'
    assert totals()['approved_adjustment_ids'] == []
    response = client.post(f'/api/adjustments/{item["id"]}/revisions', json={
        **draft(actor_id='st-02', proposed_value='163500', rationale='Reconciled revision'), 'expected_sequence': item['sequence']})
    assert response.status_code == 200
    item = response.json()
    assert item['state'] == 'draft' and item['revision'] == 2
    assert item['prepared_by'] == ['st-01', 'st-02']
    item = act(item, 'submit')
    act(item, 'approve', 'st-02', 403)
    item = act(item, 'approve', 'st-03')
    events = client.get(f'/api/adjustments/{item["id"]}/history').json()['events']
    assert [e['action'] for e in events] == ['created', 'submit', 'reject', 'revised', 'submit', 'approve']
    assert events[0]['snapshot']['payload']['proposed_value'] == '163600.00'
    assert events[3]['snapshot']['payload']['proposed_value'] == '163500.00'


def test_supersede_removes_old_effect_and_requires_fresh_approval():
    item = act(act(create(), 'submit'), 'approve', 'st-03')
    response = act(item, 'supersede', 'st-03')
    assert response['state'] == 'superseded'
    assert totals()['approved_adjustment_ids'] == []
    replacement = client.get('/api/adjustments/' + response['replacement_id']).json()
    assert replacement['state'] == 'draft' and replacement['supersedes_id'] == item['id']
    replacement = act(replacement, 'submit')
    replacement = act(replacement, 'approve', 'st-03')
    assert totals()['approved_adjustment_ids'] == [replacement['id']]
    assert totals()['jurisdictions']['federal']['tax_effect'] == '-4402.00'
    act(response, 'reverse', 'st-03', 409)


@pytest.mark.parametrize('target,value', [('SchC.1', '151200'), ('SchC.31', '69454'), ('F1040.24', '80000')])
def test_overlapping_targets_cannot_be_submitted(target, value):
    first = act(create(), 'submit')
    second = create(target=target, proposed_value=value, refs=['doc:D14#page1'])
    assert first['id'] in second['conflicts']
    act(second, 'submit', expected=409)
    assert totals()['approved_adjustment_ids'] == []


def test_shared_economic_evidence_blocks_different_targets():
    first = act(create(), 'submit')
    second = create(target='F1040.2b', proposed_value='1000')
    assert first['id'] in second['conflicts']
    act(second, 'submit', expected=409)


def test_approved_conflict_can_be_cleared_by_reversal():
    first = act(act(create(), 'submit'), 'approve', 'st-03')
    second = create()
    act(second, 'submit', expected=409)
    act(first, 'reverse', 'st-03')
    act(second, 'submit')


def test_disjoint_adjustments_sum_without_double_counting():
    first = act(act(create(), 'submit'), 'approve', 'st-03')
    second = act(create(target='F1040.26', proposed_value='14000', refs=['doc:D67#page1']), 'submit')
    second = act(second, 'approve', 'st-02')
    summary = totals()
    assert set(summary['approved_adjustment_ids']) == {first['id'], second['id']}
    assert summary['jurisdictions']['federal']['tax_effect'] == '-4402.00'
    assert summary['jurisdictions']['federal']['payment_effect'] == '1000.00'
    assert summary['jurisdictions']['federal']['estimated_balance_due'] == '-1182.00'


def test_version_specific_rates_and_isolation():
    first = create(version='v1')
    assert first['payload']['effect']['federal_tax'] == '-3794.40'
    act(act(first, 'submit'), 'approve', 'st-03')
    assert totals()['approved_adjustment_ids'] == []
    assert totals('v1')['approved_adjustment_ids'] == [first['id']]


def test_stale_packet_excluded_and_actions_blocked(monkeypatch):
    item = act(act(create(), 'submit'), 'approve', 'st-03')
    monkeypatch.setattr(service, 'packet_hash', lambda: 'changed')
    assert totals()['approved_adjustment_ids'] == []
    assert totals()['excluded_stale_ids'] == [item['id']]
    act(item, 'reverse', 'st-03', 409)


def test_unknown_method_requires_manual_review_and_blocks_approval():
    item = create(target='F8606.18', proposed_value='1000')
    assert item['payload']['effect']['manual_review']
    assert item['payload']['effect']['federal_tax'] is None
    item = act(item, 'submit')
    act(item, 'approve', 'st-03', 409)
    assert totals()['approved_adjustment_ids'] == []


@pytest.mark.parametrize('fed,ca,expected', [('0.1','0',False), ('0.100001','0',True), ('0','-0.100001',True), ('-0.1','0',False)])
def test_partner_threshold_uses_absolute_unrounded_effect(fed, ca, expected):
    version = {'tax_effect_rates': {'schc_profit': {'federal_per_dollar': float(fed), 'california_per_dollar': float(ca)}}}
    assert service.calculate(version, 'SchC.1', Decimal('10000'))['requires_partner'] is expected


def test_california_only_effect_requires_partner():
    item = create(target='SchCA540NR.1.E', proposed_value='198400', refs=['doc:D73#page1'])
    assert item['payload']['effect']['federal_tax'] == '0.00'
    assert item['payload']['effect']['california_tax'] == '-1280.00'
    item = act(item, 'submit')
    act(item, 'approve', 'st-02', 403)
    act(item, 'approve', 'st-03')


def test_expense_sign_and_rounding():
    version = service.version_data('v3')
    effect = service.calculate(version, 'SchC.25', Decimal('-0.50'))
    assert effect['federal_tax'] == '0.18'
    assert effect['california_tax'] == '0.02'
    assert service.calculate(version, 'F1040.19', Decimal('-100'))['federal_tax'] == '100.00'
    assert service.calculate({}, 'SchC.1', Decimal('-100'))['manual_review']


@pytest.mark.parametrize('overrides,status', [
    ({'actor_id': 'bogus'}, 403), ({'actor_id': 'st-05'}, 403), ({'actor_id': 'st-06'}, 403),
    ({'rationale': ' '}, 400), ({'authority': ' '}, 400), ({'refs': []}, 422),
    ({'refs': ['ev-999999']}, 400), ({'refs': ['doc:D15#page999']}, 400),
    ({'target': 'BOGUS'}, 404), ({'proposed_value': 'NaN'}, 422),
    ({'proposed_value': 'Infinity'}, 422), ({'proposed_value': '0.001'}, 422),
    ({'proposed_value': '163700'}, 400), ({'actor_role': 'partner'}, 422),
])
def test_invalid_creation_is_rejected_without_audit_side_effects(overrides, status):
    response = client.post('/api/adjustments', json=draft(**overrides))
    assert response.status_code == status, response.text
    assert client.get('/api/adjustments').json()['adjustments'] == []


def test_not_found_and_unknown_version():
    for path in ['/api/adjustments/nope', '/api/adjustments/nope/history', '/api/adjustments?version=nope',
                 '/api/workpaper-summary?version=nope', '/api/adjustment-metadata?version=nope']:
        assert client.get(path).status_code == 404


def test_invalid_state_and_stale_sequence_leave_no_events():
    item = create()
    act(item, 'approve', 'st-03', 409)
    submitted = act(item, 'submit')
    act(item, 'submit', expected=409)
    response = client.post(f'/api/adjustments/{item["id"]}/revisions', json={**draft(), 'expected_sequence': submitted['sequence']})
    assert response.status_code == 409
    assert len(client.get(f'/api/adjustments/{item["id"]}/history').json()['events']) == 2


def test_append_only_revisions_and_events(isolated_database):
    item = create()
    with sqlite3.connect(isolated_database) as db:
        for table in ('adjustment_events', 'adjustment_revisions'):
            for sql in (f'DELETE FROM {table}', f'UPDATE {table} SET adjustment_id=adjustment_id'):
                with pytest.raises(sqlite3.IntegrityError, match='append-only'):
                    db.execute(sql)
        original = db.execute('SELECT payload_json FROM adjustment_revisions WHERE adjustment_id=?', (item['id'],)).fetchone()[0]
        assert json.loads(original)['engine_value'] == '163700.00'


def test_concurrent_approvals_produce_one_effect_and_one_approval_event():
    item = act(create(), 'submit')
    data = {'actor_id': 'st-03', 'action': 'approve', 'expected_sequence': item['sequence'], 'note': 'Independent partner review'}
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: client.post(f'/api/adjustments/{item["id"]}/actions', json=data), range(2)))
    assert sorted(r.status_code for r in responses) == [200, 409]
    assert totals()['jurisdictions']['federal']['tax_effect'] == '-4402.00'
    events = client.get(f'/api/adjustments/{item["id"]}/history').json()['events']
    assert sum(e['action'] == 'approve' for e in events) == 1


def test_depreciation_and_business_adjustments_do_not_use_generic_rates():
    version = service.version_data('v3')
    for target in ('SchC.13', 'Sch1.16', 'Sch1.17'):
        effect = service.calculate(version, target, Decimal('1000'))
        assert effect['manual_review'] is True
        assert effect['federal_tax'] is None


def test_concurrent_overlapping_submissions_allow_only_one():
    items = [create(), create()]
    def submit(item):
        return client.post(f'/api/adjustments/{item["id"]}/actions', json={
            'action': 'submit', 'actor_id': 'st-01', 'expected_sequence': 1, 'note': 'Reconciliation ready'})
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(submit, items))
    assert sorted(r.status_code for r in responses) == [200, 409]
    assert sum(a['state'] == 'submitted' for a in client.get('/api/adjustments').json()['adjustments']) == 1
    assert totals()['approved_adjustment_ids'] == []
