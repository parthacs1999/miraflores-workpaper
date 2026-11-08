"""Conservative text locations: value matches are candidates, not attestations."""
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

NUMBER = re.compile(r'(?<![\w.])\(?-?\$?\d[\d,]*(?:\.\d+)?\)?(?![\w.])')


def number(text):
    try:
        negative = text.startswith('(') and text.endswith(')')
        value = Decimal(text.strip('()').replace('$', '').replace(',', ''))
        return -value if negative else value
    except InvalidOperation:
        return None


def source_candidates(evidence, text):
    raw = str(evidence.get('text_as_read') or '').strip()
    value = evidence.get('value')
    kind = evidence.get('value_type', '')
    matches = []
    numeric = kind in {'number', 'numeric', 'money', 'currency', 'amount', 'integer', 'float', 'decimal', 'percent', 'quantity'} or (isinstance(value, (int, float)) and not isinstance(value, bool))
    if numeric:
        target = number(str(value))
        for match in NUMBER.finditer(text):
            if target is not None and number(match.group()) == target:
                matches.append((match.start(), match.end(), 'exact_extracted_text' if match.group() == raw else 'normalized_number'))
    elif kind == 'date':
        try:
            target = datetime.strptime(str(value), '%Y-%m-%d').date()
        except ValueError:
            target = None
        for match in re.finditer(r'\b(?:\d{1,2}/\d{1,2}/\d{4}|\d{4}-\d{2}-\d{2})\b', text):
            try:
                parsed = datetime.strptime(match.group(), '%Y-%m-%d' if '-' in match.group() else '%m/%d/%Y').date()
                if target is not None and parsed == target:
                    matches.append((match.start(), match.end(), 'normalized_date'))
            except ValueError:
                continue
    else:
        candidate = raw or (str(value) if value is not None else '')
        if candidate:
            for match in re.finditer(r'(?<!\w)' + re.escape(candidate) + r'(?!\w)', text):
                matches.append((match.start(), match.end(), 'exact_extracted_text' if raw else 'exact_value'))
    field = str(evidence.get('field') or '')
    label = str(evidence.get('label') or '')
    box = re.match(r'box(\d+[a-z]?)(?:_([A-Za-z0-9]+))?$', field, re.I)
    expected = box[1].lower() if box else None
    code = box[2] if box else None
    if not expected:
        label_box = re.search(r'\bbox\s+([a-z]|\d+[a-z]?)\b', label, re.I)
        expected = label_box[1].lower() if label_box else None
    anchors = list(re.finditer(r'\bbox\s*(\d+[a-z]?|[a-z])\b', text, re.I))
    results = []
    for start, end, method in matches:
        preceding = [a for a in anchors if a.end() <= start]
        anchor = preceding[-1] if preceding else None
        supported = False
        anchor_text = None
        if anchor and expected and anchor[1].lower() == expected and start - anchor.end() <= 250:
            # A semicolon ends the field; Box 12 subcodes need their own anchor.
            between = text[anchor.end():start]
            if ';' not in between:
                supported = True
                anchor_text = text[anchor.start():start].strip()
                if code and expected == '12':
                    supported = bool(re.search(r'\b' + re.escape(code) + r'\s*$', between, re.I))
        if not expected:
            # Only an exact label directly before this value establishes location.
            prefix = text[max(0, start - len(label) - 8):start]
            if label and re.search(re.escape(label) + r'\s*[:=]?\s*$', prefix, re.I):
                supported = True
                anchor_text = label
        # Brokerage detail uses explicit lot IDs and column words rather than boxes.
        lot = re.fullmatch(r'([A-Z]+\d+)_(proceeds|basis|wash|acq|acquired|sold|desc|description|quantity)', field)
        if lot:
            segment_start = text.rfind(';', 0, start) + 1
            segment = text[segment_start:start]
            lot_anchor = re.search(r'(?<!\w)(?:Lot\s+)?' + re.escape(lot[1]) + r'\b', segment)
            if lot_anchor:
                column = {'acq': 'acquired', 'acquired': 'acquired', 'sold': 'sold', 'proceeds': 'proceeds', 'basis': 'basis', 'wash': 'wash sale loss disallowed'}.get(lot[2])
                if column and re.search(r'\b' + re.escape(column) + r'\s*$', segment, re.I):
                    supported, anchor_text = True, lot[1] + ' ' + column
                elif lot[2] in {'desc', 'description'} and not segment[lot_anchor.end():].strip():
                    supported, anchor_text = True, lot[1] + ' description'
                elif lot[2] == 'quantity' and re.match(r'\s+sh\b', text[end:]):
                    supported, anchor_text = True, lot[1] + ' quantity'
        results.append({'method': method, 'matched_text': text[start:end], 'start': start, 'end': end,
                        'field_supported': supported, 'field_anchor': anchor_text,
                        'context': text[max(0, start-70):min(len(text), end+70)],
                        'line': text.count('\n', 0, start) + 1,
                        'column': start - text.rfind('\n', 0, start)})
    anchored = [c for c in results if c['field_supported']]
    if len(anchored) == 1:
        assessment = 'field_supported'
        chosen = anchored[0]
        reason = 'A unique value was attributed to the named printed field. This is automatic matching, not human verification.'
    elif len(anchored) > 1 or len(results) > 1:
        assessment, chosen = 'ambiguous', None
        reason = 'Multiple matching locations remain; select and review the specific source field before attesting.'
    elif results:
        assessment, chosen = 'candidate_only', None
        reason = 'A value occurs on the page, but no reliable field anchor attributes it to this extraction.'
    else:
        assessment, chosen = 'not_found', None
        reason = 'No equivalent value was located. This is not proof of an extraction error.'
    return {'assessment': assessment, 'candidates': results, 'match': chosen, 'reason': reason,
            'automatic': True, 'human_verified': False, 'ambiguity_resolved_by_field': len(results) > 1 and len(anchored) == 1}
