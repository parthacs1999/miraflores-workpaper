"""Packet-backed collaboration and firm operations. No agency or identity adapters."""
import base64
import binascii
import hashlib
import json
import re
import struct
import zlib
from collections import Counter
from datetime import date
from decimal import Decimal
from functools import lru_cache
from uuid import uuid4

from app.services import workflow_service as w
from app.services.adjustment_service import fail, read_one
from app.services.packet_service import load_packet

MAX_FILE = 5 * 1024 * 1024
MAX_TOTAL_FILES = 100 * 1024 * 1024
EVIDENCE_KINDS = {'p_attachment', 'p_question', 'p_message'}
BUCKETS = {
    'intake_and_engagement': {'intake'}, 'wages_and_stock_compensation': {'engagement'},
    'investments_and_digital_assets': {'investments'}, 'business': {'business', 'vehicle', 'depreciation'},
    'rentals_and_sale': {'rentals'}, 'pass_throughs_and_basis': {'pass_throughs', 'carryovers'},
    'deductions_and_credits': {'itemized', 'credits'}, 'california': {'california'}, 'partner_review': {'engagement'},
}


def access(db, actor, area=None, operations=False):
    if area is not None and area not in w.AREAS:fail('Unknown workpaper area')
    w.require_access(db, actor, area, manage=operations and actor['role'] == 'firm_administrator')
    if actor['role'] not in w.PRACTICE_ROLES and not (operations and actor['role'] == 'firm_administrator'):
        fail('Assigned tax-practice staff required', 403)


def visible(db, actor, area):
    member = w.membership(db, actor)
    return bool(member and ('*' in member['data']['areas'] or area in member['data']['areas']))


def item(db, actor, identifier, kind=None):
    row = w.entity(db, identifier)
    if not row or row['engagement_id'] != w.ENGAGEMENT or kind and row['kind'] != kind:
        fail('Work item not found', 404)
    if row['kind']=='p_bulk':
        bulk_permissions(db,actor,row)
    else:access(db, actor, row['area'])
    if row['kind'] == 'p_attachment':
        for area in row['data']['areas']:
            access(db, actor, area)
    return row


def revision(row, expected):
    if (row['revision'] if row else 0) != expected:
        fail('Item changed; reload before acting', 409)


def calendar(value):
    try:
        return date.fromisoformat(value).isoformat()
    except (ValueError, TypeError):
        fail('A valid ISO calendar date is required')


def practice_member(db, identifier, area):
    person = w.staff(identifier)
    access(db, person, area)
    return person


def findings(version='v3'):
    from app.services.firm_policy import current
    return policy_findings(version,w.digest(current()))


@lru_cache(maxsize=12)
def policy_findings(version,policy_key):
    from app.services.finding_service import build_catalog
    return {f['id']: f for f in build_catalog(version)['findings']}


def normalized_area(area):
    return area if area in w.AREAS else 'engagement'


def document_areas(identifier):
    from app.services.firm_policy import current
    return policy_document_areas(identifier,w.digest(current()))


@lru_cache(maxsize=296)
def policy_document_areas(identifier,policy_key):
    from app.services.document_accountability_service import document_destinations
    from app.services.finding_service import area_for
    result = document_destinations(identifier)
    if result is None:
        fail('Document not found', 404)
    areas = {normalized_area(f['area']) for f in result['associated_findings']}
    areas.update(area_for(l['key']) for l in result['direct_lines'])
    areas.discard('other')
    return sorted(areas or {'intake'})


def target(db, actor, link):
    kind, identifier = link['kind'], link['id']
    if kind == 'finding':
        f = findings().get(identifier)
        if not f:
            fail('Finding not found', 404)
        areas = [normalized_area(f['area'])]
    elif kind == 'document':
        areas = document_areas(identifier)
    elif kind == 'adjustment':
        from app.services.finding_service import area_for
        areas = [normalized_area(area_for(read_one(db, identifier)['payload']['target']))]
    elif kind in {'note', 'workflow', 'question'}:
        row = item(db, actor, identifier)
        if row['kind'] != {'note': 'note', 'question': 'p_question'}.get(kind, row['kind']):
            fail('Evidence target kind does not match', 409)
        if row['kind'] in {'notification', 'p_bulk', 'p_checkpoint', 'p_time', 'p_budget'}:
            fail('This operational record is not a workpaper evidence target')
        areas = row['data']['areas'] if row['kind'] == 'p_attachment' else [row['area']]
    else:
        fail('Unsupported evidence target')
    for area in areas:
        access(db, actor, area)
    return areas


def validate_refs(db, actor, refs, area):
    from app.services.evidence_service import resolve_reference
    for ref in refs:
        if ref.startswith(('attachment:', 'question:', 'discussion:')):
            row = item(db, actor, ref)
            if row['kind'] not in EVIDENCE_KINDS:
                fail('Unsupported evidence record')
            continue
        result = resolve_reference(ref)
        if result.status != 'resolved':
            fail('Unresolved supporting reference: ' + ref)
        for doc in result.document_ids:
            for linked_area in document_areas(doc):
                access(db, actor, linked_area)
        if result.type == 'return_line':
            from app.services.finding_service import area_for
            access(db, actor, normalized_area(area_for(ref)))


def evidence_dependencies(db, area):
    return [e for e in w.entities(db) if e['kind'] in EVIDENCE_KINDS and
            (area == 'engagement' or e['area']=='engagement' or area in e['data'].get('areas', [e['area']]))]


def snapshot_evidence(db):
    metadata = evidence_dependencies(db, 'engagement')
    originals = [{'attachment_id': r['id'], 'sha256': r['sha256'],
                  'unprocessed_file_content_base64': base64.b64encode(r['content']).decode()}
                 for r in db.execute('SELECT * FROM product_files WHERE engagement_id=? ORDER BY id', (w.ENGAGEMENT,))]
    return {'metadata_and_discussions': metadata, 'originals': originals,
            'warning': 'Uploaded bytes are unextracted. Original bytes require cleared, purpose-audited reveal; masked packages omit them.'}


def file_bytes(filename, media_type, encoded):
    # Nothing is ever written to an uploader-controlled filesystem path.
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9 _.-]{0,119}', filename) or '..' in filename or filename.endswith(('.', ' ')):
        fail('Use a plain safe filename, without paths, dot segments or control characters')
    extension = filename.rsplit('.', 1)[-1].lower()
    expected = {'txt': 'text/plain', 'pdf': 'application/pdf', 'png': 'image/png', 'jpg': 'image/jpeg', 'jpeg': 'image/jpeg'}
    if expected.get(extension) != media_type:
        fail('Allowed evidence types are PDF, PNG, JPEG and UTF-8 plain text with matching extensions')
    if len(encoded) > ((MAX_FILE + 2) // 3) * 4:
        fail('Evidence exceeds the 5 MiB size limit', 413)
    try:
        content = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error):
        fail('Invalid base64 evidence content')
    if not content or len(content) > MAX_FILE:
        fail('Evidence must contain 1 byte to 5 MiB', 413)
    if extension == 'txt':
        try:
            text = content.decode('utf-8')
        except UnicodeDecodeError:
            fail('Plain text must be UTF-8')
        if any(ord(c) < 32 and c not in '\n\r\t' for c in text) or re.search(r'<\s*(?:html|script|iframe|svg|!doctype)', text, re.I):
            fail('Active markup or binary content is not accepted as plain text')
    elif extension == 'pdf':
        if not re.match(rb'%PDF-1\.[0-7]', content) or not content.rstrip().endswith(b'%%EOF'):
            fail('Invalid PDF file signature or trailer')
        if re.search(rb'/(?:JavaScript|JS|Launch|OpenAction|AA|EmbeddedFile|Encrypt|RichMedia)\b|#[0-9a-fA-F]{2}', content):
            fail('Active, embedded, encrypted or escaped-name PDF content requires an external secure intake process')
    elif extension == 'png':
        if not content.startswith(b'\x89PNG\r\n\x1a\n'):
            fail('Invalid PNG signature')
        offset, seen_header, seen_end, seen_data = 8, False, False, False
        while offset + 12 <= len(content):
            length = int.from_bytes(content[offset:offset + 4], 'big'); kind = content[offset + 4:offset + 8]
            if offset + 12 + length > len(content):
                fail('Truncated PNG chunk')
            chunk = content[offset + 8:offset + 8 + length]
            if zlib.crc32(kind + chunk) & 0xffffffff != int.from_bytes(content[offset + 8 + length:offset + 12 + length], 'big'):
                fail('Invalid PNG checksum')
            if not seen_header:
                if kind != b'IHDR' or length != 13:
                    fail('Invalid PNG header')
                width, height = struct.unpack('>II', chunk[:8])
                if not 0 < width <= 20000 or not 0 < height <= 20000 or width * height > 40_000_000:
                    fail('Image dimensions exceed the intake limit')
                seen_header = True
            offset += 12 + length
            if kind == b'IDAT':seen_data=True
            if kind == b'IEND':
                seen_end = length == 0 and offset == len(content)
                break
        if not seen_end or not seen_data:
            fail('Invalid PNG trailer')
    else:
        if not (content.startswith(b'\xff\xd8\xff') and content.endswith(b'\xff\xd9')):
            fail('Invalid JPEG signature or trailer')
        offset=2;dimensions=False;scan=False
        while offset+4<=len(content):
            if content[offset]!=255:fail('Invalid JPEG segment')
            marker=content[offset+1];offset+=2
            if marker==255:offset-=1;continue
            length=int.from_bytes(content[offset:offset+2],'big')
            if length<2 or offset+length>len(content):fail('Truncated JPEG segment')
            if marker in {0xc0,0xc1,0xc2,0xc3}:
                if length<8:fail('Invalid JPEG dimensions')
                height,width=struct.unpack('>HH',content[offset+3:offset+7])
                if not 0<width<=20000 or not 0<height<=20000 or width*height>40_000_000:fail('Image dimensions exceed the intake limit')
                dimensions=True
            if marker==0xda:scan=offset+length<len(content)-2;break
            offset+=length
        if not dimensions or not scan:fail('JPEG needs image dimensions and scan content')
    return content


def upload(actor, data):
    if not data['title'].strip():fail('Evidence title is required')
    content = file_bytes(data['filename'], data['media_type'], data['content_base64'])
    with w.connection() as db:
        access(db, actor, data['area'])
        total=db.execute('SELECT COALESCE(SUM(size),0) FROM product_files WHERE engagement_id=?',(w.ENGAGEMENT,)).fetchone()[0]
        if total+len(content)>MAX_TOTAL_FILES:fail('Engagement attachment storage exceeds the 100 MiB prototype quota',413)
        areas = {data['area']}
        for link in data['links']:
            areas.update(target(db, actor, link))
        identifier = 'attachment:' + uuid4().hex
        sha = hashlib.sha256(content).hexdigest()
        db.execute('INSERT INTO product_files VALUES(?,?,?,?,?,?,?,?)',
                   (identifier, w.ENGAGEMENT, sha, data['media_type'], len(content), content, actor['id'], w.now()))
        metadata = {k: data[k] for k in ('filename', 'media_type', 'title', 'note', 'links')}
        metadata.update(sha256=sha, size=len(content), areas=sorted(areas), processing='not_extracted',
                        verification='unverified', original_immutable=True, refs=[])
        return w.put(db, identifier, 'p_attachment', data['area'], 'unreviewed', metadata, [actor['id']], actor['id'], 'uploaded', 0)


def attachment_action(actor, identifier, data):
    with w.connection() as db:
        row = item(db, actor, identifier, 'p_attachment'); revision(row, data['expected_revision'])
        content = dict(row['data'])
        if data['action'] == 'metadata':
            if not data['title'].strip():fail('Evidence title is required')
            if not data['links']:
                fail('Keep at least one explicit evidence target')
            areas = {row['area']}
            for link in data['links']:
                areas.update(target(db, actor, link))
            content.update(title=data['title'], note=data['note'], links=data['links'], areas=sorted(areas), verification='unverified')
            state, authors = 'unreviewed', sorted(set(row['authors'] + [actor['id']]))
        else:
            if actor['role'] not in {'reviewer', 'partner'} or actor['id'] in row['authors']:
                fail('Independent reviewer required', 403)
            for area in content['areas']:
                w.independent(db, actor, area)
            viewed = any(json.loads(r[0]).get('attachment_id') == identifier for r in db.execute(
                "SELECT resource_json FROM workflow_access_events WHERE staff_id=? AND action='attachment_download' AND outcome='allowed'", (actor['id'],)))
            if not viewed:
                fail('Download and inspect the original with cleared audited access before recording manual support review', 409)
            content.update(verification='manual_support_review_not_extraction', reviewed_by=actor['id'], review_note=data['note'])
            state, authors = 'reviewed', row['authors']
        return w.put(db, identifier, row['kind'], row['area'], state, content, authors, actor['id'], data['action'], row['revision'])


def download(actor, identifier, reveal, purpose):
    with w.connection() as db:
        row = item(db, actor, identifier, 'p_attachment')
        if not reveal or not actor.get('sensitive_data_clearance') or len(purpose.strip()) < 8:
            fail('Unprocessed originals require sensitive clearance and a meaningful audited reveal purpose', 403)
        original = db.execute('SELECT * FROM product_files WHERE id=? AND engagement_id=?', (identifier, w.ENGAGEMENT)).fetchone()
        if not original:
            fail('Original evidence missing', 404)
        # Audit in this transaction. Never print bytes, base64, filenames or purpose in request logs.
        db.execute('INSERT INTO workflow_access_events(staff_id,action,resource_json,purpose,outcome,request_id,created_at) VALUES(?,?,?,?,?,?,?)',
                   (actor['id'], 'attachment_download', json.dumps({'attachment_id': identifier}), purpose, 'allowed', uuid4().hex, w.now()))
        return {'id': identifier, 'filename': row['data']['filename'], 'sha256': original['sha256'],
                'media_type': original['media_type'], 'size': original['size'], 'content_base64': base64.b64encode(original['content']).decode(),
                'processing': 'not_extracted', 'disposition': 'attachment_only_never_inline'}


def question_create(actor, data):
    if not data['title'].strip():fail('Question title is required')
    with w.connection() as db:
        access(db, actor, data['area'])
        practice_member(db, data['owner_id'], data['area'])
        participants = sorted(set(data['participants'] + [actor['id'], data['owner_id']]))
        for p in participants:
            practice_member(db, p, data['area'])
        if data['due_date']:
            calendar(data['due_date'])
        validate_refs(db, actor, data['refs'], data['area'])
        row = w.put(db, 'question:' + uuid4().hex, 'p_question', data['area'], 'open',
                    {**data, 'participants': participants, 'response_assurance': 'staff_or_declared_client_demonstration', 'latest_message_id': None},
                    [actor['id']], actor['id'], 'question_opened', 0)
        for p in participants:
            w.notify(db, p, 'Workpaper question assigned', row['id'], 'question:' + row['id'] + p)
        return row


def question_update(actor,identifier,data):
    if not data['title'].strip():fail('Question title is required')
    with w.connection() as db:
        row=item(db,actor,identifier,'p_question');revision(row,data['expected_revision'])
        if actor['id']!=row['data']['owner_id'] and actor['role']!='partner':fail('Question owner or assigned partner required for metadata changes',403)
        if row['data']['blocking'] and not data['blocking']:fail('A blocking designation cannot be removed; independently resolve the question instead',409)
        practice_member(db,data['owner_id'],row['area'])
        participants=sorted(set(data['participants']+[data['owner_id'],actor['id']]))
        for p in participants:practice_member(db,p,row['area'])
        if data['due_date']:calendar(data['due_date'])
        validate_refs(db,actor,data['refs'],row['area'])
        content={**row['data'],**{k:data[k] for k in ('title','note','owner_id','due_date','blocking','refs')},'participants':participants,
                 'latest_message_id':None,'resolution_valid':False}
        result=w.put(db,row['id'],row['kind'],row['area'],'open',content,sorted(set(row['authors']+[actor['id']])),actor['id'],'question_metadata_revised',row['revision'])
        for p in participants:w.notify(db,p,'Workpaper question assignment or evidence revised',identifier,identifier+str(result['revision'])+p)
        return result


def question_action(actor, identifier, data):
    with w.connection() as db:
        row = item(db, actor, identifier, 'p_question'); revision(row, data['expected_revision'])
        content = dict(row['data']); action = data['action']
        if actor['id'] not in content['participants'] and actor['role'] != 'partner':
            fail('Only a participant or assigned partner may act on the discussion', 403)
        if action == 'request_resolution':
            if row['state'] != 'answered':
                fail('A documented response is required before independent resolution', 409)
            state = 'awaiting_review'
        elif action == 'resolve':
            if row['state'] != 'awaiting_review':
                fail('Discussion is not awaiting independent resolution', 409)
            w.independent(db, actor, row['area'])
            if actor['id'] in row['authors']:
                fail('Question/response authors cannot resolve their own discussion', 403)
            content.update(resolved_by=actor['id'], resolution_note=data['note'],resolution_digest=question_control(db,row),resolution_valid=True); state = 'resolved'
        elif action == 'reopen':
            if row['state'] != 'resolved':
                fail('Only resolved discussions can be reopened', 409)
            state = 'open'
        else:
            fail('Unsupported discussion action')
        content['last_note'] = data['note']
        result = w.put(db, row['id'], row['kind'], row['area'], state, content, row['authors'], actor['id'], action, row['revision'])
        w.notify(db, content['owner_id'], 'Workpaper question status changed', row['id'], row['id'] + str(result['revision']))
        return result


def question_control(db,row):
    from app.services.finding_service import area_for
    adjustments=[]
    for a in db.execute('SELECT id FROM adjustments ORDER BY id'):
        value=read_one(db,a['id'])
        if normalized_area(area_for(value['payload']['target']))==row['area']:adjustments.append(value)
    evidence_docs={e['id']:e['document_id'] for e in load_packet()['extracted_values']}
    return w.digest({'packet':w.entity(db,w.ENGAGEMENT)['data']['packet_hash'],'policy':w.active_policy(db),
        'question_input':{k:row['data'].get(k) for k in ('title','note','refs','blocking','owner_id','participants','due_date','latest_message_id')},
        'messages':[m for m in w.entities(db,'p_message') if m['data']['question_id']==row['id']],
        'attachments':[a for a in w.entities(db,'p_attachment') if row['area'] in a['data']['areas']],
        'adjustments':adjustments,'verification_events':[dict(v) for v in db.execute('SELECT id,evidence_id,sequence,status FROM field_verification_events ORDER BY id') if v['evidence_id'] in evidence_docs and row['area'] in document_areas(evidence_docs[v['evidence_id']])],
        'members':[m for m in w.entities(db,'membership') if '*' in m['data']['areas'] or row['area'] in m['data']['areas']],
        'workpaper_records':[e for e in w.entities(db) if e['kind'] in {'record','note'} and e['area'] in {row['area'],'engagement'}]})


def invalidate_questions(db,actor):
    for row in w.entities(db,'p_question'):
        if row['state']=='resolved' and row['data'].get('resolution_digest')!=question_control(db,row):
            w.put(db,row['id'],row['kind'],row['area'],'awaiting_review',{**row['data'],'resolution_valid':False,'invalidation_reason':'Supporting evidence, workpaper, assignment or policy changed; fresh independent resolution required.'},row['authors'],actor['id'],'resolution_invalidated',row['revision'])
            w.notify(db,row['data']['owner_id'],'Question resolution requires fresh review',row['id'],row['id']+str(row['revision'])+'stale')


def message(actor, identifier, data):
    with w.connection() as db:
        row = item(db, actor, identifier, 'p_question'); revision(row, data['expected_revision'])
        if row['state'] not in {'open', 'answered'}:
            fail('Reopen the discussion before adding a response', 409)
        if actor['id'] not in row['data']['participants'] and actor['role'] != 'partner':
            fail('Discussion participant required', 403)
        if data.get('parent_id'):
            parent = item(db, actor, data['parent_id'], 'p_message')
            if parent['data']['question_id'] != identifier:
                fail('Reply parent belongs to a different discussion', 409)
        validate_refs(db, actor, data['refs'], row['area'])
        client = data.get('declared_client_id')
        if client and client not in {c['id'] for c in load_packet()['firm']['client_users']}:
            fail('Unknown packet client', 403)
        msg = w.put(db, 'discussion:' + uuid4().hex, 'p_message', row['area'], 'recorded',
                    {**data, 'question_id': identifier, 'recorded_by': actor['id'], 'recorded_at': w.now(),
                     'assurance': 'staff_mediated_client_demo_not_authenticated' if client else 'staff_session', 'client_authenticated': False},
                    [actor['id']], actor['id'], 'response_recorded', 0)
        w.put(db, row['id'], row['kind'], row['area'], 'answered', {**row['data'], 'latest_message_id': msg['id']},
              sorted(set(row['authors'] + [actor['id']])), actor['id'], 'answered', row['revision'])
        for p in row['data']['participants']:
            w.notify(db, p, 'New workpaper discussion response', identifier, msg['id'] + p)
        return msg


def overview(actor):
    with w.connection() as db:
        access(db, actor)
        rows = [e for e in w.entities(db) if e['kind'] in EVIDENCE_KINDS | {'p_bulk', 'p_document_ack'} and (visible(db, actor, e['area']) if e['kind']!='p_bulk' else all(visible(db,actor,c.get('area') or (c.get('before') or {}).get('area') or (w.entity(db,c['id']) or {}).get('area','engagement')) for c in e['data']['changes']))
                and (e['kind'] != 'p_attachment' or all(visible(db, actor, a) for a in e['data']['areas']))]
        return {'engagement_id': w.ENGAGEMENT, 'items': rows, 'areas': [a for a in w.AREAS if visible(db, actor, a)],
                'staff': [{k: s[k] for k in ('id', 'name', 'role')} for s in load_packet()['firm']['staff'] if w.membership(db, s)],
                'clients': load_packet()['firm']['client_users'], 'file_limit_bytes': MAX_FILE,
                'allowed_types': ['application/pdf', 'image/png', 'image/jpeg', 'text/plain']}


def history(actor, identifier):
    with w.connection() as db:
        item(db, actor, identifier)
        events=[]
        for r in db.execute('SELECT * FROM workflow_events WHERE entity_id=? ORDER BY id',(identifier,)):
            payload=json.loads(r['payload_json'])
            areas={a for state in ('before','after') if payload.get(state) for a in payload[state]['data'].get('areas',[payload[state]['area']])}
            if all(visible(db,actor,a) for a in areas):events.append({**dict(r),'payload':payload})
        return {'events':events,'append_only':True,'scope':'Only audit snapshots within the current assignment are disclosed.'}


def bulk_history(actor):
    with w.connection() as db:
        access(db,actor,operations=True)
        result=[]
        from app.services.adjustment_service import AdjustmentError
        for row in w.entities(db,'p_bulk'):
            if actor['role']=='firm_administrator' and row['data']['operation']!='assign_tasks':continue
            try:bulk_permissions(db,actor,row)
            except AdjustmentError:continue
            result.append(row)
        return {'items':result}


def review_version(db, identifier):
    last = db.execute('SELECT MAX(id) FROM review_events WHERE version=? AND finding_id=?', ('v3', identifier)).fetchone()[0]
    return last or 0


def set_review(db, actor, identifier, status, note):
    old = db.execute('SELECT * FROM reviews WHERE version=? AND finding_id=?', ('v3', identifier)).fetchone()
    previous = old['status'] if old else 'open'
    db.execute('INSERT INTO reviews VALUES(?,?,?,?,?,?) ON CONFLICT(version,finding_id) DO UPDATE SET status=excluded.status,note=excluded.note,updated_by=excluded.updated_by,updated_at=excluded.updated_at',
               ('v3', identifier, status, note, actor['id'] + ' (' + actor['role'] + ')', w.now()))
    db.execute('INSERT INTO review_events(version,finding_id,previous_status,new_status,note,actor_role,actor_name,created_at) VALUES(?,?,?,?,?,?,?,?)',
               ('v3', identifier, previous, status, note, actor['role'], actor['id'], w.now()))
    return review_version(db, identifier)


def bulk_permissions(db,actor,batch):
    for c in batch['data']['changes']:
        area=c.get('area') or (c.get('before') or {}).get('area') or (w.entity(db,c['id']) or {}).get('area','engagement')
        access(db,actor,area,operations=batch['data']['operation']=='assign_tasks')
        if batch['data']['operation']=='acknowledge_documents':
            row=w.entity(db,c['id'])
            for a in document_areas(row['data']['document_id']):access(db,actor,a)


def bulk_catalog(actor, operation):
    with w.connection() as db:
        access(db, actor, operations=operation == 'assign_tasks')
        if operation == 'acknowledge_findings':
            saved = {r['finding_id']: r['status'] for r in db.execute('SELECT * FROM reviews WHERE version="v3"')}
            return {'items': [{'id': f['id'], 'title': f['title'], 'area': normalized_area(f['area']), 'state': saved.get(f['id'], 'open'),
                              'expected_revision': review_version(db, f['id'])} for f in findings().values() if visible(db, actor, normalized_area(f['area'])) and saved.get(f['id'], 'open') == 'open']}
        if operation == 'acknowledge_documents':
            result = []
            for d in load_packet()['documents']:
                if all(visible(db, actor, a) for a in document_areas(d['id'])):
                    previous = w.entity(db, 'ack:' + actor['id'] + ':' + d['id'])
                    if not previous or previous['state'] == 'unacknowledged':
                        result.append({'id': d['id'], 'title': d['title'], 'area': document_areas(d['id'])[0], 'expected_revision': previous['revision'] if previous else 0})
            return {'items': result}
        kind = 'record' if operation == 'submit_records' else 'task'
        return {'items': [{'id': e['id'], 'title': e['data']['title'], 'area': e['area'], 'state': e['state'], 'expected_revision': e['revision']}
                          for e in w.entities(db, kind) if (actor['role'] == 'firm_administrator' or visible(db, actor, e['area'])) and
                          (e['state'] in {'draft', 'open'} if kind == 'record' else e['state'] == 'open')]}


def bulk(actor, data):
    with w.connection() as db:
        access(db, actor, operations=data['operation'] == 'assign_tasks')
        cached = db.execute('SELECT * FROM product_commands WHERE engagement_id=? AND staff_id=? AND command_key=?', (w.ENGAGEMENT, actor['id'], data['command_key'])).fetchone()
        fingerprint = w.digest(data)
        if cached:
            if cached['request_hash'] != fingerprint:
                fail('Idempotency key was already used for different content', 409)
            result=json.loads(cached['result_json']);bulk_permissions(db,actor,result)
            return result
        ids = [i['id'] for i in data['items']]
        if len(set(ids)) != len(ids):
            fail('Duplicate items in bulk request')
        changes = []
        for selected in data['items']:
            identifier, expected = selected['id'], selected['expected_revision']; operation = data['operation']
            if operation == 'acknowledge_findings':
                f = findings().get(identifier)
                if not f:
                    fail('Finding not found', 404)
                area = normalized_area(f['area']); access(db, actor, area)
                old = db.execute('SELECT * FROM reviews WHERE version="v3" AND finding_id=?', (identifier,)).fetchone()
                if review_version(db, identifier) != expected or old and old['status'] != 'open':
                    fail('Finding changed or is no longer open', 409)
                after = set_review(db, actor, identifier, 'in_review', data['note'])
                changes.append({'kind': 'review', 'id': identifier, 'area': area, 'before_status': 'open', 'before_review':dict(old) if old else None, 'after_revision': after})
            elif operation == 'acknowledge_documents':
                areas = target(db, actor, {'kind': 'document', 'id': identifier}); key = 'ack:' + actor['id'] + ':' + identifier
                old = w.entity(db, key); revision(old, expected)
                if old and old['state'] != 'unacknowledged':
                    fail('Document already acknowledged', 409)
                row = w.put(db, key, 'p_document_ack', areas[0], 'acknowledged', {'document_id': identifier, 'note': data['note'],
                            'meaning': 'Seen only; not verified, used or disposition-approved'}, [], actor['id'], 'acknowledged', expected)
                changes.append({'kind': 'entity', 'id': key, 'before': old, 'after_revision': row['revision']})
            else:
                old = w.entity(db, identifier)
                if not old or old['engagement_id'] != w.ENGAGEMENT:
                    fail('Bulk target not found', 404)
                access(db, actor, old['area'], operations=operation == 'assign_tasks'); revision(old, expected)
                if operation == 'submit_records':
                    if old['kind'] != 'record' or old['state'] not in {'draft', 'open'}:
                        fail('Only draft/open workflow records can be submitted', 409)
                    d = old['data']
                    if not d.get('answer', '').strip() or not d.get('authority', '').strip() or not d.get('refs') or d.get('applicability') == 'unknown':
                        fail('Each record needs an applicability decision, answer, authority and evidence', 409)
                    validate_refs(db, actor, d['refs'], old['area']); state, content = 'submitted', {**d, 'last_action_note': data['note']}
                else:
                    if actor['role'] not in {'partner', 'firm_administrator'}:
                        fail('Task assignment requires partner or administrator', 403)
                    if old['kind'] != 'task' or old['state'] != 'open':
                        fail('Only open task assignments can be changed', 409)
                    practice_member(db, data['assignee'], old['area']); state, content = old['state'], {**old['data'], 'assignee': data['assignee']}
                row = w.put(db, identifier, old['kind'], old['area'], state, content, old['authors'], actor['id'], 'bulk_' + operation, expected)
                if operation == 'assign_tasks':
                    w.notify(db, data['assignee'], 'Task assigned in bulk', identifier, data['command_key'] + identifier)
                changes.append({'kind': 'entity', 'id': identifier, 'before': old, 'after_revision': row['revision']})
        result = w.put(db, 'bulk:' + uuid4().hex, 'p_bulk', 'engagement', 'applied',
                       {'operation': data['operation'], 'changes': changes, 'note': data['note']}, [actor['id']], actor['id'], 'bulk_applied', 0)
        db.execute('INSERT INTO product_commands VALUES(?,?,?,?,?,?)', (w.ENGAGEMENT, actor['id'], data['command_key'], fingerprint, json.dumps(result), w.now()))
        return result


def undo(actor, identifier, data):
    with w.connection() as db:
        access(db, actor, operations=actor['role'] == 'firm_administrator')
        batch = w.entity(db, identifier)
        if not batch or batch['engagement_id'] != w.ENGAGEMENT or batch['kind'] != 'p_bulk':
            fail('Bulk operation not found', 404)
        revision(batch, data['expected_revision'])
        bulk_permissions(db,actor,batch)
        if batch['state'] != 'applied' or actor['id'] != batch['created_by'] and actor['role'] != 'partner':
            fail('Only the original operator or assigned partner may compensate an applied batch', 403)
        # A compensation cannot change a resource already bound into a submitted/accepted payload.
        bound_ids = {c['id'] for c in batch['data']['changes']}
        if batch['data']['operation'] in {'submit_records', 'acknowledge_findings'}:
            for filing in w.entities(db, 'lc_filing'):
                if filing['state'] in {'submitted', 'accepted'}:
                    from app.services.lifecycle_service import snapshot
                    frozen = json.dumps(snapshot(db, filing['data']['snapshot_id'])['dependencies'])
                    if any(json.dumps(key) in frozen for key in bound_ids):
                        fail('Submitted simulated filing binds this work; document a fresh correction instead of undo', 409)
        for change in batch['data']['changes']:
            if change['kind'] == 'review':
                access(db, actor, change['area'])
                if review_version(db, change['id']) != change['after_revision']:
                    fail('A finding changed after this batch; no items were undone', 409)
                set_review(db, actor, change['id'], 'open', 'Compensating undo: ' + data['note'])
            else:
                row = w.entity(db, change['id']); revision(row, change['after_revision'])
                access(db, actor, row['area'], operations=batch['data']['operation'] == 'assign_tasks')
                before = change['before']; state = before['state'] if before else 'unacknowledged'
                if state == 'approved':
                    fail('Undo can never restore an approval', 409)
                if batch['data']['operation']=='assign_tasks' and before and before['data'].get('assignee'):
                    practice_member(db,before['data']['assignee'],row['area'])
                w.put(db, row['id'], row['kind'], row['area'], state, before['data'] if before else row['data'], row['authors'], actor['id'], 'compensating_undo', row['revision'])
        return w.put(db, batch['id'], batch['kind'], batch['area'], 'undone', {**batch['data'], 'undo_note': data['note']}, batch['authors'], actor['id'], 'compensated', batch['revision'])


def time_save(actor, data):
    with w.connection() as db:
        access(db, actor, data['area'])
        if data['bucket'] not in BUCKETS or data['area'] not in BUCKETS[data['bucket']]:
            fail('Time bucket does not match the workpaper area')
        day = calendar(data['work_date'])
        if day > w.now()[:10]:
            fail('Actual time entries cannot be future estimates')
        identifier = data.get('id') or 'time:' + uuid4().hex
        previous = w.entity(db, identifier)
        if data.get('id') and not previous:fail('Existing time entry not found',404)
        if previous and (previous['kind'] != 'p_time' or previous['created_by'] != actor['id'] or previous['area'] != data['area']):
            fail('Only the original staff member can revise time within its original area', 403)
        revision(previous, data['expected_revision'])
        other = sum(e['data']['minutes'] for e in w.entities(db, 'p_time') if e['id'] != identifier and e['state'] == 'recorded' and e['created_by'] == actor['id'] and e['data']['work_date'] == day)
        if data['state'] == 'recorded' and other + data['minutes'] > 1440:
            fail('Staff time cannot exceed 24 hours in a day', 409)
        return w.put(db, identifier, 'p_time', data['area'], data['state'], {k: data[k] for k in ('bucket', 'minutes', 'work_date', 'note')},
                     [actor['id']], actor['id'], 'time_recorded' if not previous else 'time_revised', data['expected_revision'])


def budget_save(actor, data):
    with w.connection() as db:
        access(db, actor, operations=True)
        if actor['role'] not in {'partner', 'firm_administrator'}:
            fail('Budget changes require partner or administrator', 403)
        if data['bucket'] not in BUCKETS:
            fail('Unknown packet budget area')
        if actor['role']!='firm_administrator':
            for area in BUCKETS[data['bucket']]:access(db,actor,area)
        identifier = 'budget:' + data['bucket']; previous = w.entity(db, identifier); revision(previous, data['expected_revision'])
        return w.put(db, identifier, 'p_budget', 'engagement', 'active', {'bucket': data['bucket'], 'hours': str(data['hours']), 'note': data['note'],
                     'original_packet_hours': load_packet()['firm']['budget_hours'][data['bucket']]}, [], actor['id'], 'budget_revised', data['expected_revision'])


def operations(actor, query=''):
    with w.connection() as db:
        access(db, actor, operations=True); admin = actor['role'] == 'firm_administrator'
        rows = w.entities(db); times = [e for e in rows if e['kind'] == 'p_time' and (admin or visible(db, actor, e['area']))]
        budgets = {e['data']['bucket']: e for e in rows if e['kind'] == 'p_budget'}
        summaries = []
        for key, original in load_packet()['firm']['budget_hours'].items():
            if not admin and not any(visible(db, actor, a) for a in BUCKETS[key]):
                continue
            override = budgets.get(key); hours = Decimal(override['data']['hours'] if override else str(original))
            minutes = sum(e['data']['minutes'] for e in times if e['state'] == 'recorded' and e['data']['bucket'] == key)
            actual = Decimal(minutes) / 60
            summaries.append({'bucket': key, 'areas': sorted(BUCKETS[key]), 'original_packet_hours': str(original), 'budget_hours': str(hours),
                              'actual_minutes': minutes, 'actual_hours': format(actual.quantize(Decimal('.01'))), 'remaining_hours': format((hours - actual).quantize(Decimal('.01'))),
                              'over_budget': actual > hours, 'revision': override['revision'] if override else 0})
        deadlines = [e for e in rows if e['kind'] in {'task', 'p_question', 'lc_notice'} and (admin and e['kind'] == 'task' or not admin and visible(db, actor, e['area']))]
        blocks = [e for e in rows if e['kind'] == 'note' and e['state'] != 'resolved' or e['kind'] == 'p_question' and e['data']['blocking'] and e['state'] != 'resolved']
        blocks = [e for e in blocks if admin or visible(db, actor, e['area'])]
        engagement = {'id': w.ENGAGEMENT, 'name': load_packet()['packet']['name'], 'status': 'filing_blocked', 'real_filing_ready': False,
                      'owner_id': w.entity(db, w.ENGAGEMENT)['data']['owner_id'], 'blocking_discussion_note_count': len(blocks)}
        matches = not query or query.casefold() in json.dumps(engagement).casefold()
        # Admin gets operational metadata only; never question bodies, tax notes or notice contents.
        full=admin or '*' in w.membership(db,actor)['data']['areas']
        result={'engagements': [engagement] if matches else [], 'scope': 'Only the single supplied invented case-study engagement; no synthetic firm clients. Actuals include only authorized areas.',
                'budgets': summaries, 'time_entries': [{**e, 'data': {k: v for k, v in e['data'].items() if k != 'note'}} if admin else e for e in times],
                'workload': [{'staff_id': s['id'], 'name': s['name'], 'role': s['role'], 'assignment': w.membership(db, s),
                              'actual_minutes': sum(e['data']['minutes'] for e in times if e['created_by'] == s['id'] and e['state'] == 'recorded'),
                              'open_assignments': sum(e['state'] not in {'complete', 'resolved', 'simulated_closed'} and (e['data'].get('assignee') == s['id'] or e['data'].get('owner_id') == s['id']) for e in deadlines)} for s in load_packet()['firm']['staff']],
                'deadlines': [{'id': e['id'], 'kind': e['kind'], 'state': e['state'], 'due_date': e['data'].get('due_date') or e['data'].get('response_due'),
                               'owner_id': e['data'].get('assignee') or e['data'].get('owner_id'), 'title': e['data'].get('title', 'Assigned response')} for e in deadlines],
                'blockers': [{'id': e['id'], 'area': e['area'], 'state': e['state'], **({'title': e['data']['title']} if not admin else {})} for e in blocks],
                'total_budget_hours': str(sum(Decimal(b['budget_hours']) for b in summaries)), 'total_actual_minutes': sum(e['data']['minutes'] for e in times if e['state'] == 'recorded')}
    if full:
        readiness=w.readiness(actor)
        result['readiness_blockers']=[{'code':b['code'],'count':len(b['resources'])} if admin else b for b in readiness['blockers']]
    else:result['readiness_blockers']=[{'code':'SCOPED_VIEW','note':'Full filing readiness requires an entire-engagement assignment; visible discussions and notes are listed separately.'}]
    return result


def change_scope(db, actor):
    access(db, actor)
    return sorted(w.membership(db, actor)['data']['areas'])


def change_area(db, row):
    if row['area'] == 'finding':
        f = findings().get(row['resource_id']); return [normalized_area(f['area'])] if f else ['engagement']
    if row['area'] == 'adjustment':
        from app.services.finding_service import area_for
        return [normalized_area(area_for(read_one(db, row['resource_id'])['payload']['target']))]
    if row['area'] == 'document':
        evidence = next((e for e in load_packet()['extracted_values'] if e['id'] == row['resource_id']), None)
        return document_areas(evidence['document_id']) if evidence else ['intake']
    entity = w.entity(db, row['resource_id'])
    if entity and entity['kind'] == 'p_attachment':
        return entity['data']['areas']
    return [normalized_area(row['area'])]


def change_associations(db,row,scope):
    docs=set();finding_id=None;adjustment_id=None;review_status=None
    entity=w.entity(db,row['resource_id'])
    refs=[]
    if row['category']=='review':
        finding_id=row['resource_id'];review_status=row['action']
        refs=findings().get(finding_id,{}).get('refs',[])
    elif row['category']=='adjustment':
        adjustment_id=row['resource_id'];refs=read_one(db,adjustment_id)['payload']['refs']
    elif row['category']=='verification':
        evidence=next((e for e in load_packet()['extracted_values'] if e['id']==row['resource_id']),None)
        if evidence:docs.add(evidence['document_id'])
    if entity:
        refs+=entity['data'].get('refs',[])
        if entity['kind']=='p_attachment':docs.update(l['id'] for l in entity['data']['links'] if l['kind']=='document')
        if entity['kind']=='p_document_ack':docs.add(entity['data']['document_id'])
        if entity['kind']=='review_assessment':finding_id=entity['data']['finding_id']
    from app.services.document_accountability_service import reference_documents
    for ref in refs:
        if not ref.startswith(('attachment:','question:','discussion:')):docs.update(reference_documents(ref,'v3'))
    return {'document_ids':sorted(d for d in docs if '*' in scope or all(a in scope for a in document_areas(d))),
            'finding_id':finding_id,'adjustment_id':adjustment_id,'review_status':review_status}


def change_batch(actor, after=None, limit=100):
    with w.connection() as db:
        scope = change_scope(db, actor); scope_hash = w.digest(scope)
        checkpoint = db.execute('SELECT * FROM product_checkpoints WHERE engagement_id=? AND staff_id=?', (w.ENGAGEMENT, actor['id'])).fetchone()
        seen = checkpoint['cursor'] if checkpoint and checkpoint['scope_hash'] == scope_hash else 0
        start = seen if after is None else after
        head = db.execute('SELECT COALESCE(MAX(id),0) FROM product_changes').fetchone()[0]
        if start > head:
            fail('Change cursor is ahead of this database; reset to checkpoint', 409)
        rows = db.execute('SELECT * FROM product_changes WHERE engagement_id=? AND id>? ORDER BY id LIMIT 1000', (w.ENGAGEMENT, start)).fetchall()
        events, cursor = [], start
        known_staff = {s['id'] for s in load_packet()['firm']['staff']}
        for row in rows:
            cursor = row['id']
            resource=w.entity(db,row['resource_id'])
            if resource and resource['engagement_id']!=w.ENGAGEMENT:continue
            areas = change_area(db, row)
            if '*' not in scope and not all(a in scope for a in areas):
                continue
            # Never expose raw audit payload, free-text actor names, filenames or source amounts.
            events.append({**change_associations(db,row,scope),'id': row['id'], 'resource_id': row['resource_id'], 'category': row['category'], 'areas': areas,
                           'action': row['action'], 'actor_id': row['actor_id'] if row['actor_id'] in known_staff else 'recorded_staff', 'created_at': row['created_at']})
            if len(events) >= limit:
                break
        more = bool(db.execute('SELECT 1 FROM product_changes WHERE engagement_id=? AND id>?', (w.ENGAGEMENT, cursor)).fetchone())
        return {'events': events, 'cursor': cursor, 'has_more': more, 'checkpoint': {'cursor': seen, 'revision': checkpoint['revision'] if checkpoint else 0},
                'summary': {'by_area': dict(Counter(a for e in events for a in e['areas'])), 'by_category': dict(Counter(e['category'] for e in events)),
                            'by_document':dict(Counter(d for e in events for d in e['document_ids'])),
                            'by_finding':dict(Counter(e['finding_id'] for e in events if e['finding_id'])),
                            'by_adjustment':dict(Counter(e['adjustment_id'] for e in events if e['adjustment_id'])),
                            'by_review_status':dict(Counter(e['review_status'] for e in events if e['review_status']))},
                'engagement_id': w.ENGAGEMENT, 'scope_hash': scope_hash, 'transport': 'authorized_bounded_long_poll', 'page_limit': limit}


def checkpoint_save(actor, data):
    with w.connection() as db:
        scope = change_scope(db, actor); old = db.execute('SELECT * FROM product_checkpoints WHERE engagement_id=? AND staff_id=?', (w.ENGAGEMENT, actor['id'])).fetchone()
        if (old['revision'] if old else 0) != data['expected_revision']:
            fail('Checkpoint changed in another tab; reload', 409)
        head = db.execute('SELECT COALESCE(MAX(id),0) FROM product_changes WHERE engagement_id=?', (w.ENGAGEMENT,)).fetchone()[0]
        previous = old['cursor'] if old and old['scope_hash'] == w.digest(scope) else 0
        if data['cursor'] > head or data['cursor'] < previous:
            fail('Checkpoint cannot skip the database head or move backwards', 409)
        rev = (old['revision'] if old else 0) + 1
        db.execute('INSERT INTO product_checkpoints VALUES(?,?,?,?,?,?) ON CONFLICT(engagement_id,staff_id) DO UPDATE SET scope_hash=excluded.scope_hash,cursor=excluded.cursor,revision=excluded.revision,updated_at=excluded.updated_at',
                   (w.ENGAGEMENT, actor['id'], w.digest(scope), data['cursor'], rev, w.now()))
        w.event(db, actor['id'], 'p_checkpoint', 'seen_through', actor['id'], {'cursor': data['cursor'], 'scope_hash': w.digest(scope), 'revision': rev})
        return {'cursor': data['cursor'], 'revision': rev}


def resolve_dynamic(actor, ref):
    from app.security_context import request_database
    from app.services.review_service import connect
    active = request_database.get()
    db = active if active is not None else connect()
    try:
        row = item(db, actor, ref)
        if row['kind'] not in EVIDENCE_KINDS:
            fail('Unsupported evidence record')
        return row
    finally:
        if active is None:db.close()
