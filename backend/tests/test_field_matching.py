from app.services.field_match_service import source_candidates
from app.services.source_verification_service import verify_extracted_value, get_source_verification


def test_duplicate_amounts_without_field_anchor_are_ambiguous():
    result = source_candidates({'field': 'wages', 'value': 1000, 'value_type': 'money', 'text_as_read': '1,000.00'}, 'Wages 1,000.00; interest 1,000.00')
    assert result['assessment'] == 'ambiguous' and result['match'] is None
    assert len(result['candidates']) == 2
    assert not result['human_verified']


def test_named_box_disambiguates_identical_amounts():
    result = source_candidates({'field': 'box1', 'value': 1000, 'value_type': 'money'}, 'Box 1 1,000.00; Box 2 1,000.00')
    assert result['assessment'] == 'field_supported'
    assert result['match']['start'] == 6
    assert result['ambiguity_resolved_by_field']
    assert result['match']['matched_text'] == '1,000.00'


def test_repeated_same_box_is_still_ambiguous():
    result = source_candidates({'field': 'box1', 'value': 1000, 'value_type': 'money'}, 'Box 1 1,000.00; Box 1 1,000.00')
    assert result['assessment'] == 'ambiguous' and result['match'] is None


def test_matching_number_in_wrong_box_is_not_supported():
    evidence = {'id': 'test', 'document_id': 'TEST', 'page': 1, 'field': 'box1', 'label': 'Wages', 'value': 1000, 'value_type': 'money'}
    result = verify_extracted_value(evidence, {'TEST': {'title': 'Test', 'pages': [{'page': 1, 'printed_content': 'Box 1 2,000.00; Box 2 1,000.00'}]}})
    assert result['status'] == 'unverified' and result['assessment'] == 'candidate_only'
    assert result['match'] is None


def test_unique_unattributed_number_is_only_a_candidate():
    result = source_candidates({'field': 'box1', 'value': 1000, 'value_type': 'money'}, 'An amount of 1,000.00 appears here')
    assert result['assessment'] == 'candidate_only' and result['match'] is None


def test_box12_subcode_requires_exact_code_boundary():
    text = 'Box 12 D 2,500.00, W 2,500.00, DD 2,500.00;'
    result = source_candidates({'field': 'box12_W', 'value': 2500, 'value_type': 'money'}, text)
    assert result['assessment'] == 'field_supported'
    assert text[result['match']['start']-2:result['match']['start']] == 'W '
    result = source_candidates({'field': 'box12_D', 'value': 2500, 'value_type': 'money'}, text)
    assert text[result['match']['start']-2:result['match']['start']] == 'D '


def test_lot_and_column_disambiguate_repeated_basis_and_wash_amounts():
    text = 'X1 Harbor Foods proceeds 100.00 basis 100.00 wash sale loss disallowed 0.00; X2 Acadia proceeds 100.00 basis 100.00 wash sale loss disallowed 0.00.'
    result = source_candidates({'field': 'X2_basis', 'value': 100, 'value_type': 'money'}, text)
    assert result['assessment'] == 'field_supported'
    assert result['match']['start'] == text.rfind('100.00')
    assert result['match']['field_anchor'] == 'X2 basis'


def test_raw_text_does_not_override_inconsistent_numeric_value():
    result = source_candidates({'field': 'box1', 'value': 2000, 'text_as_read': '1,000.00', 'value_type': 'money'}, 'Box 1 1,000.00')
    assert result['assessment'] == 'not_found'


def test_numeric_boundaries_and_parenthesized_values():
    result = source_candidates({'field': 'box1', 'value': 1000, 'value_type': 'money'}, 'Box 1 11,000.00')
    assert result['assessment'] == 'not_found'
    result = source_candidates({'field': 'box1', 'value': -1000, 'value_type': 'money'}, 'Box 1 (1,000.00)')
    assert result['match']['matched_text'] == '(1,000.00)'


def test_real_wages_have_field_offsets_but_are_not_human_verification():
    result = get_source_verification('ev-0016')
    assert result['status'] == 'supported' and result['assessment'] == 'field_supported'
    assert result['automatic'] is True and result['human_verified'] is False
    match = result['match']
    assert result['printed_content'][match['start']:match['end']] == match['matched_text']
    assert match['field_anchor'].startswith('Box 1')
