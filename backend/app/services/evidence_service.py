"""Version-aware reference resolution. Unknown references are data, never dropped."""
import re
from typing import Any, Literal

from pydantic import BaseModel, Field
from app.services.packet_service import load_packet

EvidenceKind = Literal['extracted_value', 'document', 'document_page', 'prior_year', 'agency',
                       'questionnaire', 'message', 'call_note', 'asset', 'household_member',
                       'engine_parameter', 'fx_rate', 'timeline_event', 'return_line', 'return_version', 'attachment', 'collaboration_question', 'collaboration_message', 'unknown']


class EvidenceResolution(BaseModel):
    ref: str
    version: str
    type: EvidenceKind
    status: Literal['resolved', 'unresolved']
    reason_code: str | None = None
    reason: str
    label: str | None = None
    value: Any = None
    location: str | None = None
    related_refs: list[str] = Field(default_factory=list)
    document_ids: list[str] = Field(default_factory=list)


class EvidenceGraphResult(BaseModel):
    reference: str
    version: str
    resolution: EvidenceResolution
    nodes: list[EvidenceResolution]
    cycles: list[dict[str, str]]
    document_ids: list[str]
    unresolved: list[EvidenceResolution]


def json_pointer(root, pointer):
    """RFC 6901, including ~0/~1 escapes, arrays, nulls and the empty pointer."""
    if pointer == '':
        return root
    if not pointer.startswith('/'):
        raise ValueError('JSON Pointer must be empty or start with /')
    value = root
    for token in pointer.split('/')[1:]:
        if re.search(r'~(?![01])', token):
            raise ValueError('Invalid JSON Pointer escape')
        token = token.replace('~1', '/').replace('~0', '~')
        if isinstance(value, list):
            if not re.fullmatch(r'0|[1-9]\d*', token):
                raise ValueError('Array pointer requires a non-negative canonical integer index')
            value = value[int(token)]
        elif isinstance(value, dict):
            value = value[token]
        else:
            raise KeyError('Pointer traverses a scalar')
    return value


def reference_strings(value):
    """Only declared source/reference fields; never interpret arbitrary amounts as refs."""
    result = []
    if isinstance(value, dict):
        for key, entry in value.items():
            if key in {'sources', 'source', 'refs', 'document', 'source_document'}:
                if isinstance(entry, str):
                    # Narrative provenance is retained separately, but document IDs in
                    # explicit source fields are valid supporting links.
                    document_refs = re.findall(r'(?<![\w])D\d{2}(?!\d)', entry)
                    result.extend(document_refs)
                    if entry.startswith(('ev-', 'py:', 'agency:', 'asset:', 'doc:', 'qa-', 'msg-', 'call-', 'household:', 'ref:', 'timeline:')):
                        result.append(entry)
                    elif not document_refs and entry:
                        result.append(entry)
                elif isinstance(entry, list):
                    result.extend(x for x in entry if isinstance(x, str))
            elif isinstance(entry, (dict, list)):
                result.extend(reference_strings(entry))
    elif isinstance(value, list):
        for entry in value:
            result.extend(reference_strings(entry))
    return list(dict.fromkeys(result))


def resolve_reference(ref, version='v3', packet=None):
    if ref.startswith(('attachment:', 'question:', 'discussion:')):
        from app.security_context import request_principal
        from app.services.product_service import resolve_dynamic
        from app.services.adjustment_service import AdjustmentError
        kind='attachment' if ref.startswith('attachment:') else 'collaboration_question' if ref.startswith('question:') else 'collaboration_message'
        result=EvidenceResolution(ref=ref,version=version,type=kind,status='unresolved',reason_code='access_or_temporal_context',reason='Live supporting evidence requires an authorized current-workpaper context; it is not injected into historical packet replay.')
        if packet is not None or not request_principal.get():return result
        try:row=resolve_dynamic(request_principal.get(),ref)
        except AdjustmentError:return result.model_copy(update={'reason_code':'unavailable_reference','reason':'Supporting record is missing or outside the authorized scope.'})
        return EvidenceResolution(ref=ref,version=version,type=kind,status='resolved',reason='Live workpaper evidence resolved; no extraction or client identity assurance is inferred.',label=row['data'].get('title',ref),value=row,location='workpaper/'+ref,related_refs=row['data'].get('refs',[]))
    packet = packet if packet is not None else load_packet()
    baseline = next((v for v in packet['return_versions'] if v['version'] == version), None)
    result = EvidenceResolution(ref=ref, version=version, type='unknown', status='unresolved',
                                reason_code='unknown_format', reason='Reference does not match a documented format.')
    if baseline is None:
        return result.model_copy(update={'reason_code': 'unknown_version', 'reason': 'Return version was not found.'})
    documents = {d['id']: d for d in packet['documents']}
    def resolved(kind, value, location, label=None, related=None, doc_ids=None):
        return EvidenceResolution(ref=ref, version=version, type=kind, status='resolved', reason='Reference resolved.',
                                  label=label or ref, value=value, location=location,
                                  related_refs=list(dict.fromkeys(related or [])), document_ids=doc_ids or [])
    kind = 'unknown'
    try:
        if ref.startswith('ev-'):
            kind = 'extracted_value'
            evidence = next(e for e in packet['extracted_values'] if e['id'] == ref)
            doc = documents[evidence['document_id']]
            if not any(p['page'] == evidence['page'] for p in doc['pages']):
                raise KeyError('Source page missing')
            return resolved(kind, evidence, f"extracted_values/{ref}", evidence['label'],
                            [f"doc:{doc['id']}#page{evidence['page']}"], [doc['id']])
        if re.fullmatch(r'D\d+', ref):
            kind = 'document'
            doc = documents[ref]
            return resolved(kind, doc, f'documents/{ref}', doc['title'], doc_ids=[ref])
        if ref.startswith('doc:'):
            kind = 'document_page'
            match = re.fullmatch(r'doc:(D\d+)#page([1-9]\d*)', ref)
            if not match:
                raise ValueError('Document page format must be doc:DNN#pageN')
            doc = documents[match[1]]
            page = next(p for p in doc['pages'] if p['page'] == int(match[2]))
            return resolved(kind, {'document_id': doc['id'], 'title': doc['title'], **page},
                            f"documents/{doc['id']}/pages/{page['page']}", f"{doc['title']} · page {page['page']}", doc_ids=[doc['id']])
        for prefix, root_name, root_kind in [('py:', 'prior_years', 'prior_year'), ('agency:', 'tax_agency_records', 'agency')]:
            if ref.startswith(prefix):
                kind = root_kind
                pointer = ref[len(prefix):]
                value = json_pointer(packet[root_name], pointer)
                related = reference_strings(value)
                # Scalar pointers inherit provenance from their immediate record and
                # the packet's explicit line_sources/carryover source annotations.
                parent_pointer = pointer.rsplit('/', 1)[0] if '/' in pointer else ''
                while True:
                    parent = json_pointer(packet[root_name], parent_pointer)
                    local = reference_strings({k: v for k, v in parent.items() if k in {'source', 'sources', 'document', 'source_document'}}) if isinstance(parent, dict) else []
                    if local:
                        related.extend(local)
                        break
                    if not parent_pointer:
                        break
                    parent_pointer = parent_pointer.rsplit('/', 1)[0]
                if root_name == 'prior_years':
                    if pointer.startswith('/return_2024/lines/'):
                        key = pointer[len('/return_2024/lines/'):].replace('~1','/').replace('~0','~')
                        sources = packet[root_name]['return_2024'].get('line_sources', {}).get(key, [])
                        related.extend([sources] if isinstance(sources, str) else sources)
                    elif pointer.startswith('/carryovers_into_2025'):
                        related.extend(reference_strings({'sources': packet[root_name]['carryovers_into_2025'].get('sources', '')}))
                    elif pointer.startswith('/prior_preparer_workpaper'):
                        related.append(packet[root_name]['prior_preparer_workpaper']['source_document'])
                    elif pointer.startswith('/asset_records'):
                        related.append(packet[root_name]['prior_preparer_workpaper']['source_document'])
                if root_name == 'tax_agency_records' and pointer.startswith('/') and not related:
                    record_name = pointer.split('/')[1]
                    for document in packet['documents']:
                        for page in document['pages']:
                            if re.search(r'\b(?:see\s+)?tax_agency_records\.' + re.escape(record_name) + r'(?![\w])', page['printed_content'], re.I):
                                related.append(f"doc:{document['id']}#page{page['page']}")
                return resolved(kind, value, root_name + pointer, related=related)
        for prefix, collection, client_kind in [('qa-', 'questionnaire', 'questionnaire'), ('msg-', 'messages', 'message'), ('call-', 'call_notes', 'call_note')]:
            if ref.startswith(prefix):
                kind = client_kind
                value = next(x for x in packet['client'][collection] if x['id'] == ref)
                return resolved(kind, value, f'client/{collection}/{ref}', related=reference_strings(value))
        if ref.startswith('asset:'):
            kind = 'asset'
            identifier = ref[6:]
            value = next((a for a in baseline['assets'] if a['asset_id'] == identifier), None)
            location = f'return_versions/{version}/assets/{identifier}'
            if value is None:
                value = next(a for a in packet['prior_years']['asset_records'] if a['asset_id'] == identifier)
                location = f'prior_years/asset_records/{identifier}'
            return resolved(kind, value, location, value['description'], related=reference_strings(value))
        if ref.startswith('household:'):
            kind = 'household_member'
            value = next(x for x in packet['household']['people'] if x['id'] == ref[10:])
            return resolved(kind, value, 'household/people/' + ref[10:], value['name'])
        if ref.startswith(('ref:param.', 'ref:fx.')):
            kind = 'fx_rate' if ref.startswith('ref:fx.') else 'engine_parameter'
            path = ref[7:].split('.') if kind == 'fx_rate' else ref[10:].split('.')
            if kind == 'fx_rate':
                path = ['fx'] + path
            value = packet['engine_reference']['parameters']
            for part in path:
                if not part:
                    raise ValueError('Empty parameter path segment')
                value = value[part]
            return resolved(kind, value, 'engine_reference/parameters/' + '/'.join(path))
        if ref.startswith('timeline:'):
            kind = 'timeline_event'
            value = next(x for x in packet['timeline'] if x['id'] == ref[9:])
            return resolved(kind, value, 'timeline/' + ref[9:], value['event'], related=value.get('refs', []))
        if re.fullmatch(r'[A-Za-z][A-Za-z0-9-]*\..+', ref):
            kind = 'return_line'
            value = next(l for l in baseline['lines'] if l['key'] == ref)
            return resolved(kind, value, f'return_versions/{version}/lines/{ref}', value['label'],
                            related=value.get('sources', []) + value.get('inputs', []))
    except ValueError as error:
        return result.model_copy(update={'type': kind, 'reason_code': 'invalid_reference', 'reason': str(error)})
    except (KeyError, IndexError, StopIteration, TypeError):
        return result.model_copy(update={'type': kind, 'reason_code': 'missing_reference',
                                         'reason': 'Referenced record, key, index, or source page was not found in this packet/version.'})
    return result


def evidence_graph(ref, version='v3', packet=None):
    """Finite graph, preserving unresolved nodes and recording cycles explicitly."""
    supplied_packet = packet
    nodes, cycles = {}, []
    def visit(current, path):
        if current in path:
            cycles.append({'from': path[-1], 'to': current})
            return
        if current in nodes:
            return
        node = resolve_reference(current, version, supplied_packet)
        nodes[current] = node
        for related in node.related_refs:
            visit(related, path + [current])
    visit(ref, [])
    return {'reference': ref, 'version': version, 'resolution': nodes[ref].model_dump(),
            'nodes': [n.model_dump() for n in nodes.values()], 'cycles': cycles,
            'document_ids': sorted({d for n in nodes.values() for d in n.document_ids}),
            'unresolved': [n.model_dump() for n in nodes.values() if n.status == 'unresolved']}
