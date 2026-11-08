"""Field-level human attestations, isolated from automatic text-matching status."""
import json
from datetime import datetime, timezone

from app.services.adjustment_service import database, packet_hash, staff_member, version_data, fail
from app.services.evidence_service import resolve_reference
from app.services.packet_service import load_packet
from app.services.source_verification_service import get_source_verification

METHODS = {
    'agreed_to_source_document': {'document_page'},
    'recalculated': {'document_page', 'return_line', 'engine_parameter', 'fx_rate', 'asset', 'prior_year', 'agency'},
    'confirmed_with_client': {'questionnaire', 'message', 'call_note'},
    'agreed_to_prior_year': {'prior_year'},
    'agreed_to_third_party_record': {'document_page', 'agency'},
}


def metadata():
    return {'methods': list(METHODS), 'statuses': ['confirmed', 'needs_review', 'revoked'],
            'staff': [{k: s.get(k) for k in ('id', 'name', 'role', 'credential', 'active_from')}
                      for s in load_packet()['firm']['staff']]}


def decode(row):
    item = dict(row)
    item['snapshot'] = json.loads(item.pop('snapshot_json'))
    item['stale'] = item['packet_hash'] != packet_hash()
    item['currently_confirmed'] = item['status'] == 'confirmed' and not item['stale']
    return item


def history(evidence_id, version='v3'):
    version_data(version)
    evidence = resolve_reference(evidence_id, version)
    if evidence.type != 'extracted_value' or evidence.status != 'resolved':
        fail('Extracted evidence not found', 404)
    with database() as db:
        events = [decode(row) for row in db.execute('SELECT * FROM field_verification_events WHERE version=? AND evidence_id=? ORDER BY sequence', (version, evidence_id))]
    for index, event in enumerate(events):
        event['currently_confirmed'] = index == len(events)-1 and event['currently_confirmed']
    return {'version': version, 'evidence_id': evidence_id, 'sequence': events[-1]['sequence'] if events else 0,
            'latest': events[-1] if events else None, 'events': events}


def save(evidence_id, version, data):
    version_data(version)
    actor = staff_member(data['verifier_id'])
    from app.services.firm_policy import current
    policy=current()
    if policy and data['method'] not in policy['verification_methods']:fail('Verification method is disabled by current firm policy',403)
    evidence = resolve_reference(evidence_id, version)
    if evidence.type != 'extracted_value' or evidence.status != 'resolved':
        fail('Extracted evidence not found', 404)
    source = resolve_reference(data['source_ref'], version)
    if source.status != 'resolved':
        fail('Unresolved verification source: ' + source.reason)
    if data['method'] not in METHODS or source.type not in METHODS[data['method']]:
        fail('Verification source type is incompatible with the selected method')
    if not data['notes'].strip():
        fail('Verification notes are required')
    quote = data.get('quote')
    if source.type == 'document_page':
        text = source.value['printed_content']
        if (not quote or quote['start'] < 0 or quote['end'] <= quote['start'] or quote['end'] > len(text)
                or text[quote['start']:quote['end']] != quote['text'] or not quote['text'].strip()):
            fail('A valid, exact source-page text location is required')
    elif quote is not None:
        fail('Text locations apply only to document-page sources')
    with database(write=True) as db:
        previous = db.execute('SELECT * FROM field_verification_events WHERE version=? AND evidence_id=? ORDER BY sequence DESC LIMIT 1', (version, evidence_id)).fetchone()
        sequence = previous['sequence'] if previous else 0
        if data['expected_sequence'] != sequence:
            fail('Verification changed; reload before saving', 409)
        if data['status'] == 'revoked' and (previous is None or previous['status'] == 'revoked'):
            fail('Only an existing non-revoked attestation can be revoked', 409)
        snapshot = {'evidence': evidence.model_dump(), 'source': source.model_dump(), 'quote': quote,
                    'automatic_assessment': get_source_verification(evidence_id),
                    'previous_event_id': previous['id'] if previous else None}
        assurance = 'cpa_attestation' if actor.get('credential') == 'CPA' else 'staff_attestation'
        from app.security_context import request_principal
        principal=request_principal.get()
        if principal:
            snapshot['session_assurance']=principal['assurance']
            snapshot['legal_signature']=False
        cursor = db.execute('''INSERT INTO field_verification_events
            (version,evidence_id,sequence,verifier_id,verifier_name,verifier_role,credential,assurance,
             method,source_ref,status,notes,created_at,packet_hash,snapshot_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (version,evidence_id,sequence+1,actor['id'],actor['name'],actor['role'],actor.get('credential'),assurance,
             data['method'],data['source_ref'],data['status'],data['notes'].strip(),datetime.now(timezone.utc).isoformat(),
             packet_hash(),json.dumps(snapshot,sort_keys=True)))
        return decode(db.execute('SELECT * FROM field_verification_events WHERE id=?', (cursor.lastrowid,)).fetchone())
