#!/usr/bin/env python3
"""Reconstruct exact UK v14 objects, then adopt reviewed first birthplaces.

The v10 carrier and frozen v11/v12/v13/v14 inputs are self-contained.
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
V14_SOURCE_COMMIT = '9a4d6af3681e2ecf024a752dbcfb643951d53844'
FOLLOWUP_SCOPE = {'RS_PAST_NA3607', 'RS_PAST_NA3629', 'RS_PAST_NA3957', 'RS_PAST_NA3652',
                  'RS_PAST_NA4682', 'RS_PAST_NA4250', 'RS_PAST_NA4117', 'RS_PAST_NA4780'}
BIRTHPLACE_FIELD = 'birthplace_followup_v15'
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


def apply_first_birthplaces(rows, facts, bulk_target_ids):
    """Adopt explicit person-birthplace observations without changing native fields."""
    assert isinstance(facts, list)
    by_id = {fact['record_id']: fact for fact in facts}
    assert len(by_id) == len(facts), 'Duplicate accepted birthplace keys'
    assert set(by_id) <= FOLLOWUP_SCOPE, 'Accepted key outside the eight original-source followups'
    assert set(by_id) <= set(bulk_target_ids), 'Accepted key outside frozen blank-place window'
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
            assert BIRTHPLACE_FIELD not in before
            assert fact['source_grade'] in {'S1', 'S2', 'S3'}
            assert isinstance(fact['raw_birthplace'], str) and fact['raw_birthplace'].strip()
            assert isinstance(fact['source_url'], str) and fact['source_url'].strip()
            assert isinstance(fact['source_quote'], str) and fact['source_quote'].strip()
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
                         birthplace_claim_excerpt=fact['source_quote'],
                         birthplace_claim_status='recovered_explicit_birthplace_v15',
                         birthplace_evidence_kind='v15_reviewed_explicit_person_birthplace',
                         hemisphere=hemisphere,
                         northern_birthplace_candidate=hemisphere == 'north',
                         southern_birthplace_separate=hemisphere == 'south')
            if hemisphere == 'unknown':
                after.update(geo_resolution_status='unresolved_v15_birthplace_context',
                             geography_decision='v15_explicit_birthplace_geography_unresolved',
                             reason='new_explicit_birthplace_geography_unresolved')
            else:
                directional = 'northern' if hemisphere == 'north' else 'southern'
                after.update(geo_resolution_status='resolved_by_v15_explicit_birthplace_region',
                             geography_decision='v15_reviewed_explicit_birthplace_region',
                             reason='explicit_birthplace_context_wholly_' + directional + '_region')
            after[BIRTHPLACE_FIELD] = retained
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
        assert (set(after) - set(before)) <= (MUTABLE_OLD_FIELDS | {BIRTHPLACE_FIELD})
        for key in before:
            if key not in MUTABLE_OLD_FIELDS:
                assert after[key] == before[key], (before['record_id'], key)
        if fact is None:
            assert after == before
        updated.append(after)
    assert [row['record_id'] for row in updated] == row_ids
    assert len(changes) == len(facts)
    return updated, changes


def write_csv(path, rows):
    fields = ['record_id', 'name', 'dob', 'raw_birthplace', 'hemisphere', 'birthplace_source_grade',
              'qualified_context', 'context_source_grade', 'context_source_url', 'context_version',
              'qualified_geography_context', 'geographic_support_grade', 'geography_source_url',
              'geographic_support_grade_role', 'geo_context_version',
              'v15_birthplace', 'v15_birthplace_source_grade', 'v15_birthplace_source_url',
              'v15_source_birthdate_precision', 'v15_birthplace_grade_role', 'v15_context_version']
    buf = io.StringIO(newline='')
    writer = csv.DictWriter(buf, fieldnames=fields, lineterminator='\n')
    writer.writeheader()
    for row in rows:
        version = next((v for v in ('v13', 'v12', 'v11') if 'birthplace_followup_' + v in row), '')
        context = row.get('birthplace_followup_' + version, {})
        geography = row.get(GEOGRAPHY_FIELD, {})
        new_birthplace = row.get(BIRTHPLACE_FIELD, {})
        values = {key: row.get(key, '') for key in fields}
        values.update(qualified_context=context.get('qualified_context', ''),
                      context_source_grade=context.get('source_grade', ''),
                      context_source_url=context.get('source_url', ''), context_version=version,
                      qualified_geography_context=geography.get('qualified_context', ''),
                      geographic_support_grade=geography.get('source_grade', ''),
                      geography_source_url=geography.get('source_url', ''),
                      geographic_support_grade_role=geography.get('source_grade_role', ''),
                      geo_context_version='v14' if geography else '',
                      v15_birthplace=new_birthplace.get('raw_birthplace', ''),
                      v15_birthplace_source_grade=new_birthplace.get('source_grade', ''),
                      v15_birthplace_source_url=new_birthplace.get('source_url', ''),
                      v15_source_birthdate_precision=new_birthplace.get('source_birthdate_precision', ''),
                      v15_birthplace_grade_role=new_birthplace.get('source_grade_role', ''),
                      v15_context_version='v15' if new_birthplace else '')
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
    # Required source/adjudication inputs must exist before any output is published.
    facts = json_file(ROOT / 'inputs' / 'accepted_birthplaces.json')
    holds = json_file(ROOT / 'audit' / 'followup_holds.json')
    bulk_target_ids = json_file(ROOT / 'inputs' / 'target_ids.json')
    followup_ids = json_file(ROOT / 'inputs' / 'followup_ids.json')
    assert isinstance(facts, list) and isinstance(holds, list)
    assert isinstance(bulk_target_ids, list) and len(bulk_target_ids) == len(set(bulk_target_ids)) == 169
    assert isinstance(followup_ids, list) and len(followup_ids) == len(set(followup_ids)) == 8
    assert set(followup_ids) == FOLLOWUP_SCOPE
    baseline = load_v14()
    assert bulk_target_ids == target_ids_from_rows(baseline), 'Frozen target list differs from reconstructed v14'
    assert FOLLOWUP_SCOPE <= set(bulk_target_ids)
    accepted_ids = [fact['record_id'] for fact in facts]
    held_ids = [hold['record_id'] for hold in holds]
    assert len(set(accepted_ids)) == len(accepted_ids), 'Duplicate accepted keys'
    assert len(set(held_ids)) == len(held_ids), 'Duplicate followup hold keys'
    assert not (set(accepted_ids) & set(held_ids)), 'Followup key both accepted and held'
    assert set(accepted_ids) | set(held_ids) == FOLLOWUP_SCOPE
    baseline_by_id = {row['record_id']: row for row in baseline}
    updated, changes = apply_first_birthplaces(baseline, facts, bulk_target_ids)
    assert len(updated) == 4983 and len({row['record_id'] for row in updated}) == 4983
    new_geographic = [change for change in changes if change['after_hemisphere'] != 'unknown']
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
    assert unchanged == 4983 - len(facts)
    remaining_blank = blank_diagnostics(updated)
    assert remaining_blank['window_blank_raw_birthplace'] == 169 - len(facts)
    assert all(after['dob'] == before['dob'] for before, after in zip(baseline, updated))
    summary = {'schema': 'royal_society_birthplace_completion_v15',
               'method': 'reviewed first stored birthplaces from new original biographical sources; separate offline evidence screening',
               'baseline_v14_source_commit': V14_SOURCE_COMMIT,
               'baseline_v14_canonical_jsonl_sha256': EXPECTED_V14_CANONICAL,
               'reconstructed_v11_canonical_jsonl_sha256': EXPECTED_V11_CANONICAL,
               'underlying_v10_gzip_sha256': EXPECTED_V10,
               'records': len(updated), 'counting_unit': 'fixed UK cohort records, not cross-cohort independent persons',
               'bulk_screened_records': len(bulk_target_ids), 'targeted_source_followups': len(FOLLOWUP_SCOPE),
               'bulk_screening_count_note': 'Frozen 169-target offline screening is retained separately in audit; not a claim of 169 original biographical bodies read.',
               'new_birthplaces': len(facts), 'new_first_birthplace_records': len(facts),
               'new_primary_person_birthplace_observations': len(facts),
               'new_geographic_resolutions': len(new_geographic), 'newly_classified': len(new_geographic),
               'new_birthplaces_with_unresolved_geography': len(facts) - len(new_geographic),
               'new_birthplace_source_grade_counts': dict(Counter(fact['source_grade'] for fact in facts)),
               'birthplace_source_grade_role': 'person_birthplace_support_only; original DOB tiers unchanged',
               'new_hemisphere_counts': dict(new_counts), 'overall': dict(overall),
               'native_dob_window': '1835-1985 inclusive', 'native_dob_window_records': len(window),
               'native_dob_window_counts': dict(window_counts),
               'newly_classified_in_native_dob_window': len(changed_window_ids),
               'unchanged_complete_rows': unchanged, 'followup_held_records': len(holds),
               'followup_holds': dict(Counter(hold.get('hold_type', 'unresolved') for hold in holds)),
               'bulk_targets_remaining_without_adopted_birthplace': len(bulk_target_ids) - len(facts),
               'remaining_blank_current_fields': remaining_blank,
               'native_fields_and_prior_evidence_preserved': True,
               'all_v11_v12_v13_v14_evidence_objects_preserved': True,
               'original_DOB_source_grades_preserved': True,
               'new_birthplace_fields_versioned_with_rollback_snapshots': True,
               'prior_selected_evidence_official_field_status_and_source_hashes_kept_as_history': True,
               'other_cohorts_modified': False, 'country_or_personal_coordinates_assigned': False,
               'DOB_calendar_identity_eligibility_modified': False,
               'cross_cohort_statistical_deduplication': False, 'BaZi_or_outcomes': False, 'final_cohort_freeze': False,
               'gzip_note': 'GzipFile uses empty filename/zero mtime; baseline identity checked with canonical objects.',
               'recovery_note': 'Self-contained UK v10 carrier plus frozen v11/v12/v13/v14 inputs; no comprehensive v8 NAS/DE increment reconstruction.'}
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
