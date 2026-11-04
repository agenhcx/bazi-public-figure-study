#!/usr/bin/env python3
"""Reconstruct exact UK v12 objects, then apply only reviewed v13 region context.

The committed v10 carrier and frozen v11/v12 inputs are self-contained dependencies.
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
V12_SOURCE_COMMIT = '68f28e93e8c37fb7db585b7309aef97573968220'
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


def write_csv(path, rows):
    fields = ['record_id', 'name', 'dob', 'raw_birthplace', 'hemisphere', 'birthplace_source_grade',
              'qualified_context', 'context_source_grade', 'context_source_url', 'context_version']
    buf = io.StringIO(newline='')
    writer = csv.DictWriter(buf, fieldnames=fields, lineterminator='\n')
    writer.writeheader()
    for row in rows:
        version = next((version for version in ('v13', 'v12', 'v11') if 'birthplace_followup_' + version in row), '')
        fact = row.get('birthplace_followup_' + version, {})
        values = {key: row.get(key, '') for key in fields}
        values.update(qualified_context=fact.get('qualified_context', ''),
                      context_source_grade=fact.get('source_grade', ''),
                      context_source_url=fact.get('source_url', ''), context_version=version)
        writer.writerow(values)
    path.write_text(buf.getvalue(), encoding='utf-8')


def main():
    # Accepted input and hold audit are required. Missing files must not produce a false empty checkpoint.
    facts = json_file(ROOT / 'inputs' / 'accepted_context.json')
    holds = json_file(ROOT / 'audit' / 'holds.json')
    assert isinstance(holds, list)
    accepted_ids = [fact['record_id'] for fact in facts]
    held_ids = [hold['record_id'] for hold in holds]
    assert len(set(held_ids)) == len(held_ids), 'Duplicate held keys'
    assert not (set(accepted_ids) & set(held_ids)), 'Key both accepted and held'
    reviewed_ids = set(accepted_ids) | set(held_ids)
    assert len(reviewed_ids) == 17, 'Expected the seventeen bounded review subjects; prior Jerry Adams pilot is excluded'
    baseline = load_v12()
    baseline_by_id = {row['record_id']: row for row in baseline}
    assert reviewed_ids <= set(baseline_by_id)
    assert all(baseline_by_id[key]['hemisphere'] == 'unknown' for key in reviewed_ids)
    updated, changes = apply_context(baseline, facts, 'v13')
    assert len(updated) == 4983
    assert len({row['record_id'] for row in updated}) == len(updated)
    new_counts = Counter(change['after_hemisphere'] for change in changes)
    expected = Counter(row['hemisphere'] for row in baseline)
    expected['unknown'] -= len(changes)
    expected.update(new_counts)
    overall = Counter(row['hemisphere'] for row in updated)
    assert overall == expected
    window = [row for row in updated if in_window(row)]
    assert len(window) == 2644
    window_counts = Counter(row['hemisphere'] for row in window)
    changed_window_ids = {change['record_id'] for change in changes if in_window(baseline_by_id[change['record_id']])}
    expected_window = Counter(row['hemisphere'] for row in baseline if in_window(row))
    expected_window['unknown'] -= len(changed_window_ids)
    expected_window.update(change['after_hemisphere'] for change in changes if change['record_id'] in changed_window_ids)
    assert window_counts == expected_window
    grade_counts = Counter(fact['source_grade'] for fact in facts)
    hold_counts = Counter(hold.get('hold_type', 'unresolved') for hold in holds)
    unchanged = sum(before == after for before, after in zip(baseline, updated))
    assert unchanged == len(updated) - len(facts)
    summary = {'schema': 'royal_society_birthplace_completion_v13',
               'baseline_v12_source_commit': V12_SOURCE_COMMIT,
               'baseline_v12_canonical_jsonl_sha256': EXPECTED_V12_CANONICAL,
               'reconstructed_v11_canonical_jsonl_sha256': EXPECTED_V11_CANONICAL,
               'underlying_v10_gzip_sha256': EXPECTED_V10,
               'records': len(updated), 'counting_unit': 'fixed UK cohort records',
               'reviewed_records': len(reviewed_ids), 'newly_classified': len(changes),
               'new_explicit_region_context_observations': len(facts),
               'new_first_birthplace_records': 0, 'new_context_source_grades': dict(grade_counts),
               'new_hemisphere_counts': dict(new_counts), 'overall': dict(overall),
               'native_dob_window': '1835-1985 inclusive',
               'native_dob_window_records': len(window), 'native_dob_window_counts': dict(window_counts),
               'newly_classified_in_native_dob_window': len(changed_window_ids),
               'unchanged_complete_rows': unchanged, 'held_records': len(holds), 'holds': dict(hold_counts),
               'native_fields_and_prior_evidence_preserved': True,
               'all_v11_and_v12_evidence_objects_preserved': True,
               'original_birthplace_and_DOB_source_grades_preserved': True,
               'other_cohorts_modified': False, 'country_or_personal_coordinates_assigned': False,
               'DOB_calendar_identity_eligibility_modified': False,
               'cross_cohort_deduplication': False, 'BaZi_or_outcomes': False, 'final_cohort_freeze': False,
               'gzip_note': 'Output uses GzipFile with empty filename and zero mtime; v11/v12 identity uses canonical objects, not cross-Python gzip header equality.',
               'recovery_note': 'Self-contained UK v10 carrier plus frozen v11/v12 contexts; no comprehensive v8 NAS/DE increment reconstruction.'}
    out = ROOT / 'outputs'
    out.mkdir(exist_ok=True)
    (out / 'birthplace_rows.jsonl.gz').write_bytes(encode_gzip(updated))
    (out / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (out / 'changes.json').write_text(json.dumps(changes, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    write_csv(out / 'birthplaces.csv', updated)
    write_csv(out / 'remaining_unknown_window.csv', [row for row in window if row['hemisphere'] == 'unknown'])
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    main()
