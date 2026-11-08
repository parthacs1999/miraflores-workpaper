"""Document use, provenance and accountability; no tax conclusions or invented dispositions."""
import re
from functools import lru_cache

from app.services.packet_service import load_packet
from app.services.evidence_service import evidence_graph
from app.services.validation_service import run_validation

DISPOSITIONS = ('used', 'superseded', 'duplicate', 'unextracted', 'unused', 'requires_review')


@lru_cache(maxsize=8192)
def reference_graph(ref, version):
    return evidence_graph(ref, version)


@lru_cache(maxsize=8192)
def reference_documents(ref, version):
    graph = reference_graph(ref, version)
    return frozenset(graph['document_ids'])


@lru_cache(maxsize=3)
def version_traces(version):
    packet = load_packet()
    baseline = next((v for v in packet['return_versions'] if v['version'] == version), None)
    if baseline is None:
        return None
    direct = {}
    unresolved = {}
    for line in baseline['lines']:
        ids = set()
        for ref in line.get('sources', []):
            ids.update(reference_documents(ref, version))
            # Keep unresolvable provenance visible, rather than losing it in tracing.
            for missing in reference_graph(ref, version)['unresolved']:
                unresolved[missing['ref']] = missing
        direct[line['key']] = ids
    return {'baseline': baseline, 'direct': direct, 'unresolved': list(unresolved.values())}


def document_destinations(document_id, version='v3'):
    packet = load_packet()
    trace = version_traces(version)
    if trace is None or not any(d['id'] == document_id for d in packet['documents']):
        return None
    baseline = trace['baseline']
    direct = [line for line in baseline['lines'] if document_id in trace['direct'][line['key']]]
    direct_keys = {l['key'] for l in direct}
    downstream = set(direct_keys)
    while True:
        updated = downstream | {line['key'] for line in baseline['lines'] if downstream.intersection(line.get('inputs', []))}
        if updated == downstream:
            break
        downstream = updated
    index = {l['key']: l for l in baseline['lines']}
    evidence_ids = {e['id'] for e in packet['extracted_values'] if e['document_id'] == document_id}
    associated = []
    from app.services.finding_service import build_catalog
    for origin, findings in [('unified_catalog', build_catalog(version)['findings'])]:
        for i, finding in enumerate(findings):
            refs = finding.get('refs', [])
            direct_ref = any(document_id in reference_documents(ref, version) for ref in refs if ref not in index)
            # Referencing a computed line can be associated even without an explicit document ref.
            line_refs = sorted(set(refs).intersection(downstream))
            if direct_ref or line_refs:
                associated.append({**finding, 'id': finding.get('id', f"engine:{version}:{finding['code']}:{i}"),
                                   'origin': finding.get('origin',origin), 'relationship': 'direct_reference' if direct_ref else 'line_dependency',
                                   'associated_line_keys': line_refs})
    return {'document_id': document_id, 'version': version, 'direct_lines': direct,
            'downstream_lines': [index[k] for k in sorted(downstream-direct_keys)],
            'unused_evidence_ids': sorted(evidence_ids - {s for line in direct for s in line.get('sources', [])}),
            'document_used_by_engine': document_id in baseline.get('documents_used', []),
            'document_superseded_by_engine': document_id in baseline.get('documents_superseded', []),
            'associated_findings': associated,
            'trace_scope': 'Explicit packet provenance and calculation input graph only; no inferred tax relevance.'}


def duplicates(packet, baseline):
    relationships = {}
    for line in baseline['lines']:
        note = line.get('note') or ''
        match = re.search(r'(D\d+) is a second image.*?\((D\d+)\)', note)
        if match:
            relationships[match[1]] = {'document_id': match[2], 'evidence_ref': line['key'], 'reason': note}
    return relationships


def duplicate_pages(document):
    found = []
    pages = document['pages']
    for page in pages:
        text = ' '.join(page['printed_content'].split())
        if not re.search(r'second scan|duplicate', text, re.I):
            continue
        for earlier in pages:
            earlier_text = ' '.join(earlier['printed_content'].split())
            if earlier['page'] < page['page'] and text.endswith(earlier_text):
                found.append({'page': page['page'], 'duplicate_of_page': earlier['page'],
                              'reason': 'Printed page explicitly describes a second scan and repeats the earlier page text.'})
    return found


def accountability(version='v3'):
    packet = load_packet()
    trace = version_traces(version)
    if trace is None:
        return None
    baseline = trace['baseline']
    duplicate = duplicates(packet, baseline)
    documents = []
    for document in packet['documents']:
        identifier = document['id']
        used = identifier in baseline['documents_used']
        superseded = identifier in baseline['documents_superseded']
        traced_lines = [key for key, ids in trace['direct'].items() if identifier in ids]
        dup = duplicate.get(identifier)
        dup_pages = duplicate_pages(document)
        extraction = document['extraction']
        evidence = [e for e in packet['extracted_values'] if e['document_id'] == identifier]
        extracted_pages = {e['page'] for e in evidence}
        unread = [p['page'] for p in document['pages'] if p['page'] not in extracted_pages]
        dispositions, reasons = [], []
        def add(state, reason, refs):
            if state not in dispositions:
                dispositions.append(state)
            reasons.append({'disposition': state, 'reason': reason, 'refs': refs})
        if used or traced_lines:
            add('used', 'Engine declares document used.' if used else 'Document has explicit provenance to return calculations.', traced_lines or [identifier])
        if superseded:
            add('superseded', 'Selected engine version explicitly marks this document superseded.', [identifier])
        if dup:
            add('duplicate', dup['reason'], [dup['evidence_ref'], dup['document_id']])
        if extraction['status'] != 'extracted':
            add('unextracted', extraction.get('reason') or 'Pipeline extraction is incomplete.', [f'doc:{identifier}#page{p}' for p in unread] or [identifier])
        if not used and not traced_lines and not superseded and not dup:
            add('unused', 'No declared engine use or supported return-line provenance in this version. This does not establish irrelevance.', [identifier])
        if used and superseded:
            add('requires_review', 'Engine declares this document both used and superseded.', [identifier])
        if dup_pages:
            add('requires_review', 'A duplicate page occurs within this document; the whole document is not classified as a duplicate.', [f"doc:{identifier}#page{p['page']}" for p in dup_pages])
        if extraction['status'] == 'partial':
            add('requires_review', 'Partial extraction leaves source pages to review manually.', [f'doc:{identifier}#page{p}' for p in unread])
        if not used and not traced_lines and not superseded and not dup:
            add('requires_review', 'Document remains unaccounted for in this engine version; review its purpose and disposition.', [identifier])
        documents.append({'id': identifier, 'title': document['title'], 'dispositions': dispositions,
                          'reasons': reasons, 'engine_used': used, 'engine_superseded': superseded,
                          'extraction_status': extraction['status'], 'extraction_reason': extraction.get('reason'),
                          'extracted_values': len(evidence), 'pages_without_extracted_values': unread,
                          'duplicate_of': dup, 'duplicate_pages': dup_pages, 'traced_line_keys': traced_lines})
    return {'version': version, 'total': len(documents), 'documents': documents,
            'counts': {state: sum(state in d['dispositions'] for d in documents) for state in DISPOSITIONS},
            'unresolved_provenance': trace['unresolved'],
            'note': 'Dispositions are non-exclusive evidence-based dimensions; counts may exceed document total. Unused does not mean irrelevant. Used does not mean verified.'}
