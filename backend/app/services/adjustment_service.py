"""Audited overlays: never mutate packet data or pretend to rerun the engine."""
import hashlib
import json
import re
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4

from app.migrate import migrate
from app.services.packet_service import DATA_PATH, load_packet
from app.services.review_service import connect

STATES = ('draft', 'submitted', 'approved', 'rejected', 'reversed', 'superseded')
EDIT_ROLES = {'preparer', 'reviewer', 'partner'}
CENT = Decimal('0.01')


class AdjustmentError(Exception):
    def __init__(self, message, status_code=400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def fail(message, code=400):
    raise AdjustmentError(message, code)


def packet_hash():
    return hashlib.sha256(DATA_PATH.read_bytes()).hexdigest()


def version_data(version):
    result = next((v for v in load_packet()['return_versions'] if v['version'] == version), None)
    if result is None:
        fail('Return version not found', 404)
    return result


def staff_member(actor_id):
    staff = next((s for s in load_packet()['firm']['staff'] if s['id'] == actor_id), None)
    if staff is None or staff['active_from'] > datetime.now(timezone.utc).date().isoformat():
        fail('Unknown or inactive staff ID', 403)
    if staff['role'] not in EDIT_ROLES:
        fail('Staff role cannot prepare or approve adjustments', 403)
    return staff


@contextmanager
def database(write=False):
    db = connect()
    db.execute('PRAGMA foreign_keys = ON')
    try:
        migrate(db)
        db.execute('BEGIN IMMEDIATE' if write else 'BEGIN')
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def money(value):
    rounded = Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)
    return format(rounded if rounded else Decimal('0.00'), '.2f')


def validate_refs(refs, version):
    from app.services.evidence_service import resolve_reference
    if not refs or any(resolve_reference(ref, version['version']).status != 'resolved' for ref in refs):
        fail('Evidence must reference an existing packet record, document page, or return line')


# Conservative allowlist: each maps the line delta to the rate's economic quantity.
# Aggregate tax/AGI, SEP/SEHI, dispositions, basis and other unsupported lines are manual.
RATE_TARGETS = {
    'F1040.1a': ('wages', 1),
    'F1040.2b': ('interest', 1),
    'F1040.3b': ('interest', 1),
    'SchC.1': ('schc_profit', 1),
    'SchC.31': ('schc_profit', 1),
    'SchA.11': ('itemized', 1),
    'SchA.12': ('itemized', 1),
    'SchA.5a': ('salt', 1),
    'SchA.5b': ('salt', 1),
    'SchCA540NR.1.E': ('ca_source_income', 1),
}
for key in ('8', '9', '11', '15', '17', '18', '22', '24a', '24b', '25', '27a.1', '27a.2', '30'):
    RATE_TARGETS['SchC.' + key] = ('schc_profit', -1)

# These are leaf payments/credits only, not their aggregate totals.
DIRECT_TARGETS = {
    'F540NR.72': ('california', 'payment'),
    'F540NR.71': ('california', 'payment'),
    'F1040.26': ('federal', 'payment'),
    'F1040.25a': ('federal', 'payment'),
    'F1040.19': ('federal', 'credit'),
    'F1040.20': ('federal', 'credit'),
}


def calculate(version, target, delta, threshold=Decimal("1000")):
    result = {'method': 'manual_review', 'category': None, 'federal_tax': None,
              'california_tax': None, 'federal_payment': '0.00', 'california_payment': '0.00',
              'requires_partner': None, 'manual_review': True,
              'warning': 'No validated packet computation method for this target. Approval is blocked.'}
    if target in RATE_TARGETS:
        category, sign = RATE_TARGETS[target]
        rates = version.get('tax_effect_rates', {}).get(category)
        if not rates or any(not isinstance(rates.get(k), (int, float)) for k in ('federal_per_dollar', 'california_per_dollar')):
            return result
        fed = delta * sign * Decimal(str(rates['federal_per_dollar']))
        ca = delta * sign * Decimal(str(rates['california_per_dollar']))
        if not fed.is_finite() or not ca.is_finite():
            return result
        result.update(method='packet_rate_estimate', category=category, rates=rates)
    elif target in DIRECT_TARGETS:
        jurisdiction, kind = DIRECT_TARGETS[target]
        fed = -delta if jurisdiction == 'federal' and kind == 'credit' else Decimal(0)
        ca = -delta if jurisdiction == 'california' and kind == 'credit' else Decimal(0)
        if kind == 'payment':
            result[jurisdiction + '_payment'] = money(delta)
        result.update(method='packet_one_to_one', category=kind)
    else:
        return result
    # Compare unrounded values, so 1000.004 cannot evade the policy boundary.
    result.update(federal_tax=money(fed), california_tax=money(ca),
                  requires_partner=abs(fed) > threshold or abs(ca) > threshold,
                  manual_review=False,
                  warning='Estimate using baseline packet rates; no engine recomputation. Large changes, caps, QBI and interacting adjustments require review.')
    return result


def build_payload(version, data):
    line = next((l for l in version['lines'] if l['key'] == data['target']), None)
    if line is None:
        fail('Return line not found', 404)
    if isinstance(line['value'], bool) or not isinstance(line['value'], (int, float)):
        fail('Only numeric engine lines may be adjusted')
    proposed = Decimal(str(data['proposed_value']))
    if not proposed.is_finite() or abs(proposed) > Decimal('999999999999.99'):
        fail('Proposed value must be a finite amount within the supported range')
    if proposed != proposed.quantize(CENT):
        fail('Proposed value supports at most two decimal places')
    rationale = data['rationale'].strip()
    authority = data['authority'].strip()
    if not rationale or not authority:
        fail('Rationale and authority are required')
    refs = sorted(set(data['refs']))
    validate_refs(refs, version)
    delta = proposed - Decimal(str(line['value']))
    if not delta:
        fail('Adjustment must change the engine value')
    return {'target': line['key'], 'label': line['label'], 'engine_value': money(line['value']),
            'proposed_value': money(proposed), 'delta': money(delta), 'rationale': rationale,
            'authority': authority, 'refs': refs, 'effect': calculate(version, line['key'], delta)}


def read_one(db, adjustment_id):
    row = db.execute('SELECT * FROM adjustments WHERE id = ?', (adjustment_id,)).fetchone()
    if row is None:
        fail('Adjustment not found', 404)
    result = dict(row)
    revision = db.execute('SELECT payload_json FROM adjustment_revisions WHERE adjustment_id = ? AND revision = ?',
                          (adjustment_id, result['revision'])).fetchone()
    result['payload'] = json.loads(revision['payload_json'])
    result['prepared_by'] = json.loads(result['prepared_by'])
    result['stale'] = result['packet_hash'] != packet_hash()
    return result


def ancestor_keys(version, key):
    lines = {l['key']: l for l in version['lines']}
    visited = set()
    def visit(k):
        if k in visited:
            return
        visited.add(k)
        for parent in lines.get(k, {}).get('inputs', []):
            visit(parent)
    visit(key)
    return visited


def conflict_ids(db, item):
    version = version_data(item['version'])
    target = item['payload']['target']
    ancestors = ancestor_keys(version, target)
    evidence = {r for r in item['payload']['refs'] if re.fullmatch(r'ev-\d+', r)}
    found = []
    rows = db.execute("SELECT id FROM adjustments WHERE version = ? AND state IN ('submitted','approved') AND id != ?",
                      (item['version'], item['id'])).fetchall()
    for row in rows:
        other = read_one(db, row['id'])
        other_target = other['payload']['target']
        if (other_target in ancestors or target in ancestor_keys(version, other_target)
                or evidence.intersection(other['payload']['refs'])):
            found.append(other['id'])
    return found


def append_event(db, item, action, actor, previous, note):
    timestamp = datetime.now(timezone.utc).isoformat()
    db.execute('''INSERT INTO adjustment_events
        (adjustment_id, revision, sequence, action, actor_id, actor_role, previous_state,
         new_state, note, snapshot_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        (item['id'], item['revision'], item['sequence'], action, actor['id'], actor['role'],
         previous, item['state'], note, json.dumps(item, sort_keys=True), timestamp))


def insert_draft(db, version, payload, actor, prepared_by=None, supersedes_id=None):
    identifier = str(uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()
    # Superseding copies existing prepared content; recording the control action
    # does not make the approving partner an author of that unchanged content.
    authors = sorted(set(prepared_by if prepared_by is not None else [actor['id']]))
    db.execute('INSERT INTO adjustments VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
               (identifier, version, packet_hash(), 'draft', 1, 1, json.dumps(authors), supersedes_id, timestamp))
    db.execute('INSERT INTO adjustment_revisions VALUES (?, ?, ?, ?, ?)',
               (identifier, 1, json.dumps(payload, sort_keys=True), actor['id'], timestamp))
    item = read_one(db, identifier)
    append_event(db, item, 'created', actor, None, payload['rationale'])
    return item


def create_adjustment(version, data):
    actor = staff_member(data['actor_id'])
    payload = build_payload(version_data(version), data)
    with database(write=True) as db:
        item = insert_draft(db, version, payload, actor)
        item['conflicts'] = conflict_ids(db, item)
        return item


def get_adjustment(identifier):
    with database() as db:
        item = read_one(db, identifier)
        item['conflicts'] = conflict_ids(db, item)
        return item


def list_adjustments(version):
    version_data(version)
    with database() as db:
        items = [read_one(db, r['id']) for r in db.execute(
            'SELECT id FROM adjustments WHERE version = ? ORDER BY created_at, id', (version,)).fetchall()]
        for item in items:
            item['conflicts'] = conflict_ids(db, item)
        return {'version': version, 'adjustments': items}


def check_sequence(item, expected_sequence):
    if item['sequence'] != expected_sequence:
        fail('Adjustment changed; reload before acting', 409)
    if item['stale']:
        fail('Packet fingerprint changed; create a new adjustment against the current packet', 409)


def revise_adjustment(identifier, data):
    actor = staff_member(data['actor_id'])
    with database(write=True) as db:
        item = read_one(db, identifier)
        check_sequence(item, data['expected_sequence'])
        if item['state'] not in ('draft', 'rejected'):
            fail('Only draft or rejected adjustments can be revised; supersede an approved adjustment', 409)
        payload = build_payload(version_data(item['version']), data)
        previous = item['state']
        authors = sorted(set(item['prepared_by'] + [actor['id']]))
        db.execute("UPDATE adjustments SET state='draft', revision=revision+1, sequence=sequence+1, prepared_by=? WHERE id=?",
                   (json.dumps(authors), identifier))
        db.execute('INSERT INTO adjustment_revisions VALUES (?, ?, ?, ?, ?)',
                   (identifier, item['revision'] + 1, json.dumps(payload, sort_keys=True), actor['id'], datetime.now(timezone.utc).isoformat()))
        updated = read_one(db, identifier)
        append_event(db, updated, 'revised', actor, previous, payload['rationale'])
        updated['conflicts'] = conflict_ids(db, updated)
        return updated


def act_on_adjustment(identifier, data):
    actor = staff_member(data['actor_id'])
    action = data['action']
    note = data['note'].strip()
    if not note:
        fail('An action note is required')
    transitions = {'submit': ('draft', 'submitted'), 'approve': ('submitted', 'approved'),
                   'reject': ('submitted', 'rejected'), 'reverse': ('approved', 'reversed'),
                   'supersede': ('approved', 'superseded')}
    if action not in transitions:
        fail('Unknown adjustment action')
    with database(write=True) as db:
        item = read_one(db, identifier)
        check_sequence(item, data['expected_sequence'])
        previous, new_state = transitions[action]
        if item['state'] != previous:
            fail(f'Cannot {action} an adjustment in state {item["state"]}', 409)
        if action in ('approve', 'reject', 'reverse', 'supersede'):
            if actor['role'] not in {'reviewer', 'partner'} or actor['id'] in item['prepared_by']:
                fail('An independent reviewer or partner is required', 403)
        if action in ('approve', 'reverse', 'supersede'):
            effect = item['payload']['effect']
            if action == 'approve' and effect['manual_review']:
                fail('Manual review required: no validated tax-effect method; approval is blocked', 409)
            from app.security_context import request_principal
            principal = request_principal.get()
            requires_partner = effect['requires_partner']
            if principal and principal.get('profile') != 'legacy_test':
                from app.services.workflow_service import active_policy
                threshold = Decimal(str(active_policy(db)['policy']['partner_threshold']))
                requires_partner = requires_partner or calculate(version_data(item['version']),item['payload']['target'],Decimal(item['payload']['delta']),threshold)['requires_partner']
            if requires_partner and actor['role'] != 'partner':
                fail('Partner approval required: absolute federal or California tax effect exceeds $1,000', 403)
        if action in ('submit', 'approve'):
            conflicts = conflict_ids(db, item)
            if conflicts:
                fail('Conflicting or overlapping adjustment: ' + ', '.join(conflicts), 409)
        db.execute('UPDATE adjustments SET state=?, sequence=sequence+1 WHERE id=?', (new_state, identifier))
        updated = read_one(db, identifier)
        append_event(db, updated, action, actor, previous, note)
        if action == 'supersede':
            replacement = insert_draft(db, item['version'], item['payload'], actor,
                                       prepared_by=item['prepared_by'], supersedes_id=identifier)
            updated['replacement_id'] = replacement['id']
        return updated


def history(identifier):
    with database() as db:
        read_one(db, identifier)
        events = []
        for row in db.execute('SELECT * FROM adjustment_events WHERE adjustment_id=? ORDER BY sequence', (identifier,)):
            event = dict(row)
            event['snapshot'] = json.loads(event.pop('snapshot_json'))
            events.append(event)
        return {'adjustment_id': identifier, 'events': events}


def summary(version):
    baseline = version_data(version)
    items = list_adjustments(version)['adjustments']
    return summary_from_items(version,items)


def summary_from_items(version, items):
    baseline = version_data(version)
    approved = [a for a in items if a['state'] == 'approved' and not a['stale']]
    result = {'version': version, 'packet_hash': packet_hash(), 'estimate_only': True,
              'engine_summary': baseline['summary'], 'approved_adjustment_ids': [a['id'] for a in approved],
              'excluded_stale_ids': [a['id'] for a in items if a['stale']], 'jurisdictions': {},
              'warning': 'Estimated overlay only. Engine lines, AGI, taxable income and penalties are not recomputed. Interactions and large changes require review.'}
    for jurisdiction in ('federal', 'california'):
        tax = sum((Decimal(a['payload']['effect'][jurisdiction + '_tax']) for a in approved), Decimal(0))
        payment = sum((Decimal(a['payload']['effect'][jurisdiction + '_payment']) for a in approved), Decimal(0))
        base = baseline['summary'][jurisdiction]
        result['jurisdictions'][jurisdiction] = {
            'tax_effect': money(tax), 'payment_effect': money(payment),
            'estimated_total_tax': money(Decimal(str(base['total_tax'])) + tax),
            'estimated_payments': money(Decimal(str(base['payments'])) + payment),
            'estimated_balance_due': money(Decimal(str(base['balance_due'])) + tax - payment)}
    return result


def metadata(version):
    baseline = version_data(version)
    return {'staff': [{k: s[k] for k in ('id', 'name', 'role', 'active_from')} for s in load_packet()['firm']['staff']],
            'states': STATES,
            'targets': [{'key': l['key'], 'label': l['label'], 'engine_value': money(l['value']),
                         'method_available': l['key'] in RATE_TARGETS or l['key'] in DIRECT_TARGETS}
                        for l in baseline['lines'] if isinstance(l['value'], (int, float)) and not isinstance(l['value'], bool)],
            'demo': {'target': 'SchC.1', 'proposed_value': '151300.00',
                     'rationale': 'Remove $12,400 Paywell receipts already included in books revenue; D15 reconciles Atlas card and ACH deposits.',
                     'authority': 'Packet D14/D15/D21 receipt reconciliation; engine R-SCHC-GROSS and supplied schc_profit rates.',
                     'refs': ['doc:D14#page1', 'doc:D15#page1', 'doc:D21#page1', 'ev-0109']}}
