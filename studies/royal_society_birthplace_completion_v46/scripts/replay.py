"""Replay the positive V46 first-birthplace overlay on the pinned V44 master.

No historical pipeline is imported. A packaged baseline gzip or existing V44
master is required. Source qualification remains an independently audited act.
"""
from pathlib import Path
from collections import Counter
from datetime import date
import argparse
import copy
import csv
import gzip
import hashlib
import io
import json

ROOT = Path(__file__).resolve().parents[1]
BASELINE_COMMIT = 'cc23cc8d35eb2bfffcbbf041310dd049b308e5ca'
SOURCE_BASELINE_COMMIT = '5ceab58d4ec43f411fc0dfbf016f211e119c234a'
EXPECTED_BASELINE_GZIP = '433749a0b7ff0bfc62db8993f662cd928a4bc023418a54600259fdbea0b1537a'
EXPECTED_BASELINE_CANONICAL = 'a0c04e44631478f82e562deab64d699fc273e6fc99fa35ba23f8a61d7e1f8717'
EXPECTED_SCOPE = '6051c4a3f9887bbba4556595f9dfbbfd8c5bb6ab552d586e9cf67f217597c7bc'
EXPECTED_V44_CODE = 'e7e6e6ced8a9f49b9db0c6a8c3b8bb1c0ab71949d3e6a2a3548292d5c064d1aa'
V46_CONTEXT_FIELD = 'birthplace_followup_v46'
WINDOW_START = date(1835, 1, 1)
WINDOW_END = date(1985, 12, 31)

V36_GEOGRAPHY_FIELD = 'geography_followup_v36'

V35_GEOGRAPHY_FIELD = 'geography_followup_v35'

V34_GEOGRAPHY_FIELD = 'geography_followup_v34'

V33_GEOGRAPHY_FIELD = 'geography_followup_v33'

V32_GEOGRAPHY_FIELD = 'geography_followup_v32'

V31_GEOGRAPHY_FIELD = 'geography_followup_v31'

V30_GEOGRAPHY_FIELD = 'geography_followup_v30'

V20_GEOGRAPHY_FIELD = 'geography_followup_v20'

GEOGRAPHY_FIELD = 'geography_followup_v14'

GEO_FIELDS = {'hemisphere', 'geo_resolution_status', 'geography_decision',
              'reason', 'northern_birthplace_candidate', 'southern_birthplace_separate'}

BIRTHPLACE_FIELDS = {'raw_birthplace', 'birthplace_source_grade', 'birthplace_source_url',
                    'birthplace_source_urls', 'birthplace_claim_excerpt',
                    'birthplace_claim_status', 'birthplace_evidence_kind'}

MUTABLE_OLD_FIELDS = BIRTHPLACE_FIELDS | GEO_FIELDS

V37_GEOGRAPHY_FIELD = 'geography_followup_v37'

V38_GEOGRAPHY_FIELD = 'geography_followup_v38'

V39_GEOGRAPHY_FIELD = 'geography_followup_v39'

V40_GEOGRAPHY_FIELD = 'geography_followup_v40'

V41_GEOGRAPHY_FIELD = 'geography_followup_v41'

V42_GEOGRAPHY_FIELD = 'geography_followup_v42'

V43_GEOGRAPHY_FIELD = 'geography_followup_v43'

V44_GEOGRAPHY_FIELD = 'geography_followup_v44'

def json_file(path):
    return json.loads(path.read_text(encoding='utf-8'))

def write_json(path, value):
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))

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

def apply_first_birthplaces(rows, facts, target_ids, version, followup_scope):
    """Adopt explicit person-birthplace observations without changing native fields."""
    context_field = 'birthplace_followup_' + version
    assert version in {'v15', 'v16', 'v17', 'v18', 'v19', 'v20', 'v21', 'v22', 'v23', 'v24', 'v25', 'v26', 'v27', 'v28', 'v29', 'v46'}
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
            if version in {'v19', 'v20', 'v21', 'v22', 'v23', 'v24', 'v25', 'v26', 'v27', 'v28', 'v29', 'v46'} and not before['source_authorised_full_name']:
                assert isinstance(before.get('name'), str) and before['name'].strip(), 'Current record needs nonempty stored name'
                assert fact.get('native_full_name') == before['name'], 'Blank authority requires exact stored native full name'
            assert context_field not in before
            assert fact['source_grade'] in {'S1', 'S2', 'S3'}
            assert isinstance(fact['raw_birthplace'], str) and fact['raw_birthplace'].strip()
            assert isinstance(fact['source_url'], str) and fact['source_url'].strip()
            source_quote = fact.get('source_quote', '')
            assert isinstance(source_quote, str)
            if version in {'v17', 'v18', 'v19', 'v20', 'v21', 'v22', 'v23', 'v24', 'v25', 'v26', 'v27', 'v28', 'v29', 'v46'}:
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

def write_csv_v46(path, rows):
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
    fields.extend(['v24_birthplace', 'v24_birthplace_source_grade', 'v24_birthplace_source_url',
                   'v24_source_birthdate_precision', 'v24_birthplace_grade_role', 'v24_context_version'])
    fields.extend(['v25_birthplace', 'v25_birthplace_source_grade', 'v25_birthplace_source_url',
                   'v25_source_birthdate_precision', 'v25_birthplace_grade_role', 'v25_context_version'])
    fields.extend(['v26_birthplace', 'v26_birthplace_source_grade', 'v26_birthplace_source_url',
                   'v26_source_birthdate_precision', 'v26_birthplace_grade_role', 'v26_context_version'])
    fields.extend(['v27_birthplace', 'v27_birthplace_source_grade', 'v27_birthplace_source_url',
                   'v27_source_birthdate_precision', 'v27_birthplace_grade_role', 'v27_context_version'])
    fields.extend(['v28_birthplace', 'v28_birthplace_source_grade', 'v28_birthplace_source_url',
                   'v28_source_birthdate_precision', 'v28_birthplace_grade_role', 'v28_context_version'])
    fields.extend(['v29_birthplace', 'v29_birthplace_source_grade', 'v29_birthplace_source_url',
                   'v29_source_birthdate_precision', 'v29_birthplace_grade_role', 'v29_context_version'])
    fields.extend(['v30_geographic_hemisphere', 'v30_geographic_support_grade', 'v30_geography_source_url',
                   'v30_source_birthdate_precision', 'v30_geographic_support_grade_role', 'v30_geo_context_version'])
    fields.extend(['v31_geographic_hemisphere', 'v31_geographic_support_grade', 'v31_geography_source_url',
                   'v31_source_birthdate_precision', 'v31_geographic_support_grade_role', 'v31_geo_context_version'])
    fields.extend(['v32_geographic_hemisphere', 'v32_geographic_support_grade', 'v32_geography_source_url',
                   'v32_source_birthdate_precision', 'v32_geographic_support_grade_role', 'v32_geo_context_version'])
    fields.extend(['v33_geographic_hemisphere', 'v33_geographic_support_grade', 'v33_geography_source_url',
                   'v33_source_birthdate_precision', 'v33_geographic_support_grade_role', 'v33_geo_context_version'])
    fields.extend(['v34_geographic_hemisphere', 'v34_geographic_support_grade', 'v34_geography_source_url',
                   'v34_source_birthdate_precision', 'v34_geographic_support_grade_role', 'v34_geo_context_version'])
    fields.extend(['v35_geographic_hemisphere', 'v35_geographic_support_grade', 'v35_geography_source_url',
                   'v35_source_birthdate_precision', 'v35_geographic_support_grade_role', 'v35_geo_context_version'])
    fields.extend(['v36_geographic_hemisphere', 'v36_geographic_support_grade', 'v36_geography_source_url',
                   'v36_source_birthdate_precision', 'v36_geographic_support_grade_role', 'v36_geo_context_version'])
    fields.extend(['v37_geographic_hemisphere', 'v37_geographic_support_grade', 'v37_geography_source_url',
                   'v37_source_birthdate_precision', 'v37_geographic_support_grade_role', 'v37_geo_context_version'])
    fields.extend(['v38_geographic_hemisphere', 'v38_geographic_support_grade', 'v38_geography_source_url',
                   'v38_source_birthdate_precision', 'v38_geographic_support_grade_role', 'v38_geo_context_version'])
    fields.extend(['v39_geographic_hemisphere', 'v39_geographic_support_grade', 'v39_geography_source_url',
                   'v39_source_birthdate_precision', 'v39_geographic_support_grade_role', 'v39_geo_context_version'])
    fields.extend(['v40_geographic_hemisphere', 'v40_geographic_support_grade', 'v40_geography_source_url',
                   'v40_source_birthdate_precision', 'v40_geographic_support_grade_role', 'v40_geo_context_version'])
    fields.extend(['v41_geographic_hemisphere', 'v41_geographic_support_grade', 'v41_geography_source_url',
                   'v41_source_birthdate_precision', 'v41_geographic_support_grade_role', 'v41_geo_context_version'])
    fields.extend(['v42_geographic_hemisphere', 'v42_geographic_support_grade', 'v42_geography_source_url',
                   'v42_source_birthdate_precision', 'v42_geographic_support_grade_role', 'v42_geo_context_version'])
    fields.extend(['v43_geographic_hemisphere', 'v43_geographic_support_grade', 'v43_geography_source_url',
                   'v43_source_birthdate_precision', 'v43_geographic_support_grade_role', 'v43_geo_context_version'])
    fields.extend(['v44_geographic_hemisphere', 'v44_geographic_support_grade', 'v44_geography_source_url',
                   'v44_source_birthdate_precision', 'v44_geographic_support_grade_role', 'v44_geo_context_version'])
    fields.append(V46_CONTEXT_FIELD)
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
        for v in ('v15', 'v16', 'v17', 'v18', 'v19', 'v20', 'v21', 'v22', 'v23', 'v24', 'v25', 'v26', 'v27', 'v28', 'v29'):
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
        v30_geography = row.get(V30_GEOGRAPHY_FIELD, {})
        values.update(v30_geographic_hemisphere=v30_geography.get('reviewed_hemisphere', ''),
                      v30_geographic_support_grade=v30_geography.get('source_grade', ''),
                      v30_geography_source_url=v30_geography.get('source_url', ''),
                      v30_source_birthdate_precision=v30_geography.get('source_birthdate_precision', ''),
                      v30_geographic_support_grade_role=v30_geography.get('source_grade_role', ''),
                      v30_geo_context_version='v30' if v30_geography else '')
        v31_geography = row.get(V31_GEOGRAPHY_FIELD, {})
        values.update(v31_geographic_hemisphere=v31_geography.get('reviewed_hemisphere', ''),
                      v31_geographic_support_grade=v31_geography.get('source_grade', ''),
                      v31_geography_source_url=v31_geography.get('source_url', ''),
                      v31_source_birthdate_precision=v31_geography.get('source_birthdate_precision', ''),
                      v31_geographic_support_grade_role=v31_geography.get('source_grade_role', ''),
                      v31_geo_context_version='v31' if v31_geography else '')
        v32_geography = row.get(V32_GEOGRAPHY_FIELD, {})
        values.update(v32_geographic_hemisphere=v32_geography.get('reviewed_hemisphere', ''),
                      v32_geographic_support_grade=v32_geography.get('source_grade', ''),
                      v32_geography_source_url=v32_geography.get('source_url', ''),
                      v32_source_birthdate_precision=v32_geography.get('source_birthdate_precision', ''),
                      v32_geographic_support_grade_role=v32_geography.get('source_grade_role', ''),
                      v32_geo_context_version='v32' if v32_geography else '')
        v33_geography = row.get(V33_GEOGRAPHY_FIELD, {})
        values.update(v33_geographic_hemisphere=v33_geography.get('reviewed_hemisphere', ''),
                      v33_geographic_support_grade=v33_geography.get('source_grade', ''),
                      v33_geography_source_url=v33_geography.get('source_url', ''),
                      v33_source_birthdate_precision=v33_geography.get('source_birthdate_precision', ''),
                      v33_geographic_support_grade_role=v33_geography.get('source_grade_role', ''),
                      v33_geo_context_version='v33' if v33_geography else '')
        v34_geography = row.get(V34_GEOGRAPHY_FIELD, {})
        values.update(v34_geographic_hemisphere=v34_geography.get('reviewed_hemisphere', ''),
                      v34_geographic_support_grade=v34_geography.get('source_grade', ''),
                      v34_geography_source_url=v34_geography.get('source_url', ''),
                      v34_source_birthdate_precision=v34_geography.get('source_birthdate_precision', ''),
                      v34_geographic_support_grade_role=v34_geography.get('source_grade_role', ''),
                      v34_geo_context_version='v34' if v34_geography else '')
        v35_geography = row.get(V35_GEOGRAPHY_FIELD, {})
        values.update(v35_geographic_hemisphere=v35_geography.get('reviewed_hemisphere', ''),
                      v35_geographic_support_grade=v35_geography.get('source_grade', ''),
                      v35_geography_source_url=v35_geography.get('source_url', ''),
                      v35_source_birthdate_precision=v35_geography.get('source_birthdate_precision', ''),
                      v35_geographic_support_grade_role=v35_geography.get('source_grade_role', ''),
                      v35_geo_context_version='v35' if v35_geography else '')
        v36_geography = row.get(V36_GEOGRAPHY_FIELD, {})
        values.update(v36_geographic_hemisphere=v36_geography.get('reviewed_hemisphere', ''),
                      v36_geographic_support_grade=v36_geography.get('source_grade', ''),
                      v36_geography_source_url=v36_geography.get('source_url', ''),
                      v36_source_birthdate_precision=v36_geography.get('source_birthdate_precision', ''),
                      v36_geographic_support_grade_role=v36_geography.get('source_grade_role', ''),
                      v36_geo_context_version='v36' if v36_geography else '')
        v37_geography = row.get(V37_GEOGRAPHY_FIELD, {})
        values.update(v37_geographic_hemisphere=v37_geography.get('reviewed_hemisphere', ''),
                      v37_geographic_support_grade=v37_geography.get('source_grade', ''),
                      v37_geography_source_url=v37_geography.get('source_url', ''),
                      v37_source_birthdate_precision=v37_geography.get('source_birthdate_precision', ''),
                      v37_geographic_support_grade_role=v37_geography.get('source_grade_role', ''),
                      v37_geo_context_version='v37' if v37_geography else '')
        v38_geography = row.get(V38_GEOGRAPHY_FIELD, {})
        values.update(v38_geographic_hemisphere=v38_geography.get('reviewed_hemisphere', ''),
                      v38_geographic_support_grade=v38_geography.get('source_grade', ''),
                      v38_geography_source_url=v38_geography.get('source_url', ''),
                      v38_source_birthdate_precision=v38_geography.get('source_birthdate_precision', ''),
                      v38_geographic_support_grade_role=v38_geography.get('source_grade_role', ''),
                      v38_geo_context_version='v38' if v38_geography else '')
        v39_geography = row.get(V39_GEOGRAPHY_FIELD, {})
        values.update(v39_geographic_hemisphere=v39_geography.get('reviewed_hemisphere', ''),
                      v39_geographic_support_grade=v39_geography.get('source_grade', ''),
                      v39_geography_source_url=v39_geography.get('source_url', ''),
                      v39_source_birthdate_precision=v39_geography.get('source_birthdate_precision', ''),
                      v39_geographic_support_grade_role=v39_geography.get('source_grade_role', ''),
                      v39_geo_context_version='v39' if v39_geography else '')
        v40_geography = row.get(V40_GEOGRAPHY_FIELD, {})
        values.update(v40_geographic_hemisphere=v40_geography.get('reviewed_hemisphere', ''),
                      v40_geographic_support_grade=v40_geography.get('source_grade', ''),
                      v40_geography_source_url=v40_geography.get('source_url', ''),
                      v40_source_birthdate_precision=v40_geography.get('source_birthdate_precision', ''),
                      v40_geographic_support_grade_role=v40_geography.get('source_grade_role', ''),
                      v40_geo_context_version='v40' if v40_geography else '')
        v41_geography = row.get(V41_GEOGRAPHY_FIELD, {})
        values.update(v41_geographic_hemisphere=v41_geography.get('reviewed_hemisphere', ''),
                      v41_geographic_support_grade=v41_geography.get('source_grade', ''),
                      v41_geography_source_url=v41_geography.get('source_url', ''),
                      v41_source_birthdate_precision=v41_geography.get('source_birthdate_precision', ''),
                      v41_geographic_support_grade_role=v41_geography.get('source_grade_role', ''),
                      v41_geo_context_version='v41' if v41_geography else '')
        v42_geography = row.get(V42_GEOGRAPHY_FIELD, {})
        values.update(v42_geographic_hemisphere=v42_geography.get('reviewed_hemisphere', ''),
                      v42_geographic_support_grade=v42_geography.get('source_grade', ''),
                      v42_geography_source_url=v42_geography.get('source_url', ''),
                      v42_source_birthdate_precision=v42_geography.get('source_birthdate_precision', ''),
                      v42_geographic_support_grade_role=v42_geography.get('source_grade_role', ''),
                      v42_geo_context_version='v42' if v42_geography else '')
        v43_geography = row.get(V43_GEOGRAPHY_FIELD, {})
        values.update(v43_geographic_hemisphere=v43_geography.get('reviewed_hemisphere', ''),
                      v43_geographic_support_grade=v43_geography.get('source_grade', ''),
                      v43_geography_source_url=v43_geography.get('source_url', ''),
                      v43_source_birthdate_precision=v43_geography.get('source_birthdate_precision', ''),
                      v43_geographic_support_grade_role=v43_geography.get('source_grade_role', ''),
                      v43_geo_context_version='v43' if v43_geography else '')
        v44_geography = row.get(V44_GEOGRAPHY_FIELD, {})
        values.update(v44_geographic_hemisphere=v44_geography.get('reviewed_hemisphere', ''),
                      v44_geographic_support_grade=v44_geography.get('source_grade', ''),
                      v44_geography_source_url=v44_geography.get('source_url', ''),
                      v44_source_birthdate_precision=v44_geography.get('source_birthdate_precision', ''),
                      v44_geographic_support_grade_role=v44_geography.get('source_grade_role', ''),
                      v44_geo_context_version='v44' if v44_geography else '')
        context = row.get(V46_CONTEXT_FIELD)
        values[V46_CONTEXT_FIELD] = json.dumps(context, ensure_ascii=False, sort_keys=True, separators=(',', ':')) if context else ''
        writer.writerow(values)
    path.write_bytes(buf.getvalue().encode('utf-8'))


def file_sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def load_baseline(explicit_path=None):
    if explicit_path is not None:
        path = Path(explicit_path)
        assert path.is_file(), 'Explicit baseline gzip does not exist'
    else:
        carriers = [ROOT / 'inputs/baseline_v44_birthplace_rows.jsonl.gz',
                    ROOT.parent / 'royal_society_birthplace_completion_v44/outputs/birthplace_rows.jsonl.gz']
        path = next((candidate for candidate in carriers if candidate.is_file()), None)
        if path is None:
            raise FileNotFoundError(
                'Pinned V44 master is required: package inputs/baseline_v44_birthplace_rows.jsonl.gz '
                'or regenerate the existing V44 master from repository root with '
                'python -B studies/royal_society_birthplace_completion_v44/scripts/replay.py')
    assert file_sha256(path) == EXPECTED_BASELINE_GZIP, 'V44 baseline gzip changed'
    with gzip.open(path, 'rt', encoding='utf-8') as handle:
        rows = [json.loads(line) for line in handle]
    assert hashlib.sha256(canonical_bytes(rows)).hexdigest() == EXPECTED_BASELINE_CANONICAL, 'V44 canonical master changed'
    assert len(rows) == len({row['record_id'] for row in rows}) == 4983
    return rows


def read_reviewed_inputs():
    pointer = json_file(ROOT / 'audit/source_stage_pointer.json')
    scope_path = ROOT / 'audit/source_scope.json'
    assert file_sha256(scope_path) == pointer['scope_sha256'] == EXPECTED_SCOPE, 'Frozen source scope changed'
    scope = json_file(scope_path)
    assert scope['baseline_commit'] == SOURCE_BASELINE_COMMIT
    assert scope['master_data_commit'] == BASELINE_COMMIT
    assert scope['strategy_not_new_admission_method'] is True
    assert pointer['source_stage_directory'] == 'studies/royal_society_original_source_followup_v46'
    assert pointer['no_new_admission_method_exception'] is True
    for name, pin in [('source_qa.json', 'source_qa_sha256'),
                      ('source_adjudication.json', 'source_adjudication_sha256')]:
        assert file_sha256(ROOT / 'audit' / name) == pointer[pin], name + ' changed'
    qa = json_file(ROOT / 'audit/source_qa.json')
    assert qa['status'].upper() == 'PASS', 'Independent source QA must pass'
    assert qa['scope_sha256'] == EXPECTED_SCOPE
    for name, pin in [('accepted_birthplaces.json', 'accepted_birthplaces_sha256'),
                      ('accepted_geography.json', 'accepted_geography_sha256')]:
        assert file_sha256(ROOT / 'inputs' / name) == pointer[pin], name + ' changed'
    facts = json_file(ROOT / 'inputs/accepted_birthplaces.json')
    geography = json_file(ROOT / 'inputs/accepted_geography.json')
    assert isinstance(facts, list) and [fact['record_id'] for fact in facts] == ['RS_PAST_NA4250']
    assert pointer['accepted_record_ids'] == ['RS_PAST_NA4250']
    assert geography == [], 'This data version has no new geography-only facts'
    assert len(scope['fixed_record_ids']) == len(set(scope['fixed_record_ids'])) == 5
    assert set(pointer['accepted_record_ids']) <= set(scope['initial_blank_ids'])
    for version, authority in scope['inherited_admission_authority'].items():
        assert file_sha256(ROOT / 'audit' / ('inherited_v' + version + '_plan.json')) == authority['sha256'], 'Inherited admission plan changed'
    blocked = {'RS_PAST_NA9209', 'RS_PAST_NA8779'}
    for name, pin in scope['issue_inventory_pins'].items():
        snapshot = ROOT / 'audit' / ('baseline_' + name)
        assert file_sha256(snapshot) == pin, 'Issue inventory changed: ' + name
        if name in {'active_source_DOB_conflicts.json', 'birthplace_source_conflicts.json'}:
            blocked.update(row['record_id'] for row in json_file(snapshot)['records'])
    assert len(scope['issue_inventory_pins']) == 9
    assert not set(pointer['accepted_record_ids']) & blocked, 'Existing issue holds cannot be bypassed'
    # These are bindings to the reviewed actual source fields, not new general
    # admission criteria. No source day/month is invented from its birth year.
    fact = facts[0]
    assert fact['raw_birthplace'] == 'Australia' and fact['source_grade'] == 'S3'
    assert fact['reviewed_hemisphere'] == 'south'
    assert fact['source_birthdate'] == fact['native_dob'][:4] == '1934'
    assert fact['source_birthdate_precision'] == 'year_in_actual_person_lifespan_header'
    assert fact['source_DOB_matches_native_at_stated_precision'] is True
    assert fact['source_independent_exact_native_day_confirmation'] is False
    assert fact['source_grade_role'] == 'person_birthplace_support_only'
    return facts, scope, pointer


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, help='Explicit pinned V44 gzip carrier')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'outputs')
    args = parser.parse_args()
    facts, scope, pointer = read_reviewed_inputs()
    baseline = load_baseline(args.baseline)
    baseline_by_id = {row['record_id']: row for row in baseline}
    targets = [row['record_id'] for row in baseline if in_window(row) and row['hemisphere'] == 'unknown' and not row.get('raw_birthplace')]
    assert len(targets) == 103
    for group, ids in scope['groups'].items():
        assert json_file(ROOT / 'audit' / ('native_scope_' + group + '.json')) == [baseline_by_id[record_id] for record_id in ids], 'Native source-scope objects changed'
    updated, changes = apply_first_birthplaces(baseline, facts, targets, 'v46', scope['fixed_record_ids'])
    adopted = {fact['record_id'] for fact in facts}
    for before, after in zip(baseline, updated):
        if before['record_id'] not in adopted:
            assert after == before, 'Untargeted complete row changed'
            continue
        context = after[V46_CONTEXT_FIELD]
        rolled_back = copy.deepcopy(after)
        rolled_back.update(context['previous_birthplace_fields'])
        for key in context['previous_absent_birthplace_fields']:
            rolled_back.pop(key, None)
        del rolled_back[V46_CONTEXT_FIELD]
        assert rolled_back == before, 'V46 rollback is not exact'
    window = [row for row in updated if in_window(row)]
    overall = dict(Counter(row['hemisphere'] for row in updated))
    window_counts = dict(Counter(row['hemisphere'] for row in window))
    assert len(updated) == 4983 and len(window) == 2644 and len(changes) == 1
    assert overall == {'north': 4205, 'south': 188, 'unknown': 590}
    assert window_counts == {'north': 2305, 'south': 183, 'unknown': 156}
    blanks = blank_diagnostics(updated)
    assert blanks['all_blank_raw_birthplace'] == 524 and blanks['window_blank_raw_birthplace'] == 102
    assert blanks['window_unknown_with_nonblank_raw_birthplace'] == 54
    summary = {
        'schema': 'royal_society_birthplace_completion_v46',
        'method': 'positive first-birthplace overlay using the unchanged V15-V29 original-person admission and V29 mutation/rollback semantics',
        'method_reused_from_version': 29, 'new_admission_method_exception': False,
        'baseline_master_commit': BASELINE_COMMIT, 'source_baseline_commit': SOURCE_BASELINE_COMMIT,
        'baseline_gzip_sha256': EXPECTED_BASELINE_GZIP, 'baseline_canonical_sha256': EXPECTED_BASELINE_CANONICAL,
        'source_scope_sha256': EXPECTED_SCOPE, 'source_qa_sha256': pointer['source_qa_sha256'],
        'accepted_birthplaces_sha256': pointer['accepted_birthplaces_sha256'],
        'accepted_geography_sha256': pointer['accepted_geography_sha256'],
        'records': len(updated), 'counting_unit': 'fixed UK cohort membership records, not deduplicated independent persons',
        'actual_unique_source_reviewed_records': 5, 'new_first_birthplace_records': len(facts),
        'new_geography_only_resolutions': 0, 'new_geographic_resolutions_from_new_birthplaces': 1,
        'new_birthplace_source_grade_counts': dict(Counter(fact['source_grade'] for fact in facts)),
        'source_grade_role': 'person_birthplace_support_only',
        'source_stated_birthdate_precision': '1934 year only; no independent native day confirmation',
        'overall': overall, 'native_dob_window': '1835-1985 inclusive',
        'native_dob_window_records': len(window), 'native_dob_window_counts': window_counts,
        'remaining_blank_current_fields': blanks, 'unchanged_complete_rows': 4982,
        'existing_CSV_columns_preserved': 200, 'CSV_columns': 201,
        'new_CSV_context_column': V46_CONTEXT_FIELD,
        'native_DOB_source_grades_identity_eligibility_and_prior_evidence_preserved': True,
        'country_QIDs_personal_coordinates_and_other_cohorts_modified': False,
        'exact_previous_and_absent_field_rollback_verified': True,
        'historical_pipeline_imported_or_replayed': False,
        'no_analysis_or_final_cohort_freeze': True,
        'replay_note': 'Pinned V44 stored master plus reviewed positive facts; gzip uses empty filename and zero mtime.'}
    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    (out / 'birthplace_rows.jsonl.gz').write_bytes(encode_gzip(updated))
    write_csv_v46(out / 'birthplaces.csv', updated)
    write_csv_v46(out / 'remaining_unknown_window.csv', [row for row in window if row['hemisphere'] == 'unknown'])
    write_json(out / 'summary.json', summary)
    write_json(out / 'changes.json', changes)
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    main()
