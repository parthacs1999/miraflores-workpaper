"""Reproducible decimal comparisons. No inference of missing tax rules or values."""
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Callable

from app.services.evidence_service import resolve_reference

AMOUNT = r'(-?\d[\d,]*(?:\.\d+)?)'


class Unsupported(Exception):
    pass


class ConflictingSources(Unsupported):
    pass


def decimal(value):
    if isinstance(value, bool) or value is None:
        raise Unsupported('A numeric input is missing or not a monetary/quantity value.')
    try:
        result = Decimal(str(value).replace(',', ''))
    except (InvalidOperation, ValueError):
        raise Unsupported('Source is not numeric.') from None
    if not result.is_finite():
        raise Unsupported('Source is not finite.')
    return result


def display(value):
    return format(value, 'f') if isinstance(value, Decimal) else value


@dataclass(frozen=True)
class Rule:
    id: str
    area: str
    title: str
    target: str | None
    method: str
    evaluate: Callable
    jurisdiction: str = 'federal'
    judgment: bool = False
    unit: str = 'dollars'
    comparison: str = 'source_reconciliation'
    evidence_refs: tuple = ()


class Context:
    def __init__(self, packet, version):
        self.packet = packet
        self.version = version
        self.lines = {l['key']: l for l in version['lines']}
        self.documents = {d['id']: d for d in packet['documents']}
        self.inputs = []
        self.steps = []

    def step(self, description, value):
        self.steps.append({'description': description, 'result': display(value)})
        return value

    def input(self, label, value, ref, kind='source', location=None, raw=None):
        document_id = ref[4:].split('#')[0] if ref.startswith('doc:') else ref if re.fullmatch(r'D\d+',ref) else None
        available_at = self.documents.get(document_id,{}).get('received_at') if document_id else None
        self.inputs.append({'label': label, 'value': display(value), 'ref': ref, 'kind': kind,
                            'location': location, 'raw': raw, 'available_at': available_at,
                            'available_after_engine': bool(available_at and available_at[:10] > self.version['computed_at'][:10])})
        return value

    def text(self, doc, page=1):
        document = self.documents.get(doc)
        if not document:
            raise Unsupported(f'Source document {doc} is missing.')
        source = next((p for p in document['pages'] if p['page'] == page), None)
        if not source:
            raise Unsupported(f'Source page {doc} page {page} is missing.')
        return source['printed_content']

    def amount(self, doc, pattern, label, page=1):
        text = self.text(doc, page)
        matches = list(re.finditer(pattern, text, re.I))
        if not matches:
            raise Unsupported(f'{label}: required printed source field was not found in {doc} page {page}.')
        if len(matches) != 1:
            raise ConflictingSources(f'{label}: more than one printed source field matches; human attribution is required.')
        match = matches[0]
        value = decimal(match.group(1))
        return self.input(label, value, f'doc:{doc}#page{page}', 'printed_source',
                          {'start': match.start(1), 'end': match.end(1)}, match.group(1))

    def require_text(self, doc, phrase, page=1):
        if phrase.lower() not in self.text(doc, page).lower():
            raise Unsupported(f'{doc} does not establish the required fact: {phrase}')
        self.input('Required source fact', phrase, f'doc:{doc}#page{page}', 'printed_source')

    def record(self, ref, path=(), label=None):
        result = resolve_reference(ref, self.version['version'], self.packet)
        if result.status != 'resolved':
            raise Unsupported(result.reason + ' ' + ref)
        value = result.value
        try:
            for key in path:
                value = value[key]
        except (TypeError, KeyError, IndexError):
            raise Unsupported(f'Missing structured source input: {ref} {path}') from None
        return self.input(label or ref, value, ref, result.type)

    def number(self, ref, path=(), label=None):
        return decimal(self.record(ref, path, label))

    def line(self, key):
        line = self.lines.get(key)
        if line is None:
            raise Unsupported('Reported return line is missing: ' + key)
        return self.input(line['label'], decimal(line['value']), key, 'engine_reported')

    def param(self, name):
        return self.number('ref:param.' + name)


def compare(expected, reported, quantum=Decimal('1')):
    """Quantum comes from the packet line format, not a guessed firm tolerance."""
    expected, reported = decimal(expected), decimal(reported)
    rounded = expected.quantize(quantum, rounding=ROUND_HALF_UP)
    if reported == expected:
        conclusion = 'exact_match'
    elif reported == rounded:
        conclusion = 'rounding_difference'
    else:
        conclusion = 'exact_mismatch'
    return {'expected_value': display(rounded), 'expected_unrounded': display(expected),
            'reported_value': display(reported), 'difference': display(reported-rounded),
            'unrounded_difference': display(reported-expected), 'conclusion': conclusion,
            'tolerance': '0', 'rounding_quantum': display(quantum),
            'tolerance_basis': 'Exact comparison after packet display rounding; no firm reconciliation tolerance is supplied.'}


def execute(rule, packet, version):
    ctx = Context(packet, version)
    result = {'id': rule.id, 'version': version['version'], 'rule_version': 1, 'tax_year': packet['household']['tax_year'],
              'area': rule.area, 'title': rule.title, 'target': rule.target, 'jurisdiction': rule.jurisdiction,
              'method': rule.method, 'check_type': 'professional_judgment' if rule.judgment else rule.comparison,
              'unit': rule.unit, 'expected_value': None, 'reported_value': None, 'difference': None,
              'tolerance': None, 'conclusion': 'unsupported', 'reason': '',
              'materiality': 'No general reconciliation materiality is specified by the firm.',
              'inputs': ctx.inputs, 'steps': ctx.steps}
    try:
        if rule.target and rule.target in ctx.lines:
            result['reported_value'] = display(ctx.line(rule.target))
        expected = rule.evaluate(ctx)
        if expected is None:
            raise Unsupported('No supportable expected value is available.')
        ctx.step(rule.method,expected)
        result['expected_value'] = display(decimal(expected))
        if rule.target and result['reported_value'] is None:
            raise Unsupported('Reported return line is missing: ' + rule.target)
        reported = decimal(result['reported_value']) if rule.target else getattr(ctx,'comparison_reported',expected)
        result.update(compare(expected, reported, Decimal('0.01') if not rule.target or rule.target.startswith('F8949.') else Decimal('1')))
        ctx.step('Reported minus expected after packet display rounding',decimal(result['difference']))
        if rule.judgment:
            result['conclusion'] = 'judgment_required'
            result['reason'] = 'Conditional/document comparison only. A CPA must assess the assumptions and treatment; this is not a finalized tax result.'
        else:
            result['reason'] = 'Reproduced from the listed source values and computation steps. This does not recompute downstream tax.'
    except ConflictingSources as error:
        result.update(conclusion='conflicting_sources', reason=str(error))
    except (Unsupported, KeyError, IndexError, TypeError, ZeroDivisionError, InvalidOperation) as error:
        result.update(conclusion='unsupported', reason=str(error) or 'A required source input is missing.')
    result['refs'] = list(dict.fromkeys([i['ref'] for i in ctx.inputs] + list(rule.evidence_refs) + ([rule.target] if rule.target else [])))
    return result
