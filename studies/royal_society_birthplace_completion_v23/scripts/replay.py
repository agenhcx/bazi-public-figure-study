#!/usr/bin/env python3
"""Reconstruct exact UK v22, then apply v23 first-birthplace facts.

The v10 carrier and frozen v11/v12/v13/v14/v15/v16/v17/v18/v19/v20/v21/v22 inputs are self-contained.
First-birthplace source grades remain separate from frozen native DOB grades.
Canonical JSONL hashes avoid relying on Python-specific gzip headers.
"""
import copy
import csv
import gzip
import hashlib
import io
import json
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_V10 = 'e44f6dc02cc0cafece9b792164f016da0f08de5736ac62442d176d45b19a5799'
EXPECTED_V11_CANONICAL = '577515b90cff05d61288222a4daf595aaaed76a1baa16ab96391720b02c32da6'
EXPECTED_V12_CANONICAL = '1b6318ed3e7056886949b47ff08f65eaa518a355cede9de67be934088eadf108'
EXPECTED_V13_CANONICAL = '1b6318ed3e7056886949b47ff08f65eaa518a355cede9de67be934088eadf108'
EXPECTED_V14_CANONICAL = '1b6318ed3e7056886949b47ff08f65eaa518a355cede9de67be934088eadf108'
EXPECTED_V15_CANONICAL = 'c05181f1d910507405ed5ae728aeecb2430b36ba01ea7ced1f84694f1d026255'
EXPECTED_V16_CANONICAL = '4811ffec9a75ac2d9488bc2a1bd97922369bf40b27362a59fb9d4ddfdcfd3d9f'
EXPECTED_V17_CANONICAL = '4354dfa3272b960448ba2614d76c4cda6539ae9aa8cb0898eb8f9b1de7a3bde4'
EXPECTED_V18_CANONICAL = 'f515cb1b649f3408d960b8dacd9ccdfddb82dab312adb2c95c0f4480b43feaf8'
EXPECTED_V19_CANONICAL = '5c8d93078101a69b32c9652c6bcbc99ce926c2dd4bd50547e235071ae377c043'
EXPECTED_V20_CANONICAL = 'bbe9e22d00c4bfb3fb7a390df6a18a349e0abe64ba2986cd5075650f62ae9f2b'
EXPECTED_V21_CANONICAL = '91b14b75fa13811abed8122644ed4b10f739fef5695ee72ed62ad5fd296bcac2'
EXPECTED_V22_CANONICAL = '728502a5f0a71570a262a894dc800a9073ff19bbba68e2c7a7dd7027a5f8f2b9'
V22_SOURCE_COMMIT = 'b3c22b66be309470b5e17ad1d0f681bf71ed581f'
V21_SOURCE_COMMIT = '065a8a5e438b6fadb85756df6ad513fb9aba27ae'
V20_SOURCE_COMMIT = '4f15eecc06904eee10005d1c2a09eaea9771e834'
V19_SOURCE_COMMIT = '25b6b8f40d148d2e6c61235675446bbbfbdb4928'
V18_SOURCE_COMMIT = 'd7fa790be25c26e8fc07d92976a7dc4052e1f527'
V17_SOURCE_COMMIT = '1804b275112484268a1fd0f41318ea9cb85b2125'
V16_SOURCE_COMMIT = '72edac7cceca5cc4aa077dddc8c5fde401059b36'
V15_FOLLOWUP_SCOPE = {'RS_PAST_NA3607', 'RS_PAST_NA3629', 'RS_PAST_NA3957', 'RS_PAST_NA3652',
                  'RS_PAST_NA4682', 'RS_PAST_NA4250', 'RS_PAST_NA4117', 'RS_PAST_NA4780'}
V16_FOLLOWUP_SCOPE = {
    'RS_PAST_NA3088', 'RS_PAST_NA3964', 'RS_PAST_NA4211', 'RS_PAST_NA4680',
    'RS_PAST_NA5416', 'RS_PAST_NA3971', 'RS_PAST_NA4568', 'RS_PAST_NA4774',
    'RS_PAST_NA4050', 'RS_PAST_NA6870', 'RS_PAST_NA6897', 'RS_PAST_NA4863'
}
V17_INDIVIDUAL_FOLLOWUP_SCOPE = {
    'RS_PAST_NA4155', 'RS_PAST_NA5003', 'RS_PAST_NA629', 'RS_PAST_NA5508',
    'RS_PAST_NA6313', 'RS_PAST_NA645', 'RS_PAST_NA637', 'RS_PAST_NA4592'
}
V17_REVIEWED_SCOPE = {
    'RS_PAST_NA1266', 'RS_PAST_NA1376', 'RS_PAST_NA1614', 'RS_PAST_NA2688',
    'RS_PAST_NA3483', 'RS_PAST_NA4155', 'RS_PAST_NA4592', 'RS_PAST_NA5003',
    'RS_PAST_NA5508', 'RS_PAST_NA5620', 'RS_PAST_NA629', 'RS_PAST_NA6313',
    'RS_PAST_NA637', 'RS_PAST_NA645', 'RS_PAST_NA7080'
}
V18_INDIVIDUAL_FOLLOWUP_SCOPE = {
    'RS_PAST_NA1744', 'RS_PAST_NA3830', 'RS_PAST_NA4918', 'RS_PAST_NA8089',
    'RS_PAST_NA3358', 'RS_PAST_NA5962', 'RS_PAST_NA6938', 'RS_PAST_NA4005'
}
V18_REVIEWED_SCOPE = {
    'RS_PAST_NA1376', 'RS_PAST_NA1744', 'RS_PAST_NA3358',
    'RS_PAST_NA3830', 'RS_PAST_NA4005', 'RS_PAST_NA4918',
    'RS_PAST_NA5962', 'RS_PAST_NA6938', 'RS_PAST_NA8089'
}
V19_INDIVIDUAL_FOLLOWUP_SCOPE = {
    'RS_PAST_NA3979',
    'RS_PAST_NA4485',
    'RS_PAST_NA4601',
    'RS_PAST_NA4667',
    'RS_PAST_NA3912',
    'RS_PAST_NA4627',
    'RS_PAST_NA4614',
    'RS_PAST_NA2099',
    'RS_PAST_NA4636',
    'RS_PAST_NA4124',
    'RS_CURRENT_11792',
    'RS_CURRENT_37377',
}
V20_INDIVIDUAL_FOLLOWUP_SCOPE = {
    'RS_PAST_NA4036', 'RS_PAST_NA4166', 'RS_PAST_NA4179', 'RS_PAST_NA4490',
    'RS_PAST_NA2044', 'RS_PAST_NA2090', 'RS_PAST_NA4170', 'RS_PAST_NA1998'
}
V21_INDIVIDUAL_FOLLOWUP_SCOPE = {
    'RS_PAST_NA4651', 'RS_PAST_NA4585', 'RS_PAST_NA4834', 'RS_PAST_NA4076',
    'RS_PAST_NA8672', 'RS_PAST_NA8700', 'RS_PAST_NA5885', 'RS_PAST_NA9858'
}
V22_INDIVIDUAL_FOLLOWUP_SCOPE = {
    'RS_PAST_NA4252', 'RS_PAST_NA4747', 'RS_PAST_NA4220', 'RS_PAST_NA3931',
    'RS_PAST_NA4193', 'RS_PAST_NA6876', 'RS_PAST_NA3621', 'RS_PAST_NA3635'
}
INDIVIDUAL_FOLLOWUP_SCOPE = {
    'RS_PAST_NA4139', 'RS_PAST_NA4064', 'RS_PAST_NA4074', 'RS_PAST_NA4591',
    'RS_PAST_NA3474', 'RS_PAST_NA4233', 'RS_PAST_NA4301', 'RS_PAST_NA4642',
    'RS_PAST_NA4616', 'RS_PAST_NA4630', 'RS_PAST_NA7048', 'RS_PAST_NA5422'
}
GEOGRAPHY_PILOT_SCOPE = {'RS_PAST_NA4918'}
V20_GEOGRAPHY_FIELD = 'geography_followup_v20'
BIRTHPLACE_FIELD = 'birthplace_followup_v23'
GEOGRAPHY_FIELD = 'geography_followup_v14'
WINDOW_START, WINDOW_END = date(1835, 1, 1), date(1985, 12, 31)
GEO_FIELDS = {'hemisphere', 'geo_resolution_status', 'geography_decision',
              'reason', 'northern_birthplace_candidate', 'southern_birthplace_separate'}


def canonical_bytes(rows):
    return ''.join(json.dumps(r, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n'
                   for r in rows).encode('utf-8')


def encode_gzip(rows):
    # GzipFile uses a fixed OS header; filename and mtime are explicitly blank/zero.
    buf = io.BytesIO()
    with gzip.GzipFile(filename='', mode='wb', fileobj=buf, compresslevel=9, mtime=0) as stream:
        stream.write(canonical_bytes(rows))
    return buf.getvalue()


def in_window(row):
    return WINDOW_START <= date.fromisoformat(row['dob']) <= WINDOW_END


def json_file(path):
    return json.loads(path.read_text(encoding='utf-8'))


def apply_context(rows, facts, version):
    """Apply one accepted context object per unknown cohort key; retain old evidence."""
    assert isinstance(facts, list)
    by_id = {fact['record_id']: fact for fact in facts}
    assert len(by_id) == len(facts), 'Duplicate accepted keys'
    row_ids = {row['record_id'] for row in rows}
    assert set(by_id) <= row_ids, 'Accepted key outside fixed cohort'
    context_field = 'birthplace_followup_' + version
    allowed = GEO_FIELDS | {context_field}
    updated, changes = [], []
    for before in rows:
        after = copy.deepcopy(before)
        fact = by_id.get(before['record_id'])
        if fact is not None:
            assert before['hemisphere'] == 'unknown', before['record_id']
            assert before['dob'] == fact['native_dob'], before['record_id']
            assert before['source_authorised_full_name'] == fact['authority_name'], before['record_id']
            assert before['raw_birthplace'], 'This batch refines existing explicit birthplaces only'
            assert fact['source_grade'] in {'S1', 'S2', 'S3'}
            hemisphere = fact['reviewed_hemisphere']
            assert hemisphere in {'north', 'south'}
            assert context_field not in before, 'Already supplemented at this version'
            directional = 'northern' if hemisphere == 'north' else 'southern'
            after.update(hemisphere=hemisphere,
                         geo_resolution_status='resolved_by_' + version + '_explicit_region_context',
                         geography_decision=version + '_explicit_birthplace_region_context',
                         reason='explicit_birthplace_context_wholly_' + directional + '_region',
                         northern_birthplace_candidate=hemisphere == 'north',
                         southern_birthplace_separate=hemisphere == 'south')
            after[context_field] = fact
            changes.append({'record_id': before['record_id'], 'native_name': before['name'],
                            'dob': before['dob'], 'prior_raw_birthplace': before['raw_birthplace'],
                            'before_hemisphere': before['hemisphere'], 'after_hemisphere': hemisphere,
                            'qualified_context': fact['qualified_context'],
                            'new_context_source_grade': fact['source_grade'],
                            'source_url': fact['source_url']})
        assert set(before) <= set(after)
        assert (set(after) - set(before)) <= {context_field}
        for key in before:
            if key not in allowed:
                assert after[key] == before[key], (before['record_id'], key)
        if fact is None:
            assert before == after
        updated.append(after)
    assert [r['record_id'] for r in updated] == [r['record_id'] for r in rows]
    assert len(changes) == len(facts)
    return updated, changes


def load_v11():
    raw = (ROOT / 'inputs' / 'uk_birthplace_rows_v10.jsonl.gz').read_bytes()
    assert hashlib.sha256(raw).hexdigest() == EXPECTED_V10
    v10 = [json.loads(line) for line in gzip.decompress(raw).splitlines()]
    assert len(v10) == 4983
    assert len({row['record_id'] for row in v10}) == 4983
    assert Counter(row['hemisphere'] for row in v10) == {'north': 4155, 'south': 183, 'unknown': 645}
    v11_facts = json_file(ROOT / 'inputs' / 'v11_accepted_context.json')
    assert len(v11_facts) == 3
    v11, _ = apply_context(v10, v11_facts, 'v11')
    assert hashlib.sha256(canonical_bytes(v11)).hexdigest() == EXPECTED_V11_CANONICAL
    assert Counter(row['hemisphere'] for row in v11) == {'north': 4158, 'south': 183, 'unknown': 642}
    window = [row for row in v11 if in_window(row)]
    assert len(window) == 2644
    assert Counter(row['hemisphere'] for row in window) == {'north': 2258, 'south': 178, 'unknown': 208}
    return v11


def load_v12():
    v11 = load_v11()
    v12_facts = json_file(ROOT / 'inputs' / 'v12_accepted_context.json')
    assert len(v12_facts) == 1
    v12, _ = apply_context(v11, v12_facts, 'v12')
    assert hashlib.sha256(canonical_bytes(v12)).hexdigest() == EXPECTED_V12_CANONICAL
    assert Counter(row['hemisphere'] for row in v12) == {'north': 4159, 'south': 183, 'unknown': 641}
    window = [row for row in v12 if in_window(row)]
    assert len(window) == 2644
    assert Counter(row['hemisphere'] for row in window) == {'north': 2259, 'south': 178, 'unknown': 207}
    return v12


def load_v13():
    v12 = load_v12()
    v13_facts = json_file(ROOT / 'inputs' / 'v13_accepted_context.json')
    assert v13_facts == [], 'Frozen v13 accepted context must remain empty'
    v13, _ = apply_context(v12, v13_facts, 'v13')
    assert hashlib.sha256(canonical_bytes(v13)).hexdigest() == EXPECTED_V13_CANONICAL
    assert Counter(row['hemisphere'] for row in v13) == {'north': 4159, 'south': 183, 'unknown': 641}
    window = [row for row in v13 if in_window(row)]
    assert len(window) == 2644
    assert Counter(row['hemisphere'] for row in window) == {'north': 2259, 'south': 178, 'unknown': 207}
    return v13



def load_v14():
    v13 = load_v13()
    v14_facts = json_file(ROOT / 'inputs' / 'v14_accepted_geography.json')
    assert v14_facts == [], 'Frozen v14 principal geography acceptance must remain empty'
    assert hashlib.sha256(canonical_bytes(v13)).hexdigest() == EXPECTED_V14_CANONICAL
    return v13


BIRTHPLACE_FIELDS = {'raw_birthplace', 'birthplace_source_grade', 'birthplace_source_url',
                    'birthplace_source_urls', 'birthplace_claim_excerpt',
                    'birthplace_claim_status', 'birthplace_evidence_kind'}
MUTABLE_OLD_FIELDS = BIRTHPLACE_FIELDS | GEO_FIELDS


def target_ids_from_rows(rows):
    return [row['record_id'] for row in rows
            if row['hemisphere'] == 'unknown' and not row.get('raw_birthplace') and in_window(row)]


def apply_first_birthplaces(rows, facts, target_ids, version, followup_scope):
    """Adopt explicit person-birthplace observations without changing native fields."""
    context_field = 'birthplace_followup_' + version
    assert version in {'v15', 'v16', 'v17', 'v18', 'v19', 'v20', 'v21', 'v22', 'v23'}
    assert isinstance(facts, list)
    by_id = {fact['record_id']: fact for fact in facts}
    assert len(by_id) == len(facts), 'Duplicate accepted birthplace keys'
    assert set(by_id) <= set(followup_scope), 'Accepted key outside fixed original-source followups'
    assert set(by_id) <= set(target_ids), 'Accepted key outside frozen blank-place window'
    row_ids = [row['record_id'] for row in rows]
    assert len(set(row_ids)) == len(row_ids)
    updated, changes = [], []
    for before in rows:
        after = copy.deepcopy(before)
        fact = by_id.get(before['record_id'])
        if fact is not None:
            assert before['hemisphere'] == 'unknown', before['record_id']
            assert not before.get('raw_birthplace'), 'This stage only adopts first stored birthplaces'
            assert before['dob'] == fact['native_dob'], before['record_id']
            assert before['source_authorised_full_name'] == fact['authority_name'], before['record_id']
            if version in {'v19', 'v20', 'v21', 'v22', 'v23'} and not before['source_authorised_full_name']:
                assert isinstance(before.get('name'), str) and before['name'].strip(), 'Current record needs nonempty stored name'
                assert fact.get('native_full_name') == before['name'], 'Blank authority requires exact stored native full name'
            assert context_field not in before
            assert fact['source_grade'] in {'S1', 'S2', 'S3'}
            assert isinstance(fact['raw_birthplace'], str) and fact['raw_birthplace'].strip()
            assert isinstance(fact['source_url'], str) and fact['source_url'].strip()
            source_quote = fact.get('source_quote', '')
            assert isinstance(source_quote, str)
            if version in {'v17', 'v18', 'v19', 'v20', 'v21', 'v22', 'v23'}:
                # A labeled structured birthplace field need not become a prose quote.
                if not source_quote.strip():
                    assert fact.get('evidence_format') == 'structured_birthplace_field', 'Empty quote needs structured-field evidence'
                    assert isinstance(fact.get('source_locator'), str) and fact['source_locator'].strip(), 'Structured field needs an original-source locator'
                assert fact.get('source_birthdate_precision'), 'Explicit source date precision is required'
                assert len(source_quote.split()) <= 25, 'New source quote exceeds25 words'
            else:
                assert source_quote.strip()
                if version == 'v16':
                    assert fact.get('source_birthdate_precision'), 'Explicit source date precision is required'
                    assert len(source_quote.split()) <= 25, 'New source quote exceeds25 words'
            assert fact['identity_review'], 'Reviewed person-source binding is required'
            assert fact['geographic_basis'], 'Geography rationale, including unknown, is required'
            hemisphere = fact['reviewed_hemisphere']
            assert hemisphere in {'north', 'south', 'unknown'}
            source_urls = fact.get('source_urls', [fact['source_url']])
            assert isinstance(source_urls, list) and all(isinstance(u, str) and u.strip() for u in source_urls)
            source_urls = list(dict.fromkeys([fact['source_url'], *source_urls]))
            previous = {key: copy.deepcopy(before[key]) for key in sorted(MUTABLE_OLD_FIELDS) if key in before}
            absent = sorted(MUTABLE_OLD_FIELDS - set(before))
            if 'previous_birthplace_fields' in fact:
                assert fact['previous_birthplace_fields'] == previous, 'Supplied rollback snapshot differs from baseline'
            if 'previous_absent_birthplace_fields' in fact:
                assert fact['previous_absent_birthplace_fields'] == absent
            retained = copy.deepcopy(fact)
            retained['previous_birthplace_fields'] = previous
            retained['previous_absent_birthplace_fields'] = absent
            retained['source_grade_role'] = 'person_birthplace_support_only'
            retained['native_DOB_source_grade_unchanged'] = True
            retained['prior_selected_evidence_kept_as_history'] = True
            after.update(raw_birthplace=fact['raw_birthplace'],
                         birthplace_source_grade=fact['source_grade'],
                         birthplace_source_url=fact['source_url'],
                         birthplace_source_urls=source_urls,
                         birthplace_claim_excerpt=source_quote,
                         birthplace_claim_status='recovered_explicit_birthplace_' + version,
                         birthplace_evidence_kind=version + '_reviewed_explicit_person_birthplace',
                         hemisphere=hemisphere,
                         northern_birthplace_candidate=hemisphere == 'north',
                         southern_birthplace_separate=hemisphere == 'south')
            if hemisphere == 'unknown':
                after.update(geo_resolution_status='unresolved_' + version + '_birthplace_context',
                             geography_decision=version + '_explicit_birthplace_geography_unresolved',
                             reason='new_explicit_birthplace_geography_unresolved')
            else:
                directional = 'northern' if hemisphere == 'north' else 'southern'
                after.update(geo_resolution_status='resolved_by_' + version + '_explicit_birthplace_region',
                             geography_decision=version + '_reviewed_explicit_birthplace_region',
                             reason='explicit_birthplace_context_wholly_' + directional + '_region')
            after[context_field] = retained
            changes.append({'record_id': before['record_id'], 'native_name': before['name'],
                            'dob': before['dob'], 'before_raw_birthplace': before.get('raw_birthplace', ''),
                            'after_raw_birthplace': after['raw_birthplace'],
                            'before_birthplace_source_grade': before.get('birthplace_source_grade', ''),
                            'after_birthplace_source_grade': after['birthplace_source_grade'],
                            'before_hemisphere': before['hemisphere'], 'after_hemisphere': hemisphere,
                            'new_geographic_resolution': hemisphere != 'unknown',
                            'source_url': fact['source_url'],
                            'source_grade_role': 'person_birthplace_support_only',
                            'native_DOB_source_grade_unchanged': True})
        assert set(before) <= set(after), 'Existing fields removed'
        assert (set(after) - set(before)) <= (MUTABLE_OLD_FIELDS | {context_field})
        for key in before:
            if key not in MUTABLE_OLD_FIELDS:
                assert after[key] == before[key], (before['record_id'], key)
        if fact is None:
            assert after == before
        updated.append(after)
    assert [row['record_id'] for row in updated] == row_ids
    assert len(changes) == len(facts)
    return updated, changes


def apply_geography_only(rows, facts, pilot_ids):
    """Resolve existing birthplace geography without changing person/BP evidence."""
    assert isinstance(facts, list)
    by_id = {fact['record_id']: fact for fact in facts}
    assert len(by_id) == len(facts), 'Duplicate geography keys'
    assert set(by_id) <= set(pilot_ids) <= GEOGRAPHY_PILOT_SCOPE
    row_ids = [row['record_id'] for row in rows]
    assert len(row_ids) == len(set(row_ids))
    assert set(by_id) <= set(row_ids)
    updated, changes = [], []
    for before in rows:
        after = copy.deepcopy(before)
        fact = by_id.get(before['record_id'])
        if fact is not None:
            assert before['hemisphere'] == 'unknown'
            assert isinstance(before.get('raw_birthplace'), str) and before['raw_birthplace'].strip()
            assert before['raw_birthplace'] == fact['frozen_raw_birthplace'], 'Stored birthplace must match exactly'
            assert before['dob'] == fact['native_dob']
            assert before['source_authorised_full_name'] == fact['authority_name']
            if not before['source_authorised_full_name']:
                assert isinstance(before.get('name'), str) and before['name'].strip()
                assert fact.get('native_full_name') == before['name']
            assert V20_GEOGRAPHY_FIELD not in before
            assert fact['source_grade'] in {'S1', 'S2', 'S3'}
            assert isinstance(fact.get('source_url'), str) and fact['source_url'].strip()
            assert isinstance(fact.get('source_locator'), str) and fact['source_locator'].strip()
            assert fact['identity_review'] and fact['place_binding_review'] and fact['geographic_basis']
            source_quote = fact.get('source_quote', '')
            assert isinstance(source_quote, str) and len(source_quote.split()) <= 25
            hemisphere = fact['reviewed_hemisphere']
            assert hemisphere in {'north', 'south'}, 'Geography-only acceptance must resolve a hemisphere'
            previous = {key: copy.deepcopy(before[key]) for key in sorted(GEO_FIELDS) if key in before}
            absent = sorted(GEO_FIELDS - set(before))
            if 'previous_geography_fields' in fact:
                assert fact['previous_geography_fields'] == previous
            if 'previous_absent_geography_fields' in fact:
                assert fact['previous_absent_geography_fields'] == absent
            retained = copy.deepcopy(fact)
            retained['previous_geography_fields'] = previous
            retained['previous_absent_geography_fields'] = absent
            retained['source_grade_role'] = 'geographic_support_only'
            retained['native_DOB_source_grade_unchanged'] = True
            retained['original_birthplace_fields_and_source_grades_unchanged'] = True
            directional = 'northern' if hemisphere == 'north' else 'southern'
            after.update(hemisphere=hemisphere,
                         geo_resolution_status='resolved_by_v20_reviewed_authority_birthplace_edge',
                         geography_decision='v20_geography_only_reviewed_authority_birthplace_edge',
                         reason='explicit_birthplace_authority_edge_wholly_' + directional + '_context',
                         northern_birthplace_candidate=hemisphere == 'north',
                         southern_birthplace_separate=hemisphere == 'south')
            after[V20_GEOGRAPHY_FIELD] = retained
            changes.append({'record_id': before['record_id'], 'native_name': before['name'],
                            'dob': before['dob'], 'change_type': 'geography_only',
                            'before_raw_birthplace': before['raw_birthplace'],
                            'after_raw_birthplace': after['raw_birthplace'],
                            'before_birthplace_source_grade': before.get('birthplace_source_grade', ''),
                            'after_birthplace_source_grade': after.get('birthplace_source_grade', ''),
                            'before_hemisphere': before['hemisphere'], 'after_hemisphere': hemisphere,
                            'new_geographic_resolution': True,
                            'geographic_support_grade': fact['source_grade'],
                            'source_url': fact['source_url'],
                            'source_grade_role': 'geographic_support_only',
                            'native_DOB_source_grade_unchanged': True,
                            'original_birthplace_fields_and_source_grades_unchanged': True})
        assert set(before) <= set(after), 'Existing fields removed'
        assert (set(after) - set(before)) <= (GEO_FIELDS | {V20_GEOGRAPHY_FIELD})
        for key in before:
            if key not in GEO_FIELDS:
                assert after[key] == before[key], (before['record_id'], key)
        if fact is None:
            assert after == before
        updated.append(after)
    assert [row['record_id'] for row in updated] == row_ids
    assert len(changes) == len(facts)
    return updated, changes


def load_v15():
    baseline = load_v14()
    target_ids = json_file(ROOT / 'inputs' / 'v15_target_ids.json')
    followup_ids = json_file(ROOT / 'inputs' / 'v15_followup_ids.json')
    assert len(target_ids) == len(set(target_ids)) == 169
    assert target_ids == target_ids_from_rows(baseline)
    assert len(followup_ids) == len(set(followup_ids)) == 8
    assert set(followup_ids) == V15_FOLLOWUP_SCOPE
    facts = json_file(ROOT / 'inputs' / 'v15_accepted_birthplaces.json')
    assert len(facts) == 5
    v15, _ = apply_first_birthplaces(baseline, facts, target_ids, 'v15', V15_FOLLOWUP_SCOPE)
    assert hashlib.sha256(canonical_bytes(v15)).hexdigest() == EXPECTED_V15_CANONICAL
    assert Counter(row['hemisphere'] for row in v15) == {'north': 4162, 'south': 185, 'unknown': 636}
    window = [row for row in v15 if in_window(row)]
    assert len(window) == 2644
    assert Counter(row['hemisphere'] for row in window) == {'north': 2262, 'south': 180, 'unknown': 202}
    assert len(target_ids_from_rows(v15)) == 164
    return v15


def load_v16():
    baseline = load_v15()
    target_ids = json_file(ROOT / 'inputs' / 'v16_target_ids.json')
    followup_ids = json_file(ROOT / 'inputs' / 'v16_followup_ids.json')
    assert len(target_ids) == len(set(target_ids)) == 164
    assert target_ids == target_ids_from_rows(baseline)
    assert len(followup_ids) == len(set(followup_ids)) == 12
    assert set(followup_ids) == V16_FOLLOWUP_SCOPE
    facts = json_file(ROOT / 'inputs' / 'v16_accepted_birthplaces.json')
    assert len(facts) == 5
    v16, _ = apply_first_birthplaces(baseline, facts, target_ids, 'v16', V16_FOLLOWUP_SCOPE)
    assert hashlib.sha256(canonical_bytes(v16)).hexdigest() == EXPECTED_V16_CANONICAL
    assert Counter(row['hemisphere'] for row in v16) == {'north': 4163, 'south': 186, 'unknown': 634}
    window = [row for row in v16 if in_window(row)]
    assert len(window) == 2644
    assert Counter(row['hemisphere'] for row in window) == {'north': 2263, 'south': 181, 'unknown': 200}
    assert len(target_ids_from_rows(v16)) == 159
    return v16



def load_v17():
    baseline = load_v16()
    target_ids = json_file(ROOT / 'inputs' / 'v17_target_ids.json')
    individual_ids = json_file(ROOT / 'inputs' / 'v17_individual_followup_ids.json')
    reviewed_ids = json_file(ROOT / 'inputs' / 'v17_reviewed_record_ids.json')
    assert len(target_ids) == len(set(target_ids)) == 159
    assert target_ids == target_ids_from_rows(baseline)
    assert len(individual_ids) == len(set(individual_ids)) == 8
    assert set(individual_ids) == V17_INDIVIDUAL_FOLLOWUP_SCOPE
    assert len(reviewed_ids) == len(set(reviewed_ids)) == 15
    assert set(reviewed_ids) == V17_REVIEWED_SCOPE
    assert set(individual_ids) <= set(reviewed_ids) <= set(target_ids)
    facts = json_file(ROOT / 'inputs' / 'v17_accepted_birthplaces.json')
    assert len(facts) == 11
    v17, _ = apply_first_birthplaces(baseline, facts, target_ids, 'v17', reviewed_ids)
    assert hashlib.sha256(canonical_bytes(v17)).hexdigest() == EXPECTED_V17_CANONICAL
    assert Counter(row['hemisphere'] for row in v17) == {'north': 4169, 'south': 186, 'unknown': 628}
    window = [row for row in v17 if in_window(row)]
    assert len(window) == 2644
    assert Counter(row['hemisphere'] for row in window) == {'north': 2269, 'south': 181, 'unknown': 194}
    assert len(target_ids_from_rows(v17)) == 148
    return v17


def load_v18():
    baseline = load_v17()
    target_ids = json_file(ROOT / 'inputs' / 'v18_target_ids.json')
    individual_ids = json_file(ROOT / 'inputs' / 'v18_individual_followup_ids.json')
    reviewed_ids = json_file(ROOT / 'inputs' / 'v18_reviewed_record_ids.json')
    assert len(target_ids) == len(set(target_ids)) == 148
    assert target_ids == target_ids_from_rows(baseline)
    assert len(individual_ids) == len(set(individual_ids)) == 8
    assert set(individual_ids) == V18_INDIVIDUAL_FOLLOWUP_SCOPE
    assert len(reviewed_ids) == len(set(reviewed_ids)) == 9
    assert set(reviewed_ids) == V18_REVIEWED_SCOPE
    assert set(individual_ids) <= set(reviewed_ids) <= set(target_ids)
    facts = json_file(ROOT / 'inputs' / 'v18_accepted_birthplaces.json')
    assert len(facts) == 3
    v18, _ = apply_first_birthplaces(baseline, facts, target_ids, 'v18', reviewed_ids)
    assert hashlib.sha256(canonical_bytes(v18)).hexdigest() == EXPECTED_V18_CANONICAL
    assert Counter(row['hemisphere'] for row in v18) == {'north': 4169, 'south': 186, 'unknown': 628}
    window = [row for row in v18 if in_window(row)]
    assert len(window) == 2644
    assert Counter(row['hemisphere'] for row in window) == {'north': 2269, 'south': 181, 'unknown': 194}
    assert len(target_ids_from_rows(v18)) == 145
    return v18


def load_v19():
    baseline = load_v18()
    target_ids = json_file(ROOT / 'inputs' / 'v19_target_ids.json')
    individual_ids = json_file(ROOT / 'inputs' / 'v19_individual_followup_ids.json')
    reviewed_ids = json_file(ROOT / 'inputs' / 'v19_reviewed_record_ids.json')
    assert len(target_ids) == len(set(target_ids)) == 145
    assert target_ids == target_ids_from_rows(baseline)
    assert len(individual_ids) == len(set(individual_ids)) == 12
    assert set(individual_ids) == V19_INDIVIDUAL_FOLLOWUP_SCOPE
    assert len(reviewed_ids) == len(set(reviewed_ids)) == 12
    assert set(reviewed_ids) == V19_INDIVIDUAL_FOLLOWUP_SCOPE
    facts = json_file(ROOT / 'inputs' / 'v19_accepted_birthplaces.json')
    assert len(facts) == 4
    v19, _ = apply_first_birthplaces(baseline, facts, target_ids, 'v19', reviewed_ids)
    assert hashlib.sha256(canonical_bytes(v19)).hexdigest() == EXPECTED_V19_CANONICAL
    assert {row['cohort'] for row in v19} == {'UK_Royal_Society'}
    assert Counter(row['hemisphere'] for row in v19) == {'north': 4171, 'south': 186, 'unknown': 626}
    window = [row for row in v19 if in_window(row)]
    assert len(window) == 2644
    assert Counter(row['hemisphere'] for row in window) == {'north': 2271, 'south': 181, 'unknown': 192}
    assert len(target_ids_from_rows(v19)) == 141
    return v19


def load_v20():
    baseline = load_v19()
    target_ids = json_file(ROOT / 'inputs' / 'v20_target_ids.json')
    individual_ids = json_file(ROOT / 'inputs' / 'v20_individual_followup_ids.json')
    geography_ids = json_file(ROOT / 'inputs' / 'v20_geography_followup_ids.json')
    reviewed_ids = json_file(ROOT / 'inputs' / 'v20_reviewed_record_ids.json')
    assert len(target_ids) == len(set(target_ids)) == 141
    assert target_ids == target_ids_from_rows(baseline)
    assert len(individual_ids) == len(set(individual_ids)) == 8
    assert set(individual_ids) == V20_INDIVIDUAL_FOLLOWUP_SCOPE
    assert len(geography_ids) == len(set(geography_ids)) == 1
    assert set(geography_ids) == GEOGRAPHY_PILOT_SCOPE
    assert not (set(geography_ids) & set(target_ids))
    assert len(reviewed_ids) == len(set(reviewed_ids)) == 9
    assert set(reviewed_ids) == set(individual_ids) | set(geography_ids)
    assert set(individual_ids) <= set(target_ids)
    facts = json_file(ROOT / 'inputs' / 'v20_accepted_birthplaces.json')
    geography_facts = json_file(ROOT / 'inputs' / 'v20_accepted_geography.json')
    assert len(facts) == 4
    assert geography_facts == [], 'Frozen v20 authority-graph pilot has no accepted facts'
    intermediate, _ = apply_first_birthplaces(baseline, facts, target_ids, 'v20', individual_ids)
    v20, _ = apply_geography_only(intermediate, geography_facts, geography_ids)
    assert hashlib.sha256(canonical_bytes(v20)).hexdigest() == EXPECTED_V20_CANONICAL
    assert {row['cohort'] for row in v20} == {'UK_Royal_Society'}
    assert Counter(row['hemisphere'] for row in v20) == {'north': 4172, 'south': 186, 'unknown': 625}
    window = [row for row in v20 if in_window(row)]
    assert len(window) == 2644
    assert Counter(row['hemisphere'] for row in window) == {'north': 2272, 'south': 181, 'unknown': 191}
    assert len(target_ids_from_rows(v20)) == 137
    return v20


def load_v21():
    baseline = load_v20()
    target_ids = json_file(ROOT / 'inputs' / 'v21_target_ids.json')
    individual_ids = json_file(ROOT / 'inputs' / 'v21_individual_followup_ids.json')
    reviewed_ids = json_file(ROOT / 'inputs' / 'v21_reviewed_record_ids.json')
    assert len(target_ids) == len(set(target_ids)) == 137
    assert target_ids == target_ids_from_rows(baseline)
    assert len(individual_ids) == len(set(individual_ids)) == 8
    assert set(individual_ids) == V21_INDIVIDUAL_FOLLOWUP_SCOPE
    assert len(reviewed_ids) == len(set(reviewed_ids)) == 8
    assert set(reviewed_ids) == set(individual_ids)
    assert set(individual_ids) <= set(target_ids)
    facts = json_file(ROOT / 'inputs' / 'v21_accepted_birthplaces.json')
    assert len(facts) == 4
    v21, _ = apply_first_birthplaces(baseline, facts, target_ids, 'v21', individual_ids)
    assert hashlib.sha256(canonical_bytes(v21)).hexdigest() == EXPECTED_V21_CANONICAL
    assert {row['cohort'] for row in v21} == {'UK_Royal_Society'}
    assert Counter(row['hemisphere'] for row in v21) == {'north': 4175, 'south': 187, 'unknown': 621}
    window = [row for row in v21 if in_window(row)]
    assert len(window) == 2644
    assert Counter(row['hemisphere'] for row in window) == {'north': 2275, 'south': 182, 'unknown': 187}
    assert len(target_ids_from_rows(v21)) == 133
    return v21


def load_v22():
    baseline = load_v21()
    target_ids = json_file(ROOT / 'inputs' / 'v22_target_ids.json')
    individual_ids = json_file(ROOT / 'inputs' / 'v22_individual_followup_ids.json')
    reviewed_ids = json_file(ROOT / 'inputs' / 'v22_reviewed_record_ids.json')
    assert len(target_ids) == len(set(target_ids)) == 133
    assert target_ids == target_ids_from_rows(baseline)
    assert len(individual_ids) == len(set(individual_ids)) == 8
    assert set(individual_ids) == V22_INDIVIDUAL_FOLLOWUP_SCOPE
    assert len(reviewed_ids) == len(set(reviewed_ids)) == 8
    assert set(reviewed_ids) == set(individual_ids)
    assert set(individual_ids) <= set(target_ids)
    facts = json_file(ROOT / 'inputs' / 'v22_accepted_birthplaces.json')
    assert len(facts) == 2
    v22, _ = apply_first_birthplaces(baseline, facts, target_ids, 'v22', individual_ids)
    assert hashlib.sha256(canonical_bytes(v22)).hexdigest() == EXPECTED_V22_CANONICAL
    assert {row['cohort'] for row in v22} == {'UK_Royal_Society'}
    assert Counter(row['hemisphere'] for row in v22) == {'north': 4176, 'south': 187, 'unknown': 620}
    window = [row for row in v22 if in_window(row)]
    assert len(window) == 2644
    assert Counter(row['hemisphere'] for row in window) == {'north': 2276, 'south': 182, 'unknown': 186}
    assert len(target_ids_from_rows(v22)) == 131
    return v22


def write_csv(path, rows):
    fields = ['record_id', 'name', 'dob', 'raw_birthplace', 'hemisphere', 'birthplace_source_grade',
              'qualified_context', 'context_source_grade', 'context_source_url', 'context_version',
              'qualified_geography_context', 'geographic_support_grade', 'geography_source_url',
              'geographic_support_grade_role', 'geo_context_version']
    for v in ('v15', 'v16', 'v17', 'v18', 'v19', 'v20'):
        fields.extend([v + '_birthplace', v + '_birthplace_source_grade', v + '_birthplace_source_url',
                       v + '_source_birthdate_precision', v + '_birthplace_grade_role', v + '_context_version'])
    fields.extend(['v20_geographic_context', 'v20_geographic_support_grade',
                   'v20_geography_source_url', 'v20_geographic_support_grade_role',
                   'v20_geo_context_version'])
    fields.extend(['v21_birthplace', 'v21_birthplace_source_grade', 'v21_birthplace_source_url',
                   'v21_source_birthdate_precision', 'v21_birthplace_grade_role', 'v21_context_version'])
    fields.extend(['v22_birthplace', 'v22_birthplace_source_grade', 'v22_birthplace_source_url',
                   'v22_source_birthdate_precision', 'v22_birthplace_grade_role', 'v22_context_version'])
    fields.extend(['v23_birthplace', 'v23_birthplace_source_grade', 'v23_birthplace_source_url',
                   'v23_source_birthdate_precision', 'v23_birthplace_grade_role', 'v23_context_version'])
    buf = io.StringIO(newline='')
    writer = csv.DictWriter(buf, fieldnames=fields, lineterminator='\n')
    writer.writeheader()
    for row in rows:
        version = next((v for v in ('v13', 'v12', 'v11') if 'birthplace_followup_' + v in row), '')
        context = row.get('birthplace_followup_' + version, {})
        geography = row.get(GEOGRAPHY_FIELD, {})
        values = {key: row.get(key, '') for key in fields}
        values.update(qualified_context=context.get('qualified_context', ''),
                      context_source_grade=context.get('source_grade', ''),
                      context_source_url=context.get('source_url', ''), context_version=version,
                      qualified_geography_context=geography.get('qualified_context', ''),
                      geographic_support_grade=geography.get('source_grade', ''),
                      geography_source_url=geography.get('source_url', ''),
                      geographic_support_grade_role=geography.get('source_grade_role', ''),
                      geo_context_version='v14' if geography else '')
        for v in ('v15', 'v16', 'v17', 'v18', 'v19', 'v20', 'v21', 'v22', 'v23'):
            birthplace = row.get('birthplace_followup_' + v, {})
            values.update({v + '_birthplace': birthplace.get('raw_birthplace', ''),
                           v + '_birthplace_source_grade': birthplace.get('source_grade', ''),
                           v + '_birthplace_source_url': birthplace.get('source_url', ''),
                           v + '_source_birthdate_precision': birthplace.get('source_birthdate_precision', ''),
                           v + '_birthplace_grade_role': birthplace.get('source_grade_role', ''),
                           v + '_context_version': v if birthplace else ''})
        new_geography = row.get(V20_GEOGRAPHY_FIELD, {})
        values.update(v20_geographic_context=new_geography.get('qualified_context', new_geography.get('geographic_basis', '')),
                      v20_geographic_support_grade=new_geography.get('source_grade', ''),
                      v20_geography_source_url=new_geography.get('source_url', ''),
                      v20_geographic_support_grade_role=new_geography.get('source_grade_role', ''),
                      v20_geo_context_version='v20' if new_geography else '')
        writer.writerow(values)
    path.write_bytes(buf.getvalue().encode('utf-8'))


def blank_diagnostics(rows):
    window = [row for row in rows if in_window(row)]
    unknown = [row for row in rows if row['hemisphere'] == 'unknown']
    unknown_window = [row for row in window if row['hemisphere'] == 'unknown']
    return {'all_blank_raw_birthplace': sum(not row.get('raw_birthplace') for row in rows),
            'window_blank_raw_birthplace': sum(not row.get('raw_birthplace') for row in window),
            'all_unknown': len(unknown),
            'all_unknown_with_blank_raw_birthplace': sum(not row.get('raw_birthplace') for row in unknown),
            'all_unknown_with_nonblank_raw_birthplace': sum(bool(row.get('raw_birthplace')) for row in unknown),
            'window_unknown': len(unknown_window),
            'window_unknown_with_blank_raw_birthplace': sum(not row.get('raw_birthplace') for row in unknown_window),
            'window_unknown_with_nonblank_raw_birthplace': sum(bool(row.get('raw_birthplace')) for row in unknown_window)}


def write_json(path, value):
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))


def main():
    # Reviewed source/adjudication inputs must exist before any output is published.
    facts = json_file(ROOT / 'inputs' / 'accepted_birthplaces.json')
    holds = json_file(ROOT / 'audit' / 'followup_holds.json')
    target_ids = json_file(ROOT / 'inputs' / 'target_ids.json')
    individual_ids = json_file(ROOT / 'inputs' / 'individual_followup_ids.json')
    reviewed_ids = json_file(ROOT / 'inputs' / 'reviewed_record_ids.json')
    assert isinstance(facts, list) and isinstance(holds, list)
    assert isinstance(target_ids, list) and len(target_ids) == len(set(target_ids)) == 131
    assert isinstance(individual_ids, list) and len(individual_ids) == len(set(individual_ids)) == 12
    assert set(individual_ids) == INDIVIDUAL_FOLLOWUP_SCOPE
    assert isinstance(reviewed_ids, list) and len(reviewed_ids) == len(set(reviewed_ids)) == 12
    assert set(reviewed_ids) == set(individual_ids)
    assert set(individual_ids) <= set(target_ids)
    baseline = load_v22()
    assert target_ids == target_ids_from_rows(baseline), 'Frozen target list differs from reconstructed v22'
    baseline_by_id = {row['record_id']: row for row in baseline}
    assert set(reviewed_ids) <= set(baseline_by_id)
    accepted_ids = [fact['record_id'] for fact in facts]
    held_ids = [hold['record_id'] for hold in holds]
    assert len(set(accepted_ids)) == len(accepted_ids)
    assert len(set(held_ids)) == len(held_ids)
    assert set(accepted_ids) <= set(individual_ids)
    adopted_ids = set(accepted_ids)
    assert not (adopted_ids & set(held_ids)), 'Reviewed key both adopted and held'
    assert adopted_ids | set(held_ids) == set(reviewed_ids)
    updated, birthplace_changes = apply_first_birthplaces(baseline, facts, target_ids, 'v23', individual_ids)
    for change in birthplace_changes:
        change['change_type'] = 'first_birthplace'
    changes = birthplace_changes
    assert len(updated) == 4983 and len({row['record_id'] for row in updated}) == 4983
    assert len(changes) == len(facts)
    new_geographic = [change for change in birthplace_changes if change['after_hemisphere'] != 'unknown']
    new_counts = Counter(change['after_hemisphere'] for change in new_geographic)
    expected = Counter(row['hemisphere'] for row in baseline)
    expected['unknown'] -= len(new_geographic)
    expected.update(new_counts)
    overall = Counter(row['hemisphere'] for row in updated)
    assert overall == expected
    window = [row for row in updated if in_window(row)]
    assert len(window) == 2644
    changed_window_ids = {change['record_id'] for change in new_geographic if in_window(baseline_by_id[change['record_id']])}
    expected_window = Counter(row['hemisphere'] for row in baseline if in_window(row))
    expected_window['unknown'] -= len(changed_window_ids)
    expected_window.update(change['after_hemisphere'] for change in new_geographic if change['record_id'] in changed_window_ids)
    window_counts = Counter(row['hemisphere'] for row in window)
    assert window_counts == expected_window
    unchanged = sum(before == after for before, after in zip(baseline, updated))
    assert unchanged == 4983 - len(adopted_ids)
    remaining_blank = blank_diagnostics(updated)
    assert remaining_blank['window_blank_raw_birthplace'] == 131 - len(facts)
    assert all(after['dob'] == before['dob'] for before, after in zip(baseline, updated))
    summary = {'schema': 'royal_society_birthplace_completion_v23',
               'method': 'twelve fixed first-birthplace original-source followups; no new geography-only pilot',
               'baseline_v22_source_commit': V22_SOURCE_COMMIT,
               'baseline_v22_canonical_jsonl_sha256': EXPECTED_V22_CANONICAL,
               'reconstructed_v11_canonical_jsonl_sha256': EXPECTED_V11_CANONICAL,
               'underlying_v10_gzip_sha256': EXPECTED_V10,
               'records': len(updated), 'counting_unit': 'fixed UK cohort records, not cross-cohort independent persons',
               'frozen_blank_birthplace_target_pool': len(target_ids),
               'fixed_individual_source_followups': len(individual_ids),
               'fixed_existing_place_geography_pilots': 0,
               'actual_unique_reviewed_records': len(reviewed_ids),
               'reviewed_records_outside_blank_birthplace_pool': len(set(reviewed_ids) - set(target_ids)),
               'new_bulk_source_screening_performed': False,
               'scope_count_note': 'The 131-record blank-place pool is an eligibility queue, not 131 biographies read. Twelve fixed individual followups; no geography-only source collection/adoption in this batch.',
               'new_offline_crosscohort_screening_performed': False,
               'new_birthplaces': len(facts), 'new_first_birthplace_records': len(facts),
               'new_primary_person_birthplace_observations': len(facts),
               'new_geographic_resolutions': len(new_geographic), 'newly_classified': len(new_geographic),
               'new_geographic_resolutions_from_new_birthplaces': len(new_geographic),
               'new_geography_only_resolutions': 0,
               'new_birthplaces_with_unresolved_geography': len(facts) - len(new_geographic),
               'new_birthplace_source_grade_counts': dict(Counter(fact['source_grade'] for fact in facts)),
               'new_geographic_support_grade_counts': {},
               'birthplace_source_grade_role': 'person_birthplace_support_only; original DOB tiers unchanged',
               'geographic_support_grade_role': 'no new geography-only facts; all prior support roles unchanged',
               'new_hemisphere_counts': dict(new_counts), 'overall': dict(overall),
               'native_dob_window': '1835-1985 inclusive', 'native_dob_window_records': len(window),
               'native_dob_window_counts': dict(window_counts),
               'newly_classified_in_native_dob_window': len(changed_window_ids),
               'unchanged_complete_rows': unchanged, 'followup_held_records': len(holds),
               'followup_holds': dict(Counter(hold.get('hold_type', 'unresolved') for hold in holds)),
               'target_pool_remaining_without_adopted_birthplace': len(target_ids) - len(facts),
               'remaining_blank_current_fields': remaining_blank,
               'native_fields_and_prior_evidence_preserved': True,
               'all_v11_v12_v13_v14_v15_v16_v17_v18_v19_v20_v21_v22_evidence_objects_preserved': True,
               'original_DOB_source_grades_preserved': True,
               'prior_geography_only_original_birthplace_fields_and_grades_preserved': True,
               'new_birthplace_fields_versioned_with_rollback_snapshots': True,
               'prior_selected_evidence_official_field_status_and_source_hashes_kept_as_history': True,
               'other_cohorts_modified': False, 'country_or_personal_coordinates_assigned': False,
               'DOB_calendar_identity_eligibility_modified': False,
               'cross_cohort_statistical_deduplication': False, 'BaZi_or_outcomes': False, 'final_cohort_freeze': False,
               'gzip_note': 'GzipFile uses empty filename/zero mtime; baseline identity checked with canonical objects.',
               'recovery_note': 'Self-contained UK v10 carrier plus frozen v11-v22 inputs; no comprehensive v8 NAS/DE increment reconstruction.'}
    out = ROOT / 'outputs'
    out.mkdir(exist_ok=True)
    (out / 'birthplace_rows.jsonl.gz').write_bytes(encode_gzip(updated))
    write_json(out / 'summary.json', summary)
    write_json(out / 'changes.json', changes)
    write_csv(out / 'birthplaces.csv', updated)
    write_csv(out / 'remaining_unknown_window.csv', [row for row in window if row['hemisphere'] == 'unknown'])
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    main()
