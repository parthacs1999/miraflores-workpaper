import hashlib
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.migrate import migrate
from app.services import verification_service as service
from app.services.packet_service import DATA_PATH, load_packet
from app.services.source_verification_service import get_source_verification

client = TestClient(app)


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    path = tmp_path/'evidence.db'
    monkeypatch.setenv('REVIEW_DB_PATH', str(path))
    return path


def payload(**overrides):
    automatic = get_source_verification('ev-0016')
    match = automatic['match']
    return {'verifier_id': 'st-02', 'method': 'agreed_to_source_document', 'source_ref': 'doc:D08#page1',
            'status': 'confirmed', 'notes': 'Compared Box 1 to the printed source and confirmed the correct field.',
            'expected_sequence': 0, 'quote': {'start': match['start'], 'end': match['end'], 'text': match['matched_text']}, **overrides}


def save(**overrides):
    return client.post('/api/field-verifications/ev-0016', json=payload(**overrides))


def test_persistence_credential_and_automatic_human_separation():
    packet = deepcopy(load_packet())
    fingerprint = hashlib.sha256(DATA_PATH.read_bytes()).hexdigest()
    auto_before = get_source_verification('ev-0016')
    assert client.get('/api/field-verifications/ev-0016').json()['latest'] is None
    response = save()
    assert response.status_code == 201, response.text
    result = response.json()
    assert result['verifier_id'] == 'st-02' and result['credential'] == 'CPA'
    assert result['assurance'] == 'cpa_attestation' and result['currently_confirmed']
    assert result['created_at'] and result['source_ref'] == 'doc:D08#page1'
    assert result['snapshot']['evidence']['value']['field'] == 'box1'
    audit = client.get('/api/field-verifications/ev-0016').json()
    assert audit['latest']['id'] == result['id'] and audit['sequence'] == 1
    assert get_source_verification('ev-0016') == auto_before
    assert load_packet() == packet and hashlib.sha256(DATA_PATH.read_bytes()).hexdigest() == fingerprint
    assert client.get('/api/field-verifications/ev-0016?version=v2').json()['latest'] is None


def test_staff_attestation_is_not_labelled_cpa():
    result = save(verifier_id='st-01').json()
    assert result['assurance'] == 'staff_attestation' and result['credential'] is None


def test_amendment_and_revocation_preserve_every_prior_event():
    assert save().status_code == 201
    assert save(expected_sequence=1, status='needs_review', notes='Reopened for source review.').status_code == 201
    assert save(expected_sequence=2, status='revoked', notes='Revoked prior attestation pending additional support.').status_code == 201
    result = client.get('/api/field-verifications/ev-0016').json()
    assert [e['status'] for e in result['events']] == ['confirmed', 'needs_review', 'revoked']
    assert [e['sequence'] for e in result['events']] == [1,2,3]
    assert not any(e['currently_confirmed'] for e in result['events'])
    assert result['events'][1]['snapshot']['previous_event_id'] == result['events'][0]['id']
    assert save(expected_sequence=3, status='revoked').status_code == 409


@pytest.mark.parametrize('overrides,code', [({'verifier_id':'unknown'},403), ({'verifier_id':'st-05'},403),
    ({'verifier_id':'st-06'},403), ({'notes':' '},400), ({'source_ref':'doc:D08#page99'},400),
    ({'source_ref':'unknown'},400), ({'quote':None},400),
    ({'quote':{'start':0,'end':1,'text':'wrong'}},400),
    ({'quote':{'start':1,'end':999999,'text':'wrong'}},400),
    ({'method':'confirmed_with_client'},400), ({'credential':'CPA'},422),
    ({'expected_sequence':1},409), ({'status':'revoked'},409)])
def test_invalid_attestations_leave_no_history(overrides, code):
    response = save(**overrides)
    assert response.status_code == code, response.text
    assert client.get('/api/field-verifications/ev-0016').json()['events'] == []


def test_non_document_methods_resolve_structured_sources():
    response = save(method='confirmed_with_client', source_ref='call-01', quote=None, notes='Documented client confirmation; verifier assessed relevance.')
    assert response.status_code == 201
    assert response.json()['snapshot']['source']['type'] == 'call_note'
    response = save(expected_sequence=1, method='agreed_to_prior_year', source_ref='py:/return_2024/lines/F1040.1a', quote=None)
    assert response.status_code == 201
    response = save(expected_sequence=2, method='agreed_to_third_party_record', source_ref='agency:/irs_account_transcript_2025/0', quote=None)
    assert response.status_code == 201


def test_missing_field_and_version_and_invalid_quote_type():
    assert client.get('/api/field-verifications/ev-9999').status_code == 404
    assert client.post('/api/field-verifications/ev-9999', json=payload()).status_code == 404
    assert client.get('/api/field-verifications/ev-0016?version=v99').status_code == 404
    assert save(method='confirmed_with_client', source_ref='call-01').status_code == 400


def test_stale_fingerprint_is_not_current_confirmation(monkeypatch):
    assert save().status_code == 201
    monkeypatch.setattr(service, 'packet_hash', lambda: 'changed')
    result = client.get('/api/field-verifications/ev-0016').json()
    assert result['latest']['stale'] and not result['latest']['currently_confirmed']


def test_concurrent_saves_are_serialized():
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: save(), range(2)))
    assert sorted(r.status_code for r in responses) == [201,409]
    assert len(client.get('/api/field-verifications/ev-0016').json()['events']) == 1


def test_additive_migration_preserves_phase1_and_history_is_append_only(isolated_db):
    assert save().status_code == 201
    with sqlite3.connect(isolated_db) as db:
        original = list(db.execute("SELECT name,sql FROM sqlite_master WHERE name LIKE 'adjustment%' ORDER BY name"))
        migrate(db)
        assert original == list(db.execute("SELECT name,sql FROM sqlite_master WHERE name LIKE 'adjustment%' ORDER BY name"))
        assert db.execute('SELECT count(*) FROM evidence_schema_migrations').fetchone()[0] == 1
        for sql in ['DELETE FROM field_verification_events', 'UPDATE field_verification_events SET notes=notes']:
            with pytest.raises(sqlite3.IntegrityError, match='append-only'):
                db.execute(sql)
        assert db.execute('SELECT count(*) FROM field_verification_events').fetchone()[0] == 1
        assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'


def test_migration2_preserves_populated_phase1_ledger(isolated_db):
    from pathlib import Path
    from app import migrate as migration_module
    script = Path(migration_module.__file__).with_name('migrations')/'001_adjustments.sql'
    with sqlite3.connect(isolated_db) as db:
        db.executescript(script.read_text())
        db.execute("INSERT INTO adjustments VALUES ('preserved','v3','hash','approved',1,1,'[\"st-01\"]',NULL,'2026-01-01')")
        db.execute("INSERT INTO adjustment_revisions VALUES ('preserved',1,'{}','st-01','2026-01-01')")
        db.execute("INSERT INTO adjustment_events (adjustment_id,revision,sequence,action,actor_id,actor_role,previous_state,new_state,note,snapshot_json,created_at) VALUES ('preserved',1,1,'approve','st-03','partner','submitted','approved','Keep this approval','{}','2026-01-01')")
        db.commit()
        tables = ['adjustments', 'adjustment_revisions', 'adjustment_events']
        before = {t: list(db.execute('SELECT * FROM '+t)) for t in tables}
        migrate(db)
        assert before == {t: list(db.execute('SELECT * FROM '+t)) for t in tables}
        assert db.execute('SELECT version FROM evidence_schema_migrations').fetchone()[0] == 2
